# Missions release 1.1 publishes 300 missions

Date: 2026-10-19T12:58Z
Subject: Committed Missions dataset release 1.1, 300 missions appended to release 1.0 (31 carried unchanged, 57 new curated canon missions from TNG Seasons 4 and 5, 45 generated maintenance missions and 167 generated routine missions), the second step of the data scale-up
Status: Historical / non-normative
Lab checkpoint: lab commit `b86c765001d443af94a60c53950ec53e547e59c8`
Provenance: Git committer timestamp `2026-10-19T08:58:09-04:00` (2026-10-19 12:58:09 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's words of 2026-10-18 and 2026-10-19 (recorded verbatim in the Jobs `enterprise_scale_up` and `missions_large_release`) or this later record preparation. The lead developer selected "go" at the third preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.292-1258Z; originally written in the lab on 2026-10-19 (lab commit `325d47493ea8f8d75818d377910877313dc9c3cf`).

## Meaningful transition

The lab now has a Missions release big enough to need paging and to show differences between approaches: 300 missions (six pages of 50) and 865 change entries (eighteen pages). Release 1.1 appends to release 1.0, which is untouched: its 31 missions and 101 change entries keep their ids and bytes, and the new missions and entries get ids after them (the lead developer's ruling: append, because the mission ids need not follow a sequence), so a new change entry can carry an older timestamp than a lower change id. The 57 new canon missions come from 42 Memory Alpha episodes (TNG Seasons 4 and 5, read through the site's public API and written in the lab's own words); the 212 other new missions are generated from a recipe and labelled synthetic. The commit is on the owned branch `tx/missions-large-release`, parent lab commit `0797f59c53be460bb1ab5509c3dcba7fda9974cb`, tree `dde96c7`, 46 paths, +52148/-16. Exact subject: **Add Missions dataset release 1.1 with 300 missions appended to release 1.0**.

## Choices recorded

- **Append, MINOR.** The phase 1 proposal was a MAJOR 2.0 with new identities; the lead developer replaced it with an append, which D027 calls a MINOR. The generator reproduces the carried missions with generator 1's algorithm and seed key, and the release tests compare them byte for byte.
- **Composition.** 31 carried, 57 curated, 45 generated maintenance (50 of the type in all, so the type fills exactly one page), 167 generated routine missions. A hidden recipe parameter, the complexity, drives who staffs a repair; it is in the provenance and is not a contract field. The lead developer accepted, in a dialog, repair estimates below D027's band for the simplest repairs.
- **Crew references.** Missions numbers its own `C-n` for the 800 people (the ten of 1.0 kept), by a stream keyed by the v1 crew id, and a test proves that none equals its person's v1 suffix. Canon people who are not among the 800 (three) and references in no table are listed apart, on purpose.
- **Edge cases.** An edge ledger in the provenance lists them (partly staffed PLANNED missions, crews of 100, 99, 98 and 96, a commander as the only senior, a cancelled mission with a full staff, cancellations without an estimate, inactive and civilian crew, unmapped and dangling references, a 50-asset mission, long histories, boundary values). Picard commands 52 missions and Riker 50, so a filter on the commander pages once and twice. The lead developer's rule of 2026-10-19 added an identity trap: the returning Wesley Crusher of two Season 5 missions is an `O` participant, never Crew and never mapped.
- **Files.** Six real pages of 50 (their choice in a dialog). The Missions stub takes the release folder and now lists missions in the contract's order, which is a no-op for release 1.0.
- **Only 16 of the 800 are senior.** Staffing by rank therefore leaves most generated missions without a senior officer; question 6 will change character when its outcomes are re-derived.

## Retained evidence and limits

The seal ran 15 check entries, all passed: staged whitespace, continuity, the Mission Control generator, the Missions offline validator, the Missions data gate on real Oracle 18c (23 tests), the four adapters' offline gates, the Assets and Personnel service gates and the Apollo and Cosmo gates (`federation-router-apollo-stack` 269.4 s, `federation-router-cosmo-stack` 296.2 s), the Apollo gate with the lead developer's ELv2 acceptance for this Job. The path to this seal was not straight, and the record keeps it: a first prepare was stopped at the lead developer's order to add the returning Wesley and was abandoned with the tool's own command (its stale lock removed with their word); the second prepare failed on two checks that no earlier test had shown, the mapping adapter's release check (it fails whenever the repository holds a Missions release the mapping was not checked against, which the lead developer resolved with an explicit pending list) and the Mission Control reading of the decisions (a decision registry row and links to files that exist at HEAD).

Limits: no real Missions service ran against release 1.1 (only the Oracle data gate and the stub); the stack default, the expected outcomes of the acceptance suite, the Missions adapter's own stub and tests and the mapping release still describe release 1.0, and the mapping release for the new references is a later Job. No benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
