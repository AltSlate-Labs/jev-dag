"""jev-dag — resolve a DAG of enumerated decisions with a fast judgment oracle (Jev by default).

    from jev_dag import Decision, Graph, run, JevOracle

    graph = Graph([Decision("framework", "Which UI framework?", candidates=lambda s, a: {...}), ...])
    result = run(graph, brief, JevOracle())
    print(result.top.answers)
"""
from .graph import Alternative, Decision, Graph, Result, run
from .oracle import JevOracle, Oracle, ScriptedOracle

__all__ = ["Decision", "Graph", "Alternative", "Result", "run",
           "Oracle", "JevOracle", "ScriptedOracle"]
__version__ = "0.1.0"
