"""dbx.py — Oracle adapter ระดับ workspace ของ migrate_team2 (port จาก Migrate_ODI_Team2 kit 2.15.0 runpack/dbx.py)

อยู่นอก kit/src โดยตั้งใจ: runtime ที่ล็อกไว้ใน kit.lock.json (simulate) ยังออฟไลน์และใช้ standard library เท่านั้น
adapter นี้ถูกเรียกผ่าน `python tools/workspace.py run-sql | db-test | db-connect | db-policy | db-driver | db-status`

กติกาทีม (shared/team.json → "db"; ตั้งใน setup_workspace.ps1 ข้อ 7 หรือ workspace.py db-policy):
  ai_access   human = คนรันทั้งหมด (ระบบแค่เตรียมแผน + บอกขั้นตอน) · ai = ระบบ/AI รันได้หลังคนอนุญาตแต่ละแผน
  select_mode ask = ถามก่อนทุกครั้งรวม SELECT · auto = SELECT รันต่อเนื่อง ถามเฉพาะคำสั่งที่เขียน / แก้โครงสร้าง
  users       split = SELECT ใช้ user อ่านอย่างเดียว (session READ ONLY) · คำสั่งเขียนใช้ user ที่เขียนได้ · single = user เดียว
  read_odi_log  อนุญาตให้อ่านตาราง SNP_* ของ ODI (work repository) — ค่าเริ่มต้น false
  default_env   ฐานเริ่มต้น เช่น DEV
งานใดต้องการให้คนรันเสมอ: ใส่ "db_access": "human" ใน job.json (ชนะค่าทีม)
หมายเหตุ: config.json "db_mode" ของงานเป็นค่าของ simulator runtime (ต้องเป็น human เสมอ) ไม่ใช่กติกาของ adapter นี้

การเชื่อมต่อ: shared/db.local.json {"default": "DEV", "connections": {"DEV": {host, port, service, user_ro, user_rw}}}
  (ไม่มีรหัสผ่าน · ไม่ขึ้น Git) · รหัสผ่าน: ตัวแปร ORA_RO_PASSWORD / ORA_RW_PASSWORD (ฐานอื่นเติม _<ENV> เช่น ORA_RW_PASSWORD_SIT)
  หรือพิมพ์ตอนรันใน Terminal (ไม่แสดงบนจอ ไม่เก็บ) · ตัวต่อ: python-oracledb แบบ thin (ไม่ต้องลง Oracle Client)

ประเภทคำสั่ง: read (SELECT/WITH) · write (INSERT/UPDATE/DELETE/MERGE) · ddl (CREATE/ALTER/DROP/TRUNCATE/…) · plsql (BEGIN/DECLARE/CALL)
  ลบแล้วกู้คืนไม่ได้ (destructive): DROP · TRUNCATE · DELETE / UPDATE ที่ไม่มี WHERE · ALTER … DROP → ต้องยืนยันด้วยชื่อตารางอีกชั้น
  ไฟล์ Blendata / Spark SQL ไม่รันเสมอ (คนรันบน Blendata) · คำสั่งเขียนลงตาราง SNP_* ของ ODI ไม่รันเสมอ
ผลลัพธ์ของงาน: <job>/db_runs/<เป้าหมาย>/ (นอก input/ เพื่อไม่ให้ fingerprint ของ simulated review เปลี่ยน)
ทุกครั้งที่รันถูกบันทึก: งาน = status/DB_RUN_LOG.md (+ คำสั่งที่เขียน → status/DEPLOY_LOG.md) · workspace = registry/db_queries.log
การรันฐานจริงไม่เปลี่ยน Gate ของ simulator: G4–G7 ยังเป็น NOT_EXECUTED จนกว่าจะมีกระบวนการ production ที่อนุมัติ
"""
from __future__ import annotations

import csv
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path.cwd()                      # root ของงาน หรือ workspace (ตั้งด้วย set_root เสมอ)

READ_START = re.compile(r"^\s*(select|with)\b", re.I)
WRITE_START = re.compile(r"^\s*(insert|update|delete|merge)\b", re.I)
DDL_START = re.compile(r"^\s*(create|alter|drop|truncate|rename|comment|grant|revoke|analyze|purge|flashback)\b", re.I)
PLSQL_START = re.compile(r"^\s*(begin|declare|call|exec|execute)\b", re.I)
SKIP_START = re.compile(r"^\s*(commit|rollback|savepoint|set|spool|prompt|whenever|exit|quit|define|undefine|show|desc|describe)\b", re.I)
READ_BAD = re.compile(r"\bfor\s+update\b|\binto\s+[:\w]+\s+from\b", re.I)
SNP = re.compile(r"\bsnp_\w+", re.I)
NAME = r'((?:"[^"]+"|[\w$#]+)(?:\.(?:"[^"]+"|[\w$#]+))?)'
ENV_RX = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")

DEFAULT_POLICY = {"ai_access": "human", "select_mode": "ask", "users": "split", "read_odi_log": False, "default_env": "DEV"}
POLICY_CHOICES = {"ai_access": ("human", "ai"), "select_mode": ("ask", "auto"), "users": ("split", "single")}
RESULTS_DIR = "db_runs"


class DbxError(SystemExit):
    """ข้อผิดพลาดที่ต้องหยุด (ข้อความเป็นภาษาไทยสำหรับคน) — exit code 1"""

    def __init__(self, message: str):
        super().__init__("[ERROR] " + message)


# ---------------------------------------------------------------- ที่อยู่ / ค่าตั้ง
def set_root(p: Path):
    global ROOT
    ROOT = Path(p).resolve()


def ws_root() -> Path | None:
    for p in [ROOT, *ROOT.parents]:
        if (p / "workspace.json").exists() and (p / "tools" / "workspace.py").exists():
            return p
    return None


def is_job() -> bool:
    return (ROOT / "job.json").exists()


def job_label() -> str | None:
    if not is_job():
        return None
    meta = _read_json(ROOT / "job.json")
    return f"{meta.get('project', ROOT.parents[1].name)}/{meta.get('job', ROOT.name)}"


def _read_json(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default if default is not None else {}


def _write_json(p: Path, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def team_db() -> dict:
    w = ws_root()
    db = dict(DEFAULT_POLICY)
    db.update((_read_json(w / "shared/team.json") if w else {}).get("db") or {})
    for key, allowed in POLICY_CHOICES.items():
        if db.get(key) not in allowed:
            db[key] = DEFAULT_POLICY[key]
    db["read_odi_log"] = bool(db.get("read_odi_log"))
    if is_job() and _read_json(ROOT / "job.json").get("db_access") == "human":   # งานตั้งเองชนะค่าทีม
        db["ai_access"] = "human"
    return db


def set_policy(root: Path, **changes) -> dict:
    """แก้ shared/team.json → "db" เฉพาะคีย์ที่ระบุ · คงค่าอื่นของทีมไว้ทั้งหมด"""
    path = Path(root) / "shared/team.json"
    team = _read_json(path)
    if not team:
        raise DbxError("ไม่พบ shared/team.json — รัน `python tools/workspace.py init` ก่อน")
    db = dict(DEFAULT_POLICY)
    db.update(team.get("db") or {})
    for key, value in changes.items():
        if value is None:
            continue
        if key in POLICY_CHOICES and value not in POLICY_CHOICES[key]:
            raise DbxError(f"{key} ต้องเป็น {' / '.join(POLICY_CHOICES[key])}")
        if key == "default_env":
            value = str(value).upper()
            if not ENV_RX.match(value):
                raise DbxError("ชื่อฐานใช้ A-Z 0-9 _ ขึ้นต้นด้วยตัวอักษร")
        db[key] = value
    team["db"] = db
    _write_json(path, team)
    return db


def connections() -> tuple[str, dict]:
    w = ws_root()
    raw = _read_json(w / "shared/db.local.json") if w else {}
    return str(raw.get("default") or team_db().get("default_env") or "DEV").upper(), raw.get("connections", {}) or {}


def save_connection(root: Path, env: str, conn: dict, make_default: bool = False) -> dict:
    path = Path(root) / "shared/db.local.json"
    raw = _read_json(path) or {}
    cons = raw.get("connections") or {}
    cons[env] = conn
    default = raw.get("default")
    if make_default or not default or default not in cons:
        default = env
    value = {"default": default, "connections": cons,
             "note": "ค่าการเชื่อมต่อเฉพาะเครื่องนี้ — ไม่มีรหัสผ่าน ห้ามขึ้น Git (อยู่ใน .gitignore)"}
    _write_json(path, value)
    return value


def pw_var(kind: str, env: str) -> str:
    d, _ = connections()
    base = "ORA_RO_PASSWORD" if kind == "ro" else "ORA_RW_PASSWORD"
    return base if env == d else f"{base}_{env}"


def driver_version() -> str | None:
    try:
        import oracledb
        return getattr(oracledb, "__version__", "?")
    except ImportError:
        return None


# ---------------------------------------------------------------- แยก / จัดประเภท SQL
def strip_comments(s: str) -> str:
    """Remove -- and /* */ comments outside string literals. Optimizer hints (/*+ … */) are kept."""
    out, i, q, n = [], 0, False, len(s)
    while i < n:
        c = s[i]
        if q:
            out.append(c)
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":       # escaped quote ''
                    out.append("'"); i += 2; continue
                q = False
            i += 1
            continue
        if c == "'":
            q = True; out.append(c); i += 1; continue
        if s.startswith("--", i):
            j = s.find("\n", i)
            i = n if j < 0 else j                       # keep the newline
            continue
        if s.startswith("/*", i) and not s.startswith("/*+", i):
            j = s.find("*/", i + 2)
            out.append(" ")
            i = n if j < 0 else j + 2
            continue
        out.append(c); i += 1
    return "".join(out)


def split_statements(text: str) -> list[str]:
    """แยกคำสั่ง: บล็อก PL/SQL จบด้วยบรรทัด '/' · คำสั่งอื่นจบด้วย ';' (ไม่นับใน quote)"""
    body = strip_comments(text)
    out, cur, q, in_plsql = [], "", False, False
    for line in body.splitlines(keepends=True):
        if not cur.strip() and (PLSQL_START.match(line) or
                                re.match(r"^\s*create\s+(or\s+replace\s+)?(procedure|function|package|trigger|type)\b", line, re.I)):
            in_plsql = True
        if in_plsql:
            if line.strip() == "/":
                out.append(cur.strip()); cur = ""; in_plsql = False
            else:
                cur += line
            continue
        if line.strip() == "/":
            if cur.strip():
                out.append(cur.strip()); cur = ""
            continue
        for c in line:
            if c == "'":
                q = not q
            if c == ";" and not q:
                if cur.strip():
                    out.append(cur.strip())
                cur = ""
            else:
                cur += c
    if cur.strip():
        last = cur.strip()
        out.append(last if in_plsql else last.rstrip(";").strip())    # PL/SQL keeps its END;
    return [s for s in out if s]


def _tables(sql: str, verb: str) -> list[str]:
    pats = {
        "drop": rf"^\s*drop\s+table\s+{NAME}",
        "truncate": rf"^\s*truncate\s+table\s+{NAME}",
        "delete": rf"^\s*delete\s+(?:from\s+)?{NAME}",
        "update": rf"^\s*update\s+{NAME}",
        "alter": rf"^\s*alter\s+table\s+{NAME}",
    }
    m = re.search(pats.get(verb, r"$^"), sql, re.I)
    return [m.group(1).replace('"', "").upper()] if m else []


def _top_level(sql: str) -> str:
    """SQL with string literals and parenthesised parts removed — to see the statement's own clauses."""
    t = re.sub(r"'(?:[^']|'')*'", "''", sql)
    prev = None
    while prev != t:
        prev, t = t, re.sub(r"\([^()]*\)", " ", t)
    return t


DYNAMIC_DDL = re.compile(r"\b(?:truncate|drop)\b|\bexecute\s+immediate\b", re.I)


def classify(sql: str) -> dict:
    s = sql.strip()
    verb = (re.match(r"^\s*(\w+)", s) or [None, ""])[1].lower()
    r = {"sql": s, "verb": verb, "kind": "", "destructive": False, "tables": [], "snp": bool(SNP.search(s)), "why": ""}
    if SKIP_START.match(s):
        r["kind"] = "skip"; r["why"] = "คำสั่งของ SQL*Plus / จัดการ transaction (ระบบจัดการให้เอง)"
    elif READ_START.match(s):
        if READ_BAD.search(s):
            r["kind"] = "write"; r["why"] = "SELECT ที่ล็อกแถว / เขียนตัวแปร"
        else:
            r["kind"] = "read"
    elif WRITE_START.match(s):
        r["kind"] = "write"
        if verb in ("delete", "update") and not re.search(r"\bwhere\b", _top_level(s), re.I):
            r["destructive"] = True; r["tables"] = _tables(s, verb); r["why"] = f"{verb.upper()} ไม่มี WHERE = ทั้งตาราง"
    elif DDL_START.match(s):
        r["kind"] = "ddl"
        if verb in ("drop", "truncate"):
            r["destructive"] = True; r["tables"] = _tables(s, verb); r["why"] = f"{verb.upper()} กู้คืนไม่ได้"
        elif verb == "alter" and re.search(r"\b(?:drop|truncate)\b", _top_level(s), re.I):
            r["destructive"] = True; r["tables"] = _tables(s, "alter"); r["why"] = "ALTER … DROP / TRUNCATE (คอลัมน์ / constraint / partition)"
    elif PLSQL_START.match(s):
        r["kind"] = "plsql"; r["why"] = "บล็อก PL/SQL / เรียก procedure (อาจเขียนข้อมูล)"
        if DYNAMIC_DDL.search(re.sub(r"'(?:[^']|'')*'", lambda m: m.group(0) if DYNAMIC_DDL.search(m.group(0)) else "''", s)):
            r["destructive"] = True; r["tables"] = ["?"]
            r["why"] = "PL/SQL ที่มี TRUNCATE / DROP / EXECUTE IMMEDIATE — ระบบอ่านเป้าหมายไม่ได้ ให้คนรันเอง"
    else:
        r["kind"] = "ddl"; r["why"] = "ไม่รู้จักชนิดคำสั่ง — ถือเป็นคำสั่งแก้โครงสร้าง"
    if r["destructive"] and not r["tables"]:
        r["tables"] = ["?"]
    return r


def classify_file(f: Path) -> dict:
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    head = "\n".join(text.splitlines()[:5]).lower()
    # Blendata / Spark scripts are recognised by name or an explicit header — not by any mention of Blendata
    # (Oracle DML from the kit says "Blendata sinkOption.mode" in its comments and must still run).
    if re.search(r"blendata|spark", f.name.lower()) or re.search(
            r"blendata\s*/\s*spark sql|run (?:it )?on blendata|รันบน blendata|^--\s*spark sql", head, re.M):
        return {"file": f, "kind": "blendata", "why": "สคริปต์ของ Blendata (Spark SQL) — คนรันบน Blendata", "stmts": []}
    stmts = [classify(s) for s in split_statements(text)]
    run = [s for s in stmts if s["kind"] != "skip"]
    if not run:
        return {"file": f, "kind": "empty", "why": "ไม่มีคำสั่งให้รัน", "stmts": stmts}
    kinds = {s["kind"] for s in run}
    kind = "read" if kinds == {"read"} else "write"
    return {"file": f, "kind": kind, "why": "", "stmts": stmts}


# ---------------------------------------------------------------- แผน (plan) — สิ่งที่จะรัน แสดงให้คนเห็นก่อนเสมอ
def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except Exception:
        return Path(p).as_posix()


def _inside(base: Path, p: Path) -> bool:
    try:
        Path(p).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


def results_base() -> Path:
    """Simulation jobs: db_runs/ (outside input/, so the simulated review fingerprint is unchanged).
    Delivery jobs: input/run_results/ — where read_run_results.py and the Gate scripts read Run Pack results."""
    if not is_job():
        return ROOT / "registry" / "tmp_db"
    if _read_json(ROOT / "job.json").get("mode") == "delivery":
        return ROOT / "input" / "run_results"
    return ROOT / RESULTS_DIR


def collect(target: str, only: str | None = None) -> tuple[str, list[Path], Path]:
    """target = ชื่อ pack (rp01) / โฟลเดอร์ / ไฟล์ .sql (ภายใน root เท่านั้น) → (ชื่อ, ไฟล์, โฟลเดอร์ผล)"""
    p = (ROOT / target) if not Path(target).is_absolute() else Path(target)
    if p.exists() and not _inside(ROOT, p):
        raise DbxError(f"{target} อยู่นอก {'งาน' if is_job() else 'workspace'} — รันได้เฉพาะไฟล์ภายในโฟลเดอร์ของงาน")
    if p.is_file():
        files, name = [p], p.stem
        out = results_base() / "adhoc"
    else:
        if not p.is_dir():
            packs = sorted(x for x in (ROOT / "run_packs").glob(f"{target}*") if x.is_dir())
            if not packs:
                raise DbxError(f"ไม่พบ {target} (ไฟล์ .sql / โฟลเดอร์ / run_packs/{target}*)")
            p = packs[-1]
        files, name = sorted(p.glob("*.sql")), p.name
        out = results_base() / p.name
    if only:
        pre = tuple(x.strip() for x in only.split(",") if x.strip())
        files = [f for f in files if f.name.startswith(pre)]
    if not files:
        raise DbxError(f"{name}: ไม่มีไฟล์ .sql" + (f" ที่ขึ้นต้นด้วย {only}" if only else ""))
    return name, files, out


EXPLAIN_VERBS = ("select", "with", "insert", "merge", "update", "delete")
PLAN_WARN = [(re.compile(r"TABLE ACCESS (?:STORAGE )?FULL", re.I), "อ่านทั้งตาราง (full scan) — ตรวจว่ามี index / เงื่อนไขกรองพอไหม"),
             (re.compile(r"PARTITION RANGE ALL|PARTITION LIST ALL", re.I), "ไม่ตัด partition (อ่านทุก partition) — ตรวจเงื่อนไขตาม partition key"),
             (re.compile(r"MERGE JOIN CARTESIAN|CARTESIAN", re.I), "join ไม่มีเงื่อนไข (cartesian)")]
ROW_LEVEL = re.compile(r"(^|[_\-. ])L3([_\-. ]|$)|^L3", re.I)
IN_PACK = ("run_packs/",)
SIM_OUTPUT = ("output/",)


def make_plan(target: str, env: str | None = None, only: str | None = None, compile_: bool = False,
              out_dir: Path | None = None, explain: bool = False) -> dict:
    if compile_ and explain:
        raise DbxError("เลือกได้อย่างเดียว: --compile หรือ --explain")
    db = team_db()
    d, cons = connections()
    env = (env or d).upper()
    if not ENV_RX.match(env):
        raise DbxError("ชื่อฐานใช้ A-Z 0-9 _ ขึ้นต้นด้วยตัวอักษร")
    name, files, out = collect(target, only)
    out = Path(out_dir) if out_dir else out
    items, todo = [], []
    for f in files:
        c = classify_file(f)
        reason = ""
        if c["kind"] == "blendata":
            reason = c["why"]
        elif c["kind"] == "empty":
            continue
        elif any(s["snp"] and s["kind"] != "read" for s in c["stmts"]):
            reason = "คำสั่งเขียนลงตาราง SNP_* ของ ODI — ระบบไม่รันเสมอ (แก้ผ่าน ODI Studio)"
        elif any(s["snp"] for s in c["stmts"]) and not db.get("read_odi_log"):
            reason = "อ่านตาราง SNP_* ของ ODI — ทีมยังไม่อนุญาตให้อ่าน work repository (db-policy --read-odi-log yes)"
        elif db.get("ai_access") != "ai":
            reason = "ทีมตั้งให้คนรันทั้งหมด (setup ข้อ 7 / db-policy)"
        elif compile_ and c["kind"] != "read":
            reason = "โหมดคอมไพล์รับเฉพาะ SELECT (ใช้ --explain กับ INSERT / MERGE)"
        elif explain and not any(s_["verb"] in EXPLAIN_VERBS for s_ in c["stmts"] if s_["kind"] != "skip"):
            reason = "EXPLAIN PLAN รับเฉพาะ SELECT / INSERT / MERGE / UPDATE / DELETE"
        if reason:
            todo.append({"file": _rel(f), "why": reason, "kind": c["kind"]})
            continue
        items.append({"file": _rel(f), "sha": hashlib.sha256(f.read_bytes()).hexdigest(), "kind": c["kind"],
                      "stmts": [{k: s[k] for k in ("sql", "kind", "verb", "destructive", "tables", "why")}
                                for s in c["stmts"] if s["kind"] != "skip"]})
    if explain:   # ไม่รันคำสั่งจริง — แค่ขอแผนการรัน (เขียนลง PLAN_TABLE ของ session · rollback ทิ้งตอนจบ)
        for i in items:
            i["stmts"] = [x for x in i["stmts"] if x["verb"] in EXPLAIN_VERBS]
            i["kind"] = "read"
    has_write = any(i["kind"] != "read" for i in items)
    always = [f"{i['file']}: EXPLAIN PLAN (ไม่รันคำสั่งจริง · เขียนแผนลง PLAN_TABLE ชั่วคราวแล้วยกเลิกทิ้ง)" for i in items] if explain else []
    if not compile_ and not explain:
        for i in items:
            fn = Path(i["file"]).name
            if ROW_LEVEL.search(fn) or "-- ROW-LEVEL" in (ROOT / i["file"]).read_text(encoding="utf-8", errors="replace").upper():
                always.append(f"{i['file']}: ดึงข้อมูลรายแถว (L3)")
            elif is_job() and not i["file"].startswith(IN_PACK):
                always.append(f"{i['file']}: query นอก Run Pack")
    if env == "PROD":
        always.append("ฐาน PROD = ระบบจริง — ถามก่อนเสมอ")
    destr = sorted({t for i in items for s in i["stmts"] if s["destructive"] for t in s["tables"]})
    sim = sorted({i["file"] for i in items if i["file"].startswith(SIM_OUTPUT)})
    pid = hashlib.sha256(json.dumps([str(ROOT), env, [(i["file"], i["sha"]) for i in items], compile_, explain],
                                    sort_keys=True).encode()).hexdigest()[:10]
    plan = {"id": pid, "created": dt.datetime.now().isoformat(timespec="seconds"), "job": job_label(), "target": name,
            "env": env, "env_known": env in cons, "out": _rel(out), "items": items, "todo": todo, "has_write": has_write,
            "destructive": destr, "always_ask": always, "simulation_outputs": sim, "compile": compile_, "explain": explain,
            "ai_access": db.get("ai_access"), "select_mode": db.get("select_mode"), "users": db.get("users")}
    pdir = ROOT / ".dbx" / "plans"
    pdir.mkdir(parents=True, exist_ok=True)
    _write_json(pdir / f"{pid}.json", plan)
    return plan


def needs_question(plan: dict) -> bool:
    """ต้องถามคนก่อนรันไหม — คำสั่งเขียนถามเสมอ · SELECT ถามเมื่อ select_mode = ask"""
    if not plan["items"]:
        return False
    return plan["has_write"] or plan.get("select_mode") != "auto" or bool(plan.get("always_ask"))


def cmd_prefix(plan: dict) -> str:
    job = f" --job {plan['job']}" if plan.get("job") else ""
    return f"python tools/workspace.py run-sql{job}"


def human_steps(plan: dict, items: list | None = None) -> list[str]:
    """ขั้นตอนให้คนรันเอง (ทีละไฟล์ · 4 ข้อ: เปิดไฟล์ไหน · เพื่ออะไร · export แบบไหน · วางที่ไหน)"""
    rows = []
    src = items if items is not None else [{"file": i["file"], "kind": i["kind"], "why": ""} for i in plan["items"]] + plan["todo"]
    for n, it in enumerate(src, 1):
        where = "Blendata (Spark SQL)" if it.get("kind") == "blendata" else f"DBeaver / SQL Developer ที่ต่อ Oracle {plan['env']}"
        is_read = it.get("kind") == "read"
        rows += [f"ไฟล์ที่ {n}: {it['file']}",
                 f"  1) เปิดไฟล์ {it['file']} ใน {where}",
                 f"  2) เพื่อ: {'ดึงข้อมูลมาตรวจ' if is_read else 'สร้าง / แก้ข้อมูลหรือตารางตามสคริปต์'}" + (f" ({it['why']})" if it.get("why") else ""),
                 "  3) " + ("Ctrl+Enter แล้ว export ผลเป็น CSV (UTF-8 มีหัวคอลัมน์)" if is_read else
                            "Execute Script (Alt+X) · จดจำนวนแถว / ข้อความที่ได้"),
                 "  4) " + (f"วางไฟล์ CSV ที่ {plan['out']}/ ชื่อเดียวกับไฟล์ .sql" if is_read else
                            f"บันทึกผล: {cmd_prefix(plan)} --record-human {plan['id']} --result \"<ผลที่ได้>\"")]
    return rows


def render(plan: dict) -> str:
    L = ["=" * 64, f"  ฐานข้อมูล: {plan['env']}" + ("" if plan["env_known"] else "  (ยังไม่มีค่าการเชื่อมต่อ — workspace.py db-connect)"),
         f"  เป้าหมาย: {plan['target']}" + (f" · งาน {plan['job']}" if plan.get("job") else "") + f" · แผน {plan['id']}", "=" * 64]
    if plan["env"] == "PROD":
        L.append("🔴 PROD = ฐานจริง — คำสั่งที่เขียนจะแก้ข้อมูลจริง ตรวจ SQL ทุกบรรทัดก่อนอนุญาต")
    if plan["items"]:
        L.append(f"สิ่งที่จะรัน ({len(plan['items'])} ไฟล์):")
        for it in plan["items"]:
            w = sum(1 for s in it["stmts"] if s["kind"] != "read")
            L.append(f"  • {it['file']} — {len(it['stmts'])} คำสั่ง" + (f" (เขียน / แก้โครงสร้าง {w})" if w else " (อ่านอย่างเดียว)"))
            for s in it["stmts"]:
                tag = {"read": "อ่าน", "write": "เขียนข้อมูล", "ddl": "แก้โครงสร้าง", "plsql": "PL/SQL"}.get(s["kind"], s["kind"])
                flag = "  ⚠️ ลบแล้วกู้คืนไม่ได้: " + s["why"] if s["destructive"] else ""
                sql = " ".join(s["sql"].split())
                L.append(f"      [{tag}] {sql[:220]}{' …' if len(sql) > 220 else ''}{flag}")
    if plan["todo"]:
        L.append(f"ระบบไม่รันให้ ({len(plan['todo'])} ไฟล์ — คนทำเอง):")
        for t in plan["todo"]:
            L.append(f"  👤 {t['file']}: {t['why']}")
    if plan.get("simulation_outputs"):
        L.append("🧪 ไฟล์จาก simulator (output/) เป็น illustrative DML ที่ยังไม่เคยคอมไพล์ — แนะนำ --compile / --explain ก่อนรันจริง")
    for a in plan.get("always_ask") or []:
        L.append(f"🔎 ต้องถามก่อนเสมอ: {a}")
    if plan["destructive"]:
        L.append(f"⚠️  มีคำสั่งที่ลบแล้วกู้คืนไม่ได้ — ต้องยืนยันด้วยชื่อตาราง: {', '.join(plan['destructive'])}")
    return "\n".join(L)


def question_text(plan: dict) -> str:
    q = [f"❓ ขออนุญาตรันบนฐาน {plan['env']} (แผน {plan['id']})",
         "   1  ให้ระบบรันเลย (ตามแผนด้านบนเท่านั้น)",
         "   2  ฉันรันเอง (ระบบบอกขั้นตอนทีละไฟล์)"]
    if plan["destructive"]:
        q.append(f"   ถ้าเลือก 1: ต้องพิมพ์ชื่อตารางยืนยันอีกชั้น — {', '.join(plan['destructive'])}")
    return "\n".join(q)


# ---------------------------------------------------------------- รัน
def _password(kind: str, env: str, interactive: bool) -> str | None:
    var = pw_var(kind, env)
    pw = os.environ.get(var)
    if pw:
        return pw
    if interactive:
        print(f"   ยังไม่มีตัวแปร {var} — พิมพ์รหัสผ่านของ user {'อ่านอย่างเดียว' if kind == 'ro' else 'ที่เขียนได้'} ({env})")
        print("   ตัวอักษรไม่แสดงบนจอ · ใช้ครั้งนี้ครั้งเดียว ไม่เก็บลงไฟล์ · Enter เปล่า = ยกเลิก")
        try:
            return getpass.getpass("   รหัสผ่าน: ") or None
        except (EOFError, KeyboardInterrupt):
            return None
    return None


def _connect(env: str, kind: str, interactive: bool):
    _, cons = connections()
    c = cons.get(env)
    if not c:
        raise DbxError(f"ยังไม่มีค่าการเชื่อมต่อของ {env} — รัน `python tools/workspace.py db-connect --env {env}` ที่ root ของ workspace")
    single = team_db().get("users") == "single"
    if single:
        kind = "rw"
        user = c.get("user_rw") or c.get("user_ro") or ""
    else:
        user = c.get("user_rw" if kind == "rw" else "user_ro") or ""
    if not user:
        raise DbxError(f"ยังไม่มี user {'ที่เขียนได้' if kind == 'rw' else 'อ่านอย่างเดียว'} ของ {env} — "
                       f"ขอจาก DBA แล้วรัน `python tools/workspace.py db-connect --env {env}` · ระหว่างนี้เลือก 'ฉันรันเอง'")
    pw = _password(kind, env, interactive)
    if not pw:
        raise DbxError(f"ไม่มีรหัสผ่าน ({pw_var(kind, env)}) — AI พิมพ์รหัสแทนคนไม่ได้: ให้คนตั้งตัวแปร "
                       f"(Windows: setx {pw_var(kind, env)} \"…\" แล้วปิดเปิด Terminal ใหม่) "
                       f"หรือให้คนรันคำสั่งเดียวกันเองใน Terminal (ระบบถามรหัสแบบไม่แสดงบนจอ) · ห้ามพิมพ์รหัสในแชท")
    try:
        import oracledb
    except ImportError:
        raise DbxError("เครื่องนี้ยังไม่มีตัวต่อ Oracle ของ Python — รัน `python tools/workspace.py db-driver --install` "
                       "(pip install oracledb · ไม่ต้องลง Oracle Client)") from None
    try:
        conn = oracledb.connect(user=user, password=pw, dsn=f"{c['host']}:{c.get('port', 1521)}/{c['service']}")
    except Exception as e:
        raise DbxError(f"ต่อฐาน {env} ไม่ได้: {str(e).splitlines()[0][:200] if str(e) else type(e).__name__} — ตรวจ host / port / service / user / รหัสผ่าน") from None
    conn.autocommit = False
    return conn, user


LOG_HEAD = ("# DB_RUN_LOG — ทุกครั้งที่ระบบ / คนรัน SQL บนฐานจริง (สร้างโดย tools/dbcore · ห้ามแก้มือ)\n\n"
            "ไม่เปลี่ยน Gate ของ simulator: G4–G7 ยังเป็น NOT_EXECUTED\n\n"
            "| เวลา | ฐาน | แผน | ไฟล์ | ชนิด | ผล | อนุญาตโดย |\n|---|---|---|---|---|---|---|\n")
DEPLOY_HEAD = "\n## รายการที่รันบนฐานจริง (DDL / DML)\n\n| รายการ | วันที่ | หลักฐาน | โดย | หมายเหตุ |\n|---|---|---|---|---|\n"


def _md(cells: list[str]) -> str:
    return "| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in cells) + " |\n"


def _log(line: str, md_row: list[str] | None = None, deploy: list[str] | None = None):
    w = ws_root()
    if is_job() and (ROOT / "status").exists():
        p = ROOT / "status" / "DB_RUN_LOG.md"
        if not p.exists():
            p.write_text(LOG_HEAD, encoding="utf-8")
        if md_row:
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(_md(md_row))
        if deploy:
            dp = ROOT / "status" / "DEPLOY_LOG.md"
            current = dp.read_text(encoding="utf-8") if dp.exists() else "# DEPLOY_LOG\n"
            if "| รายการ | วันที่ | หลักฐาน |" not in current:
                with open(dp, "a", encoding="utf-8") as fh:
                    fh.write(("" if current.endswith("\n") else "\n") + DEPLOY_HEAD)
            with open(dp, "a", encoding="utf-8") as fh:
                fh.write(_md(deploy))
    if w:
        (w / "registry").mkdir(parents=True, exist_ok=True)
        with open(w / "registry" / "db_queries.log", "a", encoding="utf-8") as fh:
            fh.write(line.replace("\n", " ") + "\n")


def _who() -> str:
    try:
        import subprocess
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, cwd=str(ROOT), timeout=5).stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return os.environ.get("USERNAME") or os.environ.get("USER") or "?"


def deploy_row(it: dict, ts: str, env: str, msg: str, by: str) -> list[str]:
    kind = "DDL" if any(s["kind"] == "ddl" for s in it.get("stmts", [])) or it.get("kind") == "ddl" else "DML"
    return [f"{kind} {it['file']}", ts[:10], f"{msg} · status/DB_RUN_LOG.md", by, f"ฐาน {env}"]


def load_plan(pid: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{10}", pid or ""):
        raise DbxError("รหัสแผนต้องเป็นเลขฐานสิบหก 10 ตัว (จาก --plan)")
    p = ROOT / ".dbx" / "plans" / f"{pid}.json"
    if not p.exists():
        raise DbxError(f"ไม่พบแผน {pid} ใน {_rel(ROOT) or '.'} — สร้างแผนก่อนด้วย --plan แล้วให้คนอนุญาต (ใช้ --job เดียวกับตอนสร้างแผน)")
    return json.loads(p.read_text(encoding="utf-8"))


def record_human(plan: dict, result: str) -> int:
    ts = dt.datetime.now().isoformat(timespec="seconds")
    for it in plan["items"] + plan["todo"]:
        _log(f"{ts} HUMAN-RAN {plan['env']} plan={plan['id']} {it['file']}: {result or ''}",
             [ts, plan["env"], plan["id"], it["file"], "คนรันเอง", result or "-", "คน"],
             deploy_row(it, ts, plan["env"], result or "-", "คนรันเอง") if it.get("kind") not in ("read", "blendata") else None)
    return len(plan["items"]) + len(plan["todo"])


def execute(plan: dict, approved_by: str, confirm: list[str] | None = None, interactive: bool = False,
            read_only_call: bool = False) -> dict:
    """รันตามแผน (ไฟล์ต้องไม่เปลี่ยนหลังแสดงให้คนดู) · คืน {ok, rows, errors}"""
    if not (approved_by or "").strip():
        raise DbxError("ต้องระบุผู้อนุญาต — ห้ามอนุญาตแทนคน")
    if plan.get("ai_access") != "ai" or team_db().get("ai_access") != "ai":
        raise DbxError("ทีมตั้งให้คนรันทั้งหมด (setup ข้อ 7 / db-policy) — ระบบไม่รันให้ ดูขั้นตอนให้คนรันด้วย --human <แผน>")
    if read_only_call and plan["has_write"]:
        raise DbxError("แผนนี้มีคำสั่งที่เขียน / แก้โครงสร้าง — ต้องขออนุญาตก่อนแล้วใช้ --execute <แผน>")
    if read_only_call and plan.get("always_ask"):
        raise DbxError("แผนนี้ต้องถามคนก่อนเสมอ (" + "; ".join(plan["always_ask"]) + ") — ขออนุญาตแล้วใช้ --execute <แผน>")
    if read_only_call and team_db().get("select_mode") != "auto":
        raise DbxError("ทีมตั้งให้ถามก่อนทุกครั้งรวม SELECT (select_mode = ask) — ขออนุญาตแล้วใช้ --execute <แผน>")
    if not plan["items"]:
        raise DbxError("แผนนี้ไม่มีไฟล์ที่ระบบรันได้ — ดูขั้นตอนให้คนรันด้วย --human <แผน>")
    for it in plan["items"]:
        f = ROOT / it["file"]
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != it["sha"]:
            raise DbxError(f"{it['file']} ถูกแก้หลังสร้างแผน {plan['id']} — สร้างแผนใหม่แล้วขออนุญาตใหม่")
        # the plan file itself is not trusted: statements are re-derived from the approved file
        keys = ("sql", "kind", "verb", "destructive", "tables")
        fresh = [{k: s[k] for k in keys} for s in classify_file(f)["stmts"] if s["kind"] != "skip"]
        if plan.get("explain"):
            fresh = [s for s in fresh if s["verb"] in EXPLAIN_VERBS]
        if fresh != [{k: s[k] for k in keys} for s in it["stmts"]]:
            raise DbxError(f"แผน {plan['id']} ไม่ตรงกับไฟล์ {it['file']} (ไฟล์แผนถูกแก้?) — สร้างแผนใหม่แล้วขออนุญาตใหม่")
    expect_id = hashlib.sha256(json.dumps([str(ROOT), plan["env"], [(i["file"], i["sha"]) for i in plan["items"]],
                                           plan["compile"], plan.get("explain", False)], sort_keys=True).encode()).hexdigest()[:10]
    derived_destr = sorted({t for i in plan["items"] for s in i["stmts"] if s["destructive"] for t in s["tables"]})
    derived_write = any(s["kind"] != "read" for i in plan["items"] for s in i["stmts"]) and not plan.get("explain")
    if expect_id != plan["id"] or derived_destr != sorted(plan["destructive"]) or derived_write != plan["has_write"]:
        raise DbxError(f"แผน {plan['id']} ถูกแก้หลังสร้าง — สร้างแผนใหม่แล้วขออนุญาตใหม่")
    if plan["destructive"]:
        got = {x.strip().upper() for x in (confirm or []) if x.strip()}
        need = set(plan["destructive"])
        if "?" in need:
            raise DbxError("มีคำสั่งลบที่ระบบอ่านชื่อตารางไม่ออก — ให้คนรันเอง")
        if got != need:
            raise DbxError(f"ต้องยืนยันชื่อตารางให้ครบและตรง: {', '.join(sorted(need))} (ได้: {', '.join(sorted(got)) or '-'})")
    env = plan["env"]
    out = ROOT / plan["out"]
    out.mkdir(parents=True, exist_ok=True)
    single = team_db().get("users") == "single"
    conns = {}
    res = {"ok": True, "rows": {}, "errors": []}
    who = _who()
    try:
        try:
            if single:
                conns["rw"] = _connect(env, "rw", interactive)
            else:
                if any(it["kind"] == "read" for it in plan["items"]):
                    conns["ro"] = _connect(env, "ro", interactive)
                    if not plan.get("explain"):
                        conns["ro"][0].cursor().execute("SET TRANSACTION READ ONLY")
                if plan["has_write"]:
                    conns["rw"] = _connect(env, "rw", interactive)
        except DbxError as e:
            ts = dt.datetime.now().isoformat(timespec="seconds")
            _log(f"{ts} {who} NOT-CONNECTED {env} plan={plan['id']} approved={approved_by}: {str(e.code)[:200]}")
            raise
        for it in plan["items"]:
            kind = "rw" if (it["kind"] != "read" and "rw" in conns) else ("ro" if "ro" in conns else "rw")
            conn, user = conns[kind]
            cur = conn.cursor()
            t0 = dt.datetime.now()
            if plan.get("explain"):
                _explain_item(conn, cur, it, user, env, plan, res, who, approved_by)
                continue
            try:
                total, last_rows = 0, None
                for s in it["stmts"]:
                    sql = s["sql"]
                    if plan["compile"] and s["kind"] == "read":
                        sql = f"SELECT * FROM ({sql}) WHERE 1 = 0"
                    cur.execute(sql)
                    if s["kind"] == "read":
                        cols = [d[0] for d in cur.description or []]
                        rows = cur.fetchall() if cols else []
                        last_rows = (cols, rows)
                    else:
                        total += max(cur.rowcount or 0, 0)
                if it["kind"] != "read":
                    conn.commit()
                if last_rows is not None and not plan["compile"]:
                    cols, rows = last_rows
                    with open(out / (Path(it["file"]).stem + ".csv"), "w", encoding="utf-8-sig", newline="") as fh:
                        w = csv.writer(fh)
                        w.writerow(cols)
                        for r in rows:
                            w.writerow(["" if v is None else (v.isoformat(sep=" ") if hasattr(v, "isoformat") else v) for v in r])
                if last_rows is not None:
                    msg = ("ผ่าน (คอมไพล์ได้)" if plan["compile"] else f"{len(last_rows[1])} แถว") + (f" · เปลี่ยน {total} แถว" if it["kind"] != "read" else "")
                else:
                    msg = f"สำเร็จ · เปลี่ยน {total} แถว"
                if it["kind"] == "read" and last_rows and not last_rows[1] and not plan["compile"]:
                    msg += " (0 แถว — ไม่นับว่าผ่าน ตรวจเงื่อนไข)"
                res["rows"][it["file"]] = msg
                print(f"  ✅ {it['file']}: {msg} · {(dt.datetime.now() - t0).total_seconds():.1f}s")
                ts = dt.datetime.now().isoformat(timespec="seconds")
                _log(f"{ts} {who} {'WRITE' if it['kind'] != 'read' else ('COMPILE' if plan['compile'] else 'READ')} {user}@{env} plan={plan['id']} {it['file']} → {msg} approved={approved_by}",
                     [ts, env, plan["id"], it["file"], "เขียน / แก้" if it["kind"] != "read" else ("คอมไพล์" if plan["compile"] else "อ่าน"), msg, approved_by],
                     deploy_row(it, ts, env, msg, f"ระบบ ({user}) · อนุญาตโดย {approved_by}") if it["kind"] != "read" else None)
            except Exception as e:
                if it["kind"] != "read":
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                m = (str(e).splitlines() or [type(e).__name__])[0][:200]
                res["ok"] = False
                res["errors"].append((it["file"], m))
                print(f"  ❌ {it['file']}: {m}" + ("  (คำสั่งแก้โครงสร้าง (DDL) commit ทันทีที่รัน — ตรวจสภาพตารางด้วย SELECT)" if any(s["kind"] == "ddl" for s in it["stmts"]) else ""))
                ts = dt.datetime.now().isoformat(timespec="seconds")
                _log(f"{ts} {who} ERROR {user}@{env} plan={plan['id']} {it['file']}: {m}", [ts, env, plan["id"], it["file"], it["kind"], "ERROR: " + m, approved_by])
                if not plan["compile"]:
                    print("  หยุดที่ไฟล์นี้ ไฟล์ถัดไปไม่รัน · ส่งข้อความ error ให้ผู้ตรวจ — ไม่เดา")
                    break
    finally:
        for conn, _u in conns.values():
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
    vdir = results_base() / "verify"
    if plan.get("explain"):
        vdir.mkdir(parents=True, exist_ok=True)
        vp = vdir / "explain_plan.txt"
        vp.write_text("# EXPLAIN PLAN กับฐานจริง (ไม่รันคำสั่ง) — " + dt.datetime.now().isoformat(timespec="seconds") + f" · {env}\n" +
                      "# รูปแบบ: <ไฟล์>\t<WARN|OK|ERROR>\t<ข้อความ>\n" + "\n".join(res.get("explain_lines", [])) + "\n", encoding="utf-8")
        print(f"  → {_rel(vp)}")
    if plan["compile"]:
        vdir.mkdir(parents=True, exist_ok=True)
        vp = vdir / "sql_compile.txt"
        vp.write_text("# คอมไพล์ SQL กับฐานจริง (WHERE 1=0) — " + dt.datetime.now().isoformat(timespec="seconds") + f" · {env}\n" +
                      "\n".join(f"{f}\tOK\t" for f in res["rows"]) + ("\n" if res["rows"] else "") +
                      "\n".join(f"{f}\tERROR\t{m}" for f, m in res["errors"]) + "\n", encoding="utf-8")
        print(f"  → {_rel(vp)}")
    return res


def _explain_item(conn, cur, it, user, env, plan, res, who, approved_by):
    """EXPLAIN PLAN ทีละคำสั่ง → DBMS_XPLAN · เตือน full scan / ไม่ตัด partition / cartesian · ไม่ commit"""
    out_dir = ROOT / plan["out"]
    out_dir.mkdir(parents=True, exist_ok=True)
    texts, warns = [], []
    try:
        for n, s in enumerate(it["stmts"], 1):
            sid = f"WS{plan['id'][:6]}{n}"
            cur.execute(f"EXPLAIN PLAN SET STATEMENT_ID = '{sid}' FOR {s['sql']}")
            cur.execute(f"SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', '{sid}', 'TYPICAL'))")
            lines = [str(r[0]) for r in cur.fetchall()]
            texts += [f"-- คำสั่งที่ {n}", *lines, ""]
            for rx, why in PLAN_WARN:
                hit = [l for l in lines if rx.search(l)]
                if hit:
                    warns.append(f"คำสั่งที่ {n}: {why} — {' '.join(hit[0].split())[:120]}")
        (out_dir / (Path(it["file"]).stem + ".plan.txt")).write_text("\n".join(texts) + "\n", encoding="utf-8")
        msg = (f"🟡 {len(warns)} ข้อเตือน" if warns else "ไม่มีข้อเตือน") + f" · {len(it['stmts'])} คำสั่ง"
        res["rows"][it["file"]] = msg
        res.setdefault("explain_lines", []).extend([f"{it['file']}\tWARN\t{w}" for w in warns] or [f"{it['file']}\tOK\t-"])
        print(f"  ✅ {it['file']}: EXPLAIN PLAN {msg}")
        for w in warns:
            print(f"      🟡 {w}")
        ts = dt.datetime.now().isoformat(timespec="seconds")
        _log(f"{ts} {who} EXPLAIN {user}@{env} plan={plan['id']} {it['file']} → {msg} approved={approved_by}",
             [ts, env, plan["id"], it["file"], "EXPLAIN PLAN", msg, approved_by])
    except Exception as e:
        m = (str(e).splitlines() or [type(e).__name__])[0][:200]
        res["ok"] = False
        res["errors"].append((it["file"], m))
        res.setdefault("explain_lines", []).append(f"{it['file']}\tERROR\t{m}")
        print(f"  ❌ {it['file']}: EXPLAIN PLAN ไม่สำเร็จ: {m}" + ("  (user อาจไม่มี PLAN_TABLE / สิทธิ์ — ให้ DBA ตรวจ)" if "942" in m or "1031" in m else ""))
    finally:
        try:
            conn.rollback()   # ทิ้งแถวใน PLAN_TABLE
        except Exception:
            pass


def write_todo(plan: dict):
    if not plan["todo"]:
        return None
    out = ROOT / plan["out"]
    out.mkdir(parents=True, exist_ok=True)
    p = out / "_HUMAN_TODO.md"
    L = [f"# ไฟล์ใน {plan['target']} ที่คนต้องทำเอง ({len(plan['todo'])} ไฟล์)", "", "ทำทีละไฟล์ตามลำดับ", ""]
    L += human_steps(plan, plan["todo"])
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False
