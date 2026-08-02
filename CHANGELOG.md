# Changelog

## One More Pass 1.0.0 (unreleased)

### Added

- Added the private One More Pass 1.0.0 plugin with exactly two skills: Writing and Code.
- Added separate Codex and Claude Code manifests that load the same skill files from `plugins/one-more-pass`.
- Added local marketplace files for private installation from a checkout or Git repository.
- Added a read-only Code scanner for review signals, input limits, redacted evidence, and stable JSON output.
- Added package, behavior, and scanner tests for both skills.
- Added an isolated Codex and Claude Code behavior harness with route evidence and review templates.
- Added a runtime file inventory with SHA-256 hashes.
- Added private install, update, removal, test, and release instructions.

### Changed

- Renamed the public skill identities to `one-more-pass:writing` and `one-more-pass:code`.
- Moved the installable files into `plugins/one-more-pass` so tests, plans, and repository notes stay outside the installed copy.
- Replaced blanket bans on adverbs, passive voice, three-item lists, `Wh-` openings, and watched words with gated, contextual review rules.
- Added a mandatory meaning checklist for facts, negation, uncertainty, quantities, quotations, code, identifiers, and voice.
- Separated research signals, house style, and editorial review. Findings no longer claim or imply authorship.
- Replaced the phrase and structure ban lists with versioned rules, evidence notes, exemptions, safe rewrite instructions, and positive and negative fixtures.
- Expanded the Writing scanner with bounded file and stdin inputs, text and JSON output, stable rule IDs, protected-text masking, and documented exit codes.
- Expanded social-hook and engagement-bait checks while keeping work messages and technical terms out of those warnings.
- Added output redaction for current OpenAI and Anthropic key formats and neutralized Unicode direction controls in scanner output.
- Added a local filler-cluster warning for recurring project-copy terms without turning single words into errors.
- Added skill interface metadata in `agents/openai.yaml`.
- Added regression fixtures for semantic preservation, quoted and literal text, dialect, passive voice, real triads, domain terms, clean prose, and genuinely formulaic prose.
- Added references for research, prose rules, house style, rewrite safety, optional tools, and examples.

### Removed

- Removed the superseded `references/phrases.md` and `references/structures.md` ban lists.

## 2026-01-13

### Added

**Phrases (references/phrases.md)**
- Throat-clearing: "Here's what I find interesting", "Here's the problem though"
- Performative emphasis: "creeps in", "I promise", "They exist, I promise"
- Telling instead of showing: "This is genuinely hard", "This is what leadership actually looks like"

**Structures (references/structures.md)**
- Binary contrasts: "Not X. But Y.", "It's not this. It's that.", "stops being X and starts being Y"
- Rhythm patterns: staccato fragmentation, dashes for dramatic pause, hedging as reassurance
- Word patterns: absolute words (always, never, everyone, etc.), AI-overused intensifiers (deeply, truly, fundamentally, inherently, simply, literally, inevitably)

## 2026-01-12

- Restructured skill following Claude Code best practices (PR #1)
- Split into SKILL.md and references/ folder

## 2025-01-12

- Initial release
