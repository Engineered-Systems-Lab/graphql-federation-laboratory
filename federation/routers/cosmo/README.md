# Federation Cosmo router

The Cosmo router of the federation layer, the composition of the four subgraphs into one execution config with `wgc`, and the same end-to-end acceptance suite that the Apollo router passes. One GraphQL endpoint, `http://127.0.0.1:8171/graphql`, answers across Missions, the mapping, Assets and Personnel. The subgraphs are the ones the Apollo router uses, unchanged: the platform-neutral rule says a difference is the router's. The design is [the federation design](../../../docs/FEDERATION-DESIGN.md); the Apollo twin of this folder is [the Apollo router README](../apollo/README.md); the whole-stack compose file, its start script and the stub of the Missions service are in [federation/stack](../../stack/README.md).

## Layout and ports

- `config.yaml`: the router configuration (listen `0.0.0.0:4000` inside the container; `introspection.enabled: true`, see [introspection](#introspection-2026-10-20); `subgraph_error_propagation.mode: pass-through`, so that `extensions.code` reaches the client; `traffic_shaping.all.request_timeout: 5s`, the time the router waits for one subgraph request, the same as the Apollo router's, and `retry.enabled: false`, see [a dead adapter](#a-dead-adapter); no account, token, control plane or CDN).
- `compose_execution_config.py`: fetches each adapter's SDL (`{ _service { sdl } }`) and composes the four with `wgc router compose` in a fixed, sorted order of the names.
- `wgc/`: the image of the composition tool (`wgc` 0.133.0 in `node:22-slim`).
- `execution-config.json`: the composed execution config, a build product that is checked in (see below).
- `validation/`: the gate (`offline` and `stack` stages).
- `../../acceptance/`: the router-neutral acceptance suite that this gate runs, the SAME `shared_suite.py` as the Apollo gate ([README](../../acceptance/README.md)).
- Port: **Cosmo 8171** (the routers are in the block 8170 to 8179: Apollo 8170, Cosmo 8171, Hive 8172). One router runs at a time; both share the four adapters.

## Run

```sh
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh start
```

Docker only. No license acceptance, account or token is needed: `wgc` is Apache-2.0 and the router is started with a static execution config. The script composes the execution config again, so if a schema changed, `git diff federation/routers/cosmo/execution-config.json` shows what changed. The Cosmo router is a service of the whole-stack compose file under the profile `cosmo`; without the profile the file is the Apollo stack exactly as before.

```sh
python -B federation/routers/cosmo/validation/run_router_gate.py offline
python -B federation/routers/cosmo/validation/run_router_gate.py stack
```

## What was chosen, and why

The lead developer decided these points on 2026-10-18 (the Job record `federation_second_router` holds their words); each is built as written.

- **Self-hosted router with local composition, no Cosmo Cloud.** "Yes, let's compare apples to apples, for this round :)": Rover composes locally without GraphOS, and `wgc router compose` composes locally without the control plane, so the comparison is router against router. With no graph token, five Cosmo Cloud features stay off, and the router logs "No graph token provided" naming them: Schema Usage Tracking, Persistent operations, Advanced Request Tracing, Cosmo Cloud Tracing and Cosmo Cloud Metrics. The warning is expected. "For this round": a later round may compare the managed pieces; that is not decided.
- **The newest versions at build time, pinned by digest.** Router 0.359.0 (released 2026-10-15) and `wgc` 0.133.0 (2026-10-14) are the newest releases on 2026-10-18; no pre-release was taken.
- **The execution config is committed only because it is byte-reproducible**, with a freshness test: the same rule as Apollo's supergraph.
- **Error passthrough:** `subgraph_error_propagation: { mode: pass-through }` is the smallest setting found that delivers the decided errors entry for a failed backend call (see the settings below).
- **The same 5 s subgraph timeout as Apollo** (`request_timeout: 5s`), then a check whether Cosmo nulls only the dead subgraph's fields with the nullable `resolution`: it does.
- **The same whole-stack compose with a router switch**, one router at a time.
- **Licence re-checked at the pinned version's source:** see [the licence](#the-licence-and-the-telemetry).
- **Telemetry:** the router's anonymous usage tracking is turned off with `COSMO_TELEMETRY_DISABLED=true`, verified in the source (below). The Apollo router also runs with anonymous telemetry off in the stack (`APOLLO_TELEMETRY_DISABLED: "true"` in `federation/stack/compose.yaml`), so the two routers are aligned; the run manifest must record it.

## The execution config

**The execution config is a build product, checked in as evidence of the composition at a commit. It is never a source of truth: the sources are the adapters' schemas and `compose_execution_config.py`.** Cosmo's composition does not print a supergraph schema; `wgc router compose` prints a router execution config (JSON). It holds, per subgraph, the root and child nodes, the entity keys and the `@requires` sets, the client schema (`graphqlSchema`) and each subgraph's SDL, and a version that is the all-zero UUID, with no timestamp. The script writes wgc's JSON again with two-space indentation, wgc's key order, LF and one final newline, and changes nothing else; wgc writes one 52 KB line, which would make every diff unreadable.

- **Freshness.** The `stack` gate composes the execution config again from the running adapters and fails when `execution-config.json` differs from the result, naming the regeneration command.
- **Routing URLs.** The `url` of every subgraph is its service name on the stack's network, the same in every mode.
- **A small real change** (one new nullable field `reviewNote: String` in the Missions SDL) gives 9 changed lines in the diff: the field list of the type, the subgraph's `serviceSdl`, the client schema, the string-storage entry, and two content keys, which are 40-hex hashes of the stored SDL. Nothing is reordered and nothing is random. Unlike the Apollo diff (one line) it is not one line, because the execution config quotes the SDL in four places.
- **No composition tool disagreement on the lab's schemas.** Cosmo's own composition code (wgc 0.133.0) and Rover's (composition plugin 2.9.3) agree: the offline gate compares the client schema in the execution config with the Apollo supergraph and finds the same types, fields with their arguments and nullability, enum values and union members. The two-field `@requires` with an enum from another subgraph composed with no warning, for `AssetReference` (`assetId mappingOutcome`) and `PersonnelReference` (`mappingOutcome personnelId`).
- **wgc needed one setting to compose offline:** it asks the npm registry for a newer version before every command and fails with `--network none` (`Failed to check for updates`); `DISABLE_UPDATE_CHECK=true` in the image switches that off. That is the only thing wgc needed from the network.

## The acceptance tests

The acceptance questions 2 to 6 and the controlled cases are the router-neutral suite `federation/acceptance/shared_suite.py`; the `stack` stage runs it against the Cosmo router and keeps here only what is Cosmo's own: the determinism and freshness of the composition (Part 2), the settings it declares to the suite and one recovery check (Part 4). The stage runs 36 tests since introspection was written into the configuration (34 before; see [the large data](#the-large-data-2026-10-19) and [introspection](#introspection-2026-10-20)): 17 in Part 1 and 9 in Part 3 (the shared suite, the same test ids as the Apollo gate), 7 in Part 2 (the composition), 1 in Part 4 and 2 in Part 5 (introspection).

**Part 1 passed against Cosmo with no change to any shared assertion.** The settings object had three declared settings, all exercised only by Apollo. Cosmo showed they were not enough for the controlled cases of Part 3, and two more were added, both declared and neither weakening an assertion. The Apollo values are the defaults, so the Apollo gate declares the same three settings and runs the same assertions:

| Setting | Apollo | Cosmo |
| --- | --- | --- |
| `adapter_down_code`: the `extensions.code` of the entry for a fetch of a dead adapter | `GATEWAY_TIMEOUT` | none: the router writes the entry itself and gives it no `extensions` at all |
| `subgraph_key`: the `extensions` key that names the subgraph | `service` | none |
| `adapter_down_seconds`: the window of the answer, proving the subgraph timeout is in force | 4.5 s to 15 s | 4.5 s to 15 s |
| `subgraph_in_message` (new): where else the entry names the subgraph | none | the message, "Failed to fetch from Subgraph 'assets' at Path 'mission.assets'.": the pattern `Subgraph '([^']+)'` |
| `entries_per` (new): how many entries a failed fetch gives | `reference`: one per reference whose owning subgraph could not be asked (a mission with 2 asset references gives 2) | `subgraph_fetch`: one per failed fetch of a subgraph, the router sending the references of one list in one request (the same mission gives 1) |

The assertions that read these (the code set, the subgraph naming, the number of entries) go through helper methods of the suite's `Router` class; the new `Router.expected_entries` and the message pattern are the whole change. A failed backend call (the Assets service stopped, the adapter up) is different: the adapter writes that error, and with pass-through its code reaches the client, so the same assertions hold for both routers with no declared difference.

## The large data (2026-10-19)

The stack now serves the large data: Missions release 1.1 (300 missions), mapping release 1.2 and the Personnel v2 snapshot `personnel-v2-large-004`, and the expected outcomes were derived again from them before the suite ran. The `stack` stage runs 34 tests (33 before): Part 1 has 17 (the new `test_16` times a full page of 100 missions with assets, commanding officer and crew), Part 2 has 7, Part 3 has 9 and Part 4 has 1. The whole-list checks page (offset 0, 100 and 200, limit 100) and the suite warms the stack before its first assertion. The tables below are the run of 2026-10-18 on the small data and stay as written.

Since 2026-10-20 the stack serves Missions dataset release 1.2 (its participants reclassified as P and O) and the acceptance suite asks mapping release 1.3. The expected outcomes were derived again first: only the release names and the input hashes changed, no outcome did, and the shared suite's assertions are unchanged except that the list of mapping releases now ends with 1.3. The `stack` stage still runs 34 tests and passes on the Cosmo router.

| Fact of the run | Cosmo |
| --- | --- |
| First pages of a cold stack, after the Personnel adapter reads its snapshot once | 1.96 s, 0.64 s, 0.62 s, no errors entry |
| The three full pages once warm (1,258, 750 and 965 references) | 0.49 s, 0.45 s, 0.63 s |
| The whole list of 300 missions, Assets adapter stopped | pages of 5.05 s, 3.0 s and 5.05 s, 3 entries (one per page), all 300 missions kept |
| Question 6, Personnel adapter stopped | pages of 5.25 s, 3.0 s and 5.1 s, all 273 counted missions unconfirmed |

Before the Personnel adapter cached its snapshot (the Job `personnel_adapter_cache`), the first full pages after a start took 5.1 to 5.6 s and carried timeout entries (two on a page); that stopped this Job until the lead developer chose the cache and the warm-up.


## What the router did (Cosmo router 0.359.0, one run on 2026-10-18)

These are facts of one run on stub data, for the compatibility matrix. They decide nothing.

| Question | Cosmo router 0.359.0 |
| --- | --- |
| Composition of the four subgraphs with `@key`, `@requires` and `@external` only | Composed by `wgc router compose` 0.133.0 offline, no warning; the output is an execution config (59,540 bytes as committed), and its client schema equals Rover's on the lab schemas (types, fields with arguments and nullability, enum values, union members). The `Resolution` and `MappingOutcome` enums declared identically in several subgraphs composed as one enum each |
| A `@requires` of two fields, one of them an enum owned by another subgraph (`@requires(fields: "assetId mappingOutcome")`) | Composed, no warning; the execution config holds the set `assetId mappingOutcome` for `AssetReference.asset` and `.resolution`, and `mappingOutcome personnelId` for `PersonnelReference.personnel` and `.resolution`; the router fetched both from the mapping subgraph and passed both to the owning adapter (every reference of every mission equals the expected outcome) |
| A Federation feature beyond those three forced by composition | No: the datasources of the execution config hold keys and requires only |
| Does the output depend on the order of the subgraphs? | Yes. The four subgraphs in reverse order gave a different execution config (a diff of 635 lines, information only; the order is fixed to the sorted names). Rover's output did not depend on the order |
| RESOLVED, UNRESOLVED, UNMAPPED as data, `asset` null when not resolved, no errors entry | Yes, for all 68 asset references of the 31 missions and the 56 crew references of release 1.1 (and the 56 of release 1.0, NO_ENTRY) |
| The router calls the adapter when the `@requires` input is null (UNMAPPED) | Yes: the adapter answered UNMAPPED |
| Outage of a backend service (the Assets service stopped) | HTTP 200, partial data, each mapped reference UNAVAILABLE with `asset` null |
| The errors entry, default configuration (wrapped mode) | One entry per failed fetch, message "Failed to fetch from Subgraph 'assets' at Path 'mission.assets'.", the subgraph's own errors one level down in `extensions.errors` (with their code), `extensions.serviceName`; no code at the top level (measured again on 2026-10-18) |
| The errors entry with `subgraph_error_propagation.mode: pass-through` | The subgraph's own entry: `message` "Assets service unavailable", `path` such as `mission.assets.resolution` (no list index, and the path ends at the field that carried the error, not at the reference), `extensions.code` SERVICE_UNAVAILABLE and `extensions.serviceName` "assets"; no `classification`. `allow_all_extension_fields: true` adds `classification` and is not needed for the code |
| How many entries | A mission with 2 mapped references: 2 entries. The whole list of 31 missions: 8 entries for 65 mapped references (Apollo: 65): the entries follow the calls the router groups, not the references |
| A refused release (blank, unknown) | HTTP 200. The code (`MAPPING_RELEASE_REQUIRED` or `MAPPING_RELEASE_NOT_FOUND`) in the errors list and RELEASE_REFUSED in the data, as under Apollo |
| A request with no release | HTTP 200 with an errors entry that has no `extensions.code`, and no data (Apollo: HTTP 400, `GRAPHQL_VALIDATION_FAILED`) |
| A limit above 100 | HTTP 200, `data.missions` null, code `BAD_USER_INPUT`, as under Apollo |
| An adapter itself down (the Assets adapter container stopped) | See [a dead adapter](#a-dead-adapter): HTTP 200 after 5.1 s with the owning subgraph's fields null and the rest kept |
| A query that selects only `localRef release assetId mappingOutcome` with the Assets adapter stopped | HTTP 200, complete, no errors entry (0.04 s): the owning adapter was not called |
| A query that selects only `resolution` with the mapping adapter stopped | `resolution` null and an entry naming the mapping subgraph (5.06 s): the router fetches the `@requires` input from the mapping although the client did not select it, as under Apollo |
| `Asset.parent` (an in-subgraph traversal, one call per level) | The chain AST-0004, AST-0023, AST-0029 in one query; no federation feature beyond `@key` |
| Question 6 (three counts and one percentage) | Release 1.1 with everything up: 27 / 0 / 3 and 100.0 percent, 1 cancelled mission not counted; release 1.0 and with the Personnel adapter stopped: 0 / 0 / 30, no percentage, 1 cancelled mission not counted; the controlled missions and percentage cases pass. The Missions subgraph's `commandingOfficer(release)` composes and is served |

### A dead adapter

When an adapter itself is down (not its backend service) the Cosmo router, with `request_timeout: 5s` and `retry.enabled: false`, answered HTTP 200 after 5.1 s with the mission and every other field kept, the owning subgraph's fields null and one entry per failed fetch. The shared suite's cases, all passing:

| Case (the router at 5 s, no retry) | Answer |
| --- | --- |
| Assets adapter stopped | HTTP 200; mission, its crew and every other field kept; asset references with `assetId`, `mappingOutcome`, `resolution` null, `asset` null; one entry for the fetch, naming `assets` in its message |
| Personnel adapter stopped | the same for the crew references; the entry names `personnel` |
| Both stopped | both of the above in one answer |
| The whole list of 31 missions, Assets adapter stopped | HTTP 200, all 31 missions kept, every asset reference with `resolution` null |
| The mapping adapter stopped | a query of `localRef release` only still answers with no entry; a query of `resolution` only gives `resolution` null and an entry naming `mapping` (the router needs the mapping for the `@requires` input), as under Apollo |
| The Assets service (backend) stopped, the adapter up | unchanged: UNAVAILABLE, never null, one `SERVICE_UNAVAILABLE` entry per failed call, with the code at the top level and `extensions.serviceName` |

- **The nullable field is what keeps the rest of the object, under Cosmo too.** The first run, before any setting, already showed it: only `resolution` and `asset` were null.
- **Retry.** Cosmo retries a failed subgraph request by default (5 attempts, 3 s interval, a random wait up to 10 s). With the default retry and `request_timeout: 5s` the answer for the stopped Assets adapter took 5.1 s in one run and 21.0 s in the next (two requests, informal). The Apollo router answered in 5.07 s in the measured runs, so retry is switched off in `config.yaml` to keep the two timeouts equivalent. This is one more setting than the decision named; the lead developer decided on 2026-10-18 to keep it off for the comparison. Cosmo supports subgraph retries, on by default (5 attempts, 3 s interval, a random wait of up to 10 s), a production-resilience feature in Cosmo's favour; the pinned Apollo router v2.18.0 has no subgraph-request retry setting. Which failures Cosmo retries is not verified.
- **The execution config carries its own 10 s per subgraph** (`requestTimeoutSeconds`); the router's `request_timeout` wins, and the router's own default without the setting is not in force (the suite's window of 4.5 s to 15 s proves the 5 s is).
- **Adapters stopped and started again.** Unlike the Apollo router, the Cosmo router found a restarted adapter again by itself: after the Assets adapter was stopped and started again, the router (not restarted) answered with no errors 16.4 s after the adapter answered GraphQL again in the gate (about 11 s in a hand run before it), with the retry switched off; Part 4 of the gate asserts recovery within 90 s. The Apollo router needed a restart for this ([the Apollo README](../apollo/README.md#a-null-resolution)). The shared suite still restarts the router before its last check, which runs two seconds after the last restore.
- **Validation errors are HTTP 200 under Cosmo** (a query that omits a required argument gave an errors entry with no `extensions.code`; Apollo gives HTTP 400 `GRAPHQL_VALIDATION_FAILED`); the suite accepts 200 or 400 for that case by design. Cosmo has an `apollo_compatibility_flags` group (for example `use_graphql_validation_failed_status`) that changes such behaviors toward Apollo's; none is used here.

## Findings and open items

- **A router-generated error carries no `extensions` at all under Cosmo.** For a dead adapter the client cannot filter on a code; it can read the subgraph's name only from the message. No setting in this folder gives it a code.
- **Paths of the entries carry no list index** (`mission.assets.resolution`, Apollo: `mission.assets.0.asset`) and no `classification`; `extensions.serviceName` names the subgraph for a subgraph error. This was already seen in federation experiment 2.
- **Not tested:** the real Missions service on Oracle (the lead developer's own run, later); a `@requires` set with an argument and entity interfaces (the graph uses neither); the Cosmo Cloud pieces (a later round, if the lead developer wants it); field-level authorization and other features that need the Cosmo Cloud or its enterprise terms; Hive. No repeat measurement and no benchmark was made; every time above is informal.
- **Telemetry:** the router and wgc are told not to collect usage data. The router still enables a Prometheus endpoint on `127.0.0.1:8088` inside the container (its default; nothing publishes it).

## Introspection (2026-10-20)

The pinned router (0.359.0) has introspection on by default: its start log says `introspection` is true and a `__schema` query answers with no setting at all (measured on 2026-10-20 in a throwaway container with the then-committed configuration). The Apollo router's default is the opposite (off). The Abstraction ladder study's Epsilon scenario discovers the schema through this router, so `config.yaml` now says `introspection.enabled: true` explicitly (the lead developer decided on 2026-10-20 to set it explicitly rather than rely on the default): the setting has a name and a value that the study manifest can record, and a version change that flips the default cannot switch it off. Production deployments usually keep it off.

| Fact | Value |
| --- | --- |
| Default of the pinned router (0.359.0) | on |
| Setting used | `config.yaml`: `introspection.enabled: true` |
| Tested by | the `offline` stage (the exact lines of `config.yaml`) and Part 5 of the `stack` stage (a `__schema` query and a `__type` query through the router, and a `__schema` query to each of the four adapters) |

## The licence and the telemetry

- **Licence, re-checked at the pinned versions' own source (not legal advice).** At the tag `router@0.359.0` of the `wundergraph/cosmo` repository the root `LICENSE` is the Apache License 2.0 (SHA-256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`, 201 lines), the README says "all under the Apache 2.0 license", the image carries the label `org.opencontainers.image.licenses=Apache-2.0`, the tree has no `ee` folder and no other licence file apart from a test helper's, and `cli/package.json` at `wgc@0.133.0` says `Apache-2.0` (the same LICENSE bytes). The 2026-10-16 reading was of the main branch, and one third-party page had claimed ELv2; the pinned source shows Apache-2.0. The router image runs as root (`User: 0`) and exposes 3002, which the config overrides to 4000.
- **Telemetry.** The anonymous usage tracking of the router is disabled when `COSMO_TELEMETRY_DISABLED` is `true` or `DO_NOT_TRACK` is `1` (`router/core/router.go` at `router@0.359.0`, function `configureUsageTracking`); wgc reads the same two names in `cli/src/core/telemetry.ts` at `wgc@0.133.0`. The compose file sets the first for the router and the wgc image sets it for wgc. The guess of federation experiment 2 was right. The setting used is recorded here so that both routers can be made alike before test runs.

## Versions and digests (resolved 2026-10-18)

| Part | Version | Digest or source |
| --- | --- | --- |
| Cosmo router | 0.359.0, the newest release (released 2026-10-15) | `ghcr.io/wundergraph/cosmo/router@sha256:a125c80b7c759837901a080bb9f64518eb5826a979f7b2f512661cacf1caff6d` (the OCI image index; the image is 145 MB, amd64 and arm64) |
| Cosmo CLI | `wgc` 0.133.0, the newest on npm | `wgc@0.133.0` in the image `starfleet-federation-wgc:0.133.0` |
| wgc image base | `node:22-slim` | `sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` (the Rover image's base) |

Tags move: resolve the digests again before changing a pin, and record the date. The wgc image is a build tool shared by every run; the gate does not remove it.

## Informal timings

On a warm Docker cache the gate's `stack` stage took 546 s in total: 66.2 s to build and start the backends and adapters and 12.6 s for the first composition (the wgc image already built; building it the first time took 93 s). The `offline` stage ran 40 tests in 43.7 s. One machine, one run, no quiet-machine protocol; they are not a benchmark. Docker Desktop on the lead developer's machine.
