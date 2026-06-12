from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collectors import collect_hermes_documents
from .models import AuditContext
from .report import summarize, write_all
from .scanners.registry import run_scanners


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-audit",
        description="Read-only auditor for AI agent memory, skills, and persistent context.",
    )
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="Scan Hermes memory and optional skills")
    scan.add_argument("--home", type=Path, default=None, help="Hermes home directory override")
    scan.add_argument("--profile", default="default", help="Hermes profile name (default: default)")
    scan.add_argument("--profiles", choices=["all"], help="Reserved: scan all profiles")
    scan.add_argument("--include-skills", action="store_true", help="Include SKILL.md files")
    scan.add_argument("--strict", action="store_true", help="Return nonzero on any finding")
    scan.add_argument("--output-dir", type=Path, default=Path("reports"), help="Report output directory")
    scan.add_argument("--max-file-bytes", type=int, default=250_000, help="Per-file byte cap")
    return parser


def resolve_home(args: argparse.Namespace) -> Path:
    if args.home:
        return args.home.expanduser().resolve()
    base = Path.home() / ".hermes"
    if args.profile and args.profile != "default":
        return base / "profiles" / args.profile
    return base


def scan(args: argparse.Namespace) -> int:
    home = resolve_home(args)
    ctx = AuditContext(root=home, max_file_bytes=args.max_file_bytes)
    docs = collect_hermes_documents(home, include_skills=args.include_skills)
    findings = run_scanners(docs, ctx)
    paths = write_all(findings, args.output_dir)
    summary = summarize(findings)

    print("Agent Memory Audit")
    print(f"Home: {home}")
    print(f"Documents scanned: {len(docs)}")
    print(f"Findings: {summary['total']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"HTML: {paths['html']}")
    print(f"JSON: {paths['json']}")

    if args.strict and findings:
        return 1
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
    parser.print_help()
    return 2


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
