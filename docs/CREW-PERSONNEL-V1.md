# Crew & Personnel v1

Status: **FROZEN**, confirmed 2026-09-30. Executable XSD/WSDL, fixtures and offline checks now exist; no service exists yet. The wire semantics and six-record baseline below are unchanged. These are lab design choices, not claims about Star Trek canon.

## Purpose and ownership

Crew & Personnel is the ship's legacy personnel roster, implemented in Java with a SOAP/XML interface. Its planned component path is `uss-enterprise/crew-personnel/` inside `graphql-federation-lab`.

It owns crew identity, display name, rank, department, primary job, duty status, and reporting relationships. It does not own passwords, login accounts, mission assignments, shuttle schedules, maintenance, or inventory. LDAP is not required. Mission Operations owns mission participation; a person's ACTIVE status alone does not establish availability or permission for a mission.

V1 is read-only and serves a fixed synthetic snapshot. Changes occur by replacing a versioned fixture and restarting/resetting the service, not through public write operations. No GraphQL or MCP dependency is introduced in this component.

## Crew record

All fields are required unless marked optional. XML element order follows the table; collections retain the ordering defined below.

| Field | Type / rule | Meaning |
| --- | --- | --- |
| crewId | String matching exactly `CRW-[0-9]{4}`, excluding `CRW-0000` | Permanent, case-sensitive local key; preserve leading zeros; never derive another system's ID from it |
| displayName | Nonblank string, 1-100 characters | Display text, not a unique key; duplicate names are allowed |
| rank | Enum below | Personnel rank, distinct from job or authorization |
| department | Enum below | Exactly one primary department |
| positionTitle | Nonblank string, 1-100 characters | One primary job, e.g. Chief Engineer |
| dutyStatus | Enum below | Status in the fixed snapshot |
| supervisorCrewId | Optional crewId | Immediate supervisor; omission means "no supervisor recorded in this system"; no empty string or xsi:nil |

Ranks: `CAPTAIN`, `COMMANDER`, `LIEUTENANT_COMMANDER`, `LIEUTENANT`, `ENSIGN`, `CHIEF_PETTY_OFFICER`, `CREWMAN`, `CIVILIAN`.

Departments: `COMMAND`, `OPERATIONS`, `ENGINEERING`, `SCIENCE`, `MEDICAL`, `SECURITY`, `FLIGHT_OPERATIONS`.

Duty statuses: `ACTIVE`, `ON_LEAVE`, `INACTIVE`. Status carries no medical details. V1 excludes service histories, qualifications, shifts, family records, and medical records.

A crewId permanently identifies the same person across all supported USS Enterprise benchmark dataset versions. IDs are unique within a dataset and are never reassigned or reused, including after a person disappears from a later dataset. Preserve leading zeros and case; CRW-0000 is invalid.

An omitted supervisorCrewId means "no supervisor recorded in this system": the source intentionally cannot distinguish no supervisor from unknown/not recorded. Every present supervisorCrewId must resolve within the dataset. Inactive supervisors, cross-department reporting, and multiple hierarchy roots are allowed. Self-reference and cycles are invalid. Rank does not determine reporting order. Invalid fixtures prevent service readiness rather than being silently repaired.

## Native service contract

V1 binding: SOAP 1.1 over HTTP, document/literal wrapped, WSDL 1.1 with an XML Schema definition. The documentation rules below will be encoded and validated in WSDL/XSD before Java implementation; no separate draft schema artifact is required at this stage. Namespace: `urn:graphql-federation-lab:crew-personnel:v1`. Endpoint path: `/soap/crew-personnel`; host and port remain deployment configuration.

The XML namespace/version identifies the SOAP API contract. datasetVersion identifies exact immutable dataset content, not the API contract and not a freshness timestamp; clients cannot infer fact freshness from it. Any fixture-content change requires a new datasetVersion, and a previously published datasetVersion must never identify different content. Breaking wire-contract changes require a new contract/namespace version. Failure-profile selection does not change datasetVersion because it does not change dataset content.

Each operation uses `<OperationName>Request` and `<OperationName>Response` wrappers in the namespace above. SOAPAction is the namespace followed by `:` and the operation name. Successful operation responses begin with `datasetVersion` (baseline `crew-v1-small-001`). Record elements use the field order above. No response timestamp depends on the wall clock.

| Operation | Request fields in order | Response fields after datasetVersion |
| --- | --- | --- |
| GetCrewMember | crewId | Exactly one crewMember, or CrewNotFound fault |
| ListCrewMembers | Optional department, optional dutyStatus, optional offset, optional limit | Zero or more crewMember elements, totalCount, offset, limit, hasMore |

List filters use the exact enums above and combine with AND. An omitted filter means all values, including inactive personnel. Empty filters are invalid. Sort by crewId ascending before pagination. Offset is an integer from 0 through 2147483647, default 0; limit is an integer from 1 through 100, default 20. totalCount counts all matches before pagination. Return exactly min(limit, max(totalCount - offset, 0)) crewMember elements from the sorted matching records. Echo the effective offset and limit. hasMore is true exactly when offset plus returned count is less than totalCount. An offset at or beyond totalCount returns an empty list and hasMore=false. A no-match search is successful with totalCount=0. Consumers must compare datasetVersion on every page; if it changes between pages, discard all accumulated pages and restart at offset 0. There are no snapshot tokens. Compute pagination arithmetic without 32-bit overflow.

GetCrewMember returns records regardless of dutyStatus. No name-based lookup, batch lookup, create, update, or delete operation is part of v1. Do not add nested supervisor expansion, mission-aware filters, GraphQL cursors, or AI-specific fields. Consumers traverse supervisors client-side through GetCrewMember. Any later extension requires an explicit contract decision.

Requests reject unknown fields, duplicate scalar fields, malformed IDs, invalid enums, and invalid pagination; do not coerce case, trim IDs, or silently clamp values. XML parsing must disable DTDs and external entity resolution. Nonblank display text is validated when loading fixtures.

### XML/XSD semantics to encode

These rules complete the documentation contract; the eventual XSD must encode them and becomes the authoritative machine-validation artifact without silently changing this contract. Constraints that XSD 1.0 cannot express (such as reference integrity and pagination relationships) remain mandatory service/fixture validation rules.

- Use XSD 1.0, targetNamespace="urn:graphql-federation-lab:crew-personnel:v1", elementFormDefault="qualified", and attributeFormDefault="unqualified". All application wrappers, record fields, response metadata, and fault-detail elements are namespace-qualified. Prefix spelling is irrelevant; an unprefixed application element is valid only when its default namespace is correct. SOAP Envelope, Body, and Fault use the SOAP 1.1 namespace `http://schemas.xmlsoap.org/soap/envelope/`; SOAP 1.1 faultcode/faultstring/detail follow SOAP's own qualification rules, with CrewServiceFault inside detail.
- Use xs:sequence for every application complex type, in the exact order specified below and in the crew-field table. Optional omission skips that position; it does not permit reordering. Reject out-of-order elements, unknown elements, duplicate scalar elements, and incorrect namespaces. No application attributes or extension wildcards are defined.
- Every application element is nillable="false". The xsi:nil attribute is prohibited on all application elements, including optional elements, regardless of its value (true/1 or false/0). Namespace declarations are not application attributes.

The occurrence bounds below apply to each named child. Each successful SOAP Body contains exactly one operation response wrapper; each request Body contains exactly one operation request wrapper. A failed operation returns SOAP Fault instead of an operation response. CrewServiceFault occurs exactly once in detail for a declared fault.

| Parent | Children in order, with minOccurs..maxOccurs | Type / content |
| --- | --- | --- |
| GetCrewMemberRequest | crewId 1..1 | CrewId |
| GetCrewMemberResponse | datasetVersion 1..1, crewMember 1..1 | DatasetVersion, CrewMember |
| ListCrewMembersRequest | department 0..1, dutyStatus 0..1, offset 0..1, limit 0..1 | Department, DutyStatus, Offset, Limit |
| ListCrewMembersResponse | datasetVersion 1..1, crewMember 0..100, totalCount 1..1, offset 1..1, limit 1..1, hasMore 1..1 | DatasetVersion, CrewMember, Count, Offset, Limit, xs:boolean |
| CrewMember (each crewMember) | crewId, displayName, rank, department, positionTitle, dutyStatus each 1..1; supervisorCrewId 0..1, last | Types from the crew-field table; supervisorCrewId uses CrewId |
| CrewServiceFault | code 1..1, message 1..1, field 0..1 | FaultCode, FaultMessage, RequestField |

| Scalar type | XSD base / facets and additional validation |
| --- | --- |
| CrewId | xs:string; whiteSpace=preserve; length=8; full value matches `CRW-[0-9]{4}` and is not CRW-0000 (encode the exclusion as a schema restriction, not just a lookup miss) |
| DisplayName / PositionTitle | xs:string; whiteSpace=preserve; minLength=1, maxLength=100 XML characters; must contain at least one character other than XML whitespace (space, tab, CR, LF) |
| Rank / Department / DutyStatus | xs:string; whiteSpace=preserve; closed, case-sensitive enumerations listed above |
| DatasetVersion | xs:string; whiteSpace=preserve; minLength=1, maxLength=64; entire value matches `[a-z0-9]+(-[a-z0-9]+)*`; an opaque, registered immutable dataset identifier, baseline crew-v1-small-001 |
| Offset / Count | xs:int; minInclusive=0, maxInclusive=2147483647; Count is used by totalCount; reject oversized fixtures rather than truncate counts |
| Limit | xs:int; minInclusive=1, maxInclusive=100 |
| hasMore | xs:boolean; accept standard lexical values true/false/1/0; emit true/false |
| FaultCode | xs:string; whiteSpace=preserve; closed enumeration InvalidRequest, CrewNotFound, ServiceUnavailable, InternalError |
| FaultMessage | xs:string; whiteSpace=preserve; minLength=1, maxLength=512; nonblank by the display-text rule; prose is not a stable comparison key |
| RequestField | xs:string; whiteSpace=preserve; closed enumeration crewId, department, dutyStatus, offset, limit |

Encode and test full-value lexical constraints in the eventual schema, including rejection of surrounding characters. For numeric and boolean types, XSD whiteSpace=collapse applies: surrounding XML whitespace is accepted; xs:int lexical forms such as +02 and 002 mean 2, while decimals, exponent notation, blank content, and embedded spaces are invalid. Emit integers as plain decimal digits. No other trimming, case folding, or Unicode normalization is allowed. String whitespace is preserved after standard XML parsing (including XML line-ending and entity processing); leading/trailing whitespace in IDs, enums, and datasetVersion therefore fails validation. Preserve nonblank display text, including its meaningful spaces. Inter-element formatting whitespace has no business meaning; non-whitespace mixed content is invalid in application complex types.

Omission is the only way to request defaults or express an absent optional value. An omitted department/dutyStatus means no filter; an omitted offset/limit means 0/20. Empty or whitespace-only optional request elements are invalid, as is any xsi:nil attribute; they never mean omission. An omitted supervisorCrewId has the meaning stated above; an empty, whitespace-only, or xsi:nil-bearing supervisorCrewId makes the fixture invalid. An omitted fault field means the offending request field is not known/applicable; empty/nil field is invalid. Required scalar elements may never be omitted or empty. An empty ListCrewMembersRequest is valid and selects all defaults; zero crewMember elements in a list response is valid, with required metadata still present.

### Faults

SOAP faults use HTTP 500 for the declared faults below; normal operation responses use HTTP 200. The SOAP 1.1 faultcode is Client for caller errors and Server for service failures. The namespaced detail element `CrewServiceFault` contains, in order, `code`, `message`, and optional `field`. Clients assert code/field, not exact human-readable message text. Do not expose stack traces or credentials.

| Detail code | SOAP faultcode | Trigger |
| --- | --- | --- |
| InvalidRequest | Client | Invalid request; field identifies the offending declared request field when known; omit it for unknown element names or wrapper-level errors |
| CrewNotFound | Client | Well-formed crewId absent from snapshot; field=crewId |
| ServiceUnavailable | Server | Explicit failure profile below |
| InternalError | Server | Unexpected server error |

Malformed XML, unsupported SOAP versions, and transport failures are separate protocol/transport tests; the declared business fault contract does not imply that every infrastructure failure returns a parseable SOAP fault.

## Small baseline fixture

The hand-authored dataset `crew-v1-small-001` contains exactly these six records. It is deterministic without a random generator. A future large profile will separately pin its seed, generator version, fixed reference time, and hashes. The names are fictional examples; all IDs and assignments below are lab inventions.

| crewId | displayName | rank | department | positionTitle | dutyStatus | supervisorCrewId |
| --- | --- | --- | --- | --- | --- | --- |
| CRW-1047 | Jean-Luc Picard | CAPTAIN | COMMAND | Commanding Officer | ACTIVE | omitted |
| CRW-1048 | William Riker | COMMANDER | COMMAND | First Officer | ACTIVE | CRW-1047 |
| CRW-1049 | Geordi La Forge | LIEUTENANT_COMMANDER | ENGINEERING | Chief Engineer | ACTIVE | CRW-1048 |
| CRW-1050 | Data | LIEUTENANT_COMMANDER | OPERATIONS | Operations Officer | ACTIVE | CRW-1048 |
| CRW-1051 | Mara Venn | LIEUTENANT | FLIGHT_OPERATIONS | Shuttle Pilot | ON_LEAVE | CRW-1048 |
| CRW-1052 | Elias Renn | ENSIGN | ENGINEERING | Engineering Technician | INACTIVE | CRW-1049 |

## Separate validation and negative coverage

Keep the six baseline records above unchanged. Define small, named, deterministic validation fixtures and request/response tests separately when implementation starts. Any separately served dataset content gets its own datasetVersion; invalid fixtures are loader tests and must never be served. These cases are specifications, not tests already executed.

| Case | Expected assertion |
| --- | --- |
| Leading-zero identity | Valid separate record CRW-0007 round-trips exactly and sorts lexically; CRW-0000, crw-0007, padded IDs, and wrong-length IDs are InvalidRequest in requests and rejected in fixtures |
| Duplicate display names | Two distinct valid crew IDs named Alex Smith load successfully and remain separate records; duplicate crew IDs fail readiness |
| XML escaping | Display text `R&D <Systems>` round-trips as that parsed text, using valid XML escaping; markup must not become child elements |
| Optional request elements | For each department, dutyStatus, offset, and limit, omission applies its documented behavior; empty, whitespace-only, and xsi:nil (true/1/false/0) are InvalidRequest; wrong order, namespace, and duplicate/unknown fields are InvalidRequest |
| Optional supervisor | Omission is valid and remains omitted on output; empty, whitespace-only, and xsi:nil (true/1/false/0) prevent fixture readiness |
| Valid reporting variants | Inactive supervisor, cross-department supervisor, and multiple roots load successfully; no rank-based reporting rule is imposed |
| Invalid reporting variants | Separate dangling present reference, self-reference, and multi-record supervisor cycle each prevent readiness |
| Text and scalar bounds | Blank/overlong display text, invalid datasetVersion, and out-of-range counts fail fixture validation; request offset/limit bounds and documented numeric whitespace/lexical forms are tested |
| Beyond last page | Baseline offset=7 and offset=2147483647 return no crewMember, totalCount=6, echoed offset, limit=20, hasMore=false; offset=6 covers the exact boundary |
| Dataset replacement between pages | Deterministic consumer test supplies different datasetVersions across pages; consumer discards accumulated pages and restarts at offset 0 rather than combining them |

Compare responses semantically after namespace-aware XML parsing: compare expanded names (namespace URI and local name), element order, typed scalar values, preserved display text, element presence, records, and pagination metadata. Ignore prefix choices, namespace-declaration placement, attribute order, XML declaration/formatting differences, and equivalent escaping that do not change meaning. Omitted, empty, and nil elements remain distinct; do not trim string values or reorder children during comparison. Assert fault code/field and SOAP faultcode by meaning, not exact human-readable message text or raw response bytes. Fixture-file hashes may still pin exact stored artifacts; they are not the response equivalence rule.

## Cross-system identifiers

The native SOAP record exposes only crewId. The shared Integration & Benchmark layer owns the external-ID mapping component: its schema, versioned releases, validation, and interpretation of resolution outcomes. Native-system owners supply their key definitions and mappings; adapters consume the shared rules and must not silently invent incompatible interpretations. A separate shared, versioned mapping fixture will link external keys to crewId; it is not an LDAP directory or a crew-service responsibility. Mapping keys are (sourceSystem, externalId), preserving source types and exact values. Never join by displayName, strip `CRW-`, or infer that equal-looking numbers identify the same person.

For the first mapping example, retain the architecture's illustrative association: Mission Operations integer `1047`, Engineering & Inventory integer `847293`, and Shuttle & Logistics string `PICARD-JL` each resolve explicitly to `CRW-1047`. The remaining mappings will be specified with their owning systems.

Resolution rules for the future integration layer: zero candidates is UNMAPPED; one existing crew target is RESOLVED; multiple distinct targets is AMBIGUOUS; a single nonexistent crew target is DANGLING. Never choose the first ambiguous match. Those are mapping outcomes, not SOAP crew-service faults. Controlled mapping profiles must identify which entries are altered and their expected outcomes.

For the Shuttlecraft 04 scenario, Crew & Personnel supplies descriptive crew facts only. A pilot on leave must not be substituted for the maintenance/inventory explanation owned by the other systems.

## Local execution and controlled failures

Initial scope is a local synthetic-data lab without application authentication. Publish the service only on host loopback; avoid public exposure. Authentication/authorization is a separate future contract decision, and personnel rank is never an access-control rule.

Select failure profiles through startup configuration, outside the public SOAP contract:

- `normal`: baseline snapshot, no injected delay or fault.
- `slow`: delay every otherwise valid operation by 2000 ms before its normal outcome, including CrewNotFound. Malformed requests still fail validation immediately.
- `unavailable`: every otherwise valid operation returns ServiceUnavailable; validation errors still return InvalidRequest.

Choose exactly one profile per run; restart with `normal` to reset it. Dataset content is identical in all profiles. A proposed timeout acceptance test uses a 500 ms client deadline against `slow` and asserts a client timeout; detailed benchmark timeout/retry policies remain separate and must be pinned before comparison. Do not claim exact wall-clock latency from the configured delay.

## Acceptance gate for implementation

1. WSDL/XSD validates and describes both operations, the exact enums and required/optional fields, and the declared fault detail. Sample requests/responses validate against it.
2. GetCrewMember(CRW-1047) returns Picard with no supervisor element; GetCrewMember(CRW-1052) returns the inactive record.
3. GetCrewMember(CRW-9999) returns CrewNotFound; `CRW-0000`, `crw-1047`, empty IDs, and `CRW-10470` return InvalidRequest.
4. Default listing returns all six records ordered CRW-1047 through CRW-1052, totalCount=6, offset=0, limit=20, hasMore=false.
5. With limit=2, offsets 0, 2, and 4 produce three nonoverlapping pages; hasMore is true, true, false. Offsets 6, 7, and 2147483647 return empty lists with totalCount=6 and hasMore=false.
6. department=ENGINEERING returns CRW-1049 and CRW-1052. Adding dutyStatus=ACTIVE returns only CRW-1049. department=MEDICAL returns an empty list with totalCount=0.
7. Negative offsets, limits 0/101, unknown enums, duplicate fields, and unknown fields return InvalidRequest.
8. Duplicate crew keys, dangling present supervisor references, self-reference, supervisor cycles, and blank names prevent fixture readiness. Omitted supervisors are valid. All separate validation cases above must pass without changing the six baseline records.
9. Repeated requests after restart with the same dataset have semantically equivalent payload content and identical element/record ordering under the comparison rules above. Pagination cannot drift within an immutable datasetVersion; consumers discard accumulated pages and restart if datasetVersion changes.
10. Failure profiles behave as defined and restarting in normal restores baseline results; unsafe XML cannot resolve external entities.
11. Later mapping tests cover resolved, unmapped, ambiguous, and dangling entries without heuristic joins; they are not prerequisites for the standalone SOAP service.

Historical pre-freeze readiness (superseded by the current status above): no unresolved Crew & Personnel v1 contract decision remains in this revision; formal freeze is still pending. Runtime/library/build-tool selection and the other systems' mapping contents are later implementation/integration choices, not blockers to freezing this contract.

Historical implementation plan at that revision: after the freeze decision, the next implementation step is to encode these rules in XSD, then WSDL and concrete fixture files, and choose and pin the Java runtime, SOAP library, and build tool. Validate native SOAP behavior before adding GraphQL.

Current implementation status (2026-09-30): the freeze was approved and [contract artifacts and offline validators](../uss-enterprise/crew-personnel/README.md) exist. Dataset 001 remains immutable; 002 adds six records under the same contract. Java/SOAP stack selection and runtime acceptance remain next.
