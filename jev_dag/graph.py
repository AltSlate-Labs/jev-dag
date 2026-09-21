"""jev-dag core: a DAG of enumerated decisions, resolved by an Oracle.

You describe the *space* of valid outcomes as a graph of typed decisions — each with its
dependencies, a recipe that enumerates its bounded candidates, and (optionally) an activation
condition. A generic executor walks the graph and, for every decision, hands the Oracle the
problem statement plus every ancestor's answer, records the full trace, and forks at branch nodes
to produce several alternatives. Hard constraints live in your candidate recipe (code) so the
Oracle is never offered an invalid option.

Nothing here is design-specific: `state` is any problem statement, and candidates are any bounded
set of options. See examples/ for a general (tech-stack) graph and a UI-design graph.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from .oracle import Oracle


@dataclass
class Decision:
    """One node. `candidates(state, answers) -> {id: description}` enumerates the bounded options
    (put hard constraints here — filter before the Oracle sees them). `activate` (optional) skips
    the node when it's irrelevant. `branch=True` retains the top-`branches` options as forks."""
    id: str
    question: str
    depends_on: list[str] = field(default_factory=list)
    kind: str = "choice"                                    # "choice" | "noul"
    candidates: Callable[[str, dict], dict] | None = None
    activate: Callable[[str, dict], bool] | None = None
    branch: bool = False
    noul_desc: tuple[str, str] | None = None                # (true_desc, false_desc) for noul


@dataclass
class Alternative:
    """One finished outcome: the resolved answers, the decision trace, and optional quality."""
    answers: dict
    trace: list
    quality: dict | None = None


@dataclass
class Result:
    alternatives: list
    usage: dict
    top: Alternative | None = None


class Graph:
    """A validated DAG of Decisions."""

    def __init__(self, decisions: list[Decision]):
        self.decisions = decisions
        self.nodes = {d.id: d for d in decisions}
        self._validate()
        self.order = self._topo()
        self.ancestors = {d.id: self._ancestors(d.id) for d in decisions}

    def _validate(self):
        if len(self.nodes) != len(self.decisions):
            raise ValueError("duplicate decision id")
        for d in self.decisions:
            for dep in d.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"{d.id} depends on unknown node {dep!r}")
            if d.kind == "choice" and d.candidates is None:
                raise ValueError(f"choice node {d.id} needs a candidates recipe")
            if d.kind == "noul" and not d.noul_desc:
                raise ValueError(f"noul node {d.id} needs noul_desc=(true, false)")

    def _topo(self) -> list[str]:
        indeg = {d.id: len(d.depends_on) for d in self.decisions}
        idx = {d.id: i for i, d in enumerate(self.decisions)}    # tie-break by declaration order
        order, remaining = [], set(indeg)
        while remaining:
            ready = [x for x in remaining if indeg[x] == 0]
            if not ready:
                raise ValueError("cycle detected — graph is not a DAG")
            nid = min(ready, key=lambda x: idx[x])
            order.append(nid)
            remaining.remove(nid)
            for d in self.decisions:
                if nid in d.depends_on:
                    indeg[d.id] -= 1
        return order

    def _ancestors(self, nid: str) -> set:
        out, stack = set(), list(self.nodes[nid].depends_on)
        while stack:
            d = stack.pop()
            if d not in out:
                out.add(d)
                stack.extend(self.nodes[d].depends_on)
        return out


def _state(base: str, priors: dict) -> str:
    if not priors:
        return base
    return base + "\n\nPRIOR DECISIONS: " + "; ".join(f"{k}={v}" for k, v in priors.items())


def _run_node(graph: Graph, node: Decision, base_state: str, alt: Alternative,
              oracle: Oracle, branches: int, noul_threshold: float) -> list[Alternative]:
    priors = {k: alt.answers[k] for k in graph.ancestors[node.id] if k in alt.answers}

    if node.activate and not node.activate(base_state, alt.answers):
        alt.trace.append({"node": node.id, "active": False, "priors": priors})
        return [alt]

    state = _state(base_state, priors)

    if node.kind == "noul":
        p = oracle.noul(state, node.question, *node.noul_desc)
        alt.answers[node.id] = p >= noul_threshold
        alt.trace.append({"node": node.id, "question": node.question, "noul": round(p, 3),
                          "answer": alt.answers[node.id], "priors": priors})
        return [alt]

    options = node.candidates(base_state, alt.answers)
    if not options:
        raise ValueError(f"node {node.id}: candidate recipe returned no options")
    ans = oracle.choice(state, node.question, options)
    entry = {"node": node.id, "question": node.question, "candidates": options,
             "confidence": ans["confidence"], "probabilities": ans["probabilities"], "priors": priors}

    if node.branch:
        tops = [k for k, _ in sorted(ans["probabilities"].items(), key=lambda kv: -kv[1])][:branches]
        forks = []
        for opt in tops:
            f = Alternative(answers=copy.deepcopy(alt.answers), trace=copy.deepcopy(alt.trace))
            f.answers[node.id] = opt
            f.trace.append({**entry, "choice": opt})
            forks.append(f)
        return forks

    alt.answers[node.id] = ans["choice"]
    alt.trace.append({**entry, "choice": ans["choice"]})
    return [alt]


def run(graph: Graph, state: str, oracle: Oracle, *, branches: int = 2, max_alts: int = 3,
        max_partials: int = 8, noul_threshold: float = 0.5, coherence=None) -> Result:
    """Walk `graph` over problem `state`, resolving each decision with `oracle`.

    Branch nodes fork the run (top-`branches`); results are de-duplicated by their answer set and
    capped at `max_alts`. `coherence`, if given, is (question, levels, spec_fn): a final Oracle
    `score` over each alternative (spec_fn(answers) -> str) that ranks them best-first.
    """
    alts = [Alternative(answers={}, trace=[])]
    for nid in graph.order:
        node = graph.nodes[nid]
        nxt: list[Alternative] = []
        for alt in alts:
            nxt.extend(_run_node(graph, node, state, alt, oracle, branches, noul_threshold))
        alts = nxt[:max_partials]

    seen, deduped = set(), []
    for a in alts:
        key = tuple(sorted((k, str(v)) for k, v in a.answers.items()))
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    alts = deduped[:max_alts]

    if coherence:
        question, levels, spec_fn = coherence
        for a in alts:
            r = oracle.score(f"{state}\n\n{spec_fn(a.answers)}", question, levels)
            a.quality = {"score": round(r["score"], 2), "confidence": r["confidence"]}
        alts.sort(key=lambda a: -(a.quality["score"] if a.quality else 0))

    return Result(alternatives=alts, usage=dict(getattr(oracle, "usage", {})),
                  top=alts[0] if alts else None)
