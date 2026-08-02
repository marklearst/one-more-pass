import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
SCRIPT = REPO_ROOT / "scripts" / "list-runtime-files.py"


class RuntimeContentsTests(unittest.TestCase):
    def run_inventory(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def parse_inventory(self, output: str) -> tuple[dict[str, str], str]:
        lines = output.splitlines()
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[-1].startswith("PACKAGE_SHA256  "))

        entries: dict[str, str] = {}
        for line in lines[:-1]:
            digest, relative_path = line.split("  ", 1)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertNotIn(relative_path, entries)
            entries[relative_path] = digest

        package_digest = lines[-1].split("  ", 1)[1]
        self.assertRegex(package_digest, r"^[0-9a-f]{64}$")
        return entries, package_digest

    def test_inventory_lists_and_hashes_the_installable_runtime(self) -> None:
        result = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        entries, package_digest = self.parse_inventory(result.stdout)

        required = {
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "LICENSE",
            "skills/code/SKILL.md",
            "skills/code/agents/openai.yaml",
            "skills/code/scripts/scan.py",
            "skills/writing/SKILL.md",
            "skills/writing/agents/openai.yaml",
            "skills/writing/scripts/scan.py",
        }
        self.assertTrue(required.issubset(entries), required - entries.keys())

        for relative_path, digest in entries.items():
            path = PLUGIN_ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertFalse(path.is_symlink(), relative_path)
            self.assertTrue(
                path.resolve().is_relative_to(PLUGIN_ROOT.resolve()), relative_path
            )
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

        aggregate = hashlib.sha256()
        for relative_path in sorted(entries):
            aggregate.update(relative_path.encode("utf-8"))
            aggregate.update(b"\0")
            aggregate.update(entries[relative_path].encode("ascii"))
            aggregate.update(b"\n")
        self.assertEqual(aggregate.hexdigest(), package_digest)

    def test_inventory_excludes_development_and_local_artifacts(self) -> None:
        result = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        entries, _ = self.parse_inventory(result.stdout)

        self.assertNotIn("README.md", entries)
        forbidden_parts = {
            "tests",
            "docs",
            "reports",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
        }
        for relative_path in entries:
            path = Path(relative_path)
            self.assertTrue(forbidden_parts.isdisjoint(path.parts), relative_path)
            self.assertNotIn(path.suffix, {".pyc", ".pyo", ".patch", ".diff"})

    def test_inventory_is_reproducible_from_a_copied_plugin(self) -> None:
        first = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, first.returncode, first.stderr)
        entries, _ = self.parse_inventory(first.stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / "one-more-pass"
            for relative_path in entries:
                source = PLUGIN_ROOT / relative_path
                destination = copied_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            second = self.run_inventory(copied_root)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(first.stdout, second.stdout)

    def test_inventory_rejects_forbidden_files_in_the_runtime_tree(self) -> None:
        first = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, first.returncode, first.stderr)
        entries, _ = self.parse_inventory(first.stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / "one-more-pass"
            for relative_path in entries:
                source = PLUGIN_ROOT / relative_path
                destination = copied_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            forbidden_files = (
                copied_root / ".env",
                copied_root / "tests" / "package" / "local.txt",
                copied_root / "docs" / "plans" / "local.md",
                copied_root / "skills" / "writing" / "tests" / "fixture.md",
                copied_root / "skills" / "writing" / "reports" / "review.json",
                copied_root / "skills" / "code" / "__pycache__" / "scan.pyc",
                copied_root / "skills" / "code" / "change.patch",
            )
            for path in forbidden_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("local artifact", encoding="utf-8")

            second = self.run_inventory(copied_root)
            self.assertNotEqual(0, second.returncode)
            self.assertRegex(second.stderr.lower(), r"forbidden|unexpected")

    def test_inventory_rejects_symlinks_in_runtime_paths(self) -> None:
        first = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, first.returncode, first.stderr)
        entries, _ = self.parse_inventory(first.stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / "one-more-pass"
            for relative_path in entries:
                source = PLUGIN_ROOT / relative_path
                destination = copied_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            outside = Path(temp_dir) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            (copied_root / "skills" / "writing" / "references" / "escape.md").symlink_to(
                outside
            )

            result = self.run_inventory(copied_root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("symlink", result.stderr.lower())

    def test_copied_scanners_run_from_an_unrelated_working_directory(self) -> None:
        first = self.run_inventory(PLUGIN_ROOT)
        self.assertEqual(0, first.returncode, first.stderr)
        entries, _ = self.parse_inventory(first.stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / "installed" / "one-more-pass"
            unrelated_cwd = Path(temp_dir) / "project"
            unrelated_cwd.mkdir()
            for relative_path in entries:
                source = PLUGIN_ROOT / relative_path
                destination = copied_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            commands = (
                (
                    copied_root / "skills" / "writing" / "scripts" / "scan.py",
                    ["--fail-on", "never", "-"],
                    "Plain source text.\n",
                ),
                (
                    copied_root / "skills" / "code" / "scripts" / "scan.py",
                    ["-"],
                    "const answer = 42;\n",
                ),
            )
            for scanner, arguments, input_text in commands:
                with self.subTest(scanner=scanner):
                    result = subprocess.run(
                        [sys.executable, str(scanner), *arguments],
                        cwd=unrelated_cwd,
                        input=input_text,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
