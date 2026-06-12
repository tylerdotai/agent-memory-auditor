from __future__ import annotations

import difflib
import re
from pathlib import Path

from memory_auditor.models import AuditContext, Document, Finding, Severity

TOKEN_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9._-]{6,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s`'\"]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

IMPERATIVE_RE = re.compile(
    r"^\s*(always|never|must|do not|don't|ask .* before|make sure to|remember to)\b",
    re.I,
)
STALE_RE = re.compile(
    r"\b(today|tomorrow|yesterday|this week|last week|currently|phase\s+\d+\s+(done|complete)|"
    r"fixed|submitted|opened|closed|PR\s*#\d+|issue\s*#\d+|[a-f0-9]{7,40})\b",
    re.I,
)
SKILL_CANDIDATE_RE = re.compile(r"\b(to debug|to build|workflow|run .+ then|steps?:|playbook)\b", re.I)
ABS_PATH_RE = re.compile(r"(?<![\w/])/(?:home|tmp|opt|srv|var|etc)/[^\s`'\",)]+")


def _line_findings(
    docs: list[Document],
    category: str,
    regex: re.Pattern[str],
    severity: Severity,
    reason: str,
    suggested_action: str,
    redact: bool = False,
) -> list[Finding]:
    out: list[Finding] = []
    for doc in docs:
        for idx, line in enumerate(doc.lines, 1):
            if regex.search(line):
                out.append(
                    Finding(
                        severity=severity,
                        category=category,
                        path=str(doc.path),
                        line=idx,
                        snippet=redact_secrets(line.strip()) if redact else line.strip()[:260],
                        reason=reason,
                        suggested_action=suggested_action,
                    )
                )
    return out


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(lambda m: f"[REDACTED:{m.group(0)[:3]}…]", redacted)
    return redacted[:260]


def scan_secrets(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    findings: list[Finding] = []
    for doc in docs:
        for idx, line in enumerate(doc.lines, 1):
            if any(pattern.search(line) for pattern in TOKEN_PATTERNS):
                findings.append(
                    Finding(
                        severity="high",
                        category="secret-like",
                        path=str(doc.path),
                        line=idx,
                        snippet=redact_secrets(line.strip()),
                        reason="Line contains credential-shaped material. Reports redact the value before writing output.",
                        suggested_action="Remove or rotate the secret if real; keep credentials in environment/secret stores, not memory.",
                    )
                )
    return findings


def scan_imperatives(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    return _line_findings(
        docs,
        "imperative-memory",
        IMPERATIVE_RE,
        "medium",
        "Persistent memory should store durable facts, not standing commands that behave like hidden system instructions.",
        "Rewrite as a declarative fact or move the procedure into a skill.",
    )


def scan_stale(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    return _line_findings(
        docs,
        "stale-task-progress",
        STALE_RE,
        "medium",
        "This looks like task progress, a temporary date reference, PR/issue status, or another fact likely to go stale.",
        "Remove from durable memory; rely on session history or project tracking for short-lived state.",
    )


def _normalize(line: str) -> str:
    line = re.sub(r"[^a-z0-9]+", " ", line.lower())
    return " ".join(line.split())


def scan_duplicates(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    items: list[tuple[str, Document, int, str]] = []
    for doc in docs:
        if doc.kind != "memory":
            continue
        for idx, line in enumerate(doc.lines, 1):
            normalized = _normalize(line)
            if len(normalized) >= 18:
                items.append((normalized, doc, idx, line.strip()))

    findings: list[Finding] = []
    seen_pairs: set[tuple[int, int]] = set()
    for i, first in enumerate(items):
        for j, second in enumerate(items[i + 1 :], i + 1):
            if (i, j) in seen_pairs:
                continue
            ratio = difflib.SequenceMatcher(a=first[0], b=second[0]).ratio()
            if ratio >= 0.88:
                findings.append(
                    Finding(
                        severity="low",
                        category="duplicate-memory",
                        path=str(second[1].path),
                        line=second[2],
                        snippet=second[3][:260],
                        reason=f"Near-duplicate of {first[1].path}:{first[2]} (similarity {ratio:.2f}).",
                        suggested_action="Consolidate into one durable entry or move project-specific details to project context.",
                    )
                )
                seen_pairs.add((i, j))
    return findings


def scan_repo_paths(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    findings: list[Finding] = []
    for doc in docs:
        for idx, line in enumerate(doc.lines, 1):
            for match in ABS_PATH_RE.findall(line):
                path = Path(match).expanduser()
                if not path.exists():
                    findings.append(
                        Finding(
                            severity="medium",
                            category="repo-path-missing",
                            path=str(doc.path),
                            line=idx,
                            snippet=line.strip()[:260],
                            reason=f"Referenced path does not exist: {path}",
                            suggested_action="Update the path, delete the stale fact, or keep it in a project-specific note if historical.",
                        )
                    )
    return findings


def scan_naming_drift(docs: list[Document], ctx: AuditContext) -> list[Finding]:
    findings: list[Finding] = []
    for doc in docs:
        for idx, line in enumerate(doc.lines, 1):
            lower = line.lower()
            for old, new in ctx.known_renames.items():
                if old.lower() in lower:
                    findings.append(
                        Finding(
                            severity="medium",
                            category="naming-drift",
                            path=str(doc.path),
                            line=idx,
                            snippet=line.strip()[:260],
                            reason=f"Uses old name `{old}`; known replacement is `{new}`.",
                            suggested_action=f"Replace `{old}` with `{new}` if the entry is still worth keeping.",
                        )
                    )
    return findings


def scan_skill_candidates(docs: list[Document], _ctx: AuditContext) -> list[Finding]:
    findings: list[Finding] = []
    for doc in docs:
        if doc.kind != "memory":
            continue
        for idx, line in enumerate(doc.lines, 1):
            if SKILL_CANDIDATE_RE.search(line) and len(line) > 50:
                findings.append(
                    Finding(
                        severity="low",
                        category="skill-candidate",
                        path=str(doc.path),
                        line=idx,
                        snippet=line.strip()[:260],
                        reason="This reads like reusable procedure rather than a durable fact.",
                        suggested_action="Draft or update a SKILL.md and replace this memory with a concise fact if needed.",
                    )
                )
    return findings


def scan_possible_contradictions(docs: list[Document], ctx: AuditContext) -> list[Finding]:
    if not ctx.config.contradiction_review:
        return []

    # Offline second pass: find simple declarative facts with the same subject and conflicting values.
    # This is intentionally conservative; future model adapters can consume the same finding shape.
    fact_re = re.compile(r"^\s*(?P<subject>[A-Z][A-Za-z0-9 _.-]{3,80}?)\s+(?:is|=)\s+(?P<value>[^.\n]+)", re.I)
    facts: dict[str, tuple[Document, int, str]] = {}
    findings: list[Finding] = []
    for doc in docs:
        for idx, line in enumerate(doc.lines, 1):
            match = fact_re.match(line)
            if not match:
                continue
            subject = _normalize(match.group("subject"))
            value = _normalize(match.group("value"))
            if not subject or not value:
                continue
            previous = facts.get(subject)
            if previous and previous[2] != value:
                findings.append(
                    Finding(
                        severity="medium",
                        category="possible-contradiction",
                        path=str(doc.path),
                        line=idx,
                        snippet=line.strip()[:260],
                        reason=f"Potentially contradicts {previous[0].path}:{previous[1]}; same subject has different values.",
                        suggested_action="Review both entries; keep the current fact and delete or supersede the stale one.",
                    )
                )
            else:
                facts[subject] = (doc, idx, value)
    return findings


SCANNERS = [
    scan_secrets,
    scan_imperatives,
    scan_stale,
    scan_duplicates,
    scan_repo_paths,
    scan_naming_drift,
    scan_skill_candidates,
    scan_possible_contradictions,
]


def _filtered(findings: list[Finding], ctx: AuditContext) -> list[Finding]:
    kept: list[Finding] = []
    for finding in findings:
        text = f"{finding.snippet}\n{finding.reason}\n{finding.suggested_action}"
        if any(rule.matches(category=finding.category, path=finding.path, text=text) for rule in ctx.config.allowlist):
            continue
        if any(rule.matches(category=finding.category, path=finding.path, text=text) for rule in ctx.config.suppressions):
            continue
        kept.append(finding)
    return kept


def run_scanners(docs: list[Document], ctx: AuditContext) -> list[Finding]:
    findings: list[Finding] = []
    for scanner in SCANNERS:
        findings.extend(scanner(docs, ctx))
    findings = _filtered(findings, ctx)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(findings, key=lambda f: (order[f.severity], f.category, f.path, f.line or 0))
