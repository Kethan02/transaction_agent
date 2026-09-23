from __future__ import annotations

import json
import logging
from pathlib import Path

from .categories import normalize_category
from .categorization import build_categorization_prompt
from .descriptions import clean_description
from .ingestion import load_transactions
from .llm import LLMClient
from .models import Transaction
from .report import build_report, compute_totals

logger = logging.getLogger(__name__)


class ToolLoopFinanceAgent:
    """Run the finance report through model-selected tools."""

    def __init__(self, llm: LLMClient, step_limit: int = 8, trace: str | None = None):
        self.llm = llm
        self.trace = trace
        self.step_limit = step_limit
        self.observations: list[str] = []
        self.warnings: list[str] = []
        self.totals: dict | None = None
        self.inspected = False

    def run(self, data_dir: str | Path, output_path: str | Path) -> dict:
        logger.info("[load] Reading CSV files from %s", data_dir)
        transactions = load_transactions(data_dir)
        if self.trace and not any(self.trace.casefold() in tx.description.casefold() for tx in transactions):
            logger.info("[trace] No retained transactions match %r", self.trace)
        for tx in transactions:
            self._trace_transaction(tx, "source", tx.raw)
            self._trace_transaction(tx, "normalized", {
                "date": tx.date, "amount": str(tx.amount), "category": tx.category,
                "category_source": tx.category_source, "transaction_type": tx.transaction_type,
                "next": "LLM categorization if selected" if not tx.category else "Already categorized; skips LLM categorization",
            })
        self.observations.append(f"inspect_data: {self._inspect_data(transactions)}")
        logger.info(
            "[inspect] Loaded %d transactions after overlap matching; %d missing categories",
            len(transactions), sum(not tx.category for tx in transactions),
        )

        for step in range(self.step_limit):
            logger.info("[step %d/%d] Requesting next tool choice", step + 1, self.step_limit)
            action = self._choose_tool(step, transactions)
            tool = action.get("tool")
            logger.info("[step %d/%d] Executing %s", step + 1, self.step_limit, tool)

            if tool == "categorize_missing":
                observation = self._categorize_missing(transactions)
            elif tool == "compute_totals":
                observation = self._compute_totals(transactions)
            elif tool == "write_report":
                return self._write_report(transactions, output_path)
            else:
                raise ValueError(f"Unknown tool selected by model: {tool!r}")

            self.observations.append(f"{tool}: {observation}")

        self.observations.append("step_limit_reached: writing report")
        self.warnings.append("Agent step limit reached; report written before the model finished the workflow.")
        logger.info("[fallback] Step limit reached; finishing report")
        return self._write_report(transactions, output_path)

    def _choose_tool(self, step: int, transactions: list[Transaction]) -> dict:
        state = {
            "step": step,
            "inspected": self.inspected,
            "transaction_count": len(transactions),
            "missing_categories": sum(1 for tx in transactions if not tx.category),
            "totals_computed": self.totals is not None,
            "report_written": False,
            "goal": "write a complete report with categorized transactions and deterministic totals",
            "recommended_order": [
                "categorize missing transactions if any categories are blank",
                "compute totals in code",
                "write the report",
            ],
        }
        tool_lines = "\n".join(f"- {name}: {_TOOL_DESCRIPTIONS[name]}" for name in _TOOL_DESCRIPTIONS)
        prompt = (
            "TOOL_LOOP_AGENT_STEP\n"
            "You are controlling a finance report agent. Choose exactly one tool.\n"
            "The inspection step has already run in deterministic setup code.\n"
            "Use the current state and observations to decide the next useful action.\n"
            "The current State JSON is authoritative; older observations may describe earlier state.\n"
            "Good workflow: categorize missing labels, compute totals, then write the report.\n"
            "If missing_categories is 0, do not choose categorize_missing.\n"
            "If totals_computed is false, compute totals before writing the report.\n"
            f"Available tools:\n{tool_lines}\n"
            f"State JSON: {json.dumps(state)}\n"
            f"Observations JSON: {json.dumps(self.observations)}\n"
            'Return only JSON. The tool value must be one of: '
            '["categorize_missing", "compute_totals", "write_report"].'
        )
        action = _parse_json(self.llm.complete(prompt))
        if not isinstance(action, dict) or action.get("tool") not in tuple(_TOOL_DESCRIPTIONS):
            self.observations.append("invalid_tool_choice: writing report")
            self.warnings.append("Invalid model tool choice; report written before the model finished the workflow.")
            logger.info("[fallback] Invalid tool choice; finishing report")
            return {"tool": "write_report", "args": {}}
        return action

    def _inspect_data(self, transactions: list[Transaction]) -> str:
        self.inspected = True
        counts = {
            "transactions": len(transactions),
            "missing_categories": sum(1 for tx in transactions if not tx.category),
            "refunds": sum(1 for tx in transactions if tx.transaction_type == "refund"),
            "transfers": sum(1 for tx in transactions if tx.transaction_type == "transfer"),
            "pending": sum(1 for tx in transactions if tx.transaction_type == "pending"),
        }
        return json.dumps(counts)

    def _categorize_missing(self, transactions: list[Transaction]) -> str:
        missing = [tx for tx in transactions if not tx.category]
        if not missing:
            logger.info("[categorize] No missing categories")
            return "categorized=0; missing_categories=0"

        logger.info("[categorize] Requesting labels for %d transactions", len(missing))
        for index, tx in enumerate(missing):
            self._trace_transaction(tx, "categorization input", {
                "batch_id": index, "cleaned_description": clean_description(tx.description),
                "amount": str(tx.amount),
            })
        prompt = build_categorization_prompt(transactions)
        response = _category_mapping(_parse_json(self.llm.complete(prompt)))

        for index, tx in enumerate(missing):
            category = normalize_category(str(response.get(str(index), "")))
            tx.category = category or "Other"
            tx.category_source = "llm" if category else "default"
            if not category:
                tx.notes.append("llm_category_invalid_defaulted_other")
            self._trace_transaction(tx, "categorization result", {
                "returned_label": response.get(str(index)), "category": tx.category,
                "category_source": tx.category_source,
            })

        remaining = sum(1 for tx in transactions if not tx.category)
        defaulted = sum(tx.category_source == "default" for tx in missing)
        logger.info(
            "[categorize] Finished: %d valid labels, %d defaulted to Other",
            len(missing) - defaulted, defaulted,
        )
        return f"categorized={len(missing)}; missing_categories={remaining}"

    def _compute_totals(self, transactions: list[Transaction]) -> str:
        self.totals = compute_totals(transactions)
        logger.info("[totals] Computed totals and category sums in Python")
        return json.dumps(self.totals["totals"])

    def _write_report(self, transactions: list[Transaction], output_path: str | Path) -> dict:
        logger.info("[report] Building final totals, summary, and warnings")
        for tx in transactions:
            if not tx.category:
                tx.category = "Other"
                tx.category_source = "default"
                tx.notes.append("missing_category_defaulted_before_report")

        warnings = list(self.warnings)
        defaulted = sum(tx.category_source == "default" for tx in transactions)
        if defaulted:
            warnings.append(
                f"Categorization incomplete: {defaulted} transaction(s) defaulted to Other "
                "because categories were missing or invalid. See transaction notes."
            )
        report = build_report(transactions, flagged=_flag_transactions(transactions), warnings=warnings)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for tx in transactions:
            self._trace_transaction(tx, "report", tx.as_report_dict())
            self._trace_transaction(tx, "contribution to final totals", {
                "income": str(max(tx.amount, 0)), "expenses": str(max(-tx.amount, 0)),
                "net": str(tx.amount), "category": tx.category,
                "signed_category_amount": str(tx.amount),
            })
        for warning in warnings:
            logger.info("[warning] %s", warning)
        logger.info("[done] Report saved to %s (%d warnings)", path, len(warnings))
        return report

    def _trace_transaction(self, tx: Transaction, stage: str, details: dict) -> None:
        if self.trace and self.trace.casefold() in tx.description.casefold():
            logger.info("[trace | %s | %s | %s] %s: %s",
                        tx.source_file, tx.date, tx.description, stage, json.dumps(details))


_TOOL_DESCRIPTIONS = {
    "categorize_missing": "categorize transactions with blank categories",
    "compute_totals": "compute totals in deterministic code",
    "write_report": "write the final report after categories and totals are ready",
}


def _flag_transactions(transactions: list[Transaction]) -> list[dict]:
    seen: dict[tuple[str, float], Transaction] = {}
    flagged = []
    for tx in transactions:
        key = (tx.description.lower(), float(tx.amount))
        if tx.amount < 0 and key in seen:
            flagged.append(
                {
                    "description": tx.description,
                    "reason": "Possible repeated charge with the same description and amount.",
                }
            )
        seen[key] = tx
    return flagged


def _parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min(_positive_index(text.find("{")), _positive_index(text.find("[")))
        if start == len(text):
            return None
        end = max(text.rfind("}"), text.rfind("]"))
        if end < start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _positive_index(index: int) -> int:
    if index == -1:
        return 10**9
    return index


def _category_mapping(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        mapping = {}
        for item in value:
            if isinstance(item, dict) and "id" in item and "category" in item:
                mapping[str(item["id"])] = item["category"]
        return mapping
    return {}
