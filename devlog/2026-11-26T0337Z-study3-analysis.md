# Study 3's frozen analysis runs on the scored bundle, twice with the same bytes, and its outputs are kept as evidence

Date: 2026-11-26T03:37Z
Subject: Archived study 3's raw data and verified a copy of the scored run study3-scored-1. Ran the frozen analysis plan's analyze3.py and legacy3.py on it twice each at 72d39c2, with byte-identical outputs. Committed the score table, manifest, outputs and checksums as study/evidence/study-3/
Status: Historical / non-normative
Provenance: Written on 2026-11-26 (UTC) by the worker of the Job study3_analysis, before the commit that carries it. The entry is dated by the end of the second analysis run at 72d39c2, 03:37:25Z by `date -u` in the run script; the first run ended at 03:37:17Z. Sources, all outside the repository: the Job record with decisions B1 to B4 and the riders of entries 26, 34 and 37, the lead developer's answers in the worker's session, the run logs and the outputs. The worker held no API key, ran no stack and made no vendor call. It read the outputs, manifests and ledgers by fields, ids, counts and hashes only. The numbers below are quoted as `tables.md` and `legacy-load.json` write them, and this entry holds no interpretation of them.

## Before the analysis

- **The checks.** These checks ran on main `5a19c3d9fc0c60a73ab3b2aafefcebbf5f98a271`, and again on `68584edbbe0dda549770444f38a24333136b0645` and `ce4d042eb891fc344f44b4cf72a31f3d57e096ad`. On `72d39c2b3153de19c54f8994d397070d00f19063` the worker ran the last two again; the bundle's status and checksum and the sums file's SHA-256 were covered there by `analyze3.py`'s own verification (`tables.md`, "Inputs: the verification"):
  - The bundle's status was `complete` and its checksum `457ce298d1426a4d762bd217dd314a302e8da7ec9b73061c0a1c4e6a64133f06`.
  - The sums file `SHA256SUMS-study3-scored-1.txt` (3,422 lines) hashed to `c6da89d8beee91671c947238f05ec1d0cbd40c4397fb77a66428ead72308fb9c`.
  - `PLAN.md` hashed to `85c06abbc7e668aeeb2da337c8bf3cb9166d3113e299593e782e5536f02d5a8f`, the manifest's `identity.analysisPlan`.
  - The freeze record's frozen file hashes, its value hashes and the 21 files the run executes all matched.

  On each new main, `PLAN.md`, `data3.py`, `stats3.py`, `simulate3.py`, `validate3.py` and `power3.py` hashed as before. `legacy3.py` changed at ce4d042 in the fix Job `study3_output_labels` and hashed on 72d39c2 as on ce4d042.
- **The count of frozen hashes.** The Job record and the scored run's entry speak of 11 frozen hashes, but no record names the set. The worker first counted 10 file hashes. When the lead developer asked it to check, it found 11 hashes bound to a file in the freeze record's frozen section, leaving out the 21 code files: those 10 and corpus 2's manifest. That this is the set meant is the worker's inference. All of them matched, and the lead developer said to move on.
- **The departures from the design.** None of these touches a rule of the plan, so none is a plan deviation:
  - the OpenAI top-up during the run;
  - the machine's restart for a Windows Update before the go;
  - the VPN being off.
- **The archive (decision B2).** On the lead developer's go, three files were written beside the machine-local folder, with the originals only read:
  - `lab-results-study3-2026-11-25.zip`: 6,151 members, the whole results folder, SHA-256 `039aeb4885f392f99e8402b50322b8cb3cd5ee31a0990f8c22fd0abeb7f71b58`. It holds the scored run, the rehearsal, the two carried preflight runs, the harness's MCP call logs and the three sums files.
  - `setup-study3-2026-11-25.zip`: 166 members, SHA-256 `bf303fb3679a8edb7fd2cf281cdb0fc5f95a680f110c4c8fc4410159c1056621`. It holds the configuration, logs and state with the legacy-load folder, and `SHA256SUMS-setup`.
  - `SHA256SUMS-unlisted-study3`: the sums of the 178 archived files that no sums file lists, SHA-256 `cef932c82a85fd671e9c30b88bfedace22cb4d4a710ec9182504ffaa519c0626`.

  Every member was decompressed and compared with its sums: 6,317 in all, none missing, extra or different. The copy off this machine is the lead developer's step.
- **The copies.** The run folder and its sums file were copied outside every checkout and checked: 3,422 files, none different or extra. The legacy-load folder was copied and checked against the unlisted sums: 136 files in 34 sessions. While starting the first test suite, the worker's command also wrote a one-line timestamp file beside the analysis folder. The worker deleted it at once.
- **The holds.** Three times the Job held for a fix to the scripts' outputs, each made by its own Job. No rule of the plan and no confirmatory figure changed in any of them; the legacy-load total and the time ratios' p-values changed at ce4d042, as below. The outputs of each earlier base stay outside the repository and are not committed.
  - On 5a19c3d the suite passed (76 tests), and `analyze3.py` ran twice with byte-identical outputs, then `legacy3.py` once with the scored run's bytes. The Codex review of that candidate's preview found that `tables.md` did not show the verification, the counting or the spend, and that the legacy3 command it printed lacked `--run-id`. The fix Job `study3_analyze3_tables` changed `analyze3.py`, its README and its tests in 68584ed.
  - On 68584ed the suite passed (79 tests), and `analyze3.py` ran twice with byte-identical outputs. The Codex review of the second candidate's preview found that the legacy-load total was counted on all 226 runs of each arm rather than on the core set, and that time per run on P1 and P2 sat under an exploratory tier with p-values. It also found that the second candidate's devlog entry counted 12 Direct Access runs twice. The fix Job `study3_output_labels` changed `analyze3.py`, `legacy3.py` and their tests in ce4d042.
  - Before the suite ran on ce4d042, the lead developer had P1 and P2 named in full. The Job `study3_heading_names` changed `analyze3.py` and its tests in 72d39c2: the three confirmatory headings, the time heading and its tier, and the comparison labels, which read "Apollo and Cosmo weighted equally".

  Each time, the worktree was removed and a new one was made from the new main.
- **The suite.** The analysis3 suite passed on 72d39c2: 88 tests in 343.5 seconds, 03:18:57Z to 03:24:44Z. The lead developer first said to skip rider 3's checks and run the suite, so it ran in the primary checkout at 72d39c2, which was clean afterwards. The lead developer then had the checks run and the rest of the rider done in one go; the checks above ran after the suite, all passing.

## The analysis

- **Command.** `analyze3.py` at 72d39c2, with `--run-id study3-scored-1` and `--study2-scores study/evidence/study-2/scores.csv`. It ran on the lead developer's go, under `STUDY_MCP_PYTHON`.
- **Runs.** Two runs into fresh folders, 03:36:47Z to 03:37:17Z and 03:37:17Z to 03:37:25Z.
  - Both exited 0 with no STOP, and their outputs are byte-identical.
  - Each printed seven statsmodels PerfectSeparationWarnings.
  - Against the outputs at 68584ed, the differences are the ones the fixes made: in `results.json`, the per-measure exploratory tiers citing plan section 10, the time ratios on P1 and P2 moved to `timeOnP1AndP2` with intervals and no p-value, the tier of the study 2 tasks, and the comparison labels; in `tables.md`, the counting label of Direct Access, the four headings and the labels; in `figures/effort.svg`, its title. No output holds the old label "mean of Apollo and Cosmo".
- **Verification** (`tables.md`):
  - 3,422 files of the copy were each checked against the sums, and the bundle checksum was recomputed and equal to the one given.
  - The bundle was written at 2026-11-25T05:42:33.552+00:00.
  - Scorer contract version 2, harness commit `37124bdb3767d8f244e14c3c28832006a7e5b3ea`, harness tree not dirty.
  - The corpus has 113 tasks.
- **Which runs count** (`tables.md`):
  - 1,130 runs in the bundle: 856 core runs of the four full arms and 226 runs of Direct Access, with 60 runs of the ambiguity set analysed apart. The ambiguity set's 60 runs are 12 in each of the five arms, so 12 of them are among Direct Access's 226: 856 + 226 + 48 = 1,130.
  - No vendor error and no requeued or twice-failed run.
  - No resumed block, no void attempt and no zero-cost run.
- **The accuracy floor** (federation minus the arm, points; margin -10):

  | Against | Difference | Lower bound | Floor |
  | --- | --- | --- | --- |
  | GraphQL Adapters | +1.6 | -0.1 | cleared |
  | Guided Direct Access | +1.1 | -0.3 | cleared |

- **The effort families** (method gee, so no fallback; Holm over P1 and P2). P1 is Federation (Apollo and Cosmo weighted equally) over GraphQL Adapters, and P2 is Federation (Apollo and Cosmo weighted equally) over Guided Direct Access:

  | Family | P1 | P2 |
  | --- | --- | --- |
  | 1 + tool calls per run | 0.727 [0.689, 0.767], p 0.0000, Holm 0.0000, claimed | 1.287 [1.156, 1.433], p 0.0000, Holm 0.0000, claimed |
  | Cost per run (USD) | 0.771 [0.716, 0.830], p 0.0000, Holm 0.0000, claimed | 0.846 [0.767, 0.932], p 0.0008, Holm 0.0008, claimed |

- **The CSL family** (tool calls of P1; one-sided 0.05; method gee):

  | Test | Tasks | Difference of log ratios | One-sided bound | p | Holm | Result |
  | --- | --- | --- | --- | --- | --- | --- |
  | Advantage smaller on reverse questions than on forward questions | forward 24, reverse 30 | +0.183 | +0.064 | 0.0065 | 0.0065 | claimed |
  | Advantage larger on questions that read several systems than on one | one system 39, several systems 52 | -0.257 | -0.172 | 0.0000 | 0.0000 | claimed |

- **Time per run** (descriptive, ratios of geometric means with 95 percent intervals, no p-value and no claim; all runs):

  | | Ratio [95% CI] |
  | --- | --- |
  | P1 | 0.78 [0.72, 0.85] |
  | P2 | 1.28 [1.14, 1.44] |

- **Spend by arm** (USD, counted runs; archived and void attempts 0.000000 in every arm):

  | Arm | USD |
  | --- | --- |
  | Guided Direct Access | 15.081647 |
  | GraphQL Adapters | 15.682256 |
  | Apollo Federation | 10.386152 |
  | Cosmo Federation | 10.047476 |
  | Direct Access | 20.515214 |

- **Also written:** `tables.md` also holds the sensitivity analyses and accuracy in each CSL group. `results.json` also holds the time ratios on correct runs only and the descriptive and exploratory results of plan section 10.

## The legacy load (decision B3)

`legacy3.py` ran twice at 72d39c2, on the analysis copy and the checked legacy-load copy, 03:38:10Z to 03:38:20Z and 03:38:20Z to 03:38:31Z. Both exited 0, and their outputs are byte-identical:
- `legacy-load.json`: `b268ec7d6e1bcfce84ca772d618384605eb41e37da87ca38a7873be8c0f1ee91`
- `legacy-load.md`: `1d2a19be2e212b2f335f6c8f2c24a77bd82c0e818f259ae3ba9dd8b7df08912e`

Against the scored run's own outputs, the differences are the ones ce4d042 made:
- the total with initialization is counted on the core set, with `coreRuns` and `perCoreRun` in place of `runs` and `perRun`;
- the raw arms' requests by kind are counted on the core set;
- the new keys `ambiguitySet`, `vendorErrors` and `rawArmsNote`;
- `legacy-load.md` gains the plan section 10.6 sections and the core-set heading.

`perQuestion`, `blockInitialization`, `unattributed`, `nearBoundary` and `notCountable` are unchanged. As `legacy-load.json` writes them, the total counts 214 core runs in each of the five arms, and no core run failed at the vendor twice. The ambiguity set has 12 runs in each arm.

## What is committed (decision B1)

- `study/evidence/study-3/scores.csv` and `manifest.json`: byte copies of the run folder's files.
- `results.json`, `tables.md` and `figures/effort.svg`: the analysis output at 72d39c2.
- `legacy-load.json` and `legacy-load.md`: the legacy-load output at 72d39c2.
- `checksums.json`: the archive, sums-file, bundle, evidence and output digests, with the analysis commit and the plan hash.
- Two rows of the project's artifact classification table, classed as record: `study/evidence/study-3/*.md` and `study/evidence/study-3/figures/*.svg`. Without them three of the files had no row and could not enter a checkpoint. The lead developer chose to add them in this transaction, as study 2 did.
- A `.gitattributes` rule, `whitespace=-blank-at-eof`, for `study/evidence/study-3/tables.md`. The file ends with a blank line as `analyze3.py` wrote it, so the rule lets the commit's whitespace check pass with the file kept byte for byte.
- The rows for these files in the evidence README, and the run's row in its raw-data table.

The raw run folder, the archives and the analysis copies stay outside the repository. `PLAN.md` and every frozen file are unchanged.
