from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "run-behavior-case.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("one_more_pass_behavior", HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load behavior harness")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BehaviorHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = load_harness()

    def test_writing_pressure_001_does_not_require_a_review_only_source_flag(self) -> None:
        fixture = json.loads(
            (REPO_ROOT / "tests/behavior/fixtures/writing-cases.json").read_text(
                encoding="utf-8"
            )
        )
        case = next(
            item for item in fixture["cases"] if item["id"] == "WRITING-PRESSURE-001"
        )

        self.assertNotIn("flags-missing-source", case["expected_output_traits"])
        self.assertIn("removes-unsupported-close", case["expected_output_traits"])

    def test_request_keeps_the_fixture_prompt_and_input_exact(self) -> None:
        case = {
            "prompt": "Rewrite only what needs changing.",
            "input": "A line with `code` and a URL: https://example.test/a.",
        }

        request = self.harness.render_request(case)

        self.assertEqual(
            "Rewrite only what needs changing.\n\nInput:\n"
            "A line with `code` and a URL: https://example.test/a.",
            request,
        )

    def test_codex_command_is_ephemeral_read_only_and_noninteractive(self) -> None:
        command = self.harness.build_codex_command(
            request="Review this.",
            model="gpt-5.6-sol",
            workdir=Path("/tmp/omp-case"),
        )
        joined = " ".join(command)

        self.assertIn("--ephemeral", command)
        self.assertIn("--strict-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn("--sandbox read-only", joined)
        self.assertIn('approval_policy="never"', command)
        self.assertIn('shell_environment_policy.inherit="none"', command)
        self.assertIn("--json", command)
        self.assertNotIn("dangerously-bypass", joined)

    def test_claude_command_allows_skill_reads_but_denies_mutation(self) -> None:
        command = self.harness.build_claude_command(
            request="Review this.",
            model="opus",
            plugin_root=Path("/tmp/plugin"),
        )
        joined = " ".join(command)

        self.assertIn("--no-session-persistence", command)
        self.assertIn("--output-format stream-json", joined)
        self.assertIn("--permission-mode dontAsk", joined)
        self.assertIn("--setting-sources  --permission-mode", joined)
        self.assertIn("--tools=Skill,Read", command)
        self.assertNotIn("--allowedTools", command)
        self.assertNotIn("--disallowedTools", command)
        self.assertIn("--add-dir /tmp/plugin", joined)
        self.assertIn("--plugin-dir /tmp/plugin", joined)
        self.assertNotIn("dangerously-skip", joined)

    def test_claude_baseline_command_does_not_load_the_plugin(self) -> None:
        command = self.harness.build_claude_command(
            request="Draft this.",
            model="opus",
            plugin_root=None,
        )

        self.assertNotIn("--plugin-dir", command)

    def test_claude_tools_flag_cannot_consume_the_prompt(self) -> None:
        command = self.harness.build_claude_command(
            request="Draft this.",
            model="opus",
            plugin_root=None,
        )

        self.assertIn("--tools=Skill,Read", command)
        self.assertNotIn("--tools", command)
        self.assertEqual("Draft this.", command[-1])

    def test_normal_claude_profile_rejects_one_more_pass_before_baseline(self) -> None:
        installed = json.dumps(
            [
                {"id": "superpowers@claude-plugins-official", "enabled": True},
                {"id": "one-more-pass@one-more-pass-private", "enabled": True},
            ]
        )

        conflicts = self.harness.claude_profile_conflicts(installed)

        self.assertEqual(["one-more-pass@one-more-pass-private"], conflicts)

    def test_normal_claude_profile_allows_unrelated_plugins(self) -> None:
        installed = json.dumps(
            [
                {"id": "superpowers@claude-plugins-official", "enabled": True},
                {"id": "context7@claude-plugins-official", "enabled": True},
            ]
        )

        self.assertEqual([], self.harness.claude_profile_conflicts(installed))

    def test_normal_claude_profile_rejects_malformed_plugin_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "plugin inventory"):
            self.harness.claude_profile_conflicts("not json")

    def test_codex_route_proof_uses_command_events_not_assistant_claims(self) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "I used one-more-pass:writing.",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "sed -n '1,240p' /tmp/cache/skills/writing/SKILL.md",
                    "aggregated_output": "# One More Pass: Writing",
                },
            },
        ]

        proof = self.harness.codex_route_proof(events, "writing")

        self.assertTrue(proof.observed)
        self.assertEqual("command_execution", proof.method)
        self.assertNotIn("agent_message", proof.evidence)

    def test_codex_assistant_claim_alone_is_not_route_proof(self) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "I used one-more-pass:code.",
                },
            }
        ]

        proof = self.harness.codex_route_proof(events, "code")

        self.assertFalse(proof.observed)
        self.assertEqual("none", proof.method)

    def test_claude_route_proof_uses_skill_tool_event(self) -> None:
        events = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "one-more-pass:writing"},
                        }
                    ]
                },
            }
        ]

        proof = self.harness.claude_route_proof(events, "writing")

        self.assertTrue(proof.observed)
        self.assertEqual("skill_tool", proof.method)

    def test_baseline_capture_uses_null_route_state(self) -> None:
        proof = self.harness.RouteProof(False, "none", "")

        capture = self.harness.make_capture_template(
            client="codex",
            client_version="codex-cli 0.146.0",
            model="gpt-5.6-sol",
            prompt="Review this.",
            input_text="Input.",
            output="Result.",
            arm="baseline",
            proof=proof,
        )

        self.assertIsNone(capture["review"]["trigger_observed"])
        self.assertEqual("Input.", capture["input"])
        self.assertEqual([], capture["review"]["relationships_preserved"])
        self.assertEqual([], capture["review"]["expected_traits_observed"])

    def test_private_matrix_stays_bounded_after_bot_post_case_is_added(self) -> None:
        readme = (REPO_ROOT / "tests/behavior/README.md").read_text(encoding="utf-8")

        self.assertIn("`WRITING-PRESSURE-005`", readme)
        self.assertIn("20 fresh sessions", readme)
        self.assertIn("`WRITING-PRESSURE-006`", readme)
        self.assertIn("not part of the required matrix", readme)

    def test_preflight_docs_name_the_normal_claude_profile_guard(self) -> None:
        readme = (REPO_ROOT / "tests/behavior/README.md").read_text(encoding="utf-8")

        self.assertIn("normal Claude profile", readme)
        self.assertIn("taint the baseline", readme)

    def test_temporary_codex_home_copies_auth_with_owner_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "auth.json"
            source.write_text('{"token":"secret"}', encoding="utf-8")

            with self.harness.temporary_codex_home(source) as codex_home:
                copied = codex_home / "auth.json"
                mode = stat.S_IMODE(copied.stat().st_mode)
                self.assertEqual(0o600, mode)
                self.assertEqual(source.read_bytes(), copied.read_bytes())
                copied_home = codex_home

            self.assertFalse(copied_home.exists())

    def test_parse_json_lines_rejects_non_json_client_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-JSON output"):
            self.harness.parse_json_lines("not json\n", client="codex")

    def test_route_contract_requires_trigger_and_rejects_non_trigger_activation(self) -> None:
        self.assertTrue(
            self.harness.route_matches(route="trigger", arm="plugin", observed=True)
        )
        self.assertTrue(
            self.harness.route_matches(route="non-trigger", arm="plugin", observed=False)
        )
        self.assertFalse(
            self.harness.route_matches(route="trigger", arm="plugin", observed=False)
        )
        self.assertFalse(
            self.harness.route_matches(route="non-trigger", arm="plugin", observed=True)
        )
        self.assertTrue(
            self.harness.route_matches(route="trigger", arm="baseline", observed=False)
        )

    def test_secret_like_client_output_is_refused_before_persistence(self) -> None:
        with self.assertRaisesRegex(self.harness.HarnessError, "secret-like"):
            self.harness.assert_no_secret_like_text(
                "authorization: Bearer abcdefghijklmnopqrstuvwxyz012345",
                source="trace",
            )

    def test_unsafe_fixture_text_is_refused_before_client_launch_or_persistence(
        self,
    ) -> None:
        unsafe_values = {
            "OpenAI API key": "sk-proj-" + ("a" * 48),
            "Anthropic API key": "sk-ant-api03-" + ("b" * 48),
            "GitHub fine-grained token": "github_pat_" + ("c" * 64),
            "npm granular token": "npm_" + ("d" * 36),
            "Unicode direction controls": (
                "safe\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                "\u2066\u2067\u2068\u2069\u2028\u2029text"
            ),
        }

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            auth_source = temp_root / "auth.json"
            auth_source.write_text("{}", encoding="utf-8")

            for client in ("codex", "claude"):
                for field in ("prompt", "input"):
                    for label, unsafe_value in unsafe_values.items():
                        with self.subTest(client=client, field=field, value=label):
                            case = {
                                "id": "UNSAFE-PRESSURE-001",
                                "route": "trigger",
                                "expected_skill": "writing",
                                "prompt": "Review this existing prose.",
                                "input": "Safe input.",
                            }
                            case[field] = unsafe_value
                            output_dir = (
                                temp_root
                                / f"{client}-{field}-{label.replace(' ', '-')}"
                            )

                            with mock.patch.object(
                                self.harness,
                                "run_checked",
                                side_effect=AssertionError("client launched"),
                            ) as run_checked:
                                with self.assertRaisesRegex(
                                    self.harness.HarnessError,
                                    "secret-like|direction control",
                                ):
                                    if client == "codex":
                                        self.harness.run_codex_case(
                                            case=case,
                                            skill="writing",
                                            arm="baseline",
                                            model="gpt-5.6-sol",
                                            output_dir=output_dir,
                                            auth_source=auth_source,
                                        )
                                    else:
                                        self.harness.run_claude_case(
                                            case=case,
                                            skill="writing",
                                            arm="baseline",
                                            model="opus",
                                            output_dir=output_dir,
                                        )

                            run_checked.assert_not_called()
                            self.assertFalse(output_dir.exists())

    def test_capture_template_rechecks_prompt_and_input_before_creating_directory(
        self,
    ) -> None:
        unsafe_fields = {
            "prompt": "sk-proj-" + ("a" * 48),
            "input": "text\u202ehidden",
        }

        with tempfile.TemporaryDirectory() as temp:
            for field, unsafe_value in unsafe_fields.items():
                with self.subTest(field=field):
                    capture = {
                        "prompt": "Review this.",
                        "input": "Safe input.",
                        "output": "Safe output.",
                    }
                    capture[field] = unsafe_value
                    output_dir = Path(temp) / field

                    with self.assertRaisesRegex(
                        self.harness.HarnessError,
                        "secret-like|direction control",
                    ):
                        self.harness.save_run(
                            output_dir=output_dir,
                            raw_trace='{"type":"result"}\n',
                            stderr="",
                            output="Safe output.",
                            metadata={"case": "UNSAFE-PRESSURE-001"},
                            capture=capture,
                        )

                    self.assertFalse(output_dir.exists())

    def test_client_output_direction_controls_are_refused_before_persistence(
        self,
    ) -> None:
        unsafe_outputs = {
            "trace": {
                "raw_trace": f'{{"text":"safe{chr(0x202E)}hidden"}}\n'
            },
            "stderr": {"stderr": "safe\u2066hidden"},
            "output": {"output": "safe\u200fhidden"},
        }

        with tempfile.TemporaryDirectory() as temp:
            for label, override in unsafe_outputs.items():
                with self.subTest(source=label):
                    output_dir = Path(temp) / label
                    arguments = {
                        "output_dir": output_dir,
                        "raw_trace": '{"type":"result"}\n',
                        "stderr": "",
                        "output": "Safe output.",
                        "metadata": {"case": "UNSAFE-PRESSURE-002"},
                        "capture": {
                            "prompt": "Review this.",
                            "input": "Safe input.",
                            "output": "Safe output.",
                        },
                    }
                    arguments.update(override)

                    with self.assertRaisesRegex(
                        self.harness.HarnessError,
                        "direction control",
                    ):
                        self.harness.save_run(**arguments)

                    self.assertFalse(output_dir.exists())

    def test_client_environment_does_not_forward_token_variables(self) -> None:
        prior = dict(os.environ)
        os.environ["OPENAI_API_KEY"] = "secret"
        os.environ["ANTHROPIC_API_KEY"] = "secret"
        try:
            environment = self.harness.client_environment(Path("/tmp/client-home"))
        finally:
            os.environ.clear()
            os.environ.update(prior)

        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("ANTHROPIC_API_KEY", environment)
        self.assertEqual("/tmp/client-home", environment["HOME"])

    def test_claude_environment_keeps_keychain_home_without_forwarding_tokens(self) -> None:
        prior = dict(os.environ)
        os.environ["HOME"] = "/Users/tester"
        os.environ["CLAUDE_CONFIG_DIR"] = "/tmp/untrusted-config"
        os.environ["ANTHROPIC_API_KEY"] = "secret"
        try:
            environment = self.harness.claude_environment()
        finally:
            os.environ.clear()
            os.environ.update(prior)

        self.assertEqual("/Users/tester", environment["HOME"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", environment)
        self.assertNotIn("ANTHROPIC_API_KEY", environment)


if __name__ == "__main__":
    unittest.main()
