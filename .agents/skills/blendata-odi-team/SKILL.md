---
name: blendata-odi-team
description: Set up and operate the migrate_team2 Blendata-to-ODI team simulation workspace, including its PowerShell wizard, Project/Job setup, pinned kit and target snapshots, simulated reviews, import-lock rehearsals, evidence checks, and the approval-gated Oracle adapter (db-* / run-sql). Use for this workspace workflow; real ODI deployment needs the separate production integration.
---

# Blendata to ODI team workflow

ใช้กับ workspace `migrate_team2` และ workspace ที่สร้างจากชุดนี้ ตอบผู้ใช้เป็นภาษาไทยเมื่อผู้ใช้ใช้ภาษาไทย
ยึดสภาพไฟล์และคำสั่งปัจจุบันเหนือรายละเอียดในประวัติการสนทนา

## Locate and route

1. หา root จาก path ที่ผู้ใช้ระบุ หรือไล่ parent ของ working directory จนพบ `workspace.json` และ `tools/workspace.py`
   ถ้ายังไม่ Setup ให้หา root ของ source bundle จาก `setup_workspace.ps1` และ `kit/src/migrate_kit/`
2. อ่าน `workspace.json`, `shared/team.json`, `shared/policies/TEAM.md` ที่มีอยู่ และดู `--help` เมื่อไม่แน่ใจว่าคำสั่งรองรับอะไร
   อย่าสับสนกับ workspace เก่า `migrate_team` หรือถือว่า `Migrate_ODI_Team2/kit/setup_migrate.ps1` เป็นคำสั่งของต้นแบบนี้
3. ถ้าทำงานกับ Job ให้อ่าน `job.json`, `kit.lock.json`, config และ `status/` ของงานก่อนลงมือ
   ใช้ชื่อ `PROJECT/job` เพื่อเลี่ยงความกำกวม
4. อ่าน [references/workspace-commands.md](references/workspace-commands.md) เฉพาะส่วนที่ตรงกับ Setup, Job หรือการวินิจฉัยที่ผู้ใช้ขอ

## Workspace setup

- ใช้ `setup_workspace.ps1` เป็นทางเข้าหลักสำหรับ Setup ไม่เรียกไฟล์ใน runtime ทีละตัว
- โหมดปกติเป็น wizard 8 ข้อ: โฟลเดอร์, ชื่อ workspace/ทีม, Python, synthetic target, ผู้รีวิวจำลอง, Git ในเครื่อง,
  กติกาการรัน SQL บน Oracle (ข้อ 7) และค่าการเชื่อมต่อ Oracle (ข้อ 8 เมื่อข้อ 7 ให้ระบบรัน)
  มีคำอธิบาย ค่าแนะนำ, `?`, Enter และสรุป `y/e/q` ก่อนเขียนไฟล์
- ใช้ `-NonInteractive` เมื่อรันผ่าน automation หรือเมื่อคำตอบที่จำเป็นทราบแล้ว คงค่าที่ไม่ได้รับคำสั่งให้เปลี่ยน
  การอนุญาต Setup ไม่ได้หมายถึงต้องสร้าง Git, เพิ่ม reviewer หรือเลือก target ใหม่โดยอัตโนมัติ
- workspace ใหม่ต้องอยู่ในโฟลเดอร์ว่างนอก source tree; workspace เดิมรักษางาน ค่าทีม และ target เดิม
  อย่าใช้การลบไฟล์ ปรับ checksum หรือเขียนทับ release เพื่อหลบข้อผิดพลาดจาก Setup
- `-WhatIf` ดูแผนโดยไม่ถามและไม่เขียนไฟล์ การยกเลิกหรือ input จบก่อนยืนยันไม่มีการติดตั้งใด ๆ
- Setup ติดตั้ง skill นี้ระดับ workspace เท่านั้น การใช้ skill ไม่ได้เพิ่มสิทธิ์ต่อระบบภายนอก

## Project and Job setup

- Project คือกลุ่มงานใน workspace ไม่ใช่การสร้าง Project ใน ODI Studio
  ไม่มี `new-project` แยก; `new-job --project ...` สร้าง `_project/` ให้เมื่อเป็นงานแรก
- หนึ่ง workflow ต่อหนึ่ง Job; แยก input/config/output/status และเจ้าของงาน
  ชื่อ Project/Job/Owner เริ่มด้วยอักษรอังกฤษ ตามด้วยอักษร ตัวเลขหรือ `_` ไม่เกิน 50 ตัว
- ตรวจเลข Issue จำลองที่มีอยู่ก่อนเลือกเลขใหม่ ไม่ยึดเลขตัวอย่าง 101/102/201 ว่าจะว่างเสมอ
  เลขนี้ยังไม่ใช่การจองบน GitHub หรือ ODI repository จริง
- `new-job` ก๊อป workflow ลงงาน จึงแก้ input ของ Job ที่จะทำงาน ไม่แก้ sample แล้วคาดว่างานเดิมจะเปลี่ยน
- ใช้ sample ก่อนเมื่อทดสอบโครงงาน หากเปลี่ยน task/SQL/ตาราง ต้องเตรียม schema และ curated expected rows ให้ตรง
  Simulator รองรับ normalized synthetic JSON และ SQL subset แบบจำกัด ไม่ใช่ Blendata export ทุกรูปแบบ
- ชื่อ branch ใน `job.json` เป็นแผนเท่านั้น เมื่อทำหลาย branch พร้อมกันให้ใช้ working directory แยก
  อย่าอ้างว่าสร้าง branch/worktree/PR แล้วถ้าไม่มีหลักฐานการกระทำนั้น

## Shared kit, target and evidence

- โค้ดกลางอยู่ใน `kit/src/migrate_kit`; ไม่ก๊อป pipeline source ลงแต่ละ Job
  Job ใช้ runtime ZIP ตาม version และ SHA-256 ใน `kit.lock.json`
- source/resources ของรุ่นที่ freeze แล้วเปลี่ยน ต้องออก kit version ใหม่ ไม่แก้ release manifest ให้ตรงไฟล์ที่เปลี่ยน
  รักษา release เก่าเพื่อให้งานที่ล็อกไว้สร้างผลซ้ำได้
- Target คือ immutable synthetic snapshot; `current.json` เลือกค่าเริ่มต้นของงานใหม่ ไม่เปลี่ยน pin ของงานเดิม
  ต้นแบบยังไม่มีคำสั่ง repin/new-round งานเดิม อย่าสร้างคำสั่งนั้นขึ้นเอง
- input/config/pin เปลี่ยนทำให้ fingerprint เปลี่ยนและรีวิวเดิมเป็น STALE
  ถ้าผู้ใช้แสดงภาพที่ยังผ่าน ให้ตรวจไฟล์ที่บันทึกจริงกับ fingerprint ก่อนสรุปว่าระบบเสีย
- อย่าแก้ generated output หรือสถานะให้ดูว่าผ่าน แก้ต้นทางแล้ว regenerate พร้อมตรวจ `check`
  แถวซ้ำมีความหมายต่อผลเทียบ; จำนวนแถวเท่ากันอย่างเดียวไม่พอ และศูนย์แถวไม่เป็นหลักฐานผ่านของ fixture นี้

## Review, simulation and lock rehearsal

- `approve --simulation` เป็น fictional review ผูกกับ fingerprint ไม่ใช่ SA อนุมัติจริง
  ใช้เมื่อผู้ใช้ต้องการรีวิวจำลองหรือสาธิตวงจรนี้ อย่าอนุมัติใหม่เพียงเพื่อทำให้ error หาย
- หลังรีวิวให้ `simulate` แล้ว `check`; รายงานผลที่ตรวจได้พร้อม path ของหลักฐาน
  `SIMULATION_PASSED` ไม่ได้ยืนยัน Spark/Oracle semantics, Oracle compilation หรือ ODI import
- ตัวอย่างใช้ upsert, append และ explicit unpartitioned overwrite
  ไม่เลือก DELETE/TRUNCATE หรือเปลี่ยน semantics ของงานเอง ถ้า overwrite ไม่มีการเลือกที่ชัดเจนให้หยุดที่จุดนั้น
- อธิบายผลรันซ้ำตาม strategy: append อาจเพิ่มแถวซ้ำ ขณะที่ upsert/overwrite ใน fixture คงผลเดิม
  อย่าเรียกทุกงานว่า idempotent
- import-lock เป็นการจองผ่านไฟล์ใน directory เดียว ผู้ปลดต้องเป็น Job และ holder เดิม
  ใช้ได้กับการซ้อม local workspace ไม่ใช่ distributed lock ข้ามเครื่อง และไม่มี Smart Import ซ่อนอยู่

## Job AI context (kit 0.2.0+)

- งานที่ล็อก kit 0.2.0 ขึ้นไปมี `.claude/` และ `knowledge/` จาก kit — อ่าน `CLAUDE.md` ของงานก่อน โดยเฉพาะหัวข้อ 2 (เครื่องมือที่มี/ยังไม่มี)
- ไฟล์ที่มีป้าย ⚠️ อ้างเครื่องมือของ Migrate_ODI_Team2 ที่ยังไม่มีในชุดนี้: ห้ามสร้าง ค้นหา หรือคัดลอก scripts มาเอง ทำเฉพาะส่วนวิเคราะห์/เอกสาร
- ห้ามแก้ `.claude/**` และ `knowledge/reference/**` ในงาน (`check` FAIL) — ถ้าต้องเปลี่ยนกฎกลาง ให้แก้ `kit/ai` / `kit/knowledge` แล้วออก kit รุ่นใหม่
- งานที่ล็อก 0.1.0 (เช่น DEMO) ไม่มี AI context ชุดนี้และยังทำงานตามรุ่นเดิม

## Delivery jobs (kit 0.3.0+)

- `job.json` `mode=delivery` = งานจริง: มี `scripts/` (pipeline เต็มของ Migrate_ODI_Team2 2.15.0 + patch) ล็อกจาก kit
  สร้างด้วย `new-job --mode delivery` หรือย้ายงานเดิมด้วย `import-job --from <job folder>`
- ทำงานในโฟลเดอร์งานตาม `CLAUDE.md` ของงาน (`python scripts/...`) · SQL บนฐานผ่าน `run-sql` เท่านั้น · Smart Import = คนทำ
- ห้าม patch `scripts/` ในงาน — บั๊กของ kit แก้ที่ `kit/delivery/scripts` แล้วออก kit รุ่นใหม่ + replay regression ให้ผ่าน
- `convert_sql.py` ไม่ทับ SQL ที่แก้หลัง convert; ผลใหม่อยู่ `output/sql/converted_machine/` — `--force` เมื่อ SA สั่งเท่านั้น
- `approve --simulation`, `simulate`, import-lock rehearsal ใช้กับงาน simulation เท่านั้น · Gate จริงอยู่ที่ `status/GATES.md`

## Wiki and team knowledge (kit 0.4.0)

- Before a step: `python tools/workspace.py wiki-step <01-06> --job PROJECT/job`; search with `wiki-search <term>`. Cite L# / LT# / SIM-L#.
- Layers: kit (`kit/knowledge`) < team (`shared/knowledge`) < project < job decisions. The team layer is append-only.
- `kit-promote --job PROJECT/job --lesson L#` only shows a plan (exit 3). Show it to the person; only after they approve and type
  their name/date run `--plan-id <id> --approved "<name> <date>"`. Never approve, add approver names or edit the lesson after approval.
- Script fixes (K#) are not promoted; report them for a kit release.

## Oracle adapter (db-* / run-sql)

- อยู่ที่ `tools/dbcore` นอก kit ที่ล็อกรุ่น อ่าน `docs/DATABASE.md` และ `python tools/workspace.py db-status` ก่อนใช้
- กติกาทีมคือ `shared/team.json` → `db`; ค่าเริ่มต้น `ai_access=human` = ระบบไม่ต่อฐาน ให้ใช้ `--human <แผน>` บอกขั้นตอนทีละไฟล์
  อย่าเปลี่ยน `db-policy` หรือ `db-connect` เองถ้าผู้ใช้ไม่ได้สั่ง `config.json` `db_mode=human` เป็นค่าของ simulator ห้ามแก้
- ขั้นตอนเมื่อ AI เรียก: `run-sql --job PROJECT/job <เป้าหมาย> --plan` → ถามคนในแชทด้วยข้อความ ❓ (ตอบเป็นเลข)
  → คนตอบ 1: `--execute <แผน> --approved "<ชื่อคน> <วันที่>"` · คนตอบ 2: `--human <แผน>` แล้ว `--record-human` เมื่อคนบอกผล
  exit 3 หมายถึงต้องขออนุญาต ห้ามเลือกแทนคนหรือใส่ชื่อผู้อนุญาตเอง
- คำสั่งที่ลบแล้วกู้คืนไม่ได้ต้องให้คนพิมพ์ชื่อตารางในแชทก่อนใส่ `--confirm` · ไฟล์ที่แก้หลังสร้างแผนต้องสร้างแผนใหม่
- ห้ามขอหรือรับรหัสผ่านในแชท: ให้คน `setx ORA_RO_PASSWORD` / `ORA_RW_PASSWORD` หรือรันคำสั่งเองใน Terminal
- ไฟล์จาก `output/` เป็น illustrative DML ให้ `--compile` / `--explain` ก่อนรันจริง; ฐาน PROD ถามก่อนเสมอ
- ผลอยู่ที่ `<job>/db_runs/` และ `status/DB_RUN_LOG.md` ไม่เปลี่ยน fingerprint, Gate หรือสถานะ simulation
  ผล 0 แถวไม่นับว่าผ่าน และผลฐานจริงไม่ใช่การอนุมัติ deploy

## Production boundary

`simulate` ไม่ต่อ Spark, Oracle, ODI หรือ GitHub และยังไม่ได้ใช้ native ODI builder ของชุดเดิม
การต่อ Oracle มีเฉพาะผ่าน Oracle adapter ข้างต้นซึ่งไม่เปลี่ยน G4–G7
ไฟล์ `*.simulation.xml` / `*.simulation.zip` ไม่ใช่ Smart Export; อย่าแนะนำให้นำเข้า ODI จริง
G4–G7 ต้องยังเป็น `NOT_EXECUTED` จนมีการเชื่อมระบบและหลักฐานจริงตามกระบวนการใหม่ที่อนุมัติ

ถ้าผู้ใช้ต้องการย้ายงานจริง อ่าน `docs/PRODUCTION_PATH.md` และตรวจ converter/builder ที่มีจริงก่อนวางงานต่อ
การติดตั้ง skill ไม่ถือเป็นการทำ production integration และไม่อนุญาตการเชื่อมต่อหรือเผยแพร่เพิ่มเติม
