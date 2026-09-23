# Personal Finance Agent

A small CLI agent that ingests messy finance CSV exports, uses an LLM interface
to categorize missing transaction labels, computes all totals in deterministic
Python code, and writes a structured JSON report.

## Setup

Requires Python 3.11 or newer. The default provider is local Ollama; start
Ollama and install `llama3.1:8b` with `ollama pull llama3.1:8b` before a live run.
Replay and scripted modes require no running model or Python package installs.

```bash
python -m finance_agent --data sample_data/ --out report.json
```

The CLI runs the tool-loop agent with Ollama by default and saves prompts and
responses to `recordings/tool_loop_llm_responses.json`, replacing the previous
recording. Explicit `--provider scripted` runs use
`recordings/scripted_llm_responses.json` instead. `--recording` overrides either
path. To replay the saved model run without contacting Ollama:

```bash
python -m finance_agent --data sample_data/ --out report.json --replay recordings/tool_loop_llm_responses.json
```

The agent first inspects the loaded data in deterministic setup code, then lets
the model choose among `categorize_missing`, `compute_totals`, and `write_report`.
The prompt shows progress state and prior observations. The previous linear
implementation and its recording are preserved in `archived/`.

All CLI modes print checkpoints to stderr for loading, inspection, tool choices,
categorization, totals, and report completion. Requests are logged before waiting
for the model. Fallbacks and report warnings are also printed. These messages
do not change the report, model prompts, or replay recording.

The recorded run used local Ollama with `llama3.1:8b` at temperature 0.
The explicit equivalent of the default live command is:

```bash
OLLAMA_MODEL=llama3.1:8b python -m finance_agent \
  --data sample_data/ \
  --out report.json \
  --provider ollama \
  --recording recordings/tool_loop_llm_responses.json
```

## View Report in Terminal
```bash
python -m json.tool report.json
```

## Trace a Transaction

```bash
python -m finance_agent --data sample_data --out /tmp/trace-report.json --replay recordings/tool_loop_llm_responses.json --trace SAFEWAY
```

Uses saved Ollama responses without calling the model. Prints the preserved CSV
row, normalized fields, cleaned categorization input, category result, and final
report contribution. Replace `SAFEWAY` with any description text; matching is
case-insensitive and traces all matching retained transactions. The full agent
still runs. `--trace` also works with live model runs.

## Demonstrate Bad Model Output

```bash
python -m finance_agent --data sample_data --out /tmp/fallback-report.json --demo-bad-response --trace SAFEWAY
```

Injects `this is not json` as the first tool response and runs the actual
fallback path. Shows remaining categories defaulting to `Other`, report
warnings, and successful report writing. This demo calls no model, reads no
recording, and writes no recording. Both commands save reports to `/tmp`,
leaving the submission report unchanged.

## Time Spent

I spent around 7-8 hours on this.

## Tests

```bash
python -m unittest discover -s tests
```

The tests run offline and use a scripted LLM.

## Data-Cleaning Rules

- All dates are normalized to `YYYY-MM-DD`.
- Before LLM categorization, descriptions have whitespace collapsed and explicit
  `SQ *`, `TST*`, `POS DEBIT`, and `CHECKCARD` prefixes removed (including a
  four-digit code immediately after `CHECKCARD`). Store markers such as `#10452`
  and `STORE 11234` are removed. Original descriptions and raw rows are preserved.
  Trailing tokens separated by whitespace or `*` are removed if they are numeric
  with at least four digits, or alphanumeric with at least six characters and
  contain both letters and digits. This general heuristic can remove meaningful
  suffixes too (for example, `STUDIO 2024` becomes `STUDIO`). Short numbers,
  website names/paths, casing, and payment context such as PayPal, ACH credit,
  refunds, and transfers are retained.
- Existing categories are trusted only if they match the fixed category list.
- The 13 categories have short definitions in `finance_agent/categories.py` that
  are also included in the categorization prompt. Legacy labels are consolidated:
  Healthcare into Health, Home into Housing, Cash into Transfers, and Fees into
  Other. Original CSV labels remain in `raw`.
  Rent is separate from Housing (repairs, improvements, and home supplies).
  Payments to a landlord belong in Rent regardless of the payment method.
- The agent includes one existing CSV-labeled description per normalized
  category as prompt context. The first labeled row wins, scanning `expenses.csv`
  before `transactions_uncategorized.csv`. Examples use cleaned descriptions;
  rule-assigned and model-generated labels are not examples. Categories without
  a source example still have their definition.
- Positive rows without labels are treated as `Income`, except refunds.
- Descriptions containing `refund` with a positive amount become `Refunds`.
- Descriptions containing `transfer` become `Transfers`.
- Zero-amount pending rows are kept and categorized as `Other`.
- `income.csv`, `expenses.csv`, and `transactions_uncategorized.csv` are treated
  as the canonical transaction exports. `bank_statement.csv` is still ingested,
  but rows with matching amount and matching date or merchant text are treated
  as corroborating overlap and are not double-counted.

## LLM vs Code Boundary

Transactions keep the normalized fields needed for the required report plus
lightweight audit fields: `source_file`, `raw`, `transaction_type`,
`category_source`, and `notes`.

The LLM chooses the next tool in the agent loop and categorizes missing labels.
All arithmetic is performed in `finance_agent/report.py`. Model output is parsed
and validated before use; invalid categories default to `Other`. Totals are
account-relative: positive amounts are inflows, negative amounts are outflows,
including transfers. Each known messy input has one explicit rule, and
unrecoverable failures make the CLI exit non-zero.

Malformed JSON, invalid action shapes, and unknown tool names share one fallback:
write the report, assigning `Other` to any remaining blank categories. Reaching
the step limit also writes the report. The summary is formatted in code from
the report totals, so report writing needs no additional LLM call. Input errors
and failures to reach the model during earlier steps still exit non-zero.
The saved recording contains four model calls: three tool choices and one
categorization response. The summary is generated in code.

Every report includes a `warnings` list. Invalid tool choices and the step limit
produce an explanation of why the workflow ended early. Any defaulted categories
produce a warning with the affected transaction count, including when the model
chooses to write the report before categorizing. Transaction notes provide the
details. A normal run has `warnings: []`; a legitimate `Other` category is not
an error. `flagged` remains separate and identifies possible duplicate charges.
Warnings describe partial results; they do not introduce retries or change totals.

## What Is Not Built

I kept duplicate detection to flags for repeated descriptions and amounts.
I omitted a UI, broader anomaly detection, and category accuracy scoring to
focus on the required CLI, agent loop, and reproducibility.

With more time, I would tighten cross-file overlap matching and add tests
proving unrelated transactions are retained. The current amount-plus-date-or-
merchant rule can discard legitimate rows. I would require matching amount
and merchant within a documented date window, using each counterpart once.

## AI Usage and Decisions

Codex helped scaffold and implement the parser, agent loop, tests, and
documentation. I directed these changes and tradeoffs:

- Replaced constrained tool selection with all three tools available to the
  model, guided by state, observations, and a recommended workflow.
- Consolidated categories, kept Rent separate, and added definitions and
  existing labeled examples to the prompt.
- Replaced model-written summaries with code-formatted totals and used one
  explicit failure path with report warnings, without retries.
- Rejected an `include_in_totals` flag: all signed account movements count,
  including transfers and refunds. I preserved raw rows and used documented
  cleanup rules while keeping arithmetic entirely in code.

## Walkthrough Notes

- Run the CLI in replay mode and inspect the generated `report.json`.
- Trace `Refund AMAZON.COM` from CSV parsing through final category and totals.
- Show `finance_agent/report.py` as the deterministic arithmetic boundary.
- Make the first model tool response malformed and show the fallback path test.
- Discuss what a stronger duplicate detector would add with more time.
