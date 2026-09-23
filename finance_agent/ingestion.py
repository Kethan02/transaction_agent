from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .categories import normalize_category
from .models import Transaction


EXPECTED_FILES = (
    "income.csv",
    "expenses.csv",
    "bank_statement.csv",
    "transactions_uncategorized.csv",
)


def parse_date(value: str) -> str:
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def parse_amount(value: str) -> Decimal:
    try:
        return Decimal(value.strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Unsupported amount: {value!r}") from exc


def load_transactions(data_dir: str | Path) -> list[Transaction]:
    root = Path(data_dir)
    missing = [name for name in EXPECTED_FILES if not (root / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required CSV files: {', '.join(missing)}")

    transactions: list[Transaction] = []
    transactions.extend(_load_income(root / "income.csv"))
    transactions.extend(_load_expenses(root / "expenses.csv"))
    transactions.extend(_load_bank_statement(root / "bank_statement.csv"))
    transactions.extend(_load_uncategorized(root / "transactions_uncategorized.csv"))
    return _dedupe_overlapping_exports(transactions)


def _load_income(path: Path) -> list[Transaction]:
    rows = _read_rows(path)
    return [
        Transaction(
            date=parse_date(row["Date"]),
            description=row["Description"].strip(),
            amount=parse_amount(row["Amount"]),
            category="Income",
            source_file=path.name,
            transaction_type="income",
            category_source="rule",
            raw=dict(row),
        )
        for row in rows
    ]


def _load_expenses(path: Path) -> list[Transaction]:
    rows = _read_rows(path)
    return [
        Transaction(
            date=parse_date(row["Date"]),
            description=row["Description"].strip(),
            amount=parse_amount(row["Amount"]),
            category=normalize_category(row.get("Category")) or "Other",
            source_file=path.name,
            transaction_type="expense",
            category_source="csv",
            raw=dict(row),
        )
        for row in rows
    ]


def _load_bank_statement(path: Path) -> list[Transaction]:
    rows = _read_rows(path)
    transactions = []
    for row in rows:
        amount = parse_amount(row["Amount"])
        category = "Income" if amount > 0 else "Other"
        transactions.append(
            Transaction(
                date=parse_date(row["Date"]),
                description=row["Description"].strip(),
                amount=amount,
                category=category,
                source_file=path.name,
                transaction_type="income" if amount > 0 else "expense",
                category_source="rule",
                raw=dict(row),
                notes=["bank_statement_category_inferred"],
            )
        )
    return transactions


def _load_uncategorized(path: Path) -> list[Transaction]:
    rows = _read_rows(path)
    transactions = []
    for row in rows:
        amount = parse_amount(row["Amount"])
        category = normalize_category(row.get("Category"))
        category_source = "csv" if category else ""
        transaction_type = "income" if amount > 0 else "expense"
        notes = []
        description = row["Description"].strip()

        if amount == Decimal("0.00"):
            category = category or "Other"
            category_source = category_source or "rule"
            transaction_type = "pending"
            notes.append("zero_amount_pending_row_kept")
        elif "transfer" in description.lower():
            category = category or "Transfers"
            category_source = category_source or "rule"
            transaction_type = "transfer"
            notes.append("transfer_detected_by_rule")
        elif "refund" in description.lower() and amount > 0:
            category = category or "Refunds"
            category_source = category_source or "rule"
            transaction_type = "refund"
            notes.append("refund_detected_by_rule")
        elif amount > 0 and not category:
            category = "Income"
            category_source = "rule"
            transaction_type = "income"
            notes.append("positive_amount_income_inferred")

        transactions.append(
            Transaction(
                date=parse_date(row["Date"]),
                description=description,
                amount=amount,
                category=category,
                source_file=path.name,
                transaction_type=transaction_type,
                category_source=category_source,
                raw=dict(row),
                notes=notes,
            )
        )
    return transactions


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _dedupe_overlapping_exports(transactions: list[Transaction]) -> list[Transaction]:
    canonical_rows = [tx for tx in transactions if tx.source_file != "bank_statement.csv"]
    deduped: list[Transaction] = []

    for transaction in transactions:
        if transaction.source_file == "bank_statement.csv" and _has_corroborating_export(
            transaction, canonical_rows
        ):
            continue
        deduped.append(transaction)

    return deduped


def _merchant_key(description: str) -> str:
    return "".join(char.lower() for char in description if char.isalnum())


def _has_corroborating_export(transaction: Transaction, candidates: list[Transaction]) -> bool:
    merchant = _merchant_key(transaction.description)
    for candidate in candidates:
        if candidate.amount != transaction.amount:
            continue
        candidate_merchant = _merchant_key(candidate.description)
        if candidate.date == transaction.date:
            return True
        if merchant and candidate_merchant and (merchant in candidate_merchant or candidate_merchant in merchant):
            return True
    return False
