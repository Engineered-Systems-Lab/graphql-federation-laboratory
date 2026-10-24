# Crew & Personnel v1 passes its manual commissioning

Date: 2026-10-01T02:46Z
Subject: The lead developer's manual acceptance of the committed Crew & Personnel v1 SOAP service
Status: Historical / non-normative
Provenance: New commissioning report written at 2026-10-01T02:46:20+00:00 (UTC). The date is that of this report, not of the SOAP calls. Call date is September 30, 2026 (America/New_York), as reported by the lead developer; exact historical minutes are unknown. No call timestamp is inferred from file modification times or the earlier checkpoint.
Lab checkpoint: lab commit `64d395b4304cc3ddd86be37a248f63f8d75272e3` (HEAD when this report began; continuity governance already committed).
Runtime implementation anchor: lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`.
Migrated from lab log SD-2026.274-0246Z; originally written in the lab on 2026-10-01 (lab commit `a6d38e4a7d20954dc206b794476e4c17b6abe994`).

## Commissioning transition

The lead developer manually accepted the running service. The lab's Progress (the lab path `docs/PROGRESS.md`, at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`) then recorded its fact `manual_captain_acceptance` as PASS. This is a distinct state transition after the [runtime checkpoint](2026-10-01T0048Z-crew-personnel-java-service-checkpoint.md); its contemporary pending-acceptance statement is retained unchanged.

The lead developer reported these four direct, human-operated curl/SOAP calls against the running committed Crew & Personnel v1 service on September 30, 2026 (America/New_York), after the implementation and continuity checkpoints. These are not smoke.ps1 or JUnit results and were not rerun during this documentation task. The eight files contain requests and drivers, not captured responses; the response evidence is the lead developer's report. Exact call times were not supplied. File modification times are not response timestamps.

| Request + driver | Purpose and the response the lead developer observed |
| --- | --- |
| `get-picard.xml` + `Picard_test_1.sh` | Known crew member: HTTP 200; datasetVersion `crew-v1-small-002`; `CRW-1047`, Jean-Luc Picard; rank `CAPTAIN`; department `COMMAND`; positionTitle `Commanding Officer`; dutyStatus `ACTIVE`. |
| `get-broccoli.xml` + `Picard_test_2.sh` | Malformed crewId `CWR-5432`: HTTP 500; `soap:Client`; declared `CrewServiceFault` code `InvalidRequest`; field `crewId`; message `Request does not conform to Crew & Personnel v1.` |
| `get-unknown.xml` + `Picard_test_3.sh` | Syntactically valid but absent crewId `CRW-5432`: HTTP 500; `soap:Client`; `CrewServiceFault` code `CrewNotFound`; field `crewId`; message `No crew member has this crewId in the selected dataset.` |
| `list-crew.xml` + `List_test_1.sh` | Request offset=0, limit=2: HTTP 200; datasetVersion `crew-v1-small-002`; returned `CRW-1047` Jean-Luc Picard and `CRW-1048` William Riker; totalCount=12; offset=0; limit=2; hasMore=true. Riker: rank `COMMANDER`; department `COMMAND`; positionTitle `First Officer`; dutyStatus `ACTIVE`; supervisorCrewId `CRW-1047`. |

## Preservation and remaining direction

All eight existing request/driver files were copied unchanged into [component manual acceptance](../uss-enterprise/crew-personnel/acceptance/manual/README.md). Original filenames, including get-broccoli.xml, remain. Later clarification (final commissioning cleanup): the governed preserved record is `uss-enterprise/crew-personnel/acceptance/manual/`. Copies under ignored `tmp/` are transient working files, not preserved evidence, governed provenance, or part of the acceptance record. Relative request paths need no adjustment when run from that directory. No stored response transcripts were present among the eight artifacts.

The next action carries forward the existing Progress Next actions item 2 after closing manual acceptance. Plan Phase 1 and Next design choices item 1 require the remaining native contracts and Integration & Benchmark-owned mappings; D010 requires native validation before integration, and D015 assigns mapping ownership to the shared Integration & Benchmark layer. Architecture supplies the shuttle-unavailability scenario. This records the existing planned direction; this commissioning task starts no new implementation and authorizes no staging, commit, or frozen-contract reopening.

Authority: [Progress](../docs/PROGRESS.md), [Plan](../docs/PLAN.md), [Decisions](../project-governance/DECISIONS.md), [Architecture](../docs/ARCHITECTURE.md), and [Constraints](../project-governance/CONSTRAINTS.md). Logs are historical and do not authorize work independently.

## Commissioning-update verification

After recording manual acceptance, `python -B validation/validate_continuity.py` passed; `python -B -m unittest discover -s validation -p 'test_*.py' -v` passed all 17 regression tests; `& ./uss-enterprise/crew-personnel/validation/validate.ps1` passed (71 fixture schema/security checks, 300 xsi:nil probes, 67 scalar probes, 26 structure/readiness/protocol cases, and 20 semantic exchanges). The existing .NET supplementary-Unicode warning remains; frozen maxLength=100 is unchanged. `git diff --check` passed.

The representative reconstruction's acceptance/next-action facts and corresponding narratives were updated to match Progress. Validator logic, reconstruction contract and prompt are unchanged. This was not a fresh-agent trial. SHA-256 comparison against the pre-edit inventory confirms all 90 frozen specification/contract/fixture and runtime source/build/deployment files remain byte-identical; the commissioning update recorded that all eight copied artifacts matched the scratch originals byte-for-byte at copying time. Clarification: this historical copy check gives ignored `tmp/` no preservation or provenance authority; the governed acceptance record is under `uss-enterprise/crew-personnel/acceptance/manual/`. Java tests, Docker builds and SOAP calls were not rerun for this governance-only update. Repository work/ was neither read nor modified. No staging or commit occurred; the index remains empty.
