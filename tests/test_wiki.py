"""kit 0.4.0 Wiki: root wiki-* commands, team layer (shared/knowledge) and approved kit-promote."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
sys.path.insert(0, str(REPO / "tools"))
import wikicmd
from migrate_kit import workspace as W

LESSON = ("| L90 | 03 · review | `NVL('', x)` คืน x เพราะ Oracle ถือ '' เป็น NULL | ผลต่างจาก Spark เงียบ ๆ | "
          "ใช้ CASE WHEN col IS NULL · generic | run_packs/rp02/REPORT.md แถว 4 | 2026-11-02 · agent |")
LOCAL = ("| L91 | 05 · import | ชื่อ context ของลูกค้าเฉพาะงานนี้ | import ผิด context | ใช้ CTX_X | DB_RUN_LOG | 2026-11-02 · agent |")


class WikiWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-wiki-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ws"
        for folder in ("kit", "samples", "tools", "shared/knowledge"):
            shutil.copytree(REPO / folder, self.root / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases"))
        W.initialize(self.root); W.freeze(self.root); W.snapshot(self.root)
        self.job = W.new_job(self.root, "NEWP", "demo_delivery", 300, None, "DEV_A", "delivery")
        lessons = self.job / "knowledge/lessons-learned.md"
        lessons.write_text(lessons.read_text(encoding="utf-8").rstrip("\n") + "\n" + LESSON + "\n" + LOCAL + "\n", encoding="utf-8")

    def cmd(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = wikicmd.main(self.root, list(argv))
        return code, out.getvalue()

    def approvers(self, names):
        path = self.root / "shared/approvers.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["knowledge_approvers"] = names
        path.write_text(json.dumps(data), encoding="utf-8")


class WikiCommandTests(WikiWorkspace):
    def test_search_and_step_cover_team_layer_from_root(self):
        code, out = self.cmd("wiki-search", "kit update")
        self.assertEqual(code, 0)
        self.assertIn("ทีม (shared/knowledge)", out)
        self.assertIn("SIM-L02", out)
        code, out = self.cmd("wiki-step", "02", "--job", "NEWP/demo_delivery", "--limit", "40")
        self.assertIn("SIM-L01", out)
        self.assertIn("[ทีม]", out)
        code, out = self.cmd("wiki-check")
        self.assertEqual(code, 0, out)
        self.assertEqual(W.check(self.root), [])

    def test_missing_evidence_in_team_layer_fails_workspace_check(self):
        team = self.root / "shared/knowledge/lessons-learned.md"
        team.write_text(team.read_text(encoding="utf-8") + "| SIM-L04 | 02 · x | ปัญหา | ผล | วิธี · generic |  | ที่มา |\n", encoding="utf-8")
        self.assertTrue(any("SIM-L04" in e and e.startswith("wiki:") for e in W.check(self.root)))

    def test_job_copy_of_the_engine_sees_the_team_layer(self):
        r = subprocess.run([sys.executable, "-B", "scripts/ws/wiki.py", "--search", "kit update"], cwd=self.job,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SIM-L02", r.stdout)


class KitPromoteTests(WikiWorkspace):
    def test_plan_needs_a_person_and_a_listed_approver(self):
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90")
        self.assertEqual(code, wikicmd.EXIT_NEEDS_APPROVAL, out)
        plan_id = out.split("แผน kit-promote ")[1].split()[0]
        team = self.root / "shared/knowledge/lessons-learned.md"
        before = team.read_bytes()
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--plan-id", plan_id, "--approved", "TL_A 2026-11-02")
        self.assertEqual(code, 1); self.assertIn("approvers.json", out)
        self.assertEqual(team.read_bytes(), before)                                     # nothing written
        self.approvers(["TL_A"])
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--plan-id", "0000000000", "--approved", "TL_A 2026-11-02")
        self.assertEqual(code, 1); self.assertIn("plan_id", out)
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--plan-id", plan_id, "--approved", "TL_A")
        self.assertEqual(code, 1)                                                       # date required
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--plan-id", plan_id, "--approved", "TL_A 2026-11-02")
        self.assertEqual(code, 0, out)
        text = team.read_text(encoding="utf-8")
        self.assertIn("| LT1 | 03 · review |", text)
        self.assertIn("จาก NEWP/demo_delivery L90 · อนุมัติ TL_A 2026-11-02", text)
        ledger = json.loads((self.root / "shared/knowledge/PROMOTIONS.json").read_text(encoding="utf-8"))["entries"]
        self.assertEqual([(e["id"], e["from_id"], e["approved_by"]) for e in ledger], [("LT1", "L90", "TL_A")])
        self.assertEqual(W.check(self.root), [])
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90")
        self.assertEqual(code, 1); self.assertIn("promote แล้วเป็น LT1", out)
        # other jobs see LT1 once (team layer), not the job's own copy as well
        W.new_job(self.root, "NEWP", "second", 301, None, "DEV_A", "delivery")
        code, out = self.cmd("wiki-step", "03", "--job", "NEWP/second", "--limit", "80")
        self.assertIn("LT1", out)
        self.assertNotIn("L90 ", out)

    def test_ineligible_lessons_and_script_patches_are_refused(self):
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L91", "--lesson", "L39", "--lesson", "L404")
        self.assertEqual(code, 1)
        self.assertIn("L91: ไม่ได้ระบุว่าใช้ได้ทุกงาน", out)
        self.assertIn("L39: เป็นบทเรียนที่ติดมากับ kit", out)
        self.assertIn("L404: ไม่พบ", out)
        code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--k", "K8-x")
        self.assertEqual(code, 2); self.assertIn("ผู้ดูแล kit", out)

    def test_team_history_is_protected_without_git(self):
        self.approvers(["TL_A"])
        _code, out = self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90")
        plan_id = out.split("แผน kit-promote ")[1].split()[0]
        self.cmd("kit-promote", "--job", "NEWP/demo_delivery", "--lesson", "L90", "--plan-id", plan_id, "--approved", "TL_A 2026-11-02")
        team = self.root / "shared/knowledge/lessons-learned.md"
        original = team.read_text(encoding="utf-8")
        team.write_text(original.replace("Oracle ถือ", "Oracle มอง"), encoding="utf-8")
        _code, out = self.cmd("wiki-check")
        self.assertIn("ถูกแก้หลัง promote", out)
        team.write_text("\n".join(l for l in original.splitlines() if not l.startswith("| LT1 ")) + "\n", encoding="utf-8")
        self.assertTrue(any("LT1" in e and "หายไป" in e for e in W.check(self.root)))


if __name__ == "__main__":
    unittest.main()
