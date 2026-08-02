# Optional tools

The bundled scanner is the default check. It never invokes another program, accesses the network, installs dependencies, or changes a file.

The scanner lives at `scripts/scan.py` in the same directory as this skill's `SKILL.md`. Resolve that absolute path before running it. Do not assume the user's project contains a `scripts/scan.py` file. Claude Code can use `${CLAUDE_PLUGIN_ROOT}/skills/code/scripts/scan.py`; other clients can derive the path from the loaded skill file.

Use `--diff` only for Git unified diffs. That mode checks added lines and ignores deleted and unchanged lines. Scan the full changed file when a finding depends on nearby code that the diff did not add.

## Tool policy

Run repository tools only when they are already available and their execution is within the requested scope. Do not install a tool or change configuration merely to strengthen a review without authorization.

| Tool class | Useful evidence | Limit |
|---|---|---|
| Unit and integration tests | Reproduced behavior and regression coverage | Passing output may hide skips, filters, weak assertions, or excessive mocks. |
| Build and type checker | Compilation and checked interface evidence | Does not prove runtime, state, authorization, or test quality. |
| Linter and formatter | Repository convention violations | Style findings are not release blockers without an explicit contract. |
| Coverage tooling | Executed lines and branches | Coverage percentage does not establish meaningful assertions. |
| Semgrep or repository SAST | Known unsafe patterns and data-flow clues | Findings require context; absence does not prove security. |
| Vale or prose lint | Comment and documentation consistency | Do not apply prose rules to identifiers, code, quoted contracts, or generated text. |
| Accessibility tooling | Detectable semantic and contrast failures | Automated checks cover only part of accessibility. |
| Profilers and benchmarks | Measured hot paths and regressions | Compare controlled base and head runs before attributing change. |

## State rules

- Optional and unavailable: record why it was not applicable; do not fail the base scan.
- Required by the repository, acceptance criteria, or user and unavailable: `run_state: NOT_RUN`; release decision `INCOMPLETE`.
- Executed and failed: `run_state: FAIL`; attribute with base/head evidence.
- Executed with ambiguous output: `run_state: NEEDS_REVIEW`; include the command and relevant excerpt.
- Executed and passed: `run_state: PASS`; state exactly what the result covers.

Keep raw command evidence separate from the conclusion. Never replace a scanner or test result with an unsupported summary.

## Parser limits

The bundled scanner uses a small lexical masker, not a full parser. It treats `#` as a comment marker across supported text inputs, so JavaScript private fields and CSS color literals can hide a nearby signal. Template interpolation, regular-expression literals, heredocs, nested comments, and malformed source can also produce missed findings. Use the repository parser, linter, type checker, or security tool when that detail matters.
