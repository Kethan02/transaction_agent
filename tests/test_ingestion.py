import unittest
from decimal import Decimal

from finance_agent.ingestion import load_transactions, parse_date


class IngestionTests(unittest.TestCase):
    def test_parse_date_supports_mixed_formats(self):
        self.assertEqual(parse_date("2024-01-02"), "2024-01-02")
        self.assertEqual(parse_date("01/03/2024"), "2024-01-03")
        self.assertEqual(parse_date("2024-1-6"), "2024-01-06")

    def test_load_transactions_normalizes_and_keeps_messy_rows(self):
        transactions = load_transactions("sample_data")

        self.assertGreater(len(transactions), 0)
        self.assertTrue(all(len(tx.date) == 10 for tx in transactions))

        refund = next(tx for tx in transactions if tx.description == "Refund AMAZON.COM")
        self.assertEqual(refund.amount, Decimal("34.99"))
        self.assertEqual(refund.category, "Refunds")
        self.assertEqual(refund.transaction_type, "refund")
        self.assertEqual(refund.category_source, "rule")
        self.assertEqual(refund.raw["Description"], "Refund AMAZON.COM")

        pending = next(tx for tx in transactions if tx.description == "PENDING AUTH TARGET T-8821")
        self.assertEqual(pending.amount, Decimal("0.00"))
        self.assertEqual(pending.category, "Other")
        self.assertEqual(pending.transaction_type, "pending")

    def test_bank_statement_overlap_is_not_double_counted(self):
        transactions = load_transactions("sample_data")
        bank_rows = [tx for tx in transactions if tx.source_file == "bank_statement.csv"]

        self.assertEqual(bank_rows, [])


if __name__ == "__main__":
    unittest.main()
