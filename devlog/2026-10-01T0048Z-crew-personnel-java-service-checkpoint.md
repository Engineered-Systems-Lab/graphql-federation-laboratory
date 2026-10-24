# The Crew & Personnel Java SOAP service reaches its implementation checkpoint

Date: 2026-10-01T00:48Z
Subject: Native Java SOAP runtime, portability and governance completion
Status: Historical / non-normative
Lab checkpoint: lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`
Provenance: Git author and committer timestamps both `2026-09-30T20:48:55-04:00`, equivalent to `2026-10-01T00:48:55Z`; seconds omitted. This is the commit time, not the time of every validation run.
Migrated from lab log SD-2026.274-0048Z; originally written in the lab on 2026-10-01 (lab commit `64d395b4304cc3ddd86be37a248f63f8d75272e3`).

## State transition and evidence

The checkpoint completes the runtime transition deferred by the [log index](README.md): Java 17/CXF 4.2.3 WSDL-first SOAP service, immutable fixture loading, controlled profiles, pinned Docker deployment, and documentation authority. Its parent is the [frozen executable contract checkpoint](2026-09-30T1800Z-crew-personnel-frozen-executable-contract.md). Git shows no frozen specification, contract or fixture changes between those checkpoints.

The committed [completion report](../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md#governance-and-sha-256-portability-completion-2026-09-30) records 35 passing Java tests, a passing offline suite, a fresh Docker build, and four normal plus three unavailable SOAP calls. These are pre-commit execution findings anchored by the commit, not checks newly executed by creating this log. The report records CRLF-only hash portability, unchanged parser input, Java code-point validation, and existing offline raw-byte/.NET limitations.

## Later-context boundary

This log was added during command-continuity work because the index requires logging the completed runtime checkpoint. It preserves the report's contemporary unstaged/uncommitted claims as history; the commit establishes their later completion. The continuity-task starting Git inspection found no tracked changes and only untracked `work/`; no transient audit files were used as recovery evidence. Manual lead developer acceptance is pending as recorded in [Progress](../docs/PROGRESS.md); automated smoke calls do not establish human/manual lead developer acceptance. [Progress](../docs/PROGRESS.md) remains authoritative for current state and next actions.
