from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import AuditIssue, audit_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pycompat-audit",
        description="Audit Python compatibility metadata against GitHub Actions coverage.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Repository root to audit. Defaults to the current directory.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when warnings are found.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = audit_repository(args.path)

    if args.format == "json":
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        _print_text(result.issues)

    return int(bool(result.errors or (args.strict and result.warnings)))


def _print_text(issues: tuple[AuditIssue, ...]) -> None:
    if not issues:
        print("pycompat-audit passed: compatibility metadata matches CI coverage.")
        return
    for issue in issues:
        print(f"{issue.severity.upper():7} {issue.code} {issue.path}: {issue.message}")


if __name__ == "__main__":
    raise SystemExit(main())

