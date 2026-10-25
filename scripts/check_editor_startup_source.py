"""Fail closed on repository-controlled editor startup execution surfaces.

Source-only check: it does not open an editor, launch Node, or execute assets.
Run before dependency installation on every supported CI platform.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


_FONT_SUFFIXES = frozenset({
    ".css", ".eot", ".license", ".md", ".otf", ".svg",
    ".ttf", ".txt", ".woff", ".woff2",
})
_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _decoded_source(path: Path) -> str:
    """Expand JSON Unicode escapes for source inspection without evaluating code."""
    source = path.read_text(encoding="utf-8", errors="replace")
    return _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), source).casefold()


def scan(root: Path) -> list[str]:
    """Report source-controlled editor auto-execution and disguised font assets."""
    issues: list[str] = []
    editor = root / ".vscode"
    if editor.is_symlink():
        issues.append(".vscode: symbolic link is not permitted")
    elif editor.exists():
        for path in sorted(editor.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                issues.append(f"{relative}: symbolic link is not permitted")
                continue
            if not path.is_file():
                continue
            contents = _decoded_source(path)
            if "folderopen" in contents:
                issues.append(f"{relative}: folder-open execution is forbidden")
            if "task.allowautomatictasks" in contents:
                issues.append(f"{relative}: automatic task consent is forbidden")

    fonts = root / "public" / "fonts"
    if fonts.is_symlink():
        issues.append("public/fonts: symbolic link is not permitted")
    elif fonts.exists():
        for path in sorted(fonts.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                issues.append(f"{relative}: symbolic link is not permitted")
            elif path.is_file() and path.suffix.casefold() not in _FONT_SUFFIXES:
                issues.append(f"{relative}: unexpected executable-like font asset extension")
    return issues


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    issues = scan(root)
    for issue in issues:
        print(f"editor startup source guard: {issue}", file=sys.stderr)
    if issues:
        return 1
    print("editor startup source guard: PASS (source-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
