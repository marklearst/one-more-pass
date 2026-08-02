# One More Pass

Before you publish. Before you merge. One more pass.

One More Pass is a private plugin for final reviews. It has exactly two skills:

- **Writing** edits existing prose while protecting facts, logic, uncertainty, quantities, quotations, code, URLs, identifiers, and voice.
- **Code** reviews a diff, implementation, package, pull request, or release for defects, weak proof, unsafe assumptions, and release risk.

The installable plugin lives at [`plugins/one-more-pass`](plugins/one-more-pass). The repository root holds tests, plans, release notes, and marketplace files. Those files are not copied into the installed plugin.

## Skills

### One More Pass: Writing

In Codex, use `$one-more-pass:writing`. In Claude Code, use `/one-more-pass:writing`.

Run Writing when existing prose needs a final edit or review. A rewrite returns revised prose in chat unless the user identifies a file and asks for an edit. A review returns findings without rewriting the prose. Writing does not review code behavior and does not judge who or what wrote the text.

Writing stays out of blank-page work. Start new prose with the client's normal writing support. Once text exists, use Writing for the final pass.

### One More Pass: Code

In Codex, use `$one-more-pass:code`. In Claude Code, use `/one-more-pass:code`.

Run Code for a final review of code or a release. It checks the change against the stated behavior, tests, safety rules, and release requirements. It does not implement a feature or debug an unknown failure.

When a request includes code and public prose, run Code first. Run Writing after the behavior review is complete.

## Install with Codex

The commands below use the private marketplace name `one-more-pass-private`.

### From a local checkout

Use an absolute path to the repository root:

```bash
codex plugin marketplace add /absolute/path/to/one-more-pass
codex plugin add one-more-pass@one-more-pass-private
```

After local changes, reinstall the plugin so Codex copies the current runtime:

```bash
codex plugin remove one-more-pass@one-more-pass-private
codex plugin add one-more-pass@one-more-pass-private
```

Remove the plugin and its marketplace entry:

```bash
codex plugin remove one-more-pass@one-more-pass-private
codex plugin marketplace remove one-more-pass-private
```

### From the private Git repository

Your Git setup must already have access to the private repository.

```bash
codex plugin marketplace add marklearst/one-more-pass --ref main
codex plugin add one-more-pass@one-more-pass-private
```

Refresh the Git checkout, then reinstall the plugin:

```bash
codex plugin marketplace upgrade one-more-pass-private
codex plugin remove one-more-pass@one-more-pass-private
codex plugin add one-more-pass@one-more-pass-private
```

The removal commands are the same as the local workflow.

## Install with Claude Code

These examples install the plugin for the current user. Replace `user` with `project` or `local` when that scope is a better fit.

### From a local checkout

```bash
claude plugin marketplace add /absolute/path/to/one-more-pass --scope user
claude plugin install one-more-pass@one-more-pass-private --scope user
```

After increasing the plugin version, update the marketplace and installed copy:

```bash
claude plugin marketplace update one-more-pass-private
claude plugin update one-more-pass@one-more-pass-private --scope user
```

Run `/reload-plugins` in an open Claude Code session. Restart Claude Code if that command is unavailable or the updated plugin does not appear.

For local work before a version change, load the nested plugin for one session:

```bash
claude --plugin-dir /absolute/path/to/one-more-pass/plugins/one-more-pass
```

Remove the plugin and its marketplace entry:

```bash
claude plugin uninstall one-more-pass@one-more-pass-private --scope user
claude plugin marketplace remove one-more-pass-private --scope user
```

### From the private Git repository

Your Git setup must already have access to the private repository.

```bash
claude plugin marketplace add marklearst/one-more-pass --scope user
claude plugin install one-more-pass@one-more-pass-private --scope user
```

Refresh and update the Git-backed install:

```bash
claude plugin marketplace update one-more-pass-private
claude plugin update one-more-pass@one-more-pass-private --scope user
```

Run `/reload-plugins` in an open Claude Code session. Restart Claude Code if that command is unavailable or the updated plugin does not appear.

Remove the plugin and its marketplace entry:

```bash
claude plugin uninstall one-more-pass@one-more-pass-private --scope user
claude plugin marketplace remove one-more-pass-private --scope user
```

## Optional scanners

Each skill includes a read-only Python scanner. The scanners accept named files or standard input, use the Python standard library, and do not modify source files.

From the repository root:

```bash
python3 plugins/one-more-pass/skills/writing/scripts/scan.py README.md
git diff --no-ext-diff | python3 plugins/one-more-pass/skills/code/scripts/scan.py --diff -
```

A scanner match is a signal to review, not proof of a defect or proof of authorship. A clean scan is not release approval. The skill instructions explain how to locate the same scripts inside an installed plugin.

## Test and validate

Run the full test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Check the installable file list and its package hash:

```bash
python3 scripts/list-runtime-files.py
```

Validate the Claude Code marketplace and nested plugin manifest:

```bash
claude plugin validate . --strict
claude plugin validate plugins/one-more-pass --strict
```

Codex validates the marketplace when `codex plugin marketplace add` runs. The release checklist shows how to test both clients without changing the normal client setup.

## Runtime layout

```text
plugins/one-more-pass/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── LICENSE
└── skills/
    ├── writing/
    │   ├── SKILL.md
    │   ├── agents/openai.yaml
    │   ├── references/
    │   └── scripts/scan.py
    └── code/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        └── scripts/scan.py
```

## Credits

- [Stop Slop](https://github.com/hardikpandya/stop-slop) by [Hardik Pandya](https://hvpandya.com)
- One More Pass by Mark Learst

## License

MIT. See [LICENSE](LICENSE).
