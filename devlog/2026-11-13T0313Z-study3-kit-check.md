# Study 2's kit runs live again before study 3: every arm answers as in study 2, and a dry run of the whole schedule completes

Date: 2026-11-13T03:13Z
Subject: The Job `study3_kit_check` ran study 2's study kit live with no vendor call, on the code at commit `00fd580fd4759828a8ff68007178f9227c513e03`: Oracle and the real Missions service on study 2's fingerprint, a new image build, every pool question's reference solution in all five arms with the three outages, and one dry run of study 2's block schedule with the fake vendor client
Status: Historical / non-normative
Provenance: Written on 2026-11-13 (UTC) by the worker session of the Job (Anthropic Claude Code [Claude Opus 5.5], started by the Migration Coordinator), from the worker's own step logs, the kit's outputs and the reference and harness reports, which stay machine-local outside the repository (decisions K1 and K4 of the Job). The date is the end of the dry run's last block, the Job's last live step, read from the run's block log; the bundle was written about a minute later. Study 2's figures are read from its machine-local step-7 reference reports and its committed design, read only. Every go named below was the lead developer's word, typed in the worker session. The entry names tasks by count only; no task differs from study 2, so none is named.

## What ran

The Job's scope was decided before it started (decisions K1 to K6): one devlog entry with the reports kept outside the repository, all five arms, a task that fails answerability recorded and the run carried on, the results in one machine-local folder, every stack down and Oracle and the Missions service stopped again at the end, and the removal of the lead developer's exited stub-stack containers by the first real-mode start. No vendor was called and no API key was read: the harness launcher was never run, and the dry run used the runner's fake client directly. Oracle was neither reset nor reloaded nor provisioned, and the kit was not changed.

## Oracle, the data and the images

- **Start.** Oracle's container `starfleet-missions-data-20261009` was started with `docker start` at 2026-11-11T23:45:16Z and was healthy at 23:45:47Z; the Missions service container `starfleet-missions-service` was started the same way, as the lead developer chose, and answered 200 at 23:46:00Z. Both had been found exited.
- **Fingerprint.** `missions-db:8aae139eea3d5ad9ff764bc15502c804ccae4f94b9504b687a163a6d0bf76dd1`, the same as study 2's. Dataset version 1.2; the counts were 300 missions, 973 changes, 596 assigned assets, 2121 assigned crew, 356 participants and one clock row. The Oracle session read `oracle-instance:2026-11-11T23:45:27`; study 2's was `oracle-instance:2026-11-01T14:06:31`, as a new start of the same instance gives.
- **Images.** `launch.py build` passed and wrote its pin set at 2026-11-11T23:46:22Z. The six images the stack builds got new ids, as a new build gives: assets-service 1.0.0 `2fe0992`, personnel-service 2.0.0 `a78a710`, missions-adapter 1.1.0 `aadba89`, personnel-adapter 1.0.0 `38beddf`, assets-adapter 1.1.1 `b176479` and mapping-adapter 1.0.0 `6af003c`. The Missions service image, read and never built, is unchanged: missions-service 1.0.0 `01baf41`.
- **Config.** `make_config.py` wrote the study config from study 2's scored-run plan (its schedule, seed, models, warm-up passes and frozen limits), with a dollar ceiling per vendor and no `tokens` key, as the budget rule asks. `make_config` in the real mode needs the build's pin set, so the config was written after the build.

## Answerability in the five arms

Each arm had one go and ran one script: the arm's `launch.py up` in the real mode, its MCP server, `run_reference.py --set all`, then for each of Missions, Assets and Personnel a service stop, `run_reference.py --set all --outage`, a service start and `--check-services`, and last `launch.py down`. The runs ended between 2026-11-12T16:24Z (alpha) and 2026-11-13T02:08Z (epsilon).

| Run | Each of alpha, beta, gamma, delta and epsilon | Study 2 | Pool tasks run, all correct |
| --- | --- | --- | --- |
| All sets | 75 correct, 15 skipped | the same | 62 |
| Missions outage | 4 correct, 11 skipped | the same | 4 |
| Assets outage | 6 correct, 9 skipped | the same | 5 |
| Personnel outage | 5 correct, 10 skipped | the same | 5 |

Compared with study 2's step-7 reports by task id, no task's outcome and no task's hashes differ in any arm or run, the inputs are equal, no report lists a problem and every report is verified on the fingerprint above. `--check-services` found all three services up after every outage. No task failed, so there was no failure to give a cause for. The provenance comparison left out two fields that a new start changes, and both differ in all 20 reports: the Oracle session in the dataset fingerprint, given above, and the observation fingerprint; the Missions data fingerprint itself is the same. Beyond those two, the one provenance field that differs is the list of containers in the stack project: study 2's reports also list containers left from other arms' starts (the Cosmo router and `missions-stub` in four arms, the Apollo router and `missions-stub` in epsilon), and these list each arm's own containers only, as the kit's clean-project start (decision Q12 of study 2's preflight) makes.

## The dry run

With every stack down, `runner.py --dry-run` ran study 2's whole block schedule (williams-4-half, beta, gamma, delta and epsilon with alpha as the reference), run id `study3-kit-check-dry1`. In its block log the first block started at 2026-11-13T02:28:08Z and the last ended at 03:13:28Z, the time this entry is dated by; the runner then took the last stack down and wrote the bundle, with status `complete`, at 03:14:35Z, and exited 0. The harness started and stopped each stack and MCP server itself from the config. All 17 blocks started and ended at attempt 1 (alpha once, the four arms four times each), with no refusal; every block start read the fingerprint above and the same Oracle session. The 540 runs all ended `format_error`, the fake client's empty answers. The budget ledgers price the fake token counts at 0.0189 dollars per vendor; nothing was spent. Bundle checksum: `93d1a08475c5eb529ba9c3a708b9abf145d4d3b05b020a8eb1699f8084c02357`. A single-scenario scheduled dry run, as first considered, was not possible: the schedule always needs all five arms.

## What went wrong, and the fixes

- **A probe that never returned.** The first alpha go hung from 2026-11-12T01:14:46Z before its first reference run: the worker's script waited for the MCP server with a `curl` GET on its `/mcp` endpoint and no time limit, and that endpoint keeps the stream open. The Coordinator found it at 14:25Z, read only.
- **A stop that went further than the go.** On the lead developer's go to stop it, stopping the background task did not end the script's shell. When the stuck `curl` was killed, the script carried on: its reference run failed against the MCP server killed with it (exit 1), and the script went on to its own Missions service stop at 14:28:37Z before its shell was killed. The worker halted and reported; the lead developer's next go started the service again with the kit's own `service start`.
- **Three changes to the worker's own script**, machine-local and outside the kit, under that go: a POST probe with `--max-time 5`; an exit trap that stops the MCP server whenever the script ends; and a stop when a reference run writes no report, so that a crashed run stops the arm instead of carrying on into the outages, while a task that fails answerability still writes its report and the run goes on. The two last were the lead developer's. A run is now stopped by killing the script's own shell and what it started, not by stopping the background task.
- **A refused start.** The rerun's `launch.py up` refused because the first go's alpha stack still held the router port 8170; on a further go, `launch.py down alpha` freed it and the rerun passed. The partial files of the two failed attempts were kept beside the results.
- **The project's own network.** The kit's real-mode `down`, and the removal before every real-mode `up`, remove and make again the stack project's default network `starfleet-federation-stack_default`, as `study/launch/README.md` documents. The Job's rules forbid removing a network; the worker read this documented kit step as inside the approved goes and flagged it to the Coordinator. Oracle's and the Missions service's networks were untouched, and no image or volume was removed.

## State left behind

At 2026-11-13T03:43Z no container of the stack project was left, no study process was running, and the Missions service and Oracle were stopped again with `docker stop` (Oracle with a 600-second timeout, as study 2 stopped it), both exited as they were found. The image pin set, the config, the reports and the dry run's bundle stay in the Job's machine-local folder.

## What was not covered

No vendor model was called, so the kit's paid path and the vendor request shapes were not exercised. The dry run checks the schedule, the stack starts, the provenance and the budget arithmetic with empty answers only. It went through the scoring path with the fake submissions, which scored 540 `format_error` outcomes at zero, and gives no evidence of model accuracy. The comparison with study 2 covers the reference solutions, not agent behaviour. The kit, the corpus and the frozen files are unchanged.
