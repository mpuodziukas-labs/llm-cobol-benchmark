#!/usr/bin/env python3
"""
run_benchmark.py — Run the LLM COBOL benchmark and produce comparison report.

Scans all llm_outputs/*.cob files, groups by (program, llm), runs the
extended validator, and prints a Markdown table to stdout and writes REPORT.md.

Usage:
    python3 validator/run_benchmark.py
    python3 validator/run_benchmark.py --json       # raw JSON instead of Markdown
    python3 validator/run_benchmark.py --out REPORT.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or validator/ directory
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_HERE))

from validator import analyze_file  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

LLM_OUTPUTS_DIR = _REPO_ROOT / "llm_outputs"
REPORT_PATH = _REPO_ROOT / "REPORT.md"

# Map filename prefixes to display names
PROGRAM_MAP = {
    "payroll": "payroll_calculation",
    "inventory": "inventory_update",
    "interest": "interest_calculation",
    "report": "report_generator",
    "validation": "data_validation",
}

LLM_MAP = {
    "gpt4": "GPT-4",
    "claude": "Claude",
    "llama": "Llama",
}


def _parse_output_filename(path: Path) -> tuple[str, str] | None:
    """
    Parse llm_outputs/<program>_<llm>.cob → (program_display, llm_display).
    Returns None if the filename doesn't match.
    """
    stem = path.stem  # e.g. "payroll_gpt4"
    for prefix, prog_name in PROGRAM_MAP.items():
        for suffix, llm_name in LLM_MAP.items():
            if stem == f"{prefix}_{suffix}":
                return prog_name, llm_name
    return None


def collect_results() -> list[dict]:  # type: ignore[type-arg]
    """Analyze all LLM output files and return sorted result records."""
    results = []
    if not LLM_OUTPUTS_DIR.exists():
        print(f"ERROR: {LLM_OUTPUTS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    for cob_file in sorted(LLM_OUTPUTS_DIR.glob("*.cob")):
        parsed = _parse_output_filename(cob_file)
        if parsed is None:
            continue
        program, llm = parsed
        analysis = analyze_file(cob_file)

        high = analysis.get("severity_counts", {}).get("HIGH", 0)
        medium = analysis.get("severity_counts", {}).get("MEDIUM", 0)
        low_count = analysis.get("severity_counts", {}).get("LOW", 0)
        total = analysis.get("bugs_found", 0)
        risk = analysis.get("risk_level", "UNKNOWN")

        pattern_ids = [p["pattern_id"] for p in analysis.get("patterns", [])]

        results.append({
            "program": program,
            "llm": llm,
            "bugs_detected": total,
            "critical": high,
            "high": high,
            "medium": medium,
            "low": low_count,
            "risk_level": risk,
            "pattern_ids": pattern_ids,
            "file": str(cob_file),
        })

    # Sort by program then LLM name
    order = {"GPT-4": 0, "Claude": 1, "Llama": 2}
    results.sort(key=lambda r: (r["program"], order.get(r["llm"], 99)))
    return results


def render_markdown(results: list[dict]) -> str:  # type: ignore[type-arg]
    lines = []
    lines.append("# LLM COBOL Quality Benchmark — Results")
    lines.append("")
    lines.append(
        "| Program | LLM | Bugs Detected | Critical | High | Medium | Risk Level |"
    )
    lines.append(
        "|---------|-----|:-------------:|:--------:|:----:|:------:|:----------:|"
    )

    for r in results:
        lines.append(
            f"| {r['program']} "
            f"| {r['llm']} "
            f"| {r['bugs_detected']} "
            f"| {r['critical']} "
            f"| {r['high']} "
            f"| {r['medium']} "
            f"| {r['risk_level']} |"
        )

    lines.append("")
    lines.append("## Key Finding")
    lines.append("")

    # Count files with >= 1 HIGH bug
    high_count = sum(1 for r in results if r["high"] >= 1)
    total_files = len(results)
    lines.append(
        f"**{high_count}/{total_files} LLM output files contained at least 1 HIGH severity bug** "
        "when tested against production COBOL patterns."
    )
    lines.append("")

    # Bug frequency by pattern
    from collections import Counter
    all_patterns: list[str] = []
    for r in results:
        all_patterns.extend(r["pattern_ids"])
    counter = Counter(all_patterns)

    lines.append("## Most Common Bug Patterns")
    lines.append("")
    lines.append("| Pattern | Occurrences Across All LLM Outputs |")
    lines.append("|---------|:-----------------------------------:|")
    for pattern, count in counter.most_common():
        lines.append(f"| `{pattern}` | {count} |")

    lines.append("")
    lines.append(
        "> IBM quotes $300/hr to fix these in production. "
        "This validator catches them in CI."
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM COBOL benchmark.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--out",
        metavar="FILE",
        type=Path,
        default=REPORT_PATH,
        help="Path to write Markdown report (default: REPORT.md)",
    )
    args = parser.parse_args()

    results = collect_results()

    if args.json:
        print(json.dumps(results, indent=2))
        return

    markdown = render_markdown(results)
    print(markdown)

    args.out.write_text(markdown, encoding="utf-8")
    print(f"\n[benchmark] Report written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
