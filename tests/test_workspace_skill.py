"""Verify workspace-local installation, updates and preservation of authored guidance."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from install_workspace_skill import BLOCK, END, SKILL_NAME, START, InstallError, install


def contents(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


class WorkspaceSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migration-skill-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.cleanup_temp)
        self.source = self.root / "source"
        self.workspace = self.root / "workspace"
        shutil.copytree(ROOT / ".agents", self.source / ".agents")
        (self.workspace / "tools").mkdir(parents=True)
        (self.workspace / "tools/workspace.py").write_text("# Workspace launcher\n")
        (self.workspace / "workspace.json").write_text('{"mode":"simulation"}\n')

    def cleanup_temp(self):
        target = Path(self.temp.name).resolve()
        if not target.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not target.name.startswith("migration-skill-test-"):
            raise RuntimeError("Refusing cleanup outside allocated skill-test workspace")
        self.temp.cleanup()

    def test_install_is_local_self_contained_and_idempotent(self):
        record = install(self.source, self.workspace)
        folder = self.workspace / ".agents/skills" / SKILL_NAME
        self.assertTrue((folder / "SKILL.md").is_file())
        self.assertTrue((folder / "references/workspace-commands.md").is_file())
        self.assertTrue((folder / "agents/openai.yaml").is_file())
        self.assertEqual(record["scope"], "workspace")
        self.assertFalse((self.workspace / ".codex").exists())
        before = contents(self.workspace)
        times = {p: p.stat().st_mtime_ns for p in self.workspace.rglob("*") if p.is_file()}
        install(self.source, self.workspace)
        self.assertEqual(contents(self.workspace), before)
        self.assertEqual({p: p.stat().st_mtime_ns for p in times}, times)

    def test_update_preserves_unrelated_agents_instructions(self):
        agents = self.workspace / "AGENTS.md"
        prefix, suffix = "# Team instructions\r\nKeep the user's own rule.\r\n\r\n", "\r\n\r\nCustom trailing guidance.\r\n"
        agents.write_bytes(b"\xef\xbb\xbf" + prefix.encode())
        install(self.source, self.workspace)
        agents.write_bytes(agents.read_bytes() + suffix.encode())
        reference = self.source / ".agents/skills" / SKILL_NAME / "references/workspace-commands.md"
        reference.write_text(reference.read_text(encoding="utf-8") + "\nReviewed update.\n", encoding="utf-8")
        install(self.source, self.workspace)
        self.assertTrue(agents.read_bytes().startswith(b"\xef\xbb\xbf"))
        text = agents.read_bytes().decode("utf-8-sig")
        self.assertTrue(text.startswith(prefix))
        self.assertTrue(text.endswith(suffix))
        self.assertEqual(text.count(START), 1)
        self.assertEqual((self.workspace / ".agents/skills" / SKILL_NAME / "references/workspace-commands.md").read_bytes(), reference.read_bytes())

    def test_local_skill_edit_blocks_all_updates(self):
        install(self.source, self.workspace)
        target = self.workspace / ".agents/skills" / SKILL_NAME / "SKILL.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nLocal team edit.\n", encoding="utf-8")
        source = self.source / ".agents/skills" / SKILL_NAME / "SKILL.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nUpstream edit.\n", encoding="utf-8")
        before = contents(self.workspace)
        with self.assertRaisesRegex(InstallError, "local changes"):
            install(self.source, self.workspace)
        self.assertEqual(contents(self.workspace), before)

    def test_managed_agents_edit_is_not_overwritten(self):
        install(self.source, self.workspace)
        path = self.workspace / "AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8").replace(BLOCK, BLOCK.replace("Simulation jobs are offline", "Simulation jobs are custom")), encoding="utf-8")
        before = contents(self.workspace)
        with self.assertRaisesRegex(InstallError, "edited locally"):
            install(self.source, self.workspace)
        self.assertEqual(contents(self.workspace), before)

    def test_invalid_source_or_markers_fail_before_writes(self):
        skill = self.source / ".agents/skills" / SKILL_NAME / "SKILL.md"
        original = skill.read_bytes()
        skill.write_text("# No frontmatter\n", encoding="utf-8")
        before = contents(self.workspace)
        with self.assertRaises(InstallError):
            install(self.source, self.workspace)
        self.assertEqual(contents(self.workspace), before)
        skill.write_bytes(original)
        (self.workspace / "AGENTS.md").write_text(START + "\nUnfinished block\n")
        before = contents(self.workspace)
        with self.assertRaisesRegex(InstallError, "ambiguous"):
            install(self.source, self.workspace)
        self.assertEqual(contents(self.workspace), before)


if __name__ == "__main__":
    unittest.main()
