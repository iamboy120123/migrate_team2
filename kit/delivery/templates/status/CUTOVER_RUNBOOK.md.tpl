# CUTOVER RUNBOOK — {{WORKFLOW}} (Blendata → ODI)

Updated: {{DATE}} · ร่างโดย `/cutover` (agent `cutover-planner`) · **ผู้อนุมัติ: SA + Business** · ใช้โดย gate G7 (V9 ตรวจหัวข้อ Rollback / Go-No-go / Parallel run และช่อง TBD)

> ทุกช่อง `_(TBD)_` ต้องมีค่าจริงก่อน G7 · การตัดสินใจ (วันที่, retention, rollback criteria) มาจาก `status/OPEN_DECISIONS.md` ที่ SA ปิดแล้วเท่านั้น

## 1. ขอบเขตและผู้รับผิดชอบ

| รายการ | ค่า |
|---|---|
| ODI project / package | `{{PROJECT_CODE}}` / `{{PACKAGE_NAME}}` |
| Target schema | `{{WORK_USER}}` (Prod: _(TBD)_) |
| วัน/เวลา cutover | _(TBD)_ |
| T_snap (baseline ของ backfill) | _(TBD)_ |
| Retention ที่ต้อง backfill | _(TBD — Q retention)_ |
| ผู้รัน ODI / DBA / Blendata / Business sign-off | _(TBD)_ |

## 2. Pre-cutover checklist

| # | รายการ | หลักฐาน | สถานะ |
|---|---|---|---|
| P1 | G6 PASS (`python scripts/checks/check_gate.py G6`) | | ⬜ |
| P2 | DDL + DBA prerequisite รันใน Prod แล้ว | | ⬜ |
| P3 | Topology Prod: logical schema / context / data server | | ⬜ |
| P4 | Smart Import เข้า Prod (Overwrite) + Smart Export กลับมาเทียบ (G4 แบบ Prod) | | ⬜ |
| P5 | Backfill ครบ + reconcile (`output/backfill/06_reconcile_*`) ผลตรง | | ⬜ |

## 3. Parallel run

| รายการ | ค่า |
|---|---|
| จำนวนรอบ (N) | _(TBD)_ |
| เกณฑ์ผ่าน | L1 / L2 / L3 (`output/validation/`) ตรงกันทุกรอบ, D2 diff = 0 ยกเว้นส่วนต่างที่มี Q ปิดแล้ว |
| ผู้เทียบผล | _(TBD)_ |

## 4. Cutover steps

| # | เวลา | ขั้นตอน | ผู้ทำ | ตรวจผล |
|---|---|---|---|---|
| C1 | | หยุด schedule ของ Blendata workflow | | |
| C2 | | โหลด delta (`output/backfill/08_cutover_delta_oracle.sql`) | | |
| C3 | | เปิด schedule ODI (timezone ตาม Q schedule) | | |
| C4 | | ตรวจรอบแรก (session log + post-run capture) | | |

## 5. Go/No-go

| เกณฑ์ | Go ถ้า | No-go ถ้า |
|---|---|---|
| ผลรอบแรก | _(TBD)_ | _(TBD)_ |
| เวลาที่ใช้ | _(TBD)_ | _(TBD)_ |
| ผู้ตัดสิน | _(TBD)_ | |

## 6. Rollback

| # | trigger | ขั้นตอน | ผู้ทำ | เวลาสูงสุด |
|---|---|---|---|---|
| R1 | _(TBD)_ | ปิด schedule ODI | | |
| R2 | | ลบ/ย้อนข้อมูลที่ ODI เขียนหลัง T_cutover (_(TBD)_ วิธี) | | |
| R3 | | เปิด schedule Blendata กลับ | | |
| R4 | | แจ้งผู้เกี่ยวข้อง | | |

Rollback rehearsal (G7.M3): วันที่ _(TBD)_ · ผล _(TBD)_

## 7. หลัง go-live

- Hypercare _(TBD)_ วัน · ช่องทางแจ้งเหตุ (Q แจ้งเตือน) _(TBD)_
- Decommission Blendata workflow เมื่อ _(TBD)_
