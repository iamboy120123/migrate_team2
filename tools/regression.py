"""Regression baselines from real, already-verified migration jobs (gap W-12).

A baseline freezes one job of the production kit (Migrate_ODI_Team2) so that porting its
runtime into migrate_kit 0.2.0 can be proven equal, file by file.

Layers stored in the baseline archive (paths relative to the job):
  input       governed inputs: Blendata export, test files, d1 seeds, target columns, Smart Export reference, config
  machine     what the converter produces by itself today (re-generated at capture time) → `_machine/…`
  reviewed    Phase-4 reviewed converted SQL + review logs (what was compiled on DEV)
  derived     DML / DDL / DBA / ODI export generated from the reviewed SQL
  runpack     generated Run Packs
  evidence    run results, verify reports, Spark D1 results, DB/GATE logs
  provenance  the job's kit scripts and AI context (.claude agents/commands/rules/skills, CLAUDE.md) as used
              — 2.15.0 plus local patches — and the .ws_kit.json sync record

Commands (run from the migrate_team2 root):
  python tools/regression.py capture --job <job folder> --name ss_esim [--note "…"] [--source-label <path>]
  python tools/regression.py verify  --name ss_esim
  python tools/regression.py replay  --name ss_esim [--scripts <folder with scripts/>] [--keep]

The archive (`tests/regression/<name>/baseline.zip`) holds customer metadata and stays out of Git
(.gitignore); `BASELINE.json` (paths, sizes, SHA-256, provenance — no content) is committed.
Comparisons use normalized text: CRLF→LF, and generation timestamps / export salts masked.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "tests" / "regression"
MACHINE = "_machine/"
ZIP_TIME = (2026, 1, 1, 0, 0, 0)

# (layer, glob) — first match wins; anything unmatched is not captured
LAYERS = [
    ("input", "input/blendata/*"), ("input", "input/d1_seeds/*"), ("input", "input/d1_spec.json"),
    ("input", "input/oracle_ddl/*"), ("input", "input/odi_reference/*"), ("input", "config/*"),
    ("reviewed", "output/sql/converted/*"),
    ("reviewed", "status/REVIEW_FLAGS.md"), ("reviewed", "status/PHASE4_REVIEW_LOG.md"), ("reviewed", "status/SQL_REVIEW.md"),
    ("reviewed", "status/OPEN_DECISIONS.md"), ("reviewed", "status/BUSINESS_RULES.md"), ("reviewed", "status/GAP_ANALYSIS.md"),
    ("machine", "output/sql/raw/*"),
    ("derived", "output/dml/*"), ("derived", "output/ddl/*"), ("derived", "output/dba/*"),
    ("derived", "output/odi_export/PROJ_EXPORT.xml"), ("derived", "output/odi_export/PKG_*.zip"),
    ("derived", "output/odi_export/build-spec.json"), ("derived", "output/odi_export/_guid_keys.json"),
    ("derived", "output/odi_export/_guid_map.json"), ("derived", "output/odi_export/converted-sql/*"),
    ("runpack", "run_packs/**"),
    ("evidence", "input/run_results/**"), ("evidence", "output/verify/*"), ("evidence", "output/d1/**"),
    ("evidence", "status/DB_RUN_LOG.md"), ("evidence", "status/GATES.md"), ("evidence", "status/DEPLOY_LOG.md"),
    ("evidence", "status/IMPORT_LOG.md"), ("evidence", "status/MIGRATION_STATUS.md"), ("evidence", "status/PREFLIGHT_CHECKLIST.md"),
    ("evidence", "status/INTAKE.md"), ("evidence", "status/HANDOVER.md"), ("evidence", "status/SUMMARY_04_PACKAGE.md"),
    ("provenance", "scripts/**"), ("provenance", ".ws_kit.json"),
    ("provenance", ".claude/agents/*"), ("provenance", ".claude/commands/*"), ("provenance", ".claude/rules/*"),
    ("provenance", ".claude/skills/**"), ("provenance", ".claude/workflows/*"), ("provenance", "CLAUDE.md"),
]
SKIP_PARTS = {"__pycache__", "_deprecated", ".dbx", "spark-warehouse"}
SKIP_NAMES = ("*.pyc", "*.png", "*.jpg", "*.bak", "*.bak-*")
TEXT_EXT = {".sql", ".md", ".json", ".xml", ".txt", ".csv", ".py", ".js", ".mmd", ".yaml", ".yml"}
# generation timestamps only — business dates in inputs/run packs are never masked (masking applies to machine/derived)
MASKS = [
    (re.compile(r"(?i)(generated[^\n0-9]{0,30})\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?"), r"\1<TS>"),
    (re.compile(r"(?i)((?:DRAFT|Target DDL)[^\n0-9]{0,30}\(?)\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?"), r"\1<TS>"),
    (re.compile(r'Created="[^"]*"'), 'Created="<TS>"'),
    (re.compile(r'exportKeySalt="[^"]*"'), 'exportKeySalt="<SALT>"'),
    (re.compile(r'(type="java\.sql\.Timestamp"><!\[CDATA\[)[^\]]*(\]\])'), r"\1<TS>\2"),
    (re.compile(r'("(?:generated_at|generated|created_at|built_at|timestamp)"\s*:\s*)"[^"]*"'), r'\1"<TS>"'),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"), "<TS>"),       # ISO stamps written by generators
]
MASKED_LAYERS = {"machine", "derived", "runpack"}
COMPARE_STEPS = [  # (script under scripts/, args, output globs compared after the step)
    ("pipeline/extract_workflow.py", [], ["output/sql/raw/*"]),
    ("pipeline/convert_sql.py", [], ["output/sql/converted/*"]),
    ("pipeline/gen_dml.py", [], ["output/dml/*"]),
    ("pipeline/gen_ddl.py", [], ["output/ddl/*"]),
    ("pipeline/gen_dba_prereq.py", [], ["output/dba/*"]),
    ("pipeline/build_odi_export.py", [], ["output/odi_export/PROJ_EXPORT.xml", "output/odi_export/PKG_*.zip",
                                          "output/odi_export/build-spec.json", "output/odi_export/_guid_keys.json",
                                          "output/odi_export/_guid_map.json", "output/odi_export/converted-sql/*"]),
]


def steps_for(members: dict) -> list:
    """Fixed pipeline steps + Run Pack steps for the packs this job actually has (not tied to one job)."""
    steps = list(COMPARE_STEPS)
    names = {n.split("/")[1] for n in members if n.startswith("run_packs/") and n.count("/") >= 2}
    if any(n.startswith("rp00_preflight_") for n in names):
        steps.append(("runpack/gen_preflight_pack.py", [], ["run_packs/rp00_preflight_*/*"]))
    for base in sorted({re.match(r"(rp\d+)_\d{8}$", n).group(1) for n in names if re.match(r"rp\d+_\d{8}$", n)}):
        packs = sorted(n for n in names if re.match(rf"{base}_\d{{8}}$", n))
        if any(n == f"run_packs/{packs[-1]}/MANIFEST.json" for n in members):
            steps.append(("runpack/gen_run_pack.py", ["--pack", base], [f"run_packs/{base}_*/*", "!run_packs/*/REPORT.md"]))
        if any(n == f"run_packs/{packs[-1]}/REPORT.md" for n in members):
            steps.append(("runpack/read_run_results.py", ["--pack", f"run_packs/{packs[-1]}"], [f"run_packs/{packs[-1]}/REPORT.md"]))
    return steps


class RegressionError(Exception):
    pass


# ---------------------------------------------------------------- hashing / normalization
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(rel: str, data: bytes, layer: str) -> bytes:
    if rel.lower().endswith(".zip"):
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in sorted(z.namelist()):
                out.write(name.encode() + b"\0" + normalize(name, z.read(name), layer) + b"\0")
        return out.getvalue()
    if Path(rel).suffix.lower() not in TEXT_EXT:
        return data
    text = data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    if layer in MASKED_LAYERS:
        for rx, rep in MASKS:
            text = rx.sub(rep, text)
    return text.encode("utf-8")


def layer_of(rel: str) -> str | None:
    parts = rel.split("/")
    if SKIP_PARTS.intersection(parts) or any(fnmatch.fnmatch(parts[-1], p) for p in SKIP_NAMES):
        return None
    for layer, pattern in LAYERS:
        if fnmatch.fnmatch(rel, pattern) or (pattern.endswith("/**") and rel.startswith(pattern[:-2])):
            return layer
    return None


def job_files(job: Path) -> dict[str, str]:
    files = {}
    for p in sorted(job.rglob("*")):
        if p.is_file():
            rel = p.relative_to(job).as_posix()
            layer = layer_of(rel)
            if layer:
                files[rel] = layer
    return files


# ---------------------------------------------------------------- archive
def write_archive(path: Path, members: dict[str, bytes]) -> str:
    """Deterministic, uncompressed (STORED) ZIP — same bytes on every machine/zlib."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            z.writestr(info, members[name])
    blob = buf.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    return sha(blob)


def _show(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def read_archive(name: str) -> tuple[dict, dict[str, bytes]]:
    folder = BASE_DIR / name
    meta_path, zpath = folder / "BASELINE.json", folder / "baseline.zip"
    if not meta_path.is_file():
        raise RegressionError(f"No baseline manifest: {_show(meta_path)}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not zpath.is_file():
        raise RegressionError(f"Baseline archive is not on this machine: {_show(zpath)} "
                              f"(kept out of Git; copy it from the team share — expected SHA-256 {meta['archive_sha256']})")
    blob = zpath.read_bytes()
    if sha(blob) != meta["archive_sha256"]:
        raise RegressionError(f"{_show(zpath)} does not match BASELINE.json — restore the original archive")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return meta, {n: z.read(n) for n in z.namelist()}


# ---------------------------------------------------------------- reference pipeline
def run_script(job: Path, scripts: Path, script: str, args=()) -> tuple[int, str]:
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", str(scripts / script), *args], cwd=job, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=600)
    return r.returncode, (r.stdout + r.stderr)[-2000:]


def materialize(members: dict[str, bytes], dest: Path, include_machine=False):
    for name, data in members.items():
        if name.startswith(MACHINE) and not include_machine:
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


# ---------------------------------------------------------------- capture / replay core
# outputs that the next run also reads: GUID continuity and manual (non-SQL task) entries in the DML manifest
STATE_KEEP = {"output/odi_export/_guid_keys.json", "output/odi_export/_guid_map.json", "output/dml/_manifest.json"}


def _expected(meta: dict) -> tuple[dict, set, set]:
    rows = {r["path"]: r for r in meta["files"]}
    return rows, set(meta.get("manual_files", [])), set(meta.get("edited_files", []))


def run_pipeline(meta: dict, members: dict[str, bytes], work: Path, classify: bool = False) -> tuple[list, dict]:
    """Run every reference step in `work` and compare its outputs with the baseline.

    Each step first deletes the files it should produce (except STATE_KEEP and known manual files), so a
    stale copy can never count as a match. Files people edited after generation ("edited") are compared
    with the generator's own output stored under `_machine/`, then the edited version is put back so the
    next step continues from what the real job used — exactly like Phase-4 reviewed SQL.

    classify=True (capture): MISSING outputs are hand-written → "manual" (restored, step rerun);
    DIFF outputs were edited after generation → "edited" (generator bytes returned for `_machine/`).
    """
    rows, manual, edited = _expected(meta)
    steps, found = [], {"manual": [], "edited": {}}
    status_files = {n: d for n, d in members.items() if n.startswith("status/")}

    def matched(patterns):
        inc = [p for p in patterns if not p.startswith("!")]
        exc = [p[1:] for p in patterns if p.startswith("!")]
        keep = lambda rel: any(fnmatch.fnmatch(rel, p) for p in inc) and not any(fnmatch.fnmatch(rel, p) for p in exc)
        return keep, {p.relative_to(work).as_posix() for pat in inc for p in work.glob(pat) if p.is_file()}

    def compare(patterns):
        out = []
        keep, actual = matched(patterns)
        actual = {rel for rel in actual if keep(rel)}
        expect = {p for p in rows if not p.startswith(MACHINE) and keep(p)}
        for rel in sorted(expect | actual):
            if rel not in expect:
                out.append({"path": rel, "result": "EXTRA"}); continue
            if not (work / rel).is_file():
                out.append({"path": rel, "result": "MISSING"}); continue
            ref = rows.get(MACHINE + rel, rows[rel]) if rel in edited else rows[rel]
            got = sha(normalize(rel, (work / rel).read_bytes(), ref["layer"]))
            out.append({"path": rel, "result": "OK" if got == ref["norm_sha256"] else "DIFF"})
        return out

    def restore(paths):
        for rel in paths:
            if rel in members:
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                (work / rel).write_bytes(members[rel])

    for script, args, patterns in steps_for(members):
        keep, present = matched(patterns)
        for rel in present:
            if keep(rel) and rel not in STATE_KEEP and rel not in manual and rel not in found["manual"]:
                (work / rel).unlink()
        code, out = run_script(work, work / "scripts", script, args)
        result = compare(patterns)
        if classify:
            missing = [r["path"] for r in result if r["result"] == "MISSING"]
            if missing:                                   # hand-written: put back (+ registering state), rerun
                restore(missing + sorted(STATE_KEEP & set(members)))
                found["manual"] += missing
                code, out = run_script(work, work / "scripts", script, args)
                result = compare(patterns)
                for r in result:
                    if r["path"] in missing and r["result"] == "OK":
                        r["result"] = "MANUAL"
            for r in result:
                if r["result"] == "DIFF":                 # edited after generation: keep generator bytes
                    found["edited"][r["path"]] = (work / r["path"]).read_bytes()
                    r["result"] = "EDITED"
        restore(sorted(edited | set(found["edited"])))   # continue from the version the job really used
        restore(status_files)
        steps.append({"script": script + (" " + " ".join(args) if args else ""), "exit": code,
                      "ok": sum(r["result"] in ("OK", "MANUAL", "EDITED") for r in result),
                      "rows": [r for r in result if r["result"] not in ("OK", "MANUAL", "EDITED")],
                      "total": len(result), "tail": out if code else ""})
    return steps, found


def capture(job: Path, name: str, note: str = "", source_label: str = "") -> dict:
    job = job.resolve()
    if not (job / "config" / "config.json").is_file() or not (job / "scripts" / "pipeline" / "convert_sql.py").is_file():
        raise RegressionError("Not a delivery job folder (needs config/config.json and scripts/pipeline/convert_sql.py)")
    files = job_files(job)
    members = {rel: (job / rel).read_bytes() for rel in files}

    def rows_for(mem, manual=(), edited=()):
        out = []
        for rel in sorted(mem):
            plain = rel[len(MACHINE):] if rel.startswith(MACHINE) else rel
            layer = "machine" if rel.startswith(MACHINE) else ("reviewed" if rel in manual or rel in edited else files[rel])
            if rel.startswith(MACHINE):
                layer = files.get(plain, "derived") if files.get(plain) in MASKED_LAYERS else "derived"
            out.append({"path": rel, "layer": layer, "bytes": len(mem[rel]), "sha256": sha(mem[rel]),
                        "norm_sha256": sha(normalize(plain, mem[rel], layer))})
        return out

    with tempfile.TemporaryDirectory(prefix="regression-classify-") as tmp:   # which outputs did people write / edit?
        work = Path(tmp) / "job"
        materialize(members, work)
        _, found = run_pipeline({"files": rows_for(members)}, members, work, classify=True)
    manual, edited = sorted(found["manual"]), sorted(found["edited"])
    for rel, data in found["edited"].items():
        members[MACHINE + rel] = data
    rows = rows_for(members, manual, edited)
    meta = {"files": rows, "manual_files": manual, "edited_files": edited}
    with tempfile.TemporaryDirectory(prefix="regression-check-") as tmp:      # then the job must reproduce itself
        work = Path(tmp) / "job"
        materialize(members, work)
        steps, _ = run_pipeline(meta, members, work)
        bad = [s for s in steps if s["exit"] != 0 or s["rows"]]
        if bad:
            raise RegressionError("The job's own scripts do not reproduce its outputs; fix the job first: " +
                                  "; ".join(f"{s['script']} exit {s['exit']} {[r['path'] for r in s['rows']][:3]}" for s in bad))
    ws_kit = json.loads((job / ".ws_kit.json").read_text(encoding="utf-8")) if (job / ".ws_kit.json").is_file() else {}
    synced = ws_kit.get("files", {})
    patched = sorted(rel for rel, h in synced.items()
                     if (job / rel).is_file() and sha((job / rel).read_bytes()) != (h if isinstance(h, str) else h.get("sha256")))
    archive_sha = write_archive(BASE_DIR / name / "baseline.zip", members)
    meta = {
        "name": name, "format": 2, "captured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source_label or str(job), "note": note, "archive": "baseline.zip", "archive_sha256": archive_sha,
        "source_kit": {"workspace_version": ws_kit.get("workspace_version"), "synced_at": ws_kit.get("synced_at"),
                       "patched_after_sync": patched},
        "capture": {"python": sys.version.split()[0], "steps": [s["script"] for s in steps]},
        "review_delta": [p for p in edited if p.startswith("output/sql/converted/")],
        "manual_files": manual, "edited_files": edited,
        "layers": {layer: sum(1 for r in rows if r["layer"] == layer) for layer in sorted({r["layer"] for r in rows})},
        "masking": {"text": "CRLF→LF", "masked_layers": sorted(MASKED_LAYERS), "patterns": [rx.pattern for rx, _ in MASKS]},
        "files": rows,
    }
    (BASE_DIR / name / "BASELINE.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def verify(name: str) -> list[str]:
    meta, members = read_archive(name)
    problems = []
    listed = {r["path"]: r for r in meta["files"]}
    if set(listed) != set(members):
        problems.append(f"archive members differ from BASELINE.json: +{sorted(set(members) - set(listed))[:5]} -{sorted(set(listed) - set(members))[:5]}")
    for rel, row in listed.items():
        if rel in members and sha(members[rel]) != row["sha256"]:
            problems.append(f"{rel}: content changed")
    return problems


def replay(name: str, scripts: Path | None = None, keep: bool = False) -> dict:
    meta, members = read_archive(name)
    if meta.get("format", 1) < 2:
        raise RegressionError(f"Baseline {name} uses format {meta.get('format', 1)}; recapture it with this tool")
    tmp = Path(tempfile.mkdtemp(prefix="regression-replay-"))
    work = tmp / "job"
    report = {"name": name, "scripts": str(scripts or "baseline provenance (job's own scripts)")}
    try:
        materialize(members, work)
        if scripts:
            src = Path(scripts) / "scripts" if (Path(scripts) / "scripts").is_dir() else Path(scripts)
            shutil.rmtree(work / "scripts", ignore_errors=True)
            shutil.copytree(src, work / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        report["steps"], _ = run_pipeline(meta, members, work)
        report["passed"] = all(s["exit"] == 0 and not s["rows"] for s in report["steps"])
        if keep:
            report["workdir"] = str(work)
        return report
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("capture"); p.add_argument("--job", type=Path, required=True); p.add_argument("--name", required=True); p.add_argument("--note", default="")
    p.add_argument("--source-label", default="", help="path to record instead of --job (e.g. the original Windows path)")
    p = sub.add_parser("verify"); p.add_argument("--name", required=True)
    p = sub.add_parser("replay"); p.add_argument("--name", required=True); p.add_argument("--scripts", type=Path); p.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", a.name):
        print("ERROR: --name uses a-z 0-9 _"); return 1
    try:
        if a.cmd == "capture":
            meta = capture(a.job, a.name, a.note, a.source_label)
            print(f"Baseline {a.name}: {len(meta['files'])} files · layers {meta['layers']}")
            print(f"archive tests/regression/{a.name}/baseline.zip sha256 {meta['archive_sha256']} (keep out of Git)")
            print(f"review delta (converter output edited in Phase 4): {len(meta['review_delta'])} file(s)")
            print(f"kit scripts patched after sync: {len(meta['source_kit']['patched_after_sync'])} file(s)")
            print(f"manual outputs (not produced by the pipeline): {len(meta['manual_files'])} file(s)")
            print(f"edited after generation (compared with generator output): {len(meta['edited_files'])} file(s)")
            return 0
        if a.cmd == "verify":
            problems = verify(a.name)
            for x in problems:
                print("FAIL: " + x)
            print(f"Baseline {a.name}: {'FAIL' if problems else 'PASS'} ({len(problems)} findings)")
            return int(bool(problems))
        report = replay(a.name, a.scripts, a.keep)
        for s in report["steps"]:
            mark = "PASS" if s["exit"] == 0 and not s["rows"] else "FAIL"
            print(f"{mark}  {s['script']:<58} {s['ok']}/{s['total']} match" + (f" · exit {s['exit']}" if s["exit"] else ""))
            for r in s["rows"]:
                print(f"      {r['result']:<7} {r['path']}")
            if s["tail"]:
                print("      " + s["tail"].strip().splitlines()[-1][:200])
        if report.get("workdir"):
            print(f"workdir kept: {report['workdir']}")
        print(f"Replay {a.name}: {'PASS' if report['passed'] else 'FAIL'}")
        return 0 if report["passed"] else 1
    except (RegressionError, OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
