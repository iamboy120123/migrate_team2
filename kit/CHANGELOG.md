# Changelog

## 0.4.0 — 2026-11-02 · Wiki and team knowledge

- **Root Wiki commands** (`tools/wikicmd.py`): `wiki-search`, `wiki-step <01-06> --job`, `wiki-check`, for every job mode and pinned kit;
  `check` now includes the Wiki rules (prefixed `wiki:`). Engine is the kit's own `delivery/scripts/ws/wiki.py` (one implementation).
- **Team layer** `shared/knowledge/` (between kit and project): searched and ranked by `wiki-step`; SIM-L01–03 kept with their numbers in
  the standard lesson table. Evidence is required for team lessons, new job lessons and kit rows whose table has an evidence column
  (legacy kit sections without one no longer fail). Duplicate ids fail.
- **`kit-promote`** (lessons only): plan bound to content (`plan id`, exit 3) → named approver in `shared/approvers.json`
  `knowledge_approvers` → `--plan-id --approved` writes `LT#` + ledger `PROMOTIONS.json`. Refuses lessons without evidence/tag/"generic",
  kit-shipped rows, secrets and repeats. Ledger protects history without git. Script fixes (K#) stay a kit release. ADR-010.
- AI context: `/wiki`, `/lesson`, `/next-step` step 0 use the root commands (no banner in simulation jobs any more); `/kit-backport`
  rewritten for kit-promote; job `CLAUDE.md` templates list the Wiki.
- Jobs pinned to 0.1.0–0.3.1 are unchanged; they use the team layer through the root commands.


## 0.3.1 — 2026-11-02 · review fixes

- `check` rebuilds the expected kit-installed files from the pinned release (a patched file whose hash was also written into
  `kit.lock.json` is still caught) and reports extra files in kit-owned folders (`.claude/*`, `scripts/`, `knowledge/reference/`).
- ODI id ranges: new/imported jobs may not overlap another job's range (`|a-b| < ids.step`); import refuses `id_base` ≤ 0;
  `check` reports overlaps, not only exact duplicates.
- A failed `new-job --mode delivery` / `import-job` removes its half-created folder.
- `convert_sql.py` also keeps `status/REVIEW_FLAGS.md` when it holds decisions (RESOLVED / WAIVED / ACCEPTED / DONE).
- Delivery job template: Run Pack results from `run-sql` land in `input/run_results/<pack>/` (read by `read_run_results.py`).

## 0.3.0 — 2026-11-02 · delivery mode

- **Delivery jobs** (`new-job --mode delivery`, `import-job --from <Migrate_ODI_Team2 job>`): the full production runtime of
  Migrate_ODI_Team2 2.15.0 (+ the 8 SS_ESIM job patches) — extract, convert, check_sql, gen_dml/ddl/dba/backfill, native ODI
  Smart Export builder, validate, Run Pack generators + `read_run_results`, Spark reference / compare, Gates (`check_gate`,
  `verify_all`), hooks — ships in the release (`delivery/`) and is installed into the job as locked `scripts/`.
- Proven by regression: `tools/regression.py replay --name ss_esim --scripts kit/delivery/scripts` reproduces SS_ESIM 9/9 steps
  (pipeline, ODI ZIP + GUIDs, preflight/rp01 packs, REPORT.md).
- **R-08 fixed:** `convert_sql.py` never overwrites SQL edited after convert (Phase 4); new output → `output/sql/converted_machine/`,
  flags → `status/REVIEW_FLAGS.machine.md`; `--force` only on SA request.
- SQL runs only via `tools/workspace.py run-sql` (dbx/run_sql/run_pack are not shipped). Delivery `.claude/settings.json` (hooks +
  permissions) denies edits to `scripts/`, `.claude/`, `knowledge/reference/`, `kit.lock.json`.
- AI context banners are rendered per job mode (simulation: tools missing · delivery: only unsupported workspace commands).
- Simulation mode unchanged; `simulate` / simulated review / lock rehearsal refuse delivery jobs. 0.1.0 / 0.2.0 jobs untouched.
- Not yet: config wizard from Smart Export (fill `config.odi.*` by hand or from `read_smart_export.py`), new-round/handoff,
  cross-machine import lock and real approvals (R4).

## 0.2.0 — 2026-11-02

- Knowledge (Migrate_ODI_Team2 kit 2.15.0 reference + SS_ESIM lessons/WORKFLOW) ships in the release under `knowledge/`.
- Claude AI context (31 commands, 10 agents, 8 rules, 2 skills, 1 workflow) from the SS_ESIM job (2.15.0 + job patches)
  ships under `ai/claude/`; references to tools not yet in this kit carry a ⚠️ banner (`ai/claude/SOURCE.json`).
- `new-job` installs `.claude/` + `knowledge/` rendered for the job and a new job `CLAUDE.md` (no more "Never connect to Oracle";
  Oracle goes through `run-sql`). Locked files are recorded in `kit.lock.json` → `ai_context`; `check` fails if they change.
- Release archive is ZIP_STORED: rebuilds byte-for-byte on any machine (ADR-007).
- Simulation runtime unchanged. Jobs pinned to 0.1.0 keep their release and are not touched.
- Not yet: converter / generators / ODI builder / Run Pack generator / hooks (later kit).

## 0.1.0 — 2026-11-01

- Central package and deterministic pinned ZIP runtime/resources.
- Shared synthetic target snapshots, job fingerprints and stale-review blocking.
- Two example jobs covering upsert, explicit overwrite and non-idempotent append.
- Illustrative Oracle DML, non-importable XML/ZIP and fixture/rerun comparison.
- Local exclusive import-lock rehearsal, integrity checks and team dashboard.
- Tests for shared references, release pinning, tampering, competing locks and failure cases.
- No production integration, database connection, GitHub operation or native ODI export.
