from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_TEXT_SUFFIXES = {".json", ".md", ".py", ".sh", ".txt", ".yaml", ".yml"}
PUBLIC_TEXT_NAMES = {".gitignore", "LICENSE"}
TEST_DOCUMENTATION = (
    REPO_ROOT / "tests" / "behavior" / "README.md",
    REPO_ROOT / "tests" / "writing" / "PRESSURE_TEST.md",
)


def public_markdown_files() -> list[Path]:
    paths = [REPO_ROOT / "README.md", REPO_ROOT / "CHANGELOG.md"]
    paths.extend(TEST_DOCUMENTATION)
    paths.extend((REPO_ROOT / "docs").rglob("*.md"))
    paths.extend((REPO_ROOT / "plugins" / "one-more-pass").rglob("*.md"))
    return sorted({path for path in paths if path.is_file()})


def public_text_files() -> list[Path]:
    paths = [
        REPO_ROOT / ".gitignore",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "README.md",
    ]
    paths.extend(TEST_DOCUMENTATION)
    for directory in (
        REPO_ROOT / ".agents",
        REPO_ROOT / ".claude-plugin",
        REPO_ROOT / "docs",
        REPO_ROOT / "plugins" / "one-more-pass",
        REPO_ROOT / "scripts",
    ):
        paths.extend(directory.rglob("*"))

    return sorted(
        {
            path
            for path in paths
            if path.is_file()
            and (
                path.name in PUBLIC_TEXT_NAMES
                or path.suffix.lower() in PUBLIC_TEXT_SUFFIXES
            )
        }
    )


def markdown_targets(text: str) -> list[str]:
    return re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)


class PublicRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.markdown = public_markdown_files()
        self.public_text = public_text_files()
        self.public_prose = [
            path
            for path in self.public_text
            if path.suffix.lower() not in {".py", ".sh"}
        ]
        self.assertTrue(self.markdown)
        self.assertTrue(self.public_text)

    def test_relative_markdown_links_resolve(self) -> None:
        broken: list[str] = []

        for path in self.markdown:
            for raw_target in markdown_targets(path.read_text(encoding="utf-8")):
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue

                destination = (path.parent / unquote(parsed.path)).resolve()
                if not destination.exists():
                    broken.append(
                        f"{path.relative_to(REPO_ROOT)} -> {raw_target}"
                    )

        self.assertEqual([], broken)

    def test_public_text_inventory_covers_shipped_text_formats(self) -> None:
        inventoried = {
            path.relative_to(REPO_ROOT).as_posix() for path in self.public_text
        }
        required = {
            ".agents/plugins/marketplace.json",
            ".claude-plugin/marketplace.json",
            "LICENSE",
            "plugins/one-more-pass/.claude-plugin/plugin.json",
            "plugins/one-more-pass/.codex-plugin/plugin.json",
            "plugins/one-more-pass/LICENSE",
            "plugins/one-more-pass/skills/code/agents/openai.yaml",
            "plugins/one-more-pass/skills/code/scripts/scan.py",
            "plugins/one-more-pass/skills/writing/agents/openai.yaml",
            "plugins/one-more-pass/skills/writing/scripts/scan.py",
            "scripts/list-runtime-files.py",
        }

        self.assertTrue(
            required.issubset(inventoried), required - inventoried
        )

    def test_public_inventories_include_test_documentation(self) -> None:
        required = {
            "tests/behavior/README.md",
            "tests/writing/PRESSURE_TEST.md",
        }
        markdown = {
            path.relative_to(REPO_ROOT).as_posix() for path in self.markdown
        }
        public_text = {
            path.relative_to(REPO_ROOT).as_posix() for path in self.public_text
        }

        self.assertTrue(required.issubset(markdown), required - markdown)
        self.assertTrue(required.issubset(public_text), required - public_text)

    def test_public_text_has_no_private_absolute_paths(self) -> None:
        private_path = re.compile(
            r"(?:/Users/[^/\s`]+|/home/[^/\s`]+|[A-Za-z]:\\Users\\[^\\\s`]+)"
        )
        matches: list[str] = []

        for path in self.public_text:
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if private_path.search(line):
                    matches.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}"
                    )

        self.assertEqual([], matches)

    def test_public_text_has_no_stale_runtime_paths(self) -> None:
        stale_paths = (
            "tests/fixtures/red_cases.json",
            "~/.claude/skills/stop-slop",
            "~/.codex/skills/stop-slop",
            "/stop-slop/SKILL.md",
        )
        matches: list[str] = []

        for path in self.public_text:
            text = path.read_text(encoding="utf-8")
            for stale_path in stale_paths:
                if stale_path in text:
                    matches.append(
                        f"{path.relative_to(REPO_ROOT)}: {stale_path}"
                    )

        self.assertEqual([], matches)

    def test_public_text_has_no_secret_values(self) -> None:
        secret_patterns = (
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
            re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        )
        matches: list[str] = []

        for path in self.public_text:
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in secret_patterns):
                    matches.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}"
                    )

        self.assertEqual([], matches)

    def test_public_text_has_no_structured_tool_attribution(self) -> None:
        forbidden = (
            re.compile(r"(?im)^\s*(?:generated[- ]by|co-authored-by):\s*\S+"),
            re.compile(r"(?im)^\s*(?:assistant|ai)\s+(?:credit|attribution):\s*\S+"),
            re.compile(
                r"https?://(?:chatgpt\.com|chat\.openai\.com|claude\.ai)/share/\S+",
                re.IGNORECASE,
            ),
        )
        matches: list[str] = []

        for path in self.public_text:
            text = path.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in forbidden):
                matches.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual([], matches)

    def test_public_prose_contains_no_em_dash(self) -> None:
        matches = [
            str(path.relative_to(REPO_ROOT))
            for path in self.public_prose
            if "\N{EM DASH}" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], matches)


if __name__ == "__main__":
    unittest.main()
