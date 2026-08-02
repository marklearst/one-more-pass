#!/usr/bin/env python3
"""Conservative, read-only mechanical scanner for One More Pass: Code."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Sequence


VERSION = "1.0.0"
SCHEMA_NAME = "one-more-pass.code.scan"
SCHEMA_VERSION = "1.0.0"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 8 * 1024 * 1024
MAX_EXPLICIT_INPUTS = 256
MAX_FINDINGS_PER_RULE = 25
MAX_FINDINGS_TOTAL = 200

RUN_STATES = {"PASS", "FAIL", "NOT_RUN", "NEEDS_REVIEW"}
ATTRIBUTIONS = {
    "introduced",
    "worsened",
    "pre-existing",
    "unknown",
    "not-applicable",
}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    state_on_match: str
    action: str


RULES: tuple[Rule, ...] = (
    Rule(
        "OMP-CODE-012",
        "Disabled or focused test",
        "blocker",
        "NEEDS_REVIEW",
        "Confirm whether the test is required; restore skipped or unfinished coverage, de-focus exclusive cases, or review a narrow release exception.",
    ),
    Rule(
        "OMP-CODE-013",
        "Explicit not-implemented placeholder",
        "blocker",
        "NEEDS_REVIEW",
        "Confirm whether the path is reachable or promised; if it is, implement it or remove it from the declared scope.",
    ),
    Rule(
        "OMP-CODE-014",
        "Blanket suppression",
        "blocker",
        "NEEDS_REVIEW",
        "Inspect what the suppression hides; narrow it if it covers unrelated findings.",
    ),
    Rule(
        "OMP-CODE-015",
        "Empty catch",
        "blocker",
        "NEEDS_REVIEW",
        "Confirm whether ignoring the failure is deliberate and safe; otherwise handle, report, or propagate it.",
    ),
    Rule(
        "OMP-CODE-016",
        "Debugger statement",
        "blocker",
        "NEEDS_REVIEW",
        "Confirm whether this statement can ship or run; remove it if it can.",
    ),
    Rule(
        "OMP-CODE-017",
        "High-confidence secret shape",
        "blocker",
        "NEEDS_REVIEW",
        "Treat the value as sensitive while reviewing it; if it is real, remove it, rotate it, and inspect its exposure.",
    ),
    Rule(
        "OMP-CODE-018",
        "TODO-style marker",
        "warning",
        "NEEDS_REVIEW",
        "Confirm the marker is scoped, owned, and safe to ship.",
    ),
    Rule(
        "OMP-CODE-019",
        "Debug-style logging",
        "warning",
        "NEEDS_REVIEW",
        "Confirm the output is intentional, safe, and appropriate for the runtime.",
    ),
    Rule(
        "OMP-CODE-020",
        "Type escape",
        "warning",
        "NEEDS_REVIEW",
        "Replace the escape or document the checked boundary that makes it safe.",
    ),
    Rule(
        "OMP-CODE-021",
        "Narrow suppression",
        "warning",
        "NEEDS_REVIEW",
        "Verify the suppression names a rule, has a reason, and covers the smallest scope.",
    ),
)
RULE_BY_ID = {rule.id: rule for rule in RULES}


@dataclass(frozen=True)
class Check:
    id: str
    run_state: str
    patch_attribution: str
    evidence: str
    action: str
    severity: str = "warning"
    path: str | None = None
    line: int | None = None

    def __post_init__(self) -> None:
        if self.run_state not in RUN_STATES:
            raise ValueError(f"Invalid run_state: {self.run_state}")
        if self.patch_attribution not in ATTRIBUTIONS:
            raise ValueError(f"Invalid patch_attribution: {self.patch_attribution}")
        if not self.id.startswith("OMP-CODE-"):
            raise ValueError(f"Invalid check id: {self.id}")
        if not self.evidence.strip() or not self.action.strip():
            raise ValueError("Checks require evidence and action")

    @classmethod
    def from_dict(cls, value: dict) -> "Check":
        return cls(
            id=value["id"],
            run_state=value["run_state"],
            patch_attribution=value["patch_attribution"],
            evidence=value["evidence"],
            action=value["action"],
            severity=value.get("severity", "warning"),
            path=value.get("path"),
            line=value.get("line"),
        )

    def to_dict(self) -> dict:
        value = asdict(self)
        value["evidence"] = output_safe(value["evidence"])
        value["action"] = output_safe(value["action"])
        if value["path"] is not None:
            value["path"] = output_safe(value["path"])
        return value


@dataclass(frozen=True)
class Source:
    path: str
    text: str
    line_base: int = 1
    patch_attribution: str = "unknown"
    _line_starts: tuple[int, ...] = field(init=False, repr=False)
    _lines: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        starts = [0]
        starts.extend(match.end() for match in re.finditer(r"\n", self.text))
        object.__setattr__(self, "_line_starts", tuple(starts))
        object.__setattr__(self, "_lines", tuple(self.text.splitlines()))

    def line_number(self, offset: int) -> int:
        return self.line_base + bisect_right(self._line_starts, offset) - 1

    def line_evidence(self, number: int) -> str:
        local_number = number - self.line_base + 1
        if local_number < 1 or local_number > len(self._lines):
            return "Signal found at a source location that could not be rendered."
        value = output_safe(
            self._lines[local_number - 1].strip().replace("\t", " ")
        )
        if len(value) > 180:
            if "[REDACTED]" in value:
                value = (
                    f"{value[:80].rstrip()} ... [REDACTED] ... "
                    f"{value[-70:].lstrip()}"
                )
            else:
                value = value[:177] + "..."
        return value or "Signal found on an otherwise empty source line."


class InvalidInvocation(ValueError):
    """The requested scan cannot be interpreted safely."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvalidInvocation(message)


def _blank_channels(text: str) -> tuple[list[str], list[str], list[str]]:
    base = [char if char in "\r\n" else " " for char in text]
    return base.copy(), base.copy(), base.copy()


def _starts_javascript_regex(code: list[str], index: int) -> bool:
    previous = index - 1
    while previous >= 0 and code[previous].isspace():
        previous -= 1
    if previous < 0:
        return True
    if code[previous] in "([{:;,=!?&|+-*%^~<>":
        return True
    if code[previous].isalnum() or code[previous] in "_$":
        start = previous
        while start >= 0 and (code[start].isalnum() or code[start] in "_$"):
            start -= 1
        return "".join(code[start + 1 : previous + 1]) in {
            "await",
            "case",
            "delete",
            "do",
            "else",
            "in",
            "instanceof",
            "new",
            "of",
            "return",
            "throw",
            "typeof",
            "void",
            "yield",
        }
    return False


JAVASCRIPT_SUFFIXES = {".cjs", ".cts", ".js", ".jsx", ".mjs", ".mts", ".ts", ".tsx"}


def _is_javascript_private_hash(text: str, index: int, path: str) -> bool:
    if index + 1 >= len(text) or not re.match(r"[A-Za-z_$]", text[index + 1]):
        return False
    if Path(path).suffix.lower() in JAVASCRIPT_SUFFIXES:
        return True

    previous = index - 1
    while previous >= 0 and text[previous] in " \t":
        previous -= 1
    return previous >= 0 and text[previous] in ".{;}"


def partition_source(text: str, path: str = "") -> tuple[str, str, str]:
    """Return code-only, comment-only, and commentless views with stable offsets."""

    code, comments, commentless = _blank_channels(text)
    state = "normal"
    delimiter = ""
    regex_character_class = False
    index = 0
    length = len(text)

    def copy(target: list[str], start: int, width: int = 1) -> None:
        target[start : start + width] = text[start : start + width]

    while index < length:
        char = text[index]
        pair = text[index : index + 2]
        triple = text[index : index + 3]

        if state == "normal":
            if pair == "//":
                state = "line-comment"
                copy(comments, index, 2)
                index += 2
                continue
            if pair == "/*":
                state = "block-comment"
                copy(comments, index, 2)
                index += 2
                continue
            if char == "#" and not _is_javascript_private_hash(text, index, path):
                state = "line-comment"
                copy(comments, index)
                index += 1
                continue
            if triple in {"'''", '\"\"\"'}:
                state = "string"
                delimiter = triple
                copy(commentless, index, 3)
                index += 3
                continue
            if char in {"'", '"', "`"}:
                state = "string"
                delimiter = char
                copy(commentless, index)
                index += 1
                continue
            if char == "/" and _starts_javascript_regex(code, index):
                state = "regex"
                regex_character_class = False
                copy(commentless, index)
                index += 1
                continue
            copy(code, index)
            copy(commentless, index)
            index += 1
            continue

        if state == "line-comment":
            if char in "\r\n":
                state = "normal"
            else:
                copy(comments, index)
            index += 1
            continue

        if state == "block-comment":
            if pair == "*/":
                copy(comments, index, 2)
                index += 2
                state = "normal"
            else:
                if char not in "\r\n":
                    copy(comments, index)
                index += 1
            continue

        if state == "string":
            if char == "\\" and index + 1 < length:
                copy(commentless, index, 2)
                index += 2
                continue
            if text.startswith(delimiter, index):
                copy(commentless, index, len(delimiter))
                index += len(delimiter)
                state = "normal"
                delimiter = ""
                continue
            if char not in "\r\n":
                copy(commentless, index)
            index += 1
            continue

        if state == "regex":
            if char in "\r\n":
                state = "normal"
                index += 1
                continue
            if char == "\\" and index + 1 < length:
                copy(commentless, index, 2)
                index += 2
                continue
            copy(commentless, index)
            if char == "[":
                regex_character_class = True
            elif char == "]":
                regex_character_class = False
            elif char == "/" and not regex_character_class:
                state = "normal"
            index += 1

    return "".join(code), "".join(comments), "".join(commentless)


def make_check(rule_id: str, source: Source, offset: int, evidence: str | None = None) -> Check:
    rule = RULE_BY_ID[rule_id]
    number = source.line_number(offset)
    return Check(
        id=rule.id,
        run_state=rule.state_on_match,
        patch_attribution=source.patch_attribution,
        evidence=evidence or source.line_evidence(number),
        action=rule.action,
        severity=rule.severity,
        path=source.path,
        line=number,
    )


def regex_checks(
    rule_id: str,
    source: Source,
    view: str,
    patterns: Iterable[re.Pattern[str]],
    *,
    guard_view: str | None = None,
) -> tuple[list[Check], int]:
    checks: list[Check] = []
    omitted = 0
    seen_lines: set[int] = set()
    for pattern in patterns:
        for match in pattern.finditer(view):
            if guard_view is not None and guard_view[match.start()].isspace():
                continue
            number = source.line_number(match.start())
            if number in seen_lines:
                continue
            seen_lines.add(number)
            if len(checks) < MAX_FINDINGS_PER_RULE:
                checks.append(make_check(rule_id, source, match.start()))
            else:
                omitted += 1
    return checks, omitted


DISABLED_TEST_PATTERNS = (
    re.compile(r"\b(?:it|test|describe|suite)\s*\.\s*(?:skip|todo|only)\s*\("),
    re.compile(r"\b(?:xit|xtest|xdescribe)\s*\("),
    re.compile(r"@\s*pytest\.mark\.(?:skip|skipif)\b"),
    re.compile(r"@\s*unittest\s*\.\s*(?:skip|skipIf|skipUnless)\b"),
)
DISABLED_TEST_TEXT_PATTERNS = (
    re.compile(
        r"\b(?:it|test|describe|suite)\s*\[\s*['\"](?:skip|todo|only)['\"]\s*\]\s*\("
    ),
)
NOT_IMPLEMENTED_CODE_PATTERNS = (
    re.compile(r"\braise\s+NotImplementedError\b"),
    re.compile(r"\b(?:todo|unimplemented)!\s*\(", re.IGNORECASE),
)
NOT_IMPLEMENTED_TEXT_PATTERNS = (
    re.compile(
        r"\bthrow\s+new\s+\w*Error\s*\([^;\n]*(?:not\s+(?:yet\s+)?implemented|unimplemented)[^;\n]*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bPromise\s*\.\s*reject\s*\(\s*new\s+\w*Error\s*\([^;\n]*(?:not\s+(?:yet\s+)?implemented|unimplemented)[^;\n]*\)\s*\)",
        re.IGNORECASE,
    ),
)
EMPTY_CATCH_PATTERNS = (
    re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}", re.DOTALL),
    re.compile(r"\bexcept(?:[^:\n]*)?:\s*(?:pass|\.\.\.)\s*(?:\n|$)"),
)
DEBUGGER_PATTERNS = (
    re.compile(r"\bdebugger\s*;"),
    re.compile(r"\b(?:breakpoint|pdb\.set_trace|debugpy\.breakpoint)\s*\("),
)
LOGGING_PATTERNS = (
    re.compile(r"\bconsole\s*(?:\?\.|\.)\s*(?:log|debug|info|warn|error)\s*\("),
    re.compile(r"\b(?:logger|log)\s*(?:\?\.|\.)\s*(?:debug|trace)\s*\("),
)
LOGGING_TEXT_PATTERNS = (
    re.compile(
        r"\bconsole\s*\[\s*['\"](?:log|debug|info|warn|error)['\"]\s*\]\s*\("
    ),
    re.compile(
        r"\b(?:logger|log)\s*\[\s*['\"](?:debug|trace)['\"]\s*\]\s*\("
    ),
)
TYPE_ESCAPE_PATTERNS = (
    re.compile(r"\bas\s+any\b"),
    re.compile(r"\bas\s+unknown\s+as\b"),
    re.compile(r":\s*any\b"),
)
TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)

DETECTED_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"\bgh[opusr]_[A-Za-z0-9]{36,255}\b")),
    (
        "GitHub fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    ),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36,255}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "OpenAI API key",
        re.compile(
            r"\bsk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{20,255}|[A-Za-z0-9]{20,255})\b"
        ),
    ),
    (
        "Anthropic API key",
        re.compile(r"\bsk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,255}\b"),
    ),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
)
OUTPUT_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    *(pattern for _label, pattern in DETECTED_SECRET_PATTERNS),
    re.compile(r"(?i)\bbearer[ \t]+[A-Za-z0-9._~+/=-]{20,255}"),
)
KNOWN_SECRET_EXAMPLES = {"AKIAIOSFODNN7EXAMPLE"}
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


def redact_secret_shapes(value: str) -> str:
    for pattern in OUTPUT_SECRET_PATTERNS:
        value = pattern.sub(
            lambda match: (
                match.group(0)
                if match.group(0) in KNOWN_SECRET_EXAMPLES
                else "[REDACTED]"
            ),
            value,
        )
    return value


def escape_direction_controls(value: str) -> str:
    return "".join(
        f"\\u{ord(character):04x}"
        if ord(character) in DIRECTION_CONTROL_CODEPOINTS
        else character
        for character in value
    )


def output_safe(value: str) -> str:
    return escape_direction_controls(redact_secret_shapes(value))


def has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor) if path.is_absolute() else Path.cwd()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        current = current / part
        if current.is_symlink():
            return True
    return False


def terminal_safe(value: str) -> str:
    escaped: list[str] = []
    named = {"\n": r"\n", "\r": r"\r", "\t": r"\t"}
    for character in escape_direction_controls(value):
        codepoint = ord(character)
        if character in named:
            escaped.append(named[character])
        elif codepoint < 0x20 or 0x7F <= codepoint <= 0x9F:
            escaped.append(f"\\x{codepoint:02x}")
        else:
            escaped.append(character)
    return "".join(escaped)


def safe_diagnostic(value: object) -> str:
    return terminal_safe(redact_secret_shapes(str(value)))


def suppression_checks(source: Source, comments: str) -> tuple[list[Check], dict[str, int]]:
    checks: list[Check] = []
    omitted = {"OMP-CODE-014": 0, "OMP-CODE-021": 0}
    counts = {"OMP-CODE-014": 0, "OMP-CODE-021": 0}
    offset = 0
    for comment_line in comments.splitlines(keepends=True):
        lowered = comment_line.lower()
        blanket = False
        narrow = False

        eslint = re.search(r"eslint-disable(?:-next-line|-line)?(?P<rest>.*)", lowered)
        if eslint:
            rules = eslint.group("rest").split("--", 1)[0]
            rules = rules.replace("*/", "").strip(" :")
            blanket = not bool(rules)
            narrow = bool(rules)

        noqa = re.search(r"\bnoqa\b(?P<rest>[^\r\n]*)", lowered)
        if noqa:
            blanket = blanket or not noqa.group("rest").lstrip().startswith(":")
            narrow = narrow or noqa.group("rest").lstrip().startswith(":")

        type_ignore = re.search(r"\btype\s*:\s*ignore(?P<rest>[^\r\n]*)", lowered)
        if type_ignore:
            has_codes = bool(re.search(r"\[[^]]+\]", type_ignore.group("rest")))
            blanket = blanket or not has_codes
            narrow = narrow or has_codes

        if "@ts-nocheck" in lowered:
            blanket = True
        if "@ts-ignore" in lowered:
            narrow = True
        if re.search(r"(?:pylint|rubocop)\s*:\s*disable\s*=?(?:\s*all)?\s*(?:\*/)?$", lowered):
            blanket = True
        elif re.search(r"(?:pylint|rubocop)\s*:\s*disable\b", lowered):
            narrow = True
        if "pragma: no cover" in lowered:
            narrow = True

        if blanket:
            rule_id = "OMP-CODE-014"
            if counts[rule_id] < MAX_FINDINGS_PER_RULE:
                checks.append(make_check(rule_id, source, offset))
            else:
                omitted[rule_id] += 1
            counts[rule_id] += 1
        elif narrow:
            rule_id = "OMP-CODE-021"
            if counts[rule_id] < MAX_FINDINGS_PER_RULE:
                checks.append(make_check(rule_id, source, offset))
            else:
                omitted[rule_id] += 1
            counts[rule_id] += 1
        offset += len(comment_line)
    return checks, {rule_id: count for rule_id, count in omitted.items() if count}


def secret_checks(source: Source) -> tuple[list[Check], int]:
    checks: list[Check] = []
    omitted = 0
    seen: set[tuple[str, int]] = set()
    for label, pattern in DETECTED_SECRET_PATTERNS:
        for match in pattern.finditer(source.text):
            if match.group(0) in KNOWN_SECRET_EXAMPLES:
                continue
            number = source.line_number(match.start())
            key = (label, number)
            if key in seen:
                continue
            seen.add(key)
            if len(checks) < MAX_FINDINGS_PER_RULE:
                checks.append(
                    make_check(
                        "OMP-CODE-017",
                        source,
                        match.start(),
                        evidence=f"High-confidence {label} shape detected: [REDACTED]",
                    )
                )
            else:
                omitted += 1
    return checks, omitted


def scan_source(source: Source) -> tuple[list[Check], dict[str, int]]:
    code, comments, commentless = partition_source(source.text, source.path)
    checks: list[Check] = []
    omitted: dict[str, int] = {}

    def add(rule_id: str, batch: tuple[list[Check], int]) -> None:
        found, skipped = batch
        checks.extend(found)
        if skipped:
            omitted[rule_id] = omitted.get(rule_id, 0) + skipped

    add("OMP-CODE-012", regex_checks("OMP-CODE-012", source, code, DISABLED_TEST_PATTERNS))
    add(
        "OMP-CODE-012",
        regex_checks(
            "OMP-CODE-012",
            source,
            commentless,
            DISABLED_TEST_TEXT_PATTERNS,
            guard_view=code,
        ),
    )
    add(
        "OMP-CODE-013",
        regex_checks("OMP-CODE-013", source, code, NOT_IMPLEMENTED_CODE_PATTERNS),
    )
    add(
        "OMP-CODE-013",
        regex_checks(
            "OMP-CODE-013",
            source,
            commentless,
            NOT_IMPLEMENTED_TEXT_PATTERNS,
            guard_view=code,
        ),
    )
    suppression_found, suppression_omitted = suppression_checks(source, comments)
    checks.extend(suppression_found)
    for rule_id, count in suppression_omitted.items():
        omitted[rule_id] = omitted.get(rule_id, 0) + count
    add("OMP-CODE-015", regex_checks("OMP-CODE-015", source, code, EMPTY_CATCH_PATTERNS))
    add("OMP-CODE-016", regex_checks("OMP-CODE-016", source, code, DEBUGGER_PATTERNS))
    add("OMP-CODE-017", secret_checks(source))
    add("OMP-CODE-018", regex_checks("OMP-CODE-018", source, comments, (TODO_PATTERN,)))
    add("OMP-CODE-019", regex_checks("OMP-CODE-019", source, code, LOGGING_PATTERNS))
    add(
        "OMP-CODE-019",
        regex_checks(
            "OMP-CODE-019",
            source,
            commentless,
            LOGGING_TEXT_PATTERNS,
            guard_view=code,
        ),
    )
    add("OMP-CODE-020", regex_checks("OMP-CODE-020", source, code, TYPE_ESCAPE_PATTERNS))
    return checks, omitted


def not_run_check(path: str, evidence: str, action: str) -> Check:
    return Check(
        id="OMP-CODE-000",
        run_state="NOT_RUN",
        patch_attribution="unknown",
        evidence=evidence,
        action=action,
        severity="blocker",
        path=path,
    )


def decode_source(path: str, data: bytes) -> Source | Check:
    if len(data) > MAX_INPUT_BYTES:
        return not_run_check(
            path,
            f"Input exceeds the {MAX_INPUT_BYTES}-byte limit.",
            "Pass a smaller explicit file or review the large file with an appropriate tool.",
        )
    if b"\x00" in data:
        return not_run_check(
            path,
            "Input contains NUL bytes and appears binary.",
            "Pass a UTF-8 text file; review binary artifacts with an appropriate tool.",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        return not_run_check(
            path,
            f"Input is not valid UTF-8 at byte {error.start}.",
            "Convert or inspect the file with an encoding-aware tool before release.",
        )
    return Source(path=path, text=text)


def read_sources(paths: Sequence[str]) -> tuple[list[Source], list[Check]]:
    if len(paths) > MAX_EXPLICIT_INPUTS:
        raise InvalidInvocation(
            f"pass no more than {MAX_EXPLICIT_INPUTS} explicit inputs per scan"
        )

    sources: list[Source] = []
    problems: list[Check] = []
    stdin_seen = False
    total_bytes_read = 0

    for raw_path in paths:
        remaining = MAX_TOTAL_INPUT_BYTES - total_bytes_read
        allowed = max(remaining, 0)
        if raw_path == "-":
            if stdin_seen:
                raise InvalidInvocation("stdin ('-') may be supplied only once")
            stdin_seen = True
            data = sys.stdin.buffer.read(min(MAX_INPUT_BYTES, allowed) + 1)
            total_bytes_read += len(data)
            if len(data) > allowed:
                decoded = not_run_check(
                    "<stdin>",
                    f"Combined input exceeds the {MAX_TOTAL_INPUT_BYTES}-byte limit.",
                    "Split the review into smaller explicit scans and inspect every result.",
                )
            else:
                decoded = decode_source("<stdin>", data)
        else:
            path = Path(raw_path)
            if has_symlink_component(path):
                decoded = not_run_check(
                    raw_path,
                    "Symlink path component was not followed.",
                    "Pass the intended regular file explicitly after confirming its scope.",
                )
            elif path.is_dir():
                raise InvalidInvocation(
                    f"directories are not scanned recursively; pass explicit files: {raw_path}"
                )
            elif not path.exists():
                decoded = not_run_check(
                    raw_path,
                    "Input file does not exist.",
                    "Correct the path and rerun the required scan.",
                )
            elif not path.is_file():
                decoded = not_run_check(
                    raw_path,
                    "Input is not a regular file.",
                    "Pass a regular UTF-8 text file explicitly.",
                )
            else:
                try:
                    with path.open("rb") as handle:
                        data = handle.read(min(MAX_INPUT_BYTES, allowed) + 1)
                except OSError as error:
                    decoded = not_run_check(
                        raw_path,
                        f"Input could not be read: {error.strerror or error.__class__.__name__}.",
                        "Restore read access and rerun the required scan.",
                    )
                else:
                    total_bytes_read += len(data)
                    if len(data) > allowed:
                        decoded = not_run_check(
                            raw_path,
                            f"Combined input exceeds the {MAX_TOTAL_INPUT_BYTES}-byte limit.",
                            "Split the review into smaller explicit scans and inspect every result.",
                        )
                    else:
                        decoded = decode_source(raw_path, data)

        if isinstance(decoded, Source):
            sources.append(decoded)
        else:
            problems.append(decoded)

    return sources, problems


HUNK_HEADER = re.compile(
    r"^@@\s+-\d+(?:,\d+)?\s+\+(?P<line>\d+)(?:,(?P<count>\d+))?\s+@@"
)
BINARY_DIFF_MARKER = re.compile(
    r"(?m)^(?:GIT binary patch|Binary files .+ differ)\r?$"
)


def looks_like_unified_diff(text: str) -> bool:
    return bool(
        re.search(r"(?m)^diff --git ", text)
        and re.search(r"(?m)^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@", text)
    )


def _diff_path(header: str) -> str | None:
    value = header[4:].rstrip("\r\n").split("\t", 1)[0]
    if value == "/dev/null":
        return None
    if value.startswith('"') and value.endswith('"'):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = None
        if isinstance(parsed_value, str):
            value = parsed_value
    if value.startswith("b/"):
        value = value[2:]
    return value


def parse_unified_diff(source: Source) -> list[Source]:
    """Extract added-line blocks from a Git unified diff."""

    if not source.text.strip():
        return []
    if not re.search(r"(?m)^diff --git ", source.text):
        raise InvalidInvocation(
            f"--diff input is not a supported Git unified diff: {source.path}"
        )
    blocks: list[Source] = []
    current_path: str | None = None
    saw_new_file_header = False
    in_hunk = False
    new_line = 0
    block_start = 0
    block_lines: list[str] = []

    def flush() -> None:
        nonlocal block_start, block_lines
        if current_path is not None and block_lines:
            blocks.append(
                Source(
                    path=current_path,
                    text="".join(block_lines),
                    line_base=block_start,
                    patch_attribution="introduced",
                )
            )
        block_start = 0
        block_lines = []

    for raw_line in source.text.splitlines(keepends=True):
        if raw_line.startswith("diff --git "):
            flush()
            current_path = None
            saw_new_file_header = False
            in_hunk = False
            continue
        if raw_line.startswith("+++ ") and not in_hunk:
            flush()
            current_path = _diff_path(raw_line)
            saw_new_file_header = True
            in_hunk = False
            continue
        if raw_line.startswith("@@"):
            flush()
            if not saw_new_file_header:
                raise InvalidInvocation(
                    f"unified diff hunk has no preceding +++ file header in {source.path}"
                )
            match = HUNK_HEADER.match(raw_line)
            if match is None:
                raise InvalidInvocation(
                    f"unsupported unified diff hunk header in {source.path}"
                )
            new_line = int(match.group("line"))
            in_hunk = True
            continue
        if not in_hunk:
            if raw_line.startswith("+"):
                raise InvalidInvocation(
                    f"unified diff adds text outside a hunk in {source.path}"
                )
            continue
        if raw_line.startswith("+"):
            if current_path is None:
                raise InvalidInvocation(
                    f"unified diff adds text without a writable +++ file path in {source.path}"
                )
            if not block_lines:
                block_start = new_line
            content = raw_line[1:]
            if not content.endswith(("\n", "\r")):
                content += "\n"
            block_lines.append(content)
            new_line += 1
            continue
        if raw_line.startswith("-"):
            flush()
            continue
        if raw_line.startswith(" "):
            flush()
            new_line += 1
            continue
        if raw_line.startswith("\\ No newline at end of file"):
            continue
        flush()
        in_hunk = False

    flush()
    return blocks


def pass_check(rule: Rule) -> Check:
    return Check(
        id=rule.id,
        run_state="PASS",
        patch_attribution="not-applicable",
        evidence=f"The mechanical {rule.title.lower()} check found no matching signal in the selected text.",
        action="Continue the manual behavior review; a mechanical PASS does not prove safety.",
        severity=rule.severity,
    )


def release_decision(checks: Sequence[Check]) -> dict[str, str]:
    not_run = [check for check in checks if check.run_state == "NOT_RUN"]
    blockers = [
        check
        for check in checks
        if check.run_state == "FAIL" and check.severity == "blocker"
    ]
    review = [check for check in checks if check.run_state == "NEEDS_REVIEW"]

    if not_run:
        return {
            "status": "INCOMPLETE",
            "evidence": f"{len(not_run)} required check(s) did not run; no complete release decision is available.",
            "action": "Run every required check. Do not relabel NOT_RUN as a blocking finding or a pass.",
        }
    if blockers:
        pre_existing = sum(
            check.patch_attribution == "pre-existing" for check in blockers
        )
        attribution_note = (
            f" {pre_existing} blocker(s) are explicitly pre-existing and are not patch faults."
            if pre_existing
            else " Patch attribution remains separate from the failing gate."
        )
        return {
            "status": "BLOCK",
            "evidence": f"{len(blockers)} blocking check(s) failed.{attribution_note}",
            "action": "Resolve or explicitly waive each failed release gate before release.",
        }
    required_ids = {f"OMP-CODE-{index:03d}" for index in range(1, 12)}
    completed_ids = {check.id for check in checks if check.id in required_ids}
    missing_ids = sorted(required_ids - completed_ids)
    if missing_ids:
        return {
            "status": "INCOMPLETE",
            "evidence": f"{len(missing_ids)} required manual review check(s) have no record.",
            "action": "Complete OMP-CODE-001 through OMP-CODE-011 before making a release decision.",
        }
    if review:
        return {
            "status": "NEEDS_REVIEW",
            "evidence": f"{len(review)} check(s) need contextual review; no mechanical blocker was found.",
            "action": "Review the evidence and record a decision before release.",
        }
    return {
        "status": "CLEAR",
        "evidence": "Every required review check ran; no release blocker failed and no review decision remains.",
        "action": "Record the review evidence with the release decision.",
    }


def scan_decision(checks: Sequence[Check]) -> dict[str, str]:
    not_run = [check for check in checks if check.run_state == "NOT_RUN"]
    review = [check for check in checks if check.run_state == "NEEDS_REVIEW"]

    if not_run:
        return {
            "status": "INCOMPLETE",
            "evidence": f"{len(not_run)} mechanical check(s) did not run.",
            "action": "Fix the input problem and rerun the scan before reviewing release readiness.",
        }
    if review:
        return {
            "status": "NEEDS_REVIEW",
            "evidence": f"The scanner found {len(review)} signal(s) that need context.",
            "action": "Inspect each signal and record whether it passes or fails the full review.",
        }
    return {
        "status": "NO_MECHANICAL_BLOCKER",
        "evidence": "The scanner found no blocker pattern in the supplied text.",
        "action": "Complete OMP-CODE-001 through OMP-CODE-011 and the repository checks before making a release decision.",
    }


def build_report(
    checks: Sequence[Check],
    input_count: int,
    *,
    readable_input_count: int | None = None,
    text_block_count: int | None = None,
    scan_mode: str = "files",
    findings_reported: int = 0,
    findings_omitted: int = 0,
) -> dict:
    serialized = [check.to_dict() for check in checks]
    counts = {state: 0 for state in ("PASS", "FAIL", "NOT_RUN", "NEEDS_REVIEW")}
    for check in checks:
        counts[check.run_state] += 1
    return {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "tool_version": VERSION,
        "input_count": input_count,
        "readable_input_count": (
            input_count if readable_input_count is None else readable_input_count
        ),
        "text_block_count": input_count if text_block_count is None else text_block_count,
        "scan_mode": scan_mode,
        "checks": serialized,
        "summary": counts,
        "finding_limits": {
            "per_rule": MAX_FINDINGS_PER_RULE,
            "total": MAX_FINDINGS_TOTAL,
        },
        "findings_reported": findings_reported,
        "findings_omitted": findings_omitted,
        "truncated": findings_omitted > 0,
        "scan_decision": scan_decision(checks),
    }


def scan_paths(paths: Sequence[str], *, diff_mode: bool = False) -> dict:
    raw_sources, problems = read_sources(paths)
    if not diff_mode and any(looks_like_unified_diff(source.text) for source in raw_sources):
        raise InvalidInvocation("unified diff input requires the --diff flag")

    if diff_mode:
        for source in raw_sources:
            if BINARY_DIFF_MARKER.search(source.text):
                problems.append(
                    not_run_check(
                        source.path,
                        "Git binary patch content cannot be inspected as source text.",
                        "Review the binary change with a tool that understands its format.",
                    )
                )
        sources = [
            block
            for source in raw_sources
            for block in parse_unified_diff(source)
        ]
        scan_mode = "unified-diff-added-lines"
    else:
        sources = raw_sources
        scan_mode = "files"
    input_count = len(paths)
    readable_input_count = len(raw_sources)
    text_block_count = len(sources)

    by_rule: dict[str, list[Check]] = {rule.id: [] for rule in RULES}
    omitted_by_rule: dict[str, int] = {rule.id: 0 for rule in RULES}
    for source in sources:
        source_findings, source_omitted = scan_source(source)
        for finding in source_findings:
            retained = by_rule[finding.id]
            if len(retained) < MAX_FINDINGS_PER_RULE:
                retained.append(finding)
            else:
                omitted_by_rule[finding.id] += 1
        for rule_id, count in source_omitted.items():
            omitted_by_rule[rule_id] += count

    remaining = MAX_FINDINGS_TOTAL
    for rule in RULES:
        retained = by_rule[rule.id]
        if len(retained) > remaining:
            omitted_by_rule[rule.id] += len(retained) - remaining
            del retained[remaining:]
        remaining -= len(retained)

    findings_reported = sum(len(items) for items in by_rule.values())
    findings_omitted = sum(omitted_by_rule.values())

    checks: list[Check] = []
    if problems:
        checks.extend(problems)
    else:
        checks.append(
            Check(
                id="OMP-CODE-000",
                run_state="PASS",
                patch_attribution="not-applicable",
                evidence=f"All {input_count} explicit input(s) were read as bounded UTF-8 text.",
                action="Continue with the mechanical scan and manual behavior review.",
                severity="blocker",
            )
        )
    if findings_omitted:
        checks.append(
            Check(
                id="OMP-CODE-000",
                run_state="NEEDS_REVIEW",
                patch_attribution="unknown",
                evidence=f"The report omitted {findings_omitted} repeated finding location(s) after reaching its limits.",
                action="Inspect the full input with repository tools; do not treat the listed locations as the complete set.",
                severity="warning",
            )
        )

    for rule in RULES:
        rule_findings = by_rule[rule.id]
        if rule_findings:
            checks.extend(rule_findings)
        elif omitted_by_rule[rule.id]:
            checks.append(
                Check(
                    id=rule.id,
                    run_state="NEEDS_REVIEW",
                    patch_attribution="unknown",
                    evidence=f"All listed locations for this rule were omitted after the report reached its total limit; {omitted_by_rule[rule.id]} match(es) remain.",
                    action="Inspect the full input for this rule before recording a pass or fail.",
                    severity=rule.severity,
                )
            )
        elif sources or (diff_mode and raw_sources and not problems):
            checks.append(pass_check(rule))
        else:
            checks.append(
                Check(
                    id=rule.id,
                    run_state="NOT_RUN",
                    patch_attribution="unknown",
                    evidence="No readable source input was available for this mechanical check.",
                    action="Provide a readable explicit input and rerun the scan.",
                    severity=rule.severity,
                )
            )
    return build_report(
        checks,
        input_count=input_count,
        readable_input_count=readable_input_count,
        text_block_count=text_block_count,
        scan_mode=scan_mode,
        findings_reported=findings_reported,
        findings_omitted=findings_omitted,
    )


def exit_code_for(report: dict) -> int:
    status = report["scan_decision"]["status"]
    if status == "INCOMPLETE":
        return 2
    return 0


def render_text(report: dict) -> str:
    lines = [
        f"one-more-pass:code {report['tool_version']} schema {report['schema']} {report['schema_version']}"
    ]
    for check in report["checks"]:
        location = terminal_safe(check["path"] or "-")
        if check["line"] is not None:
            location = f"{location}:{check['line']}"
        lines.append(
            " ".join(
                (
                    "CHECK",
                    check["id"],
                    check["run_state"],
                    check["patch_attribution"],
                    check["severity"],
                    location,
                )
            )
        )
        lines.append(f"  evidence: {terminal_safe(check['evidence'])}")
        lines.append(f"  action: {terminal_safe(check['action'])}")
    decision = report["scan_decision"]
    lines.append(f"SCAN {decision['status']}")
    lines.append(f"  evidence: {terminal_safe(decision['evidence'])}")
    lines.append(f"  action: {terminal_safe(decision['action'])}")
    return "\n".join(lines) + "\n"


def make_parser() -> Parser:
    parser = Parser(
        description=(
            "Scan explicit UTF-8 text files or '-' for conservative mechanical review signals. "
            "Directories are never traversed."
        )
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="scan only added lines from a Git unified diff",
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--schema-version", action="store_true")
    parser.add_argument("paths", nargs="*")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = make_parser().parse_args(argv)
        if args.version:
            print(f"one-more-pass:code {VERSION}")
            return 0
        if args.schema_version:
            print(f"{SCHEMA_NAME} {SCHEMA_VERSION}")
            return 0
        if not args.paths:
            raise InvalidInvocation("pass at least one explicit file or '-' for stdin")
        report = scan_paths(args.paths, diff_mode=args.diff)
    except InvalidInvocation as error:
        print(
            f"one-more-pass:code: invalid invocation: {safe_diagnostic(error)}",
            file=sys.stderr,
        )
        return 2
    except Exception as error:
        print(
            f"one-more-pass:code: internal error: {safe_diagnostic(error)}",
            file=sys.stderr,
        )
        return 3

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_text(report))
    return exit_code_for(report)


if __name__ == "__main__":
    raise SystemExit(main())
