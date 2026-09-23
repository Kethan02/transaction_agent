import unittest
from decimal import Decimal

from finance_agent.models import Transaction
from finance_agent.report import build_report, compute_totals


class ReportTests(unittest.TestCase):
    def test_summary_uses_report_totals(self):
        transactions = [Transaction(
            "2024-01-01", "Purchase", Decimal("-25.00"), "Shopping",
            "test.csv", "expense", "csv", {},
        )]
        report = build_report(transactions, flagged=[], warnings=[])
        self.assertEqual(report["summary"],
            "Account inflows were $0.00, outflows were $25.00, and net cash flow "
            "was $-25.00. The account cash-flow savings rate was 0.00%. "
            "Transfers are included according to their amount's sign.")

    def test_compute_totals_uses_code_not_model_text(self):
        transactions = [
            Transaction(
                "2024-01-01",
                "Paycheck",
                Decimal("100.00"),
                "Income",
                "test.csv",
                "income",
                "rule",
                {},
            ),
            Transaction(
                "2024-01-02",
                "Groceries",
                Decimal("-25.00"),
                "Food",
                "test.csv",
                "expense",
                "csv",
                {},
            ),
            Transaction(
                "2024-01-03",
                "Refund",
                Decimal("5.00"),
                "Refunds",
                "test.csv",
                "refund",
                "rule",
                {},
            ),
        ]

        report = compute_totals(transactions)

        self.assertEqual(report["totals"]["income"], 105.0)
        self.assertEqual(report["totals"]["expenses"], 25.0)
        self.assertEqual(report["totals"]["net"], 80.0)
        self.assertEqual(round(report["totals"]["savings_rate"], 4), 0.7619)
        self.assertEqual(report["by_category"]["Food"], -25.0)


if __name__ == "__main__":
    unittest.main()
