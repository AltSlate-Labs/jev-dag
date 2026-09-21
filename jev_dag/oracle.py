"""Oracles — the decision backend for a jev-dag graph.

An Oracle resolves one decision at a time: given a state + a typed question + bounded candidates,
it returns a choice / yes-no / score with a calibrated probability distribution and confidence.

`JevOracle` is the real, default backend (TypeSafe's Jev API) — it is what the graph uses to make
every decision. `ScriptedOracle` is a deterministic stand-in for tests and offline development; it
is a test fixture, never a runtime fallback.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class Oracle(Protocol):
    """Anything that can resolve the three decision types a jev-dag node uses."""

    def choice(self, state: str, question: str, options: dict[str, str]) -> dict:
        """Pick one of `options` ({id: description}). Returns {choice, confidence, probabilities}."""

    def noul(self, state: str, question: str, true_desc: str, false_desc: str) -> float:
        """Yes/no gate. Returns P(true) in [0, 1]."""

    def score(self, state: str, question: str, levels: list[str]) -> dict:
        """Rubric score over ordered `levels`. Returns {score, confidence, probabilities}."""


class JevOracle:
    """The default backend: TypeSafe's Jev (https://docs.typesafe.ai/api). Fast, cheap, calibrated.

    Reads the API key from the JEV_KEY env var (never hard-code it). Accumulates token usage so a
    run can report exact cost, and retries 429/529 with exponential backoff.
    """

    URL = "https://api.typesafe.ai/v1/systemone"
    MODEL = "jev-latest"

    def __init__(self, key: str | None = None, *, retries: int = 4):
        self.key = key or os.environ.get("JEV_KEY")
        if not self.key:
            raise RuntimeError("JEV_KEY not set (export it, or pass key=...).")
        self.retries = retries
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def _post(self, state, questions: dict) -> dict:
        body = json.dumps({"state": state, "model": self.MODEL, "questions": questions}).encode()
        for attempt in range(self.retries):
            req = urllib.request.Request(
                self.URL, data=body, method="POST",
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    out = json.loads(resp.read())
                u = out.get("usage", {})
                self.usage["calls"] += 1
                self.usage["input_tokens"] += u.get("input_tokens", 0)
                self.usage["output_tokens"] += u.get("output_tokens", 0)
                return out["answers"]
            except urllib.error.HTTPError as e:
                if e.code in (429, 529) and attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Jev HTTP {e.code}: {e.read().decode()[:200]}") from e
        raise RuntimeError("Jev: retries exhausted")

    def choice(self, state, question, options):
        a = self._post(state, {"q": {"type": "choice", "instructions": question, "criteria": options}})
        return a["q"]

    def noul(self, state, question, true_desc, false_desc):
        a = self._post(state, {"q": {"type": "noul", "instructions": question,
                                     "criteria": {"true": true_desc, "false": false_desc}}})
        return a["q"]["noul"]

    def score(self, state, question, levels):
        a = self._post(state, {"q": {"type": "score", "instructions": question, "criteria": levels}})
        return a["q"]

    def batch(self, state, questions: dict) -> dict:
        """Resolve several independent questions in one request (cheaper: shared input tokens)."""
        return self._post(state, questions)


class ScriptedOracle:
    """Deterministic oracle for tests / offline use. NOT a runtime fallback.

    `picks` maps a question string to either an option id (choice), an ordered list of ids
    (choice, ranked — first is chosen, used to exercise branching), or a float (noul P(true)).
    Records every call in `.calls` so tests can assert what state each decision received.
    """

    def __init__(self, picks: dict | None = None):
        self.picks = picks or {}
        self.calls: list[dict] = []
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def choice(self, state, question, options):
        self.calls.append({"kind": "choice", "question": question, "state": state,
                           "options": list(options)})
        keys = list(options)
        pick = self.picks.get(question)
        ranked = pick if isinstance(pick, list) else ([pick] if isinstance(pick, str) else keys)
        ranked = [k for k in ranked if k in options] or keys
        n = len(ranked)
        probs = {k: 0.0 for k in keys}
        for i, k in enumerate(ranked):                       # descending probability by rank
            probs[k] = round((n - i) / (n * (n + 1) / 2), 4)
        self.usage["calls"] += 1
        return {"choice": ranked[0], "confidence": 1.0, "probabilities": probs}

    def noul(self, state, question, true_desc, false_desc):
        self.calls.append({"kind": "noul", "question": question, "state": state})
        self.usage["calls"] += 1
        p = self.picks.get(question, 1.0)
        return float(p) if not isinstance(p, (list, str)) else 1.0

    def score(self, state, question, levels):
        self.calls.append({"kind": "score", "question": question, "state": state})
        self.usage["calls"] += 1
        return {"score": len(levels) - 1, "confidence": 1.0,
                "probabilities": {lv: (1.0 if i == len(levels) - 1 else 0.0)
                                  for i, lv in enumerate(levels)}}
