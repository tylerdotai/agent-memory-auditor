from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from .models import Finding


def summarize(findings: list[Finding]) -> dict[str, object]:
    by_severity = Counter(f.severity for f in findings)
    by_category = Counter(f.category for f in findings)
    return {
        "total": len(findings),
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
    }


def write_json(findings: list[Finding], output: Path) -> None:
    output.write_text(
        json.dumps(
            {"summary": summarize(findings), "findings": [f.asdict() for f in findings]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_markdown(findings: list[Finding], output: Path) -> None:
    summary = summarize(findings)
    lines = [
        "# Agent Memory Audit",
        "",
        f"Total findings: **{summary['total']}**",
        "",
        "## Counts by severity",
        "",
    ]
    for key, value in summary["by_severity"].items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Counts by category", ""])
    for key, value in summary["by_category"].items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Findings", ""])
    for idx, f in enumerate(findings, 1):
        loc = f.path if f.line is None else f"{f.path}:{f.line}"
        lines.extend(
            [
                f"### {idx}. {f.severity.upper()} · {f.category}",
                "",
                f"- Location: `{loc}`",
                f"- Snippet: `{f.snippet}`",
                f"- Reason: {f.reason}",
                f"- Suggested action: {f.suggested_action}",
                "",
            ]
        )
    output.write_text("\n".join(lines), encoding="utf-8")


def write_html(findings: list[Finding], output: Path) -> None:
    summary = summarize(findings)
    rows = []
    for f in findings:
        loc = f.path if f.line is None else f"{f.path}:{f.line}"
        rows.append(
            "<tr>"
            f"<td><span class='sev {html.escape(f.severity)}'>{html.escape(f.severity)}</span></td>"
            f"<td>{html.escape(f.category)}</td>"
            f"<td><code>{html.escape(loc)}</code></td>"
            f"<td><code>{html.escape(f.snippet)}</code></td>"
            f"<td>{html.escape(f.reason)}</td>"
            f"<td>{html.escape(f.suggested_action)}</td>"
            "</tr>"
        )
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Memory Audit</title>
<style>
:root {{ color-scheme: dark; --bg:#08111f; --panel:#101b2d; --text:#e7eefc; --muted:#94a3b8; --line:#24334d; --red:#ff5c7a; --orange:#ffb454; --green:#4ade80; --blue:#60a5fa; }}
body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top left, #172554, var(--bg) 42%); color:var(--text); }}
main {{ max-width:1180px; margin:0 auto; padding:48px 24px; }}
.hero {{ border:1px solid var(--line); background:rgba(16,27,45,.86); border-radius:24px; padding:36px; box-shadow:0 20px 80px rgba(0,0,0,.35); }}
h1 {{ font-size:44px; line-height:1; margin:0 0 12px; letter-spacing:-.04em; }}
p {{ color:var(--muted); font-size:17px; }}
.cards {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin:24px 0; }}
.card {{ background:#0b1324; border:1px solid var(--line); border-radius:18px; padding:18px; }}
.card b {{ display:block; font-size:28px; }}
table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:18px; background:rgba(16,27,45,.92); border:1px solid var(--line); }}
th,td {{ padding:13px 14px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; }}
th {{ color:#cbd5e1; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
code {{ color:#bfdbfe; white-space:pre-wrap; word-break:break-word; }}
.sev {{ border-radius:999px; padding:5px 9px; font-weight:700; font-size:12px; text-transform:uppercase; }}
.sev.high,.sev.critical {{ background:rgba(255,92,122,.16); color:var(--red); }}
.sev.medium {{ background:rgba(255,180,84,.16); color:var(--orange); }}
.sev.low {{ background:rgba(96,165,250,.16); color:var(--blue); }}
</style>
</head>
<body><main>
<section class="hero">
<h1>Agent Memory Audit</h1>
<p>Read-only scan of persistent agent memory and skills. Secrets are redacted before report generation.</p>
<div class="cards">
<div class="card"><span>Total findings</span><b>{summary['total']}</b></div>
<div class="card"><span>High</span><b>{summary['by_severity'].get('high', 0) + summary['by_severity'].get('critical', 0)}</b></div>
<div class="card"><span>Categories</span><b>{len(summary['by_category'])}</b></div>
</div>
</section>
<h2>Findings</h2>
<table><thead><tr><th>Severity</th><th>Category</th><th>Location</th><th>Snippet</th><th>Reason</th><th>Suggested action</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</main></body></html>"""
    output.write_text(doc, encoding="utf-8")


def write_sarif(findings: list[Finding], output: Path) -> None:
    rules = {}
    results = []
    for finding in findings:
        rules.setdefault(
            finding.category,
            {
                "id": finding.category,
                "name": finding.category,
                "shortDescription": {"text": finding.category},
                "fullDescription": {"text": finding.reason},
                "help": {"text": finding.suggested_action},
            },
        )
        level = "error" if finding.severity in {"critical", "high"} else "warning" if finding.severity == "medium" else "note"
        results.append(
            {
                "ruleId": finding.category,
                "level": level,
                "message": {"text": f"{finding.reason} Suggested action: {finding.suggested_action}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding.path},
                            "region": {"startLine": finding.line or 1, "snippet": {"text": finding.snippet}},
                        }
                    }
                ],
            }
        )
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Agent Memory Auditor",
                        "informationUri": "https://github.com/tylerdotai/agent-memory-auditor",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    output.write_text(json.dumps(sarif, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_tui(findings: list[Finding], *, color: bool = True) -> str:
    summary = summarize(findings)
    widths = {"sev": 8, "cat": 24, "loc": 42}
    colors = {
        "critical": "\033[1;31m",
        "high": "\033[31m",
        "medium": "\033[33m",
        "low": "\033[36m",
        "reset": "\033[0m",
    }

    def paint(severity: str, text: str) -> str:
        if not color:
            return text
        return f"{colors.get(severity, '')}{text}{colors['reset']}"

    lines = [
        "Agent Memory Audit",
        "=" * 70,
        f"Findings: {summary['total']}  Severities: {summary['by_severity']}  Categories: {len(summary['by_category'])}",
        "-" * 70,
    ]
    for finding in findings:
        loc = finding.path if finding.line is None else f"{finding.path}:{finding.line}"
        lines.append(
            f"{paint(finding.severity, finding.severity.upper()):<{widths['sev']}} "
            f"{finding.category:<{widths['cat']}} "
            f"{loc[:widths['loc']]:<{widths['loc']}}"
        )
        lines.append(f"  {finding.snippet}")
        lines.append(f"  ↳ {finding.suggested_action}")
    return "\n".join(lines) + "\n"


def write_all(findings: list[Finding], output_dir: Path, *, sarif: bool = False) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_dir / "memory-audit.json",
        "markdown": output_dir / "memory-audit.md",
        "html": output_dir / "memory-audit.html",
    }
    write_json(findings, paths["json"])
    write_markdown(findings, paths["markdown"])
    write_html(findings, paths["html"])
    if sarif:
        paths["sarif"] = output_dir / "memory-audit.sarif"
        write_sarif(findings, paths["sarif"])
    return paths
