"""Live smoke test for the real Jev oracle. Skipped unless JEV_KEY is set (so CI stays offline)."""
import os

import pytest

from jev_dag import Decision, Graph, run
from jev_dag.oracle import JevOracle

pytestmark = pytest.mark.skipif(not os.environ.get("JEV_KEY"), reason="JEV_KEY not set")


def test_jev_choice_roundtrip():
    o = JevOracle()
    r = o.choice("A user must compare two invoices side by side before approving one.",
                 "What is the primary task?",
                 {"compare": "Compare records", "triage": "Sort a queue", "detail": "Deep single view"})
    assert r["choice"] in {"compare", "triage", "detail"}
    assert 0.0 <= r["confidence"] <= 1.0
    assert abs(sum(r["probabilities"].values()) - 1.0) < 0.05


def test_small_graph_runs_on_jev():
    g = Graph([
        Decision("task", "What is the primary task?",
                 candidates=lambda s, a: {"compare": "Compare records", "triage": "Sort a queue"}),
        Decision("layout", "Which layout fits?", depends_on=["task"],
                 candidates=lambda s, a: {"split": "Side by side", "list": "Single list"}),
    ])
    res = run(g, "Agents compare two tickets side by side before resolving.", JevOracle())
    assert res.top.answers["task"] in {"compare", "triage"}
    assert res.usage["calls"] >= 2
