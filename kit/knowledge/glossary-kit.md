# glossary-kit — ศัพท์กลาง (ใช้ทุกงาน)

ศัพท์ของ kit / ODI / Blendata ที่ใช้เหมือนกันทุกงาน · ศัพท์ธุรกิจของ project อยู่ที่ `projects/<P>/_project/glossary.md` · ของงานอยู่ที่ `knowledge/glossary.md`
เพิ่ม / แก้ผ่าน PR ของ kit · มีแหล่งที่มาทุกข้อ

| คำ | ความหมาย | ใช้ที่ | แหล่งที่มา |
|---|---|---|---|
| Smart Export | ไฟล์ export ของ ODI Studio ที่รวม object + Topology ที่อ้างถึง · kit อ่านค่าของ repository ปลายทางจากไฟล์นี้ | init ข้อ 7 · `shared/target/` | ODI 14c |
| Smart Import | การนำ Smart Export เข้า repository · ใช้ Overwrite กับ procedure / package ที่เปลี่ยน | ขั้น 05 · import-lock | ODI 14c · L2 |
| Logical Schema | ชื่อกลางที่ step ของ ODI ใช้ชี้ฐาน · จับคู่กับ Physical Schema ผ่าน Context | init ข้อ 8 · config.odi | ODI 14c |
| Context | ตัวเลือก environment (DEV / SIT / PROD) ที่ ODI ใช้จับคู่ Logical → Physical | init ข้อ 8 | ODI 14c |
| Scenario | package / procedure ที่ compile แล้วสำหรับรัน · generate ใน ODI Studio หลัง import (kit ไม่สร้าง) | ขั้น 05 | ODI 14c |
| work repository | schema ที่มีตาราง `SNP_*` ของ ODI (log การรัน · object) | import-lock · perf | ODI 14c · L3 |
| id_base | ช่วงเลข id ภายใน XML ของงาน = 90000 + เลขใบงาน × 1000 · กันชนกับงานอื่น | new-job | workspace |
| Run Pack | ชุดไฟล์ SQL ที่ต้องรันบนฐาน (pre-flight · ตรวจ · seed) · รันด้วย `run-sql` ตามกติกา AI กับฐานข้อมูล | ขั้น 03–06 | kit |
| landing table | ตารางที่ข้อมูลดิบถูกโหลดเข้ามารอก่อน job รัน | intake · new-job ข้อ 4 | kit |
| D1 / D2 / D3 | ระดับการเทียบผล: D1 รัน raw SQL บน Spark · D2 เทียบกับ Blendata จริง · D3 parallel run | ขั้น 06 | kit · L6 |
| gate (G0–G6) | ด่านตรวจของแต่ละขั้น · ผ่านเมื่อครบหลักฐาน + ✅ จากผู้อนุมัติ | ทุกขั้น | kit |
