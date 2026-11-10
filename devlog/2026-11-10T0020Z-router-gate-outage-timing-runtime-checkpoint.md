# The router stack gates time a paused adapter and keep one stopped adapter

Date: 2026-11-10T00:20Z
Subject: Committed the change that makes the routers' dead-adapter timing independent of how a fetch to a stopped container fails: the timed outage cases of the shared acceptance suite pause the adapter and keep both bounds, and the one stopped case (the mapping adapter) keeps the crash path with the upper bound only; with the diagnosis of a stopped and a paused adapter that it rests on, the review findings fixed before the seal, and the checks of the seal
Status: Historical / non-normative
Provenance: Written on 2026-11-10 (UTC) in the same mission by the worker that made the change in the Job router_gate_outage_timing, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit (read from the sealed packet's check evidence), the diagnosis recorded in the Job's record, and the worker's own runs before the seal, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-11-09T19:20:40-05:00`, 2026-11-10 00:20:40 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `6310de133cfa6ad3feb742704f704ca0fd4f295e`

## The transition

The Cosmo whole-stack gate failed now and then on changes that did not touch what it tests: 3 of 42 tests in the first seal of `study2_prerun_fixes` on 2026-11-05 (test_04 at 4.01 s, test_06 at 2.59 s, test_06b at 2.73 s, [that entry](2026-11-05T2357Z-study2-prerun-fixes-runtime-checkpoint.md)), and 2 of 42 in the first seal of `stack_missions_real` on 2026-11-09 (test_06 at 2.60 s, test_06b at 2.71 s). Each failure cost a seal of about 16 minutes. The gates made an adapter "down" with `docker compose stop` and held its answer to a window of 4.5 s to 15 s, whose lower end is meant to prove that the router waited for its 5 s subgraph timeout.

The commit makes that proof independent of how a fetch to a stopped container fails. The lead developer decided C1 to C3 on 2026-11-09 in the Coordinator session ("make the fix, then we finish that"): both kinds of down, each proving what it can; a short diagnosis first; this Job before `stack_missions_real`.

- **Shared acceptance suite** (`federation/acceptance/shared_suite.py`). `Controls` gains `pause`, and `restore` returns a paused or a stopped service to health. test_04, test_06, test_06b and test_07 pause the adapter (the helper `run_with_stopped` becomes `run_with_unresponsive`) and keep both bounds. test_05, the mapping adapter, is the one stopped case: its answer with `resolution` selected is held to the upper bound only (`adapter_dead_answer_time`), must carry an errors entry whose code is the router's strict one or one it declares for a fetch that fails at once, and must keep the mission and the references, with `resolution` null when it is selected. The docstrings say what unresponsive and dead mean and which bound each proves.
- **Routers** (both `test_stack.py`). `pause` is `docker compose pause`. `restore` unpauses a paused service and waits until Docker reports it healthy again (deadline 120 s), or starts a stopped one and waits with `up --wait` as before. The settings comments say how each kind answers, and Apollo's `SUBREQUEST_HTTP_ERROR` is declared for lists and for the stopped case.
- **Docs.** A dated section on unresponsive and dead adapters in each router's README (the earlier tables, measured with stopped adapters, stay as written), and the statement of the rule in `federation/acceptance/README.md`, added to the scope by the lead developer ("Yes, it should for consistency", relayed by the Coordinator on 2026-11-09).

The routers' configurations and timeouts, the adapters, `compose.yaml`, `start.sh`, `expected-outcomes.json`, every non-outage case, Cosmo's Part 4 and every frozen file are unchanged. Its parent is `48f05221e056be810d6c90a7baceef7a41e2e566`, on Comitas release 0.9.1, and its tree `5b50099`; it changed 6 files, 172 lines added and 36 removed. It follows the implementation checkpoint of [the study 2 pre-run fixes](2026-11-05T2357Z-study2-prerun-fixes-runtime-checkpoint.md).

## The diagnosis

The worker measured, on 2026-11-09 from 21:45 to 21:50 UTC, in one disposable compose project of the stack (`fed-diag-8d8bfd2c430c`, made with the Cosmo gate's own stack class, ephemeral loopback ports, both routers in it, removed afterwards), what a fetch to the Personnel adapter does from inside each router's network namespace: name resolution, a TCP connect and one HTTP request, five rounds per state, with both routers' answers to the suite's crew-and-assets query. NordVPN was off; the lead developer's stack was running and was not touched.

- **Stopped** (`docker compose stop`): the adapter's name failed to resolve after 2.50 to 2.56 s, every time. The Cosmo router answered in 2.52 to 2.60 s, 5 of 5 under the 4.5 s bound: the times of the failed seals. The Apollo router answered with `GATEWAY_TIMEOUT` at 5.02 to 5.05 s four times, and once at 3.09 s with `SUBREQUEST_HTTP_ERROR` "tcp connect error".
- **Paused** (`docker compose pause`): the name resolved in about 0.01 s to the same address, the connection was accepted, and the HTTP request got no answer within the probe's 10 s. Both routers answered at 5.02 to 5.05 s, 10 of 10. After the unpause both answered at once with no router restart.

The worker's reading: the early answer is the time the network's name resolution takes to give up on a removed container, independent of the VPN. Why earlier Cosmo seals sometimes waited the full 5 s with the adapter stopped is not established. This closes the open item that [the 2026-11-05 entry](2026-11-05T2357Z-study2-prerun-fixes-runtime-checkpoint.md) left for a later Job.

## Reviews before the seal

The lead developer relayed two reviews in the worker's session before the go, and each led to a new preview; no go was given on the earlier ones.

- The first (of tree `037c41b`) found that test_05 did not look at `data`, so an answer with `data: null` could pass; that a failed second pause in the paired case left the first adapter paused with no restore; and that `federation/acceptance/README.md` still stated the old rule. All three were fixed in tree `b17da95`.
- The second (of tree `b17da95`) found that both stack gates errored in test_06, test_06b and test_07: Docker marks a paused container unhealthy, and `docker compose up -d --wait` run right after the unpause failed at once with "is unhealthy". The restore now waits for the health check to recover. The worker then ran both stack gates on the fixed tree before the preview (Cosmo 42 tests OK, Apollo 41 tests OK); its Apollo offline gate failed one test there because the lead developer's stack held port 8182, and the lead developer stopped that stack for the seal.

## What was verified

Each check is listed with its recorded result and the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool ran at the seal, every one passing):

- Staged whitespace (`git diff --cached --check`): clean, 0.1 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 26.6 s.
- Apollo router offline (`python -B federation/routers/apollo/validation/run_router_gate.py offline`): 39 tests, PASS, 27.5 s.
- Apollo router stack (`python -B federation/routers/apollo/validation/run_router_gate.py stack`): 41 tests, PASS, 315.4 s.
- Cosmo router offline (`python -B federation/routers/cosmo/validation/run_router_gate.py offline`): 40 tests, PASS, 38.4 s.
- Cosmo router stack (`python -B federation/routers/cosmo/validation/run_router_gate.py stack`): 42 tests, PASS, 346.3 s.

The timed outage answers of the two stack gates at the seal, in seconds (every case paused except test_05):

| Case | Cosmo | Apollo |
| --- | --- | --- |
| test_04, one answer (Assets adapter) | 5.03 | 5.02 |
| test_04, another subgraph beside it (not timed) | 5.13 | 5.02 |
| test_04, the whole list, three pages | 5.05, 5.05, 5.05 (3 entries) | 5.06, 5.07, 5.04 (596 entries) |
| test_05, stopped mapping adapter, key fields only | 0.03 | 0.02 |
| test_05, stopped mapping adapter, `resolution` selected | 5.02 (no code) | 5.03 (`GATEWAY_TIMEOUT`) |
| test_06, Personnel adapter | 5.04 | 5.06 |
| test_06b, question 6 paged | 5.17, 5.10, 5.07 | 5.24, 5.09, 5.10 |
| test_07, both adapters | 5.03 | 5.02 |

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

## Not run or not covered

- In the seal the stopped mapping adapter waited for the timeout under both routers; the early failure of a stopped adapter is covered by the diagnosis above, not by a gate run.
- The paused lists keep the allowance for a page that answers early and for Apollo's `SUBREQUEST_HTTP_ERROR`; making them strict was left out of scope.
- The whole stack was not run against the real Missions service on Oracle; the router stack gates ran on disposable stacks.
- No full suite and no test beyond the checks the tool ran was run on this tree, apart from the worker's own runs before the seal, reported above as theirs.

## How it landed

The commit was approved through the early conditional approval at reach `medium`: the lead developer selected "go" at preview `5ca3c638`, with every check passing at the first seal. Because the router stack tests are on the runtime continuity boundary, the commit then entered the continuity-follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up, written in the same mission.
