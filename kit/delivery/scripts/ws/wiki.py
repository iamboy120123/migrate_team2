"""
wiki.py — Wiki / Knowledge ของ workspace (2.11.0 · migrate_team2 kit 0.4.0): อ่าน · ค้นหา · ตรวจ · promote ความรู้ 5 ชั้น

ชั้นความรู้ (กว้าง → แคบ · ชั้นแคบชนะเมื่อขัดกัน: การตัดสินที่อนุมัติแล้ว > บทเรียนทีม > กฎ kit > reference):
  kit      kit/knowledge/ (lessons-learned ที่ติดมากับ kit · glossary-kit · reference/ · README = หน้าแรกของ Wiki)
  team     shared/knowledge/ (บทเรียนทีมของ workspace นี้ · เพิ่มด้วย workspace.py kit-promote เท่านั้น · ledger PROMOTIONS.json)
  target   shared/target/ (environment-facts · CHANGELOG ของระบบปลายทาง)
  project  projects/<P>/_project/ (glossary · DECISIONS)
  job      projects/<P>/jobs/<งาน>/knowledge/ (lessons-learned · environment-facts · glossary) + status/OPEN_DECISIONS.md

Usage (จากโฟลเดอร์งาน หรือ root ของ workspace):
    python scripts/ws/wiki.py --step 03            # บทเรียนที่เกี่ยวกับขั้นนี้ (ทีม + project + งานนี้ + งานอื่น) — อ่านก่อนเริ่มขั้น
    python scripts/ws/wiki.py --search overwrite   # ค้นทุกชั้น (เพิ่ม --remote = ค้นใน branch งานของคนอื่นที่ fetch แล้ว)
    python scripts/ws/wiki.py --check              # ตรวจ: บทเรียนมีหลักฐาน · ไม่มีข้อมูลลับ · ไม่ลบประวัติ · คำแนะนำอ้าง L#
ที่ root ของ workspace ใช้ `python tools/workspace.py wiki-search | wiki-step | wiki-check | kit-promote` (engine ตัวเดียวกัน)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parents[2]          # root ของงาน (เมื่ออยู่ในงาน)
ID_RX = re.compile(r"^(L-?T\d+|L\d+|E\d+|SIM-L\d+)$", re.I)
TEAM_DIR = ("shared", "knowledge")
TEAM_FILE = "lessons-learned.md"
LEDGER = "PROMOTIONS.json"
TEAM_SECTION = "## 2. บทเรียนจากงาน (kit-promote)"
TEAM_HEADER = "| # | หมวด / ขั้น | ปัญหาที่เจอ | ผลถ้าพลาด | วิธีทำ | หลักฐาน | ที่มา / อนุมัติ |"
GENERIC = re.compile(r"generic|ทุกงาน", re.I)
SECRET = re.compile(r"(password|passwd|pwd|รหัสผ่าน)\s*[:=]\s*['\"]?[^\s'\"<>{}$,)]{3,}|jdbc:oracle:thin:[^@\s]+/[^@\s]+@|-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)
SECRET_OK = re.compile(r"ORA_R[OW]_PASSWORD|<password>|\*\*\*|(password|รหัสผ่าน)\s*[:=]\s*(null|none|\"\"|''|<)", re.I)
NEW_HEADER = "| # | หมวด / ขั้น | ปัญหาที่เจอ | ผลถ้าพลาด | วิธีทำ | หลักฐาน | วันที่ / โดย |"
NEW_SECTION = "## 2. บทเรียนของงานนี้ (/lesson)"
STEPS = {
    "01": ("ตรวจไฟล์ (intake files)", ["export", "json", "input", "intake", "ไฟล์", "workflow", "task"]),
    "02": ("ถามและเสนอแนวทาง", ["intake", "decision", "overwrite", "scope", "landing", "partition", "truncate", "delete", "q", "waiver", "procedure", "mapping"]),
    "03": ("pre-flight · convert · review SQL", ["spark", "sql", "nls", "timezone", "regex", "cast", "convert", "review", "ansi", "timestamp", "preflight", "pre-flight", "qualify", "schema", "performance", "explain", "compile"]),
    "04": ("build + grade", ["xml", "smart export", "globalid", "package", "procedure", "build", "gen-export", "validate", "verify", "grade", "zip", "guid"]),
    "05": ("import และรันจริงใน ODI DEV", ["import", "scenario", "topology", "ddl", "seed", "run pack", "snp", "log", "lag", "mock", "deploy", "session", "commit"]),
    "06": ("เทียบผลและอนุมัติ", ["d1", "d2", "d3", "compare", "validation", "cutover", "baseline", "assertion", "expected", "เทียบ", "parallel"]),
}


# ---------------------------------------------------------------- ที่อยู่
def ws_root(start: Path | None = None) -> Path | None:
    s = (start or HERE).resolve()
    for p in [s, *s.parents]:
        if (p / "workspace.json").exists() or (p / "tools" / "workspace.py").exists():
            return p
    return None


def kit_knowledge(w: Path) -> Path:
    return w / "kit" / "knowledge"


def team_dir(w: Path) -> Path:
    return w.joinpath(*TEAM_DIR)


def ledger(w: Path) -> list[dict]:
    f = team_dir(w) / LEDGER
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("entries", []) if f.exists() else []
    except Exception:
        return [{"broken": str(f)}]


def job_key(job: Path) -> str:
    return f"{job.parent.parent.name}/{job.name}"           # projects/<P>/jobs/<J> → P/J


def sources(w: Path) -> list[tuple[str, str, Path]]:
    """(ชั้น, ชื่อ, ไฟล์) ทุกไฟล์ความรู้ในเครื่อง"""
    out = []
    kk = kit_knowledge(w)
    for f in sorted(kk.glob("*.md")) if kk.exists() else []:
        out.append(("kit", f.name, f))
    for f in sorted((kk / "reference").rglob("*.md")) if (kk / "reference").exists() else []:
        out.append(("kit", "reference/" + f.relative_to(kk / "reference").as_posix(), f))
    td = team_dir(w)
    for f in sorted(td.glob("*.md")) if td.exists() else []:
        out.append(("team", f.name, f))
    for n in ("environment-facts.md", "CHANGELOG.md", "SOURCE.md"):
        f = w / "shared" / "target" / n
        if f.exists():
            out.append(("target", n, f))
    for f in sorted((w / "projects").glob("*/_project/*.md")):
        out.append(("project", f"{f.parts[-3]}/{f.name}", f))
    for j in sorted((w / "projects").glob("*/jobs/*")):
        if not j.is_dir():
            continue
        for rel in ("knowledge/lessons-learned.md", "knowledge/environment-facts.md", "knowledge/glossary.md", "status/OPEN_DECISIONS.md",
                    "status/BUSINESS_RULES.md", "status/GAP_ANALYSIS.md"):
            f = j / rel
            if f.exists():
                out.append(("job", f"{j.name}/{rel}", f))
    return out


def rd(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------- บทเรียน
def lesson_rows(text: str, src: str) -> list[dict]:
    """แถวตารางที่ช่องแรกเป็น L# / LT# / E# · section = หัวข้อ ## ที่อยู่ · ใหม่ = อยู่ใต้ NEW_SECTION หรือไฟล์ของทีม"""
    out, sec, head = [], "", []
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            sec = line.strip("# ").strip()
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] in ("#", "ID"):
            head = cells
            continue
        if cells and ID_RX.match(cells[0].replace("**", "")):
            row = {"id": cells[0].replace("**", ""), "cells": cells, "head": head, "section": sec, "line": i, "src": src, "text": " ".join(cells[1:])}
            for k, names in (("evidence", ("หลักฐาน", "evidence")), ("tag", ("หมวด", "category"))):
                idx = next((n for n, h in enumerate(head) if any(x in h.lower() for x in names)), None)
                row[k] = cells[idx] if idx is not None and idx < len(cells) else ""
                row["has_" + k] = idx is not None
            out.append(row)
    return out


def all_lessons(w: Path, job: Path | None = None) -> list[dict]:
    rows = []
    team = kit_knowledge(w) / "lessons-learned.md"
    for r in lesson_rows(rd(team), "ทีม (kit/knowledge)"):
        r["layer"] = "kit"
        rows.append(r)
    for r in lesson_rows(rd(team_dir(w) / TEAM_FILE), "ทีม (shared/knowledge)"):
        r["layer"] = "team"
        rows.append(r)
    promoted = {(e.get("from_job"), e.get("from_id")) for e in ledger(w)}
    kit_ids = {(r["id"], r["text"]) for r in rows if r["layer"] == "kit"}
    for f in sorted((w / "projects").glob("*/jobs/*/knowledge/lessons-learned.md")):
        jn = f.parts[-3]
        mine = job is not None and f.resolve() == (job / "knowledge/lessons-learned.md").resolve()
        for r in lesson_rows(rd(f), jn):
            if not mine and NEW_SECTION.strip("# ").split(" (")[0] not in r["section"]:
                continue                                            # งานอื่น: เฉพาะบทเรียนใหม่ของงานนั้น (ของ kit ซ้ำกันทุกงาน)
            if not mine and ((job_key(f.parents[1]), r["id"]) in promoted or (r["id"], r["text"]) in kit_ids):
                continue                                            # promote แล้ว (อยู่ชั้นทีม) หรือเป็นแถวที่ kit ให้มา
            r["layer"] = "job" if mine else "other-job"
            rows.append(r)
    return rows


def relevant(rows: list[dict], step: str) -> list[dict]:
    name, kws = STEPS.get(step, ("", []))
    out = []
    for r in rows:
        t = (r["tag"] + " " + r["text"]).lower()
        score = (5 if re.search(rf"\b{step}\b", r["tag"]) else 0) + sum(1 for k in kws if k in t)
        if score:
            out.append((score, r))
    order = {"job": 0, "team": 1, "kit": 2, "other-job": 3}
    out.sort(key=lambda x: (-x[0], order.get(x[1]["layer"], 9)))
    return [r for _, r in out]


def cmd_step(step: str, limit: int, job: Path | None = None, w: Path | None = None):
    w = w or ws_root()
    if job is None:
        job = HERE if (HERE / "knowledge").exists() and w and HERE != w else None
    rows = relevant(all_lessons(w, job), step) if w else []
    name = STEPS.get(step, ("?", []))[0]
    print(f"📚 Wiki · ก่อนเริ่มขั้น {step} {name} — บทเรียนที่เกี่ยวข้อง {len(rows)} ข้อ (แสดง {min(len(rows), limit)})")
    for r in rows[:limit]:
        where = {"kit": "kit", "team": "ทีม", "job": "งานนี้", "other-job": f"งาน {r['src']}"}.get(r["layer"], r["layer"])
        print(f"  {r['id']:<6} [{where}] {r['text'][:150]}")
    if w and job:
        dec = []
        for f in sorted((w / "projects").glob("*/_project/DECISIONS.md")):
            if job.resolve().is_relative_to(f.parents[1].resolve()):
                dec = [l for l in rd(f).splitlines() if l.startswith("| ") and not l.startswith("| #") and not l.startswith("|---")]
        if dec:
            print(f"  + การตัดสินระดับ project {len(dec)} ข้อ (projects/<P>/_project/DECISIONS.md)")
    print("  → เสนอแนวทางในขั้นนี้ต้องเขียน \"อ้างอิง: L# …\" (หรือ \"อ้างอิง: ไม่มีบทเรียนที่เกี่ยวข้อง\") · ค้นเพิ่ม: --search <คำ>")


def cmd_search(term: str, layer: str | None, remote: bool, w: Path | None = None):
    w = w or ws_root()
    if not w:
        raise SystemExit("[ERROR] ไม่พบ workspace")
    rx = re.compile(re.escape(term), re.I)
    hits = {}
    for lay, name, f in sources(w):
        if layer and lay != layer:
            continue
        for i, line in enumerate(rd(f).splitlines(), 1):
            if rx.search(line):
                cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
                tag = cells[0] if cells and ID_RX.match(cells[0].replace("**", "")) else ""
                hits.setdefault(lay, []).append(f"{name}:{i}  {(tag + ' ') if tag else ''}{' '.join(line.split())[:160]}")
    if remote and (w / ".git").exists():
        try:
            refs = subprocess.run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/job/"], cwd=str(w), capture_output=True, text=True).stdout.split()
            for ref in refs:
                r = subprocess.run(["git", "grep", "-n", "-i", "-F", term, ref, "--", "projects/*/jobs/*/knowledge/*.md", "projects/*/_project/*.md"],
                                   cwd=str(w), capture_output=True, text=True)
                for l in r.stdout.splitlines()[:40]:
                    hits.setdefault("remote", []).append(" ".join(l.split())[:200])
        except Exception:
            pass
    total = sum(len(v) for v in hits.values())
    print(f"🔎 Wiki · ค้น \"{term}\" — พบ {total} บรรทัด" + ("" if remote else " (เพิ่ม --remote = ค้นใน branch งานของคนอื่นที่ fetch แล้ว)"))
    names = {"kit": "1 · kit (ทุกงาน)", "team": "2 · ทีม (shared/knowledge)", "target": "3 · ระบบปลายทาง", "project": "4 · project",
             "job": "5 · งาน", "remote": "branch งานที่ยังไม่ merge"}
    for lay in ("kit", "team", "target", "project", "job", "remote"):
        if hits.get(lay):
            print(f"\n  ── {names[lay]} ({len(hits[lay])})")
            for h in hits[lay][:30]:
                print(f"    {h}")
            if len(hits[lay]) > 30:
                print(f"    … อีก {len(hits[lay]) - 30} บรรทัด")


# ---------------------------------------------------------------- ตรวจ
def _git_show(w: Path, ref: str, rel: str) -> str:
    try:
        r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=str(w), capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def check(w: Path, base: str = "HEAD") -> tuple[list[str], list[str]]:
    """คืน (errors, warns) — ใช้โดย workspace.py check / wiki-check และ CI

    ต้องมีหลักฐาน: บทเรียนชั้นทีม (shared/knowledge) ทุกข้อ · บทเรียนใหม่ของงาน (หัวข้อ 2) · แถวของ kit ที่ตารางมีช่องหลักฐาน
    ไม่ลบประวัติ: ledger ของ kit-promote (ไม่ต้องมี git) + เทียบ git base เมื่อเป็น repo
    """
    errs, warns = [], []
    team = team_dir(w) / TEAM_FILE
    files = ([kit_knowledge(w) / "lessons-learned.md", team] + sorted((w / "projects").glob("*/jobs/*/knowledge/lessons-learned.md"))
             + sorted((w / "projects").glob("*/_project/lessons-learned.md")))
    for f in files:
        if not f.exists():
            continue
        rel = f.relative_to(w).as_posix()
        layer = "kit" if f.parent == kit_knowledge(w) else "team" if f == team else "project" if "_project" in f.parts else "job"
        rows = lesson_rows(rd(f), rel)
        seen = {}
        for r in rows:
            if r["id"] in seen and layer in ("team", "job"):
                errs.append(f"{rel}:{r['line']} เลข {r['id']} ซ้ำกับบรรทัด {seen[r['id']]} — เลขบทเรียนต้องไม่ซ้ำ")
            seen.setdefault(r["id"], r["line"])
            new = (layer == "team" or (layer == "kit" and r["has_evidence"])
                   or (layer == "job" and NEW_SECTION.strip("# ").split(" (")[0] in r["section"]))
            if not new:
                continue
            ev = r["evidence"].strip(" -—")
            if not ev:
                errs.append(f"{rel}:{r['line']} {r['id']} ไม่มีหลักฐาน (ช่อง หลักฐาน ว่าง) — ใส่ไฟล์ผล / log / ข้อความ SA ที่ยืนยัน")
            if not r["tag"].strip(" -—"):
                warns.append(f"{rel}:{r['line']} {r['id']} ไม่มีหมวด / ขั้น — ใส่เช่น \"03 · performance\" (ใช้ดึงบทเรียนตามขั้น)")
        for i, line in enumerate(rd(f).splitlines(), 1):
            if SECRET.search(line) and not SECRET_OK.search(line):
                errs.append(f"{rel}:{i} อาจมีรหัสผ่าน / connection string ในบทเรียน — ห้ามใส่ข้อมูลลับใน Wiki")
        if (w / ".git").exists():                                   # ไม่ลบประวัติ: เลข L# ที่เคยมีต้องยังอยู่
            old = {r["id"] for r in lesson_rows(_git_show(w, base, rel), rel)}
            now = {r["id"] for r in rows}
            gone = sorted(old - now, key=lambda x: (len(x), x))
            if gone:
                errs.append(f"{rel}: บทเรียนหายไปเทียบกับ {base}: {', '.join(gone[:10])} — ห้ามลบประวัติ (แก้ข้อเดิมพร้อมหมายเหตุวันที่แทน)")
    trow = {r["id"]: r for r in lesson_rows(rd(team), "team")}
    for e in ledger(w):                                             # ไม่ลบประวัติแม้ไม่มี git: ทุกข้อที่ promote ต้องยังอยู่
        if "broken" in e:
            errs.append(f"{e['broken']} อ่านไม่ได้ — ledger ของ kit-promote เสีย (อย่าแก้มือ)")
            continue
        r = trow.get(e.get("id"))
        if not r:
            errs.append(f"shared/knowledge/{TEAM_FILE}: {e.get('id')} (promote จาก {e.get('from_job')} {e.get('from_id')}) หายไป — ห้ามลบบทเรียนทีม")
        elif row_sha(rd(team).splitlines()[r["line"] - 1]) != e.get("row_sha256") and not re.search(r"แก้\s*\d{4}-\d{2}-\d{2}", r["text"]):
            warns.append(f"shared/knowledge/{TEAM_FILE}:{r['line']} {r['id']} ถูกแก้หลัง promote แต่ไม่มีหมายเหตุ \"แก้ YYYY-MM-DD …\"")
    if (w / ".git").exists():                                       # คำแนะนำที่เพิ่มใหม่ (เทียบ base) ต้องอ้าง L#
        for f in sorted((w / "projects").glob("*/jobs/*/status/OPEN_DECISIONS.md")):
            rel = f.relative_to(w).as_posix()
            try:
                d = subprocess.run(["git", "diff", "-U0", base, "--", rel], cwd=str(w), capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            except Exception:
                d = ""
            if not _git_show(w, base, rel):                         # ไฟล์ใหม่ทั้งไฟล์ (คำถามตั้งต้นจาก kit) — ไม่นับ
                continue
            added = [l[1:] for l in d.splitlines() if l.startswith("+") and not l.startswith("+++")]
            bad = [l for l in added if "[แนะนำ]" in l and not re.search(r"อ้างอิง|L-?T?\d+|E\d+", l)]
            if bad:
                warns.append(f"{rel}: คำแนะนำที่เพิ่มใหม่ {len(bad)} ข้อไม่อ้างบทเรียน (เช่น \"{bad[0].strip()[:60]}\") — เขียน \"อ้างอิง: L# …\" หรือ \"อ้างอิง: ไม่มีบทเรียนที่เกี่ยวข้อง\"")
    gk = kit_knowledge(w) / "glossary-kit.md"
    if not gk.exists():
        warns.append("ไม่มี kit/knowledge/glossary-kit.md — รัน workspace.py sync-kit --all หรือ setup -Mode Workspace เพื่อเติม")
    return errs, warns


# ---------------------------------------------------------------- promote (งาน → ชั้นทีม)
def row_sha(line: str) -> str:
    return hashlib.sha256(" ".join(line.split()).encode("utf-8")).hexdigest()


def _cell(r: dict, *names: str) -> str:
    idx = next((n for n, h in enumerate(r["head"]) if any(x in h for x in names)), None)
    return r["cells"][idx] if idx is not None and idx < len(r["cells"]) else ""


def _approvers(w: Path) -> set[str]:
    try:
        a = json.loads((w / "shared" / "approvers.json").read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {x.strip() for k in ("knowledge_approvers", "production_approvers") for x in a.get(k, []) if str(x).strip()}


def next_team_id(w: Path) -> int:
    ids = [r["id"] for r in lesson_rows(rd(team_dir(w) / TEAM_FILE), "team") + lesson_rows(rd(kit_knowledge(w) / "lessons-learned.md"), "kit")]
    nums = [int(m.group(1)) for x in ids if (m := re.match(r"^L-?T(\d+)$", x, re.I))]
    return max(nums, default=0) + 1


def promote_plan(w: Path, job: Path, ids: list[str]) -> dict:
    """แถวที่จะ promote + ปัญหา (ถ้ามีปัญหา = ห้าม apply) · plan_id ผูกกับเนื้อหา (แก้หลังอนุมัติ = plan_id ไม่ตรง)"""
    src = job / "knowledge" / "lessons-learned.md"
    rows = {r["id"]: r for r in lesson_rows(rd(src), "job") if NEW_SECTION.strip("# ").split(" (")[0] in r["section"]}
    kit_rows = {(r["id"], r["text"]) for r in lesson_rows(rd(kit_knowledge(w) / "lessons-learned.md"), "kit")}
    team_text = {r["text"] for r in lesson_rows(rd(team_dir(w) / TEAM_FILE), "team")}
    done = {(e.get("from_job"), e.get("from_id")): e.get("id") for e in ledger(w)}
    key, problems, picked = job_key(job), [], []
    nid = next_team_id(w)
    for i in ids:
        r = rows.get(i)
        if not r:
            problems.append(f"{i}: ไม่พบในหัวข้อ \"{NEW_SECTION.strip('# ')}\" ของ {key}/knowledge/lessons-learned.md")
            continue
        if (r["id"], r["text"]) in kit_rows:
            problems.append(f"{i}: เป็นบทเรียนที่ติดมากับ kit อยู่แล้ว (ไม่ต้อง promote)")
        if (key, i) in done:
            problems.append(f"{i}: promote แล้วเป็น {done[(key, i)]}")
        if not r["evidence"].strip(" -—"):
            problems.append(f"{i}: ไม่มีหลักฐาน")
        if not r["tag"].strip(" -—"):
            problems.append(f"{i}: ไม่มีหมวด / ขั้น")
        if not GENERIC.search(r["text"]):
            problems.append(f"{i}: ไม่ได้ระบุว่าใช้ได้ทุกงาน (\"generic\" ในช่องวิธีทำ) — เฉพาะงานนี้ไม่ส่งเข้าทีม")
        if SECRET.search(r["text"]) and not SECRET_OK.search(r["text"]):
            problems.append(f"{i}: อาจมีรหัสผ่าน / connection string")
        cells = [_cell(r, "หมวด"), _cell(r, "ปัญหา", "บทเรียน") or r["cells"][1], _cell(r, "ผลถ้าพลาด"), _cell(r, "วิธีทำ", "ทำอย่างไร"),
                 f"{key}: {r['evidence']}"]
        if " ".join(cells[:4]) in team_text:
            problems.append(f"{i}: มีข้อความเดียวกันในชั้นทีมแล้ว")
        picked.append({"from_id": i, "id": f"LT{nid}", "cells": cells, "line": r["line"]})
        nid += 1
    body = json.dumps([[p["from_id"], p["cells"]] for p in picked], ensure_ascii=False, sort_keys=True)
    return {"job": key, "rows": picked, "problems": problems,
            "plan_id": hashlib.sha256((key + body).encode("utf-8")).hexdigest()[:10]}


def promote_apply(w: Path, job: Path, ids: list[str], plan_id: str, approved: str) -> list[dict]:
    """เขียนแถว LT# ลงชั้นทีม + ledger · ต้องมี plan_id ตรงกับเนื้อหาปัจจุบัน และผู้อนุมัติอยู่ใน shared/approvers.json"""
    plan = promote_plan(w, job, ids)
    if plan["problems"]:
        raise ValueError("แผนมีปัญหา: " + " · ".join(plan["problems"]))
    if plan_id != plan["plan_id"]:
        raise ValueError(f"plan_id ไม่ตรง ({plan_id} ≠ {plan['plan_id']}) — เนื้อหาเปลี่ยนหลังแสดงแผน ให้คนดูแผนใหม่และอนุมัติอีกครั้ง")
    m = re.match(r"^(.+?)\s+(\d{4}-\d{2}-\d{2})$", approved.strip())
    if not m:
        raise ValueError('--approved ต้องเป็น "<ชื่อผู้อนุมัติ> <YYYY-MM-DD>"')
    name, day = m.group(1).strip(), m.group(2)
    if name not in _approvers(w):
        raise ValueError(f"{name} ไม่อยู่ใน shared/approvers.json (knowledge_approvers / production_approvers) — Tech Lead เพิ่มชื่อก่อน")
    td = team_dir(w); td.mkdir(parents=True, exist_ok=True)
    f = td / TEAM_FILE
    text = rd(f) or "# Team lessons\n"
    if TEAM_SECTION not in text:
        text = text.rstrip("\n") + f"\n\n{TEAM_SECTION}\n\n{TEAM_HEADER}\n|---|---|---|---|---|---|---|\n"
    entries = ledger(w)
    if any("broken" in e for e in entries):
        raise ValueError(f"{td / LEDGER} อ่านไม่ได้ — แก้ก่อน promote")
    lines = []
    for p in plan["rows"]:
        line = f"| {p['id']} | " + " | ".join(p["cells"]) + f" | จาก {plan['job']} {p['from_id']} · อนุมัติ {name} {day} |"
        lines.append(line)
        entries.append({"id": p["id"], "from_job": plan["job"], "from_id": p["from_id"], "approved_by": name, "approved_on": day,
                        "plan_id": plan_id, "promoted_at": _dt.datetime.now().isoformat(timespec="seconds"), "row_sha256": row_sha(line)})
    f.write_text(text.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    (td / LEDGER).write_text(json.dumps({"format": 1, "entries": entries}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return plan["rows"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", choices=sorted(STEPS))
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--search")
    ap.add_argument("--layer", choices=["kit", "team", "target", "project", "job"])
    ap.add_argument("--remote", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--job", help="<Project>/<Job> (เมื่อรันจาก root)")
    a = ap.parse_args()
    if a.step:
        w = ws_root()
        cmd_step(a.step, a.limit, (w / "projects" / a.job.split("/")[0] / "jobs" / a.job.split("/")[1]) if a.job and w else None)
    elif a.search:
        cmd_search(a.search, a.layer, a.remote)
    elif a.check:
        w = ws_root()
        if not w:
            raise SystemExit("[ERROR] ไม่พบ workspace")
        errs, warns = check(w, a.base)
        for e in errs:
            print(f"  ❌ {e}")
        for x in warns:
            print(f"  ⚠️  {x}")
        print(f"Wiki check: ERROR {len(errs)} · WARN {len(warns)}")
        sys.exit(1 if errs else 0)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
