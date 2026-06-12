from __future__ import annotations

import json
import shlex
import subprocess

from .models import Document, Finding


def run_model_contradiction_review(docs: list[Document], command: str) -> list[Finding]:
    """Run an optional external model command for contradiction review.

    The command receives JSON on stdin and must return a JSON list of finding-like objects.
    No shell is used; pass a normal command string such as `python reviewer.py`.
    """
    payload = {
        "task": "Find contradictions in durable AI-agent memory. Return only JSON findings.",
        "documents": [
            {"path": str(doc.path), "kind": doc.kind, "text": doc.text[:50_000]} for doc in docs
        ],
    }
    result = subprocess.run(
        shlex.split(command),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        return [
            Finding(
                severity="medium",
                category="model-review-error",
                path="model-command",
                line=None,
                snippet=result.stderr.strip()[:260],
                reason="External contradiction-review command failed.",
                suggested_action="Fix the model command or run without --model-command.",
            )
        ]
    try:
        raw_findings = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [
            Finding(
                severity="medium",
                category="model-review-error",
                path="model-command",
                line=None,
                snippet=result.stdout.strip()[:260],
                reason="External contradiction-review command did not return JSON.",
                suggested_action="Make the command print a JSON array of findings.",
            )
        ]
    findings: list[Finding] = []
    if not isinstance(raw_findings, list):
        return findings
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        findings.append(
            Finding(
                severity=item.get("severity", "medium") if item.get("severity") in {"low", "medium", "high", "critical"} else "medium",
                category="model-contradiction",
                path=str(item.get("path", "model-command")),
                line=item.get("line") if isinstance(item.get("line"), int) else None,
                snippet=str(item.get("snippet", ""))[:260],
                reason=str(item.get("reason", "Model-assisted contradiction review flagged this entry.")),
                suggested_action=str(item.get("suggested_action", "Review the conflicting memory entries.")),
            )
        )
    return findings
