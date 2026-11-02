# นำแบบจำลองไปต่อกับ workspace เดิม

เอกสารนี้เป็นรายการพัฒนาต่อ ไม่มีการแก้หรือย้ายไฟล์จาก ../migrate_team ในรอบสร้างต้นแบบ

| ส่วน | ต้นแบบนี้ | งานก่อนใช้ production |
|---|---|---|
| Input parser | normalized synthetic tasks | นำ extract_workflow เดิมมาเป็น adapter รองรับ export จริงและ DAG |
| Delivery runtime (0.3.0) | scripts 2.15.0 + patch ของ SS_ESIM ล็อกในงาน · regression SS_ESIM ผ่าน | config wizard จาก Smart Export, new-round, port เป็น package ภายหลัง |
| SQL conversion | restricted demo rules | ย้าย converter เดิมพร้อม patch หลัง setup และ regression cases จากงานจริง |
| Native ODI builder | ยังไม่มี | นำ build_odi_export / odi_builder / validate_odi_xml เดิมมารวมใน package กลาง |
| Job root | ส่ง root/job ชัดเจน | แก้ legacy __file__/cwd/import/subprocess paths ไม่ให้เขียนกลับ kit กลาง |
| Target reference | synthetic fixtures/columns | snapshot ของ Smart Export ปลายทางจริง + schema + preflight evidence |
| DB access | `tools/dbcore` (port จาก dbx.py 2.15.0) แผน + ผู้อนุญาต + log | ย้ายเข้า kit รุ่นใหม่, ดึง target profile (all_tab_columns/constraint/NLS) เป็น snapshot |
| Approval | fictional DEMO_SA | ตรวจตัวตน/สิทธิ์ผู้อนุมัติจริงจาก PR และ hash ของสิ่งที่อนุมัติ |
| ID reservation | เลขจำลอง 101/102 | เลขใบงานจริง/ทะเบียนกลางและตรวจชนใน repository ปลายทาง |
| Release | ZIP ใน local cache | immutable release storage + pinned dependencies + restore รุ่นเก่า |
| Import lock | filesystem เดียว | authoritative lock ข้ามเครื่อง พร้อม owner/token/timeout/audit |
| Validation | SQLite/Python fixture model + Oracle adapter (`run-sql --compile/--explain`, Run Pack ที่คนอนุญาต) | Spark reference, row count/aggregate/row-level/parallel run ตาม BR และผูกผลเข้ากับ Gate |
| Delivery | simulation ZIP | Smart Import จริง + export หลัง import + Scenario/run evidence |
| Cutover | checklist template | อนุมัติ batch window, stop conditions, data/object recovery และผลซ้อม |

ต้องรักษาการแก้ K-E1…K7 และ patch ที่ wrapper setup_migrate.ps1 เดิมลงหลังแตก payload
การนำเฉพาะไฟล์จาก payload ชั้นในมาใช้จะทำให้การแก้หลัง setup ตกหล่น
ย้ายแม่แบบและ knowledge ส่วนที่มีค่าของงานเป็น template แทนการใช้ไฟล์เดียวแบบเติมค่าทับกัน

แนะนำเริ่มทดสอบกับหนึ่ง workflow จริงที่ทีมมี baseline ผ่านแล้ว ก่อนขยายไปทุกงาน
การทำ production adapters เป็นงานถัดไป ไม่อยู่ในความสามารถที่ simulator นี้อ้างว่าทำเสร็จ
