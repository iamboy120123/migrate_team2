# Synthetic business rules

SIMULATED REVIEW ONLY.

- BR-01 / T001: Exclude deleted customers, uppercase names, and replace NULL country with UNKNOWN; update by customer ID. (strategy: upsert)
- BR-02 / T002: Replace the complete synthetic active-customer snapshot; explicit full-table overwrite decision, no partitions. (strategy: overwrite)
