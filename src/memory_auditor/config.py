from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


@dataclass(frozen=True)
class Rule:
    category: str | None = None
    path: str | None = None
    pattern: str | None = None
    reason: str | None = None

    def matches(self, *, category: str, path: str, text: str) -> bool:
        if self.category and self.category != category:
            return False
        if self.path and self.path not in path:
            return False
        return not (self.pattern and not re.search(self.pattern, text, re.I))


@dataclass(frozen=True)
class AuditConfig:
    renames: dict[str, str] = field(default_factory=dict)
    allowlist: list[Rule] = field(default_factory=list)
    suppressions: list[Rule] = field(default_factory=list)
    contradiction_review: bool = False


def _rules(raw: object) -> list[Rule]:
    if not isinstance(raw, list):
        return []
    rules: list[Rule] = []
    for item in raw:
        if isinstance(item, dict):
            rules.append(
                Rule(
                    category=item.get("category"),
                    path=item.get("path"),
                    pattern=item.get("pattern"),
                    reason=item.get("reason"),
                )
            )
    return rules


def load_config(path: Path | None) -> AuditConfig:
    if path is None or not path.exists():
        return AuditConfig()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    renames = raw.get("renames", {}) if isinstance(raw.get("renames", {}), dict) else {}
    review = raw.get("contradiction_review", False)
    if isinstance(review, dict):
        review = bool(review.get("enabled", False))
    return AuditConfig(
        renames={str(k): str(v) for k, v in renames.items()},
        allowlist=_rules(raw.get("allowlist")),
        suppressions=_rules(raw.get("suppressions")),
        contradiction_review=bool(review),
    )
