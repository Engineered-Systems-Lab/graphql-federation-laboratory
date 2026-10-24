# The Personnel adapter reads each snapshot once instead of calling once per person

Date: 2026-10-19T19:06Z
Subject: Committed the Personnel adapter's snapshot cache, which reads each immutable Personnel v2 snapshot once through the list operation, keyed by datasetVersion, and serves the entity lookups of the routers from memory after one probe per batch, the fix the lead developer chose for the 5 s subgraph timeout that pages of 100 missions hit on the large data
Status: Historical / non-normative
Lab checkpoint: lab commit `32279dc6bb407a9b8a0d8be5f6e13f5d92a015d4`
Provenance: Git committer timestamp `2026-10-19T15:06:52-04:00` (2026-10-19 19:06:52 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's decision (their choice of options A and C is recorded verbatim in the Job `personnel_adapter_cache`, with the finding and the options in the Job `enterprise_scale_up`) or this later record preparation. The lead developer accepted the Elastic License 2.0 of Rover's composition plugin for this Job in a dialog and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.292-1906Z; originally written in the lab on 2026-10-19 (lab commit `81b759eecc0726994958788a7dc1b49e2c5f948e`).

## Meaningful transition

The re-derivation of the federation acceptance expectations on the large data stopped at the routers' 5 s subgraph timeout: a page of 100 missions with commanders and crews holds 750 to 1,250 references, the Personnel adapter made one SOAP call per person, and cold pages timed out (the figures are in the Job `scale_up_rederive`). The lead developer kept the 5 s value and chose a change to the adapter. The adapter now reads each immutable snapshot once, in pages of 100 through the list operation (ten calls for `personnel-v2-large-004`), and answers every `PersonnelReference` and `Personnel` lookup of a version from memory. The commit is on the owned branch `tx/personnel-adapter-cache`, parent lab commit `b2a9409a182a2033836860ddb0204a716dcfca72`, tree `8a56d7a`, 9 paths, +523/-44. Exact subject: **Make the Personnel adapter read each immutable snapshot once by pages and serve entity lookups from memory**.

## Choices recorded

- **The probe keeps outages honest.** A copy is never served without a list call (offset 0, limit 1) that has just succeeded. It runs once per `_entities` batch, lazily, so a batch that looks nothing up sends nothing. It proves the service answers and names the version it serves. A failed probe or page is UNAVAILABLE with the code the failed call had before and one errors entry per reference or entity. This was the Coordinator's proposal in the Job; the shared suite's outage cases and the service gate's `unavailable`, `slow` and stopped cases pass unchanged.
- **A new version empties the copy.** The read takes every page at offset 0 upward and requires one `datasetVersion` and one count across them; when the version changes between pages it starts over, three restarts at most, then UNAVAILABLE with `SERVICE_UNAVAILABLE`. Batches that need the read at once wait for one read. A failed read leaves no copy. One snapshot is kept at a time.
- **Worker choices, reported.** The three-restart limit and its code are the worker's. An id the contract cannot hold (anything but `PRS-0001` to `PRS-9999`) is sent to the service and refused there, as before, never looked up in the copy, so the decided outcome for such an id does not change. `Query.personnel` and `Query.personnelMembers` stay one call each. No read happens at start-up: a background call would race the adapter's own tests, and the measurement below shows the cold first page without it.
- **One behaviour change.** An outage is now per batch, not per person: a service that failed some `get` calls and not others used to fail only those people. Whole-service outages answer as before.

## Retained evidence and limits

The seal ran the 12 checks of the federation profile, all passed, the Apollo gate with the lead developer's ELv2 acceptance for this Job. Before the seal the worker ran the adapter's unit and integration stage (59 tests, 49 in the adapter test class, 11 of them new) and the Personnel service gate (9 tests, one new: the whole large snapshot read in ten pages through the real service, four people and one absent id resolved, a second batch identical).

Measured on the worker's own stacks from the worktree, with the large data (Personnel `personnel-v2-large-004`, Missions release 1.1, mapping release 1.2 asked), one page of 100 missions with assets, commanding officer and crew with each record, the three pages at offsets 0, 100 and 200, four rounds right after the stack was ready, on this Windows desktop with Docker Desktop and the provisional container limits:

| Router | Run | Cold first rounds | After four rounds |
| --- | --- | --- | --- |
| Cosmo | before | 5.1 to 7.7 s, 2 errors entries per page (subgraph timeouts) | 1.3 to 2.7 s |
| Cosmo | after | first page 3.6 s, then 0.5 to 0.7 s, no errors entry | about 0.5 s |
| Apollo | before | 5.1 to 7.0 s, 490 to 936 errors entries per page | 1.7 to 3.8 s |
| Apollo | after | first page 4.2 s, then 0.5 to 0.9 s, no errors entry | about 0.5 s |

The 24 pages after the change resolved the same references as the warm pages before (offset 0: 1,185 RESOLVED, 66 UNMAPPED, 7 UNRESOLVED; offset 100: 729, 19, 2; offset 200: 939, 23, 3). The first page of a cold stack is still the slow one, 3.6 s and 4.2 s: it holds the snapshot read (about 0.3 s against the real service in the gate) and the first requests of cold JVMs; Apollo's margin below 5 s is about 0.8 s. The gates of the stack and the expected outcomes of the acceptance suite still describe the earlier data; re-deriving them is the Job `scale_up_rederive`'s. Not claimed: a benchmark, a human acceptance, a warm-up, or a figure from another machine.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
