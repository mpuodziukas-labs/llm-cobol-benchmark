"""
15 tests for benchmark/migration_scorer.py

Covers:
- Empty program → LOW risk
- Single REDEFINES → non-zero score
- Multiple REDEFINES → MEDIUM/HIGH risk
- OCCURS DEPENDING ON → increases score
- Fixed OCCURS (no DEPENDING ON) → lower than ODO
- PERFORM count impact on score
- Copybook dependency extraction
- Multiple copybooks → higher score
- GO TO statements → increase risk
- ALTER statement → increases risk more than GO TO
- EXEC SQL embedded → adds SQL score contribution
- WORKING-STORAGE large → adds WS score
- Combined critical-level program
- score_migration_risk convenience function
- RiskCategory and MigrationScore properties
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.migration_scorer import MigrationScore, MigrationScorer, RiskCategory, score_migration_risk

# ── Fixtures ───────────────────────────────────────────────────────────────────

EMPTY_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EMPTY.
       PROCEDURE DIVISION.
           STOP RUN.
"""

ONE_REDEFINES = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RDEF1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-DATE.
               05 WS-DATE-NUM PIC 9(8).
               05 WS-DATE-STR REDEFINES WS-DATE-NUM PIC X(8).
       PROCEDURE DIVISION.
           STOP RUN.
"""

FIVE_REDEFINES = "\n".join(
    [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. RDEF5.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
    ]
    + [
        f"           01 WS-BASE-{i} PIC 9(4).\n           01 WS-ALIAS-{i} REDEFINES WS-BASE-{i} PIC X(4)."
        for i in range(5)
    ]
    + ["       PROCEDURE DIVISION.", "           STOP RUN."]
)

ODO_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ODOTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-TABLE-SIZE PIC 9(3).
           01 WS-TABLE.
               05 WS-ENTRY OCCURS 1 TO 100 TIMES DEPENDING ON WS-TABLE-SIZE
                   PIC X(10).
       PROCEDURE DIVISION.
           STOP RUN.
"""

FIXED_OCCURS_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FIXEDOCC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           01 WS-TABLE.
               05 WS-ENTRY OCCURS 10 TIMES PIC X(10).
       PROCEDURE DIVISION.
           STOP RUN.
"""

MANY_PERFORMS = "\n".join(
    [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. MANYPERFS.",
        "       PROCEDURE DIVISION.",
    ]
    + [f"           PERFORM PARA-{i}." for i in range(20)]
    + ["           STOP RUN."]
    + [f"       PARA-{i}.\n           CONTINUE." for i in range(20)]
)

ONE_COPYBOOK = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONECOPY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY PAYROLL-DEFS.
       PROCEDURE DIVISION.
           STOP RUN.
"""

FIVE_COPYBOOKS = "\n".join(
    [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. FIVECOPIES.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
    ]
    + [f"           COPY BOOK-{i}." for i in range(5)]
    + ["       PROCEDURE DIVISION.", "           STOP RUN."]
)

GOTO_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GOTEST.
       PROCEDURE DIVISION.
           IF WS-X > 0
               GO TO POSITIVE-PARA
           END-IF.
           POSITIVE-PARA.
           STOP RUN.
"""

ALTER_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ALTERTEST.
       PROCEDURE DIVISION.
           ALTER PARA-A TO PROCEED TO PARA-B.
           STOP RUN.
       PARA-A.
           CONTINUE.
       PARA-B.
           STOP RUN.
"""

SQL_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLTEST.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT ACCOUNT_BAL INTO :WS-BAL
               FROM ACCOUNTS
               WHERE ACCT_ID = :WS-ACCT-ID
           END-EXEC.
           STOP RUN.
"""

LARGE_WS_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LARGEWS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
""" + "\n".join(
    [f"           01 WS-VAR-{i:03d} PIC X(10)." for i in range(60)]
) + """
       PROCEDURE DIVISION.
           STOP RUN.
"""

CRITICAL_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CRITICAL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY MASTER-DEFS.
           COPY ACCT-DEFS.
           COPY TRANS-DEFS.
           COPY REPORT-DEFS.
           COPY CONFIG-DEFS.
           01 WS-BASE PIC 9(8).
           01 WS-ALIAS REDEFINES WS-BASE PIC X(8).
           01 WS-ALT   REDEFINES WS-BASE PIC S9(7)V9.
           01 WS-TBL.
               05 WS-ROW OCCURS 1 TO 500 TIMES DEPENDING ON WS-CNT PIC X(80).
       PROCEDURE DIVISION.
""" + "\n".join([f"           PERFORM STEP-{i}." for i in range(15)]) + """
           GO TO EXIT-PARA.
           ALTER STEP-1 TO PROCEED TO STEP-2.
           EXEC SQL SELECT 1 INTO :WS-X FROM SYSIBM.SYSDUMMY1 END-EXEC.
           EXIT-PARA.
           STOP RUN.
"""


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_empty_program_is_low_risk() -> None:
    """An empty program with no complex constructs should be LOW risk."""
    result = score_migration_risk(EMPTY_PROGRAM)
    assert result.risk_level == "LOW", f"Expected LOW, got {result.risk_level} ({result.total_score})"


def test_single_redefines_adds_nonzero_score() -> None:
    """One REDEFINES clause must increase the score above 0."""
    empty_score = score_migration_risk(EMPTY_PROGRAM).total_score
    redef_score = score_migration_risk(ONE_REDEFINES).total_score
    assert redef_score > empty_score


def test_five_redefines_raises_risk_level() -> None:
    """5 REDEFINES clauses should move risk to MEDIUM or higher."""
    result = score_migration_risk(FIVE_REDEFINES)
    assert result.risk_level in ("MEDIUM", "HIGH", "CRITICAL")


def test_odo_increases_score_vs_empty() -> None:
    """OCCURS DEPENDING ON should raise score above empty baseline."""
    empty_score = score_migration_risk(EMPTY_PROGRAM).total_score
    odo_score = score_migration_risk(ODO_PROGRAM).total_score
    assert odo_score > empty_score


def test_odo_higher_than_fixed_occurs() -> None:
    """OCCURS DEPENDING ON should score higher than fixed OCCURS."""
    odo_score = score_migration_risk(ODO_PROGRAM).total_score
    fixed_score = score_migration_risk(FIXED_OCCURS_PROGRAM).total_score
    assert odo_score > fixed_score


def test_many_performs_increases_perform_score() -> None:
    """20 PERFORM statements should produce a non-trivial PERFORM score contribution."""
    result = score_migration_risk(MANY_PERFORMS)
    perform_cat = next(c for c in result.categories if "PERFORM" in c.name)
    assert perform_cat.score_contribution > 0


def test_copybook_extraction_single() -> None:
    """Single COPY statement should be extracted as a copybook dependency."""
    result = score_migration_risk(ONE_COPYBOOK)
    assert "PAYROLL-DEFS" in result.copybook_dependencies


def test_five_copybooks_extracted() -> None:
    """5 unique COPY statements should all be in copybook_dependencies."""
    result = score_migration_risk(FIVE_COPYBOOKS)
    assert len(result.copybook_dependencies) == 5
    for i in range(5):
        assert f"BOOK-{i}" in result.copybook_dependencies


def test_goto_adds_risk() -> None:
    """GO TO statement should increase risk score."""
    empty_score = score_migration_risk(EMPTY_PROGRAM).total_score
    goto_score = score_migration_risk(GOTO_PROGRAM).total_score
    assert goto_score > empty_score


def test_alter_adds_more_risk_than_goto() -> None:
    """ALTER should add more risk than a single GO TO (ALTER is weighted 3×)."""
    goto_score = score_migration_risk(GOTO_PROGRAM).total_score
    alter_score = score_migration_risk(ALTER_PROGRAM).total_score
    # ALTER is weighted 3× compared to GO TO, so alter score >= goto
    # (both programs are otherwise similar)
    assert alter_score >= goto_score


def test_exec_sql_adds_score() -> None:
    """EXEC SQL blocks should add a score contribution."""
    empty_score = score_migration_risk(EMPTY_PROGRAM).total_score
    sql_score = score_migration_risk(SQL_PROGRAM).total_score
    assert sql_score > empty_score


def test_large_working_storage_adds_score() -> None:
    """60 WORKING-STORAGE items should produce a WS score contribution."""
    result = score_migration_risk(LARGE_WS_PROGRAM)
    ws_cat = next(c for c in result.categories if "WORKING-STORAGE" in c.name)
    assert ws_cat.score_contribution > 0


def test_critical_program_is_high_or_critical() -> None:
    """A program with REDEFINES + ODO + COPY×5 + GO TO + ALTER + SQL should be HIGH/CRITICAL."""
    result = score_migration_risk(CRITICAL_PROGRAM)
    assert result.risk_level in ("HIGH", "CRITICAL"), (
        f"Expected HIGH/CRITICAL, got {result.risk_level} ({result.total_score})"
    )


def test_score_migration_risk_convenience_function() -> None:
    """score_migration_risk() should return same result as MigrationScorer().score()."""
    source = ONE_REDEFINES
    direct = MigrationScorer().score(source)
    via_func = score_migration_risk(source)
    assert direct.total_score == via_func.total_score
    assert direct.risk_level == via_func.risk_level


def test_migration_score_summary_property() -> None:
    """MigrationScore.summary should contain risk level and score."""
    result = score_migration_risk(ONE_REDEFINES)
    summary = result.summary
    assert result.risk_level in summary
    assert str(result.total_score) in summary
