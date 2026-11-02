"""Immutable kit release store (ADR-007) — outside the pinned kit, so no kit version changes.

Why: a release ZIP is rebuilt with zlib. Different zlib builds (Windows Python vs Linux,
zlib vs zlib-ng) compress the same bytes differently, so `freeze-kit` on another machine
produced a different SHA-256 and refused the release; pinned jobs then had no runtime.

How:
- Every frozen release keeps its exact archive next to its manifest: kit/releases/<version>.zip
  (committed to Git, never rewritten). `.cache/kit/` stays a disposable local copy.
- Source is verified against the release by per-file SHA-256 (manifest "files"), which does
  not depend on zlib. If the source matches and the stored archive matches the manifest
  SHA-256, the cache is restored from the store instead of being rebuilt.
- A new version is still frozen by the kit itself; its archive is then published to the store.
- Mismatching source is never "fixed": the kit's own freeze runs and refuses as before.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

VERSION_RX = re.compile(r"^\d+\.\d+\.\d+$")


class StoreError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _manifest(root: Path, version: str) -> dict | None:
    path = root / "kit/releases" / f"{version}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def store_path(root: Path, version: str) -> Path:
    if not VERSION_RX.match(version):
        raise StoreError(f"Invalid kit version: {version}")
    return root / "kit/releases" / f"{version}.zip"


def _artifact(root: Path, manifest: dict) -> Path:
    rel = manifest["artifact"]
    path = (root / rel).resolve()
    if not path.is_relative_to((root / ".cache/kit").resolve()):
        raise StoreError(f"Release artifact path escapes .cache/kit: {rel}")
    return path


def _copy_atomic(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kit-", dir=dst.parent)
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            for block in iter(lambda: inp.read(1 << 20), b""):
                out.write(block)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restore_cache(root: Path, version: str) -> str:
    """Make .cache/kit/<version>/… match the release. Returns 'present', 'restored' or 'missing'."""
    manifest = _manifest(root, version)
    if not manifest:
        return "missing"
    artifact = _artifact(root, manifest)
    stored = store_path(root, version)
    # the immutable store is checked even when the local cache is fine — a damaged store must be noticed
    # on the machine that can still repair it, not first on a fresh clone
    if stored.is_file() and sha256_file(stored) != manifest["sha256"]:
        raise StoreError(f"kit/releases/{version}.zip does not match release {version} SHA-256; restore the original archive")
    if artifact.is_file() and sha256_file(artifact) == manifest["sha256"]:
        return "present"
    if not stored.is_file():
        return "missing"
    if artifact.is_file():
        raise StoreError(f"Cached release {artifact.name} is corrupt; delete it so it can be restored from kit/releases/{version}.zip")
    _copy_atomic(stored, artifact)
    return "restored"


def restore_all(root: Path) -> dict:
    """Restore every missing cached release that has a stored archive (used before kit commands)."""
    result = {}
    for manifest in sorted((root / "kit/releases").glob("*.json")):
        version = manifest.stem
        if VERSION_RX.match(version):
            result[version] = restore_cache(root, version)
    return result


def source_matches(root: Path, version: str) -> bool:
    """Per-file comparison of the current kit source/resources with the frozen release (zlib independent)."""
    manifest = _manifest(root, version)
    if not manifest:
        return False
    from migrate_kit.workspace import release_files      # the source's own packaging rule
    files = {name: hashlib.sha256(data).hexdigest() for name, data in release_files(root).items()}
    return files == manifest.get("files")


def publish(root: Path, version: str) -> str:
    """Copy a freshly frozen cache archive into the immutable store (never overwrite a different one)."""
    manifest = _manifest(root, version)
    if not manifest:
        raise StoreError(f"Release {version} is not frozen")
    artifact = _artifact(root, manifest)
    if not artifact.is_file() or sha256_file(artifact) != manifest["sha256"]:
        raise StoreError(f"Cached release {version} is missing or corrupt; cannot publish it")
    stored = store_path(root, version)
    if stored.is_file():
        if sha256_file(stored) != manifest["sha256"]:
            raise StoreError(f"kit/releases/{version}.zip already exists with different content; releases are immutable")
        return "present"
    _copy_atomic(artifact, stored)
    return "published"


def freeze(root: Path, version: str, kit_freeze) -> dict:
    """freeze-kit through the store: verify+restore an existing release, otherwise let the kit freeze and publish."""
    manifest = _manifest(root, version)
    if manifest and store_path(root, version).is_file() and source_matches(root, version):
        restore_cache(root, version)
        return manifest
    manifest = kit_freeze(root)                          # raises if source differs from a frozen version
    publish(root, version)
    return manifest
