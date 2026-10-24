# The Missions schema and dataset reach their runtime checkpoint

Date: 2026-10-09T11:48Z
Subject: Oracle schema, immutable release 1.0 and compatible Missions contract 1.1
Status: Historical / non-normative
Lab checkpoint: lab commit `20e46c80b725dacfd1dd22df2a9d52eb502048cc`
Provenance: Git commit time 2026-10-09T07:48:18-04:00 (11:48:18 UTC on October 9, 2026) establishes this checkpoint's minute. A separately delegated fresh records worker inspected the immutable commit, runtime-anchored component report and actual local checkpoint handoff. The runtime checks below are retained execution evidence from the implementation worker, not rerun by this records worker.
Migrated from lab log SD-2026.282-1148Z; originally written in the lab on 2026-10-09 (lab commit `e758730e116120654898371a6b7aebfe0a04c2d2`).

## State transition

The [Missions design](../docs/MISSIONS-V1-DESIGN.md) amendment was promoted at lab commit `fec63e9b664f3f84bc44c694507b2b431d05c953`. The runtime checkpoint adds the six-table Oracle 18c schema, local integrity guards, append-only audit, two bounded sequences and a transactional clock helper. Compatible contract 1.1 adds MAINTENANCE in the existing namespace; published 1.0 remains unchanged.

The immutable release 1.0 contains 31 missions and 101 changes. Its independently keyed SHA256 counter recipe uses master seed 1701, curated inputs and archived authoring sources. Explicit selected-release reset reloads frozen release bytes; it does not regenerate at startup or reset. Episode inspiration, supplied stardates and lab adaptations remain distinguished by release provenance.

## Runtime evidence

The [runtime-anchored acceptance report](../uss-enterprise/missions/README.md#schema-and-dataset-acceptance-2026-10-09) owns the observed Oracle XE 18.4.0.0.0 version_full (legacy version column 18.0.0.0.0), AL32UTF8, actual Python reset and Git Bash wrapper execution, complete loaded-value comparison, historical failures and acceptance limits. The approved Linux/amd64 image used a dedicated ownership-labeled internal bridge with no external routing, published host ports or host mounts. Missions remained stopped.

The authenticated checkpoint machinery's retained handoff reports five fresh pre-commit checks, all exit 0, with no evidence reuse:

| Check | Retained duration | Observation |
| --- | --- | --- |
| Staged whitespace | 0.058655 s | Exact candidate whitespace passed |
| Continuity | 9.112091 s | Pre-commit recovery, links, checkpoint/evidence and frozen invariants passed |
| Artifact classification | 1.270371 s | 48 tests passed |
| Missions offline contract | 0.173169 s | 1.0 probes, old fixtures under 1.1 and MAINTENANCE-only addition passed |
| Missions data | 43.810356 s | 12 tests passed, zero skips; Oracle and immutable-release slice only |

The component report separately records an earlier accepted full data run of 43.950 seconds; it is not the sealing run above. Oracle checks covered exact scalar/collection/audit values and release positions, append-only audit and identity, foreign-key/reference constraints, zero/absent/maximum decimals, atomic rollback, transactional-clock rollback and two-session serialization, sequence exhaustion, reset and stopped-service guards, and supplementary Unicode round-trips. Release checks covered archived reproduction, independent category draws, tamper/history corruption rejection and code-point bounds. Disposable acceptance schemas were cleaned; the owned database was retained for follow-on work.

## Failures preserved

Network-none attempts failed before initialization through hostname resolution, a native resolver SIGSEGV, and rejected loopback mapping. The lead developer approved the internal-bridge revision. Subsequent failures included the generated admin password exceeding the image's supported length and SQLPlus OS-user execution; values were not recorded. The implementation also corrected an unpublished operator filename shadowing the standard library, Unicode literals, golden ordering, and two failed probes caused by RPAD display width and scientific sequence-value formatting. The anchored report preserves those observations and the later passing runs; they are not rewritten as uninterrupted success.

## Verification and continuity boundary

The runtime handoff records exact approval and tool verification of this commit, parent lab commit `fec63e9b664f3f84bc44c694507b2b431d05c953`, tree identity, and the 1,079-byte message with SHA256 `c42f27087b70c70ba891620b365f09b0cca29fd9cda02d06223e7e37efda4651`. Read-only Git inspection by this records worker matched those immutable facts and the message bytes. Worker metadata on the runtime commit is OpenAI Codex [GPT-6.1 Sol Medium]; this attribution describes the retained runtime execution.

Post-commit continuity failed with exit 1 after 4.883258 seconds: `Stale implementation checkpoint: runtime history has advanced`. Progress still named the earlier contract checkpoint, and no matching indexed log existed. That is the expected runtime-record obligation, not continuity PASS or completed integration. This follow-up updates [Progress](../docs/PROGRESS.md) and the [index](README.md); its fresh continuity evidence and exact approval remain separate from the runtime evidence above. Git and the guarded lifecycle establish eventual promotion; this narrative supplies no approval or cleanup authority.

## Limits

This is schema/dataset acceptance, not Java REST/JDBC, HTTP mutation, complete deployment packaging, Personnel mapping, manual lead developer acceptance or contract freeze. Physical ASCII external references have a 50-byte capacity despite the unbounded wire grammar. Oracle DDL prevents whole-reset rollback; the reset service guard covers only the named deployment. Objective audit history is not a complete semantic snapshot. Existing immutable Personnel artifacts and published Missions 1.0 remain unchanged. The separate guidance/conventions preview is not part of this continuity slice.
