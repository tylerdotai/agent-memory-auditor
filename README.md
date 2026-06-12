# Agent Memory Auditor

<p align="center">
  <strong>Find stale, risky, contradictory, and bloated AI-agent memory before it becomes hidden prompt injection.</strong>
</p>

<p align="center">
  <a href="https://github.com/tylerdotai/agent-memory-auditor/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/tylerdotai/agent-memory-auditor/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange">
</p>

---

## Why this exists

AI agents are starting to keep durable memory: user preferences, project conventions, tool quirks, decisions, and reusable skills. That is useful right up until the memory rots.

Bad memory is not harmless. It gets injected back into future agent context and quietly steers behavior.

Agent Memory Auditor is a read-only static analyzer for persistent AI-agent context. It scans Hermes Agent memory and skills for things that should not live there anymore:

- stale task progress
- dangerous imperative memories
- secret-shaped strings
- duplicate or near-duplicate entries
- renamed projects and old aliases
- missing repo/path references
- procedures that should be skills instead of memory

It does not edit anything. It produces reports you can review.

## What it catches

```text
HIGH · secret-like
Line contains credential-shaped material.
Suggested action: remove or rotate the secret if real.

MEDIUM · imperative-memory
"Always run npm in ClawPlex before replying."
Reason: memory should store durable facts, not hidden standing orders.

MEDIUM · naming-drift
"Agent Poster repo is /home/tyler/twit-auto."
Reason: uses old name `twit-auto`; known replacement is `agent-poster`.

LOW · skill-candidate
"To debug Hermes gateway, run..."
Reason: reusable procedure belongs in a skill, not durable memory.
```

## Install

### With uv

```bash
git clone https://github.com/tylerdotai/agent-memory-auditor.git
cd agent-memory-auditor
uv sync --extra dev
uv run memory-audit --help
```

### Editable pip install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
memory-audit --help
```

## Quick start

Scan the default Hermes profile:

```bash
memory-audit scan --include-skills
```

Scan an OpenClaw memory layout:

```bash
memory-audit scan --layout openclaw --home ~/.openclaw --include-skills
```

Scan arbitrary markdown with generic include/exclude globs:

```bash
memory-audit scan --layout generic --include "**/*.md" --exclude "sessions/**" --exclude "logs/**"
```

Scan common agent layouts:

```bash
memory-audit scan --layout claude-code --home ~/.claude
memory-audit scan --layout codex --home ~/.codex
memory-audit scan --layout opencode --home ~/.opencode
```

Write reports somewhere specific:

```bash
memory-audit scan --include-skills --output-dir reports
```

Scan a non-default Hermes profile:

```bash
memory-audit scan --profile work --include-skills
```

Fail CI on any finding:

```bash
memory-audit scan --strict
```

Write SARIF for GitHub code scanning:

```bash
memory-audit scan --include-skills --sarif --output-dir reports
```

Render the terminal report viewer:

```bash
memory-audit view --include-skills
```

Emit review-only patch files without applying them:

```bash
memory-audit scan --suggest-patches --output-dir reports
```

Run a model-assisted contradiction review through an external command:

```bash
memory-audit scan --model-command "python reviewer.py"
```

## Configuration

Pass a TOML config with `--config memory-audit.toml`:

```toml
[renames]
oldbrand = "newbrand"
twit-auto = "agent-poster"

[[allowlist]]
category = "naming-drift"
path = "legacy-note.md"

[[suppressions]]
category = "imperative-memory"
pattern = "Always test fixture"
reason = "fixture noise"

[contradiction_review]
enabled = true
```

## Output

Every scan writes three files by default, plus optional SARIF and patch suggestions when requested:

```text
reports/memory-audit.md
reports/memory-audit.html
reports/memory-audit.json
reports/memory-audit.sarif        # with --sarif
reports/patches/*.patch          # with --suggest-patches
```

Each finding includes:

- severity
- category
- file path
- line number when available
- redacted snippet
- reason
- suggested action

## Scanner categories

### `secret-like`

Detects credential-shaped material, including GitHub tokens, bearer tokens, Slack-style tokens, private key headers, and common `api_key/token/secret/password` assignments.

Findings are redacted before reports are written.

### `imperative-memory`

Flags memory that reads like a standing instruction:

```text
Always...
Never...
Must...
Do not...
Ask before...
```

Durable memory should be declarative facts. Procedures belong in skills. Policy belongs in explicit config or system instructions.

### `stale-task-progress`

Flags temporary state that usually should not survive as durable memory:

```text
today
yesterday
this week
PR #123
issue #45
phase 2 complete
fixed/submitted/opened/closed
commit-like hashes
```

### `duplicate-memory`

Finds near-duplicate memory lines so the same instruction or fact does not bloat future context repeatedly.

### `repo-path-missing`

Extracts local absolute paths and checks whether they still exist.

### `naming-drift`

Flags old project names and aliases using a small rename map. The initial map includes common Agent Poster rename drift such as `twit-auto` → `agent-poster`.

### `skill-candidate`

Finds procedural memory that looks like it should become a reusable `SKILL.md`.

### `possible-contradiction` / `model-contradiction`

`--contradiction-review` enables a conservative offline second pass for simple declarative facts that share a subject but disagree on the value. `--model-command` runs an external model/reviewer command with JSON stdin and imports its JSON findings as `model-contradiction` results.

## Safety model

Agent Memory Auditor is intentionally boring.

- Read-only by default
- Safe patch suggestions are emitted as `.patch` files only; source files are not modified
- No `.env` scanning
- No session/log scraping
- No network calls during scan
- Does not follow symlinks outside the selected Hermes home
- Caps large file reads
- Redacts secret-shaped strings before writing reports

That is the point. The auditor should not become another agent making unreviewed changes to agent memory.

## Development

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run python -m build
```

Run against fixtures:

```bash
uv run memory-audit scan --home tests/fixtures/hermes --include-skills --output-dir reports/fixture
```

Run against your real Hermes memory:

```bash
uv run memory-audit scan --include-skills --output-dir reports/local
```

## Project layout

```text
agent-memory-auditor/
├── src/memory_auditor/
│   ├── cli.py
│   ├── collectors.py
│   ├── config.py
│   ├── models.py
│   ├── model_review.py
│   ├── patches.py
│   ├── report.py
│   └── scanners/
│       └── registry.py
├── tests/
│   ├── fixtures/
│   ├── test_reports_and_cli.py
│   ├── test_roadmap_features.py
│   └── test_scanners.py
├── .github/workflows/ci.yml
├── CHANGELOG.md
├── LICENSE
├── README.md
└── pyproject.toml
```

## Implemented extended features

- OpenClaw memory layout collector via `--layout openclaw`
- Generic markdown collector via repeatable `--include` and `--exclude` globs
- Named agent collectors via `--layout claude-code`, `--layout codex`, and `--layout opencode`
- Configurable rename map via `[renames]`
- Configurable allowlist / suppressions via TOML rule blocks
- SARIF output for GitHub code scanning via `--sarif`
- Terminal report viewer via `memory-audit view`
- Optional contradiction review via `--contradiction-review` and external model command import via `--model-command`
- Safe `--suggest-patches` mode that emits patch files without applying them

## Philosophy

Persistent memory is powerful because it compounds. It is dangerous for the same reason.

Treat memory like code:

- lint it
- test it
- review it
- delete what rots
- move procedures into reusable modules
- keep secrets out of it

## License

MIT
