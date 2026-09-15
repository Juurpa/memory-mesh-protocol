# Memory Mesh Protocol (MMP) & Bridge (MMB) — Deterministic Long-Term State Architecture for Autonomous AI Agents

> A state architecture for agents that must still be correct on step 400 — not just on step 4.

**Status:** Protocol specification in preparation · Public draft forthcoming
**Availability:** Closed pilot program for selected B2B partners
**Whitepaper:** [`whitepaper_preview.pdf`](./whitepaper_preview.pdf) — *Architectural Foundations of Deterministic Agent Memory*

---

## Executive Summary

Today's autonomous agents hold their working state in one place: the conversation transcript. The transcript is simultaneously the plan, the memory, and the audit log. This has three consequences, and all three are structural rather than incidental:

1. **It tears.** When the context window ends, the thread of work is gone.
2. **It compounds in cost.** Every additional step re-reads everything that came before.
3. **It cannot be audited.** Afterwards, nobody can reconstruct what happened in which order, and on what basis.

There is a fourth consequence that matters more than the first three, and it is the one the industry has been slowest to name. A transcript does not distinguish between *what the agent was told to do* and *what the agent happened to read.* Both arrive as the same undifferentiated stream of tokens. An agent that ingested a source file two hundred steps ago cannot reliably tell you whether a sentence in its context was an operator instruction or a comment inside that file — and neither can you.

MMP/MMB replaces the transcript-as-state model with an explicit, externalized, verified state mesh:

- **MMB (Bridge)** is the ingestion and transport layer. It brings raw material — documentation, research corpora, source trees — into the mesh, and records where each piece physically came from.
- **MMP (Mesh Protocol)** is the state layer. It holds the structure, the weighting, the reference graph, and — critically — a **verification verdict** for every node, answering one question on every single read: *is what I am about to hand the agent still true?*

The shift is from **probabilistic context accumulation** to **deterministic state verification**. The agent stops being asked to remember. It is instead given, on demand, exactly the material that is provably current — and nothing else.

The architecture is **Harvard-decoupled**: data and executable authority travel on separate paths and are never interchangeable. This is not a hardening measure bolted onto a working system. It is the load-bearing decision the rest of the design rests on.

---

## Core Problems Solved

### 1. State Drift & Hallucination Suppression

An agent working from a cached copy of a file has no way to know that the file changed twenty minutes ago. It will reason confidently and fluently about code that no longer exists. This is not a model failure — no amount of model capability fixes it, because the model is not being given the information it would need to detect the problem.

MMP does not ask the model to believe anything. Every node carries an **independent, verifiable link to its physical source**, and every read path re-derives a verdict on that link before releasing content. Where a language extractor is available, verification resolves below file granularity, to the level of individual **symbol anchors** — so that an edit elsewhere in a file does not invalidate the part the agent actually needs.

The result is a system in which "this is current" is a **checked property**, not an assumption inherited from whenever the material happened to be loaded.

### 2. The Circuit Breaker Pattern

Verification is only useful if something acts on the verdict. MMP's read path is **fail-closed**: content that cannot be verified as current is **not delivered at all**.

The state lifecycle is deliberately four-valued rather than a boolean, because "changed" and "unusable" are different facts and collapsing them destroys information:

| State | Meaning | Content released? |
|---|---|---|
| `FRESH` | Verified current against the physical source | Yes |
| `DRIFTED` | Source changed; every anchor was relocated intact | Yes — **explicitly labelled**, with the extraction-time state and a re-ingest recommendation |
| `STALE` | Source changed; the anchored material could not be relocated | **No** |
| `ORPHANED` | Physical source no longer exists | **No** |

The guarantee this provides is **deterministic and fail-closed**: a `STALE` or `ORPHANED` node cannot silently supply content to an agent, because the code path that would deliver it does not exist. There is no override flag, no `force=true`, no "degraded mode" — deliberately. *An emergency exit that exists will be used.*

The design rationale is asymmetric and worth stating plainly: **a run that halts costs time; a run that proceeds on demonstrably outdated material produces wrong artifacts that then enter the mesh as new truth.** The second failure is unrecoverable in a way the first is not. So the system blocks rather than warns.

### 3. Zero-Context Overhead & Resource Conservation

Carrying a growing transcript through a long task means paying for the same material again on every step. The architectural alternative is **just-in-time symbol injection**: an agent receives the verified material for the step it is on, and the execution state — where it is in the plan, what succeeded, what failed, and why — lives **outside the context window** in the mesh rather than inside the transcript.

This makes **context wiping between steps** structurally possible: the thread of work survives, because it was never in the transcript to begin with. A run can lose its context entirely, mid-step, and resume.

**Whether discarding is worth doing is a separate, arithmetic question — and we have now measured it once rather than asserting it.** In a controlled A/B run over six steps, discarding context between steps cut input tokens by roughly a quarter and still cost more in total, in every run, with no overlap between the arms. We decline to reduce that to a single percentage: the spread *within* the discard arm was 48 percent of the difference *between* the arms.

The run's most useful output was falsifying three internals of our own pre-run cost model — carrying cost 2.96 times what we predicted; roughly 82 percent of the restart penalty was the harness rewriting unchanged standing text into its cache instead of reading it, at 12.5 times the price; and chain length does not cancel out of the balance as we had concluded. Break-even is therefore a **surface, not a threshold**, moving along at least three axes: payload carried per step, length of the chain, and how the executing harness partitions its cache — which dominated here.

By our own pre-registered criteria this run should have been discarded, and nothing in it is offered as a statistically significant result. We publish it because the corrections survive the sample size even where the percentages do not. **[Full write-up →](./empirical-measurement.md)**; the decisive run — a corpus at the threshold, three repetitions per arm, cold restarts — accompanies the protocol specification. Governing principle throughout:

> **Token reduction is never the sole objective.** The objective is the equilibrium of reduced compute *and* undiminished output quality. No destructive truncation, no summarization that discards detail relevant to a later query.

One caution we put in writing rather than leave to the reader: **cost is not an energy measure.** The discard arm processed fewer tokens and paid more money, because the tokens moved from a cheap price class to an expensive one — and a cache write is a full prefill where a cache read is not, so fewer billed tokens do not by themselves mean less computation. We did not measure energy and do not claim it. What the architecture does deliver for **audit-readiness** is separate and unaffected: an externalized, append-only execution record answers "what did this system do, when, and on what basis" without archaeology through chat logs.

---

## How It Behaves

Three properties define the system's behaviour. All three are elaborated conceptually in the whitepaper.

**State is external.** The plan, the step states, and the append-only execution record live in the mesh. The transcript becomes disposable. Resumption after context loss is a normal operation, not a recovery procedure.

**Knowledge history and execution history are separate.** *How did this knowledge evolve* and *what did this run do* are different questions and are never answered from the same record. Merging them produces one row serving two state machines — and two state machines sharing a row is a defect generator.

**Nothing is silently overwritten, and nothing is truly deleted.** Every mutation requires a mandatory justification, and superseded states are retained rather than discarded. Pruning is soft: material leaves the default working set without leaving the system. The purpose of the time axis is that no experience disappears without a trace — including the mistakes.

---

## Security: Why the Harvard Separation Is Load-Bearing

Retrieval-augmented agents share a structural vulnerability that is not solved by better prompting: **material the agent retrieved and instructions the agent was given arrive in the same channel.** An attacker who can influence any indexed file — a dependency README, a code comment, an issue description, a docstring — is writing directly into the instruction stream of every agent that later retrieves it.

In autonomous CI/CD contexts this stops being theoretical. An agent with commit or deploy authority, reading from a repository that accepts external contributions, is one poisoned comment away from executing attacker-authored intent with the operator's credentials.

MMP separates the paths at the architectural level rather than filtering at the boundary:

- Nodes carry an **`origin`** classification. Material that was *extracted* from indexed sources is **data**, permanently and by construction. It can be read, reasoned over, and cited — it can never become an instruction.
- Executable authority is reserved to explicitly **authored** material, and additionally gated on current verification state: an instruction that cannot be verified as current is not executed.
- The **`procedure`** capability — a node carrying executable behaviour — remains closed in the current protocol generation. This is a sequencing decision, not an oversight: the separation is proven and load-bearing before anything is permitted to execute.

The practical consequence: an indirect prompt injection placed in an indexed file lands in the data path. It is visible, attributable to a source, and inert. Filtering approaches try to recognize hostile instructions; this approach denies the entire class of material the authority to instruct, so recognition is not required.

---

## What This Repository Is — and Is Not

**This is a claim-staking and orientation repository.** It exists to establish the architectural claim publicly, and to let prospective partners and technical evaluators assess the approach on its merits.

It contains the executive summary and the whitepaper preview. It does **not** contain the engine, the state schemas, the verification and relocation logic, or any implementation source. That material is not omitted for tidiness — it is the substance of the work, and it is not published here.

The public protocol specification, when it is released, will describe the **protocol** — the contracts, the state semantics, the guarantees — at a depth sufficient for independent implementation, without publishing the reference engine.

---

## Licensing & Availability

| Component | Status | Licence |
|---|---|---|
| Protocol specification | Public draft forthcoming | Open specification (terms published with the draft) |
| Enterprise Engine | Closed pilot | BSL 1.1 / commercial licence |
| On-Premise Core | Closed pilot | BSL 1.1 / commercial licence |

The system is architected for **single-tenant, on-premise operation**. It is deliberately not a multi-tenant SaaS product — state verification against a physical source tree, and an audit record an operator can actually hold, both presuppose that the operator controls the machine.

The documents in this repository are published for evaluation purposes. **© 2026 — all rights reserved.** No licence to the described architecture, the specification, or any implementation is granted by their publication here.

---

## Whitepaper

**[`whitepaper_preview.pdf`](./whitepaper_preview.pdf)**
*Architectural Foundations of Deterministic Agent Memory: Mitigating Context Rot and Indirect Prompt Injections via Harvard-Decoupled State Meshes*

Covers the state lifecycle as a conceptual model, the security argument for Harvard decoupling, the first empirical run with its cost breakdown, and the commercial roadmap.

**[`empirical-measurement.md`](./empirical-measurement.md)** — the full write-up of that run: what was measured and how, the result in the form it actually holds, the three corrections it forced on our own cost model, why the answer is a surface rather than a number, and what the run does *not* show.

The preview is regenerated from source via [`erzeuge_whitepaper.py`](./erzeuge_whitepaper.py).

---

## Roadmap

| Stage | Scope | Status |
|---|---|---|
| Verified state & anchoring | Source-linked nodes, four-valued lifecycle, fail-closed read path | **Implemented** |
| Externalized execution state | Plans, step lifecycle, append-only execution record, resumption after context loss | **Implemented** |
| Empirical cost model — first run | Sign check at ~11,000 carried tokens; three corrections to our own model | **[Published](./empirical-measurement.md)** |
| Empirical cost model — decisive run | Corpus at the threshold, three repetitions per arm, cold restarts | Open |
| Public protocol specification | Contracts and state semantics at implementation depth | In preparation |
| Closed B2B pilot | Selected industry partners, on-premise deployment | Accepting enquiries |

---

## Contact

*Enquiries regarding the closed pilot program, evaluation access, or licensing:*

- **Author:** Justin Paul Urbaniak
- **Enquiries:** please [open an issue](../../issues) in this repository.
- **Pilot enquiries:** please include intended deployment context, approximate corpus size, and target agent harness.

---

<sub>MMP (Memory Mesh Protocol) and MMB (Memory Mesh Bridge) are research designations of an active development program. Implementation details, internal state schemas, and verification algorithms are not part of this publication.</sub>
