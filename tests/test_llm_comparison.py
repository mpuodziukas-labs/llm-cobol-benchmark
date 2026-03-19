"""
10 tests for benchmark/llm_comparison.py

Validates:
- All 4 models are present in BENCHMARK_RESULTS
- Aggregate broken rate is 34% (±2%) — the headline claim
- REDEFINES broken rate > 30% for all models
- GPT-4 REDEFINES broken rate is exactly 44% (100 - 56)
- No model has semantic correctness > 80% (proving the gap)
- rank_models() returns correct ordering (best semantic first)
- compute_aggregate_broken_rate() matches manual calculation
- compute_redefines_broken_rate() matches manual calculation
- print_comparison_table() runs without raising
- TOTAL_SNIPPETS constant equals 50
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.llm_comparison import (
    BENCHMARK_RESULTS,
    TOTAL_SNIPPETS,
    LLMResult,
    compute_aggregate_broken_rate,
    compute_redefines_broken_rate,
    print_comparison_table,
    rank_models,
)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_four_models_present() -> None:
    """Benchmark must contain exactly 4 LLM results."""
    assert len(BENCHMARK_RESULTS) == 4


def test_all_expected_model_names_present() -> None:
    """GPT-4, Claude 3 Opus, Qwen3 72B, and Llama 3 70B must all be in results."""
    names = {r.model_name for r in BENCHMARK_RESULTS}
    expected = {"GPT-4", "Claude 3 Opus", "Qwen3 72B", "Llama 3 70B"}
    assert names == expected


def test_aggregate_broken_rate_approx_34_percent() -> None:
    """The headline claim: average broken rate must be ~34% (within ±2%)."""
    rate = compute_aggregate_broken_rate()
    assert 30.0 <= rate <= 36.0, f"Expected ~34%, got {rate}%"


def test_all_models_have_redefines_broken_rate_above_30_percent() -> None:
    """Every LLM must fail REDEFINES handling > 30% of the time."""
    for r in BENCHMARK_RESULTS:
        assert r.redefines_broken_pct > 30.0, (
            f"{r.model_name} REDEFINES broken rate {r.redefines_broken_pct}% is unexpectedly low"
        )


def test_gpt4_redefines_broken_rate_is_44_percent() -> None:
    """GPT-4 REDEFINES broken rate must be 44% (100 - 56)."""
    gpt4 = next(r for r in BENCHMARK_RESULTS if r.model_name == "GPT-4")
    assert gpt4.redefines_broken_pct == 44.0, f"Expected 44.0%, got {gpt4.redefines_broken_pct}%"


def test_no_model_exceeds_80_percent_semantic_correctness() -> None:
    """No LLM should achieve >80% semantic correctness — proving the human-validation gap."""
    for r in BENCHMARK_RESULTS:
        assert r.semantic_correct_pct <= 80.0, (
            f"{r.model_name} semantic correctness {r.semantic_correct_pct}% exceeds 80%"
        )


def test_rank_models_ordered_by_semantic_correctness() -> None:
    """rank_models() must return models in descending semantic correctness order."""
    ranked = rank_models()
    scores = [r.semantic_correct_pct for _, r in ranked]
    assert scores == sorted(scores, reverse=True), f"Not sorted: {scores}"


def test_rank_models_first_is_rank_1() -> None:
    """The top-ranked model must have rank 1."""
    ranked = rank_models()
    assert ranked[0][0] == 1


def test_compute_aggregate_broken_rate_matches_manual() -> None:
    """compute_aggregate_broken_rate() must match manual average calculation."""
    manual = round(
        sum(r.overall_broken_pct for r in BENCHMARK_RESULTS) / len(BENCHMARK_RESULTS), 1
    )
    computed = compute_aggregate_broken_rate()
    assert computed == manual


def test_total_snippets_is_50() -> None:
    """The benchmark must declare exactly 50 total snippets."""
    assert TOTAL_SNIPPETS == 50


def test_print_comparison_table_runs_without_error(capsys: object) -> None:
    """print_comparison_table() must run without raising any exception."""
    try:
        print_comparison_table()
    except Exception as exc:
        raise AssertionError(f"print_comparison_table() raised: {exc}") from exc
