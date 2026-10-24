# Assets dataset release 1.0 is published

Date: 2026-10-15T16:34Z
Subject: Committed Assets dataset release 1.0 with its controlled cases, the consumer mapping, the review page generator, the offline dataset checks and the classification rows
Status: Historical / non-normative
Lab checkpoint: lab commit `a826c5d91d9275d9215460c0f6ec4573a320d894`
Provenance: Git committer timestamp `2026-10-15T12:34:56-04:00` (2026-10-15 16:34:56 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the talks that decided the content or this later record preparation. The lead developer read the review page and approved the dataset before the release was written, and approved the sealed transaction in the worker's own session with the typed word APPROVE.
Migrated from lab log SD-2026.288-1634Z; originally written in the lab on 2026-10-15 (lab commit `9feb3c91b32ed6b8d5be9346dfcf272d9d7e6393`).

## Meaningful transition

The Assets component gained its second slice. Release 1.0 of the dataset is 32 assets covering all nine kinds, immutable like a Missions release: a manifest holds the content hash of each file, the hash of the contract and the hashes of the Missions release 1.0 it was checked against, and a change is a new release folder. The commit is on the owned branch `tx/assets-dataset-20261015`, parent lab commit `febb9c5e6ab5318cb1c75679ebdc3d13b0e2c9f0`, tree `16f572f`, 12 paths, +1759/-11. Exact subject: **Add the Assets dataset release 1.0 with its review generator, offline checks and classification rows**. At the time of this record the commit is not integrated into main.

The nine ids that the released Missions dataset references (68 references): VS-31 (the Enterprise), SH-42, EQ-64, EQ-75 and EQ-119 resolve normally; SH-53 resolves as DESTROYED; EQ-86 resolves as MISSING; EQ-97 (an isolation kit) and EQ-108 (a cargo module, which fits no equipment kind) are left out on purpose and are the DANGLING case, three Missions references each. The other 25 assets are used by no mission. Two parent chains are provided: EQ-64 aboard SH-17 aboard VS-31, and EQ-211 aboard RV-3 aboard SH-70 aboard VS-66. The id prefixes are a dataset convention (VS, SH, RV, AV and EQ), not a contract rule.

## The consumer mapping

After the review page was shown, the Coordinator relayed a scope addition from the lead developer, who had asked whether the dangling answers could cause trouble later. The expected outcomes now say that two layers answer: the Assets service answers 404 ASSET_NOT_FOUND for an id it does not have, and the consumer shows that reference as UNRESOLVED with a null asset, as data. Only a 404 maps to UNRESOLVED: any other failure of the lookup (a 500, a timeout, the service being down or a 400 for a malformed id) is a lookup failure, shown as an error entry with a null asset, so that an outage cannot pass for a dataset of missing assets. The provenance, the review page (two columns, "Assets answers" and "Consumer shows", and the rule in one sentence) and one sentence of the design document carry it. The change was made to the candidate before commit, which required a fresh preview.

## How the mission went

A first prepare was interrupted by the lead developer at a tool prompt and left a stale operation lock and staged files in the owned worktree, with no checkpoint process running. With the lead developer's word the lock in the owned worktree was removed and the transaction abandoned; the candidate was amended and a fresh preview was shown. No other worktree or branch was touched. The classification of the new paths could not use the early go, because a new path is graded high until its row exists, so the typed go only staged and sealed and the sealed Approve decided.

## Retained evidence and limits

Pre-commit checks, all exit 0: staged whitespace (0.1 s), continuity (20.0 s), `checkpoint-selector` (39.1 s), `classification-tests` (7.5 s), `assets-offline` (0.3 s) and `assets-offline-tests` (5.6 s, 81 tests); the profile was `assets-contract+governance`. The dataset validator checks every record against the contract schema, the kind table, unique ordered ids, parents that exist, are vehicles and form no cycle, the cross-check against the released Missions dataset (nine ids, 68 references, which resolve and which dangle against the written expectations), the manifest hashes and an exact regeneration of the release from its own curation file. The names are inspired by Star Trek: The Next Generation and were not verified against Memory Alpha; every description, status and parent is synthetic. No PostgreSQL schema, service, container, federation code, `frozen` mark or manual acceptance exists. The execution status reported an overlap with another mission on the classification table file.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. The PostgreSQL schema and load script are a later slice that was not in this Job's scope. No push.
