# The first federation build adds the shared library and the Assets adapter

Date: 2026-10-16T11:49Z
Subject: Committed the first build of the federation layer: the parent pom, the shared library and the Assets adapter
Status: Historical / non-normative
Lab checkpoint: lab commit `7dd97753e2b5f91bb70c6ec9906845e25c7f4360`
Provenance: Git committer timestamp `2026-10-16T07:49:18-04:00` (2026-10-16 11:49:18 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the design talks that decided the content or this later record preparation. The lead developer gave a typed go at two previews (the manifest was not eligible for early approval, so each go only staged and sealed) and selected Approve on the sealed review through the host's control.
Migrated from lab log SD-2026.289-1149Z; originally written in the lab on 2026-10-16 (lab commit `0062b13b58fa7d3a80844c05abcbd5902e9b413a`).

## Meaningful transition

The lab gained its first federation code. The commit is on the owned branch `tx/20261016-federation-assets-adapter`, parent lab commit `ccaca30e8fb0a52f24dafc1ccb46991303254bcc`, tree `39d467d`, 34 paths, +2037/-0. Exact subject: **Add the federation layer's first build: the parent pom, the shared library and the Assets adapter**. At the time of this record the commit is not integrated into main.

The commit adds a new top-level folder `federation/`, outside `uss-enterprise/` which holds the legacy systems: the parent pom, the shared library `federation/common` and the Assets adapter `federation/adapters/assets`. It follows the design talks of 2026-10-15 and 2026-10-16 (recorded in the machine-local Job `federation_design` and in [the federation design](../docs/FEDERATION-DESIGN.md)) and the two experiments of [Integration notes](../docs/INTEGRATION-NOTES.md#federation-experiment-1-a-spring-subgraph-under-the-apollo-router-2026-10-15), whose code had not been committed.

## Choices recorded

- **The library** carries the `Resolution` enum (RESOLVED, UNRESOLVED, UNAVAILABLE, UNMAPPED), the derivation of the outcome from the result of one HTTP call, the builder of the errors entry and the code list. It has no Apollo, Cosmo or Hive dependency. UNMAPPED adds no errors entry.
- **The adapter** serves `Asset` (`@key assetId`) and `AssetReference` (`@key(fields: "localRef release")`, with `astId` external and `id`, `resolution`, `asset` each requiring it), the queries `asset` and `assets`, and uses only `@key`, `@requires` and `@external`. The outcome is computed once per reference with one call, on the first selected field that needs it; a null `astId` gives UNMAPPED without a call. One errors entry is made per failed call. A page at the graph level has a default limit of 20 and a maximum of 100, takes at most two calls and is all or nothing. The field list, the nullable list `[Asset!]` with no total count, and the codes were put to the lead developer in the preview.
- **A 404 that is not ASSET_NOT_FOUND** (PATH_NOT_FOUND included) is UNAVAILABLE with the code UPSTREAM_BAD_RESPONSE; a 5xx, a timeout or a connection failure is UNAVAILABLE with SERVICE_UNAVAILABLE. This is the worker's reading of the decided code list, not a separate decision of the lead developer's.
- **Codes:** Apollo Server's error documentation, fetched 2026-10-16, lists BAD_USER_INPUT and INTERNAL_SERVER_ERROR, which confirms the names recalled in the design talk.
- **Versions, resolved 2026-10-16:** Spring Boot 3.4.13 (experiment 1 used 3.4.5; the newest 3.4 patch), Spring for GraphQL 1.3.7 as managed, graphql-java held at 22.3 (the version federation-jvm 5.4.0 declares; Boot 3.4.13 manages 22.4), federation-jvm 5.4.0. The Temurin 21 build and runtime images are pinned by the digests of 2026-10-15, unchanged on the day.
- **Found on the day, not acted on:** Maven Central lists federation-graphql-java-support 5.5.0, 6.0.0, 6.1.0, 6.2.0, 6.2.1 and 7.0.0 (7.0.0 modified 2026-08-03, declaring graphql-java 26.0), which the design document's "newest is 5.4.0" does not reflect. Spring Boot 3.4 is believed to be past open-source support; that is not verified. Both are for the lead developer's decision.
- **Packaging** follows the Assets and Missions precedent: a multi-stage Dockerfile whose build stage runs the offline tests, a non-root runtime, a compose file on loopback port 8184 with provisional limits (1 CPU, 512 MB, read-only filesystem), and a start script that refuses a taken port with one line. The container limits are provisional until the benchmark environment record.
- **Checks:** a new profile `federation-adapter-runtime` with two gates, `federation-assets-offline` (the image build runs the tests, then the image, compose file and start script are checked and run) and `federation-assets-service` (the adapter against the real Assets service and a disposable PostgreSQL 17, with the expected outcomes of dataset release 1.1), rows in the artifact classification table, and a selector test.

## Retained evidence and limits

Pre-commit checks of the seal, all exit 0: staged whitespace (0.2 s), continuity (23.2 s), `mission-control-generator` (126.3 s), `federation-assets-offline` (14 tests, 63.2 s), `federation-assets-service` (6 tests, 75.7 s), `checkpoint-selector` (47.7 s), `classification-tests` (6.2 s), `checkpoint-invariants` (135.6 s) and `commit-metadata` (18.3 s); the seal took 8 m 16 s. Before the first prepare the worker ran Maven `verify` in Docker (10 library tests and 19 adapter tests passed) and both gates by hand. The first prepare failed on `federation-assets-offline` because an edit of the worker's own to `test_packaging.py` left a syntax error that the worker had not rerun; the worker fixed it, reran the gate, abandoned that transaction and took a second preview and a second go. Images are about 523 MB, as in experiment 1.

Limits: no mapping adapter, no Personnel or Missions adapter, no router, no whole-stack compose and no Hive or Cosmo configuration exist; the Assets service and its contracts are unchanged. The adapter has been run only against a stub and against the real Assets service with the dataset's expected outcomes, not under a router. The gates need Docker. Nothing is marked `frozen`.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. This runtime commit unblocks freezing the Assets contract 1.1, which follows as its own job. A small docs update brings [the federation design](../docs/FEDERATION-DESIGN.md) up to date with the later talk and this build. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
