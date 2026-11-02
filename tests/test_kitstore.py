"""Immutable kit release store (ADR-007): releases restore on any machine without rebuilding."""
from __future__ import annotations

import contextlib
import io

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
sys.path.insert(0, str(REPO / "tools"))
import kitstore
from migrate_kit import __version__
from migrate_kit import workspace as W
from migrate_kit.storage import read



class KitStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-kitstore-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("kit", "samples", "tools"):
            shutil.copytree(REPO / folder, self.root / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "dist"))
        W.initialize(self.root)

    def launch(self, *argv):
        import runpy
        out = io.StringIO()
        saved = sys.argv
        sys.argv = [str(self.root / "tools/workspace.py"), *argv]
        try:
            with contextlib.redirect_stdout(out):
                try:
                    runpy.run_path(str(self.root / "tools/workspace.py"), run_name="__main__")
                    code = 0
                except SystemExit as exc:
                    code = exc.code or 0
        finally:
            sys.argv = saved
        return code, out.getvalue()

    def test_committed_release_restores_without_rebuilding_on_this_machine(self):
        manifest = read(self.root / f"kit/releases/{__version__}.json")
        self.assertTrue((self.root / f"kit/releases/{__version__}.zip").is_file(), "release archive must be committed")
        self.assertTrue(kitstore.source_matches(self.root, __version__))
        code, out = self.launch("freeze-kit")
        self.assertEqual(code, 0, out)
        artifact = self.root / manifest["artifact"]
        self.assertEqual(kitstore.sha256_file(artifact), manifest["sha256"])
        W.snapshot(self.root)
        job = W.new_job(self.root, "DEMO", "customer_daily", 101, self.root / "samples/workflows/customer_daily.json", "A")
        W.approve(self.root, job, "DEMO_SA")
        self.assertEqual(W.simulate(self.root, job)["state"], "SIMULATION_PASSED")
        artifact.unlink()                                   # cache lost (fresh clone / CI)
        code, out = self.launch("check")
        self.assertEqual(code, 0, out)
        self.assertTrue(artifact.is_file())

    def test_tampered_store_or_cache_is_refused(self):
        stored = self.root / f"kit/releases/{__version__}.zip"
        stored.write_bytes(stored.read_bytes() + b"x")
        with self.assertRaises(kitstore.StoreError):
            kitstore.restore_cache(self.root, __version__)
        code, out = self.launch("check")
        self.assertEqual(code, 1)
        self.assertIn("does not match", out)

    def test_damaged_store_is_noticed_even_with_a_good_cache(self):
        self.assertEqual(self.launch("freeze-kit")[0], 0)                  # cache restored and valid
        stored = self.root / f"kit/releases/{__version__}.zip"
        stored.write_bytes(stored.read_bytes() + b"x")
        code, out = self.launch("check")
        self.assertEqual(code, 1)
        self.assertIn("does not match", out)

    def test_changed_source_with_same_version_is_still_refused(self):
        before = (self.root / f"kit/releases/{__version__}.zip").read_bytes()
        runtime = self.root / "kit/src/migrate_kit/engine.py"
        runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        self.assertFalse(kitstore.source_matches(self.root, __version__))
        code, out = self.launch("freeze-kit")
        self.assertEqual(code, 1)
        self.assertIn("Bump kit version", out)
        self.assertEqual((self.root / f"kit/releases/{__version__}.zip").read_bytes(), before)

    def test_new_release_is_published_once_and_is_immutable(self):
        for p in (self.root / "kit/releases").glob("*"):
            p.unlink()
        manifest = kitstore.freeze(self.root, __version__, W.freeze)
        stored = self.root / f"kit/releases/{__version__}.zip"
        self.assertEqual(kitstore.sha256_file(stored), manifest["sha256"])
        self.assertEqual(kitstore.publish(self.root, __version__), "present")
        stored.write_bytes(b"other")
        with self.assertRaises(kitstore.StoreError):
            kitstore.publish(self.root, __version__)

    def test_store_path_rejects_bad_versions(self):
        with self.assertRaises(kitstore.StoreError):
            kitstore.store_path(self.root, "../0.1.0")


if __name__ == "__main__":
    unittest.main()
