# Knowledge ของ kit (migrate_team2)

ความรู้กลางที่ติดมากับ kit รุ่นที่งานล็อกไว้ (`kit.lock.json`) — `new-job` คัดลอกลง `knowledge/` ของงาน
ต้นฉบับ: Migrate_ODI_Team2 kit 2.15.0 + บทเรียนจากงานจริง (ดู `kit/ai/claude/SOURCE.json`)

| ไฟล์ | ใช้เมื่อ | แก้ได้ไหม (ในงาน) |
|---|---|---|
| `WORKFLOW.md` | ไม่แน่ใจว่าอยู่ขั้นไหน (ขั้น 0–7 + เลข I / Q / BR / GAP / L / G) | ได้ (ของงาน) |
| `lessons-learned.md` | ก่อนแปลง / ตัดสินใจ — บทเรียนและ edge case ที่เจอจริง (case #) | ได้ — เพิ่มด้วย `/lesson` |
| `glossary-kit.md` | คำย่อและศัพท์ของ kit | ได้ |
| `reference/migration-rules.md` | กติกาหลักของการย้าย As-Is | **ไม่ได้** (อ้างอิงกลาง) |
| `reference/spark-to-oracle-sql.md` | mapping Spark SQL → Oracle 19c | ไม่ได้ |
| `reference/oracle-checks-and-spark-config.md` | config ของ Spark ที่เปลี่ยนผลลัพธ์ + สิ่งที่ต้องตรวจฝั่ง Oracle | ไม่ได้ |
| `reference/odi-object-reference.md` | โครงสร้าง object ของ ODI 14c | ไม่ได้ |
| `reference/intake-questions.md` | คำถาม intake I1–I17 และวิธีถาม | ไม่ได้ |
| `reference/test-method.md` · `validation-and-cutover.md` | วิธีทดสอบ / เทียบผล / cutover | ไม่ได้ |
| `reference/delivery-checklist.md` · `deliverables.md` · `grading-rules.md` | ของที่ต้องส่ง และเกณฑ์ตรวจก่อนส่ง | ไม่ได้ |
| `reference/blendata-json-schema.md` | โครงสร้างไฟล์ export ของ Blendata | ไม่ได้ |
| `reference/claude-system.md` | แผนที่ rules / skills / agents / commands ของงาน | ไม่ได้ |
| `reference/optional/*` | เส้นทางทางเลือก (manual build, mapping-based) | ไม่ได้ |
| `reference/SIMULATION_SCOPE.md` | ขอบเขตของ simulator ใน migrate_team2 | ไม่ได้ |

`check` ตรวจว่า `knowledge/reference/**` และ `.claude/**` ที่ติดตั้งจาก kit ยังตรงกับ release (แก้ = FAIL)
ถ้าต้องแก้อ้างอิงกลาง ให้แก้ที่ `kit/knowledge/` แล้วออก kit รุ่นใหม่ งานเดิมยังใช้รุ่นที่ล็อกไว้

เอกสารอ้างอิงหลายไฟล์พูดถึง `scripts/...` ของ Migrate_ODI_Team2 — ใน migrate_team2 ใช้ได้เฉพาะสิ่งที่ `CLAUDE.md` หัวข้อ 2 บอกว่ามี

## Wiki — 5 ชั้น และวิธีใช้ (kit 0.4.0)

| ชั้น | ที่เก็บ | ใครเพิ่ม |
|---|---|---|
| kit | `kit/knowledge/` (รุ่นที่ติดมากับ kit) | ผู้ดูแล kit — ออก kit รุ่นใหม่ |
| ทีม | `shared/knowledge/lessons-learned.md` (LT# · SIM-L#) + ledger `PROMOTIONS.json` | `workspace.py kit-promote` เมื่อผู้อนุมัติอนุมัติเท่านั้น |
| ระบบปลายทาง | `shared/target/` | Tech Lead |
| project | `projects/<P>/_project/` (DECISIONS · glossary · lessons-learned) | SA ของ project |
| งาน | `jobs/<งาน>/knowledge/` + `status/OPEN_DECISIONS.md` | `/lesson` (มีหลักฐาน) |

ลำดับเมื่อขัดกัน: การตัดสินของงาน / project > บทเรียนทีม > kit · ทุกงานเห็นชั้นทีมทันที (ไม่ผูกกับรุ่น kit ที่ล็อก)

```
python tools/workspace.py wiki-step 03 --job <P>/<J>     # ก่อนเริ่มขั้น
python tools/workspace.py wiki-search overwrite          # ค้นทุกชั้น (--layer team = เฉพาะทีม)
python tools/workspace.py wiki-check                     # หลักฐาน · ข้อมูลลับ · เลขซ้ำ · ledger (รวมอยู่ใน check ด้วย)
python tools/workspace.py kit-promote --job <P>/<J> --lesson L43                       # แผน (exit 3 = รออนุมัติ)
python tools/workspace.py kit-promote --job <P>/<J> --lesson L43 --plan-id <id> --approved "<ชื่อ> <YYYY-MM-DD>"
```

promote ได้เฉพาะบทเรียนในหัวข้อ 2 ของงานที่มีหลักฐาน · มีหมวด / ขั้น · ระบุ "generic" (ใช้ได้ทุกงาน) · ไม่มีข้อมูลลับ · ยังไม่เคย promote
ผู้อนุมัติต้องอยู่ใน `shared/approvers.json` → `knowledge_approvers` · plan id ผูกกับเนื้อหา (แก้หลังอนุมัติ = ต้องอนุมัติใหม่)
ชั้นทีมเป็น append-only: ห้ามลบ / เปลี่ยนเลข (ledger ตรวจได้แม้ไม่มี git) — แก้ข้อเดิมให้เขียน `แก้ YYYY-MM-DD …`
บทเรียนทีมที่มั่นคงแล้ว ผู้ดูแล kit ยกเข้า `kit/knowledge/` ได้ตอนออก kit รุ่นใหม่ (คงเลข LT# เดิม)
