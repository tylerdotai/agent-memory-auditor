from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collectors import collect_documents
from .config import load_config
from .model_review import run_model_contradiction_review
from .models import AuditContext, Document, Finding
from .patches import write_patch_suggestions
from .report import render_tui, summarize, write_all
from .scanners.registry import run_scanners


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-audit",
        description="Read-only auditor for AI agent memory, skills, and persistent context.",
    )
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="Scan agent memory and optional skills")
    _add_scan_args(scan)
    scan.add_argument("--strict", action="store_true", help="Return nonzero on any finding")
    scan.add_argument("--output-dir", type=Path, default=Path("reports"), help="Report output directory")
    scan.add_argument("--sarif", action="store_true", help="Write GitHub code scanning SARIF output")
    scan.add_argument(
        "--suggest-patches",
        action="store_true",
        help="Emit review-only .patch files for deterministic fixes without applying them",
    )

    view = sub.add_parser("view", help="Render a terminal report viewer")
    _add_scan_args(view)
    view.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _add_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", type=Path, default=None, help="Agent home directory override")
    parser.add_argument("--profile", default="default", help="Hermes profile name (default: default)")
    parser.add_argument("--profiles", choices=["all"], help="Reserved: scan all profiles")
    parser.add_argument(
        "--layout",
        choices=["hermes", "openclaw", "generic", "claude-code", "codex", "opencode"],
        default="hermes",
        help="Memory layout to scan",
    )
    parser.add_argument("--include-skills", action="store_true", help="Include SKILL.md files")
    parser.add_argument("--include", action="append", dest="includes", help="Generic layout include glob; repeatable")
    parser.add_argument("--exclude", action="append", dest="excludes", help="Generic layout exclude glob; repeatable")
    parser.add_argument("--config", type=Path, default=None, help="TOML config with renames, allowlist, and suppressions")
    parser.add_argument("--max-file-bytes", type=_positive_int, default=250_000, help="Per-file byte cap")
    parser.add_argument(
        "--contradiction-review",
        action="store_true",
        help="Enable optional second pass for possible contradictory memory facts",
    )
    parser.add_argument(
        "--model-command",
        help="External model-review command; receives JSON on stdin and returns JSON findings",
    )


def resolve_home(args: argparse.Namespace) -> Path:
    if args.home:
        return args.home.expanduser().resolve()
    base = Path.home() / ".hermes"
    if args.profile and args.profile != "default":
        return base / "profiles" / args.profile
    return base


def _audit(args: argparse.Namespace) -> tuple[Path, list[Document], list[Finding]]:
    home = resolve_home(args)
    config = load_config(args.config)
    if args.contradiction_review:
        from dataclasses import replace

        config = replace(config, contradiction_review=True)
    ctx = AuditContext(root=home, max_file_bytes=args.max_file_bytes, config=config)
    docs = collect_documents(
        home,
        layout=args.layout,
        include_skills=args.include_skills,
        includes=args.includes,
        excludes=args.excludes,
        max_file_bytes=args.max_file_bytes,
    )
    findings = run_scanners(docs, ctx)
    if args.model_command:
        findings.extend(run_model_contradiction_review(docs, args.model_command))
    return home, docs, findings


def scan(args: argparse.Namespace) -> int:
    home, docs, findings = _audit(args)
    paths = write_all(findings, args.output_dir, sarif=args.sarif)
    if args.suggest_patches:
        patch_paths = write_patch_suggestions(findings, args.output_dir)
        if patch_paths:
            paths["patches"] = args.output_dir / "patches"
    summary = summarize(findings)

    print("Agent Memory Audit")
    print(f"Home: {home}")
    print(f"Layout: {args.layout}")
    print(f"Documents scanned: {len(docs)}")
    print(f"Findings: {summary['total']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"HTML: {paths['html']}")
    print(f"JSON: {paths['json']}")
    if "sarif" in paths:
        print(f"SARIF: {paths['sarif']}")
    if "patches" in paths:
        print(f"Patch suggestions: {paths['patches']}")

    if args.strict and findings:
        return 1
    if any(f.severity in {"critical", "high"} for f in findings):
        return 1
    return 0


def view(args: argparse.Namespace) -> int:
    _home, _docs, findings = _audit(args)
    print(render_tui(findings, color=not args.no_color), end="")
    if any(f.severity in {"critical", "high"} for f in findings):
        return 1
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in {None, "scan"}:
        if args.command is None:
            args = parser.parse_args(["scan", *(argv or [])])
        return scan(args)
    if args.command == "view":
        return view(args)
    parser.print_help()
    return 2


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
