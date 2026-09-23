import unittest
from unittest.mock import Mock
from decimal import Decimal

from finance_agent.descriptions import clean_description
from finance_agent.models import Transaction
from finance_agent.tool_loop_agent import ToolLoopFinanceAgent


class DescriptionTests(unittest.TestCase):
    def test_explicit_statement_noise_is_removed(self):
        examples = {
            "WHOLEFDS MKT #10452": "WHOLEFDS MKT",
            " SQ *BLUE BOTTLE COFFEE ": "BLUE BOTTLE COFFEE",
            "TST* JOE'S PIZZA DOWNTOWN": "JOE'S PIZZA DOWNTOWN",
            "CHECKCARD 1314 SAFEWAY #2910": "SAFEWAY",
            "pos debit THE HOME DEPOT 123": "THE HOME DEPOT 123",
            "STARBUCKS STORE 11234": "STARBUCKS",
            "UBER   *TRIP HELP.UBER.COM": "UBER *TRIP HELP.UBER.COM",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(clean_description(original), expected)

    def test_potentially_meaningful_context_is_retained(self):
        for description in (
            "PAYPAL *ETSYSHOP", "ACH CREDIT PAYROLL ACME CORP",
            "Refund AMAZON.COM", "APPLE.COM/BILL", "TRANSFER TO SAVINGS",
            "7-ELEVEN", "3M", "FOREVER 21", "SHOP ABCDEF", "SHOP AB123",
            "SHOP 123456 BRANCH", "SHOP AB12CD SERVICE",
        ):
            with self.subTest(description=description):
                self.assertEqual(clean_description(description), description)

    def test_general_trailing_reference_rules(self):
        examples = {
            "SHELL OIL 5748291": "SHELL OIL",
            "ATM WITHDRAWAL 001234": "ATM WITHDRAWAL",
            "UNKNOWN MERCHANT 998877": "UNKNOWN MERCHANT",
            "AMZN MKTP US*AB12C3D4E": "AMZN MKTP US",
            "ANY MERCHANT ab12cd": "ANY MERCHANT",
            "ANY MERCHANT 123abc": "ANY MERCHANT",
            "SHOP 1234": "SHOP",
            "SHOP 123": "SHOP 123",
            "SHOP AB12CD   ": "SHOP",
            "STUDIO 2024": "STUDIO",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(clean_description(original), expected)

    def test_agent_sends_clean_description_and_preserves_original(self):
        llm = Mock()
        llm.complete.return_value = '{"0": "Food"}'
        transaction = Transaction(
            date="2024-01-13", description="CHECKCARD 1314 SAFEWAY #2910",
            amount=Decimal("-64.22"), category=None, source_file="test.csv",
            transaction_type="expense", category_source="", raw={},
        )
        ToolLoopFinanceAgent(llm)._categorize_missing([transaction])
        prompt = llm.complete.call_args.args[0]
        self.assertIn("[0] SAFEWAY | amount=-64.22", prompt)
        self.assertNotIn("CHECKCARD", prompt)
        self.assertEqual(transaction.description, "CHECKCARD 1314 SAFEWAY #2910")
        self.assertEqual(transaction.category, "Food")
