# Crew & Personnel dataset 002 and the fixture validation are reviewed

Date: 2026-09-30T17:48Z
Subject: Dataset v002 expansion, fixture rationalization and offline contract review
Status: Historical / non-normative
Provenance: Original report filesystem timestamps recorded during migration; original untracked report is no longer present.
Lab checkpoint: Subsequent corroborating artifact state lab commit `9fdfba688094f3905997b345cfbdf44668c50bf3` (not the source of this date).

Migrated from `docs/PAKLED-3-REVIEW.md`. Timestamp evidence: the original file's CreationTimeUtc and LastWriteTimeUtc both read 2026-09-30 17:48:01 UTC at migration; the convention omits seconds. This is filesystem evidence for report creation, not an independently Git-authenticated event time (the report was untracked). Individual work steps have no established minute. The later 18:00:22 UTC contract commit is consistent with this sequence but does not establish the report minute.

This review concerns the expansion to Dataset 002 and maturation of the fixtures/offline validation suite. The earlier [Dataset 001 design](2026-09-30T1654Z-crew-personnel-design-dataset-001.md) had already established the original six records and contract boundaries. The subsequent [18:00 executable-contract checkpoint](2026-09-30T1800Z-crew-personnel-frozen-executable-contract.md) records the resulting committed artifacts. The reduction from 169 to 79 files and execution counts below remain report findings; Git has no intervening checkpoint independently demonstrating the larger inventory.

Preserved review findings follow. The old task-relative file inventory and transient Git-status/audit chatter were omitted; they describe an earlier working tree, not current authority. This record is not a validation specification.
Migrated from lab log SD-2026.273-1748Z; originally written in the lab on 2026-10-01 (lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`).

## Counts and validation

- Component: 79 files, including 72 XML fixtures (previously 169 files / 163 XML).
- Exactly 67 scalar XML files converted to explicit named in-memory cases; five byte-identical copies and 20 stored nil files removed.
- Original 001, XSD and WSDL are byte-identical to task-start hashes. Both immutable dataset hashes are registered in the manifest.
- Full PowerShell suite passed: 71 schema/security checks (SOAP 1.2 is handled structurally), 300 nil probes, 67 scalar cases, 26 structure/readiness/protocol cases, 20 semantic exchanges, faults and replacement checks.
- Six original records match the frozen specification; 002 has exactly 12, unique IDs, resolved supervisors and no cycles.
- Local Markdown links, trailing whitespace and git diff --check passed.
- Injected unexpected general and unrelated schema exceptions both propagated from the Unicode check.

## Dataset 002

Metadata: datasetVersion=crew-v1-small-002; totalCount=12; offset=0; limit=20; hasMore=false.

| crewId | displayName | rank | department | positionTitle | dutyStatus | supervisorCrewId |
| --- | --- | --- | --- | --- | --- | --- |
| CRW-1047 | Jean-Luc Picard | CAPTAIN | COMMAND | Commanding Officer | ACTIVE | omitted |
| CRW-1048 | William Riker | COMMANDER | COMMAND | First Officer | ACTIVE | CRW-1047 |
| CRW-1049 | Geordi La Forge | LIEUTENANT_COMMANDER | ENGINEERING | Chief Engineer | ACTIVE | CRW-1048 |
| CRW-1050 | Data | LIEUTENANT_COMMANDER | OPERATIONS | Operations Officer | ACTIVE | CRW-1048 |
| CRW-1051 | Mara Venn | LIEUTENANT | FLIGHT_OPERATIONS | Shuttle Pilot | ON_LEAVE | CRW-1048 |
| CRW-1052 | Elias Renn | ENSIGN | ENGINEERING | Engineering Technician | INACTIVE | CRW-1049 |
| CRW-1053 | Beverly Crusher | COMMANDER | MEDICAL | Chief Medical Officer | ACTIVE | CRW-1047 |
| CRW-1054 | Deanna Troi | LIEUTENANT_COMMANDER | MEDICAL | Ship's Counselor | ACTIVE | CRW-1047 |
| CRW-1055 | Wesley Crusher | ENSIGN | OPERATIONS | Acting Ensign | ACTIVE | CRW-1050 |
| CRW-1056 | Guinan | CIVILIAN | OPERATIONS | Bartender | ACTIVE | omitted |
| CRW-1057 | Reginald Barclay | LIEUTENANT | ENGINEERING | Systems Diagnostic Engineer | ACTIVE | CRW-1049 |
| CRW-1058 | Worf | LIEUTENANT | SECURITY | Chief of Security | ACTIVE | CRW-1048 |

Beverly Crusher and Deanna Troi report to Picard; Wesley to Data; Barclay to Geordi; Worf to Riker. Guinan has no supervisor recorded. All six additions are ACTIVE.

## Replacement and limitations

The manifest uses 001 page 0, 002 at offset 2, and a restart request at offset 0. The offline model clears the accumulated 001 data without appending the changed-version page, then accepts only the first 002 page. Stored replacement snapshots independently undergo semantic exchange checks.

maxLength=100 remains unchanged. Only the exact recognized .NET supplementary-Unicode/UTF-16 MaxLength schema error is tolerated. At this historical review, full Unicode boundary validation on a conforming engine had not yet been verified. WSDL checks are static structure/QName/include/binding checks; no specialized WSDL validator, service HTTP behavior, Java generation, actual consumer restart or timing tests were run. Immutable hashes protect supplied snapshots; future global version non-reuse is not proven. Python 3.9+ is documented; no software was installed.

## Later-context note

Subsequent configured Java 17 tests accept 100 and reject 101 supplementary code points; the .NET/offline limitation remains. This later result is recorded in [current integration notes](../docs/INTEGRATION-NOTES.md), not attributed to the 17:48 review. The original report is absent, so its exact filesystem timestamps cannot be independently re-read; the migration statement above is retained as recorded provenance.
