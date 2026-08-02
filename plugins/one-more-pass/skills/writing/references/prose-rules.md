# Prose rule registry

Registry version `1.3.0`; schema `1`. Rule IDs are permanent. Additions receive new IDs. Retired IDs remain reserved. A `1.x` release may clarify thresholds or exemptions. Changed meaning requires a new major registry version.

`warn` means a bounded text pattern can be identified. `review` means a human must decide whether the pattern harms the passage. `P` is a positive fixture that should trigger the rule; `N` is a negative fixture that must not.

Density gates are starting heuristics. Apply exemptions before recommending a change. The meaning checklist in [rewrite-rules.md](rewrite-rules.md) overrides every rule.

`SLP-SYN-001` may still note a complete fixed construction when the contrast is literal. Keep the sentence when the distinction changes the meaning, such as `This is not a warning. It is an error.` A note requests review; it does not require a rewrite.

`SLP-CLR-002` is model-only. It requires comparing claims, evidence, attribution, and modality across the source and rewrite. The scanner does not report it.

| Permanent ID | Category | Evidence | Default | Mark overlay | Density gate | Exemptions | Rewrite instruction | Fixture |
|---|---|---:|---|---|---|---|---|---|
| `SLP-LEX-001` | focal lexemes: `delve*`, `underscore*`, `showcase*`, `intricat*` | A | warn | use density gate | ≥2 families/500 words or one family repeated | quotations, titles, identifiers, exact technical terms | Use the precise action or property | P: “The paper delves into an intricate framework.” N: “The paper compares two dosing strategies.” |
| `SLP-LEX-002` | elevated imagery: `tapestry`, `camaraderie`, `amidst`, `palpable`, `solace`, `unravel` | B | warn | use density gate | ≥2 hits/500 or one repeated | fiction, quotations, intentional developed metaphor | Name the concrete scene, relationship, or change | P: “Amidst a vibrant tapestry of ideas...” N: “During the outage, two workers restored service.” |
| `SLP-LEX-003` | abstract boosters: `crucial`, `comprehensive`, `insights`, `notably`, `particularly`, `advancement*`, `groundbreaking`, `realm`, `align*` | B | warn | use density gate | ≥3 families/500 words | terms of art, sourced claims, quotations | Substitute the measurable fact or remove the booster | P: “These crucial advancements offer comprehensive insights.” N: “The update cut median latency from 80 to 55 ms.” |
| `SLP-PHR-001` | meta-signposting | B | warn | warn first hit | one in first/last 120 words or ≥2/document | required abstracts, teaching roadmaps, mandated templates | Start with the subject or conclusion | P: “This essay will explore the issue.” N: “The migration has three risks.” |
| `SLP-PHR-002` | stock elevated collocations | C | warn | warn first hit | ≥2 phrases/750 or one repeated | quotation, brand slogan, established domain idiom | Replace with the specific observation | P: “A rich tapestry offers valuable insights.” N: “The interviews revealed two recurring concerns.” |
| `SLP-SYN-001` | negate-and-reframe pivot | A | review | review first rhetorical use | ≥2/500; scanner may note one complete fixed construction | genuine logical contrast, quotation | State propositions directly while preserving negation and scope | P: “It’s not just faster; it’s transformative.” N: “The bug affects Safari, not Chrome.” |
| `SLP-SYN-002` | decorative three-part list | B | review | review first decorative use | ≥2 rhetorical lists/250 or ≥3/document | real data, requirements, taxonomies | Keep every distinct item; combine only overlaps | P: “Clear, scalable, and powerful.” N: “The API accepts name, email, and role.” |
| `SLP-SYN-003` | packed abstraction | B | review | same | in ≥8 sentences, ≥4 participial add-ons or ≥6 nominalizations/250 words | legal, academic, or scientific precision | Restore finite verbs and supported actors one clause at a time | P: “Leveraging automation, the implementation enables optimization.” N: “The script retries failed jobs twice.” |
| `SLP-SYN-004` | staccato revelation | M | review | note one strong fixed shape | one clipped `X. And Y. And Z.` or `No X. No Y. Just Z.` sequence | dialogue, deliberate refrain | Join related claims or explain their relationship | P: “No dashboards. No meetings. Just results.” N: “The API needs speed, scale, and trust.” |
| `SLP-SYN-005` | instant question and answer | M | review | note one strong fixed shape | one question followed at once by the writer's answer | interview transcript, FAQ, real reader question | State the answer directly unless the question helps the reader | P: “Why? Because teams need proof.” N: “Which migration should we run first?” |
| `SLP-RHY-001` | uniform sentence rhythm | B | review | same | ≥4 consecutive sentences share an opener or ±20% length band; sample ≥6 | deliberate refrain, procedures, specifications | Vary rhythm only where comprehension improves | P: “We plan. We build. We test. We ship.” N: “We planned the change. After two builds, Sam shipped the smaller patch.” |
| `SLP-FMT-001` | repeated presentation shape | B | review | review decorative use | ≥3 consecutive bold-label bullets or mechanically equal sections | API references, forms, glossaries, changelogs, scan-oriented lists | Use hierarchy only when it represents real structure | P: “**Speed:** Fast. **Scale:** Easy. **Value:** Clear.” N: “Prerequisites / Steps / Failure modes.” |
| `SLP-DOC-001` | generic opener | B | warn | warn first occurrence | first 120 words contain a stock scene but no concrete subject, event, or claim | required background, fiction, intentional rhetoric | Open with the actor, event, constraint, or result | P: “In today’s rapidly evolving digital landscape...” N: “On July 18, the importer dropped 43 rows.” |
| `SLP-DOC-002` | redundant optimistic close | B | review | review generic uplift | final 120 words repeat ≥2 claims plus generic future language | required executive summaries, compliance recaps | End with the consequence, decision, or next action | P: “In conclusion, this paves the way for a brighter future.” N: “Next, migrate the remaining 12 accounts.” |
| `SLP-SRC-001` | quotation integrity | B | review | same | review every attributed quotation lacking a supplied source | labeled fiction; user-supplied quote with known source | Keep verified words exact; otherwise flag unsupported attribution | P: `The CEO said, “This changes everything.”` with no source. N: `Transcript p. 4: Lee said, “We paused the rollout.”` |
| `SLP-CLR-001` | unsupported praise or importance claim | B+M | review | warn first hit | ≥2 unsupported claims/500 | marked opinion, sourced evaluation | State the mechanism, consequence, or evidence | P: “This is crucial and has profound implications.” N: “If retries fail, invoices remain unpaid.” |
| `SLP-CLR-002` | unsupported certainty or strengthened claim | M | review | same | one unsupported absolute or one source-to-rewrite increase in certainty | direct quotation, cited result, supplied evidence | Match the source's uncertainty, attribution, and evidence limits | P: source says “may reduce failures”; rewrite says “prevents failures.” N: source and rewrite both say “may reduce failures.” |
| `SLP-ACT-001` | hidden actor | C+M | review | warn first accountability-relevant hit | ≥2 cases/500 where a known actor is hidden | actor unknown or irrelevant; conventional technical actors | Name only a supported actor, or state that the actor is unknown | P: “A decision was made to remove access.” N: “The samples were stored at −80 °C.” |
| `SLP-ENG-001` | canned hook | M | review | warn each strong fixed hook | one strong hook | dialogue, requested campaign voice | Replace with a specific claim or genuine question | P: “Let that sink in.” N: “Which constraint should we relax first?” |
| `SLP-ENG-002` | social engagement prompt | M | review | warn each fixed prompt | one request for likes, comments, reposts, shares, saves, follows, tags, or lead-magnet messages | a requested call to action | Give the reader a useful next step | P: “Like this if you agree.” N: “Run the migration after the backup finishes.” |
| `SLP-HSE-001` | em dash | M | off | warn every unprotected occurrence | one literal or HTML-encoded occurrence | quotations, code, paths, identifiers, source titles | Choose punctuation that keeps the same logical relation | P: `The patch shipped[em dash]latency fell.` N: a quoted source title containing the same mark. |
| `SLP-HSE-002` | stale business and tech filler | M | off | warn | ≥2 families/250 words | exact domain terms, quotations, identifiers | Name the rule, object, action, constraint, or result | P: “A robust substrate unlocks seamless workflows.” N: “The deterministic finite automaton accepts three states.” |
| `SLP-HSE-003` | empty frame | M | review | warn each strong fixed frame | one fixed frame | dialogue, deliberate speaker voice | Remove the frame and state the claim | P: “The bottom line: the importer dropped 43 rows.” N: “The importer dropped 43 rows.” |

## Explicit reject list

Do not add these as general rules:

- Ban all adverbs or every `-ly` word.
- Ban passive voice or require a human subject in every sentence.
- Treat the local no-em-dash preference as a universal definition of good writing. It belongs only to [house-style.md](house-style.md).
- Ban all three-item lists, fragments, rhetorical questions, `Wh-` openings, parentheses, headings, bold text, first person, or second person.
- Remove all hedges, qualifiers, modal verbs, negation, or contrast.
- Fail a passage for one watched word or a fixed vocabulary score.
- Treat formality, polish, regular grammar, lexical richness, sentence variance, or detector consensus as proof of authorship.
- Rewrite quotations, code, identifiers, URLs, quantities, or citations to satisfy style.
