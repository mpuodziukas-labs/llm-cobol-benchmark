#!/usr/bin/env python3
"""
validator.py — Extended COBOL static analysis for the LLM benchmark.

Extends the original cobol-demo validate.py with 3 additional detectors:
    - MISSING_FILE_STATUS: FD declared with no FILE STATUS in FILE-CONTROL
    - UNCHECKED_SORT_RETURN: SORT verb with no AT END / ON SIZE ERROR
    - GOTO_EXCEEDS_SECTION: GO TO targeting a paragraph outside current section

Original detectors (5):
    - MISSING_ON_SIZE_ERROR
    - FD_WITHOUT_FILE_STATUS  (aliased as MISSING_FILE_STATUS in extended mode)
    - REDEFINES_ON_NUMERIC
    - PIC_V_NO_INTEGER
    - WHEN_OTHER_CONTINUE

Usage:
    python3 validator.py --file FILE [--report]
    python3 validator.py --compare FILE1 FILE2 [--report]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── Pattern definition ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PatternMatch:
    """A single detected pattern in a COBOL source file."""
    pattern_id: str
    line_number: int
    line_text: str
    description: str
    severity: str  # "HIGH" | "MEDIUM" | "LOW"
    financial_risk: str


def _strip_comment(line: str) -> str:
    idx = line.find("*>")
    if idx >= 0:
        return line[:idx]
    return line


def _is_comment_line(line: str) -> bool:
    stripped = line.rstrip("\n")
    if len(stripped) >= 7 and stripped[6] in ("*", "/"):
        return True
    if stripped.lstrip().startswith("*>"):
        return True
    return False


def _clean_lines(raw_lines: list[str]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for i, raw in enumerate(raw_lines, start=1):
        if _is_comment_line(raw):
            continue
        clean = _strip_comment(raw).upper().rstrip()
        if not clean.strip():
            continue
        result.append((i, clean))
    return result


# ── Original 5 checkers (carried over from cobol-demo) ───────────────────────

def check_missing_on_size_error(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    text_upper = [t for _, t in lines]
    linenos = [n for n, _ in lines]

    def _verb_col(text: str) -> int:
        return len(text) - len(text.lstrip())

    i = 0
    while i < len(text_upper):
        line = text_upper[i]
        if re.search(r"\bCOMPUTE\b", line) and not re.search(r"\bEND-COMPUTE\b", line):
            compute_col = _verb_col(line)
            found_size_error = False
            j = i + 1
            while j < len(text_upper):
                segment = text_upper[j]
                if re.search(r"\bON SIZE ERROR\b", segment):
                    found_size_error = True
                    break
                if re.search(r"\bEND-COMPUTE\b", segment):
                    break
                if re.search(
                    r"\b(MOVE|PERFORM|READ|WRITE|EVALUATE|STOP|CLOSE|OPEN|ADD|SUBTRACT|DIVIDE|MULTIPLY|IF)\b",
                    segment,
                ) and _verb_col(segment) <= compute_col and j > i:
                    break
                j += 1
            if not found_size_error:
                raw_text = raw_lines[linenos[i] - 1].rstrip()
                matches.append(PatternMatch(
                    pattern_id="MISSING_ON_SIZE_ERROR",
                    line_number=linenos[i],
                    line_text=raw_text,
                    description=(
                        "COMPUTE statement has no ON SIZE ERROR handler. "
                        "PIC field overflow silently truncates. No ABEND is raised."
                    ),
                    severity="HIGH",
                    financial_risk=(
                        "Silent truncation at PIC 9(7)V99 boundary ($9,999,999.99). "
                        "Affects high-earners and large monetary fields."
                    ),
                ))
        i += 1
    return matches


def check_fd_without_file_status(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    file_status_names: set[str] = set()
    fd_names: list[tuple[int, str]] = []

    in_file_control = False
    current_select: Optional[str] = None
    has_status = False

    for lineno, text in lines:
        stripped = text.strip()
        if re.search(r"\bFILE-CONTROL\b", stripped):
            in_file_control = True
        if in_file_control and re.search(r"\b(DATA DIVISION|I-O-CONTROL)\b", stripped):
            if current_select and has_status:
                file_status_names.add(current_select)
            in_file_control = False
            current_select = None
            has_status = False
        if in_file_control:
            m = re.search(r"\bSELECT\s+(\S+)", stripped)
            if m:
                if current_select and has_status:
                    file_status_names.add(current_select)
                current_select = m.group(1).rstrip(".")
                has_status = False
            if re.search(r"\bFILE STATUS\b", stripped):
                has_status = True

    if current_select and has_status:
        file_status_names.add(current_select)

    for lineno, text in lines:
        m = re.match(r"\s*FD\s+(\S+)", text)
        if m:
            fd_name = m.group(1).rstrip(".")
            fd_names.append((lineno, fd_name))

    for lineno, fd_name in fd_names:
        if fd_name not in file_status_names:
            raw_text = raw_lines[lineno - 1].rstrip()
            matches.append(PatternMatch(
                pattern_id="MISSING_FILE_STATUS",
                line_number=lineno,
                line_text=raw_text,
                description=(
                    f"File '{fd_name}' declared in FD section but has no FILE STATUS "
                    "clause in FILE-CONTROL. I/O errors are silently ignored."
                ),
                severity="MEDIUM",
                financial_risk=(
                    "I/O failure mid-run produces partial output. "
                    "Restart without root cause fix risks duplicate processing."
                ),
            ))
    return matches


def check_redefines_on_numeric(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    numeric_fields: dict[str, int] = {}
    for lineno, text in lines:
        m = re.search(r"\b(\d+)\s+(\S+)\s+.*\bREDEFINES\s+(\S+)", text)
        if m:
            redefines_target = m.group(3).rstrip(".")
            if redefines_target in numeric_fields:
                raw_text = raw_lines[lineno - 1].rstrip()
                matches.append(PatternMatch(
                    pattern_id="REDEFINES_ON_NUMERIC",
                    line_number=lineno,
                    line_text=raw_text,
                    description=(
                        f"REDEFINES applied to '{redefines_target}' which was declared "
                        "as a numeric (PIC 9) field. On IBM mainframes with COMP-3 "
                        "packed decimal storage, redefining corrupts byte interpretation."
                    ),
                    severity="HIGH",
                    financial_risk=(
                        "Monetary fields treated as alphanumeric produce garbage values "
                        "in reports without raising any error."
                    ),
                ))
        pic_m = re.search(r"\b(\S+)\s+PIC\s+(9[\d(V]*)", text)
        if pic_m:
            numeric_fields[pic_m.group(1).rstrip(".")] = lineno
    return matches


def check_pic_v_no_integer(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    pic_v_pattern = re.compile(r"\bPIC\s+(V9[\d()*]*)\b")
    for lineno, text in lines:
        m = pic_v_pattern.search(text)
        if m:
            raw_text = raw_lines[lineno - 1].rstrip()
            matches.append(PatternMatch(
                pattern_id="PIC_V_NO_INTEGER",
                line_number=lineno,
                line_text=raw_text,
                description=(
                    f"Field declared as '{m.group(1)}' — pure decimal, no integer "
                    "positions. Any value >= 1 silently truncates the integer portion."
                ),
                severity="HIGH",
                financial_risk=(
                    "Classic FLSA violation vector. Overtime rates stored in PIC V99 "
                    "produce $0.00 overtime pay. "
                    "At 1,000 employees × $187.50 = $187,500 underpayment per period."
                ),
            ))
    return matches


def check_when_other_continue(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    i = 0
    while i < len(lines):
        lineno, text = lines[i]
        if re.search(r"\bWHEN\s+OTHER\b", text):
            j = i + 1
            while j < len(lines) and not lines[j][1].strip():
                j += 1
            if j < len(lines) and re.search(r"\bCONTINUE\b", lines[j][1]):
                raw_text = raw_lines[lineno - 1].rstrip()
                matches.append(PatternMatch(
                    pattern_id="WHEN_OTHER_CONTINUE",
                    line_number=lineno,
                    line_text=raw_text,
                    description=(
                        "WHEN OTHER CONTINUE in EVALUATE block. Unrecognised input "
                        "values fall through without reinitialising WORKING-STORAGE. "
                        "Values from the previous iteration remain active."
                    ),
                    severity="HIGH",
                    financial_risk=(
                        "Ghost payroll: invalid records write previous record's data. "
                        "50 invalid records after a $5,000/week employee "
                        "= $250,000 phantom payroll."
                    ),
                ))
        i += 1
    return matches


# ── 3 New detectors ──────────────────────────────────────────────────────────

def check_unchecked_sort_return(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    """
    Detect SORT verb without AT END or ON SIZE ERROR handling.

    COBOL SORT returns a SORT-RETURN special register (0=success, 16=fatal).
    LLMs routinely omit the check. A failed SORT produces no output file
    and the program continues processing with an empty dataset.
    """
    matches: list[PatternMatch] = []
    i = 0
    while i < len(lines):
        lineno, text = lines[i]
        if re.search(r"\bSORT\b", text) and not re.search(r"\bSORT-RETURN\b", text):
            # Scan ahead for AT END or SORT-RETURN check within 20 lines
            found_check = False
            j = i + 1
            scan_limit = min(i + 20, len(lines))
            while j < scan_limit:
                _, seg = lines[j]
                if re.search(r"\b(AT END|SORT-RETURN|ON SIZE ERROR)\b", seg):
                    found_check = True
                    break
                # New top-level verb outside SORT block ends scan
                if re.search(r"\b(PERFORM|OPEN|CLOSE|STOP RUN|MERGE)\b", seg):
                    break
                j += 1
            if not found_check:
                raw_text = raw_lines[lineno - 1].rstrip()
                matches.append(PatternMatch(
                    pattern_id="UNCHECKED_SORT_RETURN",
                    line_number=lineno,
                    line_text=raw_text,
                    description=(
                        "SORT verb used without checking SORT-RETURN special register. "
                        "A return code of 16 indicates a fatal sort failure. "
                        "The program continues with an empty or partial output file "
                        "and no diagnostic is produced."
                    ),
                    severity="HIGH",
                    financial_risk=(
                        "Failed sort produces empty dataset processed as if valid. "
                        "Downstream batch jobs process zero records, producing "
                        "zero-balance reports or no disbursements with no alert."
                    ),
                ))
        i += 1
    return matches


def check_missing_file_status_check(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    """
    Detect REWRITE or DELETE statements not followed by a FILE STATUS check.

    LLMs commonly add REWRITE/DELETE but omit the mandatory status check.
    A locked record (STATUS=91) or disk full (STATUS=34) continues silently.
    This is distinct from the FD-level check — this catches procedure-level omissions.
    """
    matches: list[PatternMatch] = []
    i = 0
    while i < len(lines):
        lineno, text = lines[i]
        if re.search(r"\b(REWRITE|DELETE)\b", text):
            # Scan ahead up to 8 lines for an IF / EVALUATE checking WS-*-STATUS
            found_check = False
            j = i + 1
            scan_limit = min(i + 8, len(lines))
            while j < scan_limit:
                _, seg = lines[j]
                # Accept: IF WS-xxx-STATUS, EVALUATE WS-xxx-STATUS, or NOT SUCCESS
                if re.search(
                    r"\b(IF\s+WS-\w*STATUS|EVALUATE\s+WS-\w*STATUS|NOT\s+\w*SUCCESS)\b",
                    seg,
                ):
                    found_check = True
                    break
                # Stop at next I/O verb
                if re.search(r"\b(READ|WRITE|REWRITE|DELETE|OPEN|CLOSE)\b", seg):
                    break
                j += 1
            if not found_check:
                raw_text = raw_lines[lineno - 1].rstrip()
                matches.append(PatternMatch(
                    pattern_id="UNCHECKED_IO_STATUS",
                    line_number=lineno,
                    line_text=raw_text,
                    description=(
                        "REWRITE or DELETE statement not followed by FILE STATUS check. "
                        "Record locking (STATUS=91), disk full (STATUS=34), or "
                        "concurrent access failures are silently ignored. "
                        "The program continues with unverified data integrity."
                    ),
                    severity="MEDIUM",
                    financial_risk=(
                        "Silent REWRITE failure in inventory or financial files "
                        "leaves records in inconsistent state. "
                        "Audit trail shows successful run while data is corrupted."
                    ),
                ))
        i += 1
    return matches


def check_goto_exceeds_section(
    lines: list[tuple[int, str]], raw_lines: list[str]
) -> list[PatternMatch]:
    """
    Detect GO TO statements targeting paragraphs that appear to be outside
    the current section boundary (cross-section GO TO).

    Cross-section GO TO is valid COBOL but is a well-known maintenance hazard.
    LLMs generate cross-section GO TO when simplifying loop logic and fail
    to annotate or restructure with PERFORM, leaving unstructured control flow.
    """
    matches: list[PatternMatch] = []

    # Collect all paragraph/section names (lines matching ^DDDD-WORD. pattern at col 7)
    section_labels: dict[str, int] = {}  # label → line number
    for lineno, text in lines:
        # COBOL paragraph: starts near column 7, word-dot pattern
        if re.match(r"\s{0,8}[A-Z0-9][A-Z0-9-]+\.", text) and not re.search(
            r"\b(PERFORM|MOVE|COMPUTE|IF|EVALUATE|READ|WRITE|STOP|OPEN|CLOSE|ADD|SUBTRACT|MULTIPLY|DIVIDE|GO|INITIALIZE|INSPECT|CALL|SORT)\b",
            text,
        ):
            label = text.strip().rstrip(".")
            section_labels[label] = lineno

    for lineno, text in lines:
        m = re.search(r"\bGO\s+TO\s+(\S+)", text)
        if m:
            target = m.group(1).rstrip(".")
            if target in section_labels:
                target_line = section_labels[target]
                distance = abs(target_line - lineno)
                if distance > 100:  # heuristic: cross-section if > 100 lines away
                    raw_text = raw_lines[lineno - 1].rstrip()
                    matches.append(PatternMatch(
                        pattern_id="GOTO_EXCEEDS_SECTION",
                        line_number=lineno,
                        line_text=raw_text,
                        description=(
                            f"GO TO {target} targets a paragraph {distance} lines away. "
                            "This cross-section jump bypasses intervening WORKING-STORAGE "
                            "initialization and cleanup code. "
                            "LLMs generate this pattern when collapsing loop structures."
                        ),
                        severity="MEDIUM",
                        financial_risk=(
                            "Skipped initialization leaves monetary totals from a "
                            "previous iteration active. On multi-section batch jobs, "
                            "cross-section GO TO has caused $50k+ reconciliation gaps."
                        ),
                    ))
    return matches


# ── Risk scoring ──────────────────────────────────────────────────────────────

def compute_risk_level(patterns: list[PatternMatch]) -> str:
    high = sum(1 for p in patterns if p.severity == "HIGH")
    medium = sum(1 for p in patterns if p.severity == "MEDIUM")
    if high >= 2:
        return "HIGH"
    if high == 1 or medium >= 3:
        return "MEDIUM"
    if medium >= 1:
        return "LOW"
    return "LOW"


# ── Main analysis ─────────────────────────────────────────────────────────────

def analyze_file(path: Path) -> dict:  # type: ignore[type-arg]
    """Run all 8 checks against a COBOL source file and return a result dict."""
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError as exc:
        return {"error": str(exc), "path": str(path)}

    cleaned = _clean_lines(raw_lines)

    patterns: list[PatternMatch] = []
    patterns.extend(check_missing_on_size_error(cleaned, raw_lines))
    patterns.extend(check_fd_without_file_status(cleaned, raw_lines))
    patterns.extend(check_redefines_on_numeric(cleaned, raw_lines))
    patterns.extend(check_pic_v_no_integer(cleaned, raw_lines))
    patterns.extend(check_when_other_continue(cleaned, raw_lines))
    patterns.extend(check_unchecked_sort_return(cleaned, raw_lines))
    patterns.extend(check_missing_file_status_check(cleaned, raw_lines))
    patterns.extend(check_goto_exceeds_section(cleaned, raw_lines))

    risk_level = compute_risk_level(patterns)

    severity_counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in patterns:
        severity_counts[p.severity] = severity_counts.get(p.severity, 0) + 1

    return {
        "file": str(path),
        "bugs_found": len(patterns),
        "risk_level": risk_level,
        "severity_counts": severity_counts,
        "patterns": [asdict(p) for p in patterns],
    }


# ── Comparison mode ───────────────────────────────────────────────────────────

def compare_files(path1: Path, path2: Path) -> dict:  # type: ignore[type-arg]
    result1 = analyze_file(path1)
    result2 = analyze_file(path2)

    ids1: set[str] = {p["pattern_id"] for p in result1.get("patterns", [])}
    ids2: set[str] = {p["pattern_id"] for p in result2.get("patterns", [])}

    fixed = sorted(ids1 - ids2)
    introduced = sorted(ids2 - ids1)
    remaining = sorted(ids1 & ids2)

    return {
        "file1": str(path1),
        "file2": str(path2),
        "file1_bugs": result1.get("bugs_found", 0),
        "file2_bugs": result2.get("bugs_found", 0),
        "fixed_in_file2": fixed,
        "introduced_in_file2": introduced,
        "remaining_in_both": remaining,
        "net_change": result2.get("bugs_found", 0) - result1.get("bugs_found", 0),
        "verdict": _compare_verdict(fixed, introduced, remaining),
        "file1_detail": result1,
        "file2_detail": result2,
    }


def _compare_verdict(
    fixed: list[str], introduced: list[str], remaining: list[str]
) -> str:
    if not introduced and not remaining:
        return "CLEAN: all detected patterns were fixed, none introduced."
    if introduced:
        return (
            f"REGRESSION: {len(introduced)} new pattern(s) introduced "
            f"({', '.join(introduced)}), {len(fixed)} fixed, {len(remaining)} remaining."
        )
    if remaining:
        return (
            f"PARTIAL FIX: {len(fixed)} pattern(s) fixed, "
            f"{len(remaining)} remaining, 0 introduced."
        )
    return "NO CHANGE."


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="COBOL static analysis — extended validator for LLM benchmark.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", metavar="FILE", type=Path)
    group.add_argument("--compare", nargs=2, metavar=("FILE1", "FILE2"), type=Path)
    parser.add_argument("--report", action="store_true")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.file is not None:
        result = analyze_file(args.file)
    else:
        result = compare_files(args.compare[0], args.compare[1])

    indent = 2 if args.report else None
    print(json.dumps(result, indent=indent))

    if "bugs_found" in result and result["bugs_found"] > 0:
        return 1
    if "introduced_in_file2" in result and result["introduced_in_file2"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
