"""คำสั่งฐานข้อมูลของ workspace (เรียกผ่าน tools/workspace.py) — ทุกการรันต้องผ่านแผน + อนุญาตของคน

  db-status                       กติกาทีม · ค่าการเชื่อมต่อ (ไม่มีรหัสผ่าน) · ตัวต่อ Oracle · ตัวแปรรหัสผ่านที่ตั้งแล้ว
  db-policy  [--access human|ai] [--select-mode ask|auto] [--users split|single] [--default-env DEV] [--read-odi-log yes|no]
  db-connect [--env DEV] [--host H --port 1521 --service S --user-ro U --user-rw U] [--default] [--non-interactive]
  db-driver  [--install]          ตรวจ / ติดตั้ง python-oracledb (thin mode ไม่ต้องลง Oracle Client)
  db-test    [--env DEV] [--plan | --approved "<ชื่อ> <วันที่>"]   SELECT USER, SYSDATE FROM dual (อ่านอย่างเดียว)
  run-sql    --job PROJECT/job <rp01 | โฟลเดอร์ | ไฟล์.sql> [--env] [--only] [--compile | --explain]
             [--plan | --run-read] · --execute <แผน> --approved "<ชื่อ> <วันที่>" [--confirm T1,T2]
             · --human <แผน> · --record-human <แผน> --result "<ผล>"

ขั้นตอนเมื่อ AI เป็นผู้เรียก (ไม่มีจอให้ตอบ): --plan → ถามคนในแชท (ตอบเป็นเลข) → --execute <แผน> --approved "<ชื่อคน> <วันที่>"
exit code: 0 สำเร็จ · 1 ผิดพลาด · 3 ต้องขออนุญาตจากคนก่อน
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

from . import dbx

EXIT_NEED_APPROVAL = 3
COMMANDS = ("db-status", "db-policy", "db-connect", "db-driver", "db-test", "run-sql")
HOST_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,252}$")
SERVICE_RX = re.compile(r"^[A-Za-z][A-Za-z0-9_.$#\-]{0,127}$")
USER_RX = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


# ---------------------------------------------------------------- ตัวช่วยถามตอบ (Terminal เท่านั้น)
def ask(prompt: str, default: str = "", validate=None, required: bool = True) -> str:
    while True:
        shown = f" [{default}]" if default else ""
        try:
            value = input(f"   {prompt}{shown}: ").strip().strip('"') or default
        except EOFError:
            raise dbx.DbxError("input สิ้นสุดก่อนตอบครบ — ใช้ --non-interactive พร้อมค่าที่ต้องการ") from None
        if not value and not required:
            return ""
        problem = (validate(value) if validate and value else None) or (None if value else "ต้องระบุค่า")
        if problem:
            print(f"   ⚠️  {problem}")
            continue
        return value


def _check(rx, msg):
    return lambda v: None if rx.match(v) else msg


# ---------------------------------------------------------------- db-status / db-policy
def cmd_status(root: Path, a) -> int:
    dbx.set_root(root)
    db = dbx.team_db()
    d, cons = dbx.connections()
    print("กติกาทีม (shared/team.json → db):")
    print(f"   ai_access    {db['ai_access']}  ({'ระบบรันได้หลังคนอนุญาตแต่ละแผน' if db['ai_access'] == 'ai' else 'คนรันทั้งหมด — ระบบเตรียมแผนและขั้นตอน'})")
    print(f"   select_mode  {db['select_mode']}  ({'ถามก่อนทุกครั้งรวม SELECT' if db['select_mode'] == 'ask' else 'SELECT รันต่อเนื่อง ถามเฉพาะคำสั่งที่เขียน'})")
    print(f"   users        {db['users']}  ({'แยก user อ่าน / เขียน' if db['users'] == 'split' else 'user เดียว'})")
    print(f"   read_odi_log {str(db['read_odi_log']).lower()} · default_env {db.get('default_env', 'DEV')}")
    print("การเชื่อมต่อ (shared/db.local.json — เฉพาะเครื่องนี้ ไม่มีรหัสผ่าน):")
    if not cons:
        print("   ยังไม่มี — python tools/workspace.py db-connect")
    for env, c in sorted(cons.items()):
        vars_ = [dbx.pw_var("rw", env)] if db["users"] == "single" else [dbx.pw_var("ro", env), dbx.pw_var("rw", env)]
        pw = " · ".join(f"{v}={'ตั้งแล้ว' if os.environ.get(v) else 'ยังไม่ตั้ง'}" for v in vars_)
        print(f"   {'*' if env == d else ' '} {env:<6} {c.get('host')}:{c.get('port', 1521)}/{c.get('service')} · "
              f"ro={c.get('user_ro') or '-'} · rw={c.get('user_rw') or '-'} · {pw}")
    ver = dbx.driver_version()
    print(f"ตัวต่อ Oracle: {'python-oracledb ' + ver if ver else 'ยังไม่ติดตั้ง — python tools/workspace.py db-driver --install'}")
    print("ขอบเขต: simulate ยังออฟไลน์ · การรันฐานจริงไม่เปลี่ยน G4–G7 (NOT_EXECUTED)")
    return 0


def cmd_policy(root: Path, a) -> int:
    dbx.set_root(root)
    changes = {"ai_access": a.access, "select_mode": a.select_mode, "users": a.users, "default_env": a.default_env}
    if a.read_odi_log is not None:
        changes["read_odi_log"] = a.read_odi_log == "yes"
    if all(v is None for v in changes.values()):
        return cmd_status(root, a)
    db = dbx.set_policy(root, **changes)
    print("บันทึกกติกาทีมใน shared/team.json → db: " + " · ".join(f"{k}={v}" for k, v in db.items()))
    print("กติกาทีมควรเปลี่ยนผ่าน PR/การตกลงของทีม · ค่าอื่นใน team.json คงเดิม")
    return 0


# ---------------------------------------------------------------- db-connect
def cmd_connect(root: Path, a) -> int:
    dbx.set_root(root)
    db = dbx.team_db()
    if db["ai_access"] != "ai":
        raise dbx.DbxError("ทีมตั้งให้คนรันทั้งหมด (ai_access = human) — ถ้าทีมตกลงให้ระบบเข้าฐาน: "
                           "python tools/workspace.py db-policy --access ai แล้วรัน db-connect อีกครั้ง")
    d, cons = dbx.connections()
    interactive = not a.non_interactive and dbx.stdin_is_tty()
    env = (a.env or (ask("ชื่อฐาน (DEV / SIT / PROD …)", db.get("default_env") or "DEV",
                         _check(dbx.ENV_RX, "ใช้ A-Z 0-9 _ ขึ้นต้นด้วยตัวอักษร")) if interactive else db.get("default_env") or "DEV")).upper()
    if not dbx.ENV_RX.match(env):
        raise dbx.DbxError("ชื่อฐานใช้ A-Z 0-9 _ ขึ้นต้นด้วยตัวอักษร")
    old = cons.get(env, {})
    if env == "PROD":
        print("   🔴 PROD = ฐานจริง — ทุกแผนยังต้องได้รับอนุญาต และคำสั่งที่ลบแล้วกู้คืนไม่ได้ต้องพิมพ์ชื่อตารางยืนยัน")

    def value(name, flag, prompt, default, rx, msg, required=True):
        v = getattr(a, flag)
        if v is None and interactive:
            v = ask(prompt, str(default or ""), _check(rx, msg), required)
        v = v if v is not None else (default or "")
        if v and not rx.match(str(v)):
            raise dbx.DbxError(f"{name}: {msg}")
        if required and not v:
            raise dbx.DbxError(f"ต้องระบุ {name} (--{flag.replace('_', '-')})")
        return v

    c = {"host": value("host", "host", f"host ของ Oracle {env} (ดูจาก DBeaver: Edit Connection → Host)", old.get("host"),
                       HOST_RX, "ใช้ชื่อเครื่องหรือ IP ไม่มีช่องว่าง")}
    c["port"] = int(value("port", "port", "port", old.get("port") or 1521, re.compile(r"^\d{1,5}$"), "ใส่ตัวเลข"))
    c["service"] = value("service", "service", "service name (ไม่ใช่ชื่อ schema)", old.get("service"), SERVICE_RX, "รูปแบบ service name ไม่ถูกต้อง")
    if db["users"] == "split":
        c["user_ro"] = value("user_ro", "user_ro", "username อ่านอย่างเดียว (ใช้กับ SELECT)", old.get("user_ro"), USER_RX, "รูปแบบ username ไม่ถูกต้อง")
        c["user_rw"] = value("user_rw", "user_rw", "username ที่เขียนได้ (Enter เปล่า = ยังไม่มี ให้คนรันคำสั่งเขียนเอง)",
                             old.get("user_rw"), USER_RX, "รูปแบบ username ไม่ถูกต้อง", required=False)
    else:
        c["user_rw"] = value("user_rw", "user_rw", "username (ใช้กับทุกคำสั่ง)", old.get("user_rw") or a.user_ro, USER_RX, "รูปแบบ username ไม่ถูกต้อง")
        c["user_ro"] = ""
    for k in ("user_ro", "user_rw"):
        if str(c.get(k) or "").upper() in ("SYS", "SYSTEM"):
            raise dbx.DbxError("ห้ามใช้ SYS / SYSTEM — ขอ user เฉพาะ schema ของงานจาก DBA")
    dbx.save_connection(root, env, c, make_default=a.default)
    print(f"✅ บันทึกการเชื่อมต่อ {env} ใน shared/db.local.json (ไม่ขึ้น Git · ไม่มีรหัสผ่าน)")
    if db["users"] == "split" and not c.get("user_rw"):
        print("   ⚠️  ยังไม่มี user ที่เขียนได้ — คำสั่งที่เขียนจะให้คนรันเองไปก่อน")
    password_notice(env, db["users"])
    return 0


def password_notice(env: str, users: str):
    need = [dbx.pw_var("rw", env)] if users == "single" else [dbx.pw_var("ro", env), dbx.pw_var("rw", env)]
    miss = [v for v in need if not os.environ.get(v)]
    if miss:
        print("   🔑 ระบบ/AI พิมพ์รหัสผ่านแทนคนไม่ได้ — ตั้งตัวแปรบนเครื่องก่อนให้ระบบรันเอง: " + " · ".join(miss))
        print(f"      ครั้งเดียวต่อเครื่อง (PowerShell): setx {miss[0]} \"<รหัสผ่าน>\" แล้วปิดเปิด Terminal ใหม่ · ห้ามพิมพ์รหัสในแชท/ไฟล์")
        print("      หรือรันคำสั่งเองใน Terminal แล้วพิมพ์รหัสตอนถาม (ไม่แสดงบนจอ ไม่เก็บ)")


# ---------------------------------------------------------------- db-driver
def cmd_driver(root: Path, a) -> int:
    ver = dbx.driver_version()
    if ver:
        print(f"✅ python-oracledb {ver} พร้อมใช้ (thin mode · ไม่ต้องลง Oracle Client) — {sys.executable}")
        return 0
    if not a.install:
        print("ยังไม่มี python-oracledb — ติดตั้งครั้งเดียวต่อเครื่อง: python tools/workspace.py db-driver --install")
        return 1
    print(f"กำลังติดตั้ง python-oracledb ด้วย {sys.executable} -m pip install --user oracledb …")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "oracledb"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ ติดตั้งไม่สำเร็จ: " + (((r.stderr or r.stdout).strip().splitlines()) or ["?"])[-1][:300])
        print("   ถ้าเครื่องต่ออินเทอร์เน็ตไม่ได้ / บริษัทบล็อก pip ให้ขอ IT ติดตั้ง หรือให้คนรัน SQL เองใน DBeaver")
        return 1
    try:
        import site
        sys.path.append(site.getusersitepackages())
    except Exception:
        pass
    importlib.invalidate_caches()
    ver = dbx.driver_version()
    print(f"✅ ติดตั้งแล้ว: python-oracledb {ver}" if ver else "⚠️  ติดตั้งแล้วแต่ยังโหลดไม่ได้ — ปิด Terminal แล้วรันใหม่")
    return 0 if ver else 1


# ---------------------------------------------------------------- แผน → อนุญาต → รัน (ใช้ทั้ง db-test และ run-sql)
def ai_hint(plan: dict):
    pre = dbx.cmd_prefix(plan)
    print()
    print("👉 สำหรับ AI: ถามคนในแชทด้วยข้อความ ❓ ด้านบน (ตอบเป็นเลข · ห้ามเลือกแทนคน)")
    conf = f" --confirm {','.join(plan['destructive'])}" if plan["destructive"] else ""
    print(f"   ตอบ 1 → {pre} --execute {plan['id']} --approved \"<ชื่อคนที่อนุญาต> {dt.date.today()}\"{conf}")
    if plan["destructive"]:
        print(f"           (ต้องให้คนพิมพ์ชื่อตาราง {', '.join(plan['destructive'])} ในแชทก่อน แล้วใส่ใน --confirm ตามที่คนพิมพ์)")
    print(f"   ตอบ 2 → {pre} --human {plan['id']} แล้วบอกคนทีละไฟล์")


def show_human(plan: dict):
    print(f"ขั้นตอนให้คนรันเอง — ฐาน {plan['env']} · แผน {plan['id']} (ทำทีละไฟล์)")
    for line in dbx.human_steps(plan):
        print(line)
    print(f"รันเสร็จแล้ว: {dbx.cmd_prefix(plan)} --record-human {plan['id']} --result \"<ผลที่ได้>\"")


def interactive_flow(plan: dict) -> int:
    print(dbx.render(plan))
    todo = dbx.write_todo(plan)
    if todo:
        print(f"  → รายการให้คนทำ: {dbx._rel(todo)}")
    if not plan["items"]:
        show_human(plan)
        return 0
    if dbx.needs_question(plan):
        print()
        print(dbx.question_text(plan))
        print("   Enter = 1 · ? = อธิบายละเอียด · q = ยกเลิก")
        while True:
            try:
                ans = input("   คำตอบ [Enter = 1]: ").strip() or "1"
            except EOFError:
                print("   ยกเลิก — ไม่ได้รันอะไร")
                return EXIT_NEED_APPROVAL
            if ans == "?":
                print("   ℹ️  1 = ระบบต่อฐานแล้วรันเฉพาะคำสั่งในแผนด้านบน (บันทึกทุกครั้ง) · 2 = ระบบบอกขั้นตอนให้คุณรันเองทีละไฟล์")
                continue
            if ans == "q":
                print("   ยกเลิก — ไม่ได้รันอะไร")
                return 0
            if ans in ("1", "2"):
                break
            print("   ⚠️  ตอบได้: 1 หรือ 2")
        if ans == "2":
            show_human(plan)
            return 0
    confirm = []
    for t in plan["destructive"]:
        v = input(f"   ⚠️  พิมพ์ชื่อตาราง {t} เพื่อยืนยันว่าจะลบ / ล้าง (Enter เปล่า = ยกเลิก): ").strip()
        if not v:
            print("   ยกเลิก — ไม่ได้รันอะไร")
            return 0
        confirm.append(v)
    res = dbx.execute(plan, f"คนที่ Terminal ({dbx._who()})", confirm, interactive=True)
    print(f"ผลอยู่ที่ {plan['out']}/ · บันทึกใน {'status/DB_RUN_LOG.md' if plan.get('job') else 'registry/db_queries.log'}")
    return 0 if res["ok"] else 1


def plan_only(plan: dict, target_hint: str) -> int:
    print(dbx.render(plan))
    todo = dbx.write_todo(plan)
    if todo:
        print(f"  → รายการให้คนทำ: {dbx._rel(todo)} (ทำทีละไฟล์)")
    if plan["ai_access"] != "ai":
        print("\nทีมตั้งให้คนรันทั้งหมด (ai_access = human) — ระบบไม่รัน")
        show_human(plan)
        return 0
    if plan["items"]:
        print()
        print(dbx.question_text(plan))
        if dbx.needs_question(plan):
            ai_hint(plan)
            return EXIT_NEED_APPROVAL
        print(f"\nSELECT ล้วน + select_mode = auto → รันได้เลย: {dbx.cmd_prefix(plan)} {target_hint} --run-read")
    return 0


def resolve_job(root: Path, name: str | None) -> Path:
    if not name:
        return root
    sys.path.insert(0, str(root / "kit" / "src"))
    from migrate_kit.storage import WorkspaceError, find_job
    try:
        return find_job(root, name)
    except (WorkspaceError, KeyError, ValueError) as exc:
        raise dbx.DbxError(str(exc)) from None


def cmd_run_sql(root: Path, a) -> int:
    base = resolve_job(root, a.job)
    dbx.set_root(base)
    if a.execute:
        if not (a.approved or "").strip():
            raise dbx.DbxError("--execute ต้องมี --approved \"<ชื่อคนที่อนุญาต> <วันที่>\" — ถามคนก่อนเสมอ ห้ามอนุญาตแทนคน")
        plan = dbx.load_plan(a.execute)
        print(dbx.render(plan))
        res = dbx.execute(plan, a.approved.strip(), (a.confirm or "").split(","), interactive=dbx.stdin_is_tty())
        print(f"ผลอยู่ที่ {plan['out']}/")
        return 0 if res["ok"] else 1
    if a.human:
        show_human(dbx.load_plan(a.human))
        return 0
    if a.record_human:
        if not (a.result or "").strip():
            raise dbx.DbxError("--record-human ต้องมี --result \"<ผลที่คนบอก>\"")
        n = dbx.record_human(dbx.load_plan(a.record_human), a.result.strip())
        print(f"✅ บันทึกแล้ว ({n} ไฟล์) — ต่อไป: ตรวจผลด้วย SELECT")
        return 0
    if not a.target:
        raise dbx.DbxError("ต้องระบุเป้าหมาย (pack / โฟลเดอร์ / ไฟล์ .sql) หรือ --execute / --human / --record-human")
    plan = dbx.make_plan(a.target, a.env, a.only, a.compile, explain=a.explain)
    if a.run_read:
        print(dbx.render(plan))
        dbx.write_todo(plan)
        if not plan["items"]:
            return 0
        if dbx.needs_question(plan):
            print()
            print(dbx.question_text(plan))
            ai_hint(plan)
            return EXIT_NEED_APPROVAL
        res = dbx.execute(plan, "select_mode=auto (ทีมอนุญาต SELECT ต่อเนื่อง)", read_only_call=True)
        print(f"ผลอยู่ที่ {plan['out']}/")
        return 0 if res["ok"] else 1
    if a.plan or not dbx.stdin_is_tty():
        return plan_only(plan, a.target)
    return interactive_flow(plan)


def cmd_test(root: Path, a) -> int:
    dbx.set_root(root)
    if dbx.team_db()["ai_access"] != "ai":
        raise dbx.DbxError("ทีมตั้งให้คนรันทั้งหมด (ai_access = human) — ระบบไม่ต่อฐาน · ทดสอบใน DBeaver: SELECT USER FROM dual")
    tmp = root / "registry" / "tmp_db"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "ping.csv").unlink(missing_ok=True)          # never report an old result as a fresh connection
    (tmp / "ping.sql").write_text("-- ทดสอบการเชื่อมต่อ (อ่านอย่างเดียว)\nSELECT USER AS DB_USER, SYSDATE AS DB_TIME FROM dual\n", encoding="utf-8")
    plan = dbx.make_plan("registry/tmp_db/ping.sql", a.env, out_dir=tmp)
    if not plan["env_known"]:
        raise dbx.DbxError(f"ยังไม่มีค่าการเชื่อมต่อของ {plan['env']} — python tools/workspace.py db-connect --env {plan['env']}")
    if a.approved:
        print(dbx.render(plan))
        res = dbx.execute(plan, a.approved.strip(), interactive=dbx.stdin_is_tty())
    elif a.plan or not dbx.stdin_is_tty():
        return plan_only(plan, "registry/tmp_db/ping.sql")
    else:
        code = interactive_flow(plan)
        res = {"ok": code == 0}
    out = tmp / "ping.csv"
    if not out.exists():
        print("ยังไม่ได้ทดสอบการเชื่อมต่อ (ยกเลิก / เลือกรันเอง / ต่อไม่ได้)")
        return 1
    if res["ok"]:
        print("✅ ต่อฐานได้ · " + out.read_text(encoding="utf-8-sig").strip().splitlines()[-1])
        return 0
    return 1


# ---------------------------------------------------------------- entry
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="workspace.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("db-status")
    p = sub.add_parser("db-policy")
    p.add_argument("--access", choices=dbx.POLICY_CHOICES["ai_access"])
    p.add_argument("--select-mode", choices=dbx.POLICY_CHOICES["select_mode"])
    p.add_argument("--users", choices=dbx.POLICY_CHOICES["users"])
    p.add_argument("--default-env")
    p.add_argument("--read-odi-log", choices=("yes", "no"))
    p = sub.add_parser("db-connect")
    for flag in ("--env", "--host", "--service", "--user-ro", "--user-rw"):
        p.add_argument(flag)
    p.add_argument("--port")
    p.add_argument("--default", action="store_true", help="ตั้งเป็นฐานเริ่มต้น")
    p.add_argument("--non-interactive", action="store_true")
    p = sub.add_parser("db-driver"); p.add_argument("--install", action="store_true")
    p = sub.add_parser("db-test"); p.add_argument("--env"); p.add_argument("--plan", action="store_true"); p.add_argument("--approved")
    p = sub.add_parser("run-sql")
    p.add_argument("target", nargs="?")
    p.add_argument("--job", help="PROJECT/job (ไม่ระบุ = ระดับ workspace)")
    p.add_argument("--env"); p.add_argument("--only")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--compile", action="store_true", help="คอมไพล์ SELECT แบบ WHERE 1=0")
    mode.add_argument("--explain", action="store_true", help="EXPLAIN PLAN (ไม่รันคำสั่งจริง) · ถามก่อนเสมอ")
    p.add_argument("--plan", action="store_true", help="แสดงแผน + คำถาม ไม่ต่อฐาน")
    p.add_argument("--run-read", action="store_true", help="SELECT ล้วน · รันได้เลยเฉพาะเมื่อทีมตั้ง select_mode = auto")
    p.add_argument("--execute", metavar="PLAN"); p.add_argument("--approved"); p.add_argument("--confirm")
    p.add_argument("--human", metavar="PLAN"); p.add_argument("--record-human", metavar="PLAN"); p.add_argument("--result")
    return ap


HANDLERS = {"db-status": cmd_status, "db-policy": cmd_policy, "db-connect": cmd_connect,
            "db-driver": cmd_driver, "db-test": cmd_test, "run-sql": cmd_run_sql}


def main(root: Path, argv: list[str]) -> int:
    a = parser().parse_args(argv)
    try:
        return HANDLERS[a.command](Path(root).resolve(), a)
    except dbx.DbxError as exc:
        print(str(exc.code))
        return 1
    except KeyboardInterrupt:
        print("\nยกเลิก")
        return 130
