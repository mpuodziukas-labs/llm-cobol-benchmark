"""
COBOL → Modern Migration Risk Scorer

Produces a 0-100 risk score with per-category breakdown indicating how hard
a COBOL program will be to migrate to Java, Python, or Rust.

Higher score = higher migration risk / complexity.

Key risk factors:
- REDEFINES clauses      (data aliasing, non-trivial to represent in typed languages)
- OCCURS DEPENDING ON    (dynamic arrays, runtime-variable layout)
- Deep PERFORM nesting   (complex control flow)
- COPY/copybook deps     (implicit code injection — must resolve before migration)
- WORKING-STORAGE size   (large global state surface)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

# ── Patterns ───────────────────────────────────────────────────────────────────

REDEFINES_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"REDEFINES\s+\w+", re.IGNORECASE
)

OCCURS_DEPENDING_ON_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"OCCURS\s+\d+\s+TO\s+\d+\s+TIMES\s+DEPENDING\s+ON\s+\w+",
    re.IGNORECASE,
)

OCCURS_FIXED_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"OCCURS\s+\d+\s+TIMES", re.IGNORECASE
)

COPY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*COPY\s+([\w-]+)", re.IGNORECASE | re.MULTILINE
)

PERFORM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*PERFORM\b", re.IGNORECASE | re.MULTILINE
)

# PERFORM … THRU indicates multi-section spanning — complex flow
PERFORM_THRU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"PERFORM\s+\w+\s+THRU\s+\w+", re.IGNORECASE
)

WORKING_STORAGE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"WORKING-STORAGE\s+SECTION\.(.*?)(?=\n\s*[A-Z]+ SECTION\.|\Z)",
    re.IGNORECASE | re.DOTALL,
)

GOTO_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*GO\s+TO\s+\w+", re.IGNORECASE | re.MULTILINE
)

ALTER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*ALTER\s+", re.IGNORECASE | re.MULTILINE
)

EXEC_SQL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"EXEC\s+SQL", re.IGNORECASE
)

FILE_SECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"FILE\s+SECTION\.", re.IGNORECASE
)

# ── Score weights (must sum to 100 at theoretical maximum) ─────────────────────

WEIGHTS: Final[dict[str, int]] = {
    "redefines": 25,
    "occurs_depending_on": 20,
    "perform_depth": 15,
    "copybook_deps": 15,
    "working_storage": 10,
    "goto_alter": 10,
    "embedded_sql": 5,
}

assert sum(WEIGHTS.values()) == 100, "Weight table must sum to 100"  # noqa: S101


# ── Result types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RiskCategory:
    name: str
    raw_count: int
    score_contribution: float
    weight: int
    description: str


@dataclass
class MigrationScore:
    total_score: float  # 0–100
    risk_level: str     # LOW | MEDIUM | HIGH | CRITICAL
    categories: list[RiskCategory] = field(default_factory=list)
    copybook_dependencies: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Migration Risk: {self.risk_level} ({self.total_score:.1f}/100) | "
            f"Copybooks: {len(self.copybook_dependencies)}"
        )


# ── Scorer ─────────────────────────────────────────────────────────────────────


class MigrationScorer:
    """
    Analyses COBOL source and produces a structured migration risk score.

    Usage::

        scorer = MigrationScorer()
        result = scorer.score(source_code)
        print(result.summary)
    """

    def score(self, source: str) -> MigrationScore:
        categories: list[RiskCategory] = []

        # 1. REDEFINES clauses
        redefines_count = len(REDEFINES_PATTERN.findall(source))
        redefines_contrib = min(1.0, redefines_count / 5.0) * WEIGHTS["redefines"]
        categories.append(
            RiskCategory(
                name="REDEFINES Clauses",
                raw_count=redefines_count,
                score_contribution=redefines_contrib,
                weight=WEIGHTS["redefines"],
                description=(
                    "REDEFINES creates memory-aliased views of the same storage area. "
                    "Typed languages have no direct equivalent — each case requires manual analysis."
                ),
            )
        )

        # 2. OCCURS DEPENDING ON (dynamic arrays)
        odo_count = len(OCCURS_DEPENDING_ON_PATTERN.findall(source))
        odo_contrib = min(1.0, odo_count / 3.0) * WEIGHTS["occurs_depending_on"]
        categories.append(
            RiskCategory(
                name="OCCURS DEPENDING ON",
                raw_count=odo_count,
                score_contribution=odo_contrib,
                weight=WEIGHTS["occurs_depending_on"],
                description=(
                    "Variable-length arrays whose size is determined at runtime. "
                    "Requires careful bounds tracking in the migration target."
                ),
            )
        )

        # 3. PERFORM depth (proxy: total PERFORM statements + PERFORM THRU count * 2)
        perform_count = len(PERFORM_PATTERN.findall(source))
        thru_count = len(PERFORM_THRU_PATTERN.findall(source))
        perform_complexity = perform_count + thru_count * 2
        perform_contrib = min(1.0, perform_complexity / 20.0) * WEIGHTS["perform_depth"]
        categories.append(
            RiskCategory(
                name="PERFORM Depth / Control Flow",
                raw_count=perform_count,
                score_contribution=perform_contrib,
                weight=WEIGHTS["perform_depth"],
                description=(
                    f"{perform_count} PERFORM statements ({thru_count} THRU spans). "
                    "PERFORM THRU creates implicit coupling between paragraphs."
                ),
            )
        )

        # 4. Copybook dependencies
        copybooks = [m.group(1) for m in COPY_PATTERN.finditer(source)]
        unique_copybooks = sorted(set(copybooks))
        copy_contrib = min(1.0, len(unique_copybooks) / 5.0) * WEIGHTS["copybook_deps"]
        categories.append(
            RiskCategory(
                name="Copybook Dependencies",
                raw_count=len(unique_copybooks),
                score_contribution=copy_contrib,
                weight=WEIGHTS["copybook_deps"],
                description=(
                    f"Copybooks: {', '.join(unique_copybooks) if unique_copybooks else 'none'}. "
                    "Each copybook must be resolved and inlined before migration analysis."
                ),
            )
        )

        # 5. WORKING-STORAGE size (approximate: count data items)
        ws_match = WORKING_STORAGE_PATTERN.search(source)
        ws_item_count = 0
        if ws_match:
            ws_text = ws_match.group(1)
            ws_item_count = len(re.findall(r"^\s+\d{2}\s+\w+", ws_text, re.MULTILINE))
        ws_contrib = min(1.0, ws_item_count / 50.0) * WEIGHTS["working_storage"]
        categories.append(
            RiskCategory(
                name="WORKING-STORAGE Size",
                raw_count=ws_item_count,
                score_contribution=ws_contrib,
                weight=WEIGHTS["working_storage"],
                description=(
                    f"~{ws_item_count} data items in WORKING-STORAGE. "
                    "Large global state surfaces require careful scoping in modern languages."
                ),
            )
        )

        # 6. GO TO / ALTER (spaghetti control flow)
        goto_count = len(GOTO_PATTERN.findall(source))
        alter_count = len(ALTER_PATTERN.findall(source))
        goto_alter_total = goto_count + alter_count * 3  # ALTER is far worse
        goto_contrib = min(1.0, goto_alter_total / 5.0) * WEIGHTS["goto_alter"]
        categories.append(
            RiskCategory(
                name="GO TO / ALTER Statements",
                raw_count=goto_count + alter_count,
                score_contribution=goto_contrib,
                weight=WEIGHTS["goto_alter"],
                description=(
                    f"{goto_count} GO TO, {alter_count} ALTER. "
                    "ALTER dynamically rewrites PERFORM targets — nearly impossible to reason about statically."
                ),
            )
        )

        # 7. Embedded SQL
        sql_count = len(EXEC_SQL_PATTERN.findall(source))
        sql_contrib = min(1.0, sql_count / 5.0) * WEIGHTS["embedded_sql"]
        categories.append(
            RiskCategory(
                name="Embedded SQL (EXEC SQL)",
                raw_count=sql_count,
                score_contribution=sql_contrib,
                weight=WEIGHTS["embedded_sql"],
                description=(
                    f"{sql_count} EXEC SQL blocks. "
                    "Each must be extracted, tested, and replaced with modern ORM or query layer."
                ),
            )
        )

        total = round(sum(c.score_contribution for c in categories), 1)

        if total < 20:
            risk_level = "LOW"
        elif total < 45:
            risk_level = "MEDIUM"
        elif total < 70:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return MigrationScore(
            total_score=total,
            risk_level=risk_level,
            categories=categories,
            copybook_dependencies=unique_copybooks,
        )


# ── Convenience function ───────────────────────────────────────────────────────


def score_migration_risk(source: str) -> MigrationScore:
    """Score COBOL source migration complexity. Returns 0-100 risk score."""
    return MigrationScorer().score(source)
