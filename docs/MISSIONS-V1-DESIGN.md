# Missions v1 design

Status: **design frozen**, 2026-10-01, to the agreed scope below. D027 in [Decisions](../project-governance/DECISIONS.md) records the original freeze; D032 settles assignment/participation, D033 records the 2026-10-03 wire precision and D034 settles the residual wire precision on 2026-10-06. This is a documentation freeze, not an executable XSD release, service implementation, dataset release or acceptance result. Deferred implementation and dataset work is explicitly listed at the end rather than silently invented. “Missions” is the service previously called “Mission Operations”; D015 ownership remains binding.

## Recovery provenance (2026-10-03)

Recovered from stash lab commit `a3e052f3b806b6a994b052babdc3be70b133b977`, parent lab commit `cf114eb821e76a61cbc2311443681c2e2b466e6b`, index parent lab commit `32840fbc5aa07643cb562474277c1611f62931f5`. Its index and working trees are identical: `359e47a8466ebc4a88f30d3ea58d96cf2f06ef25`. Original design blob: `99c07651ace20a1c950890375a813a3f94e75891`. Recovery starts from authoritative main lab commit `f00b38ed89a0ab49341339ff63c52b6a6facf870`; the stash and unrelated refs remain preserved. Historical Missions G019 and SOA/BPM D020 become D027/D028 to avoid current governance collisions. The 2026-10-01 freeze is retained; recovery does not freeze unspecified wire rules or authorize implementation.

## Current identity reconciliation (2026-10-03)

Current D021 and the [approved identity design](PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md#missions-independent-cpo-references) establish Missions' independent C/P/O worldview and Personnel's stable PRS identity. The field-specific clarification approved by the lead developer is recorded in D032: assignment implies Starfleet responsibility; participation does not. Only Crew may be assigned to a Starfleet mission or perform/authorize mission mutations. Non-Crew Personnel and Other references may participate in mission context without acquiring Starfleet assignment obligations or mutation authority.

`commandingOfficerId` and `assignedCrewIds` accept C-* only. `assignedCrewIds` replaces `assignedPersonnelIds`: these Crew references are formally assigned to the Starfleet mission and answer to SFR obligations. `participantIds` accepts non-Crew P-* or O-* references only; participants do not acquire Starfleet assignment obligations or mutation authority. C-* MUST NOT appear in `participantIds` in v1; assignment and participation sets are semantically disjoint. The audit performer `changedBy` and authorizer/orderer `orderedBy` accept C-* only. `assignedAssetIds` remains assets only.

C/P/O are Missions-local reference classes; their syntax does not prove Personnel identity or current Personnel subtype. Explicit mappings may relate historical P and later C references to one PRS identity over time. O carries no Personnel membership claim and defines no richer ontology. D032 settles eligibility; D033 supplies the wire precision below without implementing code.

Personnel v2 exists at runtime checkpoint lab commit `5270c98d20102c1d1b38470ebe3df1563adbe369`, with PRS identity and crew clearance NONE/SECRET/TOP_SECRET; see the lab's Progress section "Personnel v2 committed runtime (2026-10-02)" (the lab path `docs/PROGRESS.md`, at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`) and the [current status](PROGRESS.md#the-systems). The original v1 mapping example below is historical illustration, not a suffix-based mapping rule or the current v2 key. D015 mappings must explicitly represent historical context and missing/ambiguous/dangling outcomes; temporal/version rules belong to the Integration & Benchmark layer under D015, not to Missions (D034). Personnel never consumes Missions classifications; historical P and later C references may map to the same PRS identity. The Missions-only O example creates no Personnel identity or inferred ontology. Current facts supersede original deferred-v2 wording without changing mission classification, resource ownership or the process boundary.

## The reference classes C, P and O (2026-10-19)

The lead developer's definitions of October 19, 2026 ([D045](../project-governance/DECISIONS.md#d045---missions-dataset-release-12-participants-reclassified-as-p-and-o-2026-10-19-accepted-scope)) say what the three classes mean. They change neither the grammar nor the eligibility rules of D032, and the classes stay Missions-local (D021).

- **C, Crew.** Starfleet crew members, assigned to missions with obligations. `commandingOfficerId` and `assignedCrewIds` take C references only, and a C reference never appears in `participantIds`.
- **P, Personnel.** The lead developer's ruling: P was meant to be Personnel, the people on the Enterprise who work there and are not crew members. They are the civilians of the Personnel v2 roster, such as Guinan, teachers, Ten Forward staff, residents and their families. A P reference names one such person by exact display name, so that a mapping can resolve it; a P reference that names no roster civilian is a defect of the data.
- **O, Outsiders.** The lead developer's ruling: O is not for groups and objects but for Outsiders, the Others, and it says entities because Star Trek has all sorts of creatures, humanoids and other entities. Anyone not on the ship's roster is an O: colonists, delegates, patients, visiting cadets such as the returning Wesley Crusher, creatures and any other entity. An O reference is never mapped to a Personnel identity.

`participantIds` takes P and O references only. Releases 1.0 and 1.1 used P for outsiders and for placeholders (only 2 of their 118 distinct P references name a roster civilian) and O for groups and objects; they are immutable and keep that classification as history. [Release 1.2](#release-12-the-participants-reclassified-2026-10-19) applies the definitions.

## Historical premise and native technology

The original premise is the Enterprise-D in 2366 / TNG Season 3 with circa-2010-or-earlier native architecture. The 2026-10-09 dataset amendment below extends curated content to 2366 onward, including later seasons, without changing the native architecture. Technology era and fictional calendar are separate; this is not episode chronology. Use REST/HTTP, application/xml, Java/Jersey/JAX-RS, JAXB and Apache Tomcat, with javax-era concepts. Persistence is **Oracle Database 18c through plain JDBC**. The minimum supported Java is **JDK 17**; later JDKs are supported, and the implementation MUST NOT require anything newer than JDK 17 (D034 extension, 2026-10-06). The exact compatible library, container and driver versions (Jersey, Tomcat, Oracle JDBC) remain implementation-time choices; authenticity does not require unsafe ancient binaries.

Native request path: HTTP client -> Tomcat -> Jersey/JAX-RS resource -> repository -> Oracle 18c, with JAXB XML representations. No classes, database schema or runtime exist from this design. Indexes, JNDI/pooling and physical schema mechanics may be selected during implementation. Missions remains distinct from Crew & Personnel's SOAP service and unaware of GraphQL/federation under the [constraint that legacy systems stay unaware of the integration layer](../project-governance/CONSTRAINTS.md#legacy-systems-stay-unaware-of-the-integration-layer).

## Ownership and identifiers

Missions owns mission resources, Crew/asset assignments and non-Crew participation by reference ID. Personnel owns personnel facts; asset-owning services own asset facts. No embedded personnel records, asset descriptions, read-time enrichment or cross-service existence, availability or clearance validation. Independent services may contain inconsistent references; assignments establish neither permission nor availability. Future Assets remains undesigned, including its relationship to earlier Engineering & Inventory / Shuttle & Logistics concepts.

- Crew references match `^C-[1-9][0-9]*$`: commandingOfficerId, assignedCrewIds, X-Starfleet-User and X-Starfleet-Ordered-By all use this grammar. Non-Crew participantIds accepts `^P-[1-9][0-9]*$` or `^O-[1-9][0-9]*$` only; C is excluded. Suffixes are positive canonical decimal integers, with no leading zeros, signs or padding. C/P/O classify Missions-local references, not proven Personnel identities.
- Asset references match `^[A-Z]{2,5}-[1-9][0-9]*$`, for example `SH-17`; the uppercase prefix has 2..5 letters and the positive decimal suffix has no leading zeros, signs or padding.
- IDs are validated exactly as sent: no case folding, trimming or identity normalization. Missions does not store `CRW-` personnel IDs. The historical v1 example `C-2047` <-> `CRW-2047` requires D015's explicit shared, versioned mapping, never suffix inference. `C-0` and padded forms are invalid; valid syntax alone establishes no Personnel identity.
- `missionId` is service-generated, immutable and unique, matching `^ST-[A-Z0-9]{9}$`. Generate it from a deliberately non-zero Oracle sequence encoded base-36 with alphabet `0-9A-Z`, zero-padded to the nine-character suffix. This missionId padding is the explicit exception to decimal reference rules. Overflow fails; never wrap, reuse or truncate IDs. It is opaque and carries no business meaning. The exact starting value belongs to later dataset design and represents substantial pre-Season-3 history.
- `changeId` is server-controlled and backed by its own Oracle sequence, separate from the missionId sequence. Its wire text matches `^[1-9][0-9]*$`: positive base-10 integer, no leading zeros, sign or padding, never base-36. Clients never choose or set it. It monotonically advances for each successful mutation, including unchanged-value PUTs; sequence gaps are permitted. Compare numerically internally, never lexically. The separate sequence and existing atomic/concurrency design must preserve this mutation ordering.
- The strong HTTP ETag is exactly the current changeId decimal text enclosed in double quotes, for example `ETag: "17"`. Every successful mutation renews it deterministically from that mutation's changeId. It is never an XML field. D033 supersedes the former independent ETag-sequence requirement: retain separate missionId/changeId sequences, not a third ETag identity.

## Lexical values

Ordinary strings preserve leading/trailing whitespace unless a field-specific rule says otherwise; empty is distinct from absent. No silent normalization beyond XML parsing is permitted. Enum tokens are exact and case-sensitive.

D034 settles two string rules. Every character bound in this design (title, objective, outcome, location name, coordinates, travelVector and the 256-character audit summary) counts **Unicode code points**, consistent with Personnel's code-point limits (D016); never UTF-16 code units, bytes or grapheme clusters. Every present string field whose minimum length is 1 (title, objective, outcome, location name, coordinates, travelVector) MUST contain at least one non-whitespace character; whitespace-only values fail with 422 DOMAIN_VALIDATION_FAILED, while an empty element fails its minimum length and an absent optional element is simply omitted. Leading and trailing whitespace of accepted values is preserved. The summary header applies the same non-whitespace rule and fails with 400 INVALID_REQUEST. Physical Oracle column types and byte limits (2000 characters can exceed a 4000-byte VARCHAR2 under multi-byte UTF-8) are implementation work; storage MUST NOT truncate silently.

Numeric fields use canonical base-10 text except missionId's specified base-36 payload: no scientific notation, leading `+`, NaN or Infinity. Integer text has no leading zeros (zero is `0` where allowed); negatives are allowed only where the field permits them. Decimal text uses an integral digit sequence with no redundant leading zeros and a fractional digit sequence separated by `.`, with no surrounding whitespace. Cost fields retain exactly two fractional digits; non-negative amounts match `^(0|[1-9][0-9]{0,12})\.[0-9]{2}$`. Signed audit cost changes permit a leading `-` for a negative difference, never `+` or negative zero, and retain the same bounds/two fractional digits. Stardate text matches exactly `^4[3-8][0-9]{3}\.[0-9][05]$`: five integral digits from 43000 through 48999 and exactly two fractional digits whose second digit is 0 or 5 (0.05 steps), so each value has a single spelling (`43125.80`, never `43125.8`). A lexical violation is a schema-invalid form (400 INVALID_REQUEST). Booleans, if present, use canonical XML `true`/`false`, never `1`/`0`.

## Mission model and cardinalities

The Mission representation uses the fixed schema element sequence in the field table below: participantIds follows assignedCrewIds and precedes assignedAssetIds. Costs follow assignedAssetIds and precede outcome. POST and PUT input exceptions for service-owned fields are specified below. Exactly-one cardinalities apply to the complete resource representation, not to forbidden POST input fields.

| Field | Cardinality / constraint |
| --- | --- |
| missionId | Exactly 1; generated immutable ID as above |
| title | Exactly 1; 1..120 characters; whitespace-only invalid |
| type | Exactly 1; mission-type enum below |
| classification | Exactly 1; classification enum below |
| status | Exactly 1; status enum below |
| priority | Exactly 1; integer 1..5: 1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL, 5 ROUTINE |
| stardate | Exactly 1; decimal per the lexical pattern above, 43000.00 <= stardate < 49000.00 (D034 widens D027's 44000.0 ceiling to cover the TNG run); scheduled/actual commencement; Oracle `NUMBER(7,2)`; preserve decimal, no Earth-date conversion |
| durationHours | Exactly 1; integer 1..8760; mission duration |
| objective | Exactly 1; 1..2000 characters; whitespace-only invalid |
| location | Exactly 1; structured location below |
| issuingAuthority | Exactly 1; issuing-authority enum below |
| commandingOfficerId | 0..1 in PLANNED/CANCELLED; exactly 1 in AUTHORIZED/ACTIVE/POSTPONED/COMPLETED/FAILED; C-* only, Crew grammar above |
| assignedCrewIds | Exactly 1 container; 0..100 C-* Crew references only; no duplicates; empty allowed; formal Starfleet assignment with SFR obligations |
| participantIds | Exactly 1 container; 0..* P-* or O-* references only; no duplicates; empty allowed; C-* MUST NOT appear; no Starfleet assignment obligations or mutation authority |
| assignedAssetIds | Exactly 1 container; 0..50 asset references only; no duplicates; empty allowed |
| estimatedCostCredits | 0..1 or exactly 1 per cost lifecycle table |
| actualCostCredits | Forbidden or exactly 1 per cost lifecycle table |
| outcome | 0..1; 1..2000 code points and not whitespace-only when present; optional in COMPLETED, FAILED and CANCELLED; forbidden in PLANNED, AUTHORIZED, ACTIVE and POSTPONED (422 DOMAIN_VALIDATION_FAILED). The service never requires it; dataset and process authors should populate it for COMPLETED/FAILED |
| lastUpdated | Exactly 1; service-owned ISO-8601 UTC timestamp in the canonical form below, with no contract constraint on the year; generated on POST and updated on successful PUT; clients omit it |

The three collections stay separate and are semantically unordered. Serialize each collection by ascending canonical lexical ID order (ordinal ASCII comparison), not input order or numeric suffix order; for example C-10 precedes C-2. Reject duplicates within each collection. The existing stronger finite maxima remain: assignedCrewIds is 0..100 and assignedAssetIds is 0..50; both retain a zero minimum. participantIds is 0..*. These maxima are preserved bounds, not minimum-cardinality discrepancies.

A commander does **not** have to appear in assignedCrewIds. Stardate and lastUpdated serve different purposes; neither derives from the other. Do not substitute the host date into mission content. Repository dates and lab log stardates use separate conventions.

Location has exactly one `type` and one `name` (1..120 characters). `coordinates` and `travelVector` each occur 0..1, with 1..120 characters when present; both are opaque strings, not interpreted by Missions. Location child order is type, name, coordinates, travelVector.

| Enum | Exact values |
| --- | --- |
| Mission type | DIPLOMATIC, EXPLORATION, SCIENTIFIC, FIRST_CONTACT, MEDICAL, RESCUE, HUMANITARIAN, SECURITY, TACTICAL, TRANSPORT |
| Classification | UNCLASSIFIED, SECRET, TOP_SECRET |
| Status | PLANNED, AUTHORIZED, ACTIVE, POSTPONED, COMPLETED, FAILED, CANCELLED |
| Location type | PLANET, STARBASE, VESSEL, SECTOR, DEEP_SPACE, ENTERPRISE, OTHER |
| Issuing authority | STARFLEET_COMMAND, ENTERPRISE_COMMAND, STARFLEET_MEDICAL, STARFLEET_SCIENCE, STARFLEET_SECURITY, FEDERATION_COUNCIL |

## Cost lifecycle invariants

`estimatedCostCredits` and `actualCostCredits` use Oracle `NUMBER(15,2)`: non-negative Mission amounts, at most 13 integral digits (maximum 9999999999999.99). XML has exactly two fractional digits, including `0.00`. Absence and zero are distinct. No currency-conversion or finance-line-item model is introduced.

| Resulting status | estimatedCostCredits | actualCostCredits |
| --- | --- | --- |
| PLANNED | Optional | Forbidden |
| AUTHORIZED, ACTIVE, POSTPONED | Required | Forbidden |
| COMPLETED, FAILED | Required | Required |
| CANCELLED with retained PLANNED-origin eligibility | Optional | Required; 0.00 valid |
| CANCELLED otherwise | Required | Required; 0.00 valid |

The CANCELLED estimate exception depends on cancellation provenance; resulting status alone is insufficient. This is a local cost invariant, not a general allowed-transition graph. PLANNED -> CANCELLED establishes eligibility to omit estimatedCostCredits. Repeated CANCELLED -> CANCELLED replacements preserve that eligibility. Leaving CANCELLED clears it; later re-entry evaluates the immediate predecessor anew. POST directly as CANCELLED requires estimatedCostCredits because no prior PLANNED state establishes the exemption. This provenance rule does not enforce lifecycle-transition legality.

## Resource integrity and future process integrity

Missions enforces local schema/value/enum validity, required fields/cardinalities, commander requiredness, cost invariants, identity integrity/immutability, stardate range, concurrency, XML structure and resource audit. It does **not** enforce lifecycle transition legality. `INVALID_STATUS_TRANSITION` does not exist in Missions v1.

Future [SOA/BPM requirements](FUTURE-SOA-BPM-REQUIREMENTS.md), Status: WIP, target Oracle SOA Suite/BPM 12.2.1.4. That layer owns process integrity: transition legality, approvals, authority/command chain, clearance, availability, compensation, human workflow and cross-service business rules. Direct legacy REST may therefore create process-invalid but resource-valid states. This is intentional.

PLANNED is proposed; AUTHORIZED is approved; ACTIVE is underway; POSTPONED is already-approved work deferred or suspended. The intended future process has **no PLANNED -> POSTPONED** transition. A direct REST replacement may nevertheless set POSTPONED if local resource invariants hold. CANCELLED may occur before approval and need not have a commander. COMPLETED, FAILED and CANCELLED have distinct terminal meanings. No complete BPEL workflow is designed here.

## REST API and concurrency

| Method/path | Behavior |
| --- | --- |
| GET /missions | Filtered, ordered, paginated collection |
| GET /missions/{missionId} | Mission XML and HTTP ETag |
| GET /missions/{missionId}/changes | Read-only, paginated resource audit |
| POST /missions | Client omits missionId/lastUpdated; service generates both; 201 Created with Location: /missions/{generated-id}, ETag and created Mission XML; append CREATED |
| PUT /missions/{missionId} | Full replacement, not PATCH; body missionId must equal URI ID (mismatch -> 409); client omits lastUpdated; service generates new lastUpdated/ETag; append UPDATED; return 200 OK with resulting Mission XML and new ETag |
| PATCH / DELETE / HEAD / OPTIONS | 405 METHOD_NOT_ALLOWED; unsupported (D034 adds HEAD and OPTIONS; they may be added later only if a need arises). The response carries an `Allow` header listing only the methods supported on that path: `GET, POST` for `/missions`; `GET, PUT` for `/missions/{missionId}`; `GET` for `/missions/{missionId}/changes`. The framework's automatic HEAD/OPTIONS handling MUST be disabled so it cannot answer them or add them to `Allow`. |

PUT If-Match accepts exactly one explicit strong tag in the quoted canonical changeId form `"[1-9][0-9]*"`. Wildcard `*`, weak tags, malformed/noncanonical tags, unsupported payload forms and multiple tags yield 400 INVALID_REQUEST. PUT requires matching `If-Match`: missing -> 428 PRECONDITION_REQUIRED; well-formed but stale/nonmatching strong tag -> 412 ETAG_MISMATCH. Successful mutation always advances ETag, including a successful PUT that does not change client-managed values. Full replacement grants no permission to alter identity or set service timestamps.

POST and PUT require `X-Starfleet-User` and `X-Starfleet-Ordered-By`, both syntax-validated canonical `C-*` Missions-local Crew references (`^C-[1-9][0-9]*$`). Only Crew may perform or authorize mission mutations; P-* and O-* are ineligible for both headers. They populate `changedBy` (who entered/performed) and `orderedBy` (who ordered/authorized). They may be identical; orderedBy need not be commandingOfficerId. No authentication, existence, rank, clearance, command-chain or authority validation is implied. Classification is metadata, not access control. Audit records assertions, not proof that they were true.

POST/PUT also require `X-Starfleet-Audit-Summary`: human-readable UTF-8 text, 1..256 characters, non-empty, with no silent trimming or normalization. It is request metadata alongside provenance, never a Mission XML field. Missing/empty/overlong or invalid summary metadata yields 400 INVALID_REQUEST; no successful mutation may omit it. Persist the exact accepted summary atomically with the Mission mutation, audit event and changeId. The existing change-log representation exposes summary; no new audit endpoint is introduced. The header field value is UTF-8 text; decoding must preserve that text exactly rather than applying a container-specific charset or normalization. Length counts Unicode code points and the value must contain a non-whitespace character, as settled in the lexical rules above. For this contract "whitespace" is exactly these code points: U+0009 to U+000D, U+001C to U+0020, U+1680, U+2000 to U+2006, U+2008 to U+200A, U+2028, U+2029, U+205F and U+3000. This is Java's `Character.isWhitespace` as of JDK 17, the comparison baseline for this rule, and unchanged through JDK 21 and 26 (JDK 8 also includes U+180E, which is why the set is pinned here: a Unicode update must not change the contract). An implementation on JDK 17 or later therefore agrees with this list; JDK 17 is also the Missions minimum (see [native technology](#historical-premise-and-native-technology)). The non-breaking spaces U+00A0, U+2007 and U+202F, and U+0085, U+200B and U+FEFF, are not whitespace. Implementations MUST test code points, not UTF-16 chars. XML 1.0 cannot carry U+000B, U+000C or U+001C to U+001F, so the XSD's summary pattern lists only the rest; those controls matter only in the request header. This deliberately differs from Personnel's XML-only definition: Missions is an independent bounded context (D021).

### Service-owned elements in request bodies

One `mission` element serves POST input, PUT input and responses, so `missionId` and `lastUpdated` are optional in the schema and their presence is checked by role. D034's 2026-10-06 extension settles the outcome: a request body carrying a service-owned element it must omit, or omitting one it must carry, is schema-valid but fails domain validation with **422 DOMAIN_VALIDATION_FAILED**.

| Request | `missionId` | `lastUpdated` |
| --- | --- | --- |
| POST | Must be absent (422 if present; the service generates it) | Must be absent (422 if present) |
| PUT | Required (422 if absent); a value differing from the URI ID remains 409 | Must be absent (422 if present) |

A client-supplied POST `missionId` is a forbidden field, not a uniqueness conflict, so it is not 409. Reference-class and grammar violations in any ID field, collection member or header are not part of this rule: they are grammar failures (400 INVALID_REQUEST). Fail-fast processing is unchanged and no ordering between these checks and others is defined.

## Media and XML

Namespace: `urn:starfleet:missions:v1`; encoding UTF-8. Mission, missionList, error and change representations use that namespace. Element order is fixed, schema-defined and JAXB/XSD-friendly. Mission order is the field-table order above; location and change order are their respective tables. Optional scalars are omitted when absent. All three collection containers occur exactly once, including empty `<assignedCrewIds/>`, `<participantIds/>` and `<assignedAssetIds/>`.

D034 settles the collection and list structure (all elements in the Missions namespace):

| Representation | Structure |
| --- | --- |
| `missionList` | Children in order: `page`, `pageSize`, `totalCount`, `totalPages`, then zero or more `mission` members directly, with no extra wrapper element. |
| `changeList` | The same four metadata children in that order, then zero or more `change` members directly. |
| `assignedCrewIds` | Zero or more `crewId` members (C-* grammar only). |
| `participantIds` | Zero or more `participantId` members (P-* or O-* grammar only; C-* excluded). |
| `assignedAssetIds` | Zero or more `assetId` members (asset grammar only). |

An empty page is the list element with its metadata and no members; zero matches report `totalPages` 0. Member names are deliberately container-specific, never a generic `id`, so each can carry its own XSD simple type and a misplaced class is a schema-invalid form (400) rather than a domain failure. Element-level patterns catch syntactic misplacement only; they prove no Personnel identity.

- Consume and produce XML only, canonical media type `application/xml`. No JSON fallback, content sniffing or vendor media type in v1; `text/xml` and `application/*+xml` are not aliases for request bodies.
- POST/PUT require Content-Type `application/xml`; missing or unsupported body media type yields 415 UNSUPPORTED_MEDIA_TYPE. XML bytes are UTF-8. Accept an absent charset or explicit UTF-8 charset; incompatible charsets yield 415. D034 closes the remaining Content-Type grammar without relying on Jersey-version matching: the type/subtype is compared case-insensitively; the only permitted parameter is `charset` (name and value case-insensitive, quoted or unquoted `utf-8`); any other parameter, a duplicate `charset`, an unparseable value or more than one Content-Type header yields 415 UNSUPPORTED_MEDIA_TYPE. An XML declaration naming a non-UTF-8 encoding yields 400 INVALID_REQUEST.
- Absent Accept, `Accept: application/xml` and `Accept: */*` are accepted; return XML. Honor quality exclusions: a most-specific applicable XML range with `q=0` excludes XML even when a less-specific wildcard allows it. A header with no acceptable XML range (including explicit exclusion) yields bodyless 406 Not Acceptable, with no XML error body. D034 closes the remaining Accept grammar: multiple Accept header lines combine as one comma-separated list; types are case-insensitive; the matching ranges are `application/xml`, `application/*` and `*/*`; only `q` (0 to 1, at most three decimals) is honored, `charset=utf-8` is tolerated, and any other non-`q` parameter makes that range non-matching without error. A malformed header (unparseable list, `q` outside 0..1, non-numeric `q` or an empty value) yields 400 INVALID_REQUEST with the usual XML error body, never a guessed match or a 406.
- Every XML response, including negotiated XML errors, explicitly uses `Content-Type: application/xml; charset=UTF-8` and UTF-8 bytes; any XML declaration must agree. Bodyless 406 has no representation Content-Type. Negotiation must be explicit and deterministic, independent of permissive Jersey defaults.
- Malformed XML or an XML schema-invalid body (including unknown elements/attributes, wrong order, xsi:nil, excess scalar/container elements or invalid schema lexical forms) yields 400 INVALID_REQUEST. A syntactically/schema-valid request failing domain validation yields 422 DOMAIN_VALIDATION_FAILED.
- Reject duplicate references within any collection; domain-level duplicate failures in otherwise schema-valid XML yield 422. Serialize accepted collections in canonical lexical order; caller order has no semantic meaning.
- No XML external entities; no DTD processing.

The executable XSD 1.0 is [missions-v1.0.xsd](../uss-enterprise/missions/contracts/missions-v1.0.xsd) in the Missions component. It expresses wire shape and lexical forms only; every rule listed as domain validation (422) in this design is outside it.

## Contract evolution

D034 settles how the Missions contract evolves. A contract version is MAJOR.MINOR. The **major** version is the namespace: `urn:starfleet:missions:v1` today, and a new major is a new namespace, component and endpoint, as Personnel v2 is beside v1. The **minor** version is not in the namespace; it is recorded in the XSD `version` attribute and the contract's revision history. The first executable contract is 1.0. This defines "breaking" for Missions without changing the general rule that breaking wire changes require a new contract/namespace version.

| Class | Changes | Version effect |
| --- | --- | --- |
| Compatible addition | New enum values; widened bounds, limits or patterns; new optional query filters, endpoints or methods; new error codes; new optional elements at a documented position | New minor, same namespace |
| Breaking change | Removing or renaming any enum value, element, field, endpoint or error code; narrowing a bound, pattern or cardinality; making an optional field required; changing element order, ID grammar, status mappings or the meaning of a value | New major, new namespace |

Each minor is a superset of the one before: anything valid under 1.n stays valid under 1.(n+1), except that newly added values or elements may appear in responses once data uses them. Strictness is unchanged: the server rejects unknown elements, attributes and enum tokens relative to the revision it implements. Each published minor revision of the XSD is a separate immutable file and is never edited afterward. There is no patch level; clarifications and errata go in the revision history. There is no wire marker (header or element) for runtime discovery of the minor; add one only if a need appears. Consumers carry no obligation to tolerate unknown values; a consumer that validates strictly against a pinned XSD refreshes it when the server's minor advances. The contract version is independent of any `datasetVersion` or dataset content. This rule binds Missions only and adds nothing for Personnel or other services.

## Collection filters, pagination and ordering

GET /missions defaults to `page=1&pageSize=20`. `page >= 1`; pageSize 1..50. Metadata: page, pageSize, totalCount, totalPages. Totals are calculated after filtering. Valid pages beyond the end return an empty collection; zero matches means totalPages=0. Repeated page or pageSize parameters are invalid (400 INVALID_REQUEST). Each response is internally consistent, but pagination is a live view with no cross-request snapshot guarantee. The collection representation provides no per-mission concurrency token: GET the individual mission to obtain its ETag before PUT.

Supported filters: type, classification, status, priority, issuingAuthority, commandingOfficerId, assignedCrewId, assignedAssetId, locationType. assignedCrewId replaces assignedPersonnelId to select assignedCrewIds membership; no participant filter is introduced. Combine supplied filters with AND; singular assignment filters select membership in the respective collections. An invalid recognized value, unknown query parameter or repeated scalar filter yields 400 INVALID_REQUEST. No implicit OR.

Order: stardate ASC, priority ASC, missionId ASC. No fuzzy title search, full-text objective search, sorting DSL, field selection or query language in v1.

## Errors

Use the common namespaced XML error below, except for the explicitly bodyless 406 response. An unknown path, which the frozen contract does not define, answers a bodyless 404, an open contract question left as decided ([Missions README](../uss-enterprise/missions/README.md)). HTTP status is authoritative; codes are deterministic and human messages are not intended for parsing. Never expose Java/Jersey internals. The `message` is 1..1000 Unicode code points of human-readable text, never a stack trace or framework detail; the service shortens a message that would exceed the bound rather than emit an invalid body.

```xml
<error xmlns="urn:starfleet:missions:v1">
  <code>...</code>
  <message>...</message>
</error>
```

| Status | Code / condition |
| --- | --- |
| 400 Bad Request | INVALID_REQUEST: malformed XML/schema-invalid body; malformed/unsupported If-Match form; missing/invalid required mutation metadata; invalid recognized query values, unknown parameters or repeated scalar filters |
| 400 Bad Request | INVALID_MISSION_ID: malformed mission ID |
| 404 Not Found | MISSION_NOT_FOUND: well-formed nonexistent mission, including its change-log endpoint |
| 405 Method Not Allowed | METHOD_NOT_ALLOWED: PATCH / DELETE / HEAD / OPTIONS, with an `Allow` header |
| 406 Not Acceptable | Bodyless when no acceptable XML representation exists, including explicit XML exclusion; no error code is serialized |
| 409 Conflict | RESOURCE_CONFLICT: detectable POST uniqueness/invariant conflict; PUT URI/body missionId mismatch remains 409 |
| 412 Precondition Failed | ETAG_MISMATCH: well-formed but stale/nonmatching strong If-Match tag |
| 415 Unsupported Media Type | UNSUPPORTED_MEDIA_TYPE: missing/unsupported POST/PUT body media type |
| 422 Unprocessable Entity | DOMAIN_VALIDATION_FAILED: syntactically/schema-valid request fails domain validation, including absent status-required commander, cost invariants, state-dependent `outcome`, collection duplicates, whitespace-only minimum-1 strings and misuse of the service-owned `missionId`/`lastUpdated` elements (see [Service-owned elements](#service-owned-elements-in-request-bodies)) and a valid reference longer than the 50-byte storage capacity (see the physical schema amendment). A reference of the wrong class or malformed grammar is never 422: it fails the field's grammar and is 400 INVALID_REQUEST |
| 428 Precondition Required | PRECONDITION_REQUIRED: missing If-Match on PUT |
| 500 Internal Server Error | INTERNAL_ERROR: unexpected server/database failure, including change-log repository failure |

Business/domain validation failures MUST NOT surface as 500. A detectable POST persistence uniqueness/invariant conflict is 409; ordinary domain validation remains 422. The former blanket business-conflict 409 and backend-failure 503 mappings are superseded by D033; Missions v1 does not map unexpected database failure to 503.

No INVALID_STATUS_TRANSITION. Request processing remains intentionally fail-fast: return the first encountered validation or processing failure and stop, without aggregation. Later defects may surface after correction and resubmission. No global error-precedence matrix or ordering of independent checks beyond the natural request pipeline is guaranteed. These mappings specify outcomes, not a new comprehensive precedence order.

## Audit / change log

Change field order:

| Field | Meaning / presence |
| --- | --- |
| changeId | Server-generated canonical positive decimal Oracle-sequence identity; numeric mutation order |
| missionId | Owning mission |
| operation | CREATED or UPDATED |
| changedAt | Service-generated change timestamp |
| changedBy | Required performer assertion; C-* Crew only |
| orderedBy | Required authorizer/orderer assertion; C-* Crew only |
| previousStatus | Omitted for CREATED; required for UPDATED even when unchanged |
| newStatus | Required for CREATED and UPDATED, including unchanged status |
| estimatedCostCredits | Optional new resulting estimate |
| estimatedCostCreditsChange | Optional signed estimate change |
| actualCostCredits | Optional new resulting actual cost |
| actualCostCreditsChange | Optional signed actual-cost change |
| summary | Required mutation metadata from X-Starfleet-Audit-Summary; 1..256 code points and at least one non-whitespace character (enforced by the XSD); absent from Mission representation |

POST appends CREATED; **every successful PUT** appends UPDATED. The cost history records the new resulting value plus signed change, for example estimatedCostCredits 140000.00 and estimatedCostCreditsChange 15000.00. A decrease is negative. All cost audit fields use two fractional digits; Mission amounts themselves remain non-negative. Finance's special cost history does not expand the audit into full snapshots or arbitrary before/after diffs.

Cost audit population applies independently to estimated and actual cost, including creation with no prior value:

| Before -> resulting value | Resulting cost field | Change field |
| --- | --- | --- |
| absent -> absent | Omitted | Omitted |
| absent -> value | Resulting value | Omitted |
| value -> same value | Resulting value | 0.00 |
| value -> different value | Resulting value | Signed arithmetic difference (result minus prior) |
| value -> absent, when otherwise valid | Omitted | Omitted |

Absence is never zero, and no null marker is introduced. Prior audit history establishes disappearance when a formerly present value is legitimately removed; this does not relax cost invariants.

The authoritative timestamp is database-sourced transaction time, rendered in UTC with `Z` and exactly three fractional digits (milliseconds), for example `2366-10-14T19:42:31.472Z`. Obtain one transaction timestamp per successful mutation and use that same value for Mission lastUpdated and audit changedAt. Do not use the application/container clock. Timestamp ties are permitted; timestamps do not establish total mutation order, changeId does. The contract places no constraint on the year: any valid four-digit year is accepted, and 2366 appears only in examples. The project's intent to load in-universe 2366 dates is dataset and runtime content, owned by later dataset design and the synthetic database/reference-clock configuration; it is not a wire rule (D034 extension, 2026-10-06). The service still never substitutes the application or host clock.

Audit entries are append-only, immutable and retained indefinitely; no archive/purge/delete in v1. Mission mutation and audit insertion are atomic in one database transaction. If audit persistence fails, POST/PUT fails; no resource-only success or audit-only mutation is permitted.

GET /missions/{missionId}/changes returns mutation order, changeId ASC compared numerically. D033 replaces the former changedAt-first ordering so clock ties or regressions cannot define mutation order. Pagination: page >=1/default 1; pageSize 1..50/default 20. The same pagination metadata, beyond-end/zero-match behavior, repeated page/pageSize rejection, query validation and live-view consistency apply here as appropriate. No audit filtering/search; unsupported query parameters are invalid. Unknown mission -> 404 MISSION_NOT_FOUND; unexpected repository/backend failure -> 500 INTERNAL_ERROR. Process audit belongs to SOA/BPM and is distinct from this resource history.

## Dataset and physical-schema amendment (2026-10-09)

This promotes the lead developer's October 8 design agreements under the [D027
schema and dataset extension](../governance/DECISIONS.md#d027-schema-and-dataset-extension-2026-10-09).
It supersedes only the original exact-20/Season-3 dataset restriction and the
deferred choices explicitly settled here. D032-D034 wire/domain rules remain
binding. These are design requirements, not an implemented release or acceptance
result. The original D027 decision and historical records retain their wording.

### Content and release identity

Each release contains **at least 20 missions**, starting in **2366 onward**,
using Season 3 material first and later seasons as useful. A release of more than 100 missions has a curated canon core under the rules of this section and generated missions that its provenance labels synthetic ([D044](../project-governance/DECISIONS.md#d044---missions-dataset-release-11-300-missions-appended-to-release-10-2026-10-18-accepted-scope); [Release 1.1](#release-11-a-larger-appended-release-2026-10-18)). It contains at least
**60 meaningful, unevenly distributed change entries**, targeting roughly three
per mission on average. CREATED counts as an entry; do not pad each history to a
fixed count or treat about 300 entries at 100 missions as a hard cap. Recurring
officers/assets, varied statuses/classifications/priorities and distinct failed
and cancelled assignments provide connected analytical data.

Memory Alpha episode material supplies inspirations and source anchors, not
canonical mission orders or finance. Retain source links and distinguish verified
source facts, previously reported source observations, and synthetic lab content.
Episode stardates are anchors, not proof of a sub-mission's commencement. Unknown
source stardates and added offsets are explicitly synthetic, on the existing
0.05 lattice; do not convert them to Earth-format audit dates.

The local worksheet has 31 candidates and 101 proposed events. Its accepted lab
snapshot has 16 COMPLETED, 4 PLANNED, 3 AUTHORIZED, 3 ACTIVE, 2 POSTPONED, 2 FAILED
and 1 CANCELLED mission. Its detailed metadata, event wording, costs and exact
timestamps are **provisional inputs**, requiring concrete release review. Hollow
Pursuits investigation and decontamination remain separate; tissue transport is
not a replacement. Lab snapshots may differ from episode outcomes. Final useful
event authoring may increase the entry count.

Within curated histories preserve mission purpose and type. Minor objective
refinements are allowed; materially different work receives its own mission,
history and costs, with narrative links using actual mission IDs in existing text
fields. This introduces no type-immutability API rule, semantic text validator,
relationship field, or audit snapshots. Vary summary style by changedBy, not
orderedBy. Concise initial and revised objective text in selected summaries may
support extraction; missing/ambiguous evidence means unknown coverage. The
256-code-point summary bound remains unchanged and cannot hold every allowed
2000-code-point objective. Never truncate to manufacture complete history.

Dataset versions are **MAJOR.MINOR**, independent of contract revision. MINOR
preserves existing identities, structure and meaning while adding/correcting
compatible content. Removals, identity changes, incompatible structure or changed
field meanings require MAJOR. Every published version is immutable; corrections
create a new version. Deployment and reset select a known explicit version,
never implicit latest. There is no startup or reset rerandomization.

### Deterministic generation and seed history

Use master seed **1701** with independent reproducible category streams. Adding
draws/items to one category must not shift unrelated categories. Specify and
freeze the exact algorithm/version, seed derivation bytes, category labels,
generator version, input order and recipe before publishing output. A seed alone
is insufficient. Stable digest derivation is a recommended mechanical choice;
per-mission/event substreams and their exact key encoding remain subject to the
concrete implementation preview, not implicitly accepted dependencies.

The fixed ordered candidate list receives monotonically increasing mission IDs.
Process missions in ascending canonical missionId order and events in deterministic
local order. Choose the initial numeric mission ordinal from 990000..1010000
(1000000 plus an inclusive +/-10000 offset), and the initial decimal changeId
from 9900000..10100000 (10000000 plus an inclusive +/-100000 offset), using separate
category streams. Encode mission IDs with the existing nine-character base-36
suffix. Global chronological event interleaving/changeId assignment is distinct
from generator traversal. Preserve identities when extending compatible releases;
changed list/seed/recipe inputs do not promise unchanged generated output. This
does not impose universal gapless runtime sequences or prohibit major releases.

Seed histories use bounded pseudo-random elapsed increments: urgent 5..45
minutes, routine 1..8 hours, planning 6..48 hours. Reconcile timing with each
mission's duration, meaningful operational events and explicit cross-mission
causality. Preserve investigation findings before dependent remediation and
incident evidence before follow-on response. Exact timestamps, terminal timing
and any justified exceptions must be authored and reviewed with the release.

Costs are **synthetic lab assumptions**, including tactical/engagement resource
use. Use positive, category-sensitive reproducible variation for cost-bearing
scenarios. Illustrative overlapping estimate bands in credits are routine
survey/transport 5000..50000, diplomatic/first-contact 10000..120000,
medical/rescue/relief/security/maintenance 25000..200000, and tactical or
engagement-heavy work 100000..500000. Mission scope may justify exceptions.
Typical completed/failed actuals are 80%..135% of final estimate, with reasoned
exceptions; cancellations retain positive incurred costs appropriate to progress.
Do not invent weapons fire or double-count related response costs. Use exact cents
or decimal arithmetic, meaningful revision reasons and exact signed audit deltas.
Unfinished actuals remain absent; this adds no universal wire prohibition of 0.00.

### Six-table Oracle storage

Use missions (current scalars, flattened location, current_change_id and
cancelled_without_estimate_allowed), mission_assigned_crew, mission_participants,
mission_assigned_assets, mission_changes, and a singleton configuration/clock
table. Collection keys are (mission_id, reference), with local mission foreign
keys only. External references remain opaque; no Personnel lookups, reconciliation
or external foreign keys. Audit stores the specified mutation metadata/cost history,
not full historical mission snapshots.

External reference columns have **50-byte physical capacity** (`VARCHAR2(50 BYTE)`),
including commander and audit actors, under the existing ASCII grammar, where 50
bytes equal 50 characters. This is the lead developer's YAGNI lab limitation; **it is not
a new XML/header maximum**. Published 1.0 and compatible 1.1 keep unbounded
reference patterns. A valid wire reference whose UTF-8 length is more than 50 bytes
cannot fit this storage and is refused with **422 DOMAIN_VALIDATION_FAILED** (the
existing code: no new error code and no contract revision) and the common XML error
body, whose message says the reference exceeds the storage capacity. Nothing is
stored, nothing is truncated and the clock is untouched. The check counts UTF-8
bytes, never characters, and covers the commander, every crew, participant and asset
member and the actor headers `X-Starfleet-User` and `X-Starfleet-Ordered-By`.
This later settlement (2026-10-15, the [D027 oversized reference extension](../project-governance/DECISIONS.md#d027-oversized-reference-extension-2026-10-15))
supersedes this paragraph's earlier wording, which forbade truncation and any
400/422 mapping and left such a write to fail as 500. The expected reference-pool
sizing discussion does not establish a participant cardinality cap or released count.

Human-text storage has 20% headroom: VARCHAR2(144 CHAR) for title/location name/
coordinates/travelVector, VARCHAR2(308 CHAR) for summary, and Unicode-capable CLOB
for objective/outcome. XML/domain code-point limits remain authoritative; storage
headroom does not admit overlong requests. Verify actual charset/Unicode behavior.
Stardate is NUMBER(7,2); costs and signed deltas are NUMBER(15,2). Store millisecond
timestamps with explicit UTC semantics, preserving NULL separately from zero.
Exact DDL, sequence numeric limits and database-client conversions require review
and real Oracle evidence; never silently wrap or truncate.

Initially use table primary keys and audit index (mission_id, change_id). Defer
extra filter indexes until measurements justify them. Clock has a singleton key
and corresponding check. Loaded release metadata may reside in the singleton
row; do not add a seventh table for convenience.

### Transactional reference clock and reset

The singleton row holds release baseline, transactional counter and interval.
Baseline is the latest seeded changedAt, interval **one second**, reset counter
**zero**. Advance before use: the first successful runtime mutation is baseline
plus one second; later timestamps are baseline + counter * interval. Clock advance,
mission/scalar and collection replacement, cancellation provenance, current
changeId and audit insertion succeed or roll back in one transaction. Use the
same timestamp for lastUpdated and changedAt; never the application/host clock.

Acquire the singleton clock-row lock before the target mission-row lock; recheck
If-Match under the mission lock. Allocate changeId while serialized by the clock
lock to preserve global mutation ordering. Mission and change Oracle sequences
remain separate and nontransactional, with permitted gaps; neither replaces the
transactional clock counter. Actual SQL rollback/locking evidence belongs to the
data slice and later HTTP/JDBC mutation evidence to the service slice.

Reset is an explicit stopped-service terminal maintenance operation: a small
shell wrapper plus SQL through the Oracle container client. Verify the selected
known immutable release and stopped Missions service before destructive work;
reload all six tables, restore next mission/change sequence positions and clock
state, validate the loaded state, and report the restored version. Reset discards
runtime changes. Oracle DDL is not a whole-operation rollback guarantee. On any
failure leave Missions stopped, fail clearly, and require a successful explicit
reset/validation before resuming service. No REST reset endpoint is introduced.

The immutable manifest records dataset version, contract revision, generator/
recipe/seed derivation and category metadata, input/output hashes and counts,
provenance/limitations, clock baseline/interval/counter and next sequence values.
Review the exact canonical serialization/hash policy and metadata placement with
the implementation. Never replace published content with a newly generated result.

### Contract revision and phase acceptance

MAINTENANCE is the only added mission type. Publish it in a separate compatible
**missions-v1.1.xsd**, keeping namespace urn:starfleet:missions:v1 and published
**missions-v1.0.xsd byte content unchanged**. ENGINEERING remains deferred. No
reference maxLength, new error mapping or other wire change accompanies this
addition. Update version-specific validation/examples when publishing 1.1.

The schema/dataset slice supplies executable real Oracle 18c DDL/load/reset tests,
immutable release integrity and deterministic reproduction/category-isolation
checks, grammar/domain/collection checks, complete numeric audit order/status
chains/cost deltas, final currentChangeId/lastUpdated/state consistency and causal
chronology checks. Include clock rollback, separate sequence positions, Unicode
storage and reset failure behavior within implemented scope. Report actual
versions/observations. Missing Oracle or tests is a failure, never a skip or PASS.

Use the manifest-derived missions-contract and missions-data gates where their
paths apply; this design-only promotion selects governance continuity, not Oracle
or Personnel acceptance. Later service and packaging slices own HTTP/JDBC and
deployed acceptance. No Java REST implementation, image pull/database startup,
full packaging, Mission Control publication or completed runtime conformance is
authorized or claimed by this design amendment. Runtime commits still require a
separately delegated fresh continuity-record worker and separate exact approval.

### Release 1.1: a larger appended release (2026-10-18)

The lead developer's rulings of October 18, 2026 ([D044](../project-governance/DECISIONS.md#d044---missions-dataset-release-11-300-missions-appended-to-release-10-2026-10-18-accepted-scope)) replace the range of curated missions per release by at least 20, with a curated canon core and generated missions that the provenance labels synthetic. Release 1.0 is unchanged. Release 1.1 appends to it:

- **Append rule.** The 31 missions and 101 change entries of release 1.0 are in 1.1 byte for byte, with their missionIds and changeIds. New missions get missionIds after the last of 1.0 (the order of the list, not of time) and their change entries get changeIds after the last of 1.0, numbered by changedAt, missionId and event index among themselves. A new entry can therefore be older than a carried one; each mission's own history is chronological. The clock baseline is the latest changedAt of the whole release and the sequences continue after the last ids. The carried missions are reproduced by the unchanged 1.0 algorithm with generator 1's seed key.
- **Composition (300).** 31 carried; 57 new curated canon missions from TNG Seasons 4 and 5 (the lab's own words, links and verified source facts kept apart from synthetic content, Memory Alpha as inspiration and anchor under the rules above); 45 generated maintenance missions (50 of type MAINTENANCE in all, one full page of 50); 167 generated routine missions (surveys and science, transports, patrols, escorts, medical outreach). Status counts: COMPLETED 158, PLANNED 30, CANCELLED 27, AUTHORIZED 25, ACTIVE 23, FAILED 22, POSTPONED 15.
- **Maintenance and complexity.** A hidden recipe parameter, the complexity (1 to 4), and a task class are recorded in the provenance and are not contract fields. Routine repairs (door, replicator, turbolift panel) are led and crewed by chief petty officers, crewmen and ensigns; ship systems (deflector tuning, warp core alignment) by lieutenants and, at complexity 4, lieutenant commanders. Complexity 1 and 2 estimates sit below the illustrative maintenance band above, an exception this section allows when the scope justifies it.
- **Generator.** `missions-generator-2`: master seed 1701, SHA-256 counter streams with independent categories (adding a category never shifts another), the generator version in the seed key; the inputs (curation, recipe, roster, generator) are archived with the release and hashed in the manifest. A fixed roster of 800 people from Personnel dataset `crew-v1-large-003` supplies ranks and departments.
- **Crew references.** Missions numbers its own `C-n` for the 800 people (135 to 9999; the ten references of 1.0 are kept for the same people), by the `crew_reference` stream keyed by the v1 crew id. No reference equals the numeric suffix of its person's v1 id and none is derived from a PRS number (D015, D032); the generator tests this. The recipe lists each person by exact v1 display name; canon people who are not among the 800 (three) are listed apart as `unmappedCrew`, which a mapping process does not read, and some references appear in no table at all.
- **Edge cases.** Placed by an `edge_cases` stream on missions that carry no other edge and listed in the `edgeLedger` of the provenance: partly staffed PLANNED missions, crews of 100, 99, 98 and 96, a commander as the only senior officer, the commander also listed in the assigned crew, cancelled missions with a full staff, cancellations from PLANNED without an estimate (actual 0.00), assigned crew who are inactive or on leave, a civilian listed as assigned crew, TOP_SECRET missions with crew whose rank carries no clearance, crew references that are unmapped or in no table, asset references without a mapping entry, a mission with 50 assets, missions with many participants, histories of 8 and 12 entries, and boundary values (stardates 43000.00 and 48999.95, durations 1 and 8760, a 120-character title, a 2000-character objective, non-ASCII text), and an identity trap: Wesley Crusher, returning as a visitor in two Season 5 missions, is an `O` participant (a reference that carries no Personnel membership claim), never `C-120` and never a `P` reference, and the mapping must never map it to his Personnel identity. Picard commands exactly 52 missions and Riker exactly 50, so a filter on the commanding officer pages once and twice.
- **Files.** Missions are written as six real pages of 50 (`missions-1.xml` to `missions-6.xml`) and the changes as pages of 50 as in 1.0.
- **Limits.** Most missions are synthetic. The release is a snapshot and claims no canon order, finance or Personnel mapping. The expected outcomes of the federation acceptance suite, the mapping release and the Missions adapter's own stub still describe release 1.0.
- **Note 2026-10-27 (pre-publication check).** A sample of five `sourceFacts` strings compared with their Memory Alpha pages found no copied sentence, but some follow their source's wording closely, so "the lab's own words" above is too strong for them. The Brothers record (`candidate-35`) says its stardate comes from a quoted log; the page gives 44149.1 as an earlier script's stardate, and the infobox range used is right. The releases are not changed.

### Release 1.2: the participants reclassified (2026-10-19)

[D045](../project-governance/DECISIONS.md#d045---missions-dataset-release-12-participants-reclassified-as-p-and-o-2026-10-19-accepted-scope) records the lead developer's rulings. Release 1.2 appends to release 1.1 and is a MINOR; the contract stays 1.1.

- **Append rule.** The 300 missions and the 865 change entries of 1.1 keep their missionIds and changeIds, and the change entries are in 1.2 byte for byte. A mission whose participants change gets the corrected `participantIds`, a new `lastUpdated` and `currentChangeId`, and one appended UPDATED entry (change ids 9906248 to 9906355, in missionId order, one minute apart from 2368-12-23T09:00:00.000Z). The entry keeps the status and the costs (previous and new status equal, cost changes 0.00), is performed by Data (C-85) and ordered by William Riker (C-78), and says in its summary that the participants were reclassified. Nothing else of a mission changes.
- **Composition.** 108 of the 115 missions with participants are corrected: the 19 of the 31 carried missions that have participants (the lead developer chose to correct them like the rest), 25 of the new canon missions and all 64 generated routine missions with participants. Seven missions already complied and are untouched: six whose only participant is an O (Ventax II claim arbitration, the returning Wesley, the Ullian historian, the isolated colony, the J'naii shuttle search and the injured Borg drone) and the Earth anomaly mission with Guinan.
- **Canon.** Every outsider that release 1.1 named as P (Dr Paul Stubbs, the Tau Cygna V colonists, Kamala, Sarek, K'mpec and the others) becomes a new O reference with the same name; the 56 old references that change class are listed in the participant table (`was`). Alexander (Alexander Rozhenko on the roster) and Guinan keep P-1003 and P-1068. The eight O references that already were outsiders keep their numbers. Clara Sutter is an on-board civilian of the canon who is not on `personnel-v2-large-004`; she stays O and the provenance flags her (`offRosterCivilians`). Personnel is not changed.
- **Generated missions.** The recipe gives each mission a class by its title or template: drills, screening, evacuation exercises, equipment and cargo runs and the scientific and survey work take roster civilians as P (technical work from technicians and specialists, scientific work from specialists and botanists, drills and screening from any civilian); passenger transfers, delegation escorts and envoys, relief support, clinics and vaccinations, survivor searches and convoy or sector patrols take named synthetic outsiders as O, drawn from pools of passengers, delegates, colonists, patients, survivors and traders. The number of participants of each mission is kept. The 20 roster civilians who are also crew in the legacy Crew system are never drawn as P, so a person is not both assigned and participating in one mission.
- **References.** The new references are numbered from 2121 in steps of 13 (reclassified canon people in the order of their old reference, then the outsiders drawn from the pools, then the civilians drawn), never from an old suffix or a PRS number. The release has 58 P references (56 roster civilians and the two kept) and 153 O references (56 reclassified, 89 synthetic and 8 kept); the participant table `participants.json` lists each with its class and name.
- **Build-time check.** The generator and the release validator check that no C reference is a participant, that each P name is exactly one civilian of the roster in `civilians.json` (the display names of `personnel-v2-large-004`, pinned by the hash of its manifest and read once by an authoring step, so the dataset has no runtime coupling to Personnel), that a P name is not an assigned crew member of the same mission, and that no O names a person of the roster or a crew member. A test compares the archived roster with the released Personnel pages.
- **Generator and files.** `missions-generator-3` (master seed 1701, categories `participant_pool`, `participant_roster` and `participant_outsider`) reads the archived release 1.1 and its own recipe and reproduces the release; the eighteen change pages of 1.1 become twenty. The validator learns the appended correction entries: they keep the status and costs, they are not part of a mission's curated duration, and the missions of the earlier release differ only in the participants and the current state.
- **Limits.** The synthetic outsiders and the choice of civilians for generated missions are lab content, not canon. The mapping release for the new P references, the switch of the federation stack to release 1.2 and the re-derived acceptance outcomes are later Jobs; until then the mapping check excuses release 1.2 through its explicit pending list.

## Personnel clearance relationship (original 2026-10-01 design)

The original design anticipated Personnel v2 securityClearance NONE, SECRET, TOP_SECRET; current v2 now supplies that field for crew, as recorded above. Frozen Personnel v1 remains unchanged. Mission classification describes information; clearance describes a person, so their enums intentionally differ.

| Mission classification | NONE clearance | SECRET clearance | TOP_SECRET clearance |
| --- | --- | --- | --- |
| UNCLASSIFIED | Sufficient | Sufficient | Sufficient |
| SECRET | Insufficient | Sufficient | Sufficient |
| TOP_SECRET | Insufficient | Insufficient | Sufficient |

This semantic relationship is future process policy, not a Missions cross-service validator. Locally valid assignments may include insufficient clearance. Preserve independent-system inconsistency for later integration scenarios; no Personnel v2 fields or inconsistent fixtures are implemented here.

## Remaining precision and governance

D033 settles the seven categories approved by the lead developer: error mappings; canonical lexical values; fixed element/collection structure and deterministic collection order; decimal changeId and derived strong ETag; database transaction timestamps at millisecond precision; required header-carried audit summary; and XML-only media negotiation. D027's original wording remains historical provenance; D033 explicitly supersedes the conflicting earlier rules without reopening the rest of the freeze. D032's semantic foundation remains intact.

### Open for tomorrow

Historical heading, retained so existing links stay valid. D034 (2026-10-06) settled every item it listed:

- **List and collection structure:** `missionList`/`changeList` metadata-first with direct `mission`/`change` members; `crewId`, `participantId` and `assetId` container members (see [Media and XML](#media-and-xml)).
- **Lexical bounds:** code-point length counting, non-whitespace rule for minimum-1 strings, state-dependent `outcome`, and the stardate pattern and range (see [Lexical values](#lexical-values) and the field table).
- **Media grammar:** Content-Type parameters and Accept grammar, including malformed headers (see [Media and XML](#media-and-xml)).
- **Historical mapping time/version semantics:** not a Missions concern. Missions stores reference strings only and neither reads nor resolves mappings, so its contract defines no mapping time or version rule. The question belongs to the Integration & Benchmark layer under D015 and is recorded in [Plan](PLAN.md#next-design-choices) with a non-binding direction: immutable versioned mapping releases in the Personnel dataset style, an explicit release named by every resolution request with no implicit latest, no effective-interval axis until a scenario needs one, and missing/ambiguous/dangling outcomes never guessed.

No residual wire precision blocks the executable Missions contract. The 2026-10-09 amendment settles the accepted schema/dataset requirements above. Exact release content, generator/seed derivation, DDL/operator implementation and compatible runtime pins other than the JDK 17 minimum remain reviewable implementation work. JNDI/JDBC service mechanics remain in the later service slice.

D032 settles Crew-only command/assignment/mutation eligibility and non-Crew participation. D033 and D034 supply wire precision and supersede only the identified D027 details; historical mapping resolution (owned by the Integration & Benchmark layer) and future command-chain policy remain outside Missions. D027's Missions REST/XML technology supersession of D010 remains binding. D014/D015, frozen Personnel artifacts and unrelated branch work remain unchanged. [Plan](PLAN.md) and [Progress](PROGRESS.md) own next work and current status. The [checkpoint workflow](../governance/CHECKPOINT-WORKFLOW.md) requires separate exact transaction/message approval before commit. This transaction records design and strictly necessary references only; no implementation is authorized.

The existing [design-record convention](CREW-PERSONNEL-DATASET-003-DESIGN.md#authority-and-compatibility-findings) permits uncommitted design preparation without a devlog entry. Current freeze status and recovery are recorded in D027/Progress; no completed implementation checkpoint or acceptance evidence is fabricated, and historical logs remain intact.
