# Review output examples

## Scanner signal before review

```json
{
  "id": "OMP-CODE-016",
  "run_state": "NEEDS_REVIEW",
  "patch_attribution": "introduced",
  "severity": "blocker",
  "path": "src/server.ts",
  "line": 24,
  "evidence": "debugger;",
  "action": "Confirm whether this statement can ship or run; remove it if it can."
}
```

This is a scanner signal. It shows where to look and the possible impact. It does not prove a defect or block release.

After inspection, the reviewer can record a separate `PASS`, `FAIL`, or `NEEDS_REVIEW` check. A confirmed `FAIL` with blocker severity can support a `BLOCK` release decision.

## Patch-introduced blocker

```json
{
  "id": "OMP-CODE-005",
  "run_state": "FAIL",
  "patch_attribution": "introduced",
  "evidence": "src/projects.ts:81 loads a project by ID after authentication but never checks owner_id",
  "action": "Enforce object ownership in the query and add a cross-user regression test"
}
```

Release decision: `BLOCK` because the patch introduces an authorization bypass.

## Pre-existing failed release gate

```json
{
  "id": "OMP-CODE-006",
  "run_state": "FAIL",
  "patch_attribution": "pre-existing",
  "evidence": "The required release test fails with the same assertion on base and head",
  "action": "Repair or explicitly waive the existing gate before release; do not attribute it to this patch"
}
```

Release decision: `BLOCK`. The gate blocks release, while attribution shows that the patch did not cause it.

## Required check did not run

```json
{
  "id": "OMP-CODE-006",
  "run_state": "NOT_RUN",
  "patch_attribution": "unknown",
  "evidence": "The required integration suite was not available in this environment",
  "action": "Run the integration suite before making a release decision"
}
```

Release decision: `INCOMPLETE`, not `BLOCK`. `NOT_RUN` describes missing evidence rather than a demonstrated defect.

## Contextual review signal

```json
{
  "id": "OMP-CODE-020",
  "run_state": "NEEDS_REVIEW",
  "patch_attribution": "introduced",
  "evidence": "src/decoder.ts:24 casts an external payload as any before validation",
  "action": "Confirm the boundary validation or replace the escape with a checked decoder"
}
```

Release decision: `NEEDS_REVIEW` until context establishes `PASS` or `FAIL`. The type escape does not prove authorship.

## Mechanical pass

```json
{
  "id": "OMP-CODE-016",
  "run_state": "PASS",
  "patch_attribution": "not-applicable",
  "evidence": "The debugger-statement check completed across three explicit inputs without a matching signal",
  "action": "Continue the manual behavior review; a mechanical PASS does not prove safety"
}
```

A collection of mechanical passes supports the review but does not clear OMP-CODE-001 through OMP-CODE-011.

The scanner reports `SCAN NO_MECHANICAL_BLOCKER` for this case. It never reports `RELEASE CLEAR`. The reviewer makes the release decision after completing the manual checks and repository tests.
