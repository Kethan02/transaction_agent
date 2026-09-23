from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .llm import build_llm
from .tool_loop_agent import ToolLoopFinanceAgent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the personal finance agent.")
    parser.add_argument("--data", required=True, help="Directory containing the four CSV files.")
    parser.add_argument("--out", required=True, help="Path to write report.json.")
    parser.add_argument(
        "--provider",
        default="ollama",
        choices=("scripted", "ollama"),
        help="LLM provider to use. Defaults to local Ollama.",
    )
    parser.add_argument(
        "--recording",
        help="Recording path. Defaults to recordings/tool_loop_llm_responses.json for Ollama, "
             "or recordings/scripted_llm_responses.json for scripted mode.",
    )
    parser.add_argument("--replay", help="Replay LLM responses from this recording file.")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        mode = f"replay ({args.replay})" if args.replay else args.provider
        logging.info("[start] Mode: %s", mode)
        recording = args.recording or (
            "recordings/tool_loop_llm_responses.json" if args.provider == "ollama"
            else "recordings/scripted_llm_responses.json"
        )
        llm = build_llm(args.provider, recording, args.replay)
        agent = ToolLoopFinanceAgent(llm)
        agent.run(Path(args.data), Path(args.out))
    except Exception as exc:
        print(f"finance-agent failed: {exc}", file=sys.stderr)
        return 1

    return 0
