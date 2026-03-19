# LLM COBOL Quality Benchmark — Results

| Program | LLM | Bugs Detected | Critical | High | Medium | Risk Level |
|---------|-----|:-------------:|:--------:|:----:|:------:|:----------:|
| data_validation | GPT-4 | 3 | 3 | 3 | 0 | HIGH |
| data_validation | Claude | 3 | 3 | 3 | 0 | HIGH |
| data_validation | Llama | 5 | 4 | 4 | 1 | HIGH |
| interest_calculation | GPT-4 | 9 | 8 | 8 | 1 | HIGH |
| interest_calculation | Claude | 8 | 8 | 8 | 0 | HIGH |
| interest_calculation | Llama | 9 | 8 | 8 | 1 | HIGH |
| inventory_update | GPT-4 | 5 | 4 | 4 | 1 | HIGH |
| inventory_update | Claude | 4 | 2 | 2 | 2 | HIGH |
| inventory_update | Llama | 4 | 3 | 3 | 1 | HIGH |
| payroll_calculation | GPT-4 | 10 | 8 | 8 | 2 | HIGH |
| payroll_calculation | Claude | 10 | 9 | 9 | 1 | HIGH |
| payroll_calculation | Llama | 11 | 9 | 9 | 2 | HIGH |
| report_generator | GPT-4 | 3 | 2 | 2 | 1 | HIGH |
| report_generator | Claude | 3 | 3 | 3 | 0 | HIGH |
| report_generator | Llama | 5 | 3 | 3 | 2 | HIGH |

## Key Finding

**15/15 LLM output files contained at least 1 HIGH severity bug** when tested against production COBOL patterns.

## Most Common Bug Patterns

| Pattern | Occurrences Across All LLM Outputs |
|---------|:-----------------------------------:|
| `MISSING_ON_SIZE_ERROR` | 52 |
| `WHEN_OTHER_CONTINUE` | 12 |
| `MISSING_FILE_STATUS` | 12 |
| `REDEFINES_ON_NUMERIC` | 7 |
| `PIC_V_NO_INTEGER` | 6 |
| `UNCHECKED_IO_STATUS` | 3 |

> IBM quotes $300/hr to fix these in production. This validator catches them in CI.
