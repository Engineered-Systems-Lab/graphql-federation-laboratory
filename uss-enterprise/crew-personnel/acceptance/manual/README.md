# Manual commissioning artifacts

These are human-operated commissioning artifacts, not automated regression tests. All eight original filenames and file bytes are preserved, including the historical `get-broccoli.xml` name and original comments. The governed commissioning artifacts are preserved under `uss-enterprise/crew-personnel/acceptance/manual/`. Copies under ignored `tmp/` are transient working files, not preserved evidence, governed provenance, or part of the acceptance record.

The lead developer reported these four direct, human-operated curl/SOAP calls against the running committed Crew & Personnel v1 service on September 30, 2026 (America/New_York), after the implementation and continuity checkpoints. These are not smoke.ps1 or JUnit results and were not rerun during this documentation task. The eight files contain requests and drivers, not captured responses; the response evidence is the lead developer's report. Exact call times were not supplied. File modification times are not response timestamps.

| Request + driver | Purpose and lead-developer-observed response |
| --- | --- |
| `get-picard.xml` + `Picard_test_1.sh` | Known crew member: HTTP 200; datasetVersion `crew-v1-small-002`; `CRW-1047`, Jean-Luc Picard; rank `CAPTAIN`; department `COMMAND`; positionTitle `Commanding Officer`; dutyStatus `ACTIVE`. |
| `get-broccoli.xml` + `Picard_test_2.sh` | Malformed crewId `CWR-5432`: HTTP 500; `soap:Client`; declared `CrewServiceFault` code `InvalidRequest`; field `crewId`; message `Request does not conform to Crew & Personnel v1.` |
| `get-unknown.xml` + `Picard_test_3.sh` | Syntactically valid but absent crewId `CRW-5432`: HTTP 500; `soap:Client`; `CrewServiceFault` code `CrewNotFound`; field `crewId`; message `No crew member has this crewId in the selected dataset.` |
| `list-crew.xml` + `List_test_1.sh` | Request offset=0, limit=2: HTTP 200; datasetVersion `crew-v1-small-002`; returned `CRW-1047` Jean-Luc Picard and `CRW-1048` William Riker; totalCount=12; offset=0; limit=2; hasMore=true. Riker: rank `COMMANDER`; department `COMMAND`; positionTitle `First Officer`; dutyStatus `ACTIVE`; supervisorCrewId `CRW-1047`. |

To repeat a case against the already-running local service, change directory to `uss-enterprise/crew-personnel/acceptance/manual/` in Bash and run, for example, `bash Picard_test_1.sh`. Drivers use relative XML filenames and `http://127.0.0.1:8081/soap/crew-personnel`; no relocation edits were necessary. Copying preserved filesystem metadata where supported. Windows with `core.filemode=false` does not establish a portable Git executable bit; explicit Bash invocation works without one, and the index was not changed.

Current acceptance status belongs to [Progress](../../../../docs/PROGRESS.md#recovery-facts). See the [commissioning report](../../../../devlog/2026-10-01T0246Z-crew-personnel-manual-commissioning.md) for the historical transition and timing limits.
