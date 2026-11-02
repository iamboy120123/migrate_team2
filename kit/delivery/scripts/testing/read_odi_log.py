"""
read_odi_log.py — อ่านเวลาต่อ step จาก log ของ ODI (work repository) ของ session ที่รัน แล้วทำใบรายงานความเร็ว (ขั้น 05.3)

ชื่อตามแผน Migration Workspace · ทำงาน 3 จังหวะ (ทุกจังหวะผ่านกติกาขออนุญาตของ workspace.py run-sql):
  1) python scripts/testing/read_odi_log.py --session 48213
       สร้าง run_packs/rp05_perf/ (SELECT จากตาราง SNP_* · ชื่อตารางยังต้องยืนยันกับ ODI 14c ของทีม)
       แล้วแสดงแผนรันด้วย workspace.py run-sql --plan (AI ถามคน 1 = ให้ AI รัน / 2 = ฉันรันเอง)
  2) คนอนุญาต → workspace.py run-sql --execute <แผน> --approved "…"  หรือคนรันเองแล้ววาง CSV ที่ input/run_results/rp05_perf/
  3) python scripts/testing/read_odi_log.py --summary   → status/SUMMARY_05_PERFORMANCE.md

ทีมต้องอนุญาตอ่าน log ของ ODI ก่อน (shared/team.json db.read_odi_log = true) ไม่งั้นแผนจะบอกให้คนรัน
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", help="เลข session ของ ODI ที่รัน scenario (ดูใน Operator)")
    ap.add_argument("--summary", action="store_true", help="อ่าน CSV ใน input/run_results/rp05_perf/ แล้วเขียน SUMMARY_05")
    a = ap.parse_args()
    py = sys.executable
    if a.summary or not a.session:
        return subprocess.run([py, str(HERE / "perf_summary.py")], cwd=str(ROOT)).returncode
    r = subprocess.run([py, str(HERE / "perf_summary.py"), "--make-pack", "--session", a.session], cwd=str(ROOT))
    if r.returncode != 0:
        return r.returncode
    # migrate_team2: SQL runs only through the workspace Oracle adapter (plan → human approval → execute)
    job = json.loads((ROOT / "job.json").read_text(encoding="utf-8"))
    launcher = ROOT.parents[3] / "tools" / "workspace.py"
    return subprocess.run([py, str(launcher), "run-sql", "--job", f"{job['project']}/{job['job']}", "rp05_perf", "--plan"],
                          cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
