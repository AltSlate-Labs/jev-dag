"""General (non-design) example: choose a web-app tech stack for a project brief.

Shows jev-dag is domain-agnostic — the same engine that picks UI decisions picks engineering ones.
Every decision is an enumerated choice over a closed set; hard constraints live in the candidate
recipes; Jev makes each call. Run:

    export JEV_KEY=...   # your TypeSafe key
    python -m examples.tech_stack
"""
from jev_dag import Decision, Graph, JevOracle, run

BRIEF = (
    "Project: a realtime collaborative kanban board for small teams.\n"
    "Constraints: the team knows Python well; must ship fast; must be self-hostable; "
    "live multi-user updates are essential."
)

FRONTENDS = {
    "react": "React — largest ecosystem, most hiring, heavier",
    "svelte": "Svelte — compact, fast, less boilerplate",
    "vue": "Vue — gentle learning curve, solid ecosystem",
    "htmx": "HTMX — server-rendered, minimal JS, pairs with a Python backend",
}
BACKENDS = {
    "fastapi": "FastAPI (Python) — async, great for websockets, quick to build",
    "django": "Django (Python) — batteries included, heavier",
    "express": "Node/Express (JS) — same language as the frontend",
    "go": "Go — fast, but a new language for this team",
}


def _styling(state, ans):
    opts = {"tailwind": "Tailwind — utility-first, fast to build",
            "css_modules": "CSS Modules — scoped plain CSS"}
    if ans.get("frontend") == "react":                      # hard constraint in code, not Jev
        opts["styled_components"] = "styled-components — CSS-in-JS (React only)"
    return opts


def _database(state, ans):
    opts = {"postgres": "PostgreSQL — robust, relational, self-hostable",
            "sqlite": "SQLite — zero-ops, single file, great for small/self-hosted"}
    if ans.get("backend") in ("express", "go"):
        opts["mongo"] = "MongoDB — document store"
    return opts


GRAPH = Graph([
    Decision("realtime", "Does this project require live, multi-user realtime updates?",
             kind="noul",
             noul_desc=("Realtime collaboration is essential",
                        "Periodic refresh or manual reload is acceptable")),
    Decision("frontend", "Which frontend approach fits the brief best?",
             branch=True, candidates=lambda s, a: FRONTENDS),
    Decision("backend", "Which backend fits the team and constraints best?",
             candidates=lambda s, a: BACKENDS),
    Decision("styling", "Which styling approach?", depends_on=["frontend"], candidates=_styling),
    Decision("transport", "Which realtime transport?", depends_on=["realtime", "backend"],
             activate=lambda s, a: a.get("realtime"),
             candidates=lambda s, a: {"websockets": "WebSockets — full duplex, best for live boards",
                                      "sse": "Server-Sent Events — one-way, simpler",
                                      "polling": "Short polling — simplest, least live"}),
    Decision("database", "Which database?", depends_on=["backend"], candidates=_database),
    Decision("deploy", "Which deployment target?", depends_on=["backend"],
             candidates=lambda s, a: {"docker": "Docker Compose — self-hostable anywhere",
                                      "fly": "Fly.io — managed, cheap",
                                      "vercel": "Vercel — managed, frontend-first"}),
])

COHERENCE = ("Rate how well this stack fits the brief (team skills, speed, self-hosting, realtime).",
             ["Poor fit", "Weak", "Acceptable", "Strong", "Excellent fit"],
             lambda ans: "PROPOSED STACK:\n" + "\n".join(f"- {k}: {v}" for k, v in ans.items()))


def main():
    result = run(GRAPH, BRIEF, JevOracle(), coherence=COHERENCE)
    print(BRIEF, "\n")
    for i, alt in enumerate(result.alternatives, 1):
        q = alt.quality
        print(f"--- alternative {i}  (fit {q['score']}/4, conf {q['confidence']}) ---")
        for t in alt.trace:
            if t.get("active") is False:
                continue
            pick = t.get("choice", t.get("answer"))
            conf = f" [{t['confidence']}]" if "confidence" in t else ""
            print(f"  {t['node']:10} -> {pick}{conf}")
        print()
    print(f"Jev usage: {result.usage}")


if __name__ == "__main__":
    main()
