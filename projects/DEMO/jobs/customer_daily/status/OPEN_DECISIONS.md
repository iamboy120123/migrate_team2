# Decisions — customer_daily

SIMULATION ONLY. No real SA sign-off.

The synthetic sample explicitly selects append/upsert/full-table overwrite per task.
The overwrite fixture has no partitions and has an explicit `truncate_all` demo decision.
Unknown functions, partition overwrite and NULL merge keys require review and are rejected.

Real migration must separately confirm schema qualification, Spark configuration,
all source/target types, overwrite semantics, ODI topology and import overwrite behavior.
