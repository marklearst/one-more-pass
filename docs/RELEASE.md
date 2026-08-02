# Private release checklist

This checklist covers the private One More Pass 1.0.0 release. The installable files are under `plugins/one-more-pass` and contain exactly two skills: Writing and Code.

Do not publish, tag, push, or open a release until that action is approved.

## 1. Check the release files

- [ ] The two plugin manifests and the Claude Code marketplace entry use version 1.0.0. Both marketplace files register the plugin as `one-more-pass`.
- [ ] Each marketplace points to `plugins/one-more-pass`.
- [ ] The runtime directory contains only `.claude-plugin`, `.codex-plugin`, `LICENSE`, and `skills`.
- [ ] The `skills` directory contains only `writing` and `code`.
- [ ] README install commands match the current client help.
- [ ] The changelog describes the work in this release and leaves the imported Stop Slop history unchanged.
- [ ] Hardik Pandya and the original Stop Slop project remain credited.

Record the client versions used for the checks:

```bash
codex --version
claude --version
python3 --version
```

## 2. Run the local checks

Run the full test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

List and hash every file that would enter an installed copy:

```bash
python3 scripts/list-runtime-files.py
```

Validate the Claude Code marketplace and plugin manifests:

```bash
claude plugin validate . --strict
claude plugin validate plugins/one-more-pass --strict
```

Run the optional Writing scanner against the public release prose:

```bash
python3 plugins/one-more-pass/skills/writing/scripts/scan.py --fail-on never README.md CHANGELOG.md docs/RELEASE.md
```

Choose the reviewed commit or tag that precedes this release. The working tree and untracked-file list must both be empty before the final comparison:

```bash
RELEASE_BASE="<reviewed base commit or tag>"
git status --short
git ls-files --others --exclude-standard
git diff --check "$RELEASE_BASE"...HEAD
git diff --no-ext-diff --binary "$RELEASE_BASE"...HEAD |
  python3 plugins/one-more-pass/skills/code/scripts/scan.py --diff -
```

Stop if either listing reports a file. Review every change between `RELEASE_BASE` and `HEAD`. A binary patch makes the Code scan incomplete and requires another review tool.

Review every scanner match. Do not treat scanner output as proof that a defect exists, proof that a person or tool wrote the input, or approval to release.

## 3. Prove a local Codex install

Use a temporary Codex home so the test does not change the normal plugin setup:

```bash
REPO_ROOT="$(pwd)"
CODEX_TEST_HOME="$(mktemp -d)"

CODEX_HOME="$CODEX_TEST_HOME" codex plugin marketplace add "$REPO_ROOT" --json
CODEX_HOME="$CODEX_TEST_HOME" codex plugin add one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_TEST_HOME" codex plugin list --json
CODEX_HOME="$CODEX_TEST_HOME" codex plugin remove one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_TEST_HOME" codex plugin marketplace remove one-more-pass-private --json
```

Check that the installed entry reports version 1.0.0 and that its source resolves to `plugins/one-more-pass`.

## 4. Prove a local Claude Code install

Use a temporary Claude Code config directory:

```bash
REPO_ROOT="$(pwd)"
CLAUDE_TEST_HOME="$(mktemp -d)"

CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin marketplace add "$REPO_ROOT" --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin install one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin list --json
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin marketplace update one-more-pass-private
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin update one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin uninstall one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_TEST_HOME" claude plugin marketplace remove one-more-pass-private --scope user
```

Check that the installed entry reports version 1.0.0.

Run `/reload-plugins` in an open Claude Code session. Restart Claude Code if that command is unavailable or the updated plugin does not appear.

## 5. Prove private Git installation

Do this only after the release commit or tag exists in the private repository. The machine running the check must already have Git access.

Codex:

```bash
RELEASE_REF="<reviewed release tag or full commit SHA>"
CODEX_GIT_HOME="$(mktemp -d)"

CODEX_HOME="$CODEX_GIT_HOME" codex plugin marketplace add marklearst/one-more-pass --ref "$RELEASE_REF" --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin add one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin marketplace upgrade one-more-pass-private --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin remove one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin add one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin list --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin remove one-more-pass@one-more-pass-private --json
CODEX_HOME="$CODEX_GIT_HOME" codex plugin marketplace remove one-more-pass-private --json
```

Claude Code:

```bash
RELEASE_REF="<reviewed release tag or full commit SHA>"
CLAUDE_GIT_SOURCE="https://github.com/marklearst/one-more-pass.git#$RELEASE_REF"
CLAUDE_GIT_HOME="$(mktemp -d)"

CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin marketplace add "$CLAUDE_GIT_SOURCE" --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin install one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin marketplace update one-more-pass-private
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin update one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin list --json
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin uninstall one-more-pass@one-more-pass-private --scope user
CLAUDE_CONFIG_DIR="$CLAUDE_GIT_HOME" claude plugin marketplace remove one-more-pass-private --scope user
```

If either client cannot clone the private repository, fix Git authentication before continuing. Do not replace a failed Git proof with a local-path result.

## 6. Check skill behavior

Check the current client flags without contacting a model:

```bash
python3 scripts/run-behavior-case.py preflight
```

Read `tests/behavior/README.md`, then run its five-case matrix: `WRITING-PRESSURE-001`, `WRITING-PRESSURE-005`, `WRITING-PRESSURE-004`, `CODE-PRESSURE-001`, and `CODE-PRESSURE-004`. Run every case in both clients, once with `--arm baseline` and once with `--arm plugin`, for 20 fresh sessions. Keep the client version, model, prompt, input, full response, route proof, and review notes.

If a case finds a skill contract defect, keep the failed evidence, fix the contract, and rerun only that case in the affected client with a new output directory. A contract-only fix needs a fresh plugin arm. Rerun the baseline only when its prompt, input, client, model, or harness changed. Do not repeat unaffected cases.

The harness writes only to temporary client homes and the requested ignored evidence directory. It does not edit fixture results. Review `capture-template.json` against the case before copying it into a fixture.

Writing must:

- edit or review existing prose when asked;
- stay inactive for a blank-page writing request;
- preserve protected facts, quotations, code, URLs, and voice;
- refuse authorship classification while offering an editorial review.

Code must:

- review a stated change or release when asked;
- stay inactive for an implementation-only request;
- separate scanner signals from reviewer findings;
- withhold release approval when required checks have not run.

## 7. Review the final change

- [ ] Every changed release or runtime file is direct, factual, and free of unsupported praise.
- [ ] No release or runtime file contains a generated-by line, assistant credit, task link, secret, or private path.
- [ ] No command points to the old Stop Slop layout.
- [ ] Markdown links resolve from the file that contains them.
- [ ] The full diff contains only intended release work.
- [ ] Every required check has fresh output from the release candidate.
- [ ] No release action remains unapproved.
