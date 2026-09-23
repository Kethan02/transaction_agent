import json
import unittest

from finance_agent.categories import VALID_CATEGORIES, normalize_category
from finance_agent.categorization import build_categorization_prompt
from finance_agent.ingestion import load_transactions
from finance_agent.llm import _guess_category


class CategorizationTests(unittest.TestCase):
    def test_old_labels_are_consolidated(self):
        self.assertEqual(len(VALID_CATEGORIES), 13)
        for old, new in (("Healthcare", "Health"), ("Home", "Housing"),
                         ("Cash", "Transfers"), ("Fees", "Other")):
            self.assertEqual(normalize_category(old), new)
        transactions = load_transactions("sample_data")
        pharmacy = next(tx for tx in transactions if tx.description == "Pharmacy")
        self.assertEqual(pharmacy.category, "Health")
        self.assertEqual(pharmacy.raw["Category"], "Healthcare")

    def test_rent_is_separate_from_housing_and_transfers(self):
        self.assertEqual(normalize_category("rent"), "Rent")
        self.assertEqual(_guess_category("ZELLE PAYMENT TO LANDLORD"), "Rent")
        self.assertEqual(_guess_category("VENMO RENT"), "Rent")
        self.assertEqual(_guess_category("HOME DEPOT"), "Housing")
        self.assertEqual(_guess_category("ZELLE PAYMENT TO JOHN"), "Transfers")
        prompt = build_categorization_prompt(load_transactions("sample_data"))
        self.assertIn("- Rent: Rent payments", prompt)

    def test_prompt_uses_one_source_example_per_category(self):
        transactions = load_transactions("sample_data")
        # A previous model decision must not become a labeled source example.
        missing = next(tx for tx in transactions if not tx.category)
        missing.category = "Other"
        missing.category_source = "llm"
        prompt = build_categorization_prompt(transactions)
        examples = json.loads(prompt.split(
            "Existing CSV-labeled examples (category to description):\n"
        )[1].splitlines()[0])
        self.assertEqual(examples, {
            "Food": "Grocery Store", "Transportation": "Gas Station",
            "Shopping": "Amazon Purchase", "Entertainment": "Netflix Subscription",
            "Health": "Pharmacy", "Housing": "Home Depot",
            "Insurance": "Car Insurance", "Utilities": "COMCAST CABLE COMM",
        })
        self.assertIn("- Transfers:", prompt)
        self.assertNotIn("Transfers", examples)
        self.assertNotIn("Other", examples)
        self.assertIn("AMZN MKTP US | amount=-129.99", prompt)
