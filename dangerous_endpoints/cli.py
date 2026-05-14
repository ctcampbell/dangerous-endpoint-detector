import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

import anthropic

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional
    load_dotenv = None

from .core import (
    SOURCE_EXTENSIONS,
    EndpointResult,
    analyze_endpoint_with_llm,
    extract_endpoints_from_code,
)

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", "dist", "build", ".next", ".nuxt", "target", "out",
    ".idea", ".vscode", ".tox", ".mypy_cache", ".pytest_cache",
}


def find_source_files(root: Path, extensions: set, ignore_dirs: set) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if any(part in ignore_dirs for part in path.parts):
            continue
        files.append(path)
    return files


def colorize(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def format_findings(findings: List[EndpointResult], root: Path, color: bool) -> str:
    if not findings:
        return colorize("No dangerous endpoints detected.", "32", color)

    by_file: dict = {}
    for f in findings:
        by_file.setdefault(f.file_path, []).append(f)

    lines: List[str] = []
    lines.append(colorize(f"\nFound {len(findings)} dangerous endpoint(s) in {len(by_file)} file(s):\n", "1;31", color))

    for file_path, items in sorted(by_file.items()):
        try:
            rel = Path(file_path).resolve().relative_to(root.resolve())
        except ValueError:
            rel = Path(file_path)
        lines.append(colorize(f"📄 {rel}", "1;36", color))
        for item in sorted(items, key=lambda x: x.line_number):
            conf_color = {"high": "31", "medium": "33", "low": "37"}.get(item.confidence.lower(), "37")
            lines.append(
                f"  L{item.line_number}: {colorize(item.endpoint, '1', color)}  "
                f"[{colorize(item.dangerous_action, '35', color)}]  "
                f"confidence={colorize(item.confidence, conf_color, color)}"
            )
            lines.append(f"      {item.explanation}")
        lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Error: path does not exist: {root}", file=sys.stderr)
        return 2

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    extensions = set(SOURCE_EXTENSIONS)
    if args.extensions:
        extensions = {e if e.startswith(".") else f".{e}" for e in args.extensions}

    ignore_dirs = set(DEFAULT_IGNORE_DIRS) | set(args.ignore or [])

    use_color = sys.stdout.isatty() and not args.no_color

    print(f"Scanning {root} for source files...")
    files = find_source_files(root, extensions, ignore_dirs)
    print(f"Found {len(files)} source file(s).")

    all_endpoints = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            print(f"  ! skip {f}: {e}", file=sys.stderr)
            continue
        endpoints = extract_endpoints_from_code(content, str(f))
        all_endpoints.extend(endpoints)

    if not all_endpoints:
        print("No endpoints detected.")
        return 0

    print(f"Extracted {len(all_endpoints)} endpoint(s). Analyzing with Claude...")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    semaphore = asyncio.Semaphore(args.concurrency)

    completed = 0
    findings: List[EndpointResult] = []

    async def analyze_one(ep):
        nonlocal completed
        result = await analyze_endpoint_with_llm(ep, client, model=args.model, semaphore=semaphore)
        completed += 1
        progress = f"[{completed}/{len(all_endpoints)}]"
        if result is not None:
            findings.append(result)
            print(f"  {progress} ⚠️  {ep['endpoint']} ({result.dangerous_action}, {result.confidence})")
        elif args.verbose:
            print(f"  {progress} ✓  {ep['endpoint']}")
        return result

    await asyncio.gather(*(analyze_one(ep) for ep in all_endpoints))

    output = format_findings(findings, root, use_color)
    print(output)

    if args.json:
        payload = {
            "root": str(root),
            "total_files_scanned": len(files),
            "total_endpoints_analyzed": len(all_endpoints),
            "total_dangerous_endpoints": len(findings),
            "findings": [f.to_dict() for f in findings],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"JSON report written to {args.json}")

    return 1 if findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="dangerous-endpoints",
        description="Scan a source tree for dangerous API endpoints using Claude.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model to use")
    parser.add_argument("--concurrency", type=int, default=8, help="Max concurrent LLM requests")
    parser.add_argument("--extensions", nargs="+", help="Override the file extensions to scan (e.g. .py .js)")
    parser.add_argument("--ignore", nargs="+", help="Additional directory names to ignore")
    parser.add_argument("--json", help="Write a JSON report to this path")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print safe endpoints as well as dangerous ones")
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
