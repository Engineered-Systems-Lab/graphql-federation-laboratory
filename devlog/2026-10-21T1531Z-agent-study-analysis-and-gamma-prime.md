# Agent study 1 is analysed, with the Gamma-prime run

Date: 2026-10-21T15:31Z
Subject: The Gamma-prime run gave the adapters-only scenario a fair second measurement, and the first full agent study was analysed under the agreed plan and written up as a report
Status: Historical / non-normative
Lab checkpoint: lab commit `f7e54da77ccc622ae78cc59681ecf4cb7bcc7d2f`
Provenance: the date is the Git committer time of the report lab commit `f7e54da77ccc622ae78cc59681ecf4cb7bcc7d2f`, `2026-10-21T11:31:28-04:00` (15:31 UTC), converted to the prescribed UTC minute. It is not a runtime commit, and this record does not advance the implementation checkpoint. The lead developer asked for this record in the Federation thread on 2026-10-21, as another important milestone. The figures below are the analysis's own output and the run's bundle, as recorded in the report and the evidence files.
Migrated from lab log SD-2026.294-1531Z; originally written in the lab on 2026-10-21 (lab commit `4087861a95a756c5c67c4899f5450484078f6ef6`); the study it names is now the Abstraction ladder study.

## Meaningful transition

Until now study-1 had results as scored and first readings from a descriptive look. It now has an analysis fixed in a plan the lead developer agreed, scripts that reproduce every number from verified copies of the raw runs, and a report that states what holds and what does not. The adapters-only scenario, which study-1 had measured under our own design error, has a fair second measurement.

## Gamma-prime

- **Why.** In study-1, Gamma could not translate the Missions local references, because the mapping adapter exposed that translation only through `_entities`, which the scenario blocks. The lead developer decided to run Gamma-prime, to be fair to Gamma.
- **The fix.** The plain lookups of the mapping adapter (lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73`, with its records lab commit `ace5e4b020ed2cf66a298ff24918943f4fb7c990`) and their test through the study's adapters MCP server (lab commit `6e5ce156b7ef411430ad5fb92385330b5be05b9a`).
- **The run.** gamma-prime-1, started by the lead developer on 2026-10-21 and finished at 13:10 UTC: Gamma only, 64 runs, the same frozen corpus, models, trials, limits, machine and network path as study-1. 50 of 64 correct (Claude 23 of 32, GPT 27 of 32), against 28 of 64 as built. Matched by task, model and trial, 22 runs were right only in Gamma-prime and none only in study-1's Gamma. Spend 3.19 dollars for Claude and 1.92 for GPT. Bundle checksum `ff31d2bb752ef1df5b3fb28f7be767c2862b53b197b9ae441a6b9f078329390c`; archive `gamma-prime-1-2026-10-21.zip`, SHA-256 `1c394bd06edfc98bb7556c7a6af02f08b1f28de86d8ec9042131aa59e2aa8ff6`.

## The analysis and the report

- **Plan.** Agreed by the lead developer on 2026-10-21, after a descriptive look, which the report says plainly. Confirmatory: Alpha, Beta, Delta and Epsilon of study-1, a logistic GEE clustered by task, six Holm-corrected comparisons and equivalence tests at plus or minus 10 points (primary) and 15 (secondary). Everything else exploratory; Gamma as built in the methods and limitations only.
- **Confirmatory results, as the report states them.**
  - Delta over Alpha: +25.5 points (95 percent interval +12.7 to +38.4), Holm p = 0.0006.
  - Beta over Alpha: +22.1 points (+4.2 to +40.1), p = 0.016 before and 0.079 after the Holm correction: not shown at the confirmatory level, though the exact paired test was strong.
  - No difference among Beta, Delta and Epsilon. The two routers equivalent within 10 points (Epsilon minus Delta -1.9, -7.2 to +3.5); Beta and Epsilon within 15 only; Beta and Delta at neither margin, an inconclusive result.
  - Claude and GPT alike in accuracy (+3.4 points, -3.6 to +10.4), with no sign of a scenario by model interaction (p = 0.32).
- **Secondary.** An Alpha run cost about twice a router run; a Claude run cost about 2.2 times a GPT run at the dated prices.
- **Exploratory, labelled as such.** Gamma-prime 17.2 points above Alpha (+3.0 to +31.4) and 5.1 below Beta (-20.0 to +9.7), across runs that were not interleaved. On the outage tasks T10 and T11 the scenarios with a guide or a router were nearly always honest about the stopped service, while Alpha and Gamma-prime more often claimed a complete answer; this rests on the scored outcomes only, and the transcripts were not read. On T07 the guide led Beta to 0 of 4. Under a post-hoc crew-only reading of T15, six study-1 runs would flip and comparison i would pass the correction; that reading is not confirmatory.
- **The limit that matters most.** 16 tasks, of which 11 separate the scenarios, and one stack run per scenario: only large effects can be detected.

## Along the way

- **A wording correction.** The first commit of the analysis tooling said "small evidence", which can read as weak evidence. The lead developer asked for precise wording, so the approved commit (lab commit `882e9bd`) was replaced before integration by one that names the files; the superseded branch was removed on the lead developer's word and the commit is unreferenced.
- **A figure bug.** The cost figure's axis labels were rounded to one decimal; it was caught by looking at the rendered figure and fixed with a test before the report landed.
- **Still open.** What "structure over kind", one of the exploratory items, means is being discussed with the lead developer; the report states the reading it used.

## Evidence

- **Analysis tooling and evidence files.** lab commit `3a65070083b4693ccdd3c18b0dd43b5c78e03bad`: the scripts, their tests and the study gate's analysis suite; the score tables, run manifests and bundle and archive checksums of both runs. The raw transcripts and bundles stay outside the repository and are cited by checksum.
- **Report.** lab commit `f7e54da77ccc622ae78cc59681ecf4cb7bcc7d2f`: [the agent study report](../docs/AGENT-STUDY-REPORT.md) with its figures, and the Progress entry.
- **study-1.** Bundle checksum `b914cafa2528a3b62feaabdab3af32727c2e2dcb14238cf489e421fd2b70a6b2`; its earlier record is [Agent study 1 complete](2026-10-21T0242Z-agent-study-1-complete.md).
- **Not verified here.** The transcripts behind the exploratory readings; the lead developer's own copy of the results.

[Progress](../docs/PROGRESS.md) owns current state.

## Later context (2026-10-21): the study testbed

Added after this record was committed (lab commit `4087861a95a756c5c67c4899f5450484078f6ef6`); the text above is unchanged. Neither this record nor the report said that one of the three legacy systems was a simulator. Both study-1 and gamma-prime-1 ran on a mixed testbed: Personnel was the real Personnel v2 SOAP service (`personnel-v2-large-004`) and Assets the real Assets read service on PostgreSQL 17 (release 1.1), but Missions was a simulator, `federation/stack/missions-stub/server.py`, serving release 1.2. In gamma-prime-1 the Missions adapter's surviving container points at that simulator. The Oracle-backed Missions service was validated separately with its adapter (lab commit `f2f76f78985a68549898507a637c177a131952c2`) and was in neither run. The report gained a dated section, [Correction (2026-10-21): the study testbed](../docs/AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed), with the evidence, the unknowns and the limits on generalization; every result, statistic and limitation recorded above is unchanged.
