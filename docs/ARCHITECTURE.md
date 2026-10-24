# Architecture

Status: Crew & Personnel is implemented; other native systems and integration layers remain conceptual/planned. See the implemented runtime section below.

## Stable enterprise model

**USS Enterprise (NCC-1701-D)** is the fictional enterprise used throughout the lab. It is a stable, intentionally messy legacy environment whose vocabulary, native contracts, relationships, and scenarios are shared across integration comparisons. Data is synthetic and contains no real customer or employee records. The Star Trek framing does not imply a unified database or futuristic technology.

| Subsystem | Native technology | Responsibility | Example local crew identifier |
| --- | --- | --- | --- |
| Crew & Personnel | Java / SOAP / XML | Identity, descriptive personnel facts, primary department/position, duty status, and reporting relationships | `crewId: "CRW-1047"` |
| Missions (Mission Operations) | Java / Jersey JAX-RS / JAXB XML / Apache Tomcat / Oracle 18c / plain JDBC | Mission data and personnel/asset assignments by ID | `commandingOfficerId: "C-2047"` (canonical C-* string reference) |
| Engineering & Inventory | Oracle Database | Components, stock, and maintenance dependencies | `personnel_key: 847293` |
| Shuttle & Logistics | Python / REST / JSON | Shuttle availability, logistics, and replacement shipments | `assignedCrew: "PICARD-JL"` |

The [Missions v1 design](MISSIONS-V1-DESIGN.md) is documentation-only under D027/D032/D033: circa-2010-or-earlier native architecture in the 2366 / TNG Season 3 calendar. Missions knows no graphs or federation. Locked resource, audit, concurrency, filtering and pagination decisions are recorded there; the agreed design is frozen, with narrow wire edge cases explicitly identified for clarification before executable contract work. Oracle 18c/plain JDBC, separate sequence-backed mission/change identities and a strong ETag derived from decimal changeId, lifecycle-dependent NUMBER(15,2) costs, atomic resource/audit persistence and indefinite audit retention are decided. The [2026-10-09 schema/dataset amendment](MISSIONS-V1-DESIGN.md#dataset-and-physical-schema-amendment-2026-10-09) requires 20..100 curated missions from 2366 onward, at least 60 meaningful uneven changes, independent immutable dataset versions and a transactional synthetic clock. MAINTENANCE is planned for separate compatible contract 1.1; 1.0 remains unchanged. No schema, dataset or runtime acceptance is supplied by that design promotion. Missions owns RESOURCE integrity. Future SOA/BPM/BPEL above the legacy services owns PROCESS integrity: transition legality, approval sequence, authority, command-chain/clearance, asset availability and cross-service rules. Direct legacy REST may bypass those process rules while satisfying local resource invariants; this is intentional. Future orchestration may coordinate Personnel SOAP, Missions REST, Assets and human workflows/rules. The [WIP SOA/BPM requirements](FUTURE-SOA-BPM-REQUIREMENTS.md) target Oracle SOA Suite/BPM 12.2.1.4, including compensation/bonus and cost-approval processes. GraphQL Federation remains the future modern API/data-composition layer; process-sensitive mutations express business commands handled by the process layer. Analytics is outside SOA responsibility. Future Assets is undesigned, and its relationship to the earlier Engineering / Shuttle concepts is unresolved. The scenario below remains a proposal, not an Assets contract.

Identifiers deliberately differ by system. Under D032, Missions commander, assignedCrewIds and both mutation audit actors use C-only references with grammar `^C-[1-9][0-9]*$`; participantIds accepts `^P-[1-9][0-9]*$` or `^O-[1-9][0-9]*$` only, excluding C-* in v1. D033 fixes canonical decimal references, XML/media/error behavior, database millisecond timestamps, required audit-summary metadata and deterministic collection serialization in the owning design; its residual wire items and historical mapping semantics remain open. Assignment implies Starfleet responsibility/SFR obligations; participation supplies neither assignment obligations nor mutation authority. assignedAssetIds remains assets only with grammar `^[A-Z]{2,5}-[1-9][0-9]*$`. These are Missions-local classes; syntax proves no Personnel identity, and O makes no Personnel membership claim or richer ontology. The other illustrative keys are not new schema contracts. Define explicit, versioned mappings and expected missing/ambiguous-match behavior. Do not silently normalize the source systems into a single identifier scheme.

The shared Integration & Benchmark layer is the accountable owner of the external-ID mapping component, including its schema, versioned releases, validation, and interpretation of resolution outcomes. Native-system owners supply their key definitions and mapping entries. The component stays outside Crew & Personnel; all adapters use the shared rules and must not silently invent incompatible mappings. Mission participation and assignments remain owned by Mission Operations.

The first proposed cross-system question is: "Why is Shuttlecraft 04 unavailable for the mission to Minos?" Mission Operations identifies the required shuttle; Shuttle & Logistics reports maintenance; a maintenance record references component EPS-441; Engineering & Inventory reports no stock; logistics records explain the delayed replacement shipment. Crew & Personnel supplies crew details through explicit identifier mappings. Confirm ownership, entity keys, pagination, and business invariants before implementation.

Start with the [frozen Crew & Personnel v1 contract](CREW-PERSONNEL-V1.md) and its native data/interface contract. Build and validate the legacy environment independently before adding GraphQL. Expand it only through versioned contract changes shared by every adapter.

## Approved identity evolution (2026-10-02)

The [Personnel v2 and Missions identity design](PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md) records the approved stable Personnel parent identity, crew/civilian choice, independent Missions C/P/O references and explicit mapping boundary. It governs that future identity direction; the table above retains the implemented Personnel v1 key and earlier illustrative system sketches. The recovered [Missions design](MISSIONS-V1-DESIGN.md#current-identity-reconciliation-2026-10-03) preserves the completed resource design and records D032's settled C/P/O field eligibility. Explicit mappings may relate historical P and later C references to one PRS identity; mapping time/version semantics and the listed wire precision remain open before executable contract work. No frozen v1 contract or historical dataset is changed.

## Logical boundaries

```text
Acceptance runner / benchmark driver           Later: AI agent
                  |                                  |
       Selected federation gateway                MCP/tools
         Apollo | Cosmo | Hive                 /             \
                  |                    validated graph    direct adapters
       Shared business subgraphs                     |          |
                  +----------------------------------+----------+
                                                     |
                          Stable USS Enterprise legacy systems
                     Java/SOAP | Java/REST | Oracle DB | Python/REST
                                                     |
                          Deterministic fixtures and failure profiles
```

Only one selected platform is needed for a given comparable run. Exact router, composition tooling, registry/control-plane components, and deployment modes will be chosen and pinned separately; the diagram does not imply identical vendor architectures. Graph-backed and direct-service MCP/AI approaches are separate experiments against the same native systems, not equivalent router-performance measurements.

Shared assets: legacy contracts, identifier mappings, fixtures, failure profiles, business schemas, resolvers where compatible, operation documents, expected results, and measurement protocol. Adapter-owned assets: platform composition, routing, startup, configuration, and any necessary compatibility changes. Record those changes so they cannot silently alter the workload.

The planned legacy-system component is named `uss-enterprise`. This replaces the ACME naming convention in the design; no `acme-enterprise` component references or existing component directories were found to rename. The repository name remains `graphql-federation-lab`.

## Controlled failures

Version opt-in scenarios for slow or unavailable services, stale inventory, inconsistent crew identifiers, missing maintenance records, and engineering authentication failures. Each profile specifies its trigger, expected outcome, timeout, and reset procedure. Run identical profiles across eligible adapters and restore the baseline between trials. Failures are deliberate benchmark inputs, not random faults that invalidate reproducibility.

## Deterministic data

Crew & Personnel v1 starts with six hand-authored canonical records and separate small deterministic validation/negative fixtures; no generator is required for this baseline. Its namespace versions the API contract, while datasetVersion identifies immutable content, not freshness. Content changes require a new datasetVersion; breaking wire changes require a new contract/namespace version. Paginated consumers restart if datasetVersion changes between pages.

For future generated dataset profiles, use a fixed, committed seed with a pinned pseudorandom generator algorithm and generator version. The literal seed remains to be selected. Derive stable IDs and relationships deterministically; use a fixed reference clock and explicit ordering, locale, and timezone rules. A seed alone is insufficient if wall-clock time or unpinned dependencies affect output.

Version dataset profiles and record record-count parameters plus output hashes. Reset mutable state to the same fixture snapshot before each comparable trial. Shared fixtures are the oracle for acceptance assertions.

## Measurement and observability

Collect client-side latency and errors alongside gateway/subgraph resource metrics. Keep instrumentation and resource limits comparable. Record runtime topology and configuration with results; isolate platform-specific features into separate experiments. Correctness is a prerequisite for performance interpretation.

## Later MCP/AI-agent layer

Build the interface that lets someone say "Computer..." to a messy enterprise. Expose bounded tasks through an MCP server backed by the validated graph; later compare direct-service adapters against the same scenario contracts and expected outcomes. Keep authentication and authorization enforced by services, validate tool inputs, and define separate read/write capabilities before enabling mutations. Evaluate agent task outcomes, tool errors, latency, and cost separately from federation benchmarks; record model and prompt versions for those experiments.

## Open details

Missions v1 design and Oracle Database 18c are selected under D027; Personnel retains its frozen contract and pinned implemented runtime. Remaining Missions runtime/library/driver pins and executable schema details, other unimplemented service contracts, shared mapping releases, integration authorization, federation feature subset, platform components and deployment layout remain future work. No current platform capability or compatibility is assumed without version-specific verification during implementation.

## Crew & Personnel implemented runtime (2026-09-30)

Current extension (2026-10-01): explicit typed registrations select legacy 001/002 snapshots or the released 003 package; 002 remains default. `DatasetPackage` eagerly reads the pinned raw manifest and eight exact page resources with bounded reads, strict JSON structure/types/duplicate-key rejection, raw page hash/length checks and secure frozen-XSD validation. Page metadata and strictly increasing IDs are checked before building one defensively copied immutable 800-record `Dataset`; supervisor resolution/cycle checks run over that whole aggregate. `Main` publishes only after successful loading. No request-time resource access, scanning, path/URL selectors, hot reload or fallback exists. Get/List use the existing unchanged `CrewService`, so storage boundaries are invisible and responses remain capped at 100. D017 hash normalization applies only to legacy 001/002. The initial implementation description below is retained as dated context.

Crew & Personnel v1 now has a standalone Java 17 / Apache CXF 4.2.3 JAX-WS service with embedded Jetty HTTP transport and a Maven build. The committed WSDL/XSD drive generated Java; a separate deployment descriptor imports the frozen binding. No Spring application framework is used. See D016 in [Decisions](../project-governance/DECISIONS.md).

The request path is secure SOAP/XML parsing, frozen-XSD validation before JAXB binding, generated JAX-WS dispatch, deterministic profile handling, and a read-only fixture lookup/page operation. Declared faults retain the frozen SOAP Client/Server distinction. Startup checks registered snapshot hashes, schema validity, unique IDs and supervisor integrity before listening. Default dataset 002 contains 12 records; 001 remains independently selectable. The public operation set is exactly GetCrewMember and ListCrewMembers.

Local JVM runs bind `127.0.0.1:8081`; the container listens on its internal interface and Compose publishes only `127.0.0.1:8081`. The path is `/soap/crew-personnel`. Containerization serves lab reproducibility and does not imply that the fictional original deployment used containers. Other native systems and integration layers remain future work.

## Personnel v2 prepared runtime (2026-10-02)

[Personnel v2](PERSONNEL-V2.md) is implemented alongside v1 in a separate component, namespace and endpoint. Stable PRS identity contains a required crew/civilian choice; Get/List remain common. Two raw-hash-registered snapshots retain Wesley's identity across subtype change. Semantic disagreement between bounded contexts MUST NOT be erased merely because a canonical model could make them agree (D021); Personnel does not consume Missions C/P/O or infer suffix mappings. See [validation](PERSONNEL-V2-VALIDATION.md) for measured checks and limitations. This prepared transaction is not a frozen-contract change, commit or manual acceptance.
