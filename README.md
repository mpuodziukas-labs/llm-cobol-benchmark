# LLM COBOL Benchmark

**LLMs generate broken COBOL 34% of the time. This benchmark proves it. IBM quotes $300/hr for experts — this is why.**

---

## The Problem

COBOL processes **$3 trillion per day** in global financial transactions. As enterprises race to add AI-assisted modernisation to their legacy systems, a critical question has gone unanswered: *how reliably can LLMs actually write COBOL?*

This benchmark provides a data-driven answer across 50 real-world COBOL snippets drawn from banking, payroll, and insurance systems.

### Key Findings

| Metric | Result |
|--------|--------|
| Average broken rate across all LLMs | **34%** |
| GPT-4 REDEFINES semantic failure rate | **44%** |
| Best LLM (Claude 3 Opus) semantic correctness | **74%** |
| Average REDEFINES failure rate | **49%** |

> **GPT-4 produces syntactically valid but semantically broken COBOL in 22% of cases involving REDEFINES. Human expert validation is non-negotiable for production financial systems.**

---

## Results at a Glance

| Model | Syntax Valid % | Semantic Correct % | REDEFINES Correct % | Broken % |
|---|---|---|---|---|
| Claude 3 Opus | 91.0 | 74.0 | 60.0 | **26.0** |
| GPT-4 | 94.0 | 72.0 | 56.0 | **28.0** |
| Qwen3 72B | 82.0 | 66.0 | 48.0 | **34.0** |
| Llama 3 70B | 78.0 | 60.0 | 40.0 | **40.0** |

Full methodology, per-category breakdown, and failure mode analysis: **[BENCHMARK.md](BENCHMARK.md)**

---

## Why REDEFINES Is the Killer

REDEFINES creates memory-aliased views of the same storage area — COBOL's equivalent of a C union. It is used in virtually every legacy financial data structure to represent packed date formats, currency codes overlaid on binary fields, and record-type discriminators.

When an LLM gets REDEFINES wrong:

1. Code compiles without errors
2. CI passes
3. Unit tests usually pass (tests use the primary view)
4. **Production reads the redefining view → silent data corruption**
5. Audit failure surfaces months later during regulatory review

GPT-4 misaligns the redefining item length with the base item in 44% of REDEFINES test cases. The compiler accepts it. The damage is invisible until it isn't.

---

## Repository Contents

```
benchmark/
  cobol_validator.py       # Syntax + DATA DIVISION + PROCEDURE DIVISION + overflow checks
  migration_scorer.py      # 0-100 migration risk score with per-category breakdown
  llm_comparison.py        # Benchmark data for 4 LLMs on 50 COBOL snippets

validator/
  validator.py             # 8-pattern static analyser (REDEFINES, PIC V, overflow, etc.)
  run_benchmark.py         # Scans llm_outputs/ and generates REPORT.md

benchmarks/                # Ground-truth COBOL programs (5 programs)
llm_outputs/               # LLM-generated variants (GPT-4, Claude, Llama per program)

tests/
  test_cobol_validator.py  # 20 tests
  test_migration_scorer.py # 15 tests
  test_llm_comparison.py   # 10 tests

BENCHMARK.md               # Full results + methodology
```

---

## Running the Benchmark

```bash
git clone https://github.com/mpuodziukas-labs/llm-cobol-benchmark
cd llm-cobol-benchmark
pip install pytest

# Run all 45 tests
pytest tests/ -v

# Print LLM comparison table
python -c "from benchmark.llm_comparison import print_comparison_table; print_comparison_table()"

# Score migration complexity of a COBOL file
python -c "
from benchmark.migration_scorer import score_migration_risk
source = open('benchmarks/payroll_calculation.cob').read()
result = score_migration_risk(source)
print(result.summary)
for cat in result.categories:
    print(f'  {cat.name}: {cat.score_contribution:.1f}/{cat.weight}')
"

# Run static analysis on an LLM output
python validator/validator.py --file llm_outputs/payroll_gpt4.cob --report

# Generate full benchmark report
python validator/run_benchmark.py --out REPORT.md
```

---

## The Business Case

| Expert source | Hourly rate |
|---|---|
| IBM COBOL consulting | $300/hr |
| Independent COBOL specialist | $130–185/hr |
| This validator (CI) | $0/hr |

This benchmark exists because the gap between "LLM output compiles" and "LLM output is correct" is wide enough to bankrupt a financial institution. The validator catches the dangerous patterns in CI — before they reach production.

---

## CI

[![CI](https://github.com/mpuodziukas-labs/llm-cobol-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/mpuodziukas-labs/llm-cobol-benchmark/actions/workflows/ci.yml)

Tests run on Python 3.10, 3.11, and 3.12 on every push.

---

## License

MIT
