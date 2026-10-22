# Federation Assets adapter

The Assets subgraph of the federation layer: a Java 21 Spring Boot adapter that turns the Assets REST/JSON service (contract 1.1, ids `AST-nnnn`) into a Federation subgraph. It holds no state and no database; every answer comes from calls to the Assets service. It is not a legacy system: it lives under `federation/`, beside the shared library `federation/common`. The design it implements is [the federation design](../../../docs/FEDERATION-DESIGN.md); the findings it builds on are the two federation experiments in [Integration notes](../../../docs/INTEGRATION-NOTES.md).

## Layout and ports

- `federation/pom.xml`: the parent pom (Java 21, Maven, the pinned versions, the modules `common`, `adapters/missions` and `adapters/assets`).
- `federation/common/`: the shared library, with no vendor-specific feature and no Apollo, Cosmo or Hive dependency. It holds the `Resolution` enum (RESOLVED, UNRESOLVED, UNAVAILABLE, UNMAPPED), the derivation of the outcome from the result of one HTTP call (`Outcomes.fromCall`), the builder of the errors entry (`FederationErrors`) and the `ErrorCode` list.
- `federation/adapters/assets/`: this adapter (`Dockerfile`, `compose.yaml`, `start.sh`, `src`, `validation`).
- The ports of the federation layer: the routers 8170 (Apollo), 8171 (Cosmo) and 8172 (Hive); the adapters of legacy services mirror the legacy last digit at 81xx: Personnel adapter 8182, Missions adapter 8183, **Assets adapter 8184**; the mapping adapter 8190; 8180 is kept free. The legacy ports stay 8081, 8082, 8083 and 8084. Only 8184 is used here. The GraphQL endpoint is `http://127.0.0.1:8184/graphql`.

## The schema

The schema file is `src/main/resources/graphql/schema.graphqls`. It declares Federation 2.0 (`@link`) and uses only `@key`, `@requires` and `@external`.

- `Asset` (entity, `@key(fields: "assetId")`): `assetId`, `kind`, `category`, `name`, `description`, `status`, `parentAssetId`, the fields of contract 1.1, with its three enums `AssetKind`, `AssetCategory` and `AssetStatus`, and `parent: Asset`, the parent asset. `parent` is resolved by this adapter from its own service: ONE call per level, made only when the client selects it (lazy), with no federation feature beyond `@key`, no caching and no batching. A top-level asset (no `parentAssetId`) gives null with no call; a parent id that does not exist gives null with no errors entry (not-found is data); a failed call gives null with one `SERVICE_UNAVAILABLE` (or `UPSTREAM_BAD_RESPONSE`) entry for that call. A chain such as AST-0004, AST-0023, AST-0029 is one query: `asset { assetId parent { assetId parent { assetId } } }`.
- `AssetReference` (entity, `@key(fields: "localRef release")`): `localRef`, `release`, `assetId` and `mappingOutcome` (both `@external`, supplied by the mapping subgraph) and `resolution` and `asset`, each with `@requires(fields: "assetId mappingOutcome")`. There is no separate `id` field: the mapped id is `assetId`, the confirmed one is `asset.assetId`. The outcome is computed once per entity with at most one call, on the first of those fields the query selects, and it is **read from `mappingOutcome`, never inferred from a null `assetId`**: `NO_ENTRY` gives UNMAPPED and `RELEASE_REFUSED` gives RELEASE_REFUSED, both without a call; `MAPPED` is looked up. `MAPPED` with no `assetId` is a contradiction of the mapping and is UNAVAILABLE with `UPSTREAM_BAD_RESPONSE`. A representation without a valid `mappingOutcome` is an adapter fault (`INTERNAL_SERVER_ERROR`). The `Resolution` enum has five values: RESOLVED, UNRESOLVED, UNAVAILABLE, UNMAPPED and RELEASE_REFUSED. `resolution` is nullable in the schema, but THIS adapter never returns null: a null reaches a client only when the router could not ask the adapter (see the [router README](../../routers/apollo/README.md#a-null-resolution)).
- `Query.asset(assetId)` and `Query.assets(kind, category, status, parentAssetId, offset, limit)`. Offset and limit page at the graph level: the default limit is 20, the maximum 100, and a page above 50 takes two calls because the service allows 50 per call. A limit above 100 or below 1, or a negative offset, is `BAD_USER_INPUT` and makes no call.

## Outcomes and errors

| Answer of the service | Outcome of a reference | Errors entry |
| --- | --- | --- |
| 200 | RESOLVED, with the asset (any status: DESTROYED and MISSING resolve) | none |
| 404 whose body carries `ASSET_NOT_FOUND` | UNRESOLVED, `asset` null | none |
| `mappingOutcome` NO_ENTRY | UNMAPPED, no call | none |
| `mappingOutcome` RELEASE_REFUSED | RELEASE_REFUSED, no call | none from this adapter (the mapping subgraph made the `MAPPING_RELEASE_*` entry) |
| connection failure, timeout, 5xx | UNAVAILABLE, `asset` null | `SERVICE_UNAVAILABLE` |
| any other answer (a 404 `PATH_NOT_FOUND` included) or a body that cannot be used | UNAVAILABLE, `asset` null | `UPSTREAM_BAD_RESPONSE` |

One errors entry is made per failed call, not per reference, and it is attached to the first selected field of the entity that needs the call. A page of `assets` is all or nothing: if any call of the page fails, the whole list is null with one entry, and the second call is not made after a first failure. The other codes: `BAD_USER_INPUT` (a malformed id or paging argument) and `INTERNAL_SERVER_ERROR` (a fault of the adapter). The names `BAD_USER_INPUT` and `INTERNAL_SERVER_ERROR` are those of Apollo Server's documented error codes (checked 2026-10-16 in its error documentation). `MAPPING_RELEASE_REQUIRED` and `MAPPING_RELEASE_NOT_FOUND` are in the library for the mapping adapter and are not used here. A failure of the adapter itself is the router's own error, by the decided limit.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `ASSETS_SERVICE_URL` | `http://127.0.0.1:8084` on the host; `http://host.docker.internal:8084` in the compose file | The Assets service. In one compose project use the service name. |
| `ASSETS_CONNECT_TIMEOUT_MS` | 1000 | Connect timeout. |
| `ASSETS_READ_TIMEOUT_MS` | 1500 | Timeout of the whole call after the connection. |
| `ADAPTER_PORT`, `ADAPTER_BIND_HOST` | 8184, 127.0.0.1 (0.0.0.0 in the image) | Where the adapter listens. |
| `ASSETS_ADAPTER_HOST_PORT` | 8184 | The loopback port compose publishes (`start.sh`, `compose.yaml`). |

No secret is needed or kept in any file.

## Run

Docker only; no JDK or Maven is needed on the machine. From Git Bash, with the Assets service running on 8084 (`bash uss-enterprise/assets/start.sh start`):

```sh
bash federation/adapters/assets/start.sh start
```

`start.sh` refuses with one line when 127.0.0.1:8184 is taken (the Assets precedent), and never removes a container, an image or a volume. The container limits (1 CPU, 512 MB, read-only filesystem, no capabilities) are **provisional**: the limits of the adapters wait for the benchmark environment record.

## Versions and digests (resolved 2026-10-16)

Spring Boot 3.4.13 (experiment 1 used 3.4.5; 3.4.13 is the newest 3.4 patch on Maven Central), which manages Spring for GraphQL 1.3.7; graphql-java held at 22.3, the version federation-jvm 5.4.0 declares and the experiments ran (Boot 3.4.13 manages 22.4); federation-graphql-java-support 5.4.0. Java 21 on Temurin.

| Image | Digest |
| --- | --- |
| `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |

Both are the digests of 2026-10-15 and 2026-10-16: the tags had not moved. Tags move; resolve the digests again before changing a pin.

Found on the day and not acted on: federation-jvm has releases after 5.4.0 on Maven Central (5.5.0, 6.0.0, 6.1.0, 6.2.0, 6.2.1 and 7.0.0, the last modified 2026-08-03), which the design document's "newest is 5.4.0" does not reflect. They are majors or a minor, not patches, and were not tried; 7.0.0 declares graphql-java 26.0. Spring Boot 3.4 is believed to be past its open-source support; that is not verified.

## Validation

`validation/run_adapter_gate.py` runs two stages and fails closed (a skip, an empty suite or a missing Docker is a failure):

- `offline`: the committed Dockerfile builds the adapter, and its build stage runs `mvn verify`: the unit and integration tests against a stub of the Assets service (all four outcomes, a 404 `ASSET_NOT_FOUND` against any other 404, the timeouts, the two-call page and the all-or-nothing rule, one errors entry per failed call, the `_service` and `_entities` answers, the Federation features limited to `@key`, `@requires` and `@external`, a limit above 100 refused with `BAD_USER_INPUT`). Then the image, the compose file and the start script are checked and run on an ephemeral loopback port.
- `service`: the adapter against the real Assets service and a disposable PostgreSQL 17 (Assets compose file, uniquely named project, random credentials), with the expected outcomes of the released Assets dataset 1.1 (the expected mapping in three layers) and a stopped service for UNAVAILABLE.

```sh
python -B federation/adapters/assets/validation/run_adapter_gate.py offline
python -B federation/adapters/assets/validation/run_adapter_gate.py service
```

## Limits

Not built here: the Personnel adapter, the routers, the whole-stack compose, the Hive or Cosmo configuration and a start script shared by all containers. The adapter folder builds from the `federation/` context. The Dockerfile copies the pom and the sources of every adapter, because the parent pom lists every module, so a later adapter changes the parent's module list and nothing in this folder.
