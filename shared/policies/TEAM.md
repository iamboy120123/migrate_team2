# Team policy

- One job folder, branch and chat per migration; separate working directories for concurrent branches.
- The simulation runtime (`simulate`) is offline and never connects to databases or GitHub.
- Real Oracle access goes only through `tools/dbcore` (`db-*` / `run-sql`) under the team policy in
  shared/team.json "db" (default: people run SQL). Every run needs a displayed plan bound to file hashes and a named
  human approval; destructive statements need the table name typed again. Passwords are never stored or typed in chat.
- Delivery jobs (kit 0.3.0+) run the kit's locked scripts/; never patch them in a job — kit fixes go through a new
  kit release. Re-running convert must not overwrite Phase-4 reviewed SQL (R-08); Smart Import stays a human step.
- Team knowledge (shared/knowledge) is append-only and grows only through `kit-promote` with a named human approver
  listed in shared/approvers.json "knowledge_approvers"; AI never approves or adds approvers.
- Oracle results stay in the job's db_runs/ and DB_RUN_LOG.md; they never change G4–G7 or approve deployment.
- Each job pins a released kit archive and synthetic target snapshot by SHA-256.
- Kit changes use a separate review/release from migration changes.
- Input/config/pin changes invalidate the fingerprint-bound simulated review.
- A simulated review never represents an actual SA approval.
- A generated simulation bundle is never an ODI Smart Export or permission to deploy.
- Real import/comparison/cutover/go-live gates remain NOT_EXECUTED.
- Filesystem locking demonstrates one local shared lock directory only; it is not a distributed team lock service.
