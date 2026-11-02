---
description: รวมผลตรวจ SQL ทุกชั้น (①–⑦ + ความเร็ว) เป็น status/SQL_REVIEW.md แล้วไล่ ⛔ ก่อน · 🟡 ถามว่าไม่ต้องแก้ใช่ไหม
---
<!-- KIT-BANNER {"scripts": ["scripts/checks/review_report.py"], "other": []} -->
1. `python scripts/checks/review_report.py` → `status/SQL_REVIEW.md` (สรุป ✅ · 🟡 · ⛔ ต่อ task)
2. ชั้น ⑥ คอมไพล์กับฐานจริง: ถ้ายังเป็น – ให้สร้าง pack `python scripts/checks/review_report.py --make-compile-pack` แล้วทำตามโหมดการเช็กฐานของงาน
   แล้ว `python ../../../../tools/workspace.py run-sql --job {{PROJECT}}/{{JOB}} rp_compile --compile --plan` → ถามคน `1 = ให้ AI รัน` / `2 = ฉันรันเอง` ตามกติกา "AI กับฐานข้อมูล" ใน CLAUDE.md (ส่วน kit) (ทีมตั้งคนรันทั้งหมด = บอกตามลำดับ: ไฟล์ไหน · รันเพื่ออะไร · export เป็นอะไร · วางที่ไหน)
2b. ความเร็วจากแผนการรัน (ทีมอนุญาต AI เข้าฐาน · ไม่บังคับ): ถาม 1 ข้อ "ขอดูแผนการรัน (EXPLAIN PLAN) ของ SQL ที่แปลงแล้วไหม — ไม่รันคำสั่งจริง แค่ให้ Oracle บอกว่าจะอ่านตารางแบบไหน" `1 = ดู [แนะนำ ถ้ามีตารางใหญ่]` / `2 = ข้าม` / `3 = ยังไม่ทราบ`
   ตอบ 1 → `python ../../../../tools/workspace.py run-sql --job {{PROJECT}}/{{JOB}} output/sql/converted --explain --plan` → ขออนุญาตตามขั้นปกติ (ถามเสมอ แม้ตั้ง SELECT รันต่อเนื่อง) → ผลที่ `output/verify/explain_plan.txt` + `input/run_results/…/<task>.plan.txt` → รัน `review_report.py` ใหม่ (ข้อเตือนเข้าคอลัมน์ความเร็ว)
   ข้อเตือนที่ระบบจับ: อ่านทั้งตาราง (full scan) · ไม่ตัด partition · join ไม่มีเงื่อนไข — เป็น 🟡 ให้คนดู ไม่บล็อก · ข้อมูล DEV น้อยกว่า PROD แผนอาจต่างกันจริง · ชั้น ⑦ sandbox ไม่ทำ
3. แสดงสรุปบนจอ: "✅ n · 🟡 n · ⛔ n" แล้วไล่ข้อ ⛔ ก่อนทีละข้อ (แก้ที่ converted SQL เฉพาะ dialect ที่ไม่เปลี่ยนความหมาย · เปลี่ยนความหมาย = เปิด Q)
4. ข้อ 🟡 ที่เป็น WARN: ถามทีละข้อ "ข้อนี้ไม่ต้องแก้ใช่ไหม" พร้อม [แนะนำ] และเหตุผล → ตอบใช่ = บันทึก `NO_CHANGE` + เหตุผลใน `status/PHASE4_REVIEW_LOG.md` (ห้ามแก้ SQL เพียงให้ WARN หาย)
5. มี ⛔ = ห้าม build · จบแล้วรัน `/update-status` (แสดงกล่องสถานะ)
