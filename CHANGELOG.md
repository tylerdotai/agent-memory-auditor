# Changelog

All notable changes to Agent Memory Auditor will be documented here.

## Unreleased

- Added OpenClaw layout collection with memory, memories, agent-brain-dump, and optional skill scanning.
- Added generic markdown layout collection with repeatable `--include` and `--exclude` globs.
- Added named agent layouts: `claude-code`, `codex`, and `opencode`.
- Added TOML configuration for rename maps, allowlists, suppressions, and contradiction review.
- Added SARIF output for GitHub code scanning via `--sarif`.
- Added terminal report viewer via `memory-audit view`.
- Added offline contradiction review and external model-command review imports.
- Added safe `--suggest-patches` mode that emits `.patch` files without applying them.
- Hardened generic collection so absolute include globs and `../` escapes cannot scan outside `--home`.
- Added positive validation for `--max-file-bytes` and Python 3.10 TOML parsing support via `tomli`.
- Expanded tests across new layouts, outputs, patch safety, model-command review, path traversal protection, and Python 3.10/3.11/3.12 compatibility.

## 0.1.0 - Initial public release

- Read-only Hermes memory and skill collection
- Secret-like string redaction
- Imperative memory detection
- Stale/task-progress detection
- Near-duplicate memory detection
- Missing repo/path verification
- Naming drift detection
- Skill-candidate detection
- Markdown, HTML, and JSON reports
- Fixture-backed pytest suite
