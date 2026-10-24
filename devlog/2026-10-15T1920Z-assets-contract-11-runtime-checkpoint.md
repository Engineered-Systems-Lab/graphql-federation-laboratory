# Assets contract 1.1 brings native identifiers and dataset release 1.1

Date: 2026-10-15T19:20Z
Subject: Committed Assets contract 1.1: native AST identifiers, PATH_NOT_FOUND, dataset release 1.1 and the decision D038
Status: Historical / non-normative
Lab checkpoint: lab commit `c717e3cbb46b2a200609837f9ca33d306cf9bfe4`
Provenance: Git committer timestamp `2026-10-15T15:20:36-04:00` (2026-10-15 19:20:36 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the talks that decided the content or this later record preparation. The lead developer read the review page of the dataset release before it was released, gave the typed go at the preview (the candidate was eligible for early approval, so the go approved the exact tree) and no separate sealed Approve was taken.
Migrated from lab log SD-2026.288-1920Z; originally written in the lab on 2026-10-15 (lab commit `589a7f042f7173a860fe78d9e472c91c8dccf8f4`).

## Meaningful transition

The Assets component gained a second contract and a second dataset release. The commit is on the owned branch `tx/assets-unknown-path`, parent lab commit `60aa7750e7c4294794b963d8743be2a81b3cdc12`, tree `15c05aa`, 68 paths, +2882/-392. Exact subject: **Add Assets contract 1.1 with native AST identifiers and PATH_NOT_FOUND, and dataset release 1.1**. At the time of this record the commit is not integrated into main.

The work began as one small change, a distinct code for a path outside the contract, which the lead developer chose as PATH_NOT_FOUND; the read service had answered ASSET_NOT_FOUND, so a client that built a wrong path would have read it as an unresolved asset. The scope then grew by the lead developer's decision: they expected the Assets system to have an identifier of its own, like Personnel, and not the Missions references, so contract 1.1 carries both changes. The first plan, an in-place edit of the 1.0 file, was dropped when the worker found that the dataset release 1.0 pins the hash of that file in its immutable manifest; the lead developer chose a new contract file instead of editing 1.0, and then, when the identifier grammar was added, chose to keep it in 1.1 as a recorded exception rather than a 2.0.

## Choices recorded

- **Contract 1.1 is a new immutable file beside 1.0**, with its fixtures in `fixtures/v1.1/valid` and `fixtures/v1.1/invalid`. The 1.0 file, its fixtures and release 1.0 are unchanged. The validator checks both, and checks that 1.1 differs from 1.0 only by the grammar and PATH_NOT_FOUND once prose and example links are ignored.
- **The grammar** is a prefix of one to three segments of capital letters joined by single underscores (the first of 2 to 8 letters, the others of 1 to 8), a hyphen and a number of four or more digits: padded to four up to 9999, never all zeros, no leading zeros from 10000 on. The lookahead that would state the length of the whole prefix is outside the portable pattern subset, so the length bound is expressed by the segments. Double underscores are not allowed, a choice of the worker (a second spelling for no gain).
- **The version exception** is recorded once, as D038: a change of the identifier grammar is breaking and would normally be a new major; it is made in 1.1 because 1.0 never had a consumer. The rule is unchanged for later changes. 1.1 is not a superset of 1.0 in its identifiers.
- **The dataset release 1.1** keeps the 32 assets and renames them AST-0001 to AST-0032 by a stated rule (the order of the release 1.0 identifiers, one step each), pinned in the manifest with the hashes of the release 1.0 assets and manifest. The expected mapping of the nine Missions references is in the provenance and on the review page, in three layers: five NORMAL, one DESTROYED, one MISSING, one MAPPED BUT NOT FOUND (EQ-97 to AST-0097, which Assets does not hold: 404 ASSET_NOT_FOUND, UNRESOLVED) and one UNMAPPED (EQ-108: Assets is not asked, the consumer reports no mapping). The mapping is not a field of the record and not a service. The consumer rule is refined: UNRESOLVED only for a 404 whose code is ASSET_NOT_FOUND; the immutable provenance of release 1.0 keeps its older wording, corrected by the design document.
- **Gates** now run against contract 1.1 and release 1.1: the unit tests, the service gate and the packaging gate share the checks for PATH_NOT_FOUND, for the old-style id answering 400 and for the three-layer outcomes. The Dockerfile copies contract 1.1 and release 1.1; the port rule, limits, start script and compose file are otherwise unchanged.

## Retained evidence and limits

Pre-commit checks, all exit 0: staged whitespace (0.1 s), continuity (18.5 s), `assets-offline` (0.3 s), `assets-offline-tests` (10.3 s), `assets-service` (41 tests, 27.0 s) and `assets-packaging` (35 tests, 127.7 s). Before the seal the worker ran the whole offline suite (130 tests) and both gates by hand; the first packaging run failed on one test that still named an old identifier, which was fixed and rerun. The dataset review page was sent to the lead developer as a file and approved before release.

Limits: no mapping service, subgraph or federation exists; the expected mapping is a statement to check a later integration against, not an implementation. The gates run the service on the admitted Python 3.14.8 on the host side and 3.13 in the image. Missions and Personnel are unchanged and were not rerun. Nothing is marked `frozen`; the exact files and folders of both versions are for a later, separate step.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. The frozen mark of both contract files and fixture folders follows as its own job. No push.
