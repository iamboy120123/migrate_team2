"""Regression baselines (tools/regression.py, gap W-12)."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import regression as R

PIPELINE = {
    # minimal stand-in for the production kit: deterministic outputs with generation timestamps
    "pipeline/extract_workflow.py": """
        import json, pathlib, datetime
        w = json.load(open("input/blendata/export_workflow.json"))
        out = pathlib.Path("output/sql/raw"); out.mkdir(parents=True, exist_ok=True)
        for t in w["tasks"]:
            (out / (t["id"] + ".sql")).write_text(t["sql"])
        (out / "_manifest.json").write_text(json.dumps({"generated_at": datetime.datetime.now().isoformat(), "n": len(w["tasks"])}))
    """,
    "pipeline/convert_sql.py": """
        import pathlib
        out = pathlib.Path("output/sql/converted"); out.mkdir(parents=True, exist_ok=True)
        for p in pathlib.Path("output/sql/raw").glob("*.sql"):
            (out / p.name).write_text(p.read_text().replace("ifnull", "COALESCE"))
        pathlib.Path("status").mkdir(exist_ok=True); pathlib.Path("status/REVIEW_FLAGS.md").write_text("flags")
    """,
    "pipeline/gen_dml.py": """
        import pathlib, datetime
        out = pathlib.Path("output/dml"); out.mkdir(parents=True, exist_ok=True)
        for p in pathlib.Path("output/sql/converted").glob("*.sql"):
            (out / p.name).write_text("-- generated " + datetime.datetime.now().isoformat(timespec="seconds") + "\\nINSERT INTO T " + p.read_text())
    """,
    "pipeline/gen_ddl.py": "import pathlib; pathlib.Path('output/ddl').mkdir(parents=True, exist_ok=True); pathlib.Path('output/ddl/01.sql').write_text('CREATE TABLE T (A NUMBER)')",
    "pipeline/gen_dba_prereq.py": "import pathlib; pathlib.Path('output/dba').mkdir(parents=True, exist_ok=True); pathlib.Path('output/dba/01.sql').write_text('-- dba')",
    "pipeline/build_odi_export.py": """
        import pathlib
        out = pathlib.Path("output/odi_export"); out.mkdir(parents=True, exist_ok=True)
        body = "".join(p.read_text() for p in sorted(pathlib.Path("output/dml").glob("*.sql")))
        (out / "PROJ_EXPORT.xml").write_text('<Admin Created="2026-11-02 10:00:00 +0700" />' + body.replace("\\n", " "))
    """,
}


MINI_STEPS = [(script, [], patterns) for script, _a, patterns in R.COMPARE_STEPS if script in PIPELINE]


def make_job(root: Path) -> Path:
    job = root / "job"
    for rel, code in PIPELINE.items():
        p = job / "scripts" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(code))
    (job / "config").mkdir(parents=True)
    (job / "config/config.json").write_text("{}")
    (job / "input/blendata").mkdir(parents=True)
    (job / "input/blendata/export_workflow.json").write_text(json.dumps(
        {"tasks": [{"id": "t1", "sql": "select ifnull(a,1) from s"}, {"id": "t2", "sql": "select regexp_extract(b) from s"}]}))
    import subprocess
    for script, _args, _patterns in MINI_STEPS:
        subprocess.run([sys.executable, str(job / "scripts" / script)], cwd=job, check=True)
    (job / "output/sql/converted/t2.sql").write_text("select REGEXP_SUBSTR(b) from s")    # Phase-4 review edit
    subprocess.run([sys.executable, str(job / "scripts/pipeline/gen_dml.py")], cwd=job, check=True)
    (job / "output/dml/manual_cleanup.sql").write_text("DELETE FROM T")                    # hand-written DML
    subprocess.run([sys.executable, str(job / "scripts/pipeline/build_odi_export.py")], cwd=job, check=True)
    return job


class RegressionToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-regression-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for patcher in (mock.patch.object(R, "BASE_DIR", self.root / "baselines"),
                        mock.patch.object(R, "COMPARE_STEPS", MINI_STEPS)):
            patcher.start(); self.addCleanup(patcher.stop)

    def test_normalize_masks_only_generation_noise_in_generated_layers(self):
        sql = b"-- generated 2026-10-29T20:57:32\r\nSELECT '2026-10-29 21:30:00' FROM dual\r\n"
        self.assertEqual(R.normalize("a.sql", sql, "derived"), b"-- generated <TS>\nSELECT '2026-10-29 21:30:00' FROM dual\n")
        self.assertIn(b"2026-10-29T20:57:32", R.normalize("a.sql", sql, "input"))
        xml = b'<Admin Created="2026-10-29 18:18:23 +0700"/><Encryption exportKeySalt="17b1"/>'
        self.assertEqual(R.normalize("x.xml", xml, "derived"), b'<Admin Created="<TS>"/><Encryption exportKeySalt="<SALT>"/>')

    def test_run_pack_steps_follow_the_jobs_own_packs(self):
        members = {"run_packs/rp02_20261105/MANIFEST.json": b"", "run_packs/rp02_20261105/REPORT.md": b"",
                   "run_packs/rp00_preflight_20261101/P1.sql": b""}
        with mock.patch.object(R, "COMPARE_STEPS", []):
            steps = R.steps_for(members)
        self.assertEqual([(s[0], s[1]) for s in steps], [
            ("runpack/gen_preflight_pack.py", []), ("runpack/gen_run_pack.py", ["--pack", "rp02"]),
            ("runpack/read_run_results.py", ["--pack", "run_packs/rp02_20261105"])])

    def test_archive_is_deterministic(self):
        a = R.write_archive(self.root / "a.zip", {"b.txt": b"2", "a.txt": b"1"})
        b = R.write_archive(self.root / "b.zip", {"a.txt": b"1", "b.txt": b"2"})
        self.assertEqual(a, b)
        with zipfile.ZipFile(self.root / "a.zip") as z:
            self.assertEqual({i.compress_type for i in z.infolist()}, {zipfile.ZIP_STORED})

    def test_capture_classifies_layers_and_replay_detects_changed_converter(self):
        job = make_job(self.root)
        meta = R.capture(job, "mini", "test", "C:\\jobs\\mini")
        self.assertEqual(meta["source"], "C:\\jobs\\mini")
        self.assertEqual(meta["review_delta"], ["output/sql/converted/t2.sql"])
        self.assertIn("_machine/output/sql/converted/t2.sql", {r["path"] for r in meta["files"]})
        self.assertEqual(meta["manual_files"], ["output/dml/manual_cleanup.sql"])
        self.assertEqual(R.verify("mini"), [])
        self.assertTrue(R.replay("mini")["passed"])
        changed = self.root / "changed"
        (changed / "scripts/pipeline").mkdir(parents=True)
        for rel, code in PIPELINE.items():
            text = textwrap.dedent(code).replace('"COALESCE"', '"NVL"') if rel.endswith("convert_sql.py") else textwrap.dedent(code)
            (changed / "scripts" / rel).write_text(text)
        report = R.replay("mini", changed)
        self.assertFalse(report["passed"])
        convert = next(s for s in report["steps"] if s["script"].endswith("convert_sql.py"))
        self.assertEqual([r["path"] for r in convert["rows"]], ["output/sql/converted/t1.sql"])

    def test_tampered_or_missing_archive_is_reported(self):
        R.capture(make_job(self.root), "mini")
        zpath = R.BASE_DIR / "mini/baseline.zip"
        zpath.write_bytes(zpath.read_bytes() + b"x")
        with self.assertRaises(R.RegressionError):
            R.verify("mini")
        zpath.unlink()
        with self.assertRaisesRegex(R.RegressionError, "not on this machine"):
            R.verify("mini")


SS_ESIM = REPO / "tests/regression/ss_esim/baseline.zip"


@unittest.skipUnless(SS_ESIM.is_file(), "SS_ESIM baseline.zip is not on this machine (kept out of Git)")
class SsEsimBaselineTests(unittest.TestCase):
    def test_baseline_is_intact_and_reference_pipeline_reproduces_it(self):
        self.assertEqual(R.verify("ss_esim"), [])
        report = R.replay("ss_esim")
        self.assertTrue(report["passed"], json.dumps(report["steps"], ensure_ascii=False, indent=1)[:3000])

    def test_kit_delivery_runtime_reproduces_it(self):
        report = R.replay("ss_esim", REPO / "kit/delivery/scripts")
        self.assertTrue(report["passed"], json.dumps(report["steps"], ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    unittest.main()
