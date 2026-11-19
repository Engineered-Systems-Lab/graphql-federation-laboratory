# Study 3 analysis plan (draft)

Status: **draft, not frozen.** No scored run of study 3 has been made. This plan says, rule by rule and in the order of the outputs, what [analyze3.py](analyze3.py) computes from a study-3 bundle. Places marked **MARKED PLACE** are filled at the freeze. The freeze also pins this file's hash, which every manifest then names as `identity.analysisPlan`.

Effort is the primary outcome and accuracy is a floor. Study 2 made accuracy primary; every full arm was at or near 100 percent, its primary model could not be fitted, and effort, which did separate the arms, had been labelled exploratory in advance.

## 1. Inputs and verification

1. The input is a copy of one study-3 run folder, its archive's per-file sums file, its bundle checksum and the corpus folder it ran. The raw folder stays outside the repository and read-only.
2. The copy is verified before anything is computed: every file against the sums, no file missing or extra, the bundle checksum recomputed and equal to the one given, and a complete bundle of the named run.
3. The manifest must name its scorer contract (version 2, with the scorer's hash), its corpus hash, its harness commit and its analysis plan hash, which must be the SHA-256 of this file's bytes. It must hold a `williams-4-half` schedule of the four full arms with Direct Access as the reference block, and exactly two models.
4. The corpus manifest must hash to the corpus hash and list the hash of `tasks.json`, which must match. `tasks.json` must hold exactly the tasks of the schedule and a `directions` entry for each.
5. Any failure stops the analysis with `STOP` and exit code 2, and nothing is written.

## 2. What is read about a task

Only a task's id, category, set, size, systems, stopped service and category-D tag, and from corpus 3's `directions` map its `direction`, `csl`, `anchor` and `requiredSystems`. Never a question, a schema, a key, a design note or a reference solution. A task id is a cluster label and nothing else.

- **Forward against reverse:** `direction` forward (24 core tasks) and reverse (30).
- **Join width:** `requiredSystems`, without category D and without the 2 tasks that read no system: one system (39 tasks) and several (52 tasks), 91 tasks in all.

## 3. Which runs count

1. Study 2's counting rules apply unchanged: every planned run has exactly one record (its last attempt), a void block attempt is excluded and its cost reported apart, and a bundle that breaks a rule stops the analysis.
2. **Effort** counts every scored run of the four full arms on the core set, right or wrong. A run that hits a limit counts with its calls and cost.
3. A vendor error is requeued once. A run that fails again is missing.
4. **A zero cost.** A scored run with a zero cost should not occur. If one does, it is counted, reported, and given the smallest positive cost among all scored runs of the bundle before the log is taken. The spend tables keep the recorded cost.
5. The ambiguity set and Direct Access never enter the confirmatory families.

## 4. The accuracy floor (confirmatory gate)

1. For each comparison arm (GraphQL Adapters and Guided Direct Access): federation (0.5 Apollo + 0.5 Cosmo) minus the arm, in accuracy, on the core set, vendor errors missing.
2. **Estimator:** the mean in each arm x model x round cell; each arm's value is the equal-weight mean over the planned rounds and then the two models.
3. **Resampling:** 10,000 replicates of whole core tasks with replacement, stratified by direction (forward, reverse, none), seed 20261118.
4. **Bound:** the bias-corrected and accelerated (BCa) lower bound at 2.5 percent, with the acceleration from a jackknife within the direction strata.
5. The floor is cleared only when the bound is above -10 percentage points. It is not cleared when a required cell of the full sample is empty or when more than 1 percent of the replicates have an empty cell.
6. **Sensitivity:** the same floor with vendor errors counted as wrong.

## 5. The effort families (confirmatory)

1. **First family:** 1 + tool calls per run. **Second family:** cost per run.
2. **Model:** Gaussian GEE of log(1 + calls), or of log(cost), clustered by task, exchangeable working correlation, robust covariance. Terms: arm x model and round, plus session only when a session boundary falls inside a round and the design has full rank. Each arm is standardized as in study 2, over the planned rounds and sessions with equal weight for the two models.
3. **P1:** federation over GraphQL Adapters. **P2:** federation over Guided Direct Access. Each is a ratio of geometric means with a 95 percent interval, tested two-sided at 0.05, with Holm over P1 and P2 within the family.
4. **A usable fit** follows study 2's rule (converged, finite, no negative covariance eigenvalue beyond rounding, every contrast with a positive variance). A planned round with no runs also makes a fit unusable.

## 6. The effort fallback

Each effort family switches on its own, only when its own fit is unusable, and then both comparisons use the fallback.

1. It is an alternative estimator with the same contrast definition as the GEE. It has no session adjustment, so it is not the adjusted GEE estimator.
2. Resampling and estimator are those of section 4, on the transformed outcome, with 10,000 attempted replicates.
3. A replicate with an empty cell is unusable. The attempted and usable counts are reported. If more than 1 percent are unusable, or a required cell of the full sample is empty, the family is reported as not estimable and every other output is still produced.
4. The bootstrap deviations are widened by sqrt(n/(n-s)) x t(0.975, n-s)/z(0.975), with n the tasks and s the direction strata.
5. The two-sided p-value is (1 + #{|d* - d| >= |d|}) / (B_valid + 1), and the interval is d +/- q_0.95(|d* - d|), matched so that it excludes 0 exactly when p < 0.05. Holm applies to these p-values.

## 7. The CSL family (confirmatory)

Two one-sided tests on P1 tool calls, family level 0.05, Holm over the two.

1. **Model:** the primary GEE's terms plus a group main effect and a group x arm interaction, with the bias-reduced covariance. Each group's P1 contrast is averaged over the two models with equal weight.
2. **Test:** the Wald test of the interaction contrast with a t reference on the number of tasks in the fit minus 1.
3. **Forward against reverse:** fitted on the 54 forward and reverse tasks. The test is log ratio (reverse) minus log ratio (forward) > 0: the advantage is smaller on reverse questions.
4. **Join width:** fitted on the 91 tasks of section 2. The test is log ratio (several) minus log ratio (one) < 0: the advantage is larger on questions that read several systems.
5. **How join width is interpreted.** The model is the prespecified one and has no direction terms. Its result is an association within this corpus, with direction contributing to the difference between the groups, because reverse questions are more common among those that read several systems. It does not isolate join width as a cause.
6. **Fallback.** If either CSL fit is unusable, both tests use it. Each task's own P1 contrast is computed within its model-and-round pairs as 0.5 Apollo + 0.5 Cosmo minus GraphQL Adapters; a pair that lacks any of the three runs is left out, and a task with no complete pair has no contrast. Whole tasks are resampled within each group (10,000 replicates), and the statistic is the difference of the two groups' means. Each group's deviations are widened by sqrt(n/(n-1)) x t(0.975, n1+n2-2)/z(0.975). With s = +1 for a predicted positive contrast and -1 for a negative one, p = (1 + #{s(d* - d) >= s d}) / (B_valid + 1), and the one-sided 95 percent bound is d - s q_0.95(s(d* - d)).

## 8. What can be claimed

1. An effort result against an arm is **claimed** only if it is significant after Holm and federation clears the floor against that arm.
2. A CSL result is claimed only if it is significant after Holm and federation clears the floor against GraphQL Adapters on the core set. Accuracy in each CSL group is reported beside it, descriptively.
3. The gate never changes Holm: Holm runs over both comparisons of a family whatever the floor shows.
4. A result that is significant but fails its gate is reported as significant and not claimed. A family that cannot be estimated makes no claim.

## 9. Sensitivity analyses

Vendor errors counted as wrong for the floor; the bias-reduced covariance for the effort families; the bootstrap of the effort ratios (section 6) beside the GEE; effort on correct runs only.

## 10. Descriptive and exploratory results, labelled so

Time per run on P1 and P2; the other arm pairs; Direct Access; the ambiguity set, apart; results per category, size, anchor and CSL kind, including the link-integrity group and the forward aggregates; correct runs only; the honest-gap rate on category D; spend; and the tasks of study 2 against study 2's results. None of these supports a confirmatory claim. A descriptive or exploratory analysis that cannot be computed is reported as not estimable, and every other output is still written.

**Legacy load.** The measure is the requests to Missions, Personnel and Assets per run and arm, descriptive, as ratios with intervals. The reader is [legacy3.py](legacy3.py) (Job `study3_legacy_load`, decisions L1 to L6 and D1 to D7). The analysis runs without it.

1. **What is recorded.** The raw arms' requests are in their transcripts. For the GraphQL arms, the study launch kit turns on the JDK's request log in the Missions, Personnel and Assets adapters with a compose overlay; no image changes. Before each stack is removed it saves the time, system and answer status of every request and answer, never a URL or a body. It also saves the offset between the host's and Docker's clocks, at each stack start and before each removal ([the launch kit](../launch/README.md#the-legacy-load-record)).
2. **What counts as one request.** A request that reached the service, whatever the answer.
   - **Raw arms:** an `http_request` or `soap_request` (with the harness tools on, read from the run's `results.jsonl` under the result id the transcript names) that returned an HTTP status, that timed out, or whose error shows that a connection was made and the request was sent (a reset, a remote disconnect, a bad status line). The last kind is counted and also reported apart.
   - **Not counted:** an address the allow-list refused, a refused connection, a name that did not resolve, and an error the reader cannot classify, which is reported as unclassified.
   - **GraphQL arms:** every request line of the three adapters.
   - **The system** is named by the port (8082 Personnel, 8083 Missions, 8084 Assets), or by the adapter.
3. **Which runs count.** The runs of section 3: the scored runs of the core set, their last attempts, with the void-block rule. A vendor error is missing.
4. **Placing a GraphQL request.** A run's window is its first transcript event to its `finishedAt`. A request belongs to the run whose window holds it, in the stack start that covers the run. Within a stack start:
   - the requests before its first scored run are the **block initialization load**;
   - the other requests outside every window are **unattributed**;
   - every request within the measured clock offset of a window's start or end is counted as **near a boundary**.
5. **A block that is not countable.** A block of a GraphQL arm is not countable when any of these holds:
   - its log was not saved whole, does not match its file sums, or holds a row the reader cannot read;
   - a clock offset is missing, or above 1 second at either end;
   - for Apollo and Cosmo, the log does not show the Personnel snapshot read completed before the first scored run: 11 consecutive Personnel requests each answered 200 (one probe and 10 pages of the 1,000 people of `personnel-v2-large-004`).

   Its runs are left out of the per-question figures and counted as left out.
6. **The figures.** For each system, and the three together, and each arm: the mean requests per scored run, each arm the equal-weight mean of its model x round cells as in section 4. The ratios of the means are:
   - federation (0.5 Apollo + 0.5 Cosmo) over GraphQL Adapters;
   - federation over Guided Direct Access;
   - each arm over Direct Access.

   The cells are those of the planned runs, so a cell whose every run is a vendor error is an empty cell. The 95 percent percentile intervals use section 4's resampling: whole core tasks with replacement, stratified by direction, 10,000 replicates, seed 20261118.
   - **Not estimable:** a figure with an empty cell or a zero denominator in the full sample, or with more than 1 percent of its replicates unusable.
   - **Reported beside them:** the block initialization load per arm and system, a total that includes it, the unattributed requests, the requests near a boundary per block, the blocks that are not countable with their reasons, and the raw arms' requests by kind.
   - **What the figures describe.** The per-question figures describe the prepared system. The total with initialization keeps the cost of starting the adapters visible.
7. **A setup difference from study 2.** In study 3's config, the warm-up of Apollo and Cosmo resolves one Personnel reference, so the Personnel adapter reads its whole snapshot before the first scored run: `{ mission(missionId: "ST-00000LD4O") { commandingOfficer(release: "1.3") { resolution } } }`.
   - **Why a Missions request too:** through the graph, the snapshot is read only through a mission's crew or commanding-officer reference. So each warm-up pass also asks Missions for one mission.
   - **In study 2,** the warm-up was `{ __typename }`, which reaches no legacy system, so the first Personnel-using run of a block read the snapshot.
   - **GraphQL Adapters is unchanged:** its server blocks `_entities`, and its Personnel root field never reads the snapshot.
   - **The outage behaviour is unchanged:** the adapter probes the service at every batch even with the snapshot held. A stopped Personnel service still answers UNAVAILABLE, as the instrumentation Job confirmed on the adapter image against a counting backend. The data a run can read is unchanged.

## 11. Power

**MARKED PLACE: the final power figures.** The freeze uses the power of the implemented analysis. The draft figures below come from section 12's validation (2,000 simulated studies per cell; a rate near 0.5 has a simulation error of about 0.011). "Stand-in" is [power3.py](power3.py): t-tests over resampled questions from study 2's data, 4,000 simulations per cell.

**Effort, claimed, at 107 tasks (implemented analysis / stand-in):**

| Share of study 2's effect | Tool calls P1 | Tool calls P2 | Cost P1 | Cost P2 |
| --- | --- | --- | --- | --- |
| 100 percent | 1.000 / 1.000 | 1.000 / 0.998 | 0.991 / 0.996 | 1.000 / 1.000 |
| 75 percent | 1.000 / 1.000 | 0.962 / 0.941 | 0.905 / 0.938 | 0.996 / 0.993 |
| 50 percent | 0.951 / 0.953 | 0.719 / 0.659 | 0.587 / 0.616 | 0.824 / 0.806 |

**The CSL family under Holm, implemented analysis.** Each scenario reports the differences of log ratios it actually generates on corpus 3's shape.

| Scenario | Share | Generated: reverse minus forward | Generated: several minus one | Forward against reverse | Join width |
| --- | --- | --- | --- | --- | --- |
| Advantage gone on reverse only | 100 | +0.239 | +0.074 | 0.722 | 0.002 |
| | 75 | +0.179 | +0.055 | 0.496 | 0.007 |
| | 50 | +0.120 | +0.037 | 0.250 | 0.012 |
| Join width only | 100 | +0.036 | -0.180 | 0.095 | 0.725 |
| | 75 | +0.027 | -0.135 | 0.065 | 0.472 |
| | 50 | +0.018 | -0.090 | 0.050 | 0.255 |
| Both effects together | 100 | +0.275 | -0.106 | 0.862 | 0.402 |
| | 75 | +0.206 | -0.080 | 0.624 | 0.249 |
| | 50 | +0.138 | -0.053 | 0.315 | 0.127 |

The 100 percent join-width effect is an estimate from study 2: the P1 tool-call log ratio on questions that read several systems minus those that read one, without category D, by corpus 2's `systems` field (-0.180, from 18 and 20 questions). The two groups' compositions explain the generated differences: an effect on one CSL contrast moves the other because direction and join width overlap.

**The stand-in beside the calculation of 2026-11-10** (simulation error in brackets):

| Figure | That calculation | power3.py |
| --- | --- | --- |
| P1 tool calls, 76 questions, 75 percent, Holm | 1.00 | 0.992 (0.001) |
| P2 tool calls, 76 questions, 75 percent, Holm | 0.84 | 0.835 (0.006) |
| Forward against reverse, 30 and 30, advantage gone on reverse | 0.90 | 0.886 (0.005) |
| Forward against reverse, 21 and 30, advantage gone on reverse | 0.82 | 0.826 (0.006) |

## 12. Validation of the implemented analysis

**The validation is accepted with one documented exception (decision A26). Not every validation limit passed.** [validate3.py](validate3.py) ran the whole selection procedure (usability check, any fallback, Holm and the accuracy gate) on simulated studies at corpus 3's shape: 107 core tasks, the schedule of the study, both models, log-normal tool calls and cost at study 2's spread, tool calls capped at 80, about 2 percent missing runs, and a session boundary inside a round in every second study.

- **Size:** 2,000 simulated studies per scenario, 10,000 bootstrap replicates, master seed 20261120. The simulation error of a rate of 0.05 is 0.0049.
- **The limits (decision A11):** a false-positive rate above 0.06 for a 0.05 test or family, above 0.035 for the floor at a true -10 points, or a coverage below 0.93.
- **The code validated (SHA-256 with LF line ends):** `data3.py` 3e51c48662c46b2f4edd40004b04ff5def3ab3ab140f01a2195e013a77109dcc, `simulate3.py` 800f62544d7e62abdc12d093dd5a6363162133d7dcce3ec6daf92c97729adfd4, `stats3.py` 138c559e1d4f9a2b3b3ec7608d6e103a4bc55320ffb2e7925be7c556be235d6c, `validate3.py` e5e2b2ec1df1826dbe7a14a78b54d432ca2d31118a5c2c68f0054b1b1c0f52fb.

**The exception.** With the CSL fallback forced, in the scenario with study 2's effort effects and no CSL effect (`effort-100`), the forward-against-reverse test alone, before Holm, wrongly rejected at a rate of **0.0620**, above the limit of 0.06. The Holm family rate in that scenario is **0.0590**. The lead developer approved this exception and required no further tuning on this evidence.

**At the limit, not above it.** The selected procedure's tool-call family under no effect has a false-positive rate of **0.0600**.

**False-positive rates (selected procedure / fallback forced):**

| Scenario | Tool calls family | Cost family | CSL family (Holm) | Forward against reverse alone | Join width alone |
| --- | --- | --- | --- | --- | --- |
| No effect | 0.0600 / 0.0525 | 0.0565 / 0.0500 | 0.0510 / 0.0530 | 0.0480 / 0.0555 | 0.0520 / 0.0495 |
| Effort at 100 percent | - | - | 0.0550 / 0.0590 | 0.0555 / **0.0620** | 0.0515 / 0.0540 |
| Effort at 75 percent | - | - | 0.0500 / 0.0550 | 0.0540 / 0.0570 | 0.0455 / 0.0470 |
| Effort at 50 percent | - | - | 0.0450 / 0.0505 | 0.0460 / 0.0475 | 0.0470 / 0.0470 |

**Coverage of the 95 percent intervals:** the lowest over every comparison and scenario is 0.9315 for the selected procedure and 0.9360 with the fallback forced.

**The floor at a true difference of exactly -10 points**, the share of studies that wrongly clear it (against GraphQL Adapters / Guided Direct Access):

| Case | Wrongly cleared |
| --- | --- |
| Comparison arm at 100 percent, federation varying by task around 90 percent | 0.0260 / 0.0255 |
| Comparison arm 96 to 100 percent, federation 10 points lower on every task | 0.0335 / 0.0300 |
| Comparison arm at 100 percent, one task in ten wrong in every federated run | 0.0215 / 0.0225 |

**Limits of this evidence.**

1. No simulated study had an unusable GEE, so the mix of methods that natural fit failures would cause was not measured. The selected and the forced runs show each method alone.
2. Earlier validation runs led to changes in the method and are development history. The figures here come from one run on the final code, on a seed no earlier run used.
3. About 30 false-positive rates are checked, each with the simulation error above, so a rate near a limit can cross it by chance.

## 13. Outputs

`results.json`, `tables.md` and `figures/effort.svg`, written outside the repository. Every float is rounded to six decimals and every random draw is seeded, so the same inputs give the same bytes; no absolute path is written. The tiers stay apart in every output: confirmatory, sensitivity, descriptive and exploratory.

## 14. Filled at the freeze

- **MARKED PLACE: the final power figures** (section 11).
- **MARKED PLACE: the price table** read for the scored run. Cost is computed from each run's tokens and its model's price entry in the manifest.
- **MARKED PLACE: the limits of the scored run** (tool calls, tokens, time and retries).

The legacy-load reader of section 10 was filled before the freeze by the instrumentation Job, because the load can only be recorded during the scored run.
