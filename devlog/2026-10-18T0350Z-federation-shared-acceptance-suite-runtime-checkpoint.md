# The federation acceptance checks become a router-neutral shared suite

Date: 2026-10-18T03:50Z
Subject: Committed the move of the federation acceptance checks (questions 2 to 6 and the controlled cases) out of the Apollo stack gate into a router-neutral suite, with the Apollo gate passing the same tests
Status: Historical / non-normative
Lab checkpoint: lab commit `c22c83319d7249231ed276f255dfdb4974f47190`
Provenance: Git committer timestamp `2026-10-17T23:50:08-04:00` (2026-10-18 03:50:08 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the decision that led to it (the lead developer's ruling of 2026-10-17 in the Federation thread to do it before Cosmo, recorded in the Job `federation_shared_acceptance_suite`) or this later record preparation. The preview was not eligible for the early conditional approval (the new README had no classification row at HEAD, so it counted as high); the lead developer's go staged and sealed it and their Approve on the sealed review committed it.
Migrated from lab log SD-2026.291-0350Z; originally written in the lab on 2026-10-18 (lab commit `6b980b1fdcba4e9392aa9d1b4a0d9f2a38ad73a2`).

## Meaningful transition

The list A acceptance checks no longer live in the Apollo router's stack gate. They are a router-neutral suite, `federation/acceptance/shared_suite.py`, that takes the router's address and its stack controls, so the Cosmo and Hive routers will run the same operation documents, variables and assertions. The refactor is behavior preserving: no new behavior and no new test case. The Apollo `stack` gate ran 30 tests before the change (292.5 s, on main lab commit `b8bfda7`), 30 on the candidate (276.2 s) and 30 inside the seal (287.9 s), with identical test ids (checked by loading both suites without Docker). The commit is on the owned branch `tx/federation-shared-acceptance-suite`, parent lab commit `b8bfda7c011d77ca87003fe8aac6d1cf0d26d294`, tree `7cfa864`, 10 paths, +717/-533. Exact subject: **Move the federation acceptance checks into a router-neutral suite that the Apollo gate runs unchanged**. At the time of this record the commit is not integrated into main.

## Choices recorded

- **Layout.** `shared_suite.py` holds the question 6 helper, the queries, `AcceptanceQuestions` (the 14 tests of Part 1) and `ControlledCases` (the 9 of Part 3) as mixins, not test cases, so nothing runs until a router module composes them with `unittest.TestCase` and the test ids stay those of that module. `graphql_client.py` holds the POST, the wait and the codes helper, moved out of the Apollo `stack_support.py`, which re-exports them. `Part2Determinism` (the composition) stays in the Apollo module.
- **The parameter.** The suite takes one `Router(url, controls, settings, facts)`. The controls (stop one compose service, restore it until healthy, restart the router) are supplied by the router's test module over its own compose project.
- **Router-specific differences are declared, never absorbed.** `RouterSettings` holds three facts: the code of the errors entry of a dead adapter (Apollo: `GATEWAY_TIMEOUT`), the `extensions` key that names the subgraph (Apollo: `service`; `None` means the router names none and the entries are matched by code and number only) and the time window of that answer (Apollo: 4.5 s to 15 s, which proves the 5 s subgraph timeout of `router.yaml` is in force). Every other assertion is shared and identical. The outage code `SERVICE_UNAVAILABLE` of question 5 stays a shared assertion; Apollo's `include_subgraph_errors` setting stays in `router.yaml`.
- **The classification table** gained one feature-needed row, `federation/acceptance/README.md`, under the lab's governance freeze; no profile command changed because the existing stack check already runs the suite. The `limitations` text of the federation profile now says "acceptance questions 2 to 6 (the router-neutral shared suite under federation/acceptance)", which resolves the finding of the question 6 record.
- **Effort accounting.** This is shared-bucket work (two buckets, Job `agent_scenarios_design`), not charged to the Cosmo build.

## Retained evidence and limits

Checks of the seal, all 14 passed (times from the retained handoff): staged whitespace (0.1 s), continuity (20.0 s), `federation-assets-offline` (59.6 s), `federation-assets-service` (67.7 s), `federation-mapping-offline` (56.5 s), `federation-missions-offline` (57.2 s), `federation-personnel-offline` (64.4 s), `federation-personnel-service` (65.2 s), `federation-router-apollo-offline` (24.4 s), `federation-router-apollo-stack` (287.9 s, 30 tests), the checkpoint selector (40.1 s), classification tests (3.7 s), checkpoint invariants (77.5 s) and commit metadata (12.6 s).

Limits: stub-backend mode only; the real Missions service on Oracle, Cosmo and Hive were not run, so the settings object has been exercised by Apollo only. Times are informal, from one run. No benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
