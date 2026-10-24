# Federation question 6 is answered in the Apollo acceptance tests

Date: 2026-10-18T02:25Z
Subject: Committed baseline question 6 (senior officers among the assigned crew, with the percentage) to the Apollo acceptance tests on the existing federation graph, with the expected outcomes written first
Status: Historical / non-normative
Lab checkpoint: lab commit `0439bcf5ead7c8aa5ce16813f8d69d5acf0176bd`
Provenance: Git committer timestamp `2026-10-17T22:25:55-04:00` (2026-10-18 02:25:55 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the decision that led to it (the lead developer's word of 2026-10-17 in the Federation thread, recorded in the Job `federation_question_6`) or this later record preparation. The lead developer typed "go" at the preview of the candidate, which the early conditional approval carried to the commit once every check passed.
Migrated from lab log SD-2026.291-0225Z; originally written in the lab on 2026-10-18 (lab commit `b8bfda7c011d77ca87003fe8aac6d1cf0d26d294`).

## Meaningful transition

Baseline question 6 is answered and tested under Apollo, and it needed no new adapter code. The earlier statement that it needed the Personnel live path was stale: the live crew path already existed (mapping release 1.1 maps all 56 crew references, which resolve through the router against the Personnel v2 snapshot `personnel-v2-small-003`). The commit is on the owned branch `tx/federation-question-6`, parent lab commit `485172ea27d134b57d304d4ca3e35b7ced03b3b0`, tree `cf3539e`, 6 paths, +222/-13. Exact subject: **Add baseline question 6 to the Apollo acceptance tests on the existing federation graph**. At the time of this record the commit is not integrated into main.

## Choices recorded

- **Expected outcomes first.** `federation/acceptance/derive_expected.py` gained a `question6` section, written to `expected-outcomes.json` from the released files and never from a run: 25 of 31 missions have one or more senior officers (rank CAPTAIN, COMMANDER or LIEUTENANT_COMMANDER read from `CrewDetails`) among the assigned crew, 80.6 percent (all missions of the release whatever their status, one decimal). Only `assignedCrewIds` count, not the commanding officer or the participants; a civilian is never senior; a reference that is not RESOLVED is never counted. The graph is unchanged: the count and the percentage are made by the test over the query result, with no aggregate field.
- **The controlled case** is ST-00000LD4O, whose only senior assigned member is C-92 (LIEUTENANT_COMMANDER). The worker read "unresolved" two ways, both tested: in release 1.0 the member is UNMAPPED (0 counted, 56 references not resolved, not a lower bound, no errors entry), and with the Personnel adapter stopped the resolution is null (0 counted, 56 references not resolved, a lower bound, `GATEWAY_TIMEOUT` entries naming `personnel`). The rounding mode "half up" is the worker's choice; 80.645... is not a tie, so no result depends on it.
- **Tests.** Three new tests in the router stack module (`test_12`, `test_13` and `test_06b`); the helper `run_with_stopped` takes an optional query and variables, and every earlier test is unchanged.
- **Stale lines corrected.** The Apollo router README (table row for question 6, the sentence under the table, the not-tested list), the personnel mapping README and `docs/FEDERATION-DESIGN.md` now say question 6 is answered and tested under Apollo. The two historical lines of the design (the migration entry and the router Job entry) were kept as written with the later context appended.
- **Found, not changed:** the `limitations` text of the federation profile in `validation/checkpoint-profiles.json` still says "acceptance questions 2 to 5". Governance is frozen, so it is left for the Coordinator.

## Retained evidence and limits

Checks of the seal, all passed (times from the retained handoff): staged whitespace (0.1 s), continuity (18.1 s), `federation-assets-offline` (54.2 s), `federation-assets-service` (66.7 s), `federation-mapping-offline` (53.5 s), `federation-missions-offline` (53.0 s), `federation-personnel-offline` (54.9 s), `federation-personnel-service` (57.7 s), `federation-router-apollo-offline` (24.1 s) and `federation-router-apollo-stack` (269.5 s, 30 tests). The worker also ran the stack gate once on the uncommitted candidate (30 tests, 288 s) before the preview.

Limits: stub-backend mode only; the real Missions service on Oracle was not run, and question 6 is not tested under Cosmo or Hive. Times are informal, from one run. No benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
