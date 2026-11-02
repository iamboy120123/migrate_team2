from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import workspace as W
from .storage import WorkspaceError, find_job, read


def parser():
    ap = argparse.ArgumentParser(description="Blendata → ODI team workspace: offline simulation jobs and kit-pinned delivery jobs")
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("init", "freeze-kit", "demo", "status", "report", "check", "lock-status"):
        sub.add_parser(command)
    p = sub.add_parser("snapshot"); p.add_argument("--source", type=Path)
    p = sub.add_parser("new-job")
    p.add_argument("--project", required=True); p.add_argument("--job", required=True)
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--workflow", type=Path, help="simulation: normalized workflow JSON (required) · delivery: Blendata export JSON (optional)")
    p.add_argument("--owner", default="DEMO_DEVELOPER")
    p.add_argument("--mode", choices=("simulation", "delivery"), default="simulation")
    p = sub.add_parser("import-job", help="bring an existing Migrate_ODI_Team2 job in as a delivery job")
    p.add_argument("--from", dest="source", type=Path, required=True)
    p.add_argument("--project", required=True); p.add_argument("--job", required=True)
    p.add_argument("--issue", type=int, required=True); p.add_argument("--owner", required=True)
    p = sub.add_parser("approve"); p.add_argument("--job", required=True)
    p.add_argument("--reviewer", required=True); p.add_argument("--simulation", action="store_true", required=True)
    p = sub.add_parser("simulate"); p.add_argument("--job", required=True)
    for command in ("import-lock", "import-unlock"):
        p = sub.add_parser(command); p.add_argument("--job", required=True)
        p.add_argument("--holder", required=True); p.add_argument("--simulation", action="store_true", required=True)
    return ap


def main(root, argv=None):
    args = parser().parse_args(argv)
    try:
        cmd = args.command
        if cmd == "init":
            W.initialize(root); print("Simulation workspace initialized")
        elif cmd == "freeze-kit":
            print(json.dumps(W.freeze(root), indent=2))
        elif cmd == "snapshot":
            print(W.snapshot(root, args.source))
        elif cmd == "demo":
            W.demo(root); print("Demo ready. Open STATUS.html or STATUS.md")
        elif cmd == "new-job":
            if args.mode == "simulation" and not args.workflow:
                raise ValueError("--workflow is required for simulation jobs")
            print(W.new_job(root, args.project, args.job, args.issue,
                            args.workflow.resolve() if args.workflow else None, args.owner, args.mode))
        elif cmd == "import-job":
            print(W.import_job(root, args.source, args.project, args.job, args.issue, args.owner))
        elif cmd == "approve":
            W.approve(root, find_job(root, args.job), args.reviewer)
            print("SIMULATED_APPROVAL recorded for current input/config/kit fingerprint; no production approval")
        elif cmd == "simulate":
            W.simulate(root, find_job(root, args.job)); W.report(root)
        elif cmd in ("status", "report"):
            W.report(root); print((root / "STATUS.md").read_text(encoding="utf-8"))
        elif cmd == "check":
            errors = W.check(root)
            for error in errors:
                print("FAIL: " + error)
            print(f"Workspace integrity: {'FAIL' if errors else 'PASS'} ({len(errors)} findings)")
            return int(bool(errors))
        elif cmd == "import-lock":
            print(json.dumps(W.acquire_lock(root, find_job(root, args.job), args.holder), indent=2))
        elif cmd == "import-unlock":
            W.release_lock(root, find_job(root, args.job), args.holder); print("Simulation lock released; no actual import performed")
        elif cmd == "lock-status":
            path = root / "registry/import_simulation.lock.json"
            print(json.dumps(read(path), indent=2) if path.exists() else "SIMULATION IMPORT: FREE (local filesystem only)")
        return 0
    except (WorkspaceError, OSError, ValueError, KeyError) as exc:
        print("ERROR: " + str(exc))
        return 1
