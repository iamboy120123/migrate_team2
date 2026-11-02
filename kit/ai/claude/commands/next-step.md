---
description: อ่านสถานะล่าสุดแล้วทำ step ถัดไปของ migration
---
<!-- KIT-BANNER {"scripts": ["scripts/runpack/read_run_results.py", "scripts/ws/job_status.py"], "other": []} -->
> **ใครรัน SQL — กฎทีม `CLAUDE.md` (ส่วน kit) หัวข้อ "AI กับฐานข้อมูล" ชนะขั้นตอนด้านล่างเรื่องนี้** · ดูโหมด: `python scripts/ws/job_status.py --modes`
> - `db=ask` / `db=auto` → ใช้ `python ../../../../tools/workspace.py run-sql --job {{PROJECT}}/{{JOB}} <pack | ไฟล์> --plan` แล้ว **ถามคนในแชท: 1 = ให้ AI รัน / 2 = ฉันรันเอง** (ตอบเป็นเลข · ห้ามเลือกแทนคน)
>   ตอบ 1 → `run-sql --execute <แผน> --approved "<ชื่อคน> <วันที่>"` (คำสั่งที่ลบแล้วกู้คืนไม่ได้ ให้คนพิมพ์ชื่อตารางก่อน → `--confirm`) · ตอบ 2 → `run-sql --human <แผน>` บอกคนทีละไฟล์ แล้ว `--record-human`
>   `db=auto` + SELECT ล้วน → `run-sql <pack> --run-read` ได้เลยไม่ต้องถาม · pack หลายขั้นใช้ `--only` เฉพาะขั้นที่ถึงแล้ว
> - `db=human` → AI ไม่ต่อฐาน · บอกคนทีละไฟล์ตามขั้นตอนด้านล่าง (เปิดไฟล์ไหน · รันเพื่ออะไร · export แบบไหน · วางที่ไหน)
> - ไฟล์ Blendata (Spark SQL) · งานใน ODI Studio = คนทำเสมอ · ห้ามเรียก sqlplus / sqlcl เอง · ห้ามขอรหัสผ่านในแชท

0. **Wiki (เริ่มขั้น):** รัน `python ../../../../tools/workspace.py wiki-step <เลขขั้นที่จะทำ 01–06> --job {{PROJECT}}/{{JOB}}` แล้วสรุปบทเรียนที่เกี่ยวข้องให้คนเห็นก่อนลงมือ · คำแนะนำทุกข้อในขั้นนี้ต้องมี `อ้างอิง: L# …` หรือ `อ้างอิง: ไม่มีบทเรียนที่เกี่ยวข้อง`
1. อ่าน `status/PREFLIGHT_CHECKLIST.md` (gate Phase 0), `status/MIGRATION_STATUS.md` (หัวข้อ "ยังค้าง" และ "ผล Run Pack") และ `status/OPEN_DECISIONS.md`
2. ถ้ามี `input/run_results/<pack>/` ที่ใหม่กว่า `run_packs/<pack>/REPORT.md` → รัน `python scripts/runpack/read_run_results.py --pack <pack ล่าสุด>` ก่อน แล้วอ่าน `REPORT.md`
3. เลือก step ถัดไปที่ **ไม่ติด human-decide** แล้วลงมือทำ (regenerate / validate / สร้าง Run Pack / แก้ SQL ตาม flag)
   - ก่อนข้ามช่วงงาน (เช่น สร้าง Run Pack = G3, ไป Pre-Prod = G5) ต้องรัน `/gate G<n>` — BLOCKED = ห้ามข้าม เว้นแต่มี waiver ที่ SA อนุมัติ
4. ถ้าติดการตัดสินใจ → เขียนคำถามแบบมีตัวเลือกลง `status/OPEN_DECISIONS.md` แล้ว **ถาม SA ในแชตเลย** (ยกคำถาม+ตัวเลือกมาแสดง ทีละข้อ ไม่ให้ไปเปิดไฟล์อ่านเอง) เมื่อตอบแล้ว agent บันทึกลงไฟล์เอง แทนการเดา
5. ถ้าต้องให้คนรันบน Oracle/ODI/Blendata → สร้าง Run Pack และบอกลำดับขั้นให้คนทำ (มีเลขกำกับ)
6. จบด้วย `/update-status` (ถามเรื่องบทเรียนของขั้นนี้) แล้วสรุปสั้น ๆ: ทำอะไรไป, ผล, คนต้องทำอะไรต่อ
7. ลำดับขั้นของงานยึด `knowledge/WORKFLOW.md` (คู่มือใน knowledge/ เป็นแกน + BR / Gap / Decision / Status) — เลือกขั้นถัดไปจากขั้นแรกในตารางที่ยังไม่ผ่าน gate

$ARGUMENTS
