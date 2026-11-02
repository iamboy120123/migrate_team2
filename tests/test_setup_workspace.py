"""Exercise the user-facing setup script, including Windows PowerShell 5.1."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kit/src"))
from migrate_kit import workspace as W
from migrate_kit.runtime import run
from migrate_kit.storage import file_map, read, write

SHELLS = [path for name in ("powershell", "pwsh") if (path := shutil.which(name))]
bundled_pwsh = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
if bundled_pwsh.is_file() and str(bundled_pwsh).lower() not in [path.lower() for path in SHELLS]:
    SHELLS.append(str(bundled_pwsh))


@unittest.skipUnless(SHELLS, "Requires PowerShell 5.1 or 7")
class SetupWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-setup-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.cleanup_temp)

    def cleanup_temp(self):
        path = Path(self.temp.name).resolve()
        if not path.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not path.name.startswith("migration-setup-test-"):
            raise RuntimeError("Refusing recursive cleanup outside the allocated setup-test directory")
        self.temp.cleanup()

    def setup_workspace(self, destination, *args, shell=None, expected=0):
        command = [shell or SHELLS[0], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(ROOT / "setup_workspace.ps1"), "-NonInteractive", "-WorkspaceDir", str(destination), *map(str, args)]
        result = subprocess.run(command, cwd=self.root, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(result.returncode, expected, result.stdout + "\n" + result.stderr)
        return result.stdout + result.stderr

    def test_fresh_setup_and_repeat_on_each_available_powershell(self):
        for index, shell in enumerate(SHELLS):
            with self.subTest(shell=shell):
                destination = self.root / f"fresh workspace {index}"
                self.setup_workspace(destination, "-PythonExecutable", sys.executable, shell=shell)
                self.assertTrue(read(destination / ".cache/setup/last-result.json")["success"])
                self.assertEqual(list(destination.glob("projects/*/jobs/*/job.json")), [])
                self.assertTrue((destination / "STATUS.html").exists())
                self.assertTrue((destination / "setup_workspace.ps1").exists())
                self.assertFalse((destination / ".git").exists())
                self.assertTrue((destination / ".agents/skills/blendata-odi-team/SKILL.md").is_file())
                self.assertTrue((destination / "AGENTS.md").is_file())
                self.assertTrue((destination / "registry/workspace_skill.json").is_file())
                self.assertIn("install-skill", [row["step"] for row in read(destination / ".cache/setup/last-result.json")["steps"]])
                team_path = destination / "shared/team.json"
                team = read(team_path); team["keep_this_setting"] = "original"
                write(team_path, team)
                marker = destination / "projects/keep.txt"
                marker.write_text("existing content")
                prior = read(destination / "shared/target/current.json")
                output = self.setup_workspace(destination, "-PythonExecutable", sys.executable, shell=shell)
                self.assertIn("Preserved verified target", output)
                self.assertEqual(read(team_path)["keep_this_setting"], "original")
                self.assertEqual(read(destination / "shared/target/current.json"), prior)
                self.assertEqual(marker.read_text(), "existing content")

    def test_whatif_creates_nothing(self):
        destination = self.root / "plan only"
        output = self.setup_workspace(destination, "-WhatIf")
        self.assertIn("Plan only", output)
        self.assertFalse(destination.exists())

    def test_relative_destination_uses_powershell_location(self):
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        other = self.root / "dotnet-working-directory"
        other.mkdir()
        script = (f"[Environment]::CurrentDirectory = {quote(other)}; "
                  f"Set-Location -LiteralPath {quote(self.root)}; "
                  f"& {quote(ROOT / 'setup_workspace.ps1')} -NonInteractive -WorkspaceDir 'relative workspace' "
                  f"-PythonExecutable {quote(sys.executable)}")
        result = subprocess.run([SHELLS[0], "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "relative workspace/workspace.json").exists())
        self.assertFalse((other / "relative workspace").exists())

    def test_nonworkspace_nonempty_directory_is_not_overwritten(self):
        destination = self.root / "foreign"
        destination.mkdir()
        (destination / "important.txt").write_text("keep")
        self.setup_workspace(destination, expected=1)
        self.assertEqual(list(destination.iterdir()), [destination / "important.txt"])
        self.assertEqual((destination / "important.txt").read_text(), "keep")

    def test_invalid_python_fails_before_bootstrap(self):
        destination = self.root / "no-python"
        self.setup_workspace(destination, "-PythonExecutable", self.root / "missing-python.exe", expected=1)
        self.assertFalse(destination.exists())

    def test_explicit_target_is_preserved_on_default_rerun(self):
        custom = self.root / "synthetic reference"
        shutil.copytree(ROOT / "samples/target", custom)
        (custom / "CUSTOM_SOURCE.txt").write_text("new synthetic source")
        destination = self.root / "custom workspace"
        self.setup_workspace(destination, "-TargetSource", custom)
        selected = read(destination / "shared/target/current.json")
        folder = destination / "shared/target/snapshots" / selected["snapshot"]
        self.assertTrue((folder / "CUSTOM_SOURCE.txt").exists())
        self.setup_workspace(destination)
        self.assertEqual(read(destination / "shared/target/current.json"), selected)

    def test_corrupt_target_stops_setup_and_records_failure(self):
        destination = self.root / "corrupt workspace"
        self.setup_workspace(destination)
        sid = read(destination / "shared/target/current.json")["snapshot"]
        fixture = destination / "shared/target/snapshots" / sid / "fixtures/rows.json"
        fixture.write_text("{}")
        output = self.setup_workspace(destination, expected=1)
        self.assertIn("Snapshot", output.title())
        summary = read(destination / ".cache/setup/last-result.json")
        self.assertFalse(summary["success"])
        self.assertEqual(summary["stage"], "verify-target")
        self.assertEqual(fixture.read_text(), "{}")

    def wizard(self, destination, answers, shell=None, expected=0):
        command = [shell or SHELLS[0], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(ROOT / "setup_workspace.ps1"), "-WorkspaceDir", str(destination)]
        result = subprocess.run(command, cwd=self.root, input="\n".join(answers) + "\n",
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(result.returncode, expected, result.stdout + "\n" + result.stderr)
        return result.stdout + result.stderr

    def test_interactive_wizard_saves_confirmed_answers_on_both_hosts(self):
        for index, shell in enumerate(SHELLS):
            with self.subTest(shell=shell):
                destination = self.root / f"wizard workspace {index}"
                output = self.wizard(destination, ["", "ทีมทดสอบ QA", "1", "", "QA_REVIEWER", "", "", "y"], shell=shell)
                self.assertIn("[1/8]", output)
                self.assertIn("[7/8]", output)
                self.assertIn("สรุปก่อน Setup", output)
                self.assertNotIn("\ufffd", output)
                self.assertEqual(read(destination / "workspace.json")["workspace_name"], "ทีมทดสอบ QA")
                self.assertEqual(read(destination / "shared/approvers.json")["simulation_reviewers"], ["DEMO_SA", "QA_REVIEWER"])
                self.assertTrue(read(destination / ".cache/setup/last-result.json")["interactive"])
                self.assertTrue((destination / ".cache/setup/confirmed-answers.json").exists())
                self.assertFalse((destination / ".git").exists())
                self.assertEqual(list(destination.glob("projects/*/jobs/*/job.json")), [])

    def test_interactive_cancel_and_eof_create_nothing(self):
        for name, answers in (("cancel", ["", "QA", "1", "", "", "", "", "q"]), ("eof", [""])):
            destination = self.root / name
            output = self.wizard(destination, answers, expected=2)
            self.assertIn("SETUP CANCELLED", output)
            self.assertFalse(destination.exists())

    def test_interactive_cancel_preserves_existing_workspace(self):
        destination = self.root / "existing cancelled workspace"
        self.setup_workspace(destination)
        before = file_map(destination)
        self.wizard(destination, ["", "Draft name", "1", "", "DRAFT_REVIEWER", "", "", "q"], expected=2)
        self.assertEqual(file_map(destination), before)

    def test_interactive_help_validation_and_edit_preserve_last_answers(self):
        destination = self.root / "edited workspace"
        # Help on Q1; invalid reviewer is retried; e repeats questions without extra custom-path prompts.
        output = self.wizard(destination, ["?", "", "First Team", "1", "", "bad-name", "QA_ONE", "", "", "e",
                                           "", "Second Team", "", "", "", "", "", "y"])
        self.assertIn("ตอบไม่ถูกต้อง", output)
        self.assertGreaterEqual(output.count("[1/8]"), 2)
        self.assertEqual(read(destination / "workspace.json")["workspace_name"], "Second Team")
        self.assertIn("QA_ONE", read(destination / "shared/approvers.json")["simulation_reviewers"])

    def test_noninteractive_explicit_settings_keep_existing_values(self):
        destination = self.root / "configured workspace"
        self.setup_workspace(destination, "-WorkspaceName", "QA Team", "-SimulationReviewers", "QA_ONE")
        self.assertEqual(read(destination / "workspace.json")["workspace_name"], "QA Team")
        self.setup_workspace(destination, "-SimulationReviewers", "QA_TWO,QA_THREE")
        self.assertEqual(read(destination / "workspace.json")["workspace_name"], "QA Team")
        self.assertEqual(read(destination / "shared/approvers.json")["simulation_reviewers"], ["DEMO_SA", "QA_ONE", "QA_TWO", "QA_THREE"])

    @unittest.skipUnless(shutil.which("git"), "Requires Git")
    def test_optional_local_git_init_has_no_commit_or_remote(self):
        destination = self.root / "git workspace"
        self.setup_workspace(destination, "-InitializeGit")
        self.assertTrue((destination / ".git").is_dir())
        head = (destination / ".git/HEAD").read_bytes()
        self.assertIn(b"refs/heads/main", head)
        self.assertEqual(subprocess.check_output(["git", "-C", str(destination), "remote"]), b"")
        self.assertNotEqual(subprocess.run(["git", "-C", str(destination), "rev-parse", "--verify", "HEAD"], capture_output=True).returncode, 0)
        self.setup_workspace(destination, "-InitializeGit")
        self.assertEqual((destination / ".git/HEAD").read_bytes(), head)

    def test_stale_job_blocks_setup_without_changing_review_or_input(self):
        destination = self.root / "job workspace"
        self.setup_workspace(destination)
        job = W.new_job(destination, "TRAINING", "customer_trial", 201,
                        destination / "samples/workflows/customer_daily.json", "DEV_A")
        W.approve(destination, job, "DEMO_SA")
        self.assertEqual(run(destination, job)["state"], "SIMULATION_PASSED")
        workflow = job / "input/blendata/export_workflow.json"
        changed = read(workflow); changed["tasks"][0]["task_name"] += "_test"
        write(workflow, changed)
        before = file_map(job)
        self.setup_workspace(destination, expected=1)
        self.assertEqual(file_map(job), before)
        summary = read(destination / ".cache/setup/last-result.json")
        self.assertEqual(summary["stage"], "check")
        self.assertFalse(summary["success"])

    def test_wizard_oracle_policy_and_connection_store_no_password(self):
        destination = self.root / "oracle wizard workspace"
        answers = ["", "Oracle Team", "1", "", "", "", "2", "1", "1", "1", "dev", "devdb.local", "", "DEVPDB",
                   "APP_RO", "APP_RW", "3", "y"]
        output = self.wizard(destination, answers)
        self.assertIn("[8/8]", output)
        team = read(destination / "shared/team.json")
        self.assertEqual(team["db"]["ai_access"], "ai")
        self.assertEqual(team["db_mode"], "human")                 # simulator runtime field untouched
        local = read(destination / "shared/db.local.json")
        self.assertEqual(local["default"], "DEV")
        self.assertEqual(local["connections"]["DEV"], {"host": "devdb.local", "port": 1521, "service": "DEVPDB",
                                                       "user_ro": "APP_RO", "user_rw": "APP_RW"})
        steps = [row["step"] for row in read(destination / ".cache/setup/last-result.json")["steps"]]
        self.assertIn("db-connect", steps)
        self.assertNotIn("db-test", steps)
        self.assertIn("shared/db.local.json", (destination / ".gitignore").read_text())
        answers_file = (destination / ".cache/setup/confirmed-answers.json").read_text(encoding="utf-8-sig")
        self.assertNotIn("password", answers_file.lower())

    def test_wizard_edit_from_connection_now_to_later_does_not_abort(self):
        destination = self.root / "oracle edit workspace"
        first = ["", "Team", "1", "", "", "", "2", "1", "1", "1", "DEV", "devdb.local", "", "DEVPDB", "APP_RO", "", "3", "e"]
        second = ["", "", "", "", "", "", "2", "", "", "2", "y"]          # same answers, but connection "later"
        self.wizard(destination, first + second)
        self.assertTrue(read(destination / ".cache/setup/last-result.json")["success"])
        self.assertFalse((destination / "shared/db.local.json").exists())

    def test_noninteractive_oracle_settings_and_failed_test_warns_without_failing(self):
        destination = self.root / "oracle cli workspace"
        self.setup_workspace(destination, "-DbHost", "devdb.local", "-DbService", "DEVPDB", "-DbUserRo", "APP_RO", expected=1)
        self.assertFalse(destination.exists())
        output = self.setup_workspace(destination, "-DbAccess", "ai", "-DbSelectMode", "auto", "-DbHost", "devdb.local",
                                      "-DbService", "DEVPDB", "-DbUserRo", "APP_RO", "-TestDbConnection")
        result = read(destination / ".cache/setup/last-result.json")
        self.assertTrue(result["success"])
        self.assertEqual(result["db"]["access"], "ai")
        self.assertTrue(result["db"]["warnings"])
        self.assertIn("WARN", output)
        self.assertEqual(read(destination / "shared/team.json")["db"]["select_mode"], "auto")
        self.setup_workspace(destination)                          # rerun keeps policy and connection
        self.assertEqual(read(destination / "shared/team.json")["db"]["ai_access"], "ai")
        self.assertIn("DEV", read(destination / "shared/db.local.json")["connections"])
        self.setup_workspace(destination, "-DbAccess", "ai", "-DbHost", "x", "-DbService", "S", "-DbUserRo", "SYSTEM", expected=1)


if __name__ == "__main__":
    unittest.main()
