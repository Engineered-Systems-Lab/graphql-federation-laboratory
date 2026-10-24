# Federation question 6 gets its final rules

Date: 2026-10-18T14:45Z
Subject: Committed the two final question 6 rules (a PLANNED mission is never confirmed without a senior officer; CANCELLED missions are left out and counted beside the answer) in the shared acceptance suite, with the expected outcomes re-derived first and the suite passing under Apollo and Cosmo
Status: Historical / non-normative
Lab checkpoint: lab commit `d9f27ddcce0375d077f4e840813bf22a7375a179`
Provenance: Git committer timestamp `2026-10-18T10:45:18-04:00` (2026-10-18 14:45:18 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's rulings of 2026-10-18 (recorded verbatim in the Job `federation_design`) or this later record preparation. The lead developer typed "go" at the preview (their first reply carried extra words, did not match the approval words and was asked again) and accepted the Elastic License 2.0 for the Apollo gate; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.291-1445Z; originally written in the lab on 2026-10-18 (lab commit `118e9dfd9037dc50c6ec6406c7147cb69468aec3`).

## Meaningful transition

Question 6 now counts the way the lead developer finally ruled. A PLANNED mission is unconfirmed unless a confirmed senior officer is already assigned, because its staffing is not final; the only confirmed-without mission, ST-00000LD5G, was a PLANNED mission with one assigned member, so it is now unconfirmed. A CANCELLED mission never ran, so it is in none of the three counts and not in the percentage, and the number of cancelled missions not counted is reported beside the answer. The commit is on the owned branch `tx/20261018-q6-final-rules`, parent lab commit `cac9173184e55654aedd4d8aa12a2c32bcb18c0a`, tree `89de10d`, 8 paths, +518/-139. Exact subject: **Make federation question 6 never confirm a planned mission without a senior officer and leave cancelled missions out, in the shared suite under Apollo and Cosmo**.

## Choices recorded

- **Expected outcomes first.** `derive_expected.py` was changed and `expected-outcomes.json` derived again from the released files before the suite changed. The empty-mission rule and its options were deleted; the history stays in the federation design. Release 1.1: 27 confirmed with, 0 without, 3 unconfirmed (ST-00000LD4V, ST-00000LD57, ST-00000LD5G), 100.0 percent, 1 cancelled not counted (ST-00000LD5D). Release 1.0 and the Personnel adapter down: 0 / 0 / 30, no percentage, 1 cancelled not counted, 80 references not resolved (those of the counted missions).
- **The Job's figures were an estimate.** The Job gave 28 / 0 / 2 for release 1.1 and asked for verification. The script decides: ST-00000LD5G moves to unconfirmed and the excluded ST-00000LD5D was one of the 28 confirmed with, so 27 / 0 / 3. The design document says so.
- **Controlled cases.** 39 controlled missions (PLANNED with and without a confirmed senior, CANCELLED of every staffing, each other status by its staffing) and two more percentage cases (cancelled missions change nothing; only cancelled missions confirm nothing). They run in `test_14` and `test_15` with no stack.
- **Beyond the Job's list.** The Apollo and Cosmo READMEs quoted the old figures (28 / 1 / 2, 96.6 percent, 83 references) and were updated; the router configuration comment that called Cosmo a later Job and the design text that said question 6 was not built were corrected, as the Coordinator added to the scope.

## Retained evidence and limits

Test counts before and after, from the same runs: Apollo offline 33 and 33, Apollo stack 32 and 32, Cosmo offline 40 and 40, Cosmo stack 33 and 33 (no test was added, the question 6 tests changed). The seal ran 11 checks, all passed: staged whitespace, continuity, the four adapters' offline gates, the Assets and Personnel service gates, and the four router gates. The Apollo stack gate ran with `APOLLO_ELV2_LICENSE=accept`, which the lead developer accepted for this Job; the Cosmo gate needs no acceptance. The Cosmo-specific settings of the suite (`subgraph_in_message`, `entries_per`) were unchanged and both routers pass the same question 6 assertions.

Limits: stub-backend mode only; the real Missions service on Oracle and Hive were not run; no benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
