"""Fail closed on editor autorun and executable content disguised as public fonts.

This uses only the Python standard library so CI can run it before installing
dependencies or invoking any repository-provided build script.
"""

import json
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FONT_SIGNATURES = {
    ".eot": lambda data: len(data) >= 36 and data[34:36] == b"LP",
    ".ttf": lambda data: data.startswith((b"\x00\x01\x00\x00", b"OTTO")),
    ".woff": lambda data: data.startswith(b"wOFF"),
    ".woff2": lambda data: data.startswith(b"wOF2"),
    ".svg": lambda data: data.lstrip(b"\xef\xbb\xbf \t\r\n").startswith((b"<?xml", b"<svg")),
}


def _inspect_value(value, location, failures):
    if isinstance(value, dict):
        if value.get("task.allowAutomaticTasks") is True:
            failures.append(f"{location}: automatic editor tasks explicitly enabled")
        if value.get("runOn") == "folderOpen":
            failures.append(f"{location}: unprompted folderOpen task")
        command = value.get("command")
        if isinstance(command, str) and re.search(r"public[/\\]fonts[/\\]", command, re.I):
            failures.append(f"{location}: task command references public font assets")
        for key, member in value.items():
            _inspect_value(member, f"{location}.{key}", failures)
    elif isinstance(value, list):
        for i, member in enumerate(value):
            _inspect_value(member, f"{location}[{i}]", failures)


def audit_repository(root):
    failures = []
    # Launch configurations require explicit user action and can be JSONC.
    # Only the two VS Code files capable of enabling folder-open tasks are
    # parsed here; both are strict JSON in this repository.
    for name in ("tasks.json", "settings.json"):
        path = root / ".vscode" / name
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeError, OSError, json.JSONDecodeError) as exc:
            failures.append(f"{path.relative_to(root)}: invalid editor JSON: {exc}")
            continue
        _inspect_value(value, str(path.relative_to(root)), failures)

    fonts = root / "public" / "fonts"
    if fonts.exists():
        for path in sorted(fonts.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if path.name == "README.md":
                continue
            check = FONT_SIGNATURES.get(path.suffix.lower())
            if check is None:
                failures.append(f"{relative}: unexpected asset type in font directory")
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                failures.append(f"{relative}: unreadable font asset: {exc}")
                continue
            if not check(data):
                failures.append(f"{relative}: font file signature does not match extension")
            if path.suffix.lower() == ".svg" and re.search(
                rb"<\s*script\b|\bon[a-z]+\s*=|javascript\s*:", data, re.I
            ):
                failures.append(f"{relative}: active content in SVG font")
    return failures


class RepositoryStartupSecurityTests(unittest.TestCase):
    def test_checked_out_repository_is_safe(self):
        self.assertEqual(audit_repository(ROOT), [])

    def test_hidden_folder_open_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".vscode").mkdir()
            (root / ".vscode" / "tasks.json").write_text(json.dumps({
                "tasks": [{"hide": True, "command": "node public/fonts/fa-solid.lkf",
                           "runOptions": {"runOn": "folderOpen"}}]
            }), encoding="utf-8")
            result = audit_repository(root)
            self.assertTrue(any("folderOpen" in defect for defect in result), result)
            self.assertTrue(any("font assets" in defect for defect in result), result)

    def test_settings_based_folder_open_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".vscode").mkdir()
            (root / ".vscode" / "settings.json").write_text(json.dumps({
                "task.allowAutomaticTasks": True,
                "tasks": {"runOn": "folderOpen", "command": "npm run lint"}
            }), encoding="utf-8")
            self.assertEqual(len(audit_repository(root)), 2)

    def test_obfuscated_nonfont_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public" / "fonts").mkdir(parents=True)
            (root / "public" / "fonts" / "fa-solid.lkf").write_text(
                "require('child_process').spawn('curl')", encoding="utf-8"
            )
            self.assertTrue(any("unexpected asset" in defect for defect in audit_repository(root)))

    def test_script_disguised_as_woff2_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public" / "fonts").mkdir(parents=True)
            (root / "public" / "fonts" / "fa-solid-500.woff2").write_bytes(b"require('child_process')")
            self.assertTrue(any("signature" in defect for defect in audit_repository(root)))

    def test_real_woff2_and_ttf_signatures_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public" / "fonts").mkdir(parents=True)
            (root / "public" / "fonts" / "ok.woff2").write_bytes(b"wOF2" + b"\x00" * 12)
            (root / "public" / "fonts" / "ok.ttf").write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 12)
            self.assertEqual(audit_repository(root), [])

    def test_active_svg_font_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public" / "fonts").mkdir(parents=True)
            (root / "public" / "fonts" / "ok.svg").write_bytes(b"<svg><script>1</script></svg>")
            self.assertTrue(any("active content" in defect for defect in audit_repository(root)))


if __name__ == "__main__":
    unittest.main()
