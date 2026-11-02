"""Oracle adapter (tools/dbcore): plan → human approval → execute, without a real database.

A fake `oracledb` module records every statement, so these tests prove the guard rails
(policy, approval, file hashes, destructive confirmation, scope) rather than Oracle itself.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kit/src"))
sys.path.insert(0, str(REPO / "tools"))
from migrate_kit import workspace as W
from migrate_kit.storage import fingerprint, read, write
from dbcore import cli, dbx


class FakeCursor:
    def __init__(self, log):
        self.log, self.description, self.rowcount, self._rows = log, None, 0, []

    def execute(self, sql):
        self.log.append(sql)
        if "FAIL_ME" in sql:
            raise RuntimeError("ORA-00942: table or view does not exist")
        if sql.lstrip().upper().startswith("SELECT") and "TRANSACTION" not in sql.upper():
            self.description = [("DB_USER",), ("DB_TIME",)]
            self._rows = [] if "1 = 0" in sql else [("APP_RO", "2026-11-02")]
        else:
            self.description, self._rows, self.rowcount = None, [], 3

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, log, user):
        self.log, self.user, self.autocommit, self.commits = log, user, True, 0

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.commits += 1
        self.log.append("COMMIT")

    def rollback(self):
        pass

    def close(self):
        pass


class DbCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-db-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("kit", "samples", "tools"):
            shutil.copytree(REPO / folder, self.root / folder,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "releases", "dist"))
        W.initialize(self.root); W.freeze(self.root); W.snapshot(self.root)
        self.job = W.new_job(self.root, "DEMO", "customer_daily", 101,
                             self.root / "samples/workflows/customer_daily.json", "DEMO_ALICE")
        self.pack = self.job / "run_packs/rp02_check"
        self.pack.mkdir(parents=True)
        (self.pack / "V1_counts.sql").write_text("SELECT COUNT(*) AS N FROM CUSTOMER_DIM;\n", encoding="utf-8")
        self.statements, self.connects = [], []
        fake = types.ModuleType("oracledb")
        fake.__version__ = "fake"

        def connect(user, password, dsn):
            self.connects.append((user, password, dsn))
            return FakeConnection(self.statements, user)
        fake.connect = connect
        patches = [mock.patch.dict(sys.modules, {"oracledb": fake}),
                   mock.patch.object(dbx, "stdin_is_tty", lambda: False),
                   mock.patch.dict("os.environ", {"ORA_RO_PASSWORD": "ro-secret", "ORA_RW_PASSWORD": "rw-secret"})]
        for p in patches:
            p.start(); self.addCleanup(p.stop)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(self.root, list(argv))
        return code, out.getvalue()

    def enable_ai(self, select_mode="ask", users="split"):
        self.assertEqual(self.run_cli("db-policy", "--access", "ai", "--select-mode", select_mode, "--users", users)[0], 0)
        code, out = self.run_cli("db-connect", "--non-interactive", "--env", "DEV", "--host", "devdb.local", "--port", "1521",
                                 "--service", "DEVPDB", "--user-ro", "APP_RO", "--user-rw", "APP_RW")
        self.assertEqual(code, 0, out)

    def plan_id(self, output):
        return output.split("--execute ")[1].split()[0]

    def test_classifier_splits_plsql_and_flags_destructive(self):
        stmts = dbx.split_statements("BEGIN\n  x := 1;\nEND;\n/\nDELETE FROM T1;\nTRUNCATE TABLE s.T2;\n"
                                     "SELECT ';' FROM dual; -- comment ; here\n")
        kinds = [dbx.classify(s) for s in stmts]
        self.assertEqual([k["kind"] for k in kinds], ["plsql", "write", "ddl", "read"])
        self.assertEqual([k["tables"] for k in kinds if k["destructive"]], [["T1"], ["S.T2"]])
        self.assertEqual(dbx.classify("SELECT * FROM t FOR UPDATE")["kind"], "write")

    def test_review_findings_classification(self):
        for sql in ("UPDATE t SET a = (SELECT b FROM s WHERE s.id = t.id)", "UPDATE t SET note = 'where'",
                    "ALTER TABLE t TRUNCATE PARTITION p", "BEGIN EXECUTE IMMEDIATE 'TRUNCATE TABLE x'; END;"):
            self.assertTrue(dbx.classify(sql)["destructive"], sql)
        self.assertFalse(dbx.classify("DELETE FROM t WHERE x = 1")["destructive"])
        self.assertFalse(dbx.classify("BEGIN p_load(1); END;")["destructive"])
        stmts = dbx.split_statements("INSERT /*+ APPEND */ INTO t SELECT 'a--b\nc' FROM dual; -- x\nBEGIN null; END;")
        self.assertEqual(stmts, ["INSERT /*+ APPEND */ INTO t SELECT 'a--b\nc' FROM dual", "BEGIN null; END;"])
        dml = self.pack / "T1_load.sql"
        dml.write_text("-- Load Strategy: append (Blendata sinkOption.mode = Append)\nINSERT INTO t SELECT 1 FROM dual;\n", encoding="utf-8")
        self.assertEqual(dbx.classify_file(dml)["kind"], "write")
        spark = self.pack / "S3_profile.sql"
        spark.write_text("-- 03_profile (Blendata / Spark SQL, generated 2026-10-29)\nSELECT 1;\n", encoding="utf-8")
        self.assertEqual(dbx.classify_file(spark)["kind"], "blendata")

    def test_edited_plan_file_is_refused(self):
        self.enable_ai()
        pid = self.plan_id(self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02")[1])
        plan_path = self.job / ".dbx/plans" / f"{pid}.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["items"][0]["stmts"][0]["sql"] = "DELETE FROM CUSTOMER_DIM WHERE 1 = 1"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana")
        self.assertEqual(code, 1)
        self.assertIn("ไม่ตรงกับไฟล์", out)
        self.assertEqual(self.connects, [])

    def test_db_test_never_reports_an_old_result(self):
        self.enable_ai()
        tmp = self.root / "registry/tmp_db"; tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "ping.csv").write_text("DB_USER,DB_TIME\nOLD,2026-01-01\n", encoding="utf-8")
        code, out = self.run_cli("db-test", "--plan")
        self.assertNotEqual(code, 0)
        self.assertNotIn("ต่อฐานได้", out)

    def test_default_policy_is_human_and_never_connects(self):
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--plan")
        self.assertEqual(code, 0)
        self.assertIn("คนรันทั้งหมด", out)
        self.assertEqual(self.connects, [])
        code, out = self.run_cli("db-connect", "--non-interactive", "--host", "h", "--service", "S", "--user-ro", "U")
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "shared/db.local.json").exists())

    def test_connection_file_has_no_password_and_rejects_sys(self):
        self.enable_ai()
        saved = read(self.root / "shared/db.local.json")
        self.assertEqual(saved["connections"]["DEV"]["user_ro"], "APP_RO")
        self.assertNotIn("secret", json.dumps(saved))
        self.assertNotIn("password", json.dumps(saved["connections"]).lower())
        code, out = self.run_cli("db-connect", "--non-interactive", "--env", "SIT", "--host", "sit", "--service", "S",
                                 "--user-ro", "SYSTEM")
        self.assertEqual(code, 1)
        self.assertIn("SYS", out)
        team = read(self.root / "shared/team.json")
        self.assertEqual(team["db_mode"], "human")          # simulator field preserved
        self.assertEqual(team["db"]["ai_access"], "ai")

    def test_plan_requires_human_approval_then_runs_read_only_and_keeps_fingerprint(self):
        self.enable_ai()
        W.approve(self.root, self.job, "DEMO_SA")
        before = fingerprint(self.job)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02")
        self.assertEqual(code, cli.EXIT_NEED_APPROVAL)
        self.assertEqual(self.connects, [])
        pid = self.plan_id(out)
        self.assertEqual(self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid)[0], 1)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana 2026-11-02")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.connects[0][0], "APP_RO")
        self.assertEqual(self.connects[0][2], "devdb.local:1521/DEVPDB")
        self.assertIn("SET TRANSACTION READ ONLY", self.statements)
        self.assertNotIn("COMMIT", self.statements)
        self.assertTrue((self.job / "db_runs/rp02_check/V1_counts.csv").exists())
        log = (self.job / "status/DB_RUN_LOG.md").read_text(encoding="utf-8")
        self.assertIn("Mana 2026-11-02", log)
        self.assertIn("V1_counts.sql", (self.root / "registry/db_queries.log").read_text(encoding="utf-8"))
        self.assertEqual(fingerprint(self.job), before)

    def test_changed_file_after_plan_is_refused(self):
        self.enable_ai()
        pid = self.plan_id(self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02")[1])
        (self.pack / "V1_counts.sql").write_text("SELECT 1 FROM dual;\n", encoding="utf-8")
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana")
        self.assertEqual(code, 1)
        self.assertIn("ถูกแก้หลังสร้างแผน", out)
        self.assertEqual(self.connects, [])

    def test_destructive_statement_needs_exact_table_confirmation(self):
        self.enable_ai()
        (self.pack / "S1_reset.sql").write_text("TRUNCATE TABLE CUSTOMER_DIM;\nINSERT INTO CUSTOMER_DIM SELECT * FROM STG;\n", encoding="utf-8")
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--only", "S1")
        self.assertEqual(code, cli.EXIT_NEED_APPROVAL)
        pid = self.plan_id(out)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana", "--confirm", "WRONG")
        self.assertEqual(code, 1)
        self.assertEqual(self.connects, [])
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana",
                                 "--confirm", "customer_dim")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.connects[0][0], "APP_RW")
        self.assertIn("COMMIT", self.statements)
        self.assertIn("DDL run_packs/rp02_check/S1_reset.sql", (self.job / "status/DEPLOY_LOG.md").read_text(encoding="utf-8"))

    def test_scope_snp_and_blendata_guards(self):
        self.enable_ai()
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", str(self.root / "samples"), "--plan")
        self.assertEqual(code, 1)
        self.assertIn("นอก", out)
        (self.pack / "S2_odi.sql").write_text("UPDATE SNP_SESSION SET X = 1 WHERE Y = 2;\n", encoding="utf-8")
        (self.pack / "S3_blendata_source.sql").write_text("-- Blendata Spark SQL\nSELECT 1;\n", encoding="utf-8")
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--only", "S2,S3", "--plan")
        self.assertEqual(code, 0)
        self.assertIn("SNP_*", out)
        self.assertIn("Blendata", out)
        self.assertEqual(self.connects, [])

    def test_run_read_respects_select_mode_and_job_override(self):
        self.enable_ai(select_mode="ask")
        self.assertEqual(self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--run-read")[0], cli.EXIT_NEED_APPROVAL)
        self.enable_ai(select_mode="auto")
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--run-read")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.connects), 1)
        meta = read(self.job / "job.json"); meta["db_access"] = "human"; write(self.job / "job.json", meta)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02", "--run-read")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.connects), 1)            # override: human only, nothing executed
        self.assertEqual(W.check(self.root), [])

    def test_compile_mode_and_simulator_output_warning(self):
        self.enable_ai()
        W.approve(self.root, self.job, "DEMO_SA"); W.simulate(self.root, self.job)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "output/sql/converted", "--compile")
        self.assertEqual(code, cli.EXIT_NEED_APPROVAL)
        self.assertIn("simulator", out)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", self.plan_id(out), "--approved", "Mana")
        self.assertEqual(code, 0, out)
        self.assertTrue(any("WHERE 1 = 0" in s for s in self.statements))
        self.assertIn("OK", (self.job / "db_runs/verify/sql_compile.txt").read_text(encoding="utf-8"))
        self.assertEqual(W.check(self.root), [])

    def test_db_test_and_human_record(self):
        self.enable_ai()
        code, out = self.run_cli("db-test", "--approved", "setup -TestDbConnection (Mana)")
        self.assertEqual(code, 0, out)
        self.assertIn("APP_RO", out)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02")
        pid = self.plan_id(out)
        code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--record-human", pid, "--result", "DBeaver: 10 rows")
        self.assertEqual(code, 0)
        self.assertIn("DBeaver: 10 rows", (self.job / "status/DB_RUN_LOG.md").read_text(encoding="utf-8"))

    def test_missing_password_is_not_prompted_without_terminal(self):
        self.enable_ai()
        pid = self.plan_id(self.run_cli("run-sql", "--job", "DEMO/customer_daily", "rp02")[1])
        with mock.patch.dict("os.environ", {"ORA_RO_PASSWORD": ""}):
            code, out = self.run_cli("run-sql", "--job", "DEMO/customer_daily", "--execute", pid, "--approved", "Mana")
        self.assertEqual(code, 1)
        self.assertIn("ORA_RO_PASSWORD", out)
        self.assertEqual(self.connects, [])


if __name__ == "__main__":
    unittest.main()
