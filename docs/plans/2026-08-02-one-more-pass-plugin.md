# One More Pass implementation plan

Date: 2026-08-02
Design: `docs/specs/2026-08-02-one-more-pass-plugin-design.md`

## Working rules

- Confirm the repository root with `git rev-parse --show-toplevel` before work begins.
- Preserve current dirty work and imported history.
- Write tests before each behavior change.
- Use `apply_patch` for source edits.
- Run focused tests after each task and the full suite at the end.
- Do not commit, change remotes, push, or open a pull request until the finished diff passes independent review.
- Never add assistant credit, generated-by text, task links, or tool names to public Git records.

## Runtime path correction

Client install tests showed that a repository-root marketplace source copied development files into the plugin cache. The installable plugin now lives at `plugins/one-more-pass`.

- Paths below that begin with `skills/` resolve under `plugins/one-more-pass/`.
- Client manifests live under `plugins/one-more-pass/.codex-plugin/` and `plugins/one-more-pass/.claude-plugin/`.
- Marketplace catalogs remain at the repository root.
- Tests, plans, release notes, and the inventory script remain outside the installed runtime.

## Task 1: Fix Writing modes and routing

Files:

- Modify `skills/writing/SKILL.md`
- Modify `skills/writing/agents/openai.yaml`
- Add `tests/behavior/test_skill_contracts.py`
- Add `tests/behavior/fixtures/writing-routing.json`

Steps:

1. Add failing tests for rewrite, review-only, non-trigger, and paired Writing/Code use.
2. Assert that drafting from a blank prompt is outside the Writing skill.
3. Assert that Writing protects prose facts and does not review code behavior.
4. Update the skill description, modes, and routing text.
5. Add a refusal path for authorship questions that offers an editorial review instead.
6. Run `python3 -m unittest tests.behavior.test_skill_contracts -v`.

Expected result: all routing cases pass and the skill no longer advertises an undefined draft mode.

## Task 2: Restore and tighten strict Writing rules

Files:

- Modify `skills/writing/references/prose-rules.md`
- Modify `skills/writing/references/house-style.md`
- Modify `skills/writing/references/rewrite-rules.md`
- Modify `skills/writing/references/examples.md`
- Modify `skills/writing/scripts/scan.py`
- Move and expand tests under `tests/writing/`

Steps:

1. Add failing cases for every unprotected em dash, single strong canned hooks, generic engagement prompts, social calls to comment or repost, empty frames, fake contrast, staccato revelation, instant question and answer, decorative three-part lists, repeated presentation shapes, unsupported praise, repeated same-family phrases, and vague tech-language clusters.
2. Add negative cases for quotations, code, paths, source titles, true logical contrast, real requirements, scientific terms, and deliberate voice.
3. Add rewrite cases that preserve negation, uncertainty, quantities, quotations, citations, links, names, profanity, and dialect.
4. Restore useful fixed phrases from the imported Stop Slop history, including stale social hooks and business filler. Do not restore blanket bans on adverbs, passive voice, questions, `Wh-` openings, hedges, or every three-item list.
5. Update the rule records and scanner patterns. Keep research vocabulary behind density limits.
6. Report every fixed mechanical occurrence, not only the first match for a rule.
7. Keep house rules strict for this private release and make a house warning the default nonzero threshold.
8. Run `python3 -m unittest discover -s tests/writing -v`.

Expected result: strict house rules are found without changing or flagging protected spans and valid counterexamples.

## Task 3: Bound the Writing scanner report

Files:

- Modify `skills/writing/scripts/scan.py`
- Modify `skills/writing/references/optional-tools.md`
- Modify `tests/writing/test_scan.py`

Steps:

1. Add failing tests for more than 256 inputs, more than 8 MiB combined input, more than 25 findings for one rule, and more than 200 findings in one report.
2. Add tests for exact omitted counts and a `truncated` field.
3. Add input-count, combined-size, per-rule, and report limits.
4. Preserve the current per-file limit and read-only design.
5. Run `python3 -m unittest discover -s tests/writing -v`.

Expected result: large jobs stop safely or report truncation without hiding that findings were omitted.

## Task 4: Correct Code scanner truth semantics

Files:

- Modify `skills/code/scripts/scan.py`
- Modify `skills/code/SKILL.md`
- Modify `skills/code/references/code-invariants.md`
- Modify `skills/code/references/review-checklist.md`
- Modify `skills/code/references/examples.md`
- Move and expand tests under `tests/code/`

Steps:

1. Add failing tests showing that a scanner match is not a reviewed `FAIL`.
2. Add counterexamples for intentional `skipif`, a deliberate unsupported branch, and a documented best-effort catch.
3. Keep the planned schema name, version `1.0.0`, and current record fields because the contract has not been released.
4. Make every scanner match `NEEDS_REVIEW`. Keep `severity: blocker` or `warning` as the possible impact if review confirms the defect.
5. Use `NEEDS_REVIEW`, `NO_MECHANICAL_BLOCKER`, or `INCOMPLETE` for scanner results. The scanner never emits `BLOCK`.
6. Exit `0` after every complete scan, including scans with patterns. Keep `2` for bad or unreadable input and `3` for an internal scanner error.
7. Reserve `PASS`, `FAIL`, `NOT_RUN`, `NEEDS_REVIEW`, `CLEAR`, and `BLOCK` for the completed review contract.
8. Update actions so they ask the reviewer to confirm context before removing or rotating anything.
9. Update text and JSON renderers, fixtures, and docs.
10. Prove that a separate reviewer-confirmed `FAIL` still produces a `BLOCK` release decision.
11. Run `python3 -m unittest discover -s tests/code -v`.

Expected result: mechanical patterns remain visible and useful without being reported as proved defects.

## Task 5: Add shared Codex and Claude Code packaging

Files:

- Modify `plugins/one-more-pass/.codex-plugin/plugin.json`
- Add `plugins/one-more-pass/.claude-plugin/plugin.json`
- Add `.claude-plugin/marketplace.json`
- Add `.agents/plugins/marketplace.json`
- Add `tests/package/test_manifests.py`
- Add `tests/package/test_runtime_contents.py`
- Add `scripts/list-runtime-files.py`

Steps:

1. Add failing tests for shared identity, matching versions, repository metadata, no hook field, local marketplace sources, and paths kept inside the plugin root.
2. Add failing tests for a runtime allowlist that excludes `tests/`, `docs/`, caches, patches, and local reports.
3. Add the Claude Code and Codex manifests with one shared `plugins/one-more-pass/skills/` path.
4. Add a small standard-library script that prints and hashes the allowed runtime files without copying or modifying them.
5. Run `python3 -m unittest discover -s tests/package -v`.
6. Run the available Codex plugin validator.
7. Run `claude plugin validate .` when the Claude CLI is available.

Expected result: both clients accept the same skills and the runtime file list is small and reviewable.

## Task 6: Make scanner invocation work after installation

Files:

- Modify both `skills/*/SKILL.md`
- Modify both `skills/*/references/optional-tools.md`
- Modify `tests/behavior/test_skill_contracts.py`
- Modify `tests/package/test_runtime_contents.py`

Steps:

1. Add failing tests that reject repository-root-only commands such as bare `python3 scripts/scan.py`.
2. Document scanner lookup from the active skill or plugin directory for Codex and Claude Code.
3. Provide stdin examples that do not need the user's project path.
4. Verify every documented command against a copied temporary plugin directory.
5. Run behavior and package tests.

Expected result: documented scanner commands work from an installed copy and never assume the user's working directory is One More Pass.

## Task 7: Build saved behavior pressure tests

Files:

- Add `tests/behavior/fixtures/writing-cases.json`
- Add `tests/behavior/fixtures/code-cases.json`
- Add `tests/behavior/test_fixture_contract.py`
- Add `tests/behavior/README.md`
- Replace the old `skills/writing/tests/PRESSURE_TEST.md` with a root test record or remove it after its useful cases move.

Steps:

1. Save hard Writing and Code cases with required facts, protected spans, forbidden edits, and expected traits.
2. Include trigger and non-trigger prompts.
3. Add contract tests for fixture shape and protected content.
4. Save exact no-skill and skill-assisted outputs during the final manual run.
5. Review results without detector scores or authorship claims.

Expected result: the plugin can be judged against repeatable hard cases instead of an unsaved impression.

## Task 8: Rewrite public documentation

Files:

- Modify `README.md`
- Modify `CHANGELOG.md`
- Add `docs/RELEASE.md`
- Review `LICENSE`

Steps:

1. Add Codex private install and update steps.
2. Add Claude Code private marketplace install and update steps.
3. Explain both skills, their limits, scanner use, tests, and local development.
4. Keep Hardik Pandya and Stop Slop credit clear.
5. Remove stale install paths and claims that have not been tested.
6. Run One More Pass: Writing against every public Markdown file with strict house rules.
7. Check links and commands.

Expected result: a new user can install, call, update, test, and remove the private plugin without guessing.

## Task 9: Full verification and independent review

Commands and checks:

1. Run all Python unit tests from the repository root.
2. Run both scanners against their own public files.
3. Run JSON, YAML, Markdown-link, manifest, runtime-file, attribution, secret, and cache checks.
4. Time both scanners against their maximum supported combined input.
5. Copy the runtime file set to a temporary directory and rerun package tests there.
6. Validate with Codex and Claude Code.
7. Run one trigger and one non-trigger case per skill in each client.
8. Request independent Writing, Code, packaging, and release reviews.
9. Fix every proved blocker, then rerun the full suite from a clean command log.

Expected result: fresh proof covers behavior, packaging, safety, installation, and public prose.

## Task 10: Prepare private Git history

Only begin after Task 9 passes and the final diff is approved.

Proposed commit groups:

1. `feat(writing): strengthen final-pass review rules`
2. `fix(code): separate scanner signals from review findings`
3. `feat(plugin): add Codex and Claude packaging`
4. `test: add behavior and package checks`
5. `docs: document private installation and release checks`

Git steps:

1. Confirm the old remote still points to the imported Stop Slop source.
2. Rename that remote to `upstream`.
3. Add `git@github.com:marklearst/one-more-pass.git` as `origin`.
4. Create `feat/one-more-pass` from the preserved imported history.
5. Stage each commit by concern and inspect its exact diff.
6. Scan commit messages and public files for banned attribution and stale names.
7. Push only to the private One More Pass repository.
8. Open a private pull request with a direct, factual body.

Expected result: the repository keeps its source credit and gains readable project history without one oversized commit.
