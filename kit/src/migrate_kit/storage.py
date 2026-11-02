from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class WorkspaceError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def safe_name(value):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,49}", value):
        raise WorkspaceError(f"Invalid name: {value!r}; use letters, digits, underscore (max 50)")
    return value


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise WorkspaceError(f"Path escapes expected directory: {relative}")
    return path


def jobs(root):
    return sorted(Path(root).glob("projects/*/jobs/*/job.json"))


def find_job(root, name):
    matches = [p.parent for p in jobs(root) if p.parent.name == name or
               f"{p.parents[2].name}/{p.parent.name}" == name]
    if len(matches) != 1:
        raise WorkspaceError(f"Expected one job for {name!r}, found {len(matches)}; use PROJECT/job")
    return matches[0]


def file_map(folder, exclude=()):
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and not any(part in exclude for part in p.relative_to(folder).parts)}


def fingerprint(job):
    """Only governed inputs, never generated reports or simulated approvals."""
    return object_digest({name: file_map(job / name) for name in ("input", "config")} |
                         {"kit.lock.json": digest(job / "kit.lock.json")})
