# The Missions service container gets a 768 MiB memory limit and a Java heap cap

Date: 2026-10-28T01:40Z
Subject: Committed a memory limit of 768 MiB and a Java heap cap of 60 percent of it for the Missions service in its compose file, with one sentence in the Missions README, verified by the Missions gates against the reviewed Oracle container
Status: Historical / non-normative
Provenance: Written on 2026-10-28 (UTC) after the commit by a fresh records worker, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit (read from the sealed packet in the mission's checkpoint store) and the report that the worker who made the change kept in its Job notes, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-10-27T21:40:57-04:00`, 2026-10-28 01:40:57 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `b18c1af4cb532548989dd0247855b236bc6ce649`

## The transition

Before this commit `uss-enterprise/missions/compose.yaml` started the service `missions` with no memory limit. The memory plan of [the study 2 design](../docs/STUDY-2-DESIGN.md#the-backend-the-real-missions-service-on-oracle) proposed 768 MiB with a heap cap for it, inside a total of about 8.2 GiB of limits; that plan is on paper, from documented limits and recorded machine facts, and measured nothing.

The commit adds `mem_limit: 768m` to the `missions` service and `JAVA_TOOL_OPTIONS: -XX:MaxRAMPercentage=60.0` to its environment, so the JVM caps its heap at 60 percent of the limit, about 460 MiB. One sentence in the Packaging and deployment section of `uss-enterprise/missions/README.md` says so. The Dockerfile is unchanged. Its parent is `2fb391c2e3ba609291ccb3bb2a046db574b3e132`, on Comitas release 0.7.0, and its tree `0b34e2b`; it changed 2 files, 4 lines added and 1 removed. It follows the implementation checkpoint of [the in-memory Assets database entry](2026-10-26T1706Z-stack-assets-database-in-memory-runtime-checkpoint.md).

The worker who made the change proposed the 60 percent cap in its preview. It reported that the lead developer asked what 800 MiB would change, was told that it differs from the approved 768 MiB of the design page with no technical gain, and kept 768 MiB.

## What was verified

Each check is listed with its recorded result and the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool selected for the profile `missions-packaging`, which no impact mapping narrows, so its whole envelope ran; all ran fresh on 2026-10-27 and exited 0):

- Staged whitespace (`git diff --cached --check`): clean, 0.3 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 58.0 s. The tool flagged it slower than its mean of 14.3 s over 20 runs.
- Missions offline (`python -B uss-enterprise/missions/validation/validate.py`): PASS, 0.5 s.
- Missions data (`python -B uss-enterprise/missions/validation/missions_runtime.py data`): 34 tests, PASS, 433.2 s.
- Missions service (`python -B uss-enterprise/missions/validation/missions_runtime.py service`): 33 tests, PASS, 159.1 s.
- Missions packaging (`python -B uss-enterprise/missions/validation/missions_runtime.py packaging`): 5 tests, PASS, 33.9 s. This gate builds the image from the committed files and starts the service through this compose file on the Oracle network, so the service started and answered with the limit and the cap in place.

The data, service and packaging gates ran against the Oracle container `starfleet-missions-data-20261009` as it was. The worker reported that it was healthy before the seal and that the worker did not provision, reset or stop it and read no credential.

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

## Not run or not covered

- No preflight step of study 2 was run.
- No memory was measured: no gate reads the container's memory, its limit or the JVM heap, and no `docker stats` reading was taken. The 768 MiB and the 60 percent cap remain planning figures until preflight steps 4 and 5 of [the study 2 design](../docs/STUDY-2-DESIGN.md#preflight-steps) measure the service and the whole stack.
- No test ran beyond the checks the tool selected.
- No manual acceptance is recorded.

## How it landed

The commit was approved through the early conditional approval at reach `medium`: the lead developer's go at preview `ee7d8188`, with every check passing at the seal, on the first prepare attempt. Because the compose file is on the runtime continuity boundary, the commit then entered the continuity-follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up, written by a fresh records worker in the same mission.
