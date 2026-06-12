from __future__ import annotations

import difflib
import re
from collections import defaultdict
from pathlib import Path

from .models import Finding


def _safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path).strip("_") or "memory"


def write_patch_suggestions(findings: list[Finding], output_dir: Path) -> list[Path]:
    """Emit unified diff files for safe, review-only remediations.

    The source files are never modified. Only findings with deterministic replacements are emitted.
    """
    patches_dir = output_dir / "patches"
    patches_dir.mkdir(parents=True, exist_ok=True)
    by_path: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        if finding.category == "naming-drift":
            by_path[finding.path].append(finding)

    written: list[Path] = []
    for raw_path, path_findings in by_path.items():
        source = Path(raw_path)
        if not source.exists() or source.is_symlink():
            continue
        original = source.read_text(encoding="utf-8", errors="replace")
        updated = original
        for finding in path_findings:
            match = re.search(r"Uses old name `([^`]+)`; known replacement is `([^`]+)`", finding.reason)
            if match:
                old, new = match.groups()
                updated = updated.replace(old, new)
        if updated == original:
            continue
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(source),
                tofile=str(source),
            )
        )
        patch_path = patches_dir / f"{_safe_name(str(source))}.patch"
        patch_path.write_text(diff, encoding="utf-8")
        written.append(patch_path)
    return written
