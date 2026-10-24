# The Missions write service reaches its runtime checkpoint

Date: 2026-10-13T20:00Z
Subject: Java write operations for Missions (POST and PUT) and their service acceptance gate
Status: Historical / non-normative
Lab checkpoint: lab commit `2b37ba96f079e517e979a240baa541256e578d77`
Provenance: Git commit time 2026-10-13T16:00:26-04:00 (20:00:26 UTC on October 13, 2026) establishes this checkpoint's minute. A separately delegated fresh records worker inspected the immutable commit, its message, the component README section committed with it, the retained authenticated checkpoint handoff and the implementation worker's Job notes. The runtime checks below are retained execution evidence from the implementation worker; the records worker did not rerun them, and the worker's own measurements are marked as reports.
Migrated from lab log SD-2026.286-2000Z; originally written in the lab on 2026-10-13 (lab commit `36d135840ce7075d592b2da634d407f592ffd37b`).

## State transition

Parent lab commit `5709f4ce852103c0a02e5d8a8306c674041e2741`, tree 1f7387129f0900f5af8c22900bdffda054e04d30 (a tree, not a commit). The commit adds the write operations of the [Missions design](../docs/MISSIONS-V1-DESIGN.md) to the read service of the [previous checkpoint](2026-10-13T0158Z-missions-read-service-runtime-checkpoint.md): `POST /missions` and `PUT /missions/{id}`, each one database transaction that ticks the reference clock, writes the mission, its collections and its audit event, and commits or rolls everything back. Per its message it adds the domain rules of the cost lifecycle with cancellation provenance, commander, outcome, duplicates and whitespace-only text (422), the `If-Match` handling (428, 412, 400), the required mutation headers with the audit summary decoded and stored as exact UTF-8, the Content-Type and XML encoding checks, secure XML parsing, the `Allow` list of each path for the 405 answers and a servlet guard that answers 415 for an unusable Content-Type of a mutation. The [component README](../uss-enterprise/missions/README.md#write-service-slice) describes the slice, the grants of the service login and the findings.

The commit also moves the image, schema, login and container handling of the read gate into a shared `service_harness.py` that builds one image per run, adds the write gate `test_write_service.py`, and makes the read gate expect the `Allow` list of each path. The README introduction, which still said that no Java REST service was supplied, now describes the current functionality, and the schema and dataset acceptance report is kept as written. It is a single-class runtime commit (`Class: runtime`; 32 files, 2,858 insertions and 329 deletions, as the handoff's commit output reports). No contract artifact, classification row or tooling path changed.

The lead developer decided the slicing on 2026-10-13, as the Job record quotes: POST and PUT together in one slice, the two open contract questions left as they are, and the README introduction fix bundled into this commit.

## Runtime evidence

The authenticated checkpoint handoff for the exact approved transaction records these checks, all exit 0, none reused:

| Check | Retained duration | Observation |
| --- | --- | --- |
| Staged whitespace | 0.078 s | Exact candidate whitespace passed |
| Continuity | 18.487 s | Pre-commit recovery, links, checkpoint/evidence and frozen invariants passed |
| Missions offline contract | 0.277 s | XSD, fixture and 1.1 compatibility probes passed |
| Missions data | 74.930 s | 12 tests against Oracle; the data slice only |
| Missions service | 86.574 s | 33 tests (the unittest summary in the retained output reads `Ran 33 tests in 85.848s`); the read and write classes in one process |

The whole prepare took 3 min 00 s, as the implementation worker reported; the checkpoint estimate was partial (at least 1 min 30 s, with too little history for the three Missions checks). The profile derived for the manifest was `missions-data+missions-service`.

The service gate builds one uniquely tagged image whose build runs `mvn verify` on JDK 17, then runs the read class and the write class against the existing, reviewed Oracle container with a disposable schema and login for each test class, on ephemeral loopback ports. The write class uses a login holding exactly the grants the README lists. A count of `def test_` in the committed gate files agrees with the sealed total (8 read, 25 write). The write checks cover every row of the error table, the cost matrix, cancellation provenance, the If-Match forms, the exact summary, the ETag advance, concurrency, rollback on a forced failure, sequence overflow and the `Allow` lists, per the commit message.

Figures the implementation worker reported in its Job notes (measurements outside the seal; one machine; advisory):

- Maven unit tests: 84 in all, of which 27 came from the read slice and 57 are new. The worker first wrote 38 and 46, then corrected itself from the Maven surefire reports. A count of `@Test` annotations in the committed test files agrees with 84; the gate does not echo the Maven summary, so this log retains the count as reported, not as a separately observed result.
- Service gate: 286 s for 32 tests on the first run after the Oracle container restart (cold), and 121.4 s for 33 tests on the second run (warm). The sealing run above is a third run with 33 tests in 86.6 s. The notes do not say why the first run counted 32; this log does not reconcile it. Warm phases reported: guard 0.6 to 0.9 s, schema load and login 17.5 s (read class) and 11.7 s (write class), image build with Maven 24.5 s (55.3 s cold), containers ready 5.5 to 5.7 s, read class 62.7 s, write class 58.7 s.

The sealing run observed `Oracle 18.0.0.0.0 / AL32UTF8` in the retained output of the data and service checks. No performance claim is made beyond these timings.

## Verification and continuity boundary

The sealed review (digest `34afa58c93414e490d14316b3326f577b5de7bae2388c4b1aee1d856b6aa7bc5`) was approved by the lead developer's selection of Approve in the implementation worker's session, recorded by the handoff as an interactive-control decision after the lead developer typed `approved` at the preview. The tool verified the commit: parent, tree 1f7387129f0900f5af8c22900bdffda054e04d30 (a tree, not a commit), message SHA256 `6262bbf3dfb2978569b2d66d0bd6ee3ebc6add22e145f14a932d80e4ec951a72` (recomputed from the commit object by the records worker) and an empty post-commit status. Worker metadata on the runtime commit is Anthropic Claude Code [claude-sonnet-5-5]; this attribution describes the runtime execution.

Post-commit continuity failed with exit 1 after 13.1 seconds: `Stale implementation checkpoint: runtime history has advanced`. Progress still named the read service checkpoint and no matching indexed log existed. That is the expected runtime-record obligation, not continuity PASS and not completed integration. This follow-up updates [Progress](../docs/PROGRESS.md) and the [index](README.md); its fresh continuity evidence and exact approval remain separate from the runtime evidence above. Integration and cleanup of the mission worktree follow under the guarded lifecycle; this narrative supplies no approval or cleanup authority.

## Observations and limits

The implementation worker's findings, each recorded in the README write section:

- Tomcat itself refuses a control character in a header value (U+000B, U+000C, U+001C to U+001F, DEL) with an HTML 400 page before the application runs, so the whitespace rule of `X-Starfleet-Audit-Summary` for those code points is proven by the unit tests only; the gate shows the 400. A custom error report valve would give them the XML error body; it was not done.
- Jersey parses the request Content-Type before any filter and answers a bare 400 for an unparseable value or a repeated header, where the contract says 415. The slice guards that in `MissionsServlet`: POST and PUT get 415 with the XML body, and other requests lose the unusable header and route normally.
- The design is silent on three cases, which the worker decided: a summary with U+FFFE or U+FFFF (valid UTF-8, not XML 1.0, and it would make the change log representation fail) is 400; a body above 8 MiB is 400; a repeated `X-Starfleet` header line is 400.
- The 50-byte physical capacity of the reference columns is unchanged. The design says a valid longer reference cannot fit, forbids truncation and forbids inventing a 400 or 422 mapping, and does not name the status. The service answers 500 `INTERNAL_ERROR` with nothing stored and the clock untouched, and the gate asserts that as the documented lab limitation. The worker flagged it, and this log reports it to the Coordinator as a possible contract question; it is not settled here.
- The read gate's sixth test used to assert 405 with `Allow: GET` for POST and PUT. It now asserts each path's own `Allow` list; the shared harness otherwise leaves its assertions unchanged.
- The Oracle container `starfleet-missions-data-20261009` was found in state Exited(255) after a Docker restart when the worker began, and the worker ran only `docker start` on it (healthy in about a minute). It was not removed, recreated or changed.

The two open contract questions of the read slice stay as the lead developer decided on 2026-10-13: an unknown path keeps its bodyless 404, and the service sends `application/xml;charset=UTF-8` without the space the design text shows; the gate compares the two whitespace-normalized. No frozen artifact changed.

This is the write slice only. It is not the packaging slice (WAR, image, compose, the service container name), nonroot packaging, Personnel mapping, manual lead developer acceptance or contract freeze, and it claims nothing about behavior no check covered. The service gate reuses the existing owned Oracle container and builds its Docker context in a temporary directory; no `Dockerfile` is committed. The Job notes record no failed attempts of the gate, and this log does not claim there were none. The Plan's projection of Missions status is not changed by this follow-up.
