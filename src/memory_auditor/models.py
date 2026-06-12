from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .config import AuditConfig

Severity = Literal["low", "medium", "high", "critical"]

DEFAULT_RENAMES = {
    "twit-auto": "agent-poster",
    "window.__twitAuto": "window.__ap",
    "twit_auto": "agent_poster",
}


@dataclass(frozen=True)
class Document:
    path: Path
    kind: str
    text: str

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


@dataclass(frozen=True)
class AuditContext:
    root: Path
    max_file_bytes: int = 250_000
    known_renames: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_RENAMES))
    config: AuditConfig = field(default_factory=AuditConfig)

    def __post_init__(self) -> None:
        if self.config.renames:
            merged = dict(DEFAULT_RENAMES)
            merged.update(self.config.renames)
            object.__setattr__(self, "known_renames", merged)


@dataclass(frozen=True)
class Finding:
    severity: Severity
    category: str
    path: str
    line: int | None
    snippet: str
    reason: str
    suggested_action: str

    def asdict(self) -> dict[str, object]:
        return asdict(self)
