# Review checklist

## Establish scope

- Identify the requested behavior and acceptance criteria.
- Record the base and head revisions or state that attribution is unknown.
- Inspect changed files plus the callers, tests, configuration, migrations, and contracts needed to understand impact.
- Separate changed behavior from nearby pre-existing defects.

## Review behavior

- `OMP-CODE-001`: Check exported APIs, CLI flags, schemas, events, serialization, compatibility, and version declarations.
- `OMP-CODE-002`: Follow resource ownership through success, error, timeout, cancellation, and cleanup.
- `OMP-CODE-003`: Bound external input, recursion, retries, concurrency, memory, work, and output.
- `OMP-CODE-004`: Trace partial writes, transactions, idempotency, retry, ordering, detached work, and reported success.
- `OMP-CODE-005`: Check authorization after authentication, object ownership, isolation, injection, privacy, and secret exposure.
- `OMP-CODE-006`: Name the production change each test would catch. Inspect skipped tests, filters, mocks, snapshots, coverage exclusions, and deleted assertions.
- `OMP-CODE-007`–`OMP-CODE-011`: Apply explicit repository, architecture, accessibility, performance, naming, and comment contracts.

Compilation and green CI are evidence that commands ran. They do not prove runtime correctness, authorization, state safety, public compatibility, or test relevance.

## Run mechanical checks

Pass explicit changed files or a diff through `scripts/scan.py`. Do not point it at a directory. Every match is a `NEEDS_REVIEW` signal. Inspect it in context before recording a separate `PASS` or `FAIL`. Generic TODOs, logging, type escapes, and narrow suppressions are review signals, not authorship evidence.

If an optional tool is absent, do not weaken or skip the bundled scanner. If a repository or user makes that tool required, record `NOT_RUN` and make the release decision `INCOMPLETE` until it runs.

## Record every check

Use one record per applicable check:

```json
{
  "id": "OMP-CODE-006",
  "run_state": "FAIL",
  "patch_attribution": "introduced",
  "evidence": "tests/payments.test.ts:44 changes test.skip to cover the new retry path",
  "action": "Restore the regression test and verify it fails without the fix"
}
```

Do not merge state and attribution. These combinations are valid:

| Situation | Run state | Attribution | Release decision |
|---|---|---|---|
| Required gate fails on base and head | `FAIL` | `pre-existing` | `BLOCK`, without blaming the patch |
| Patch causes a new gate failure | `FAIL` | `introduced` | `BLOCK` |
| Patch makes an existing defect worse | `FAIL` | `worsened` | `BLOCK` |
| Required check was not executed and no blocker is proven | `NOT_RUN` | `unknown` | `INCOMPLETE` |
| Warning needs context | `NEEDS_REVIEW` | Best supported value | `NEEDS_REVIEW` |
| Check ran and passed | `PASS` | Supported value or `not-applicable` | Contributes to `CLEAR` |

Never write `run_state: BLOCK`. `BLOCK` belongs only to the separate release decision.

Scanner severity records possible impact if the signal is confirmed. A `severity: blocker` signal is not a failed check and cannot block release on its own.

## Use other review evidence carefully

- Another code review can supply paths, lines, reproduced behavior, and open questions. Check its scope before using those records.
- Verification output must name the command, revision, scope, exit status, and relevant result. If those details are missing or stale, rerun the check or use `NOT_RUN`.
- Do not copy another review's final verdict. Record the evidence under the matching OMP-CODE ID and make this review's decision from the complete set of checks.
- Avoid repeating expensive checks when fresh evidence covers the same revision and scope.
- Do not require another skill, agent, or service. One More Pass: Code remains usable by itself.

## Make the release decision

Choose one result after listing checks:

A proven blocker takes precedence over missing checks. Keep every `NOT_RUN` check listed even when the release decision is `BLOCK`. If no blocker is proven, any required `NOT_RUN` check makes the decision `INCOMPLETE`.

- `BLOCK`: A demonstrated release blocker is `FAIL`, including a pre-existing required gate that remains unresolved. List any checks that remain `NOT_RUN`.
- `INCOMPLETE`: No blocker is proven, and at least one required check is `NOT_RUN`. Run it before deciding.
- `NEEDS_REVIEW`: No blocker is proven, but an unresolved contextual decision remains.
- `CLEAR`: All required checks ran, no blocker failed, and no review decision remains.

Give the decision its own evidence and action. Patch attribution determines responsibility, not whether a release gate exists.

## Guard against superficial proof

- A build can pass while runtime behavior is fabricated, errors are swallowed, or detached work is lost.
- Authentication can pass while object-level authorization fails.
- Tests can pass because affected cases are skipped, excluded, mocked away, or asserted through snapshots that were blindly replaced.
- A clean mechanical scan can coexist with contract, concurrency, accessibility, or architecture defects.
- Bland code with no lexical signal can still be unsafe. Review behavior and evidence first.
