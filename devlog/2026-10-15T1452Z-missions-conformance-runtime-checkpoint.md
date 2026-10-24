# Missions conforms on oversized references and the XML error body

Date: 2026-10-15T14:52Z
Subject: Committed conformance fix of the Missions service: an oversized reference answers 422, a container-level refusal of a control character in a header gets the XML error body, and the stale packaging comments are corrected
Status: Historical / non-normative
Lab checkpoint: lab commit `d7a25b9d808fb7657c127bea8faf7573e5c1cec6`
Provenance: Git committer timestamp `2026-10-15T10:52:45-04:00` (2026-10-15 14:52:45 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the earlier conversation that decided the content or this later record preparation. The transaction was approved by the lead developer's typed go at the preview (early conditional approval, receipt bound to prepared digest `6eec7d1f68f42f0ae510e893c567982000a001ba1c2fdcec9f0f07ae6c3a6b51`), which the tool accepted because the sealed result equalled the previewed candidate and every check passed. The same worker that made the commit prepared this record, from the immutable commit, its message, the retained authenticated handoff and the Job record; the checks below are the retained execution evidence of that transaction, and the worker's own earlier runs are marked as such.
Migrated from lab log SD-2026.288-1452Z; originally written in the lab on 2026-10-15 (lab commit `4419d0774bde324744fdf40a08e71cec7e2d3682`).

## State transition

The commit is the first Missions change after the packaging checkpoint, on the owned branch `tx/missions-conformance`, parent lab commit `9a9002058a8fe7b0559e1e15fc984fe52d7133df`, tree e8bd51f (a tree, not a commit), 14 paths, +271/-26. Exact subject: **Refuse an oversized Missions reference with 422 and give container refusals the XML error body**. It is a conformance fix of the existing service. The XSD does not change and no error code is added, so it is not a new contract version.

- **The oversized reference.** A valid reference longer than 50 UTF-8 bytes (the commander, every crew, participant and asset member, and the headers `X-Starfleet-User` and `X-Starfleet-Ordered-By`) now answers 422 `DOMAIN_VALIDATION_FAILED` with the XML error body and a message that the reference exceeds the storage capacity. Nothing is stored or truncated and the clock is untouched. The check counts bytes, never characters, because the columns are `VARCHAR2(50 BYTE)`. Before this commit the write failed in the database and answered 500 `INTERNAL_ERROR`, which the earlier checkpoint log recorded as a known limitation and the design said not to map. The design paragraph and the 422 row of its error table are amended, and the [D027 oversized reference extension](../project-governance/DECISIONS.md#d027-oversized-reference-extension-2026-10-15) records the decision with its audit row and [rationale](../project-governance/RATIONALE.md#missions-oversized-reference-d027-oversized-reference-extension). The lead developer's words are quoted there.
- **The control-character headers.** Tomcat refuses a control character in a header value (U+000B, U+000C, U+001C to U+001F, DEL) before the application runs and used to answer its own HTML 400. A new `XmlErrorReportValve`, installed on the embedded host by `Main`, gives that 400 the contract's XML body with `INVALID_REQUEST`. Only a 400 without a body is changed; any other container status keeps Tomcat's page.
- **The test count.** The service gate discovers 33 tests (8 read, 25 write) from files that define every test unconditionally. The earlier checkpoint log noted a first run after an Oracle restart that counted 32 and did not explain it. A run on 2026-10-15 right after restarting the Oracle container counted 33, so the count does not depend on a cold start. The cause of the 32 was not reproduced; the most likely explanation, that the suite gained its last test between those runs, is an inference. The README says so.
- **The stale comments.** The comment in `Main.java` and the sentence in the README's read-service section that called packaging a later slice now point to the committed image and compose file.

The commit also adds unit tests for the byte count, the reference check, the actor headers and the valve (which runs a real embedded Tomcat), and changes the write acceptance gate: the oversized reference asserts 422 for every reference field and both actor headers, and every control character asserts the XML 400 for POST and PUT. The schema comment that says "capacity 50" was not changed: it is byte-identical to the immutable release 1.0 `schema.sql`.

The numbered-decision requirement of the Job named G029, which is the decision-record rule; the decision itself is recorded as a dated extension of D027, the owner of the schema and dataset extension whose wording it supersedes.

## Runtime evidence

The authenticated checkpoint handoff for the exact approved transaction records these checks, all exit 0, none reused. The derived profile was `governance+missions-data+missions-service`.

| Check | Retained duration | Observation |
| --- | --- | --- |
| Staged whitespace | 0.1 s | Exact candidate whitespace passed |
| Continuity | 15.3 s | Pre-commit recovery, links, logs, checkpoint/evidence and frozen invariants passed |
| Missions offline contract | 0.3 s | XSD 1.0 surface, fixtures, and the 1.1 compatibility probes passed |
| Missions data | 70.6 s | 12 tests (`Ran 12 tests in 69.869s`); the data slice only |
| Missions service | 83.6 s | 33 tests (`Ran 33 tests in 82.683s`), including the changed write gate |

The handoff records no wall-clock total for the prepare, so none is claimed. The estimate shown at the preview was about 2 min 33 s, measured on this machine.

Figures from the worker's own runs outside the seal (advisory): `mvn verify` ran on the host before the preview, and the service gate once before it, with the Maven summary of the image build reading 89 tests, no failures, errors or skips; a count of `@Test` annotations in the committed test files agrees (89), five more than the 84 of the write checkpoint. The sealing run does not echo the Maven summary, so the Maven count is not part of the sealed evidence. The worker started the stopped Oracle container `starfleet-missions-data-20261009` to run the gates; the gates did not remove or recreate it.

## Verification and continuity boundary

The tool verified the commit: parent, tree e8bd51f, the message SHA-256 `73a75792dc29f77781dfa9fd03e500c32bde959dc2622893289921e7c70431c9` and the result as the commit named above. Worker metadata on the commit is Anthropic Claude Code [claude-sonnet-5-5].

Post-commit continuity failed with exit 1 after 10.4 seconds: `Stale implementation checkpoint: runtime history has advanced`. That is the expected runtime-record obligation, not continuity PASS and not completed integration. This follow-up updates [Progress](../docs/PROGRESS.md) and the [index](README.md); its continuity evidence and exact approval are separate from the runtime evidence above. Integration and cleanup follow under the guarded lifecycle; this narrative supplies no approval or cleanup authority.

## Observations and limits

- The mission was first opened on a base before the `assets_amendment` landing and rebuilt on the advanced main at the Coordinator's request, when the lead developer revised the order of work: the worker saved its 14 files outside the worktree, removed its own worktree and branch, created them again and reapplied the files, which no upstream change touched. The earlier preview was discarded and a new one was shown and approved.
- A container-generated error other than a 400 without a body still shows Tomcat's page.
- Not changed and not claimed: the dataset release 1.1 idea (references to the Assets kinds), any XSD change, a new error code, the packaging gate (the Dockerfile and compose file are untouched, so the packaging gate was not selected), manual lead developer acceptance and a contract freeze.
