# Federation Personnel adapter

The Personnel subgraph of the federation layer: a Java 21 Spring Boot adapter that turns the Personnel v2 SOAP service (contract `urn:graphql-federation-lab:personnel:v2`) into a Federation subgraph. It holds no database. The query fields are answered by one call to the Personnel v2 service each; the entity lookups (the crew references of the routers) are answered from a copy of the immutable snapshot, read once per `datasetVersion` ([The snapshot in memory](#the-snapshot-in-memory)). It is not a legacy system: it lives under `federation/`, beside the shared library `federation/common` and the [Assets](../assets/README.md), [mapping](../mapping/README.md) and [Missions](../missions/README.md) adapters. The design it implements is [the federation design](../../../docs/FEDERATION-DESIGN.md); the findings it builds on are the two federation experiments in [Integration notes](../../../docs/INTEGRATION-NOTES.md). The service it reads is described in the [Personnel v2 specification](../../../docs/PERSONNEL-V2.md) and the [component README](../../../uss-enterprise/personnel-v2/README.md); its contract is the [WSDL](../../../uss-enterprise/personnel-v2/contracts/personnel-v2.wsdl) and the [XSD](../../../uss-enterprise/personnel-v2/contracts/personnel-v2.xsd).

## Layout and ports

- `federation/adapters/personnel/`: this adapter (`Dockerfile`, `compose.yaml`, `start.sh`, `src`, `validation`).
- The shared library `federation/common` is reused as it is; nothing in it changed for this adapter.
- The ports of the federation layer: the routers 8170 (Apollo), 8171 (Cosmo) and 8172 (Hive); the adapters of legacy services mirror the legacy last digit at 81xx: **Personnel adapter 8182**, Missions adapter 8183, Assets adapter 8184; the mapping adapter 8190; 8180 is kept free. The legacy Personnel v2 service stays on 8082. Only 8182 is used here. The GraphQL endpoint is `http://127.0.0.1:8182/graphql`.

## The schema

The schema file is `src/main/resources/graphql/schema.graphqls`. It declares Federation 2.0 (`@link`) and uses only `@key`, `@requires` and `@external`. The contract's element names are the field names, and the enum names and values are the contract's own.

- `Personnel` (entity, `@key(fields: "personnelId")`): `personnelId`, `displayName`, `positionTitle`, `dutyStatus` and `details`, in the contract's order.
- `details` is the union `PersonnelDetails = CrewDetails | CivilianDetails`, which mirrors the contract's choice (a member has `crewDetails` or `civilianDetails`, exactly one). `CrewDetails` is `rank`, `department`, `securityClearance` and `supervisorPersonnelId` (nullable: no supervisor recorded). The supervisor stays a plain `ID`; there is no nested supervisor object yet.
- **`CivilianDetails` has one placeholder field.** The contract's `CivilianDetails` is an empty type (a civilian has no rank, department, clearance or reporting fields), and GraphQL does not allow an object type without fields. The type has the single nullable field `placeholder: Boolean`, which is always null and carries no fact (its description says so). It was chosen over a non-null `Boolean` that is always true because a client then reads nothing it did not get from the service: a civilian is recognized by the type name (`__typename` or `... on CivilianDetails`), never by a value. A civilian is never senior: there is no rank to read.
- Enums with the contract's exact values: `Rank` (`CAPTAIN`, `COMMANDER`, `LIEUTENANT_COMMANDER`, `LIEUTENANT`, `ENSIGN`, `CHIEF_PETTY_OFFICER`, `CREWMAN`), `Department`, `SecurityClearance`, `DutyStatus`. A test compares them with the XSD.
- `Query.personnel(personnelId)` and `Query.personnelMembers(department, dutyStatus, offset, limit)`.
- `PersonnelPage` is what `personnelMembers` returns: `datasetVersion`, `items`, `totalCount`, `offset`, `limit` and `hasMore`, all taken from the service's answer. The Missions and Assets lists are bare lists; this one is a page because the contract says a consumer must restart at offset 0 when `datasetVersion` changes between pages, and the adapter holds no state, so it cannot see that across the pages of a client. It **exposes `datasetVersion` on every page** and the client compares it. The candidate code `DATASET_CHANGED` is not used.
- `PersonnelReference` (entity, `@key(fields: "localRef release")`): the crew reference, on the pattern of `AssetReference`. `personnelId` and `mappingOutcome` are `@external` (the mapping subgraph contributes them) and `resolution` and `personnel` each `@requires(fields: "personnelId mappingOutcome")`. There is no separate `id` field: the mapped id is `personnelId`, the confirmed one is `personnel.personnelId`. The outcome is read from `mappingOutcome`, never inferred from a null id (`NO_ENTRY` gives UNMAPPED, `RELEASE_REFUSED` gives RELEASE_REFUSED, `MAPPED` is looked up). The `Resolution` enum has five values. `resolution` is nullable in the schema, but THIS adapter never returns null: a null reaches a client only when the router could not ask the adapter (see the [router README](../../routers/apollo/README.md#a-null-resolution)). The mapping release is a key field, with no implicit latest.

## Outcomes and errors

| Answer of the service | `personnel(personnelId)` | `PersonnelReference` | Errors entry |
| --- | --- | --- | --- |
| 200 with the member | the member | `RESOLVED` | none |
| fault `PersonnelNotFound` (HTTP 500) | null (not-found is data) | `UNRESOLVED` | none |
| fault `InvalidRequest` | null | `UNAVAILABLE` | `BAD_USER_INPUT` for the query (a client id); `UPSTREAM_BAD_RESPONSE` for a reference (an id the mapping handed on) |
| connection failure, timeout, any other 5xx (the faults `ServiceUnavailable` and `InternalError` included) | null | `UNAVAILABLE` | `SERVICE_UNAVAILABLE` |
| a body that is not the contract, or any other status | null | `UNAVAILABLE` | `UPSTREAM_BAD_RESPONSE` |
| `mappingOutcome` NO_ENTRY (the mapping has no entry) | | `UNMAPPED`, no call | none |
| `mappingOutcome` RELEASE_REFUSED | | `RELEASE_REFUSED`, no call | none from this adapter (the mapping subgraph made the `MAPPING_RELEASE_*` entry) |

One errors entry is made per failed call, attached to the field that needed it; a reference whose fields are all selected makes at most one entry. For `Query.personnel` and `Query.personnelMembers` the table is read as written. For a `PersonnelReference` and for a `Personnel` entity the answer is read from the snapshot ([below](#the-snapshot-in-memory)): the failure rows are the failure of the list call that confirmed or read the snapshot, with the same codes, and `PersonnelNotFound` is a person absent from the snapshot. `UNRESOLVED` and `UNMAPPED` are data and add no entry. The codes are those of [the decided list](../../../docs/FEDERATION-DESIGN.md#failure-semantics); `MAPPING_RELEASE_REQUIRED` and `MAPPING_RELEASE_NOT_FOUND` are not used here (the mapping subgraph refuses a missing or unknown release). `_entities` for `Personnel` answers an unknown key with null and no entry, as the router expects.

A body is accepted only if it reads as the contract says: the SOAP 1.1 envelope, the elements in order and in the Personnel namespace, no attribute (so no `xsi:nil`), the id `PRS-0001` to `PRS-9999`, every enum token, a name of 1 to 100 characters counted as code points and not blank, exactly one of `crewDetails` and `civilianDetails`, an empty `civilianDetails`, the members in ascending `personnelId` order, and a page whose `hasMore` and counts agree. The member must be the one asked for and the page must echo the offset and the limit that were asked for. Anything else is `UPSTREAM_BAD_RESPONSE`, never a guess.

## The snapshot in memory

A page of 100 missions with commanders and crews holds about 750 to 1,250 references, and one SOAP call per person put cold pages over the routers' 5 second subgraph timeout. The Personnel v2 contract makes a snapshot immutable and stamps every answer with its `datasetVersion` ([specification](../../../docs/PERSONNEL-V2.md)): a person's record cannot differ between two answers that name the same version. The adapter uses that for the entity lookups, and for nothing else.

- **A batch** is one `_entities` call. Its first lookup asks the service ONE cheap list call (offset 0, limit 1), the probe, which proves the service answers now and names the version it serves. The probe is the only call a further batch of the same version makes. A batch that looks nothing up (every reference UNMAPPED or RELEASE_REFUSED, or no field selected) makes no call.
- **Reading the snapshot.** When the version is not the copy's (the first batch, or the service switched snapshot), the copy is emptied and the whole snapshot is read through the list operation in pages of 100 (ten calls for `personnel-v2-large-004`). Every page must carry the same `datasetVersion` and the same count; when the version changes between pages the read restarts at offset 0 (three restarts at most, then UNAVAILABLE with `SERVICE_UNAVAILABLE`). A page that fails, does not echo its offset and limit, lists a member twice or does not add up gives UNAVAILABLE and no copy is kept. Batches that find the copy missing at the same moment wait for one read.
- **An outage is still an outage.** A copy is never served without a probe that has just succeeded. A failed probe or page is UNAVAILABLE with the code the failed call had before (`SERVICE_UNAVAILABLE` for a connection failure, a timeout or any 5xx, `UPSTREAM_BAD_RESPONSE` for a body the adapter cannot use or a request the service refuses), with one errors entry per reference or entity, as before. The copy survives an outage: when the service is back at the same version nothing is read again.
- **A person who is not in the snapshot** is UNRESOLVED (data, no entry), as the fault `PersonnelNotFound` was; a `Personnel` entity of an unknown key is null with no entry.
- **Not served from the copy.** `Query.personnel` and `Query.personnelMembers` stay one call each, because their answers go to a client that compares versions itself. An id the contract cannot hold (anything but `PRS-0001` to `PRS-9999`) is not looked up: it is sent to the service, which refuses it as before.
- **Size and limits.** One snapshot at a time, about a thousand members for `personnel-v2-large-004`, replaced when the version changes. The probe and the lookups of a batch are not one atomic step: a service that switches snapshot between them is answered from the snapshot the probe confirmed, the same window that two calls of a call-per-person adapter had. No new setting was added; the timeouts below apply to every call of a read.

## Paging

The graph pages by `offset` and `limit` (default 20, maximum 100). The service allows 100 per call, so a page is **one call**. A limit above 100 or below 1, or a negative offset, is `BAD_USER_INPUT` and makes no call; a null offset or limit means the default. An offset past the end gives an empty page. **All or nothing:** if the call fails, the whole result is null with one errors entry.

## The SOAP client

The adapter sends the two requests of the contract as hand-written SOAP 1.1 envelopes with the JDK's HTTP client and reads the answers with the JDK's DOM parser: **no dependency was added** to the Missions adapter's set. A client generated from the WSDL (JAX-WS with Apache CXF, or Spring Web Services with JAXB) would add a SOAP stack, a code generation step and several libraries to pin, for two operations of a few lines each; the contract is small and frozen enough that a strict reader of it is simpler to review than generated code. The cost is that the adapter's reading of the contract is its own code, which the tests check against the real XSD and the real snapshots.

- **Requests:** the id is written into the envelope XML-escaped; an id with a character outside printable ASCII (a control character cannot be written in XML at all) is `BAD_USER_INPUT` and is never sent. Any other malformed id is sent and the service owns the verdict: it answers `InvalidRequest`. The offline tests validate **every request the adapter sends against the real XSD** in the stub.
- **The parser is safe, the same way the Missions adapter's is:** a document that carries a DOCTYPE is refused outright (`disallow-doctype-decl`), which removes external entities, external DTDs and entity expansion (a billion-laughs document included) in one rule, because the service never sends one; secure processing is on, external general and parameter entities and external DTD loading are off, XInclude is off, and `ACCESS_EXTERNAL_DTD` and `ACCESS_EXTERNAL_SCHEMA` are empty. The tests run hostile bodies against a tripwire server and assert that nothing was fetched.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `PERSONNEL_SERVICE_URL` | `http://127.0.0.1:8082/soap/personnel-v2` on the host; `http://host.docker.internal:8082/soap/personnel-v2` in the compose file | The Personnel v2 SOAP endpoint. In one compose project use the service name. |
| `PERSONNEL_CONNECT_TIMEOUT_MS` | 1000 | Connect timeout. |
| `PERSONNEL_READ_TIMEOUT_MS` | 1500 | Timeout of the whole call after the connection. |
| `ADAPTER_PORT`, `ADAPTER_BIND_HOST` | 8182, 127.0.0.1 (0.0.0.0 in the image) | Where the adapter listens. |
| `PERSONNEL_ADAPTER_HOST_PORT` | 8182 | The loopback port compose publishes (`start.sh`, `compose.yaml`). |

No secret is needed or kept in any file.

## Run

Docker only; no JDK or Maven is needed on the machine. From Git Bash, with the Personnel v2 service running on 8082 (`docker compose -f uss-enterprise/personnel-v2/compose.yaml up --build`, see the [component README](../../../uss-enterprise/personnel-v2/README.md); `PERSONNEL_DATASET_VERSION` selects the snapshot):

```sh
bash federation/adapters/personnel/start.sh start
```

`start.sh` refuses with one line when 127.0.0.1:8182 is taken, and never removes a container, an image or a volume. The container limits (1 CPU, 512 MB, read-only filesystem, no capabilities) are **provisional**: the limits of the adapters wait for the benchmark environment record.

## Versions and digests (resolved 2026-10-16)

The versions are those of the [Assets adapter](../assets/README.md#versions-and-digests-resolved-2026-10-16): Spring Boot 3.4.13, Spring for GraphQL 1.3.7, graphql-java 22.3 and federation-graphql-java-support 5.4.0 on Java 21 (Temurin); nothing was upgraded and nothing was added. The two base images are the same digests as the other adapters, read again on 2026-10-16 and unchanged (the build uses its own copy of the pins, recorded in the `Dockerfile`):

| Image | Digest |
| --- | --- |
| `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |

The build context is the repository root, not `federation/`: the offline tests read the real XSD and the two registered snapshots from `uss-enterprise/personnel-v2`, and `Dockerfile.dockerignore` keeps the context to the poms, the sources, that contract and those snapshots.

## Validation

`validation/run_adapter_gate.py` runs two stages and fails closed (a skip, an empty suite or a missing Docker is a failure):

- `offline`: the committed Dockerfile builds the adapter, and its build stage runs `mvn verify`: the unit and integration tests against a stub of the Personnel v2 service that serves the two registered snapshots (every member, both subtypes, the Wesley case in both snapshots, the list, the filters and the paging) and checks every request against the real XSD, the faults (not found, invalid request, service unavailable, internal error), a 500, a timeout, a malformed envelope, hostile XML, the four outcomes of a crew reference, the snapshot read once in pages of 100 and served from memory (one probe per batch, a reload on a new `datasetVersion`, a restart when the version changes between pages, a failed or inconsistent page, concurrent batches reading once), an outage of the probe answered UNAVAILABLE with one errors entry per reference, the `_service` and `_entities` answers and the Federation features limited to `@key`, `@requires` and `@external`. Then the image, the compose file and the start script are checked and run on an ephemeral loopback port.
- `service`: the adapter against the REAL Personnel v2 service (a light Java 17 container, no database), through a private Docker network with no published port: every member of the default snapshot, the page and the filters, the Wesley case across a restart with the first snapshot, the four outcomes of a reference, the whole `personnel-v2-large-004` snapshot read in ten pages and served from memory (the first, a middle and the last person of the snapshot, and an absent one), and the failure profiles `unavailable` and `slow` and a stopped service.

```sh
python -B federation/adapters/personnel/validation/run_adapter_gate.py offline
python -B federation/adapters/personnel/validation/run_adapter_gate.py service
```

## Limits

**The live crew path.** The mapping release 1.1 carries the crew section, so the mapping subgraph supplies `personnelId` and `mappingOutcome`, and through the router the crew references of a mission resolve against the Personnel v2 snapshot `personnel-v2-small-003` (the whole-stack default until 2026-10-19, which now serves `personnel-v2-large-004`); in release 1.0 they are `NO_ENTRY` and UNMAPPED, and in a refused release RELEASE_REFUSED. The Apollo router Job (`federation/routers/apollo`) tests the composition and the graph refinements Job tests release 1.1 end to end. The Missions adapter's `assignedCrewIds` stay raw strings. Not built here: the nested supervisor object, the router and the whole-stack compose. `Personnel.datasetVersion` is not a field of the entity: only a list page carries the version, because the contract's version is a property of an answer, and a federated entity fetched by key has no page to hold it.
