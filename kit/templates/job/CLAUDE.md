# {{PROJECT}}/{{JOB}} — Blendata → ODI (migrate_team2 kit {{KIT}})

อ่านไฟล์นี้ทุก session · กติกากลางอยู่ที่นี่ รายละเอียดอยู่ใน `.claude/rules/`, `.claude/skills/` และ `knowledge/`
ลำดับเมื่อกฎขัดกัน: `status/OPEN_DECISIONS.md` / `status/GATES.md` > ไฟล์นี้ + `.claude/rules/` > `knowledge/reference/`

## 1. งานนี้อยู่ในระบบไหน

- workspace root = `../../../..` (โฟลเดอร์ที่มี `workspace.json`) · คำสั่งทั้งหมดผ่าน `python ../../../../tools/workspace.py …`
- kit ล็อกไว้ใน `kit.lock.json` (รุ่น + SHA-256 + target snapshot) · ห้ามคัดลอกโค้ด kit ลงงาน ห้ามแก้ `.claude/**` และ `knowledge/reference/**` ที่ติดตั้งจาก kit (`check` จะ FAIL)
- `job.json` `mode=simulation` · `simulate` ทำงานออฟไลน์ด้วย SQLite + fixture — **ไม่ใช่** การพิสูจน์บน Spark / Oracle / ODI
- simulated review (`approve --simulation`) ไม่ใช่การอนุมัติของ SA · ไฟล์ `*.simulation.xml/zip` นำเข้า ODI ไม่ได้ · G4–G7 = NOT_EXECUTED

## 2. เครื่องมือที่มี / ยังไม่มี ใน kit {{KIT}}

| ใช้ได้แล้ว | คำสั่ง |
|---|---|
| ดูสถานะ / ตรวจหลักฐาน | `status` · `check` |
| รีวิวจำลอง + จำลองการโหลด | `approve --job {{PROJECT}}/{{JOB}} --reviewer <ชื่อ> --simulation` · `simulate --job {{PROJECT}}/{{JOB}}` |
| รัน SQL บน Oracle จริง (ต้องมีคนอนุญาตทุกแผน) | `db-status` · `run-sql --job {{PROJECT}}/{{JOB}} <pack/โฟลเดอร์/ไฟล์> --plan` → ถามคน → `--execute <แผน> --approved "<ชื่อ> <วันที่>"` · `--compile` · `--explain` · `--human` / `--record-human` |
| ซ้อม import lock | `import-lock` / `import-unlock --simulation` |
| Wiki: บทเรียน kit · ทีม · project · งาน | `wiki-step <01-06> --job {{PROJECT}}/{{JOB}}` · `wiki-search <คำ>` · `wiki-check` · ส่งบทเรียน generic เข้าทีม: `/kit-backport` (`kit-promote` — คนอนุมัติ) |

| ไม่มีในงานแบบ simulation นี้ |
|---|
| `scripts/**` ของงานจริง (converter, generators, ODI builder, Run Pack, checks, hooks) — มีเฉพาะงาน `mode=delivery` (`new-job --mode delivery` หรือ `import-job`) |
| `workspace.py new-round / handoff / release / set-mode / update-target / sync-kit / init-github` |

คำสั่ง `/…` และ agent ที่อ้างเครื่องมือที่ไม่มีในงานนี้จะมีป้าย ⚠️ ที่หัวไฟล์ — **ห้ามสร้าง ค้นหา หรือคัดลอก scripts เหล่านั้นมาเอง**
ทำเฉพาะส่วนที่เป็นการอ่าน วิเคราะห์ ถาม และเขียนเอกสาร แล้วบอกผู้ใช้ตรง ๆ ว่าขั้นไหนต้องทำในงาน delivery

## 3. AI กับฐานข้อมูล

คำว่า `db=human / ask / auto` ในคำสั่ง `/…` หมายถึงกติกาทีมใน `shared/team.json` → `db` (ดูด้วย `db-status`):
`ai_access=human` = คนรันทั้งหมด · `ai_access=ai` + `select_mode=ask` = ถามทุกแผน · `select_mode=auto` = SELECT ใน Run Pack รันต่อได้
งานนี้ตั้งให้คนรันเสมอได้ด้วย `"db_access": "human"` ใน `job.json`

- ทุกครั้ง: `run-sql … --plan` → ถามคนในแชทด้วยข้อความ ❓ (ตอบเป็นเลข) → ตอบ 1 `--execute <แผน> --approved "<ชื่อคน> <วันที่>"` · ตอบ 2 `--human <แผน>`
- exit 3 = ต้องขออนุญาต · ห้ามเลือกแทนคน ห้ามใส่ชื่อผู้อนุญาตเอง ห้ามแก้ไฟล์หลังได้รับอนุญาต
- DROP / TRUNCATE / DELETE-UPDATE ไม่มี WHERE: ให้คนพิมพ์ชื่อตารางในแชทก่อน แล้วใส่ใน `--confirm`
- ห้ามขอหรือรับรหัสผ่านในแชท · Spark / Blendata SQL และงานใน ODI Studio = คนทำเสมอ
- ผลอยู่ที่ `db_runs/` และ `status/DB_RUN_LOG.md` · ผล 0 แถวไม่นับว่าผ่าน · ผลฐานจริงไม่ใช่การผ่าน Gate

## 4. กฎ migration ที่ต้องทำตามเสมอ (ต้นฉบับใน rule / skill / knowledge)

1. As-Is: คงความหมายของ Spark SQL — ไม่ปรับ logic ทางธุรกิจ · ไม่แน่ใจให้ถามและบันทึกใน `status/OPEN_DECISIONS.md`
2. **overwrite: ห้ามเลือก DELETE หรือ TRUNCATE เอง** — ถาม I14 ทีละ task (`knowledge/reference/spark-to-oracle-sql.md` หัวข้อ overwrite เฉพาะ partition)
3. ก่อนแปลง SQL ที่อ่าน landing ต้องรู้ชนิดคอลัมน์จริง (all_tab_columns) · ผลของ Spark ขึ้นกับ `ansi.enabled`, `timeParserPolicy`, `escapedStringLiterals` → skill `spark-oracle-dialect`
4. SQL ใน ODI step: ไม่มี `;` ท้าย SQL ธรรมดา, PL/SQL จบ `END;`, ไม่มีบรรทัด `/`, ไม่มีอักขระนอก latin-1 → `.claude/rules/odi-step-sql.md`
5. SQL ที่ผ่าน Phase 4 แล้วห้ามถูกเขียนทับด้วยการ convert ซ้ำ — บันทึกการแก้ใน `status/PHASE4_REVIEW_LOG.md` เสมอ
6. Dev DB อาจไม่ใช่ 19c — feature ใหม่ต้องยืนยันบน 19c ก่อน cutover

## 5. ขอบเขตการแก้ไฟล์

- **ห้ามแก้:** `input/**` (governed input — แก้แล้ว review เดิมเป็น STALE), `kit.lock.json`, `.claude/**`, `knowledge/reference/**`, ไฟล์ที่ `simulate` สร้างใน `output/` (`check` ตรวจ hash)
- **แก้ได้:** `status/*.md` (ช่อง SA ห้ามติ๊กแทน), `knowledge/lessons-learned.md`, `knowledge/WORKFLOW.md`, `glossary-kit.md`, `.design/**`, `run_packs/**` ที่สร้างเอง
- `config/config.json`: แก้ได้เมื่อ SA สั่ง (fingerprint เปลี่ยน → ต้องรีวิวใหม่) · `db_mode` ใน config เป็นค่าของ simulator ต้องเป็น `human`
- ห้ามลบไฟล์ — แทนด้วยการเขียนทับหรือ backup `*.bak-YYYYMMDD`

## 6. Human-decide vs Agent-decide

| คนตัดสิน (บันทึก `status/OPEN_DECISIONS.md`) | agent ทำเองได้ |
|---|---|
| scope task, load strategy, overwrite, error handling | อ่าน / วิเคราะห์ / ร่างเอกสาร / สร้างแผน run-sql |
| schema, logical schema, context, ชื่อ project ODI | แก้ dialect ที่ไม่เปลี่ยนความหมาย (บันทึก review log) |
| การรัน SQL บนฐานจริง, retention, cutover, rollback, go-live | สรุปผลที่คนนำกลับมา |

ถามทีละข้อพร้อมตัวเลือกและ [แนะนำ] (`.claude/rules/one-at-a-time.md`, `ask-with-recommendation.md`) · อ่านไฟล์ก่อนถาม (`read-before-ask.md`)
