# ทดลองทำงานเป็นทีม

ทุกคำสั่งรันจาก root ของ migrate_team2 ใช้ Python 3.11+ และไม่ต่อระบบภายนอก

## รอบที่ 1 — ของกลางชุดเดียว งานแยกกัน

1. รัน `python tools/workspace.py demo`
2. เปิด `projects/DEMO/jobs/customer_daily/kit.lock.json` และไฟล์เดียวกันใน `order_daily`
3. จะเห็นรุ่น kit, kit hash, target snapshot และ target hash ตรงกัน
4. เปิด `output/sql/converted/` และ `output/dml/` ของแต่ละงาน ผลลัพธ์แยกโฟลเดอร์กัน
5. เปิด `output/validation/REPORT.md` และ JSON ในงานนั้นเพื่อตรวจผลรอบแรกและรอบสอง
6. `python tools/workspace.py check` ต้องรายงาน PASS

ผู้พัฒนา DEMO_ALICE/DEMO_BOB และผู้รีวิว DEMO_SA เป็นชื่อสมมติทั้งหมด
เลขใบงาน 101/102 จองเฉพาะใน simulator และยังไม่ยืนยันกับ GitHub จริง

## รอบที่ 2 — ข้อมูลเปลี่ยนต้องรีวิวใหม่

1. เปิด `projects/DEMO/jobs/customer_daily/input/blendata/export_workflow.json`
2. เพิ่ม space หนึ่งตัวท้ายข้อความ SQL ของ T001 ภายใน string แล้ว save (JSON ยังต้องถูกต้อง)
3. รัน `python tools/workspace.py status` จะเห็น STALE_REVIEW_REQUIRED
4. รัน `python tools/workspace.py simulate --job DEMO/customer_daily` ต้องถูกบล็อก
5. ตรวจความเปลี่ยนแปลง แล้วบันทึก fictional review:

```powershell
python tools/workspace.py approve --job DEMO/customer_daily --reviewer DEMO_SA --simulation
python tools/workspace.py simulate --job DEMO/customer_daily
python tools/workspace.py check
```

การเปลี่ยน space ใช้สาธิตการตรวจ content change โดยไม่เปลี่ยนผล query
ถ้าแก้ business rule จนผลต่างจาก fixture การอนุมัติอย่างเดียวจะไม่ทำให้ผลเทียบผ่าน
ต้องออก target/fixture snapshot ใหม่ที่มี expected results ซึ่งผ่านการตรวจแยกต่างหาก
ต้นแบบนี้ไม่มีคำสั่งย้าย snapshot ของงานเดิมอัตโนมัติ

## รอบที่ 3 — สองงานแย่ง import slot

```powershell
python tools/workspace.py import-lock --job DEMO/customer_daily --holder DEMO_ALICE --simulation
python tools/workspace.py import-lock --job DEMO/order_daily --holder DEMO_BOB --simulation
```

คำสั่งของ DEMO_BOB ต้องล้มด้วย occupied จากนั้น:

```powershell
python tools/workspace.py import-unlock --job DEMO/customer_daily --holder DEMO_ALICE --simulation
python tools/workspace.py import-lock --job DEMO/order_daily --holder DEMO_BOB --simulation
python tools/workspace.py import-unlock --job DEMO/order_daily --holder DEMO_BOB --simulation
```

ดูประวัติได้ที่ `status/events.json` และ `status/IMPORT_LOG.md` ของงานนั้น
ข้อความทุกแถวระบุว่าไม่มีการ import ODI จริง และ G4 ไม่ถูกเปลี่ยนเป็นผ่าน

## รอบที่ 3.5 — รัน SQL บนฐาน Oracle DEV (เมื่อทีมเปิดใช้)

1. ผู้ดูแลตั้งกติกาและการเชื่อมต่อด้วย Setup ข้อ 7–8 หรือ `db-policy` / `db-connect` แล้วรัน `db-test`
2. เจ้าของงานคอมไพล์ SQL ที่แปลงแล้ว: `run-sql --job DEMO/customer_daily output/sql/converted --compile`
3. ระบบแสดงแผน → คนตอบ 1/2 → ผลอยู่ที่ `db_runs/verify/sql_compile.txt` และ `status/DB_RUN_LOG.md`
4. `python tools/workspace.py check` ยังต้องผ่าน — การรันฐานไม่เปลี่ยน fingerprint และไม่เปลี่ยน G4–G7

## รอบที่ 3.6 — บทเรียนของงานกลายเป็นความรู้ของทีม (kit 0.4.0)

1. ก่อนเริ่มขั้น: `python tools/workspace.py wiki-step 03 --job <P>/<J>` (ในแชทงาน `/wiki step 03`) — คำแนะนำต้องอ้าง L# / LT# / SIM-L#
2. จบขั้น: `/lesson` บันทึกบทเรียนลง `knowledge/lessons-learned.md` หัวข้อ 2 ของงาน พร้อมหลักฐาน · ใช้ได้ทุกงาน = ระบุ "generic"
3. `/kit-backport` → `kit-promote --job <P>/<J> --lesson L#` แสดงแผน + plan id (exit 3) → ผู้อนุมัติอ่านว่าไม่มีข้อมูลลูกค้า
4. ผู้อนุมัติพิมพ์ชื่อ + วันที่ → `kit-promote … --plan-id <id> --approved "<ชื่อ> <วันที่>"` → LT# ใน `shared/knowledge` ทุกงานเห็นทันที
5. `check` / `wiki-check` ตรวจหลักฐาน ข้อมูลลับ เลขซ้ำ และว่า LT# ที่ promote ยังอยู่ · การแก้สคริปต์ (K#) ส่งผู้ดูแล kit ออกรุ่นใหม่

ผู้อนุมัติความรู้กำหนดที่ `shared/approvers.json` → `knowledge_approvers` (Tech Lead เพิ่มชื่อ · AI ห้ามเพิ่มชื่อหรืออนุมัติแทน)

## รอบที่ 4 — การแยก branch/พื้นที่ทำงานเมื่อใช้จริง

Setup สามารถเลือกสร้าง Git repository เปล่าในเครื่องได้ แต่ยังไม่มี remote/initial commit และไม่สร้าง worktree ให้อัตโนมัติ
เมื่อจัดตั้ง repository ของทีมแล้ว: แต่ละคนใช้ clone ของตนเอง และถ้าทำหลายงานพร้อมกันบนเครื่องเดียว
ให้สร้าง worktree ของแต่ละ job/round แยกกัน เปิดแชทที่โฟลเดอร์งานใน worktree นั้น
ห้ามสลับ branch ใต้ working directory ที่อีกแชทกำลังใช้

PR ของงานแก้ input/config/decisions/ผลลัพธ์ของงานนั้น
PR ของ kit แก้เครื่องมือกลาง พร้อมผลทดสอบและ release ใหม่
Main ต้องมี required checks และ Code Owner review ซึ่งเป็นการตั้งค่าบนระบบจริงแยกจากต้นแบบนี้
