# Research signals

## Scope

Research signals identify patterns worth reviewing. They do not establish who wrote a passage, whether a tool was used, or whether prose is good or bad. Vocabulary and syntax vary by model, date, genre, discipline, speaker, and prompt.

Evidence levels used by the registry:

- `A`: convergent peer-reviewed evidence across more than one study or corpus
- `B`: peer-reviewed evidence from one scoped study or corpus
- `C`: preliminary, preprint, or practitioner evidence
- `M`: local editorial preference, not a general research claim

Scanner thresholds are conservative engineering defaults. They are not cutoffs reported by the studies.

## Evidence base

- [Juzek and Ward (COLING 2025)](https://aclanthology.org/2025.coling-main.426.pdf) compared PubMed vocabulary trends with ChatGPT rewrites. Words including forms of `delve`, `showcase`, `underscore`, and `intricate` rose sharply, but the profile changed across models.
- [Kobak et al. (Science Advances 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12219543/) measured excess vocabulary in biomedical abstracts. Its scientific scope does not justify universal word bans.
- [Reinhart et al. (PNAS 2025)](https://doi.org/10.1073/pnas.2422455122) found cross-genre differences in vocabulary and constructions, including participial clauses and nominalizations. Genre and instruction tuning materially changed the profile.
- [Jiang and Hyland (Applied Linguistics 2025)](https://doi.org/10.1093/applin/amae052) found excess essay signposting and noun-heavy bundles in a scoped argumentative-essay comparison.
- [Russell et al. (ACL 2025)](https://aclanthology.org/2025.acl-long.267.pdf) recorded reader observations about vocabulary, sentence structure, formatting, quotations, introductions, and conclusions. The authors explicitly limited generalization beyond their nonfiction sample.
- [Schmalz and Tack (BEA 2025)](https://aclanthology.org/2025.bea-1.71.pdf) found that a fixed marketing vocabulary list performed poorly as a detector, especially across model families.
- [Liang et al. (Patterns 2023)](https://doi.org/10.1016/j.patter.2023.100779) documented high false-positive rates for human TOEFL essays. Authorship and misconduct judgments are outside this skill's scope.

## Mechanically scanned subset

The scanner implements only patterns with an observable, conservative gate:

| Rule ID | Signal | Gate | Layer |
|---|---|---|---|
| `SLP-LEX-001` | focal lexeme families | at least two distinct families | research note |
| `SLP-LEX-002` | elevated-image families | at least two distinct families | research note |
| `SLP-LEX-003` | abstract-booster families | at least three distinct families | research note |
| `SLP-PHR-001` | meta-signposting | one phrase in the first or last 120 words, or a repeated family | research note |
| `SLP-PHR-002` | stock collocations | at least two distinct phrases | research note |
| `SLP-SYN-001` | fixed negate-and-reframe construction | one complete construction | research note |
| `SLP-SYN-004` | clipped three-beat sequence | one fixed `X. And Y. And Z.` or `No X. No Y. Just Z.` sequence | research note |
| `SLP-SYN-005` | immediate question and answer | one fixed question-and-answer turn | research note |
| `SLP-ENG-001` | canned hook | one strong fixed hook | house warning |
| `SLP-ENG-002` | social engagement prompt | one fixed request for platform activity | house warning |
| `SLP-HSE-001` | em dash | one outside protected text | house warning |
| `SLP-HSE-002` | local filler families | at least two distinct families | house warning |
| `SLP-HSE-003` | empty frame | one strong fixed frame | house warning |

The remaining registry rules require judgment about meaning or the full document and stay manual.

## Rejected detector logic

Do not compute or report authorship probability from watched words, perplexity, burstiness, grammar quality, formality, sentence-length variance, lexical richness, passive frequency, punctuation, typos, or agreement among detectors. Do not treat a single word as a finding. Do not infer anything from non-native English features.
