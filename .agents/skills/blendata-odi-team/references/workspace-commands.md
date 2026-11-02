# Workspace commands

รันจาก workspace root ที่ตรวจพบจริง ไม่ใช้ path ของเครื่องผู้สร้างเป็นค่าตายตัว
ดู `docs/SETUP_PROJECT_JOB.md` เมื่อจำเป็นต้องอ่าน schema/ไฟล์ผลลัพธ์ละเอียด

## Setup

```powershell
# ผู้ใช้โต้ตอบกับ wizard
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_workspace.ps1

# Automation ใช้ค่าเดิมโดยไม่ถาม
.\setup_workspace.ps1 -NonInteractive

# สร้าง scaffold ใหม่ในโฟลเดอร์ว่างข้าง source
.\setup_workspace.ps1 -WorkspaceDir <ABSOLUTE_EMPTY_DESTINATION> -NonInteractive

# ดูแผน ไม่ติดตั้ง skill หรือเขียนไฟล์
.\setup_workspace.ps1 -WhatIf
```

Setup: preflight → bootstrap เมื่อจำเป็น → init → install workspace skill → confirmed settings เมื่อระบุ
→ freeze-kit → snapshot/verify-target → check → report → optional local Git
ค่า reviewer เพิ่มเข้ารายชื่อเดิม ไม่เปลี่ยน production approvers
Log และผลล่าสุดอยู่ `.cache/setup/`; `confirmed-answers.json` มีเฉพาะคำตอบ wizard ที่ยืนยันแล้ว

โหมด Git ในเครื่องไม่ commit/push/ตั้ง remote การสร้าง Git ต้องมาจากตัวเลือกผู้ใช้
ไฟล์อ้างอิง `Migrate_ODI_Team2/kit/setup_migrate.ps1` (นอก workspace นี้) ใช้อ่านรูปแบบ ไม่จำเป็นต่อการรัน wizard และไม่ถูกเรียกอัตโนมัติ

## New Job

ตรวจเลขและชื่อใน `projects/*/jobs/*/job.json` แล้วแทน placeholder ก่อนรัน:

```powershell
python tools/workspace.py new-job --project TRAINING --job customer_trial --issue <UNUSED_ISSUE> --workflow samples/workflows/customer_daily.json --owner DEV_A
```

คำสั่งสร้าง Project แรกพร้อม `_project/DECISIONS.md`, glossary และ lessons
Job มี `job.json`, `kit.lock.json`, config, input, status, output, run_packs, .design และ CLAUDE.md
ตรวจ input ที่ถูกก๊อปลง `projects/TRAINING/jobs/customer_trial/input/blendata/export_workflow.json`

## Simulated review and run

ใช้ reviewer ที่มีจริงใน `shared/approvers.json` และเมื่อผู้ใช้ต้องการการรีวิวจำลอง:

```powershell
python tools/workspace.py approve --job TRAINING/customer_trial --reviewer DEMO_SA --simulation
python tools/workspace.py simulate --job TRAINING/customer_trial
python tools/workspace.py check
python tools/workspace.py status
```

ตรวจ `output/sql/converted/`, `output/dml/`, `output/validation/REPORT.md`, fixture_comparison.json,
`output/odi_export/build-manifest.json` และ `status/simulation.json`
review ใหม่แก้ปัญหา fingerprint หมดอายุ แต่ไม่แก้ fixture mismatch หรือ SQL ที่ไม่รองรับ

## Import slot rehearsal

```powershell
python tools/workspace.py import-lock --job TRAINING/customer_trial --holder DEV_A --simulation
python tools/workspace.py lock-status
python tools/workspace.py import-unlock --job TRAINING/customer_trial --holder DEV_A --simulation
```

ก่อนจองต้องมี simulation ปัจจุบันผ่านแล้ว ผู้ถือคนอื่นจะได้ occupied
ใช้ holder/Job เดิมปลดเมื่อซ้อมเสร็จ ประวัติบอก actual_odi_import=false
อย่าปลดล็อกของคนอื่นหรือแก้ไฟล์ lock เพื่อทำให้ผ่านโดยไม่มีขอบเขตการแก้ปัญหาที่ผู้ใช้ระบุ

## Diagnose by evidence

| อาการ | ตรวจอะไร / ทำต่ออย่างไร |
|---|---|
| status ยังผ่านหลังผู้ใช้บอกว่าแก้ input | ตรวจ path จริง การ Save และ current/result/review fingerprints |
| STALE_REVIEW_REQUIRED | ตรวจสิ่งที่เปลี่ยน; simulated review ใหม่เฉพาะเมื่อผู้ใช้ต้องการ แล้วรันใหม่ |
| BLOCKED_REVIEW_REQUIRED | ดู approvals.json, current fingerprint และรายชื่อ reviewer |
| Kit hash mismatch | ตรวจ release ZIP และ manifest คืนไฟล์ที่ถูกต้อง; ไม่แก้ checksum หลบการตรวจ |
| Cache release หาย / clone ใหม่ / CI | launcher คืนจาก `kit/releases/<v>.zip` เอง; ถ้า store ไม่ตรง hash ให้คืนไฟล์เดิมจาก Git ห้ามสร้างทับ |
| Snapshot modified | คืน snapshot ที่ถูกต้อง หรือเตรียม snapshot ใหม่สำหรับงานใหม่ |
| Fixture comparison mismatch | ตรวจ SQL, strategy, source rows และ expected results แยกกัน |
| Zero fixture rows | ตรวจ filter/source; ไม่ถือว่าไม่มี error แล้วผ่าน |
| Output ถูกแก้ | ตรวจต้นทางและ regenerate; ไม่แก้หลักฐานย้อนหลัง |
| Setup หยุด | อ่าน stage/error จาก .cache/setup/last-result.json และ log; ไม่ใช้ approve เป็นวิธีซ่อม Setup ทั่วไป |

## Delivery job (kit 0.3.0+)

```powershell
python tools/workspace.py new-job --mode delivery --project <P> --job <J> --issue <UNUSED_ISSUE> --owner <O> [--workflow <export.json>]
python tools/workspace.py import-job --from "<Migrate_ODI_Team2 job folder>" --project <P> --job <J> --issue <N> --owner <O>
# ในโฟลเดอร์งาน
python scripts/pipeline/extract_workflow.py ; python scripts/pipeline/convert_sql.py ; python scripts/pipeline/gen_dml.py
python scripts/pipeline/build_odi_export.py ; python scripts/pipeline/validate_odi_xml.py
python scripts/runpack/gen_run_pack.py --pack rp01 ; python scripts/runpack/read_run_results.py --pack run_packs/<pack>
python scripts/checks/check_gate.py G3
# ผู้ดูแล kit: พิสูจน์ runtime ก่อนออกรุ่น
python tools/regression.py replay --name ss_esim --scripts kit/delivery/scripts
```

| อาการ | ตรวจอะไร / ทำต่ออย่างไร |
|---|---|
| Kit-installed file modified: scripts/… | คืนไฟล์จาก kit; แก้บั๊กที่ `kit/delivery/scripts` + ออกรุ่นใหม่ |
| [KEPT] ตอน convert | SQL ถูก review แล้ว — เทียบ `converted_machine/` และยกการแก้เอง |
| simulate/approve ปฏิเสธ | งาน delivery ใช้ GATES.md |

## Wiki (kit 0.4.0)

```powershell
python tools/workspace.py wiki-step 03 --job <P>/<J>
python tools/workspace.py wiki-search <term> [--layer kit|team|target|project|job]
python tools/workspace.py wiki-check
python tools/workspace.py kit-promote --job <P>/<J> --lesson L43            # plan + plan id (exit 3)
python tools/workspace.py kit-promote --job <P>/<J> --lesson L43 --plan-id <id> --approved "<name> <YYYY-MM-DD>"
```

| อาการ | ตรวจอะไร / ทำต่ออย่างไร |
|---|---|
| ไม่ได้ระบุว่าใช้ได้ทุกงาน | บทเรียนเฉพาะงานไม่ส่งเข้าทีม · ถ้าใช้ได้ทุกงานจริงให้แก้ช่องวิธีทำเป็น generic แล้วสร้างแผนใหม่ |
| ไม่อยู่ใน shared/approvers.json | Tech Lead เพิ่มชื่อใน `knowledge_approvers` |
| plan_id ไม่ตรง | เนื้อหาเปลี่ยนหลังแสดงแผน — แสดงแผนใหม่ให้คนอนุมัติ |
| wiki: … หายไป | LT# ที่ promote แล้วถูกลบ — คืนแถวจาก ledger / backup |

## Oracle adapter

```powershell
python tools/workspace.py db-status
python tools/workspace.py db-policy --access ai --select-mode ask --users split   # เฉพาะเมื่อทีมตกลง
python tools/workspace.py db-connect --env DEV --host <HOST> --service <SERVICE> --user-ro <RO> --user-rw <RW> --non-interactive
python tools/workspace.py db-driver --install
python tools/workspace.py db-test --plan
python tools/workspace.py run-sql --job TRAINING/customer_trial rp01 --plan
python tools/workspace.py run-sql --job TRAINING/customer_trial --execute <PLAN> --approved "<NAME> <DATE>" [--confirm T1,T2]
python tools/workspace.py run-sql --job TRAINING/customer_trial output/sql/converted --compile --plan
python tools/workspace.py run-sql --job TRAINING/customer_trial output/dml --explain --plan
python tools/workspace.py run-sql --job TRAINING/customer_trial --human <PLAN>
python tools/workspace.py run-sql --job TRAINING/customer_trial --record-human <PLAN> --result "<ผลที่คนบอก>"
```

Setup ใส่ค่าเดียวกันได้ด้วย `-DbAccess -DbSelectMode -DbUsers -DbEnv -DbHost -DbPort -DbService -DbUserRo -DbUserRw
-InstallOracleDriver -TestDbConnection`; ไม่มีพารามิเตอร์รหัสผ่าน และ db-test ล้มเหลวเป็น WARN ไม่ใช่ Setup ล้มเหลว

| อาการ | ตรวจอะไร / ทำต่ออย่างไร |
|---|---|
| ทีมตั้งให้คนรันทั้งหมด | ใช้ `--human <PLAN>`; เปลี่ยน policy เฉพาะเมื่อผู้ใช้/ทีมสั่ง |
| exit 3 | แสดงคำถาม ❓ ให้คนตอบเป็นเลขก่อน ห้าม execute เอง |
| ไม่มีรหัสผ่าน | ให้คน setx ORA_*_PASSWORD หรือรันใน Terminal เอง ห้ามรับรหัสในแชท |
| ถูกแก้หลังสร้างแผน | สร้างแผนใหม่และขออนุญาตใหม่ ไม่แก้ไฟล์ในแผน |
| ต้องยืนยันชื่อตาราง | ให้คนพิมพ์ชื่อตารางในแชทแล้วใส่ `--confirm` ตามที่คนพิมพ์ |
| ต่อฐานไม่ได้ | `db-status`, `registry/db_queries.log`; ตรวจ host/port/service/user กับ DBA |
| 0 แถว | ไม่นับว่าผ่าน ตรวจเงื่อนไข/ข้อมูล |

## Development checks

เปลี่ยน runtime หรือ Setup ให้รันทดสอบตามส่วนที่แก้:

```powershell
python -B -m unittest discover -s tests -v
```

เมื่อเปลี่ยนวิธีสร้าง release ให้ตรวจว่างานที่ pin รุ่นเดิมยังรันจาก archive เดิม
งาน production ต้องแยกการทดสอบ Oracle/Spark/ODI ออกจาก fixture checks ของต้นแบบนี้
