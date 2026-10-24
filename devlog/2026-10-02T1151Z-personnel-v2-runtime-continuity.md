# Personnel v2 reaches its runtime checkpoint with its continuity follow-up

Date: 2026-10-02T11:51Z
Subject: Committed Personnel v2 runtime, bounded verifier recovery and separate continuity follow-up
Status: Historical / non-normative
Lab checkpoint: lab commit `5270c98d20102c1d1b38470ebe3df1563adbe369`
Provenance: Git committer timestamp `2026-10-02T07:51:19-04:00` (2026-10-02 11:51:19 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not acceptance calls or this later record preparation. Recovery/lifecycle context below was inspected during the October 2, 2026 America/New_York follow-up.
Migrated from lab log SD-2026.275-1151Z; originally written in the lab on 2026-10-03 (lab commit `f83c6ccf3fd859f2cac90a58b03a91bd0f5ec7e5`).

## Meaningful transition

Personnel v2 now exists as a separate Java 17/CXF SOAP component alongside unchanged v1, with common Get/List operations, stable personnel identity, exclusive crew/civilian details and two immutable snapshots showing Wesley's subtype transition. Missions retains independent identity semantics; no Missions work was restored or included.

Runtime parent: lab commit `100cdb22b13d61127d8a39adabbfdcab962d258e`. Runtime tree object: 19c660425f2bba2099f6dce37a0150a2e08b82b3. Exact subject: **Implement Personnel v2 with stable identity and validated container runtime**. Immutable Git metadata, current authoritative records and committed reports establish this transition; no new runtime implementation is part of this record transaction.

## Retained acceptance evidence and limits

The unchanged [Personnel v2 validation report](../docs/PERSONNEL-V2-VALIDATION.md) records 38 v2 Java tests, 87 v1 Java tests, initial full Python discovery of 112 tests, both offline validators, a pinned Linux container build with 38 passing tests, and 135 container HTTP/SOAP exchanges. Its later correction identifies the host JDK as Microsoft OpenJDK 17.0.20.1+1; the container bases remain pinned Temurin. Those are retained historical executions, not newly run Java/Docker/SOAP acceptance in this follow-up. The report preserves the initial Docker failure and subsequent successful completion separately.

No manual lead developer acceptance for v2 or contract freeze is established here. Historical v1 commissioning remains separate. The unchanged continuity contract still selects the September 30 completion section of the [v1 runtime report](../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md#governance-and-sha-256-portability-completion-2026-09-30); those historical counts must not be relabeled as v2 results. That report is anchored in the runtime commit. Frozen specification/contracts/fixtures remain unchanged.

## Later recovery and lifecycle context

The explicitly approved original Personnel transaction `a308ae222409e0142c92534cc9b40806` committed the runtime but stopped at `commit-attempted` because the verifier compared pre-staging residual status. It was never normally verified. Its original envelope SHA-256 is `00ebf4af187cd0b8ae2028748855d496860696fd980a10ee5e6b4957cc00351e`.

Separately approved repair lab commit `fecab630070f46068ca61000145866be61b6e3a7` achieved `repair-verified-continuity-pending`, not original Personnel verification or continuity PASS. Separately approved lifecycle lab commit `0e52266df9bb6658cde9bfd84682ca5193d737eb` then recorded the durable disposition and obligation in Progress and made operational checkpoint state disposable. Its exact parent/tree/message verification and successful guarded cleanup were checked against retained verification evidence and Git at follow-up start. Only the integrity key remained in the active scratch directory. Original Personnel/recovery metadata remained optional local incident evidence, not an active slot or an authoritative continuity dependency.

The live checker at follow-up start still failed with **Stale implementation checkpoint: runtime history has advanced**. That failure is preserved honestly. The present separately delegated Progress/index/log change is the first normal transaction after disposition; it does not reopen or retroactively verify either historical transaction. Normal continuity, Python regressions (including checkpoint/lifecycle tests), component offline checks and whitespace validation must pass before sealing. Exact G018 approval, commit verification and guarded scratch completion remain separate gates. A prepared working-copy PASS alone is not durable completion.

[Progress](../docs/PROGRESS.md) owns current state. No Docker backlog, Missions changes, runtime changes or push belong to this follow-up. Historical-record commits do not recursively require another devlog entry.
