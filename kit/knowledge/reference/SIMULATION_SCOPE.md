# Scope and evidence boundary

This kit demonstrates team isolation, version/target pins, stale-review detection,
limited SQL conversion, explicit load strategies, deterministic packaging and fixture checks.

The normalized workflow grammar supports explicit SELECT columns from one source,
UPPER/LOWER, IFNULL/COALESCE and CAST AS STRING. Unknown functions and unsupported
constructs are rejected. This is not a general Spark SQL parser or an Oracle compiler.

SQLite evaluates a portable projection on curated synthetic rows. A Python model
applies append, upsert or explicit unpartitioned overwrite and compares duplicate-sensitive
results for the first and second run. This is not execution on Spark, Oracle or ODI.

Oracle-shaped DML files are illustrative and have not been compiled against Oracle.
Generated XML uses MigrationSimulationPlan, not native ODI objects. Bundles explicitly
declare native_odi_smart_export=false and import_allowed=false.

G0/G1/G3 refer to offline simulation evidence, G2 to a fictional reviewer, and G4–G7
always remain NOT_EXECUTED. All issue numbers are local synthetic reservations.
