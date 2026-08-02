---
name: writing
description: Use only when the request starts with existing prose supplied or identified by the user and that prose needs a final editorial review, especially for engagement bait, canned social hooks, formulaic bot copy, repeated templates, filler, vague praise, or loss of voice. Do not use to draft new prose from a prompt, brief, outline, or notes, or to create prose and review it in the same turn.
---

# One More Pass: Writing

Give existing prose one strict final pass without changing what it says or who is saying it.

## Scope

Writing reviews prose. It does not review code behavior, test quality, runtime safety, or release risk. Use `one-more-pass:code` for those concerns. A request that contains prose and code may use both skills, with each skill limited to its own part.

Do not use this skill to draft from a blank prompt. The user must supply or identify the target prose before the request begins. Do not create prose and then review it in the same turn.

Requests to remove engagement bait, canned social hooks, or formulaic bot copy from existing prose route here. Those terms describe editing problems, not proof of authorship.

## Modes

### Rewrite

Return only the revised prose unless the user asks for a diff or explanation. Do not append findings, commentary, or source-check notes.

### Review-only

Report findings and minimal suggestions. Do not edit the source.

## Non-negotiable boundary

This skill is an editorial aid, not an authorship detector. Never label text as human-written or machine-written. Never imply misconduct. A finding means only that a pattern needs review in context.

Before any rewrite, read [references/rewrite-rules.md](references/rewrite-rules.md). Its meaning checklist overrides every style preference and scanner finding.

## Authorship questions

Do not classify authorship or provide a detector score. Say that wording patterns cannot prove who or what wrote a passage, then offer an editorial review instead.

## Workflow

1. Identify the requested mode: rewrite or review-only. Review-only does not authorize edits.
2. List the facts, relationships, logic, uncertainty, quantities, quotations, citations, code, URLs, identifiers, and voice that must stay intact.
3. If mechanical screening would help, run the bundled scanner on explicit files or stdin. Follow [references/optional-tools.md](references/optional-tools.md). Do not install anything.
4. Classify each observation by layer:
   - `research-signal`: seen often in published research but dependent on context; note only.
   - `house-style`: required for this private release; revise unless an exemption applies.
   - `editorial-review`: needs human judgment; never automate the rewrite.
5. Apply gates and exemptions from [references/prose-rules.md](references/prose-rules.md). A single research word is not a defect. A fixed house pattern may require a change on its first unprotected use.
6. Rewrite the smallest span that resolves a real problem. Preserve protected text byte-for-byte.
7. Check the rewrite against the meaning checklist. If style and meaning conflict, keep the original and flag it for review.
8. Compare the source and rewrite for unsupported certainty. This requires judgment and cannot be delegated to the scanner.

## Rewrite priorities

Work in this order:

1. Cut empty framing, fake emphasis, and repeated conclusions.
2. Replace vague praise with a fact already present in the source. If a closing sentence contains only unsupported praise or importance, remove the whole closing sentence. Do not soften it into a different unsupported claim.
3. Put a supported actor next to a clear verb. Do not invent an actor when the source does not name one.
4. Break repeated sentence templates and decorative lists only when they make the passage harder to read.
5. Read the result in the writer's voice. Restore any line that became flatter, safer, more formal, or less specific.

Do not trade one stock phrase for another. Replacing `delve into` with `explore`, `leverage` with `use`, or `robust` with `strong` is not an improvement unless the new word is more accurate in context.

## Review priorities

- Prefer specific actors, actions, constraints, and consequences when the source supports them.
- Remove canned framing only when the claim survives.
- Remove every unprotected em dash. Use punctuation that keeps the same logical relationship.
- Preserve useful passive voice, real triads, genuine questions, dialect, profanity, and domain terminology.
- Preserve first-person judgment and identity-bearing voice. Do not turn a speaker's view into an impersonal fact.
- Keep quotations, code, commands, paths, URLs, package names, API names, and identifiers exact.
- Do not invent people, organizations, examples, evidence, citations, or certainty.

## References

- [Research signals](references/research-signals.md): evidence, scope, and scanner coverage
- [Prose rules](references/prose-rules.md): permanent IDs, gates, exemptions, and fixtures
- [House style](references/house-style.md): local preferences kept separate from research
- [Rewrite rules](references/rewrite-rules.md): what every rewrite must preserve
- [Optional tools](references/optional-tools.md): read-only scanner interface and output contract
- [Examples](references/examples.md): safe transformations and counterexamples

## Output

For a rewrite request, return only the revised prose unless the user asks for commentary or a diff. Do not append findings, commentary, or source-check notes. For a review request, report the rule ID, excerpt, reason, and a minimal suggested change. Do not return a detector score.

## License

MIT. Adapted from Stop Slop by Hardik Pandya (https://hvpandya.com).
