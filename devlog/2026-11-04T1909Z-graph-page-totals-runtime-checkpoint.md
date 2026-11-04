# The graph's Missions and Assets lists get page fields with the services' totals

Date: 2026-11-04T19:09Z
Subject: Committed `missionsPage` and `assetsPage` with the services' totals beside the graph's `missions` and `assets` lists, which are deprecated, raised the two adapters to 1.1.0, recomposed both routers, added the study's totals check and recorded the D041 page totals revision, verified by the router and adapter gates on disposable stacks
Status: Historical / non-normative
Provenance: Written on 2026-11-04 (UTC) after the commit by a fresh records worker, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit (read from the sealed packet's check evidence) and the report of the worker who made the change in the Job study2_graph_totals, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-11-04T14:09:04-05:00`, 2026-11-04 19:09:04 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `eb196ce59540d8e619618277132553276f8b1527`

## The transition

Before this commit the graph's `missions` and `assets` lists returned a window of items and no total, so a client could not tell from one answer how many records matched.

The commit adds `missionsPage` to the Missions adapter and `assetsPage` to the Assets adapter, with the lists' filters, offset and limit, returning `MissionPage` and `AssetPage` (`items`, `totalCount`, `offset`, `limit`, `hasMore`). The items come from the same backend calls as the list's; the total is read from the service's own count. The page fields check the count metadata of every call and refuse metadata they cannot use as `UPSTREAM_BAD_RESPONSE`. The two lists are marked `@deprecated` with a reason naming the page field and answer exactly as in 1.0.0, so a default introspection shows only the page fields while existing queries still work. Both adapters go from 1.0.0 to 1.1.0, the Apollo supergraph and the Cosmo execution config are recomposed from their schemas, and the stack's compose file and the launch kit's image list name the 1.1.0 tags. The commit also adds `study/preflight/totals_check.py`, the graph-arm check that every total equals the paged count through the arm's own tool, with its offline tests, and records the [D041 page totals revision](../project-governance/DECISIONS.md#d041-page-totals-revision-2026-11-04-accepted-scope) with its rationale, the federation design, the adapters' READMEs, the preflight README and the study 2 design. Its parent is `abc3abc099dbd5c3862c4716166a5fec5ac71f65`, on Comitas release 0.8.0, and its tree `dd31577`; it changed 29 files, 1,419 lines added and 59 removed. It follows the implementation checkpoint of [the Missions memory limit entry](2026-10-28T0140Z-missions-memory-limit-runtime-checkpoint.md).

The worker who made the change reported that development failures of study 2 motivated it: in the second failure of the calculation tool's declared check ([its entry](2026-11-04T1456Z-study2-calculation-tool-v2-fails-its-check.md)), two answers to a task that needs all 300 missions counted only 200 of them, in GraphQL Adapters and in Cosmo Federation. It reported that it presented the API first and revised it after a ChatGPT Codex review that the lead developer passed on, and that before the final preview it fixed three P2 issues from a second review: an `assetsPage` offset that overflowed at the largest offset, a JSON null body that became `INTERNAL_SERVER_ERROR`, and unbounded loops in `study/preflight/totals_check.py`. It also reported that before the seal it ran the Apollo stack gate, which passed 40 of 41 tests, the one failure a field-order assertion of its own new `test_20` that it then fixed, and the Cosmo stack gate, which passed 42 of 42.

## What was verified

Each check is listed with its recorded result and the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool ran, with every check passing at the seal):

- Staged whitespace (`git diff --cached --check`): clean, no output, 0.1 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 22.9 s.
- Apollo router offline (`python -B federation/routers/apollo/validation/run_router_gate.py offline`): 39 tests, PASS, 27.6 s.
- Apollo router stack (`python -B federation/routers/apollo/validation/run_router_gate.py stack`): 41 tests, PASS, 393.8 s.
- Cosmo router offline (`python -B federation/routers/cosmo/validation/run_router_gate.py offline`): 40 tests, PASS, 37.7 s.
- Cosmo router stack (`python -B federation/routers/cosmo/validation/run_router_gate.py stack`): 42 tests, PASS, 366.8 s.
- Assets adapter offline (`python -B federation/adapters/assets/validation/run_adapter_gate.py offline`): 14 tests, PASS, 65.1 s.
- Assets adapter service (`python -B federation/adapters/assets/validation/run_adapter_gate.py service`): 6 tests, PASS, 76.1 s.
- Mapping adapter offline (`python -B federation/adapters/mapping/validation/run_adapter_gate.py offline`): 130 tests, PASS, 72.9 s.
- Missions adapter offline (`python -B federation/adapters/missions/validation/run_adapter_gate.py offline`): 14 tests, PASS, 79.6 s.
- Personnel adapter offline (`python -B federation/adapters/personnel/validation/run_adapter_gate.py offline`): 14 tests, PASS, 64.0 s.
- Personnel adapter service (`python -B federation/adapters/personnel/validation/run_adapter_gate.py service`): 9 tests, PASS, 65.1 s.
- Continuity regressions (`python -B governance/tools/run_tests.py -s governance/tests/continuity -s governance/config -p test_*.py -v`): 332 tests, OK, 302.8 s.
- Mission Control generator (`python -B governance/tools/run_tests.py -s governance/tests/extensions/mission_control -p test_generate*.py -v`): 90 tests, OK, 126.6 s.
- Study tests (`python -B study/harness/study_gate.py`): the gate's own verdict "failed=none not_run=none" over its nine suites (harness, corpus, corpus2, mcp, analysis, analysis2, launch, preflight, blind), 481.1 s in all.

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

## Not run or not covered

- The whole stack was not run against the real Missions service on Oracle; the router stack gates ran on disposable stacks.
- The Missions adapter's service stage against Oracle was not run; only its offline gate ran.
- No study stack was started, no step 7 run and no run of the totals check against a stack was made, and no paid run was made. The worker reported that these belong to the Job's later evidence transaction.
- No test ran on this tree beyond the checks the tool ran.
- No manual acceptance is recorded.

## How it landed

The commit was approved through the early conditional approval at reach `medium`: the lead developer typed "approve" at preview `300a357d`, with every check passing at the seal, on the first prepare attempt. Because the adapters, the routers' composition and the stack's compose file are on the runtime continuity boundary, the commit then entered the continuity-follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up, written by a fresh records worker in the same mission.
