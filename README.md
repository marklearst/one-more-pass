# Stop Slop

A skill for removing AI tells from prose.

## What this is

AI writing has patterns. Predictable phrases, structures, rhythms. Once you notice them, you see them everywhere. This skill teaches Claude (or any LLM) to avoid them.

## Skill Structure

```
stop-slop/
├── SKILL.md              # Core instructions
├── references/
│   ├── phrases.md        # Phrases to remove
│   ├── structures.md     # Structural patterns to avoid
│   └── examples.md       # Before/after transformations
├── README.md
└── LICENSE
```

## Quick start

**Claude Code:** Add this folder as a skill.

**Claude Projects:** Upload `SKILL.md` and reference files to project knowledge.

**Custom instructions:** Copy core rules from `SKILL.md`.

**API calls:** Include `SKILL.md` in your system prompt. Reference files load on demand.

## What it catches

**Banned phrases** — Throat-clearing openers, emphasis crutches, business jargon. See `references/phrases.md`.

**Structural clichés** — Binary contrasts, dramatic fragmentation, rhetorical setups. See `references/structures.md`.

**Stylistic habits** — Tripling, immediate question-answers, metronomic endings.

## Scoring

Rate 1-10 on each dimension:

| Dimension | Question |
|-----------|----------|
| Directness | Statements or announcements? |
| Rhythm | Varied or metronomic? |
| Trust | Respects reader intelligence? |
| Authenticity | Sounds human? |
| Density | Anything cuttable? |

Below 35/50: revise.

## Author

[Hardik Pandya](https://hvpandya.com)

## License

MIT. Use freely, share widely.
