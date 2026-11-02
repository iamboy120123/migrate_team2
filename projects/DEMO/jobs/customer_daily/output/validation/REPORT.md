# Fixture comparison

SIMULATION ONLY. SQLite is not Spark or Oracle.

| Task | Strategy | Selected fixture rows | Fixture + rerun check |
|---|---|---|---|
| T001 | upsert | 2 | PASS |
| T002 | overwrite | 2 | PASS |

Append intentionally adds rows again; upsert and overwrite are stable for these fixtures.
