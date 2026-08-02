# Code check registry

Use these IDs in review output. The IDs are part of the Code review contract. A scanner match is evidence to inspect, not a completed check.

| ID | Check | Failure boundary |
|---|---|---|
| `OMP-CODE-000` | Scan completeness | A required input or required mechanical check could not run. Use `NOT_RUN`, not `FAIL`. |
| `OMP-CODE-001` | Public contracts | The patch breaks an exported API, CLI, schema, event, file format, compatibility promise, or declared version boundary. |
| `OMP-CODE-002` | Resource lifetime | A handle, lock, transaction, subscription, task, timer, or connection can leak, outlive ownership, or be released twice. |
| `OMP-CODE-003` | Input limits | User-controlled or external input can cause unbounded allocation, recursion, work, retries, fan-out, or output. |
| `OMP-CODE-004` | State-change safety | Partial failure, retry, ordering, or cancellation can lose data, duplicate effects, corrupt state, or report false success. |
| `OMP-CODE-005` | Security and authorization | Authentication, ownership, authorization, injection, secret handling, privacy, or trust-boundary checks are missing or bypassable. |
| `OMP-CODE-006` | Verification quality | Changed behavior lacks a meaningful regression test or the evidence is skipped, filtered, weakened, over-mocked, or blindly updated. |
| `OMP-CODE-007` | Reuse | Duplication violates an explicit shared boundary, creates divergent critical logic, or misses an established reusable component. |
| `OMP-CODE-008` | Architecture | The change creates a forbidden dependency, cycle, layer violation, ownership ambiguity, or contradiction with an accepted design. |
| `OMP-CODE-009` | Accessibility | The change breaks semantics, naming, focus, keyboard operation, announcements, contrast, motion preferences, or an acceptance criterion. |
| `OMP-CODE-010` | Performance | Evidence shows a material regression, unbounded query or loop, excessive transfer, hot-path allocation, or missed caching contract. |
| `OMP-CODE-011` | Comments and names | A name or comment misstates behavior, hides risk, preserves dead rationale, or makes a public contract materially ambiguous. |
| `OMP-CODE-012` | Disabled or focused tests | A required test is skipped, left unfinished, or focused so the rest of the suite does not run, without a reviewed exception. |
| `OMP-CODE-013` | Not implemented | A reachable placeholder remains in behavior the change or public contract claims to support. |
| `OMP-CODE-014` | Blanket suppression | A broad lint, type, coverage, or analysis suppression hides required or unrelated findings. |
| `OMP-CODE-015` | Empty catches | An error path discards a failure that must be handled, reported, or deliberately propagated. |
| `OMP-CODE-016` | Debugger statements | A debugger or interactive breakpoint can ship or run in the released artifact. |
| `OMP-CODE-017` | Secret shapes | A real credential or private key is exposed. Keep scanner evidence redacted while confirming it. |
| `OMP-CODE-018` | TODO markers | A TODO, FIXME, HACK, or XXX marker needs ownership and release context. Default to `NEEDS_REVIEW`. |
| `OMP-CODE-019` | Debug logging | Debug-style logging may expose data, alter output, or add noise. Default to `NEEDS_REVIEW`. |
| `OMP-CODE-020` | Type escapes | An escape such as `any` may bypass a checked boundary. Default to `NEEDS_REVIEW`. |
| `OMP-CODE-021` | Narrow suppressions | A scoped suppression needs a named rule, reason, and minimal span. Default to `NEEDS_REVIEW`. |

## Applying the registry

- Use `PASS` only when the check ran and evidence supports it. `PASS` means no defect found in scope, not proof of global safety.
- Use `FAIL` for demonstrated violations. Record severity separately; not every failure must block release.
- Use `NOT_RUN` when required evidence is unavailable or a required check did not execute.
- Use `NEEDS_REVIEW` when a plausible risk lacks enough evidence for `PASS` or `FAIL`.
- Scanner matches always use `NEEDS_REVIEW`. Their severity is the possible impact if review confirms the failure boundary.
- Record a separate `PASS` or `FAIL` only after inspecting the matched code and its release context.
- Use `patch_attribution: not-applicable` when a check does not apply to the patch, paired with evidence explaining why.
- Preserve negation, modality, uncertainty, quantities, comparison direction, chronology, causality, attribution, identifiers, and commitments when proposing a change.

OMP-CODE-007 through OMP-CODE-011 are contextual. Apply repository baselines and acceptance criteria before treating them as blockers. Never turn style preference into release policy without evidence.
