# Behavior pressure tests

These fixtures keep difficult Writing and Code cases repeatable. Each case states what should route, what must remain exact, which changes are forbidden, and which output traits a reviewer should observe.

## Files

- `fixtures/writing-cases.json` covers final prose rewrites, review-only restraint, protected quotations, logical scope, voice, social bot-post cleanup, ordinary work messages, commands, URLs, and a drafting non-trigger.
- `fixtures/code-cases.json` covers mechanical signals, missing required checks, patch attribution, and an implementation non-trigger.
- `test_fixture_contract.py` validates the case and capture record shapes.
- `../../scripts/run-behavior-case.py` runs one isolated client session and saves its evidence without editing a fixture.

The dated record at `tests/writing/PRESSURE_TEST.md` remains in place. It contains earlier results that are not fully represented by these fixtures. Its two explicitly documented follow-up cases now also appear in `writing-cases.json`, but deleting the original record would lose evidence about the earlier runs.

## Check the clients first

Run the preflight before any paid client session:

```bash
python3 scripts/run-behavior-case.py preflight
```

The preflight checks the flags used by the harness. It also refuses to continue when One More Pass is enabled in the normal Claude profile, because that would taint the baseline. It does not install the plugin, contact a model, or write a result.

The checked command shape matches Codex 0.146.0 and Claude Code 2.1.220. Run the preflight again after either client changes.

## Running one arm

Preview a command without running it:

```bash
python3 scripts/run-behavior-case.py run \
  --client codex \
  --case WRITING-PRESSURE-001 \
  --arm plugin \
  --dry-run
```

Run the same arm and save its local evidence:

```bash
python3 scripts/run-behavior-case.py run \
  --client codex \
  --case WRITING-PRESSURE-001 \
  --arm plugin \
  --output-dir tests/behavior/evidence/codex-writing-001-plugin
```

Use `--client claude` for Claude Code. Use `--arm baseline` to run without the plugin. Evidence directories are ignored by Git. The harness refuses to overwrite an existing directory.

Codex uses a temporary `CODEX_HOME`, copies the existing `auth.json` with mode `0600`, installs the plugin only for the plugin arm, runs with a read-only sandbox, and removes the temporary home when done. It does not forward API key or token environment variables.

Claude Code keeps the normal home only so the client can use its existing keychain sign-in. It does not replace `CLAUDE_CONFIG_DIR`, because an empty config directory cannot use that sign-in. The command excludes user, project, and local setting sources, loads the plugin through `--plugin-dir` only for the plugin arm, and gives `Read` access to that same plugin directory so bundled references can be opened. It limits tools to `Skill` and `Read`, denies mutation and network tools, and disables session persistence. It does not copy a Claude credential into the repository or evidence directory.

Each run saves:

- `trace.jsonl`, the client event stream used for route proof;
- `output.txt`, the exact final response;
- `stderr.txt`, client diagnostics;
- `metadata.json`, the case, arm, command shape, and route evidence;
- `capture-template.json`, an unreviewed fixture record with empty review fields.

Do not paste the template into a fixture until a person has checked every required fact, protected span, forbidden change, and expected trait.

## Route proof

Route proof comes from the client event stream, not from a model saying it used a skill.

- Codex must emit a command event that reads the installed `skills/<name>/SKILL.md` file.
- Claude Code must emit a `Skill` tool event for `one-more-pass:<name>`.
- A plugin non-trigger passes routing only when no matching route event appears.
- A baseline has `trigger_observed: null` because the plugin was unavailable.

If route proof is missing, keep the response as failed evidence. Do not change `trigger_observed` by hand.

## Full private matrix

Wait until the release tree is stable. Then run these five cases in both clients, once with `baseline` and once with `plugin`:

| Skill | Trigger | Non-trigger |
| --- | --- | --- |
| Writing | `WRITING-PRESSURE-001`, `WRITING-PRESSURE-005` | `WRITING-PRESSURE-004` |
| Code | `CODE-PRESSURE-001` | `CODE-PRESSURE-004` |

That is 20 fresh sessions. The bot-post case adds four sessions: two clients, each with a baseline and plugin arm. `WRITING-PRESSURE-006` keeps the ordinary work-message counterexample repeatable but is not part of the required matrix, so it adds no paid sessions. Keep the client version and model fixed within a comparison pair. The harness defaults to `gpt-5.6-sol` for Codex and `opus` with maximum effort for Claude Code.

## Saving a reviewed result

Use the exact `prompt` and `input` from one fixture case.

1. Start a fresh session with One More Pass unavailable. Keep the client version and model fixed. Save the exact response under `results.no_skill`.
2. Start another fresh session with One More Pass available. Use the same client version, model, prompt, and input. Save the exact response under `results.skill_assisted`.
3. For a trigger case, allow normal skill routing. For a non-trigger case, the plugin stays available but the named skill should remain inactive.
4. Preserve the complete response, including Markdown, commands, code, and refusals. Do not trim or rewrite it before saving.
5. Review each response against the case fields. Keep the review field-based. Do not reduce it to a number.

Each result bucket is a list so the same case can hold separate client or model runs. Add one object per run:

```json
{
  "client": "client name",
  "client_version": "client version",
  "model": "model identifier",
  "captured_at": "2026-08-02T16:00:00Z",
  "prompt": "Copy the case prompt exactly.",
  "input": "Copy the case input exactly.",
  "output": "Paste the complete response exactly.",
  "review": {
    "trigger_observed": true,
    "required_facts_preserved": [
      "Copy each preserved fact from required_facts."
    ],
    "relationships_preserved": [
      "Record each attribution, condition, cause, contrast, sequence, or hierarchy that remained intact."
    ],
    "protected_spans_preserved": [
      "Copy each exact span that remained intact."
    ],
    "forbidden_changes_absent": [
      "Copy each forbidden change that did not occur."
    ],
    "expected_traits_observed": [
      "copy-observed-trait-identifiers"
    ],
    "notes": "Record concrete omissions or unexpected behavior."
  }
}
```

For the disabled-plugin run, set `trigger_observed` to `null`. For an available-plugin non-trigger case, set it to `false` when the skill stays inactive. Leave a result list empty until that run has actually happened.

## Reviewing results

A case passes only when its required facts, relationships, and protected spans remain intact, every forbidden change stays absent, and the expected traits are visible. Report missing evidence directly. Keep the exact response even when a case fails so a later review can reproduce the judgment.
