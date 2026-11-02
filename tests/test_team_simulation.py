from __future__ import annotations

import concurrent.futures
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
from migrate_kit import workspace as W
from migrate_kit.engine import compare_rows, convert, make_dml
from migrate_kit.runtime import run
from migrate_kit.storage import WorkspaceError, find_job, fingerprint, read, write


class TeamSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-team-test-")
        self.addCleanup(self.cleanup_temp)
        self.root = Path(self.temp.name)
        for folder in ("kit", "samples"):
            shutil.copytree(REPO / folder, self.root / folder,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases", "dist"))
        W.initialize(self.root); W.freeze(self.root); W.snapshot(self.root)
        self.job = W.new_job(self.root, "DEMO", "customer_daily", 101,
                             self.root / "samples/workflows/customer_daily.json", "DEMO_ALICE")

    def cleanup_temp(self):
        target = Path(self.temp.name).resolve()
        if not target.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not target.name.startswith("migration-team-test-"):
            raise RuntimeError("Refusing cleanup outside the allocated test directory")
        self.temp.cleanup()

    def approved_run(self):
        W.approve(self.root, self.job, "DEMO_SA")
        result = run(self.root, self.job)
        self.assertEqual(result["state"], "SIMULATION_PASSED", result.get("error"))
        return result

    def test_pinned_runtime_executes_even_if_mutable_source_breaks(self):
        W.approve(self.root, self.job, "DEMO_SA")
        (self.root / "kit/src/migrate_kit/runtime.py").write_text("raise RuntimeError('mutable source must not run')\n")
        result = W.simulate(self.root, self.job)
        self.assertEqual(result["state"], "SIMULATION_PASSED")
        with self.assertRaises(WorkspaceError):
            W.freeze(self.root)

    def test_approval_is_required(self):
        result = run(self.root, self.job)
        self.assertEqual(result["state"], "BLOCKED_REVIEW_REQUIRED")
        self.assertFalse((self.job / "output/odi_export/package.simulation.xml").exists())

    def test_input_change_invalidates_review_and_previous_result(self):
        self.approved_run()
        source = self.job / "input/blendata/export_workflow.json"
        value = read(source); value["tasks"][0]["sql"] += " "
        write(source, value)
        self.assertTrue(any("STALE" in x for x in W.check(self.root)))
        self.assertEqual(run(self.root, self.job)["state"], "BLOCKED_REVIEW_REQUIRED")

    def test_unauthorized_simulated_reviewer_is_rejected(self):
        with self.assertRaises(WorkspaceError):
            W.approve(self.root, self.job, "OTHER_PERSON")

    def test_tampered_kit_archive_is_rejected(self):
        archive = W.verify_pin(self.root, self.job)
        with archive.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(WorkspaceError):
            W.verify_pin(self.root, self.job)

    def test_tampered_snapshot_is_rejected(self):
        pin = read(self.job / "kit.lock.json")
        fixture = self.root / "shared/target/snapshots" / pin["target_snapshot"] / "fixtures/rows.json"
        fixture.write_text("{}")
        with self.assertRaises(WorkspaceError):
            W.verify_pin(self.root, self.job)

    def test_duplicate_issue_and_path_traversal_are_rejected(self):
        with self.assertRaises(WorkspaceError):
            W.new_job(self.root, "OTHER", "another", 101, self.root / "samples/workflows/order_daily.json")
        with self.assertRaises(WorkspaceError):
            W.new_job(self.root, "../escape", "another", 102, self.root / "samples/workflows/order_daily.json")

    def test_correct_job_lookup_and_artifact_is_never_importable(self):
        self.assertEqual(find_job(self.root, "DEMO/customer_daily"), self.job)
        self.approved_run()
        xml = ET.parse(self.job / "output/odi_export/package.simulation.xml").getroot()
        self.assertEqual(xml.tag, "MigrationSimulationPlan")
        self.assertEqual(xml.attrib["importableInODI"], "false")
        bundle = next((self.job / "output/odi_export").glob("*.zip"))
        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("output/odi_export/build-manifest.json"))
        self.assertFalse(manifest["native_odi_smart_export"])
        self.assertFalse(manifest["import_allowed"])
        self.assertEqual(read(self.job / "status/simulation.json")["gates"]["G7"], "NOT_EXECUTED")

    def test_fixture_mismatch_and_zero_rows_block_build(self):
        source = self.job / "input/blendata/export_workflow.json"
        value = read(source)
        value["tasks"][0]["sql"] = value["tasks"][0]["sql"].replace("deleted_flag = 0", "deleted_flag = 1")
        write(source, value); W.approve(self.root, self.job, "DEMO_SA")
        self.assertIn("mismatch", run(self.root, self.job)["error"])
        value["tasks"][0]["sql"] = value["tasks"][0]["sql"].replace("deleted_flag = 1", "deleted_flag = 9")
        write(source, value); W.approve(self.root, self.job, "DEMO_SA")
        self.assertIn("zero fixture rows", run(self.root, self.job)["error"])

    def test_generated_output_tampering_fails_integrity_check(self):
        self.approved_run()
        (self.job / "output/sql/converted/T001.sql").write_text("SELECT 1\n")
        self.assertTrue(any("Generated evidence modified" in x for x in W.check(self.root)))

    def test_competing_local_lock_has_exactly_one_winner(self):
        self.approved_run()
        def attempt(holder):
            try:
                W.acquire_lock(self.root, self.job, holder)
                return holder
            except WorkspaceError:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            winners = [holder for holder in pool.map(attempt, ["DEMO_ALICE", "DEMO_BOB"]) if holder]
        self.assertEqual(len(winners), 1)
        with self.assertRaises(WorkspaceError):
            W.release_lock(self.root, self.job, "OTHER_PERSON")
        W.release_lock(self.root, self.job, winners[0])
        self.assertFalse((self.root / "registry/import_simulation.lock.json").exists())
        self.assertFalse(read(self.job / "status/events.json")[0]["actual_odi_import"])

    def test_shared_snapshot_independent_job_outputs_and_append_rerun(self):
        self.approved_run()
        other = W.new_job(self.root, "DEMO", "order_daily", 102,
                          self.root / "samples/workflows/order_daily.json", "DEMO_BOB")
        W.approve(self.root, other, "DEMO_SA")
        self.assertEqual(run(self.root, other)["state"], "SIMULATION_PASSED")
        pins = ("kit_version", "kit_sha256", "target_snapshot", "target_sha256")   # ai_context is rendered per job
        self.assertEqual({k: read(other / "kit.lock.json")[k] for k in pins}, {k: read(self.job / "kit.lock.json")[k] for k in pins})
        report = read(other / "output/validation/fixture_comparison.json")["checks"][0]
        self.assertEqual(len(report["after_first_run"]), 2)
        self.assertEqual(len(report["after_second_run"]), 4)
        self.assertEqual(W.check(self.root), [])

    def test_deterministic_release_and_missing_cache_can_be_restored(self):
        prior = W.freeze(self.root)
        artifact = self.root / prior["artifact"]
        original = artifact.read_bytes(); artifact.unlink()
        self.assertEqual(W.freeze(self.root), prior)
        self.assertEqual(artifact.read_bytes(), original)

    def test_unsupported_dialect_and_implicit_overwrite_are_rejected(self):
        for sql in ("SELECT sqrt(x) FROM raw_customer", "SELECT x FROM raw_customer; DROP TABLE t", "SELECT * FROM raw_customer"):
            with self.assertRaises(WorkspaceError):
                convert(sql)
        task = read(self.job / "input/blendata/export_workflow.json")["tasks"][1]
        task.pop("overwrite_decision")
        with self.assertRaises(WorkspaceError):
            make_dml(task, "SELECT x FROM sample")

    def test_literals_and_duplicate_counts_are_preserved(self):
        self.assertIn("'IFNULL(x)'", convert("SELECT 'IFNULL(x)' AS X FROM sample"))
        self.assertFalse(compare_rows([[1], [1]], [[1]]))
        self.assertTrue(compare_rows([[2], [1]], [[1], [2]]))


if __name__ == "__main__":
    unittest.main()
