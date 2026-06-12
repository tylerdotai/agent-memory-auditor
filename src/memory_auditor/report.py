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


def _severity_total(summary: dict[str, object], *names: str) -> int:
    by_severity = summary["by_severity"]
    assert isinstance(by_severity, dict)
    return sum(int(by_severity.get(name, 0)) for name in names)


def _category_total(summary: dict[str, object], name: str) -> int:
    by_category = summary["by_category"]
    assert isinstance(by_category, dict)
    return int(by_category.get(name, 0))


def _top_items(counts: dict[str, int], limit: int = 6) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def write_html(findings: list[Finding], output: Path) -> None:
    summary = summarize(findings)
    by_category = {str(k): int(v) for k, v in summary["by_category"].items()}
    by_severity = {str(k): int(v) for k, v in summary["by_severity"].items()}
    high_total = _severity_total(summary, "critical", "high")
    medium_total = _severity_total(summary, "medium")
    low_total = _severity_total(summary, "low")
    secret_total = _category_total(summary, "secret-like")
    contradiction_total = _category_total(summary, "possible-contradiction") + _category_total(summary, "model-contradiction")
    patchable_total = _category_total(summary, "naming-drift")

    triage = [
        ("Review high-severity findings first", f"{high_total} credential-shaped or critical findings need human review before sharing memory broadly."),
        ("Separate examples from live secrets", "Credential-shaped snippets are redacted. Confirm whether each is a placeholder, environment variable name, or real exposed value."),
        ("Treat contradiction review as a second pass", f"{contradiction_total} possible contradictions are useful leads, not automatic delete instructions."),
        ("Apply patches only after review", f"{patchable_total} naming-drift findings may produce patch suggestions, but historical rename context should stay intact."),
    ]
    if not findings:
        triage = [("No findings", "This scan did not find obvious stale, risky, contradictory, or bloated memory entries.")]

    category_pills = "".join(
        f"<button class='filter' data-filter='{html.escape(category)}'>{html.escape(category)} <b>{count}</b></button>"
        for category, count in _top_items(by_category, limit=12)
    )
    severity_bars = "".join(
        f"<div class='bar-row'><span>{html.escape(name)}</span><div class='bar'><i style='width:{(count / max(int(summary['total']), 1)) * 100:.1f}%'></i></div><b>{count}</b></div>"
        for name, count in _top_items(by_severity, limit=4)
    )
    category_bars = "".join(
        f"<div class='bar-row'><span>{html.escape(name)}</span><div class='bar'><i style='width:{(count / max(int(summary['total']), 1)) * 100:.1f}%'></i></div><b>{count}</b></div>"
        for name, count in _top_items(by_category, limit=8)
    )
    triage_cards = "".join(
        f"<article class='triage-card'><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>"
        for title, body in triage
    )

    rows = []
    for idx, f in enumerate(findings, 1):
        loc = f.path if f.line is None else f"{f.path}:{f.line}"
        rows.append(
            "<tr "
            f"data-category='{html.escape(f.category)}' data-severity='{html.escape(f.severity)}'>"
            f"<td class='num'>{idx}</td>"
            f"<td><span class='sev {html.escape(f.severity)}'>{html.escape(f.severity)}</span></td>"
            f"<td><span class='category'>{html.escape(f.category)}</span></td>"
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
<title>AI Agent Memory Audit</title>
<style>
:root {{ color-scheme: dark; --bg:#080b12; --panel:#111827; --panel2:#0d1320; --ink:#eef4ff; --muted:#9aa7bd; --line:#253044; --red:#ff5570; --orange:#f8b84e; --blue:#67a7ff; --green:#58d68d; --purple:#b48cff; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 12% 0%, rgba(89,118,255,.24), transparent 32%), linear-gradient(180deg,#070a11 0%,#0b1020 54%,#070a11 100%); color:var(--ink); }}
a {{ color:#b9d5ff; }}
main {{ max-width:1280px; margin:0 auto; padding:36px 22px 64px; }}
.hero {{ display:grid; grid-template-columns: 1.25fr .75fr; gap:24px; align-items:stretch; border:1px solid rgba(255,255,255,.09); background:linear-gradient(135deg,rgba(17,24,39,.92),rgba(13,19,32,.82)); border-radius:28px; padding:32px; box-shadow:0 30px 100px rgba(0,0,0,.38); }}
.eyebrow {{ color:#8fb9ff; text-transform:uppercase; letter-spacing:.18em; font-size:12px; font-weight:800; }}
h1 {{ font-size:clamp(40px,6vw,74px); line-height:.92; margin:12px 0 16px; letter-spacing:-.065em; max-width:880px; }}
h2 {{ font-size:28px; letter-spacing:-.03em; margin:0 0 12px; }}
h3 {{ margin:0 0 8px; font-size:16px; }}
p {{ color:var(--muted); font-size:16px; line-height:1.6; }}
.lede {{ font-size:19px; max-width:760px; }}
.cards {{ display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:12px; }}
.card, .panel, .triage-card {{ background:rgba(13,19,32,.78); border:1px solid rgba(255,255,255,.09); border-radius:20px; padding:18px; }}
.card span {{ color:var(--muted); font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }}
.card b {{ display:block; font-size:36px; line-height:1; margin-top:10px; letter-spacing:-.04em; }}
.nav {{ position:sticky; top:0; z-index:5; backdrop-filter:blur(16px); background:rgba(8,11,18,.78); border:1px solid rgba(255,255,255,.08); border-radius:999px; padding:8px; margin:18px 0 24px; display:flex; gap:8px; overflow:auto; }}
.nav a, .filter, #clearFilter {{ border:1px solid rgba(255,255,255,.1); color:var(--ink); background:#121a2a; border-radius:999px; padding:10px 14px; text-decoration:none; white-space:nowrap; font-size:13px; font-weight:750; cursor:pointer; }}
.nav a:hover, .filter:hover, #clearFilter:hover {{ border-color:#6da8ff; }}
.grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:18px; margin:22px 0; }}
.triage {{ display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:14px; }}
.triage-card h3 {{ color:#f4f7ff; }}
.triage-card p {{ margin:0; font-size:14px; }}
.bar-row {{ display:grid; grid-template-columns: 160px 1fr 48px; gap:12px; align-items:center; padding:9px 0; border-bottom:1px solid rgba(255,255,255,.06); }}
.bar-row span {{ color:#d7e3f8; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bar {{ height:9px; background:#0a101c; border-radius:999px; overflow:hidden; border:1px solid rgba(255,255,255,.08); }}
.bar i {{ display:block; height:100%; background:linear-gradient(90deg,#6da8ff,#b48cff); border-radius:999px; }}
.filters {{ display:flex; flex-wrap:wrap; gap:8px; margin:14px 0; }}
.table-wrap {{ overflow:auto; border:1px solid rgba(255,255,255,.1); border-radius:22px; background:rgba(13,19,32,.72); }}
table {{ width:100%; border-collapse:collapse; min-width:1120px; }}
th,td {{ padding:13px 14px; border-bottom:1px solid rgba(255,255,255,.08); vertical-align:top; text-align:left; }}
th {{ position:sticky; top:0; background:#111827; color:#cbd8ee; font-size:11px; text-transform:uppercase; letter-spacing:.08em; z-index:1; }}
code {{ color:#c9ddff; white-space:pre-wrap; word-break:break-word; font-size:12px; }}
.num {{ color:#68758a; font-variant-numeric:tabular-nums; }}
.category {{ color:#dce8ff; font-weight:750; }}
.sev {{ border-radius:999px; padding:5px 9px; font-weight:850; font-size:11px; text-transform:uppercase; display:inline-block; }}
.sev.high,.sev.critical {{ background:rgba(255,85,112,.16); color:var(--red); }}
.sev.medium {{ background:rgba(248,184,78,.16); color:var(--orange); }}
.sev.low {{ background:rgba(103,167,255,.16); color:var(--blue); }}
.note {{ border-left:3px solid #6da8ff; padding:12px 14px; background:rgba(109,168,255,.08); border-radius:12px; color:#c9d7ed; }}
.hidden {{ display:none; }}
@media (max-width:900px) {{ .hero,.grid,.triage {{ grid-template-columns:1fr; }} .cards {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} main {{ padding:18px 12px 44px; }} .hero {{ padding:22px; }} }}
@media print {{ body {{ background:#fff; color:#111827; }} .nav,.filters,#clearFilter {{ display:none; }} .hero,.panel,.triage-card,.table-wrap {{ box-shadow:none; border-color:#cbd5e1; }} main {{ max-width:none; }} }}
</style>
</head>
<body><main>
<section class="hero" id="top">
  <div>
    <div class="eyebrow">Read-only agent memory review</div>
    <h1>AI Agent Memory Audit</h1>
    <p class="lede">A presentable review of durable agent context: stale state, risky instructions, credential-shaped strings, naming drift, missing paths, duplication, and contradiction candidates.</p>
    <p class="note">Secrets are redacted before report generation. Patch suggestions are review-only files and are never applied automatically.</p>
  </div>
  <div class="cards" aria-label="Audit totals">
    <div class="card"><span>Total findings</span><b>{summary['total']}</b></div>
    <div class="card"><span>High priority</span><b>{high_total}</b></div>
    <div class="card"><span>Medium</span><b>{medium_total}</b></div>
    <div class="card"><span>Low</span><b>{low_total}</b></div>
    <div class="card"><span>Secret-like</span><b>{secret_total}</b></div>
    <div class="card"><span>Categories</span><b>{len(by_category)}</b></div>
  </div>
</section>
<nav class="nav" aria-label="Report sections">
  <a href="#summary">Executive summary</a>
  <a href="#triage">Recommended triage</a>
  <a href="#methodology">Methodology</a>
  <a href="#findings">Finding explorer</a>
</nav>
<section id="summary" class="grid">
  <article class="panel"><h2>Executive summary</h2><p>This report is designed for builders reviewing the health of long-lived AI-agent memory. Findings are leads for human review, not automatic truth. Start with high-severity and secret-like items, then clean stale task progress and imperative memory that behaves like hidden instructions.</p>{severity_bars}</article>
  <article class="panel"><h2>Category distribution</h2><p>Large counts in contradiction review usually mean “review candidates,” not guaranteed conflicts. Use category filters below to focus the conversation.</p>{category_bars}</article>
</section>
<section id="triage" class="panel"><h2>Recommended triage</h2><div class="triage">{triage_cards}</div></section>
<section id="methodology" class="panel"><h2>Methodology</h2><p>The scanner reads only selected memory documents, does not follow symlinks outside the audit root, redacts credential-shaped snippets, and writes Markdown, HTML, JSON, and optional SARIF. Generic layouts are rooted under <code>--home</code>; absolute include paths and parent-directory escapes are ignored.</p></section>
<section id="findings" class="panel"><h2>Finding explorer</h2><p>Filter by category for a review-room workflow. The full machine-readable record is in <code>memory-audit.json</code>; this HTML is the human briefing layer.</p><div class="filters"><button id="clearFilter">All findings <b>{summary['total']}</b></button>{category_pills}</div><div class="table-wrap"><table><thead><tr><th>#</th><th>Severity</th><th>Category</th><th>Location</th><th>Snippet</th><th>Reason</th><th>Suggested action</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div></section>
<script>
const rows = [...document.querySelectorAll('tbody tr')];
const buttons = [...document.querySelectorAll('[data-filter]')];
const clear = document.getElementById('clearFilter');
function applyFilter(category) {{ rows.forEach(row => row.classList.toggle('hidden', category && row.dataset.category !== category)); }}
buttons.forEach(button => button.addEventListener('click', () => applyFilter(button.dataset.filter)));
clear.addEventListener('click', () => applyFilter(''));
</script>
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
