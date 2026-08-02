---
name: code
description: Use only when existing code, code changes, diffs, or release candidates already exist and need a final review before merge or release. Do not use to implement features, write code, or modify the project.
---

# One More Pass: Code

Review behavior and evidence. Do not guess whether a person or model wrote the code.

Do not use this skill to implement a feature or fix. If the request asks for code changes, use the normal implementation workflow. Run this review after the changes exist and the user asks for a final pass.

The plugin release version is the public release identity. The scanner keeps a separate schema version for machine-readable output.

## Review contract

For every applicable check, report these fields separately:

- `id`: stable ID from [code-invariants.md](references/code-invariants.md)
- `run_state`: `PASS`, `FAIL`, `NOT_RUN`, or `NEEDS_REVIEW`
- `patch_attribution`: `introduced`, `worsened`, `pre-existing`, `unknown`, or `not-applicable`
- `evidence`: concrete path, line, command result, or observed behavior
- `action`: the smallest next step that resolves uncertainty or risk

Keep the final release decision separate. Never replace `NOT_RUN` with `FAIL`, `BLOCK`, or `PASS`. A pre-existing failed gate can block release without becoming a patch fault. A proven blocker takes precedence over missing checks. Keep every `NOT_RUN` check listed even when the release decision is `BLOCK`. If no blocker is proven, any required `NOT_RUN` check makes the decision `INCOMPLETE`.

State concrete evidence and uncertainty separately. A variable name, log label, TODO, or scanner signal does not prove credential disclosure or a release-blocking security failure. Trace the value, its capability, and its path to the log or other sink. If that trace is missing, keep the check at `NEEDS_REVIEW` and do not set the release decision to `BLOCK` solely from the signal.

## Workflow

1. Establish the requested behavior, changed files, base revision, head revision, and repository conventions. If the comparison boundary is unknown, mark patch attribution `unknown`.
2. Inspect the diff and enough surrounding code to understand callers, data flow, error paths, and public contracts.
3. Run the bundled scanner on explicit files or stdin. It supplies signals to inspect, not completed review findings.
4. Inspect each scanner signal in context, then record a separate `PASS`, `FAIL`, or `NEEDS_REVIEW` check.
5. Review OMP-CODE-001 through OMP-CODE-011 using [code-invariants.md](references/code-invariants.md) and [review-checklist.md](references/review-checklist.md).
6. Separate verification evidence from test quality. A passing command does not compensate for skipped, filtered, weakened, or irrelevant tests.
7. Emit check records, then a separate release decision: `CLEAR`, `NEEDS_REVIEW`, `BLOCK`, or `INCOMPLETE`.

Use this priority when guidance conflicts:

1. Correctness, security, privacy, and behavior
2. Explicit user requirements and acceptance criteria
3. Repository contracts and established conventions
4. Maintainability and style heuristics

## Scanner

Resolve the scanner before running it. `scripts/scan.py` is in the same directory as this `SKILL.md`, not in the project being reviewed. Never build its path from the user's working directory.

- In Claude Code, use `${CLAUDE_PLUGIN_ROOT}/skills/code/scripts/scan.py` when `CLAUDE_PLUGIN_ROOT` is set.
- In Codex or another client, start with the absolute path of this `SKILL.md`, then replace `SKILL.md` with `scripts/scan.py`.

Store that absolute path in `ONE_MORE_PASS_CODE_SCANNER`. Run it only on files placed in scope:

```bash
python3 "$ONE_MORE_PASS_CODE_SCANNER" --format text path/to/file.ts path/to/other.py
git diff --no-ext-diff | python3 "$ONE_MORE_PASS_CODE_SCANNER" --diff --format json -
```

Plain `-` means source text. `--diff -` means a Git unified diff and scans added lines only. It ignores removed and unchanged lines, records changed paths and new-file line numbers, and marks matches as `introduced`. An empty or metadata-only Git diff is valid and contains no added-line blocks. Scan full changed files when a rule may depend on unchanged code around the edit.

The scanner uses only the Python standard library. It accepts at most 256 explicit inputs, 2 MiB per input, and 8 MiB combined. It keeps at most 25 pattern locations per rule or 200 per report. When matches exceed either limit, it reports the exact omitted count and requires review of the full input. It does not recurse, follow symlinks, access the network, invoke subprocesses, mutate inputs, or offer fixes.

It raises review signals for:

- disabled tests, explicit not-implemented placeholders, blanket suppressions, empty catches, debugger statements, and high-confidence secret shapes with possible `blocker` impact
- generic TODO markers, debug-style logging, type escapes, and narrow suppressions with possible `warning` impact

Every pattern match uses `run_state: NEEDS_REVIEW`. Severity describes the possible impact if review confirms a defect. It does not change the run state or decide whether release should stop.

Strings and comments are masked where their contents would create false positives. The not-implemented rule requires a code statement before it inspects the error text, so a quoted code example is not treated as runtime code. Secret evidence is redacted. A signal never proves authorship or a defect. A reviewer must inspect it before recording `PASS` or `FAIL`.

| Exit | Meaning |
|---|---|
| `0` | Scan completed; review signals may remain |
| `2` | Bad input, bad arguments, or a required check that did not run |
| `3` | Internal scanner failure |

Exit `1` is reserved and is not emitted. A pattern match cannot fail a completed scan.

Use `--version` and `--schema-version` to inspect the contracts. JSON output includes tool and schema versions, files supplied, files read, text blocks checked, scan mode, bounded check records, omitted-match counts, state counts, and a `scan_decision`. Text output ends with the same `SCAN` result.

The scanner can report `NO_MECHANICAL_BLOCKER`, `NEEDS_REVIEW`, or `INCOMPLETE`. It never reports `FAIL`, `BLOCK`, or `CLEAR`. Only the completed review may issue `CLEAR` or `BLOCK`, after OMP-CODE-001 through OMP-CODE-011 and the required repository checks run.

## Blocking rules

Block release for concrete runtime correctness, data loss, state corruption, public-contract breakage, resource leaks, unbounded input, security or authorization failures, privacy exposure, destructive migrations, unsafe concurrency, or missing required verification.

Reuse, architecture, accessibility, performance, comments, names, and test design can also block when evidence ties them to an explicit boundary, acceptance criterion, user harm, or release gate. Do not block on taste alone.

Keep severity, confidence, applicability, run state, and patch attribution distinct. A severe low-confidence concern remains visible as `NEEDS_REVIEW` with a verification path.

## Review boundaries

- Do not claim AI authorship, intent, negligence, or quality from lexical patterns.
- Do not treat compilation, CI, or superficial tests as proof of correct behavior.
- Do not invent behavior, actors, requirements, or repository rules.
- Report the signal and the smallest next step. Do not rewrite the supplied patch unless the user explicitly asks for a patch. When recommending a patch, explain what it preserves.
- Do not hide pre-existing failures. Report them without blaming the patch.
- Do not let optional tools change the base scanner contract. See [optional-tools.md](references/optional-tools.md).
- Treat another review or verification report as evidence, not a verdict. Confirm its scope and freshness before using it.
- Do not require another skill, agent, or service. This review must work on its own.
- Minimize churn. Flag unrelated formatting, deleted explanatory comments, blind snapshot replacement, and dependency changes mixed into logic.

See [examples.md](references/examples.md) for correctly separated state, attribution, evidence, action, and release decisions.
