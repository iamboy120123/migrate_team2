# 02 — Architecture: As-Is vs To-Be

Workflow: `{{WORKFLOW}}` · Updated: {{DATE}}

## 1. As-Is (Blendata)

```mermaid
flowchart LR
  SRC[Source / ingestion] --> LND[({{LANDING_TABLE}})]
  LND --> BLD[Blendata workflow<br/>{{WORKFLOW}}<br/>Spark SQL tasks]
  BLD --> TGT[(Target tables)]
  BLD --> ST[(workflow status / checkpoint)]
```

| รายการ | ค่า | หมายเหตุ |
|---|---|---|
| Scheduler | _(เติม — cron จาก manifest: ดู 04_task_mapping)_ | |
| Engine | Spark SQL (Blendata) | |
| Landing | `{{LANDING_TABLE}}` | retention: _(Q ใน OPEN_DECISIONS)_ |
| Downstream consumer | _(เติม)_ | |

## 2. To-Be (ODI {{ODI_VERSION}} / Oracle 19c)

```mermaid
flowchart LR
  SRC[Source / ingestion] --> LND[({{WORK_USER}}.{{LANDING_TABLE}})]
  subgraph ODI[ODI — {{PROJECT_CODE}}]
    VAR[Variables<br/>v_max_partition / v_lag_minutes] --> PKG[Package {{PACKAGE_NAME}}]
    PKG --> PRC[Procedures<br/>1 task = 1 procedure]
  end
  LND --> VAR
  PRC -->|ELT pushdown<br/>{{LOGICAL_SCHEMA}} / {{CONTEXT_CODE}}| TGT[({{WORK_USER}} target tables)]
  PRC --> ST[(status / checkpoint)]
```

| องค์ประกอบ | ค่า |
|---|---|
| ODI project / package | `{{PROJECT_CODE}}` / `{{PACKAGE_NAME}}` |
| Logical schema / context | `{{LOGICAL_SCHEMA}}` / `{{CONTEXT_CODE}}` |
| Data server login (ต้องเป็น) | `{{WORK_USER}}` |
| Scenario / schedule | _(เติม — ODI Agent schedule)_ |

## 3. ความต่างที่ต้องรู้ (As-Is → To-Be)

| เรื่อง | Blendata (Spark) | ODI / Oracle | ผลกระทบ |
|---|---|---|---|
| empty string | `''` ≠ NULL | `''` = NULL | เงื่อนไข `= ''` ต้องแปลงเป็น `IS NULL` |
| overwrite | `INSERT OVERWRITE` | `TRUNCATE` + `INSERT` (execute immediate) | ไม่ atomic — ดู ADR |
| precheck | task SQL | ODI Variable refresh | ดู ADR-002 |
| encoding ของ step | UTF-8 | ISO-8859-1 ใน Smart Export | ห้ามภาษาไทยใน SQL |

## 4. Integration / dependency

_(เติม: ระบบต้นทาง, ปลายทาง, external table, DB link)_
