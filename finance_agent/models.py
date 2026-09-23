from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Transaction:
    date: str
    description: str
    amount: Decimal
    category: str
    source_file: str
    transaction_type: str
    category_source: str
    raw: dict[str, str]
    notes: list[str] = field(default_factory=list)

    def as_report_dict(self) -> dict:
        return {
            "date": self.date,
            "description": self.description,
            "amount": float(self.amount),
            "category": self.category,
            "transaction_type": self.transaction_type,
            "category_source": self.category_source,
            "source_file": self.source_file,
            "notes": self.notes,
            "raw": self.raw,
        }
