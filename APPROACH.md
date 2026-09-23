# My Approach and Improvements

## Approach

I focused on a small, explainable CLI that loads the four CSVs, categorizes
transactions, and produces a financial report. I used the LLM for interpreting
merchant descriptions and choosing tools, while keeping arithmetic in Python.
My priority was completing the assessment's core requirements without adding
unnecessary frameworks, retries, or layers of fallback logic.

## Decisions and Improvements

1. **Keep the account's cash flow simple.** Every positive amount is an inflow
   and every negative amount is an outflow. Refunds and transfers stay in the
   totals according to their sign. I decided against an `include_in_totals`
   flag because the report describes this account's movements, not just
   consumption spending. The savings rate is therefore an account cash-flow
   ratio, not a complete measure of personal savings.

2. **Normalize useful fields without losing the source data.** Dates use one
   format and amounts use `Decimal`. Original CSV rows and descriptions remain
   available, alongside the source file, transaction type, category source,
   and processing notes. Refunds, transfers, and the zero-amount pending row
   have explicit rules. The pending row is retained and contributes zero.

3. **Clean merchant descriptions before categorizing.** Initially, the model
   received noisy descriptions directly. I added shared regex cleanup for
   payment prefixes, store markers, extra whitespace, and likely trailing
   reference codes. I chose general rules instead of merchant-specific rules.
   This can remove meaningful suffixes, so the original description is preserved.

4. **Simplify categories and give the model context.** I reduced the original
   16 categories (recommended by Codex) to 12 by merging Healthcare into Health, Home into Housing,
   Cash into Transfers, and Fees into Other. I then added Rent separately,
   bringing the total to 13. Each category has a definition in the prompt.
   The prompt also includes one existing labeled example per category across
   the expenses and transactions CSVs, with expenses taking priority. These
   examples come from source labels, not previous model guesses.

5. **Make tool selection a real model decision.** I moved from the initial
   constrained workflow to a loop that exposes all three tools at every step:
   categorize missing transactions, compute totals, and write the report.
   Initial inspection is deterministic setup. The model sees current progress
   and prior tool observations; the prompt recommends an order, but code does
   not restrict it to the next expected tool. The original version is archived.

6. **Use one clear failure path.** Invalid tool choices finish the report,
   with remaining blank categories assigned to Other. Invalid category results
   also become Other and receive a note. An eight-step limit prevents endless
   tool selection. A report-level `warnings` list explains early termination
   and counts defaulted categories, so partial results are visible without
   inspecting every transaction. A normal run has an empty warnings list.
   Input errors and model connection failures still stop the
   run. I kept this explicit rather than adding retries or multiple recovery
   layers.

7. **Generate the numeric summary in code.** The summary originally came from
   the model. I replaced it with a fixed template populated from computed
   totals so its numbers agree with the report and report writing requires no
   additional model call.

8. **Make the result reproducible.** I recorded the real Ollama prompts and
   responses and added offline replay. Offline tests cover parsing,
   cleanup, categories, arithmetic, and failure paths. The refreshed recording
   contains three tool choices and one categorization response; offline replay
   reproduces the current report exactly.

## Scope and Remaining Limitation

I kept duplicate-charge detection minimal: retain the repeated-looking charge
and flag it for review. I did not add a UI, fuzzy anomaly detection, or category
accuracy scoring because the assessment prioritizes a finished, understandable
core workflow.

Cross-file overlap matching still needs tightening. It currently removes bank
statement rows when the amount and either the date or merchant match another
export, which can remove unrelated transactions. We discussed matching amount
and merchant within a small date window, using each counterpart once, but that
change has not been implemented.

I used Codex to help implement and test the project. My decisions shaped the
cash-flow definition, category consolidation, prompt context, tool autonomy,
description cleanup, and minimal failure handling described above.
