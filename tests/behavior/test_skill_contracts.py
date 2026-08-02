from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
PUBLIC_README = REPO_ROOT / "README.md"
WRITING_SKILL = PLUGIN_ROOT / "skills" / "writing" / "SKILL.md"
WRITING_INTERFACE = PLUGIN_ROOT / "skills" / "writing" / "agents" / "openai.yaml"
WRITING_TOOLS = PLUGIN_ROOT / "skills" / "writing" / "references" / "optional-tools.md"
WRITING_EXAMPLES = PLUGIN_ROOT / "skills" / "writing" / "references" / "examples.md"
WRITING_RULES = PLUGIN_ROOT / "skills" / "writing" / "references" / "prose-rules.md"
WRITING_REWRITE = PLUGIN_ROOT / "skills" / "writing" / "references" / "rewrite-rules.md"
CODE_SKILL = PLUGIN_ROOT / "skills" / "code" / "SKILL.md"
CODE_CHECKLIST = PLUGIN_ROOT / "skills" / "code" / "references" / "review-checklist.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class WritingRoutingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = WRITING_SKILL.read_text(encoding="utf-8")
        self.interface = WRITING_INTERFACE.read_text(encoding="utf-8")
        self.writing_tools = WRITING_TOOLS.read_text(encoding="utf-8")
        self.writing_rules = WRITING_RULES.read_text(encoding="utf-8")
        self.writing_rewrite = WRITING_REWRITE.read_text(encoding="utf-8")
        self.code_skill = CODE_SKILL.read_text(encoding="utf-8")
        self.routing = json.loads(
            (FIXTURES / "writing-routing.json").read_text(encoding="utf-8")
        )

    def test_routing_fixture_covers_rewrite_review_nontrigger_pair_and_authorship(self) -> None:
        modes = {case["mode"] for case in self.routing["cases"]}
        self.assertTrue(
            {
                "rewrite",
                "review-only",
                "outside-scope",
                "paired",
                "authorship-refusal",
            }.issubset(modes),
            modes,
        )

        ids = [case["id"] for case in self.routing["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(case["prompt"].strip() for case in self.routing["cases"]))

    def test_skill_supports_only_rewrite_and_review_only_modes(self) -> None:
        self.assertIn("## Modes", self.skill)
        self.assertIn("### Rewrite", self.skill)
        self.assertIn("### Review-only", self.skill)
        self.assertNotIn("mode: draft", self.skill.lower())
        self.assertNotIn("draft, rewrite, or review-only", self.skill.lower())

    def test_blank_page_drafting_is_outside_scope(self) -> None:
        self.assertIn("Do not use this skill to draft from a blank prompt", self.skill)
        description = self.skill.split("---", 2)[1]
        self.assertIn("existing prose", description)
        self.assertIn("request starts", description.lower())
        self.assertIn("do not use to draft new prose", description.lower())
        self.assertIn("same turn", description.lower())

    def test_code_frontmatter_excludes_implementation_work(self) -> None:
        description = self.code_skill.split("---", 2)[1]

        self.assertIn("already exist", description.lower())
        self.assertIn("do not use to implement features", description.lower())
        self.assertIn("write code", description.lower())
        self.assertIn("modify the project", description.lower())

    def test_code_contract_does_not_promote_untraced_security_signals(self) -> None:
        contract = self.code_skill.lower()

        for signal in ("variable name", "log label", "todo", "scanner signal"):
            with self.subTest(signal=signal):
                self.assertIn(signal, contract)

        self.assertIn("concrete evidence and uncertainty separately", contract)
        self.assertIn("trace the value, its capability, and its path to the log", contract)
        self.assertIn("keep the check at `needs_review`", contract)
        self.assertIn(
            "do not set the release decision to `block` solely from the signal",
            contract,
        )
        self.assertIn("report the signal", contract)
        self.assertIn(
            "do not rewrite the supplied patch unless the user explicitly asks for a patch",
            contract,
        )

    def test_code_release_decision_prioritizes_proven_blockers(self) -> None:
        checklist = CODE_CHECKLIST.read_text(encoding="utf-8")

        for contract in (self.code_skill, checklist):
            with self.subTest(document=contract[:40]):
                self.assertIn(
                    "A proven blocker takes precedence over missing checks",
                    contract,
                )
                self.assertIn(
                    "Keep every `NOT_RUN` check listed",
                    contract,
                )
                self.assertIn(
                    "If no blocker is proven, any required `NOT_RUN` check makes the decision `INCOMPLETE`",
                    contract,
                )


    def test_public_readme_does_not_advertise_blank_page_drafting_for_writing(self) -> None:
        readme = PUBLIC_README.read_text(encoding="utf-8")
        writing_section = readme.split("### One More Pass: Writing", 1)[1].split(
            "### One More Pass: Code", 1
        )[0]

        self.assertNotRegex(writing_section.lower(), r"\b(?:draft|drafting)\b")
        self.assertIn("existing prose", writing_section.lower())

    def test_social_prompt_example_removes_bait_without_inventing_a_next_step(self) -> None:
        examples = WRITING_EXAMPLES.read_text(encoding="utf-8")
        section = examples.split("## Remove a social prompt", 1)[1].split(
            "\n## ", 1
        )[0]
        quoted_lines = re.findall(r"(?m)^> (.+)$", section)

        self.assertEqual(len(quoted_lines), 2)
        before, after = quoted_lines
        source_words = set(re.findall(r"[a-z0-9]+", before.lower()))
        rewrite_words = set(re.findall(r"[a-z0-9]+", after.lower()))

        self.assertEqual(rewrite_words - source_words, set())
        for required_word in ("importer", "rejects", "stale", "rows"):
            with self.subTest(required_word=required_word):
                self.assertIn(required_word, rewrite_words)

    def test_writing_scope_protects_facts_and_excludes_code_behavior(self) -> None:
        self.assertIn("Writing reviews prose", self.skill)
        self.assertIn("does not review code behavior", self.skill)
        for protected in ("facts", "logic", "uncertainty", "quantities", "voice"):
            with self.subTest(protected=protected):
                self.assertIn(protected, self.skill.lower())

    def test_writing_routes_explicit_bot_post_cleanup_requests(self) -> None:
        description = self.skill.split("---", 2)[1]
        for trigger in (
            "engagement bait",
            "canned social hooks",
            "formulaic bot copy",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, description.lower())

    def test_manual_rule_blocks_unsupported_certainty(self) -> None:
        self.assertIn("`SLP-CLR-002`", self.writing_rules)
        self.assertIn("model-only", self.writing_rules.lower())
        self.assertIn("unsupported certainty", self.writing_rules.lower())

    def test_rewrite_contract_preserves_first_person_judgment_and_identity(self) -> None:
        for protected in (
            "first-person judgment",
            "identity-bearing",
            "I think",
        ):
            with self.subTest(protected=protected):
                self.assertIn(protected.lower(), self.writing_rewrite.lower())

    def test_dense_formula_example_keeps_the_claim_relationships(self) -> None:
        section = WRITING_EXAMPLES.read_text(encoding="utf-8").split(
            "## Remove a dense formula without dropping content", 1
        )[1].split("\n## ", 1)[0]
        quoted_lines = re.findall(r"(?m)^> (.+)$", section)

        self.assertEqual(2, len(quoted_lines))
        rewrite = quoted_lines[1]
        self.assertIn("speed alone is not enough", rewrite.lower())
        self.assertIn("clarity:", rewrite.lower())
        for item in ("clear plans", "crisp feedback", "confident execution"):
            with self.subTest(item=item):
                self.assertIn(item, rewrite.lower())

    def test_paired_request_routes_prose_and_code_to_separate_skills(self) -> None:
        self.assertIn("one-more-pass:code", self.skill)
        paired = next(case for case in self.routing["cases"] if case["mode"] == "paired")
        self.assertEqual(paired["expected_skills"], ["writing", "code"])

    def test_authorship_request_refuses_classification_and_offers_editorial_review(self) -> None:
        self.assertIn("## Authorship questions", self.skill)
        self.assertIn("Do not classify authorship", self.skill)
        self.assertIn("offer an editorial review", self.skill)

    def test_interface_prompt_requests_a_final_pass_on_existing_prose(self) -> None:
        self.assertIn("final pass", self.interface.lower())
        self.assertIn("existing prose", self.interface.lower())

    def test_scanner_instructions_do_not_depend_on_the_users_working_directory(self) -> None:
        for text in (self.writing_tools, self.code_skill):
            with self.subTest(document=text[:40]):
                self.assertNotIn("python3 scripts/scan.py", text)
                self.assertIn("same directory as this `SKILL.md`", text)
                self.assertIn("CLAUDE_PLUGIN_ROOT", text)


if __name__ == "__main__":
    unittest.main()
