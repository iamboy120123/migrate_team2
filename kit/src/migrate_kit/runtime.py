"""Pinned simulation runtime. Produces a rehearsal bundle, never ODI Smart Export."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .engine import compare_rows, convert, evaluate, identifier, make_dml
from .storage import WorkspaceError, digest, fingerprint, inside, now, read, text, write
from .workspace import verify_pin, verify_snapshot


def apply_rows(task, columns, incoming, existing):
    strategy = task["strategy"]
    if strategy == "append":
        return existing + incoming
    if strategy == "overwrite":
        return list(incoming)
    keys = [columns.index(identifier(x)) for x in task["merge_keys"]]
    def key(row):
        value = tuple(row[index] for index in keys)
        if any(x is None for x in value):
            raise WorkspaceError("NULL merge keys are outside the simulation contract")
        return value
    result = {key(row): row for row in existing}
    if len(result) != len(existing) or len({key(row) for row in incoming}) != len(incoming):
        raise WorkspaceError("Duplicate merge keys: review source/target uniqueness")
    result.update({key(row): row for row in incoming})
    return list(result.values())


def run(root, job):
    root, job = Path(root).resolve(), Path(job).resolve()
    if not job.is_relative_to(root / "projects"):
        raise WorkspaceError("Runtime can write only to a job within this workspace")
    verify_pin(root, job)
    meta = read(job / "job.json")
    if meta.get("mode") != "simulation" or meta.get("production_import_allowed") is not False:
        raise WorkspaceError("This runtime is simulation-only")
    pin = read(job / "kit.lock.json")
    current = fingerprint(job)
    gates = {"G0": "NOT_RUN", "G1": "NOT_RUN", "G2": "NOT_RUN", "G3": "NOT_RUN",
             "G4": "NOT_EXECUTED", "G5": "NOT_EXECUTED", "G6": "NOT_EXECUTED", "G7": "NOT_EXECUTED"}
    generated, checks = [], []
    def save_text(rel, value):
        path = inside(job, rel); text(path, value); generated.append(rel)
    def save_json(rel, value):
        path = inside(job, rel); write(path, value); generated.append(rel)
    state, error = "SIMULATION_FAILED", None
    try:
        target = root / "shared/target/snapshots" / pin["target_snapshot"]
        verify_snapshot(root, pin["target_snapshot"])
        cfg = read(job / "config/config.json")
        if cfg.get("mode") != "simulation" or cfg.get("db_mode") != "human":
            raise WorkspaceError("Simulation config must keep DB execution in human mode")
        workflow = read(job / "input/blendata/export_workflow.json")
        fixture = read(inside(target, cfg["fixture"]))
        with (target / "columns/all_tab_columns.csv").open(encoding="utf-8-sig", newline="") as stream:
            schema = {}
            for row in csv.DictReader(stream):
                schema.setdefault(identifier(row["TABLE_NAME"]), []).append(identifier(row["COLUMN_NAME"]))
        tasks = workflow["tasks"]
        if not tasks or len({task["task_id"] for task in tasks}) != len(tasks):
            raise WorkspaceError("Workflow must have unique task IDs")
        if len({task["target_table"].upper() for task in tasks}) != len(tasks):
            raise WorkspaceError("Demo requires one target table per task")
        for task in tasks:
            identifier(task["task_id"])
            if task["target_columns"] != schema.get(identifier(task["target_table"])):
                raise WorkspaceError(f"{task['task_id']}: target columns differ from the pinned schema")
        gates["G0"] = "OFFLINE_FIXTURE_CHECK_PASS"
        approved = any(a.get("state") == "SIMULATED_APPROVAL" and a.get("gate") == "G2" and
                       a.get("fingerprint") == current and a.get("reviewer") in
                       read(root / "shared/approvers.json")["simulation_reviewers"]
                       for a in read(job / "status/approvals.json")["approvals"])
        if not approved:
            gates["G2"] = "BLOCKED_REVIEW_REQUIRED"
            state = "BLOCKED_REVIEW_REQUIRED"
            raise WorkspaceError("Missing or stale simulated review. Run approve --simulation after reviewing changed inputs.")
        gates["G2"] = "SIMULATED_APPROVAL"
        plan = ET.Element("MigrationSimulationPlan", {"formatVersion": "1", "importableInODI": "false",
                              "workflow": workflow["workflow_name"], "package": cfg["package_name"],
                              "kitVersion": pin["kit_version"], "inputFingerprint": current})
        ET.SubElement(plan, "Warning").text = "OFFLINE SIMULATION. NOT AN ODI SMART EXPORT. DO NOT IMPORT."
        steps, sql_report, dml_files = [], [], []
        for number, task in enumerate(tasks, 1):
            tid = identifier(task["task_id"])
            sql = convert(task["sql"])
            raw_rel = f"output/sql/raw/{tid}.sql"
            converted_rel = f"output/sql/converted/{tid}.sql"
            save_text(raw_rel, task["sql"] + "\n")
            save_text(converted_rel, sql + "\n")
            dml = make_dml(task, sql)
            task_element = ET.SubElement(plan, "Task", {"id": tid, "strategy": task["strategy"],
                                                        "demoObjectId": str(meta["id_base"] + number)})
            for step_number, statement in enumerate(dml, 1):
                rel = f"output/dml/{tid}_{step_number:02d}.sql"
                save_text(rel, statement + "\n")
                dml_files.append(rel)
                ET.SubElement(task_element, "Step", {"order": str(step_number), "sqlFile": rel}).text = statement
            columns, actual = evaluate(sql, fixture["sources"])
            if columns != task["target_columns"]:
                raise WorkspaceError(f"{tid}: SELECT column order/names differ from target")
            if not actual:
                raise WorkspaceError(f"{tid}: zero fixture rows is not sufficient evidence")
            expected = fixture["tasks"][tid]
            first = apply_rows(task, columns, actual, expected["initial_target"])
            second = apply_rows(task, columns, actual, first)
            passed = compare_rows(actual, expected["selected_rows"]) and compare_rows(first, expected["after_first_run"]) and compare_rows(second, expected["after_second_run"])
            checks.append({"task": tid, "strategy": task["strategy"], "rows_selected": len(actual),
                           "selected_rows": actual, "after_first_run": first, "after_second_run": second,
                           "pass": passed, "evaluator": "SQLite portable subset + Python load-strategy model",
                           "spark_executed": False, "oracle_executed": False})
            steps.append(tid)
            sql_report.append(f"| {tid} | {task['strategy']} | {len(actual)} | {'PASS' if passed else 'FAIL'} |")
        gates["G1"] = "OFFLINE_SUBSET_CHECK_PASS"
        if not all(row["pass"] for row in checks):
            raise WorkspaceError("Fixture comparison mismatch; generated SQL/strategy must be reviewed")
        save_json("output/validation/fixture_comparison.json", {"mode": "simulation", "checks": checks,
                    "scope": "Curated synthetic expectations, not measured Blendata or Oracle outputs"})
        save_text("output/validation/REPORT.md", "# Fixture comparison\n\nSIMULATION ONLY. SQLite is not Spark or Oracle.\n\n"
                  "| Task | Strategy | Selected fixture rows | Fixture + rerun check |\n|---|---|---|---|\n" + "\n".join(sql_report) +
                  "\n\nAppend intentionally adds rows again; upsert and overwrite are stable for these fixtures.\n")
        xml = ET.tostring(plan, encoding="unicode", xml_declaration=True)
        if ET.fromstring(xml).get("importableInODI") != "false":
            raise WorkspaceError("Missing non-importable simulation marker")
        save_text("output/odi_export/package.simulation.xml", xml + "\n")
        save_text("output/odi_export/README.md", "# Simulation bundle\n\nNOT ODI SMART EXPORT. DO NOT IMPORT INTO ODI.\n"
                  "This bundle rehearses packaging, traceability and checksums. Native ODI object generation is not implemented.\n")
        save_text("run_packs/rp01_validation/V1_counts.sql", "-- Rehearsal only; never executed by this workspace.\n" +
                  "\n\n".join(f"SELECT COUNT(*) AS ROW_COUNT FROM {identifier(task['target_table'])}" for task in tasks) + "\n")
        save_text(".design/03_package_flow.md", "# Simulated package flow\n\n" + " → ".join(steps) +
                  "\n\nDAG scheduling, ODI variable refresh and error routing are outside this demo.\n")
        save_text("status/BUSINESS_RULES.md", "# Synthetic business rules\n\nSIMULATED REVIEW ONLY.\n\n" +
                  "\n".join(f"- BR-{i:02d} / {t['task_id']}: {t['business_rule']} (strategy: {t['strategy']})" for i, t in enumerate(tasks, 1)) + "\n")
        save_text("status/SQL_REVIEW.md", "# Simulation review\n\nSIMULATED_APPROVAL; no real SA approval.\n\n"
                  f"Input fingerprint: `{current}`\n\n" + "\n".join(sql_report) + "\n")
        bundle_manifest = {"mode": "simulation", "native_odi_smart_export": False, "import_allowed": False,
                           "kit": pin, "input_fingerprint": current, "tasks": steps,
                           "files": {rel: digest(job / rel) for rel in generated}}
        save_json("output/odi_export/build-manifest.json", bundle_manifest)
        bundle_rel = f"output/odi_export/{identifier(cfg['package_name'])}.simulation.zip"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            # Explicit manifest list; obsolete files from earlier runs are never packaged.
            for rel in generated:
                info = zipfile.ZipInfo(rel, (2026, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, (job / rel).read_bytes())
        (job / bundle_rel).write_bytes(buffer.getvalue()); generated.append(bundle_rel)
        gates["G3"] = "SIMULATION_BUNDLE_CHECK_PASS"
        state = "SIMULATION_PASSED"
    except (WorkspaceError, KeyError, ValueError, OSError, sqlite3.Error) as exc:
        error = str(exc)
    save_text("status/GATES.md", "# Gate evidence\n\nSIMULATION ONLY — this is not production gate approval.\n\n"
              "| Gate | Result |\n|---|---|\n" + "\n".join(f"| {gate} | {value} |" for gate, value in gates.items()) +
              "\n\nG4 real import, G5 real comparison, G6 cutover, G7 go-live remain NOT EXECUTED.\n")
    if checks and state != "SIMULATION_PASSED":
        save_json("output/validation/fixture_comparison.json", {"mode": "simulation", "checks": checks, "error": error})
    result = {"mode": "simulation", "state": state, "fingerprint": current, "at": now(), "gates": gates,
              "error": error, "production_import_allowed": False, "real_systems_executed": [],
              "outputs": {rel: digest(inside(job, rel)) for rel in generated}}
    write(job / "status/simulation.json", result)
    print(f"{meta['project']}/{meta['job']}: {state}")
    if error:
        print("  " + error)
    return result


def main():
    try:
        result = run(Path(sys.argv[1]), Path(sys.argv[2]))
        raise SystemExit(0 if result["state"] == "SIMULATION_PASSED" else 1)
    except (WorkspaceError, OSError, ValueError) as exc:
        print("ERROR: " + str(exc)); raise SystemExit(1)


if __name__ == "__main__":
    main()
