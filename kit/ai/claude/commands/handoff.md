---
description: ส่งต่องาน / จบ session — สรุปสำหรับคนรับงาน (HANDOVER + รายการตาราง) · ถ้าเปลี่ยนคนทำ แก้ owner ใน job.json · push ถามก่อน
argument-hint: "[ว่าง = สรุปจบ session · <ชื่อบัญชี GitHub ของคนรับงาน> = ส่งต่องาน]"
---
<!-- KIT-BANNER {"scripts": ["scripts/checks/check_gate.py", "scripts/checks/verify_all.py", "scripts/ws/job_status.py"], "other": ["workspace.py handoff"]} -->
1. `python scripts/checks/check_gate.py --all` · `python scripts/checks/verify_all.py --quiet` · `python scripts/ws/job_status.py --json`
2. อ่าน `status/MIGRATION_STATUS.md` (rev ล่าสุด) · `status/OPEN_DECISIONS.md` · `status/GATES.md` · REPORT ของ Run Pack ล่าสุด · `status/DEPLOY_LOG.md` · `status/IMPORT_LOG.md`
3. เขียน / อัปเดต `status/HANDOVER.md` (ภาษาไทย กระชับ · ไม่มีรหัสผ่าน / host / ผลรันจริง):
   - **ทำไปแล้ว** — ขั้นที่ผ่าน (อ้างเลขขั้นใน `knowledge/WORKFLOW.md`) · ไฟล์ที่เปลี่ยน
   - **ขั้นถัดไป** 1 ข้อ + ใครต้องทำ · ⏳ รอใคร (Q ที่เปิด · manual ที่ค้าง · waiver)
   - **รายการตาราง** (table inventory): ตารางปลายทาง / staging / error table / ตาราง mock ที่งานนี้สร้างหรือเขียน — ชื่อ · สร้างจากไฟล์ไหน · อยู่ใน DEPLOY_LOG ไหม · ข้อมูลทดสอบค้างอยู่ไหม (marker) + วิธี cleanup
   - **เส้นตาย** (เช่น ล็อก import หมดอายุ 2 ชม. · ต้อง Smart Import ก่อนรัน) · **สมมติฐานที่ยังไม่ยืนยัน** · บทเรียนที่ยังไม่บันทึก (เสนอ `/lesson`)
4. ถ้า `$ARGUMENTS` มีชื่อคนรับงาน (หรือคนบอกในแชทว่าจะส่งต่อ):
   - ถามยืนยัน 1 ข้อ: `1 = ส่งต่อให้ <ชื่อ>` / `2 = ยังไม่ส่งต่อ (แค่สรุปจบ session)` / `3 = ยังไม่ทราบ`
   - ตอบ 1 → บอกให้คนรันใน Terminal ที่ root ของ workspace (คำสั่งนี้แก้ job.json และอาจ comment ใบงาน = ถามก่อนเสมอ):
     `python tools/workspace.py handoff --job <ชื่องาน> --to <ชื่อ> --reason "<เหตุผล>"`
     (โหมด GitHub แบบอ่านเอง-เขียนถาม / ถามทุกครั้ง: AI รันคำสั่งนี้ได้หลังคนอนุญาต · ระบบถามยืนยันอีกชั้น)
5. `/update-status` (ถ้ายังไม่ครอบคลุม session นี้) แล้วเสนอ commit `status/HANDOVER.md` + `job.json` และ push branch — **ถามก่อนตามโหมด GitHub**
   - ส่งมอบรอบ (จบขั้น 06 · ไม่ใช่แค่จบ session): ถามทีละข้อ ตามลำดับ — แต่ละข้อแสดงคำสั่งจริงแล้วรอ `1 = ทำเลย` / `2 = ฉันทำเอง`
     (ก) เปลี่ยน draft PR เป็น ready: `gh pr ready <เลข PR>` · (ข) tag ส่งมอบ: `git tag -a <PROJECT>/<งาน>/<รอบ>-handover -m "<รอบ> handover"` แล้ว `git push origin <tag>`
     ห้าม merge เอง · ห้าม push เข้า main — ผู้อนุมัติ review (CODEOWNERS) → CI ผ่าน 3 ตัว → merge
6. บอกคนรับงาน 3 บรรทัด: `git fetch` → `git switch <branch ของงาน>` → เปิด Claude Code ที่โฟลเดอร์งานแล้วพิมพ์ `/status`
7. ปิดท้ายด้วยกล่องสถานะ (`python scripts/ws/job_status.py --box`)
