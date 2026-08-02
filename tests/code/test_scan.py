from __future__ import annotations

from contextlib import redirect_stderr
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
SCRIPT = PLUGIN_ROOT / "skills" / "code" / "scripts" / "scan.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_scanner():
    spec = importlib.util.spec_from_file_location("one_more_pass_code_scan", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scanner from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


def json_report(*paths: Path | str, stdin: str | None = None):
    result = run_cli("--format", "json", *(str(path) for path in paths), stdin=stdin)
    return result, json.loads(result.stdout)


def non_pass_checks(report: dict) -> dict[str, dict]:
    return {
        check["id"]: check
        for check in report["checks"]
        if check["run_state"] != "PASS"
    }


class ScannerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = load_scanner()

    def test_version_and_schema_are_stable(self):
        version = run_cli("--version")
        schema = run_cli("--schema-version")

        self.assertEqual(version.returncode, 0)
        self.assertEqual(version.stdout.strip(), "one-more-pass:code 1.0.0")
        self.assertEqual(schema.returncode, 0)
        self.assertEqual(schema.stdout.strip(), "one-more-pass.code.scan 1.0.0")

    def test_rule_ids_use_the_owned_public_prefix(self):
        ids = {"OMP-CODE-000", *(rule.id for rule in self.scan.RULES)}

        self.assertTrue(all(rule_id.startswith("OMP-CODE-") for rule_id in ids))
        self.assertFalse(any(rule_id.startswith("SSC-") for rule_id in ids))

    def test_high_impact_fixture_matches_expected_ids(self):
        result, report = json_report(FIXTURES / "mechanical-positive.js")
        expected = json.loads(
            (FIXTURES / "mechanical-positive.expected.json").read_text(encoding="utf-8")
        )

        actual = {
            rule_id: check["run_state"]
            for rule_id, check in non_pass_checks(report).items()
        }
        self.assertEqual(result.returncode, 0)
        self.assertEqual(actual, expected)
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_strings_comments_and_handled_catches_do_not_trigger_signals(self):
        result, report = json_report(FIXTURES / "mechanical-negative.js")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(non_pass_checks(report), {})
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_quoted_not_implemented_example_is_not_a_placeholder(self):
        source = 'const sample = "throw new Error(\\"Not implemented\\")";\n'
        result, report = json_report("-", stdin=source)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(non_pass_checks(report), {})
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_runtime_not_implemented_throw_needs_review(self):
        result, report = json_report(
            "-", stdin='throw new Error("Not implemented");\n'
        )

        self.assertEqual(result.returncode, 0)
        check = non_pass_checks(report)["OMP-CODE-013"]
        self.assertEqual(check["run_state"], "NEEDS_REVIEW")
        self.assertEqual(check["patch_attribution"], "unknown")
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_rejected_not_implemented_error_needs_review(self):
        result, report = json_report(
            "-",
            stdin='return Promise.reject(new Error("Not yet implemented"));\n',
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            non_pass_checks(report)["OMP-CODE-013"]["run_state"],
            "NEEDS_REVIEW",
        )
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_unittest_skip_decorators_need_review(self):
        cases = (
            '@unittest.skip("later")\ndef test_x(self): pass\n',
            '@unittest.skipIf(sys.platform == "win32", "later")\ndef test_x(self): pass\n',
            '@unittest.skipUnless(HAS_API, "later")\ndef test_x(self): pass\n',
        )

        for source in cases:
            with self.subTest(source=source.splitlines()[0]):
                result, report = json_report("-", stdin=source)

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    non_pass_checks(report)["OMP-CODE-012"]["run_state"],
                    "NEEDS_REVIEW",
                )

    def test_literal_bracket_test_modifiers_need_review(self):
        for modifier in ("skip", "todo", "only"):
            with self.subTest(modifier=modifier):
                source = f'test["{modifier}"]("later", () => {{}});\n'
                result, report = json_report("-", stdin=source)

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    non_pass_checks(report)["OMP-CODE-012"]["run_state"],
                    "NEEDS_REVIEW",
                )

    def test_focused_test_rule_names_both_risks(self):
        rule = self.scan.RULE_BY_ID["OMP-CODE-012"]

        self.assertEqual(rule.title, "Disabled or focused test")
        self.assertIn("de-focus", rule.action)

    def test_optional_and_bracket_logging_calls_need_review(self):
        cases = (
            'console?.log("diagnostic");\n',
            'logger?.debug("diagnostic");\n',
            'console["log"]("diagnostic");\n',
            "logger['trace']('diagnostic');\n",
        )

        for source in cases:
            with self.subTest(source=source.strip()):
                result, report = json_report("-", stdin=source)

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    non_pass_checks(report)["OMP-CODE-019"]["run_state"],
                    "NEEDS_REVIEW",
                )

    def test_javascript_regex_literal_does_not_look_like_a_debugger_statement(self):
        source = "const pattern = /debugger;/;\n"

        result, report = json_report("-", stdin=source)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(non_pass_checks(report), {})
        self.assertEqual(
            report["scan_decision"]["status"],
            "NO_MECHANICAL_BLOCKER",
        )

    def test_review_signals_warn_without_blocking(self):
        result, report = json_report(FIXTURES / "review-positive.ts")
        expected = json.loads(
            (FIXTURES / "review-positive.expected.json").read_text(encoding="utf-8")
        )

        actual = {
            rule_id: check["run_state"]
            for rule_id, check in non_pass_checks(report).items()
        }
        self.assertEqual(result.returncode, 0)
        self.assertEqual(actual, expected)
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_high_impact_patterns_need_review_without_failing_scan(self):
        result, report = json_report(FIXTURES / "mechanical-positive.js")
        findings = [
            check
            for check in report["checks"]
            if check["id"] in {f"OMP-CODE-{index:03d}" for index in range(12, 18)}
            and check["run_state"] != "PASS"
        ]

        self.assertEqual(result.returncode, 0)
        self.assertEqual({check["run_state"] for check in findings}, {"NEEDS_REVIEW"})
        self.assertEqual({check["severity"] for check in findings}, {"blocker"})
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_intentional_contexts_are_signals_not_proven_failures(self):
        cases = (
            (
                "intentional platform skip",
                "@pytest.mark.skipif(sys.platform == 'win32', reason='Unix only')\n"
                "def test_unix_path():\n    assert path.is_absolute()\n",
                "OMP-CODE-012",
            ),
            (
                "deliberately unsupported branch",
                "if protocol_version < 2:\n"
                "    raise NotImplementedError('Version 1 is not supported')\n",
                "OMP-CODE-013",
            ),
            (
                "documented best effort cleanup",
                "try { removeTemporaryPreview(); } catch (error) {}\n",
                "OMP-CODE-015",
            ),
        )

        for label, source, rule_id in cases:
            with self.subTest(label=label):
                result, report = json_report("-", stdin=source)
                finding = non_pass_checks(report)[rule_id]

                self.assertEqual(result.returncode, 0)
                self.assertEqual(finding["run_state"], "NEEDS_REVIEW")
                self.assertEqual(finding["severity"], "blocker")
                self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_complete_pattern_scan_never_emits_fail_or_block(self):
        result, report = json_report(FIXTURES / "mechanical-positive.js")
        rendered = json.dumps(report)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(
            any(check["run_state"] == "FAIL" for check in report["checks"])
        )
        self.assertNotEqual(report["scan_decision"]["status"], "BLOCK")
        self.assertNotIn('"status": "BLOCK"', rendered)

    def test_reviewer_confirmed_failure_can_still_block_release(self):
        confirmed = self.scan.Check(
            id="OMP-CODE-016",
            run_state="FAIL",
            patch_attribution="introduced",
            evidence="src/server.ts:24 contains a debugger statement in shipped code.",
            action="Remove the debugger statement before release.",
            severity="blocker",
            path="src/server.ts",
            line=24,
        )

        decision = self.scan.release_decision([confirmed])

        self.assertEqual(decision["status"], "BLOCK")

    def test_clean_fixture_is_clear(self):
        result, report = json_report(FIXTURES / "clean.ts")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(non_pass_checks(report), {})
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_clean_scan_reports_a_scan_result_not_release_clearance(self):
        fixture = FIXTURES / "clean.ts"
        json_result, report = json_report(fixture)
        text_result = run_cli("--format", "text", str(fixture))

        self.assertEqual(json_result.returncode, 0)
        self.assertNotIn("release_decision", report)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )
        self.assertIn("SCAN NO_MECHANICAL_BLOCKER", text_result.stdout)
        self.assertNotIn("RELEASE", text_result.stdout)

    def test_every_check_has_required_state_fields(self):
        _, report = json_report(FIXTURES / "mechanical-positive.js")
        required = {
            "id",
            "run_state",
            "patch_attribution",
            "evidence",
            "action",
        }

        for check in report["checks"]:
            self.assertTrue(required.issubset(check), check)
            self.assertIn(
                check["run_state"], {"PASS", "FAIL", "NOT_RUN", "NEEDS_REVIEW"}
            )
            self.assertIn(
                check["patch_attribution"],
                {
                    "introduced",
                    "worsened",
                    "pre-existing",
                    "unknown",
                    "not-applicable",
                },
            )

    def test_stdin_is_an_explicit_input(self):
        result, report = json_report("-", stdin="debugger;\n")
        check = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(check["path"], "<stdin>")
        self.assertEqual(check["line"], 1)

    def test_crlf_unicode_preserves_line_and_evidence(self):
        source = "const café = 1;\r\nconsole.log(café);\r\n"
        result, report = json_report("-", stdin=source)
        check = non_pass_checks(report)["OMP-CODE-019"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(check["line"], 2)
        self.assertIn("café", check["evidence"])

    def test_text_and_json_have_state_parity(self):
        fixture = FIXTURES / "review-positive.ts"
        json_result, report = json_report(fixture)
        text_result = run_cli("--format", "text", str(fixture))
        pattern = re.compile(r"^CHECK\s+(OMP-CODE-\d+)\s+(PASS|FAIL|NOT_RUN|NEEDS_REVIEW)\b")
        text_states = {
            match.group(1): match.group(2)
            for line in text_result.stdout.splitlines()
            if (match := pattern.match(line))
        }
        json_states = {check["id"]: check["run_state"] for check in report["checks"]}

        self.assertEqual(json_result.returncode, text_result.returncode)
        self.assertEqual(text_states, json_states)
        self.assertIn(
            f"SCAN {report['scan_decision']['status']}", text_result.stdout
        )

    def test_diff_mode_ignores_removed_signal(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1 +1 @@
-debugger;
+safe();
"""
        result, report = json_report("--diff", "-", stdin=diff)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(non_pass_checks(report), {})
        self.assertEqual(report["scan_mode"], "unified-diff-added-lines")
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )
        self.assertFalse(
            any(
                "debugger" in check["evidence"]
                for check in report["checks"]
                if check["run_state"] != "PASS"
            )
        )

    def test_deleted_file_diff_with_no_added_lines_is_valid(self):
        diff = """diff --git a/a.js b/a.js
deleted file mode 100644
--- a/a.js
+++ /dev/null
@@ -1 +0,0 @@
-debugger;
"""
        result, report = json_report("--diff", "-", stdin=diff)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["text_block_count"], 0)
        self.assertEqual(report["findings_reported"], 0)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_diff_mode_flags_added_signal(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1 +1 @@
-safe();
+debugger;
"""
        result, report = json_report("--diff", "-", stdin=diff)
        check = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(check["run_state"], "NEEDS_REVIEW")
        self.assertEqual(check["patch_attribution"], "introduced")
        self.assertEqual(check["path"], "a.js")
        self.assertEqual(check["line"], 1)
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_diff_mode_keeps_added_increment_line_inside_hunk(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1 +1 @@
-count += 1;
+++ count; debugger;
"""
        result, report = json_report("--diff", "-", stdin=diff)
        check = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(check["patch_attribution"], "introduced")
        self.assertEqual(check["path"], "a.js")
        self.assertEqual(check["line"], 1)

    def test_diff_mode_does_not_treat_added_header_like_text_as_file_header(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1,2 +1,2 @@
-old();
-safe();
+++ b/not-a-header
+debugger;
"""
        result, report = json_report("--diff", "-", stdin=diff)
        check = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(check["patch_attribution"], "introduced")
        self.assertEqual(check["path"], "a.js")
        self.assertEqual(check["line"], 2)

    def test_unmarked_unified_diff_is_rejected(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1 +1 @@
-debugger;
+safe();
"""
        result = run_cli("--format", "json", "-", stdin=diff)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("--diff", result.stderr)

    def test_diff_hunk_without_new_file_header_is_rejected(self):
        diff = """diff --git a/a.js b/a.js
@@ -1 +1 @@
-safe();
+debugger;
"""
        result = run_cli("--diff", "--format", "json", "-", stdin=diff)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("+++", result.stderr)

    def test_diff_with_malformed_hunk_header_is_rejected(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ malformed @@
+debugger;
"""
        result = run_cli("--diff", "--format", "json", "-", stdin=diff)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("hunk header", result.stderr)

    def test_diff_with_added_line_outside_hunk_is_rejected(self):
        diff = """diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
+debugger;
"""
        result = run_cli("--diff", "--format", "json", "-", stdin=diff)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("outside a hunk", result.stderr)

    def test_scan_does_not_modify_input(self):
        fixture = FIXTURES / "mechanical-positive.js"
        before = hashlib.sha256(fixture.read_bytes()).hexdigest()

        run_cli("--format", "json", str(fixture))

        after = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_no_input_and_directory_are_invalid_invocations(self):
        no_input = run_cli("--format", "json")
        directory = run_cli("--format", "json", str(FIXTURES))

        self.assertEqual(no_input.returncode, 2)
        self.assertEqual(directory.returncode, 2)

    def test_unexpected_scanner_failure_uses_exit_three(self):
        original = self.scan.scan_paths

        def fail_scan(_paths):
            raise RuntimeError("forced test failure")

        self.scan.scan_paths = fail_scan
        stderr = io.StringIO()
        try:
            with redirect_stderr(stderr):
                code = self.scan.main([str(FIXTURES / "clean.ts")])
        finally:
            self.scan.scan_paths = original

        self.assertEqual(code, 3)
        self.assertIn("internal error", stderr.getvalue())

    def test_invalid_invocation_redacts_secrets_and_escapes_terminal_controls(self):
        secret = "ghp_" + ("a" * 36)
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            path = Path(directory) / f"bad\x1b[31m-{secret}"
            path.mkdir()
            result = run_cli(str(path))

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("\x1b", result.stderr)
        self.assertNotIn(secret, result.stderr)
        self.assertIn(r"\x1b", result.stderr)
        self.assertIn("[REDACTED]", result.stderr)

    def test_missing_input_is_not_run_and_incomplete_not_block(self):
        result, report = json_report(FIXTURES / "missing.py")
        states = [check["run_state"] for check in report["checks"]]

        self.assertEqual(result.returncode, 2)
        self.assertIn("NOT_RUN", states)
        self.assertNotIn("PASS", states)
        self.assertNotIn("BLOCK", states)
        self.assertEqual(report["scan_decision"]["status"], "INCOMPLETE")

    def test_symlink_and_oversized_inputs_are_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target.ts"
            link = root / "link.ts"
            large = root / "large.ts"
            target.write_text("export const ok = true;\n", encoding="utf-8")
            link.symlink_to(target)
            large.write_text("x" * (2 * 1024 * 1024 + 1), encoding="utf-8")

            link_result, link_report = json_report(link)
            large_result, large_report = json_report(large)

        self.assertEqual(link_result.returncode, 2)
        self.assertEqual(link_report["scan_decision"]["status"], "INCOMPLETE")
        self.assertIn("Symlink", json.dumps(link_report))
        self.assertEqual(large_result.returncode, 2)
        self.assertEqual(large_report["scan_decision"]["status"], "INCOMPLETE")
        self.assertIn("limit", json.dumps(large_report))

    def test_files_below_symlinked_directories_are_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target_directory = root / "target"
            linked_directory = root / "linked"
            target_directory.mkdir()
            (target_directory / "input.ts").write_bytes(b"\xff")
            linked_directory.symlink_to(target_directory, target_is_directory=True)

            result, report = json_report(linked_directory / "input.ts")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["scan_decision"]["status"], "INCOMPLETE")
        rendered = json.dumps(report)
        self.assertIn("Symlink", rendered)
        self.assertNotIn("UTF-8", rendered)

    def test_pre_existing_failure_is_not_attributed_to_patch(self):
        fixture = json.loads(
            (FIXTURES / "pre-existing-release-gate.json").read_text(encoding="utf-8")
        )
        checks = [self.scan.Check.from_dict(item) for item in fixture["checks"]]

        report = self.scan.build_report(checks, input_count=1)

        self.assertEqual(report["checks"][0]["run_state"], "FAIL")
        self.assertEqual(report["checks"][0]["patch_attribution"], "pre-existing")
        decision = self.scan.release_decision(checks)
        self.assertEqual(decision["status"], "BLOCK")
        self.assertIn("pre-existing", decision["evidence"])

    def test_not_run_check_stays_not_run_and_uses_exit_two(self):
        fixture = json.loads(
            (FIXTURES / "required-check-not-run.json").read_text(encoding="utf-8")
        )
        checks = [self.scan.Check.from_dict(item) for item in fixture["checks"]]

        report = self.scan.build_report(checks, input_count=1)

        self.assertEqual(report["checks"][0]["run_state"], "NOT_RUN")
        self.assertEqual(self.scan.release_decision(checks)["status"], "INCOMPLETE")
        self.assertEqual(self.scan.exit_code_for(report), 2)

    def test_secret_evidence_is_redacted(self):
        secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        result, report = json_report("-", stdin=f'const token = "{secret}";\n')
        check = non_pass_checks(report)["OMP-CODE-017"]

        self.assertEqual(result.returncode, 0)
        self.assertNotIn(secret, json.dumps(report))
        self.assertIn("REDACTED", check["evidence"])

    def test_fine_grained_github_and_npm_tokens_are_flagged_and_redacted(self):
        secrets = (
            "github_pat_" + ("a" * 64),
            "npm_" + ("b" * 36),
        )

        for secret in secrets:
            with self.subTest(prefix=secret.split("_", 1)[0]):
                source = f'const token = "{secret}"; debugger;\n'
                json_result, report = json_report("-", stdin=source)
                text_result = run_cli("--format", "text", "-", stdin=source)

                self.assertEqual(json_result.returncode, 0, json_result.stderr)
                self.assertEqual(text_result.returncode, 0, text_result.stderr)
                self.assertIn("OMP-CODE-017", non_pass_checks(report))
                self.assertNotIn(secret, json_result.stdout)
                self.assertNotIn(secret, text_result.stdout)
                self.assertIn("REDACTED", json_result.stdout)
                self.assertIn("REDACTED", text_result.stdout)

    def test_modern_ai_provider_keys_are_flagged_and_redacted(self):
        secrets = (
            "sk-proj-" + ("a" * 48),
            "sk-ant-api03-" + ("b" * 48),
        )

        for secret in secrets:
            with self.subTest(prefix=secret.split("-", 2)[:2]):
                source = f'const token = "{secret}"; debugger;\n'
                json_result, report = json_report("-", stdin=source)
                text_result = run_cli("--format", "text", "-", stdin=source)

                self.assertEqual(json_result.returncode, 0, json_result.stderr)
                self.assertEqual(text_result.returncode, 0, text_result.stderr)
                self.assertIn("OMP-CODE-017", non_pass_checks(report))
                self.assertNotIn(secret, json_result.stdout)
                self.assertNotIn(secret, text_result.stdout)
                self.assertIn("REDACTED", json_result.stdout)
                self.assertIn("REDACTED", text_result.stdout)

    def test_broad_output_redaction_covers_a_secret_missed_by_detection(self):
        secret = "Bearer " + ("z" * 48)
        source = f'const authorization = "{secret}"; debugger;\n'

        json_result, report = json_report("-", stdin=source)
        text_result = run_cli("--format", "text", "-", stdin=source)

        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertNotIn("OMP-CODE-017", non_pass_checks(report))
        self.assertIn("OMP-CODE-016", non_pass_checks(report))
        self.assertNotIn(secret, json_result.stdout)
        self.assertNotIn(secret, text_result.stdout)
        self.assertIn("REDACTED", json_result.stdout)
        self.assertIn("REDACTED", text_result.stdout)

    def test_javascript_private_access_does_not_hide_later_debugger(self):
        source = "class A { run() { this.#value = 1; debugger; } }\n"

        result, report = json_report("-", stdin=source)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OMP-CODE-016", non_pass_checks(report))

    def test_javascript_private_declaration_does_not_hide_later_signals(self):
        source = "class A { #value = 1; run(): any { debugger; } }\n"

        result, report = json_report("-", stdin=source)
        findings = non_pass_checks(report)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OMP-CODE-016", findings)
        self.assertIn("OMP-CODE-020", findings)

    def test_secret_is_redacted_from_another_rules_source_evidence(self):
        secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        padding = "x" * 138
        source = f'const note = "{padding}"; const token = "{secret}"; debugger;\n'

        json_result, report = json_report("-", stdin=source)
        text_result = run_cli("--format", "text", "-", stdin=source)
        debugger = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(text_result.returncode, 0)
        self.assertIn("REDACTED", debugger["evidence"])
        self.assertNotIn(secret[:12], json_result.stdout)
        self.assertNotIn(secret[:12], text_result.stdout)

    def test_secret_is_redacted_from_another_rules_diff_evidence(self):
        secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        diff = f"""diff --git a/a.js b/a.js
--- a/a.js
+++ b/a.js
@@ -1 +1 @@
-safe();
+const token = "{secret}"; debugger;
"""

        json_result, report = json_report("--diff", "-", stdin=diff)
        text_result = run_cli("--diff", "--format", "text", "-", stdin=diff)
        debugger = non_pass_checks(report)["OMP-CODE-016"]

        self.assertEqual(json_result.returncode, 0)
        self.assertEqual(text_result.returncode, 0)
        self.assertIn("REDACTED", debugger["evidence"])
        self.assertNotIn(secret, json_result.stdout)
        self.assertNotIn(secret, text_result.stdout)

    def test_terminal_controls_are_escaped_in_text_and_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "report\x1b[31m.ts"
            path.write_text("debugger;\x1b[31m\n", encoding="utf-8")

            text_result = run_cli("--format", "text", str(path))
            json_result = run_cli("--format", "json", str(path))

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        self.assertNotIn("\x1b", text_result.stdout)
        self.assertIn(r"\x1b", text_result.stdout)
        self.assertNotIn("\x1b", json_result.stdout)
        self.assertIn(r"\u001b", json_result.stdout)
        json.loads(json_result.stdout)

    def test_direction_controls_are_escaped_in_text_json_paths_and_errors(self):
        controls = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u2028\u2029"
        secret = "sk-ant-api03-" + ("c" * 48)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / f"report{controls}.ts"
            path.write_text("debugger;\n", encoding="utf-8")

            text_result = run_cli("--format", "text", str(path))
            json_result, report = json_report(path)
            bad_path = root / f"bad{controls}-{secret}"
            bad_path.mkdir()
            error_result = run_cli(str(bad_path))

        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        self.assertEqual(error_result.returncode, 2)
        rendered_json = json.dumps(report, ensure_ascii=False)
        for character in controls:
            self.assertNotIn(character, text_result.stdout)
            self.assertNotIn(character, rendered_json)
            self.assertNotIn(character, error_result.stderr)
        self.assertIn(r"\u202e", text_result.stdout)
        self.assertIn(r"\u202e", rendered_json)
        self.assertIn(r"\u202e", error_result.stderr)
        self.assertNotIn(secret, error_result.stderr)
        self.assertIn("[REDACTED]", error_result.stderr)

    def test_repeated_high_impact_signals_are_capped_without_blocking(self):
        source = "debugger;\n" * 10_000
        result, report = json_report("-", stdin=source)
        findings = [
            check
            for check in report["checks"]
            if check["id"] == "OMP-CODE-016"
            and check["run_state"] == "NEEDS_REVIEW"
        ]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(findings), 25)
        self.assertEqual(report["findings_omitted"], 9_975)
        self.assertTrue(report["truncated"])
        self.assertLess(len(report["checks"]), 50)
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")
        truncation = [
            check
            for check in report["checks"]
            if check["id"] == "OMP-CODE-000"
            and check["run_state"] == "NEEDS_REVIEW"
        ]
        self.assertEqual(len(truncation), 1)

    def test_repeated_warnings_are_capped_without_false_block(self):
        source = "// TODO: inspect this path\n" * 10_000
        result, report = json_report("-", stdin=source)
        findings = [
            check
            for check in report["checks"]
            if check["id"] == "OMP-CODE-018" and check["run_state"] == "NEEDS_REVIEW"
        ]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(findings), 25)
        self.assertEqual(report["findings_omitted"], 9_975)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")

    def test_too_many_explicit_inputs_is_rejected_before_reading(self):
        result = run_cli("--format", "json", *(["missing.ts"] * 257))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("256", result.stderr)

    def test_input_count_includes_a_file_not_read_after_combined_limit(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root).resolve()
            paths = []
            for index in range(5):
                path = root_path / f"input-{index}.ts"
                path.write_text("x" * (2 * 1024 * 1024), encoding="utf-8")
                paths.append(path)

            result, report = json_report(*paths)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["input_count"], 5)
        self.assertEqual(report["readable_input_count"], 4)
        self.assertEqual(report["scan_decision"]["status"], "INCOMPLETE")

    def test_empty_file_is_readable_after_exact_combined_byte_limit(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root).resolve()
            paths = []
            for index in range(4):
                path = root_path / f"full-{index}.ts"
                path.write_text("x" * (2 * 1024 * 1024), encoding="utf-8")
                paths.append(path)
            empty = root_path / "empty.ts"
            empty.write_text("", encoding="utf-8")
            paths.append(empty)

            result, report = json_report(*paths)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["input_count"], 5)
        self.assertEqual(report["readable_input_count"], 5)
        self.assertEqual(report["text_block_count"], 5)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_empty_stdin_is_readable_after_exact_combined_byte_limit(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root).resolve()
            paths = []
            for index in range(4):
                path = root_path / f"full-{index}.ts"
                path.write_text("x" * (2 * 1024 * 1024), encoding="utf-8")
                paths.append(path)

            result, report = json_report(*paths, "-", stdin="")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["input_count"], 5)
        self.assertEqual(report["readable_input_count"], 5)
        self.assertEqual(report["text_block_count"], 5)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_total_finding_count_is_capped_across_rules(self):
        lines: list[str] = []
        for index in range(30):
            lines.extend(
                (
                    f'test.skip("case {index}", () => {{}});',
                    'throw new Error("Not implemented");',
                    "/* eslint-disable */",
                    "try { run(); } catch (error) {}",
                    "debugger;",
                    f'const token{index} = "ghp_{index:036d}";',
                    "// TODO: inspect this path",
                    "console.log(payload);",
                    f"const value{index}: any = payload;",
                    "// eslint-disable-next-line no-console -- reviewed output",
                )
            )
        result, report = json_report("-", stdin="\n".join(lines) + "\n")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["findings_reported"], 200)
        self.assertEqual(report["finding_limits"]["total"], 200)
        self.assertEqual(report["findings_omitted"], 100)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["scan_decision"]["status"], "NEEDS_REVIEW")
        self.assertFalse(
            any(
                check["id"] in {"OMP-CODE-020", "OMP-CODE-021"}
                and check["run_state"] == "PASS"
                for check in report["checks"]
            )
        )

    def test_empty_diff_is_a_valid_scan_with_no_added_lines(self):
        result, report = json_report("--diff", "-", stdin="")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["scan_mode"], "unified-diff-added-lines")
        self.assertEqual(report["findings_reported"], 0)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_metadata_only_diff_is_a_valid_scan_with_no_added_lines(self):
        diff = """diff --git a/a.js b/a.js
old mode 100644
new mode 100755
"""
        result, report = json_report("--diff", "-", stdin=diff)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["scan_mode"], "unified-diff-added-lines")
        self.assertEqual(report["text_block_count"], 0)
        self.assertEqual(report["findings_reported"], 0)
        self.assertEqual(
            report["scan_decision"]["status"], "NO_MECHANICAL_BLOCKER"
        )

    def test_binary_diff_is_not_run_and_requires_another_review_tool(self):
        diff = """diff --git a/image.png b/image.png
new file mode 100644
index 0000000..1111111
GIT binary patch
literal 4
LcmeAS@N?(olHy`u
"""

        result, report = json_report("--diff", "-", stdin=diff)
        states = [check["run_state"] for check in report["checks"]]

        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["text_block_count"], 0)
        self.assertEqual(report["scan_decision"]["status"], "INCOMPLETE")
        self.assertIn("NOT_RUN", states)
        self.assertNotIn("PASS", states)
        self.assertIn("binary", json.dumps(report).lower())

    def test_release_clear_requires_every_manual_review_check(self):
        mechanical_pass = self.scan.Check(
            id="OMP-CODE-016",
            run_state="PASS",
            patch_attribution="not-applicable",
            evidence="The debugger pattern did not match.",
            action="Complete the manual review.",
        )

        self.assertEqual(self.scan.release_decision([])["status"], "INCOMPLETE")
        self.assertEqual(
            self.scan.release_decision([mechanical_pass])["status"], "INCOMPLETE"
        )

        manual_passes = [
            self.scan.Check(
                id=f"OMP-CODE-{index:03d}",
                run_state="PASS",
                patch_attribution="not-applicable",
                evidence=f"Manual check OMP-CODE-{index:03d} completed.",
                action="Keep the recorded evidence.",
            )
            for index in range(1, 12)
        ]
        self.assertEqual(
            self.scan.release_decision(manual_passes)["status"], "CLEAR"
        )

        nonblocking_failure = [
            replace(
                check,
                run_state="FAIL",
                evidence="The reuse check found local duplication.",
                severity="warning",
            )
            if check.id == "OMP-CODE-007"
            else check
            for check in manual_passes
        ]
        decision = self.scan.release_decision(nonblocking_failure)
        self.assertEqual(decision["status"], "CLEAR")
        self.assertNotIn("passed", decision["evidence"].lower())
        self.assertIn("ran", decision["evidence"].lower())


if __name__ == "__main__":
    unittest.main()
