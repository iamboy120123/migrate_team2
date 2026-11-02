# Fixture comparison

SIMULATION ONLY. SQLite is not Spark or Oracle.

| Task | Strategy | Selected fixture rows | Fixture + rerun check |
|---|---|---|---|
| T003 | append | 2 | PASS |

Append intentionally adds rows again; upsert and overwrite are stable for these fixtures.
