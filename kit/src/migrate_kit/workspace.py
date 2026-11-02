from __future__ import annotations

import csv
import io
import json
import re
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from . import __version__
from .storage import (WorkspaceError, digest, file_map, find_job, fingerprint, inside,
                      jobs, now, object_digest, read, safe_name, text, write)


def initialize(root):
    """Add missing scaffolding only. Never replace existing workspace settings."""
    for folder in ("projects", "registry", ".cache/kit", "kit/releases", "shared/policies",
                   "shared/knowledge", "shared/target/_incoming"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    defaults = {
        "workspace.json": {"workspace_version": "0.1.0", "mode": "simulation", "created_at": now()},
        "shared/team.json": {"github_mode": "manual", "db_mode": "human", "simulation_only": True,
                             "ids": {"base": 90000, "step": 1000}},
        "shared/approvers.json": {"simulation_reviewers": ["DEMO_SA"], "production_approvers": [], "knowledge_approvers": []},
    }
    for name, value in defaults.items():
        if not (root / name).exists():
            write(root / name, value)
    return defaults


def release_files(root):
    files = {p.relative_to(root / "kit/src").as_posix(): p.read_bytes()
             for p in sorted((root / "kit/src").rglob("*.py")) if "__pycache__" not in p.parts}
    for group in ("templates", "ai", "knowledge", "delivery"):
        folder = root / "kit" / group
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    files[f"migrate_kit/resources/{group}/{path.relative_to(folder).as_posix()}"] = path.read_bytes()
    return files


def archive_bytes(files):
    """Deterministic release archive. STORED (no compression) since 0.2.0: identical bytes on every
    machine and zlib build, so any clone can rebuild and verify a release (ADR-007)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


AI_PREFIX = "migrate_kit/resources/ai/claude/"
KNOWLEDGE_PREFIX = "migrate_kit/resources/knowledge/"
JOB_EDITABLE_KNOWLEDGE = {"knowledge/WORKFLOW.md", "knowledge/lessons-learned.md", "knowledge/glossary-kit.md"}


DELIVERY_PREFIX = "migrate_kit/resources/delivery/"
BANNER_RX = re.compile(r"<!-- KIT-BANNER (\{.*?\}) -->\n")
BANNER_TEXT = ("> ⚠️ **migrate_team2 kit {kit} ({mode}):** ส่วนนี้อ้างเครื่องมือที่ไม่มีในงานนี้ — {items}\n"
               "> ห้ามสร้าง ค้นหา หรือคัดลอก scripts / คำสั่งเหล่านี้มาเอง · ทำเฉพาะส่วนที่เป็นการอ่าน วิเคราะห์ ถาม และเขียนเอกสาร\n"
               "> แล้วบอกผู้ใช้ว่าขั้นนี้ต้องทำ{where} (ดู CLAUDE.md หัวข้อ 2)\n\n")


def render_banner(body, mode, kit):
    """KIT-BANNER marker → warning text for what this job lacks (delivery jobs have scripts/)."""
    def one(match):
        info = json.loads(match.group(1))
        items = (info.get("scripts", []) if mode == "simulation" else []) + info.get("other", [])
        if not items:
            return ""
        shown = " · ".join(f"`{x}`" for x in items[:8]) + (f" และอีก {len(items) - 8} รายการ" if len(items) > 8 else "")
        where = "ในงาน delivery หรือ Migrate_ODI_Team2" if mode == "simulation" else "ด้วยช่องทางของทีม (ยังไม่มีใน workspace นี้)"
        return BANNER_TEXT.format(kit=kit, mode=mode, items=shown, where=where)
    return BANNER_RX.sub(one, body)


def install_ai_context(job, archive_path, values, mode="simulation"):
    """Install the release's AI context, knowledge (and for delivery jobs: scripts, settings, templates).

    Returns the locked file hashes. Locked: .claude/**, knowledge/reference/**, scripts/**, references/**.
    Not locked: CLAUDE.md, job-editable knowledge pages, status/.design documents created from templates.
    Text is rendered with {{KEY}} values; scripts are copied byte for byte.
    """
    import hashlib
    locked = {}

    def render(data):
        body = data.decode("utf-8")
        for key, value in values.items():
            body = body.replace("{{" + key + "}}", str(value))
        return body.encode("utf-8")

    def put(rel, data, lock=True, keep_existing=False):
        target = inside(job, rel)
        if keep_existing and target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if lock:
            locked[rel] = hashlib.sha256(data).hexdigest()

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        for name in sorted(names):
            data = archive.read(name)
            if name.startswith(AI_PREFIX):
                rel = ".claude/" + name[len(AI_PREFIX):]
                if rel == ".claude/SOURCE.json":
                    continue
                if rel.endswith((".md", ".js", ".json")):
                    data = render(render_banner(data.decode("utf-8"), mode, values.get("KIT", "")).encode("utf-8"))
                put(rel, data)
            elif name.startswith(KNOWLEDGE_PREFIX):
                rel = "knowledge/" + name[len(KNOWLEDGE_PREFIX):]
                data = render(render_banner(data.decode("utf-8"), mode, values.get("KIT", "")).encode("utf-8"))
                put(rel, data, lock=rel not in JOB_EDITABLE_KNOWLEDGE, keep_existing=rel in JOB_EDITABLE_KNOWLEDGE)
            elif mode == "delivery" and name.startswith(DELIVERY_PREFIX):
                rel = name[len(DELIVERY_PREFIX):]
                if rel.startswith("scripts/"):
                    put(rel, data)
                elif rel == "templates/claude-settings.json":
                    put(".claude/settings.json", data)
                elif rel.startswith("templates/references/"):
                    put("references/" + rel[len("templates/references/"):], data)
                elif rel.startswith("templates/status/") and rel.endswith(".tpl"):
                    put("status/" + rel[len("templates/status/"):-4], render(data), lock=False, keep_existing=True)
                elif rel.startswith("templates/design/") and rel.endswith(".tpl"):
                    put(".design/" + rel[len("templates/design/"):-4], render(data), lock=False, keep_existing=True)
        template = "migrate_kit/resources/templates/job/" + ("CLAUDE.delivery.md" if mode == "delivery" else "CLAUDE.md")
        if template in names:
            if (job / "CLAUDE.md").exists():          # imported job: keep its own notes beside the kit's rules
                (job / "CLAUDE.imported.md").write_bytes((job / "CLAUDE.md").read_bytes())
            text(job / "CLAUDE.md", render(archive.read(template)).decode("utf-8"))
    return locked


LOCK_SCOPES = (".claude/agents/", ".claude/commands/", ".claude/rules/", ".claude/skills/", ".claude/workflows/",
               "knowledge/reference/", "scripts/", "references/")


def verify_ai_context(root, job):
    """Files installed from the pinned kit (AI context, knowledge, delivery scripts) must be unchanged.

    The expected content is rebuilt from the pinned release itself (not taken from kit.lock.json, which a
    job could edit), so a patched file whose hash was also written into the lock is still detected, and
    extra files placed in kit-owned folders are reported.
    """
    import tempfile
    pin = read(job / "kit.lock.json")
    locked = pin.get("ai_context")
    if not locked:
        if read(job / "job.json").get("mode") == "delivery":
            raise WorkspaceError("kit.lock.json has no ai_context record for a delivery job")
        return
    meta = read(job / "job.json")
    artifact = inside(root, read(root / "kit/releases" / f"{safe_version(pin['kit_version'])}.json")["artifact"])
    values = {"PROJECT": meta["project"], "JOB": meta["job"], "KIT": pin["kit_version"]}
    with tempfile.TemporaryDirectory(prefix="kit-expected-") as tmp:
        expected = install_ai_context(Path(tmp), artifact, values, meta.get("mode", "simulation"))
    problems = [rel for rel, sha in expected.items() if not (job / rel).is_file() or digest(job / rel) != sha]
    problems += [rel for rel, sha in locked["files"].items() if rel not in expected]          # lock rewritten
    for scope in LOCK_SCOPES:
        base = job / scope
        if base.is_dir():
            problems += [p.relative_to(job).as_posix() for p in base.rglob("*")
                         if p.is_file() and p.relative_to(job).as_posix() not in expected
                         and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    if problems:
        problems = sorted(set(problems))
        raise WorkspaceError(f"Kit-installed file modified (AI context / knowledge / scripts): {', '.join(problems[:5])}"
                             f"{' …' if len(problems) > 5 else ''} — restore it; changes go through a new kit release")


def freeze(root):
    import hashlib
    files = release_files(root)
    blob = archive_bytes(files)
    sha = hashlib.sha256(blob).hexdigest()
    version = __version__
    release_path = root / "kit/releases" / f"{version}.json"
    relative = f".cache/kit/{version}/migrate_kit-{sha}.zip"
    if release_path.exists():
        prior = read(release_path)
        if prior["sha256"] != sha:
            raise WorkspaceError("This version is already frozen with different source. Bump kit version; do not overwrite a release.")
    artifact = root / relative
    if not artifact.exists():
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(blob)
    if digest(artifact) != sha:
        raise WorkspaceError("Cached release is corrupt; restore its original artifact")
    manifest = {"version": version, "sha256": sha, "artifact": relative,
                "kind": "simulation-kit", "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    if not release_path.exists():
        write(release_path, manifest)
    return manifest


def snapshot(root, source=None):
    source = source or root / "samples/target"
    files = file_map(source)
    sid = "sim-" + object_digest(files)[:16]
    dest = root / "shared/target/snapshots" / sid
    if dest.exists():
        verify_snapshot(root, sid)
    else:
        dest.mkdir(parents=True)
        for name in files:
            target = inside(dest, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inside(source, name), target)
        write(dest / "manifest.json", {"id": sid, "kind": "synthetic-target", "files": files,
                                       "sha256": object_digest(files), "production_verified": False})
    write(root / "shared/target/current.json", {"snapshot": sid})
    return sid


def verify_snapshot(root, sid):
    if not isinstance(sid, str) or not sid.startswith("sim-"):
        raise WorkspaceError("Expected a synthetic target snapshot")
    folder = inside(root / "shared/target/snapshots", sid)
    manifest = read(folder / "manifest.json")
    actual = {k: v for k, v in file_map(folder).items() if k != "manifest.json"}
    if actual != manifest["files"] or object_digest(actual) != manifest["sha256"]:
        raise WorkspaceError(f"Target snapshot modified: {sid}")
    return manifest


def verify_pin(root, job):
    pin = read(job / "kit.lock.json")
    release = read(root / "kit/releases" / f"{safe_version(pin['kit_version'])}.json")
    artifact = inside(root, release["artifact"])
    if pin["kit_sha256"] != release["sha256"] or digest(artifact) != pin["kit_sha256"]:
        raise WorkspaceError("Pinned kit hash does not match release artifact")
    if "target_snapshot" in pin:                       # delivery jobs keep their real target files in input/
        target = verify_snapshot(root, pin["target_snapshot"])
        if target["sha256"] != pin["target_sha256"]:
            raise WorkspaceError("Pinned target hash does not match snapshot")
    return artifact


def safe_version(value):
    import re
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise WorkspaceError("Expected a numeric kit version")
    return value


def new_job(root, project, name, issue, workflow, owner="DEMO_DEVELOPER", mode="simulation"):
    if mode == "delivery":
        return new_delivery_job(root, project, name, issue, owner, workflow)
    if mode != "simulation":
        raise WorkspaceError("mode must be simulation or delivery")
    safe_name(project); safe_name(name); safe_name(owner)
    if issue < 1:
        raise WorkspaceError("Simulation issue number must be positive")
    path = root / "projects" / project / "jobs" / name
    if path.exists():
        raise WorkspaceError(f"Job already exists: {project}/{name}")
    for other in jobs(root):
        if read(other)["issue"] == issue:
            raise WorkspaceError(f"Issue/id range already reserved by {other.parent.name}")
    team_ids = read(root / "shared/team.json")["ids"]
    clash = _id_conflict(root, team_ids["base"] + issue * team_ids["step"])
    if clash:
        raise WorkspaceError(f"ODI id range for issue {issue} overlaps job {clash}")
    definition = read(workflow)
    if not definition.get("tasks"):
        raise WorkspaceError("Workflow must contain tasks")
    release = read(root / "kit/releases" / f"{__version__}.json")
    if digest(inside(root, release["artifact"])) != release["sha256"]:
        raise WorkspaceError("Cannot create a job from a modified release artifact")
    sid = read(root / "shared/target/current.json")["snapshot"]
    target = verify_snapshot(root, sid)
    for folder in ("config", "input/blendata", "input/run_results", "output", "status", "run_packs",
                   ".design", "knowledge", ".claude/commands"):
        (path / folder).mkdir(parents=True, exist_ok=True)
    team = read(root / "shared/team.json")
    write(path / "job.json", {"project": project, "job": name, "owner": owner, "issue": issue,
                               "issue_source": "simulation", "issue_unconfirmed": True,
                               "id_base": team["ids"]["base"] + issue * team["ids"]["step"],
                               "branch": f"job/{project}/{name}/R01", "round": "R01",
                               "mode": "simulation", "production_import_allowed": False, "created_at": now()})
    lock = {"kit_version": release["version"], "kit_sha256": release["sha256"],
            "target_snapshot": sid, "target_sha256": target["sha256"]}
    installed = install_ai_context(path, inside(root, release["artifact"]),
                                   {"PROJECT": project, "JOB": name, "KIT": release["version"]}, "simulation")
    if installed:
        lock["ai_context"] = {"files": installed, "sha256": object_digest(installed)}
    write(path / "kit.lock.json", lock)
    shutil.copy2(workflow, path / "input/blendata/export_workflow.json")
    write(path / "config/config.json", {"mode": "simulation", "package_name": "PKG_" + name.upper()[:26],
                                         "schema_mode": "simulation_unqualified", "db_mode": "human",
                                         "github_mode": "manual", "fixture": "fixtures/rows.json"})
    write(path / "status/approvals.json", {"mode": "simulation", "approvals": []})
    write(path / "status/events.json", [])
    for doc in ("INTAKE", "BUSINESS_RULES", "GAP_ANALYSIS", "OPEN_DECISIONS", "GATES",
                "IMPORT_LOG", "DEPLOY_LOG", "CUTOVER_RUNBOOK"):
        template = f"migrate_kit/resources/templates/status/{doc}.md"
        with zipfile.ZipFile(inside(root, release["artifact"])) as archive:
            content = archive.read(template).decode("utf-8") if template in archive.namelist() else f"# {doc}\n\nSimulation only. No production evidence recorded.\n"
        text(path / "status" / f"{doc}.md", content.replace("{{JOB}}", name))
    if not installed:   # releases without AI context (0.1.0 layout)
        text(path / "CLAUDE.md", f"# {project}/{name}\n\nSIMULATION ONLY. Never connect to Oracle/GitHub.\n"
             "Read kit.lock.json and status/ before work. Use the workspace launcher; do not duplicate kit code.\n"
             "A simulated approval is never an SA approval. Generated XML is not ODI Smart Export.\n")
        text(path / ".claude/commands/next-step.md", "Read job.json, kit.lock.json, status/GATES.md and the workspace README.\n"
             "Use `python <workspace>/tools/workspace.py status` to inspect the next simulation step.\n")
    text(path / "ROUNDS.md", "# Rounds\n\n| Round | Mode | Reason |\n|---|---|---|\n| R01 | simulation | Initial demonstration |\n")
    project_dir = path.parents[1] / "_project"
    for doc in ("DECISIONS", "glossary", "lessons-learned"):
        dest = project_dir / f"{doc}.md"
        if not dest.exists():
            text(dest, f"# {doc}\n\nProject: {project}\n")
    return path


DELIVERY_DIRS = ("config", "input/blendata", "input/oracle_ddl", "input/odi_reference", "input/run_results",
                 "input/d1_seeds", "output/sql/raw", "output/sql/converted", "output/dml", "output/odi_export",
                 "output/ddl", "output/dba", "status", "run_packs", ".design", "knowledge")


def _id_conflict(root, id_base, exclude=None):
    step = read(root / "shared/team.json")["ids"]["step"]
    for other in jobs(root):
        if other.parent == exclude:
            continue
        theirs = read(other).get("id_base")
        if isinstance(theirs, int) and abs(theirs - id_base) < step:
            return other.parent.name
    return None


def _reserve(root, project, name, issue, owner, id_base=None):
    safe_name(project); safe_name(name); safe_name(owner)
    if issue < 1:
        raise WorkspaceError("Issue number must be positive")
    if id_base is not None:
        if not isinstance(id_base, int) or id_base <= 0:
            raise WorkspaceError("config.odi.id_base must be a positive integer")
        clash = _id_conflict(root, id_base)
        if clash:
            raise WorkspaceError(f"ODI id range {id_base} overlaps job {clash}; choose another issue or id_base")
    path = root / "projects" / project / "jobs" / name
    if path.exists():
        raise WorkspaceError(f"Job already exists: {project}/{name}")
    for other in jobs(root):
        if read(other)["issue"] == issue:
            raise WorkspaceError(f"Issue/id range already reserved by {other.parent.name}")
    release = read(root / "kit/releases" / f"{__version__}.json")
    if digest(inside(root, release["artifact"])) != release["sha256"]:
        raise WorkspaceError("Cannot create a job from a modified release artifact")
    if not any(n.startswith(DELIVERY_PREFIX + "scripts/") for n in zipfile.ZipFile(inside(root, release["artifact"])).namelist()):
        raise WorkspaceError(f"kit {__version__} has no delivery runtime")
    return path, release


def _delivery_values(project, name, release, config, owner):
    odi = config.get("odi") or {}
    scope = (config.get("scope") or {}).get("excluded_tasks") or []
    return {"PROJECT": project, "JOB": name, "KIT": release["version"], "KIT_VERSION": f"migrate_team2 {release['version']}",
            "WORKFLOW": config.get("project_name") or name, "PROJECT_NAME": config.get("project_name") or name,
            "DATE": now()[:10], "ODI_VERSION": odi.get("odi_version") or "14.1.2", "PROJECT_CODE": odi.get("project_code", ""),
            "PACKAGE_NAME": odi.get("package_name", ""), "LOGICAL_SCHEMA": odi.get("logical_schema", ""),
            "CONTEXT_CODE": odi.get("context_code", ""), "WORK_USER": odi.get("work_user", ""),
            "CREATED_BY": config.get("created_by") or owner,
            "EXPORT_PATH": (config.get("paths") or {}).get("input_export_workflow", "input/blendata/export_workflow.json"),
            "EXCLUDED": ", ".join(f"`{t}`" for t in scope) or "-",
            "LANDING_TABLE": (config.get("profile") or {}).get("landing_table") or "<landing table - ยังไม่ระบุ>",
            "MAX_LAG": (config.get("precheck") or {}).get("landing_max_lag_minutes", 120)}


def _finish_delivery(root, path, project, name, issue, owner, release, config, imported_from=None):
    values = _delivery_values(project, name, release, config, owner)
    installed = install_ai_context(path, inside(root, release["artifact"]), values, "delivery")
    write(path / "job.json", {"project": project, "job": name, "owner": owner, "issue": issue,
                               "issue_source": "workspace", "issue_unconfirmed": True,
                               "id_base": int((config.get("odi") or {}).get("id_base") or 0),
                               "branch": f"job/{project}/{name}/R01", "round": "R01", "mode": "delivery",
                               "production_import_allowed": False, "created_at": now(),
                               **({"imported_from": imported_from} if imported_from else {})})
    write(path / "kit.lock.json", {"kit_version": release["version"], "kit_sha256": release["sha256"],
                                   "ai_context": {"files": installed, "sha256": object_digest(installed)}})
    if not (path / "ROUNDS.md").exists():
        text(path / "ROUNDS.md", "# Rounds\n\n| Round | Mode | Reason |\n|---|---|---|\n| R01 | delivery | "
             + ("Imported from " + imported_from if imported_from else "New job") + " |\n")
    project_dir = path.parents[1] / "_project"
    for doc in ("DECISIONS", "glossary", "lessons-learned"):
        if not (project_dir / f"{doc}.md").exists():
            text(project_dir / f"{doc}.md", f"# {doc}\n\nProject: {project}\n")
    return path


def new_delivery_job(root, project, name, issue, owner, export=None):
    """A real (delivery) job: kit scripts + AI context installed and locked; config from the kit template."""
    team = read(root / "shared/team.json")
    if export and not (read(export).get("airflowExportModels") or read(export).get("tasks")):
        raise WorkspaceError("Export file does not look like a Blendata workflow export")
    path, release = _reserve(root, project, name, issue, owner, team["ids"]["base"] + issue * team["ids"]["step"])
    try:
        return _create_delivery(root, path, project, name, issue, owner, export, release, team)
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)            # never leave a half-created job behind
        raise


def _create_delivery(root, path, project, name, issue, owner, export, release, team):
    with zipfile.ZipFile(inside(root, release["artifact"])) as archive:
        config = json.loads(archive.read(DELIVERY_PREFIX + "templates/config.example.json").decode("utf-8"))
    code = re.sub(r"[^A-Z0-9_]", "_", name.upper())[:30]
    config.update({"project_name": name, "created_at": now()[:10], "created_by": owner, "schema_mode": "odiref"})
    config["paths"]["input_export_workflow"] = "input/blendata/export_workflow.json"
    config["odi"].update({"project_code": code, "project_name": name, "folder_name": name, "package_name": ("PKG_" + code)[:30],
                          "id_base": team["ids"]["base"] + issue * team["ids"]["step"]})
    for folder in DELIVERY_DIRS:
        (path / folder).mkdir(parents=True, exist_ok=True)
    write(path / "config/config.json", config)
    if export:
        shutil.copy2(export, path / "input/blendata/export_workflow.json")
    return _finish_delivery(root, path, project, name, issue, owner, release, config)


IMPORT_SKIP_PARTS = {"scripts", ".claude", "__pycache__", "_deprecated", ".dbx", "spark-warehouse", ".git"}


def import_job(root, source, project, name, issue, owner):
    """Bring an existing Migrate_ODI_Team2 job in as a delivery job. Its own kit copy (scripts/, .claude/,
    knowledge/reference/) is replaced by this kit's locked files; inputs, outputs, status and decisions are kept."""
    source = Path(source).resolve()
    if not (source / "config/config.json").is_file() or not (source / "scripts/pipeline/convert_sql.py").is_file():
        raise WorkspaceError("Source is not a Migrate_ODI_Team2 job (needs config/config.json and scripts/pipeline/)")
    id_base = (read(source / "config/config.json").get("odi") or {}).get("id_base")
    path, release = _reserve(root, project, name, issue, owner, id_base)
    try:
        return _copy_import(root, source, path, project, name, issue, owner, release)
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)
        raise


def _copy_import(root, source, path, project, name, issue, owner, release):
    copied = 0
    for src in sorted(source.rglob("*")):
        rel = src.relative_to(source)
        if (not src.is_file() or IMPORT_SKIP_PARTS.intersection(rel.parts) or src.suffix == ".pyc"
                or ".bak" in src.name or rel.as_posix().startswith("knowledge/reference/")
                or rel.as_posix() in ("job.json", ".ws_kit.json", "kit.lock.json")):
            continue
        dest = path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    write(path / "status/IMPORTED_FROM.json", {"source": str(source),
                                                "job_json": read(source / "job.json") if (source / "job.json").is_file() else None,
                                                "ws_kit": read(source / ".ws_kit.json") if (source / ".ws_kit.json").is_file() else None,
                                                "files_copied": copied, "at": now()})
    config = read(path / "config/config.json")
    return _finish_delivery(root, path, project, name, issue, owner, release, config, imported_from=str(source))


def _require_simulation(job, action):
    if read(job / "job.json").get("mode") == "delivery":
        raise WorkspaceError(f"{action} is for simulation jobs. Delivery jobs use status/GATES.md "
                             "(python scripts/checks/check_gate.py) and the team's real import lock")


def approve(root, job, reviewer):
    _require_simulation(job, "Simulated review")
    allowed = read(root / "shared/approvers.json")["simulation_reviewers"]
    if reviewer not in allowed:
        raise WorkspaceError("Reviewer is not in the simulation reviewer list")
    verify_pin(root, job)
    value = {"mode": "simulation", "approvals": [{"gate": "G2", "reviewer": reviewer,
             "state": "SIMULATED_APPROVAL", "fingerprint": fingerprint(job), "at": now(),
             "note": "Synthetic persona, not a real SA approval or deployment permission"}]}
    write(job / "status/approvals.json", value)
    return value


def simulate(root, job):
    _require_simulation(job, "simulate")
    artifact = verify_pin(root, job)
    # Actual execution imports the pinned ZIP, not mutable kit/src.
    bootstrap = "import sys;sys.path.insert(0,sys.argv.pop(1));from migrate_kit.runtime import main;main()"
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", bootstrap,
                             str(artifact), str(root), str(job)], cwd=job, check=False)
    if result.returncode:
        raise WorkspaceError(f"Simulation failed/blocked (exit {result.returncode}); inspect status and output/verify")
    return read(job / "status/simulation.json")


def acquire_lock(root, job, holder):
    safe_name(holder)
    _require_simulation(job, "Import-lock rehearsal")
    verify_pin(root, job)
    current = read(job / "status/simulation.json") if (job / "status/simulation.json").exists() else {}
    if current.get("fingerprint") != fingerprint(job) or current.get("state") != "SIMULATION_PASSED":
        raise WorkspaceError("Complete a current simulation before rehearsing import locking")
    lock = root / "registry/import_simulation.lock.json"
    payload = {"job": job.relative_to(root).as_posix(), "holder": holder, "at": now(), "mode": "simulation"}
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
    except FileExistsError:
        raise WorkspaceError("Simulation import lock is occupied; inspect lock-status") from None
    return payload


def release_lock(root, job, holder):
    path = root / "registry/import_simulation.lock.json"
    if not path.exists():
        raise WorkspaceError("No simulation import lock is held")
    lock = read(path)
    if lock["holder"] != holder or lock["job"] != job.relative_to(root).as_posix():
        raise WorkspaceError("Only the same job and holder may release this simulation lock")
    events = read(job / "status/events.json")
    events.append({"event": "SIMULATED_IMPORT_REHEARSAL", "holder": holder, "at": now(),
                   "actual_odi_import": False, "note": "No connection or Smart Import was performed"})
    write(job / "status/events.json", events)
    text(job / "status/IMPORT_LOG.md", "# Import rehearsal\n\nSIMULATION ONLY — actual ODI import: NOT EXECUTED.\n\n" +
         "\n".join(f"- {e['at']} {e['holder']}: lock/unlock rehearsal, no ODI connection" for e in events) + "\n")
    path.unlink()


def check(root):
    issues, ranges, errors = set(), set(), []
    for path in jobs(root):
        job = path.parent
        try:
            meta = read(path)
            base = read(root / "shared/team.json")["ids"]
            if meta["issue"] in issues or any(abs(meta["id_base"] - r) < base["step"] for r in ranges):
                raise WorkspaceError("Duplicate or overlapping issue/id range")
            if meta.get("mode") == "delivery":
                cfg_id = (read(job / "config/config.json").get("odi") or {}).get("id_base")
                if meta["id_base"] != cfg_id:
                    raise WorkspaceError("job.json id_base does not match config.odi.id_base")
            elif meta["id_base"] != base["base"] + meta["issue"] * base["step"]:
                raise WorkspaceError("Issue and id_base do not agree")
            issues.add(meta["issue"]); ranges.add(meta["id_base"])
            verify_pin(root, job)
            verify_ai_context(root, job)
            if meta.get("production_import_allowed") is not False or meta.get("mode") not in ("simulation", "delivery"):
                raise WorkspaceError("Job boundary modified (mode / production_import_allowed)")
            if meta.get("mode") == "delivery":
                continue
            report = job / "status/simulation.json"
            if report.exists():
                state = read(report)
                if state["fingerprint"] != fingerprint(job):
                    raise WorkspaceError("STALE: inputs/config/pin changed; rerun review and simulation")
                for rel, sha in state.get("outputs", {}).items():
                    if digest(inside(job, rel)) != sha:
                        raise WorkspaceError(f"Generated evidence modified: {rel}")
                if state["state"] != "SIMULATION_PASSED":
                    raise WorkspaceError("Simulation is blocked or failed")
        except (WorkspaceError, OSError, ValueError, KeyError) as exc:
            errors.append(f"{job.name}: {exc}")
    return errors + wiki_errors(root)


def wiki_errors(root):
    """Wiki rules (kit 0.4.0): evidence, no secrets, unique ids, kit-promote ledger. Engine = the kit's own wiki.py."""
    import importlib.util
    engine = Path(__file__).resolve().parents[2] / "delivery/scripts/ws/wiki.py"
    if not engine.is_file():
        return []
    spec = importlib.util.spec_from_file_location("migrate_kit_wiki", engine)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [f"wiki: {e}" for e in module.check(Path(root))[0]]


def report(root):
    import html
    rows = []
    for path in jobs(root):
        meta = read(path); job = path.parent
        state = read(job / "status/simulation.json") if (job / "status/simulation.json").exists() else {}
        label = state.get("state", "NOT_RUN")
        if meta.get("mode") == "delivery":
            label = "DELIVERY (status/GATES.md)"
        elif state and state.get("fingerprint") != fingerprint(job):
            label = "STALE_REVIEW_REQUIRED"
        pin = read(job / "kit.lock.json")
        rows.append({"project": meta["project"], "job": meta["job"], "owner": meta["owner"],
                     "kit": pin["kit_version"], "snapshot": pin.get("target_snapshot", "-"), "state": label,
                     "import": "NOT_EXECUTED" if meta.get("mode") != "delivery" else "SEE GATES (human Smart Import)",
                     "path": job.relative_to(root).as_posix()})
    errors = check(root)
    write(root / "registry/status.json", {"mode": "simulation", "jobs": rows, "errors": errors})
    lines = ["# Team simulation status", "", "SIMULATION ONLY — Oracle/Spark/ODI runtime: NOT EXECUTED.", "",
             "| Project | Job | Owner | Kit | State | Real import |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(row[k] for k in ("project", "job", "owner", "kit", "state", "import")) + " |")
    if errors:
        lines += ["", "Integrity findings:"] + ["- " + x for x in errors]
    text(root / "STATUS.md", "\n".join(lines) + "\n")
    body = "".join("<tr>" + "".join(f"<td>{html.escape(row[k])}</td>" for k in
                   ("project", "job", "owner", "kit", "state", "import")) + "</tr>" for row in rows)
    text(root / "STATUS.html", '<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         '<title>Migration team simulation</title><style>body{font:16px system-ui;background:#f3f6fb;color:#15233b;max-width:1200px;margin:40px auto;padding:20px}'
         'h1{font-size:30px}.notice{background:#fff0cb;padding:18px;border-radius:10px}table{width:100%;background:white;border-collapse:collapse;margin-top:24px}'
         'td,th{padding:14px;text-align:left;border-bottom:1px solid #dde4ed}th{background:#172c50;color:white}.flow{padding:24px 0;line-height:2}</style>'
         '<h1>Blendata → ODI · Team simulation</h1><div class="notice">จำลองออฟไลน์เท่านั้น · ไม่ได้ต่อ Oracle / Spark / ODI / GitHub<br>'
         'SIMULATION_PASSED หมายถึงชุดทดสอบข้อมูลตัวอย่างผ่าน ไม่ใช่การอนุมัติขึ้นระบบจริง</div>'
         '<div class="flow">Input → Pin kit & target → Review → SQL / DML → Simulation package → Fixture comparison → Import lock rehearsal</div>'
         '<table><thead><tr><th>Project</th><th>Job</th><th>Owner</th><th>Kit</th><th>Simulation</th><th>Real import</th></tr></thead><tbody>' + body +
         '</tbody></table><p>Integrity findings: ' + str(len(errors)) + '</p>' +
         '<ul>' + ''.join('<li>' + html.escape(x) + '</li>' for x in errors) + '</ul></html>')
    return rows


def demo(root):
    initialize(root); freeze(root); snapshot(root)
    for name, issue, owner in (("customer_daily", 101, "DEMO_ALICE"), ("order_daily", 102, "DEMO_BOB")):
        path = root / "projects/DEMO/jobs" / name
        if not path.exists():
            path = new_job(root, "DEMO", name, issue, root / "samples/workflows" / f"{name}.json", owner)
            approve(root, path, "DEMO_SA")
        simulate(root, path)
    report(root)
