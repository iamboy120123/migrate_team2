# {{PROJECT}}/{{JOB}} — Blendata → ODI (migrate_team2 kit {{KIT}} · delivery)

อ่านไฟล์นี้ทุก session · ขั้นตอนหลักอยู่ที่ `knowledge/WORKFLOW.md` · กฎละเอียดใน `.claude/rules/`, `.claude/skills/`, `knowledge/reference/`
ลำดับเมื่อกฎขัดกัน: `status/OPEN_DECISIONS.md` / `status/GATES.md` > ไฟล์นี้ + `.claude/rules/` > `knowledge/reference/`

## 1. งานนี้อยู่ในระบบไหน

- งานจริง (`job.json` `mode=delivery`) · workspace root = `../../../..` · คำสั่ง workspace: `python ../../../../tools/workspace.py …`
- kit ล็อกไว้ใน `kit.lock.json` — `scripts/`, `.claude/`, `knowledge/reference/` ติดตั้งจาก kit และ**ห้ามแก้** (`check` FAIL, settings ปฏิเสธการแก้)
  เจอบั๊กของ kit: บันทึกใน `status/MIGRATION_STATUS.md` หัวข้อ "Kit — สิ่งที่แก้" แล้วแจ้งผู้ดูแล kit (แก้ใน `kit/` + ออกรุ่นใหม่) — ห้าม patch ในงาน
- Gate ของงานจริงอยู่ที่ `status/GATES.md` (`python scripts/checks/check_gate.py G<n>`) · Smart Import / งานใน ODI Studio = คนทำเสมอ

## 2. Pipeline (รันจากโฟลเดอร์งานนี้)

| Phase | คำสั่ง | ผล |
|---|---|---|
| 0 Pre-flight | `/preflight` → `python scripts/runpack/gen_preflight_pack.py` | `run_packs/rp00_preflight_*/` |
| 1-3 Extract + Convert | `python scripts/pipeline/extract_workflow.py` → `python scripts/pipeline/convert_sql.py` | `output/sql/raw/`, `output/sql/converted/`, `status/REVIEW_FLAGS.md` |
| 4 Review | `/review-sql` แล้วแก้ใน `output/sql/converted/` + บันทึก `status/PHASE4_REVIEW_LOG.md` | |
| 5a DML | `python scripts/pipeline/gen_dml.py` | `output/dml/` |
| 5b ODI export | `/inputs` (`scripts/checks/check_inputs.py`) → `python scripts/pipeline/build_odi_export.py` → `validate_odi_xml.py` | `output/odi_export/<package>.zip` |
| 6 DDL / DBA | `/gen-ddl` → `gen_ddl.py` + `gen_dba_prereq.py` | `output/ddl/`, `output/dba/` |
| 7 Validation | `/validation` → `python scripts/runpack/gen_validation.py` · `/compare-d2` | `output/validation/` |
| 8 Backfill / Cutover | `/cutover` → `gen_backfill.py` | `output/backfill/`, `status/CUTOVER_RUNBOOK.md` |
| Run Pack | `python scripts/runpack/gen_run_pack.py --pack rpNN` → รัน (ข้อ 3) → `python scripts/runpack/read_run_results.py --pack run_packs/<pack>` | `run_packs/<pack>/REPORT.md` |

แก้ SQL หรือ config แล้วต้อง regenerate จนถึง `validate_odi_xml.py` ผ่าน 0 error
**convert ซ้ำไม่เขียนทับ SQL ที่แก้หลัง convert (R-08):** ไฟล์ที่ถูกแก้จะถูกเก็บไว้ ผลใหม่อยู่ `output/sql/converted_machine/` และ flag ใหม่อยู่ `status/REVIEW_FLAGS.machine.md`
ต้องเทียบแล้วยกการแก้เอง · `--force` เขียนทับได้เมื่อ SA สั่งเท่านั้น

## 3. AI กับฐานข้อมูล (แทน `run_sql.py` ของ Migrate_ODI_Team2)

คำว่า `db=human / ask / auto` ในคำสั่ง `/…` = กติกาทีมใน `shared/team.json` → `db` (ดูด้วย `python ../../../../tools/workspace.py db-status`)
`ai_access=human` = คนรันทั้งหมด · `ai_access=ai` + `select_mode=ask` = ถามทุกแผน · `select_mode=auto` = SELECT ใน Run Pack รันต่อได้ · งานนี้ตั้งคนรันเสมอได้ด้วย `"db_access": "human"` ใน `job.json`

- `python ../../../../tools/workspace.py run-sql --job {{PROJECT}}/{{JOB}} <pack | ไฟล์> --plan` → ถามคนในแชท (ตอบเป็นเลข)
  → ตอบ 1 `--execute <แผน> --approved "<ชื่อคน> <วันที่>"` · ตอบ 2 `--human <แผน>` แล้ว `--record-human <แผน> --result "…"`
- `--compile` (SELECT แบบ WHERE 1=0) · `--explain` (EXPLAIN PLAN) · exit 3 = ต้องขออนุญาต · ห้ามเลือกแทนคน ห้ามขอรหัสผ่านในแชท
- DROP / TRUNCATE / DELETE-UPDATE ไม่มี WHERE (รวม UPDATE ที่มี WHERE แค่ใน subquery, ALTER … TRUNCATE PARTITION): ให้คนพิมพ์ชื่อตารางก่อน → `--confirm`
  PL/SQL ที่มี TRUNCATE / DROP / EXECUTE IMMEDIATE ระบบไม่รันให้ (คนรันเอง)
- ผล SELECT (ระบบรัน หรือคนรันใน DBeaver แล้ววาง CSV) อยู่ที่ `input/run_results/<pack>/` → `read_run_results.py` · log ที่ `status/DB_RUN_LOG.md`
- ORA error ที่ไม่อยู่ใน `KNOWN_ERRORS` ของ reader = **ห้ามเดาแก้** → `/diagnose`

## 4. กฎ ODI / migration ที่ต้องทำตามเสมอ

1. As-Is: คงความหมายของ Spark SQL · **overwrite: ห้ามเลือก DELETE หรือ TRUNCATE เอง** — ถาม I14 ทีละ task บันทึก `status/OPEN_DECISIONS.md`
2. SQL ใน step: ไม่มี `;` ท้าย SQL ธรรมดา, PL/SQL จบ `END;`, ไม่มีบรรทัด `/`, ไม่มีอักขระนอก latin-1 → `.claude/rules/odi-step-sql.md`
3. GlobalId: reuse จาก `_guid_keys.json` · ห้าม `--new-guid` เว้นแต่ SA สั่ง · Smart Import ครั้งเดียวตอนจบ (Overwrite) → skill `odi-smart-export`
4. ของครบก่อน build: `/inputs` ต้องขึ้น `[พร้อม]` ก่อนสร้าง package และก่อนบอกให้ import
5. ก่อนแปลง SQL ที่อ่าน landing ต้องรู้ชนิดคอลัมน์จริง · ผลของ Spark ขึ้นกับ `ansi.enabled`, `timeParserPolicy`, `escapedStringLiterals` → ยืนยันก่อนปิด Phase 4
6. Dev DB อาจไม่ใช่ 19c — feature ใหม่ต้องยืนยันบน 19c ก่อน cutover

## 5. ขอบเขตการแก้ไฟล์

- **ห้ามแก้:** `input/**/export_workflow.json`, `input/blendata/**`, `input/odi_reference/**`, `scripts/**`, `.claude/**`, `knowledge/reference/**`, `kit.lock.json`, `output/odi_export/_guid_*.json`, `PROJ_EXPORT.xml`
- **แก้ได้:** `output/sql/converted/*.sql` (Phase 4 + log), `config/config.json` (บอก SA ว่าแก้ field ไหน), `status/*.md` (ช่อง SA ห้ามติ๊กแทน), `knowledge/lessons-learned.md`, `WORKFLOW.md`, `.design/**`, `run_packs/**`
- ไฟล์อื่นใน `output/` = generate — แก้ที่ต้นทางแล้ว regenerate · ห้ามลบไฟล์ (เขียนทับหรือ backup `*.bak-YYYYMMDD`)

## 6. Human-decide vs Agent-decide

| คนตัดสิน (บันทึก `status/OPEN_DECISIONS.md`) | agent ทำเองได้ |
|---|---|
| scope task, load strategy, overwrite, error handling | regenerate / validate / สร้าง Run Pack และแผน run-sql |
| logical schema, context, ชื่อ project ODI, การรัน SQL บนฐานจริง | แก้ dialect ที่ไม่เปลี่ยนความหมาย (บันทึก review log) |
| retention, cutover, rollback, go-live, ติ๊ก Gate แบบ Manual | อ่านผล Run Pack และสรุป |

ถามทีละข้อพร้อมตัวเลือกและ [แนะนำ] (`.claude/rules/one-at-a-time.md`, `ask-with-recommendation.md`) · อ่านไฟล์ก่อนถาม (`read-before-ask.md`)
## 7. Wiki (ความรู้ของทีม)

- ก่อนเริ่มขั้น: `python ../../../../tools/workspace.py wiki-step <01-06> --job {{PROJECT}}/{{JOB}}` (หรือ `python scripts/ws/wiki.py --step <01-06>`) · ค้น: `/wiki <คำ>` · คำแนะนำต้องอ้าง `L#` / `LT#` / `SIM-L#`
- จบขั้น: บทเรียนใหม่ → `/lesson` (มีหลักฐาน) · ใช้ได้ทุกงาน → `/kit-backport` → `kit-promote` เข้าชั้นทีม `shared/knowledge` เมื่อผู้อนุมัติอนุมัติ (ห้ามอนุมัติแทน)

ยังไม่มีในชุดนี้: `workspace.py new-round / handoff / release / set-mode / update-target / sync-kit / init-github` และ import lock ข้ามเครื่อง (ใช้ช่องทางของทีมไปก่อน)
