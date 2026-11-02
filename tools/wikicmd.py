"""Workspace Wiki commands (gap W-wiki · kit 0.4.0): wiki-search, wiki-step, wiki-check, kit-promote.

One engine: kit/delivery/scripts/ws/wiki.py (the same file delivery jobs run as scripts/ws/wiki.py),
loaded from the workspace's kit source so every job — simulation or delivery, any pinned kit — can use it.
kit-promote copies an approved, generic job lesson into the team layer (shared/knowledge) — never into kit/
and never without a person: plan → person approves → apply with the same plan id.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

COMMANDS = ("wiki-search", "wiki-step", "wiki-check", "kit-promote")
EXIT_NEEDS_APPROVAL = 3


def engine(root: Path):
    path = root / "kit/delivery/scripts/ws/wiki.py"
    if not path.is_file():
        raise SystemExit(f"ERROR: Wiki engine not found: {path}")
    spec = importlib.util.spec_from_file_location("migrate_wiki", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_job(root: Path, ref: str) -> Path:
    parts = ref.replace("\\", "/").strip("/").split("/")
    if len(parts) != 2:
        raise SystemExit("ERROR: --job ต้องเป็น <Project>/<Job>")
    job = root / "projects" / parts[0] / "jobs" / parts[1]
    if not (job / "job.json").is_file():
        raise SystemExit(f"ERROR: ไม่พบงาน {ref}")
    return job


def parser():
    ap = argparse.ArgumentParser(prog="workspace.py")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("wiki-search", help="ค้น Wiki ทุกชั้น (kit · ทีม · ระบบปลายทาง · project · งาน)")
    p.add_argument("term"); p.add_argument("--layer", choices=["kit", "team", "target", "project", "job"])
    p = sp.add_parser("wiki-step", help="บทเรียนที่เกี่ยวกับขั้น 01–06 (อ่านก่อนเริ่มขั้น)")
    p.add_argument("step", choices=["01", "02", "03", "04", "05", "06"]); p.add_argument("--job"); p.add_argument("--limit", type=int, default=12)
    sp.add_parser("wiki-check", help="ตรวจ Wiki: หลักฐาน · ข้อมูลลับ · เลขซ้ำ · ledger ของ kit-promote")
    p = sp.add_parser("kit-promote", help="ส่งบทเรียน generic ของงานเข้าชั้นทีม (shared/knowledge) — คนอนุมัติ")
    p.add_argument("--job", required=True, help="<Project>/<Job>")
    p.add_argument("--lesson", action="append", required=True, help="เลขบทเรียนในหัวข้อ 2 ของงาน เช่น L43 (ซ้ำได้)")
    p.add_argument("--plan-id", help="plan id ที่คนเห็นและอนุมัติ")
    p.add_argument("--approved", help='"<ชื่อผู้อนุมัติ> <YYYY-MM-DD>" — คนพิมพ์เอง ห้าม AI ใส่แทน')
    p.add_argument("--k", help=argparse.SUPPRESS)
    return ap


def main(root: Path, argv) -> int:
    args = parser().parse_args(argv)
    wiki = engine(root)
    if args.cmd == "wiki-search":
        wiki.cmd_search(args.term, args.layer, False, root)
        return 0
    if args.cmd == "wiki-step":
        wiki.cmd_step(args.step, args.limit, find_job(root, args.job) if args.job else None, root)
        return 0
    if args.cmd == "wiki-check":
        errs, warns = wiki.check(root)
        for e in errs:
            print(f"  ❌ {e}")
        for x in warns:
            print(f"  ⚠️  {x}")
        print(f"Wiki check: ERROR {len(errs)} · WARN {len(warns)}")
        return 1 if errs else 0
    # kit-promote
    if args.k:
        print("ERROR: การแก้สคริปต์ (K#) ไม่ส่งผ่าน kit-promote ใน migrate_team2 — ผู้ดูแล kit แก้ใน kit/ แล้วออก kit รุ่นใหม่ "
              "(docs/TEAM_WORKFLOW.md) · kit-promote รับเฉพาะบทเรียน (--lesson L#)")
        return 2
    job = find_job(root, args.job)
    if args.approved or args.plan_id:
        if not (args.approved and args.plan_id):
            print("ERROR: ต้องใส่ทั้ง --plan-id และ --approved")
            return 2
        try:
            rows = wiki.promote_apply(root, job, args.lesson, args.plan_id, args.approved)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        for r in rows:
            print(f"PROMOTED {args.job} {r['from_id']} → {r['id']} (shared/knowledge/lessons-learned.md)")
        print("ทุกงานเห็นทันทีผ่าน wiki-search / wiki-step · ledger: shared/knowledge/PROMOTIONS.json")
        return 0
    plan = wiki.promote_plan(root, job, args.lesson)
    print(f"แผน kit-promote {plan['plan_id']} · จาก {plan['job']} → shared/knowledge/lessons-learned.md")
    for r in plan["rows"]:
        tag, problem, impact, how, evidence = r["cells"]
        print(f"\n  {r['from_id']} → {r['id']}  [{tag}]\n    ปัญหา: {problem}\n    ผลถ้าพลาด: {impact}\n    วิธีทำ: {how}\n    หลักฐาน: {evidence}")
    if plan["problems"]:
        print("\nส่งไม่ได้:")
        for p in plan["problems"]:
            print(f"  ❌ {p}")
        return 1
    print(f"\n❓ ให้ผู้อนุมัติ (shared/approvers.json → knowledge_approvers) อ่านข้อความข้างบน — ต้องไม่มีข้อมูลลูกค้า / ชื่อระบบภายในที่ไม่ควรออกนอกงาน"
          f"\n   อนุมัติแล้วรัน: python tools/workspace.py kit-promote --job {args.job} "
          + " ".join(f"--lesson {i}" for i in args.lesson) + f' --plan-id {plan["plan_id"]} --approved "<ชื่อ> <YYYY-MM-DD>"')
    return EXIT_NEEDS_APPROVAL


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parents[1], sys.argv[1:]))
