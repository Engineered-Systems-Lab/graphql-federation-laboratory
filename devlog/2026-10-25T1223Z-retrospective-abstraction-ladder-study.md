# Retrospective: Abstraction ladder study 1

Date: 2026-10-25T12:23Z
Subject: A retrospective of the lab's first full agent study, Abstraction ladder study 1: the run study-1 of 2026-10-20 and 2026-10-21, the design error found in its adapters-only scenario, the Gamma-prime run that measured that scenario again, and the analysis and report of 2026-10-21
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). Nothing was run again for it.

## What changed

Before study-1 the agent study was a design, a harness, a pilot and a frozen corpus (lab commit `20610ada0cb3a05e2193f6ecd485e83d099fe879`). Study-1 gave it its first full set of measurements ([entry](2026-10-21T0242Z-agent-study-1-complete.md)): 16 frozen tasks, five scenarios, two models, two trials, 320 runs, from 23:05 UTC on 2026-10-20 to 02:41 UTC on 2026-10-21. The five scenarios are the rungs of the ladder: the raw legacy systems (Alpha), the raw systems with a guide written blind (Beta), the four adapters alone (Gamma), and the adapters behind the Apollo router (Delta) or the Cosmo router (Epsilon). The models were Claude Sonnet 5.5 and GPT-6.1 Sol, each at medium effort. Answers were scored by script against expected answers derived from the released data, with no language-model judge.

As scored, 229 of 320 runs were correct: Alpha 39 of 64, Beta 53, Gamma 28, Delta 55 and Epsilon 54.

## What was found, and decided

- **Gamma as built was a design error of the lab's, not a finding.** The mapping adapter offered the translation of the Missions references only through `_entities`, the federation plumbing that the Gamma scenario blocks by design. The lesson recorded: subgraphs built for federation are not standalone APIs. The check that every task is answerable had been run for Alpha only. The lead developer decided to run Gamma-prime, to be fair to Gamma: the mapping adapter gained plain lookups, kept out of the router schemas so that Delta and Epsilon stay as measured (lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73`, [entry](2026-10-21T0424Z-mapping-lookups-runtime-checkpoint.md)), and Gamma alone ran again on the same corpus, models, trials and limits: 50 of 64 correct, against 28 as built.
- **T15 is a wording mismatch of the frozen corpus.** No run of it was correct in any scenario; its accepted answers count the commanding officer with the crew while its question does not say so. The corpus stays frozen, and the analysis reports T15 as scored with a sensitivity line labelled post hoc.
- **The raw data first.** The lead developer ruled that before anything else the raw data must be preserved safely; it is kept in three places and the analysis works on copies.
- **The analysis plan** was agreed by the lead developer on 2026-10-21, after a descriptive look at the data, which the report says plainly.

## What was measured

The analysis and the report landed on 2026-10-21 (lab commit `3a65070083b4693ccdd3c18b0dd43b5c78e03bad` for the scripts and evidence files, lab commit `f7e54da77ccc622ae78cc59681ecf4cb7bcc7d2f` for the report; [entry](2026-10-21T1531Z-agent-study-analysis-and-gamma-prime.md)). As [the report](../docs/AGENT-STUDY-REPORT.md) states them:

- The graph over raw access is clear: Delta answered 25.5 points more than Alpha (95 percent interval +12.7 to +38.4, Holm-corrected p = 0.0006).
- The guide over raw access is likely but not shown after correction: Beta 22.1 points over Alpha, p = 0.016 before and 0.079 after the Holm correction.
- Beta, Delta and Epsilon could not be told apart. The two routers were equivalent within 10 points; Beta and Delta at neither margin, which is inconclusive and not a finding of no difference.
- The two models did not differ in accuracy, and a Claude run cost about 2.2 times a GPT run at the dated prices; an Alpha run cost about twice a router run.
- Gamma-prime, exploratory: 17.2 points above Alpha and 5.1 below Beta, across runs that were not interleaved.

The limit that matters most: 16 tasks, of which about 11 separate the scenarios, and one stack run per scenario, so only large effects can be detected.

## Later context

Both runs were made on a mixed testbed that neither the first records nor the report named: Personnel and Assets were the real services, and Missions was a simulator serving release 1.2, not the Oracle-backed Missions service. The report gained a dated correction on 2026-10-21 ([the study testbed](../docs/AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed)); every result as scored is unchanged. The study came into this repository with commit `3acf04447a5095316168959bafa21daa4180e6dc`, and the tasks and expected answers of its corpus and its guide are frozen here (commits `8224a5784dd7c6156f205e2949a1b00e14b6136d` and `dbeae079860877585a6b60758d9efeb665e0a08d`). The raw transcripts and bundles stay outside the repository and are cited by checksum.

## Evidence

- The three migrated entries linked above, with lab commit `20610ada0cb3a05e2193f6ecd485e83d099fe879`, lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73`, lab commit `3a65070083b4693ccdd3c18b0dd43b5c78e03bad` and lab commit `f7e54da77ccc622ae78cc59681ecf4cb7bcc7d2f`.
- [The Abstraction Ladder: Evaluating AI-Agent Access to Legacy Systems](../docs/AGENT-STUDY-REPORT.md), the study's report.
- [The study folder](../study/README.md), with its corpus, harness, analysis and evidence.
