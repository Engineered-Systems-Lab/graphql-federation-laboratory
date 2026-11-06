# Study 2's resume, analysis, restore and deprecated assets list are fixed before the freeze

Date: 2026-11-05T23:57Z
Subject: Committed the study-2 resume check of the code a run executes, the analysis requiring the scorer's honesty checks, the restore waiting until the arm answers for the restored service, and the deprecated assets list computing its offset as a long in Assets adapter 1.1.1, verified on the second seal after the first failed the Cosmo stack gate's dead-adapter timing; with the Job's findings on the 60-second cut and on that timing
Status: Historical / non-normative
Provenance: Written on 2026-11-06 (UTC) after the commit by a fresh records worker, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit (read from the sealed packet's check evidence), the machine-local timing record of the first, withdrawn seal, and the reports of the worker who made the change in the Job study2_prerun_fixes, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-11-05T18:57:10-05:00`, 2026-11-05 23:57:10 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `484683b93cd0aa6a40adbb2c2023bb84be754410`

## The transition

Study 2's freeze hashes the harness, the scorer and the analysis, so the fixes below had to land before it. The commit makes four changes, by area as its message gives them.

- **Harness.** The run manifest records `codeFiles`, the hash of every Python file a run executes (the harness modules, the four MCP server files, the launch kit, the preflight module the fingerprint imports and the corpus scorer), and a resume refuses a file added, removed or changed, naming each; the commit stays recorded and is no longer compared. The restore of a category D task's service waits, after the health check, until the arm's ready command finds the service answering through the arm's entry point, within the same `ready_timeout_seconds`, records it as `entryPoint` on the restore's line of `health.jsonl` and treats a miss as the restore void trigger. Under a schedule every stopped service needs a ready command, and the ready commands are in the plan identity of the void rule.
- **Launch kit.** `launch.py ready <service> <scenario>` is read only: one request for the service through the router (delta, epsilon), its adapter (gamma) or the service's own published port (alpha, beta); `make_config.py` writes one ready command per outage service into every scenario.
- **Analysis.** `study/analysis2/data2.py` requires `honestyChecks` on every score, `honestyFailures` as a list of check names among them and at least one check for a judged category D answer; `analyze2.py`'s definition of honest, `simulate.py` and the test scorer follow.
- **Assets adapter.** The deprecated `assets` list computes its call offset as a long in `AssetsGraph.java`, so offsets from 2147483598 with a limit above 50 answer an empty list instead of `UPSTREAM_BAD_RESPONSE`, and the adapter goes from 1.1.0 to 1.1.1 (pom, jar, its compose image tag, the stack's image tag and the launch kit's list of built images). The lead developer decided in the worker's session that this fix goes into the Job's transaction ("Yes, fix it here").

The commit also adds tests for each change (`study/harness/test_runner.py`, `test_runner_schedule.py`, `study/launch/test_launch.py`, `study/analysis2/test_analysis2.py` and `AssetsAdapterTest.java`), the lead developer's dated addendum (2026-11-05) on the deprecated list's overflow to the [D041 page totals revision](../project-governance/DECISIONS.md#d041-page-totals-revision-2026-11-04-accepted-scope) with its rationale, and the harness, launch kit and analysis 2 READMEs, the study 2 design, the Assets adapter's README and the federation design. Its parent is `085ea25ea7609a8e10b3c63e833b9e04915d67da`, on Comitas release 0.8.0, and its tree `9aefef5`; it changed 24 files, 576 lines added and 47 removed. It follows the implementation checkpoint of [the graph page totals entry](2026-11-04T1909Z-graph-page-totals-runtime-checkpoint.md).

The worker reported where the items came from. The resume gap was found by the lead developer's GPT review and confirmed in `runner.py`. On the honesty checks the worker found that the corpus 2 scorer has returned `honestyChecks` since commit `590b516ebce6206e6e14e93cec14769e8a65c6dc` and that only the analysis did not read them; the lead developer chose the analysis side only. The worker reproduced the other two on live stacks on the lead developer's go: after `launch.py service stop` and `start` of Assets in delta, a router query that needs Assets answered `SERVICE_UNAVAILABLE` for about 6 s in two of four restores while the harness's health command had already passed; and the deprecated `assets` list answered `UPSTREAM_BAD_RESPONSE` at offset 2147483647 with limit 100, the only list of every service, adapter and graph page field that did not answer an empty page beyond its end. The worker also reported that before the seal the seven paid development runs were scored again with the committed scorer (282 scored runs) with every score identical and none refused by the new requirement.

## What was verified

Each check is listed with its recorded result and the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool ran in the second, passing seal, with every check passing):

- Staged whitespace (`git diff --cached --check`): clean, no output, 0.1 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 22.6 s.
- Assets adapter offline (`python -B federation/adapters/assets/validation/run_adapter_gate.py offline`): 14 tests, PASS, 64.9 s.
- Assets adapter service (`python -B federation/adapters/assets/validation/run_adapter_gate.py service`): 6 tests, PASS, 76.5 s.
- Apollo router stack (`python -B federation/routers/apollo/validation/run_router_gate.py stack`): 41 tests, PASS, 344.4 s.
- Cosmo router stack (`python -B federation/routers/cosmo/validation/run_router_gate.py stack`): 42 tests, PASS, 366.2 s.
- Mapping adapter offline (`python -B federation/adapters/mapping/validation/run_adapter_gate.py offline`): 130 tests, PASS, 70.6 s.
- Missions adapter offline (`python -B federation/adapters/missions/validation/run_adapter_gate.py offline`): 14 tests, PASS, 77.6 s.
- Personnel adapter offline (`python -B federation/adapters/personnel/validation/run_adapter_gate.py offline`): 14 tests, PASS, 60.6 s.
- Personnel adapter service (`python -B federation/adapters/personnel/validation/run_adapter_gate.py service`): 9 tests, PASS, 61.8 s.
- Apollo router offline (`python -B federation/routers/apollo/validation/run_router_gate.py offline`): 39 tests, PASS, 27.0 s.
- Cosmo router offline (`python -B federation/routers/cosmo/validation/run_router_gate.py offline`): 40 tests, PASS, 37.6 s.
- Continuity regressions (`python -B governance/tools/run_tests.py -s governance/tests/continuity -s governance/config -p test_*.py -v`): 332 tests, OK, 275.6 s.
- Mission Control generator (`python -B governance/tools/run_tests.py -s governance/tests/extensions/mission_control -p test_generate*.py -v`): 90 tests, OK, 110.3 s.
- Study tests (`python -B study/harness/study_gate.py`): the gate's own verdict "failed=none not_run=none" over its nine suites (harness, corpus, corpus2, mcp, analysis, analysis2, launch, preflight, blind), 545.5 s in all.

In the passing Cosmo stack gate, the outage answers with an adapter stopped took 5.02 s (Assets adapter down), 5.08 s (Personnel adapter down), 5.03 s (both) and 5.04 s (mapping adapter down, resolution selected); the answer with another subgraph beside the stopped Assets adapter took 3.0 s, and the pages of the whole list with that adapter down took 5.17, 3.01 and 5.07 s. The router's configured subgraph timeout is 5 s, and the gate's lower bound for an answer with an adapter stopped is 4.5 s. The gate holds a single timed answer to that bound and, for the paged list, only its slowest page, so the 3.01 s page sits inside a passing check; the case beside the stopped adapter is not timed against the bound.

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

## The first seal failed, and was withdrawn

The first `prepare` on the same tree, with the lead developer's go at preview `88f30ebe`, did not pass. The machine-local timing record of that run (written 2026-11-05T22:09Z) shows 14 of its 15 checks passing and the Cosmo router stack gate failing after 338.3 s. The worker reported, from that run's sealed evidence, that 3 of the gate's 42 tests failed, all outage timing assertions of the shared acceptance suite, which require an answer with an adapter stopped to take at least 4.5 s, the gate's lower bound under the router's 5 s subgraph timeout: test_04 (an adapter itself down) answered in 4.01 s, test_06 (Personnel adapter down) in 2.59 s and test_06b (question 6 paged, Personnel adapter down) in 2.73 s at its slowest page, the page the paged check holds to the bound. That run's packet was withdrawn with `abandon` on the lead developer's word, which clears it, so the test count and the three times rest on the worker's report and can no longer be checked against the packet.

The worker then ran a read-only investigation, on the lead developer's word, and the second `prepare` with the same go on the same tree passed every check. The go was used in two prepare attempts, within the tool's limit of three.

## The Job's findings outside the commit

Both findings are the study2_prerun_fixes worker's, recorded here on the lead developer's decision; nothing in the commit changes for either.

**The 60-second cut.** The worker found that every failed vendor request in the seven paid development runs was a connection error at 60.04 to 60.19 s, Claude and GPT alike and all on task V05, and that no request over 57.5 s succeeded. The harness sets no timeout, and the installed SDKs default to 600 s, so it is not a harness setting. In an idle-connection probe with no vendor and no key (one HTTPS connection to `1.1.1.1` and to `www.google.com`, reused after an idle wait), both servers reused the connection after 55 s and closed it after 65 and 90 s with NordVPN on (NordLynx as the default route), and reused it after 55, 65 and 90 s with NordVPN off. The worker's finding: the NordVPN path closes a TCP connection that carries no bytes for about 60 s, and the servers do not. Its limits, as the worker gave them: one probe each way, two servers, and the probe tests an idle connection between requests, not a request in flight; that a non-streaming vendor request the model takes more than 60 s to answer is such an idle connection is an inference, not tested. The worker reported it to the lead developer as outside the repository and proposed, as mitigations, running the scored run with the VPN off or with the vendors' hosts outside the tunnel; neither was tested on a vendor request in flight, and routing the vendors' hosts outside the tunnel was not tried.

**The Cosmo stack gate's dead-adapter timing.** The worker's investigation found that the gate stops an adapter with `docker compose stop`, so the gate's lower bound assumes that a fetch to a stopped adapter hangs until the router's 5 s timeout; an answer under 5 s means the fetch failed by itself before it. The worker first named NordVPN, off during the first seal, as the likely cause; the passing seal ran with NordVPN on and still had two early answers of about 3 s (above), so the worker corrected that: the early failure happens with the VPN on or off, is intermittent and lands on a timed single answer (test_04, test_06) by chance. In the worker's reading it is not caused by this change, which touches no file under `federation/acceptance`, `federation/routers` or the Personnel adapter; the re-run does not establish that, since the gates' stacks run the changed Assets adapter. Its limits: the cause of the early failure is not established, including whether the changed runtime contributes (the worker's guess is the bridge's address-resolution give-up time), and no container was started to test it. The worker left it as an open item for a later Job: make the dead-adapter proof independent of how a fetch to a stopped container fails, for example by pausing the container or asserting the timeout from the router's own configuration.

## Not run or not covered

- No live stack run of `launch.py ready` was made; the ready commands are covered by the offline tests above.
- The checks above built disposable images from the changed Assets adapter code. The Study 2 run images are not built or pinned on Assets adapter 1.1.1, and step 7 (the reference solutions) and the totals check in the three graph arms have not been run against those pins; they are a later rider of the Job, after integration, on the lead developer's go.
- The whole stack was not run against the real Missions service on Oracle; the router stack gates ran on disposable stacks.
- No test ran on this tree beyond the checks the tool ran, apart from the worker's own runs before the seal, reported above as theirs.
- No paid run was made, and no manual acceptance is recorded.

## How it landed

The commit was approved through the early conditional approval at reach `medium`: the lead developer typed "go" at preview `88f30ebe`, with every check passing at the second seal. Because the Assets adapter is on the runtime continuity boundary, the commit then entered the continuity-follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up, written by a fresh records worker in the same mission.
