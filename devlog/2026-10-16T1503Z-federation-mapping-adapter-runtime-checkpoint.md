# The federation mapping adapter and mapping release 1.0 are built

Date: 2026-10-16T15:03Z
Subject: Committed the federation mapping adapter and the mapping release 1.0, assets only
Status: Historical / non-normative
Lab checkpoint: lab commit `9e97bc73170726a45c067658d54a8cb626293d2e`
Provenance: Git committer timestamp `2026-10-16T11:03:12-04:00` (2026-10-16 15:03:12 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the design talks that decided the content or this later record preparation. The lead developer gave a typed go at the preview (the manifest was not eligible for early approval, so the go only staged and sealed) and selected Approve on the sealed review through the host's control.
Migrated from lab log SD-2026.289-1503Z; originally written in the lab on 2026-10-16 (lab commit `7016d338ec02387afadf92390ce8cd8dc00935b9`).

## Meaningful transition

The federation layer gained its second adapter and its first mapping data. The commit is on the owned branch `tx/20261016-mapping-adapter`, parent lab commit `609aaba`, tree `4c162c9`, 38 paths, +1943/-6. Exact subject: **Add the federation mapping adapter and the mapping release 1.0, assets only**. At the time of this record the commit is not integrated into main.

The commit adds `federation/adapters/mapping`, the mapping subgraph on port 8190, and `federation/mapping-releases/1.0`, the first immutable mapping release. It builds to the design talks of 2026-10-15 and 2026-10-16 (recorded in the machine-local Job `federation_design` and in [the federation design](../docs/FEDERATION-DESIGN.md)) and to experiment 2 in [Integration notes](../docs/INTEGRATION-NOTES.md#federation-experiment-2-the-owning-adapter-produces-the-outcome-under-three-routers-2026-10-16), whose mapping subgraph it now implements for real.

## Choices recorded

- **Port 8190, not 8185.** The Coordinator relayed the lead developer's correction of 2026-10-16 before the build: the adapters of legacy services mirror the legacy last digits in 8181 to 8189, and the mapping adapter has no legacy twin, so it takes the first port of the block 8190 to 8199 for federation-only services. Other ranges the Coordinator proposed were not confirmed by the lead developer and are not used.
- **The release** is `federation/mapping-releases/1.0/`: `assets.json` with the eight entries of the expected mapping of the Assets dataset release 1.1 (EQ-64, EQ-75, EQ-119, SH-42 and VS-31 normal, EQ-86 missing, SH-53 destroyed, and EQ-97 mapped to AST-0097, an id Assets does not hold) and no entry for EQ-108; and `manifest.json` with the SHA-256 of each file, taken over the LF-normalized bytes, and the checked-against list of the Missions dataset release 1.0 (its manifest), the Assets contract 1.1 (its file) and the Assets dataset release 1.1 (its manifest). No entry was invented. There is one file per kind of reference, so crew can be added in a later MINOR; the adapter loads and hash-checks sections it does not serve and gives a null for a kind a release lacks.
- **The adapter** serves `AssetReference` (`@key(fields: "localRef release")`, `astId`) with only `@key`. A missing or blank release is refused with `MAPPING_RELEASE_REQUIRED` and an unknown release with `MAPPING_RELEASE_NOT_FOUND`, with one errors entry per distinct cause in one `_entities` call; a reference with no entry gives `astId` null and no entry. There is no implicit latest and no partial match. It has no database and makes no outbound call. The loader stops the start when a release file differs from its hash, is missing or unlisted. The adapter also serves a diagnostic query `mappingReleases`, which the preview named and the lead developer approved with the commit.
- **What the adapter itself sees** of a blank release is written in its README: the router rejects a null or absent `String!` argument before any subgraph, but an empty string passes, and a direct `_entities` call can omit the field.
- **The checked-against rule** is a gate and not a Maven test, because the system files lie outside the image build context. The gate fails when a system file differs from the hash the release holds, or when the repository holds a newer Missions dataset release, Assets contract or Assets dataset release than the release lists, which surfaces the probable need for a new mapping release. It also re-derives `assets.json` from the Assets provenance.
- **Shared files:** the parent pom lists the third module; the Assets Dockerfile and dockerignore copy the mapping pom, because Maven loads every listed module; the Assets packaging test pins that line.
- **Checks:** the profile `federation-adapter-runtime` was extended with the command `federation-mapping-offline`, so every federation path runs the gates of both adapters. A mapping-only change therefore also runs the Assets service gate; a narrower profile per adapter was not made.
- **Versions** are those of the Assets adapter through the shared parent (Spring Boot 3.4.13, graphql-java held at 22.3, federation-jvm 5.4.0), with the same two image digests resolved on 2026-10-16. No new dependency or image was needed. The container limits are provisional, the same as the Assets adapter's.

## Retained evidence and limits

Pre-commit checks of the seal, all passed, none reused: staged whitespace (0.1 s), continuity (28.2 s), `mission-control-generator` (136.0 s), `federation-assets-offline` (14 tests, 65.7 s), `federation-assets-service` (82.2 s), `federation-mapping-offline` (29 tests, 68.1 s), `checkpoint-selector` (59.8 s), `classification-tests` (7.0 s), `checkpoint-invariants` (196.6 s) and `commit-metadata` (74.4 s); the seal took 11 m 58 s, and the last two were flagged slower than their history. Before the prepare the worker ran the build of the mapping image by hand, which runs 10 library tests and 29 adapter tests in Maven (the first run failed on a missing test helper and then on a wrong SDL pattern in the worker's own test; both were fixed and the gate rerun), and the Assets offline gate after the Dockerfile edit. The lead developer approved starting Docker containers and the image build before they ran.

Limits: no crew mapping (release 1.1 comes after the Personnel adapter and a crew mapping dataset design), no Missions or Personnel adapter, no router and no whole-stack compose exist. The mapping adapter has been run only on its own and against the fixture releases and the real release, never under a router. The gates need Docker. Nothing is marked `frozen`.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. The Missions adapter, the Personnel adapter and the routers remain separate Jobs, and the Assets contract 1.1 freeze is its own Job. No push.
