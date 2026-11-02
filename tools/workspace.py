"""Team migration workspace launcher. Run from any working directory.

Simulation commands come from the pinned-kit source (kit/src/migrate_kit/cli.py).
Optional Oracle commands (db-* / run-sql) come from tools/dbcore and never change the
pinned kit, the simulation runtime or its gates.
"""
from pathlib import Path
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kit" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

DB_HELP = """
Oracle adapter (optional · tools/dbcore · every run needs an approved plan):
  db-status | db-policy | db-connect | db-driver | db-test | run-sql
  python tools/workspace.py <command> --help   for details (docs/DATABASE.md)

Wiki / team knowledge (tools/wikicmd.py · engine kit/delivery/scripts/ws/wiki.py):
  wiki-search <term> [--layer] | wiki-step <01-06> [--job P/J] | wiki-check
  kit-promote --job P/J --lesson L# [--plan-id X --approved "<name> <date>"]   (person approves; docs/TEAM_WORKFLOW.md)"""


def kit_command(argv):
    """Restore cached releases from kit/releases/<v>.zip, and route freeze-kit through the store (ADR-007)."""
    import json
    import kitstore
    try:
        kitstore.restore_all(ROOT)
        if argv and argv[0] == "freeze-kit" and len(argv) == 1:
            from migrate_kit import __version__
            from migrate_kit.storage import WorkspaceError
            from migrate_kit.workspace import freeze
            try:
                print(json.dumps(kitstore.freeze(ROOT, __version__, freeze), indent=2))
                return 0
            except WorkspaceError as exc:
                print("ERROR: " + str(exc))
                return 1
    except (kitstore.StoreError, OSError, ValueError, KeyError) as exc:
        print("ERROR: kit release store: " + str(exc))
        return 1
    return None


def main(argv):
    from dbcore import cli as db_cli
    if argv and argv[0] in db_cli.COMMANDS:
        return db_cli.main(ROOT, argv)
    import wikicmd
    if argv and argv[0] in wikicmd.COMMANDS:
        return wikicmd.main(ROOT, argv)
    handled = kit_command(argv)
    if handled is not None:
        return handled
    from migrate_kit.cli import main as kit_main
    if not argv or argv[0] in ("-h", "--help"):
        try:
            return kit_main(ROOT, argv)
        finally:
            print(DB_HELP)
    return kit_main(ROOT, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
