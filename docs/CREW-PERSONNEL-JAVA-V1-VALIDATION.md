# Crew & Personnel Java SOAP Service v1 — validation record

Date: 2026-09-30 (America/New_York). Historical pre-commit execution record, subsequently included in lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`. References below to unstaged/uncommitted work describe the execution session. Current status is owned by [Progress](PROGRESS.md).

## Released 003 runtime validation (2026-10-01)

This addendum records the current uncommitted 003 extension; the original sections below retain their historical results. The approved nine files were copied without regeneration from proposed to released. Raw manifest/package SHA-256: `c06125dbe6883981293b485497474c46a0128372056efca389d7421f35ba2690` (116,874 manifest bytes, eight XML pages). The existing released-package validator passes recipe/provenance, exact bytes, 800-person readiness and all eight frozen-XSD validations.

Validation uses Windows, Microsoft JDK 17.0.20.1+1 (temporary extraction), Maven 3.9.16, CPython 3.12.14 and lxml 6.1.1. No global JDK/Python installation was changed. LibreOffice's Python wrapper reports a directory as `sys.executable`, preventing child processes; execution uses its actual `python-core-3.12.14/bin/python.exe` with the corresponding Python home and temporary pinned lxml path. This is environment setup only, with no repository workaround.

Final JDK 17 Maven `clean verify`: **87 tests passed, zero failures/errors/skips** (49 package, 15 dataset/service, 23 real HTTP). Coverage includes strict/rehashed negative manifest/page cases, secure XML, cross-page duplicate/order/reference/cycle failures, valid forward/backward references, defensive copies, complete traversals at limits 1/20/100, offsets 95/199/695/799/800/801/2147483647, all departments/statuses and AND combinations, status totals 719/40/41, retained/new/inactive lookups, Data/Wesley/Guinan semantics, 002-to-003 client restart, slow/unavailable profiles and legacy regressions. Each successful HTTP payload and declared fault detail is frozen-XSD-validated, with an explicit <=100 record assertion.

Built-JAR acceptance passes: exactly 11 approved dataset resources (two legacy snapshots plus nine release files), byte-identical to their source files; real loopback normal smoke for unset/default 002, explicit 001, explicit 002 and explicit 003; unavailable-003 fault/precedence smoke. 003 smoke checks all 800 ordered IDs, offset 95/limit 20, status totals, complete supervisor graph and selected Get results. Four modified JARs (missing/tampered manifest and missing/tampered page) exit nonzero with resource/integrity diagnostics, without endpoint publication or fallback. All temporary service processes are stopped. The repeatable harness is `validation/runtime_acceptance.py` within the component; temporary JARs are removed automatically.

Full Python regression discovery ran once: **106 tests passed** in 191.358 seconds, including the dataset and extended portable smoke suites. The authoritative root Python validation passes recovery links/logs/checkpoint/frozen invariants, 71 fixture schema/security checks, 300 nil probes, 67 scalar probes, 26 structure/readiness/protocol cases and 20 semantic exchanges. Both supplementary-Unicode boundaries pass. The initial root-validation attempt caught a missing link target for this addendum before component validation; after adding the heading, the rerun passed. No component suite was manually duplicated. The separate released-package validation also passes.

Final preservation review: no diff in frozen specification/contracts/fixtures, proposal/generator, `CrewService`, `Main`, `Xml`, deployment WSDL, Compose, lab logs or checkpoint/continuity tooling. Maven and Docker context resources explicitly allowlist the approved release; `.gitattributes` preserves its raw bytes. Git whitespace checks pass; the index is empty and HEAD remains lab commit `b58c15c7361acee76e8b0a7e03b05188b9b6e53c`. No staging, repository commit, push or lab log was performed. The existing checkpoint regression suite uses its own temporary repositories as before.

Docker client 29.8.0 is present, but the configured `desktop-linux` daemon pipe is absent. No new container build, Linux execution, image resource inspection or container smoke is claimed. Dockerfile release-resource copying is updated; existing base pins/defaults and Compose are unchanged. Manual commissioning evidence and recorded runtime checkpoint remain historical and unchanged.

## Outcome and scope

Standalone Java 17 / CXF JAX-WS service implements exactly GetCrewMember and ListCrewMembers. Embedded Jetty provides HTTP; JAXB and the service interface are generated from the committed frozen WSDL/XSD. The runtime deployment descriptor imports that binding and adds service/port metadata only. No Spring Boot/WS, database, authentication, GraphQL, federation, MCP or AI layer was introduced. No frozen contract or fixture file changed; no genuine contract defect was found and no reopening is needed.

## Exact environment

| Item | Used/observed version |
| --- | --- |
| Build/test JDK | Eclipse Temurin 17.0.17+10 (Java 17 container) |
| Container runtime | Eclipse Temurin 17.0.20.1+1, Java 17 JRE on Ubuntu Jammy |
| CXF runtime and wsdl2java | 4.2.3, successfully resolved from Maven repositories |
| Build/test Maven | 3.9.11, commit 3e54c93a704957b63ee3494413a2b544fd3d825b |
| Compiler plugin | 3.14.1, `release=17` |
| Surefire / JUnit | 3.5.3 / 5.11.4 |
| Docker Engine / Desktop | 29.8.0 / 4.92.0 (240144), Linux containers |
| Host tools, detected only | Maven 3.9.16; Oracle Java 26.0.2.1; no host JDK 17 found in the inspected Java installation directories |

The build base is `maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82`.
The runtime base is `eclipse-temurin:17-jre-jammy@sha256:97137382c6f0c30427d9b7c44ad8b2d55ac823b0768c171d81a643ed219023c5`.
The initial implementation image `crew-personnel:v1` had image ID `sha256:6098a4ca4b5ae7947d4cd40b51cc604c1937577bb3bad65a732b13e32ca6fbf2`.

## Runtime configuration

Endpoint: `http://127.0.0.1:8081/soap/crew-personnel`. `?wsdl` publishes the deployment descriptor with links to the frozen contract and XSD. Default dataset: `crew-v1-small-002` (12 records); optional `crew-v1-small-001` (6 records), selected by `CREW_DATASET_VERSION`. Startup validates canonical file hashes, version, schema, counts, ID uniqueness and supervisor references/cycles. No snapshot merging occurs.

`CREW_FAILURE_PROFILE=normal|slow|unavailable`, default normal. Slow requests a 2,000 ms delay before every valid request's normal outcome, including not-found; unavailable returns ServiceUnavailable after validation. InvalidRequest wins in both. Port is configured by `CREW_PORT`; local bind defaults to loopback, while the image sets its internal bind to 0.0.0.0 and host publication remains loopback. See the [component README](../uss-enterprise/crew-personnel/README.md) for exact build/run/test/reset commands.

## Initial implementation checks (historical; superseded by completion below)

| Check | Exact result |
| --- | --- |
| Existing `validation/validate.ps1` | PASS: XSD 1.0 compiled; 71 fixture schema/security checks; 300 xsi:nil position/value probes; 67 named scalar probes. |
| Existing Python structure/semantic suite, invoked by PowerShell | PASS: WSDL QNames/binding/include; 26 structure/readiness/protocol cases; six frozen records plus 12-record 002; 20 semantic exchanges; fault/replacement expectations. |
| Maven verify in Java 17 container | BUILD SUCCESS; 31 tests, 0 failures, 0 errors, 0 skipped. 10 DatasetServiceTest + 21 SoapHttpTest. |
| Fresh multi-stage Docker build | BUILD SUCCESS; regenerated the contract and reran all 31 tests, 0 failures/errors/skips. Compiler reported `release 17`. |
| Real SOAP HTTP integration | PASS: successful Get/list, inactive/on-leave and supervisor handling, defaults/AND filters/pages/empty and max offset, lexical integers, bounds/nil/structural invalidity, all four declared faults, SOAP Client/Server QNames and HTTP 200/500. Success payloads and declared details validate against the frozen XSD. |
| Profile/restart acceptance | PASS: exactly 2,000 ms requested delay in unit test; real slow not-found response took at least 2,000 ms; 500 ms client deadline timed out; invalid requests bypass delay; unavailable honors validation precedence; restart normal restores service and identical semantic page content. |
| Readiness and immutable behavior | PASS: existing five negative dataset fixtures rejected, valid edge fixture accepted, leading-zero/duplicate names/escaped text/preserved spaces retained; canonical 001/002 separate; returned records cannot mutate snapshot. |
| Supplementary Unicode boundary | PASS in configured Java validator: 100 supplementary XML characters accepted, 101 rejected. Frozen XSD unchanged. |
| WSDL/XSD publication | PASS over real HTTP: deployment WSDL import resolves, imported frozen WSDL has five messages and two operations, XSD include resolves. |
| Windows to final normal container, loopback 8081 | PASS: four SOAP calls — successful Picard Get, offset=2/limit=2 page with totalCount=12/hasMore=true, CrewNotFound/crewId, InvalidRequest/limit. XSD/status/fault QName checks passed. |
| Windows to final unavailable container, loopback 8082 | PASS: three SOAP calls — both valid operations return ServiceUnavailable, invalid limit returns InvalidRequest. XSD/status/fault QName checks passed. |

Temporary test containers were stopped after validation. No host Java service was started because a host JDK 17 was not available in the inspected installation locations; real HTTP services ran both inside Java test containers and in the final JRE image with Windows-to-container requests. No system software was installed. The existing offline consumer replacement model remains the consumer-side test; this phase does not claim a new deployed integration consumer.

## File inventory

Created under `uss-enterprise/crew-personnel/`:

- `pom.xml`: pinned CXF/JUnit/plugins, Java 17 compilation, WSDL generation, tests, executable JAR with adjacent runtime libraries.
- `Dockerfile`, `.dockerignore`, `compose.yaml`: pinned Java 17 multi-stage build, minimal non-root runtime, loopback publication.
- `src/main/resources/deployment.wsdl`: imports frozen binding and adds deployment metadata only.
- `src/main/java/lab/enterprise/crew/Main.java`: validated configuration, startup and shutdown/publication.
- `src/main/java/lab/enterprise/crew/CrewService.java`: the two operations and deterministic profiles.
- `src/main/java/lab/enterprise/crew/Dataset.java`: registered immutable snapshots and readiness checks.
- `src/main/java/lab/enterprise/crew/Xml.java`: secure offline schema validation and field attribution.
- `src/main/java/lab/enterprise/crew/RequestValidation.java`: pre-binding SOAP payload validation.
- `src/main/java/lab/enterprise/crew/Faults.java`, `FaultMapping.java`: declared fault construction/mapping.
- `src/test/java/lab/enterprise/crew/DatasetServiceTest.java`, `SoapHttpTest.java`: focused readiness/service and real HTTP tests.
- `validation/smoke.ps1`: reusable Windows-originated HTTP/schema smoke.

Documentation modified: root `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (appended D016), `docs/PROGRESS.md`, component `README.md`. This report is new. Historical decision entries, frozen specification, contracts, fixtures and existing validation scripts are unchanged. `.gitignore` already covers target output, caches, IDE state and logs and did not require modification.

## Initial implementation Git and evidence boundary (historical)

Final audit: five tracked documentation files modified and sixteen new implementation/test/deployment/report files; all are unstaged, and the index is empty. `git diff --check` passes. Contracts, fixtures, frozen specification and both existing validation scripts have no diff. Generated output and caches are confirmed ignored. Nothing was committed. The initial repository had only `docs/PAKLED-3-REVIEW.md` and `work/` untracked. These three audit files were left unmodified/unincluded and their SHA-256 values were preserved:

- `docs/PAKLED-3-REVIEW.md`: `1bfbc50b59ab49fa479cfcd467094fb49906f7a4696182efae94270df09c092b`.
- `work/before.json`: `945608be97b99e4613c0eb9365637195c95f270f2a428390a51002809cc94ca7`.
- `work/pakled-start.json`: same `945608be97b99e4613c0eb9365637195c95f270f2a428390a51002809cc94ca7`.

Build output and generated Java remain ignored under the component's `target/`; Maven cache/build logs remain ignored under root `.cache/`. Test reports from the mounted build are in `target/surefire-reports/`; the fresh final image build log is `.cache/crew-docker-build.log`. The source inventory above covers the review changes; `git diff --stat` alone excludes new untracked source files.

## Warnings and limitations

- The unchanged .NET contract suite retains its narrowly recognized supplementary-Unicode length warning. Java's configured validator now independently passes that boundary; no schema workaround was applied.
- CXF code generation warns that the frozen WSDL defines no service, intentionally. The separate deployment descriptor solves publication without touching it. Generated BARE Java parameter style preserves the committed wrapped XML payload.
- SLF4J has no provider and uses its no-op fallback; CXF JUL logs still appear. A deliberately timed-out HTTP client can cause a server-side disconnected-writer log. These did not fail tests.
- Image digests pin this verified environment; later dependency/base updates require explicit review. Timings are acceptance checks, not performance benchmark results.
- No issue requires reopening the frozen contract.

## Governance and SHA-256 portability completion (2026-09-30)

The interrupted loader fix and regression/anti-drift tests were inspected and retained without source edits. Current results supersede the initial 31-test count and image identity above.

| Independently executed check | Completion result |
| --- | --- |
| Java 17 container Maven `clean verify` against working tree | BUILD SUCCESS: 35 tests; 14 DatasetServiceTest + 21 SoapHttpTest; 0 failures, errors or skipped. Maven 3.9.11 / pinned Temurin 17 build image. |
| Fresh Docker `--no-cache` multi-stage build | BUILD SUCCESS: all 35 tests rerun; 0 failures, errors or skipped; compiler release 17. |
| Offline PowerShell and Python suite | PASS: 71 fixture schema/security checks, 300 nil probes, 67 scalar probes, 26 structure/readiness/protocol cases, 20 semantic exchanges, frozen six-record and 12-record snapshots, faults and replacement expectations. Known .NET supplementary-character warning remains. |
| Host-loopback SOAP, normal profile, port 18081 | PASS: 4 requests (Get, paged List, CrewNotFound, InvalidRequest); HTTP status, payload XSD, fault QName/field, dataset/count/pagination assertions. |
| Host-loopback SOAP, unavailable profile, port 18082 | PASS: 3 requests (both valid operations unavailable, invalid limit InvalidRequest); HTTP status, payload XSD and fault assertions. |
| Invalid dataset container startup | Unknown canonical dataset rejected, process exit 1, before HTTP publication. |
| Hash regression and readiness | LF, CRLF, current bytes, synthesized mixed bytes including 002's 113 CRLF + one LF all pass the actual loader. Content/whitespace mutations and standalone/trailing CR fail. Input arrays remain unchanged. Five invalid readiness fixtures still rejected. |
| Deployment WSDL anti-drift | Existing HTTP test passed: rejects local types/message/portType/binding and permits only import/service/port/address metadata; frozen import/XSD resolve. |
| Java supplementary Unicode | 100 code points accepted, 101 rejected; frozen maxLength=100 unchanged. |
| Profiles/restart | Existing Java tests passed for slow delay, timeout, invalid-request precedence, unavailable, normal restart and declared fault behavior. |

Rebuilt `crew-personnel:v1` image identity from Docker inspect: `sha256:7d9246b3a4e0d73b09ec95c804cda70092b8d888829bbe6b5810621f5dc2a021`. Temporary smoke containers were stopped. No software was installed. Ignored logs: `.cache/governance-docker-build.log` and `.cache/governance-maven-verify.log`; generated reports remain under ignored component `target/surefire-reports/`.

Canonical hashes independently recomputed from `git show HEAD:<path>` bytes:

- `crew-v1-small-001`: `daeebe24706e3345d3f14c320a8fb9eb866fcfea7ce2dc8f01ce1977bbc0a35e`.
- `crew-v1-small-002`: `6cf7e7ec590fa247aa8f884916a4014ce86aa27276c7bcbe409abd65465da8b9`.

The loader skips only CR immediately before LF for SHA-256, then compares these full hashes; original bytes enter XML parsing unchanged. All other bytes remain significant. The offline manifest still uses historical working-copy raw-byte hashes. This fixes Java checkout portability, not offline manifest portability or SOAP semantics.

### Governance and historical preservation

`AGENTS.md` now orients workers to current `docs/`, active CONSTRAINTS, ARCHITECTURE, standing DECISIONS, normative component specifications/contracts, PLAN/PROGRESS and non-normative INTEGRATION-NOTES. Frozen contracts outrank implementation convenience. Lab logs are historical and never override these authorities.

CONSTRAINTS prominently preserves: **The integration platform must adapt to the enterprise; the enterprise must not be redesigned to accommodate the integration platform.** Its operational scope permits legitimate legacy bug/contract-compliance fixes. Distilled rules cover immutable datasets, integration-layer ID reconciliation, authoritative ownership, acceptance before performance, generated artifacts and D016's Java 17/CXF/WSDL-first/no-Spring runtime.

The untracked `docs/PAKLED-3-REVIEW.md` was migrated to `captains-log/SD-2026.273-1748Z-crew-personnel-contract-dataset-fixture-review.md` in the lab (in this repository the [devlog entry of 2026-09-30T17:48Z](../devlog/2026-09-30T1748Z-crew-personnel-contract-dataset-fixture-review.md)); its old path was removed. Useful dataset/fixture/review evidence and limitations remain, while obsolete task-relative inventory/Git chatter was omitted. Matching original file creation and last-write timestamps, 2026-09-30 17:48:01 UTC, support the report's minute; this is filesystem provenance, not an independently authenticated Git event timestamp. Seconds are omitted under `YYYY.DDD-HHmmZ`. The later migration time was not substituted.

D016's stored UTF-8 mojibake was repaired to an ASCII hyphen. No other candidate was found in the documentation/source text scan. The likely Windows-1252 misdecode/re-save mechanism is documented as inference, not a proven editor diagnosis. Intentional Unicode fixtures/tests were untouched. Decision IDs and rationale/history remain; stale open-choice/freeze sections are explicitly historical. README build examples now derive the repository location rather than hard-code a machine path.

No `.editorconfig` or `.gitattributes` was added. Effective `core.autocrlf=true`, absent explicit contract/dataset attributes, mixed fixture bytes and the raw-byte offline manifest warrant a separate controlled policy/normalization change. No mass normalization occurred.

### Preservation audit and proposed future commit

All starting contract and fixture files, Java source/tests, deployment descriptor and both work audit files are byte-identical to the mission-start SHA-256 inventory. Frozen WSDL/XSD and canonical datasets also match Git HEAD after CRLF-to-LF comparison, with no Git diff. Dataset 001 retains 61 CRLF; 002 retains 113 CRLF and one bare LF. No dataset XML was rewritten. Both `work/before.json` and `work/pakled-start.json` retain SHA-256 `945608be97b99e4613c0eb9365637195c95f270f2a428390a51002809cc94ca7`, matching the earlier recorded evidence.

The exact proposed future commit paths below include the pre-existing approved Java implementation and documentation work as well as this completion. Review these paths explicitly; do not stage the whole working tree. Exclude `work/before.json`, `work/pakled-start.json`, `.cache/`, component `target/`, generated outputs, logs and all unrelated changes. No credential/private-key/absolute Windows machine-path candidates were found in the proposed text files; ignored build/cache files remain outside the scope. No index or commit changes were made.

Mission-relative added files:

- `AGENTS.md`
- `captains-log/README.md`
- `captains-log/SD-2026.273-1748Z-crew-personnel-contract-dataset-fixture-review.md`
- `docs/CONSTRAINTS.md`

Mission-relative modified files:

- `docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md`
- `docs/INTEGRATION-NOTES.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/PROGRESS.md`
- `uss-enterprise/crew-personnel/README.md`

Mission-relative removed old path (content migrated as described):

- `docs/PAKLED-3-REVIEW.md`

Exact proposed future commit paths (relative to HEAD):

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/PROGRESS.md`
- `uss-enterprise/crew-personnel/README.md`
- `AGENTS.md`
- `captains-log/README.md`
- `captains-log/SD-2026.273-1748Z-crew-personnel-contract-dataset-fixture-review.md`
- `docs/CONSTRAINTS.md`
- `docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md`
- `docs/INTEGRATION-NOTES.md`
- `uss-enterprise/crew-personnel/.dockerignore`
- `uss-enterprise/crew-personnel/Dockerfile`
- `uss-enterprise/crew-personnel/compose.yaml`
- `uss-enterprise/crew-personnel/pom.xml`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/CrewService.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/Dataset.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/FaultMapping.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/Faults.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/Main.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/RequestValidation.java`
- `uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/Xml.java`
- `uss-enterprise/crew-personnel/src/main/resources/deployment.wsdl`
- `uss-enterprise/crew-personnel/src/test/java/lab/enterprise/crew/DatasetServiceTest.java`
- `uss-enterprise/crew-personnel/src/test/java/lab/enterprise/crew/SoapHttpTest.java`
- `uss-enterprise/crew-personnel/validation/smoke.ps1`

Final checks: `git diff --check` passes; index is empty. Local Markdown file links resolve. Generated target/cache/log files are ignored. Remaining limitations are the unchanged .NET/offline Unicode discrepancy, offline manifest raw-byte checkout dependence, and filesystem-only historical timestamp provenance. None requires reopening the frozen contract.
