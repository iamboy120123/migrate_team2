---
description: Wiki / Knowledge — ค้นความรู้ทุกชั้น (kit · ทีม · ระบบปลายทาง · project · งาน) หรือดึงบทเรียนของขั้นที่กำลังทำ
argument-hint: "<คำค้น> | step <01-06> | check"
---
หน้าแรกของ Wiki: `../../../../kit/knowledge/README.md` · ใช้ได้ทั้งงาน simulation และ delivery (คำสั่งอยู่ที่ root ของ workspace)

- `$ARGUMENTS` เป็น `step 03` → `python ../../../../tools/workspace.py wiki-step 03 --job {{PROJECT}}/{{JOB}}` แล้วสรุปบทเรียนที่ใช้กับงานนี้ (บอกเลข L# / LT# / SIM-L# · ใช้ได้เพราะอะไร)
- `$ARGUMENTS` เป็น `check` → `python ../../../../tools/workspace.py wiki-check` แล้วบอกข้อที่ต้องแก้ทีละข้อ
- อื่น ๆ = คำค้น → `python ../../../../tools/workspace.py wiki-search "$ARGUMENTS"` (เพิ่ม `--layer team` = เฉพาะบทเรียนทีม)
- สรุปผลเป็นตาราง: ชั้น · ไฟล์ · เลขอ้างอิง · ใจความ · ใช้กับงานนี้ได้ไหม — แยก "ข้อเท็จจริงจาก Wiki" กับ "ความเห็นของ AI" ให้ชัด
- ลำดับเมื่อขัดกัน: การตัดสินของงาน / project > บทเรียนทีม (`shared/knowledge`) > kit (`kit/knowledge`)
