# The Crew & Personnel design and dataset 001 are established

Date: 2026-09-30T16:54Z
Subject: Read-only Personnel contract design and canonical six-record Dataset 001
Status: Historical / non-normative
Lab checkpoint: lab commit `748c3bb987848b9757e5f4f5da806069685921ba`
Provenance: Git author and committer timestamps both `2026-09-30T12:54:10-04:00`, equivalent to `2026-09-30T16:54:10Z`; seconds omitted from the date.
Migrated from lab log SD-2026.273-1654Z; originally written in the lab on 2026-10-01 (lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`).

## State and evidence

This checkpoint first added `docs/CREW-PERSONNEL-V1.md` and D013-D015. Its parent, lab commit `d40be91584fb4a88a2d0e1ea40f585fd5b978c54`, contained the enterprise planning baseline but no Personnel specification. Dataset 001 was established here as six canonical records in the specification, not yet as an executable XML fixture.

The commit title says "Freeze Crew & Personnel v1 contract", but its specification, Decisions and Progress still describe a revised candidate with formal freeze pending. That discrepancy is retained: the checkpoint proves the design and records, but does not establish the exact approval time. The later frozen executable state is recorded in the [18:00 checkpoint](2026-09-30T1800Z-crew-personnel-frozen-executable-contract.md).

## Contract boundaries and significance

The design made Personnel a read-only Java SOAP/XML roster, with GetCrewMember and ListCrewMembers over SOAP 1.1 document/literal wrapped. It owned identity, descriptive facts, primary department/job, duty status and reporting relationships. Mission Operations owned participation and assignments; ACTIVE alone did not establish mission availability or permission. LDAP/accounts, maintenance, inventory, GraphQL and MCP were outside Personnel. D015 assigned external-ID mapping schema, releases, validation and interpretation to the shared Integration & Benchmark layer, with no name-based or numeric-identity inference.

D014 made crewId permanent across supported datasets, case-sensitive, never reused, preserving leading zeros and excluding CRW-0000. An omitted supervisor meant no supervisor recorded, without distinguishing absence from unknown. Present references had to resolve within the snapshot; self-reference and cycles prevented readiness. Inactive/cross-department supervisors and multiple roots were valid.

Contract namespace/version and immutable datasetVersion had distinct meanings. Changed content required a new datasetVersion, never reuse; versions implied no freshness. Lists sorted by crewId before pagination; defaults were offset 0 and limit 20. A version change between pages required discarding accumulated pages and restarting at offset 0. Explicit XML order, presence, whitespace and nil rules, separate negative coverage, and semantic XML comparison made the intended behavior precise before implementation.

## Canonical Dataset 001 as specified

`crew-v1-small-001` was deterministic without a generator. The specification recorded exactly:

| crewId | displayName | rank | department | positionTitle | dutyStatus | supervisorCrewId |
| --- | --- | --- | --- | --- | --- | --- |
| CRW-1047 | Jean-Luc Picard | CAPTAIN | COMMAND | Commanding Officer | ACTIVE | omitted |
| CRW-1048 | William Riker | COMMANDER | COMMAND | First Officer | ACTIVE | CRW-1047 |
| CRW-1049 | Geordi La Forge | LIEUTENANT_COMMANDER | ENGINEERING | Chief Engineer | ACTIVE | CRW-1048 |
| CRW-1050 | Data | LIEUTENANT_COMMANDER | OPERATIONS | Operations Officer | ACTIVE | CRW-1048 |
| CRW-1051 | Mara Venn | LIEUTENANT | FLIGHT_OPERATIONS | Shuttle Pilot | ON_LEAVE | CRW-1048 |
| CRW-1052 | Elias Renn | ENSIGN | ENGINEERING | Engineering Technician | INACTIVE | CRW-1049 |

The default list was specified to return six records; ENGINEERING returned CRW-1049 and CRW-1052, while MEDICAL returned none. Separate edge/negative cases were planned without changing this baseline.

## Contemporary decision wording

The following D013/D014 wording is preserved from Decisions to retain the superseded proposal and pre-freeze status; it is historical context, not current instructions. Only relative link destinations were adjusted for this location; the checkpoint version is available through Git.

| ID | Date | Status | Decision and rationale |
| --- | --- | --- | --- |
| D013 | 2026-09-30 | Superseded by D014 | Define Crew & Personnel v1 as a read-only Java SOAP/XML roster backed by an immutable synthetic fixture, with explicit crew keys, two read operations, deterministic pagination, and controlled failures. Keep LDAP, mission ownership, and external ID resolution outside this service. See [the v1 design](../docs/CREW-PERSONNEL-V1.md); WSDL/XSD and implementation remain pending. |
| D014 | 2026-09-30 | Accepted | Revise the [Crew & Personnel v1 contract candidate](../docs/CREW-PERSONNEL-V1.md) before formal freeze: crewId identifies the same person across all supported benchmark datasets, is never reused, and excludes CRW-0000; omitted supervisor means no supervisor recorded, while present references must resolve and remain acyclic. Allow inactive/cross-department supervisors and multiple roots. Distinguish contract namespace from immutable datasetVersion, require pagination restart on version change, and make no freshness inference. Specify complete XML occurrence, type, order, namespace, whitespace, and nil rules in documentation before XSD/WSDL/Java. Retain six canonical records plus separate deterministic negative/validation coverage and semantic XML comparison. Formal freeze and implementation remain pending. |

## Open choices recorded at the design checkpoint

The following open-choice list and contemporary guidance are preserved from Decisions at this checkpoint:

- Initial platform and exact component versions/deployment modes.
- Shared federation feature subset and treatment of unsupported features.
- Exact versions and libraries for the selected legacy stacks, native schema contracts, identifier mappings, adapter languages, and authorization scope.
- Literal seed, generator algorithm/version, reference clock, and dataset sizes.
- Workload mix, resource budgets, load levels, and numeric acceptance thresholds.

These later implementation/integration choices do not block freezing Crew & Personnel Contract v1; its documented contract decisions are resolved, with formal freeze pending. The baseline six-record fixture needs no generator.

Resolve these with a short decision entry including rationale and consequences. Environment observations belong in Progress; execution phases belong in Plan.

## Pending at this checkpoint

The specification and Progress explicitly said no service, WSDL/XSD, concrete fixture files or executable acceptance tests existed. XSD, then WSDL/fixtures, Java runtime/library/build-tool selection, native SOAP validation and integration mappings remained ahead. Controlled normal/slow/unavailable profiles and acceptance assertions were requirements, not demonstrated runtime results. No later Dataset 002 or Java validation result is attributed to this state.
