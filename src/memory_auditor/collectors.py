from __future__ import annotations

from pathlib import Path

from .models import Document

MEMORY_NAMES = {"MEMORY.md", "USER.md", "memory.md", "user.md"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "sessions", "logs", "auth"}


def _safe_read(path: Path, max_bytes: int = 250_000) -> str:
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


def collect_hermes_documents(home: Path, include_skills: bool = False) -> list[Document]:
    """Collect read-only Hermes memory docs and optional SKILL.md files.

    This intentionally avoids .env/auth/session/log files. It also refuses to follow symlinks
    outside the selected Hermes home.
    """
    home = home.expanduser().resolve()
    docs: list[Document] = []

    candidates: list[tuple[Path, str]] = []
    memories = home / "memories"
    if memories.exists():
        candidates.extend((p, "memory") for p in memories.glob("*.md"))
    candidates.extend((home / name, "memory") for name in MEMORY_NAMES)

    if include_skills:
        skills = home / "skills"
        if skills.exists():
            candidates.extend((p, "skill") for p in skills.rglob("SKILL.md"))

    seen: set[Path] = set()
    for path, kind in candidates:
        if not path.exists() or path in seen:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_symlink() and not _under(path, home):
            continue
        text = _safe_read(path)
        if text:
            docs.append(Document(path=path, kind=kind, text=text))
            seen.add(path)
    return docs
