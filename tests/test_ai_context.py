"""kit 0.2.0+: knowledge + Claude AI context ship in the pinned release and install into new jobs (W-01/W-02)."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
from migrate_kit import __version__
from migrate_kit import workspace as W
from migrate_kit.storage import read

AI = REPO / "kit/ai/claude"
UNAVAILABLE = re.compile(r"scripts/(?:pipeline|checks|testing|hooks|odi_builder|ws)/\w+\.py|scripts/runpack/(?:gen_\w+|read_run_results)\.py")


class AiContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-ai-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("kit", "samples"):
            shutil.copytree(REPO / folder, self.root / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases"))
        W.initialize(self.root); W.freeze(self.root); W.snapshot(self.root)
        self.job = W.new_job(self.root, "TRAINING", "customer_trial", 201,
                             self.root / "samples/workflows/customer_daily.json", "DEV_A")

    def test_new_job_installs_rendered_context_and_locks_it(self):
        lock = read(self.job / "kit.lock.json")
        self.assertEqual(lock["kit_version"], __version__)
        files = lock["ai_context"]["files"]
        for rel in (".claude/commands/run-pack.md", ".claude/agents/sql-reviewer.md", ".claude/rules/odi-step-sql.md",
                    ".claude/skills/spark-oracle-dialect/SKILL.md", "knowledge/reference/spark-to-oracle-sql.md"):
            self.assertIn(rel, files)
            self.assertTrue((self.job / rel).is_file())
        self.assertNotIn(".claude/SOURCE.json", files)
        self.assertNotIn("knowledge/lessons-learned.md", files)
        claude = (self.job / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("TRAINING/customer_trial", claude)
        self.assertNotIn("Never connect to Oracle", claude)
        for rel in files:
            self.assertIsNone(re.search(r"\{\{(PROJECT|JOB|KIT)\}\}", (self.job / rel).read_text(encoding="utf-8")), rel)
        run_pack = (self.job / ".claude/commands/run-pack.md").read_text(encoding="utf-8")
        self.assertIn("run-sql --job TRAINING/customer_trial", run_pack)
        self.assertIn("⚠️ **migrate_team2 kit", run_pack)               # simulation job: generator scripts absent
        self.assertNotIn("<!-- KIT-BANNER", run_pack)
        self.assertFalse((self.job / "scripts").exists())

    def test_check_rejects_edited_kit_context_but_allows_job_pages(self):
        (self.job / "knowledge/lessons-learned.md").write_text("job lesson", encoding="utf-8")
        with (self.job / "CLAUDE.md").open("a", encoding="utf-8") as f:
            f.write("\n## job notes\n")
        self.assertEqual(W.check(self.root), [])
        (self.job / ".claude/rules/run-pack.md").write_text("weakened rule", encoding="utf-8")
        self.assertTrue(any("Kit-installed file modified" in e for e in W.check(self.root)))

    def test_simulation_still_passes_and_release_is_reproducible(self):
        W.approve(self.root, self.job, "DEMO_SA")
        self.assertEqual(W.simulate(self.root, self.job)["state"], "SIMULATION_PASSED")
        self.assertEqual(W.check(self.root), [])
        self.assertEqual(W.archive_bytes(W.release_files(self.root)), W.archive_bytes(W.release_files(self.root)))


class PortedContentTests(unittest.TestCase):
    def test_every_reference_to_missing_tools_carries_a_banner_marker(self):
        for path in sorted(AI.rglob("*.md")):
            body = path.read_text(encoding="utf-8")
            if UNAVAILABLE.search(body):
                self.assertIn("<!-- KIT-BANNER ", body, path.relative_to(REPO))

    def test_banner_is_rendered_per_job_mode(self):
        marker = '<!-- KIT-BANNER {"scripts": ["scripts/checks/verify_all.py"], "other": ["workspace.py handoff"]} -->\n'
        sim = W.render_banner(marker + "body", "simulation", "0.3.0")
        self.assertIn("scripts/checks/verify_all.py", sim)
        dlv = W.render_banner(marker + "body", "delivery", "0.3.0")
        self.assertNotIn("verify_all", dlv)
        self.assertIn("workspace.py handoff", dlv)
        only_scripts = '<!-- KIT-BANNER {"scripts": ["scripts/x/y.py"], "other": []} -->\n'
        self.assertEqual(W.render_banner(only_scripts + "body", "delivery", "0.3.0"), "body")

    def test_frontmatter_survives_banner(self):
        for folder in ("commands", "agents", "rules"):
            for path in (AI / folder).glob("*.md"):
                body = path.read_text(encoding="utf-8")
                if "<!-- KIT-BANNER " in body and body.startswith("---\n"):
                    self.assertLess(body.index("\n---\n"), body.index("<!-- KIT-BANNER "), path.name)

    def test_provenance_lists_every_ported_file(self):
        record = json.loads((AI / "SOURCE.json").read_text(encoding="utf-8"))
        listed = {f["path"] for f in record["files"]}
        actual = {p.relative_to(REPO / "kit").as_posix() for p in AI.rglob("*") if p.is_file() and p.name != "SOURCE.json"}
        self.assertTrue(actual <= listed, sorted(actual - listed))


if __name__ == "__main__":
    unittest.main()
