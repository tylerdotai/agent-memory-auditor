from __future__ import annotations

import fnmatch
from pathlib import Path

from .models import Document

MEMORY_NAMES = {"MEMORY.md", "USER.md", "memory.md", "user.md"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "sessions", "logs", "auth"}
OPENCLAW_MEMORY_DIRS = ("memory", "memories", "agent-brain-dump")
OPENCLAW_SKILL_DIRS = ("skills", "workspace/skills")
NAMED_LAYOUTS = {
    "claude-code": {
        "includes": ["CLAUDE.md", "commands/**/*.md", "memory/**/*.md", "memories/**/*.md"],
        "skill_includes": ["skills/**/SKILL.md"],
    },
    "codex": {
        "includes": ["AGENTS.md", "prompts/**/*.md", "memory/**/*.md", "memories/**/*.md"],
        "skill_includes": [],
    },
    "opencode": {
        "includes": ["AGENTS.md", "context/**/*.md", "memory/**/*.md", "memories/**/*.md"],
        "skill_includes": ["skills/**/SKILL.md"],
    },
}


def _safe_read(path: Path, max_bytes: int = 250_000) -> str:
    if max_bytes <= 0:
        raise ValueError("max_file_bytes must be greater than 0")
    try:
        if path.is_symlink():
            return ""
        if path.stat().st_size > max_bytes:
            return path.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_excluded(path: Path, home: Path, excludes: list[str] | None = None) -> bool:
    if not _under(path, home):
        return True
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if not excludes:
        return False
    rel = path.resolve().relative_to(home.resolve()).as_posix()
    return any(fnmatch.fnmatch(rel, pattern) for pattern in excludes)


def _materialize(
    home: Path,
    candidates: list[tuple[Path, str]],
    *,
    excludes: list[str] | None = None,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    home = home.expanduser().resolve()
    docs: list[Document] = []
    seen: set[Path] = set()
    for path, kind in candidates:
        path = path.expanduser()
        resolved = path.resolve()
        if not path.exists() or resolved in seen:
            continue
        if _is_excluded(path, home, excludes):
            continue
        if path.is_symlink() and not _under(path, home):
            continue
        text = _safe_read(path, max_bytes=max_file_bytes)
        if text:
            docs.append(Document(path=path, kind=kind, text=text))
            seen.add(resolved)
    return docs


def _glob_candidates(home: Path, patterns: list[str], kind: str) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    for pattern in patterns:
        if Path(pattern).is_absolute():
            continue
        candidates.extend((p, kind) for p in home.glob(pattern) if p.is_file())
    return candidates


def collect_hermes_documents(
    home: Path,
    include_skills: bool = False,
    *,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    """Collect read-only Hermes memory docs and optional SKILL.md files.

    This intentionally avoids .env/auth/session/log files. It also refuses to follow symlinks
    outside the selected Hermes home.
    """
    home = home.expanduser().resolve()
    candidates: list[tuple[Path, str]] = []
    memories = home / "memories"
    if memories.exists():
        candidates.extend((p, "memory") for p in memories.glob("*.md"))
    candidates.extend((home / name, "memory") for name in MEMORY_NAMES)
    candidates.extend((p, "memory") for p in home.glob("*.md"))

    if include_skills:
        skills = home / "skills"
        if skills.exists():
            candidates.extend((p, "skill") for p in skills.rglob("SKILL.md"))

    return _materialize(home, candidates, max_file_bytes=max_file_bytes)


def collect_openclaw_documents(
    home: Path,
    include_skills: bool = False,
    *,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    """Collect OpenClaw memory/skill docs without reading sessions, logs, or auth material."""
    home = home.expanduser().resolve()
    candidates: list[tuple[Path, str]] = []

    for rel in OPENCLAW_MEMORY_DIRS:
        directory = home / rel
        if directory.exists():
            candidates.extend((p, "memory") for p in directory.rglob("*.md"))
    candidates.extend((home / name, "memory") for name in MEMORY_NAMES)
    candidates.extend((p, "memory") for p in home.glob("*.md"))

    if include_skills:
        for rel in OPENCLAW_SKILL_DIRS:
            directory = home / rel
            if directory.exists():
                candidates.extend((p, "skill") for p in directory.rglob("SKILL.md"))

    return _materialize(home, candidates, max_file_bytes=max_file_bytes)


def collect_generic_documents(
    home: Path,
    *,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    home = home.expanduser().resolve()
    patterns = includes or ["*.md", "**/*.md"]
    candidates = _glob_candidates(home, patterns, "memory")
    return _materialize(home, candidates, excludes=excludes, max_file_bytes=max_file_bytes)


def collect_named_agent_documents(
    home: Path,
    layout: str,
    include_skills: bool = False,
    *,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    home = home.expanduser().resolve()
    spec = NAMED_LAYOUTS[layout]
    candidates = _glob_candidates(home, spec["includes"], "memory")
    if include_skills:
        candidates.extend(_glob_candidates(home, spec["skill_includes"], "skill"))
    return _materialize(home, candidates, max_file_bytes=max_file_bytes)


def collect_documents(
    home: Path,
    *,
    layout: str = "hermes",
    include_skills: bool = False,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    max_file_bytes: int = 250_000,
) -> list[Document]:
    if layout == "openclaw":
        return collect_openclaw_documents(
            home,
            include_skills=include_skills,
            max_file_bytes=max_file_bytes,
        )
    if layout == "hermes":
        return collect_hermes_documents(
            home,
            include_skills=include_skills,
            max_file_bytes=max_file_bytes,
        )
    if layout == "generic":
        return collect_generic_documents(
            home,
            includes=includes,
            excludes=excludes,
            max_file_bytes=max_file_bytes,
        )
    if layout in NAMED_LAYOUTS:
        return collect_named_agent_documents(
            home,
            layout,
            include_skills=include_skills,
            max_file_bytes=max_file_bytes,
        )
    raise ValueError(f"unsupported memory layout: {layout}")
