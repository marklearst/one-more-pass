# One More Pass plugin design

Date: 2026-08-02
Status: Approved for implementation

## Product

One More Pass gives finished work a final review before it becomes public.

The first release contains two skills:

- One More Pass: Writing edits public prose while protecting meaning and voice.
- One More Pass: Code reviews changed behavior, proof, and release risk.

The plugin supports Codex and Claude Code from one shared runtime directory. Each client gets a small manifest. The skills keep the same rules, scanners, and examples on both clients. Development tests stay outside the installed copy.

## Goals

The first release must:

1. Remove stale, formulaic writing without flattening the writer.
2. Keep the strict private house rules that Mark uses now, including no em dashes outside protected text.
3. Catch repeated social-post hooks, fake contrasts, empty praise, engagement bait, stock conclusions, repeated list shapes, and clusters of vague tech language.
4. Protect facts, logic, uncertainty, numbers, quotations, citations, code, URLs, names, and intentional voice.
5. Review code through behavior and evidence instead of style guesses.
6. Keep scanner matches separate from proved code defects.
7. Install and run as a native Codex plugin and a native Claude Code plugin.
8. Stay small enough to inspect in one sitting.

## Limits

The first release will not add:

- startup hooks
- context injection
- an MCP server
- telemetry
- a browser helper
- a Node.js runtime
- automatic source rewrites
- network calls from either scanner
- copied skill directories for each client
- support for clients that have not been tested

The plugin does not identify who wrote text or code. It does not report an authorship score. It reviews the work in front of it.

## Repository shape

```text
one-more-pass/
├── .agents/plugins/marketplace.json
├── .claude-plugin/marketplace.json
├── plugins/
│   └── one-more-pass/
│       ├── .claude-plugin/plugin.json
│       ├── .codex-plugin/plugin.json
│       ├── LICENSE
│       └── skills/
│           ├── writing/
│           │   ├── SKILL.md
│           │   ├── agents/openai.yaml
│           │   ├── references/
│           │   └── scripts/scan.py
│           └── code/
│               ├── SKILL.md
│               ├── agents/openai.yaml
│               ├── references/
│               └── scripts/scan.py
├── tests/
│   ├── writing/
│   ├── code/
│   ├── behavior/
│   └── package/
├── docs/
│   ├── plans/
│   └── specs/
├── CHANGELOG.md
├── LICENSE
└── README.md
```

Tests live outside `plugins/one-more-pass` so an installed plugin does not carry its development suite. Fixtures may still import scanner files from the runtime directory.

## Writing review

### Modes

The Writing skill has two modes:

- `rewrite`: return revised prose unless the user asks for notes or a diff.
- `review-only`: report findings without changing the source.

Drafting is outside this skill. A final review needs source text and a clear publication target.

### Order of work

1. Record the claims and protected spans that must remain exact.
2. Read the whole passage before applying a rule.
3. Run the scanner when a mechanical pass would help.
4. Review scanner matches in context.
5. Rewrite the smallest useful span.
6. Compare the result with the source claim by claim.
7. Restore the source when a safe rewrite is unclear.

### Private house rules

The private release uses Mark's house rules by default:

- no em dashes outside protected spans
- no canned social hooks or generic engagement prompts
- no empty opening or closing frame
- no fake `not X, but Y` turn when a direct statement works
- no decorative three-part list that adds rhythm without information
- no repeated bold-label or equal-section template used for decoration
- no clusters of vague tech terms where a concrete noun or verb is available
- no generic claim that something is important, powerful, modern, or meaningful without support in the source

The fixed-pattern bank also covers stale social and business copy such as `let that sink in`, `the uncomfortable truth`, `it turns out`, `let me be clear`, `full stop`, `plot twist`, `read that again`, `no one is talking about`, `I was not going to post this`, `that is the post`, `comment below`, `repost`, `share`, `save`, `follow for more`, `unpack`, `lean into`, `double down`, `deep dive`, `moving forward`, `circle back`, and `on the same page`. Exact triggers receive their own rule IDs or named pattern groups. Ambiguous terms still require context.

These rules do not change quotations, code, identifiers, URLs, source titles, required templates, or exact user terms. A house rule can trigger on the first clear match. Research-based vocabulary rules still use density limits because a watched word alone proves nothing.

### Rule records

Each rule keeps:

- a stable ID
- category
- scanner level when applicable
- a clear trigger
- exclusions
- a safe edit instruction
- positive cases
- negative cases

The scanner reports patterns. The skill decides whether an edit improves the passage.

### Writing scanner

The scanner:

- reads explicit UTF-8 files or stdin
- rejects directories and symlinks
- uses the Python standard library
- masks code, URLs, quoted text, and other protected spans
- has per-input, total-input, input-count, per-rule, and total-finding limits
- never writes files, runs source, starts a process, or uses the network
- reports omitted findings when a limit is reached

Its strict private default may exit with status `1` for a house-rule warning. Informational use remains available through `--fail-on never`.

## Code review

### Review record

The full review reports:

- check ID
- review state
- change attribution
- severity
- confidence
- evidence
- next action

The release result remains separate from each check.

### Scanner truth

A scanner pattern is a signal. It cannot prove that a disabled test, empty catch, placeholder, suppression, debugger statement, or secret-like value is wrong in its actual context.

The scanner therefore records a mechanical result instead of assigning a reviewed `FAIL`. The reviewer may later mark the related check as `PASS`, `FAIL`, `NOT_RUN`, or `NEEDS_REVIEW` after inspecting the code.

The scanner exits successfully after a complete scan, even when patterns need review. Its report calls that result `NEEDS_REVIEW`. Bad input exits with code `2`; an internal scanner error exits with code `3`. A pattern match never becomes a proved release blocker on its own.

### Code scanner

The code scanner keeps its current safety limits and read-only behavior. It must:

- scan explicit files, stdin, or added lines in a unified diff
- preserve source paths and line numbers
- redact secret-like evidence
- cap input and findings
- report incomplete reads as `NOT_RUN`
- distinguish a pattern match from a reviewed result
- reserve `CLEAR` and `BLOCK` for the completed human or agent review

This is a pre-release contract correction. The scanner keeps its planned `1.0.0` schema name, version, and record fields. Every scanner match becomes `NEEDS_REVIEW`, even when the possible impact is high. The scanner never emits `FAIL` or `BLOCK`. A completed review can still use those results after it proves a defect.

## Skill routing

Writing runs when a user asks for a final edit or review of prose that is ready to publish. It does not review code behavior.

Code runs when a user asks for a final review of a diff, implementation, package, pull request, or release. It does not implement features or debug an unknown failure.

When both apply, Code reviews behavior first. Writing then reviews the public explanation, documentation, changelog, pull request copy, or release notes.

The skills can work alone. They do not require another workflow plugin.

## Codex and Claude Code

Codex reads `plugins/one-more-pass/.codex-plugin/plugin.json` and the shared skills.

Claude Code reads `plugins/one-more-pass/.claude-plugin/plugin.json` and the same shared skills. The repository also acts as a private Claude marketplace through `.claude-plugin/marketplace.json`.

The Codex and Claude marketplace files point at `plugins/one-more-pass`. This keeps tests, plans, release notes, and repository metadata out of installed copies. Both runtime manifests use the same plugin name, version, repository URL, author, license, and description.

Scanner instructions must work from a copied plugin directory. They may not assume that the user's current directory is the repository root. Each skill explains how to locate its bundled script through the client-provided skill or plugin path, with a manual path fallback.

## Tests

### Scanner tests

Writing tests cover:

- every strict house rule
- useful counterexamples
- protected text
- meaning locks
- input-count and total-byte limits
- finding limits and omitted counts
- UTF-8, CRLF, stdin, symlink, and invalid-input behavior
- no write, process, or network capability

Code tests cover:

- the revised scanner schema
- advisory pattern records
- full-review state separation
- diff line mapping
- redaction
- limits and omitted counts
- false blockers such as intentional skips and deliberate unsupported branches
- no write, process, or network capability

### Behavior tests

Behavior fixtures test when each skill should and should not run. Each case keeps the prompt, source material, required facts, protected spans, forbidden changes, and expected output traits.

The suite includes:

- product copy
- documentation
- pull request text
- social copy
- quotations and citations
- technical terms with ordinary meanings
- deliberate profanity and dialect
- a valid logical contrast
- a valid three-item requirement
- code that contains a scanner pattern but has a sound reason
- code with a proved defect outside scanner coverage

The private release matrix runs five named cases in Codex and Claude Code, with and without the plugin. Exact responses and route evidence stay in the ignored local evidence directory for review. Fixture result fields remain empty unless reviewed evidence is deliberately added to the repository.

### Package and release checks

Package tests verify:

- JSON manifests parse
- manifest versions and identity match
- every referenced file stays inside the plugin root
- runtime package contents use an allowlist
- tests and development notes do not enter the runtime package
- Markdown links resolve and stale Stop Slop install paths are gone
- public repository text files contain no secret values, private paths, or structured generated and assistant attribution
- public prose files contain no em dash

Release checks verify:

- Codex accepts the marketplace and installs the nested plugin
- Claude Code validators accept the marketplace and nested plugin
- one trigger and one non-trigger case run for each skill in each client
- the reviewed Git comparison contains every release change

## Documentation

The README will explain:

- what each skill does
- when each skill should stay out of the way
- private Codex installation and update steps
- private Claude Code marketplace installation and update steps
- direct local development commands
- scanner use through stdin and explicit files
- test and release commands
- credit to the original Stop Slop project and its author

Public prose follows the Writing skill's own rules.

## Release checks

Before a private release:

1. Run both scanner test suites.
2. Run behavior and package tests.
3. Validate both client manifests with their own tools.
4. Load the plugin locally in Codex and Claude Code.
5. Run one trigger and one non-trigger case per skill in each client.
6. Inspect the runtime file list and checksum.
7. Scan public files for stale names, broken links, secrets, and banned attribution.
8. Review the full diff.

Git history will keep the imported Stop Slop commits and credit. New work will be split into honest commits by concern. The new private repository will become `origin`; the Stop Slop repository will remain available as `upstream`.
