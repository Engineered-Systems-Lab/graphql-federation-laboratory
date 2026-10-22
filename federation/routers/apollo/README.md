# Federation Apollo router

The Apollo router of the federation layer, the composition of the four subgraphs into one supergraph with Rover, and the first end-to-end acceptance tests. One GraphQL endpoint, `http://127.0.0.1:8170/`, answers across Missions, the mapping, Assets and Personnel. The design it implements is [the federation design](../../../docs/FEDERATION-DESIGN.md); the findings it builds on are the two federation experiments in [Integration notes](../../../docs/INTEGRATION-NOTES.md). The whole-stack compose file, its start script and the stub of the Missions service are in [federation/stack](../../stack/README.md).

## Layout and ports

- `router.yaml`: the router configuration (listen `0.0.0.0:4000` inside the container; `supergraph.introspection: true`, see [introspection](#introspection-2026-10-20); `include_subgraph_errors: { all: true }`, so that the code `SERVICE_UNAVAILABLE` reaches the client; `traffic_shaping.all.timeout: 5s`, the time the router waits for one subgraph request, see [a dead adapter](#a-dead-adapter); `resolution` is nullable, see [a null resolution](#a-null-resolution); no account, key or graph reference).
- `compose_supergraph.py`: fetches each adapter's SDL (`{ _service { sdl } }`) and composes the four with Rover in a fixed, sorted order of the names.
- `rover/`: the Rover image (Rover 1.0.0 with the composition plugin `supergraph` v2.9.3 already inside).
- `supergraph.graphql`: the composed supergraph, a build product that is checked in (see below).
- `validation/`: the gate (`offline` and `stack` stages).
- `../../acceptance/`: the router-neutral acceptance suite (questions 2 to 6 and the controlled cases), the expected outcomes it compares with, derived from the released files, and the script that derives them ([README](../../acceptance/README.md)). The Cosmo router runs the same suite ([its README](../cosmo/README.md)) and the Hive router will.
- Ports (decided): the routers are in the block 8170 to 8179, **Apollo 8170**, Cosmo 8171, Hive 8172; the adapters of legacy services mirror the legacy last digit at 81xx (Personnel 8182, Missions 8183, Assets 8184); the mapping adapter is 8190; 8180 is kept free. Every start checks that its port is free.

## The two modes

- **Stub-backend mode (run and tested here).** The four adapters, the real Assets service with its PostgreSQL 17, the real Personnel v2 service and a stub of the Missions service that serves the released Missions dataset 1.2 (300 missions). No Oracle. The stub is not the Missions service.
- **Real-service mode (not run here).** The real Missions service on Oracle (about 9 GB, minutes to start), started as its own component, with the Missions adapter pointed at it through `MISSIONS_SERVICE_URL`. The acceptance tests are written against the released datasets and so should hold there, but that was **not tested**. Nothing in this folder starts the real Missions service.

## Run

```sh
APOLLO_ELV2_LICENSE=accept bash federation/stack/start.sh start
```

Docker only. `APOLLO_ELV2_LICENSE=accept` is your acceptance of the Elastic License 2.0 of Rover's composition plugin (see [the license](#the-license-of-the-composition-plugin)); without it the script refuses. The script composes the supergraph again, so if a schema changed, `git diff federation/routers/apollo/supergraph.graphql` shows what changed in the composition.

```sh
python -B federation/routers/apollo/validation/run_router_gate.py offline
APOLLO_ELV2_LICENSE=accept python -B federation/routers/apollo/validation/run_router_gate.py stack
```

## The supergraph

**The supergraph is a build product, checked in as evidence of the composition at a commit. It is never a source of truth: the sources are the adapters' schemas and `compose_supergraph.py`.** The lead developer decided on 2026-10-16 that it is committed if and only if a fixed build sequence gives a byte-identical output every time and a small real change of a schema gives a diff with no randomness. Both held on 2026-10-16 (below), so it is committed.

- **Freshness.** The `stack` gate composes the supergraph again from the running adapters and fails when `supergraph.graphql` differs from the result, naming the regeneration command. A stale committed supergraph would be a false story, so it cannot go stale unnoticed.
- **Routing URLs.** The `url` of every subgraph is its service name on the stack's network (for example `http://assets-adapter:8184/graphql`), the same in every mode and on every machine. Only the SDL is fetched through the host's ports, so the file does not change with the ports.
- **How to read it.** `enum join__Graph` lists the four subgraphs with their routing URLs. Each type carries one `@join__type(graph: X, key: ...)` per subgraph that defines it, and `resolvable: false` marks a subgraph that only names the type (the Missions stub of a reference). A field with `@join__field(graph: X, requires: ...)` is resolved by X and needs the named fields from others; `external: true` marks a field X needs and does not own. A type defined by one subgraph shows no `@join__field`. The story of a reference is in one place:

```graphql
type AssetReference
  @join__type(graph: ASSETS, key: "localRef release", resolvable: true)
  @join__type(graph: MAPPING, key: "localRef release", resolvable: true)
  @join__type(graph: MISSIONS, key: "localRef release", resolvable: false)
{
  asset: Asset @join__field(graph: ASSETS, requires: "assetId mappingOutcome")
  assetId: ID @join__field(graph: ASSETS, external: true) @join__field(graph: MAPPING)
  localRef: ID!
  mappingOutcome: MappingOutcome! @join__field(graph: ASSETS, external: true) @join__field(graph: MAPPING)
  release: String!
  resolution: Resolution @join__field(graph: ASSETS, requires: "assetId mappingOutcome")
}
```

  Missions names the reference and its key, the mapping subgraph supplies `assetId` and `mappingOutcome`, and Assets produces `resolution` and `asset` from them. `PersonnelReference` has the same shape with Personnel as the owner. `resolution` is nullable (`Resolution`, not `Resolution!`): see [a null resolution](#a-null-resolution).
- **A comment in a schema reaches the supergraph.** The descriptions and the `#` comments before a type or a field appear in the composed file, so editing a comment of a schema changes the supergraph. That is a real change of the input, not randomness.

### Is the composition reproducible? The evidence

Measured on 2026-10-16 with Rover 1.0.0, the composition plugin `supergraph` v2.9.3 and `federation_version: =2.9.3`, the Apollo router v2.18.0, in Docker Desktop on the lead developer's machine.

| Check | Result |
| --- | --- |
| Each adapter's `{ _service { sdl } }` fetched twice | Byte-identical for all four (sizes: assets 2876, mapping 2681, missions 5142, personnel 4053 bytes) |
| Compose twice from the same SDL files | Same SHA-256 |
| Compose from the SDL of the four restarted adapters | Same SDL bytes, same SHA-256 |
| Compose again by `start.sh` (another project, other host ports) | Same SHA-256 |
| The four subgraphs in reverse order (information only; the order is fixed and composition is not run in parallel today) | Same SHA-256 (the composed file lists types and fields in alphabetical order, so the order of the subgraphs does not show) |
| A small real change (one new nullable field `reviewNote: String` in the Missions SDL) | The diff has exactly one changed line, `+  reviewNote: String`; no reordering and no identifier changed |
| Result | `115653f65211e9f09d154b9e6f2339538a6ce23cd82a931f603eeae260cfb68f`, 13,452 bytes, LF only, `join` v0.3 |

What could have broken it, and what was done: the plugin or Rover drifting (both are pinned: `@apollo/rover@1.0.0` in the image and `federation_version: =2.9.3`; the image is built once and the plugin is stored in it, so composing runs with no network at all, `--network none`); the SDL being printed in another order (it is not: checked above); the order of the subgraphs (sorted in the script, and the reverse order gave the same file); line endings (the script writes LF only, the file is `text eol=lf` in `.gitattributes`); routing URLs differing by environment (they are the service names, the same in every mode). The ELv2 plugin is downloaded only when the Rover image is built; once the image exists nothing is fetched. The SHA-256 above is evidence for this date, not a pin: there is no committed hash of the file, because the file itself is committed and the freshness test compares it.

### The license of the composition plugin

Rover's composition plugin is under the Elastic License 2.0 and Rover asks for acceptance before it downloads or runs it. Nothing in this repository accepts it for you. The lead developer accepted it for this Job on 2026-10-16. To build the image or compose, you set `APOLLO_ELV2_LICENSE=accept` on purpose: the Dockerfile refuses to build, `compose_supergraph.py` and `start.sh` refuse to run, and the `stack` gate fails, without it. The plain Apollo router needs no account, key or graph reference; it runs with the supergraph file and `router.yaml` only.

## The acceptance tests

The expected outcomes were written first, in `federation/acceptance/expected-outcomes.json`, derived by `federation/acceptance/derive_expected.py` from the released Missions dataset 1.0, the mapping release 1.0 and the Assets dataset 1.1, never from a run. A test of the `offline` stage derives them again and fails if the file differs. The `stack` stage then compares what the router returns with that file.

The acceptance questions 2 to 6 and the controlled cases (the outage, the dead adapters) are the router-neutral suite `federation/acceptance/shared_suite.py`; the `stack` stage runs it against the Apollo router and keeps here only what is Apollo's own: the determinism and freshness of the composition (Part 2), the router settings it declares to the suite (the 5 s subgraph timeout and the `GATEWAY_TIMEOUT` code with `extensions.service` naming the subgraph, from `router.yaml`) and the router restart. The stage runs 35 tests since introspection was enabled (33 before; see [the large data](#the-large-data-2026-10-19) and [introspection](#introspection-2026-10-20)): 17 in Part 1 and 9 in Part 3 (the shared suite), 7 in Part 2 (Apollo's composition) and 2 in Part 4 (introspection); it ran 30 before the two controlled question 6 tests (test_14 and test_15 of Part 1) were added.

| Test | What it checks |
| --- | --- |
| Each subgraph answers | `mappingReleases`, `asset`, `personnel` and `mission` through the one endpoint |
| The missions list | the 31 missions of the dataset in the service order; `offset`/`limit` paging; the default limit 20 |
| Every reference | for every reference of every mission, `mappingOutcome`, `assetId`, `resolution` and `asset` equal the expected outcome (MAPPED or NO_ENTRY; RESOLVED, UNRESOLVED or UNMAPPED) |
| Question 2 | the missions that used a DESTROYED or MISSING asset: SH-53 (DESTROYED) and EQ-86 (MISSING) give ST-00000LD4W, LD52, LD53, LD5C and LD5I |
| Question 3 | the missions with an UNRESOLVED asset: EQ-97 gives ST-00000LD4U, LD53 and LD58; EQ-108 is UNMAPPED, not UNRESOLVED, and is not counted; no errors entry |
| Question 4 | the parent chain of EQ-64: AST-0004, AST-0023, AST-0029, in ONE query (`asset { assetId parent { assetId parent { assetId ... } } }`, `Asset.parent`) |
| Question 5 | the outage: the Assets service stopped, a mission answers with HTTP 200, `resolution` UNAVAILABLE and `asset` null for each mapped reference, UNMAPPED stays UNMAPPED, one `SERVICE_UNAVAILABLE` entry per failed call; the graph recovers when the service is back |
| Question 6 | three counts and one percentage over the mission's Starfleet personnel, the commanding officer (`commandingOfficer(release)`, null when the mission has none) and the assigned crew (CAPTAIN, COMMANDER, LIEUTENANT_COMMANDER, read from `CrewDetails`, are senior): the missions confirmed with a senior officer, confirmed without, and unconfirmed, and the percentage over the confirmed missions (with / (with + without), one decimal, half up; not a number when no mission is confirmed). Release 1.1 with everything up: 27 / 0 / 3 and 100.0 percent, with 1 cancelled mission not counted (a PLANNED mission is unconfirmed unless a confirmed senior is already assigned and a CANCELLED mission is left out of the population, the lead developer's final rules of 2026-10-18; the 3 unconfirmed are ST-00000LD4V, ST-00000LD57 and ST-00000LD5G, all PLANNED, and the cancelled one is ST-00000LD5D). The counts are made by the test over the query result; the graph has no aggregate field. The participants never count. The controlled case is ST-00000LD4Q, whose only person is its commanding officer C-85, a senior officer, who does not make it confirmed when unresolved: UNMAPPED in release 1.0 and null with the Personnel adapter stopped both give 0 / 0 / 30 and not a number, with 1 cancelled mission not counted (80 references not resolved, those of the counted missions; the PLANNED missions are unconfirmed too). Small controlled missions (a commanding officer who is the only senior, one that cannot be confirmed, a confirmed senior and an unconfirmed member is with, confirmed non-senior members and an unconfirmed member is unconfirmed, one case per kind of unconfirmed member, the PLANNED, CANCELLED and other-status cases) and the percentage cases (a tie goes up, the unconfirmed in neither side, none confirmed, the cancelled missions change nothing) run in the same suite without a stack |
| Crew references, release 1.0 | every crew reference (56 in the dataset) is `NO_ENTRY` and UNMAPPED, `personnel` and `personnelId` null, no errors entry |
| Crew references, release 1.1 | every crew reference (56) is MAPPED and RESOLVED against the Personnel v2 snapshot `personnel-v2-small-003`, with the name, rank, department and clearance of the snapshot (the whole-stack default); no errors entry |
| Releases | a blank release is `MAPPING_RELEASE_REQUIRED`; `2.0`, `latest` and `1` are `MAPPING_RELEASE_NOT_FOUND`; in both cases (assets and crew) the data says `mappingOutcome` and `resolution` RELEASE_REFUSED beside the errors entry; a request with no release is refused by GraphQL itself |
| Selections without `resolution` and `asset` | seven shapes (only the key, the id and the outcome, only the outcome, only `resolution`, only `asset`, ...): every reference is listed and equals the expected outcome; a reference is never hidden or guessed |
| Paging | a limit above 100 is `BAD_USER_INPUT` |
| Determinism | the table above, and the freshness of the committed supergraph |
| An adapter itself down | the Assets adapter stopped: HTTP 200 after 5 s, the mission KEPT (title, status, the crew, the other subgraphs' fields), each asset reference with `assetId` and `mappingOutcome` from the mapping, `resolution` null and `asset` null, and one `GATEWAY_TIMEOUT` entry per failed fetch naming the subgraph; the whole list of 31 missions keeps every mission; a root that another subgraph owns still answers. The same for the Personnel adapter stopped (crew references), and for both stopped. The mapping adapter stopped: a query of `localRef release` only still answers, and a query of `resolution` only gives `resolution` null with a `GATEWAY_TIMEOUT` entry naming `mapping` (the router needs the mapping for the `@requires` input) |

Question 1 (last seen) is not in the router Jobs: it needs more adapter work. Question 6 (senior officers) is answered and tested under Apollo on the live crew path (mapping release 1.1 against the Personnel v2 snapshot `personnel-v2-small-003`); it needed no new adapter code.

## The large data (2026-10-19)

The stack now serves the large data: Missions release 1.1 (300 missions), mapping release 1.2 and the Personnel v2 snapshot `personnel-v2-large-004`, and the expected outcomes were derived again from them before the suite ran. The `stack` stage runs 33 tests (32 before): Part 1 has 17 (the new `test_16` times a full page of 100 missions with assets, commanding officer and crew), Part 2 has 7 and Part 3 has 9. The whole-list checks page (offset 0, 100 and 200, limit 100) and the suite warms the stack before its first assertion. The tables below are the run of 2026-10-16 on the small data and stay as written.

Since 2026-10-20 the stack serves Missions dataset release 1.2 (its participants reclassified as P and O) and the acceptance suite asks mapping release 1.3. The expected outcomes were derived again first: only the release names and the input hashes changed, no outcome did, and the shared suite's assertions are unchanged except that the list of mapping releases now ends with 1.3. The `stack` stage still runs 33 tests and passes on the Apollo router.

| Fact of the run | Apollo |
| --- | --- |
| First pages of a cold stack, after the Personnel adapter reads its snapshot once | 3.11 s, 0.74 s, 0.49 s, no errors entry |
| The three full pages once warm (1,258, 750 and 965 references) | 0.86 s, 0.49 s, 0.49 s |
| The whole list of 300 missions, Assets adapter stopped | each page waits for the 5 s timeout (5.1 to 5.2 s), 596 `GATEWAY_TIMEOUT` entries, all 300 missions kept |
| Question 6, Personnel adapter stopped | each page 5.1 to 5.3 s, all 273 counted missions unconfirmed |
| A dead adapter in a list | a page that follows the first failures can get a connection refused at once: `SUBREQUEST_HTTP_ERROR`, declared for lists in `adapter_down_other_codes` |

Before the Personnel adapter cached its snapshot (the Job `personnel_adapter_cache`), the first full pages after a start took 5.1 to 5.6 s and carried timeout entries (490 to 936 on a page); that stopped this Job until the lead developer chose the cache and the warm-up.


## What the router did (Apollo router v2.18.0, one run on 2026-10-16)

These are facts of one run on stub data, for the compatibility matrix. They decide nothing.

| Question | Apollo router v2.18.0 |
| --- | --- |
| Composition of the four subgraphs with `@key`, `@requires` and `@external` only | Composed, no warning. The `Resolution` enum declared identically in the Assets and Personnel subgraphs composed as one enum, and so did `MappingOutcome` (declared in the mapping, Assets and Personnel subgraphs) |
| A `@requires` of two fields, one of them an enum owned by another subgraph (`@requires(fields: "assetId mappingOutcome")`) | Composed, no warning, and the router fetched both from the mapping subgraph and passed both to the owning adapter in the representation (2026-10-17, graph refinements Job; experiments 1 and 2 covered one field) |
| A Federation feature beyond those three forced by composition | No |
| Composition without the mapping subgraph's `PersonnelReference` | Fails: `EXTERNAL_MISSING_ON_BASE: Field "PersonnelReference.personnelId" is marked @external on all the subgraphs in which it is listed (subgraph "personnel")`. A field marked `@external` needs one subgraph that owns it |
| RESOLVED, UNRESOLVED, UNMAPPED as data, `asset` null when not resolved, no errors entry | Yes, for all 68 asset references of the 31 missions |
| The router calls the adapter when the `@requires` input is null (UNMAPPED) | Yes: the adapter answered UNMAPPED |
| Outage of a backend service | HTTP 200, partial data, each mapped reference UNAVAILABLE with `asset` null |
| The errors entry (with `include_subgraph_errors: all: true`) | One per failed call: `message` "Assets service unavailable", `path` such as `mission.assets.0.asset`, `extensions.code` `SERVICE_UNAVAILABLE`, plus `classification` "DataFetchingException" and `service` "assets" |
| How many entries | A mission with 2 mapped references: 2 entries. The whole list of 31 missions: 65 entries for 65 mapped references. The router does not merge identical calls, so one reference occurrence is one call |
| Time of the outage answer | About 3.3 s for the first mission, 1.0 s for the next, 0.11 s for the whole list (informal) |
| A refused release (blank, unknown) | HTTP 200. The errors list carries the code (`MAPPING_RELEASE_REQUIRED` or `MAPPING_RELEASE_NOT_FOUND`), once per reference, and the data says `mappingOutcome` RELEASE_REFUSED and `resolution` RELEASE_REFUSED for each reference (graph refinements Job). On 2026-10-16 the data showed UNMAPPED, because the mapping subgraph answered a null entity and the Assets adapter inferred UNMAPPED from the null id; the mapping now states the outcome and the owning adapters read it |
| A request with no release | HTTP 400, `GRAPHQL_VALIDATION_FAILED`, no data |
| A limit above 100 | HTTP 200, `data.missions` null, code `BAD_USER_INPUT` |
| An adapter itself down (the Assets adapter container stopped) | See [a dead adapter](#a-dead-adapter) |
| A query that selects only `localRef release assetId mappingOutcome` with the Assets adapter stopped | HTTP 200, complete, no errors entry: the router asked the mapping subgraph only, the owning adapter was not called |
| A query that selects only `resolution` with the mapping adapter stopped | `resolution` null and `GATEWAY_TIMEOUT` naming the mapping subgraph: the router fetches the `@requires` input from the mapping although the client did not select it |
| `Asset.parent` (an in-subgraph traversal, one call per level) | The chain AST-0004, AST-0023, AST-0029 in one query, 0.46 s; no federation feature beyond `@key` |

### A dead adapter

When an adapter itself is down (not its backend service) the router, with its default of 30 s, answered HTTP 504 `GATEWAY_TIMEOUT` with `data` null after 30.05 s. The question of the graph refinements Job was whether the router can return partial data and an error for the failed subgraph's fields; measured on 2026-10-17 with the Apollo router v2.18.0 (one run, informal times):

| Setting | Answer for the Assets adapter stopped |
| --- | --- |
| default (no `traffic_shaping`) | HTTP 504, `GATEWAY_TIMEOUT` "Your request has been timed out", `data` null, after 30.05 s |
| `traffic_shaping.all.timeout: 3s` and `5s` | HTTP 200 after 3.07 s and 5.07 s. One `GATEWAY_TIMEOUT` entry per failed fetch (`path` `mission.assets.0`, `extensions.service` "assets"), and `data.mission` null, because `resolution` is non-null (`Resolution!`) in the schema and the null climbs to the nearest nullable ancestor (`extensions.valueCompletion` says so). Roots that other subgraphs own still answer in the same response (`mappingReleases` did); the dead subgraph's own roots are null |

So, with `Resolution!`, Apollo did not return partial data for the fields of a dead subgraph: it nulled the nearest nullable ancestor, because the schema said those fields were non-null, and the router has no setting that changes that. Per the lead developer's rule (B if Apollo supports it cleanly, otherwise A), the setting is A: `traffic_shaping.all.timeout: 5s` in `router.yaml`, which turns the slow all-or-nothing 504 into a fast answer of HTTP 200 with per-fetch entries. 5 s is about four times the slowest normal answer measured (a query of all 31 missions with assets, parents and crew took 0.8 to 1.3 s). The measurement above is the one that led to the next decision: the lead developer decided on 2026-10-17 to make `resolution` nullable, see [a null resolution](#a-null-resolution), which is what keeps the rest of the mission. Cosmo has its own settings and is built ([its README](../cosmo/README.md#a-dead-adapter)); Hive is a later Job.

### A null resolution

`resolution` is nullable on `AssetReference` (Assets subgraph) and on `PersonnelReference` (Personnel subgraph); `asset` and `personnel` already were. The rule:

- **A null `resolution` means ONLY that the router could not ask the owning adapter** (the adapter is down, or the mapping subgraph that supplies its `@requires` input is). The errors list says why: a `GATEWAY_TIMEOUT` entry whose `extensions.service` names the subgraph.
- **Every other case is an explicit value, as data:** RESOLVED, UNRESOLVED, UNAVAILABLE (the adapter answered, its backend service did not), UNMAPPED, RELEASE_REFUSED. The adapters themselves never return a null `resolution`.
- **A client must check the errors list whenever `resolution` is null.** A null `resolution` with no errors entry is not a case this stack produces; a client that reads a null as "unresolved" or "unmapped" is wrong, because those have their own values.
- The price is the guarantee that `resolution` is always present, which the schema no longer gives; the gain is that a dead subgraph costs the fields it owns and not the mission (or the whole list of missions).

| Case (the router at 5 s, one run on 2026-10-17) | Answer |
| --- | --- |
| Assets adapter stopped | HTTP 200; mission, its crew and every other field kept; asset references with `assetId`, `mappingOutcome`, `resolution` null, `asset` null; one `GATEWAY_TIMEOUT` entry per failed fetch, `service` "assets" |
| Personnel adapter stopped | HTTP 200; mission and assets kept; crew references with `personnelId`, `mappingOutcome`, `resolution` null, `personnel` null; one `GATEWAY_TIMEOUT` entry per failed fetch, `service` "personnel" |
| Both stopped | both of the above in one answer; the entries name `assets` and `personnel` |
| The whole list of 31 missions, Assets adapter stopped | HTTP 200 after 5.1 s, all 31 missions kept, every asset reference with `resolution` null, 68 `GATEWAY_TIMEOUT` entries (one per asset reference) |
| Adapters stopped and started again | They may get new addresses and the router did not find them again by itself within 60 s (`SUBREQUEST_HTTP_ERROR`, `tcp connect error`, `resolution` null, one run): the router has to be restarted (`docker compose restart router`), as the gate does. A property of the stack and the router, not of the graph |
| The Assets service (backend) stopped, the adapter up | unchanged: UNAVAILABLE, never null, one `SERVICE_UNAVAILABLE` entry per failed call |
| Refused release | unchanged: RELEASE_REFUSED beside the `MAPPING_RELEASE_*` entry |

## Introspection (2026-10-20)

The Apollo router refuses GraphQL introspection unless it is told otherwise: with the default configuration every `__schema` or `__type` query was answered with the error code `INTROSPECTION_DISABLED` (measured on the running stack before the change). The Abstraction ladder study's Delta scenario discovers the schema through this router, so `router.yaml` now sets `supergraph.introspection: true`, the router's own setting; the supergraph and the subgraphs are unchanged. Production deployments usually keep it off.

| Fact | Value |
| --- | --- |
| Default of the pinned router (v2.18.0) | off (`INTROSPECTION_DISABLED`) |
| Setting used | `router.yaml`: `supergraph.introspection: true` |
| Tested by | the `offline` stage (the exact lines of `router.yaml`) and Part 4 of the `stack` stage (a `__schema` query and a `__type` query through the router) |

Fairness between the GraphQL scenarios: the four adapters answer introspection on their own endpoints (Part 4 asks each of them), so a scenario that goes to the adapters directly and a scenario that goes through either router can discover the schema the same way. Their federation plumbing (`_service`, `_entities`) is a separate matter and is not changed here.

## Findings and open items

- **The mapping subgraph and the Missions subgraph changed in the router Job.** Composition with the Personnel subgraph fails unless some subgraph owns `PersonnelReference.personnelId`, so the mapping adapter gained a `PersonnelReference` type, and the Missions adapter gained `Mission.crew(release)`, one stub per entry of `assignedCrewIds` (not the commanding officer, not the participants). Both are additive.
- **The graph refinements Job (2026-10-17)** made the mapping outcome explicit (`mappingOutcome`, one enum `MappingOutcome` for both kinds of reference, and the fifth `Resolution` value RELEASE_REFUSED), renamed the mapping's external asset id from `astId` to `assetId`, removed the redundant `id` field of `AssetReference` and `PersonnelReference`, added `Asset.parent` (question 4 in one query), set the subgraph timeout, tested the selections without `resolution` and `asset`, and moved the whole-stack Personnel snapshot to `personnel-v2-small-003` with the crew references asked in release 1.1.
- **`Asset.parent` has no caching and no batching**, by decision: each level is one call and a long chain is one call per level. A parent id that does not exist gives null with no errors entry. Caching is for later, when the need becomes apparent.
- **Not tested:** the real Missions service on Oracle (the lead developer's own run, later); a `@requires` set with an argument; entity interfaces; the Hive Console; Hive (a later Job; Cosmo is built, see [its README](../cosmo/README.md)); field-level authorization and other features that need a GraphOS licence. No repeat measurement and no benchmark was made; every time above is informal.

## Versions and digests (resolved 2026-10-16)

| Part | Version | Digest or source |
| --- | --- | --- |
| Apollo router | v2.18.0, the newest release that is not a preview (`v2.19.0-rc.0` and `v3.0.0-preview.0` exist) | `ghcr.io/apollographql/router@sha256:5b02af03e8f0268b8fcf85132c9e54ea36a1029b0823b00bb9151f698a991215` |
| Rover | 1.0.0 (the newest on npm) | `@apollo/rover@1.0.0` |
| Composition plugin | `supergraph` v2.9.3, `federation_version: =2.9.3` | downloaded by Rover when the image is built |
| Rover image base | `node:22-slim` | `sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` |
| CA bundle source | `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |
| Missions stub | `python:3.13-slim-bookworm` | `sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641` |
| Assets database | `postgres:17-bookworm` | `sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826` |

The adapters and the two real services keep their own pinned bases (see their READMEs). Tags move: resolve the digests again before changing a pin, and record the date. The Rover image `starfleet-federation-rover:1.0.0-supergraph-2.9.3` is a build tool shared by every run; the gate does not remove it. `node:22-slim` has no CA certificates, so the bundle is copied from the Temurin image (as in experiment 1) instead of installing a package.

## Informal timings

On a warm Docker cache the gate's `stack` stage took 296 s in total: 92.6 s to build and start the backends and adapters, 3.6 s for the first composition. One machine, one run, no quiet-machine protocol; they are not a benchmark.
