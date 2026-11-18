"""B security regression: actual repository checkout remains editor-startup inert.

Does not open the editor, execute the embedded script, or import old code.
Tests the checkout itself, unlike the existing guard tests' temporary fixtures.
"""
from pathlib import Path
import subprocess
import unittest

from scripts.check_editor_startup_source import scan


ROOT = Path(__file__).resolve().parents[1]


class EditorSourceTreeIntegrity(unittest.TestCase):
    def test_checkout_editor_configuration_remains_inert(self):
        self.assertEqual(scan(ROOT), [], "Repository source startup guard regressed")

    def test_removed_autoexecute_entries_absent_from_actual_checkout(self):
        self.assertFalse((ROOT / ".vscode" / "ini").exists())
        self.assertFalse((ROOT / ".vscode" / "tasks.json").exists())

    def test_guard_catches_historical_main_but_not_current_candidate(self):
        # This is a local source-only falsifier. Work with Git objects as BYTES;
        # NEVER materialize or run the historical Node script.
        historic = "ad9ee55dc5aba0882bdd93420d6e74b0e0c38f21"
        for relative in (".vscode/tasks.json", ".vscode/settings.json"):
            prior = subprocess.check_output(
                ["git", "-C", str(ROOT), "show", f"{historic}:{relative}"]
            ).decode("utf-8-sig")
            self.assertTrue(
                "folderOpen" in prior or "task.allowAutomaticTasks" in prior,
                f"Expected source-staged startup evidence: {relative}",
            )
        self.assertFalse((ROOT / ".vscode" / "tasks.json").exists())
        self.assertFalse((ROOT / ".vscode" / "ini").exists())


if __name__ == "__main__":
    unittest.main()