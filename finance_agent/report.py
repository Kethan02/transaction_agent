from __future__ import annotations

from decimal import Decimal

from .models import Transaction


def compute_totals(transactions: list[Transaction]) -> dict:
    income = sum((tx.amount for tx in transactions if tx.amount > 0), Decimal("0.00"))
    expenses = sum((-tx.amount for tx in transactions if tx.amount < 0), Decimal("0.00"))
    net = income - expenses
    savings_rate = (net / income) if income else Decimal("0.00")

    by_category: dict[str, Decimal] = {}
    for tx in transactions:
        by_category.setdefault(tx.category, Decimal("0.00"))
        by_category[tx.category] += tx.amount

    return {
        "totals": {
            "income": float(income),
            "expenses": float(expenses),
            "net": float(net),
            "savings_rate": float(savings_rate),
        },
        "by_category": {key: float(value) for key, value in sorted(by_category.items())},
    }


def build_report(transactions: list[Transaction], flagged: list[dict], warnings: list[str]) -> dict:
    report = compute_totals(transactions)
    report["flagged"] = flagged
    report["warnings"] = warnings
    report["transactions"] = [tx.as_report_dict() for tx in transactions]
    totals = report["totals"]
    report["summary"] = (
        f"Account inflows were ${totals['income']:,.2f}, outflows were "
        f"${totals['expenses']:,.2f}, and net cash flow was ${totals['net']:,.2f}. "
        f"The account cash-flow savings rate was {totals['savings_rate']:.2%}. "
        "Transfers are included according to their amount's sign."
    )
    return report
