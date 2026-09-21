"""Core executor tests — deterministic, no network (ScriptedOracle). Run: pytest -q"""
import pytest

from jev_dag import Decision, Graph, ScriptedOracle, run


def _chain():
    return Graph([
        Decision("a", "Pick A?", candidates=lambda s, ans: {"a1": "one", "a2": "two"}),
        Decision("b", "Pick B?", depends_on=["a"],
                 candidates=lambda s, ans: {"b1": "one", "b2": "two"}),
    ])


def test_topo_and_ancestors():
    g = _chain()
    assert g.order == ["a", "b"]
    assert g.ancestors["b"] == {"a"}
    assert g.ancestors["a"] == set()


def test_cycle_detected():
    with pytest.raises(ValueError):
        Graph([Decision("x", "?", depends_on=["y"], candidates=lambda s, a: {"o": "d"}),
               Decision("y", "?", depends_on=["x"], candidates=lambda s, a: {"o": "d"})])


def test_unknown_dependency_rejected():
    with pytest.raises(ValueError):
        Graph([Decision("x", "?", depends_on=["nope"], candidates=lambda s, a: {"o": "d"})])


def test_ancestor_answers_reach_the_oracle_state():
    g = _chain()
    o = ScriptedOracle(picks={"Pick A?": "a2"})
    run(g, "BASE", o)
    b_call = next(c for c in o.calls if c["question"] == "Pick B?")
    assert "PRIOR DECISIONS: a=a2" in b_call["state"]        # b literally receives a's answer
    a_call = next(c for c in o.calls if c["question"] == "Pick A?")
    assert "PRIOR DECISIONS" not in a_call["state"]          # root sees no priors


def test_branching_produces_distinct_alternatives():
    g = Graph([Decision("a", "Pick A?", branch=True,
                        candidates=lambda s, ans: {"a1": "one", "a2": "two", "a3": "three"})])
    o = ScriptedOracle(picks={"Pick A?": ["a1", "a2", "a3"]})   # ranked -> top-2 retained
    res = run(g, "BASE", o, branches=2)
    picks = sorted(a.answers["a"] for a in res.alternatives)
    assert picks == ["a1", "a2"]


def test_activate_if_skips_node():
    g = Graph([
        Decision("gate", "gate?", kind="noul", noul_desc=("t", "f")),
        Decision("maybe", "maybe?", depends_on=["gate"],
                 activate=lambda s, ans: ans.get("gate") is True,
                 candidates=lambda s, ans: {"o": "d"}),
    ])
    o = ScriptedOracle(picks={"gate?": 0.0})                 # noul false -> maybe deactivated
    res = run(g, "BASE", o)
    assert res.alternatives[0].answers.get("maybe") is None
    assert any(t["node"] == "maybe" and t.get("active") is False for t in res.alternatives[0].trace)


def test_hard_constraint_lives_in_candidate_recipe():
    # 'main' offers only the compare grid once the task is comparison — the oracle never sees others.
    def cands(state, ans):
        return {"grid": "compare"} if ans.get("task") == "compare" else {"table": "t", "cards": "c"}
    g = Graph([
        Decision("task", "task?", candidates=lambda s, a: {"compare": "x", "triage": "y"}),
        Decision("main", "main?", depends_on=["task"], candidates=cands),
    ])
    o = ScriptedOracle(picks={"task?": "compare"})
    res = run(g, "BASE", o)
    main_call = next(c for c in o.calls if c["question"] == "main?")
    assert main_call["options"] == ["grid"]                  # invalid options filtered before Jev


def test_dedupe_and_coherence_ranks_best_first():
    g = Graph([Decision("a", "Pick A?", branch=True,
                        candidates=lambda s, ans: {"a1": "one", "a2": "two"})])
    o = ScriptedOracle(picks={"Pick A?": ["a1", "a2"]})
    coherence = ("rate", ["low", "high"], lambda ans: str(ans))
    res = run(g, "BASE", o, branches=2, coherence=coherence)
    assert res.top is res.alternatives[0]
    assert all(a.quality is not None for a in res.alternatives)


def test_usage_is_reported():
    g = _chain()
    o = ScriptedOracle()
    res = run(g, "BASE", o)
    assert res.usage["calls"] == 2


def test_example_graphs_run_offline():
    from examples.tech_stack import GRAPH as TECH
    from examples.ui_design import GRAPH as UI
    for g in (TECH, UI):
        res = run(g, "some brief", ScriptedOracle())
        assert res.alternatives and res.top is not None
