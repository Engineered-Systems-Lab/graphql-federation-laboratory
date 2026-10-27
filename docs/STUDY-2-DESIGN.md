# Abstraction ladder study 2: design

Status: design record of Abstraction ladder study 2 (run id `study-2`), written on 2026-10-27 from the repository at commit `eab14958de78e5f26c1437a1ff34fdebf048718a`. It is published before any study-2 run so that what was decided in advance is on record. It is non-normative: it is not the frozen analysis plan, which is written, tested and frozen before the first scored run (see [the build work](#build-work)), and where the frozen plan, the frozen scoring contract or the frozen guide differ from this page, they win. Nothing here is queued, built or authorized by this page.

The content is carried from the study-2 design and execution proposal of 2026-10-21, which stays private with its working scripts and tables; the power and cost results below are stated, not their scripts. The page holds no task text and no findings of study 1 about single tasks, because study 2's own blindness rules forbid them to the workers who build its corpus and its guide (see [the corpus](#the-corpus)). Study 1's findings are in the [Abstraction ladder study report](AGENT-STUDY-REPORT.md); the corpus is rebuilt for study 2.

## The question and what "better" means

**The question,** in the lead developer's words: "does federation improve on separate adapters or well-documented direct access?" As comparisons: does Apollo Federation or Cosmo Federation improve on GraphQL Adapters, and on Guided Direct Access? For the business: document the existing interfaces well, build adapters, or build adapters plus federation?

**"Better" is four declared measures,** reported side by side with no composite score:

1. Accuracy: a correct answer, yes or no. This is the primary measure.
2. Model API cost per run.
3. Elapsed time per run.
4. Handling of unavailable services: the honest-gap rate on the controlled-outage tasks.

Tool calls, tokens and calls of the calculation tool are reported as secondary measures.

**Declared before execution:** study 2 compares access architectures that share calculation support. It is not a replication of study 1, and its accuracy numbers are not pooled with study 1's.

## The arms

| Arm | What the agent gets | Role |
| --- | --- | --- |
| GraphQL Adapters | separate GraphQL APIs: the four adapters on their own; `_entities` and `_service` stay refused | full repeated arm |
| Guided Direct Access | the same raw SOAP and REST interfaces, with a new integration guide written blind for study 2 (decision J) | full repeated arm |
| Apollo Federation | the adapters connected through Apollo Router v2.18.0 | full repeated arm (federation) |
| Cosmo Federation | the adapters connected through Cosmo Router 0.359.0 | full repeated arm (federation) |
| Direct Access | the raw SOAP and REST interfaces | exploratory reference: one complete block |

Every arm gets the same calculation tool (see [the tools](#the-tools)), system prompt, limits, models (Claude Sonnet 5.5 and GPT-6.1 Sol at medium effort, pinned) and corpus.

**The one mapping to the internal identifiers, for the methods:** Alpha is Direct Access, Beta is Guided Direct Access, Gamma is GraphQL Adapters, Delta is Apollo Federation and Epsilon is Cosmo Federation. The letters stay in configurations, run keys and bundles, and where study 1 is cited; study 1 keeps its own names.

**The methods wording on the adapters' history,** used once, in the lead developer's sentence: "Study-2's Gamma uses the standalone lookup capabilities introduced for Study-1's Gamma-prime follow-up." Everywhere else this arm is GraphQL Adapters.

**The methods wording for Direct Access,** in the lead developer's sentence, with the internal identifier: "One exploratory Alpha block provides a raw-access reference under Study-2 conditions."

- Direct Access is a new reference measurement, not a check that study 1 replicates: the corpus, the Missions backend and the calculation support all change.
- Its single block leaves its performance confounded with the time window in which that block ran.

## The corpus

**Size.** 48 core scored tasks plus 6 in a separate ambiguity set, 54 in all. The power calculation (see [power](#power-tasks-against-trials)) shows that the number of distinct tasks, not of trials, decides what can be detected. The 48 is fixed by decision D (F follows it).

**Core tasks (48), by category, size and system coverage.**

| Category | Tasks | Small (at most 20 records) | Medium (about 100) | Large (300 or more) | Systems |
| --- | --- | --- | --- | --- | --- |
| A single-system lookup | 6 | 6 | | | 2 Missions, 2 Assets, 2 Personnel |
| B cross-system join | 10 | 6 | 4 | | 4 Missions and Personnel, 4 Missions and Assets, 2 all three |
| C mapping-dependent (release rules, unmapped against unresolved, a refused or absent release) | 8 | 5 | 3 | | through the mapping |
| P pagination and completeness (the answer needs every page) | 6 | | 3 | 3 | the Missions, Assets and Personnel lists |
| E aggregation (count, group, deduplicate, sum) | 10 | 3 | 4 | 3 | 4 single-system, 6 cross-system |
| D controlled outage | 8 | 4 | 4 | | 2 with the Missions service down (new), 3 with Assets down, 3 with Personnel down; 2 of the 8 are fully answerable without the stopped service, a check for over-reporting |

The size columns show where architecture matters, not only on large aggregations.

**The ambiguity set (6), kept separate.**

- Each task has explicit accepted interpretations, a closed list in which any set of ranks that is a subset of the ranks in the data is accepted, and a fixed scoring rule.
- The data involved is small, so the ambiguity is the only difficulty.
- It is scored separately from the main completed-answer accuracy and never enters it (decision I).
- Clarification goes through the `ask_requester` tool (decision I), present identically in every arm. The answer schema has no ASKED field: a request counts only from the tool log. The scoring is in [the scoring contract](#the-scoring-contract).

**Construction rules,** so that no task is chosen to favour federation:

1. **A candidate pool of about 70 questions,** written in the enterprise's words from the domain (missions, people, assets, releases), by a worker who sees neither the arms' results nor study 1's per-task results.
2. **A scripted reference solution per arm,** code and not a language model, that uses only that arm's tools and proves every task answerable in every arm. Study 1 ran this check for one scenario only. The tasks are also run against the Oracle-backed stack (step 7 of [the preflight](#preflight-steps)).
3. **A stratified random draw** of the 48 from the pool, with a recorded seed, after the answerability check. Nothing is selected for its expected effect.
4. **Two independent derivations of every answer key,** a declared list of variants, and the population rules written into the question.
5. **Development use only.** A development set of 8 tasks, disjoint from the scored set, debugs the harness and the calculation tool. No scored task is run before the freeze.
6. **A new integration guide for Guided Direct Access** (decision J). Study 2's Guided Direct Access represents well-documented direct access under the new study conditions.
   - **Author:** a fresh worker who has not seen the scored corpus, the answer key or study 1's task-level findings.
   - **Given only:** the actual study-2 service contracts, the real Missions service included, the tool capabilities, the calculation tool and `ask_requester` included, and general business context. No task-specific hints.
   - **Independent check:** a separate check of the guide's accuracy and coverage against those same sources, without exposing the scored corpus to its author.
   - **Freeze:** finalized and frozen, with its version and hash recorded in every manifest, before scored execution. No revision driven by outcomes during the scored runs.
   - **Study 1's guide** ([study/guide](../study/guide/README.md), frozen at lab commit `506eeb1`) stays unchanged.

## The tools

### The calculation tool, `calculate` (decision B)

- **One tool, identical in every arm,** Direct Access and Guided Direct Access included: the same name, description, schema and limits.
- **Generic operations only:** count, distinct, group-by with count or sum, sort, filter by literal comparison, set union, intersection and difference, and arithmetic. No operation knows a domain term.
- **Input: results of the same run, referenced by id** (decision G). The agent names earlier tool results it obtained in that run through its own tools; the harness stores them per run, covered by the bundle checksum.
  - The tool never fetches. It has no network, file, database, backend or answer-key access, and never sees the results of other runs.
  - An unknown or foreign id is an error, logged like any other call.
- **Logged:** the result ids used, the operation, the output, failures, seconds, and the bytes and tokens the call added. Calculation calls count in the tool-call limit and in every declared measure.
- **The agent stays responsible** for retrieving the right records and choosing the right calculation.
- **Development preflight, before any freeze:**
  - Four development tasks, two large cross-system aggregations and two medium aggregations, run in GraphQL Adapters, Guided Direct Access, Apollo Federation and Cosmo Federation with both models, once without the tool and once with it, and each failure is classified by its cause.
  - **Declared check:** the tool is fit only if the failures where the agent says it cannot count and the failures from token volume fall, the definitional failures stay as they are, and no new kind of failure appears (a wrong operation or a wrong result id).
  - If it fails, the tool design returns to the lead developer before the corpus freeze.
  - The same preflight measures the tool's real token overhead, which replaces the estimate of +20 percent in [the budget](#cost).

### The `ask_requester` tool (decision I)

Present identically in every arm and every run.

- The agent's clarification question is logged with its run id.
- It always returns the fixed text "No requester response is available during this evaluation."
- Its calls and their overhead count in the tool-call limit and in every declared usage measure.

## Experimental design

### The schedule: a Williams square in four rounds

The four full arms run in **4 rounds**, one **block** per arm per round, so each arm gets **4 blocks**, that is 4 separate starts of its access layer.

- A block is one start of an arm's access layer: the Missions service and everything above it (the adapters, the router if any, the MCP server).
- The Oracle database stays up for a whole session (decision E). The study only reads, and a dataset fingerprint, recorded by the provenance observation, is checked unchanged at the start of each block; a changed fingerprint stops the session.
- A session is one continuous run of Oracle. Sessions are recorded as a factor beside the round.

The orders of the rounds form a **Williams Latin square** for four arms. Rounds are named by the rows of the square below, not by when they run. Letters are assigned to arms by a seeded draw, and the order in which the four rounds run is seeded too, under the rule in [what each block runs](#what-each-block-runs-and-the-split-between-the-models):

| Round | Position 1 | Position 2 | Position 3 | Position 4 |
| --- | --- | --- | --- | --- |
| 1 | a | b | d | c |
| 2 | b | c | a | d |
| 3 | c | d | b | a |
| 4 | d | a | c | b |

Why this design:

- Every arm sits once in every position, so the start of a session, the vendors' time of day and warm caches are spread evenly; Guided Direct Access is never always in the same place.
- Each arm directly follows each other arm exactly once (12 ordered pairs, all different), so the run that precedes an arm (a warm vendor cache, a stack just torn down) is balanced too.
- Four rounds are the minimum for both properties. All 24 orders would add nothing the analysis uses. Two rounds, an earlier draft, balance position only on average and leave carryover unbalanced.
- Blocks come in multiples of 4.

### What each block runs, and the split between the models

**Decided (decision D): W4-half.**

- The 54 tasks are split into two halves, H1 and H2, stratified by category, size and system.
- Rounds 1 and 3 run H1 in every arm; rounds 2 and 4 run H2. The halves stay with these rows of the square, the complementary pairs, whatever order the rounds run in: the seeded order moves whole rounds and never pairs rounds 1 and 2, 1 and 4, 2 and 3, or 3 and 4 in a half (a rule clarified on 2026-10-27).
- Within a half, a seeded draw balanced by category gives each task to Claude in one of its two rounds and to GPT in the other.
- So every arm runs every task once per model (2 runs per task and arm), in two different rounds.
- In each pair of rounds that share a half, the positions of every arm add up to the same total, 5 (1 and 4, or 2 and 3), so the halves do not tilt position either. Only the pairs 1 and 3, and 2 and 4, have this property: in rounds 1 and 2, for example, arm a holds positions 1 and 3 and arm b positions 2 and 1.
- All four arms in a round run the same tasks, so comparisons stay paired within a round.

**Not chosen (W4-full):** every block runs all 54 tasks, still one model per task per block, giving 4 runs per task and arm at about 1.7 times the scored cost.

### Randomized, held constant, and the Direct Access block

**Randomized, seeded and recorded:**

- the assignment of arms to the letters of the square, and the order in which the rounds run, with each half kept on its pair of rounds;
- the split of the tasks into halves, and the model assignment per task and round;
- the order of the tasks inside each block, with the model order alternating;
- the position of each outage task inside its block (the service is stopped before its run and restored after, as in study 1).

**Held constant and recorded:**

- **Models:** Claude Sonnet 5.5 and GPT-6.1 Sol at medium effort, pinned.
- **Prompt, tools and limits:** the system prompt and the tool descriptions, the calculation tool, and the limits (80 tool calls, 1 M tokens, 900 s, 3 retries), set again from the development runs once the tool exists, before the freeze.
- **Data:** the corpus and the scorer, and the datasets: Missions release 1.2 on Oracle, mapping release 1.3, Personnel `personnel-v2-large-004`, Assets release 1.1.
- **Versions:** the router versions, the image digests and the harness commit.
- **Environment:** the machine, the Docker resource share and the container limits, and the VPN exit (Ashburn, recorded this time).
- **Prices:** the dated price table.

**The Direct Access block:** one complete block, all 54 tasks with both models (108 runs), **last in the schedule, after round 4** (decision M).

- Placing it last keeps it from preceding any arm of the balanced square.
- Its time-window confound is stated with its results.

### Hypotheses and analysis

The analysis plan is frozen before the first scored run and committed in this repository, and its hash goes in every manifest. What follows is its design.

**Planned comparisons** (decision C), defined now, two-sided, with Holm's correction over the two (family α 0.05):

- **P1, federation against adapters:** the mean of Apollo Federation and Cosmo Federation minus GraphQL Adapters, in accuracy.
- **P2, federation against the guide:** the mean of Apollo Federation and Cosmo Federation minus Guided Direct Access, in accuracy.
- Each is reported as a difference in percentage points with its 95 percent interval and a superiority test, and is tested for equivalence at **±10 percentage points, the only predeclared margin** (decision K; no other margin and no fallback).
- Equivalence holds only if the whole 95 percent interval lies inside ±10 percentage points.
- Differences and intervals are reported whether or not equivalence is established, and the report says that "equivalence not established" does not prove a difference.
- The practical justification of ±10 is written into the frozen plan before scored execution. The draft: a difference under 10 percentage points is fewer than one more correct answer in ten business questions, and the comparisons of cost, time and outage handling would then decide.

**Secondary, Holm-corrected as one family:**

- Apollo Federation against GraphQL Adapters, Cosmo Federation against GraphQL Adapters, Apollo Federation against Cosmo Federation (with equivalence at the same ±10 percentage points), GraphQL Adapters against Guided Direct Access, Claude against GPT, and the arm by model interaction.
- Cost, time and tool calls as ratios of geometric means; the honest-gap rate on category D.

**Meaningful effects:** 10 percentage points of accuracy; a ratio of 1.25 for cost and time; 15 percentage points on the honest-gap rate of category D.

**Exploratory, and labelled so:** everything involving Direct Access, the ambiguity set, the size strata, the use of the calculation tool, and the results per category.

**Model:**

- Logistic GEE clustered by task, with arm, model, their interaction, and round and session as fixed effects (session only where a session boundary falls inside the schedule).
- Sensitivity analyses: a cluster bootstrap over tasks, and a mixed model with a random task and a random block.
- The scripts are tested on simulated data before the freeze.

### The scoring contract

Frozen with the scorer before the first scored run.

- **Outcomes, one per run:** correct, wrong answer, format error, definition not accepted, abstained, did not finish, vendor error.
- **Abstained (decision H):** the agent declines to give an answer.
  - Primary accuracy counts it as incorrect.
  - The outcome tables report it as its own category beside wrong answers.
  - Its exact definition is frozen with the scoring: which submissions count as abstention, how it relates to the honesty checks of category D (reporting an outage gap is not abstention) and to did not finish (no submission at all).
- **Primary accuracy:** correct only. Wrong answer, format error, definition not accepted, abstained and did not finish are incorrect; each is reported.
- **The ambiguity set (decision I)** is scored separately from the main completed-answer accuracy:
  - Credit goes to an appropriate clarification or to an explicitly stated interpretation that the frozen rubric accepts. Both criteria are defined before the scored runs.
  - A clarification counts only from the `ask_requester` tool log, never from a field the agent fills in; the answer schema drops ASKED.
  - Clarification requests and answers with an accepted interpretation are reported separately. A request alone does not show that the task was completed after clarification.
- **Usage:** calculation and clarification calls and their overhead count in tool calls, tokens, time and cost.
- How an `ask_requester` call in a core task is treated is frozen with the scoring as well.

**Exclusions:**

- A vendor error is queued again once, at the end of its block. If it errs again it is missing in the main analysis and wrong in a sensitivity analysis. Study 1's vendor errors fell on long-context runs, so they are not treated as ignorable.
- A block in which the provenance or health check finds a backend down outside a category D task is void and repeated whole. The trigger is declared, not judged.
- No other repeated runs, and no tuning of the prompt, the tools or the guide after the freeze.

### Power: tasks against trials

- Study 1 and the gamma-prime-1 run give the differences between arms per task. The between-task standard deviation of a difference (τ) is about 17 percentage points for federation against GraphQL Adapters, 23 for federation against Guided Direct Access and 6 for Apollo against Cosmo Federation, estimated from study 1's Beta, Delta and Epsilon and the gamma-prime-1 Gamma.
- Binomial noise per run adds little once there are a few runs per task.
- The detectable difference therefore falls with the number of tasks (as 1/√k) and only a little with the runs per task.

Superiority at power 0.8, in percentage points:

| Contrast | α | Detectable at 48 tasks, 2 runs per task and arm | The same, 4 runs | Tasks to detect 10 percentage points, 2 runs |
| --- | --- | --- | --- | --- |
| **P1 federation − GraphQL Adapters** | 0.025 | **10.1** | 8.8 | 49 |
| **P2 federation − Guided Direct Access** | 0.025 | **11.3** | 10.8 | 61 |
| Apollo Federation − GraphQL Adapters | 0.0125 | 12.6 | 11.4 | 77 |
| Cosmo Federation − Apollo Federation | 0.0125 | 7.0 | 5.3 | 23 |
| GraphQL Adapters − Guided Direct Access | 0.0125 | 15.9 | 14.9 | 121 |

Reading:

- With 48 tasks, P1 reaches the meaningful 10 percentage points and P2 comes close (11.3).
- **Spending on tasks beats spending on runs.** 64 core tasks with 2 runs give about 8.8 percentage points for P1 and 9.8 for P2: as good as W4-full at 48 tasks or better, for about 36 dollars less all in (see [cost](#cost)).
- **Caveats:** τ comes from only 16 tasks, the gamma-prime-1 run was not interleaved with study 1, and a corpus with a calculation tool may spread differently. The development runs estimate τ again before the freeze, the task count is fixed then, and a simulation under the GEE model confirms the figures.

### Power to establish equivalence at ±10 percentage points (decision K)

The calculation is seeded and reproducible, and it uses the planned analysis itself, read from [study/analysis/stats.py](../study/analysis/stats.py) without changing it: the GEE clustered by task, the model average with equal weights, the delta-method contrast and the rule of the whole 95 percent interval.

**What power means here.** Power is the chance that study 2 *establishes* equivalence (the whole 95 percent interval inside ±10 percentage points) under the stated assumptions. It is **not** the probability that the approaches are equivalent.

Two calculations:

1. **A simulation with the planned GEE,** 400 simulated studies per line, 48 core tasks, 2 runs per task and arm.
   - The tasks are drawn from study 1's 16 accuracy profiles per task, with GraphQL Adapters taken from the gamma-prime-1 run.
   - A true difference is set by shifting the reference arm by a constant.
   - The observed study-1 proportions are treated as true values, which slightly overstates the spread between tasks. This makes the simulation the more cautious of the two.
2. **A normal approximation of the same clustered contrast,** with study 1's between-task spread τ after removing the noise of runs. It is varied to show sensitivity.

**The comparisons of the guide with federation,** at 48 tasks:

| Contrast | Status | Power if the true difference is 0 (simulation / analytic) | If it is 5 percentage points (simulation) | Tasks for 80 percent power at 0 (analytic) |
| --- | --- | --- | --- | --- |
| P2 federation − Guided Direct Access | planned | **53 / 56 percent** | 29 percent | 68 |
| Apollo Federation − Guided Direct Access | for reference, not a declared test | 37 / 35 percent | 22 percent | 87 |
| Cosmo Federation − Guided Direct Access | for reference, not a declared test | 58 / 65 percent | 30 percent | 61 |

**The other comparisons:**

| Contrast | Status | Power if the true difference is 0 (simulation / analytic) | If it is 5 percentage points (simulation) | Tasks for 80 percent power at 0 (analytic) |
| --- | --- | --- | --- | --- |
| P1 federation − GraphQL Adapters | planned | **68 / 73 percent** | 32 percent | 55 |
| Apollo Federation − Cosmo Federation | secondary | **91 / 100 percent** | 46 percent | 23 |

**Sensitivity to the study-1 assumptions** (analytic):

- **P2, at a true difference of 0:** 99, 85, 56, 23 and 0 percent for a spread between tasks of 0.5, 0.75, 1, 1.25 and 1.5 times study 1's. Halving the run-to-run variance, or adding half to it, gives 63 and 49 percent. At a true difference of 2.5, 5 and 7.5 percentage points it gives 46, 26 and 10 percent.
- **P1, at 0:** 95 to 31 percent over the same range of spread.
- **Apollo against Cosmo, at 0:** 96 percent or more at every spread tried.

Reading:

- The power to establish equivalence of federation with the guide is **about 53 to 56 percent** if there is truly no difference. It drops to about 26 to 29 percent if federation is truly 5 percentage points better or worse.
- It depends mostly on how much tasks differ from one another, which study 1's 16 tasks estimate poorly.
- Apollo against Cosmo is very likely to establish equivalence if they truly do not differ.
- **Results are reported in every case:**
  - The estimated differences and their 95 percent intervals are results whether or not equivalence is established.
  - "Equivalence not established" does not prove a difference; it means the interval was too wide, or the difference too large, to show equivalence at ±10.
  - Such an outcome authorizes no extra tasks, repeated runs or spending. Any change of budget or design goes to the lead developer for decision before execution.
- **Limits:**
  - round and session are left out of the simulation (the Williams schedule makes them close to orthogonal to arm);
  - a corpus with a calculation tool may spread differently;
  - the development runs estimate τ again before the freeze, and the frozen plan records the final power figures.

### Provenance

Study 2 relies on the Job `run_provenance`, built in this repository before the pilot. Its scope covers:

- the declared intended backends per arm (mode real or simulated, image, dataset, routing);
- a read-only observation of the running stack before the first paid request, refusing on a mismatch;
- the redacted launch configuration and the script hashes in the bundle;
- drift detection on resume.

Study 2 adds one requirement: an observation per block, because every block restarts the access layer. Completed runs are saved after every run, and `--resume` already runs only the missing runs ([the harness](../study/harness/README.md)); it must also resume inside the block schedule.

## The backend: the real Missions service on Oracle

Study 2 replaces the Missions simulator of study 1 (see [the report's correction](AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed)) with the Oracle-backed Missions service.

**Memory on paper,** from documented limits and recorded machine facts; nothing was measured:

| Item | Source | Planned ceiling |
| --- | --- | --- |
| Oracle XE 18.4 container | [oracle-environment.json](../uss-enterprise/missions/datasets/oracle-environment.json): 4 GiB memory, 1 GiB shm (shm use is charged inside the 4 GiB), 2 CPUs; XE caps database memory (SGA and PGA) at 2 GB by its licence terms, to be confirmed from `v$sgainfo` and `v$pgastat` | 4.0 GiB |
| Missions service (Tomcat, Java 17) | [its compose file](../uss-enterprise/missions/compose.yaml) sets **no** limit; proposed 768 MiB with a heap cap | 0.75 GiB |
| Personnel service, Assets service and database, 4 adapters, 1 router | `docker inspect` of the study stack: 384 + 256 + 512 + 4 × 512 + 256 MiB (the simulator's 128 MiB drops out) | 3.4 GiB |
| **Total of the limits** | | **about 8.2 GiB** |
| Docker share | `docker info`: 15.4 GiB, 16 CPUs | headroom of about 7 GiB |
| Host | about 32 GB; free at stack start 15.6 GiB (study 1) and 14.9 GiB (gamma-prime-1), with the simulator stack only | about 10 to 11 GiB free expected with Oracle |

On paper this is feasible.

- The "about 9 GB" of Oracle in the federation documents is the size of the Oracle image (9.14 GB), not its memory.
- The pinned image is present by its digest, `sha256:b17a93fb…`, but its tag now shows `<none>`.
- The service image `starfleet-missions-service` does not exist yet and must be built.
- The earlier exits with code 137 were kills (`OOMKilled` false), not memory failures.

### Preflight steps

Each step is an explicit operator action with the lead developer's go, run in this repository.

1. **Inventory:**
   - Verify the Oracle image by its digest.
   - Build the Missions service image from the committed Dockerfile with the proposed memory limit (a governed change).
   - Confirm a disk reserve of 20 GiB.
2. **Oracle alone:**
   - Start it and time its readiness (the pinned timeout is 900 s).
   - Record the container's peak memory (`docker stats`), the size of the Windows `vmmem` process, the host's free memory and the SGA and PGA views.
3. **Data:**
   - Reset to Missions release 1.2 through the operator script, with the exact comparison of the loaded values.
   - Use a read-only service login.
   - Record the dataset hash and the row counts.
   - Check that the Missions clock moves no answer (the expected answers are equal before and after a block).
4. **The Missions service on 127.0.0.1:8083:**
   - `GET /missions` returns 300.
   - Write down the raw behaviour that Direct Access and Guided Direct Access depend on (unknown paths, status codes, headers, error bodies, paging) next to the simulator's. Differences are recorded, not hidden: the simulator was what study 1 measured. Any difference goes through the gate below (decision L).
   - Give the guide's independent checker the real service's observed behaviour as a source (decision J).
   - Confirm that the raw tool cannot change the state of Oracle (an allowlist of GET only, a read-only login).
5. **The whole stack, for each of the four arms and Direct Access:**
   - Federation acceptance list A on both routers.
   - The adapter gates.
   - A scripted heavy load (all missions with their nested crew and assets).
   - A 30-minute soak at study load.
   - The peak memory per container and in total; restarts; the latency of the Missions REST calls against the simulator's.
6. **Outage mechanics:**
   - Stop and restore Assets, Personnel and (new) the Missions service in every arm.
   - Measure the recovery time, and check that the routers need no restart. In the earlier build Cosmo found restarted adapters by itself, and Apollo needed a restart after the adapters restarted. That category D stops backends is to be confirmed.
7. **Answerability:** the scripted reference solutions of every task in every arm, run against this stack, match the key.
8. **Provenance:** a dry run of `run_provenance` with fake clients. The intended mode is real for Missions; the observed mode must equal it.
9. **Paid smoke test:** the development tasks in every arm, compared with the archived behaviour of study 1 and gamma-prime-1.

**The gate before the freeze: the real Missions service against the simulator (decision L).** If the real service differs from the simulator in step 4 or later:

1. **Classify each difference first.** Does it affect the contracts, the tool behaviour, the guide's accuracy, the answerability of tasks or the expected answers?
2. **Record it** in the preflight record, with its evidence.
3. **Fix any affected setup:** the tool configuration, the guide (through its independent check, decision J), the reference solutions or the answer key.
4. **Run the relevant Direct Access and Guided Direct Access smoke checks again.**
5. **An unexplained discrepancy blocks the freeze.** It is not carried into scored execution.

Expected latency differences are documented; the real service is not made to imitate the simulator.

**Go or no-go thresholds:**

- Docker peak under 12 GiB.
- Host free memory never under 6 GiB during the soak.
- No OOM kill and no unplanned restart.
- Oracle ready within 15 minutes.
- Every reference solution matches the key.
- The decision-L gate is passed: no unexplained discrepancy between the real service and the simulator.

On a failure the options go to the lead developer:

- a larger Docker share (the lead developer's setting);
- only the running arm's router (already the case);
- a lower Oracle memory pin (a governed change of the reviewed environment).

**Alternatives.** A substitute for Oracle only with an explicit rationale and validation. The simulator would be a declared simulated arm, never a silent replacement.

## Cost

**Basis: actual usage** of study 1 and gamma-prime-1.

- The per-run cost per arm and model reproduces the report to the cent: study 1, 23.52 dollars Claude and 10.93 GPT; gamma-prime-1, 3.19 and 1.92.
- The mean cost per run, averaged over the two models: GraphQL Adapters 0.080 (from the gamma-prime-1 run), Apollo Federation 0.078, Cosmo Federation 0.078, Guided Direct Access 0.152 and Direct Access 0.163 dollars (from study 1's Delta, Epsilon, Beta and Alpha).
- Claude was 68 percent of the spend.
- Retries were 18 of about 3,160 requests (0.6 percent).
- The costliest runs were those of the large aggregations, 0.15 to 0.32 dollars a run, up to 0.77.

**The budget for the chosen schedule** (decision D: W4-half, 48 + 6 tasks), model API usage only, in dollars:

| Line | Base | With the +20 percent tool factor |
| --- | --- | --- |
| 1. Development and preflight: the development set (8 tasks in 5 arms), the tool preflight (4 tasks in 4 arms), the Oracle smoke test | 23.46 | 28.15 |
| 2. Scored runs: 540 (4 Williams rounds of the four arms, plus the Direct Access block) | 59.49 | 71.39 |
| 3. Subtotal (1 + 2) | | 99.54 |
| 4. Contingency: 25 percent of the whole subtotal | | 24.89 |
| **5. Total** | | **124.43** |

- **The +20 percent** is an estimate of the tool's extra tokens, not a contingency. The development preflight replaces it with a measurement.
- **The contingency** covers all estimated API spend, development and scored alike: unforeseen repeated runs, vendor errors beyond the 0.6 percent retry rate already in the per-run costs, and drift in prices or tokens. It does not cover infrastructure or development effort.
- **The ceiling (decision D):** 125 dollars of model API spend for all of study 2, development included.
  - It is split at the observed vendor share: Anthropic 85 dollars, OpenAI 40 dollars. The harness budgets are set to these.
  - The budget is estimated again after the development preflight. Any rise above the ceiling needs the lead developer's word.

**The schedules compared before decision D,** four full arms plus the Direct Access block:

| Schedule | Scored runs | Scored, with +20 percent | All in, with development and +25 percent | Hours of runs (about 45 s each) |
| --- | --- | --- | --- | --- |
| **W4-half, 48 + 6 tasks (chosen)** | 540 | 71 dollars | **124 dollars** | 6.8 |
| W4-half, 64 + 6 tasks | 700 | 93 dollars | 151 dollars | 8.8 |
| W4-full, 48 + 6 tasks | 972 | 122 dollars | 187 dollars | 12.2 |
| W4 with both models in every block | 1,836 | 222 dollars | 313 dollars | 22.9 |

Reading:

- Moving from three arms to four full arms costs nothing extra under W4-half: it has the same run count as the earlier recommended package (540) and gives four stack starts per arm instead of two.
- **50 dollars is not enough for any four-arm schedule.** It covers about two thirds of W4-half's scored runs, without development.
- At study 1's split between the models, W4-half's API cost is about 84 dollars for Claude and 40 for GPT, inside the ceiling's 85 and 40. The vendor account balances were not checked; the OpenAI balance probably needs a top-up.
- One round is 4 blocks of 27 tasks (about 108 runs, 1.4 hours plus four starts), so the schedule fits in two or three sessions. Round and session are recorded factors in the analysis, so a day boundary between rounds is allowed.
- **API cost only.** Infrastructure (electricity, the machine, disk) and development effort (the harness changes, the tool, the corpus, the guide, the preflight) are separate and are not estimated here.
- A budget stop ends cleanly and resumes without repeating completed runs (the existing harness behaviour, to be kept for the block schedule).

## Build work

The work this design implies, as a plan; nothing is queued by this page.

1. The study apparatus in this repository ([study](../study/README.md)) is the base; the launch scripts, which were machine-local for study 1, become governed launch configuration.
2. `run_provenance`, plus the observation per block.
3. Harness changes:
   - the Williams block schedule, with the seeded letters, round order, halves and model split;
   - resume per block;
   - queueing a vendor error again once;
   - the `abstained` outcome and the scoring contract;
   - the calculation tool over result ids, with the storage of results per run and its logging;
   - the `ask_requester` tool and its log;
   - the harness budgets set to the ceiling (Anthropic 85, OpenAI 40 dollars);
   - the dataset fingerprint check at the start of each block, and the session recorded.
4. Corpus 2: the pool, the reference solutions per arm, the stratified draw, the keys with two derivations, the development set and the ambiguity set.
5. The new Guided Direct Access guide (decision J): a fresh blind author, an independent check of accuracy and coverage without exposure to the corpus, and a freeze with its hash recorded before scored execution.
6. The memory limit of the Missions service image and the preflight scripts (see [the backend](#the-backend-the-real-missions-service-on-oracle)).
7. The frozen analysis plan and its scripts, tested on simulated data. The plan carries the written justification of ±10 percentage points and the final equivalence power, estimated again from the development runs.

## Decisions of the lead developer

All answered on 2026-10-21.

- **A.** Models: the same models as study 1.
- **B.** Calculation tool: one shared calculation tool, the same in every arm.
- **C.** Arms: four full repeated arms, one exploratory Direct Access block, two planned comparisons, and the name of the adapters-only arm.
- **Names.** Descriptive scenario names for study 2 (Direct Access, Guided Direct Access, GraphQL Adapters, Apollo Federation, Cosmo Federation), with one mapping to the letters in the methods; the letters stay as internal identifiers.
- **D.** W4-half, 48 core tasks plus 6 ambiguity tasks. A ceiling of 125 dollars for all of study 2, development included (Anthropic 85, OpenAI 40), estimated again after the development preflight; anything above it needs the lead developer's word.
- **E.** Oracle stays up for a whole session; only the access layer restarts per block. The database fingerprint is checked unchanged at the start of each block, and the session is recorded beside the round.
- **F.** Follows D: 48 core tasks.
- **G.** The calculation tool takes results of the same run by result id; it never fetches; an unknown or foreign id is a logged error.
- **H.** Abstained is its own outcome: incorrect in primary accuracy, reported separately from wrong answers, its definition frozen with the scoring.
- **I.** `ask_requester`, identical in every arm, returning the fixed text. A clarification counts only from the tool log (ASKED dropped from the schema). The ambiguity set is scored separately; requests and answers with an accepted interpretation are reported separately, and a request alone is not success. Clarification calls count in usage.
- **J.** A new integration guide for Guided Direct Access, written by a fresh worker without exposure to the scored corpus, the answer key or study 1's task-level findings; given only the study-2 service contracts, the tool capabilities and general business context; independently checked for accuracy and coverage; frozen with its version and hash before scored execution; no revisions driven by outcomes. Study 1's guide stays unchanged.
- **K.** ±10 percentage points is study 2's only predeclared equivalence margin; ±15 is removed, with no fallback. Differences and intervals are reported whether or not equivalence is established, and "equivalence not established" does not prove a difference. The practical justification of ±10 is documented before scored execution. Addition: a documented power calculation at ±10 replaces the earlier rough figure (see [power to establish equivalence](#power-to-establish-equivalence-at-10-percentage-points-decision-k)). It states that power is the chance of establishing equivalence under the stated assumptions, and that a failure to establish equivalence authorizes no extra tasks, repeated runs or spending; any change goes to the lead developer first.
- **L.** If the real Missions service differs from the simulator, first determine whether the difference affects the contracts, the tool behaviour, the guide's accuracy, the answerability of tasks or the expected answers. Record it, fix any affected setup, and run the relevant Direct Access and Guided Direct Access smoke checks again. An unexplained discrepancy blocks the freeze. Expected latency differences are documented; the real service is not made to imitate the simulator (the gate in [the preflight](#preflight-steps)).
- **M.** The Direct Access reference block runs last in the schedule.
