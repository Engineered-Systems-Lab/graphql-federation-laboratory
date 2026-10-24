# Missions release 1.2 reclassifies the participants as P and O

Date: 2026-10-20T00:44Z
Subject: Committed Missions dataset release 1.2, an append to release 1.1 that applies the lead developer's definitions of the reference classes: outsiders that the data called P become O, placeholders become roster civilians as P or named synthetic outsiders as O, and every identity of 1.1 is kept
Status: Historical / non-normative
Lab checkpoint: lab commit `1740ef3ca4cb484a66b12028366d56c9e776d22a`
Provenance: Git committer timestamp `2026-10-19T20:44:14-04:00` (2026-10-20 00:44:14 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's definitions (their words of 2026-10-19 are recorded verbatim in the Job `federation_design`) or this later record preparation. The lead developer chose the form of the correction, the treatment of the carried missions and of the off-roster civilian by selecting dialog options, accepted the Elastic License 2.0 for all Jobs, and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.293-0044Z; originally written in the lab on 2026-10-20 (lab commit `1e263c1b7e0a52412ec48526986a0886b6eba4ec`).

## Meaningful transition

The lead developer found that P, meant as Personnel (people on the ship who are not crew), had been used for outsiders since release 1.0, and that O had been used for groups and objects. Release 1.2 appends to release 1.1 (a MINOR): the 300 missions keep their ids, the 865 change entries are unchanged, and 108 missions carry corrected participants with one appended UPDATED entry each, so the clean-up has an audit trail. The release has 58 P references and 153 O references; every P names one civilian of `personnel-v2-large-004` by exact display name, and the generator and the validator check it. The commit is on the owned branch `tx/20261019-missions-participants-cleanup`, parent lab commit `74d9710eeec1a3d84df62f36d354732527057f44`, tree `2d9475d`.

## Choices recorded

- **Appended corrections, 1.2.** The lead developer chose appended correction entries over direct edits in a MAJOR 2.0. The entries keep status and costs, are performed by Data (C-85) and ordered by Riker (C-78) from 2368-12-23T09:00 one minute apart; these actors and times are the worker's synthetic choices.
- **The 31 carried missions are corrected too,** the lead developer's choice; releases 1.0 and 1.1 stay as history.
- **Clara Sutter stays O.** She is the one canon on-board civilian missing from the roster; she is flagged in the provenance and Personnel is not changed. Her reference is a new O reference.
- **Worker choices, reported.** Generated missions get their class from their title or template (drills, screening, equipment and science work: roster civilians; transfers, escorts, relief, clinics, searches, patrols: synthetic outsiders from six pools); the 20 roster civilians who are also crew in the legacy Crew system are never drawn as P; new references are numbered from 2121 in steps of 13; the mapping check gets a pending-list entry for release 1.2, the pattern used for 1.1.

## Retained evidence and limits

The seal ran 15 checks, all passed in the second attempt. The first attempt failed only `missions-data`: the project's Oracle container (`starfleet-missions-data-20261009`) was stopped. The worker started it, ran the data gate alone (34 tests, pass) and prepared the same candidate again under the same go. Offline, the new tests cover counts, the append rule, the archived reproduction, the stream keys, tamper and class corruption, the pinned roster against the released Personnel pages and the definitions on the released data. Not claimed: the mapping release for the new P references, the switch of the stack to release 1.2, the re-derived acceptance outcomes, or any canon claim about the synthetic outsiders and the drawn civilians.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
