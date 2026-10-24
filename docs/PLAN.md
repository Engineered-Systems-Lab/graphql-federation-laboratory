# Plan

How to read this page. It is the outline of the plan as it stands on 2026-10-19, with the Abstraction ladder study brought up to date on 2026-10-21; it decides nothing of its own. Each item carries one label: **DECIDED** (settled; the owning source is linked), **DIRECTION** (stated, not decided) or **OPEN** (waiting for a decision). A phase also carries its **standing** from [Progress](PROGRESS.md), which owns the verified state; where Progress does not say a gate passed, this page does not say so either. Short-term work is on the queue, not here (the lab's horizon rule, in the lab path `governance/LOCAL-COORDINATION.md` at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`; in this repository the queue is in the [local coordination records](../governance/LOCAL-COORDINATION.md)).

## Objective

Evaluate federation platforms through a stable USS Enterprise (NCC-1701-D) legacy-system scenario, reproducible correctness checks, and comparable measurements. Platform differences should be explicit rather than hidden by changing the enterprise workload.

Lore: **Saucer separation maneuver = Git worktrees**. The ship separates bounded work into isolated operational sections while preserving common command/history. This is a cultural illustration, not a normative dependency or a replacement for the repository's transaction workflow.

## End goals

The evaluation above serves four larger goals. They are the reason the lab exists; none of them changes a phase gate.

1. **The business decision (DIRECTION).** The lab exists to decide which of the main federation platforms can become a profitable business offer: services, alone or in a small organization, that modernize legacy systems into GenAI-enabled systems without costly redesign of the legacy side. The Beta-versus-Gamma and Gamma-versus-Delta/Epsilon comparisons of the [agent scenarios](#agent-scenario-design) (sell adapters alone, or adapters plus a federation router) and the shared-versus-per-platform split of the implementation effort ([below](#how-the-evaluation-is-measured)) are the measurements that answer it. A platform winner is not assumed ([D003](../project-governance/DECISIONS.md)).
2. **The final deliverable (DIRECTION).** A clean new repository, built from the governance template plus the lab's systems and designs, is the intended final deliverable; the lab stays the private workshop and archive. When the cutover happens is OPEN.
3. **A portable framework (DIRECTION).** The governance machinery (transaction worktrees, checkpoints, records) is meant to be reusable for any project worked with agents, customer work included, not only this lab.
4. **Career and market relevance (DIRECTION).** Apollo is the first platform partly for market reasons (the [Federation design](FEDERATION-DESIGN.md#the-platform) records the reason with its hedge; the demand claim is not verified). Which licence the repository carries if it is shown to others is OPEN; the leaning is a source-available licence readable for hiring evaluation.

## Phases and acceptance gates

Gates are unchanged. The last column is the standing taken from [Progress](PROGRESS.md) and the owning documents.

| Phase | Deliverable | Exit gate | Standing |
| --- | --- | --- | --- |
| 0. Environment | Working WSL and Docker runtime | User-reported Docker hello-world smoke test succeeded; capture pinned runtime details when implementation begins | Done |
| 1. Legacy enterprise | Crew & Personnel first, then Mission Operations, Engineering & Inventory, and Shuttle & Logistics; native contracts and deterministic fixtures (hand-authored Crew baseline; fixed-seed generation later) | Legacy systems work independently of GraphQL/MCP; identifier mappings and controlled failures have expected outcomes; fixture resets preserve content; later generated profiles reproduce identical fixture hashes | Done for the systems built: Crew & Personnel v1, Personnel v2, Missions (contract, service, packaging, datasets 1.0, 1.1 and 1.2) and Assets (contract 1.1, dataset, service, packaging). The relationship of Assets to the earlier Engineering & Inventory and Shuttle & Logistics concepts is unresolved in [Architecture](ARCHITECTURE.md). The data **scale-up** (DIRECTION, [D044](../project-governance/DECISIONS.md)) has reached the federation stack: the large Personnel v2 snapshot `personnel-v2-large-004`, Missions release 1.2 (300 missions, the participants reclassified as crew, on-board non-crew Personnel and outsiders) and mapping release 1.3 (the crew and participant references mapped to the large snapshot, with O-references refused by class) have landed, and the expected outcomes of the acceptance suite are derived again from the released files |
| 2. Reference graph | Shared subgraphs and one initial platform adapter | Schema composes; all baseline acceptance tests pass from a clean fixture reset | Built on Apollo and also on Cosmo: four adapters, the routers, the committed supergraph and execution config and the whole-stack compose in stub-backend mode, with acceptance questions 2 to 6 in a router-neutral shared suite ([Federation design](FEDERATION-DESIGN.md)). The stack runs on the large data (Missions release 1.2, mapping release 1.3, `personnel-v2-large-004`) and its expected outcomes are derived for it. The Missions adapter's service stage passed once against the real Missions service on Oracle on release 1.2; the whole stack was not run against that service. Progress does not record the gate as passed: question 1 is not built, the whole stack has not run on Oracle, and the graph does not resolve a participant yet |
| 3. Platform comparison | Apollo, Cosmo, and Hive adapters; repeatable harness | Each platform has correctness evidence or an explicit unsupported/blocked result; run manifests are complete | In progress. Cosmo, the second router, is built on the same subgraphs and passes the shared suite. Hive is not built and stays in the plan until the lead developer says otherwise; their interest in it is falling. The repeatable harness and the run manifests are not built |
| 4. Benchmark report | Raw results and comparison | Repeated trials, latency distributions, error rates, resource use, and limitations are published together | Not started; needs the Phase 3 harness and the [benchmark environment](#how-the-evaluation-is-measured) |
| 5. MCP/AI agents | Graph-backed and direct-service tool experiments with bounded enterprise tasks | Tool contracts, authorization boundaries, task outcomes, and failure handling pass separate acceptance tests | In progress. The Abstraction ladder study ran its first full study (study-1) and the Gamma-prime run, analysed in the [Abstraction ladder study report](AGENT-STUDY-REPORT.md); its MCP servers use the reserved federation ports 8191 to 8199. Progress does not record the gate as passed. Whether field-level authorization is needed, and which router offers it without a paid plan, is OPEN (the [Apollo terms as read](FEDERATION-DESIGN.md#the-platform)) |

The overarching **Development Stages** organize delivery as **Stage → existing Phase → Scenario**. The existing numbered phases above retain their names, numbering and gates; Alpha/Beta/Gamma/Delta/Epsilon remain scenarios. **Stage A — Read-Only Evaluation**: establish the architecture, stable query workload, measurements, correctness criteria and comparative evidence before enabling experimental mutations. Plan the Alpha–Epsilon evaluation framework now; agent execution still follows the validated enterprise graph/comparison harness under D006. Agent outcomes remain separate from router benchmarks (D011).

**Stage B — Transactional Integration** (later): add writes/mutations and SOA integration after Stage A evidence is established, under separate design and implementation scope. Preserve Missions' resource integrity and the future SOA/BPM process-integrity boundary in [Architecture](ARCHITECTURE.md) and [WIP SOA/BPM requirements](FUTURE-SOA-BPM-REQUIREMENTS.md). Existing native mutation contracts are not changed by the read-only experiment; their acceptance work does not authorize Stage B or expand Stage A.

The legacy technology mix is Java/SOAP/XML, Missions Java/Jersey REST/XML on Tomcat with Oracle 18c/plain JDBC (D027), and Assets as a Python/REST/JSON service on PostgreSQL ([Assets design](ASSETS-V1-DESIGN.md)). The federation layer is Java 21 with Spring and federation-jvm; its decisions ([D041](../project-governance/DECISIONS.md), D042, D043), the compatibility matrix, the pinned versions and what is still open are in the [Federation design](FEDERATION-DESIGN.md). Keep the legacy environment stable as integration layers change.

## How the evaluation is measured

One method, tying together what the sections below and their owners hold. Nothing here is new.

**Two kinds of evidence, kept apart (DECIDED, D011).** Router benchmarks send a fixed set of GraphQL operation documents with no agent. Agent comparisons ask natural-language tasks of an agent in each scenario. The two have separate workloads: the federation questions (list A) and the agent questions (list B) of the [query workload](FEDERATION-DESIGN.md#the-query-workload).

**Correctness first (DECIDED).** Acceptance tests are defined independently of the router and run unchanged on each ([Acceptance-test approach](#acceptance-test-approach)); a failing scenario is excluded from rankings; for agents a faster or cheaper wrong answer cannot win.

**Vendor claims are hypotheses and the lab is the independent evaluator (DECIDED, design direction).** The [registry](INTEGRATION-NOTES.md#vendor-claim-metric-registry) holds 12 attributed claims: 7 for Apollo, 5 for Cosmo, none for Hive. Provenance and evidence type stay with each claim; vendor marketing is not independent validation.

**Statistics (DIRECTION).** Repeated-measures or blocked ANOVA with the query as the block, effect sizes and confidence intervals, and an alternative when assumptions fail ([Planned statistical analysis](#planned-statistical-analysis)). For the Abstraction ladder study the plan the lead developer agreed on 2026-10-21 used logistic GEE clustered by task instead ([report](AGENT-STUDY-REPORT.md#methods)).

**Environment (DECIDED as requirements, nothing built).** The machine is the measuring instrument. Every run manifest records the machine facts (CPU, RAM, Docker and OS versions, container limits, date) and the telemetry settings, which must be equivalent across the routers compared (both routers already run with anonymous telemetry off in the stack). Runs use explicit container limits, a quiet machine with a recorded idle baseline (a run during which the machine paged is discarded), a warm-up and a repeat count the statistics need, and one copy of a service per port with every start refusing a taken port. The limits, the protocol and the repeat counts are OPEN ([Federation design](FEDERATION-DESIGN.md#the-environment)).

**Implementation effort in two buckets (DECIDED, design).** The graph (adapters, mapping releases, crew migration, acceptance oracle, graph refinements) is a shared bucket, reported once as the cost of putting a graph in front of the legacy systems and not compared across routers; the router, its configuration, composition, deployment and any adapter change a router forces are the per-platform bucket, compared across platforms. The split is by file path. The Apollo side is an estimate rebuilt from history; the Cosmo side was measured live.

### Agent scenario design

DECIDED as design and built: the harness, the MCP servers, the frozen corpus and the blind guide are in [study](../study/README.md), and the first full study, the Gamma-prime run and their analysis are in the [Abstraction ladder study report](AGENT-STUDY-REPORT.md). The full design text is to be written into [Integration notes](INTEGRATION-NOTES.md#stage-a-benchmark-design); until then it is in a machine-local record.

- **The ladder (five scenarios, letters in ladder order; the lead developer decided on 2026-10-20 to add the adapters-only step and renamed the letters, so this replaces the earlier Gamma = Apollo, Delta = Cosmo and optional Epsilon).** Alpha the raw legacy systems (the control); Beta the raw systems plus a written guide (knowledge as text); Gamma the four adapters only, with no router and no guide (the adapters as separate modern APIs: the agent sees each adapter's normal queries and does the cross-service joins itself, and does not see the federation plumbing, `_entities` and `_service`, which would be federation by the back door); Delta the adapters plus the Apollo router; Epsilon the adapters plus the Cosmo router. A possible Zeta (adapters plus Hive) exists only if Hive ever joins.
- **What each step isolates.** Alpha to Gamma: what clean modern APIs over the legacy systems are worth. Gamma to Delta or Epsilon: what the federation router adds, because Gamma has no guide, as Delta and Epsilon have none. Beta to Gamma: knowledge as text against knowledge as an API. Beta against Alpha measures what guidance is worth. The ladder has two branches from Alpha: Beta (a guide) and Gamma then Delta or Epsilon (a router).
- **Shared parts first.** The task corpus, expected outcomes and scoring rubric are frozen before any run; the federation acceptance outcomes, derived from the released files, are the scoring oracle.
- **One harness and one tool mechanism.** The same agent loop, model and limits in every scenario; only what sits behind the tools differs.
- **Alpha is raw.** Only what the legacy systems publish themselves, plus the mapping release as plain data with no explanation.
- **Beta's guide is written blind**, by a session that never sees the test questions, and frozen before the first run.
- **The agent is sandboxed** away from the repository, which holds the answers.
- **Clean runs.** A fresh fixture reset and container per scenario, randomized or counterbalanced order, repeated trials, token accounting with cached tokens counted, elapsed time.
- **Corpus.** A draft of 16 scored tasks in six categories (single-system lookup, cross-system join, mapping-dependent, honesty under failure, aggregation, deliberate ambiguity) and a separate dev set that is never scored, frozen on 2026-10-20 before any scored run. The pilot (dev set, two scenarios, one trial) measured the cost per run; the full study ran two trials. Cost per run is token counters, money applied later at a dated rate, and wall time.
- **Build order.** Corpus and oracle, then the harness with Alpha, then Beta, Gamma on the adapters alone, Delta on the Apollo stack, and Epsilon on the Cosmo stack.
- **Deliberate ambiguity (DIRECTION).** For a question whose key term is undefined, the outcome is scored as asked, chose and stated a definition, or guessed silently; the first two are rewarded and the silent guess is penalized, with the accepted definitions declared in the rubric in advance.

### Open points of the evaluation method

- **OPEN (C1):** the verdict rule for a vendor claim (matched, not matched, not reproducible here). The raw metrics are captured now so the rule can be applied later.
- **OPEN (C2):** whether the ANOVA also covers the router benchmark of Phase 4 or only the Alpha-to-Epsilon agent comparison.
- **OPEN (C3):** Hive has no agent scenario (Delta is Apollo, Epsilon is Cosmo; a Zeta for Hive exists only if Hive joins).
- **Settled for the Abstraction ladder study:** the corpus (frozen on 2026-10-20), two trials, two pinned models (Claude Sonnet 5.5 and GPT-6.1 Sol) and MCP as the common tool mechanism ([study](../study/README.md)).
- **OPEN:** the benchmark environment's limits and protocol.

## Side threads

Named for context; they are not phases.

- The licence of the repository (OPEN).
- The Claude-versus-Codex worker comparison: an idea, not started.

## Acceptance-test approach

Define expected behavior independently of the selected router. Run the same operation documents, variables, fixtures, and assertions against each implementation.

- Validate schema composition, entity lookup, cross-subgraph joins, pagination, and empty/not-found results.
- Assert known business outcomes from fixed fixtures, including invalid inputs; apply agreed mutation invariants to native contract acceptance and, later, Stage B.
- Test authorization and tenant isolation if included in the agreed contract; specify identity context explicitly.
- Exercise unavailable or slow legacy services and subgraphs, stale inventory, mismatched crew identifiers, missing maintenance records, and authentication failures. Use deterministic failure profiles, bounded timeouts, explicit expected data/errors, and a reset to baseline.
- For Crew SOAP responses, compare namespace-aware parsed content and typed values, preserving element order, string whitespace, and omitted/empty/nil distinctions; ignore irrelevant prefixes and XML formatting. Require the separate validation/negative cases in the Crew contract and pagination restart on datasetVersion change.
- Normalize only irrelevant response differences; preserve semantic differences and report platform-specific error details separately.
- Reset state between tests that mutate data. Acceptance failures exclude the affected scenario from performance rankings.

Set numeric pass/fail thresholds before timed runs. Tests and thresholds are planned, not implemented.

## Benchmark protocol

Stage A measurement design, vendor-claim provenance, implementation-effort limitations, benchmark profiles and unresolved choices are collected in [Integration notes](INTEGRATION-NOTES.md#stage-a-benchmark-design). This is design direction only; the phase gates above remain unchanged.

Use a common baseline supported by the pinned platform versions. Evaluate vendor-specific features separately. Freeze schema, dataset, operations, resource limits, topology, and configuration for each comparison revision.

Record platform/component versions, image digests, source revision, schema and fixture hashes, generator version and seed, machine/runtime details, configuration, concurrency, warm-up duration, measurement duration, and repetition count. Distinguish cold and warm runs. Use equivalent cache policies and document unavoidable differences.

Measure throughput, p50/p95/p99 latency, error rate, and CPU/memory consumption under the same offered load. Include load-generator settings, raw samples, and repeat-to-repeat variability. Avoid universal performance claims from one local Windows/WSL host.

### Read-only agent comparison framework

Each scenario has its own isolated container/environment and uses the same enterprise source state/dataset, workload and protocol wherever technically possible. Record unavoidable differences as limitations rather than silently changing the task.

| Scenario | Treatment and scope |
| --- | --- |
| Alpha | Control: raw enterprise system/data exposed directly to the agent, without extra architectural help |
| Beta | Skills/guidance to improve agent performance, without GraphQL |
| Gamma | Adapters only: the four adapters as separate modern APIs, with no router and no guide; the agent does the cross-service joins itself and sees each adapter's normal queries only, not the federation plumbing (`_entities`, `_service`) |
| Delta | Adapters plus the Apollo router (Apollo Federation / GraphOS path); study-1 measured Apollo router v2.18.0 ([Federation design](FEDERATION-DESIGN.md)) |
| Epsilon | Adapters plus the Cosmo router, retaining the repository's Cosmo terminology; study-1 measured Cosmo router 0.359.0 ([Federation design](FEDERATION-DESIGN.md)) |

Alpha–Epsilon are the committed Stage A evaluation framework, not implemented environments or a platform selection. These letters replace the earlier ones (Gamma = Apollo, Delta = Cosmo, Epsilon optional), changed on 2026-10-20 when the adapters-only scenario was added; nothing was built or run under the earlier letters. The existing Apollo/Cosmo/Hive adapter roadmap under D003 remains intact; a possible Zeta (adapters plus Hive) does not silently remove Hive or commit to an additional product. Define any Zeta treatment explicitly before running it.

Freeze a stable query/task corpus, expected outcomes and scoring rubric before comparisons. Start with token consumption and elapsed time, with **correctness/task success required** so a faster or cheaper wrong answer cannot win. Track failure/error rate where applicable and variance/repeatability alongside means. Retain raw run evidence, inputs, outputs, scores and run manifests sufficient to inspect and reproduce the comparison, including model/prompt versions and token accounting. Repeat trials as needed to distinguish treatment effects from stochastic agent variation.

Keep the protocol identical except for the defined treatment: use the same agent/model/configuration unless that configuration is itself the independent variable. Record versions, configuration and provenance for every run, including source/dataset identity and scenario-specific guidance/interfaces. Avoid scenario-specific prompt tuning after seeing results unless tuning is an explicitly defined treatment. Randomize or counterbalance run order when order, caching or warm-up effects could matter; distinguish setup/warm-up costs from steady-state query execution where relevant.

### Planned statistical analysis

Primary question: does architecture/treatment produce a meaningful difference in performance after accounting for query difficulty? Because the same query set will likely run across Alpha/Beta/Gamma/Delta/Epsilon, treat query difficulty as a repeated/blocking factor rather than assuming fully independent groups. Candidate analysis is repeated-measures or blocked ANOVA where assumptions are appropriate, with each query as a block/within-subject unit and repeated trials represented explicitly.

Select the analysis after reviewing the design and outcome distributions; if ANOVA assumptions are materially violated, use an appropriate alternative. Report effect sizes and confidence intervals alongside significance tests, rather than reducing conclusions to `p < .05`. Evaluate tokens, elapsed time, correctness/task success and failure rate together; a combined cost/performance view may follow later. These are planned analysis directions, not a frozen implementation or an assertion that every outcome supports ANOVA.

Later context (2026-10-21): for the Abstraction ladder study, whose primary outcome is a correct answer (yes or no), the analysis plan the lead developer agreed used a logistic regression fitted with GEE clustered by task, six Holm-corrected comparisons and equivalence tests at two margins; the methods and results are in the [Abstraction ladder study report](AGENT-STUDY-REPORT.md).

## Next design choices

This heading stays as a compatibility anchor for incoming links. The numbered list that stood here left under the lab's horizon rule (the lab path `governance/LOCAL-COORDINATION.md`, at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`): short-term work is on the queue, verified results are in [Progress](PROGRESS.md), and the long-term direction is in the phases, gates and protocols above. One non-binding direction that other documents cite stays here. Mapping time and version semantics for historical resolution belong to the Integration & Benchmark layer under D015, not to Missions (D034). The direction is immutable versioned mapping releases in the Personnel dataset style, an explicit release named by every resolution request with no implicit latest, no effective-interval axis until a scenario needs one, and missing, ambiguous or dangling outcomes never guessed.

## Checkpoint automation sequence

Later context (2026-10-08): the following paragraphs preserve the original preparation sequence and boundary decisions. The checkpoint tooling and explicit profiles are implemented; current mechanics and authority belong to the linked governance sources. Fresh-worker/devlog automation remains deferred. Historical step labels below are contemporary narrative, not current queue identities.

Governance first (G018): the [checkpoint workflow](../governance/CHECKPOINT-WORKFLOW.md) defines authority, exact-message approval, separate record follow-up and the bounded runtime continuity gap. This step changes documentation only. Next, under a separate implementation mandate, build and test deterministic checkpoint mechanics and explicit validation profiles against that workflow. No checkpoint tool, packet machinery or new tests exist from this step; dataset 003 and external-ID mapping implementation are outside it.

Step 2 implements the deterministic [checkpoint tool and reviewed profile format](../governance/CHECKPOINT-TOOL.md), with isolated temporary-repository tests. Step 3 fresh-worker/devlog integration remains deferred. Runtime command/profile review is required before using the tool for runtime scope. No real checkpoint execution is authorized by this implementation status.

For the first checkpoint of the current working tree, the choice is to checkpoint Step 1 governance and Step 2 deterministic checkpoint implementation together as one checkpoint-infrastructure transition: their current Plan/Progress updates share whole files, and the approved checkpoint tool operates on explicit whole-file manifests. Governance preceded implementation and remains conceptually distinct; this is only the commit-boundary decision for the current working tree. The prose written in the lab's earlier persona voice in `docs/COMMAND-CONTINUITY.md` (the lab's copy of what is now the framework's [Command continuity](../governance/COMMAND-CONTINUITY.md)) and `docs/CREW-PERSONNEL-DATASET-003-DESIGN.md` remained separate future checkpoint candidates, excluded from this boundary. Step 3 worker/devlog integration remains deferred. This boundary decision authorizes neither staging nor commit execution.

## Personnel v2 preparation (2026-10-02)

The implementation and selective staging authorized by the lead developer stop before commit under G018. Review [the v2 contract](PERSONNEL-V2.md), [validation evidence](PERSONNEL-V2-VALIDATION.md), exact manifest and full proposed message before authorizing any commit. After an approved runtime commit, separately prepare the new SHA/current-record/devlog follow-up and restore continuity; do not predeclare acceptance or update the committed implementation checkpoint now. Missions artifacts and v1 remain untouched.

Later context (2026-10-08): the preceding Personnel v2 preparation paragraph is historical. The approved runtime and subsequent continuity records are committed; current evidence, incident disposition and acceptance limitations belonged to the lab's Progress (the lab path `docs/PROGRESS.md`, section "Personnel v2 committed runtime (2026-10-02)", at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`); the current state is in [Progress](PROGRESS.md). No fresh runtime execution or manual v2 acceptance is claimed.
