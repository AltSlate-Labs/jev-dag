# Why jev-dag — the reasoning

[← back to README](../README.md)

## The problem: generation samples, and the modal sample is generic

When you ask one model to produce a whole artifact — a UI, a stack, a plan — it **samples** from a
distribution. The high-probability, modal region of that distribution is the *generic* one: it's the
center of mass of everything the model has seen. That's why one-shot generation drifts to templated,
"safe", samey output ("slop"). You can fight it with better sampling (best-of-N, temperature, DPO),
but you're still sampling, and you're still fighting the mode.

## The move: replace sampling with selection

A judgment oracle like [Jev](https://docs.typesafe.ai/api) doesn't generate — it **discriminates**:
given a state, a typed question, and a *bounded* set of candidates, it returns a choice / yes-no /
score with a calibrated probability distribution and confidence.

So jev-dag reframes the task:

1. **Factor the artifact into a DAG of dependent decisions**, each with a *small, enumerable*
   candidate set.
2. **The oracle chooses at each node**, seeing the problem statement plus every ancestor's answer.
3. **Code holds the invariants** — hard constraints filter candidates *before* the oracle sees them;
   the candidate recipe, the graph shape, and validation stay deterministic.

Where the candidate set is closed, this converts *generation* into *selection*: enumerate the
options, let the oracle pick, and a bad option can't appear because it isn't in the set (or the
oracle rejects it). The oracle is the thinnest part of each node.

## Where this is strongest: a fixed vocabulary (e.g. a design system)

"Enumerate every option" sounds impossible in the abstract, but it becomes natural the moment you
work inside a **fixed vocabulary** — a design system, a component catalog, an approved tech radar,
a policy set. The vocabulary is *closed*, so every decision is an enumerated selection:

- **No generation → no coverage gamble.** You never ask a model to invent a candidate; you enumerate
  from the catalog. The unreliable generative problem ("did the model propose something good?")
  becomes a bounded, verifiable **curation** problem ("does our catalog contain something good?").
- **Fast & cheap.** Each node is one small oracle call (Jev returns ~tens of tokens). Independent
  nodes run in parallel; the latency floor is the graph's *critical path*, not its node count.
- **Slop-free by construction.** A generic option is either absent from the vocabulary or rejected.
- **Auditable, and gap-detecting.** Every outcome is a trace of decisions + evidence. Low oracle
  confidence (or a low coherence score) is a signal that *the vocabulary lacks a good option here* —
  a curation feedback loop you don't get from a black-box generator.

## Empirical notes (from the R&D spike this grew out of)

Findings from applying the DAG + Jev pattern to real UI-design briefs (in a private predecessor):

- **Jev reliably makes the less-sloppy choice.** Given the brief and two options (one on-brief, one
  a generic anti-pattern), it picked on-brief ~240/240 on blatant contrasts and ~200/200 on subtle
  ones (shared palette/fonts, neutral framing) — without being told what "slop" was, and with no
  position bias. It even *overrode a mislabelled ground truth* by reading the brief, which is the
  clearest sign it judges fit rather than matching keywords.
- **Coverage, not the oracle, is the bottleneck.** A decision graph authored for one domain only
  produced good outcomes for that domain; the oracle correctly scored off-domain outcomes near-zero.
  Supplying per-brief candidates (closing the vocabulary) lifted quality ~5× across every failing
  domain. **The oracle selects well; the value is bounded by what's in the candidate set.**

That is exactly why this library separates the two: the **graph + oracle** (reliable selection) is
the engine; the **candidate recipes** (your vocabulary/coverage) are where the domain lives.

## Scaling

- **Composition, not one giant graph.** Like a programming language scales via functions, a design
  space scales via a small library of reusable decision primitives and sub-graphs composed per brief.
- **Keep the graph *thin*.** A "fat" graph that encodes knowledge in its topology is an expert
  system and hits the classic knowledge-acquisition wall. A thin graph that only provides structure +
  typing + verification, while the vocabulary supplies knowledge and the oracle supplies judgment,
  can scale.
- **Parallelism is free along the DAG.** Independent nodes (antichains) and separate branches run
  concurrently; batch independent questions into one oracle call. Latency scales with depth, not
  size.
- **The tension to budget for:** independently-resolved decisions can conflict at the seams (shared
  tokens, cross-cutting consistency). Thread a shared constraint/token context through composition,
  or add a reconciliation pass — parallelism buys latency, not global coherence.

## Honest limits

- The oracle judges the **state you give it** (text/structure), not pixels — a visual/aesthetic layer
  needs a vision judge or a human on top.
- Quality is bounded by the **candidate vocabulary's completeness** (a curation problem — verifiable,
  and the confidence signal flags gaps).
- Large catalogs need a **retrieval-to-shortlist** step to fit an oracle-sized choice.
- Whether the oracle *beats* a plain LLM judge (rather than merely being sufficient, faster, and
  cheaper) is worth an A/B for your domain.

[← back to README](../README.md)
