# Regression baseline — SS_ESIM (W-12)

Baseline ของงานจริง `SS_ESIM/ss_esim_landing_to_discovery` จาก Migrate_ODI_Team2 (kit 2.15.0)
ใช้พิสูจน์ว่าการย้าย runtime เข้า `migrate_kit` 0.2.0 ให้ผลเท่าเดิมทีละไฟล์

| รายการ | ค่า |
|---|---|
| ต้นทาง | `D:\Projects\Blendata_To_ODI\Migrate_ODI_Team2\projects\SS_ESIM\jobs\ss_esim_landing_to_discovery` |
| หลักฐานว่าผลถูก | rp_compile 10/10 ไม่มี error · S7a seed OK (landing 30/30) · S7c cleanup OK บน DEV (2026-10-29/30) · G2.M1 SA 2026-10-29 |
| ไฟล์ | `BASELINE.json` (ขึ้น Git: path, ขนาด, SHA-256, provenance — ไม่มีเนื้อหา) · `baseline.zip` (**ไม่ขึ้น Git**) |
| เครื่องมือ | `python tools/regression.py capture | verify | replay` |

## ชั้นข้อมูลใน baseline

| ชั้น | เนื้อหา | ใช้ทำอะไร |
|---|---|---|
| input | Blendata export, ไฟล์ทดสอบ, d1 seeds, all_tab_columns, Smart Export อ้างอิง, config | input ของ pipeline |
| machine | ผลของ extract + convert ล้วน ๆ (สร้างใหม่ตอน capture) อยู่ใต้ `_machine/` | เกณฑ์ของ converter ที่จะ port (ต้องตรง 100%) |
| reviewed | converted SQL หลัง Phase 4 + review logs + DML ที่คนเขียนเอง 2 ไฟล์ | สิ่งที่คอมไพล์ผ่านบน DEV (เป้าหมายเชิงความหมาย) |
| derived | DML / DDL / DBA / ODI Smart Export ที่สร้างจาก reviewed | เกณฑ์ของ gen_* และ ODI builder |
| runpack | Run Pack ที่สร้างแล้ว | เกณฑ์ของ Run Pack generator (W-04) |
| evidence | ผลรัน, verify, Spark D1, DB_RUN_LOG, GATES | หลักฐานว่า baseline ถูก |
| provenance | scripts + `.claude` ที่งานใช้จริง (2.15.0 + patch ในงาน) + `.ws_kit.json` | ต้นฉบับสำหรับ port (R-01) |

เทียบไฟล์หลังปรับ: CRLF→LF และปิด timestamp ตอนสร้าง / `exportKeySalt` ในชั้น machine และ derived เท่านั้น
วันที่ในข้อมูลทดสอบและ Run Pack ไม่ถูกปิด

## ผลตอน capture (2026-11-02)

- **Replay ด้วย scripts ของงานเอง: PASS ทุกขั้น** — extract 11/11, convert 10/10 (machine), gen_dml 12/12, gen_ddl 3/3,
  gen_dba_prereq 3/3, build_odi_export 24/24 (รวม Smart Export ZIP และ GUID) → pipeline deterministic ยกเว้น timestamp/salt
- **Review delta 4/10 task:** converter ยังทิ้ง Spark-ism / ความหมายต่างไว้ และ Phase 4 แก้เองใน 030000, 090000 (`true` → `'TRUE'`),
  020000 (boolean compare), 040000 (`regexp_extract/reverse/split` → `REGEXP_SUBSTR`, `to_date` → `TRUNC`, `NULLS FIRST`, escape regex)
- **รันซ้ำ `convert_sql.py` เขียนทับ SQL ที่ review แล้ว** — ถ้ามีคนรันซ้ำในงานจริง การแก้ Phase 4 จะหาย ต้องแก้ใน kit 0.2.0
- **Manual output 2 ไฟล์:** DML ของ task ที่ไม่ใช่ SQL (080000 cleanup, 999999 placeholder) และ entry `"manual": true` ใน `output/dml/_manifest.json`
- **Patch ในงานหลัง sync 16 ไฟล์** (scripts 8: check_inputs, pre_delivery_gate, review_report, verify_all, build_odi_export,
  gen_dba_prereq, gen_ddl, gen_design_docs · `.claude` 8) แต่ `kit/CHANGES-ws.md` ว่าง = ยังไม่ backport
  Replay ด้วย scripts รุ่นก่อน patch (`*.bak-*`) **FAIL** ที่ gen_ddl, gen_dba_prereq และ build_odi_export → ยืนยัน R-01

## วิธีใช้

```powershell
# ตรวจว่า baseline.zip ตรงกับ BASELINE.json
python tools/regression.py verify --name ss_esim

# รัน pipeline อ้างอิงจาก baseline (scripts ในงาน) แล้วเทียบ
python tools/regression.py replay --name ss_esim

# เทียบกับ scripts ชุดอื่น เช่น adapter ของ kit 0.2.0 (โฟลเดอร์ที่มี scripts/ แบบเดียวกัน)
python tools/regression.py replay --name ss_esim --scripts <folder> --keep

# capture ใหม่ (เมื่องานต้นทางเปลี่ยนรอบและผ่านหลักฐานบน DEV แล้วเท่านั้น)
python tools/regression.py capture --job "<job folder>" --name ss_esim --source-label "<path>" --note "<หลักฐาน>"
```

`tests/test_regression.py` จะ verify + replay อัตโนมัติเมื่อมี `baseline.zip` ในเครื่อง ถ้าไม่มีจะ skip
ต้องใช้ Python 3.11+ (scripts ของ 2.15.0)

## ข้อมูลอ่อนไหว

ข้อมูลทดสอบเป็นข้อมูลสังเคราะห์ (`gen_esim_testdata.js`, ICCID `SAT*`) แต่ baseline มี metadata ของลูกค้า:
ชื่อ schema / ตาราง DEV, Smart Export ของ repository DEV, all_tab_columns, business logic SQL และ config ที่มีชื่อผู้ใช้ GitHub
จึงไม่ขึ้น Git (`.gitignore`: `tests/regression/*/baseline.zip`) — เก็บใน share ของทีมและตรวจด้วย SHA-256 ใน BASELINE.json
ไม่ได้ mask เพราะการเปลี่ยนชื่อจะทำให้เทียบผลกับ converter ไม่ได้ (ตัดสินใจเพิ่มเติม: D-07)
