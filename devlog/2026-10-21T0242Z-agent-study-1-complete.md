# Agent study 1 is complete

Date: 2026-10-21T02:42Z
Subject: The first full agent study, study-1, ran 320 of 320 runs over five scenarios and two models on the frozen corpus; the results are preserved and the first findings recorded
Status: Historical / non-normative
Lab checkpoint: lab commit `20610ada0cb3a05e2193f6ecd485e83d099fe879`
Provenance: the date is the `writtenAt` of the run's `bundle.json`, `2026-10-21T02:42:48.684+00:00` (22:42 EDT on October 20), converted to the prescribed UTC minute; the last of the 320 runs finished at 02:41:44 UTC by its `result.json`. The repository checkpoint is the commit the run manifest names as measured (`treeDirty` false); it is not a runtime commit, and this record does not advance the implementation checkpoint. The lead developer asked for this record in the Federation thread on 2026-10-21, judging that the milestone deserved a devlog entry. Every figure below was recomputed read-only by the recording worker from the run folder and the archive on 2026-10-21; the findings are the Coordinator's of the same night, kept as they stood then.
Migrated from lab log SD-2026.294-0242Z; originally written in the lab on 2026-10-21 (lab commit `5851c7c5f135187620f1f14f4e61c01090934a8a`); the study it names is now the Abstraction ladder study.

## Meaningful transition

Until now the agent study existed as a design, a harness, a pilot and a frozen corpus. With study-1 it has its first full set of measurements: every one of the 16 frozen scored tasks was asked in every scenario of the ladder by both models, twice.

- **Design.** 16 tasks x 5 scenarios x 2 models x 2 trials = 320 runs. Scenarios: Alpha (the raw legacy systems), Beta (raw plus a guide written blind), Gamma (the four adapters only, federation plumbing blocked), Delta (adapters plus the Apollo router) and Epsilon (adapters plus the Cosmo router). Models: Claude Sonnet 5.5 (`claude-sonnet-5-5`) and GPT-6.1 Sol (`gpt-6.1-sol`), each at medium effort. One stack run per scenario, with the models nested inside it (split-plot), so the scenario factor has a single replicate.
- **Run.** The manifest was written at 23:05 UTC on October 20; the scenarios ran in the order Alpha, Beta, Gamma, Delta, Epsilon; the last run finished at 02:41 UTC, about 3 h 36 min later. Status complete, 320 result records, one attempt each. Limits: 80 tool calls, 1,000,000 tokens and 900 s per task.

## Results as scored

| Scenario | Correct | Claude | GPT |
| --- | --- | --- | --- |
| Alpha | 39/64 | 21 | 18 |
| Beta | 53/64 | 27 | 26 |
| Gamma | 28/64 | 14 | 14 |
| Delta | 55/64 | 27 | 28 |
| Epsilon | 54/64 | 28 | 26 |

- **By model.** Claude 117 of 160, GPT 112 of 160; 229 of 320 in all.
- **Other outcomes.** 75 wrong answers, 9 did not finish (5 on the tool-call limit, 4 on the token limit), 4 definitions not accepted and 3 errors.
- **Errors.** The 3 errors are vendor connection errors, all GPT on T14, in Beta, Delta and Epsilon. They count as missing, not as wrong answers.
- **Spend.** At the prices of 2026-10-20 the budget records give 23.52 dollars for Claude (31,721,853 tokens, of which 24,872,196 cached reads and 6,324,652 cache writes) and 10.93 dollars for GPT (18,824,668 tokens, of which 14,972,975 cached reads).

## Findings, as they stood on 2026-10-21

These are first readings, before any agreed analysis.

- **The ladder holds for the large steps.** Beta over Alpha, the routers over Alpha, and the routers over Gamma as built. Matched on task, model and trial, with the 3 errors left out, the discordant pairs are: Beta over Alpha 17 to 3, Delta over Alpha 17 to 1, Epsilon over Alpha 16 to 1, Delta over Gamma 28 to 1, Epsilon over Gamma 26 to 0.
- **Beta, Delta and Epsilon cannot be told apart at 16 tasks.** The discordant pairs are few: Beta against Delta 2 to 4, Beta against Epsilon 2 to 3, Delta against Epsilon 2 to 1. Only about 10 tasks separate anything: T01, T02, T08 and T09 were right in all 20 runs, T14 was right once and T15 never.
- **Gamma's low score is structural.** The mapping adapter's only ordinary query is `mappingReleases`. The translation of the Missions local references to asset and personnel ids lives on the `AssetReference` and `PersonnelReference` entities, which are reachable only through `_entities`. The study's MCP server refuses `_entities` in Gamma by design. The Coordinator's post-run check found the mapping adapter up in Gamma's outage tasks, so the cause is not an outage. Gamma scored 0 of 4 on T04, T05, T06, T07, T10, T11 and T12. The lesson as recorded: subgraphs built for federation are not standalone APIs, because their cross-system mapping exists only in entity resolvers. The fairness check that every task is answerable had been run for Alpha only, not per scenario.
- **T15 is a wording mismatch in the frozen corpus, not an agent failure.** No run of T15 was correct in any scenario. The accepted answers count the commanding officer together with the assigned crew, but the question says "among their crew" and, unlike T14, does not say that commanding officers are included. Recounting crew only, the Coordinator found 3, 38, 116 and 207 missions for the four accepted definitions. The agents' answers match: GPT answered 116 four times (Delta and Epsilon twice each, with lieutenant commander and above), and Claude answered 38 with the command ranks. Claude's 115 and 36 are near misses. The corpus stays frozen. The analysis is to report T15 as scored, plus a sensitivity line labelled post hoc.
- **The pilot projection overstated the cost.** The committed pilot projection for two trials was about 42 dollars for Claude and 13 for GPT, against 23.52 and 10.93 measured: about 1.8 times too high for Claude and about 1.2 times for GPT. The projection said itself that its multiplier and its unmeasured scenarios were guesses.
- **Caching affects latency, not only cost.** OpenAI caches by itself. Claude caches only where the request marks it (lab commit `4e2419b`), and the cache lives for five minutes. The cached-read and cache-write tokens of every request are recorded, and every request is timed on its own (lab commit `6f2a7d6`). Caching is a limitation the analysis has to report next to each vendor's latency.

## Decisions and preservation

- **Raw data preserved.** The lead developer ruled that, before anything else, the raw data must be preserved safely. The originals in the machine-local results folder are marked read-only. The Coordinator's archive `lab-results-2026-10-21.zip` holds study-1, pilot-1 and smoke-1 to smoke-3 (719 files) and was verified against its per-file sums. The lead developer also keeps their own zip of the results on their cloud drive; it is a different zip, so it has a different checksum, and the per-file sums verify it after extraction. The data are thus kept in three places, and the analysis works on copies.
- **Gamma-prime.** The lead developer decided to run Gamma-prime, to be fair to Gamma. The mapping adapter gets a plain lookup query, marked `@inaccessible` so that the router schemas, and with them Delta and Epsilon, stay as study-1 measured them. Then Gamma alone runs again on the same frozen corpus, with the same limits, models and trials. Study-1's Gamma stays as the as-built case beside it. At the date of this entry the change was in progress in its own Job and nothing of it had landed. Later context, added before this record was committed: the lookups landed in lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73` with their own [devlog entry](2026-10-21T0424Z-mapping-lookups-runtime-checkpoint.md), which says what the routers' schemas show after the change; the scored Gamma-prime run had not started, and only its dry runs were in the results folder.
- **Analysis next.** The analysis design is to be agreed with the lead developer before the analysis Job starts. The proposal makes the named contrasts confirmatory and the rest exploratory. The single stack run per scenario is a limitation to state there.

## Evidence

- **Run.** `study-1`; bundle checksum `b914cafa2528a3b62feaabdab3af32727c2e2dcb14238cf489e421fd2b70a6b2`, recomputed from the bundle's file list. All 646 files of that list match their recorded SHA-256. Plan hash `fae83d2`.
- **Archive.** `lab-results-2026-10-21.zip`, SHA-256 `1b74534e0a3238fef1ca46bdd8d8a1c9c262ef8c3f5a10f6926187e4e39885ab`. All 719 entries match `SHA256SUMS-2026-10-21.txt`, and so do the 647 study-1 originals.
- **Repository.**
  - The frozen corpus and the pilot summary: lab commit `20610ada0cb3a05e2193f6ecd485e83d099fe879`.
  - The name-field descriptions of the answer schemas: lab commit `f76225cb4e1a3a73ebed156fe28579b395955f2d`.
  - The two-vendor harness: lab commit `46c57d8bf6e00c2fd868f8499d6c79a6d7663f21`.
  - Claude prompt caching and the cached-read price: lab commit `4e2419b259beb1dd8e35eac5acac3dbfe9ad4b28`.
  - Per-request timing: lab commit `6f2a7d6fc7c2bd3a8cfb8446c3f98be2d3516a3f`.
  - Router introspection: lab commit `c20dfbfd76585e5287bc3df4f576e1f7a68c2af7`.
- **Not verified here.**
  - The crew-only recount of T15, which is the Coordinator's: this worker checked the agents' submitted answers against it, not the recount itself.
  - The transcripts' wording behind the Gamma finding.
  - The lead developer's own zip.

The results and transcripts stay outside the repository by design. [Progress](../docs/PROGRESS.md) owns current state.

## Later context (2026-10-21): the study testbed

Added after this record was committed (lab commit `5851c7c5f135187620f1f14f4e61c01090934a8a`); the text above is unchanged. This record calls Alpha "the raw legacy systems" and does not say that one of them was a simulator. study-1 ran the federation stack in its stub-backend mode: Personnel was the real Personnel v2 SOAP service (`personnel-v2-large-004`) and Assets the real Assets read service on PostgreSQL 17 (release 1.1), but Missions was a simulator, `federation/stack/missions-stub/server.py`, serving release 1.2. Alpha and Beta called the simulator directly; Gamma, Delta and Epsilon reached it through the Missions adapter. The Oracle-backed Missions service was validated separately with its adapter (lab commit `f2f76f78985a68549898507a637c177a131952c2`) and was not part of study-1. The run manifest records none of this. The evidence, the unknowns and what this means for reading the results are in [the report's correction](../docs/AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed). The results as scored above are unchanged.
