<!-- migrate-team-skill:start -->
## Blendata to ODI workspace skill

For workspace setup, Project/Job operations, simulated reviews, evidence checks and
import-lock rehearsals, use `blendata-odi-team` at
`.agents/skills/blendata-odi-team/SKILL.md` and read its references as needed.
Locate the workspace root before running commands. Read the relevant job's status,
config and `kit.lock.json` before changing that job.
Simulation jobs are offline: their XML/ZIP is not native ODI Smart Export and simulated
approvals or fixture checks never approve deployment. Delivery jobs (kit 0.3.0+) run the
kit's locked `scripts/`; never patch them in a job. Smart Import stays a human step.
Real Oracle SQL runs only through `tools/workspace.py run-sql` / `db-*` (docs/DATABASE.md):
show the plan, ask the person (numbered answer), then `--execute <plan> --approved`.
Never approve for a person, ask for passwords in chat or change the team db policy unasked.
Team lessons grow only via `kit-promote` after a named person approves the shown plan.
Preserve user instructions outside this setup-managed block.
<!-- migrate-team-skill:end -->
