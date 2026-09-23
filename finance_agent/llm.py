from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


class RecordingLLM:
    def __init__(self, inner: LLMClient, path: str | Path):
        self.inner = inner
        self.path = Path(path)
        self.records: list[dict[str, str]] = []

    def complete(self, prompt: str) -> str:
        response = self.inner.complete(prompt)
        self.records.append({"prompt": prompt, "response": response})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.records, indent=2), encoding="utf-8")
        return response


class ReplayLLM:
    def __init__(self, path: str | Path):
        self.records = json.loads(Path(path).read_text(encoding="utf-8"))
        self.index = 0

    def complete(self, prompt: str) -> str:
        if self.index >= len(self.records):
            raise RuntimeError("Replay recording exhausted")
        response = self.records[self.index]["response"]
        self.index += 1
        return response


class ScriptedLLM:
    """Deterministic offline stand-in used for development and tests."""

    def __init__(self, bad_first_response: bool = False):
        self.agent_step = 0
        self.bad_first_response = bad_first_response

    def complete(self, prompt: str) -> str:
        if prompt.startswith("TOOL_LOOP_AGENT_STEP"):
            if self.bad_first_response and self.agent_step == 0:
                self.agent_step += 1
                return "this is not json"
            tools = ("categorize_missing", "compute_totals", "write_report")
            tool = tools[min(self.agent_step, len(tools) - 1)]
            self.agent_step += 1
            return json.dumps({"tool": tool, "args": {}})

        if prompt.startswith("CATEGORIZE_TRANSACTIONS"):
            return json.dumps(_categorize_from_prompt(prompt))

        return "{}"


class OllamaLLM:
    def __init__(self, model: str):
        self.model = model

    def complete(self, prompt: str) -> str:
        import urllib.request

        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}
        ).encode("utf-8")
        request = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["response"]


def build_llm(provider: str, recording_path: str | Path, replay_path: str | Path | None = None) -> LLMClient:
    if replay_path:
        return ReplayLLM(replay_path)

    if provider == "ollama":
        inner: LLMClient = OllamaLLM(os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    elif provider == "scripted":
        inner = ScriptedLLM()
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return RecordingLLM(inner, recording_path)


def _categorize_from_prompt(prompt: str) -> dict[str, str]:
    descriptions = re.findall(r"\[(\d+)\] ([^\n]+)", prompt)
    return {index: _guess_category(description) for index, description in descriptions}


def _guess_category(description: str) -> str:
    text = description.lower()
    if "landlord" in text or re.search(r"\brent\b", text):
        return "Rent"
    if any(term in text for term in ("wholefds", "safeway", "pizza", "doordash", "starbucks")):
        return "Food"
    if any(term in text for term in ("shell", "uber", "lyft")):
        return "Transportation"
    if any(term in text for term in ("amzn", "etsy", "costco")):
        return "Shopping"
    if any(term in text for term in ("spotify", "netflix", "apple.com")):
        return "Entertainment"
    if "cvs" in text or "pharmacy" in text:
        return "Health"
    if "home depot" in text or "homedepot" in text:
        return "Housing"
    if "geico" in text:
        return "Insurance"
    if "comcast" in text:
        return "Utilities"
    if "atm" in text:
        return "Transfers"
    if "venmo" in text or "zelle" in text:
        return "Transfers"
    return "Other"

