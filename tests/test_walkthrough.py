import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class WalkthroughTests(unittest.TestCase):
    def test_trace_follows_replay_without_changing_report(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            run = subprocess.run([
                sys.executable, "-m", "finance_agent", "--data", "sample_data",
                "--out", str(output), "--replay", "recordings/tool_loop_llm_responses.json",
                "--trace", "safeway",
            ], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            for stage in ("source:", "normalized:", "categorization input:",
                          "categorization result:", "report:", "contribution to final totals:"):
                self.assertIn(stage, run.stderr)
            self.assertIn('"cleaned_description": "SAFEWAY"', run.stderr)
            self.assertIn('"category": "Food"', run.stderr)
            self.assertEqual(json.loads(output.read_text()), json.loads(Path("report.json").read_text()))

    def test_demo_bypasses_provider_and_recording(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            recording = Path(tmp) / "unused.json"
            run = subprocess.run([
                sys.executable, "-m", "finance_agent", "--data", "sample_data",
                "--out", str(output), "--demo-bad-response", "--trace", "SAFEWAY",
                "--replay", str(Path(tmp) / "nonexistent.json"), "--recording", str(recording),
            ], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("[demo]", run.stderr)
            self.assertIn("[fallback]", run.stderr)
            self.assertIn("[warning]", run.stderr)
            self.assertNotIn("categorization input:", run.stderr)
            self.assertIn('"category_source": "default"', run.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(len(report["warnings"]), 2)
            self.assertFalse(recording.exists())

    def test_trace_reports_no_match(self):
        with TemporaryDirectory() as tmp:
            run = subprocess.run([
                sys.executable, "-m", "finance_agent", "--data", "sample_data",
                "--out", str(Path(tmp) / "report.json"), "--demo-bad-response",
                "--trace", "NO MATCH HERE",
            ], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("No retained transactions match", run.stderr)
