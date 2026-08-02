from __future__ import annotations

import json
import unittest
from pathlib import Path


FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PATHS = {
    "writing": FIXTURES / "writing-cases.json",
    "code": FIXTURES / "code-cases.json",
}
CASE_FIELDS = {
    "id",
    "route",
    "expected_skill",
    "prompt",
    "input",
    "required_facts",
    "protected_spans",
    "forbidden_changes",
    "expected_output_traits",
    "results",
}
CAPTURE_FIELDS = {
    "client",
    "client_version",
    "model",
    "captured_at",
    "prompt",
    "input",
    "output",
    "review",
}
REVIEW_FIELDS = {
    "trigger_observed",
    "required_facts_preserved",
    "relationships_preserved",
    "protected_spans_preserved",
    "forbidden_changes_absent",
    "expected_traits_observed",
    "notes",
}


class FixtureContractTests(unittest.TestCase):
    def load_fixture(self, skill: str) -> dict:
        path = FIXTURE_PATHS[skill]
        self.assertTrue(path.is_file(), f"missing fixture: {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_fixture_schema_and_case_fields_are_complete(self) -> None:
        all_ids: list[str] = []

        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            with self.subTest(skill=skill):
                self.assertEqual(1, fixture["schema_version"])
                self.assertEqual(skill, fixture["skill"])
                self.assertGreaterEqual(len(fixture["cases"]), 4)
                self.assertEqual(
                    sorted(CAPTURE_FIELDS),
                    sorted(fixture["record_format"]["capture_fields"]),
                )
                self.assertEqual(
                    sorted(REVIEW_FIELDS),
                    sorted(fixture["record_format"]["review_fields"]),
                )

            for case in fixture["cases"]:
                with self.subTest(case=case.get("id", "missing-id")):
                    self.assertEqual(CASE_FIELDS, set(case))
                    self.assertRegex(case["id"], rf"^{skill.upper()}-PRESSURE-\d{{3}}$")
                    self.assertIn(case["route"], {"trigger", "non-trigger"})
                    self.assertTrue(case["prompt"].strip())
                    self.assertTrue(case["input"].strip())
                all_ids.append(case["id"])

        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_each_skill_has_trigger_and_non_trigger_cases(self) -> None:
        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            routes = {case["route"] for case in fixture["cases"]}
            self.assertEqual({"trigger", "non-trigger"}, routes, skill)

            for case in fixture["cases"]:
                expected_skill = skill if case["route"] == "trigger" else None
                with self.subTest(case=case["id"]):
                    self.assertEqual(expected_skill, case["expected_skill"])

    def test_non_trigger_cases_do_not_forbid_the_requested_work(self) -> None:
        conflicting_traits = {
            "does-not-perform-blank-page-drafting",
            "does-not-implement",
        }

        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            for case in fixture["cases"]:
                if case["route"] != "non-trigger":
                    continue
                with self.subTest(case=case["id"]):
                    self.assertTrue(
                        conflicting_traits.isdisjoint(case["expected_output_traits"])
                    )

    def test_protected_spans_are_exact_source_text(self) -> None:
        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            for case in fixture["cases"]:
                spans = case["protected_spans"]
                with self.subTest(case=case["id"]):
                    self.assertTrue(spans)
                    self.assertEqual(len(spans), len(set(spans)))
                    for span in spans:
                        self.assertTrue(span)
                        self.assertIn(span, case["input"])

    def test_cases_have_reviewable_expectations(self) -> None:
        required_traits = {
            "writing": {
                "preserves-negation",
                "preserves-uncertainty",
                "preserves-quotations",
                "leaves-valid-contrast-intact",
                "does-not-trigger",
                "removes-engagement-bait",
                "preserves-first-person-judgment",
                "keeps-ordinary-work-instructions",
            },
            "code": {
                "separates-signal-from-defect",
                "preserves-not-run",
                "keeps-patch-attribution",
                "does-not-trigger",
            },
        }

        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            observed_traits: set[str] = set()
            for case in fixture["cases"]:
                with self.subTest(case=case["id"]):
                    for field in (
                        "required_facts",
                        "forbidden_changes",
                        "expected_output_traits",
                    ):
                        values = case[field]
                        self.assertTrue(values, field)
                        self.assertEqual(len(values), len(set(values)), field)
                        self.assertTrue(all(isinstance(value, str) and value for value in values))
                    for trait in case["expected_output_traits"]:
                        self.assertRegex(trait, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                    observed_traits.update(case["expected_output_traits"])

            self.assertTrue(
                required_traits[skill].issubset(observed_traits),
                required_traits[skill] - observed_traits,
            )

    def test_result_slots_accept_only_the_saved_capture_format(self) -> None:
        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            for case in fixture["cases"]:
                results = case["results"]
                with self.subTest(case=case["id"]):
                    self.assertEqual({"no_skill", "skill_assisted"}, set(results))

                for result_name, captures in results.items():
                    self.assertIsInstance(captures, list)
                    for capture in captures:
                        with self.subTest(case=case["id"], result=result_name):
                            self.assertEqual(CAPTURE_FIELDS, set(capture))
                            self.assertEqual(case["prompt"], capture["prompt"])
                            self.assertEqual(case["input"], capture["input"])
                            for field in (
                                "client",
                                "client_version",
                                "model",
                                "captured_at",
                                "output",
                            ):
                                self.assertIsInstance(capture[field], str)
                                self.assertTrue(capture[field])

                            review = capture["review"]
                            self.assertEqual(REVIEW_FIELDS, set(review))
                            self.assertIn(review["trigger_observed"], {True, False, None})
                            for field in (
                                "required_facts_preserved",
                                "relationships_preserved",
                                "protected_spans_preserved",
                                "forbidden_changes_absent",
                                "expected_traits_observed",
                            ):
                                self.assertIsInstance(review[field], list)
                                self.assertTrue(
                                    all(isinstance(value, str) for value in review[field])
                                )
                            self.assertIsInstance(review["notes"], str)

                            self.assertTrue(
                                set(review["required_facts_preserved"]).issubset(
                                    case["required_facts"]
                                )
                            )
                            self.assertTrue(
                                set(review["protected_spans_preserved"]).issubset(
                                    case["protected_spans"]
                                )
                            )
                            self.assertTrue(
                                set(review["forbidden_changes_absent"]).issubset(
                                    case["forbidden_changes"]
                                )
                            )
                            self.assertTrue(
                                set(review["expected_traits_observed"]).issubset(
                                    case["expected_output_traits"]
                                )
                            )

    def test_writing_fixtures_cover_bot_post_and_work_message(self) -> None:
        fixture = self.load_fixture("writing")
        cases = {case["id"]: case for case in fixture["cases"]}

        bot_post = cases["WRITING-PRESSURE-005"]
        self.assertEqual("trigger", bot_post["route"])
        self.assertIn(
            "preserves-first-person-judgment",
            bot_post["expected_output_traits"],
        )
        self.assertIn("removes-engagement-bait", bot_post["expected_output_traits"])

        work_message = cases["WRITING-PRESSURE-006"]
        self.assertEqual("trigger", work_message["route"])
        self.assertIn(
            "keeps-ordinary-work-instructions",
            work_message["expected_output_traits"],
        )

    def test_fixture_text_contains_no_em_dash(self) -> None:
        em_dash = chr(0x2014)
        for skill in FIXTURE_PATHS:
            fixture = self.load_fixture(skill)
            serialized = json.dumps(fixture, ensure_ascii=False)
            self.assertNotIn(em_dash, serialized, skill)


if __name__ == "__main__":
    unittest.main()
