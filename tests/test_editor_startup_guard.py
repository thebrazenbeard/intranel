"""Source-only regression tests; never launch an editor or suspicious asset."""

from pathlib import Path
import tempfile
import unittest

from scripts.check_editor_startup_source import scan


class EditorStartupSourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def put(self, name: str, content: str):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_inert_font_files_and_manual_debug_configuration_allowed(self):
        self.put("public/fonts/README.md", "Metadata only")
        self.put("public/fonts/family.woff2", "inert placeholder")
        self.put(".vscode/launch.json", '{"configurations": [{"request": "launch"}]}')
        self.assertEqual(scan(self.root), [])

    def test_folder_open_task_is_rejected_without_running_it(self):
        self.put(".vscode/tasks.json", '{"tasks": [{"runOptions": {"runOn": "folderOpen"}, "command": "inert"}]}')
        self.assertTrue(any("folder-open" in issue for issue in scan(self.root)))

    def test_unicode_escaped_folder_open_is_rejected(self):
        self.put(".vscode/tasks.json", r'{"runOptions": {"runOn": "folder\u004fpen"}}')
        self.assertTrue(any("folder-open" in issue for issue in scan(self.root)))

    def test_nested_editor_directory_auto_start_is_rejected(self):
        self.put("subproject/.vscode/tasks.json", '{"runOn": "folderOpen"}')
        self.assertTrue(any("folder-open" in issue for issue in scan(self.root)))

    def test_nested_workspace_unicode_escaped_auto_start_is_rejected(self):
        self.put(
            "nested/protocol.code-workspace",
            r'{"tasks": {"tasks": [{"runOptions": {"runOn": "folder\u004fpen"}}]}}',
        )
        self.assertTrue(any("folder-open" in issue for issue in scan(self.root)))

    def test_workspace_automatic_task_consent_is_rejected(self):
        self.put(
            "subproject/intranel.code-workspace",
            '{"settings": {"task.allowAutomaticTasks": true}}',
        )
        self.assertTrue(any("automatic task consent" in issue for issue in scan(self.root)))

    def test_workspace_file_symlink_is_rejected_when_supported(self):
        target = self.root / "inert.txt"
        target.write_text("inert", encoding="utf-8")
        symlink = self.root / "linked.code-workspace"
        try:
            symlink.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("platform does not allow unprivileged symbolic links")
        self.assertTrue(any("symbolic link" in issue for issue in scan(self.root)))

    def test_automatic_task_consent_is_rejected(self):
        self.put(".vscode/settings.json", '{"task.allowAutomaticTasks": true}')
        self.assertTrue(any("automatic task consent" in issue for issue in scan(self.root)))

    def test_disguised_code_in_fonts_is_rejected_without_execution(self):
        self.put("public/fonts/fa-solid.lkf", "inert test string")
        self.assertTrue(any("font asset extension" in issue for issue in scan(self.root)))


if __name__ == "__main__":
    unittest.main()
