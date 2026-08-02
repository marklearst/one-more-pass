# Rewrite rules

## Meaning checklist

Write down what must stay true before changing prose. A rewrite must preserve:

1. **Facts and relationships:** every proposition, proper noun, date, comparison, source-supported example, attribution, condition, cause, contrast, sequence, and hierarchy.
2. **Negation and logic:** `not`, exclusions, exceptions, conditions, causality, contrast, list membership, and logical scope.
3. **Modality:** uncertainty and evidential strength, including `may`, `might`, `could`, `likely`, `probably`, `suggests`, and confidence levels.
4. **Quantities:** numbers, units, ranges, approximations, version boundaries, order, and required item counts.
5. **Quotations and citations:** quoted words remain verbatim and attached to their source. Never invent or silently paraphrase quotations.
6. **Code and literals:** code, commands, paths, URLs, package names, API names, keys, identifiers, and literal values remain byte-for-byte exact unless the user authorizes their modification.
7. **Voice:** preserve speaker, person, tone, dialect, profanity, point of view, first-person judgment, and identity-bearing language. Phrases such as `I think`, `I believe`, and `in my experience` identify who owns a judgment and how strongly it is stated. Do not rewrite them as impersonal facts unless the user asks for that change.
8. **Structure with meaning:** preserve enumerated requirements, sequence, headings required by a format, and deliberate rhetoric that carries the speaker's intent.

Do not add people, organizations, examples, evidence, certainty, causality, or conclusions that are absent from the source.

## Unsupported certainty

Compare the rewrite with the source. This is a model-only review because a scanner cannot decide whether evidence supports a stronger claim.

- Keep modal force. `May`, `might`, `could`, `likely`, and `probably` cannot become fact without new evidence.
- Keep attribution. `I think the patch may help` cannot become `The patch will help`.
- Keep limits. One passing test does not prove that a bug is fixed for every user.
- Keep relationships. Do not turn sequence into cause, correlation into proof, or an example into a general rule.

If a direct rewrite cannot keep these limits, restore the source and return `review required`.

## Protected spans

Treat these as immutable by default:

- Markdown fenced code and inline code
- URLs and link destinations
- file paths, commands, package names, API names, identifiers, and literal values
- direct quotations and their punctuation
- citations, footnotes, and source titles
- user-specified terminology and required templates

Markdown italics alone do not prove that a span is a title. The scanner protects an italic title only when nearby words identify it as a source, title, book, article, paper, essay, report, chapter, or work.

The scanner masks Markdown code, blockquotes, quoted spans, URLs, and locally identified source titles. Manual rewrites must protect the broader set above.

## Rewrite procedure

1. Record what must stay true in a short internal checklist.
2. Identify a rule only after its density gate and exemptions are satisfied.
3. Select the smallest editable span around the finding.
4. Draft one direct alternative. Do not revise adjacent clean prose for variety alone.
5. Compare each source claim with the rewrite.
6. Compare all protected spans byte-for-byte.
7. Check the revised prose against the strict house rules. Do not alter a protected span to clear a finding.
8. If any check fails, restore the original span and return a review flag.

## Unsupported closing claims

When a final sentence adds praise, importance, urgency, or a lesson that the source does not support, remove the whole closing sentence if the factual passage stands on its own. Do not soften the claim and keep it.

For example, a passage may end with `Here's the thing: this underscores a crucial need for transparency.` If the source only reports what two people said and gives no evidence for that conclusion, remove the sentence. Rewriting it as `This underscores the need for transparency.` keeps the same unsupported claim.

## Output contract

- For rewriting, return only revised prose unless the user requests a diff or explanation.
- For review-only work, return findings and suggestions without modifying the source.
- Do not report authorship probability, detector scores, or misconduct claims.
- Do not hide uncertainty about a rewrite. Use `review required` when meaning cannot be preserved safely.
- Do not claim that clean prose was written by a person. A clean review means only that the listed editing checks passed.

## Regression locks

The source repository keeps the ten baseline scenarios in `tests/writing/fixtures/red_cases.json`. Installed copies do not include them. At minimum:

- `The scheduler is slow because each job opens three database connections, not because of Python.` must keep both causal claims.
- `probably`, `about 12%`, `may fail`, and `older than 5.10` must keep their epistemic and numeric force.
- `“Mistakes were made.”`, inline code, and URLs must remain exact.
- `ain't`, `gonna`, `shit`, and `y'all` must remain unless normalization is requested.
- The passive storage sentence, the three required endpoint fields, the domain uses of `market`, `navigates`, and `landscape`, and the genuine `Which` question must remain valid unchanged.
