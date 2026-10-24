# Personnel dataset 003 is released for the runtime

Date: 2026-10-01T20:48Z
Subject: Immutable 800-person Dataset 003 released for Personnel runtime
Status: Historical / non-normative
Lab checkpoint: lab commit `03abf8c17c1a78dec88885fdc77392577a2ade9a`
Provenance: Git committer timestamp `2026-10-01T16:48:19-04:00` (2026-10-01 20:48:19 UTC), converted to the prescribed UTC minute. This dates the commit, not acceptance calls. The lead developer's 18/18 commissioning result is reported evidence from the branch-repair request; exact call times were not supplied.
Migrated from lab log SD-2026.274-2048Z; originally written in the lab on 2026-10-01 (lab commit `cf114eb821e76a61cbc2311443681c2e2b466e6b`).

## Meaningful transition

Personnel now explicitly registers and eagerly validates the released nine-file `crew-v1-large-003` package containing 800 records before endpoint publication. Dataset 002 remains default. The approved commit was fast-forwarded into main, with a separate Missions stream continuing from that checkpoint. Missions design material was excluded from the 28-file Personnel commit.

Parent: lab commit `b58c15c7361acee76e8b0a7e03b05188b9b6e53c`. Exact commit subject: **Release crew-v1-large-003 for Personnel runtime**. The authorized transaction was `personnel-003-e0c0045187a2`; its full message, parent, tree and manifest were verified after execution. Frozen contracts/fixtures and the proposal/generator were preserved. The branch repair retained all original working-tree file bytes, backed by a separately verified complete pre-repair archive.

## Evidence and limits

- Retained pre-commit evidence in the [003 validation addendum](../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md#released-003-runtime-validation-2026-10-01): 87 Java tests, 106 Python tests, released-package validation, root validation and built-JAR resource/startup/loopback acceptance passed. These broad suites were not rerun for branch repair or this follow-up.
- Picard commissioning reported by the lead developer: PASS, 18/18. This is human-reported evidence; the follow-up worker did not execute or independently observe those calls.
- Fresh branch-repair checks verified raw release hashes, exact staged scope/message/tree, whitespace, pre-commit continuity and byte-for-byte preservation. The immutable commit metadata and exact approved message were independently rechecked during this follow-up.
- The actual immediate post-commit continuity result was **FAIL: Stale implementation checkpoint: runtime history has advanced**. The runtime commit necessarily preceded its SHA-bearing Progress/log record. This was the narrowly bounded continuity-follow-up-pending phase, not a passing check.
- Proposed Progress and indexed-log records were checked with continuity verification in an isolated bundle-derived clone at this checkpoint; that verification passed. This proves the proposed records, not that they have been applied or committed in the source repository. No follow-up commit or push was performed.
- Docker limitation remains as recorded: the configured `desktop-linux` daemon pipe was absent. No new container build, Linux execution, image-resource inspection or container smoke is claimed.

The original validation report, its anchored September 30 completion section, and all older devlog entries remain unchanged. Their contemporary uncommitted wording and earlier counts are historical. [Progress](../docs/PROGRESS.md) owns current state; this log is non-normative. The unchanged historical completion evidence remains the continuity contract's source; later 003 results are separately recorded in the addendum.
