# Federation Missions adapter

The Missions subgraph of the federation layer: a Java 21 Spring Boot adapter that turns the Missions REST/XML service (contract 1.1, namespace `urn:starfleet:missions:v1`) into a Federation subgraph. It holds no state and no database; every answer comes from calls to the Missions service. It is not a legacy system: it lives under `federation/`, beside the shared library `federation/common` and the [Assets adapter](../assets/README.md). The design it implements is [the federation design](../../../docs/FEDERATION-DESIGN.md); the findings it builds on are the two federation experiments in [Integration notes](../../../docs/INTEGRATION-NOTES.md). The service it reads is described in the [Missions README](../../../uss-enterprise/missions/README.md) and the [Missions design](../../../docs/MISSIONS-V1-DESIGN.md).

## Layout and ports

- `federation/adapters/missions/`: this adapter (`Dockerfile`, `compose.yaml`, `start.sh`, `src`, `validation`).
- The shared library `federation/common` is reused as it is, with one addition: `Outcomes.fromCall` takes an optional reader of the service's error code, because the Missions service answers its errors in XML and the library read only JSON.
- The ports of the federation layer: the routers 8170 (Apollo), 8171 (Cosmo) and 8172 (Hive); the adapters of legacy services mirror the legacy last digit at 81xx: Personnel adapter 8182, **Missions adapter 8183**, Assets adapter 8184; the mapping adapter 8190; 8180 is kept free. The legacy Missions service stays on 8083. Only 8183 is used here. The GraphQL endpoint is `http://127.0.0.1:8183/graphql`.

## The schema

The schema file is `src/main/resources/graphql/schema.graphqls`. It declares Federation 2.0 (`@link`) and uses only `@key`, with `resolvable: false` on the reference stub.

- `Mission` (entity, `@key(fields: "missionId")`): the contract's element names are the field names, in the contract's order: `missionId`, `title`, `type`, `classification`, `status`, `priority`, `stardate`, `durationHours`, `objective`, `location`, `issuingAuthority`, `commandingOfficerId`, `assignedCrewIds`, `participantIds`, `assignedAssetIds`, `estimatedCostCredits`, `actualCostCredits`, `outcome`, `lastUpdated`, and the reference fields `assets(release: String!)`, `crew(release: String!)` and `commandingOfficer(release: String!)`.
- `MissionLocation`: `type`, `name`, `coordinates`, `travelVector`. Two contract type names carry a `Mission` prefix because the graph is shared: the contract's `Status` is `MissionStatus` and its `Location` is `MissionLocation`. The other enums keep the contract's names and exact values: `MissionType` (with MAINTENANCE of contract 1.1), `Classification`, `LocationType`, `IssuingAuthority`.
- **Credits and the stardate are strings.** They carry the contract's canonical decimal spelling exactly as the service sent it (`"140000.00"`, `"43125.80"`). A binary float never holds them: it cannot hold every decimal and would turn `43125.80` into `43125.8`; a scalar of our own would be one more thing for every router to agree on, and the contract already fixes one spelling. `priority` and `durationHours` are `Int`. `lastUpdated` is the contract's UTC text.
- `assignedCrewIds`, `participantIds` and `assignedAssetIds` are the Missions-local references as stored, plain data.
- `Mission.crew(release: String!)` returns one `PersonnelReference` stub per entry of `assignedCrewIds` (not the commanding officer and not the participants), `{ localRef, release }`, in the service's order, on the same pattern as `assets`. `PersonnelReference` is `@key(fields: "localRef release", resolvable: false)`: the Personnel adapter owns and resolves it and the mapping subgraph supplies `personnelId`. Added by the router Job so that a crew reference can be reached through the graph; no call is made.
- `Mission.commandingOfficer(release: String!)` returns the commanding officer as one `PersonnelReference` stub, `{ localRef, release }` with the `commandingOfficerId` as stored, or null when the mission has none (the contract requires one from AUTHORIZED on; a PLANNED or CANCELLED mission may have none). It lets a client check the mission's Starfleet personnel, the commanding officer and the assigned crew (question 6), through the same mapping and the same Personnel resolution; `commandingOfficerId` stays as it was, and no call is made.
- `Mission.assets(release: String!)` returns one `AssetReference` stub per assigned asset, `{ localRef, release }`, in the service's order. `AssetReference` is `@key(fields: "localRef release", resolvable: false)`, exactly the missions stub of experiment 2: this adapter does not call Assets or the mapping. It supplies the reference as stored and the release the client named, passed through unchanged (the mapping subgraph refuses an unknown release). federation-jvm lists a `resolvable: false` type in the `_Entity` union all the same, as in the experiment; the adapter answers an `_entities` request for it with `INTERNAL_SERVER_ERROR`, and a router never sends one.
- `Query.mission(missionId)` and `Query.missions(type, classification, status, priority, issuingAuthority, commandingOfficerId, assignedCrewId, assignedAssetId, locationType, offset, limit)`: the filters of the contract, combined with AND by the service.

## Paging

The graph pages by `offset` and `limit` (default 20, maximum 100). The service pages by `page` and `pageSize` (1 to 50), ordered by stardate, priority and missionId ascending. The adapter translates with the covering pages and slices:

- It chooses the page size from 1 to 50 that covers the window `[offset, offset + limit)` with the fewest calls, then with the fewest rows fetched. A limit of 20 at offset 0 is one call of 20; an offset that is not a multiple of the limit usually still fits one call of another size (offset 45, limit 20 is page 3 of size 22); a limit above 50 takes two calls where a page size covers the window with two and three otherwise (for example offset 49, limit 100).
- An offset past the end gives an empty list (the service answers a valid page beyond the end with no missions); a short page ends the fetch, because the rows after it do not exist.
- **All or nothing:** if any call of the page fails, the whole list is null with ONE errors entry and no further call is made. The page and page size a response echoes must be the ones asked for, or the call is an `UPSTREAM_BAD_RESPONSE`.
- A limit above 100 or below 1, or a negative offset, is `BAD_USER_INPUT` and makes no call.

## Outcomes and errors

| Answer of the service | `mission(missionId)` | Errors entry |
| --- | --- | --- |
| 200 | the mission | none |
| 404 whose XML error body carries `MISSION_NOT_FOUND` | null (not-found is data) | none |
| 400 with `INVALID_MISSION_ID` | null | `BAD_USER_INPUT` |
| connection failure, timeout, 5xx | null | `SERVICE_UNAVAILABLE` |
| any other answer (the bodyless 404 of an unknown path included) or a body that is not the contract | null | `UPSTREAM_BAD_RESPONSE` |

A list reads the same way, except that a 400 with `INVALID_REQUEST` is `BAD_USER_INPUT` (only a filter value can cause it, because the adapter's own `page` and `pageSize` are valid), and any failure makes the whole list null with one entry. An enum filter value outside the contract never reaches the adapter: GraphQL refuses it first with its own validation error. One errors entry is made per failed call, attached to the field that needed it. `_entities` for `Mission` answers an unknown key with null and no entry, as the router expects. The ETag headers are ignored: the adapter only reads. The codes are those of [the decided list](../../../docs/FEDERATION-DESIGN.md#failure-semantics); `MAPPING_RELEASE_REQUIRED` and `MAPPING_RELEASE_NOT_FOUND` are not used here.

A body is accepted only if it reads as the contract says: the root element and every element in the Missions namespace, every required element present, every enum token and number in range. Anything else is `UPSTREAM_BAD_RESPONSE`, never a guess.

## The XML parser is safe

The XML is parsed with the JDK's namespace-aware DOM parser configured so that nothing outside the document can be read: a document that carries a DOCTYPE is refused outright (`disallow-doctype-decl`), which removes external entities, external DTDs and entity expansion (a billion-laughs document included) in one rule, because the service never sends one; secure processing is on, external general and parameter entities and external DTD loading are off, XInclude is off, and `ACCESS_EXTERNAL_DTD` and `ACCESS_EXTERNAL_SCHEMA` are empty. The tests run hostile bodies (an external general entity, an external parameter entity, an external DTD, an internal entity bomb, an XInclude) against a tripwire server and assert that nothing was fetched.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `MISSIONS_SERVICE_URL` | `http://127.0.0.1:8083` on the host; `http://host.docker.internal:8083` in the compose file | The Missions service. In one compose project use the service name. |
| `MISSIONS_CONNECT_TIMEOUT_MS` | 1000 | Connect timeout. |
| `MISSIONS_READ_TIMEOUT_MS` | 1500 | Timeout of the whole call after the connection. |
| `ADAPTER_PORT`, `ADAPTER_BIND_HOST` | 8183, 127.0.0.1 (0.0.0.0 in the image) | Where the adapter listens. |
| `MISSIONS_ADAPTER_HOST_PORT` | 8183 | The loopback port compose publishes (`start.sh`, `compose.yaml`). |

No secret is needed or kept in any file.

## Run

Docker only; no JDK or Maven is needed on the machine. From Git Bash, with the Missions service running on 8083 (`docker compose -f uss-enterprise/missions/compose.yaml up --detach --build`, which needs the Oracle container and a service login, see the [Missions README](../../../uss-enterprise/missions/README.md#packaging-and-deployment)):

```sh
bash federation/adapters/missions/start.sh start
```

`start.sh` refuses with one line when 127.0.0.1:8183 is taken, and never removes a container, an image or a volume. The container limits (1 CPU, 512 MB, read-only filesystem, no capabilities) are **provisional**: the limits of the adapters wait for the benchmark environment record.

## Versions and digests (resolved 2026-10-16)

The versions are those of the [Assets adapter](../assets/README.md#versions-and-digests-resolved-2026-10-16): Spring Boot 3.4.13, Spring for GraphQL 1.3.7, graphql-java 22.3 and federation-graphql-java-support 5.4.0 on Java 21 (Temurin); nothing was upgraded. The two base images are the same digests (the build uses its own copy of the pins, recorded in the `Dockerfile`):

| Image | Digest |
| --- | --- |
| `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |

The build context is the repository root, not `federation/`: the offline tests read the real contract fixtures and the six pages of the released dataset 1.2 from `uss-enterprise/missions`, and `Dockerfile.dockerignore` keeps the context to the poms, the sources, those fixtures and the released pages.

## Validation

`validation/run_adapter_gate.py` runs two stages and fails closed (a skip, an empty suite or a missing Docker is a failure):

- `offline`: the committed Dockerfile builds the adapter, and its build stage runs `mvn verify`: the unit and integration tests against a stub of the Missions service that serves the real contract fixtures and the released dataset 1.2 (every one of its 300 missions, listed in the contract's order, the list pages, the filters, the 404, the 400s, a 500, a timeout, a malformed body, hostile XML), the paging translation (every window of every limit against an in-memory service), the all-or-nothing rule, one errors entry per failed call, the asset reference stubs, the `_service` and `_entities` answers and the Federation features limited to `@key`. Then the image, the compose file and the start script are checked and run on an ephemeral loopback port.
- `service`: the adapter against the REAL Missions service on Oracle 18c, through the harness of the Missions service gates (a disposable schema loaded with release 1.2, a read-only login, a service with the right password and one with a wrong one, which answers 500). **The reviewed Oracle container must already be running**; it is a lab container of about 9 GB that the lead developer keeps stopped, so this stage is run deliberately and is not part of a checkpoint.

```sh
python -B federation/adapters/missions/validation/run_adapter_gate.py offline
python -B federation/adapters/missions/validation/run_adapter_gate.py service
```

## Limits

Not built here: the crew mapping. The start script for all containers is `federation/stack/start.sh` and the routers are in `federation/routers/apollo`. Every crew reference is unmapped in the graph until the crew mapping (release 1.1) exists. The adapter leaves the grammar of a mission id to the service, which answers `INVALID_MISSION_ID` for a malformed one; the only id it refuses itself, as `BAD_USER_INPUT` and without a call, is one that cannot be a single path segment (a slash or a backslash in it, or an empty, `.` or `..` id): the real service gate showed that the service's container answers such an id with something that is not the contract's error, which would have been reported as `UPSTREAM_BAD_RESPONSE` and blamed on the service.
