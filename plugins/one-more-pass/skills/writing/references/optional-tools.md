# Optional tools

Tools support review. They do not decide authorship or rewrite prose automatically.

## Bundled scanner

The scanner uses only the Python standard library. It reads explicit files or stdin and reports likely review points.

Resolve the scanner before running it. `scripts/scan.py` is in the same directory as this `SKILL.md`, not in the project being reviewed. Never build its path from the user's working directory.

- In Claude Code, use `${CLAUDE_PLUGIN_ROOT}/skills/writing/scripts/scan.py` when `CLAUDE_PLUGIN_ROOT` is set.
- In Codex or another client, start with the absolute path of this `SKILL.md`, then replace `SKILL.md` with `scripts/scan.py`.

Store that absolute path in `ONE_MORE_PASS_WRITING_SCANNER` for the commands below.

```text
python3 "$ONE_MORE_PASS_WRITING_SCANNER" [--format text|json]
                        [--fail-on error|warning|never]
                        [--version]
                        FILE... | -
```

Inputs must be UTF-8 file paths or one stdin marker, `-`. Directories and symlinks are rejected. The scanner does not search folders.

Limits:

- 256 explicit inputs per run
- 2 MiB per input
- 8 MiB across all inputs
- 25 reported findings for one rule
- 200 reported findings in one run

When findings exceed a report limit, the scanner reports exactly how many it left out.

Examples:

```bash
python3 "$ONE_MORE_PASS_WRITING_SCANNER" draft.md notes.txt
python3 "$ONE_MORE_PASS_WRITING_SCANNER" --format json --fail-on never draft.md
printf '%s\n' "Text to review" | python3 "$ONE_MORE_PASS_WRITING_SCANNER" -
```

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | scan completed and no finding reached the selected threshold |
| `1` | at least one finding reached the selected threshold |
| `2` | invalid arguments or unsupported input |
| `3` | internal scanner failure |

The default threshold is `warning`. Research signals are notes and house-style findings are warnings. Use `--fail-on never` for a report that always exits `0` after a valid scan.

### JSON contract

```json
{
  "version": "1.0.0",
  "schema_version": 1,
  "findings": [
    {
      "rule_id": "SLP-PHR-002",
      "category": "research-signal",
      "severity": "note",
      "confidence": "high",
      "source": "draft.md",
      "line": 4,
      "column": 1,
      "excerpt": "A rich tapestry offers valuable insights.",
      "message": "Multiple stock collocations cluster in this text; replace them only when a specific observation is available."
    }
  ],
  "summary": {
    "total": 1,
    "by_severity": {"note": 1, "warning": 0, "error": 0}
  },
  "truncated": false,
  "omitted": {
    "total": 0,
    "by_rule": {}
  }
}
```

Rule IDs and field names stay stable within schema version 1. A breaking output change requires a schema increment.

### Safety boundary

The scanner reads and reports. It has no folder search, network access, subprocess calls, source execution, file writes, or fix mode. It masks frontmatter for prose rules, plus Markdown code, link destinations, blockquotes, quoted spans, paths, selected HTML elements, and URLs. The local em-dash rule still checks visible frontmatter. Masking keeps the original offsets for line and column reporting.

## Other local tools

If a project already has a prose linter, run it in read-only mode only when the user asks or authorizes it. Record the command and version. Do not install a linter, download rule data, or treat its result as an authorship judgment. Project terms and allowlists take priority over generic defaults.
