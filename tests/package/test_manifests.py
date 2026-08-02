import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
PLUGIN_NAME = "one-more-pass"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "A final review for writing and code before it goes public."
AUTHOR = {"name": "Mark Learst"}
REPOSITORY = "https://github.com/marklearst/one-more-pass"


class ManifestContractTests(unittest.TestCase):
    def load_json(self, root: Path, relative_path: str) -> dict:
        path = root / relative_path
        self.assertTrue(path.is_file(), f"missing manifest: {relative_path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_plugin_manifests_share_release_identity(self) -> None:
        codex = self.load_json(PLUGIN_ROOT, ".codex-plugin/plugin.json")
        claude = self.load_json(PLUGIN_ROOT, ".claude-plugin/plugin.json")
        claude_marketplace = self.load_json(
            REPO_ROOT, ".claude-plugin/marketplace.json"
        )
        claude_entry = claude_marketplace["plugins"][0]

        for manifest in (codex, claude, claude_entry):
            with self.subTest(manifest=manifest.get("name", "missing-name")):
                self.assertEqual(PLUGIN_NAME, manifest["name"])
                self.assertEqual(PLUGIN_VERSION, manifest["version"])
                self.assertEqual(PLUGIN_DESCRIPTION, manifest["description"])
                self.assertEqual(AUTHOR, manifest["author"])

        for manifest in (codex, claude):
            with self.subTest(repository_manifest=manifest["name"]):
                self.assertEqual(REPOSITORY, manifest["repository"])
                self.assertEqual(REPOSITORY, manifest["homepage"])
                self.assertEqual("MIT", manifest["license"])

        self.assertEqual(REPOSITORY, codex["interface"]["websiteURL"])
        self.assertEqual(AUTHOR, claude_marketplace["owner"])

    def test_skills_do_not_publish_separate_release_versions(self) -> None:
        for skill_name in ("writing", "code"):
            skill = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            with self.subTest(skill=skill_name):
                self.assertNotIn("skill version", skill.lower())

    def test_codex_manifest_uses_shared_skills_without_runtime_integrations(self) -> None:
        codex = self.load_json(PLUGIN_ROOT, ".codex-plugin/plugin.json")

        self.assertEqual("./skills/", codex["skills"])
        self.assertTrue((PLUGIN_ROOT / "skills").is_dir())
        for unsupported in ("apps", "mcpServers", "hooks", "commands", "agents"):
            self.assertNotIn(unsupported, codex)

    def test_marketplaces_point_to_the_nested_runtime(self) -> None:
        claude_marketplace = self.load_json(
            REPO_ROOT, ".claude-plugin/marketplace.json"
        )
        codex_marketplace = self.load_json(
            REPO_ROOT, ".agents/plugins/marketplace.json"
        )

        self.assertEqual(
            "./plugins/one-more-pass",
            claude_marketplace["plugins"][0]["source"],
        )

        codex_entry = codex_marketplace["plugins"][0]
        self.assertEqual(PLUGIN_NAME, codex_entry["name"])
        self.assertEqual(
            {"source": "local", "path": "./plugins/one-more-pass"},
            codex_entry["source"],
        )
        self.assertEqual(
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            codex_entry["policy"],
        )
        self.assertEqual("Developer Tools", codex_entry["category"])

    def test_declared_local_paths_resolve_inside_the_plugin_root(self) -> None:
        codex = self.load_json(PLUGIN_ROOT, ".codex-plugin/plugin.json")
        declared_paths = [codex["skills"]]

        for declared_path in declared_paths:
            with self.subTest(path=declared_path):
                self.assertTrue(declared_path.startswith("./"))
                resolved = (PLUGIN_ROOT / declared_path).resolve()
                self.assertTrue(resolved.is_relative_to(PLUGIN_ROOT.resolve()))
                self.assertTrue(resolved.exists())

        claude_source = self.load_json(
            REPO_ROOT, ".claude-plugin/marketplace.json"
        )["plugins"][0]["source"]
        codex_source = self.load_json(
            REPO_ROOT, ".agents/plugins/marketplace.json"
        )["plugins"][0]["source"]["path"]
        for source in (claude_source, codex_source):
            with self.subTest(source=source):
                resolved = (REPO_ROOT / source).resolve()
                self.assertEqual(PLUGIN_ROOT.resolve(), resolved)

    def test_plugin_root_contains_only_runtime_entries(self) -> None:
        self.assertEqual(
            {".claude-plugin", ".codex-plugin", "LICENSE", "skills"},
            {path.name for path in PLUGIN_ROOT.iterdir()},
        )
        self.assertEqual(
            (REPO_ROOT / "LICENSE").read_bytes(),
            (PLUGIN_ROOT / "LICENSE").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
