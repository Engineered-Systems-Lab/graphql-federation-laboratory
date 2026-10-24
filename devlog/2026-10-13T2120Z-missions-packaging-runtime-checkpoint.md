# The Missions service is packaged as an image with a compose file

Date: 2026-10-13T21:20Z
Subject: Committed image, compose file and packaging acceptance gate for the Missions service
Status: Historical / non-normative
Lab checkpoint: lab commit `09496d41c1481287473bba16eb8eb76d58c8ad53`
Provenance: Git commit time 2026-10-13T17:20:47-04:00 (21:20:47 UTC on October 13, 2026) establishes this checkpoint's minute. A separately delegated fresh records worker inspected the immutable commit, its message, the component README section committed with it, the retained authenticated checkpoint handoff and the Job records of the implementation worker and of this follow-up. The runtime checks below are retained execution evidence from the implementation worker; the records worker did not rerun them, and the worker's own measurements are marked as reports.
Migrated from lab log SD-2026.286-2120Z; originally written in the lab on 2026-10-13 (lab commit `e40597078fe234420e5625dc812ea804fac8b4b1`).

## State transition

Parent lab commit `b07449348e46ec2e50d5549a5f9d751d940025b2`, tree cf41486 (a tree, not a commit). The commit packages the read and write service of the [previous checkpoint](2026-10-13T2000Z-missions-write-service-runtime-checkpoint.md) as the [Missions design](../docs/MISSIONS-V1-DESIGN.md) leaves it open: the component README had said that image packaging and deployment were not supplied. Per its message it adds:

- `uss-enterprise/missions/Dockerfile`: two stages, Maven 3.9.11 on JDK 17 running `mvn verify`, then a JRE 17 stage with the jar and its libraries; both bases pinned by digest, the same digests the service gate harness already used; the non-root user `10001:10001`; `MISSIONS_BIND_HOST=0.0.0.0` and `MISSIONS_PORT=8083` inside the container.
- `.dockerignore`: the build context holds only `pom.xml`, the 1.1 schema, `fixtures/valid` and `src`.
- `compose.yaml`: the service only. It joins the existing internal Oracle network `starfleet-missions-data-20261009` as an external network, plus an ordinary bridge of its own because the Oracle network has no host access, and publishes `127.0.0.1:8083` only. The three credentials come from the environment with no default, and compose fails before starting anything without them; `MISSIONS_DB_SCHEMA` defaults to `MISSIONS_LAB`. The operator script keeps owning the Oracle container; compose never starts, removes or recreates it.
- The README packaging and deployment section, replacing the not-supplied statement and keeping the historical sections as written.
- The packaging gate `validation/runtime/packaging/test_packaging.py` (5 tests), described below.

The service gate harness now builds from the committed Dockerfile, so one copy of the Dockerfile exists (its `DOCKERFILE` string and base constants were deleted, and its container port moved to 8083). The artifact classification table and its golden file gained three rows, one each for `.dockerignore`, `Dockerfile` and `compose.yaml`, as runtime paths of the `missions-packaging` profile. Two conformance tests changed: the Missions gate test now lists the three packaging names as reviewed, and the selector test uses `Dockerfile.bak` and `docker-compose.yaml` as the unreviewed names that still block. It is a mixed commit (`Class: governance, tooling, runtime`; 10 files, 376 insertions and 47 deletions, as the handoff's commit output reports). No contract artifact changed, and the commit supplies no registry, orchestration or Mission Control publication.

The lead developer accepted all five design points on 2026-10-13, as the Job record quotes: the minimal scope, compose on the existing external Oracle network with credentials from the environment, port 8083, the non-root user, and one copy of the Dockerfile with a new packaging gate.

## Runtime evidence

The authenticated checkpoint handoff for the exact approved transaction records these checks, all exit 0, none reused. The profile derived for the manifest was `governance+missions-data+missions-packaging+missions-service+tooling`.

| Check | Retained duration | Observation |
| --- | --- | --- |
| Staged whitespace | 0.053 s | Exact candidate whitespace passed |
| Continuity | 12.616 s | Pre-commit recovery, links, checkpoint/evidence and frozen invariants passed |
| Checkpoint selector | 35.674 s | 39 tests of `test_checkpoint_scope.py` |
| Classification tests | 2.451 s | 55 tests |
| Missions offline contract | 0.298 s | XSD, fixture and 1.1 compatibility probes passed |
| Missions data | 71.500 s | Oracle acceptance; the data slice only |
| Missions service | 111.890 s | 33 tests (`Ran 33 tests in 111.069s`), now through the committed Dockerfile |
| Missions packaging | 38.494 s | 5 tests (`Ran 5 tests in 37.890s`) |
| Checkpoint invariants | 99.327 s | 83 tests, flagged by the tool as faster than its 20-run mean of 264.4 s |
| Commit metadata | 12.554 s | 21 tests |
| Missions gate tests | 1.998 s | 11 tests |

The retained durations add up to about 387 s. The handoff records no wall-clock total for the prepare, so none is claimed. The checkpoint estimate was partial: an expected 444 s, a lower bound because `missions-packaging` had no history and `missions-service` had thin history.

The packaging gate runs through compose against the existing, reviewed Oracle container, with a disposable schema and a read-only login, a unique image tag, project and container name and an ephemeral loopback port, cleaned up at the end. Its five tests:

1. Both bases are pinned by digest in the committed Dockerfile, the user, port and environment lines are as designed, the harness keeps no copy, and the `.dockerignore` and the credential interpolations are as designed.
2. `docker compose config` is valid, names only the service, publishes loopback only, joins the Oracle network as an external network and the other as an ordinary bridge, keeps its pinned defaults, and fails for each credential both missing and empty.
3. The image builds from the committed files (Maven verify) and runs as UID and GID 10001.
4. Compose starts the service on the Oracle network, `GET /missions` answers with a schema-valid list of 31 missions, and `down` removes only what the project created and leaves Oracle and its network as reviewed.
5. An invalid `MISSIONS_PORT`, `MISSIONS_BIND_HOST` or `MISSIONS_DB_SCHEMA` makes the container exit non-zero with the message of `Config`.

The API matrix stays in the service gate. A count of `def test_` in the committed gate file agrees with the sealed total of 5.

Figures the implementation worker reported in its Job notes (measurements outside the seal; one machine; advisory): the packaging gate on its own took 51.5 s, of which the Oracle schema load and login 14.2 s, the image build with Maven verify 21.2 s with a warm cache, compose up until ready 4.0 s and each bad-configuration case about 1.1 s. The sealing run's own phase timings, retained in the handoff output, were 14.9 s, 3.5 s (the build layers were cached), 5.0 s and 1.2 s, 1.4 s and 1.4 s, with the class total 37.9 s. The sealing run of the service gate read 111.9 s against 86.6 s in the previous checkpoint's seal; the retained output shows the same 33 tests, and this log does not explain the difference. The sealing run observed `Oracle 18.0.0.0.0 / AL32UTF8` in the retained output of the data, service and packaging checks. The gates do not echo the Maven test summary, so no Maven count is claimed. No performance claim is made beyond these timings.

## Verification and continuity boundary

The sealed review (prepared digest `86d650d91259156ac44ba726396ec65d8e369586a131e71f4ba4e076a6a5bbbd`) was approved by the lead developer's selection of Approve in the implementation worker's session, recorded by the handoff as an interactive-control decision, after the lead developer's go at the preview. The tool verified the commit: parent, tree cf41486 (a tree, not a commit), message SHA256 `79b8612e6514583593c56757c869336eda7d79486bec959da983c7c27fbe92ef` (as the handoff records it) and the result as the commit named above. Worker metadata on the runtime commit is Anthropic Claude Code [claude-sonnet-5-5]; this attribution describes the runtime execution.

Post-commit continuity failed with exit 1 after 11.6 seconds: `Stale implementation checkpoint: runtime history has advanced`. Progress still named the write service checkpoint and no matching indexed log existed. That is the expected runtime-record obligation, not continuity PASS and not completed integration. This follow-up updates [Progress](../docs/PROGRESS.md) and the [index](README.md); its fresh continuity evidence and exact approval remain separate from the runtime evidence above. Integration and cleanup of the mission worktree follow under the guarded lifecycle; this narrative supplies no approval or cleanup authority.

## Observations and limits

- The comment in `Main.java` still says that packaging into a WAR and image is a later slice. It is a runtime file and out of scope for a records commit; the implementation worker reported it, and a later runtime change owns the fix. The write service section of the component README likewise still says that packaging belongs to the packaging slice, as the historical text of that checkpoint; the new section describes the packaging.
- The service gate and the packaging gate each use a disposable schema and login in the existing Oracle container; the gates did not remove or recreate the container `starfleet-missions-data-20261009`.
- The open questions parked for the Coordinator (the 50-byte reference limit answering 500, the 32 against 33 service tests of an earlier run, and the header error body) are not part of this slice and are not settled here.

This is the packaging slice only. It is not a registry or image publication, orchestration beyond compose, Mission Control publication, deployment of the service login itself, Personnel mapping, manual lead developer acceptance or contract freeze, and it claims nothing about behavior no check covered. The Job notes record no failed attempts of the gate, and this log does not claim there were none. The Plan's projection of Missions status is not changed by this follow-up.
