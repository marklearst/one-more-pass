# House style

These rules apply to this private release. They are editing choices, not claims about who wrote the text. Quoted material, code, paths, identifiers, source titles, and required formats stay unchanged.

## `SLP-HSE-001`: em dash

- Warn on every em dash outside protected text.
- Treat literal em dashes, named HTML entities, numeric HTML entities, and page frontmatter as visible uses.
- Leave verbatim quotations, code, paths, identifiers, and source titles alone.
- Replace it with a comma, colon, parentheses, or a new sentence only when the relationship between the clauses stays the same.

## `SLP-ENG-001`: canned hook

- Warn on each strong canned hook, even when it appears once.
- Examples include `Here's the thing`, `Here is the thing`, `Let that sink in`, ellipsis-heavy forms of that hook, `Make no mistake`, a standalone `Stop scrolling`, `Nobody is talking about this`, `Nobody's talking about this`, `Hot take`, a standalone `Read that again`, and a standalone `Thoughts?`.
- Do not flag ordinary instructions such as `Stop scrolling when the footer appears` or `Read that again before you approve the contract`.
- Dialogue and a campaign voice requested by the user may keep them.
- Start with the fact or ask the real question.

## `SLP-ENG-002`: social engagement prompt

- Warn on each social request such as a standalone `Agree?`, `Agree or disagree?`, `Like this if you agree`, `Comment below`, `Drop your thoughts below`, `Repost this`, `Repost if you agree`, `Share this if you agree`, `Save it for later`, `Send this to someone who needs this`, `Send this to someone who needs to hear it`, `Let me know what you think in the comments`, `Bookmark this`, `Tag someone who needs this`, `Follow for more`, or a giveaway tied to a direct-message keyword.
- Do not flag ordinary work instructions such as commenting below a line in a diff, reposting an incident update, bookmarking a function, sharing a file with legal, saving a document, tagging an incident owner, or checking whether totals agree.
- A call to action requested by the user may keep the action, but the wording still needs review.
- Replace requests for platform activity with a useful next step for the reader.

## `SLP-HSE-002`: stale business and tech filler

- Warn when two or more watched families occur within 250 words.
- Watched terms include `canonical`, `deterministic`, `surface`, `substrate`, `agency`, `slice`, `align`, `leverage`, `unlock`, `robust`, `seamless`, `empower`, `elevate`, `transformative`, `revolutionary`, `game-changing`, `unpack`, `lean into`, `double down`, `deep dive`, `take a step back`, `moving forward`, `circle back`, and `on the same page`.
- Do not flag exact technical uses such as `robust regression`, `deterministic algorithm`, `deterministic finite automaton`, `canonical URL`, `array slice`, `geometric surface`, a `canonical surface` in a named field of geometry, `financial leverage`, or `legal agency`.
- Other precise uses include singular and plural forms of `canonical schema`, `canonical correlation`, `canonical syntax`, `deterministic ordering`, `deterministic parser`, and `robust estimator`.
- Name the rule, object, action, constraint, or measured result. A softer synonym is not a fix.

## `SLP-HSE-003`: empty frame

- Warn on frames such as `The uncomfortable truth`, `It turns out`, `Let me be clear`, `The truth is`, `The real issue is`, `Here's why`, `The bottom line:`, `The bottom line is`, and `Can we talk about`.
- Keep one only when it carries the speaker's voice or prepares the reader for a needed shift.
- Otherwise, remove the frame and state the claim.

## Writing choices

- Start with a concrete actor, event, behavior, constraint, or result when the source supplies one.
- Use calm, plain, direct language.
- Let specific behavior prove the point. Do not add praise or importance claims that the source cannot support.
- Do not invent a team, company, experience, quotation, source, or metric.
- Do not add generated-by lines, co-author trailers, task links, or tool-focused names to public or version-controlled prose.

These rules never override the meaning checklist. If a change alters scope, emphasis, logic, or voice, keep the source and request review.
