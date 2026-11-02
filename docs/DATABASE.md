# ต่อฐาน Oracle จาก workspace (Oracle adapter)

Oracle adapter อยู่ที่ `tools/dbcore/` เป็นส่วนเสริมระดับ workspace ที่ port มาจาก `kit/job/scripts/runpack/dbx.py`
ของ Migrate_ODI_Team2 (kit 2.15.0) ใช้รัน Run Pack / คอมไพล์ SQL / EXPLAIN PLAN / DDL บนฐาน Oracle จริง
โดยต้องมีแผนที่คนเห็นและอนุญาตก่อนทุกครั้ง

| ยังคงเหมือนเดิม | เปลี่ยน / เพิ่มขึ้น |
|---|---|
| `simulate` ออฟไลน์ ใช้ SQLite + fixture เท่านั้น | มีคำสั่ง `db-*` และ `run-sql` ที่ต่อ Oracle ได้เมื่อทีมอนุญาต |
| kit 0.1.0 และ `kit.lock.json` ของงานเดิมไม่เปลี่ยน hash | adapter อยู่นอก `kit/src` จึงไม่ต้องออก kit รุ่นใหม่ |
| `config.json` `db_mode` ของงาน = `human` (ค่าของ simulator runtime) | กติกาฐานจริงอยู่ที่ `shared/team.json` → `"db"` |
| G4–G7 = `NOT_EXECUTED` | การรันฐานจริงบันทึกใน `status/DB_RUN_LOG.md` แต่ไม่เปลี่ยน Gate |
| fingerprint ของ simulated review (input/config/kit.lock) | ผลจากฐานเก็บที่ `<job>/db_runs/` นอก `input/` จึงไม่ทำให้งานเป็น STALE |

## 1. ตั้งค่า

### ผ่าน Setup wizard (แนะนำ)

`.\setup_workspace.ps1` ถาม 8 ข้อ ข้อ 7–8 เป็นเรื่องฐานข้อมูล:

| ข้อ | คำถาม | บันทึกที่ |
|---|---|---|
| 7 | ใครรัน SQL บนฐานจริง: คนรันเอง (ค่าเริ่มต้น) / ระบบ-AI รันหลังคนอนุญาต | `shared/team.json` → `db.ai_access` |
| 7.1 | SELECT ต้องถามก่อนทุกครั้ง (`ask`) หรือรันต่อเนื่องใน Run Pack (`auto`) | `db.select_mode` |
| 7.2 | แยก user อ่าน/เขียน (`split`) หรือ user เดียว (`single`) | `db.users` |
| 8 | env / host / port / service / user อ่านอย่างเดียว / user ที่เขียนได้ | `shared/db.local.json` (ไม่มีรหัสผ่าน · ไม่ขึ้น Git) |
| 8.1 | หลัง Setup: ติดตั้ง python-oracledb + ทดสอบ / ติดตั้งอย่างเดียว / ข้าม | ผลใน `.cache/setup/last-result.json` → `db` |

ข้อ 8 จะถามเฉพาะเมื่อข้อ 7 เลือกให้ระบบรัน ถ้าเลือกคนรันเองและเดิมก็เป็นคนรันอยู่แล้ว Setup จะไม่เขียนอะไรเพิ่ม
ถ้าการทดสอบการเชื่อมต่อล้มเหลว Setup จะเตือน (WARN) แต่ไม่ยกเลิก เพราะ workspace ที่ทำงานออฟไลน์พร้อมใช้แล้ว

### ผ่านพารามิเตอร์ (automation)

```powershell
.\setup_workspace.ps1 -NonInteractive -DbAccess ai -DbSelectMode ask -DbUsers split `
  -DbEnv DEV -DbHost devdb.company.local -DbPort 1521 -DbService DEVPDB `
  -DbUserRo APP_RO -DbUserRw APP_RW -InstallOracleDriver -TestDbConnection
```

ไม่มีพารามิเตอร์สำหรับรหัสผ่าน ถ้าไม่ส่ง `-Db*` กติกาและค่าการเชื่อมต่อเดิมจะคงไว้
ถ้าส่ง `-DbHost` ต้องมีกติกาเป็น `ai` (จาก `-DbAccess ai` หรือค่าที่มีอยู่แล้ว) และห้ามใช้ user `SYS` / `SYSTEM`

### ผ่านคำสั่ง

```powershell
python tools/workspace.py db-policy --access ai --select-mode ask --users split
python tools/workspace.py db-connect            # ถามทีละค่าใน Terminal
python tools/workspace.py db-connect --env SIT --host sitdb --service SITPDB --user-ro APP_RO --non-interactive
python tools/workspace.py db-driver --install   # pip install --user oracledb (thin mode ไม่ต้องลง Oracle Client)
python tools/workspace.py db-status
```

### รหัสผ่าน

รหัสผ่านไม่ถูกเก็บลงไฟล์ใดเลย มีสองทาง:

1. ตั้งตัวแปรครั้งเดียวต่อเครื่อง: `setx ORA_RO_PASSWORD "…"` และ `setx ORA_RW_PASSWORD "…"` แล้วปิดเปิด Terminal ใหม่
   สำหรับฐานที่ไม่ใช่ค่าเริ่มต้นให้เติมชื่อฐานต่อท้าย เช่น `ORA_RW_PASSWORD_SIT`
2. รันคำสั่งเองใน Terminal แล้วพิมพ์รหัสตอนระบบถาม ตัวอักษรไม่แสดงบนจอและใช้ครั้งเดียว

AI พิมพ์รหัสผ่านแทนคนไม่ได้ และห้ามพิมพ์รหัสผ่านลงในแชท

## 2. กติกาการรัน (ทุกคำสั่งผ่านแผน)

```text
make_plan (เก็บ SHA-256 ของทุกไฟล์ใน .dbx/plans/<id>.json)
   → แสดงแผน (ฐาน · ไฟล์ · คำสั่ง · คำเตือน)
   → คนตอบ 1 = ให้ระบบรัน / 2 = ฉันรันเอง
   → execute: ตรวจ hash อีกครั้ง → ต่อฐาน → รัน → บันทึก
```

| กติกา | รายละเอียด |
|---|---|
| ทีมตั้งให้คนรัน (`human`) | ระบบไม่ต่อฐาน แสดงขั้นตอนให้คนรันทีละไฟล์ และบันทึกผลด้วย `--record-human` |
| คำสั่งที่เขียน / แก้โครงสร้าง | ถามก่อนเสมอ ไม่ว่าจะตั้ง `select_mode` เป็นอะไร |
| SELECT | ถามก่อนเมื่อ `select_mode = ask` · ถ้าเป็น `auto` รันต่อเนื่องได้เฉพาะไฟล์ใน `run_packs/` |
| ถามก่อนเสมอ | L3 (ดึงข้อมูลรายแถว) · query นอก Run Pack · EXPLAIN PLAN · ฐาน PROD |
| คำสั่งที่ลบแล้วกู้คืนไม่ได้ | DROP · TRUNCATE · DELETE / UPDATE ที่ไม่มี WHERE ของตัวคำสั่งเอง (WHERE ใน subquery หรือในข้อความไม่นับ) · ALTER … DROP / TRUNCATE ต้องพิมพ์ชื่อตารางยืนยันให้ตรงทุกตัว · PL/SQL ที่มี TRUNCATE / DROP / EXECUTE IMMEDIATE = คนรันเอง |
| แผนถูกแก้ | ตอนรัน ระบบสร้างคำสั่งใหม่จากไฟล์ SQL ที่อนุญาตแล้วเทียบกับแผน — แก้ไฟล์แผน (`.dbx/plans`) จะถูกปฏิเสธ |
| ไฟล์ Blendata | รู้จากชื่อไฟล์ (blendata / spark) หรือหัวไฟล์ที่ระบุว่า Blendata / Spark SQL เท่านั้น — DML ของ Oracle ที่แค่กล่าวถึง Blendata ยังรันได้ |
| hint | `/*+ … */` ถูกส่งไปที่ฐานตามเดิม (comment อื่นถูกตัด) |
| `users = split` | SELECT ใช้ user อ่านอย่างเดียวพร้อม `SET TRANSACTION READ ONLY` · คำสั่งเขียนใช้ user ที่เขียนได้ |
| ไฟล์ถูกแก้หลังสร้างแผน | รันไม่ได้ ต้องสร้างแผนใหม่และขออนุญาตใหม่ |
| ไม่รันเสมอ | Spark / Blendata SQL · คำสั่งเขียนลงตาราง `SNP_*` ของ ODI · อ่าน `SNP_*` เมื่อ `read_odi_log = false` |
| ขอบเขตไฟล์ | รันได้เฉพาะไฟล์ภายในโฟลเดอร์ของงาน (หรือ workspace ถ้าไม่ระบุ `--job`) |
| error | หยุดที่ไฟล์ที่ error และ rollback คำสั่ง DML (DDL ของ Oracle commit ทันที) |
| ไฟล์จาก `output/` | ระบบเตือนว่าเป็น illustrative DML จาก simulator แนะนำให้ `--compile` / `--explain` ก่อนรันจริง |

งานใดต้องการให้คนรันเสมอแม้ทีมตั้งเป็น `ai`: ใส่ `"db_access": "human"` ใน `job.json` ของงานนั้น
(`job.json` ไม่อยู่ใน fingerprint จึงไม่ทำให้งานเป็น STALE)

## 3. คำสั่ง `run-sql`

```powershell
# แสดงแผน ไม่ต่อฐาน (AI ใช้รูปแบบนี้แล้วถามคนในแชท) → exit 3 = ต้องขออนุญาต
python tools/workspace.py run-sql --job DEMO/customer_daily rp01 --plan

# คนอนุญาตแล้ว
python tools/workspace.py run-sql --job DEMO/customer_daily --execute <แผน> --approved "Mana 2026-11-02"
python tools/workspace.py run-sql --job DEMO/customer_daily --execute <แผน> --approved "Mana 2026-11-02" --confirm CUSTOMER_DIM

# คนรันใน Terminal เอง (ถามเป็นเลขบนจอ)
python tools/workspace.py run-sql --job DEMO/customer_daily rp01

# คอมไพล์ SQL ที่แปลงแล้ว (SELECT แบบ WHERE 1=0) / EXPLAIN PLAN ของ INSERT-MERGE (ไม่รันจริง)
python tools/workspace.py run-sql --job DEMO/customer_daily output/sql/converted --compile
python tools/workspace.py run-sql --job DEMO/customer_daily output/dml --explain

# SELECT ล้วน + ทีมตั้ง select_mode = auto
python tools/workspace.py run-sql --job DEMO/customer_daily rp01 --run-read

# คนรันใน DBeaver เอง
python tools/workspace.py run-sql --job DEMO/customer_daily --human <แผน>
python tools/workspace.py run-sql --job DEMO/customer_daily --record-human <แผน> --result "DBeaver 2026-11-02: 10 แถว ไม่มี error"

# ทดสอบการเชื่อมต่อ (SELECT USER, SYSDATE FROM dual)
python tools/workspace.py db-test
```

เป้าหมายระบุได้เป็น ชื่อ pack (`rp01` → `run_packs/rp01*`) · โฟลเดอร์ · ไฟล์ `.sql` และใช้ `--only S2,S3` เพื่อเลือกไฟล์ตามคำขึ้นต้น

exit code: `0` สำเร็จ · `1` ผิดพลาด · `3` ต้องขออนุญาตจากคนก่อน

## 4. ผลลัพธ์และบันทึก

| Path | เนื้อหา |
|---|---|
| `<job>/db_runs/<pack>/*.csv` (งาน simulation) · `<job>/input/run_results/<pack>/*.csv` (งาน delivery — ที่ `read_run_results.py` อ่าน) | ผล SELECT (UTF-8 BOM มีหัวคอลัมน์) · 0 แถวไม่นับว่าผ่าน |
| `<job>/db_runs/<pack>/_HUMAN_TODO.md` | ไฟล์ที่คนต้องรันเอง |
| `<job>/db_runs/verify/sql_compile.txt` | ผลคอมไพล์ (OK / ERROR) |
| `<job>/db_runs/verify/explain_plan.txt` + `*.plan.txt` | EXPLAIN PLAN และคำเตือน full scan / partition / cartesian |
| `<job>/status/DB_RUN_LOG.md` | ทุกครั้งที่รัน: เวลา · ฐาน · แผน · ไฟล์ · ผล · ผู้อนุญาต |
| `<job>/status/DEPLOY_LOG.md` | รายการ DDL / DML ที่เขียนลงฐานจริง |
| `registry/db_queries.log` | log รวมของ workspace รวมถึงครั้งที่ต่อฐานไม่สำเร็จ |
| `<job>/.dbx/plans/*.json` | แผนที่คนอนุญาต (ไม่ขึ้น Git) |

`db_runs/`, `.dbx/`, `shared/db.local.json` และ `registry/` อยู่ใน `.gitignore` เพราะอาจมีข้อมูลจริงหรือค่าเฉพาะเครื่อง
ถ้าต้องการเก็บหลักฐานใน PR ให้สรุปผลลงเอกสารของงานแทนการ commit ข้อมูลดิบ

## 5. สำหรับ AI

1. อ่าน `db-status` ก่อน และห้ามเปลี่ยน `db-policy` เองโดยที่ทีมไม่ได้สั่ง
2. ใช้ `--plan` เสมอ แล้วถามคนในแชทด้วยข้อความ ❓ ที่ระบบพิมพ์ (ตอบเป็นเลข)
3. คนตอบ 1 → `--execute <แผน> --approved "<ชื่อคน> <วันที่>"` · คนตอบ 2 → `--human <แผน>` แล้วบอกทีละไฟล์
4. คำสั่งที่ลบแล้วกู้คืนไม่ได้: ให้คนพิมพ์ชื่อตารางในแชท แล้วใส่ใน `--confirm` ตามที่คนพิมพ์
5. ห้ามขอหรือรับรหัสผ่านในแชท ห้ามอนุญาตแทนคน และห้ามแก้ไฟล์หลังได้รับอนุญาต
6. ผลจากฐานจริงไม่ใช่การผ่าน Gate และไม่ใช่การอนุมัติ deploy

## 6. ข้อจำกัด

- `CLAUDE.md` ของแต่ละงานที่ kit 0.1.0 สร้างเขียนว่า "Never connect to Oracle/GitHub" ซึ่งหมายถึง simulator runtime
  การต่อฐานผ่าน adapter อยู่ภายใต้ AGENTS.md / skill / เอกสารนี้; ข้อความนั้นจะแก้ได้เมื่อออก kit รุ่นใหม่

- adapter เป็นตัวรัน SQL ไม่ใช่ตัวเทียบผล Spark กับ Oracle; การเทียบผลจริง (G5) ยังต้องมีกระบวนการแยก
- การแยกคำสั่งรองรับ `;` และบล็อก PL/SQL ที่จบด้วย `/` เท่านั้น ไม่รองรับคำสั่ง SQL*Plus ทุกแบบ
- ระบบอ่านชื่อตารางจากคำสั่งลบได้เฉพาะรูปแบบมาตรฐาน; ถ้าอ่านไม่ออก (`?`) ระบบจะไม่รันและให้คนรันเอง
- ยังไม่ได้ port `fetch_profile` (ดึง all_tab_columns / constraint / NLS เป็น target snapshot) เพราะ snapshot ของ simulator
  เป็นข้อมูลสังเคราะห์ที่ล็อกด้วย hash; ถ้าต้องการให้เปิดเป็นงานแยกพร้อมรูปแบบ snapshot ใหม่
