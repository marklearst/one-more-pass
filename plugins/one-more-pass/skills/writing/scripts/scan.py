#!/usr/bin/env python3
"""Read-only, conservative prose-pattern scanner for One More Pass: Writing."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import List, Pattern, Sequence, Tuple


VERSION = "1.0.0"
SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_INPUTS = 256
MAX_COMBINED_INPUT_BYTES = 8 * 1024 * 1024
MAX_FINDINGS_PER_RULE = 25
MAX_REPORT_FINDINGS = 200

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT = 2
EXIT_INTERNAL = 3

SEVERITY_RANK = {"note": 1, "warning": 2, "error": 3}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    severity: str
    confidence: str
    patterns: Tuple[Pattern[str], ...]
    minimum_distinct: int
    message: str
    window_words: int | None = None
    repeat_qualifies: int | None = None
    report_each: bool = False
    edge_words: int | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: str
    severity: str
    confidence: str
    source: str
    line: int
    column: int
    excerpt: str
    message: str


@dataclass(frozen=True)
class ScanResult:
    findings: Tuple[Finding, ...]
    omitted_by_rule: dict[str, int]


class InputError(Exception):
    """An explicit input could not be scanned safely."""


SECRET_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{36,255}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{36,255}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(
        r"\bsk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{20,255}|[A-Za-z0-9]{20,255})\b"
    ),
    re.compile(r"\bsk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,255}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
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
    for pattern in SECRET_PATTERNS:
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
    escaped: List[str] = []
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


def words(*patterns: str) -> Tuple[Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


RULES: Tuple[Rule, ...] = (
    Rule(
        "SLP-LEX-001",
        "research-signal",
        "note",
        "medium",
        words(
            r"\bdelv(?:e|es|ed|ing)\b",
            r"\bunderscor(?:e|es|ed|ing)\b",
            r"\bshowcas(?:e|es|ed|ing)\b",
            r"\b(?:intricate|intricately|intricacies)\b",
        ),
        2,
        "Multiple focal lexeme families cluster in this text; review for more precise wording.",
        window_words=500,
        repeat_qualifies=2,
    ),
    Rule(
        "SLP-LEX-002",
        "research-signal",
        "note",
        "medium",
        words(
            r"\btapestr(?:y|ies)\b",
            r"\bcamaraderie\b",
            r"\bamidst\b",
            r"\bpalpable\b",
            r"\bsolace\b",
            r"\bunravel(?:s|ed|ing)?\b",
            r"\bvibrant\b",
        ),
        2,
        "Multiple elevated-image words cluster in this text; check whether concrete detail would be clearer.",
        window_words=500,
        repeat_qualifies=2,
    ),
    Rule(
        "SLP-LEX-003",
        "research-signal",
        "note",
        "medium",
        words(
            r"\bcrucial(?:ly)?\b",
            r"\bcomprehensive(?:ly)?\b",
            r"\binsights?\b",
            r"\bnotably\b",
            r"\bparticularly\b",
            r"\badvancements?\b",
            r"\bgroundbreaking\b",
            r"\brealms?\b",
            r"\balign(?:s|ed|ing|ment)?\b",
            r"\bpotential\b",
        ),
        3,
        "Several abstract-booster families cluster in this text; prefer evidence or a concrete consequence.",
        window_words=500,
    ),
    Rule(
        "SLP-PHR-001",
        "research-signal",
        "note",
        "high",
        words(
            r"\bthis (?:essay|article|section) will\b",
            r"\bthis (?:essay|article|section) (?:explores?|examines?)\b",
            r"\bin conclusion\b",
            r"\bthe rest of this (?:essay|article|section)\b",
        ),
        2,
        "Repeated meta-signposting may be removable when the content can start directly.",
        repeat_qualifies=2,
        edge_words=120,
    ),
    Rule(
        "SLP-PHR-002",
        "research-signal",
        "note",
        "high",
        words(
            r"\b(?:rich|vibrant) tapestry\b",
            r"\bvaluable insights?\b",
            r"\bindelible mark\b",
            r"\b(?:pivotal|crucial) role\b",
            r"\bunlock(?:s|ed|ing)? (?:the )?potential\b",
            r"\bsheds? light\b",
        ),
        2,
        "Multiple stock collocations cluster in this text; replace them only when a specific observation is available.",
        window_words=750,
        repeat_qualifies=2,
    ),
    Rule(
        "SLP-SYN-001",
        "research-signal",
        "note",
        "high",
        words(
            r"\bnot just\b[^.!?\n]{0,120}(?:\bbut also\b|[;,]\s*(?:it(?:['’]s| is)|they(?:['’]re| are)|we(?:['’]re| are))\b)",
            r"\b(?:isn['’]t|is not|aren['’]t|are not|wasn['’]t|was not|weren['’]t|were not)\b[^.!?\n]{0,160}[.!?]\s*(?:it(?:['’]s| is)|they(?:['’]re| are)|we(?:['’]re| are))\b",
            r"\bnot because\b[^.!?\n]{0,160}\bbecause\b",
            r"\b(?:this|that|it) (?:is|was) not\b[^.!?\n]{1,120}[.!?]\s+(?:this|that|it) (?:is|was)\b",
            r"(?:^|[.!?]\s+)not because\b[^.!?\n]{1,120}[.!?]\s+because\b",
        ),
        1,
        "A stock negate-and-reframe structure appears here; preserve any meaningful negation when revising.",
    ),
    Rule(
        "SLP-ENG-001",
        "house-style",
        "warning",
        "high",
        words(
            r"\bhere(?:['’]s| is) the thing\b",
            r"\blet(?:(?:\.{1,3}|…)\s*|\s+)that(?:(?:\.{1,3}|…)\s*|\s+)sink(?:(?:\.{1,3}|…)\s*|\s+)in\b",
            r"\bmake no mistake\b",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)think about it(?=[.!?](?:\s|$))",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)read that again(?=[.!?](?:\s|$))",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)read this twice(?=[.!?](?:\s|$))",
            r"(?m)^\s*thoughts\?\s*$",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)stop scrolling(?=[.!?](?:\s|$))",
            r"\b(?:nobody|no one)(?: is|['’]s) talking about this\b",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)hot take(?=\s*[:!,.])",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)(?:hard truth|unpopular opinion)\s*[:!]",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)this is your sign to\b",
            r"\bi learned this the hard way\b",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)the part nobody tells you\s*[:!]",
            (
                r"(?m)(?:^\s*|(?<=[.!?])\s+)(?:we are|we['’]re) entering "
                r"a new era(?=[.!?](?:\s|$))"
            ),
            r"\bi (?:wasn['’]t|was not) going to post this\b",
            r"\bthis (?:won['’]t|will not) be up for long\b",
            r"(?m)^\s*plot twist(?:\s*[:!,.]|\s*$)",
            r"(?m)^\s*full stop[.!]?\s*$",
            r"\bthat(?:['’]s| is) the post\b",
        ),
        1,
        "A canned hook conflicts with the direct house style.",
        report_each=True,
    ),
    Rule(
        "SLP-ENG-002",
        "house-style",
        "warning",
        "high",
        words(
            r"(?m)^\s*agree\s*\?",
            r"(?<=[.!?])\s+agree\s*\?",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)do you agree\s*\?\s*$",
            r"(?m)(?:^\s*|(?<=[.!?])\s+)what is your take\s*\?\s*$",
            r"(?m)^\s*tell me in the comments[.!?]?\s*$",
            (
                r"\bcomment\s+(?:below|beneath)"
                r"(?=(?:\s+this post)?[.!?,:]|$|\s+(?:if|with|and|your|what|which)\b)"
            ),
            (
                r"\bre[- ]?post this"
                r"(?=(?:\s+(?:post|thread|carousel|with your network))?[.!?]|$)"
            ),
            r"\bshare this(?=(?:\s+(?:post|thread|carousel|with your network))?[.!?]|$)",
            r"\bsave this(?=(?:\s+(?:post|thread|for later))?[.!?]|$)",
            r"\bfollow for more\b",
            r"(?m)^\s*share if (?:this|that) resonates[.!?]?\s*$",
            r"(?m)^\s*save for later[.!?]?\s*$",
            r"(?m)^\s*re[- ]?post to help your network[.!?]?\s*$",
            r"(?m)^\s*follow (?:me|us) for more[.!?]?\s*$",
            r"(?m)^\s*agree or disagree\s*\?[.!?]?\s*$",
            r"(?m)^\s*drop\s+your\s+(?:thoughts|take|opinion)\s+below[.!?]?\s*$",
            (
                r"\bbookmark this"
                r"(?=(?:\s+(?:post|thread|carousel|for later))?[.!?]|$)"
            ),
            (
                r"\btag someone (?:who|that)\s+"
                r"(?:needs? (?:this|to (?:see|read|hear) this)|"
                r"(?:should|would|has to) (?:see|read|hear) this)\b"
            ),
            r"\bdrop (?:a )?(?:yes|y|1) in the comments\b",
            r"(?m)^\s*like this if (?:you )?agree[.!?]?\s*$",
            r"(?m)^\s*re[- ]?post if (?:you )?agree[.!?]?\s*$",
            r"(?m)^\s*save it for later[.!?]?\s*$",
            (
                r"(?m)^\s*send this to someone who needs(?:\s+this|\s+to\s+"
                r"(?:see|read|hear)\s+(?:this|it))[.!?]?\s*$"
            ),
            r"(?m)^\s*let me know what you think in the comments[.!?]?\s*$",
            (
                r"(?m)^\s*dm me (?:guide|template|checklist|playbook|prompt|pdf|link|resource) "
                r"and i(?:['’]ll| will) (?:send|share|give) (?:you )?the "
                r"[^\r\n.!?]{1,80}[.!?]?\s*$"
            ),
            r"(?m)^\s*re[- ]?post this(?:\s*[🔁♻️]+)?[.!?]?\s*$",
            r"(?m)^\s*share this if (?:you )?agree[.!?]?\s*$",
            (
                r"(?m)^\s*comment(?:\s+[a-z0-9_-]{2,30}|\s{2,40})\s+and "
                r"i(?:['’]ll| will) (?:send|share|give) (?:you )?(?:the )?"
                r"(?:template|guide|checklist|playbook|prompt|pdf|link|resource)"
                r"[.!?]?\s*$"
            ),
            (
                r"(?m)^\s*reply(?:\s+[a-z0-9_-]{2,30}|\s{2,40})\s+and "
                r"i(?:['’]ll| will) dm you (?:the )?"
                r"(?:template|guide|checklist|playbook|prompt|pdf|link|resource)"
                r"[.!?]?\s*$"
            ),
            (
                r"(?m)^\s*if this helped,?\s+save it and share it with your "
                r"network[.!?]?\s*$"
            ),
            (
                r"(?m)^\s*tag (?:a|an) [a-z][a-z0-9-]{1,30} who needs to "
                r"(?:see|read|hear) this[.!?]?\s*$"
            ),
            (
                r"(?m)^\s*follow (?:me|us) to learn how to\b"
                r"[^\r\n.!?]{1,100}[.!?]?\s*$"
            ),
        ),
        1,
        "An engagement prompt asks for platform activity instead of serving the reader.",
        report_each=True,
    ),
    Rule(
        "SLP-HSE-001",
        "house-style",
        "warning",
        "high",
        (
            re.compile(
                r"(?:—|&mdash;|&#0*8212;|&#x0*2014;)",
                re.IGNORECASE,
            ),
        ),
        1,
        "An em dash conflicts with this installation's house style; preserve it in protected text.",
        report_each=True,
    ),
    Rule(
        "SLP-HSE-002",
        "house-style",
        "warning",
        "high",
        words(
            r"\bcanonical\b",
            r"\bdeterministic(?:ally)?\b",
            r"\bsurfaces?\b",
            r"\bsubstrates?\b",
            r"\bagency\b",
            r"\bslices?\b",
            r"\balign(?:s|ed|ing|ment)?\b",
            r"\bleverag(?:e|es|ed|ing)\b",
            r"\bunlock(?:s|ed|ing)?\b",
            r"\brobust(?:ly|ness)?\b",
            r"\bseamless(?:ly)?\b",
            r"\bempower(?:s|ed|ing|ment)?\b",
            r"\belevat(?:e|es|ed|ing)\b",
            r"\btransformative\b",
            r"\brevolutionary\b",
            r"\bgame[- ]chang(?:e|er|ers|ing)\b",
            r"\bunpack(?:s|ed|ing)?\b",
            r"\blean into\b",
            r"\bdouble down\b",
            r"\bdeep dive\b",
            r"\btake a step back\b",
            r"\bmoving forward\b",
            r"\bcircle back\b",
            r"\bon the same page\b",
        ),
        2,
        "Several local filler families cluster here; replace them with the rule, action, constraint, or result.",
        window_words=250,
    ),
    Rule(
        "SLP-HSE-003",
        "house-style",
        "warning",
        "high",
        words(
            r"\bthe uncomfortable truth\b",
            (
                r"\bit turns out\b(?!\s+(?:the\s+)?(?:lights?|lamps?)\s+"
                r"(?:when|before|after)\b)"
            ),
            r"\blet me be clear\b",
            r"\bthe truth is\b",
            r"\bthe real (?:issue|problem|question|story|lesson) is\b",
            r"\bhere['’]s (?:why|what|this|that)\b",
            r"\bcan we talk about\b",
            (
                r"\bthe bottom line(?:\s*:|\s+is\b(?!\s*(?:"
                r"[$€£¥]\s*\(?-?\d|(?:USD|EUR|GBP|JPY|CAD|AUD)\s+\(?-?\d|"
                r"\(?-?\d[\d,]*(?:\.\d+)?\s+(?:USD|EUR|GBP|JPY|CAD|AUD)\b"
                r")))"
            ),
            r"\bat its core\b",
            r"\bit(?: is|['’]s) worth noting\b",
            r"\bat the end of the day\b",
            r"\bwhen it comes to\b",
            r"\bin a world where\b",
            r"\bthe reality is\b",
            r"\blet['’]s dive in\b",
            r"\blet me break it down\b",
            r"\bi(?: will|['’]ll) say it again\b",
            r"\bi(?: am|['’]m) going to be honest\b",
            r"\bwithout further ado\b",
        ),
        1,
        "An empty frame delays the concrete claim.",
        report_each=True,
    ),
    Rule(
        "SLP-SYN-004",
        "research-signal",
        "note",
        "medium",
        words(
            r"(?m)(?:^|[.!?]\s+)[A-Z][\w'-]{1,30}\.\s+And\s+[\w'-]{1,30}\.\s+And\s+[\w'-]{1,30}\.",
            r"(?m)(?:^|[.!?]\s+)No\s+[^.!?\n]{1,60}[.!?]\s+No\s+[^.!?\n]{1,60}[.!?]\s+Just\s+[^.!?\n]{1,60}[.!?]",
        ),
        1,
        "A clipped three-beat sequence may be using rhythm in place of explanation.",
    ),
    Rule(
        "SLP-SYN-005",
        "research-signal",
        "note",
        "medium",
        words(
            r"(?m)(?:^|[.!?]\s+)(?:What|Why|How|Who|When|Where)\b[^?\n]{1,90}\?\s+(?:The|It|This|That|We|They|I)\b",
            r"(?m)(?:^|[.!?]\s+)The result\?\s+[A-Z]",
            r"(?m)(?:^|[.!?]\s+)Why\?\s+Because\b",
        ),
        1,
        "An immediate question-and-answer turn may be a presentation device rather than a real question.",
    ),
)


def _mask_range(chars: List[str], start: int, end: int) -> None:
    for index in range(start, end):
        if chars[index] not in "\r\n":
            chars[index] = " "


def _mask_matches(chars: List[str], pattern: Pattern[str]) -> None:
    current = "".join(chars)
    for match in pattern.finditer(current):
        _mask_range(chars, match.start(), match.end())


def _mask_group_matches(chars: List[str], pattern: Pattern[str], group: str) -> None:
    current = "".join(chars)
    for match in pattern.finditer(current):
        _mask_range(chars, match.start(group), match.end(group))


def _mask_markdown_emphasis_markers(chars: List[str]) -> None:
    current = "".join(chars)
    pattern = re.compile(r"(?P<em>\*|_)(?=\S)[^*_\r\n]{1,160}(?P=em)")
    for match in pattern.finditer(current):
        _mask_range(chars, match.start(), match.start() + 1)
        _mask_range(chars, match.end() - 1, match.end())


def _mask_contextual_markdown_titles(chars: List[str]) -> None:
    """Mask emphasized titles only when nearby words identify them as sources."""

    _mask_group_matches(
        chars,
        re.compile(
            r"\b(?:read|consult|cite)\s+"
            r"(?P<title>(?P<em>\*|_)(?=\S)[^*_\r\n]{1,160}(?P=em))",
            re.IGNORECASE,
        ),
        "title",
    )
    _mask_group_matches(
        chars,
        re.compile(
            r"\b(?:read|consult|cite)\s+"
            r"\[(?P<title>[^\]\r\n]{1,160})\]\([^)\r\n]+\)",
            re.IGNORECASE,
        ),
        "title",
    )


def mask_protected_text(text: str, *, protect_frontmatter: bool = True) -> str:
    """Mask common quoted and code-like regions without moving offsets."""

    chars = list(text)
    frontmatter = re.match(
        r"\A(?:\ufeff)?(?P<delimiter>---|\+\+\+)[ \t]*\r?\n",
        text,
    )
    if frontmatter and protect_frontmatter:
        delimiter = re.escape(frontmatter.group("delimiter"))
        closing = re.search(
            rf"(?m)^{delimiter}[ \t]*\r?$",
            text[frontmatter.end() :],
        )
        if closing:
            end = frontmatter.end() + closing.end()
            _mask_range(chars, 0, end)

    offset = 0
    fence_character = ""
    fence_length = 0

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        marker = re.match(r"(`{3,}|~{3,})", stripped)

        if fence_character:
            _mask_range(chars, offset, offset + len(line))
            if marker and marker.group(1)[0] == fence_character and len(marker.group(1)) >= fence_length:
                fence_character = ""
                fence_length = 0
        elif marker:
            fence_character = marker.group(1)[0]
            fence_length = len(marker.group(1))
            _mask_range(chars, offset, offset + len(line))
        elif re.match(r"[ \t]{0,3}>", line):
            _mask_range(chars, offset, offset + len(line))
        elif line.startswith(("    ", "\t")):
            _mask_range(chars, offset, offset + len(line))

        offset += len(line)

    _mask_group_matches(
        chars,
        re.compile(
            r"\b(?:source(?:\s+title)?|title|book|article|paper|essay|report|chapter|work)"
            r"(?:\s+(?:is|was|called|named|titled)|\s*:)\s*"
            r"(?P<title>(?P<em>\*|_)(?=\S)[^*_\r\n]{1,160}(?P=em))",
            re.IGNORECASE,
        ),
        "title",
    )
    _mask_contextual_markdown_titles(chars)
    _mask_markdown_emphasis_markers(chars)

    for pattern in (
        re.compile(r"<!--.*?-->", re.DOTALL),
        re.compile(
            r"<(?P<tag>script|style|pre|code|template|blockquote|q)\b[^>]*>.*?</(?P=tag)\s*>",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(r"(`+)(.+?)\1", re.DOTALL),
        re.compile(r"(?<=\]\()[^)\r\n]+(?=\))"),
        re.compile(r"(?m)^[ \t]{0,3}\[[^\]\r\n]+\]:[ \t]*\S+.*$"),
        re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]{}\"“”]+", re.IGNORECASE),
        re.compile(r'"(?:\\.|[^"\\\r\n])*"'),
        re.compile(r"“[^”]{0,8192}”"),
        re.compile(r"‘[^’]{0,8192}’"),
        re.compile(r"(?<![\w’])'(?:\\.|[^'\\\r\n])+'(?!\w)"),
        re.compile(
            r"(?<!\S)(?:/|\.{1,2}/|~/)[^\r\n<>\"'“”`]*?"
            r"\.[A-Za-z0-9][A-Za-z0-9._-]{0,15}"
            r"(?=[.,;:!?)]?(?:\s|$))"
        ),
        re.compile(r"(?<!\S)(?:/|\.{1,2}/)[^\s<>\"'“”`]+"),
        re.compile(r"(?<!\S)~/[^\s<>\"'“”`]+"),
        re.compile(r"\b[A-Za-z]:\\[^\s<>\"'“”`]+"),
        re.compile(r"@[A-Za-z0-9._-]+/[A-Za-z0-9._-]+"),
        re.compile(r"\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+(?:\(\))?"),
        re.compile(r"<[^>\r\n]+>"),
    ):
        _mask_matches(chars, pattern)

    return "".join(chars)


def mask_house_style_domain_terms(text: str) -> str:
    """Mask exact technical phrases before applying the local filler rule."""

    chars = list(text)
    for pattern in (
        re.compile(r"\brobust (?:regressions?|estimators?)\b", re.IGNORECASE),
        re.compile(
            r"\bdeterministic (?:algorithms?|automata|finite automata|orderings?|parsers?)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bcanonical URLs?\b", re.IGNORECASE),
        re.compile(
            r"\bcanonical surface\b(?=[^.!?\n]{0,80}\b"
            r"(?:algebraic|contact|differential|geometric|mathematical|"
            r"projective|Riemannian|topological)\s+geometry\b)",
            re.IGNORECASE,
        ),
        re.compile(r"\barray slice\b", re.IGNORECASE),
        re.compile(r"\b(?:Redux|state) slice\b", re.IGNORECASE),
        re.compile(r"\bAPI surfaces?\b", re.IGNORECASE),
        re.compile(r"\bgeometric surface\b", re.IGNORECASE),
        re.compile(r"\bfinancial leverage\b", re.IGNORECASE),
        re.compile(r"\blegal agency\b", re.IGNORECASE),
        re.compile(
            r"\bcanonical (?:JSON|forms?|representations?|encodings?|orderings?|"
            r"schemas?|correlations?|syntaxes?)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bdeterministic (?:byte )?output\b", re.IGNORECASE),
        re.compile(r"\bdeterministic (?:build|serialization)\b", re.IGNORECASE),
        re.compile(r"\brobust standard errors?\b", re.IGNORECASE),
        re.compile(r"\bdeterministic bootstrap samples?\b", re.IGNORECASE),
    ):
        _mask_matches(chars, pattern)
    return "".join(chars)


def _location(text: str, start: int) -> Tuple[int, int, str]:
    line = text.count("\n", 0, start) + 1
    line_start = text.rfind("\n", 0, start) + 1
    column = start - line_start + 1
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    excerpt = output_safe(
        text[line_start:line_end].rstrip("\r").strip()
    )
    if len(excerpt) > 180:
        excerpt = excerpt[:177].rstrip() + "..."
    return line, column, excerpt


def _first_qualifying_match(masked: str, rule: Rule):
    occurrences = [
        (match.start(), family, match)
        for family, pattern in enumerate(rule.patterns)
        for match in pattern.finditer(masked)
    ]
    occurrences.sort(key=lambda item: (item[0], item[1]))
    if not occurrences:
        return None

    total_family_counts: dict[int, int] = {}
    for _, family, _ in occurrences:
        total_family_counts[family] = total_family_counts.get(family, 0) + 1

    word_starts = [match.start() for match in re.finditer(r"\b[\w'-]+\b", masked, re.UNICODE)]
    if rule.edge_words is not None:
        total_words = len(word_starts)
        for _, _, match in occurrences:
            word_position = bisect_right(word_starts, match.start())
            if (
                word_position <= rule.edge_words
                or word_position > max(0, total_words - rule.edge_words)
            ):
                return match

    def qualifies(family_counts: dict[int, int]) -> bool:
        enough_families = len(family_counts) >= rule.minimum_distinct
        enough_repetition = (
            rule.repeat_qualifies is not None
            and any(count >= rule.repeat_qualifies for count in family_counts.values())
        )
        return enough_families or enough_repetition

    if not qualifies(total_family_counts):
        return None

    if rule.minimum_distinct == 1 or rule.window_words is None:
        return occurrences[0][2]

    positioned = [
        (
            start,
            family,
            match,
            bisect_right(word_starts, match.start()),
            bisect_right(word_starts, max(match.start(), match.end() - 1)),
        )
        for start, family, match in occurrences
    ]
    family_counts = {}
    left = 0

    for right, (_, family, _, _, end_word) in enumerate(positioned):
        family_counts[family] = family_counts.get(family, 0) + 1
        while left <= right and end_word - positioned[left][3] + 1 > rule.window_words:
            left_family = positioned[left][1]
            family_counts[left_family] -= 1
            if family_counts[left_family] == 0:
                del family_counts[left_family]
            left += 1
        if qualifies(family_counts):
            return positioned[left][2]
    return None


def _make_finding(text: str, source: str, rule: Rule, start: int) -> Finding:
    line, column, excerpt = _location(text, start)
    return Finding(
        rule_id=rule.rule_id,
        category=rule.category,
        severity=rule.severity,
        confidence=rule.confidence,
        source=output_safe(source),
        line=line,
        column=column,
        excerpt=output_safe(excerpt),
        message=rule.message,
    )


def scan_text(text: str, source: str) -> ScanResult:
    masked = mask_protected_text(text)
    masked_with_frontmatter = mask_protected_text(
        text,
        protect_frontmatter=False,
    )
    findings: List[Finding] = []
    omitted_by_rule: dict[str, int] = {}

    for rule in RULES:
        if rule.rule_id == "SLP-HSE-001":
            candidate_text = masked_with_frontmatter
        elif rule.rule_id == "SLP-HSE-002":
            candidate_text = mask_house_style_domain_terms(masked)
        else:
            candidate_text = masked
        if rule.report_each:
            candidates = []
            total_matches = 0
            for pattern in rule.patterns:
                kept_for_pattern = 0
                for match in pattern.finditer(candidate_text):
                    total_matches += 1
                    if kept_for_pattern < MAX_FINDINGS_PER_RULE:
                        candidates.append(match)
                        kept_for_pattern += 1
            matches = sorted(
                candidates,
                key=lambda match: (match.start(), match.end()),
            )[:MAX_FINDINGS_PER_RULE]
            findings.extend(
                _make_finding(text, source, rule, match.start())
                for match in matches
            )
            omitted = max(0, total_matches - len(matches))
            if omitted:
                omitted_by_rule[rule.rule_id] = omitted
            continue

        first = _first_qualifying_match(candidate_text, rule)
        if first is None:
            continue
        findings.append(_make_finding(text, source, rule, first.start()))

    return ScanResult(
        findings=tuple(
            sorted(findings, key=lambda finding: (finding.line, finding.column, finding.rule_id))
        ),
        omitted_by_rule=omitted_by_rule,
    )


def read_inputs(inputs: Sequence[str]) -> List[Tuple[str, str]]:
    if len(inputs) > MAX_INPUTS:
        raise InputError(f"input count exceeds the {MAX_INPUTS}-input limit")
    if inputs.count("-") > 1:
        raise InputError("stdin marker - may appear only once")

    loaded: List[Tuple[str, str]] = []
    combined_bytes = 0
    for token in inputs:
        if token == "-":
            data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            source = "<stdin>"
        else:
            path = Path(token)
            if has_symlink_component(path):
                raise InputError(f"symlink path component is not allowed: {token}")
            if not path.is_file():
                raise InputError(f"not a regular file: {token}")
            try:
                with path.open("rb") as handle:
                    data = handle.read(MAX_INPUT_BYTES + 1)
            except OSError as error:
                raise InputError(f"cannot read {token}: {error}") from error
            source = token

        if len(data) > MAX_INPUT_BYTES:
            raise InputError(
                f"input exceeds the {MAX_INPUT_BYTES}-byte limit: {source}"
            )
        combined_bytes += len(data)
        if combined_bytes > MAX_COMBINED_INPUT_BYTES:
            raise InputError(
                "combined input exceeds the "
                f"{MAX_COMBINED_INPUT_BYTES}-byte limit"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise InputError(f"input is not valid UTF-8: {source}") from error
        if "\x00" in text:
            raise InputError(f"unsupported NUL byte in input: {source}")
        loaded.append((source, text))

    return loaded


def _bounded_report(
    findings: Sequence[Finding],
    omitted_by_rule: dict[str, int] | None = None,
) -> Tuple[List[Finding], dict[str, int]]:
    kept: List[Finding] = []
    kept_by_rule: dict[str, int] = {}
    omitted = dict(omitted_by_rule or {})

    for finding in findings:
        rule_count = kept_by_rule.get(finding.rule_id, 0)
        if rule_count >= MAX_FINDINGS_PER_RULE or len(kept) >= MAX_REPORT_FINDINGS:
            omitted[finding.rule_id] = omitted.get(finding.rule_id, 0) + 1
            continue
        kept.append(finding)
        kept_by_rule[finding.rule_id] = rule_count + 1

    return kept, dict(sorted(omitted.items()))


def build_payload(
    findings: Sequence[Finding],
    omitted_by_rule: dict[str, int] | None = None,
) -> dict:
    kept, omitted = _bounded_report(findings, omitted_by_rule)
    counts = {
        severity: sum(finding.severity == severity for finding in kept)
        for severity in ("note", "warning", "error")
    }
    return {
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "findings": [asdict(finding) for finding in kept],
        "summary": {"total": len(kept), "by_severity": counts},
        "truncated": bool(omitted),
        "omitted": {
            "total": sum(omitted.values()),
            "by_rule": omitted,
        },
    }


def render_text(
    findings: Sequence[Finding],
    omitted_by_rule: dict[str, int] | None = None,
) -> str:
    kept, omitted = _bounded_report(findings, omitted_by_rule)
    lines = [f"one-more-pass:writing {VERSION} (schema {SCHEMA_VERSION})"]
    for finding in kept:
        source = terminal_safe(finding.source)
        excerpt = terminal_safe(finding.excerpt)
        lines.append(
            f"{source}:{finding.line}:{finding.column}: "
            f"{finding.severity.upper()} {finding.rule_id} "
            f"[{finding.category}/{finding.confidence}] {finding.message}"
        )
        lines.append(f"  {excerpt}")

    counts = {
        severity: sum(finding.severity == severity for finding in kept)
        for severity in ("note", "warning", "error")
    }
    if not kept:
        lines.append("No findings.")
    lines.append(
        "summary: "
        f"{len(kept)} finding(s) "
        f"(note={counts['note']}, warning={counts['warning']}, error={counts['error']})"
    )
    if omitted:
        lines.append(
            f"report limit: {sum(omitted.values())} additional finding(s) omitted"
        )
    return "\n".join(lines) + "\n"


def reaches_threshold(findings: Sequence[Finding], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    threshold = SEVERITY_RANK[fail_on]
    return any(SEVERITY_RANK[finding.severity] >= threshold for finding in findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read explicit UTF-8 prose files or stdin and report conservative review signals."
    )
    parser.add_argument("inputs", nargs="*", metavar="FILE|-", help="explicit file path or - for stdin")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--fail-on", choices=("error", "warning", "never"), default="warning")
    parser.add_argument("--version", action="version", version=f"one-more-pass:writing {VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.inputs:
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: at least one explicit file or - is required", file=sys.stderr)
        return EXIT_INPUT

    try:
        inputs = read_inputs(args.inputs)
        scan_results = [scan_text(text, source) for source, text in inputs]
        findings = [
            finding
            for result in scan_results
            for finding in result.findings
        ]
        omitted_by_rule: dict[str, int] = {}
        for result in scan_results:
            for rule_id, count in result.omitted_by_rule.items():
                omitted_by_rule[rule_id] = omitted_by_rule.get(rule_id, 0) + count
        payload = build_payload(findings, omitted_by_rule)
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(render_text(findings, omitted_by_rule), end="")
        return EXIT_FINDINGS if reaches_threshold(findings, args.fail_on) else EXIT_OK
    except InputError as error:
        print(
            f"one-more-pass:writing: input error: {safe_diagnostic(error)}",
            file=sys.stderr,
        )
        return EXIT_INPUT
    except Exception as error:
        print(
            f"one-more-pass:writing: internal error: {safe_diagnostic(error)}",
            file=sys.stderr,
        )
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
