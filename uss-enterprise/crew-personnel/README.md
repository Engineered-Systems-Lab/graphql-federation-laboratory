# Crew & Personnel v1 SOAP service and contract artifacts

**Deprecated and frozen.** Crew & Personnel v1 is kept as a reference and is no longer developed. Personnel v2 (`uss-enterprise/personnel-v2/`) replaces it in the federation. Its contract, fixtures and released datasets keep their identity, every file of this folder is frozen by checksum, and it stays readable and runnable as described below. Dataset 003 is not regenerated in this repository; its released package is the reference. Other systems still read its released dataset 003 and its shared XML helper `validation/xml_validation.py`.

Crew & Personnel Contract v1 is **FROZEN**. Executable XSD/WSDL, deterministic fixtures and offline checks implement [the frozen specification](../../docs/CREW-PERSONNEL-V1.md). Contract semantics and the original six-record dataset remain unchanged. The committed frozen artifacts remain authoritative. The Java 17/CXF 4.2.3 standalone service implements them; the implementation is committed; [Progress](../../docs/PROGRESS.md) owns current checkpoint and acceptance status.

## Contract layout

- `contracts/crew-personnel-v1.xsd`: XSD 1.0, all application scalar/record types, four operation wrappers, and `CrewServiceFault`.
- `contracts/crew-personnel-v1.wsdl`: WSDL 1.1, SOAP 1.1 over HTTP, document/literal wrapped.
- `fixtures/manifest.json`: exhaustive fixture inventory, expected validity/layer, 20 request/response pairs, fault expectations, dataset-replacement trace, and controlled-failure expectations.
- `validation/validate.py`: portable lxml XSD compilation/validation, safe XML parsing, and nil probes; invokes the Python checker.
- `validation/validate_structure.py`: standard-library-only WSDL structure/QName checks, fixture readiness checks, semantic exchanges, and comparison of the canonical records directly against the frozen Markdown table.

The XSD and WSDL definitions both use `urn:graphql-federation-lab:crew-personnel:v1`. The WSDL's inline schema has that same target namespace and includes the sibling `crew-personnel-v1.xsd` by relative `xs:include`. There are no `xs:import`, `wsdl:import`, transitive includes, or network schema dependencies. Application elements are qualified; attributes are unqualified, with no application attributes declared. All complex types use sequences, and every element explicitly sets `nillable="false"`.

The five WSDL messages are `GetCrewMemberRequestMessage`, `GetCrewMemberResponseMessage`, `ListCrewMembersRequestMessage`, `ListCrewMembersResponseMessage`, and `CrewServiceFaultMessage`. Each has one element-based `parameters` part referencing its same-named application wrapper without the `Message` suffix. `CrewPersonnelPortType` exposes only `GetCrewMember` and `ListCrewMembers`. `CrewPersonnelSoap11Binding` binds both with literal input/output and the shared declared `CrewServiceFault`. SOAPActions are the application namespace plus `:GetCrewMember` or `:ListCrewMembers`.

The reusable WSDL ends at the binding: no deployment-specific `service`, `port`, host, or port number is invented. Deployment must expose this binding at `/soap/crew-personnel`, using the configured host/port. SOAP envelope/fault structure is checked separately; no modified SOAP-envelope schema is introduced. Examples use SOAP 1.1 Envelope/Body/Fault, unqualified faultcode/faultstring/detail, and qualified CrewServiceFault/code/message/field. Faultcode is a QName, not a prefix-sensitive string.

Both operations declare the same fault detail with four code values: `InvalidRequest` and `CrewNotFound` map to SOAP `Client`; `ServiceUnavailable` and `InternalError` map to SOAP `Server`. Declared faults require HTTP 500; successes require HTTP 200. HTTP status and runtime fault selection cannot be enforced by the application XSD.

## Fixture organization

| Location | Purpose |
| --- | --- |
| `canonical/crew-v1-small-001.xml` | Exactly the six frozen records, unchanged, in the existing default ListCrewMembersResponse shape. This immutable baseline is retained alongside version 002. |
| `canonical/crew-v1-small-002.xml` | Exactly 12 records: the original six unchanged plus six approved additions. A separate immutable dataset version under the same frozen wire contract. |
| `requests/`, `responses/` | Operation payloads: defaults, filters/AND, inactive lookup, leading-zero lookup, pages 0/2/4, empty pages 6/7/2147483647, no matches, numeric lexical equivalents, and limit bounds. |
| `soap/` | Complete SOAP 1.1 request and success-response envelopes for both operations. |
| `faults/` | Complete declared SOAP faults for all four codes; InvalidRequest examples with and without field. |
| `validation/crew-v1-edge-001.xml` | Separate complete dataset: CRW-0007, duplicate Alex Smith names, escaped R&D text, preserved spaces, inactive/cross-department supervisor, multiple roots, and rank-independent reporting. |
| `validation/crew-v1-replacement-001.xml` | Retained independent edge dataset adding CRW-0010; the active replacement trace now uses canonical 001 to 002. |
| `scalar-probes.json` | Exactly 67 named in-memory cases, each with a base fixture, explicit target/value edits and expected validity; includes lexical, whitespace, boolean and text/version boundaries. |
| `negative/requests/`, `negative/schema/` | Expected XSD rejection: invalid IDs/enums/bounds/lexemes, empty optionals, ordering, namespaces, duplicates, unknown fields/attributes, mixed content, scalar limits and record occurrence limits. |
| `negative/datasets/` | Schema-valid but readiness-invalid duplicates, dangling/self/cyclic supervisors, and count mismatch. Never serve these. |
| `negative/soap/`, `protocol/` | Structural fault/envelope violations; separate malformed XML, SOAP 1.2, DTD and external-entity rejection cases. Protocol failures do not promise a declared business fault. |

Complete small fixture datasets reuse a valid ListCrewMembersResponse with offset 0, effective limit 20 and hasMore=false, avoiding a new wire wrapper or fixture namespace. This storage convention is only for these small snapshots; it does not cap a future service's total dataset at 100. Larger fixtures need a separate storage design while each list response remains limited to 100 records.

`manifest.json` distinguishes schema payload checks from full dataset/readiness checks. Invalid/schema probes must not be loaded as served datasets. Record identity, cycle/reference integrity, immutable version registration, and pagination relationships remain mandatory outside XSD 1.0. IDs are never inferred from names. The standalone checker can verify the supplied snapshots, not prove non-reuse across all future dataset history.

String whitespace is preserved. The nonblank pattern names space/tab/CR/LF explicitly, avoiding the local validator's broader interpretation of `\s`. XSD 1.0 patterns match the full lexical value ([W3C datatype specification](https://www.w3.org/TR/2004/REC-xmlschema-2-20041028/datatypes.html#regexs)); IDs also have length 8 and explicitly exclude CRW-0000. Defaults are applied only by omission in the exchange oracle, never by XSD element defaults. Integer and boolean types retain their standard collapsed-whitespace lexical rules.

## Run and validation limits

From the repository root, use an explicitly verified Python 3.13+ interpreter under the [interpreter policy](../../governance/CONSTRAINTS.md#python-interpreter-policy). Here `python` denotes that verified invocation. First install `python -m pip install -r uss-enterprise/requirements.txt`:

```text
python -B uss-enterprise/crew-personnel/validation/validate.py
```

After installing the pinned lxml dependency, no network access, code generation, or running service is required for offline validation. The validator prohibits DTDs and disables external resolution. It does not process instance schema-location hints. The structure checker alone does not perform XSD validation; run `validate.py` for the complete offline suite.

Local review on 2026-09-30: 72 XML fixtures, 20 semantic request/response pairs, 300 in-memory nil position/value probes and 67 named scalar probes. The .NET XSD compiler and the fixture/structure checks pass, with this explicit additional limitation:

**Observed validator mismatch:** this local .NET implementation rejects 100 supplementary Unicode characters (tested with U+1F680) because it counts 200 UTF-16 code units. The frozen rule is 100 XML characters. The XSD correctly retains `maxLength=100`; no narrower Unicode contract or workaround was introduced. The former runner warned only for the schema validation exception naming displayName, the exact 100 supplementary-character value, and the recognized MaxLength failure; unexpected exceptions propagated. The active Python/lxml runner replaces that path and passes both Unicode boundaries. Configured Java 17 validation now regression-tests 100 supplementary characters accepted and 101 rejected; see [integration notes](../../docs/INTEGRATION-NOTES.md).

No specialized WSDL validator was used; WSDL validation here is static structure, relative include, QName/message references, operations, SOAPAction, and binding/fault consistency. That offline suite does not establish service readiness, HTTP response, Java generation, restart or timing behavior. The additional Java/runtime validation below now covers service behavior; the existing consumer replacement model remains an offline test. No wire-contract ambiguity or artifact mismatch was found; the local Unicode-validator discrepancy remains documented for review.

## Dataset evolution and fixture maintenance

The replacement trace consumes 001 offset 0 / limit 2, encounters 002 at offset 2, clears the accumulated records, and restarts at 002 offset 0. The offline client model tracks version provenance and asserts that the restarted accumulator contains only the first two 002 records. Both replacement response snapshots are checked independently against dataset 002. This is an offline model, not a running consumer test.

The manifest records SHA-256 values for immutable 001 and 002. Readiness checks enforce unique IDs, resolved supervisors, no cycles and exact record counts; 002's first six records must match 001. The original six also remain checked against the frozen specification table.

Five byte-identical copies now reuse manifest references; 20 stored nil files are covered by the 300-position/value sweep. Exactly 67 scalar XML files became explicit cases in `scalar-probes.json`; their original names and parsed leaf values were verified during conversion. The runner applies only named text edits or appends a named optional request element. Expected response snapshots remain stored independently. Structural text-as-markup and 101-record fixtures remain XML.

New supervisors: Beverly Crusher and Deanna Troi report to Picard (CRW-1047); Wesley Crusher reports to Data (CRW-1050); Reginald Barclay reports to Geordi (CRW-1049); Worf reports to Riker (CRW-1048). Guinan has no supervisor recorded (element omitted). All six additions have ACTIVE duty status. These are lab reporting assignments under frozen Personnel semantics.


## Java service architecture

Exactly two generated JAX-WS operations are implemented by `CrewService`: GetCrewMember and ListCrewMembers. Apache CXF embeds its Jetty HTTP transport; there is no Spring Boot, Spring-WS, database, authentication or integration layer. CXF 4.2.3 resolved successfully. Java compilation explicitly uses `maven.compiler.release=17`.

Maven's CXF `wsdl2java` execution reads **only** `contracts/crew-personnel-v1.wsdl` and its unchanged XSD include, generating `lab.enterprise.crew.contract` under `target/generated-sources/cxf`. No generated Java is committed. CXF maps the committed Request-suffixed wrappers to a BARE Java parameter style; SOAP still contains exactly the frozen, qualified request/response wrapper. This does not change the document/literal wire contract.

`src/main/resources/deployment.wsdl` adds only deployment service/port/address metadata and imports the frozen binding. CXF serves this descriptor at `http://127.0.0.1:8081/soap/crew-personnel?wsdl`; follow its import and XSD include links for the authoritative contract. CXF rewrites retrieval URLs and the runtime address for the current deployment; stored contract files remain byte-for-byte unchanged.

`RequestValidation` securely parses and validates the raw payload **before** CXF dispatch/JAXB can discard unknown, duplicate or invalid values. DTDs and external entities are prohibited. Non-namespace application attributes, including every xsi:nil value, are rejected. XSD errors become InvalidRequest with the offending field when known. Malformed XML, SOAP-version and transport errors retain the documented protocol distinction; they do not promise a business detail. `FaultMapping` preserves declared HTTP 500 Client/Server faults and sanitized InternalError messages. Normal responses use HTTP 200.

`Dataset` verifies the selected canonical SHA-256 registration (copied from the unchanged fixture manifest), XSD, version, complete snapshot metadata, unique IDs and acyclic resolved supervisor references before HTTP publication. It sorts lexically by crewId and protects the in-memory records from mutation. Validation/negative datasets cannot be selected at startup. Java tests load them only to test readiness and edge behavior.

Java 17's bundled Xerces defaults to UTF-16 length counting. The application enables `com.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength=true` before schema initialization; test JVMs and the container also set it at startup. A boundary test proves acceptance of 100 supplementary XML characters and rejection of 101 without altering the XSD. When embedding this component in another JVM, set that property before any schema engine initializes; the standalone deployment is the supported runtime here.

## Configuration

| Environment variable | Default | Behavior |
| --- | --- | --- |
| `CREW_DATASET_VERSION` | `crew-v1-small-002` | Default 12-record snapshot. `crew-v1-small-001` selects the original six; `crew-v1-large-003` selects the released 800-person aggregate. No version merging; unknown versions fail startup. |
| `CREW_FAILURE_PROFILE` | `normal` | Exactly `normal`, `slow`, or `unavailable`; unknown values fail startup. |
| `CREW_PORT` | `8081` | Local listening port, 1..65535. |
| `CREW_BIND_HOST` | `127.0.0.1` | Local JVM loopback. Docker sets `0.0.0.0` internally; publish only on host loopback. |

Restart to change profile or snapshot. `normal` injects nothing. `slow` requests a 2,000 ms delay after validation and before every normal outcome, including CrewNotFound; actual elapsed latency includes overhead. `unavailable` returns ServiceUnavailable for valid requests, including valid IDs absent from the snapshot. InvalidRequest takes precedence in every profile. Profile selection never changes datasetVersion. Interrupted/unexpected service execution maps to InternalError. No fault-injection operation is exposed for InternalError; tests inject an internal dependency failure.

## Build, test and run

Run commands below from repository root. Replace `<absolute-repository-path>` in the optional Docker build command with your checkout path. A local build requires JDK 17 and Maven 3.9+; check `java -version` and `mvn -version` first. The tested container build provides both, so no host JDK installation is needed. Host Java 26 was detected in this review and was **not** used to build or run the service.

```text
# Existing offline contract suite (explicitly verified Python 3.13+).
python -B uss-enterprise/crew-personnel/validation/validate.py

# Local JDK 17 / Maven build; keep the Maven cache inside this repository.
mvn -B -ntp "-Dmaven.repo.local=<absolute-repository-path>/.cache/maven" -f uss-enterprise/crew-personnel/pom.xml clean verify

# Or use the tested Java 17 Maven image, writing build output and cache inside the repository.
docker run --rm --mount "type=bind,source=<absolute-repository-path>,target=/lab" -w /lab/uss-enterprise/crew-personnel maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82 mvn -B -ntp '-Dmaven.repo.local=/lab/.cache/maven' clean verify

# Local run with a Java 17 runtime; keep target/lib alongside the JAR.
java '-Dcom.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength=true' -jar uss-enterprise/crew-personnel/target/crew-personnel-1.0.0.jar
```

The Dockerfile pins both base-image digests, runs the Java tests during build, and copies only the application/resources plus runtime dependencies into a Java 17 JRE image running as UID 10001. No generated sources, fixtures for negative tests, build cache or IDE state enter the runtime image.

```text
docker build -t crew-personnel:v1 uss-enterprise/crew-personnel
docker run --rm --name crew-personnel -p 127.0.0.1:8081:8081 crew-personnel:v1
# In another terminal:
python -B uss-enterprise/crew-personnel/validation/smoke.py
# Stop the foreground container with Ctrl+C, or:
docker stop crew-personnel
```

Compose offers the same default endpoint:

```text
docker compose -f uss-enterprise/crew-personnel/compose.yaml up --build -d
python -B uss-enterprise/crew-personnel/validation/smoke.py
docker compose -f uss-enterprise/crew-personnel/compose.yaml down
```

For a standalone JVM, set `CREW_DATASET_VERSION` and `CREW_FAILURE_PROFILE` using your terminal's environment-variable syntax before launching Java, and unset them to restore defaults. Portable Docker examples for profile/snapshot selection:

```text
# Container: change configuration by starting a new run.
docker run --rm --name crew-unavailable -p 127.0.0.1:8082:8081 -e CREW_FAILURE_PROFILE=unavailable crew-personnel:v1
# Another terminal:
python -B uss-enterprise/crew-personnel/validation/smoke.py --endpoint http://127.0.0.1:8082/soap/crew-personnel --profile unavailable
docker stop crew-unavailable
```

Use `-e CREW_DATASET_VERSION=crew-v1-small-001` and smoke parameter `--dataset-version crew-v1-small-001` for the original snapshot. For a different host port, change the left side of Docker's mapping; the default container port stays 8081. Compose honors the dataset/profile environment variables shown in its file.

## Runtime validation evidence

The 2026-10-01 release adds `datasets/released/crew-v1-large-003/`, copied byte-for-byte from the retained proposal. Its raw manifest SHA-256 is `c06125dbe6883981293b485497474c46a0128372056efca389d7421f35ba2690`. A typed package registration pins that manifest and its size; all eight ordered pages are verified for raw length/hash, secure XSD validity, metadata, ordering and whole-dataset reporting readiness before publication. The strict JSON parser is the explicitly pinned Jackson dependency. Recipe semantics/reproducibility stay in the existing Python release validator. No Python is needed at Java startup. D017 CRLF normalization remains only for 001/002; 003 rejects changed bytes. Any selected-003 problem prevents startup without fallback. Get/List and the frozen 100-record ceiling remain unchanged.

The dataset 003 release-validation group, which ran under the legacy CPython 3.12.14 exception for the pinned generator and package checks, is not part of this repository's checks: dataset 003 is frozen by checksum and not regenerated here, and its released package is the reference. The component commands of that group stay as they were for anyone who runs them by hand from the repository root, with `uss-enterprise/requirements.txt`, Maven and JDK 17:

```sh
python -B -m unittest discover -s uss-enterprise/crew-personnel/validation/tests -p 'test_*.py' -v
mvn -B -ntp -f uss-enterprise/crew-personnel/pom.xml clean verify
python -B uss-enterprise/crew-personnel/validation/runtime_acceptance.py
```

`runtime_acceptance.py` checks the built JAR's exact approved resource inventory/bytes, starts temporary loopback JVMs for default/001/002/003 and unavailable-003 smoke, and verifies missing/tampered manifest/page variants exit without publication or fallback. It stops all child processes. The expanded Java HTTP tests cover arbitrary pagination, all filters, version restart and slow/unavailable profiles. For a separately running 003 process:

```sh
CREW_DATASET_VERSION=crew-v1-large-003 java -jar uss-enterprise/crew-personnel/target/crew-personnel-1.0.0.jar
# In another terminal:
python -B uss-enterprise/crew-personnel/validation/smoke.py --dataset-version crew-v1-large-003
```

The following 2026-09-30 evidence is historical; new results and Docker limitations are recorded in the [validation report](../../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md).

2026-09-30: **31 Java tests passed (10 loader/service, 21 real HTTP; zero failures/errors/skips)** on Temurin JDK 17.0.17+10 and Maven 3.9.11, including the fresh Docker build. The final container uses Temurin JRE 17.0.20.1+1. CXF is 4.2.3; JUnit is 5.11.4. See [the complete report](../../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md) for scope, results and file inventory.

Real SOAP HTTP tests cover success, original/latest dataset versions, full baseline response equivalence, pagination/filters/bounds, inactive/on-leave records, omitted supervisors, all four declared faults, schema-invalid requests and nil variants, unsafe/protocol XML, published WSDL/XSD, restart equivalence, slow/not-found timing and a 500 ms client timeout. Each successful application payload and declared fault detail is checked against the frozen XSD. Tests record a requested delay of exactly 2,000 ms; they do not assert exact wall-clock equality.

Windows-to-container smoke passed for normal on port 8081 (Get, page, CrewNotFound, InvalidRequest) and unavailable on port 8082 (both operations and invalid-request precedence), with XSD, HTTP status and fault QName/field assertions. Temporary test containers were stopped afterward. Maven reports are in ignored `target/surefire-reports/`; build logs and the local dependency cache are ignored under root `.cache/`.

The former .NET offline suite reported a supplementary-character limitation. The Python/lxml suite now checks acceptance of 100 and rejection of 101 supplementary characters; Java's configured validator also covers that boundary. Expected CXF codegen warning: the frozen WSDL declares no deployment service. SLF4J reports no provider and uses its no-op fallback; CXF's JUL logs still appear. Client-timeout tests may log a disconnected response writer. These are not test failures. No contract defect or reason to reopen the frozen contract was found. No source was staged or committed.

Dataset startup integrity uses canonical Git LF SHA-256 values, normalizing CRLF to LF for hashing only and parsing the original bytes. Frozen dataset files are not rewritten. The unchanged offline manifest validator still uses historical raw-byte hashes; see [integration notes](../../docs/INTEGRATION-NOTES.md).
