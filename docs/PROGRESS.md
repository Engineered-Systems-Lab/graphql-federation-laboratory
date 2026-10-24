# Progress

Progress records what is verified now, with no task lists and no history; history is in [devlog entries](../devlog/README.md) and in Git, direction is in [Plan](PLAN.md). Specifications, decisions and evidence stay in their owning documents, and Git and those sources outrank this page.

## Current state

The laboratory was imported from the lab at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66` into a repository started from the Comitas template at template commit `733f65a11f2d2639c7015f6c4b491712773db50a`; its governance is now Comitas release 0.5.0. The lab stays as the archive of everything not carried. The state below is the one the lab verified at that commit, each part with the devlog entry that records its last checkpoint there; this repository has not run the services again since the import.

### The systems

- **Crew & Personnel v1** ([specification](CREW-PERSONNEL-V1.md)): the read-only Java SOAP service with datasets 001, 002 (the default) and the released 800-person dataset 003. Its manual acceptance passed on 2026-09-30 as reported by the lead developer, and the 003 release was commissioned 18 of 18 ([commissioning](../devlog/2026-10-01T0246Z-crew-personnel-manual-commissioning.md), [003 release](../devlog/2026-10-01T2048Z-personnel-003-runtime-release.md)). It is deprecated and frozen ([D050](../project-governance/DECISIONS.md#d050---crew--personnel-v1-is-deprecated-and-frozen-2026-10-21-accepted)): it stays readable and runnable as a reference, and no new work builds on it.
- **Personnel v2** ([design](PERSONNEL-V2.md), [validation](PERSONNEL-V2-VALIDATION.md)): the Java SOAP service with stable identity alongside v1, and the large snapshot of 1,000 people ([large snapshot](../devlog/2026-10-19T0134Z-personnel-v2-large-snapshot-runtime-checkpoint.md)).
- **Missions** ([design](MISSIONS-V1-DESIGN.md)): contracts 1.0 and 1.1 (frozen), the Oracle schema and the dataset releases 1.0, 1.1 and 1.2, the Java read and write service (GET, POST and PUT; an oversized reference is 422) and its packaging as an image with a compose file ([release 1.2](../devlog/2026-10-20T0044Z-missions-release-1-2-runtime-checkpoint.md)).
- **Assets** ([design](ASSETS-V1-DESIGN.md)): contract 1.0 (frozen) with nine named kinds and contract 1.1 with native identifiers and `PATH_NOT_FOUND`, the dataset releases 1.0 and 1.1, the read-only Python service on PostgreSQL 17 and its packaging ([contract 1.1](../devlog/2026-10-15T1920Z-assets-contract-11-runtime-checkpoint.md)).
- **GraphQL Federation** ([design](FEDERATION-DESIGN.md), [integration notes](INTEGRATION-NOTES.md)): the shared library and the four adapters, the mapping releases 1.0 to 1.3, the Apollo and Cosmo routers on the same four subgraphs with the router-neutral shared acceptance suite, question 6 under its final rules, the Personnel adapter's snapshot cache, introspection through both routers and the plain mapping lookups kept out of the supergraph. The last runtime checkpoint of the lab is lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73` ([plain mapping lookups](../devlog/2026-10-21T0424Z-mapping-lookups-runtime-checkpoint.md)). Not built: Hive, a registry, orchestration.
- **Abstraction ladder study** ([report](AGENT-STUDY-REPORT.md)): Abstraction ladder study 1, with the scored runs study-1 (320 runs) and gamma-prime-1 (64 runs) analysed; the raw transcripts and bundles stay outside the repository and are cited by checksum ([analysis](../devlog/2026-10-21T1531Z-agent-study-analysis-and-gamma-prime.md)).
- **Future SOA/BPM** ([requirements](FUTURE-SOA-BPM-REQUIREMENTS.md)): a responsibility boundary and work-in-progress requirements; nothing is implemented.
- **Operations** ([service scripts](SERVICE-SCRIPTS.md)): read-only wrappers in `uss-enterprise/scripts/` for looking at a running service.

### What this repository has verified

- Crew & Personnel v1 came in through the checkpoint workflow (commit `bb1231475c7be41a3c33a28825249db91e889b29`). Personnel v2, Missions, Assets, the service scripts, the federation layer and the study came in as set-up commits under the bootstrap exception of [D051](../project-governance/DECISIONS.md#d051---a-narrowly-scoped-bootstrap-exception-for-importing-the-labs-code-content-2026-10-22-accepted); before each of them every check its profile selects, the runtime gates included, ran by hand on its exact tree and passed. One more set-up commit started the recovery chain ([D052](../project-governance/DECISIONS.md#d052---one-set-up-commit-to-start-the-recovery-chain-2026-10-22-accepted)), and the history was rewritten once to keep the lead developer's email private ([D053](../project-governance/DECISIONS.md#d053---the-commit-identity-is-rewritten-once-to-hide-the-lead-developers-email-2026-10-23-accepted)). The [recovery-chain entry](../devlog/2026-10-22T2342Z-recovery-chain-adopted.md) lists the commits.
- The frozen set of 168 files (all of Crew & Personnel v1, the frozen Missions and Assets contracts and fixtures, and the study's corpus and guide) is pinned by checksum in the frozen manifest and compared by the continuity check.
- No service has been run here since the import, and no manual acceptance is recorded in this repository.

## Recovery facts

These current-state fields keep the exact table format consumed by [continuity verification](../governance/COMMAND-CONTINUITY.md) and the [v1 reconstruction contract](../governance/config/reconstruction-contract-v1.json).

| Fact | Value |
| --- | --- |
| service | Imported, not recorded as running: Personnel v2, Missions, Assets and the federation layer are on the runtime boundary |
| manual_acceptance | Not recorded |
| implementation_checkpoint | 94f7e34494876b2953ee099b1b2a7653f380d91d |
| next_authorized_action | None recorded here: each action requires its own applicable checkpoint authorization |

A project that declares a runtime boundary in the classification table also adds an `implementation_checkpoint` row (a full Git SHA) and the matching fact in the reconstruction contract; see [Command continuity](../governance/COMMAND-CONTINUITY.md#adopting-the-recovery-chain). Record, governance and tooling transactions do not advance the implementation checkpoint.
