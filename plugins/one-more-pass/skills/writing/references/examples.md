# Safe rewrite examples

## Remove framing, preserve negation

Before:

> Here's the thing: the scheduler isn't slow because of Python. It's slow because each job opens three database connections. Let that sink in.

After:

> The scheduler is slow because each job opens three database connections, not because of Python.

The rewrite removes two canned hooks but keeps both causal propositions.

## Preserve uncertainty and quantities

Leave this unchanged unless surrounding prose needs work:

> The patch will probably reduce median latency by about 12%, but it may fail on kernels older than 5.10.

Deleting `probably`, `about`, or `may` would strengthen the claim. Changing `12%` or `5.10` would change its facts.

## Preserve quotations and literals

Before and after:

> The hearing transcript says, “Mistakes were made.” Run `tool --mode=deep-dive --retry=3`; see https://docs.example.com/really/landscape.

Do not invent an actor for the quoted passive. Keep the quotation, inline code, and URL exact.

## Preserve voice

Before and after:

> I ain't gonna pretend this shit worked; y'all saw it crash twice.

The dialect, profanity, first-person stance, and count belong to the speaker.

## Preserve first-person judgment and identity-bearing voice

Before and after:

> I'm Deaf, and I think the captions read too fast.

`I'm Deaf` identifies the speaker. `I think` marks the sentence as that speaker's judgment. Do not rewrite it as an impersonal fact.

## Legitimate passive voice

Before and after:

> The samples were stored at −80 °C before analysis.

The actor is irrelevant and absent from the source. Adding “the researchers” would invent a fact.

## Meaning-bearing list

Before and after:

> The endpoint requires account_id, region, and checksum.

All three identifiers are contract requirements. Do not shorten the list for rhythm.

## Domain terminology and a genuine question

Before and after:

> The prediction market rewards accurate forecasts; the browser navigates to the results in landscape orientation. Which migration should we run first?

`market rewards`, `navigates`, and `landscape` have precise domain senses. The `Which` question asks for information.

## Remove a dense formula without dropping content

Before:

> Here's the thing: modern teams need to move fast. It's not just about speed; it's about clarity. Clear plans, crisp feedback, confident execution. Let that sink in.

After:

> Modern teams need to move fast, but speed alone is not enough. They also need clarity: clear plans, crisp feedback, and confident execution.

The rewrite removes framing, keeps the contrast between speed and clarity, and retains the three parts of clarity. It does not flatten them into unrelated peers.

## Remove a social prompt

Before:

> The importer now rejects stale rows. Agree? Comment below and repost this.

After:

> The importer now rejects stale rows.

The rewrite removes the requests for platform activity and keeps the stated product behavior. It does not invent a next step.

## Remove an empty frame

Before:

> It turns out the importer dropped 43 rows on July 18.

After:

> The importer dropped 43 rows on July 18.

The date, count, actor, and event stay the same. Only the empty lead-in is removed.

## Keep real contrast

Before and after:

> Safari, not Chrome, drops the cookie.

The negation identifies which browser fails. Removing it would change the claim.

## Remove an unsupported close without changing the quotations

Before:

> Dr. Lee said, “We did not find evidence that the patch caused the outage,” but the draft report says the outage “may have started between 03:10 and 03:25 UTC.” Here's the thing: this underscores a crucial need for transparency.

After:

> Dr. Lee said, “We did not find evidence that the patch caused the outage,” but the draft report says the outage “may have started between 03:10 and 03:25 UTC.”

The rewrite keeps both quotations, their sources, the negation, the uncertainty, and the time range. It removes the canned close and the importance claim because the source does not support either one.
