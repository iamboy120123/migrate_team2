# Setup Workspace, Project และ Job — migrate_team2 รุ่น 0.1.0

คู่มือนี้อ้างอิง CLI และ source ที่มีจริงใน migrate_team2 ไม่ใช่คำสั่งของ migrate_team รุ่นเดิม
ใช้สำหรับการจำลองออฟไลน์เท่านั้น ไม่มีการต่อ Oracle/Spark/ODI/GitHub
ชุดส่งมอบที่สร้างเป็น simulation bundle ไม่ใช่ native ODI Smart Export

## 1. แยกความหมายให้ชัด

| ระดับ | ความหมาย | ใครทำ | ทำเมื่อใด |
|---|---|---|---|
| Workspace | เครื่องมือ กติกาทีม และ target snapshot ร่วมกัน | ผู้ดูแล kit / Tech Lead | ตอนเตรียม workspace หรือเปลี่ยนรุ่น |
| Project | กลุ่มงานระบบเดียวกัน เช่น TRAINING | เจ้าของงานแรก | สร้างอัตโนมัติพร้อม Job แรก |
| Job | หนึ่ง workflow พร้อม input/config/output/status ของตัวเอง | เจ้าของงาน | ทุกครั้งที่เริ่ม workflow ใหม่ |

สำหรับ Setup Workspace ใช้ `E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2\setup_workspace.ps1`
สำหรับคำสั่งจัดการ Project/Job ใช้ `E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2\tools\workspace.py`
บน Windows ใช้ `tools\ws.cmd <command>` แทน `python tools/workspace.py <command>` ได้
รันจาก root ตามตัวอย่างเพื่อให้ relative workflow path ชัดเจน
ไม่ต้องรัน setup_migrate.ps1 จาก workspace เดิมหรือรันไฟล์ใน kit/src ทีละตัว

## 2. เตรียมเครื่องและเข้า workspace

```powershell
Set-Location E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2
python --version
python tools/workspace.py --help
```

ต้องเป็น Python 3.11 ขึ้นไป ต้นแบบใช้ standard library จึงไม่ต้อง pip install
คำสั่งด้านล่างสมมติว่าอยู่ใน root นี้ตลอด

## 3. Setup Workspace — ผู้ดูแลทำก่อนเปิด Job แรก

โฟลเดอร์ที่เตรียมให้มี workspace, release และ snapshot พร้อมแล้ว สามารถข้ามไปข้อ 4
หากต้องการ Setup/ตรวจความพร้อมด้วยคำสั่งเดียว ให้รัน:

```powershell
.\setup_workspace.ps1
```

หาก Execution Policy บล็อก:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_workspace.ps1
```

เมื่อรันปกติจะถาม 8 ข้อ: โฟลเดอร์, ชื่อ workspace/ทีม, Python, target, ผู้รีวิวจำลอง, Git ในเครื่อง,
กติกาการรัน SQL บน Oracle จริง (ข้อ 7) และค่าการเชื่อมต่อ Oracle (ข้อ 8 — ถามเมื่อข้อ 7 ให้ระบบรัน)
ค่าเริ่มต้นของข้อ 7 คือคนรันเอง ไม่ต่อฐาน รายละเอียดอยู่ใน [DATABASE.md](DATABASE.md)
มีคำอธิบายทุกข้อ, Enter ใช้ค่าแนะนำ, ? ดูรายละเอียด และ q ยกเลิก
ท้าย wizard มีสรุปให้เลือก 1/y เริ่ม, 2/e แก้คำตอบล่าสุด หรือ 3/q ยกเลิกก่อนเขียนไฟล์
คำตอบที่ยืนยันเก็บใน `.cache/setup/confirmed-answers.json`; การยกเลิกไม่บันทึกคำตอบข้ามรอบ

สคริปต์รองรับ PowerShell 5.1/7 ตรวจ Python 3.11+ ไม่ติดตั้งโปรแกรมเพิ่มและไม่สร้าง Job ให้
หลัง init จะติดตั้ง skill ระดับ workspace ที่ `.agents/skills/blendata-odi-team/SKILL.md`
พร้อมจุดอ้างอิงใน AGENTS.md และทะเบียน checksum ที่ registry/workspace_skill.json
นำแนวทาง Setup/Job/pins/review/validation/lock มาใช้ต่อโดยเรียก `$blendata-odi-team` ในแชท Codex
ไม่แก้ skill/config ส่วนตัวของผู้ใช้ และไม่เปลี่ยน runtime release ที่งานเดิมล็อกไว้
หากมี AGENTS.md อยู่แล้วจะรักษาข้อความนอก managed block; ถ้าทีมแก้สำเนา skill ที่ปลายทางไว้จะหยุดแทนเขียนทับ
รันซ้ำจะรักษาค่าทีม งาน และ target snapshot เดิม การพบงาน STALE จะทำให้ Setup หยุด
เพื่อให้เจ้าของงานแก้และรีวิวเอง ผลแต่ละรอบเก็บที่ `.cache/setup/setup-*.log`
และ `.cache/setup/last-result.json`

เพื่อสร้าง workspace ใหม่จาก scaffold ในโฟลเดอร์ว่าง:

```powershell
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace
```

ใช้ `-WhatIf` เพื่อดูแผนโดยไม่เขียนไฟล์ และ `-PythonExecutable C:\Python313\python.exe`
หากต้องการเลือก interpreter เอง โฟลเดอร์ใหม่ต้องอยู่นอก source tree เช่นเป็นโฟลเดอร์ข้างกัน
จะคัดลอกเฉพาะ source/templates/samples/docs/tests/policies และไม่เอา jobs/team settings/.git เดิมไปด้วย
หากปลายทางมีข้อมูลอื่นและยังไม่ใช่ workspace สคริปต์จะหยุดแทนการเขียนทับ

หากรันใน script/CI และไม่ต้องการถามตอบ ให้เพิ่ม `-NonInteractive`:

```powershell
.\setup_workspace.ps1 -NonInteractive
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace -NonInteractive
```

เลือกเพิ่มชื่อ workspace และผู้รีวิวจำลองด้วย `-WorkspaceName` / `-SimulationReviewers`
หรือ `-InitializeGit` เพื่อสร้าง local repo ถ้ายังไม่มี ไม่ commit/push และไม่ตั้ง remote
โหมดอัตโนมัติที่ไม่ส่งตัวเลือกเหล่านี้จะคง settings เดิมไว้

หากต้องการรันเองทีละขั้นแทนสคริปต์:

```powershell
python tools/workspace.py init
python tools/workspace.py freeze-kit
python tools/workspace.py snapshot
python tools/workspace.py check
```

สคริปต์ยังรัน report ตอนท้ายให้ และจะ verify/preserve current target เมื่อมีแล้ว
ต่างจากการรัน snapshot เองที่เลือก samples/target กลับมาเป็นค่าเริ่มต้น
หากเลือกทำทุกขั้นเองแทน Setup ให้ติดตั้ง skill หลัง init ด้วย `python tools/install_workspace_skill.py --workspace .`

| คำสั่ง | สิ่งที่ทำ / ผลที่ต้องตรวจ |
|---|---|
| init | สร้างโฟลเดอร์กลาง และค่าเริ่มต้น workspace.json, shared/team.json, shared/approvers.json เมื่อยังไม่มี; ไม่ถาม wizard และไม่เขียนทับค่าที่มีแล้ว |
| freeze-kit | แพ็ก source + AI/knowledge/templates เป็น release ZIP; เก็บ version/hash ใน kit/releases/0.1.0.json และ ZIP ใน .cache/kit/0.1.0 |
| snapshot | อ่าน samples/target สร้าง snapshot ตาม content hash และเขียน shared/target/current.json |
| check | ตรวจงานที่มีอยู่; ถ้ายังไม่มีงานการผ่านหมายถึงยังไม่พบปัญหาในงาน ไม่ใช่ผลทดสอบ Oracle/ODI |

`freeze-kit` เป็นงานผู้ดูแลรุ่น ไม่จำเป็นต้องทำก่อนเปิดทุก Job
ถ้าแจ้ง version เดิมแต่ source ต่าง ห้ามแก้ manifest/hash ให้ผ่าน ให้คืน source เดิมหรือออก version ใหม่
ถ้า cache หาย source/resources ที่ตรง release เดิมเท่านั้นจึงสร้าง ZIP เดิมคืนได้

ข้อมูลส่วนกลางที่ควรรู้:

| ไฟล์/โฟลเดอร์ใต้ workspace root | ใช้ทำอะไร |
|---|---|
| shared/team.json | github_mode=manual, db_mode=human, simulation_only=true และสูตร ID |
| shared/approvers.json | simulation_reviewers มี DEMO_SA; ไม่มีผู้อนุมัติ production ในต้นแบบ |
| shared/policies/TEAM.md | กติกาทีม |
| shared/target/current.json | snapshot เริ่มต้นสำหรับงานใหม่ |
| shared/target/snapshots/<id>/columns/all_tab_columns.csv | คอลัมน์เป้าหมายสังเคราะห์ |
| shared/target/snapshots/<id>/fixtures/rows.json | Source rows และ expected results แยกจาก SQL ที่ทดสอบ |
| kit/releases/0.1.0.json | หลักฐาน release และ checksum |

หากต้องการใช้ target ตัวอย่างชุดอื่น ให้เตรียมโครงเหมือน samples/target แล้วใช้:

```powershell
python tools/workspace.py snapshot --source "E:\path\to\synthetic_target"
```

snapshot เปลี่ยนค่าเริ่มต้นเฉพาะงานใหม่ งานเดิมไม่เปลี่ยน target ที่ล็อกไว้
ต้นแบบยังไม่มีคำสั่ง repin/new-round สำหรับงานเดิม
สำหรับการทดลองตามคู่มือนี้ให้ใช้ snapshot จาก samples/target เดิม

## 4. Setup Project และ Job แรก

ไม่มีคำสั่ง new-project แยก Project จะถูกสร้างพร้อมงานแรก
ตัวอย่างใช้ Project `TRAINING`, Job `customer_trial`, Owner `DEV_A`, Issue จำลอง `201`
ขณะเขียนคู่มือมีเลข 101 และ 102 อยู่แล้ว; ก่อนใช้ให้ตรวจว่า 201 ยังไม่มีงานอื่นจอง

ชื่อ Project, Job และ Owner ต้องเริ่มด้วยตัวอักษร ใช้ A–Z/a–z/0–9/_ และยาวไม่เกิน 50 ตัว
ชื่อ Project รักษาตัวพิมพ์ตามที่ระบุ จึงควรตกลงชื่อกับทีมให้ตรงกัน

```powershell
python tools/workspace.py new-job --project TRAINING --job customer_trial --issue 201 --workflow samples/workflows/customer_daily.json --owner DEV_A
```

| Argument | ความหมาย |
|---|---|
| --project TRAINING | กลุ่มงานที่จะอยู่ใต้ projects/TRAINING |
| --job customer_trial | ชื่อโฟลเดอร์งานใหม่ ห้ามใช้โฟลเดอร์งานที่มีอยู่แล้ว |
| --issue 201 | เลขจำลองที่ไม่ซ้ำทั้ง workspace; ไม่เปิดหรือยืนยัน GitHub Issue จริง |
| --workflow ... | ไฟล์ JSON ต้นทางที่ระบบก๊อปลง input ของงาน |
| --owner DEV_A | ชื่อเจ้าของจำลองที่แสดงในทะเบียน |

ผลที่สร้าง:

```text
E:\AI_Blendata_to_ODI\Migrate_Team\migrate_team2\projects\TRAINING\
├── _project/
│   ├── DECISIONS.md
│   ├── glossary.md
│   └── lessons-learned.md
└── jobs/customer_trial/
    ├── job.json
    ├── kit.lock.json
    ├── CLAUDE.md                      # kit 0.2.0: กติกางาน + เครื่องมือที่มี/ยังไม่มี (แก้เพิ่มบันทึกงานได้)
    ├── .claude/                       # commands / agents / rules / skills / workflows จาก kit (ล็อก)
    ├── config/config.json
    ├── input/blendata/export_workflow.json
    ├── input/run_results/
    ├── status/
    ├── output/
    ├── run_packs/
    ├── .design/
    ├── knowledge/                     # README, WORKFLOW, lessons-learned + reference/** (ล็อก)
    └── ROUNDS.md
```

สูตร ID ปัจจุบันคือ 90000 + issue × 1000; issue 201 จึงได้ id_base=291000
ชื่อ branch ที่บันทึกคือ job/TRAINING/customer_trial/R01 แต่ยังไม่สร้าง Git branch/worktree จริง

## 5. ตรวจไฟล์ก่อนเริ่มรัน

ตรวจไฟล์ใต้ `projects/TRAINING/jobs/customer_trial/`:

1. job.json — Project/Job/Owner/Issue และ id_base ถูกต้อง
2. kit.lock.json — kit_version, kit_sha256, target_snapshot, target_sha256 ถูกบันทึกแล้ว
3. input/blendata/export_workflow.json — มี workflow และ task ที่ต้องการทดลอง
4. config/config.json — mode=simulation, db_mode=human และชื่อ package เหมาะสม
5. status/INTAKE.md และ OPEN_DECISIONS.md — อ่านขอบเขตและการเลือก load strategy

สำหรับ job นี้ให้คง Task T001/T002, target_columns และ business rule ตาม sample ก่อน
เพราะ target snapshot เดิมมี expected rows สำหรับ task เหล่านี้
เปลี่ยน workflow เป็นงานใหม่คนละ semantics ต้องเตรียม schema/fixture/expected ของงานนั้นก่อน
ไฟล์ JSON จาก Blendata จริงทุกรูปแบบยังใช้กับ simulator โดยตรงไม่ได้

`new-job` ตรวจเบื้องต้นว่ามี tasks แต่ไม่ได้ยืนยันว่า schema/SQL/expected ถูกครบทั้งหมด
การตรวจละเอียดเกิดตอน simulate และอาจล้มเมื่อ input ไม่อยู่ในรูปแบบที่รองรับ

## 6. บันทึกรีวิวจำลอง แล้วรัน Job

หลังตรวจ input/config และ load strategy:

```powershell
python tools/workspace.py approve --job TRAINING/customer_trial --reviewer DEMO_SA --simulation
python tools/workspace.py simulate --job TRAINING/customer_trial
python tools/workspace.py check
python tools/workspace.py status
```

คาดหวัง SIMULATED_APPROVAL → SIMULATION_PASSED → Workspace integrity: PASS (0 findings)
ถ้า workspace มีงานอื่นเสีย check/status จะรายงานงานอื่นด้วย
DEMO_SA เป็น fictional reviewer ไม่ใช่การพิสูจน์ตัวตนหรือการอนุมัติของ SA จริง

simulate ทำงานต่อเนื่องให้:

1. ตรวจ hash ของ kit release และ target snapshot
2. ตรวจ input/config fingerprint เทียบ simulated review
3. แยก raw SQL และแปลงเฉพาะ SQL subset ที่รองรับ
4. สร้าง illustrative Oracle DML ตาม strategy ที่ระบุ
5. ใช้ SQLite + Python load model เทียบ curated fixture รอบแรกและรอบสอง
6. สร้าง simulation XML/ZIP และ manifest ของไฟล์ที่ใช้จริง
7. บันทึก Gate/status/output hashes และอัปเดตรายงานรวม

ผลลัพธ์อยู่ในงานเดียวกัน:

| Path ใต้ job | เนื้อหา |
|---|---|
| output/sql/raw | SQL ก่อนแปลง |
| output/sql/converted | SQL หลังแปลง |
| output/dml | INSERT / MERGE / explicit overwrite ตาม task |
| output/validation/REPORT.md | สรุปผลเทียบ fixture |
| output/validation/fixture_comparison.json | แถวที่อ่าน ผลรอบแรก ผลรอบสอง และ PASS/FAIL |
| output/odi_export | simulation XML/ZIP + build-manifest.json; นำเข้า ODI ไม่ได้ |
| status/simulation.json | fingerprint, state, gates, error และ output hashes |
| status/GATES.md | ผลตรวจ offline; G4–G7 ยังคง NOT_EXECUTED |
| run_packs/rp01_validation | SQL สำหรับอธิบายการตรวจ ไม่ได้รันฐานจริง |
| .design/03_package_flow.md | ลำดับ task จำลอง |

ภาพรวมทั้งทีมอยู่ที่ STATUS.md / STATUS.html ของ workspace root

## 7. เพิ่ม Job ที่สองใน Project เดิม

```powershell
python tools/workspace.py new-job --project TRAINING --job order_trial --issue 202 --workflow samples/workflows/order_daily.json --owner DEV_B
python tools/workspace.py approve --job TRAINING/order_trial --reviewer DEMO_SA --simulation
python tools/workspace.py simulate --job TRAINING/order_trial
python tools/workspace.py status
```

จะใช้ _project เดิม และมี input/config/status/output แยกใต้ jobs/order_trial
ไม่ได้ก๊อป pipeline source ทั้งชุดลง job และ kit.lock จะระบุ reference ที่ใช้ร่วมกัน

## 8. เมื่อกลับมาทำงานเดิม

```powershell
python tools/workspace.py status
python tools/workspace.py check
```

ไม่ต้อง init, freeze-kit, snapshot, new-job หรือ demo ใหม่ทุกครั้ง
เมื่อแก้ input/config/pin ให้ตรวจการเปลี่ยนแปลง บันทึก simulated review ใหม่ แล้ว simulate
อย่าแก้ output ที่ generate เพื่อให้ผลผ่าน เพราะ check ตรวจ hash ของหลักฐาน
ให้แก้ต้นทางแล้วสร้างผลลัพธ์ใหม่

## 9. ทดลองจอง import หลัง simulation ผ่าน

```powershell
python tools/workspace.py import-lock --job TRAINING/customer_trial --holder DEV_A --simulation
python tools/workspace.py lock-status
python tools/workspace.py import-unlock --job TRAINING/customer_trial --holder DEV_A --simulation
```

นี่เป็นการซ้อม local lock เท่านั้น ไม่มีคำสั่ง import/ต่อ ODI ซ่อนอยู่
ผู้ปลดต้องใช้ job และ holder เดิม และต้องปลดหลังทดลองเสร็จ
การประสานงานหลายเครื่องต้องใช้ lock service กลางก่อนใช้งานจริง

## 9.1 รัน SQL บน Oracle จริง (เมื่อทีมเปิดใช้)

```powershell
python tools/workspace.py db-status
python tools/workspace.py db-test
python tools/workspace.py run-sql --job TRAINING/customer_trial output/sql/converted --compile --plan
python tools/workspace.py run-sql --job TRAINING/customer_trial --execute <แผน> --approved "<ชื่อ> <วันที่>"
```

ผลอยู่ที่ `db_runs/` และ `status/DB_RUN_LOG.md` ของงาน ไม่ทำให้งานเป็น STALE และไม่เปลี่ยน G4–G7
คำสั่งที่เขียนต้องได้รับอนุญาตเสมอ และคำสั่งที่ลบแล้วกู้คืนไม่ได้ต้องพิมพ์ชื่อตารางยืนยัน ดู [DATABASE.md](DATABASE.md)

## 9.2 งานจริง (delivery mode, kit 0.3.0+)

| ทางเข้า | คำสั่ง |
|---|---|
| งานใหม่ | `new-job --mode delivery --project P --job J --issue N --owner O [--workflow <export.json>]` |
| ย้ายงานเดิม | `import-job --from <โฟลเดอร์งานของ Migrate_ODI_Team2> --project P --job J --issue N --owner O` |

งานใหม่: วาง `input/blendata/export_workflow.json`, `input/oracle_ddl/*.csv` (all_tab_columns), `input/odi_reference/*.xml`
(Smart Export ปลายทาง) แล้วกรอก `config/config.json` → `odi.logical_schema / context_code / work_user` (ดูค่าได้จาก
`python scripts/pipeline/read_smart_export.py --root . --json`) จากนั้นทำตาม `CLAUDE.md` หัวข้อ 2 (`/intake` → `/convert` → …)
import-job คัดลอก input / config / output / status / run_packs / .design / บันทึกงาน และเก็บที่มาใน `status/IMPORTED_FROM.json`
`CLAUDE.md` เดิมของงานถูกเก็บเป็น `CLAUDE.imported.md` · `scripts/`, `.claude/`, `knowledge/reference/` มาจาก kit (ล็อก)
งาน delivery ไม่ใช้ `approve --simulation` / `simulate` / import-lock rehearsal — Gate อยู่ที่ `status/GATES.md`

## 10. อาการที่พบบ่อย

| อาการ | วิธีตรวจ |
|---|---|
| File not found / release JSON หาย | ตรวจว่าอยู่ root ถูกแห่ง และทำ init → freeze-kit → snapshot แล้ว |
| Job already exists | กลับทำงานเดิมด้วย --job PROJECT/job หรือเลือกชื่อใหม่; ไม่เปิดทับ |
| Issue/id range already reserved | ใช้เลขจำลองใหม่ที่ไม่ซ้ำทั้ง workspace |
| Invalid name | ใช้ชื่ออังกฤษ/ตัวเลข/_ เริ่มด้วยตัวอักษร |
| Missing or stale simulated review | ตรวจสิ่งที่เปลี่ยน แล้ว approve --simulation ใหม่ก่อน simulate |
| Snapshot modified / kit hash mismatch | คืน reference/release ที่ถูกต้อง ไม่แก้ hash ให้ตรงไฟล์ที่เสีย |
| Fixture comparison mismatch | ผลต่างจาก expected; approval ใหม่อย่างเดียวไม่แก้ business/data mismatch |
| Target columns differ / unsupported function | Input นอก schema หรือ dialect subset ที่ simulator รองรับ |
| Simulation import lock occupied | lock-status แล้วให้ผู้ถือเดิมปลดด้วย job/holder เดิม |
| ทีมตั้งให้คนรันทั้งหมด | db-policy ยังเป็น human — ใช้ --human <แผน> หรือให้ทีมตกลงเปลี่ยนเป็น ai |
| ไม่มีรหัสผ่าน (ORA_*_PASSWORD) | setx ตัวแปรแล้วเปิด Terminal ใหม่ หรือรันใน Terminal แล้วพิมพ์รหัส (ไม่ใส่ในแชท) |
| ถูกแก้หลังสร้างแผน | ไฟล์ SQL เปลี่ยนหลังคนอนุญาต สร้างแผนใหม่แล้วขออนุญาตใหม่ |
| ต่อฐานไม่ได้ | ตรวจ host/port/service/user ด้วย db-status และ log ใน registry/db_queries.log |

## 11. ทางลัดเพื่อทดลองทั้งหมดจาก source

```powershell
python tools/workspace.py demo
```

demo รวม init + freeze-kit + snapshot + สร้างงาน DEMO ที่ยังไม่มี + simulated review สำหรับงานใหม่ + simulate
ไม่ใช่ wizard ตั้ง Project/Job ตามชื่อที่ผู้ใช้เลือก และไม่อนุมัติ input ของงานเดิมใหม่ให้อัตโนมัติ
สำหรับการฝึก setup ด้วยตนเองให้ใช้ลำดับข้อ 3–7

การทำตามตัวอย่างในคู่มือนี้เป็นสิ่งที่ผู้ใช้เลือกทำต่อ คู่มือไม่ได้สร้าง TRAINING/customer_trial
หรือ TRAINING/order_trial ให้อัตโนมัติขณะบันทึกเอกสาร
