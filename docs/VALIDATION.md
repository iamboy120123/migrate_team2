# ผลตรวจต้นแบบ — 2026-11-01 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Python ที่ใช้ตรวจบนเครื่องนี้ | 3.13.7 |
| Unit/integration suite | PASS — 34 tests (Setup/Wizard 14, team simulation 15, workspace skill 5) |
| SKILL.md validator | PASS — bundled quick_validate.py จาก skill-creator |
| Workspace skill Setup integration | PASS — PowerShell 5.1/7; step install-skill มีหลักฐานใน last-result.json |
| setup_workspace.ps1 | PASS — PowerShell 5.1 และ PowerShell 7 |
| Setup ใน workspace ที่มีงานแล้ว | PASS — ไฟล์งาน/ค่าทีม/target snapshot 76 ไฟล์คงเดิม |
| Wizard ภาษาไทย | PASS — ถาม 6 ข้อ, help, แก้คำตอบ, ยืนยัน, ยกเลิก และ EOF บน PowerShell 5.1/7 |
| NonInteractive หลังเพิ่ม wizard | PASS — ไฟล์งาน/ค่าทีม/target/ไฟล์อ้างอิง 77 ไฟล์คงเดิม |
| CLI smoke checks | PASS — 10 commands; expected lock-contention failure included |
| Demo customer_daily | SIMULATION_PASSED — upsert + overwrite |
| Demo order_daily | SIMULATION_PASSED — append และผลรันซ้ำ |
| Workspace integrity | PASS — 0 findings |
| Demo rerun | PASS |
| Final simulation import lock | FREE |
| Native ODI import / Oracle / Spark | NOT EXECUTED |
| GitHub Actions | มี workflow template; ยังไม่รันบน GitHub |
| Original migrate_team repository | Working tree clean; HEAD 4fff7e62d0d719f4b7d8e102bd88fe71bd813e77 |

ทดสอบกรณีปฏิเสธ: ไม่มีรีวิว, รีวิวหมดอายุหลัง input เปลี่ยน, reviewer ไม่อยู่ในรายชื่อจำลอง,
release ZIP หรือ target snapshot ถูกแก้, issue/ID ซ้ำ, path traversal, fixture ไม่ตรง,
ไม่มีข้อมูลทดสอบ, output ถูกแก้ย้อนหลัง, ผู้ถือ lock แข่งขันกัน, ผู้ปลดไม่ใช่เจ้าของ,
SQL นอกขอบเขต และ overwrite ที่ไม่มีการเลือกชัดเจน

ทดสอบเพิ่มว่า runtime ที่ตรึงไว้ยังทำงานจาก ZIP ได้แม้แก้ source runtime ปัจจุบันให้เสีย
และ release เดิมสร้างคืนจาก source/resources ที่ตรงกันได้แบบ byte-for-byte

Setup script ทดสอบการสร้าง workspace ใหม่ใน path ที่มีช่องว่าง การรันซ้ำโดยไม่เขียนทับค่าทีม/งาน
การรักษา custom target, -WhatIf ไม่สร้างไฟล์, การปฏิเสธปลายทางที่มีข้อมูลอื่น,
Python ที่ใช้ไม่ได้, target ที่ถูกแก้, งาน STALE และ relative path ที่อ้างตำแหน่ง PowerShell ถูกต้อง

Wizard อ้างรูปแบบจาก `Migrate_ODI_Team2/kit/setup_migrate.ps1` รุ่น 2.15.0 โดยไม่ได้เรียกหรือแก้ไฟล์อ้างอิง
ทดสอบชื่อภาษาไทย บันทึก confirmed answers/settings, เพิ่ม reviewer โดยคงชื่อเดิม,
แก้คำตอบด้วย e, รายละเอียด ?, ยกเลิก q/EOF โดยไม่สร้าง workspace หรือเปลี่ยน workspace เดิม,
และ optional Git init ที่ไม่มี commit/remote พร้อมรักษา Git ที่มีอยู่

ผล Setup ล่าสุด: `.cache/setup/last-result.json`
หลักฐานตรวจไฟล์เดิมคงอยู่: `.cache/setup/verification.json`
หลักฐานตรวจโหมดอัตโนมัติหลังเพิ่ม wizard: `.cache/setup/wizard-verification.json`
หลักฐานติดตั้ง skill โดยคงไฟล์งาน/ค่าทีม/target/release/ไฟล์อ้างอิง 78 ไฟล์: `.cache/setup/skill-verification.json`

Skill ทดสอบการติดตั้งใหม่ การรันซ้ำโดยไม่เขียนไฟล์ซ้ำ การอัปเดตจาก source,
การรักษาข้อความ AGENTS.md ที่ทีมเพิ่มเอง รวม UTF-8 BOM/CRLF และการหยุดเมื่อ skill หรือ managed block
ถูกแก้ในปลายทาง การติดตั้งไม่มีการเขียนโฟลเดอร์ Codex ส่วนตัว และไม่แก้ pinned runtime release
PyYAML สำหรับตัวตรวจเอกสาร (เดิมอยู่ `.cache/skill-validation`, ลบแล้ว 2026-11-02) ไม่ใช่ dependency ของ runtime/Setup — ตรวจซ้ำได้ด้วย `pip install pyyaml` ชั่วคราว

หลักฐาน CLI: `cli-verification.json`

## Oracle adapter + Setup ข้อ 7–8 — 2026-11-02 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Unit/integration suite | PASS — 47 tests (เดิม 34 + dbcore 11 + Setup Oracle 2) บน Linux, Python 3.13, PowerShell 7.4 |
| dbcore บน Python 3.11 | PASS — 11 tests |
| kit 0.1.0 release / งาน DEMO | ไม่เปลี่ยน — `check` PASS 0 findings; ไม่มีไฟล์ใน `kit/` ถูกแก้ |
| SKILL.md validator | PASS — quick_validate.py |
| python-oracledb จริง (thin) | ต่อ host ที่ไม่มีอยู่ → error ภาษาไทยและบันทึก NOT-CONNECTED; ยังไม่ได้ทดสอบกับฐาน Oracle จริง |

ทดสอบด้วย oracledb จำลอง: ค่าเริ่มต้น human ไม่ต่อฐาน · ไฟล์เชื่อมต่อไม่มีรหัสผ่านและปฏิเสธ SYS/SYSTEM ·
แผนต้องมีผู้อนุญาต (exit 3) · split user ใช้ READ ONLY และไม่ commit · ไฟล์ถูกแก้หลังแผนถูกปฏิเสธ ·
TRUNCATE ต้องยืนยันชื่อตารางตรง · ไฟล์นอกงาน / SNP_* / Blendata ไม่รัน · select_mode และ job override ·
--compile เขียน db_runs/verify โดย fingerprint และ `check` ไม่เปลี่ยน · --record-human · ไม่มีรหัสผ่านและไม่มี Terminal → ไม่ถาม
Setup: wizard ข้อ 7–8 (ai + connection) ไม่บันทึกรหัสผ่าน · NonInteractive ปฏิเสธ -DbHost ที่ไม่มี -DbAccess ai ·
db-test ล้มเหลวเป็น WARN · รันซ้ำคงกติกาและการเชื่อมต่อ · ปฏิเสธ SYSTEM

ข้อสังเกตจากการทดสอบบน Linux: release ZIP ของ kit 0.1.0 สร้างคืนแบบ byte-for-byte ได้เฉพาะ zlib รุ่นเดียวกับ
เครื่องที่ freeze (Windows Python 3.13) — แก้แล้วด้วย ADR-007 ด้านล่าง

## Release store (ADR-007) — 2026-11-02 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Unit/integration suite บน Linux ด้วย release 0.1.0 ตัวเดิมจาก Windows (ไม่ freeze ใหม่) | PASS — 52 tests (เดิม 47 + kitstore 5) · ก่อนแก้ Setup tests ล้ม 10 รายการที่ขั้น freeze-kit |
| ลบ `.cache/kit` แล้ว `check` / `freeze-kit` | PASS — คืน `migrate_kit-857d5c89….zip` จาก `kit/releases/0.1.0.zip` |
| kitstore + dbcore บน Python 3.11 | PASS |
| กรณีปฏิเสธ | store ถูกแก้ · cache เสีย · source เปลี่ยนแต่ version เดิม (ยังได้ "Bump kit version") · publish ทับรุ่นเดิมด้วยไฟล์อื่น · version ไม่ถูกรูปแบบ |

## Regression baseline SS_ESIM (W-12) — 2026-11-02 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Capture | 357 ไฟล์ 7 ชั้น · `tests/regression/ss_esim/baseline.zip` (ไม่ขึ้น Git) + `BASELINE.json` |
| Replay ด้วย scripts ของงาน (2.15.0 + patch) | PASS — extract 11/11, convert 10/10, gen_dml 12/12, gen_ddl 3/3, gen_dba 3/3, build_odi_export 24/24 |
| Replay ด้วย scripts ก่อน patch (`*.bak-*`) | FAIL ที่ gen_ddl, gen_dba_prereq, build_odi_export — ยืนยันว่า patch ในงานจำเป็น (R-01) |
| Unit/integration suite | PASS — 57 tests (เดิม 52 + regression 5) บน Python 3.13; regression ผ่านบน 3.11 |

ข้อค้นพบ: converter ต้องแก้ใน Phase 4 อีก 4/10 task · รัน `convert_sql.py` ซ้ำจะเขียนทับ SQL ที่ review แล้ว ·
DML ที่คนเขียนเอง 2 ไฟล์ · patch ในงานหลัง sync 16 ไฟล์ที่ยังไม่ backport — รายละเอียด `tests/regression/ss_esim/README.md`

## kit 0.2.0 — ความรู้ + AI context (W-01/W-02) — 2026-11-02 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Port | 69 ไฟล์ (`.claude` 48 + knowledge 21) · ป้าย ⚠️ 37 ไฟล์ใน `.claude` · settings.json (hooks) ยังไม่นำมา |
| Release 0.2.0 | SHA-256 `8525537c…08b7f9` · ZIP_STORED · freeze ซ้ำบน Python 3.11 / 3.13 (zlib ต่างกัน) ได้ SHA เดียวกัน · `kit/releases/0.2.0.zip` |
| new-job (0.2.0) | ติดตั้ง `.claude` + `knowledge` 68 ไฟล์ล็อก · CLAUDE.md ใหม่ · approve + simulate + check PASS |
| แก้ไฟล์ที่ล็อก | `check` FAIL "Kit AI context/knowledge modified" · แก้ lessons-learned / CLAUDE.md ได้ |
| งาน DEMO (0.1.0) | ไม่เปลี่ยน · `check` PASS |
| Unit/integration suite | PASS — 63 tests (เดิม 57 + ai_context 6) บน Python 3.13 · ai_context / team simulation ผ่านบน 3.11 |

## kit 0.3.0 — delivery mode (W-04 + R2) — 2026-11-02 (Asia/Bangkok)

| รายการ | ผล |
|---|---|
| Vendored scripts | 43 ไฟล์จาก SS_ESIM (2.15.0 + patch) · แก้ 8 ไฟล์ (R-08 convert guard, run-sql แทน run_sql.py, ข้อความ) · ไม่รวม dbx/run_sql/run_pack |
| Regression replay ด้วย `kit/delivery/scripts` | PASS 9/9 — extract 11/11, convert 10/10, gen_dml 12/12, gen_ddl 3/3, gen_dba 3/3, build_odi_export 24/24, preflight pack 7/7, rp01 pack 20/20, REPORT.md 1/1 |
| import-job SS_ESIM แล้วรันทั้ง pipeline ในงาน | ทุกขั้น exit 0 · SQL ที่ review 4 ไฟล์ไม่ถูกทับ · G3 verdict ตรงกับ scripts เดิมของงาน · `check` PASS |
| hooks selftest ในงาน delivery | 55/55 |
| แก้ `scripts/` ในงาน | `check` FAIL "Kit-installed file modified" |
| Unit/integration suite | PASS — 68 tests (เดิม 63 + delivery 3 + ai_context/regression ปรับ) · delivery + ai_context ผ่านบน Python 3.11 |

## Independent review + kit 0.3.1 — 2026-11-02 (Asia/Bangkok)

รีวิวแยก (agent ที่ไม่ได้เขียนโค้ด) พบ 12 ข้อ + 1 ช่องว่าง — แก้ทั้งหมดและมี test กำกับ:

| # | เรื่อง | แก้ |
|---|---|---|
| 1 | Oracle DML ที่มีคำว่า Blendata ในหัวไฟล์ถูกมองเป็น Spark (ไม่รัน) | รู้จาก Blendata เฉพาะชื่อไฟล์/หัวไฟล์ที่ระบุ |
| 2 | UPDATE ที่ WHERE อยู่ใน subquery / ข้อความ, ALTER … TRUNCATE PARTITION, PL/SQL EXECUTE IMMEDIATE ไม่ต้องยืนยัน | ตรวจ WHERE ระดับคำสั่ง · PL/SQL dynamic DDL = คนรันเอง |
| 3 | แก้ไฟล์แผน `.dbx/plans` แล้วรัน SQL ที่ถูกแก้ได้ | ตอนรันสร้างคำสั่งใหม่จากไฟล์ที่อนุญาตและเทียบแผน/รหัสแผน |
| 4 | hint `/*+ */` หาย · string หลายบรรทัดที่มี `--` · PL/SQL ท้ายไฟล์เสีย `END;` | ตัว strip ใหม่ (อ่านข้ามบรรทัด เก็บ hint) |
| 5 | db-test รายงานผลเก่าว่าต่อได้ | ลบ ping.csv ก่อน · ไม่ได้รันจริง = exit 1 |
| 6 | id_base ของงานที่ import ไม่ถูกตรวจ / ช่วงทับกัน | ตรวจช่วงทับตอนสร้าง + ใน check |
| 7 | แก้ script แล้วเขียน hash ใหม่ลง kit.lock ผ่าน check · ไฟล์เพิ่มใน .claude ไม่ถูกจับ | check สร้างไฟล์ที่คาดจาก release เอง + หาไฟล์เกิน |
| 8 | kit/releases/<v>.zip เสียแต่เครื่องที่มี cache ไม่รู้ | ตรวจ store ทุกครั้ง |
| 9 | สร้างงาน delivery ล้มแล้วเหลือโฟลเดอร์ครึ่ง ๆ | ลบเองเมื่อล้ม |
| 10 | regression ผูกกับ pack ของ SS_ESIM | ขั้น Run Pack มาจาก pack ที่งานมีจริง |
| 11 | convert ซ้ำล้าง REVIEW_FLAGS ที่ตัดสินแล้ว | เก็บไว้เมื่อมี RESOLVED/WAIVED/… |
| 12 | wizard: ตั้งการเชื่อมต่อ → แก้คำตอบเป็น "ภายหลัง" แล้ว Setup ล้ม | ล้างค่าที่ค้าง |
| + | ผล run-sql ของงาน delivery ไป db_runs แต่ reader อ่าน input/run_results | งาน delivery เขียนที่ input/run_results |

ผล: 76 tests PASS (Linux, Python 3.13, PowerShell 7.4) · release 0.3.1 `6b54f74c…` reproducible (3.11/3.13) · replay SS_ESIM ด้วย kit scripts PASS

ข้อจำกัด: การผ่านหมายถึงการตรวจ workflow จำลองและ synthetic fixtures เท่านั้น
ไม่ได้ยืนยันว่า Oracle-shaped DML compile ผ่าน Oracle หรือสร้าง native ODI objects ได้

## kit 0.4.0 — Wiki และบทเรียนของทีม — 2026-11-02 (Asia/Bangkok)

| ตรวจอะไร | ผล |
|---|---|
| `wiki-search` / `wiki-step` / `wiki-check` จาก root (งาน simulation + delivery) | PASS — เห็นชั้นทีม `shared/knowledge` (SIM-L01–03) |
| `scripts/ws/wiki.py` ที่ติดตั้งในงาน delivery 0.4.0 | PASS — เห็นชั้นทีมเช่นกัน (engine เดียว) |
| Wiki rules ใน `check` | บทเรียนทีมไม่มีหลักฐาน → `wiki:` FAIL · แถว legacy ของ kit ที่ไม่มีช่องหลักฐานไม่ FAIL (เดิม 68 ERROR → 0) |
| `kit-promote` | แผน exit 3 · ผู้อนุมัติไม่อยู่ในรายชื่อ / plan id ไม่ตรง / ไม่มีวันที่ → ไม่เขียนอะไร · อนุมัติแล้ว → LT1 + ledger · promote ซ้ำ / ไม่ generic / แถวของ kit / K# → ปฏิเสธ |
| ประวัติชั้นทีมโดยไม่มี git | ลบ LT# → `check` FAIL · แก้ไม่มีหมายเหตุวันที่ → WARN |
| ชุดทดสอบทั้งหมด | 82 tests PASS (รวม `tests/test_wiki.py` 6 ข้อ) · release 0.4.0 `c5546177…` · replay SS_ESIM ด้วย kit scripts PASS |
