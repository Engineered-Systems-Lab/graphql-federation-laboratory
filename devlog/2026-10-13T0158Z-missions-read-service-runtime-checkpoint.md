# The Missions read service reaches its runtime checkpoint

Date: 2026-10-13T01:58Z
Subject: Java read service for Missions (list, get with ETag, change log) and its service acceptance gate
Status: Historical / non-normative
Lab checkpoint: lab commit `05d89908965db7c84607c9d926770ef358afe3f2`
Provenance: Git commit time 2026-10-12T21:58:24-04:00 (01:58:24 UTC on October 13, 2026) establishes this checkpoint's minute; the local date differs from the UTC date. A separately delegated fresh records worker inspected the immutable commit, its message, the component README section committed with it and the retained authenticated checkpoint handoff, and read the implementation worker's Job notes. The runtime checks below are retained execution evidence from the implementation worker; the records worker did not rerun them.
Migrated from lab log SD-2026.286-0158Z; originally written in the lab on 2026-10-13 (lab commit `42fe41b2b65feb1c1ce811496633775f63693b65`).

## State transition

Parent lab commit `f275d99749a1b1bf9e598510090e83ff97665f22`. The commit adds the first Missions Java service under `uss-enterprise/missions`: a Java 17 / Maven project that generates its XML types from the frozen [1.1 contract](../uss-enterprise/missions/contracts/missions-v1.1.xsd) and runs on Jersey 2 and embedded Tomcat 9 with plain JDBC to Oracle 18c. It implements only the reads of the [Missions design](../docs/MISSIONS-V1-DESIGN.md): `GET /missions` (nine filters, paging, ordering), `GET /missions/{id}` with its strong ETag and `GET /missions/{id}/changes`, the Accept grammar and the 400, 404, 405, 406 and 500 mappings. Every response is validated against the schema before it is sent. POST and PUT answer 405 with `Allow: GET` until the write slice. The [component README](../uss-enterprise/missions/README.md#read-service-slice) describes the slice, its environment configuration and how to run the gate.

The same commit adds the first service acceptance gate and the build descriptor's row in the artifact classification table (runtime, `missions-service`), updates the independent golden file and changes the two tooling tests that had named `pom.xml` as blocked. It was therefore a mixed governance, tooling and runtime commit (`Class: governance, tooling, runtime`; 25 paths, 1,641 insertions and 5 deletions).

## Runtime evidence

The authenticated checkpoint handoff for the exact approved transaction records these checks, all exit 0, none reused:

| Check | Retained duration | Observation |
| --- | --- | --- |
| Staged whitespace | 0.046 s | Exact candidate whitespace passed |
| Continuity | 9.674 s | Pre-commit recovery, links, checkpoint/evidence and frozen invariants passed |
| Checkpoint selector | 38.447 s | 39 tests |
| Artifact classification | 1.071 s | 55 tests |
| Missions offline contract | 0.191 s | XSD, fixture and 1.1 compatibility probes passed |
| Missions data | 46.375 s | 12 tests against Oracle; the data slice only |
| Missions service | 32.423 s | 8 acceptance tests; the implemented read slice only |
| Checkpoint invariants | 339.658 s | 83 tests |
| Commit metadata | 16.007 s | 21 tests |
| Missions gates | 1.033 s | 11 tests |

The whole prepare took 8 min 16 s, as the implementation worker measured it; the checkpoint estimate was partial (at least 7 min 01 s, with no history yet for the Missions data and service checks).

The service gate builds a uniquely tagged image whose build runs `mvn verify` on JDK 17, loads release 1.0 into a disposable schema of the existing, reviewed Oracle container (reused unchanged), creates a disposable read-only login, starts the service on an ephemeral loopback port joined to the internal Oracle network, and compares every mission, list page, filter, change log and error response with the release data and the schema. It also runs a second container with a wrong password to check that a database failure is a clean 500. It removes every container, image, login and schema it created. The eight tests cover every mission with its strong ETag, list order and paging, every filter and their conjunction, the change log order and paging, the error mapping, 405 with only the supported `Allow`, the Accept negotiation and a database failure answered as a clean 500.

The implementation worker reports 27 JUnit tests in the Maven build (Accept parsing, query validation, route recognition, page arithmetic and the XML codec); a count of `@Test` methods in the committed test files agrees, but the gate does not echo the Maven summary, so this log retains that count as reported, not as a separately observed result. The same worker measured the service gate outside the seal at 62.3 s cold and 35.0 s warm (Oracle schema load and login 9.4 s, image build with Maven 34.5 s cold or 10.7 s warm, containers ready 4.3 s); the sealing run's 32.4 s is a warm run. Both sets of figures describe one machine and are advisory.

## Verification and continuity boundary

The sealed review was approved by the lead developer's selection of Approve in the implementation worker's session (recorded by the handoff as an interactive-control decision), and the tool verified the commit: parent lab commit `f275d99749a1b1bf9e598510090e83ff97665f22`, tree 792a4a5992c76743fea65ff61a0b292621cb8e50 (a tree, not a commit), message SHA256 `6b098b2905d7da91bfd78d61a5d54c8fba782e1f8e55ca5f1af5a78dceb28664`, empty post-commit status. Worker metadata on the runtime commit is Anthropic Claude Code [claude-sonnet-5-5]; this attribution describes the runtime execution.

Post-commit continuity failed with exit 1 after 7.206 seconds: `Stale implementation checkpoint: runtime history has advanced`. Progress still named the schema/dataset checkpoint and no matching indexed log existed. That is the expected runtime-record obligation, not continuity PASS and not completed integration. This follow-up updates [Progress](../docs/PROGRESS.md) and the [index](README.md); its fresh continuity evidence and exact approval remain separate from the runtime evidence above. Integration and cleanup of the mission worktree follow under the guarded lifecycle; this narrative supplies no approval or cleanup authority.

## Observations and limits

An unknown path answers a bodyless 404 because the frozen contract defines no body for it. The lead developer was shown this gap at the environment preview and did not object; it is reported to the Coordinator as a contract question and is not settled here. The implementation worker also observed that Jersey and Tomcat render `Content-Type` as `application/xml;charset=UTF-8` without the space the design text shows; the two are semantically equal and the gate compares them whitespace-normalized.

This is the read slice only. It is not HTTP mutation (the write slice), the packaging slice (WAR, image, compose, the service container name), nonroot packaging, Personnel mapping, manual lead developer acceptance or contract freeze. The service gate reuses the existing owned Oracle container and a disposable schema, and builds its Docker context in a temporary directory; no `Dockerfile` is committed. The Job notes record no failed attempts of the gate, and this log does not claim there were none. The Plan's projection of Missions status is not changed by this follow-up.
