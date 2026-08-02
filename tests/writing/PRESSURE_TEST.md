# Rewrite pressure test

This record moved with the Writing tests so installed plugin copies contain only runtime files.

Date: 2026-08-02

A reviewer read the skill and its required references, drafted a response for each case in `fixtures/red_cases.json`, then checked the response against the preserved and removed text listed in the fixture.

A fully blind test was not possible because the required references include some of the examples. The reviewer did not read the fixture's `preserve`, `remove`, or `rewrite` fields until after drafting.

Result: 10 of 10 saved fixture cases passed.

- The two formulaic passages were rewritten.
- The eight clean passages were left alone.
- Facts, negation, uncertainty, quantities, quotations, code, URLs, voice, dialect, profanity, required fields, domain terms, and genuine questions stayed intact.
- No authorship claim or detector score was produced.

## Forward review

A second reviewer ran a separate 12-case set. All 12 passed. The final two cases added risks that were not named in the saved fixture report.

### Logical contrast stays intact

Expected result: no change.

```text
Safari, not Chrome, drops the cookie. The bug appears only on iOS 18.4 and later, and we have reproduced it on 2 of 7 test devices.
```

The review kept Safari as the affected browser, Chrome as the exclusion, the scope of `only`, the iOS version, and the `2 of 7` count.

### Quotations keep their source and limits

Original:

```text
Dr. Lee said, “We did not find evidence that the patch caused the outage,” but the draft report says the outage “may have started between 03:10 and 03:25 UTC.” Here’s the thing: this underscores a crucial need for transparency.
```

Expected rewrite:

```text
Dr. Lee said, “We did not find evidence that the patch caused the outage,” but the draft report says the outage “may have started between 03:10 and 03:25 UTC.”
```

The review kept both quotations exact and attached each one to its stated source. It kept the negation, `may`, the time range, UTC, and the contrast. It removed only the canned close and its unsupported claim. Publication still requires a source check because no citation was supplied.
