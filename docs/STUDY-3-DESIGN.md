# Abstraction ladder study 3: design

Status: design page of Abstraction ladder study 3 (strand 1). It was written on 2026-11-26, after study 3's scored run (`study3-scored-1`, 2026-11-24 and 2026-11-25), at main commit `94b11c974f919798b21fc56aa75e846ec87eaef5`, from sources that were frozen or decided before that run. **It is not pre-registration.** Study 3's pre-registration is the [frozen analysis plan](../study/analysis3/PLAN.md) (frozen on 2026-11-22), the project decisions [D068 to D074](../project-governance/DECISIONS.md) and the [freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json), and those bind. The page is non-normative: where the frozen plan, the freeze record, the scoring contract (version 2, defined in [study/harness/scoring_contract.py](../study/harness/scoring_contract.py) and implemented by corpus 3's [scorer](../study/corpus3/scoring.py)) or the guide ([study/guide2/GUIDE.md](../study/guide2/GUIDE.md)) differ from it, they win. It describes the design as it was frozen, not as later corrected, and it describes the design only, not the results. The worker that wrote it, the AI agent of the Job `study3_design`, did not read the scored run's outputs or the analysis of them, and the page holds no result of that run.

**Its sources** are only these, read as they stood at the freeze: the [frozen analysis plan](../study/analysis3/PLAN.md); the study 3 analysis README in the text it had at the scored run, the text of commit `9a2459ba416199495999b892847834a03d7f9524` (the freeze's second commit), read with `git show 9a2459ba416199495999b892847834a03d7f9524:study/analysis3/README.md` (the [file on main](../study/analysis3/README.md) was changed by a commit after the run, so its link shows later text); decisions D068 to D074 in [DECISIONS](../project-governance/DECISIONS.md) and their [rationale](../project-governance/RATIONALE.md#study-3-design-d068-d074); the [corpus 3 README](../study/corpus3/README.md); the [launch kit README](../study/launch/README.md); the [freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json); the four devlog entries before the run: the [kit check](../devlog/2026-11-13T0313Z-study3-kit-check.md), the [comparison of the second key derivation](../devlog/2026-11-17T1907Z-study3-keys-b3-comparison.md), the [preflight](../devlog/2026-11-20T1835Z-study3-preflight.md) and the [freeze](../devlog/2026-11-22T0230Z-study3-freeze.md). It follows the form of [study 2's design page](STUDY-2-DESIGN.md), section by section where a section applies, and links that page only as a pointer, for how the arms, the tools and the block schedule shared with study 2 work. The commit ids of the freeze's two transactions are as Git records them. It holds no task text, key, design note or reference solution: corpus 3 is described by counts and fields only.

## The question and what "better" means

**The question.** Study 3 asks whether GraphQL federation reduces agent effort (tool calls, cost) on cross-system lookups, with accuracy only as a floor ([corpus 3](../study/corpus3/README.md)).

**Why effort and not accuracy.** The plan says: "Effort is the primary outcome and accuracy is a floor." Study 2 made accuracy primary. Every full arm of study 2 was at or near 100 percent, its primary model could not be fitted, and effort, which did separate the arms, had been labelled exploratory in advance ([the plan](../study/analysis3/PLAN.md)). The rationale of D069 adds that only a new run under a plan frozen first can make effort confirmatory ([rationale](../project-governance/RATIONALE.md#study-3-design-d068-d074)).

**What a cross-system lookup is** (D068). A cross-system lookup (CSL) is a reverse lookup, a link-integrity question or an aggregate over joined data. Forward joins stay their own category and are the comparison. Decision 1a narrows the aggregates: an aggregate is a CSL only when it starts from the far side (per person or per asset); aggregates that start from missions are forward, and are also reported as their own descriptive group. The rationale states the reason: these questions have an answer only where the systems meet, and only the mapping knows the global ids.

**The measures** (D069, D070, D073):

1. **Tool calls:** 1 + the tool calls of a run. This is the primary confirmatory family.
2. **Cost:** the cost of a run, a second confirmatory family.
3. **Accuracy:** a non-inferiority floor of 10 percentage points that gates the effort results; it is not a claim.
4. **Time:** descriptive, with intervals and no claim.
5. **The load on the legacy systems:** descriptive, with intervals and no claim.

**The planned comparisons** ([plan, section 5](../study/analysis3/PLAN.md#5-the-effort-families-confirmatory)):

- **P1:** federation over GraphQL Adapters.
- **P2:** federation over Guided Direct Access.
- **Federation** is 0.5 Apollo Federation + 0.5 Cosmo Federation, with the two arms weighted equally ([plan, section 4](../study/analysis3/PLAN.md#4-the-accuracy-floor-confirmatory-gate)).

## The arms

The arms are study 2's five ([study 2's arms](STUDY-2-DESIGN.md#the-arms)), with the internal letters that stay in configurations, run keys and bundles:

| Arm | Letter | Role in study 3 |
| --- | --- | --- |
| Guided Direct Access | beta | full arm; reads study 2's frozen guide, unchanged (D072) |
| GraphQL Adapters | gamma | full arm |
| Apollo Federation | delta | full arm (federation) |
| Cosmo Federation | epsilon | full arm (federation) |
| Direct Access | alpha | the reference block, outside the confirmatory families |

- **The schedule** holds the four full arms with Direct Access as the reference block ([plan, section 1](../study/analysis3/PLAN.md#1-inputs-and-verification)). The ambiguity set and Direct Access never enter the confirmatory families ([plan, section 3](../study/analysis3/PLAN.md#3-which-runs-count)).
- **Every scenario starts the whole federation stack:** the backends, the four adapters and one router, Cosmo for epsilon and Apollo otherwise. Alpha and beta also publish the legacy services on their loopback ports ([launch kit](../study/launch/README.md#the-two-missions-modes)).
- **The models** are exactly two, named with their request settings in the freeze record: `claude-sonnet-5-5` (Anthropic, adaptive thinking, effort medium, at most 16,000 output tokens) and `gpt-6.1-sol` (OpenAI, reasoning effort medium, not stored, at most 16,000 output tokens).
- **Held equal in every arm:** the system prompt, the harness tools and the limits, each equal to study 2's ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json); [the tools](#the-tools-and-the-guide)).

## The corpus

**What it is** ([corpus 3](../study/corpus3/README.md)). Study 2's checked pool and ambiguity set, carried byte for byte, plus 31 new tasks: 27 in the reverse group and 4 forward tasks that read all three systems. The Job `study3_corpus3` built it under decisions C1 to C8. Corpus 2 and its frozen files are unchanged.

**No draw** (D071). D071 reads: "There is no draw: every checked pool question plus the new CSL questions, one run per question, arm and model." The frozen `tasks.json` is "the whole scored set, with no draw (decisions C2 and C7)": its 113 tasks also hold the 4 new forward tasks, which are not CSL, and the 6 ambiguity tasks, reported apart ([corpus 3](../study/corpus3/README.md#files); [the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json)). The two sources differ in wording, and no committed rule names which binds, so this page names neither and does not settle the difference. Any pool question set aside at study 2's answerability check stays out. The rationale gives the alternative rejected: a draw with quotas, as in study 2; the pool keeps study 2's coverage at about 1.4 times its quotas, and study 2's 48 drawn tasks are a subset of it.

**The counts:**

| Set | Tasks | Source |
| --- | --- | --- |
| Core: corpus 2's pool | 76 | [corpus 3, `tasks.json`](../study/corpus3/README.md#files) |
| Core: new | 31 | the same |
| Core, in all | 107 | the same |
| Ambiguity set (`set: ambiguity`, reported apart) | 6 | the same |
| Scored set, in all | 113, of which 14 in category D (run under an outage) | the [freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json) |
| Development set (`dev.json`, corpus 2's, byte for byte) | 8 | [corpus 3](../study/corpus3/README.md#files); the [preflight](../devlog/2026-11-20T1835Z-study3-preflight.md) |

**The new tasks, by group** (the corpus README lists them by id): 10 reverse lookups from a person, 8 reverse lookups from an asset, 9 far-side aggregates (4 per asset or asset group, 5 per person or Personnel group) and 4 forward tasks over all three systems. Their sizes: 10 small, 17 medium, 4 large. Categories keep study 2's letters (decision C4): a reverse lookup is B or C, a far-side aggregate is E.

**The direction fields** ([corpus 3](../study/corpus3/README.md#the-direction-fields)). Each scored task has an entry in the `directions` map of `tasks.json`, with `direction`, `csl`, `anchor` (the system the question starts from) and `requiredSystems` (the services the answer must read). `classify` in `derive_a3.py` sets `direction` and `csl` (decision C5):

- the ambiguity set and category D: `direction: none`, `csl: null`;
- anchor a person or an asset, and the task must read Missions: `reverse`, with `csl: far-side-aggregate` for category E and `reverse-lookup` otherwise;
- anchor missions, category C, and the task must read another system: `none`, `csl: link-integrity`, outside the forward-against-reverse test and reported as its own group;
- anchor missions and another system to read: `forward`; anything else `none`.

The result: 30 reverse (20 reverse lookups and 10 far-side aggregates), 24 forward (20 carried and the 4 new), 4 link integrity and 55 none. The join-width groups read `requiredSystems`, never the anchor ([plan, section 2](../study/analysis3/PLAN.md#2-what-is-read-about-a-task)): without category D and the 2 tasks that read no system, 39 tasks read one system and 52 several, 91 in all.

**The keys.** `keys-a.json` holds corpus 2's keys byte for byte and the keys of the new tasks, derived by `derive_a3.py`. A second derivation of the 31 new keys (keys B) was written blind to the first derivation's code, keys and design notes, in a cloud task with no network, from a package built by `study/blind/blind.py`. The comparison in `compare_keys3.py` found no difference on any of the 31 tasks, so nothing was put to the lead developer and no key changed ([corpus 3](../study/corpus3/README.md); [the comparison devlog](../devlog/2026-11-17T1907Z-study3-keys-b3-comparison.md)).

**Answerability.** Corpus 2's reference solutions and one solver per new task, written against corpus 2's access interface, are run by `reference/run_reference.py` ([corpus 3](../study/corpus3/README.md#the-reference-solutions)). In study 3's preflight, on the real Oracle-backed stack, every task was correct in all five arms, the three outages included: core 107 of 107, ambiguity 6 of 6 and development 8 of 8 ([the preflight](../devlog/2026-11-20T1835Z-study3-preflight.md)).

**Blindness.** No task text leaves corpus 3's folder and corpus 2's; `test_corpus3.py` checks that no tracked file outside the folder holds a new question ([corpus 3](../study/corpus3/README.md)). The analysis reads only a task's id, category, set, size, systems, stopped service and category-D tag, and the four direction fields; a task id is a cluster label and nothing else ([plan, section 2](../study/analysis3/PLAN.md#2-what-is-read-about-a-task); the analysis README at commit `9a2459b` (not the post-run text on main)).

## The tools and the guide

- **The harness tools:** `calculate` and `ask_requester`, harness tools version 5, with the same hash as study 2's ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json)). What they do is described in [study 2's design](STUDY-2-DESIGN.md#the-tools).
- **The system prompt:** the same text as study 2's, named by hash in the freeze record.
- **The guide** (D072): Guided Direct Access reads study 2's frozen guide, [study/guide2/GUIDE.md](../study/guide2/GUIDE.md), unchanged (10,990 bytes, frozen since 2026-11-06). The rationale gives the reasons: the guide was written blind to study 2's corpus and may say nothing about reverse lookups; the graph is not extended for CSL either, so neither side gets help, and both are tested as a business has them today. Whether the guide copes is part of what is measured. The tradeoff it names: CSL results may reflect the guide's silence as well as the graph. No alternative is recorded.
- **The limits** (decision Z3 of the Job `study3_freeze`; [plan, section 14](../study/analysis3/PLAN.md#14-filled-at-the-freeze)): study 2's limits in every run of every arm and both models: 80 tool calls, 1,000,000 tokens and 900 seconds per run, and 3 retries of a request, 5 seconds apart, with at most 2 nudges. A run stopped at a limit is `did_not_finish` and counts for effort with its calls and cost. A request that still fails after its 3 retries ends the run as a vendor error, which the harness queues again once. The plan gives the measurements behind the limits, from the preflight's paid run of the 8 development tasks.

## Experimental design

### The schedule

- **The shape:** a `williams-4-half` schedule of the four full arms, with Direct Access as the reference block ([plan, section 1](../study/analysis3/PLAN.md#1-inputs-and-verification)). It is study 2's block schedule: [the Williams square in four rounds](STUDY-2-DESIGN.md#the-schedule-a-williams-square-in-four-rounds) and [the halves and the split between the models](STUDY-2-DESIGN.md#what-each-block-runs-and-the-split-between-the-models). In the scored plan as the freeze's dry runs ran it, the Direct Access reference block came last ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json)).
- **The size of the scored plan:** the 113 scored tasks, both models and all five arms, 1,130 runs in 17 blocks; one trial; every task with both models in every arm, 226 runs per arm ([the freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md); the freeze record's dry run of that plan).
- **Not set at the freeze:** the scored run's seed, its budget and any top-up. They were left to the scored run's Job ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json); [the freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md)), and this page does not describe them.

### Which runs count

([plan, section 3](../study/analysis3/PLAN.md#3-which-runs-count))

1. Study 2's counting rules apply unchanged: every planned run has exactly one record (its last attempt), a void block attempt is excluded and its cost reported apart, and a bundle that breaks a rule stops the analysis.
2. Effort counts every scored run of the four full arms on the core set, right or wrong. A run that hits a limit counts with its calls and cost.
3. A vendor error is requeued once; a run that fails again is missing.
4. A scored run with a zero cost should not occur. If one does, it is counted, reported, and given the smallest positive cost among all scored runs of the bundle before the log is taken; the spend tables keep the recorded cost.
5. The ambiguity set and Direct Access never enter the confirmatory families.

### The accuracy floor (confirmatory gate)

([plan, section 4](../study/analysis3/PLAN.md#4-the-accuracy-floor-confirmatory-gate); D070)

- **The difference:** for each comparison arm (GraphQL Adapters and Guided Direct Access), federation minus the arm, in accuracy, on the core set, vendor errors missing.
- **The estimator:** the mean in each arm x model x round cell; each arm's value is the equal-weight mean over the planned rounds and then the two models.
- **Resampling:** 10,000 replicates of whole core tasks with replacement, stratified by direction (forward, reverse, none), seed 20261118.
- **The bound:** the BCa lower bound at 2.5 percent, with the acceleration from a jackknife within the direction strata.
- **Cleared** only when the bound is above -10 percentage points. It is not cleared when a required cell of the full sample is empty or when more than 1 percent of the replicates have an empty cell.
- **Sensitivity:** the same floor with vendor errors counted as wrong.
- **The margin** is study 2's justified one (decision Z3 of the Job `study2_freeze`), as the rationale of D070 states. The tradeoff: no claim that accuracy is superior.

### The effort families (confirmatory)

([plan, sections 5 and 6](../study/analysis3/PLAN.md#5-the-effort-families-confirmatory); D069)

- **Two families:** tool calls (1 + tool calls per run) and cost per run.
- **The model:** a Gaussian GEE of log(1 + calls), or of log(cost), clustered by task, with an exchangeable working correlation and robust covariance. Terms: arm x model and round, plus session only when a session boundary falls inside a round and the design has full rank. Each arm is standardized as in study 2, over the planned rounds and sessions, with equal weight for the two models.
- **The tests:** P1 and P2, each a ratio of geometric means with a 95 percent interval, tested two-sided at 0.05, with Holm over P1 and P2 within the family.
- **A usable fit** follows study 2's rule (converged, finite, no negative covariance eigenvalue beyond rounding, every contrast with a positive variance); a planned round with no runs also makes a fit unusable.
- **The fallback,** switched on per family only when its own fit is unusable, and then for both comparisons: the estimator and the stratified resampling of the floor on the transformed outcome, 10,000 attempted replicates, with no session adjustment. Replicates with an empty cell are unusable; above 1 percent unusable, or with an empty required cell, the family is not estimable. The deviations are widened by sqrt(n/(n-s)) x t(0.975, n-s)/z(0.975), and the p-value and interval are matched so that the interval excludes 0 exactly when p < 0.05.
- **Alternatives the rationale records:** one family of six (Holm over six) or a fixed order; one family would cost the primary up to 19 points of power. The tradeoffs: no confirmatory claim on time, and cost depends on the price table read at the freeze.

### The CSL family (confirmatory)

([plan, section 7](../study/analysis3/PLAN.md#7-the-csl-family-confirmatory); D068, D071)

Two one-sided tests on P1 tool calls, family level 0.05, Holm over the two:

- **Forward against reverse:** fitted on the 54 forward and reverse tasks. The test is log ratio (reverse) minus log ratio (forward) > 0: the advantage is smaller on reverse questions.
- **Join width:** fitted on the 91 tasks of the join-width groups. The test is log ratio (several) minus log ratio (one) < 0: the advantage is larger on questions that read several systems.
- **The model:** the primary GEE's terms plus a group main effect and a group x arm interaction, with the bias-reduced covariance; each group's P1 contrast is averaged over the two models with equal weight. The Wald test of the interaction contrast uses a t reference on the number of tasks in the fit minus 1.
- **How join width is read:** the model has no direction terms, so its result is an association within this corpus. Direction contributes to the difference between the groups, because reverse questions are more common among those that read several systems. It does not isolate join width as a cause.
- **The fallback,** used by both tests if either fit is unusable: each task's own P1 contrast within its model-and-round pairs, whole tasks resampled within each group (10,000 replicates), and the difference of the two groups' means, with the widening and the one-sided p-value and bound the plan gives.
- **The rationale's tradeoff** (D071): only "the advantage disappears on reverse" is testable at a feasible size.

### What can be claimed

([plan, section 8](../study/analysis3/PLAN.md#8-what-can-be-claimed))

1. An effort result against an arm is claimed only if it is significant after Holm and federation clears the floor against that arm.
2. A CSL result is claimed only if it is significant after Holm and federation clears the floor against GraphQL Adapters on the core set. Accuracy in each CSL group is reported beside it, descriptively.
3. The gate never changes Holm: Holm runs over both comparisons of a family whatever the floor shows.
4. A result that is significant but fails its gate is reported as significant and not claimed. A family that cannot be estimated makes no claim.

### Sensitivity, descriptive and exploratory results

- **Sensitivity** ([plan, section 9](../study/analysis3/PLAN.md#9-sensitivity-analyses)): vendor errors counted as wrong for the floor; the bias-reduced covariance for the effort families; the bootstrap of the effort ratios beside the GEE; effort on correct runs only.
- **Descriptive and exploratory, labelled so** ([plan, section 10](../study/analysis3/PLAN.md#10-descriptive-and-exploratory-results-labelled-so)): time per run on P1 and P2; the other arm pairs; Direct Access; the ambiguity set, apart; results per category, size, anchor and CSL kind, including the link-integrity group and the forward aggregates; correct runs only; the honest-gap rate on category D; spend; the tasks of study 2 against study 2's results; and the legacy load ([below](#the-legacy-load-record)). None of these supports a confirmatory claim, and one that cannot be computed is reported as not estimable while every other output is still written.
- **The outputs** ([plan, section 13](../study/analysis3/PLAN.md#13-outputs)): `results.json`, `tables.md` and `figures/effort.svg`, written outside the repository, with the tiers kept apart: confirmatory, sensitivity, descriptive and exploratory. The same inputs give the same bytes.

### Power

([plan, section 11](../study/analysis3/PLAN.md#11-power); decision Z1 of the Job `study3_freeze`)

The frozen figures are the power of the implemented analysis, from 2,000 simulated studies per cell, beside a stand-in, `power3.py` (t-tests over resampled questions from study 2's data, 4,000 simulations per cell). Effort, claimed, at 107 tasks (implemented analysis / stand-in):

| Share of study 2's effect | Tool calls P1 | Tool calls P2 | Cost P1 | Cost P2 |
| --- | --- | --- | --- | --- |
| 100 percent | 1.000 / 1.000 | 1.000 / 0.998 | 0.991 / 0.996 | 1.000 / 1.000 |
| 75 percent | 1.000 / 1.000 | 0.962 / 0.941 | 0.905 / 0.938 | 0.996 / 0.993 |
| 50 percent | 0.951 / 0.953 | 0.719 / 0.659 | 0.587 / 0.616 | 0.824 / 0.806 |

The CSL family under Holm, implemented analysis (the generated differences of log ratios are in the plan):

| Scenario | Share | Forward against reverse | Join width |
| --- | --- | --- | --- |
| Advantage gone on reverse only | 100 | 0.722 | 0.002 |
| | 75 | 0.496 | 0.007 |
| | 50 | 0.250 | 0.012 |
| Join width only | 100 | 0.095 | 0.725 |
| | 75 | 0.065 | 0.472 |
| | 50 | 0.050 | 0.255 |
| Both effects together | 100 | 0.862 | 0.402 |
| | 75 | 0.624 | 0.249 |
| | 50 | 0.315 | 0.127 |

The 100 percent join-width effect is an estimate from study 2 (-0.180, from 18 and 20 questions), and an effect on one CSL contrast moves the other because direction and join width overlap. The rationale of D071 gives the earlier power calculation behind the size: tool calls on P2 need 76 to 90 questions for a power of 0.84 or more if the effect shrinks by a quarter; forward against reverse needs about 30 and 30; more questions help more than repeats.

### Validation of the implemented analysis

([plan, section 12](../study/analysis3/PLAN.md#12-validation-of-the-implemented-analysis))

- **What ran:** `validate3.py` ran the whole selection procedure (usability check, any fallback, Holm and the accuracy gate) on simulated studies at corpus 3's shape: 107 core tasks, the study's schedule, both models, log-normal tool calls and cost at study 2's spread, tool calls capped at 80, about 2 percent missing runs, and a session boundary inside a round in every second study. 2,000 simulated studies per scenario, 10,000 bootstrap replicates, master seed 20261120.
- **The limits** (decision A11): a false-positive rate above 0.06 for a 0.05 test or family, above 0.035 for the floor at a true -10 points, or a coverage below 0.93.
- **Accepted with one documented exception (decision A26).** With the CSL fallback forced, in the scenario with study 2's effort effects and no CSL effect, the forward-against-reverse test alone, before Holm, wrongly rejected at 0.0620, above the limit; the Holm family rate there is 0.0590. The lead developer approved the exception and required no further tuning on this evidence. The selected procedure's tool-call family under no effect is at the limit, 0.0600.
- **Coverage:** the lowest over every comparison and scenario is 0.9315 for the selected procedure and 0.9360 with the fallback forced.
- **Not exercised: the loader's cost.** The simulated studies hand each run's cost straight to the selection procedure and do not go through `data3.py`'s loader, which changed after the validation's snapshot (lab commit `4d44f05b381b7b7cf6309632b95ffd4b19852174`) to price each request on its own. The statistical procedure and the files the validation ran are unchanged, so the figures stand; the loader's per-request pricing is checked by the tests `LongContextCostTests`.
- **Its own limits,** as the plan states them: no simulated study had an unusable GEE; earlier validation runs led to changes and are development history, and the rerun after the cutoff fix used the same seed; about 30 rates are checked, so a rate near a limit can cross it by chance.

## The backend and the legacy-load record

### The backend

- **The real Missions service on Oracle,** in the launch kit's real mode ([launch kit](../study/launch/README.md#the-two-missions-modes)), as in study 2. Oracle and the service are the operator's explicit steps; the kit never starts, provisions, resets or removes Oracle.
- **The data:** Missions release 1.2 on Oracle, with the dataset fingerprint `missions-db:8aae139eea3d5ad9ff764bc15502c804ccae4f94b9504b687a163a6d0bf76dd1`, equal to study 2's, read at the kit check, the preflight and the freeze ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json); [the kit check](../devlog/2026-11-13T0313Z-study3-kit-check.md)). The released data of the new keys: the mapping releases 1.0 to 1.3, the Assets dataset 1.1 and the Personnel v2 snapshot `personnel-v2-large-004` ([corpus 3](../study/corpus3/README.md)).
- **The images:** one `launch.py build` per study run, which writes its own pin set; every start of the real mode runs from those images without building. Every build writes new image ids in the containerd image store, so the scored run's Job builds once and records its own pin set ([launch kit](../study/launch/README.md#the-two-missions-modes); [the freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md)).
- **The outages** of category D stop and start the Missions service, Assets or Personnel through the kit ([launch kit](../study/launch/README.md#the-two-missions-modes)).

### The legacy-load record

(D073; [plan, section 10](../study/analysis3/PLAN.md#10-descriptive-and-exploratory-results-labelled-so); [launch kit](../study/launch/README.md#the-legacy-load-record))

- **What is measured:** the requests to Missions, Personnel and Assets per run and arm, descriptive only, as ratios with intervals. The rationale states why it is reported: the router's per-reference fetches (no caching, no batching) may raise the requests to the legacy systems. A third confirmatory family was rejected: the direction was not predicted, and it would take power.
- **How it is recorded:** the raw arms' requests are in their transcripts. For the GraphQL arms, the compose overlay `request-log.compose.yaml` turns on the JDK's request log in the Missions, Personnel and Assets adapters, with no image change. Before each stack is removed the kit saves the time, system and answer status of every request and answer, never a URL or a body, and the offset between the host's and Docker's clocks at each stack start and before each removal.
- **What counts as one request:** a request that reached the service, whatever the answer. The plan lists what the raw arms count and what is not counted; for the GraphQL arms, every request line of the three adapters.
- **Placing a request:** a run's window is its first transcript event to its `finishedAt`. Requests before a stack start's first scored run are the block initialization load; other requests outside every window are unattributed; requests within the measured clock offset of a window's edge are counted as near a boundary.
- **A block that is not countable:** a log not saved whole, not matching its sums or holding a row the reader cannot read, a missing clock offset or one above 1 second at either end, or, for Apollo and Cosmo, no sign that the Personnel snapshot read completed before the first scored run (11 consecutive Personnel requests answered 200). Its runs are left out of the per-question figures and counted as left out.
- **Which runs count:** the runs of [plan section 3](../study/analysis3/PLAN.md#3-which-runs-count): the scored runs of the core set, their last attempts, with the void-block rule; a vendor error is missing.
- **The figures:** per system and for the three together, the mean requests per counted run, each arm the equal-weight mean of its model x round cells; the ratios federation over GraphQL Adapters, federation over Guided Direct Access and each arm over Direct Access, with 95 percent percentile intervals from the floor's resampling. Beside them: the initialization load, a total that includes it, the unattributed requests, the requests near a boundary, the blocks not countable with their reasons, and the raw arms' requests by kind.
- **The reader** is `study/analysis3/legacy3.py` (the Job `study3_legacy_load`, decisions L1 to L6 and D1 to D7). The analysis runs without it.
- **A setup difference from study 2.** In study 3's config the warm-up of Apollo and Cosmo is `{ mission(missionId: "ST-00000LD4O") { commandingOfficer(release: "1.3") { resolution } } }`, which resolves one Personnel reference, so the Personnel adapter reads its whole snapshot before the first scored run; each pass also asks Missions for that one mission. Study 2's warm-up was `{ __typename }`, which reaches no legacy system. GraphQL Adapters' warm-up is unchanged, and so are Direct Access's and Guided Direct Access's. The outage behaviour is unchanged: a stopped Personnel service still answers UNAVAILABLE with the snapshot held.

## Cost

What was planned before the run:

- **How cost is computed** ([plan, section 14](../study/analysis3/PLAN.md#14-filled-at-the-freeze); decision Z2): from each run's tokens and its model's price entry in the manifest, which the harness takes from `study/harness/prices-20261121.json`, dated 2026-11-21. Both pricing pages were read again on 2026-11-21 (UTC). In dollars per million tokens:

  | Model | Input | Cached read | Cache write | Output |
  | --- | --- | --- | --- | --- |
  | claude-sonnet-5-5 | 2.00 | 0.10 | 2.50 (five minutes) | 10.00 |
  | gpt-6.1-sol | 2.00 | 0.10 | 2.50 (30 minutes) | 10.00 |
  | gpt-6.1-sol, a request above 272,000 input tokens | 4.00 | 0.20 | 5.00 (30 minutes) | 15.00 |

- **Each request is priced on its own:** a gpt-6.1-sol request whose input (input, cached-read and cache-write tokens together) is above 272,000 tokens is priced at the long-context rates for the full request. Cost includes OpenAI cache writes (the Jobs `study3_openai_cache_write` and `study3_openai_long_context`, both landed before the freeze).
- **The size,** as the rationale of D071 gives it: about 850 runs in the four full arms against study 2's 384, as estimated then. The two sources differ here: the scored plan that the freeze dry-ran is 1,130 runs, 226 per arm, so 904 in the four full arms ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json)). The rationale is non-normative, so the freeze record binds; this page does not settle the difference.
- **Not set at the freeze:** the scored run's budget and any top-up ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json)).

## The freeze

The Job `study3_freeze` (2026-11-20 to 2026-11-22) froze what the scored run uses, before the scored run, in two transactions of one mission: commit `3ef23b4b49d7292994a4da46531013cac065ac84` (the content, with the freeze record, D068 to D074 and their rationale) and commit `9a2459ba416199495999b892847834a03d7f9524` (the frozen rows in the [project's artifact classification table](../project-governance/ARTIFACT-CLASSIFICATION.md) and the frozen checksums in the frozen manifest, because a frozen path cannot enter a checkpoint). The [freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md) describes the two transactions; it was written before either commit, so the ids are Git's.

| What | Frozen as | SHA-256 |
| --- | --- | --- |
| The analysis plan | [study/analysis3/PLAN.md](../study/analysis3/PLAN.md), frozen on 2026-11-22; every manifest's `identity.analysisPlan` | `85c06abbc7e668aeeb2da337c8bf3cb9166d3113e299593e782e5536f02d5a8f` |
| The corpus manifest | `study/corpus3/corpus-manifest.json`, status `frozen-2026-11-22`; every manifest's `identity.corpusFreeze` | `808ddbf7f125916e3add9beeee10ebfda23047e0221674022fb880c064660d4b` |
| The scored tasks | `study/corpus3/tasks.json`, listed in the manifest | `3879f7e7231c0170c7ef26643121cec2599636103cbd8b7249891158c4f518cd` |
| The scorer | `study/corpus3/scoring.py`, corpus 2's byte for byte, scoring contract version 2 | `b872f8e2c3bed3fe3cc1c99712dbb2b5b5c5292e1af165bb556391930464084d` |
| The guide of Guided Direct Access | [study/guide2/GUIDE.md](../study/guide2/GUIDE.md), 10,990 bytes | `e9a4c12620fea0b924683666f20f44a60a4d8888088b583038e1e47cd0b3fade` |
| The price table | `study/harness/prices-20261121.json`, dated 2026-11-21 | `55181c0f5957cc6684a9071777af6cc2b20fad44661b0f2e46124de73025a2a2` |

- **Also named by hash in the freeze record:** the system prompt, the harness tools, the limits and the models, each equal to study 2's except the models' entry, which is named on its own; `schemas.json`, `expected.json`, `keys-a.json` and `dev.json`, listed in the corpus manifest; and the 21 files the run executes, at the harness commit `c5c4d9656daec97268462d3ba04752482ce40912`, the last commit that changed one of them.
- **Frozen rows:** the plan, the corpus manifest, `tasks.json`, `schemas.json` and `expected.json`. The scorer, `keys-a.json`, `dev.json` and the analysis scripts stay open; the plan is frozen, not the scripts ([corpus 3](../study/corpus3/README.md); the analysis README at commit `9a2459b` (not the post-run text on main)).
- **What the freeze changed in the plan,** in these places only and no rule ([plan, "The changes at the freeze"](../study/analysis3/PLAN.md#the-changes-at-the-freeze)):
  - the title and the status line;
  - section 11: its marked place, closed with the figures as they stood (Z1);
  - section 12: the validated code's hashes named as those of the validation's snapshot (`4d44f05`), and a note that the simulation did not exercise the loader's cost, which changed after it, with the tests that check it; no figure or rule changed;
  - section 14: the price table (Z2) and the limits (Z3) filled, and the power figures' place closed.
- **The price table and two code Jobs.** The OpenAI page lists cache-write prices where `prices.json` had 0.00. The lead developer first answered "Not a change, go on". A review then found that the harness did not count OpenAI cache writes, and the lead developer routed that to a code Job before the freeze ("(a), code Job first"). Two Jobs landed: `study3_openai_cache_write` (commit `93e0663b80cca4e816c330805d2c62389ded4936`) and `study3_openai_long_context` (commit `c5c4d9656daec97268462d3ba04752482ce40912`) ([the freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md)).
- **The dry runs** (decision Z4). The full scored plan ran twice on the fake vendor client, with no key and no spend: `study3-freeze-dry-1` on commit `0d8b5ee35dd2b10e37fcf9d57e8dc2a476224023`, kept as superseded for code, and `study3-freeze-dry-2` on `c5c4d96`, after the two code Jobs. Each was 1,130 runs in 17 blocks; every block ended at attempt 1, every provenance check matched, every health point was up, and `legacy3.py` counted every block of both bundles. The frozen files were written after the second run, so their date is 2026-11-22 ([the freeze record](../study/evidence/study-3-freeze/freeze-record-20261122.json); [the freeze devlog](../devlog/2026-11-22T0230Z-study3-freeze.md)).

## Decisions of the lead developer

Study 3's decisions were answered from 2026-11-10 to 2026-11-17 and recorded as project decisions D068 to D074 at the freeze (decision Z5). Each entry of [DECISIONS](../project-governance/DECISIONS.md) quotes the lead developer's answer; the [rationale](../project-governance/RATIONALE.md#study-3-design-d068-d074) gives the reasons, labelled by who gave them.

- **D068, decision 1** ("Far side only", 2026-11-10; refined as decision 1a, "A, yes", 2026-11-11): what counts as a cross-system lookup ([above](#the-question-and-what-better-means)).
- **D069, decision 2** ("Yes, two families", 2026-11-10): tool calls on P1 and P2 as the primary family (Holm over 2), cost on P1 and P2 as a second confirmatory family (Holm over 2), time descriptive.
- **D070, decision 3** ("Yes, as recommended", 2026-11-10): accuracy as a non-inferiority floor at 10 percentage points, one-sided, by a cluster bootstrap over questions, as a gate on each arm's effort results.
- **D071, decision 4** ("Yes, whole pool", 2026-11-10): no draw; every checked pool question plus the new CSL questions, one run per question, arm and model; forward against reverse tested one-sided. How this wording differs from the frozen `tasks.json` is stated [above](#the-corpus).
- **D072, decision 5** ("Keep it as is", 2026-11-10): study 2's frozen guide, unchanged.
- **D073, decision 6** ("Yes, descriptive", 2026-11-10): the legacy load descriptive only, with intervals and no claim.
- **D074, decision 8** (as revised on 2026-11-17, "Record it: postpone strand 2 until study 3 is complete"): study 3 is strand 1, and strand 2 is postponed.

**Where the sources differ on a date.** DECISIONS says that each of D068 to D074 was "recorded as a project decision on 2026-11-22, at the freeze". The rationale's evidence line says: "These decisions were recorded on 2026-11-21, at the freeze". The rationale's own status line reads "Explanatory / non-normative" ([rationale](../project-governance/RATIONALE.md)), so DECISIONS binds; this page does not settle the difference.
