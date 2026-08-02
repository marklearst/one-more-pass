#!/usr/bin/env python3
"""Run one behavior fixture without changing normal client configuration."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterator, NamedTuple, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "one-more-pass"
FIXTURE_PATHS = {
    "writing": REPO_ROOT / "tests" / "behavior" / "fixtures" / "writing-cases.json",
    "code": REPO_ROOT / "tests" / "behavior" / "fixtures" / "code-cases.json",
}
DEFAULT_MODELS = {"codex": "gpt-5.6-sol", "claude": "opus"}
SAFE_ENV_KEYS = {
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "SHELL",
    "TERM",
    "TMPDIR",
    "USER",
}
SECRET_PATTERNS = (
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,255}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,255}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(
        r"\bsk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{20,255}|[A-Za-z0-9]{20,255})\b"
    ),
    re.compile(r"\bsk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,255}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer[ \t]+[A-Za-z0-9._~+/=-]{20,255}"),
)
DIRECTION_CONTROL_CODEPOINTS = frozenset(
    {
        0x061C,
        0x200E,
        0x200F,
        0x2028,
        0x2029,
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
    }
)


class RouteProof(NamedTuple):
    observed: bool
    method: str
    evidence: str


class HarnessError(RuntimeError):
    pass


def render_request(case: dict[str, Any]) -> str:
    return f"{case['prompt']}\n\nInput:\n{case['input']}"


def build_codex_command(request: str, model: str, workdir: Path) -> list[str]:
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--strict-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="ultra"',
        "-c",
        'shell_environment_policy.inherit="none"',
        "--cd",
        str(workdir),
        "--model",
        model,
        "--json",
        request,
    ]


def build_claude_command(
    request: str, model: str, plugin_root: Optional[Path]
) -> list[str]:
    command = [
        "claude",
        "--print",
        "--model",
        model,
        "--effort",
        "max",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--no-chrome",
        "--setting-sources",
        "",
        "--permission-mode",
        "dontAsk",
        "--tools=Skill,Read",
    ]
    if plugin_root is not None:
        command.extend(
            ["--add-dir", str(plugin_root), "--plugin-dir", str(plugin_root)]
        )
    command.append(request)
    return command


def client_environment(home: Path) -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if key in SAFE_ENV_KEYS
    }
    environment["HOME"] = str(home)
    environment["NO_COLOR"] = "1"
    return environment


def claude_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if key in SAFE_ENV_KEYS
    }
    environment["HOME"] = os.environ.get("HOME", str(Path.home()))
    environment["NO_COLOR"] = "1"
    return environment


@contextmanager
def temporary_codex_home(auth_source: Path) -> Iterator[Path]:
    if not auth_source.is_file():
        raise HarnessError(
            "Codex auth.json was not found. Sign in with the normal Codex setup first."
        )
    with tempfile.TemporaryDirectory(prefix="one-more-pass-codex-") as temp:
        codex_home = Path(temp)
        copied_auth = codex_home / "auth.json"
        shutil.copyfile(auth_source, copied_auth)
        copied_auth.chmod(stat.S_IRUSR | stat.S_IWUSR)
        yield codex_home


@contextmanager
def temporary_client_home(prefix: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=prefix) as temp:
        yield Path(temp)


def parse_json_lines(raw: str, client: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{client} emitted non-JSON output on line {line_number}"
            ) from error
        if not isinstance(event, dict):
            raise ValueError(f"{client} emitted a non-object event on line {line_number}")
        events.append(event)
    if not events:
        raise ValueError(f"{client} emitted no JSON events")
    return events


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    return ""


def codex_route_proof(events: Sequence[dict[str, Any]], skill: str) -> RouteProof:
    expected = f"/skills/{skill}/skill.md"
    windows_expected = f"\\skills\\{skill}\\skill.md"
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        command = _flatten_text(item.get("command", ""))
        normalized = command.lower()
        if expected in normalized or windows_expected in normalized:
            return RouteProof(True, "command_execution", command[:1000])
    return RouteProof(False, "none", "")


def claude_route_proof(events: Sequence[dict[str, Any]], skill: str) -> RouteProof:
    expected = f"one-more-pass:{skill}"
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use" or block.get("name") != "Skill":
                continue
            tool_input = block.get("input")
            if not isinstance(tool_input, dict):
                continue
            invoked = str(tool_input.get("skill", "")).lstrip("$/")
            if invoked == expected:
                return RouteProof(True, "skill_tool", invoked)
    return RouteProof(False, "none", "")


def extract_codex_output(events: Sequence[dict[str, Any]]) -> str:
    messages: list[str] = []
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str) and text:
            messages.append(text)
    if not messages:
        raise HarnessError("Codex trace contains no final agent message")
    return messages[-1]


def extract_claude_output(events: Sequence[dict[str, Any]]) -> str:
    results = [
        event.get("result")
        for event in events
        if event.get("type") == "result" and isinstance(event.get("result"), str)
    ]
    if not results:
        raise HarnessError("Claude trace contains no result event")
    return results[-1]


def make_capture_template(
    *,
    client: str,
    client_version: str,
    model: str,
    prompt: str,
    input_text: str,
    output: str,
    arm: str,
    proof: RouteProof,
) -> dict[str, Any]:
    trigger_observed: Optional[bool] = None if arm == "baseline" else proof.observed
    route_note = (
        "Baseline run. The plugin was unavailable."
        if arm == "baseline"
        else f"Route proof: {proof.method}. Manual field review is still required."
    )
    return {
        "client": client,
        "client_version": client_version,
        "model": model,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prompt": prompt,
        "input": input_text,
        "output": output,
        "review": {
            "trigger_observed": trigger_observed,
            "required_facts_preserved": [],
            "relationships_preserved": [],
            "protected_spans_preserved": [],
            "forbidden_changes_absent": [],
            "expected_traits_observed": [],
            "notes": route_note,
        },
    }


def route_matches(*, route: str, arm: str, observed: bool) -> bool:
    if arm == "baseline":
        return True
    return observed is (route == "trigger")


def assert_no_secret_like_text(text: str, *, source: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise HarnessError(
                f"refusing to persist secret-like text found in {source}"
            )


def assert_no_direction_controls(text: str, *, source: str) -> None:
    if any(ord(character) in DIRECTION_CONTROL_CODEPOINTS for character in text):
        raise HarnessError(
            f"refusing to persist Unicode direction control found in {source}"
        )


def assert_safe_fixture_text(case: dict[str, Any]) -> None:
    for field in ("prompt", "input"):
        value = case.get(field)
        if not isinstance(value, str):
            raise HarnessError(f"behavior fixture {field} must be text")
        assert_no_secret_like_text(value, source=f"fixture {field}")
        assert_no_direction_controls(value, source=f"fixture {field}")


def redact_secret_like_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def load_case(case_id: str) -> tuple[str, dict[str, Any]]:
    for skill, path in FIXTURE_PATHS.items():
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            if case["id"] == case_id:
                return skill, case
    raise HarnessError(f"unknown behavior case: {case_id}")


def run_checked(
    command: Sequence[str],
    *,
    environment: dict[str, str],
    cwd: Path,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        safe_error = redact_secret_like_text(result.stderr.strip()) or "no error text"
        raise HarnessError(
            f"command failed with exit {result.returncode}: {safe_error[:1000]}"
        )
    return result


def client_version(client: str, environment: dict[str, str], cwd: Path) -> str:
    result = run_checked([client, "--version"], environment=environment, cwd=cwd)
    return result.stdout.strip()


def install_codex_plugin(environment: dict[str, str], cwd: Path) -> None:
    run_checked(
        ["codex", "plugin", "marketplace", "add", str(REPO_ROOT), "--json"],
        environment=environment,
        cwd=cwd,
    )
    run_checked(
        [
            "codex",
            "plugin",
            "add",
            "one-more-pass@one-more-pass-private",
            "--json",
        ],
        environment=environment,
        cwd=cwd,
    )


def _redacted_command(command: Sequence[str], request: str) -> list[str]:
    return ["<fixture request>" if item == request else item for item in command]


def save_run(
    *,
    output_dir: Path,
    raw_trace: str,
    stderr: str,
    output: str,
    metadata: dict[str, Any],
    capture: dict[str, Any],
) -> None:
    assert_safe_fixture_text(capture)
    assert_no_secret_like_text(raw_trace, source="trace")
    assert_no_secret_like_text(stderr, source="stderr")
    assert_no_secret_like_text(output, source="client output")
    assert_no_direction_controls(raw_trace, source="trace")
    assert_no_direction_controls(stderr, source="stderr")
    assert_no_direction_controls(output, source="client output")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "trace.jsonl").write_text(raw_trace, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (output_dir / "output.txt").write_text(output, encoding="utf-8")
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "capture-template.json").write_text(
        json.dumps(capture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run_codex_case(
    *,
    case: dict[str, Any],
    skill: str,
    arm: str,
    model: str,
    output_dir: Path,
    auth_source: Path,
) -> None:
    assert_safe_fixture_text(case)
    request = render_request(case)
    with temporary_codex_home(auth_source) as codex_home:
        environment = client_environment(codex_home)
        environment["CODEX_HOME"] = str(codex_home)
        with temporary_client_home("one-more-pass-case-") as workspace:
            if arm == "plugin":
                install_codex_plugin(environment, workspace)
            version = client_version("codex", environment, workspace)
            command = build_codex_command(request, model, workspace)
            result = run_checked(
                command, environment=environment, cwd=workspace, timeout=900
            )
            events = parse_json_lines(result.stdout, client="codex")
            proof = codex_route_proof(events, skill)
            output = extract_codex_output(events)
            capture = make_capture_template(
                client="codex",
                client_version=version,
                model=model,
                prompt=case["prompt"],
                input_text=case["input"],
                output=output,
                arm=arm,
                proof=proof,
            )
            metadata = {
                "case": case["id"],
                "client": "codex",
                "arm": arm,
                "route": case["route"],
                "expected_skill": case["expected_skill"],
                "route_proof": proof._asdict(),
                "command": _redacted_command(command, request),
            }
            save_run(
                output_dir=output_dir,
                raw_trace=result.stdout,
                stderr=result.stderr,
                output=output,
                metadata=metadata,
                capture=capture,
            )
            if not route_matches(
                route=case["route"], arm=arm, observed=proof.observed
            ):
                raise HarnessError(
                    f"route mismatch for {case['id']}; failed evidence was saved"
                )


def run_claude_case(
    *,
    case: dict[str, Any],
    skill: str,
    arm: str,
    model: str,
    output_dir: Path,
) -> None:
    assert_safe_fixture_text(case)
    request = render_request(case)
    environment = claude_environment()
    with temporary_client_home("one-more-pass-case-") as workspace:
        version = client_version("claude", environment, workspace)
        plugin_root = PLUGIN_ROOT if arm == "plugin" else None
        command = build_claude_command(request, model, plugin_root)
        result = run_checked(
            command, environment=environment, cwd=workspace, timeout=900
        )
        events = parse_json_lines(result.stdout, client="claude")
        proof = claude_route_proof(events, skill)
        output = extract_claude_output(events)
        capture = make_capture_template(
            client="claude",
            client_version=version,
            model=model,
            prompt=case["prompt"],
            input_text=case["input"],
            output=output,
            arm=arm,
            proof=proof,
        )
        metadata = {
            "case": case["id"],
            "client": "claude",
            "arm": arm,
            "route": case["route"],
            "expected_skill": case["expected_skill"],
            "route_proof": proof._asdict(),
            "command": _redacted_command(command, request),
        }
        save_run(
            output_dir=output_dir,
            raw_trace=result.stdout,
            stderr=result.stderr,
            output=output,
            metadata=metadata,
            capture=capture,
        )
        if not route_matches(route=case["route"], arm=arm, observed=proof.observed):
            raise HarnessError(
                f"route mismatch for {case['id']}; failed evidence was saved"
            )


def check_help(command: Sequence[str], required: Sequence[str]) -> dict[str, Any]:
    result = subprocess.run(
        list(command), text=True, capture_output=True, check=False, timeout=30
    )
    text_output = f"{result.stdout}\n{result.stderr}"
    missing = [flag for flag in required if flag not in text_output]
    return {
        "command": list(command),
        "exit": result.returncode,
        "missing": missing,
        "ok": result.returncode == 0 and not missing,
    }


def claude_profile_conflicts(raw: str) -> list[str]:
    try:
        inventory = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("Claude plugin inventory is not valid JSON") from error
    if not isinstance(inventory, list):
        raise ValueError("Claude plugin inventory must be a list")

    conflicts: list[str] = []
    for entry in inventory:
        if not isinstance(entry, dict):
            continue
        plugin_id = entry.get("id")
        if not isinstance(plugin_id, str):
            continue
        if plugin_id.split("@", maxsplit=1)[0] == "one-more-pass":
            conflicts.append(plugin_id)
    return conflicts


def check_claude_profile() -> dict[str, Any]:
    result = subprocess.run(
        ["claude", "plugin", "list", "--json"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    try:
        conflicts = claude_profile_conflicts(result.stdout)
        inventory_error = ""
    except ValueError as error:
        conflicts = []
        inventory_error = str(error)
    return {
        "command": ["claude", "plugin", "list", "--json"],
        "exit": result.returncode,
        "conflicts": conflicts,
        "error": inventory_error,
        "ok": result.returncode == 0 and not conflicts and not inventory_error,
    }


def preflight() -> int:
    codex_shape = build_codex_command(
        "preflight", DEFAULT_MODELS["codex"], Path.cwd()
    )[:-1] + ["--help"]
    claude_shape = build_claude_command(
        "preflight", DEFAULT_MODELS["claude"], PLUGIN_ROOT
    )[:-1] + ["--help"]
    checks = [
        check_help(
            ["codex", "exec", "--help"],
            [
                "--ephemeral",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "--json",
            ],
        ),
        check_help(
            ["codex", "plugin", "marketplace", "add", "--help"],
            ["--json"],
        ),
        check_help(
            ["codex", "plugin", "add", "--help"],
            ["--json"],
        ),
        check_help(
            ["claude", "--help"],
            [
                "--effort",
                "--no-session-persistence",
                "--output-format",
                "--permission-mode",
                "--plugin-dir",
            ],
        ),
        check_help(codex_shape, []),
        check_help(claude_shape, []),
        check_claude_profile(),
    ]
    report = {
        "codex_version": subprocess.run(
            ["codex", "--version"], text=True, capture_output=True, check=False
        ).stdout.strip(),
        "claude_version": subprocess.run(
            ["claude", "--version"], text=True, capture_output=True, check=False
        ).stdout.strip(),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if all(check["ok"] for check in checks) else 1


def dry_run_report(
    *, client: str, case: dict[str, Any], arm: str, model: str
) -> dict[str, Any]:
    request = render_request(case)
    if client == "codex":
        command = build_codex_command(request, model, Path("<temporary-workspace>"))
        setup = (
            [
                "codex",
                "plugin",
                "marketplace",
                "add",
                str(REPO_ROOT),
                "--json",
            ],
            [
                "codex",
                "plugin",
                "add",
                "one-more-pass@one-more-pass-private",
                "--json",
            ],
        ) if arm == "plugin" else ()
    else:
        command = build_claude_command(
            request, model, PLUGIN_ROOT if arm == "plugin" else None
        )
        setup = ()
    return {
        "case": case["id"],
        "client": client,
        "arm": arm,
        "model": model,
        "setup": [list(item) for item in setup],
        "command": _redacted_command(command, request),
        "writes": (
            "temporary Codex home and workspace plus the requested evidence directory"
            if client == "codex"
            else "temporary workspace plus the requested evidence directory"
        ),
        "source_tree": "read-only",
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one One More Pass behavior fixture in an isolated client session."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Check the required local CLI flags only.")

    run_parser = subparsers.add_parser("run", help="Run or preview one fixture arm.")
    run_parser.add_argument("--client", choices=("codex", "claude"), required=True)
    run_parser.add_argument("--case", required=True)
    run_parser.add_argument("--arm", choices=("baseline", "plugin"), required=True)
    run_parser.add_argument("--model")
    run_parser.add_argument("--output-dir", type=Path)
    run_parser.add_argument("--auth-file", type=Path)
    run_parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "preflight":
        return preflight()

    skill, case = load_case(args.case)
    model = args.model or DEFAULT_MODELS[args.client]
    if args.dry_run:
        print(
            json.dumps(
                dry_run_report(
                    client=args.client, case=case, arm=args.arm, model=model
                ),
                indent=2,
            )
        )
        return 0
    if args.output_dir is None:
        raise HarnessError("--output-dir is required unless --dry-run is used")
    if args.output_dir.exists():
        raise HarnessError(f"output directory already exists: {args.output_dir}")

    if args.client == "codex":
        default_auth = Path(
            os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
        ) / "auth.json"
        run_codex_case(
            case=case,
            skill=skill,
            arm=args.arm,
            model=model,
            output_dir=args.output_dir,
            auth_source=args.auth_file or default_auth,
        )
    else:
        run_claude_case(
            case=case,
            skill=skill,
            arm=args.arm,
            model=model,
            output_dir=args.output_dir,
        )
    print(f"Saved an unreviewed capture bundle to {args.output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HarnessError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"behavior harness: {error}", file=sys.stderr)
        raise SystemExit(2)
