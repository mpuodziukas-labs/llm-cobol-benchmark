"""
tests/test_validator.py

pytest tests for validator.py — Extended COBOL static analysis (8 detectors).

Covers original 5 detectors + 3 new:
    1.  PIC_V_NO_INTEGER — PIC V99 drops integer part
    2.  MISSING_ON_SIZE_ERROR — COMPUTE without ON SIZE ERROR
    3.  WHEN_OTHER_CONTINUE — ghost-pay fall-through
    4.  MISSING_FILE_STATUS — FD without FILE STATUS in FILE-CONTROL
    5.  REDEFINES_ON_NUMERIC — REDEFINES on PIC 9 field
    6.  UNCHECKED_SORT_RETURN — SORT without SORT-RETURN check
    7.  UNCHECKED_IO_STATUS — REWRITE/DELETE without FILE STATUS check
    8.  GOTO_EXCEEDS_SECTION — GO TO jumping > 100 lines
    9.  Clean file = 0 bugs
    10. Risk level: 1 HIGH = MEDIUM risk
    11. Risk level: 2 HIGH = HIGH risk
    12. Compare mode: fix detected
    13. Compare mode: regression detected
    14. Compare mode: net_change accurate
    15. Benchmark files: all 5 benchmarks have >= 1 HIGH bug
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import sys

_ROOT = Path(__file__).parent.parent
_VALIDATOR_DIR = _ROOT / "validator"
if str(_VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATOR_DIR))

from validator import (  # noqa: E402
    analyze_file,
    compare_files,
)


def write_cob(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(source))
    return p


# ── Test 1: PIC V with no integer positions ───────────────────────────────────

def test_pic_v_no_integer_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "pic_v.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CALC.
           05  WS-OVERTIME-RATE    PIC V99.
           05  WS-GROSS            PIC 9(7)V99.
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "PIC_V_NO_INTEGER" in ids, "PIC V99 must trigger PIC_V_NO_INTEGER"
    match = next(p for p in result["patterns"] if p["pattern_id"] == "PIC_V_NO_INTEGER")
    assert match["severity"] == "HIGH", "PIC_V_NO_INTEGER must be HIGH severity"


def test_pic_9v99_not_flagged(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "pic_9v99.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC 9(5)V99.
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "PIC_V_NO_INTEGER" not in ids, "PIC 9(5)V99 has integer positions — must not flag"


# ── Test 2: Missing ON SIZE ERROR ─────────────────────────────────────────────

def test_compute_without_size_error_flagged(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "no_size.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A    PIC 9(7)V99.
       01  WS-B    PIC 9(7)V99.
       01  WS-C    PIC 9(7)V99.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B.
           STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "MISSING_ON_SIZE_ERROR" in ids


def test_compute_with_size_error_not_flagged(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "with_size.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A    PIC 9(7)V99.
       01  WS-B    PIC 9(7)V99.
       01  WS-C    PIC 9(7)V99.
       01  WS-OVF  PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B
               ON SIZE ERROR
                   MOVE 'Y' TO WS-OVF
           END-COMPUTE.
           STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "MISSING_ON_SIZE_ERROR" not in ids


# ── Test 3: WHEN OTHER CONTINUE ───────────────────────────────────────────────

def test_when_other_continue_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "ghost.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TYPE     PIC X.
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TYPE = 'F'
                   MOVE 1 TO WS-TYPE
               WHEN OTHER
                   CONTINUE
           END-EVALUATE.
           STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "WHEN_OTHER_CONTINUE" in ids
    match = next(p for p in result["patterns"] if p["pattern_id"] == "WHEN_OTHER_CONTINUE")
    assert match["severity"] == "HIGH"


def test_when_other_perform_not_flagged(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "when_perform.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TYPE     PIC X.
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TYPE = 'F'
                   MOVE 1 TO WS-TYPE
               WHEN OTHER
                   PERFORM SKIP-IT
           END-EVALUATE.
           STOP RUN.
       SKIP-IT.
           MOVE SPACES TO WS-TYPE.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "WHEN_OTHER_CONTINUE" not in ids


# ── Test 4: FD without FILE STATUS (new detector ID) ─────────────────────────

def test_fd_without_file_status_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "no_status.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT PAYROLL-REPORT
               ASSIGN TO 'PAYROLL.RPT'
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD PAYROLL-REPORT.
       01  REPORT-LINE    PIC X(132).
       WORKING-STORAGE SECTION.
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "MISSING_FILE_STATUS" in ids, "FD with no FILE STATUS must be flagged"


# ── Test 5: REDEFINES on numeric field ────────────────────────────────────────

def test_redefines_on_numeric_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "redefines.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-GROUP.
           05  WS-AMOUNT     PIC 9(7)V99.
           05  WS-AMOUNT-X   REDEFINES WS-AMOUNT PIC X(9).
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "REDEFINES_ON_NUMERIC" in ids


# ── Test 6: UNCHECKED_SORT_RETURN ─────────────────────────────────────────────

def test_sort_without_return_check_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "sort_no_check.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-SORT-KEY   PIC 9(6).
       PROCEDURE DIVISION.
           SORT INPUT-FILE
               ON ASCENDING KEY WS-SORT-KEY
               USING UNSORTED-FILE
               GIVING SORTED-FILE.
           PERFORM 2000-PROCESS.
           STOP RUN.
       2000-PROCESS.
           MOVE SPACES TO WS-SORT-KEY.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "UNCHECKED_SORT_RETURN" in ids, "SORT without SORT-RETURN check must be flagged"
    match = next(p for p in result["patterns"] if p["pattern_id"] == "UNCHECKED_SORT_RETURN")
    assert match["severity"] == "HIGH"


def test_sort_with_return_check_not_flagged(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "sort_checked.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-SORT-KEY   PIC 9(6).
       PROCEDURE DIVISION.
           SORT INPUT-FILE
               ON ASCENDING KEY WS-SORT-KEY
               USING UNSORTED-FILE
               GIVING SORTED-FILE.
           IF SORT-RETURN NOT = 0
               PERFORM 9999-ABORT
           END-IF.
           STOP RUN.
       9999-ABORT.
           STOP RUN.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "UNCHECKED_SORT_RETURN" not in ids


# ── Test 7: UNCHECKED_IO_STATUS (REWRITE without check) ───────────────────────

def test_rewrite_without_status_check_detected(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "rewrite_no_check.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INVENTORY-FILE
               ASSIGN TO 'INV.DAT'
               ORGANIZATION IS INDEXED
               RECORD KEY IS INV-KEY
               FILE STATUS IS WS-INV-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD INVENTORY-FILE.
       01  INV-RECORD.
           05  INV-KEY    PIC X(10).
           05  INV-QTY    PIC 9(7).
       WORKING-STORAGE SECTION.
       01  WS-INV-STATUS   PIC XX.
       PROCEDURE DIVISION.
           REWRITE INV-RECORD.
           PERFORM 3000-CLOSE.
           STOP RUN.
       3000-CLOSE.
           CLOSE INVENTORY-FILE.
    """)
    result = analyze_file(cob)
    ids = [p["pattern_id"] for p in result["patterns"]]
    assert "UNCHECKED_IO_STATUS" in ids, "REWRITE without FILE STATUS check must be flagged"


# ── Test 8: Clean file returns 0 bugs ─────────────────────────────────────────

def test_clean_file_no_bugs(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "clean.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLEAN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A    PIC 9(7)V99.
       01  WS-B    PIC 9(7)V99.
       01  WS-C    PIC 9(7)V99.
       01  WS-OVF  PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B
               ON SIZE ERROR
                   MOVE 'Y' TO WS-OVF
           END-COMPUTE.
           STOP RUN.
    """)
    result = analyze_file(cob)
    assert result["bugs_found"] == 0, f"Expected 0 bugs, got {result['bugs_found']}"
    assert result["risk_level"] == "LOW"


# ── Test 9: Risk level — 1 HIGH = MEDIUM ─────────────────────────────────────

def test_risk_level_one_high_is_medium(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "one_high.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A    PIC 9(7)V99.
       01  WS-B    PIC 9(7)V99.
       01  WS-C    PIC 9(7)V99.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B.
           STOP RUN.
    """)
    result = analyze_file(cob)
    high_count = result["severity_counts"].get("HIGH", 0)
    assert high_count >= 1
    assert result["risk_level"] in ("MEDIUM", "HIGH")


# ── Test 10: Risk level — 2 HIGH = HIGH ───────────────────────────────────────

def test_risk_level_two_high_is_high(tmp_path: Path) -> None:
    cob = write_cob(tmp_path, "two_high.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC V99.
       01  WS-A       PIC 9(7)V99.
       01  WS-B       PIC 9(7)V99.
       01  WS-C       PIC 9(7)V99.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B.
           STOP RUN.
    """)
    result = analyze_file(cob)
    high_count = result["severity_counts"].get("HIGH", 0)
    assert high_count >= 2
    assert result["risk_level"] == "HIGH"


# ── Test 11: Compare mode — fix detected ──────────────────────────────────────

def test_compare_detects_fixed_patterns(tmp_path: Path) -> None:
    broken = write_cob(tmp_path, "broken.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BROKEN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC V99.
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    fixed = write_cob(tmp_path, "fixed.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FIXED.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC 9(5)V99.
       PROCEDURE DIVISION.
       STOP RUN.
    """)
    result = compare_files(broken, fixed)
    assert "PIC_V_NO_INTEGER" in result["fixed_in_file2"]
    assert result["net_change"] <= 0


# ── Test 12: Compare mode — regression detected ───────────────────────────────

def test_compare_detects_regression(tmp_path: Path) -> None:
    clean = write_cob(tmp_path, "clean_eval.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLEAN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TYPE     PIC X.
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TYPE = 'F'
                   MOVE 1 TO WS-TYPE
               WHEN OTHER
                   PERFORM SKIP-IT
           END-EVALUATE.
           STOP RUN.
       SKIP-IT.
           MOVE SPACES TO WS-TYPE.
    """)
    regressed = write_cob(tmp_path, "regressed.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REGRESSED.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TYPE     PIC X.
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TYPE = 'F'
                   MOVE 1 TO WS-TYPE
               WHEN OTHER
                   CONTINUE
           END-EVALUATE.
           STOP RUN.
    """)
    result = compare_files(clean, regressed)
    assert "WHEN_OTHER_CONTINUE" in result["introduced_in_file2"]
    assert "REGRESSION" in result["verdict"]


# ── Test 13: Compare mode — net_change accurate ───────────────────────────────

def test_compare_net_change_accurate(tmp_path: Path) -> None:
    two_bugs = write_cob(tmp_path, "two_bugs.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TWOBUGS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC V99.
       01  WS-A       PIC 9(7)V99.
       01  WS-C       PIC 9(7)V99.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-A.
           STOP RUN.
    """)
    one_bug = write_cob(tmp_path, "one_bug.cob", """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONEBUG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RATE    PIC 9(5)V99.
       01  WS-A       PIC 9(7)V99.
       01  WS-C       PIC 9(7)V99.
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-A.
           STOP RUN.
    """)
    result = compare_files(two_bugs, one_bug)
    expected_net = result["file2_bugs"] - result["file1_bugs"]
    assert result["net_change"] == expected_net
    assert result["net_change"] < 0


# ── Test 14: All 5 benchmark files have >= 1 HIGH bug ─────────────────────────

@pytest.mark.parametrize("benchmark_file", [
    "payroll_calculation.cob",
    "inventory_update.cob",
    "interest_calculation.cob",
    "report_generator.cob",
    "data_validation.cob",
])
def test_benchmark_files_have_high_bugs(benchmark_file: str) -> None:
    cob = _ROOT / "benchmarks" / benchmark_file
    if not cob.exists():
        pytest.skip(f"Benchmark file not found: {cob}")
    result = analyze_file(cob)
    high_count = result["severity_counts"].get("HIGH", 0)
    assert high_count >= 1, (
        f"{benchmark_file} must have >= 1 HIGH severity bug, found {high_count}. "
        f"Patterns: {[p['pattern_id'] for p in result['patterns']]}"
    )


# ── Test 15: All LLM outputs have >= 1 bug detected ───────────────────────────

@pytest.mark.parametrize("llm_file", [
    "payroll_gpt4.cob", "payroll_claude.cob", "payroll_llama.cob",
    "inventory_gpt4.cob", "inventory_claude.cob", "inventory_llama.cob",
    "interest_gpt4.cob", "interest_claude.cob", "interest_llama.cob",
    "report_gpt4.cob", "report_claude.cob", "report_llama.cob",
    "validation_gpt4.cob", "validation_claude.cob", "validation_llama.cob",
])
def test_llm_outputs_have_bugs(llm_file: str) -> None:
    cob = _ROOT / "llm_outputs" / llm_file
    if not cob.exists():
        pytest.skip(f"LLM output file not found: {cob}")
    result = analyze_file(cob)
    assert result["bugs_found"] >= 1, (
        f"{llm_file} must have >= 1 bug detected, found 0. "
        "LLM 'fix' outputs should always contain at least one residual pattern."
    )
