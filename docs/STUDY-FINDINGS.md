# The two agent studies: results across study 1 and study 2

Status: a non-normative page of the results of Abstraction ladder study 1 and study 2 side by side, written on 2026-11-08 from the two reports only: [study 1's report](AGENT-STUDY-REPORT.md) (runs study-1 and gamma-prime-1) and [study 2's report](STUDY-2-REPORT.md) (run `study2-scored-1`). The reports govern, and where this page differs from them, they win. It holds no new number, analysis or interpretation: every figure is copied from a report as written, with its interval where the report gives one and under the label the report gives it, and links to the section it comes from. It recommends nothing. The design of both studies is in [the study overview](STUDY-OVERVIEW.md).

## What study 1 established

Study 1 is a pilot: 16 tasks, two models, two trials, five scenarios (Alpha raw access, Beta raw access with a guide, Gamma the adapters alone, Delta the adapters behind Apollo, Epsilon the adapters behind Cosmo). Its six named comparisons are confirmatory, Holm-corrected over six, and its equivalence tests use margins of ±10 (primary) and ±15 (secondary) percentage points ([its methods](AGENT-STUDY-REPORT.md#methods)).

**Confirmatory** ([the six comparisons](AGENT-STUDY-REPORT.md#confirmatory-the-six-comparisons), [equivalence](AGENT-STUDY-REPORT.md#confirmatory-equivalence)):

- **Alpha against Delta (ii):** Delta +25.5 percentage points [+12.7, +38.4], Holm p 0.0006. This is the one difference that holds after the correction.
- **Alpha against Beta (i):** Beta +22.1 [+4.2, +40.1], p 0.016 before and 0.079 after the Holm correction; the report states it as not shown at the confirmatory level.
- **Delta and Epsilon (iv):** -1.9 [-7.2, +3.5], shown equivalent within ±10.
- **Beta and Epsilon (vi):** +1.6 [-8.7, +11.8], shown equivalent within ±15 only.
- **Beta and Delta (iii):** +3.4 [-9.5, +16.4], shown equivalent at neither margin; the report calls this inconclusive, not evidence of a difference.
- **Claude against GPT (v):** +3.4 [-3.6, +10.4], p 0.34 before and 1.00 after the Holm correction: the confirmatory test detected no difference in accuracy. It was not tested for equivalence, which the plan applied to iii, iv and vi only. The scenario by model interaction was p 0.32 (unadjusted).

**Accuracy by scenario (confirmatory model)** ([the table](AGENT-STUDY-REPORT.md#confirmatory-accuracy-by-scenario)): Alpha 60.9 percent [43.6, 75.9], Beta 83.1 [58.3, 94.5], Delta 86.5 [62.8, 96.0], Epsilon 84.6 [61.9, 94.9].

**Secondary outcome: cost of a model** ([secondary outcomes](AGENT-STUDY-REPORT.md#secondary-outcomes)): Claude over GPT, cost per run 2.17 [1.82, 2.59]; the report's summary reads it as about 2.2 times.

**Gamma** ([our design error](AGENT-STUDY-REPORT.md#gamma-as-built-our-design-error)): Gamma as built was a design error, not a result, and is used in no test (28/64 correct, descriptive). Gamma-prime, the run after the fix, is exploratory: 78.1 percent [55.8, 91.0], +17.2 points over Alpha [+3.0, +31.4] and -5.1 against Beta [-20.0, +9.7] ([exploratory results](AGENT-STUDY-REPORT.md#exploratory-results)).

**Its stated limits** ([limitations](AGENT-STUDY-REPORT.md#limitations), [the testbed](AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed), [honesty note](AGENT-STUDY-REPORT.md#honesty-note)):

- 16 tasks, of which 11 separate the scenarios, so only large effects can be detected;
- one stack run per scenario, in a fixed order, so time-of-run effects are confounded with the scenario;
- the analysis plan was written after a descriptive look at the data;
- Missions was a simulator, not the Oracle-backed service; no result is shown for the Oracle-backed service;
- Gamma-prime was not interleaved with study-1;
- a synthetic domain and two models at medium effort.

## What study 2 leaves open

Study 2 has four full arms (Guided Direct Access, GraphQL Adapters, Apollo Federation, Cosmo Federation) and one exploratory Direct Access block, on 48 core tasks.

- **No accuracy verdict.** The primary GEE is not estimable. The cause the analysis names is separation: GPT-6.1 Sol's cells in the four full arms are all right or all wrong (in the data, 48 of 48 correct in each). There is no P1 or P2 verdict, no equivalence at ±10 percentage points and no Holm family of S1 to S6. Judgement on accuracy is suspended by the lead developer's decision ([summary](STUDY-2-REPORT.md#summary), [not estimable](STUDY-2-REPORT.md#planned-and-secondary-comparisons-of-accuracy-not-estimable), [what study 2 does and does not show](STUDY-2-REPORT.md#what-study-2-does-and-does-not-show)). The report adds that no equivalence was tested, so the absence of a verdict says nothing about either equivalence or a difference.
- **Observed correct answers in the core set (descriptive)** ([the table](STUDY-2-REPORT.md#descriptive-correct-answers-and-outcomes-in-the-core-set)):

  | Arm | Claude Sonnet 5.5 | GPT-6.1 Sol |
  | --- | --- | --- |
  | Guided Direct Access | 47/48 | 48/48 |
  | GraphQL Adapters | 45/48 | 48/48 |
  | Apollo Federation | 47/48 | 48/48 |
  | Cosmo Federation | 47/48 | 48/48 |
  | Direct Access (one exploratory block) | 36/48 | 27/48 |

- **Also not estimable:** Direct Access against each arm, the planned model comparison (S5) and arm × model interaction (S6) of accuracy, the per-model fits added after the primary stop, and the comparison of the honest-gap rate ([what study 2 does and does not show](STUDY-2-REPORT.md#what-study-2-does-and-does-not-show)). The cluster bootstrap, a sensitivity cross-check that the plan does not let decide, writes an S5 interval of its own ([sensitivity analyses](STUDY-2-REPORT.md#sensitivity-analyses)).

## What study 2 adds

In study 1 the adapters alone had no tested comparison with federation: Gamma as built was used in no test, and Gamma-prime ran separately and was compared only with Alpha and Beta (exploratory). In study 2, GraphQL Adapters is a full arm in the same schedule as the two federation arms ([design](STUDY-2-REPORT.md#design)), and row P1 below compares federation with it on cost, time and tool calls.

These are exploratory, with unadjusted p ([the exploratory measures](STUDY-2-REPORT.md#exploratory-cost-time-and-tool-calls)). They are ratios of geometric means over all core runs of the four full arms, with 95 percent intervals; a ratio below 1 means the first-named arm has the lower geometric mean. In this section the labels P1, P2 and S3 to S5 name the contrasts only, not a planned verdict. The report states the plan's meaningful ratio, 1.25, beside these ratios and draws no conclusion from it; this page draws none either.

| | Comparison | Cost | Time | 1 + tool calls |
| --- | --- | --- | --- | --- |
| P1 | Federation (mean of Apollo and Cosmo) over GraphQL Adapters | 0.85 [0.77, 0.94], p 0.0020 | 0.90 [0.82, 0.99], p 0.0318 | 0.79 [0.72, 0.86], p 0.0000 |
| P2 | Federation (mean of Apollo and Cosmo) over Guided Direct Access | 0.77 [0.68, 0.87], p 0.0000 | 1.33 [1.14, 1.55], p 0.0003 | 1.29 [1.10, 1.52], p 0.0016 |
| S4 | GraphQL Adapters over Guided Direct Access | 0.90 [0.82, 0.99], p 0.0260 | 1.47 [1.31, 1.64], p 0.0000 | 1.64 [1.44, 1.87], p 0.0000 |
| S3 | Apollo Federation over Cosmo Federation | 1.03 [1.00, 1.07], p 0.0768 | 1.02 [0.98, 1.06], p 0.3093 | 1.05 [1.01, 1.09], p 0.0089 |
| S5 | Claude Sonnet 5.5 over GPT-6.1 Sol | 2.19 [2.11, 2.28], p 0.0000 | 0.95 [0.90, 0.99], p 0.0293 | 1.09 [1.05, 1.14], p 0.0001 |

The report also gives these ratios for correct runs only, and S1 and S2 for each router alone.

- **The honest-gap rate on category D (exploratory):** each of the four full arms was honest in 12 of 12 runs of the tasks that need the stopped service, and in 4 of 4 runs of the over-reporting controls. The arms cannot be compared on it: every cell is separated (all honest), and its GEE is not estimable ([the honest-gap rate](STUDY-2-REPORT.md#exploratory-the-honest-gap-rate-on-category-d)).
- **Direct Access (exploratory):** 36 and 27 of 48 correct. It ran as one block, last in the schedule, so its counts are confounded with that time window, and its comparison with each arm is not estimable ([exploratory results](STUDY-2-REPORT.md#exploratory-results)).

## Where the two reports agree

Each pair below is two results under their own labels, from two studies that differ in their conditions. It is not a replication and not a pooled result.

- **The cost of a Claude run.** Study 1, secondary outcome: Claude over GPT 2.17 [1.82, 2.59] ([secondary outcomes](AGENT-STUDY-REPORT.md#secondary-outcomes)). Study 2, exploratory with unadjusted p: S5 2.19 [2.11, 2.28], p 0.0000 ([the exploratory measures](STUDY-2-REPORT.md#exploratory-cost-time-and-tool-calls)).
- **Raw access lowest in accuracy.** Study 1, confirmatory model: Alpha 60.9 percent [43.6, 75.9], the lowest of the four scenarios in the model, and Alpha against Delta is the one difference that holds after correction ([accuracy by scenario](AGENT-STUDY-REPORT.md#confirmatory-accuracy-by-scenario)); Gamma as built was lower descriptively and is used in no test. Study 2, descriptive: Direct Access 36/48 and 27/48, lower than every full arm's counts, from one block, last, with no estimable comparison ([the core set](STUDY-2-REPORT.md#descriptive-correct-answers-and-outcomes-in-the-core-set)).

## Why the studies are not pooled

Study 2's report says that study 2 is not a replication of study 1 and that its accuracy is not pooled with study 1's ([the question](STUDY-2-REPORT.md#the-question)). The conditions that differ:

| | Study 1 | Study 2 |
| --- | --- | --- |
| Missions backend | a simulator ([the testbed](AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed)) | the real Missions service on Oracle ([design](STUDY-2-REPORT.md#design)) |
| Scored tasks | 16 | 48 core tasks, and 6 in a separate ambiguity set |
| The `calculate` tool | no calculation tool ([the overview](STUDY-OVERVIEW.md#at-a-glance); study 1's report names none) | in every arm ([departures](STUDY-2-REPORT.md#departures-and-run-conditions)) |
| Network | a commercial VPN, exit Ashburn, USA ([run conditions](AGENT-STUDY-REPORT.md#run-conditions)) | NordVPN off, the machine's direct connection ([departures](STUDY-2-REPORT.md#departures-and-run-conditions)) |
