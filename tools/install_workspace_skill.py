"""Install repo-local guidance without changing personal Codex settings or pinned kit releases."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SKILL_NAME = "blendata-odi-team"
START = "<!-- migrate-team-skill:start -->"
END = "<!-- migrate-team-skill:end -->"
BLOCK = f"""{START}
## Blendata to ODI workspace skill

For workspace setup, Project/Job operations, simulated reviews, evidence checks and
import-lock rehearsals, use `{SKILL_NAME}` at
`.agents/skills/{SKILL_NAME}/SKILL.md` and read its references as needed.
Locate the workspace root before running commands. Read the relevant job's status,
config and `kit.lock.json` before changing that job.
Simulation jobs are offline: their XML/ZIP is not native ODI Smart Export and simulated
approvals or fixture checks never approve deployment. Delivery jobs (kit 0.3.0+) run the
kit's locked `scripts/`; never patch them in a job. Smart Import stays a human step.
Real Oracle SQL runs only through `tools/workspace.py run-sql` / `db-*` (docs/DATABASE.md):
show the plan, ask the person (numbered answer), then `--execute <plan> --approved`.
Never approve for a person, ask for passwords in chat or change the team db policy unasked.
Team lessons grow only via `kit-promote` after a named person approves the shown plan.
Preserve user instructions outside this setup-managed block.
{END}"""


class InstallError(Exception):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".skill-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_path(root, relative):
    path = root / relative
    # Do not follow external symlinks/junctions while installing workspace guidance.
    if not path.resolve().is_relative_to(root.resolve()):
        raise InstallError(f"Guidance destination escapes workspace: {relative}")
    return path


def source_files(source):
    folder = source / ".agents/skills" / SKILL_NAME
    if not (folder / "SKILL.md").is_file():
        raise InstallError(f"Missing skill source: {folder / 'SKILL.md'}")
    content = (folder / "SKILL.md").read_text(encoding="utf-8-sig")
    front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.S)
    if not front or not re.search(rf"(?m)^name:\s*{SKILL_NAME}\s*$", front[1]):
        raise InstallError("Skill frontmatter/name is invalid")
    if not re.search(r"(?m)^description:\s*\S.+$", front[1]):
        raise InstallError("Skill description is missing")
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            if not path.resolve().is_relative_to(folder.resolve()):
                raise InstallError(f"Skill resource escapes its source: {path}")
            files[path.relative_to(folder).as_posix()] = path.read_bytes()
    for relative in re.findall(r"\]\((references/[^)]+)\)", content):
        if relative not in files:
            raise InstallError(f"Missing skill reference: {relative}")
    return folder, files


def agents_document(existing, previous):
    counts = (existing.count(START), existing.count(END))
    if counts == (0, 0):
        return existing + ("\n\n" if existing and not existing.endswith("\n\n") else "") + BLOCK + "\n"
    if counts != (1, 1) or existing.index(END) < existing.index(START):
        raise InstallError("AGENTS.md has ambiguous skill markers; preserve and resolve them before rerunning setup")
    first, last = existing.index(START), existing.index(END) + len(END)
    current = existing[first:last]
    if current != BLOCK and sha(current.encode()) != previous.get("agents_block_sha256"):
        raise InstallError("The managed AGENTS.md block was edited locally; review it before updating")
    return existing[:first] + BLOCK + existing[last:]


def install(source, workspace):
    source, workspace = Path(source).resolve(), Path(workspace).resolve()
    if not (workspace / "workspace.json").is_file() or not (workspace / "tools/workspace.py").is_file():
        raise InstallError("Initialize a recognized workspace before installing its skill")
    source_folder, files = source_files(source)
    target = safe_path(workspace, f".agents/skills/{SKILL_NAME}")
    manifest_path = safe_path(workspace, "registry/workspace_skill.json")
    previous = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.exists() else {}
    same_source = source_folder.resolve() == target.resolve()
    writes = []
    # Plan all updates before changing anything; a local edit blocks the update.
    for name, data in files.items():
        destination = safe_path(workspace, f".agents/skills/{SKILL_NAME}/{name}")
        if destination.exists():
            current = destination.read_bytes()
            if current == data:
                continue
            if not same_source and sha(current) != previous.get("files", {}).get(name):
                raise InstallError(f"Skill file has unmanaged local changes: {destination}")
        writes.append((destination, data))
    agents = safe_path(workspace, "AGENTS.md")
    old_bytes = agents.read_bytes() if agents.exists() else b""
    old_agents = old_bytes.decode("utf-8-sig")
    new_agents = agents_document(old_agents, previous)
    if old_agents != new_agents:
        bom = b"\xef\xbb\xbf" if old_bytes.startswith(b"\xef\xbb\xbf") else b""
        writes.append((agents, bom + new_agents.encode("utf-8")))
    for path, data in writes:
        atomic_write(path, data)
    record = {"skill": SKILL_NAME, "scope": "workspace", "path": f".agents/skills/{SKILL_NAME}/SKILL.md",
              "files": {name: sha(data) for name, data in files.items()}, "agents_block_sha256": sha(BLOCK.encode())}
    encoded = (json.dumps(record, indent=2) + "\n").encode()
    if not manifest_path.exists() or manifest_path.read_bytes() != encoded:
        atomic_write(manifest_path, encoded)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = install(args.source, args.workspace)
        print(f"Workspace skill installed/verified: {args.workspace.resolve() / result['path']}")
        print("Scope: workspace only; personal Codex settings and pinned kit archives unchanged")
        return 0
    except (InstallError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
