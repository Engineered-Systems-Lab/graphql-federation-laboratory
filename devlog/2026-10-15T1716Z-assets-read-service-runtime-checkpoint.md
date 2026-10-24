# The Assets read service runs on PostgreSQL 17

Date: 2026-10-15T17:16Z
Subject: Committed Assets read service with its PostgreSQL 17 schema, load script, real-container gate, classification rows and the assets-service profile
Status: Historical / non-normative
Lab checkpoint: lab commit `969a9906b876e98f8f6ade011ea4ef823e714e47`
Provenance: Git committer timestamp `2026-10-15T13:16:53-04:00` (2026-10-15 17:16:53 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the talks that decided the content or this later record preparation. The lead developer gave the typed go at the preview and approved the sealed transaction through the host's Approve control in the worker's own session.
Migrated from lab log SD-2026.288-1716Z; originally written in the lab on 2026-10-15 (lab commit `0a42a09eaac439aa6a2cdacfe9d9a7ece68489be`).

## Meaningful transition

The Assets component gained its third slice: a read-only service that answers what contract 1.0 says for dataset release 1.0, backed by PostgreSQL 17, with a gate that proves it against a real disposable container. The commit is on the owned branch `tx/assets-readservice-20261015`, parent lab commit `9feb3c91b32ed6b8d5be9346dfcf272d9d7e6393`, tree `efb7d88`, 17 paths, +2126/-14. Exact subject: **Add the Assets read service on PostgreSQL 17 with its schema, load script and real-container gate**. At the time of this record the commit is not integrated into main.

What the commit holds: the schema (the asset table with the identifier grammar as a check, the lookup tables for kinds, categories and statuses, the view that derives the category, triggers for the parent rules, append-only reference data), the load script (manifest check, one transaction, parents first, refusal of a non-empty database), the service on the standard library and psycopg 3 (127.0.0.1, port 8084, one read-only connection per request), the gate and its fail-closed runner, the unit tests that need no database, the `assets-service` profile and policy command, the classification rows of the new paths, a scope test of the profile, and the design and README sections.

## Choices recorded

- **Web layer: the standard library.** The reason given in the design is plain on purpose: the only third-party package is the driver, and one method table answers every method with 405 and `Allow: GET`, which a framework would have to be told not to handle itself. The cost is hand-written routing and error mapping, covered by unit tests.
- **One kind-to-category table.** It lives in `asset_kinds` in the database. The service reads kinds, categories and statuses from it at startup, so the filter tokens come from that table; the category is never stored.
- **A path outside the two answers 404 with the code ASSET_NOT_FOUND**, the only 404 code the contract has. This was the worker's choice and is flagged to the lead developer and the Coordinator: a client that builds a wrong path would read it as an unresolved asset, so the federation must build its paths from the contract.
- **The gate entry lives inside the component** (`uss-enterprise/assets/validation/run_service_gate.py`), not as a new tool under `validation/` as Missions has it, which avoided new tooling files and tooling tests. The profile and policy rows are the approval-sensitive part of the change.
- **Pins resolved on 2026-10-15.** The image is `postgres:17-bookworm` by the digest of its OCI index, `sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826`, the same value the design recorded earlier; PostgreSQL 17.11 ran in the gate and the pulled image measures 637 MB. The driver is `psycopg 3.3.6` with `psycopg-binary 3.3.6` (and `tzdata 2026.5` on Windows), which the worker installed into the admitted Python 3.14.8; the requirements file pins them.

## Retained evidence and limits

Pre-commit checks, all exit 0, in a seal that took 3 m 04 s (the whole prepare took 3 m 17 s): staged whitespace (0.1 s), continuity (14.9 s), `checkpoint-selector` (35.5 s), `classification-tests` (5.3 s), `assets-offline` (0.2 s), `assets-offline-tests` (5.2 s, which now include the unit tests of the service), `assets-service` (24.9 s) and, because the profile includes tooling and governance paths, `checkpoint-invariants` (82.5 s) and `commit-metadata` (15.7 s). The `assets-service` gate has 41 tests; run alone it took 17 to 21 s, of which about 5 s were container start, schema, load and service start. It checks every valid contract example against the live service, the expected outcomes of the dataset provenance (EQ-97 and EQ-108 answer 404 ASSET_NOT_FOUND, SH-53 is DESTROYED, EQ-86 is MISSING, the others answer 200, both parent chains), the filters alone and combined, paging, order, the 400, 404 and 405 cases, that the database refuses a non-vehicle parent, a missing parent, a cycle and malformed data, that two loads give identical dumps, and that the service never writes (its login cannot, the server's statement log shows only read-only transactions from it, and the rows are unchanged).

Limits: the gate ran under the admitted Python 3.14.8; the 22 unit tests of the service logic also passed under Python 3.13.16, but the service itself was not run on 3.13 against a container. The first gate run found and fixed several defects of the draft before the seal (a generated column that raised before its check, a 500 for an unsupported HTTP version, the standard library collapsing a leading double slash in the path, and tests that granted or revoked on the wrong role). No Dockerfile, compose file, packaging, federation, write endpoint, manual lead developer acceptance or `frozen` mark exists. The Oracle container of the Missions gates was not touched.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. Packaging is the next Assets slice and the planned `frozen` mark of the contract is a separate later decision; neither is part of this record. No push.
