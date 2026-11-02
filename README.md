# Migration Team 2 — ต้นแบบการทำงานร่วมกัน

ต้นแบบออฟไลน์สำหรับจำลองการย้าย **Blendata → Oracle SQL/DML → ODI delivery workflow**
แยกจาก `../migrate_team/` โดยไม่เปลี่ยนโค้ดหรือข้อมูลของ workspace เดิม

**สถานะ: simulation reference implementation รุ่น 0.1.0**

ตัวอย่างนี้ทดสอบกระบวนการทำงานของทีม การใช้ของกลาง การล็อกรุ่น การตรวจ input ที่เปลี่ยน
และการตรวจผลกับข้อมูลตัวอย่าง `simulate` ไม่ได้ต่อ Spark, Oracle, ODI หรือ GitHub
ส่วนการรัน SQL บนฐาน Oracle จริงทำผ่าน **Oracle adapter** (`tools/dbcore`) ที่ต้องเปิดใช้และอนุญาตทุกแผน —
ดู [คู่มือต่อฐาน Oracle](docs/DATABASE.md)
ไฟล์ `*.simulation.xml` / `*.simulation.zip` **ไม่ใช่ ODI Smart Export และนำเข้า ODI ไม่ได้**

## เริ่มลอง

ต้องใช้ Python 3.11 ขึ้นไป ไม่มี dependency เพิ่ม ไม่ต้องติดตั้ง Oracle Client หรือให้รหัสผ่าน

```powershell
Set-Location E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2
python tools/workspace.py demo
python tools/workspace.py status
python tools/workspace.py check
```

เปิด `STATUS.html` เพื่อดูภาพรวม หรืออ่าน `STATUS.md`
เมื่อส่งมอบโฟลเดอร์นี้ ได้รัน demo และสร้างผลลัพธ์ 2 งานไว้แล้ว
รัน `demo` ซ้ำได้ แต่จะไม่อนุมัติ input ของงานเดิมใหม่ให้โดยอัตโนมัติ

## Setup Workspace ด้วย PowerShell

ใช้ `setup_workspace.ps1` เพื่อเตรียม workspace โดยไม่สร้าง Demo/Project/Job:

```powershell
Set-Location E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2
.\setup_workspace.ps1
```

หาก Execution Policy ของเครื่องบล็อก ให้ใช้เฉพาะ process นี้:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_workspace.ps1
```

เมื่อรันปกติจะเข้าสู่ **wizard ภาษาไทย 8 ข้อ** อ้างรูปแบบคำถามจาก `Migrate_ODI_Team2/kit/setup_migrate.ps1` รุ่น 2.15.0:

| ข้อ | คำถาม | สิ่งที่ใช้จริง |
|---|---|---|
| 1 | ตั้ง workspace ที่ไหน | ใช้โฟลเดอร์เดิมหรือสร้าง scaffold ในโฟลเดอร์ว่างใหม่ |
| 2 | ชื่อ workspace / ทีม | บันทึก workspace_name ใน workspace.json |
| 3 | Python อัตโนมัติหรือระบุเอง | ตรวจ Python 3.11+ ก่อนสร้างไฟล์ |
| 4 | ใช้ target เดิม / ตัวอย่าง / custom | ตรวจหรือเลือก synthetic target snapshot |
| 5 | ผู้รีวิวจำลอง | เพิ่ม simulation_reviewers โดยรักษารายชื่อเดิมไว้ |
| 6 | สร้าง Git ในเครื่องหรือไม่ | เลือกได้; ไม่มี commit/remote/push และรักษา repo เดิม |
| 7 | ใครรัน SQL บนฐาน Oracle จริง (+ 7.1 SELECT ถามทุกครั้ง/ต่อเนื่อง, 7.2 แยก user อ่าน/เขียน) | `shared/team.json` → `db`; ค่าเริ่มต้นคนรันเอง ไม่ต่อฐาน |
| 8 | ค่าการเชื่อมต่อ Oracle (+ 8.1 ติดตั้ง python-oracledb / ทดสอบ) — ถามเมื่อข้อ 7 ให้ระบบรัน | `shared/db.local.json` ไม่มีรหัสผ่าน ไม่ขึ้น Git |

ทุกข้อมีคำอธิบาย ค่าแนะนำ Enter เพื่อใช้ค่าเริ่มต้น และ `?` สำหรับรายละเอียด
ท้าย wizard มีสรุป แล้วเลือก `1/y` เริ่ม Setup, `2/e` แก้คำตอบ หรือ `3/q` ยกเลิก
ก่อนยืนยันยังไม่มีการสร้างหรือแก้ไฟล์ workspace; q หรือ stdin จบก่อนยืนยันจะออกด้วย exit code 2
คำตอบที่ยืนยันแล้วเก็บใน `.cache/setup/confirmed-answers.json` ของ workspace ปลายทาง
คำตอบที่ยังไม่ยืนยันไม่ถูกบันทึกข้ามการรัน; e ใช้ค่าล่าสุดเป็น default ภายในรอบนั้น

### Workspace skill ที่ Setup ติดตั้งให้

Setup ติดตั้ง/ตรวจ `blendata-odi-team` อัตโนมัติหลัง init พร้อมแนวทางที่ตกลงกันเรื่อง
Setup, Project/Job, kit/target pins, simulated review, ผลรันซ้ำ และ import-lock rehearsal

```text
.agents/skills/blendata-odi-team/
├── SKILL.md
├── agents/openai.yaml
└── references/workspace-commands.md
AGENTS.md                         # จุดอ้างอิง skill ของ workspace
registry/workspace_skill.json    # checksum และข้อมูลการติดตั้ง
```

เปิด workspace root ใน Codex แล้วเรียกในแชท เช่น:

```text
ใช้ $blendata-odi-team ช่วย Setup Project TRAINING และเปิด Job สำหรับทดลอง workflow ลูกค้า
```

Codex ใช้ `.agents/skills` สำหรับ repo-local discovery ตาม
[OpenAI Docs](https://learn.chatgpt.com/docs/build-skills)
หาก skill ยังไม่ปรากฏหลังติดตั้ง ให้เปิด workspace ใหม่หรือ restart Codex
ต้นแบบนี้ไม่ติดตั้ง skill ลงโฟลเดอร์ส่วนตัวของผู้ใช้ และไม่เปลี่ยน config ส่วนกลาง

Skill เป็นคำแนะนำการทำงาน ไม่ใช่ตัวรัน SQL/ODI และไม่เปลี่ยน simulation ให้เป็น production
ต้นฉบับอยู่ใน `.agents/skills/blendata-odi-team` ของ source bundle; เมื่อสร้าง workspace ใหม่จะติดตั้งสำเนาให้
ไม่ใส่ skill เข้า runtime ZIP รุ่น 0.1.0 ที่ freeze ไว้แล้ว จึงไม่เปลี่ยน hash ของงานเดิม
Setup เพิ่ม managed block ใน AGENTS.md และรักษาข้อความอื่นไว้ หากไฟล์ skill ปลายทางหรือ block ที่เคยติดตั้ง
ถูกทีมแก้เองไม่ตรงต้นฉบับ ระบบจะหยุดให้ตรวจความต่าง แทนการเขียนทับ

สคริปต์ตรวจ Python 3.11+ แล้วรัน init → install workspace skill → freeze-kit → สร้างหรือยืนยัน target snapshot → check → report
รันซ้ำแล้วคงค่าทีม งานเดิม และ target ที่เลือกไว้ หากตรวจพบงาน STALE หรือไฟล์ถูกแก้จะหยุดพร้อม log
ไม่มีการอนุมัติหรือซ่อมหลักฐานให้อัตโนมัติ

สร้าง workspace ใหม่จาก scaffold ชุดนี้ในโฟลเดอร์ว่างได้ด้วย:

```powershell
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace
```

พารามิเตอร์ที่ส่งให้เป็นค่าเริ่มต้นใน wizard หากต้องการไม่ถามเลย ใช้ `-NonInteractive`:

```powershell
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace -NonInteractive

# ตั้งชื่อและเพิ่ม reviewer แบบอัตโนมัติ
.\setup_workspace.ps1 -NonInteractive -WorkspaceName "Migration Training" -SimulationReviewers DEMO_SA,QA_REVIEWER
```

โหมดไม่ถามจะคงพฤติกรรมเดิม: ไม่เปลี่ยนชื่อ/รายชื่อ reviewer เว้นแต่ส่งพารามิเตอร์นั้น
หากต้องการสร้าง Git เปล่าในเครื่องในโหมดนี้ ให้ระบุ `-InitializeGit` เพิ่มเอง

จะคัดลอก source/templates/samples/docs/tests และ CI template โดยไม่คัดลอก jobs, team settings, cache,
registry หรือ .git ของต้นทาง โฟลเดอร์ปลายทางที่ไม่ว่างและไม่ใช่ workspace จะถูกปฏิเสธ

ตัวเลือกเพิ่มเติม:

```powershell
# ดูแผนก่อน ไม่เขียนไฟล์
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace -WhatIf

# เลือก Python เอง
.\setup_workspace.ps1 -PythonExecutable C:\Python313\python.exe

# ระบุ synthetic target ชุดใหม่อย่างชัดเจน
.\setup_workspace.ps1 -TargetSource E:\path\to\synthetic_target
```

`-WhatIf` ไม่ถาม wizard และไม่เขียนไฟล์ รองรับทั้ง PowerShell 5.1 และ 7
ไฟล์ PS1 เก็บ UTF-8 with BOM เพื่อให้ข้อความภาษาไทยบน Windows PowerShell 5.1 อ่านได้ถูกต้อง
การเข้าฐาน Oracle ตั้งได้ในข้อ 7–8 หรือด้วย `-DbAccess`, `-DbSelectMode`, `-DbUsers`, `-DbEnv`, `-DbHost`, `-DbPort`,
`-DbService`, `-DbUserRo`, `-DbUserRw`, `-InstallOracleDriver`, `-TestDbConnection` (ไม่มีพารามิเตอร์รหัสผ่าน)
การทดสอบการเชื่อมต่อที่ล้มเหลวเป็นเพียงคำเตือนใน `last-result.json` → `db.warnings`
GitHub จริงและ Smart Import ยังแยกไว้สำหรับการเชื่อม production kit ในอนาคต

log และผลล่าสุดอยู่ใต้ `.cache/setup/` ของ workspace ที่ Setup
ขั้นต่อไปคือ `new-job --project ...` ตาม [คู่มือ Setup Project และ Job](docs/SETUP_PROJECT_JOB.md)

## สิ่งที่จำลองได้จริง

| ความสามารถ | วิธีพิสูจน์ |
|---|---|
| โค้ดกลางชุดเดียว | ไม่มี pipeline source ก๊อปลง jobs; launcher โหลด runtime จาก ZIP ที่งานล็อก |
| ล็อกรุ่น kit | `kit.lock.json` ระบุ version + SHA-256; เปลี่ยน source ไม่เปลี่ยน runtime ของงานเดิม |
| ล็อกข้อมูลอ้างอิง | ทั้งสองงานใช้ `shared/target/snapshots/<id>` ชุดเดียวและตรวจ checksum |
| แยกงาน/เจ้าของ/ช่วง ID | DEMO_ALICE / DEMO_BOB และเลขใบงานจำลอง 101 / 102 |
| บังคับรีวิวใหม่ | เปลี่ยน input/config/pin แล้ว fingerprint เปลี่ยน ผลเดิมเป็น STALE |
| SQL conversion แบบจำกัด | backtick → identifier, IFNULL → COALESCE, CAST AS STRING → VARCHAR2(100) |
| DML generation | สร้าง INSERT, MERGE หรือ TRUNCATE + INSERT ตามการเลือกที่ระบุไว้ใน task |
| ตรวจข้อมูลและรันซ้ำ | SQLite อ่านข้อมูลสังเคราะห์ + Python จำลอง load strategy เทียบ expected rows |
| ตรวจชุดส่งมอบ | XML จำลอง, manifest, checksums และ ZIP ที่สร้างอย่างคงที่จาก input เดิม |
| จอง import ร่วมกัน | exclusive file creation กันสองผู้ถือบน lock directory เดียว |
| ตรวจผลถูกแก้ย้อนหลัง | `check` ตรวจ hash ของ output ที่ใช้เป็นหลักฐาน |
| รัน SQL บน Oracle จริงแบบมีผู้อนุญาต | `run-sql` สร้างแผน + SHA-256 → คนอนุญาต → รัน · บันทึก `status/DB_RUN_LOG.md` (ไม่เปลี่ยน Gate) |

## งานตัวอย่าง

| Job | Owner สมมติ | Task | Strategy | ผลที่คาดเมื่อรันซ้ำ |
|---|---|---|---|---|
| `DEMO/customer_daily` | DEMO_ALICE | T001 ลูกค้า | upsert | อัปเดตแถวเดิมและเก็บลูกค้าเดิมที่ไม่อยู่ใน source |
| `DEMO/customer_daily` | DEMO_ALICE | T002 snapshot ลูกค้าที่ใช้งาน | overwrite | แทนทั้งตารางตามการเลือกจำลองชัดเจน ผลคงเดิม |
| `DEMO/order_daily` | DEMO_BOB | T003 คำสั่งซื้อยอดบวก | append | จำนวนแถวเพิ่มจาก 2 เป็น 4; ไม่ใช่ idempotent load |

Expected rows เขียนแยกไว้ใน `samples/target/fixtures/rows.json` ไม่ได้สร้าง expected จากผล query ที่กำลังตรวจ
การเทียบสนใจจำนวนแถวซ้ำด้วย แต่ไม่บังคับลำดับแถว

## โครงสร้าง

```text
migrate_team2/
├── .github/                   # CI template และ Code Owner; ยังไม่เปิดใช้งานบน GitHub
├── tools/workspace.py         # จุดเรียกคำสั่งเดียว
├── tools/dbcore/              # Oracle adapter (db-* / run-sql) นอก kit ที่ล็อกรุ่น
├── kit/
│   ├── src/migrate_kit/        # source กลาง
│   ├── ai/                    # กติกาสำหรับ AI
│   ├── knowledge/reference/   # ขอบเขตและข้อจำกัดของรุ่น
│   ├── templates/             # แม่แบบเอกสารที่เติมเป็นรายงาน
│   └── releases/              # manifest ของ release ที่ตรึง hash แล้ว
├── shared/
│   ├── team.json
│   ├── approvers.json         # มีเฉพาะ fictional simulation reviewer
│   ├── policies/
│   ├── knowledge/
│   └── target/snapshots/      # synthetic reference ที่สองงานใช้ร่วมกัน
├── projects/DEMO/
│   ├── _project/              # ความรู้ระดับ project
│   └── jobs/
│       ├── customer_daily/    # input / config / status / output / run_packs / .design
│       └── order_daily/
├── samples/                   # ต้นฉบับ fixture สำหรับเริ่มจำลอง
├── tests/                     # กรณีผ่านและกรณีที่ต้องบล็อก
├── docs/                      # คู่มือทีม สถาปัตยกรรม และทางต่อไปใช้จริง
├── .cache/kit/                # release ZIP ที่โหลดจริง ไม่ขึ้น Git
├── registry/                  # สถานะรวมและ local import lock ไม่ขึ้น Git
├── STATUS.md
└── STATUS.html
```

## คำสั่งหลัก

```powershell
# ดูภาพรวมและตรวจหลักฐาน
python tools/workspace.py status
python tools/workspace.py check

# รันงานเดิมด้วย kit และ target ที่ล็อกไว้
python tools/workspace.py simulate --job DEMO/customer_daily

# บันทึกการรีวิวจำลองหลังตรวจ input ปัจจุบัน
python tools/workspace.py approve --job DEMO/customer_daily --reviewer DEMO_SA --simulation

# ทดลองจอง import (ไม่มีการต่อ ODI)
python tools/workspace.py import-lock --job DEMO/customer_daily --holder DEMO_ALICE --simulation
python tools/workspace.py lock-status
python tools/workspace.py import-unlock --job DEMO/customer_daily --holder DEMO_ALICE --simulation

# เปิดงานเพิ่ม โดยใช้รูปแบบ workflow ตัวอย่าง
python tools/workspace.py new-job --project DEMO --job order_trial --issue 103 --workflow samples/workflows/order_daily.json --owner DEMO_CHARLIE
python tools/workspace.py approve --job DEMO/order_trial --reviewer DEMO_SA --simulation
python tools/workspace.py simulate --job DEMO/order_trial

# Oracle (ต้องเปิดกติกาก่อน · ทุกแผนต้องมีคนอนุญาต) — ดู docs/DATABASE.md
python tools/workspace.py db-status
python tools/workspace.py db-test
python tools/workspace.py run-sql --job DEMO/customer_daily output/sql/converted --compile --plan

# รันทดสอบใน workspace ชั่วคราวแยกจากงานตัวอย่าง
python -B -m unittest discover -s tests -v
```

## รุ่นเครื่องมือและ cache

`freeze-kit` สร้าง ZIP จาก runtime, AI policy, คู่มือกลาง และ templates พร้อม hash
จากนั้น `simulate` เปิด subprocess ที่ import package จาก ZIP ที่งานล็อกไว้
ไม่ใช้ runtime source ที่อาจกำลังแก้ระหว่างพัฒนา

```powershell
python tools/workspace.py freeze-kit
```

ถ้า source เปลี่ยนแต่ใช้ version เดิม คำสั่งนี้จะปฏิเสธการเขียนทับ release
เมื่อพัฒนารุ่นใหม่ ให้ปรับ version ทั้ง `kit/src/migrate_kit/__init__.py` และ `kit/pyproject.toml`
แล้วทดสอบ ออก release และเปิดงานใหม่ด้วยรุ่นใหม่ งานเดิมยังคงใช้รุ่นเดิม

release ZIP ตัวจริงเก็บถาวรที่ `kit/releases/<version>.zip` คู่กับ manifest `<version>.json` และขึ้น Git (ADR-007)
ส่วน `.cache/kit/` เป็นสำเนาในเครื่องที่ลบได้ ทุกคำสั่งของ launcher จะคืน cache จาก `kit/releases/` ให้เองเมื่อหาย
`freeze-kit` ของรุ่นที่ freeze แล้วจะตรวจ source ทีละไฟล์ด้วย SHA-256 (ไม่ขึ้นกับ zlib ของเครื่อง) แล้วใช้ ZIP ตัวเดิม
จึงใช้ได้ทั้ง Windows, Linux และ CI โดยไม่สร้าง ZIP ใหม่ ส่วนรุ่นใหม่จะ freeze แล้วคัดลอกเข้า `kit/releases/` ครั้งเดียว
ห้ามแก้หรือเขียนทับ `kit/releases/*.zip` — ถ้าไฟล์ไม่ตรง hash ระบบจะหยุดและให้คืนไฟล์เดิม

## kit 0.4.0 — Wiki และบทเรียนของทีม

```powershell
python tools/workspace.py wiki-step 03 --job <P>/<J>      # บทเรียนที่เกี่ยวกับขั้น (kit · ทีม · งานอื่น)
python tools/workspace.py wiki-search overwrite           # ค้นทุกชั้น
python tools/workspace.py kit-promote --job <P>/<J> --lesson L43   # แผน → คนอนุมัติ → --plan-id <id> --approved "<ชื่อ> <วันที่>"
```

ความรู้ 5 ชั้น: kit (`kit/knowledge`) · ทีม (`shared/knowledge` — ทุกงานเห็นทันที) · ระบบปลายทาง · project · งาน
บทเรียน generic ของงานเข้าชั้นทีมได้ด้วย `kit-promote` เมื่อผู้อนุมัติใน `shared/approvers.json` → `knowledge_approvers` อนุมัติ
ใช้ได้ทั้งงาน simulation และ delivery · `check` รวมการตรวจ Wiki · ดู `kit/knowledge/README.md` และ ADR-010

## kit 0.3.0 — งานจริง (delivery mode)

```powershell
# งานใหม่ (วาง export / all_tab_columns / Smart Export ใน input/ แล้วกรอก config.odi.* ก่อน /convert)
python tools/workspace.py new-job --mode delivery --project SS_ESIM --job esim_new --issue 203 --owner DEV_A
# ย้ายงานเดิมจาก Migrate_ODI_Team2 เข้ามา (scripts/.claude/knowledge ของงานถูกแทนด้วยชุดที่ล็อกจาก kit)
python tools/workspace.py import-job --from D:\Projects\Blendata_To_ODI\Migrate_ODI_Team2\projects\SS_ESIM\jobs\ss_esim_landing_to_discovery --project SS_ESIM --job ss_esim_landing_to_discovery --issue 2 --owner MANA
```

งาน delivery ได้ pipeline เต็มของ Migrate_ODI_Team2 2.15.0 (extract → convert → DML/DDL → native ODI Smart Export → Run Pack →
read results → Gate) เป็น `scripts/` ที่ล็อกจาก kit · รันในโฟลเดอร์งานตาม `CLAUDE.md` ของงาน · SQL บนฐานผ่าน `run-sql` เท่านั้น
`convert_sql.py` รันซ้ำไม่ทับ SQL ที่ review แล้ว (R-08) · ยืนยันความถูกต้องด้วย regression SS_ESIM (ผลตรงทุกไฟล์) · ดู ADR-009

## kit 0.2.0 — ความรู้และ AI context ติดมากับงาน

งานใหม่ (`new-job`) ได้ `.claude/` (31 commands, 10 agents, 8 rules, 2 skills, workflow) และ `knowledge/` (อ้างอิงกลาง 15 ไฟล์ +
บทเรียนจากงานจริง) จาก kit ที่ล็อกไว้ พร้อม `CLAUDE.md` ของงานที่บอกว่าเครื่องมือไหนมีแล้ว/ยังไม่มี
คำสั่งที่ต้องใช้ converter / ODI builder / Gate script ยังไม่พร้อมในรุ่นนี้และมีป้าย ⚠️ — ใช้ Migrate_ODI_Team2 สำหรับขั้นนั้นไปก่อน
ไฟล์ที่ติดตั้งจาก kit ห้ามแก้ในงาน (`check` ตรวจ) · งาน DEMO ยังใช้ 0.1.0 ตามที่ล็อกไว้ · ดู `kit/CHANGELOG.md` และ ADR-008

## Regression baseline จากงานจริง

`tools/regression.py` เก็บงานที่ผ่านหลักฐานบน DEV แล้วเป็น baseline (input · ผล converter · SQL ที่ review · DML/DDL/ODI ·
Run Pack · หลักฐาน · scripts ที่ใช้จริง) และ replay เพื่อพิสูจน์ว่า runtime ที่ port เข้า kit 0.2.0 ให้ผลเท่าเดิม
ชุดแรกคือ SS_ESIM — ดู `tests/regression/ss_esim/README.md` · `baseline.zip` มี metadata ลูกค้าจึงไม่ขึ้น Git

```powershell
python tools/regression.py verify --name ss_esim
python tools/regression.py replay --name ss_esim
```

## ขอบเขตที่ยังไม่ใช่ระบบจริง

- Oracle adapter รัน SQL ได้จริงเมื่อทีมเปิดใช้ แต่ไม่เทียบผล Spark กับ Oracle และไม่เปลี่ยน G4–G7
- JSON เป็น normalized synthetic workflow ไม่ใช่ตัวอ่าน Blendata export ครบทุกรูปแบบ
- ไม่ได้ใช้ converter หรือ native ODI XML builder ของ workspace เดิม
- `simulate` ไม่ได้ทดสอบ semantic equivalence ของ Spark กับ Oracle หรือ ODI Smart Import; Oracle compile ทำได้ผ่าน `run-sql --compile` แยกต่างหาก
- ไม่รองรับ partition overwrite, DAG scheduling, ODI variables และ task error-routing แบบเต็ม
- `SIMULATED_APPROVAL` เป็น persona สมมติ ไม่ใช่ SA ลงนาม
- G4–G7 เป็น `NOT_EXECUTED` เสมอ: real import / real comparison / cutover / go-live
- `branch` ใน job.json เป็นแผนชื่อ branch; Setup เลือก init Git เปล่าได้ แต่ยังไม่สร้าง branch/worktree ของงานหรือเชื่อม remote
- import lock ครอบคลุมเพียง processes ที่ใช้ lock directory เดียว ไม่ใช่ distributed lock ข้ามเครื่อง

อ่านต่อ: [Setup Workspace / Project / Job แบบละเอียด](docs/SETUP_PROJECT_JOB.md), [ต่อฐาน Oracle](docs/DATABASE.md),
[ลองทำงานเป็นทีม](docs/TEAM_WORKFLOW.md), [สถาปัตยกรรม](docs/ARCHITECTURE.md),
[นำไปต่อยอดกับ kit เดิม](docs/PRODUCTION_PATH.md)
