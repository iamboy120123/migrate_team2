"""kit 0.3.0 delivery mode: real jobs run the pinned kit scripts (vendored from Migrate_ODI_Team2 2.15.0)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
sys.path.insert(0, str(REPO / "tools"))
import regression as R
from migrate_kit import workspace as W
from migrate_kit.storage import WorkspaceError, read

SS_ESIM = REPO / "tests/regression/ss_esim/baseline.zip"


class DeliveryWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-delivery-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ws"
        for folder in ("kit", "samples", "tools"):
            shutil.copytree(REPO / folder, self.root / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases"))
        W.initialize(self.root); W.freeze(self.root); W.snapshot(self.root)

    def run_py(self, job, *args):
        return subprocess.run([sys.executable, "-B", *args], cwd=job, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)


class NewDeliveryJobTests(DeliveryWorkspace):
    def test_new_delivery_job_layout_lock_and_boundaries(self):
        job = W.new_job(self.root, "NEWP", "demo_delivery", 300, None, "DEV_A", "delivery")
        meta, config, lock = read(job / "job.json"), read(job / "config/config.json"), read(job / "kit.lock.json")
        self.assertEqual(meta["mode"], "delivery")
        self.assertFalse(meta["production_import_allowed"])
        self.assertEqual(config["odi"]["package_name"], "PKG_DEMO_DELIVERY")
        self.assertEqual(config["odi"]["id_base"], meta["id_base"])
        for rel in ("scripts/pipeline/convert_sql.py", "scripts/runpack/gen_run_pack.py", "scripts/hooks/guard_bash.py",
                    ".claude/settings.json", "references/odi-smart-export-format.md", "knowledge/reference/migration-rules.md"):
            self.assertIn(rel, lock["ai_context"]["files"], rel)
        for rel in ("scripts/runpack/dbx.py", "scripts/runpack/run_sql.py"):
            self.assertFalse((job / rel).exists(), rel)                  # SQL goes through tools/dbcore only
        for rel in ("status/GATES.md", "status/OPEN_DECISIONS.md", ".design/README.md"):
            self.assertNotIn("{{", (job / rel).read_text(encoding="utf-8"), rel)
        self.assertIn("mode=delivery", (job / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertNotIn("⚠️ **migrate_team2 kit", (job / ".claude/commands/run-pack.md").read_text(encoding="utf-8"))
        self.assertEqual(W.check(self.root), [])
        for action in (lambda: W.simulate(self.root, job), lambda: W.approve(self.root, job, "DEMO_SA"),
                       lambda: W.acquire_lock(self.root, job, "DEV_A")):
            with self.assertRaises(WorkspaceError):
                action()
        settings = (job / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn('"Edit(scripts/**)"', settings.split('"deny"')[1])
        (job / "scripts/pipeline/gen_dml.py").write_text("patched in job", encoding="utf-8")
        self.assertTrue(any("Kit-installed file modified" in e for e in W.check(self.root)))

    def test_lock_cannot_be_bypassed_and_extra_files_are_found(self):
        import hashlib, json
        job = W.new_job(self.root, "NEWP", "demo_delivery", 300, None, "DEV_A", "delivery")
        target = job / "scripts/pipeline/gen_dml.py"
        target.write_text("patched", encoding="utf-8")
        lock = read(job / "kit.lock.json")
        lock["ai_context"]["files"]["scripts/pipeline/gen_dml.py"] = hashlib.sha256(target.read_bytes()).hexdigest()
        (job / "kit.lock.json").write_text(json.dumps(lock), encoding="utf-8")
        self.assertTrue(any("gen_dml.py" in e for e in W.check(self.root)))      # lock rewritten → still caught
        job2 = W.new_job(self.root, "NEWP", "demo_two", 301, None, "DEV_A", "delivery")
        (job2 / ".claude/commands/extra.md").write_text("not from kit", encoding="utf-8")
        self.assertTrue(any("extra.md" in e for e in W.check(self.root)))

    def test_id_ranges_and_failed_creation(self):
        W.new_job(self.root, "NEWP", "demo_delivery", 300, None, "DEV_A", "delivery")
        with self.assertRaises(WorkspaceError):            # 90000 + 300*1000 already used by demo_delivery
            W.new_job(self.root, "NEWP", "other", 300, None, "DEV_A", "delivery")
        bad = Path(self.temp.name) / "bad_export.json"
        bad.write_text('{"something": 1}', encoding="utf-8")
        with self.assertRaises(WorkspaceError):
            W.new_job(self.root, "NEWP", "j1", 302, bad, "DEV_A", "delivery")
        self.assertFalse((self.root / "projects/NEWP/jobs/j1").exists())
        source = Path(self.temp.name) / "legacy_job"
        (source / "config").mkdir(parents=True); (source / "scripts/pipeline").mkdir(parents=True)
        (source / "scripts/pipeline/convert_sql.py").write_text("# legacy", encoding="utf-8")
        (source / "config/config.json").write_text('{"odi": {"id_base": 390500}}', encoding="utf-8")   # overlaps 390000
        with self.assertRaisesRegex(WorkspaceError, "overlaps"):
            W.import_job(self.root, source, "LEG", "legacy", 9, "DEV_A")
        (source / "config/config.json").write_text('{"odi": {"id_base": 0}}', encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "positive"):
            W.import_job(self.root, source, "LEG", "legacy", 9, "DEV_A")
        self.assertFalse((self.root / "projects/LEG/jobs/legacy").exists())
        self.assertEqual(W.check(self.root), [])

    def test_simulation_jobs_keep_working_beside_delivery_jobs(self):
        W.new_job(self.root, "NEWP", "demo_delivery", 300, None, "DEV_A", "delivery")
        sim = W.new_job(self.root, "DEMO", "customer_daily", 101, self.root / "samples/workflows/customer_daily.json", "A")
        W.approve(self.root, sim, "DEMO_SA")
        self.assertEqual(W.simulate(self.root, sim)["state"], "SIMULATION_PASSED")
        self.assertEqual(W.check(self.root), [])
        self.assertIn("DELIVERY", {r["state"].split()[0] for r in W.report(self.root)})


@unittest.skipUnless(SS_ESIM.is_file(), "SS_ESIM baseline.zip is not on this machine (kept out of Git)")
class ImportSsEsimTests(DeliveryWorkspace):
    def test_imported_job_runs_full_pipeline_from_pinned_kit_and_keeps_reviewed_sql(self):
        meta, members = R.read_archive("ss_esim")
        source = Path(self.temp.name) / "source_job"
        R.materialize(members, source)
        job = W.import_job(self.root, source, "SS_ESIM", "ss_esim_landing_to_discovery", 2, "MANA")
        self.assertTrue((job / "status/IMPORTED_FROM.json").is_file())
        self.assertTrue((job / "CLAUDE.imported.md").is_file() or not (source / "CLAUDE.md").exists())
        self.assertEqual(W.check(self.root), [])
        reviewed = {p: (job / p).read_bytes() for p in meta["review_delta"]}
        for step in (["scripts/pipeline/extract_workflow.py"], ["scripts/pipeline/convert_sql.py"],
                     ["scripts/pipeline/gen_dml.py"], ["scripts/pipeline/gen_ddl.py"], ["scripts/pipeline/gen_dba_prereq.py"],
                     ["scripts/pipeline/build_odi_export.py"], ["scripts/pipeline/validate_odi_xml.py"],
                     ["scripts/runpack/gen_run_pack.py", "--pack", "rp01"],
                     ["scripts/runpack/read_run_results.py", "--pack", "run_packs/rp01_20261029"]):
            r = self.run_py(job, *step)
            self.assertEqual(r.returncode, 0, f"{step}: {r.stdout[-800:]}{r.stderr[-800:]}")
        self.assertEqual({p: (job / p).read_bytes() for p in reviewed}, reviewed)     # R-08: Phase-4 SQL kept
        self.assertTrue((job / "status/REVIEW_FLAGS.machine.md").is_file())           # decided flags kept too
        # Gate verdict must equal what the job's own 2.15.0 scripts say about the same content
        own = self.run_py(source, "scripts/checks/check_gate.py", "G3")
        kit = self.run_py(job, "scripts/checks/check_gate.py", "G3")
        self.assertNotIn("Traceback", kit.stdout + kit.stderr)
        self.assertEqual(kit.stdout.splitlines()[0], own.stdout.splitlines()[0])
        self.assertTrue((job / "output/sql/converted_machine").is_dir())
        self.assertEqual(W.check(self.root), [])


if __name__ == "__main__":
    unittest.main()
