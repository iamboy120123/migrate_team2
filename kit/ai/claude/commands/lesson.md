---
description: บันทึกความรู้ลง Wiki ของงาน — บทเรียน (L#) · ข้อเท็จจริงของ environment · ศัพท์ — มีหลักฐานทุกข้อ
argument-hint: "<สิ่งที่เรียนรู้ / ข้อเท็จจริง>"
---
กติกา Wiki: `../../../../kit/knowledge/README.md` (ตรวจอัตโนมัติด้วย `python ../../../../tools/workspace.py wiki-check` · `workspace.py check`)

1. แยกประเภทของ: $ARGUMENTS
   - **บทเรียน** (ปัญหาที่เจอ + ผลถ้าพลาด + วิธีทำ) → `knowledge/lessons-learned.md` หัวข้อ `## 2. บทเรียนของงานนี้ (/lesson)` (ไม่มีหัวข้อ = สร้างท้ายไฟล์พร้อมหัวตารางด้านล่าง) · เลข L ถัดไป (ต่อจากเลขสุดท้ายของทั้งไฟล์)
     `| # | หมวด / ขั้น | ปัญหาที่เจอ | ผลถ้าพลาด | วิธีทำ | หลักฐาน | วันที่ / โดย |`
     หมวด / ขั้น = เลขขั้น 01–06 + หมวด เช่น `03 · performance` · `05 · import` (ระบบใช้ดึงบทเรียนตามขั้น)
   - **ข้อเท็จจริงของงาน** (ชนิดคอลัมน์ landing, schedule, Spark config, path) → `knowledge/environment-facts.md`
   - **ข้อเท็จจริงระดับ env** (Oracle version, NLS, timezone ที่ใช้ทุกงาน) → เสนอเข้า `shared/target/environment-facts.md` ผ่าน PR แยก (บอกคน ไม่แก้เอง)
   - **ศัพท์** → `knowledge/glossary.md` (ของงาน) · ศัพท์ธุรกิจทั้ง project → เสนอเข้า `../../_project/glossary.md` · ศัพท์ที่ใช้ทุกงาน → `/kit-backport`
2. ต้องมี **หลักฐาน** ทุกข้อ (ไฟล์ผลใน `input/run_results/<pack>/`, `status/DB_RUN_LOG.md`, screenshot, บรรทัด SQL, ข้อความของ SA พร้อมวันที่) — ไม่มีหลักฐาน = ถาม SA ก่อน ห้ามบันทึกจากการเดา
3. **ห้ามข้อมูลลับ** (รหัสผ่าน · connection string · ข้อมูลลูกค้า) · **ห้ามลบ / เปลี่ยนเลขข้อเดิม** — ขัดกับข้อเดิม = แก้ข้อเดิมพร้อมหมายเหตุวันที่
4. ค้นก่อนว่าซ้ำไหม: `python ../../../../tools/workspace.py wiki-search <คำหลัก>` (ซ้ำกับ LT# / SIM-L# ของทีม = อ้างข้อนั้น ไม่ต้องเพิ่ม)
5. ใช้ได้ทุกงาน → ระบุ "generic" ในช่องวิธีทำ แล้วเสนอ `/kit-backport` (ส่งเข้าชั้นทีมเมื่อคนอนุมัติ) · ต้องแก้ script เพื่อป้องกัน → เสนอ K# (ผู้ดูแล kit)
6. รัน `python ../../../../tools/workspace.py wiki-check` ต้องไม่มี ERROR · ตอบสั้น ๆ ว่าเพิ่มที่ไหน เลขอะไร
