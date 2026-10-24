# The Assets design and executable contract 1.0 are committed

Date: 2026-10-15T12:21Z
Subject: Committed Assets design document, OpenAPI contract 1.0 with examples, offline validator and the assets-contract gate
Status: Historical / non-normative
Lab checkpoint: lab commit `1e915acb267ab4d05694d661f170f9bf77b8f558`
Provenance: Git committer timestamp `2026-10-15T08:21:20-04:00` (2026-10-15 12:21:20 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the earlier design talks or this later record preparation. Transaction `108394d3734804fffec3bdba6f53da83` was approved by the lead developer's selected Approve against prepared digest `36e878454505baf2ee3c95c6a9e20c253d8c815d672292a87d78ae047706a92b`; the lead developer's typed go at the preview had authorized staging and sealing only.
Migrated from lab log SD-2026.288-1221Z; originally written in the lab on 2026-10-15 (lab commit `0c4006f8f84839553f12c1566b05cc8a8d813366`).

## Meaningful transition

The future Assets bounded context, until now only a pointer in the plan, has a design and an executable contract. The commit is the first slice of the Assets service, on the owned branch `tx/20261015-assets-contract`, parent lab commit `5dd1feff47597963ec1f8efe5d27befddc0db6df`, tree `f3724d4`. Exact subject: **Add the Assets design and the executable Assets contract 1.0 with its offline validator**. At the time of this record the commit is not integrated into main.

What exists: [the design document](../docs/ASSETS-V1-DESIGN.md); the OpenAPI 3.1 contract 1.0 as one JSON file with JSON Schema inside it; 14 valid and 10 invalid example bodies under `uss-enterprise/assets`; a standard-library validator with a strict JSON Schema subset checker and 38 tests; and a README. The contract is a read-only REST/JSON surface: `GET /assets/{assetId}` and `GET /assets`, a six-member asset record, five statuses, stable JSON error codes and 405 for every other method. What does not exist: a dataset, a PostgreSQL schema, a service, a container, a contract freeze or any manual acceptance. No location field exists, by decision.

## Decisions carried into the design

The lead developer's words are quoted in the design document; the reasons were the Coordinator's, which the lead developer accepted in the design talk.

- A hypothesis for the context: whether a federation layer can compose SOAP Personnel, XML REST Missions and JSON REST Assets and behave predictably when a reference does not resolve. Missions release 1.0 references 9 distinct assets in 68 references, which this worker counted again in the immutable `missions.xml`; the dataset slice will omit one or two on purpose and carry the destroyed, missing, unreferenced and parent-chain cases with expected outcomes.
- Five statuses: ACTIVE, MAINTENANCE and DECOMMISSIONED, plus DESTROYED (final) and MISSING (can return), so that a mission referencing a destroyed asset differs from one referencing a missing asset.
- A parent must exist inside Assets (a database foreign key, later); dangling is a cross-service case only. No location, because Missions already owns where a mission takes place and an asset location would invite contradictions; it can be added as a compatible minor.
- The worker's own choices, put to the lead developer at the review as open points: JSON rather than YAML, and a purpose-written standard-library checker rather than a pinned third-party `jsonschema`; offset and limit paging rather than the Missions page shape, because the recorded direction is a service that differs from Missions on purpose; the bounds 1 to 120 and 1 to 1000 for name and description; and that any asset may be a parent.

## Policy

`uss-enterprise/assets` is a runtime path like Missions, with its own `assets-contract` profile whose runtime gates are the offline validator and its tests; every other path under it blocks. The design under `docs` selects continuity alone. The checkpoint policy gained two commands and the profiles one profile and two invariants; the artifact classification table gained its exact rows; one scope test pins the separation from the Personnel and Missions gates.

## Retained evidence and limits

Pre-commit checks, all exit 0 (8 of 8, 2 min 45 s in all): staged whitespace, continuity, `checkpoint-selector`, `classification-tests`, `assets-offline`, `assets-offline-tests` (38 tests), `checkpoint-invariants` and `commit-metadata`. No Personnel or Missions gate was run, by design. The validator proves the contract is well-formed OpenAPI of the decided surface, that every example validates against its own response and that the invalid examples and probes are rejected; it does not establish service behavior, ordering, filtering, the `Allow` header or any rule across records. The digests of the two container images in the design were read from the registry on 2026-10-15 for reference and are not pins.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. The Coordinator is asked to decide whether the design talk needs a numbered decision in the decisions record, as Missions has D027 to D034; this slice added none. [Plan](../docs/PLAN.md) still describes Assets as open and needs its own record transaction. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
