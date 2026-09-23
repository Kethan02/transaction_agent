import json
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from finance_agent.llm import ScriptedLLM
from finance_agent.models import Transaction
from finance_agent.tool_loop_agent import ToolLoopFinanceAgent


class AgentTests(unittest.TestCase):
    def test_invalid_tool_choices_write_report_without_another_model_call(self):
        for response in ('garbage', '[]', '{}', 'null', '42',
                         '{"tool": "unknown"}', '{"tool": []}', '{"tool": {}}'):
            with self.subTest(response=response), TemporaryDirectory() as tmpdir:
                llm = Mock()
                llm.complete.side_effect = [response]
                agent = ToolLoopFinanceAgent(llm)
                output = Path(tmpdir) / "report.json"
                report = agent.run("sample_data", output)
                self.assertEqual(json.loads(output.read_text()), report)
                self.assertTrue(all(tx["category"] for tx in report["transactions"]))
                self.assertIn("invalid_tool_choice: writing report", agent.observations)
                self.assertIn("Invalid model tool choice", report["warnings"][0])
                self.assertIn("16 transaction(s) defaulted to Other", report["warnings"][1])
                llm.complete.assert_called_once()

    def test_step_limit_writes_report_without_summary_model_call(self):
        llm = Mock()
        llm.complete.side_effect = ['{"tool": "compute_totals"}'] * 2
        agent = ToolLoopFinanceAgent(llm, step_limit=2)
        with TemporaryDirectory() as tmpdir:
            report = agent.run("sample_data", Path(tmpdir) / "report.json")
        self.assertEqual(llm.complete.call_count, 2)
        self.assertIn("step_limit_reached: writing report", agent.observations)
        self.assertTrue(report["summary"])
        self.assertIn("Agent step limit reached", report["warnings"][0])
        self.assertIn("16 transaction(s) defaulted to Other", report["warnings"][1])

    def test_early_report_warns_about_missing_categories(self):
        llm = Mock()
        llm.complete.side_effect = ['{"tool": "write_report"}']
        with TemporaryDirectory() as tmpdir:
            report = ToolLoopFinanceAgent(llm).run("sample_data", Path(tmpdir) / "report.json")
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("16 transaction(s) defaulted to Other", report["warnings"][0])

    def test_invalid_categories_are_reported_even_when_workflow_finishes(self):
        llm = Mock()
        llm.complete.side_effect = [
            '{"tool": "categorize_missing"}', '{"0": "Not a category"}',
            '{"tool": "compute_totals"}', '{"tool": "write_report"}',
        ]
        with TemporaryDirectory() as tmpdir:
            report = ToolLoopFinanceAgent(llm).run("sample_data", Path(tmpdir) / "report.json")
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("16 transaction(s) defaulted to Other", report["warnings"][0])

    def test_successful_run_has_no_warnings(self):
        with TemporaryDirectory() as tmpdir:
            report = ToolLoopFinanceAgent(ScriptedLLM()).run("sample_data", Path(tmpdir) / "report.json")
        self.assertEqual(report["warnings"], [])
        self.assertTrue(any(tx["category"] == "Other" for tx in report["transactions"]))

    def test_invalid_model_category_defaults_to_other(self):
        llm = Mock()
        llm.complete.return_value = '{"0": "Not a category"}'
        transaction = Transaction(
            date="2024-01-01",
            description="Unknown merchant",
            amount=Decimal("-12.00"),
            category="",
            source_file="transactions_uncategorized.csv",
            transaction_type="expense",
            category_source="",
            raw={},
        )

        ToolLoopFinanceAgent(llm)._categorize_missing([transaction])

        self.assertIn("Valid categories and definitions:", llm.complete.call_args.args[0])
        self.assertEqual(transaction.category, "Other")
        self.assertEqual(transaction.category_source, "default")
        self.assertIn("llm_category_invalid_defaulted_other", transaction.notes)

    def test_tool_loop_survives_bad_first_model_response(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            agent = ToolLoopFinanceAgent(ScriptedLLM(bad_first_response=True))

            report = agent.run("sample_data", output)

            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)
            self.assertTrue(report["summary"])
            self.assertTrue(all(tx["category"] for tx in report["transactions"]))
            self.assertTrue(any(
                "missing_category_defaulted_before_report" in tx["notes"]
                for tx in report["transactions"]
            ))


if __name__ == "__main__":
    unittest.main()
