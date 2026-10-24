# The Assets service is packaged with its Docker Compose gate

Date: 2026-10-15T18:02Z
Subject: Committed Assets packaging: Dockerfile, compose file, start script with its port-free check, one-shot bootstrap, packaging gate and the assets-packaging profile
Status: Historical / non-normative
Lab checkpoint: lab commit `8c23e5c9e8985078f3e8332f6092c4a8b9a8c663`
Provenance: Git committer timestamp `2026-10-15T14:02:25-04:00` (2026-10-15 18:02:25 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the talks that decided the content or this later record preparation. The lead developer gave the typed go at the preview (which was not eligible for early approval, so it only staged and sealed) and approved the sealed transaction through the host's Approve control in the worker's own session.
Migrated from lab log SD-2026.288-1802Z; originally written in the lab on 2026-10-15 (lab commit `60aa7750e7c4294794b963d8743be2a81b3cdc12`).

## Meaningful transition

The Assets component gained its fourth slice: one command, `start.sh start`, brings the read service up with its own PostgreSQL 17 database from the committed files, on loopback, with release 1.0 loaded, and a gate proves it through Docker Compose. The commit is on the owned branch `tx/assets-packaging-20261015`, parent lab commit `0a42a09eaac439aa6a2cdacfe9d9a7ece68489be`, tree `26ace11`, 19 paths, +933/-26. Exact subject: **Add the Assets packaging with its Dockerfile, compose file, start script and Docker Compose gate**. At the time of this record the commit is not integrated into main.

What the commit holds: a one-stage Dockerfile on `python:3.13-slim-bookworm` pinned by digest (pinned dependencies, user `10001:10001`, only the service code, schema, load script, the contract the load script checks and release 1.0), its `.dockerignore`, a compose file with three containers, an example environment file of placeholders, the bootstrap, the start script, the packaging gate stage and suite, offline tests of the port rule, the `assets-packaging` profile and policy command, the classification rows and golden entries, a scope test and the design and README sections.

## Choices recorded

- **The database is published nowhere.** Only the project's containers reach it; the service is published on `127.0.0.1:8084` only and holds the read-only login. The administrator password reaches the database and the one-shot bootstrap only. The gate therefore reuses the service gate's HTTP checks but not its administrator-connection checks, which stay in the service gate.
- **Bootstrap, idempotent, verify and never repair.** An empty database gets the schema and the release; a loaded one is verified to equal the release and left alone, and a difference fails. The verification was moved out of the load script into one function that both share.
- **A named volume**, so that a stop and a start keep the data and the second-start rule is a real property. The script never removes anything; the reset is the lead developer's own `docker compose down --volumes`.
- **Limits** (chosen by the worker as modest for 15.6 GB of RAM, to be revisited at 32 GB): database 1 CPU and 512 MB, service and bootstrap 0.5 CPU and 256 MB, memory and swap equal. The benchmark design wants the machine facts and these limits in every run manifest; the README says so.
- **The port rule** (the lead developer, 2026-10-15): the start script refuses a taken port with one line, judged by a connect attempt and not a bind, because Windows lets a second listener bind a taken port without an error.
- **Pins resolved on 2026-10-15** with `docker buildx imagetools inspect`: `python:3.13-slim-bookworm` is `sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641` and `postgres:17-bookworm` is `sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826`, both equal to the design talk's digests.
- **Deviation: no executable bit.** `core.filemode` is false on this machine and every committed script is mode 100644, so `start.sh` is documented to run with `bash`. A line-ending attribute keeps it LF.

## Retained evidence and limits

Pre-commit checks, all exit 0, in a seal that took 6 m 19 s: staged whitespace (0.1 s), continuity (16.3 s), `mission-control-generator` (74.5 s), `checkpoint-selector` (33.5 s), `classification-tests` (4.7 s), `assets-offline` (0.2 s), `assets-offline-tests` (7.8 s), `assets-service` (20.4 s), `assets-packaging` (124.3 s), `checkpoint-invariants` (82.7 s) and `commit-metadata` (14.2 s). The packaging gate has 35 tests: the pinned bases and a compose file that fails closed without credentials, an image built from the committed files that holds only the expected files and runs as a non-root user, the real start through the script on an ephemeral port and the refusal of a taken one, the loopback publication, the unpublished database, the limits as Docker reports them, the service gate's HTTP checks against the published service, a second start that duplicates nothing, a tampered database that is refused and not repaired, and a clean teardown. Before the seal one assertion of the gate was wrong (the container keeps its log across a stop, so two bootstrap lines are expected) and was fixed.

Limits: the executable bit, as above; the gate runs the service on Python 3.13 in the image but the host side runs under the admitted Python 3.14.8; no federation, write endpoint, registry, orchestration, load or benchmark measurement, manual lead developer acceptance or `frozen` mark exists. The Oracle container was not started.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. The federation and the planned `frozen` mark of the contract are later, separate work. No push.
