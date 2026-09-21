"""UI-design example: instantiate a small, closed design system for a brief.

This is the motivating use case — with a fixed design system the design vocabulary is *closed*, so
every decision is an enumerated Jev selection: no generation, slop-free by construction, fast and
cheap. Run:

    export JEV_KEY=...
    python -m examples.ui_design
"""
from jev_dag import Decision, Graph, JevOracle, run

BRIEF = (
    "Internal admin console for support agents to review and resolve customer tickets.\n"
    "Agents work all day at a desk, keyboard-first, and compare several tickets while resolving one.\n"
    "Must show ticket status, priority, customer, and SLA timer. Desktop-first; dense over pretty."
)

# --- A tiny CLOSED design system (finite catalogs). Real systems just have bigger sets. ---------
PRIMARY_TASKS = {
    "triage_queue": "Work a prioritized queue of incoming tickets fast",
    "compare_resolve": "Compare several tickets side by side while resolving one",
    "deep_single": "Focus on one ticket at a time in depth",
}
LAYOUTS = {
    "list_detail": "Master list on the left, detail pane on the right",
    "split_compare": "Two/three ticket panes side by side for comparison",
    "table_drawer": "Dense table of tickets; detail opens in a drawer",
    "single_focus": "One full-width ticket at a time with prev/next",
}
MAIN_COMPONENTS = {
    "data_table": "Dense, sortable table of tickets",
    "card_list": "Scannable list of ticket cards",
    "compare_grid": "Grid of ticket panels aligned for comparison",
}
DENSITY = {"compact": "Compact rows, more on screen", "comfortable": "Roomier spacing"}


def _main_component(state, ans):
    """Hard constraint in code: a comparison task must use the comparison grid."""
    if ans.get("primary_task") == "compare_resolve":
        return {"compare_grid": MAIN_COMPONENTS["compare_grid"]}
    return {k: v for k, v in MAIN_COMPONENTS.items() if k != "compare_grid"}


GRAPH = Graph([
    Decision("primary_task", "What is the agent's primary task on this screen?",
             branch=True, candidates=lambda s, a: PRIMARY_TASKS),
    Decision("layout", "Which layout from the design system best supports that task?",
             depends_on=["primary_task"], branch=True, candidates=lambda s, a: LAYOUTS),
    Decision("main_component", "Which component leads the main region?",
             depends_on=["primary_task", "layout"], candidates=_main_component),
    Decision("density", "Which density?", depends_on=["primary_task"],
             candidates=lambda s, a: DENSITY),
])

COHERENCE = ("Rate how coherently this design serves the brief's task, workflow, and density needs.",
             ["Incoherent", "Weak", "Acceptable", "Strong", "Excellent"],
             lambda ans: "DESIGN:\n" + "\n".join(f"- {k}: {v}" for k, v in ans.items()))


def main():
    result = run(GRAPH, BRIEF, JevOracle(), coherence=COHERENCE)
    print(BRIEF, "\n")
    for i, alt in enumerate(result.alternatives, 1):
        q = alt.quality
        print(f"--- design {i}  (coherence {q['score']}/4, conf {q['confidence']}) ---")
        for t in alt.trace:
            if t.get("active") is False:
                continue
            print(f"  {t['node']:14} -> {t.get('choice', t.get('answer'))}")
        print()
    print(f"top pick: design 1 | Jev usage: {result.usage}")


if __name__ == "__main__":
    main()
