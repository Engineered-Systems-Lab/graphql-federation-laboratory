# Assets v1 design

Status: **design and executable contracts 1.0 and 1.1, the service implements 1.1** (decisions [D036](../project-governance/DECISIONS.md#d036---assets-contract-10-2026-10-15-accepted-scope) and [D038](../project-governance/DECISIONS.md#d038---assets-contract-11-native-identifiers-and-path_not_found-2026-10-15-accepted-scope)). The first slice of the Assets service is this document, the [OpenAPI contract](../uss-enterprise/assets/contracts/assets-v1.0.openapi.json), its examples (for instance [a list page](../uss-enterprise/assets/fixtures/valid/asset-list.json)) and an offline validator. The second slice is the [dataset release 1.0](#the-dataset), with its review page generator and offline checks; [release 1.1](#release-11-native-identifiers) renames its assets with native identifiers. The third slice is the [read service](#the-read-service): the PostgreSQL schema and load script, the Python service and a gate against a real disposable PostgreSQL 17 container. The fourth slice is the [packaging](#packaging): a Dockerfile, a compose file, a start script and a packaging gate. Nothing else exists: no federation. Contract 1.0 is settled: it was edited in place on the day of its design, through the review amendments (the list of kinds, the derived category with its filter, the parent rule and the rename of the kind SHIP to STARSHIP; see [the asset record](#the-asset-record)), and from the landing of that rename it is not edited again, under [the publication rule](#contract-evolution). The fixtures and the offline validator follow it. **Contract 1.1** is the current contract and the one the service implements: a new immutable file, [assets-v1.1.openapi.json](../uss-enterprise/assets/contracts/assets-v1.1.openapi.json), that gives Assets its own identifier grammar (AST-0017) and adds the error code PATH_NOT_FOUND; contract 1.0 stays beside it as published history (see [Contract 1.1](#contract-11-native-identifiers-and-path_not_found)). The decisions below come from the design talk of 2026-10-15 and the direction talk of 2026-10-13 and 2026-10-14; their sources are listed in [Decisions and their sources](#decisions-and-their-sources).

## Purpose and hypothesis

Assets is a bounded context that owns the facts of the fleet's assets: starships, shuttles, ground vehicles (rovers and armored vehicles) and equipment such as phasers, tricorders and scientific instruments. The [Missions design](MISSIONS-V1-DESIGN.md#ownership-and-identifiers) keeps asset references as identifiers only and leaves their facts to "asset-owning services"; Assets is that service. It stands beside Personnel (SOAP, an immutable in-memory dataset) and Missions (REST with XML, Oracle) as a third legacy system built differently on purpose: REST with JSON, an OpenAPI contract and PostgreSQL. The [Prime Directive](../project-governance/CONSTRAINTS.md#legacy-systems-stay-unaware-of-the-integration-layer) applies: Assets knows nothing of GraphQL, federation, MCP or AI.

A bounded context is added only for a defined hypothesis (see [Integration notes](INTEGRATION-NOTES.md)). The hypothesis of Assets is:

> The federation layer can compose three differently built services (SOAP Personnel, XML REST Missions, JSON REST Assets) into one GraphQL view, and it behaves predictably when a reference does not resolve.

The Missions release 1.0 is immutable and references 9 distinct assets in 68 references (31 missions: EQ-64, EQ-75, EQ-86, EQ-97, EQ-108, EQ-119, SH-42, SH-53 and VS-31). Those references are Missions-local, as C-85 is for crew: Assets has its own identifiers (from contract 1.1 and dataset release 1.1: AST-0004 and the like), and the mapping from a Missions reference to an Assets identifier belongs to the integration layer, not to Assets and not to Missions. Missions does not check that those assets exist, and Assets is built so that a few do not. The dataset carries controlled cases, each with an expected outcome written in its provenance and shown on its review page before any federation code exists, in three layers: what the mapping says, what the Assets service answers and what the consumer shows:

| Case | What the dataset holds | Expected outcome |
| --- | --- | --- |
| NORMAL | An asset that Missions references, that the expected mapping reaches and that Assets has | The reference resolves to the asset |
| MAPPED BUT NOT FOUND | The expected mapping points a Missions reference to a well-formed Assets id that the dataset does not hold (EQ-97 to AST-0097) | Assets answers 404 ASSET_NOT_FOUND and the consumer shows the reference as UNRESOLVED |
| UNMAPPED | The expected mapping has no entry for a Missions reference (EQ-108) | Assets is never asked; the consumer reports no mapping, a failure of the mapping layer and never UNRESOLVED |
| DESTROYED | A referenced asset with status DESTROYED | It resolves, with its status; no judgment is made |
| MISSING | A referenced asset with status MISSING | It resolves, with its status; no judgment is made |
| UNREFERENCED | An asset that no mission reaches through the expected mapping | It resolves when asked for; no mission lists it |
| PARENT CHAIN | Equipment aboard a ship, for example AST-0004 aboard AST-0023 aboard AST-0029 | A mission, its assets and each asset's parent ship answer in one federated query |

The dataset has 30 or more assets. It holds the Missions-referenced ones except the deliberately omitted, plus extras. It is derived from what Missions references, extended, and reviewed by the lead developer before release.

## Ownership and what the service does not do

Assets owns asset facts and nothing else. It does not store missions, crew or any reference to them; the link from a mission to an asset is the Missions field `assignedAssetIds`, and Assets never learns it.

- **No writes.** The service is read-only. POST, PUT, PATCH, DELETE, HEAD and OPTIONS are 405 METHOD_NOT_ALLOWED with an `Allow: GET` header. The framework's automatic HEAD and OPTIONS handling must be disabled so that it cannot answer them.
- **No frontend.** The reading interface for all services is the GraphQL explorer of the federation layer. The Assets JSON is readable in a browser. The only viewer foreseen is a static HTML review page for the dataset, which belongs to the dataset slice and is not a service frontend.
- **No time semantics.** DESTROYED and MISSING assets resolve with their status and the service judges nothing about when. Time semantics belong to the integration layer (D034); no effective-interval field exists until a scenario needs one.
- **No location.** See [the record](#the-asset-record).
- **No cross-service validation.** Assets does not check the assets that other services reference, and Missions does not check Assets.

## The asset record

| Field | Type and constraint |
| --- | --- |
| assetId | Required string, native to Assets from contract 1.1: a prefix of capital letters (one to three segments joined by single underscores), a hyphen and a zero-padded number of four or more digits, for example AST-0017 (see [Contract 1.1](#contract-11-native-identifiers-and-path_not_found)); contract 1.0 used the Missions grammar `^[A-Z]{2,5}-[1-9][0-9]*$`; the prefix carries no meaning and the kind is a field |
| kind | Required enum: STARSHIP, SHUTTLE, ROVER, ARMORED_VEHICLE, PHASER, TRICORDER, COMMUNICATOR, SCIENTIFIC_INSTRUMENT, MUSICAL_INSTRUMENT |
| category | Required enum: VEHICLE, EQUIPMENT; computed from the kind by the table below and never stored apart from it |
| name | Required string, 1 to 120 Unicode code points |
| description | Required free text, 1 to 1000 Unicode code points |
| status | Required enum: ACTIVE, MAINTENANCE, DECOMMISSIONED, DESTROYED, MISSING |
| parentAssetId | Always present; an assetId, or JSON null when the asset has no parent |

The JSON response has exactly these seven members and no others. Identifiers are validated exactly as sent, after the usual percent-decoding of the path: no case folding, trimming or normalization. Text counts code points, never UTF-16 units or bytes. Member order carries no meaning.

**Status.** ACTIVE and MAINTENANCE describe an asset in the fleet. DECOMMISSIONED is a normal retirement. DESTROYED is confirmed and final: it cannot return. MISSING means the whereabouts are unknown: it can return to ACTIVE if it is found. Two values are kept for destruction and loss because a mission that references a destroyed asset is a different case from one that references a missing asset, which matters to the dangling-reference hypothesis.

**Kinds.** The list is meant to be extended easily. Each kind has one definition:

| Kind | Definition |
| --- | --- |
| STARSHIP | A starship, a large crewed ship such as the Enterprise |
| SHUTTLE | A small craft that flies between ships and surfaces; a runabout counts as a SHUTTLE until a scenario needs a separate kind |
| ROVER | A ground exploration vehicle |
| ARMORED_VEHICLE | "Land-based vehicles built for active combat zones and mechanized warfare" (the lead developer's definition): an armored ground vehicle built for combat, tracked or wheeled |
| PHASER | A hand-held energy weapon |
| TRICORDER | A hand-held scanner and recorder |
| COMMUNICATOR | A personal communication device such as a comm badge |
| SCIENTIFIC_INSTRUMENT | An instrument for measurement, analysis or research that is not a tricorder |
| MUSICAL_INSTRUMENT | An instrument for making music, such as a flute, a violin or a trombone; musical instruments are plain assets too |

There is no generic kind: every piece of equipment must fit a named kind, and a new kind later is one enum value and one row of the table below. The first draft had one kind EQUIPMENT with phaser and tricorder only as examples; the lead developer recalled that they were meant to be kinds of their own under the category EQUIPMENT, and the list was fixed before the contract was settled. The word EQUIPMENT now names only the category. The contract carries the same one-line definitions in the description of the `AssetKind` enum. GROUND_VEHICLE was proposed first and is not used: ROVER is the ground exploration kind and ARMORED_VEHICLE the combat kind. The acronym AFV (armored fighting vehicle) was considered and not chosen, because the plain words need no explanation. A STATION kind is not added now. The identifier prefix still carries no meaning: the ids of the Missions release 1.0 (EQ, SH and VS) are a dataset convention, not a rule of the contract, and a later dataset may use AV-n for armored vehicles; the dataset slice chooses its ids with this in mind. The same holds for the EQ prefix: an EQ id may name a phaser or a flute.

**Category.** The category is computed from the kind by one table and is never stored separately, so it cannot disagree with the kind. It is a member of every response so that a consumer need not know the table, and `GET /assets` filters on it. The name VEHICLE is the Coordinator's proposal (a tank-like kind rules out VESSEL); the lead developer did not object in two exchanges, so it is treated as agreed unless they say otherwise at the review.

| Kind | Category | Can be a parent |
| --- | --- | --- |
| STARSHIP | VEHICLE | yes |
| SHUTTLE | VEHICLE | yes |
| ROVER | VEHICLE | yes |
| ARMORED_VEHICLE | VEHICLE | yes |
| PHASER | EQUIPMENT | no |
| TRICORDER | EQUIPMENT | no |
| COMMUNICATOR | EQUIPMENT | no |
| SCIENTIFIC_INSTRUMENT | EQUIPMENT | no |
| MUSICAL_INSTRUMENT | EQUIPMENT | no |

The contract cannot say that a category agrees with its kind, because JSON Schema as used here has no rule between members. The offline validator checks it: a record whose category differs from the table value for its kind is rejected, and so is a record without a category.

**Parent.** A parent is a VEHICLE, and only a VEHICLE: equipment or a shuttle aboard a ship points to it, for example AST-0004 aboard AST-0023, and equipment aboard a rover is as valid as equipment aboard a ship. An asset of the category EQUIPMENT cannot be a parent. It is an asset-to-asset relationship inside Assets and involves no other service. The parent must exist: in PostgreSQL it is a foreign key, so a dangling parent cannot happen inside Assets. Dangling references are a cross-service case only. The contract cannot express rules that span records, so these are stated here and enforced by the schema and the dataset checks of later slices: a parent exists, its category is VEHICLE, an asset is not its own parent, and the parent chain has no cycle. An equipment used as a parent is therefore not checkable by the contract, and no invalid fixture shows it; the offline validator only checks that the parents named by its own examples are vehicles. A new kind later is one row of the table above and one enum value, a compatible minor change. A station or a starbase would map to VEHICLE or to a new category, and neither is added now.

**No location.** Missions already holds a location (`location_name` and `location_type`: where a mission takes place). An asset's location would be a different fact, where the asset is, and would invite contradictions with the mission data. It can be added later as an optional field, which is a compatible minor change under [the evolution rule](#contract-evolution). Until then the 1.0 record is strict: a `location` member is rejected by the validator, and one of the invalid examples shows it.

## REST API and outcomes

| Method and path | Outcome |
| --- | --- |
| GET /assets/{assetId} | 200 with the asset, whatever its status; 404 ASSET_NOT_FOUND for a well-formed identifier that names nothing; 400 INVALID_ASSET_ID for a malformed identifier, which includes an identifier in the old Missions grammar such as SH-17 |
| GET /assets | 200 with a filtered, ordered, paginated list; 400 INVALID_REQUEST for a bad query |
| any other method on either path | 405 METHOD_NOT_ALLOWED with `Allow: GET` |
| any path outside the two above, whatever the method (contract 1.1) | 404 PATH_NOT_FOUND |
| any failure the service cannot classify | 500 INTERNAL_ERROR |

Every response body is `application/json` in UTF-8. The service always answers JSON and ignores `Accept`: there is no 406, which Missions has, because content negotiation adds nothing to a single representation. There is no ETag, no `Location` header and no caching metadata. A path outside the two above is 404 PATH_NOT_FOUND from contract 1.1 on; in contract 1.0 it was not part of the contract.

## Collection filters, paging and ordering

`GET /assets` takes `kind`, `category`, `status` and `parentAssetId` as filters, and `offset` and `limit` for paging. Filters combine with AND; an enum filter takes exactly one token (no list, no implicit OR), so `category` is VEHICLE or EQUIPMENT and `category=VEHICLE` lists ships, shuttles, rovers and armored vehicles; `parentAssetId` lists the assets aboard a given asset, and a parent that names no asset selects nothing and is not an error. An unknown parameter, a repeated parameter or an invalid recognized value is 400 INVALID_REQUEST. Number parameters use one canonical decimal spelling: `offset` is 0 or a positive number without leading zeros (default 0) and `limit` is 1 to 50 (default 20).

The list answers `{ "items": [...], "offset": n, "limit": n, "total": n }`: the offset and limit the request used and the number of assets that match the filters before paging. An offset at or past the total returns an empty `items` array and the same total: it is not an error. A list is a live view; there is no snapshot across requests.

Order is `assetId` ascending: the letter prefix as text first, then the number as a number, so AST-0002 comes before AST-0017, AST-9999 before AST-10000 and AB before AB_C. No search, sorting option, field selection or query language exists.

**Why offset and limit, not Missions' page and pageSize.** The Missions shape (`page`, `pageSize`, `totalCount`, `totalPages`, pages from 1, sizes 1 to 50, default 20) was the model asked for, and the filter style (AND, one token per enum, 400 for anything unrecognized) and the bounds (limit 1 to 50, default 20) are taken from it unchanged. The paging model is not. The direction recorded for Assets is a deliberately plain service that differs from Missions on purpose, and two paging models are exactly the kind of heterogeneity the federation layer must adapt, which is the hypothesis. `offset` and `limit` are also the plainest to implement over SQL. The cost is one more adapter in the federation layer; there is none for the contract. The lead developer agreed with offset and limit in the review of 2026-10-15.

## Errors

The body is JSON: `{ "code": "...", "message": "..." }`. HTTP status is authoritative, codes are stable and the message is 1 to 1000 Unicode code points of human-readable text that is not meant for parsing and never carries a stack trace or framework detail.

| Status | Code | Condition |
| --- | --- | --- |
| 400 | INVALID_REQUEST | An invalid recognized query value, an unknown query parameter or a repeated parameter on `GET /assets` |
| 400 | INVALID_ASSET_ID | A malformed identifier in the path of `GET /assets/{assetId}` |
| 404 | ASSET_NOT_FOUND | A well-formed identifier that names no asset: this code has that one meaning only |
| 404 | PATH_NOT_FOUND | A path outside the two paths of the contract, whatever the method (contract 1.1; the body has the same JSON shape as every error) |
| 405 | METHOD_NOT_ALLOWED | Any method but GET; the response carries `Allow: GET` |
| 500 | INTERNAL_ERROR | An unexpected server or database failure; never mapped to 503 |

Processing is fail-fast: the first failure is returned. No precedence between independent checks is guaranteed.

## Contract format and offline validation

**Format.** Each contract is an OpenAPI 3.1 description in one JSON file, [assets-v1.0.openapi.json](../uss-enterprise/assets/contracts/assets-v1.0.openapi.json) and [assets-v1.1.openapi.json](../uss-enterprise/assets/contracts/assets-v1.1.openapi.json), with JSON Schema inside it for the data shapes. OpenAPI is the REST counterpart of Personnel's WSDL and the JSON Schema inside it plays the part of the XSD. OpenAPI lists endpoints, inputs, outputs and errors with descriptions in one place, so tooling and a GenAI agent can discover them easily; the usual company pattern is REST with OpenAPI per backend service and GraphQL on top as a gateway. OpenAPI 3.1 is chosen over 3.0 because its schemas are real JSON Schema (a nullable value is the type `null`, not a flag). JSON is chosen over YAML because the repository convention for tooling is the Python standard library only, which reads JSON and not YAML, and a contract that needs a YAML parser would need a third-party dependency for no gain. Each example is linked from the contract by `externalValue`, so the contract itself says which file illustrates which response.

**Validation approach.** No OpenAPI or JSON Schema validator ships with Python, and the repository's one third-party offline dependency (lxml for the XSD checks) exists because the standard library cannot validate XML Schema. For Assets the standard library is enough, because the contract uses a small part of JSON Schema. The offline validator is therefore a small checker written for this contract, [jsonschema_subset.py](../uss-enterprise/assets/validation/jsonschema_subset.py), plus [validate.py](../uss-enterprise/assets/validation/validate.py), which holds the structure checks, the example checks and the negative probes. The checker implements only the keywords the contract uses and fails on any other, so the contract cannot drift into a rule that nobody evaluates; patterns are limited to a portable subset on which Python and ECMAScript agree, with `$` meaning the very end of the text. A reviewer who prefers a general validator has the alternative: a pinned `jsonschema` package in `validation/requirements.txt`, with its own classification and its own tests, at the cost of a third-party dependency. That is a one-slice change and nothing in the contract depends on it.

The validator checks both contract files, each with its own fixtures (`fixtures/valid` and `fixtures/invalid` for 1.0, `fixtures/v1.1/valid` and `fixtures/v1.1/invalid` for 1.1), and then that 1.1 differs from 1.0 in nothing but the identifier grammar, the error code PATH_NOT_FOUND and its answer, ignoring prose and example links. What the validator establishes for each: the contract is well-formed OpenAPI 3.1 of the decided surface (two paths, GET only, the response statuses, the enums, the identifier grammar, the seven fields, the kind-to-category table, no location, the defaults and bounds); every reference resolves; every example in the contract validates against the schema of its response and, for an error, carries the code its status requires; every valid fixture is used by exactly one response; each invalid fixture is rejected, one of them only by the kind-to-category table; every record of every example agrees with that table; and probes show that enums are exact and case-sensitive, the grammar has one spelling per identifier, text counts code points, numbers are not booleans, and the list and error shapes are strict. What it does not establish: service behavior, ordering, filtering, the `Allow` header, HTTP mechanics, the database and every rule across records. It never touches a network, a database or Docker.

## Contract evolution

The rule is that of Missions, [D034](../project-governance/DECISIONS.md#d034---missions-v1-residual-wire-precision-2026-10-06-accepted-scope), applied to Assets only. A contract version is MAJOR.MINOR. The major version is the component: a new major is a new component and a new endpoint, as Personnel v2 stands beside v1. The minor version is recorded in `info.version` and in the revision history. The first contract is 1.0.

| Class | Changes | Version effect |
| --- | --- | --- |
| Compatible addition | New enum values (a new kind is one value and one row of the kind-to-category table); widened bounds or patterns; new optional query filters, endpoints or methods; new error codes; new optional members of a response, for example `location` | New minor, same component |
| Breaking change | Removing or renaming a value, member, endpoint or error code; narrowing a bound, a pattern or a requirement; making an optional member required; changing the identifier grammar, the order or the meaning of a value | New major, new component |

Each minor is a superset of the one before: what is valid under 1.n stays valid under 1.(n+1), except that new values or members may appear once data uses them. The server is strict relative to the revision it implements. Each published minor is a separate immutable file (`assets-v1.1.openapi.json`) and is never edited afterward. **Publication.** Contract 1.0 is settled on 2026-10-15, the day of the landing of the rename of SHIP to STARSHIP, and by this rule `assets-v1.0.openapi.json` is edited no more: a compatible addition is a new minor published as a new file, a breaking change is a new major, and the fixtures follow the contract they illustrate. This is a status stated in words, as it is for Missions, whose published contract files are immutable by the same rule: the classification table keeps the Assets contract under the runtime boundary and does not mark it `frozen`. The planned hardening, after the service exists, is to mark the exact contract file and fixture files `frozen, runtime`, not their enclosing folders, so that a later minor can be added beside them. There is no patch level, and there is no wire marker for the minor. A consumer that validates strictly against a pinned file refreshes it when the server's minor advances. The contract version is independent of any dataset version. **The exception of 1.1.** A change of the identifier grammar is breaking by the table above, and would normally make a new major, a new component and a new endpoint. The lead developer decided to make it in 1.1 instead ("A, keep 1.1 with the exception. yup! :D"), because the 1.0 file never had a consumer and was never marked frozen. The exception is stated once, in [D038](../project-governance/DECISIONS.md#d038---assets-contract-11-native-identifiers-and-path_not_found-2026-10-15-accepted-scope), and the rule is unchanged for every later change. A consequence is that 1.1 is not a superset of 1.0 in its identifiers: a 1.0 identifier such as SH-17 is not valid under 1.1, and the 1.0 fixtures validate against the 1.0 file only.

## The federation outcome, as the consumer expects it

This is the expectation of the federation layer, not behavior of Assets, which knows nothing of it. Each asset reference of a mission appears as `{ id, resolution, asset }`, where `resolution` is RESOLVED or UNRESOLVED and `asset` is null when it is unresolved. Nothing is hidden or guessed, which follows the direction of D034 that missing, ambiguous or dangling outcomes are never guessed. The federation layer would also add an entry to the GraphQL `errors` list as a courtesy; that detail was not separately confirmed. A DESTROYED or MISSING asset is RESOLVED with its status, and the federation makes no judgment about timing. Assets supports this with one fact only: a well-formed identifier that names nothing is 404 ASSET_NOT_FOUND, which the federation reads as UNRESOLVED. The refined rule: UNRESOLVED only for a 404 whose code is ASSET_NOT_FOUND, never for any other 404. A 404 PATH_NOT_FOUND means the consumer built a wrong path, and it is a lookup failure like any other failure of the lookup (a 500, a timeout, the service being down, or a 400 for a malformed identifier): the consumer shows an error entry with a null asset and never UNRESOLVED, so that an outage or a wrong path cannot pass for a dataset of missing assets. A Missions reference that has no entry in the mapping is a failure of the mapping layer: Assets is not asked, and the consumer shows no mapping, never UNRESOLVED. The dataset provenance of release 1.0 says "only a 404 maps to UNRESOLVED"; that release is immutable (its manifest holds the hashes), so it is not edited and this rule corrects it. The provenance of release 1.1 states the refined rule and shows three layers for every controlled case: what the mapping says, what Assets answers and what the consumer shows.

Ideas for later, parked and not part of any slice: the federation could answer "when was this asset last seen?" with the asset's last recorded mission (its mission and stardate, labeled as a fact, never as the loss date) by reading `totalPages` of `GET /missions?assignedAssetId=...` and fetching the last page, and it could answer which missions used a DESTROYED or MISSING asset and which missions have unresolved assets. Each needs two or three services together, which is why they are good demonstration questions for the GraphQL explorer. An optional `statusStardate` field in Assets was considered and not chosen; it would be a compatible minor addition if a scenario ever needed it.

## Technology and images

Python with psycopg 3 for the service (the web layer is the standard library, see [the read service](#the-read-service)), PostgreSQL for the data. Heterogeneity is on purpose: Oracle for Missions, PostgreSQL for Assets, an immutable in-memory dataset for Personnel. Legacy systems stay independent by design: no code, identifiers or tables are shared with another service, and the duplication that follows is intentional.

| Image | Choice | Not chosen |
| --- | --- | --- |
| Service | `python:3.13-slim-bookworm` (Python 3.13, the repository's stated minimum) | `python:3.14-slim-bookworm` |
| Database | `postgres:17-bookworm` (PostgreSQL 17) | `postgres:18-bookworm`, whose image keeps its data elsewhere: harmless for a disposable database but no reason to pay for newness |

Both are Debian bookworm for consistency, and glibc avoids the surprises of Alpine's musl. Missions uses an Ubuntu jammy Temurin image pinned by digest: the same style. Tags move. The digests read from the registry on 2026-10-15 (metadata only, nothing pulled) are for reference and are not pins: `postgres:17-bookworm` was sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826 and `python:3.13-slim-bookworm` was sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641. The packaging slice resolved both again on 2026-10-15 with `docker buildx imagetools inspect` and found the same index digests: the Dockerfile pins the Python one, the compose file and the gate pin the PostgreSQL one, and the [README](../uss-enterprise/assets/README.md#packaging) records both with the date. The pulled image measures 637 MB on disk (Docker's own figure), larger than the Alpine variant and much smaller than Oracle XE, whose local image is 9 GB. The gate keeps the container small: a 512 MB memory limit, 32 MB of shared buffers and its data in memory.

## The dataset

Release 1.0 is the second slice, in [datasets/releases/1.0](../uss-enterprise/assets/datasets/releases/1.0/manifest.json). It is immutable like a Missions release: a manifest holds the content hash of each file, the hash of the contract and the hashes of the Missions release it was checked against, and a change is a new release folder, never an edit. The lead developer read its static review page and approved it before release on 2026-10-15, ruling that the dataset was fine as shown and that the release and the preview should follow.

- **Content.** 32 assets, with at least one of each of the nine kinds, each valid against the contract. `curation.json` holds the authored records and the expected outcomes; `generate.py` derives `assets.json` (it adds the category from the kind table) and `provenance.json`, and the release holds its own copy of both so that the validator can rebuild the release byte for byte. The names are inspired by Star Trek: The Next Generation and are not verified against Memory Alpha; every description, status and parent is synthetic.
- **Id convention (release 1.0).** A dataset convention, not a contract rule: VS for a STARSHIP (Missions uses VS-31), SH for a SHUTTLE, RV for a ROVER, AV for an ARMORED_VEHICLE, and EQ for any of the five equipment kinds. Release 1.1 replaces it with the single native prefix AST.
- **The nine Missions-referenced ids** (68 references): VS-31, SH-42, EQ-64, EQ-75 and EQ-119 resolve as NORMAL; SH-53 resolves as DESTROYED; EQ-86 resolves as MISSING; EQ-97 (an isolation kit) and EQ-108 (a cargo module, which fits no equipment kind) are DANGLING and Assets leaves them out. The other 25 assets are UNREFERENCED. Two parent chains are listed: EQ-64 aboard SH-17 aboard VS-31, and EQ-211 aboard RV-3 aboard SH-70 aboard VS-66. The expected outcome of each reference is written in `provenance.json` and shown on the review page. This describes release 1.0, whose dangling references are what release 1.1 restates as one mapped-but-not-found and one unmapped reference.

### Release 1.1: native identifiers

Release 1.1, in [datasets/releases/1.1](../uss-enterprise/assets/datasets/releases/1.1/manifest.json), is a new immutable release that holds the same 32 assets as release 1.0 under native identifiers, checked against contract 1.1. Release 1.0 is untouched, with its manifest and its hash of the 1.0 contract.

- **The rule.** The assets of release 1.0, in the order of their release 1.0 identifiers (the letter prefix as text, then the number as a number), receive AST-0001, AST-0002 and so on, one step each; a parent keeps pointing at the same asset. The generator applies the rule, the manifest pins the hashes of the release 1.0 assets and manifest it was applied to, and the provenance lists every pair, so the result is reproducible and reviewable. The Enterprise is AST-0029, the shuttle Magellan AST-0023 and the sensor suite aboard it AST-0004.
- **The expected mapping.** The nine Missions references and what an integration layer should find: EQ-64, EQ-75, EQ-119, SH-42 and VS-31 map to AST-0004, AST-0005, AST-0007, AST-0024 and AST-0029 and resolve as NORMAL; SH-53 maps to AST-0025 (DESTROYED); EQ-86 maps to AST-0006 (MISSING); EQ-97 maps to AST-0097, which Assets does not hold (MAPPED BUT NOT FOUND: 404 ASSET_NOT_FOUND, UNRESOLVED); EQ-108 has no entry (UNMAPPED: Assets is not asked, the consumer reports no mapping). It is written in the provenance and on the review page; it is not a field of the record, not a service and not a Missions change: the mapping subgraph or service belongs to the federation phase.
- **Three layers.** Every controlled case states what the mapping says, what Assets answers and what the consumer shows, and the review page shows all three.
- **Checks.** `validate_dataset.py` validates release 1.1 against contract 1.1 and the native grammar, checks that the assignment follows the rule and covers exactly the assets of the release, that the mapping targets agree with it, the Missions cross-check, the pinned hashes of the Missions release and of release 1.0, and the exact regeneration from its own generator.
- **Review.** The lead developer read the review page of release 1.1 before it was released (see the decisions table).
- **Checks.** `validate_dataset.py` checks every record against the contract schema and the kind table, that ids are unique, in grammar and in order, that parents exist, are VEHICLEs and form no cycle, the Missions cross-check (nine ids and 68 references in the released Missions dataset; which resolve and which dangle, with their statuses and mission ids, equal the expected outcomes), the manifest hashes and the exact regeneration. It never touches a network, a database or Docker.
- **Review page.** `generate.py review --output <new folder>` writes the candidate files and a self-contained HTML page (no script, no external font): the nine references with their outcomes, the controlled cases, the parent chains and every asset. It is a dataset-review artifact, not a service frontend, and it is not committed. `generate.py release --lead-reviewed` publishes the release folder and refuses to reuse one (releases 1.0 and 1.1 were published with the flag's earlier name, `--captain-reviewed`, which their frozen generator copies keep).

## The read service

The third slice, in [uss-enterprise/assets](../uss-enterprise/assets/README.md). It answers exactly what contract 1.1 says for dataset release 1.1, and it writes nothing.

- **Schema.** [schema.sql](../uss-enterprise/assets/schema/schema.sql) for PostgreSQL 17, committed and applied to an empty database. `assets` is keyed by `asset_id` with the native grammar of contract 1.1 as a CHECK; `kind` and `status` are foreign keys to the lookup tables `asset_kinds` and `asset_statuses`; the kind-to-category table lives in `asset_kinds` and nowhere else in the service (the service reads the kinds, categories and statuses from the database when it starts, so the filter tokens come from that one table); the category is never stored, and the view `asset_records` derives it from the kind. `parent_asset_id` is a foreign key to the same table, and a trigger enforces the rules the contract cannot express: the parent must exist, only a VEHICLE may be a parent (`asset_categories.can_be_parent`), an asset is not its own parent and the parent chain has no cycle; a second trigger refuses to turn an asset that carries others into one that cannot. The three lookup tables are append-only (a new kind is one row; an update, a delete or a truncate is refused). The order is stored as two generated columns, the letter prefix and the number as a number.
- **Load.** [load_release.py](../uss-enterprise/assets/service/load_release.py) reads `releases/1.1/assets.json` (the default; `--release` picks another) only after the release manifest has vouched for every file and for the contract, loads it in one transaction, parents before children, ordered by depth and then by identifier, refuses a database that already holds assets and checks what it stored (the category included) against the release. Two loads of the release give identical dumps.
- **Service.** [assets_service.py](../uss-enterprise/assets/service/assets_service.py): Python (the repository minimum is 3.13), psycopg 3, one thread per connection. **Web layer: the standard library.** The reason is the one the design already gave for the service, plain on purpose: the only third-party package is the database driver, and the standard handler needs one method table to answer every method with 405 and `Allow: GET`, while a framework would add HEAD and OPTIONS handling that this contract requires to be switched off. The cost is hand-written routing and error mapping, which is small and covered by unit tests that need no database. A request line the library cannot parse is also answered with the contract's JSON error. The service binds to 127.0.0.1 on port 8084 (Personnel 8082 and Missions 8083 are taken), takes the database login from the libpq environment variables only, uses one short read-only connection per request and sends no statement that changes data.
- **Choices the contract left open.** A path outside the two of the contract answers 404 with the code `PATH_NOT_FOUND` (contract 1.1). The first version of the service, under contract 1.0, which had one 404 code, answered `ASSET_NOT_FOUND`, which a consumer that built a wrong path would have read as an unresolved asset; contract 1.1 gives that case its own code. The path and the method are judged before the identifier: a path outside the two is 404 whatever the method, and a method other than GET on either path is 405 whatever the identifier. The raw request target is judged, so `//assets` is outside the contract. An offset beyond the total, however large, is an empty page that echoes the offset. A request that carries a body is answered and its connection closed.
- **Gate.** [run_service_gate.py](../uss-enterprise/assets/validation/run_service_gate.py) discovers [the suite](../uss-enterprise/assets/validation/runtime/service/test_service_gate.py), which starts a disposable `postgres:17-bookworm` container pinned by digest, applies the schema, loads the release with the real script, runs the service as a local process and checks: every valid example of the contract against the live service (status, headers and body against the contract schema); the expected outcomes of the dataset provenance (the three layers of the expected mapping: AST-0097 answers 404 ASSET_NOT_FOUND, the unmapped EQ-108 is never asked and a Missions reference asked of Assets by mistake is 400, AST-0025 is DESTROYED, AST-0006 is MISSING, the others answer 200, the two parent chains, every record of the release served unchanged; and that every path outside the contract answers PATH_NOT_FOUND and never ASSET_NOT_FOUND); the filters alone and combined, paging, the order, and the 400, 404 and 405 cases; that the database refuses a non-VEHICLE parent, a missing parent, a cycle and bad data; that two loads give identical dumps; and that the service never writes (its login cannot, every transaction it opened was read-only according to the server's statement log, and the rows are unchanged). It fails closed and always removes the container. The unit tests of the service logic need no database and run with the other offline tests.
- **What it does not establish.** Python 3.13 (the gate runs under the admitted interpreter, and the code uses nothing newer; the packaging gate runs the service on 3.13 in its image), the federation, any write endpoint (none exists) and behavior under load.

## Packaging

The fourth slice, in [uss-enterprise/assets](../uss-enterprise/assets/README.md#packaging). One command, [start.sh](../uss-enterprise/assets/start.sh) `start`, brings the service up with its own database from the committed files; nothing about the service's behavior changes.

- **Files.** A [Dockerfile](../uss-enterprise/assets/Dockerfile) (one stage on `python:3.13-slim-bookworm` pinned by digest, pinned dependencies, the user `10001:10001`, only the service code, the schema, the load script, the contract 1.1 it checks and release 1.1), its [.dockerignore](../uss-enterprise/assets/.dockerignore), a [compose file](../uss-enterprise/assets/compose.yaml), an example environment file (`uss-enterprise/assets/.env.example`) of placeholders and the [start script](../uss-enterprise/assets/start.sh).
- **Containers.** The database is a separate container (`postgres:17-bookworm` pinned by digest) published nowhere; the service is published on 127.0.0.1:8084 only and holds only the read-only login; a one-shot bootstrap container, built from the service image, holds the administrator login, applies the schema, loads the release or verifies a loaded one and sets the service login on every start. Compose refuses to start without the two passwords, which come from the environment, and the service waits for the healthy database and the completed bootstrap.
- **Data: a named volume.** The volume survives a stop and a start, so the second-start rule (nothing duplicates, a difference from the release is a failure and not a repair) is a real property and not a side effect of throwing the data away. The dataset release is the source of truth and the volume is disposable; the script never removes it, and the reset is the lead developer's own `docker compose down --volumes`. An in-memory database was the alternative: it makes every start a first start and so hides the idempotence rule.
- **Limits.** Explicit CPU and memory limits on all three containers, memory and swap alike: database 1 CPU and 512 MB, service 0.5 CPU and 256 MB, bootstrap 0.5 CPU and 256 MB, chosen modest for a machine with 15.6 GB of RAM (32 GB expected). They exist so that every run of the future benchmark starts from the same conditions; the benchmark design (the Job `benchmark_environment`) wants the machine facts and these limits in every run manifest.
- **The port rule** (the lead developer, 2026-10-15: one copy at a time is fine, but every start checks that the port is free and refuses if it is not). The script tries to connect to 127.0.0.1 on the published port and refuses with one line when something answers; a bind attempt is no test, because Windows lets a second listener bind a taken port without an error. A different service keeps its own port.
- **Gate.** [run_service_gate.py](../uss-enterprise/assets/validation/run_service_gate.py) `packaging` discovers [its suite](../uss-enterprise/assets/validation/runtime/packaging/test_packaging.py): the pinned bases, a compose file that fails closed without credentials, an image built from the committed files that holds nothing else and runs as a non-root user, the real start through the script on an ephemeral port (and the refusal of a taken one), the loopback publication, the database published nowhere, the limits as Docker reports them, the service gate's own HTTP checks run against the published service, a second start that duplicates nothing, a database that differs from the release being refused, and a clean teardown. The checks that need an administrative connection stay in the service gate, because this stack deliberately does not publish the database.
- **What it does not establish.** The federation, orchestration beyond one compose project, a registry, behavior under load and a measured benchmark.

## Contract 1.1: native identifiers and PATH_NOT_FOUND

Contract 1.1 makes two changes to 1.0 and nothing else, in a new immutable file, [assets-v1.1.openapi.json](../uss-enterprise/assets/contracts/assets-v1.1.openapi.json), with its examples in [fixtures/v1.1](../uss-enterprise/assets/fixtures/v1.1/valid/asset-list.json) (`valid` and `invalid`). The 1.0 file and its fixtures are not edited; both versions are validated.

- **Native identifiers.** The lead developer expected the Assets system to have its own identifier, like the Personnel system (PRS-0042 and CRW-1058), and not the references of Missions, and ruled that the prefix must allow an underscore even though no identifier uses one yet. The grammar is `^[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})$`. The prefix is one to three segments of capital letters joined by single underscores: it starts and ends with a letter, has no double underscore (a single underscore keeps a prefix readable, and a double one would only add a second spelling for no gain), has a first segment of 2 to 8 letters and further segments of 1 to 8, so at most 26 characters in all and no limit that the schema cannot state. The number has one canonical spelling: four digits with leading zeros up to 9999 and never all zeros, and from 10000 on no leading zeros, so AST-0017 and AST-10000 are valid and AST-17, AST-017, AST-00017 and AST-0000 are not. Every asset of the dataset uses the prefix AST; the grammar allows other prefixes for the future. The Missions-style identifiers (SH-17) are not valid asset identifiers in 1.1: `GET /assets/SH-17` answers 400 INVALID_ASSET_ID, and so does every filter that names one. The order is the prefix as text, then the number as a number.
- **Why Assets does not reuse the Missions grammar any more.** The Missions references are Missions-local: they belong to the Missions system, as C-85 does for crew. A federated query needs a mapping from a local reference to the owning system's identifier, as Personnel has for crew; that mapping is the integration layer's work (the mapping, releases, validation and interpretation belong to the Integration and Benchmark layer, with immutable releases, an explicit release per request and nothing missing, ambiguous or dangling ever guessed). Assets stores no Missions reference and offers no mapping; Missions stays exactly as it is, with its immutable release 1.0.
- **PATH_NOT_FOUND.** A path outside the two paths answers 404 with a JSON error whose code is PATH_NOT_FOUND. ASSET_NOT_FOUND keeps one meaning only: a well-formed asset lookup that found nothing. Missions answers an unknown path with a bodyless 404 because its frozen contract has no code for it; the Assets contract says every response body is JSON, so a bodyless answer would be the exception. An OpenAPI path object cannot describe "every other path", so the contract names the answer in a top-level `x-unmatchedPath` member that mirrors `x-unsupportedMethods`.
- **The version.** By the table in [Contract evolution](#contract-evolution) a change of the identifier grammar is breaking and would be a new major. It is made in 1.1 by a decision of the lead developer, because 1.0 never had a consumer and was never marked frozen; the exception is recorded once in D038 and the rule is unchanged afterwards. 1.0 and D036 stay as written.
- **Layout and versions.** `contracts/assets-v1.0.openapi.json` and `fixtures/valid`, `fixtures/invalid` are 1.0; `contracts/assets-v1.1.openapi.json` and `fixtures/v1.1/valid`, `fixtures/v1.1/invalid` are 1.1. The service implements 1.1; the unit tests, the service gate and the packaging gate check it against 1.1, and the image holds the 1.1 contract and dataset release 1.1. The dataset release 1.0 pins the hash of the 1.0 file, which has not changed.
- **Not changed.** Missions, Personnel, the port rule, the limits, the start script and the compose file. A later freeze of the exact files and folders of both versions is a separate step.

## Later slices

Each has its own continuity records, in the order Missions followed.

1. Done: the PostgreSQL schema and its load script for the dataset, with the read service.
2. Done: the read service with its gate: the two endpoints against PostgreSQL, checked against this contract.
3. Done: packaging, a Dockerfile and a compose file like the other services, the database as a separate pinned container, the service on loopback and credentials from the environment, with the start script and the packaging gate. Both image digests were resolved again on 2026-10-15.
4. Next, the federation layer, which belongs to a later stage.
5. After the service exists, the planned `frozen` mark of the exact contract and fixture files (see [the evolution rule](#contract-evolution)); it is a separate decision and is not part of the read service slice.

## Points of the lead developer's review

The five open points of the first draft were answered on 2026-10-15; the sources are in the table below.

1. **Paging shape.** Settled: offset and limit stay, with the response `{ items, offset, limit, total }`, limit 1 to 50 and default 20.
2. **Kind of a parent.** Settled by the amendment above: a list of kinds that is easy to extend, a derived category and the rule that only a VEHICLE can be a parent.
3. **Field bounds.** Settled: `name` 1 to 120 and `description` 1 to 1000 code points stay. Widening later is a compatible minor change; narrowing is breaking.
4. **Record of the decision.** Settled: yes, a numbered decision in [Decisions](../project-governance/DECISIONS.md) with its rationale. It is [D036](../project-governance/DECISIONS.md#d036---assets-contract-10-2026-10-15-accepted-scope), added when the contract was settled.
5. **The freeze.** Settled after the amendment: the contract is settled and immutable by [the publication rule](#contract-evolution), stated in words and not marked `frozen` in the classification table; the mark is planned for after the service exists.

## Decisions and their sources

Where the lead developer gave a ruling in the main-console sessions, the table restates it with its date and substance; their exact words are kept in the lab (this document at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`). The rest of this document is the Coordinator's proposals, which the lead developer accepted in the talks, and this slice's drafting.

| Decision | Date | The lead developer's ruling, where they gave one |
| --- | --- | --- |
| A read-only service in a different technology: REST with JSON; ships, shuttles and equipment | 2026-10-13 | The five answers of the direction talk; the asset kinds and the Missions grammar were confirmed there |
| OpenAPI, with JSON Schema for the shapes | 2026-10-14 | OpenAPI for Assets, to be recorded in the design |
| No frontend per service (the conclusion of the talk) | 2026-10-14 | No frontend is needed |
| Python | 2026-10-15 | Python, chosen with enthusiasm |
| A nullable parentAssetId | 2026-10-15 | Add a nullable parentAssetId |
| No location (the Coordinator's reasons, given when the lead developer asked) | 2026-10-15 | The lead developer asked whether a location was needed, since it could interact with Missions; the Coordinator's reasons settled it |
| Five statuses | 2026-10-15 | The three proposed statuses are good, with a value added for destroyed or lost; then the two added values were confirmed |
| Thirty or more assets | 2026-10-15 | 30 or more assets is good |
| The first slice is this design and the contract with examples, validated offline, then a review | 2026-10-15 | Yes |
| The parent must exist | 2026-10-15 | Yes, the parent must exist |
| The federation outcome of an unresolved reference | 2026-10-15 | Option 1 |
| Destroyed and missing assets resolve, with no timing judgment | 2026-10-15 | Yes to destroyed and missing, and no timing judgment |
| The images | 2026-10-15 | Version 17 is good, and both images are settled |
| The kind list and the derived category | 2026-10-15 | A derived category, and ROVER |
| ARMORED_VEHICLE as the name of the combat kind (AFV was considered and not chosen) | 2026-10-15 | ARMORED_VEHICLE, the second of the options |
| Missions may refer to the kind as AV in its own ids | 2026-10-15 | Missions may use AV for short, because the Missions system likes extreme succinctness |
| The parent kind: a list that is easy to extend, not only a SHIP | 2026-10-15 | Not only a SHIP: a list that is easy to extend, since there were surely ground vehicles |
| Offset and limit paging | 2026-10-15 | Agreed |
| A distinct code for a path outside the contract: PATH_NOT_FOUND, added before the freeze | 2026-10-15 | Option A, PATH_NOT_FOUND, and the dependency as proposed |
| Native Assets identifiers, with an underscore allowed in the prefix, in contract 1.1 | 2026-10-15 | The prefix must allow an underscore even though none is used yet, and contract 1.1 is to make the change |
| The review of dataset release 1.1 before its release | 2026-10-15 | The dataset review page is approved; release it and continue with the preview |
| The version of the change: 1.1 with a recorded exception, not 2.0 and not an edit of 1.0 | 2026-10-15 | Option A: keep 1.1 with the exception |
| The text bounds | 2026-10-15 | The bounds are fair and settled |
| A numbered decision for the contract | 2026-10-15 | Yes |
| The freeze waits | 2026-10-15 | Hold point 5 |
| The kind SHIP is renamed STARSHIP | 2026-10-15 | The lead developer asked whether a shuttle is a SHIP and pointed to the Starship Enterprise |
| Assets follows Missions: settled in words, the `frozen` mark after the service exists | 2026-10-15 | Since Missions was not frozen, Assets is not frozen yet either; the freeze is reasonable once the implementation exists (as recorded by the Coordinator) |
| Equipment kinds of their own, and no generic EQUIPMENT kind: nine kinds | 2026-10-15 | Phaser and tricorder were meant to be kinds of their own in the category EQUIPMENT, which the landed draft had departed from; a more specific MUSICAL_INSTRUMENT; keep COMMUNICATOR (as recorded by the Coordinator) |
