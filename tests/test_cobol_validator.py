"""
20 tests for benchmark/cobol_validator.py

Covers:
- Valid complete COBOL programs (pass through cleanly)
- Missing IDENTIFICATION DIVISION (ERROR)
- Missing PROCEDURE DIVISION (ERROR)
- Missing optional divisions (WARNING only)
- Valid PIC clauses: 9, X, V, S, COMP, COMP-3 variants
- Invalid PIC clause characters (ERROR)
- EVALUATE without END-EVALUATE (ERROR)
- Balanced EVALUATE/END-EVALUATE (clean)
- EVALUATE without WHEN OTHER (WARNING)
- PERFORM UNTIL without END-PERFORM (WARNING)
- Arithmetic verbs without ON SIZE ERROR (WARNING)
- Arithmetic verbs WITH ON SIZE ERROR (clean)
- score degradation with multiple issues
- ValidationResult helper methods
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure benchmark package is importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.cobol_validator import (
    COBOLValidator,
    ValidationResult,
    validate_cobol,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

MINIMAL_VALID = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       PROCEDURE DIVISION.
           STOP RUN.
"""

FULL_VALID = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-HOURS        PIC 9(3).
           01 WS-RATE         PIC 9(4)V99.
           01 WS-GROSS-PAY    PIC 9(6)V99.
           01 WS-NAME         PIC X(30).
       PROCEDURE DIVISION.
           COMPUTE WS-GROSS-PAY = WS-HOURS * WS-RATE
               ON SIZE ERROR
                   DISPLAY "OVERFLOW"
           END-COMPUTE
           STOP RUN.
"""

MISSING_ID_DIVISION = """\
       PROCEDURE DIVISION.
           STOP RUN.
"""

MISSING_PROC_DIVISION = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BROKEN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-X PIC X.
"""

MISSING_OPTIONAL_DIVISIONS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NODIVS.
       PROCEDURE DIVISION.
           STOP RUN.
"""

INVALID_PIC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BADPIC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-BAD PIC ZZZ9.
       PROCEDURE DIVISION.
           STOP RUN.
"""

VALID_PIC_VARIANTS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PICTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-ALPHA        PIC X(10).
           01 WS-NUM          PIC 9(5).
           01 WS-SIGNED       PIC S9(7)V99.
           01 WS-PACKED       PIC COMP-3.
           01 WS-BINARY       PIC COMP.
           01 WS-BINARY5      PIC COMP-5.
       PROCEDURE DIVISION.
           STOP RUN.
"""

EVALUATE_UNBALANCED = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UNBAL.
       PROCEDURE DIVISION.
           EVALUATE WS-CODE
               WHEN 1
                   DISPLAY "ONE"
               WHEN OTHER
                   DISPLAY "OTHER"
       STOP RUN.
"""

EVALUATE_BALANCED = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BALANCED.
       PROCEDURE DIVISION.
           EVALUATE WS-CODE
               WHEN 1
                   DISPLAY "ONE"
               WHEN OTHER
                   DISPLAY "OTHER"
           END-EVALUATE
           STOP RUN.
"""

EVALUATE_NO_WHEN_OTHER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOWHEN.
       PROCEDURE DIVISION.
           EVALUATE WS-CODE
               WHEN 1
                   DISPLAY "ONE"
               WHEN 2
                   DISPLAY "TWO"
           END-EVALUATE
           STOP RUN.
"""

PERFORM_UNTIL_NO_END = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PERFORM-TEST.
       PROCEDURE DIVISION.
           PERFORM PROCESS-LOOP UNTIL WS-COUNT = 10
           STOP RUN.
       PROCESS-LOOP.
           ADD 1 TO WS-COUNT
           EXIT.
"""

ADD_WITHOUT_SIZE_ERROR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ADDTEST.
       PROCEDURE DIVISION.
           ADD WS-A TO WS-B.
           STOP RUN.
"""

ADD_WITH_SIZE_ERROR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ADDSAFE.
       PROCEDURE DIVISION.
           ADD WS-A TO WS-B
               ON SIZE ERROR
                   DISPLAY "OVERFLOW"
           END-ADD
           STOP RUN.
"""

COMPUTE_WITHOUT_SIZE_ERROR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMPTEST.
       PROCEDURE DIVISION.
           COMPUTE WS-RESULT = WS-A * WS-B.
           STOP RUN.
"""

MULTIPLE_ISSUES = """\
       PROGRAM-ID. BROKEN-MULTI.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-BAD PIC QQQ.
       PROCEDURE DIVISION.
           ADD 1 TO WS-X.
           EVALUATE TRUE
               WHEN WS-X = 1
                   DISPLAY "ONE"
           STOP RUN.
"""

# ── Tests ──────────────────────────────────────────────────────────────────────


def test_minimal_valid_program_passes() -> None:
    """A minimal valid COBOL program should produce no errors."""
    result = validate_cobol(MINIMAL_VALID)
    assert result.is_valid, f"Expected valid but got errors: {result.issues}"
    assert result.error_count == 0


def test_full_valid_program_passes() -> None:
    """A fully structured COBOL program with safe arithmetic should pass cleanly."""
    result = validate_cobol(FULL_VALID)
    assert result.is_valid, f"Unexpected errors: {result.issues}"
    assert result.error_count == 0


def test_missing_identification_division_is_error() -> None:
    """Missing IDENTIFICATION DIVISION must produce an ERROR."""
    result = validate_cobol(MISSING_ID_DIVISION)
    assert result.error_count >= 1
    categories = [i.category for i in result.issues if i.severity == "ERROR"]
    assert "DIVISION_STRUCTURE" in categories


def test_missing_procedure_division_is_error() -> None:
    """Missing PROCEDURE DIVISION must produce an ERROR."""
    result = validate_cobol(MISSING_PROC_DIVISION)
    assert result.error_count >= 1
    categories = [i.category for i in result.issues if i.severity == "ERROR"]
    assert "DIVISION_STRUCTURE" in categories


def test_missing_optional_divisions_produces_warnings_only() -> None:
    """Missing ENVIRONMENT/DATA DIVISION should warn but not error."""
    result = validate_cobol(MISSING_OPTIONAL_DIVISIONS)
    assert result.error_count == 0
    warning_categories = [i.category for i in result.issues if i.severity == "WARNING"]
    assert "DIVISION_STRUCTURE" in warning_categories


def test_invalid_pic_clause_is_error() -> None:
    """Invalid PIC characters (Z) should produce a PIC_CLAUSE ERROR."""
    result = validate_cobol(INVALID_PIC)
    pic_errors = [i for i in result.issues if i.category == "PIC_CLAUSE" and i.severity == "ERROR"]
    assert len(pic_errors) >= 1, "Expected at least one PIC_CLAUSE error"


def test_valid_pic_9_and_x_pass() -> None:
    """Standard PIC 9 and X clauses should not trigger PIC errors."""
    result = validate_cobol(VALID_PIC_VARIANTS)
    pic_errors = [i for i in result.issues if i.category == "PIC_CLAUSE"]
    assert len(pic_errors) == 0, f"Unexpected PIC errors: {pic_errors}"


def test_valid_pic_signed_decimal_passes() -> None:
    """PIC S9(7)V99 should be recognised as valid."""
    source = MINIMAL_VALID.replace(
        "PROCEDURE DIVISION.",
        "DATA DIVISION.\n       WORKING-STORAGE SECTION.\n           01 WS-AMT PIC S9(7)V99.\n       PROCEDURE DIVISION.",
    )
    result = validate_cobol(source)
    pic_errors = [i for i in result.issues if i.category == "PIC_CLAUSE"]
    assert len(pic_errors) == 0


def test_valid_pic_comp_passes() -> None:
    """PIC COMP and PIC COMP-3 should be valid."""
    source = MINIMAL_VALID.replace(
        "PROCEDURE DIVISION.",
        "DATA DIVISION.\n       WORKING-STORAGE SECTION.\n           01 WS-A PIC COMP.\n           01 WS-B PIC COMP-3.\n       PROCEDURE DIVISION.",
    )
    result = validate_cobol(source)
    pic_errors = [i for i in result.issues if i.category == "PIC_CLAUSE"]
    assert len(pic_errors) == 0


def test_evaluate_without_end_evaluate_is_error() -> None:
    """Unbalanced EVALUATE/END-EVALUATE must produce an ERROR."""
    result = validate_cobol(EVALUATE_UNBALANCED)
    eval_errors = [i for i in result.issues if i.category == "EVALUATE_STRUCTURE" and i.severity == "ERROR"]
    assert len(eval_errors) >= 1


def test_balanced_evaluate_passes() -> None:
    """Balanced EVALUATE/END-EVALUATE should not produce an EVALUATE ERROR."""
    result = validate_cobol(EVALUATE_BALANCED)
    eval_errors = [i for i in result.issues if i.category == "EVALUATE_STRUCTURE" and i.severity == "ERROR"]
    assert len(eval_errors) == 0


def test_evaluate_without_when_other_is_warning() -> None:
    """EVALUATE without WHEN OTHER should produce a WARNING."""
    result = validate_cobol(EVALUATE_NO_WHEN_OTHER)
    eval_warnings = [i for i in result.issues if i.category == "EVALUATE_STRUCTURE" and i.severity == "WARNING"]
    assert len(eval_warnings) >= 1


def test_perform_until_without_end_perform_is_warning() -> None:
    """PERFORM UNTIL without END-PERFORM should produce a WARNING."""
    result = validate_cobol(PERFORM_UNTIL_NO_END)
    perf_warnings = [i for i in result.issues if i.category == "PERFORM_STRUCTURE"]
    assert len(perf_warnings) >= 1


def test_add_without_on_size_error_is_warning() -> None:
    """ADD without ON SIZE ERROR must produce an ARITHMETIC_OVERFLOW warning."""
    result = validate_cobol(ADD_WITHOUT_SIZE_ERROR)
    overflow_warnings = [i for i in result.issues if i.category == "ARITHMETIC_OVERFLOW"]
    assert len(overflow_warnings) >= 1


def test_add_with_on_size_error_passes() -> None:
    """ADD followed by ON SIZE ERROR must NOT produce an overflow warning."""
    result = validate_cobol(ADD_WITH_SIZE_ERROR)
    overflow_warnings = [i for i in result.issues if i.category == "ARITHMETIC_OVERFLOW"]
    assert len(overflow_warnings) == 0


def test_compute_without_on_size_error_is_warning() -> None:
    """COMPUTE without ON SIZE ERROR should produce ARITHMETIC_OVERFLOW warning."""
    result = validate_cobol(COMPUTE_WITHOUT_SIZE_ERROR)
    overflow_warnings = [i for i in result.issues if i.category == "ARITHMETIC_OVERFLOW"]
    assert len(overflow_warnings) >= 1


def test_multiple_issues_lowers_score() -> None:
    """A program with multiple errors/warnings should have score < 0.8."""
    result = validate_cobol(MULTIPLE_ISSUES)
    assert result.score < 0.8, f"Expected degraded score, got {result.score}"


def test_score_is_one_for_clean_program() -> None:
    """A clean valid program should have score == 1.0."""
    result = validate_cobol(FULL_VALID)
    assert result.score == 1.0, f"Expected score 1.0, got {result.score}"


def test_validation_result_error_count_property() -> None:
    """ValidationResult.error_count should count only ERROR severity issues."""
    result = ValidationResult(is_valid=False, score=0.5)
    result.add_issue("ERROR", "TEST", "error one")
    result.add_issue("ERROR", "TEST", "error two")
    result.add_issue("WARNING", "TEST", "a warning")
    assert result.error_count == 2
    assert result.warning_count == 1


def test_validate_cobol_convenience_function() -> None:
    """validate_cobol() convenience function should return the same result as COBOLValidator().validate()."""
    source = MINIMAL_VALID
    direct = COBOLValidator().validate(source)
    via_func = validate_cobol(source)
    assert direct.is_valid == via_func.is_valid
    assert direct.score == via_func.score
    assert len(direct.issues) == len(via_func.issues)
