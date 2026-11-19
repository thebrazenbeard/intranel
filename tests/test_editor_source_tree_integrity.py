"""B security regression: actual repository checkout remains editor-startup inert.

Does not open the editor, execute the embedded script, or import old code.
Tests the checkout itself, unlike the existing guard tests' temporary fixtures.
"""
from pathlib import Path
import tempfile
import unittest

from scripts.check_editor_startup_source import scan


ROOT = Path(__file__).resolve().parents[1]


class EditorSourceTreeIntegrity(unittest.TestCase):
    def test_checkout_editor_configuration_remains_inert(self):
        self.assertEqual(scan(ROOT), [], "Repository source startup guard regressed")

    def test_removed_autoexecute_entries_absent_from_actual_checkout(self):
        self.assertFalse((ROOT / ".vscode" / "ini").exists())
        self.assertFalse((ROOT / ".vscode" / "tasks.json").exists())

    def test_guard_catches_simulated_regression_without_git_history(self):
        # Hosted CI uses a shallow checkout. Never require historical objects
        # for a safety invariant in a running test.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            editor = source / ".vscode"
            editor.mkdir()
            (editor / "tasks.json").write_text(
                '{"tasks":[{"runOptions":{"runOn":"folderOpen"},"command":"node"}]}',
                encoding="utf-8",
            )
            (editor / "settings.json").write_text(
                '{"task.allowAutomaticTasks":true}', encoding="utf-8",
            )
            violations = scan(source)
            self.assertTrue(any("folder-open" in item for item in violations))
            self.assertTrue(any("automatic task consent" in item for item in violations))
        self.assertEqual(scan(ROOT), [])



if __name__ == "__main__":
    unittest.main()