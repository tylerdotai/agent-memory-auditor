import json

from memory_auditor.cli import run
from memory_auditor.collectors import collect_documents, collect_openclaw_documents
from memory_auditor.config import AuditConfig, load_config
from memory_auditor.models import AuditContext, Finding
from memory_auditor.patches import write_patch_suggestions
from memory_auditor.scanners.registry import run_scanners


def test_openclaw_collector_reads_memory_and_brain_dump_layout(tmp_path):
    root = tmp_path / ".openclaw"
    (root / "memory").mkdir(parents=True)
    (root / "workspace" / "skills" / "alpha").mkdir(parents=True)
    (root / "memory" / "USER.md").write_text("Always stale\n", encoding="utf-8")
    (root / "workspace" / "skills" / "alpha" / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (root / "workspace" / "sessions").mkdir(parents=True)
    (root / "workspace" / "sessions" / "log.md").write_text("do not read me", encoding="utf-8")

    docs = collect_openclaw_documents(root, include_skills=True)

    assert {doc.kind for doc in docs} == {"memory", "skill"}
    assert {doc.path.name for doc in docs} == {"USER.md", "SKILL.md"}


def test_collect_documents_dispatches_openclaw_layout(tmp_path):
    root = tmp_path / ".openclaw"
    (root / "memory").mkdir(parents=True)
    (root / "memory" / "memory.md").write_text("hello", encoding="utf-8")

    docs = collect_documents(root, layout="openclaw")

    assert len(docs) == 1
    assert docs[0].path.name == "memory.md"


def test_generic_layout_honors_include_and_exclude_globs(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "memory.md").write_text("Always keep this\n", encoding="utf-8")
    (tmp_path / "sessions" / "session.md").write_text("Always skip session\n", encoding="utf-8")
    (tmp_path / "logs" / "log.md").write_text("Always skip log\n", encoding="utf-8")
    (tmp_path / "docs" / "note.txt").write_text("Always skip txt\n", encoding="utf-8")

    docs = collect_documents(
        tmp_path,
        layout="generic",
        includes=["**/*.md"],
        excludes=["sessions/**", "logs/**"],
    )

    assert [doc.path.relative_to(tmp_path).as_posix() for doc in docs] == ["docs/memory.md"]


def test_generic_layout_rejects_include_globs_that_escape_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Always outside\n", encoding="utf-8")

    docs = collect_documents(home, layout="generic", includes=["../*.md"])

    assert docs == []


def test_generic_layout_escape_with_excludes_does_not_crash(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Always outside\n", encoding="utf-8")

    docs = collect_documents(home, layout="generic", includes=["../*.md"], excludes=["sessions/**"])

    assert docs == []


def test_max_file_bytes_is_honored_by_collectors(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "memory.md").write_text("0123456789", encoding="utf-8")

    docs = collect_documents(home, layout="generic", includes=["*.md"], max_file_bytes=4)

    assert docs[0].text == "0123"


def test_max_file_bytes_rejects_non_positive_values(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "memory.md").write_text("0123456789", encoding="utf-8")

    try:
        collect_documents(home, layout="generic", includes=["*.md"], max_file_bytes=0)
    except ValueError as exc:
        assert "max_file_bytes" in str(exc)
    else:
        raise AssertionError("expected max_file_bytes validation failure")


def test_generic_layout_ignores_absolute_include_globs(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Always outside\n", encoding="utf-8")

    docs = collect_documents(home, layout="generic", includes=[str(outside)])

    assert docs == []


def test_named_agent_layouts_collect_known_memory_files(tmp_path):
    cases = {
        "claude-code": ["CLAUDE.md", "commands/review.md"],
        "codex": ["AGENTS.md", "prompts/build.md"],
        "opencode": ["AGENTS.md", "context/system.md"],
    }
    for layout, files in cases.items():
        root = tmp_path / layout
        for rel in files:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"Always scan {layout}\n", encoding="utf-8")

        docs = collect_documents(root, layout=layout)

        assert {doc.path.relative_to(root).as_posix() for doc in docs} == set(files)


def test_cli_accepts_generic_include_exclude_and_named_agent_layouts(tmp_path):
    generic = tmp_path / "generic"
    (generic / "sessions").mkdir(parents=True)
    (generic / "memory").mkdir()
    (generic / "memory" / "memory.md").write_text("Always generic\n", encoding="utf-8")
    (generic / "sessions" / "skip.md").write_text("Always skip\n", encoding="utf-8")

    code = run([
        "scan",
        "--layout",
        "generic",
        "--home",
        str(generic),
        "--include",
        "**/*.md",
        "--exclude",
        "sessions/**",
        "--output-dir",
        str(tmp_path / "generic-reports"),
    ])
    assert code == 0

    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "CLAUDE.md").write_text("Always claude\n", encoding="utf-8")
    code = run([
        "scan",
        "--layout",
        "claude-code",
        "--home",
        str(claude),
        "--output-dir",
        str(tmp_path / "claude-reports"),
    ])
    assert code == 0


def test_patch_suggestions_skip_historical_rename_context(tmp_path):
    memory = tmp_path / "memory.md"
    memory.write_text(
        "Agent Poster was renamed from twit-auto in 2026.\nUse twit-auto command here.\n",
        encoding="utf-8",
    )
    findings = [
        Finding(
            severity="medium",
            category="naming-drift",
            path=str(memory),
            line=1,
            snippet="Agent Poster was renamed from twit-auto in 2026.",
            reason="Uses old name `twit-auto`; known replacement is `agent-poster`.",
            suggested_action="Replace `twit-auto` with `agent-poster` if the entry is still worth keeping.",
        ),
        Finding(
            severity="medium",
            category="naming-drift",
            path=str(memory),
            line=2,
            snippet="Use twit-auto command here.",
            reason="Uses old name `twit-auto`; known replacement is `agent-poster`.",
            suggested_action="Replace `twit-auto` with `agent-poster` if the entry is still worth keeping.",
        ),
    ]

    patches = write_patch_suggestions(findings, tmp_path / "reports")

    assert len(patches) == 1
    patch_text = patches[0].read_text(encoding="utf-8")
    assert "renamed from twit-auto" in patch_text
    assert "renamed from agent-poster" not in patch_text
    assert "Use agent-poster command here." in patch_text


def test_configurable_rename_map_allowlist_and_suppressions(tmp_path):
    config_path = tmp_path / "memory-audit.toml"
    config_path.write_text(
        """
[renames]
oldbrand = "newbrand"

[[allowlist]]
category = "naming-drift"
path = "allowed.md"

[[suppressions]]
category = "imperative-memory"
pattern = "Always test fixture"
reason = "fixture noise"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.renames == {"oldbrand": "newbrand"}

    allowed = tmp_path / "allowed.md"
    blocked = tmp_path / "blocked.md"
    suppressed = tmp_path / "suppressed.md"
    allowed.write_text("oldbrand\n", encoding="utf-8")
    blocked.write_text("oldbrand\n", encoding="utf-8")
    suppressed.write_text("Always test fixture\n", encoding="utf-8")

    docs = collect_documents(tmp_path, layout="hermes")
    ctx = AuditContext(root=tmp_path, known_renames=config.renames, config=config)
    findings = run_scanners(docs, ctx)

    assert any(f.category == "naming-drift" and f.path.endswith("blocked.md") for f in findings)
    assert not any(f.category == "naming-drift" and f.path.endswith("allowed.md") for f in findings)
    assert not any(f.category == "imperative-memory" and f.path.endswith("suppressed.md") for f in findings)


def test_cli_writes_sarif_and_patch_suggestions(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "memory.md").write_text("Use twit-auto here\nAlways do that\n", encoding="utf-8")
    output = tmp_path / "reports"

    code = run([
        "scan",
        "--home",
        str(home),
        "--output-dir",
        str(output),
        "--sarif",
        "--suggest-patches",
        "--strict",
    ])

    assert code == 1
    sarif = json.loads((output / "memory-audit.sarif").read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"]
    patch_files = sorted((output / "patches").glob("*.patch"))
    assert patch_files
    patch_text = patch_files[0].read_text(encoding="utf-8")
    assert "twit-auto" in patch_text
    assert "agent-poster" in patch_text
    assert (home / "memory.md").read_text(encoding="utf-8") == "Use twit-auto here\nAlways do that\n"


def test_cli_tui_renders_readable_terminal_report(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    (home / "memory.md").write_text("Always do that\n", encoding="utf-8")

    code = run(["view", "--home", str(home), "--no-color"])

    assert code == 0
    captured = capsys.readouterr().out
    assert "Agent Memory Audit" in captured
    assert "imperative-memory" in captured
    assert "Always do that" in captured


def test_optional_contradiction_review_adds_second_pass_findings(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "memory.md").write_text(
        "Agent Poster default mode is dry-run.\nAgent Poster default mode is live posting.\n",
        encoding="utf-8",
    )

    docs = collect_documents(home, layout="hermes")
    ctx = AuditContext(root=home, config=AuditConfig(contradiction_review=True))
    findings = run_scanners(docs, ctx)

    assert any(f.category == "possible-contradiction" for f in findings)


def test_model_assisted_contradiction_review_uses_external_command(tmp_path):
    home = tmp_path / "home"
    output = tmp_path / "reports"
    model = tmp_path / "fake_model.py"
    home.mkdir()
    (home / "memory.md").write_text("one\ntwo\n", encoding="utf-8")
    model.write_text(
        """
import json, sys
payload = json.load(sys.stdin)
print(json.dumps([{
    "path": payload["documents"][0]["path"],
    "line": 1,
    "snippet": "one",
    "reason": "model saw conflicting fact",
    "suggested_action": "review model finding"
}]))
""".strip(),
        encoding="utf-8",
    )

    code = run([
        "scan",
        "--home",
        str(home),
        "--output-dir",
        str(output),
        "--model-command",
        f"python {model}",
    ])

    assert code == 0
    data = json.loads((output / "memory-audit.json").read_text(encoding="utf-8"))
    assert any(f["category"] == "model-contradiction" for f in data["findings"])
