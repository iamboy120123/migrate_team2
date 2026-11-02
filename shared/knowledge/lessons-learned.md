# Team lessons

ชั้น "ทีม" ของ Wiki (`shared/knowledge/`) — บทเรียนที่ใช้ได้ทุกงานใน workspace นี้ · ทุกงานเห็นทันทีผ่าน `wiki-search` / `wiki-step` (ไม่ต้องรอ kit รุ่นใหม่)
เพิ่มข้อใหม่ด้วย `python tools/workspace.py kit-promote` เท่านั้น (คนอนุมัติ · บันทึกใน `PROMOTIONS.json`) · ห้ามลบหรือเปลี่ยนเลข — แก้ข้อเดิมให้เขียน `แก้ YYYY-MM-DD …` ต่อท้าย
ลำดับเมื่อขัดกัน: การตัดสินของงาน / project > บทเรียนทีม > kit/knowledge

## 1. จาก simulation ของ migrate_team2 (ก่อนมี kit-promote · เลขเดิม)

| # | หมวด / ขั้น | ปัญหาที่เจอ | ผลถ้าพลาด | วิธีทำ | หลักฐาน | ที่มา / อนุมัติ |
|---|---|---|---|---|---|---|
| SIM-L01 | 02 · load strategy | Append can duplicate rows on rerun; idempotency depends on the chosen strategy. | rerun ซ้ำแล้วแถวซ้ำโดยไม่มี error | ถาม I14 (append / overwrite / upsert) ทีละ task และทดสอบรัน 2 รอบ · generic | Demo T003 first/second-run fixture report | migrate_team2 simulation (2026-11) |
| SIM-L02 | kit | A kit update must not silently change an in-progress job. | งานที่กำลังทำเปลี่ยนพฤติกรรมเองหลังอัปเดต kit | งานยึด `kit.lock.json` · เปลี่ยนรุ่นเฉพาะเมื่อตั้งใจ · generic | kit.lock.json + immutable release tests | migrate_team2 simulation (2026-11) |
| SIM-L03 | 03 · review | A review is stale when governed input/config/pin content changes. | ใช้ผล review เก่ากับเนื้อหาใหม่ | แก้ input / config / pin แล้ว review + simulate ใหม่ · generic | Fingerprint and stale-review test | migrate_team2 simulation (2026-11) |
