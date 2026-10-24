# The Missions adapter's service stage runs against the real Oracle service on release 1.2

Date: 2026-10-20T03:25Z
Subject: Committed the move of the Missions adapter's service stage against the real Missions service on Oracle 18c from dataset release 1.0 to release 1.2, ran it once, and corrected the stale limitations text of the federation adapter profile
Status: Historical / non-normative
Lab checkpoint: lab commit `f2f76f78985a68549898507a637c177a131952c2`
Provenance: Git committer timestamp `2026-10-19T23:25:59-04:00` (2026-10-20 03:25:59 UTC), converted to the prescribed UTC minute. The lead developer accepted the Elastic License 2.0 for all federation Jobs, chose in a dialog to run only the adapter's service stage and not the whole stack on Oracle, and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.293-0325Z; originally written in the lab on 2026-10-20 (lab commit `93125dccaec20c60bb80e4b0b2431cfe73faea2d`).

## Meaningful transition

The adapter's real-Oracle stage was the one federation test still pinned to Missions dataset release 1.0, and the scale-up had not run it. It now loads release 1.2 (300 missions, the participants reclassified as P and O) into a disposable schema through the shared Missions harness and compares every mission, every paging window and every filter with the release, and it passed on the real Oracle container: 9 tests in 125.1 s. The commit is on the owned branch `tx/missions-oracle-large`, parent lab commit `513b28fd378850e44f90d2776b31755cf3f9a844`, tree `79639d9`.

## Choices recorded

- **Adapter stage only.** The lead developer chose not to also run the whole stack against the real Missions service.
- **No change to the Missions component.** The harness has no release seam, so the stage swaps the release for the length of its preparation instead of changing `uss-enterprise/missions`. Worker choice, reported.
- **Filters are paged.** With 300 missions some filters select more than one page, so the stage reads them at the adapter's largest page of 100.
- **One string in the profile file** states the stack as it is now (Missions 1.2, mapping 1.3, `personnel-v2-large-004`, both routers) and the one real-Oracle run.

## Retained evidence and limits

The run used the Oracle container that was already running and left it running. Not claimed: the whole stack against the real Missions service, Hive, benchmarking. Two stale remarks remain outside this scope: the Javadoc of `MissionsAdapterTest` and the docstring of `run_adapter_gate.py`.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
