# Mapping release 1.3 lands and the stack serves Missions release 1.2

Date: 2026-10-20T02:22Z
Subject: Committed mapping release 1.3 for the participants that Missions dataset release 1.2 reclassified, with a strict participant step, and switched the whole federation stack to Missions release 1.2 and mapping release 1.3 with the expected outcomes derived again
Status: Historical / non-normative
Lab checkpoint: lab commit `0b7ee2481dc7b9e5af7f30a364abef04e678714d`
Provenance: Git committer timestamp `2026-10-19T22:22:53-04:00` (2026-10-20 02:22:53 UTC), converted to the prescribed UTC minute. The lead developer accepted the Elastic License 2.0 for all Jobs, chose release number 1.3 by selecting a dialog option, and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.293-0222Z; originally written in the lab on 2026-10-20 (lab commit `513b28fd378850e44f90d2776b31755cf3f9a844`).

## Meaningful transition

Missions release 1.2 made every participant a P (on-board non-crew Personnel) or an O (outsider). Mapping release 1.3 follows: all 58 P references resolve to non-crew people of the roster, 57 by exact name and P-1003 Alexander Rozhenko by the exceptions table, and the 153 O references stay refused by class, the returning Wesley and the off-roster civilian Clara Sutter included. The crew and assets files are those of 1.2 byte for byte. Under the lead developer's definitions every P must resolve, so the participant step now has a strict mode in which an unplaced P fails the build and names the reference. The stack default moved to Missions release 1.2 and mapping release 1.3. The commit is on the owned branch `tx/20261020-mapping-13-switch`, parent lab commit `1e263c1b7e0a52412ec48526986a0886b6eba4ec`, tree `3bcf59a`.

## Choices recorded

- **Release 1.3, a MINOR.** The lead developer selected 1.3 over 2.0: the same file kinds, new entries.
- **The exceptions table stays.** It is pinned for release 1.2, which never changes, so P-1003 remains an EXCEPTION outcome although its full name now matches by exact name. Worker choice, reported.
- **The shared suite changed in one place,** the lists of mapping releases, which now end with 1.3; the Job asked for no other change in its assertions.

## Retained evidence and limits

The expected outcomes derived from the new inputs differ from the previous file only in the release names and the input hashes. Test counts before and after: mapping offline 107 and 129, Missions offline 14 and 14, Apollo offline 39 and 39, Apollo stack 33 and 33, Cosmo offline 40 and 40, Cosmo stack 34 and 34. The first run of the mapping gate failed twice on assumptions of the old newest release in its packaging test (the files of the image and the expected release list), which were corrected before the seal. Not claimed: the Missions adapter service stage on the real Oracle, which still pins release 1.0, or any resolution of participants in the graph.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
