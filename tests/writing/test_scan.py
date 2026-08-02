from __future__ import annotations

import ast
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest


TEST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TEST_ROOT.parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
ROOT = PLUGIN_ROOT / "skills" / "writing"
SCRIPT = ROOT / "scripts" / "scan.py"
FIXTURES = TEST_ROOT / "fixtures"


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def json_result(*args: str, input_text: str | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = run_cli("--format", "json", *args, input_text=input_text)
    payload = json.loads(result.stdout)
    return result, payload


class ScannerContractTests(unittest.TestCase):
    def test_version_and_schema(self) -> None:
        version = run_cli("--version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout, "one-more-pass:writing 1.0.0\n")

        result, payload = json_result("--fail-on", "never", str(FIXTURES / "clean.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["version"], "1.0.0")
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["omitted"], {"total": 0, "by_rule": {}})

    def test_no_arguments_and_directory_are_usage_errors(self) -> None:
        no_args = run_cli()
        self.assertEqual(no_args.returncode, 2)
        self.assertIn("at least one explicit file or -", no_args.stderr)

        directory = run_cli(str(FIXTURES))
        self.assertEqual(directory.returncode, 2)
        self.assertIn("not a regular file", directory.stderr)

    def test_invalid_utf8_is_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "invalid.txt"
            path.write_bytes(b"valid\n\xff\n")
            result = run_cli(str(path))
        self.assertEqual(result.returncode, 2)
        self.assertIn("UTF-8", result.stderr)

    def test_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target.md"
            link = root / "link.md"
            target.write_text("Plain prose.\n", encoding="utf-8")
            link.symlink_to(target)
            result = run_cli(str(link))
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr.lower())

    def test_files_below_symlinked_directories_are_rejected_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target_directory = root / "target"
            linked_directory = root / "linked"
            target_directory.mkdir()
            (target_directory / "input.md").write_bytes(b"\xff")
            linked_directory.symlink_to(target_directory, target_is_directory=True)

            result = run_cli(str(linked_directory / "input.md"))

        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr.lower())
        self.assertNotIn("utf-8", result.stderr.lower())

    def test_file_and_stdin_inputs_are_bounded(self) -> None:
        oversized = "x" * (2 * 1024 * 1024 + 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "large.md"
            path.write_text(oversized, encoding="utf-8")
            file_result = run_cli(str(path))
        stdin_result = run_cli("-", input_text=oversized)

        self.assertEqual(file_result.returncode, 2)
        self.assertIn("limit", file_result.stderr.lower())
        self.assertEqual(stdin_result.returncode, 2)
        self.assertIn("limit", stdin_result.stderr.lower())

    def test_input_count_is_limited_to_256(self) -> None:
        path = str(FIXTURES / "clean.md")
        result = run_cli(*([path] * 257))
        self.assertEqual(result.returncode, 2)
        self.assertIn("256", result.stderr)

    def test_combined_input_is_limited_to_eight_mib(self) -> None:
        chunk = "plain prose\n" * 150_000
        self.assertLess(len(chunk.encode("utf-8")), 2 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = []
            for index in range(5):
                path = root / f"part-{index}.md"
                path.write_text(chunk, encoding="utf-8")
                paths.append(str(path))
            result = run_cli(*paths)
        self.assertEqual(result.returncode, 2)
        self.assertIn("combined", result.stderr.lower())
        self.assertIn("8388608", result.stderr)

    def test_unexpected_scanner_failure_uses_exit_code_three(self) -> None:
        namespace = runpy.run_path(str(SCRIPT), run_name="one_more_pass_writing_scan_test")

        def fail_scan(_text: str, _source: str):
            raise RuntimeError("forced test failure")

        namespace["main"].__globals__["scan_text"] = fail_scan
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = namespace["main"]([str(FIXTURES / "clean.md")])
        self.assertEqual(code, 3)
        self.assertIn("internal error", stderr.getvalue())

    def test_input_error_redacts_secrets_and_escapes_terminal_controls(self) -> None:
        secret = "ghp_" + ("a" * 36)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / f"missing\x1b[31m-{secret}.md"
            result = run_cli(str(missing))

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("\x1b", result.stderr)
        self.assertNotIn(secret, result.stderr)
        self.assertIn(r"\x1b", result.stderr)
        self.assertIn("[REDACTED]", result.stderr)

    def test_clean_fixture_has_no_findings(self) -> None:
        result, payload = json_result(str(FIXTURES / "clean.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["summary"]["total"], 0)

    def test_strict_default_returns_nonzero_for_a_house_warning(self) -> None:
        result = run_cli("-", input_text="The patch shipped—latency fell by 12%.")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("SLP-HSE-001", result.stdout)

    def test_every_unprotected_em_dash_is_reported(self) -> None:
        text = "One—two.\nThree—four.\nFive—six.\n"
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        em_dash_findings = [
            finding for finding in payload["findings"]
            if finding["rule_id"] == "SLP-HSE-001"
        ]
        self.assertEqual(len(em_dash_findings), 3)
        self.assertEqual([finding["line"] for finding in em_dash_findings], [1, 2, 3])

    def test_per_rule_limit_reports_exact_omitted_count(self) -> None:
        text = "\n".join(f"left—right {index}" for index in range(30))
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        em_dash_findings = [
            finding for finding in payload["findings"]
            if finding["rule_id"] == "SLP-HSE-001"
        ]
        self.assertEqual(len(em_dash_findings), 25)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["omitted"]["total"], 5)
        self.assertEqual(payload["omitted"]["by_rule"], {"SLP-HSE-001": 5})

    def test_report_limit_reports_exact_omitted_count(self) -> None:
        namespace = runpy.run_path(str(SCRIPT), run_name="one_more_pass_report_limit_test")
        finding_type = namespace["Finding"]
        findings = [
            finding_type(
                rule_id=f"SLP-TEST-{index % 9:03d}",
                category="house-style",
                severity="warning",
                confidence="high",
                source="fixture.md",
                line=index + 1,
                column=1,
                excerpt=f"line {index + 1}",
                message="Review this line.",
            )
            for index in range(225)
        ]
        payload = namespace["build_payload"](findings, {})
        self.assertEqual(len(payload["findings"]), 200)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["omitted"]["total"], 25)
        self.assertEqual(sum(payload["omitted"]["by_rule"].values()), 25)

    def test_true_positive_fixture_reports_layered_stable_ids(self) -> None:
        result, payload = json_result("--fail-on", "never", str(FIXTURES / "formulaic.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertTrue(
            {
                "SLP-LEX-001",
                "SLP-LEX-002",
                "SLP-LEX-003",
                "SLP-PHR-002",
                "SLP-SYN-001",
                "SLP-ENG-001",
                "SLP-HSE-001",
            }.issubset(ids),
            ids,
        )
        for finding in payload["findings"]:
            self.assertEqual(
                {
                    "rule_id",
                    "category",
                    "severity",
                    "confidence",
                    "source",
                    "line",
                    "column",
                    "excerpt",
                    "message",
                },
                set(finding),
            )

    def test_watched_words_outside_the_density_window_do_not_form_a_cluster(self) -> None:
        text = "The report delves into one topic. " + ("plain detail " * 520) + "An intricate constraint appears later."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("SLP-LEX-001", {finding["rule_id"] for finding in payload["findings"]})

    def test_local_filler_needs_a_cluster(self) -> None:
        one_word = "The deterministic algorithm returns the same bytes for the same input."
        clustered = "A robust substrate unlocks seamless workflows."

        one_result, one_payload = json_result(
            "--fail-on", "never", "-", input_text=one_word
        )
        cluster_result, cluster_payload = json_result(
            "--fail-on", "never", "-", input_text=clustered
        )

        self.assertEqual(one_result.returncode, 0, one_result.stderr)
        self.assertNotIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in one_payload["findings"]},
        )
        self.assertEqual(cluster_result.returncode, 0, cluster_result.stderr)
        self.assertIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in cluster_payload["findings"]},
        )

    def test_precise_domain_terms_do_not_form_a_filler_cluster(self) -> None:
        text = (
            "The robust regression uses a deterministic algorithm. "
            "The canonical URL names the array slice used in the example."
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_canonical_surface_is_exempt_only_in_geometry_context(self) -> None:
        technical = (
            "The canonical surface in contact geometry is computed by "
            "a deterministic algorithm."
        )
        filler = "The canonical surface unlocks a seamless workflow."

        technical_result, technical_payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text=technical,
        )
        filler_result, filler_payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text=filler,
        )

        self.assertEqual(technical_result.returncode, 0, technical_result.stderr)
        self.assertNotIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in technical_payload["findings"]},
        )
        self.assertEqual(filler_result.returncode, 0, filler_result.stderr)
        self.assertIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in filler_payload["findings"]},
        )

    def test_single_strong_hooks_and_empty_frames_are_reported(self) -> None:
        cases = (
            ("Let that sink in.", "SLP-ENG-001"),
            ("The uncomfortable truth is that the rollout failed.", "SLP-HSE-003"),
            ("It turns out the importer dropped 43 rows.", "SLP-HSE-003"),
            ("Read that again.", "SLP-ENG-001"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_social_engagement_prompts_are_reported_individually(self) -> None:
        text = "Agree? Comment below. Repost this. Follow for more."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        social = [
            finding for finding in payload["findings"]
            if finding["rule_id"] == "SLP-ENG-002"
        ]
        self.assertEqual(len(social), 4)

    def test_work_instructions_are_not_social_engagement_prompts(self) -> None:
        cases = (
            "Share this file with legal before the deadline.",
            "Save this document before closing the editor.",
            "Do the source and generated totals agree?",
            "Tag someone in the incident ticket so ownership is clear.",
            "Comment below the failing line in the diff.",
            "Tag someone who owns the incident.",
            "Repost this incident update in #ops.",
            "Bookmark this function in the debugger.",
            "Share if the checksum matches the release record.",
            "Save for later processing when the queue recovers.",
            "Repost to help the incident team reach on-call staff.",
            "Follow me through the debugger.",
            "The source and generated totals agree or disagree based on rounding.",
            "Drop your thoughts into notes.md before the review.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-ENG-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_common_hook_and_social_prompt_variants_are_reported(self) -> None:
        cases = (
            ("Here is the thing: the importer failed.", "SLP-ENG-001"),
            ("Let. That. Sink. In.", "SLP-ENG-001"),
            ("Nobody's talking about this.", "SLP-ENG-001"),
            ("Re-post this.", "SLP-ENG-002"),
            ("Agree ?", "SLP-ENG-002"),
            ("Comment beneath this post.", "SLP-ENG-002"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_common_social_bait_is_reported(self) -> None:
        cases = (
            ("Stop scrolling.", "SLP-ENG-001"),
            ("Nobody is talking about this.", "SLP-ENG-001"),
            ("Hot take: this changed everything.", "SLP-ENG-001"),
            ("I wasn't going to post this.", "SLP-ENG-001"),
            ("This won't be up for long.", "SLP-ENG-001"),
            ("Bookmark this.", "SLP-ENG-002"),
            ("Tag someone who needs this.", "SLP-ENG-002"),
            ("Drop a YES in the comments.", "SLP-ENG-002"),
            ("Share if this resonates.", "SLP-ENG-002"),
            ("Save for later.", "SLP-ENG-002"),
            ("Repost to help your network.", "SLP-ENG-002"),
            ("Follow me for more.", "SLP-ENG-002"),
            ("Agree or disagree?", "SLP-ENG-002"),
            ("Drop your thoughts below.", "SLP-ENG-002"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_common_engagement_farming_variants_are_reported(self) -> None:
        cases = (
            "Like this if you agree.",
            "Repost if you agree.",
            "Save it for later.",
            "Send this to someone who needs to hear it.",
            "Let me know what you think in the comments.",
            "DM me GUIDE and I will send the template.",
            "COMMENT\nBELOW",
            "DROP YOUR THOUGHTS\nBELOW.",
            "Repost this 🔁",
            "Share this if you agree.",
            "Send this to someone who needs this.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-ENG-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_more_engagement_farming_forms_are_reported(self) -> None:
        cases = (
            "Do you agree?",
            "What is your take?",
            "Tell me in the comments.",
            "Comment 'GUIDE' and I will send you the template.",
            "Reply 'YES' and I will DM you the link.",
            "If this helped, save it and share it with your network.",
            "Tag a founder who needs to see this.",
            "Follow me to learn how to build with AI.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-ENG-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_more_fixed_canned_hooks_are_reported(self) -> None:
        cases = (
            "Hard truth: the release is late.",
            "Unpopular opinion: fewer features would help.",
            "This is your sign to rewrite the importer.",
            "I learned this the hard way.",
            "Read this twice.",
            "The part nobody tells you: maintenance takes time.",
            "We are entering a new era.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-ENG-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_more_empty_house_frames_are_reported(self) -> None:
        cases = (
            "At its core, this is a parser.",
            "It is worth noting that the build failed.",
            "At the end of the day, the test still fails.",
            "When it comes to releases, the checksum matters.",
            "In a world where builds fail, logs matter.",
            "The reality is that the file is empty.",
            "Let's dive in.",
            "Let me break it down.",
            "I will say it again: the test failed.",
            "I am going to be honest: the patch is late.",
            "Without further ado, here is the report.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-HSE-003",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_extended_ellipsis_hook_is_reported(self) -> None:
        for text in ("Let... That... Sink... In.", "Let… That… Sink… In."):
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-ENG-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_each_fixed_hook_and_empty_frame_is_reported(self) -> None:
        text = (
            "Here's the thing. Let that sink in. "
            "It turns out the import failed. The truth is the file was empty."
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        counts = {
            rule_id: sum(
                finding["rule_id"] == rule_id
                for finding in payload["findings"]
            )
            for rule_id in ("SLP-ENG-001", "SLP-HSE-003")
        }
        self.assertEqual(counts, {"SLP-ENG-001": 2, "SLP-HSE-003": 2})

    def test_stale_business_filler_uses_the_cluster_gate(self) -> None:
        text = "We can lean into the deep dive, then circle back moving forward."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_repeated_same_family_phrase_qualifies(self) -> None:
        text = "This article explores one claim. This article explores a second claim."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-PHR-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_single_meta_signpost_near_an_edge_qualifies(self) -> None:
        cases = (
            "This essay will explore the issue. The migration has three risks.",
            "The migration has three risks. In conclusion, the third risk remains open.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-PHR-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_single_meta_signpost_in_a_long_document_middle_does_not_qualify(self) -> None:
        text = (
            ("plain detail " * 130)
            + "This article explores one detail. "
            + ("more plain detail " * 130)
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-PHR-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_repeated_focal_and_elevated_words_qualify(self) -> None:
        cases = (
            ("The report delves into one claim. It delves into another.", "SLP-LEX-001"),
            ("The first tapestry was literal. The second tapestry was also literal.", "SLP-LEX-002"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_strong_structural_templates_are_review_signals(self) -> None:
        cases = (
            ("Speed. And scale. And trust.", "SLP-SYN-004"),
            ("What changed? The importer now rejects stale rows.", "SLP-SYN-005"),
            ("It is not just faster; it is transformative.", "SLP-SYN-001"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_more_formulaic_structures_are_review_signals(self) -> None:
        cases = (
            ("This is not a feature. This is a movement.", "SLP-SYN-001"),
            ("Not because it was easy. Because it mattered.", "SLP-SYN-001"),
            ("No dashboards. No meetings. Just results.", "SLP-SYN-004"),
            ("The result? Faster launches.", "SLP-SYN-005"),
            ("Why? Because teams need proof.", "SLP-SYN-005"),
            ("The bottom line: the importer dropped 43 rows.", "SLP-HSE-003"),
            ("The bottom line is the importer dropped 43 rows.", "SLP-HSE-003"),
        )
        for text, expected_rule in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    expected_rule,
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_valid_counterexamples_remain_clean(self) -> None:
        text = (
            "Safari, not Chrome, drops the cookie. "
            "The endpoint requires account_id, region, and checksum. "
            "The samples were stored at −80 °C before analysis. "
            "I ain't gonna pretend this shit worked; y'all saw it crash twice."
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["findings"], [])

    def test_protected_em_dashes_are_not_reported(self) -> None:
        text = (
            "The source title is “Design—Systems at Work.”\n"
            "Run `tool --name=a—b`.\n"
            "Open /tmp/a—b/report.md.\n"
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_more_source_titles_quotes_and_paths_are_protected(self) -> None:
        cases = (
            "‘Design—Systems at Work’ is the source title.",
            "Read *Design—Systems at Work* before the review.",
            "The source says, “The patch shipped—\nthen latency fell.”",
            "Open /Users/Mark/My Project/Design—Systems.md.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-HSE-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_formulaic_emphasized_prose_is_not_mistaken_for_a_title(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text="*This Is Important—Read That Again.*",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-HSE-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_html_em_dash_entity_is_reported_outside_protected_text(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text="The patch shipped&mdash;latency fell by 12%.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-HSE-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_numeric_html_em_dash_entities_are_reported(self) -> None:
        for entity in ("&#8212;", "&#x2014;"):
            with self.subTest(entity=entity):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=f"The patch shipped{entity}latency fell by 12%.",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "SLP-HSE-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_frontmatter_em_dash_is_reported(self) -> None:
        text = "---\ntitle: Left—right\n---\nPlain body.\n"
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-HSE-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_paths_identifiers_packages_and_source_titles_are_protected(self) -> None:
        text = (
            "The package exports @primitree/surface and calls graph.surface.resolve().\n"
            "Open ~/surface/canonical.json or C:\\agency\\slice\\config.json.\n"
            "The source title is *The Canonical Surface&mdash;A Field Guide*.\n"
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertNotIn("SLP-HSE-001", ids)
        self.assertNotIn("SLP-HSE-002", ids)

    def test_capitalized_markdown_emphasis_does_not_hide_formulaic_prose(self) -> None:
        text = (
            "*Here's the thing: let that sink in.* The importer failed.\n"
            "_Stop scrolling. Comment below._\n"
        )
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        counts = {
            rule_id: sum(
                finding["rule_id"] == rule_id
                for finding in payload["findings"]
            )
            for rule_id in ("SLP-ENG-001", "SLP-ENG-002")
        }
        self.assertEqual(counts, {"SLP-ENG-001": 3, "SLP-ENG-002": 1})

    def test_precise_serialization_terms_do_not_form_a_filler_cluster(self) -> None:
        text = "The parser produces canonical JSON and deterministic byte output."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-002",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_more_precise_technical_terms_do_not_form_a_filler_cluster(self) -> None:
        cases = (
            "The canonical schema uses deterministic ordering.",
            "The robust estimator uses canonical correlations.",
            "The deterministic parser accepts a canonical syntax.",
            "The canonical schemas use deterministic parsers and robust estimators.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-HSE-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_more_precise_domain_terms_do_not_form_a_filler_cluster(self) -> None:
        cases = (
            "The public API surface aligns with the React package.",
            "The Redux slice aligns state with the server response.",
            "Use robust standard errors and deterministic bootstrap samples.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-HSE-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_accounting_language_is_not_an_empty_frame(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text="The bottom line is $10.00.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-003",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_phrasal_verb_is_not_an_empty_frame(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text="It turns out the light when the door opens.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-003",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_contextual_markdown_link_title_is_protected(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text=(
                "Read [Design—Systems at Work](https://example.com/book)."
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-HSE-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_hot_take_in_a_title_sentence_is_not_a_canned_hook(self) -> None:
        result, payload = json_result(
            "--fail-on",
            "never",
            "-",
            input_text="Hot take is the show title.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "SLP-ENG-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_ordinary_instructions_are_not_canned_hooks(self) -> None:
        cases = (
            "Think about it overnight and tell me tomorrow.",
            "Replace the comma with a full stop.",
            "The plot twist occurs in chapter six.",
            "Stop scrolling when the footer appears.",
            "Read that again before you approve the contract.",
            "I attached two logo options. Thoughts?",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result("--fail-on", "never", "-", input_text=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-ENG-001",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_work_messages_are_not_giveaway_prompts(self) -> None:
        cases = (
            "DM me LOG and I will send the patch.",
            "Send this to someone who owns the incident.",
            "Share this file if legal approves it.",
            "Save it for later processing.",
        )
        for text in cases:
            with self.subTest(text=text):
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=text,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(
                    "SLP-ENG-002",
                    {finding["rule_id"] for finding in payload["findings"]},
                )

    def test_failure_thresholds(self) -> None:
        path = str(FIXTURES / "formulaic.md")
        errors_only = run_cli("--fail-on", "error", path)
        warnings = run_cli("--fail-on", "warning", path)
        never = run_cli("--fail-on", "never", path)
        self.assertEqual(errors_only.returncode, 0, errors_only.stderr)
        self.assertEqual(warnings.returncode, 1, warnings.stderr)
        self.assertEqual(never.returncode, 0, never.stderr)

    def test_text_and_json_have_finding_parity(self) -> None:
        path = str(FIXTURES / "formulaic.md")
        text_result = run_cli("--format", "text", "--fail-on", "never", path)
        json_process, payload = json_result("--fail-on", "never", path)
        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_process.returncode, 0, json_process.stderr)
        text_ids = set(re.findall(r"\bSLP-[A-Z]+-\d{3}\b", text_result.stdout))
        json_ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertEqual(text_ids, json_ids)

    def test_secret_shapes_are_redacted_without_hiding_the_rest_of_the_excerpt(self) -> None:
        github_token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        aws_access_key = "AKIAABCDEFGHIJKLMNOP"
        text = (
            f"Here is the thing: keep token {github_token} private. Let that sink in.\n"
            f"Here is the thing: keep key {aws_access_key} private. Let that sink in.\n"
        )

        text_result = run_cli("--format", "text", "--fail-on", "never", "-", input_text=text)
        json_process, payload = json_result("--fail-on", "never", "-", input_text=text)

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_process.returncode, 0, json_process.stderr)
        self.assertNotIn(github_token, text_result.stdout)
        self.assertNotIn(aws_access_key, text_result.stdout)
        self.assertNotIn(github_token, json_process.stdout)
        self.assertNotIn(aws_access_key, json_process.stdout)
        self.assertIn("[REDACTED]", text_result.stdout)
        self.assertIn("[REDACTED]", json.dumps(payload))
        self.assertIn("keep token", text_result.stdout)
        self.assertIn("keep key", text_result.stdout)

    def test_modern_ai_provider_keys_are_redacted_from_unrelated_findings(self) -> None:
        secrets = (
            "sk-proj-" + ("a" * 48),
            "sk-ant-api03-" + ("b" * 48),
        )
        text = "\n".join(
            f"Here is the thing: keep {secret} private."
            for secret in secrets
        )

        text_result = run_cli(
            "--format", "text", "--fail-on", "never", "-", input_text=text
        )
        json_result = run_cli(
            "--format", "json", "--fail-on", "never", "-", input_text=text
        )

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        for secret in secrets:
            self.assertNotIn(secret, text_result.stdout)
            self.assertNotIn(secret, json_result.stdout)
        self.assertGreaterEqual(text_result.stdout.count("[REDACTED]"), 2)
        self.assertGreaterEqual(json_result.stdout.count("[REDACTED]"), 2)

    def test_secret_is_redacted_before_excerpt_truncation(self) -> None:
        secret = "ghp_" + ("a" * 36)
        lead = "Here is the thing: "
        line = lead + ("x" * (137 - len(lead))) + " " + secret + " private."

        text_result = run_cli(
            "--format", "text", "--fail-on", "never", "-", input_text=line
        )
        json_process, payload = json_result(
            "--fail-on", "never", "-", input_text=line
        )

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_process.returncode, 0, json_process.stderr)
        self.assertNotIn(secret[:-1], text_result.stdout)
        self.assertNotIn(secret[:-1], json_process.stdout)
        self.assertIn("[REDACTED]", text_result.stdout)
        self.assertIn("[REDACTED]", json.dumps(payload))

    def test_fine_grained_github_and_npm_tokens_are_redacted(self) -> None:
        secrets = (
            "github_pat_" + ("a" * 64),
            "npm_" + ("b" * 36),
        )
        text = "\n".join(
            f"Here is the thing: keep {secret} private."
            for secret in secrets
        )

        text_result = run_cli(
            "--format", "text", "--fail-on", "never", "-", input_text=text
        )
        json_process, payload = json_result(
            "--fail-on", "never", "-", input_text=text
        )

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_process.returncode, 0, json_process.stderr)
        for secret in secrets:
            self.assertNotIn(secret, text_result.stdout)
            self.assertNotIn(secret, json_process.stdout)
        self.assertGreaterEqual(text_result.stdout.count("[REDACTED]"), 2)
        self.assertGreaterEqual(json.dumps(payload).count("[REDACTED]"), 2)

    def test_terminal_controls_are_escaped_in_text_and_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "report\x1b[31m.md"
            path.write_text(
                "Here is the thing:\x1b[31m this delves into an intricate system.\n",
                encoding="utf-8",
            )

            text_result = run_cli("--format", "text", "--fail-on", "never", str(path))
            json_process = run_cli("--format", "json", "--fail-on", "never", str(path))

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_process.returncode, 0, json_process.stderr)
        self.assertNotIn("\x1b", text_result.stdout)
        self.assertIn(r"\x1b", text_result.stdout)
        self.assertNotIn("\x1b", json_process.stdout)
        self.assertIn(r"\u001b", json_process.stdout)
        json.loads(json_process.stdout)

    def test_direction_controls_are_escaped_in_text_json_paths_and_errors(self) -> None:
        controls = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u2028\u2029"
        secret = "sk-proj-" + ("c" * 48)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / f"report{controls}.md"
            path.write_text("Here is the thing: review this text.\n", encoding="utf-8")

            text_result = run_cli(
                "--format", "text", "--fail-on", "never", str(path)
            )
            json_result = run_cli(
                "--format", "json", "--fail-on", "never", str(path)
            )
            missing = root / f"missing{controls}-{secret}.md"
            error_result = run_cli(str(missing))

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        self.assertEqual(error_result.returncode, 2)
        parsed = json.loads(json_result.stdout)
        rendered_json = json.dumps(parsed, ensure_ascii=False)
        for character in controls:
            self.assertNotIn(character, text_result.stdout)
            self.assertNotIn(character, rendered_json)
            self.assertNotIn(character, error_result.stderr)
        self.assertIn(r"\u202e", text_result.stdout)
        self.assertIn(r"\u202e", rendered_json)
        self.assertIn(r"\u202e", error_result.stderr)
        self.assertNotIn(secret, error_result.stderr)
        self.assertIn("[REDACTED]", error_result.stderr)

    def test_stdin_uses_stable_source_name(self) -> None:
        text = (FIXTURES / "formulaic.md").read_text(encoding="utf-8")
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["findings"])
        self.assertEqual({finding["source"] for finding in payload["findings"]}, {"<stdin>"})

    def test_markdown_code_quotes_blockquotes_and_urls_are_masked(self) -> None:
        result, payload = json_result(str(FIXTURES / "masked.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["findings"], [])

        namespace = runpy.run_path(str(SCRIPT), run_name="one_more_pass_writing_mask_test")
        original = (FIXTURES / "masked.md").read_text(encoding="utf-8")
        masked = namespace["mask_protected_text"](original)
        self.assertEqual(len(masked), len(original))
        self.assertEqual(
            [index for index, character in enumerate(masked) if character == "\n"],
            [index for index, character in enumerate(original) if character == "\n"],
        )

    def test_frontmatter_links_indented_code_html_code_and_single_quotes_are_masked(self) -> None:
        protected = """---
title: delves into an intricate topic
---
[read more](../delves/intricate)
    The example delves into an intricate system.
<code>The example delves into an intricate system.</code>
'The example delves into an intricate system.'
"""
        result, payload = json_result("--fail-on", "never", "-", input_text=protected)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["findings"], [])

    def test_visible_html_and_link_text_remain_scannable(self) -> None:
        prose = "<p>[The paper delves into an intricate model](guide.md).</p>"
        result, payload = json_result("--fail-on", "never", "-", input_text=prose)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "SLP-LEX-001",
            {finding["rule_id"] for finding in payload["findings"]},
        )

    def test_crlf_unicode_and_input_hash_are_preserved(self) -> None:
        content = (
            "Résumé: naïve café.\r\n"
            "Here's the thing: an intricate system delves into a rich tapestry—let that sink in.\r\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "crlf-unicode.md"
            path.write_bytes(content)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            result, payload = json_result("--fail-on", "never", str(path))
            after = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)
        self.assertTrue(payload["findings"])
        self.assertTrue(any(finding["line"] == 2 for finding in payload["findings"]))

    def test_curly_apostrophes_match_complete_structures(self) -> None:
        text = "Here’s the thing: it’s not just fast; it’s vague. Let that sink in."
        result, payload = json_result("--fail-on", "never", "-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertIn("SLP-SYN-001", ids)
        self.assertIn("SLP-ENG-001", ids)

    def test_fixture_hash_is_unchanged(self) -> None:
        path = FIXTURES / "formulaic.md"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        result = run_cli("--fail-on", "never", str(path))
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)

    def test_red_cases(self) -> None:
        data = json.loads((FIXTURES / "red_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["cases"]), 10)
        for case in data["cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["preserve"])
                for token in case["preserve"] + case["remove"]:
                    self.assertIn(token, case["text"])
                rewrite_preserve = case.get("rewrite_preserve", case["preserve"])
                for token in rewrite_preserve:
                    self.assertIn(token, case["rewrite"])
                for token in case["remove"]:
                    self.assertNotIn(token, case["rewrite"])
                result, payload = json_result(
                    "--fail-on",
                    "never",
                    "-",
                    input_text=case["text"],
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    {finding["rule_id"] for finding in payload["findings"]},
                    set(case["expected_rule_ids"]),
                )

    def test_scanner_source_has_no_mutating_or_expansive_capabilities(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(
            imports.issubset(
                {"__future__", "argparse", "bisect", "dataclasses", "json", "pathlib", "re", "sys", "typing"}
            ),
            imports,
        )
        self.assertTrue({"subprocess", "socket", "urllib", "http", "requests"}.isdisjoint(imports))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"eval", "exec", "compile"}.isdisjoint(called_names))
        self.assertNotIn("--fix", source)
        self.assertNotIn("rglob(", source)
        self.assertNotIn("os.walk", source)
        self.assertNotRegex(source, r"\.write_(?:text|bytes)\(")


class SkillPackageTests(unittest.TestCase):
    def test_required_package_files_and_removed_stale_references(self) -> None:
        skill_files = {
            "agents/openai.yaml",
            "scripts/scan.py",
            "references/research-signals.md",
            "references/prose-rules.md",
            "references/house-style.md",
            "references/rewrite-rules.md",
            "references/optional-tools.md",
            "references/examples.md",
            "SKILL.md",
        }
        repository_files = {"README.md", "CHANGELOG.md", "LICENSE"}
        self.assertTrue(all((ROOT / path).is_file() for path in skill_files))
        self.assertTrue((TEST_ROOT / "PRESSURE_TEST.md").is_file())
        self.assertTrue(
            all((REPO_ROOT / path).is_file() for path in repository_files)
        )
        self.assertTrue((PLUGIN_ROOT / "LICENSE").is_file())
        self.assertFalse((ROOT / "tests").exists())
        self.assertFalse((ROOT / "references" / "phrases.md").exists())
        self.assertFalse((ROOT / "references" / "structures.md").exists())

    def test_rewrite_contract_names_every_meaning_check(self) -> None:
        contract = (ROOT / "references" / "rewrite-rules.md").read_text(encoding="utf-8").lower()
        for term in (
            "facts",
            "negation",
            "modality",
            "quantities",
            "quotations",
            "code",
            "urls",
            "identifiers",
            "voice",
            "dialect",
            "profanity",
        ):
            with self.subTest(term=term):
                self.assertIn(term, contract)

    def test_rewrite_contract_removes_unsupported_closes_instead_of_softening_them(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
        contract = (ROOT / "references" / "rewrite-rules.md").read_text(
            encoding="utf-8"
        ).lower()
        combined = skill + "\n" + contract
        self.assertIn("remove the whole closing sentence", combined)
        self.assertIn("do not soften", combined)
        self.assertIn("this underscores the need for transparency", combined)

    def test_rewrite_mode_returns_only_the_requested_prose(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("return only the revised prose", skill)
        self.assertIn("do not append findings, commentary, or source-check notes", skill)

    def test_manual_rules_cover_context_that_regex_cannot_prove(self) -> None:
        rules = (ROOT / "references" / "prose-rules.md").read_text(encoding="utf-8")
        for rule_id in ("SLP-SYN-002", "SLP-FMT-001", "SLP-CLR-001"):
            with self.subTest(rule_id=rule_id):
                self.assertIn(rule_id, rules)
        for phrase in (
            "decorative three-part list",
            "repeated presentation shape",
            "unsupported praise",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules.lower())

    def test_original_author_and_license_credit_are_preserved(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        runtime_license = (PLUGIN_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Hardik Pandya (https://hvpandya.com)", skill)
        self.assertIn("[Hardik Pandya](https://hvpandya.com)", readme)
        self.assertIn("Copyright (c) 2025 Hardik Pandya", license_text)
        self.assertEqual(license_text, runtime_license)

    def test_skill_and_interface_metadata(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill.split("---", 2)[1]
        keys = {
            line.split(":", 1)[0]
            for line in frontmatter.splitlines()
            if line and not line.startswith((" ", "\t")) and ":" in line
        }
        self.assertEqual(keys, {"name", "description"})
        self.assertIn("name: writing", frontmatter)

        interface = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "One More Pass: Writing"', interface)
        self.assertIn('short_description: "Edit prose without losing its meaning or voice"', interface)
        self.assertIn("$one-more-pass:writing", interface)

    def test_public_writing_files_have_no_em_dash(self) -> None:
        public_files = [ROOT / "SKILL.md", ROOT / "agents" / "openai.yaml"]
        public_files.extend(sorted((ROOT / "references").glob("*.md")))
        offenders = [
            str(path.relative_to(PLUGIN_ROOT))
            for path in public_files
            if "—" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
