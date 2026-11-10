# The whole stack can run with the real Missions service, chosen by MISSIONS_BACKEND

Date: 2026-11-10T03:41Z
Subject: Committed the switch `MISSIONS_BACKEND=stub|real` of `federation/stack/start.sh`, whose default `stub` keeps the script's commands and output, and whose `real` mode joins the Missions adapter to the operator's Missions service on Oracle through a stack-owned overlay and refuses before starting anything when that service is not up; with the review finding fixed before the go, the seals and moves of main on the way, and the checks of the seal
Status: Historical / non-normative
Provenance: Written on 2026-11-10 (UTC) in the same mission by the worker that made the change in the Job stack_missions_real, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit (read from the sealed packet's check evidence), the notes in the Job's record, and the worker's own runs before the seal, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-11-09T22:41:09-05:00`, 2026-11-10 03:41:09 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `817a9268e1fc436cc4f404ad3d195a96699bbb0c`

## The transition

Before this commit the whole stack of `federation/stack/start.sh` always ran the Missions adapter against `missions-stub`; the real Missions service on Oracle could only be reached by the study launch kit's own overlay or by setting `MISSIONS_SERVICE_URL` by hand. The commit adds one switch to the script:

- `MISSIONS_BACKEND=stub` (the default, also when unset) runs exactly what ran before: the same compose calls and the same printed output.
- `MISSIONS_BACKEND=real` adds `federation/stack/missions-real.compose.yaml` to every compose call of `start`, `stop` and `status` and starts the backends without `missions-stub`. The overlay points the adapter at `http://starfleet-missions-service:8083` on that service's bridge network `starfleet-missions_default` (external, so it is never created here) and resets the adapter's dependency on the stub with `!reset`. It is the stack's own copy; the study kit keeps its own and neither reads the other.
- A real start checks, after the existing port and license checks and before anything starts, that the container `starfleet-missions-service` runs, that the network exists, that Docker Compose is 2.24.4 or later (for `!reset`), and that `http://127.0.0.1:8083/missions?pageSize=1` answers 200; any failure prints one line and exits. The checks are read-only: the script never starts, stops, creates, resets or removes Oracle or the Missions service.
- Any other value exits 2, and the usage text names the switch.

`federation/stack/README.md` describes both modes, the operator's steps that come before a real start (Oracle, then the service, then a curl that prints 200), how to switch modes, and one example query; `federation/routers/apollo/README.md` now points its real-service mode to that section. The Apollo router's offline packaging test gained dry-run tests of the real mode with a fake Docker and curl, a test that the stub mode prints what it printed before, and tests of the overlay's merged configuration.

## Reviews and stops before the commit

- The lead developer relayed one finding before the go: `federation/routers/apollo/README.md` still described the real-service mode by `MISSIONS_SERVICE_URL` alone. Its line was fixed and a new preview (`0015b062`) presented; the go was given on that preview.
- The first seal failed two dead-adapter timing tests of the Cosmo stack gate (test_06 at 2.60 s, test_06b at 2.71 s against the 4.5 s lower bound), a failure outside this change. The worker stopped and did not retry; the Job router_gate_outage_timing then changed the gates (commit `6310de133cfa6ad3feb742704f704ca0fd4f295e`, [its entry](2026-11-10T0020Z-router-gate-outage-timing-runtime-checkpoint.md)).
- Main moved to `477f10a`, and on the lead developer's word `worktree.py carry-go` carried the go there (preview `2f2abcc6`), with the same patch id; its notice named one file that both the candidate and the upstream range touched, `federation/routers/apollo/README.md`, and the merge was clean. The second prepare was refused before staging by the checkpoint tool's preparation gate, which looked for the latest runtime commit with literal pathspecs, so the glob rows of the classification table matched nothing and it took `484683b` for the latest runtime commit instead of `6310de1`. The worker recorded the defect and changed nothing in `governance/`.
- Comitas release 0.9.2 (commit `66af10e0a783707db55d8916534dd6e2bc06460d`) fixed that gate. On the lead developer's word the go was carried a second time, to main `292c1a5` (preview `1bebfce8`, tree `b2fd92c`), again with the same patch id and no shared file, and the third `prepare` run sealed; it was the second attempt charged to the go, because the refused run stopped before the go was recorded.

## What was verified

Each check is listed with its recorded result and the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool ran at the seal, every one passing):

- Staged whitespace (`git diff --cached --check`): clean, 0.1 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 24.5 s.
- Apollo router offline (`python -B federation/routers/apollo/validation/run_router_gate.py offline`): 50 tests, PASS, 155.6 s.
- Apollo router stack (`python -B federation/routers/apollo/validation/run_router_gate.py stack`): 41 tests, PASS, 324.4 s.
- Cosmo router offline (`python -B federation/routers/cosmo/validation/run_router_gate.py offline`): 40 tests, PASS, 38.0 s.
- Cosmo router stack (`python -B federation/routers/cosmo/validation/run_router_gate.py stack`): 42 tests, PASS, 342.8 s.

The Apollo offline gate grew from 39 to 50 tests with this commit; its dry-run starts cost about 10 s each on this Windows machine, where a connect to a closed loopback port takes about 2 s.

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

**The worker's own runs before the seal:** the stub mode's dry-run output of `start.sh` compared byte for byte with the script before the change in 12 combinations of command and environment, all identical; `study/launch/test_launch.py` passed with the unchanged `BACKENDS` line it pins.

## Not run or not covered

- The stack was not started in the real mode against a running Missions service on Oracle: Oracle and the service stayed stopped throughout. The real-mode start, stop, status and refusal tests ran as dry runs with a fake Docker and curl; only the overlay tests ran the real `docker compose config` to check the merged configuration. The lead developer is to start the real mode live once after landing.
- The README's operator step for a container that was only stopped (`docker start starfleet-missions-data-20261009`) is the worker's wording and was not run.
- The refusal checks were tested against fake answers only; a real Docker's messages for a missing container or network were not exercised.
- No full suite and no test beyond the checks the tool ran was run on this tree, apart from the worker's own runs before the seal, reported above as theirs.

## How it landed

The commit was approved through the early conditional approval at reach `medium`: the lead developer typed "Go" at preview `0015b062`, the go was carried twice to a moved main by `carry-go` (to previews `2f2abcc6` and `1bebfce8`), and every check passed at the seal of the third `prepare` run, the second attempt charged to the go. Because the stack script and the router tests are on the runtime continuity boundary, the commit then entered the continuity-follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up, written in the same mission.
