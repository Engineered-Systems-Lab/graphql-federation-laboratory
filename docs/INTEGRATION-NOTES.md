# Cross-platform integration lessons

## Unicode length validation

The frozen XSD retains `maxLength=100`, measured in XML characters. Windows PowerShell/.NET validation rejects 100 supplementary characters (U+1F680) as 200 UTF-16 code units. The offline suite reports this known limitation; the .NET path is not fixed. Java 17 enables `com.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength=true` and regression-tests 100 supplementary characters accepted / 101 rejected. Validator behavior must be checked across platforms without weakening the contract.

## Immutable dataset identity and checkout line endings

Git HEAD stores the canonical datasets with LF. At the portability review, Windows dataset 001 had 61 CRLF endings; 002 had 113 CRLF endings and one bare LF. Both working copies normalize exactly to their Git HEAD content. Raw-byte SHA-256 made Java startup depend on checkout line endings, so a successful Windows-tree build alone did not establish LF-checkout portability.

The Java loader now hashes the original bytes while skipping only a CR byte immediately followed by LF. All other bytes, including standalone CR, remain significant. This is CRLF-to-LF normalization for hashing only: the original bytes are passed unchanged to XML parsing, followed by the existing version/schema/readiness checks before publication. There is no trimming, Unicode normalization, XML canonicalization, or dataset-file rewrite. Actual content changes still fail with `Immutable dataset hash mismatch`.

Full SHA-256 values were computed directly from Git HEAD blob bytes before editing the loader, and verified against normalized working-copy bytes:

| Dataset | Canonical LF SHA-256 |
| --- | --- |
| crew-v1-small-001 | `daeebe24706e3345d3f14c320a8fb9eb866fcfea7ce2dc8f01ce1977bbc0a35e` |
| crew-v1-small-002 | `6cf7e7ec590fa247aa8f884916a4014ce86aa27276c7bcbe409abd65465da8b9` |

The shared startup loader path is tested with current working-copy bytes, LF, CRLF and synthesized mixed endings, including 002's 113 CRLF / one LF case on any checkout. Tests also reject changed text, added whitespace, standalone CR replacing LF, and trailing CR, and verify that hashing does not mutate the input array.

The unchanged offline manifest validator still checks historical working-copy **raw-byte hashes**. It retains its own checkout portability limitation; this Java fix does not update that validator or the manifest. These are cross-platform development/integration issues, with no change to immutable dataset semantics or the frozen SOAP contract.

See the [Java validation report](CREW-PERSONNEL-JAVA-V1-VALIDATION.md) for executed checks.

## UTF-8 Markdown and previously misdecoded text

The D016 heading contained the three code points U+00E2 U+20AC U+201D in place of a dash. The file decoded as valid UTF-8: this was stored mojibake, not invalid UTF-8 or merely a display issue. Those characters are consistent with UTF-8 em-dash bytes having been decoded as Windows-1252 and then saved as UTF-8; repository evidence does not identify the responsible editor or command. The confirmed heading was repaired to an ASCII hyphen. A documentation/source scan found no other such candidates. Intentional Unicode, especially boundary fixtures/tests, was preserved. ASCII punctuation is practical for technical headings, not an anti-Unicode rule.

## Text policy follow-up

No repository `.editorconfig` or `.gitattributes` existed at this review. Effective `core.autocrlf=true`; representative contract/dataset attribute checks reported no explicit attributes. Git blobs use LF while the working copies include CRLF and mixed endings. UTF-8, LF in Git and final newlines for normal text are the desired direction. No blanket policy or normalization was introduced: fixture bytes include deliberate boundary/negative cases, and the offline manifest still hashes working-copy bytes. A separate controlled policy change should first classify fixtures, agree on exceptions, and reconcile offline hash portability before any renormalization. Do not run mass normalization as part of this mission.

Later context (2026-10-12): the offline hash portability above is reconciled for the two canonical datasets only. A fresh worktree on Git for Windows checks the files out with CRLF, and the manifest's raw-byte pins describe the original working copies (001 all CRLF, 002 CRLF with one bare LF), which no checkout can reproduce from the LF blobs, so the offline check failed for every new worktree while it passed in a checkout made earlier. `validate_structure.py` now hashes the two datasets with each CR that precedes an LF skipped, like the Java loader, and compares them with the canonical LF digests in the table above. Nothing else changed: no `.gitattributes` rule, no renormalization, no fixture or manifest edit, and the raw pins stay in the manifest as the historical record. Every other fixture, the contracts and the deliberate boundary and negative cases keep their bytes and classification, so the broader text policy (classify fixtures, agree exceptions) remains open.

## Offline validator portability (2026-10-01)

The active offline validator now uses Python/lxml against the unchanged XSD and checks 100 supplementary characters accepted and 101 rejected. The earlier .NET limitation above records the former validator; it no longer applies to the active offline entry point. Historical execution reports retain their original results.

## Stage A benchmark design

Status: Design direction / open experiment planning (2026-10-06). This section records proposed cross-platform measurement design, not executed interoperability findings, governance, acceptance thresholds or implementation authority. [Plan](PLAN.md#benchmark-protocol) owns the roadmap and Alpha/Beta/Gamma/Delta/Epsilon treatments (the letters in ladder order since 2026-10-20: Alpha raw legacy, Beta raw plus a guide, Gamma adapters only, Delta adapters plus Apollo, Epsilon adapters plus Cosmo; the text below that says Gamma/Delta for the two routers was written under the earlier letters and is read as Delta/Epsilon, and the registry column is updated); D006 and D011 retain the execution ordering and separation of agent outcomes from router performance. No harness, API access, dataset expansion, synthetic subgraph, Missions contract or Mission Control change is part of this design record.

### Hypothesis sources and independence

Prefer benchmark dimensions derived from a vendor's stated value proposition when it makes a concrete measurable claim. Add lab-derived metrics where those claims leave important gaps. Vendor claims define hypotheses; this lab is the independent evaluator. These are design guidelines, not immutable rules or a definition of victory.

Keep provenance, evidence type, baseline and intervention context alongside each claim: vendor marketing and vendor-published customer evidence are not independent validation. Do not seek independent external assessments at this stage. Later triangulation may be useful if our measurements materially diverge from vendor claims or ambiguity remains; our own evidence comes first.

### Vendor-claim metric registry

The five vendor-owned pages below were checked directly on 2026-10-06. Values are attributed claims, not lab results, universal expectations or Stage A pass/fail targets. Measured results and replication status may be added later with run evidence; none exists here yet. Source IDs link to exact titles/URLs and context below.

| Metric | Category | Vendor | Supported claim | Claim evidence type | Source | Stage A applicability / likely comparison |
| --- | --- | --- | --- | --- | --- | --- |
| Throughput | Router/runtime | Apollo | RS Group: 5x increase | Named customer case study | [A](#vendor-sources-and-context) | Delta/Epsilon under equivalent offered load; customer migration baseline is different |
| P95 latency | Router/runtime | Apollo | RS Group: 24% decrease | Named customer case study | [A](#vendor-sources-and-context) | Delta/Epsilon; isolate cache and downstream behavior |
| Query planning time | Planner/runtime | Apollo | Router 2.0: 10x faster, median improvement | Vendor-reported customer-base/testing results | [B](#vendor-sources-and-context) | Delta/Epsilon planner hypothesis; version-upgrade replication would need a separate Apollo baseline |
| Execution time | Router/runtime | Apollo | Router 2.0: 1.9x faster | Vendor-reported customer-base/testing results | [B](#vendor-sources-and-context) | Delta/Epsilon; separate planning from execution |
| CPU consumption | Resource/runtime | Apollo | Router 2.0: 5.5x lower | Vendor-reported customer-base/testing results | [B](#vendor-sources-and-context) | Delta/Epsilon at matched load and resource limits |
| Heap consumption | Resource/runtime | Apollo | Router 2.0: 2.7x lower | Vendor-reported customer-base/testing results | [B](#vendor-sources-and-context) | Delta/Epsilon where heap accounting is comparable; do not equate heap with total memory |
| Data-source/functionality rollout | Developer productivity | Apollo | AlphaSense estimate: 20-40% faster, feature-dependent | Named customer estimate/case study | [C](#vendor-sources-and-context) | Equivalent implementation/change tasks; lab proxy for team delivery, not literal replication |
| P95 latency | Router/runtime | WunderGraph / Cosmo | SoundCloud reactions query: 171 ms to 94 ms, about 45% lower | Named customer case study, vendor-published | [D](#vendor-sources-and-context) | Delta/Epsilon; query-specific and source baseline wording is ambiguous |
| Compute allocation | Resource/runtime | WunderGraph / Cosmo | SoundCloud headline: 600 to 80 vCPUs, reported 86% reduction | Named customer case study, vendor-published | [D](#vendor-sources-and-context) | Delta/Epsilon resource hypothesis; allocation is not measured CPU consumption; source inconsistency remains open |
| Annual infrastructure savings | Derived economics | WunderGraph / Cosmo | SoundCloud: estimated $265,000 annually | Named customer case study / vendor estimate | [D](#vendor-sources-and-context) | Later economics from raw resources and explicit pricing; not a local dollar target |
| Feature shipping speed | Developer productivity | WunderGraph / Cosmo | SoundCloud body: more than 3x faster (summary: 3x) | Named customer case study, vendor-published | [D](#vendor-sources-and-context) | Equivalent change tasks; organizational/platform intervention limits transfer |
| Slow operation / planning latency | Planner/cache/runtime | WunderGraph / Cosmo | Anonymous customer: 10+ seconds to under one; roughly 90-95% less planning latency, 12-18x faster operation | Anonymous customer case study | [E](#vendor-sources-and-context) | Delta/Epsilon graph-complexity and cold/warm experiments; cache-warming treatment, not a pure planner-speed ratio |

#### Vendor sources and context

- **A — [RS Group's API Strategy: Modernizing their Tech Stack with Apollo](https://www.apollographql.com/customers/rs-group).** Federation/GraphOS adoption and Gateway-to-Router Core migration are discussed with granular caching and event-driven architecture. The 5x throughput and 24% P95 gains do not establish an isolated router-swap effect.
- **B — [What's New in GraphOS: Apollo Winter '25 Release - Apollo Connectors, Native Query Planner, Improved Tools, and More!](https://www.apollographql.com/blog/whats-new-in-graphos-apollo-winter-25-release-apollo-connectors-native-query-planner-improved-tools-and-more).** Published February 19, 2025; the supplied URL remains available. Apollo reports customer-base gains following native-planner validation and production load testing. Only the planning figure is explicitly a median. This concerns upgrading to Router 2.0, not Apollo versus Cosmo; the page supplies no complete reproducible workload or per-customer configuration.
- **C — [AI Market Intelligence Company AlphaSense ships features in hours instead of days or weeks with GraphOS](https://www.apollographql.com/customers/ai-market-intelligence-company-alphasense-ships-features-in-hours-instead-of-days-or-weeks-with-graphos).** The 20-40% figure is Eldar's estimate for rollout to client teams, depending on feature. Federation, GraphOS schema checks, automated workflows and team standardization accompany the change; this is not a controlled individual coding-time measurement.
- **D — [SoundCloud and WunderGraph Cosmo Cut Computing Costs by 86%](https://wundergraph.com/blog/cosmo_case_study_soundcloud).** Updated July 2, 2026. The headline uses 600 to 80 vCPUs, but the body specifies ten containers at four vCPUs each (40 vCPUs) and 80 GiB memory. Preserve this unresolved inconsistency; do not silently repair it. Session management, geo lookups and subscriptions moved to other services. The savings estimate uses AWS Fargate US-EAST pricing; a separate monthly infrastructure-cost comparison is about $14,000 to $9,750 with Tyk and Cosmo combined. The summary labels the query endpoints P95, while the body calls 171 ms an average and 94 ms P95. Architecture and workload scope changed, so neither latency nor compute headlines prove a pure router swap.
- **E — [From 10+ Seconds to Under One: Solving Their Slowest Operation](https://wundergraph.com/blog/casestudy-anon-10-sec-to-under-1).** Updated July 26, 2026. An anonymous finance marketplace used an aging Node Apollo Gateway and roughly ten subgraphs. After migration, Cosmo Cache Warmer preplanned expensive operations. The reported window had no other deployed changes and attributes the improvement to warming. Planning and operation/execution wording overlap; retain their distinction and do not recast this as an uncached Apollo Router-versus-Cosmo planner comparison.

### Lab-derived metrics — not vendor claims

Preserve raw measurements and their accounting definitions, units and availability. Unavailable telemetry is unknown, not zero. Economic values can be derived later because API prices and assumptions about human labor costs change. Cached tokens need explicit accounting so totals do not double-count them.

| Measurement family | Initial candidates | Interpretation |
| --- | --- | --- |
| Agent tokens | Input tokens, output tokens, cached tokens where available, total token consumption | Raw provider counters with model/configuration and accounting provenance |
| Time | Wall-clock elapsed task/query time; human active effort minutes; agent execution minutes | Distinguish active human work, agent execution and elapsed duration; overlapping work is not automatically additive |
| Outcomes | Correctness/task-success rate; failure/error rate | Retain raw counts, scoring evidence and denominator; a faster wrong answer cannot win |
| Execution behavior | Retries; tool/retrieval count where measurable; variance/repeatability across repeated trials | Preserve per-trial evidence rather than only aggregates |
| Implementation effort | Human intervention count; implementation failures/retries; effort to reach acceptance | Include design, review, debug, correction, redirects, rejections and manual repairs |
| Accepted scope | Scope/capability delivered; successful capability and acceptance point | Normalize effort against equivalent outcomes, not unequal amounts of delivered functionality |

Examples of later derived measures, not commitments: tokens per successful task; human minutes per successful capability; agent minutes per successful capability; failures/interventions per accepted implementation task; operating cost per correct query; cost per successful outcome. Preserve raw inputs and make any later pricing assumptions explicit and dated.

### Implementation-effort experiments

Stage A may test vendor/developer-productivity hypotheses through the effort the lead developer plus agent(s) need to implement equivalent approaches. Define tasks and acceptance points beforehand. Capture human active design/review/debug/correction minutes, agent execution minutes and tokens, interventions/redirects/rejections/manual repairs, failed builds/tests/transactions and retries, and the accepted capability reached. Design measurement before work starts: implementation effort cannot be reconstructed reliably after the fact.

Order creates learning and reuse effects. If Apollo precedes Cosmo, later work can inherit knowledge and infrastructure paid for by the earlier treatment; we cannot unlearn it. Initial comparisons may therefore be partly observational. Mitigate with equivalent predefined tasks, fresh agent contexts where practical, active-effort measurement and retained run evidence. Label inherited/reused work explicitly, including setup versus incremental change effort, rather than pretending it did not exist. No perfectly controlled productivity claim is established by this design.

### Controlled API execution direction

API-driven agent execution is likely to become the preferred Stage A benchmark mechanism because repeatability and evidence capture can be enforced automatically. This is a design idea only; no API integration or harness is implemented or authorized here, and the existing execution gates remain in place.

An eventual harness should help hold constant, except for a declared treatment:

- Raw enterprise source state/dataset and query/task corpus.
- Model/version/configuration, unless the model itself is the treatment.
- Base instructions and tool permissions where applicable; Beta guidance, Gamma adapter interfaces and Delta/Epsilon router interfaces remain declared treatment differences.
- Context, token and time limits; cache/warm-up policy; repetitions and scoring rubric.
- Underlying evidence across Alpha/Beta/Gamma/Delta/Epsilon wherever technically possible, with unavoidable differences recorded.

Potentially blind the correctness/quality evaluator to scenario identity where practical. Retain inputs, outputs, scores, raw measurements, versions and run manifests. The precise providers, execution settings and evaluator design remain open.

### Benchmark profiles and topology scaling

The design direction is to avoid enlarging the canonical Enterprise dataset or architecture merely to imitate a customer case study or produce impressive numbers. Keep canonical datasets deterministic, understandable and human-auditable. Add deterministic benchmark profiles only when a defined hypothesis requires properties current fixtures do not exercise.

| Possible profile | Property a hypothesis might require |
| --- | --- |
| Baseline | Small auditable reference workload |
| Load/concurrency | Sustained offered load and concurrent requests |
| Graph/topology complexity | More subgraphs, entity hops, branches and joins |
| Agent/semantic complexity | Cross-domain reasoning, ambiguity and broader records |
| Cold-start/cache state | Explicitly controlled cold versus warm planning/execution |
| Large-data, if justified later | Data volume absent from current fixtures |

Vary data volume, topology/subgraph count, query complexity and concurrency independently where possible, so row growth is not mistaken for planner stress. A future planner/federation experiment may scale topology as small/moderate/high without pretending the fictional Enterprise needs every synthetic split. Synthetic topology is experimental apparatus, not product architecture; profile sizes and counts are undecided.

Enterprise scope is not expected to stop at Personnel plus Missions. Assets and possible financial domains may naturally supply bounded contexts later; their contracts are not invented here. Extend datasets or architecture only when a defined hypothesis needs a property the current fixtures do not exercise.

### Experimental interpretation

Agent-level metrics can compare Alpha/Beta/Gamma/Delta/Epsilon. Federation/router runtime metrics mainly compare Delta/Epsilon (the two routers; Gamma has no router). Developer-productivity metrics require equivalent implementation/change tasks. Do not force every metric across every treatment or treat a historical vendor baseline as the lab's baseline. Distinguish a directional hypothesis test from numerical replication; record unsupported or non-comparable claims explicitly. Keep the planned blocked/repeated-trial analysis in [Plan](PLAN.md#planned-statistical-analysis), with correctness, variability and limitations alongside speed and resource measurements.

### Open questions / later

- Final benchmark corpus, expected outcomes and scoring rubric.
- Exact repetitions and statistical power considerations.
- API providers, models/configuration and handling of model drift.
- Whether/when independent third-party assessments should be consulted after lab evidence.
- Which vendor claims are reproducible in the lab topology, including ambiguous SoundCloud figures and metric definitions.
- Exact deterministic profile sizes and topology/subgraph counts.
- Fair implementation-effort normalization across treatments, including learning/reuse effects.
- Whether/how to price human effort in economic comparisons.
- Whether combined cost/benefit scoring is useful or misleading.
- Whether federation alternatives beyond Apollo/Cosmo/Hive warrant Stage A inclusion; the existing Hive roadmap is retained and a possible Zeta (adapters plus Hive) exists only if Hive joins.

## Federation experiment 1: a Spring subgraph under the Apollo router (2026-10-15)

Status: executed once, in disposable containers outside the repository, and thrown away; the source is not committed. This section records interoperability findings only. It decides nothing, freezes no version and is not a benchmark: every size, time and memory figure is **informal** (one run, no repeats, no quiet-machine protocol, Docker Desktop on the lead developer's machine before the memory upgrade). The questions come from the experiments list of the [federation design](FEDERATION-DESIGN.md#the-open-list), numbers (1), (3) and (4). Each result below is a fact the run showed, or says **not tested**.

### What was built

- **Subgraph `assets`:** one Spring Boot adapter with one entity, `Asset`, keyed by `assetId`, serving four stubbed assets (AST-0001 to AST-0004) copied from the released Assets dataset 1.1. It does not call the Assets service.
- **Subgraph `missions` (a reference stub):** a second instance of the same jar with another schema, so that the router has to reach `Asset` through `_entities`. It owns `Mission` and declares `Asset` only as a reference, `@key(fields: "assetId", resolvable: false)`. With one subgraph the router would never call `_entities`.
- **Router:** the official Apollo router image, started with a supergraph file and no account.
- **Composition:** Rover, run inside a disposable Node container.

### Versions that worked together on Java 21

| Part | Version | Where it came from |
| --- | --- | --- |
| Java | Temurin 21.0.12.1+1 (runtime and build) | `maven:3.9-eclipse-temurin-21`, `eclipse-temurin:21-jre` |
| Spring Boot | 3.4.5 | `spring-boot-starter-parent` |
| Spring for GraphQL | 1.3.5 | managed by Spring Boot |
| graphql-java | 22.3 | the version federation-jvm 5.4.0 declares; Spring Boot 3.4.5 manages the same version, so no override was needed |
| federation-graphql-java-support | 5.4.0 | Maven Central |
| Rover | 1.0.0, with the composition plugin `supergraph` v2.9.3 | npm `@apollo/rover`; the plugin was downloaded by Rover |
| Apollo router | v2.13.0 | `ghcr.io/apollographql/router` |

federation-jvm 5.4.0 on Java 21: **it built and ran with no change**. Its published pom declares no Java target, so the run shows that it works on 21 and not that the project declares 21 supported. The fallback (Netflix DGS) was not needed and was not tried.

Image digests, resolved with `docker buildx imagetools inspect` on 2026-10-15 (tags move; the date is part of the record):

| Image | Digest |
| --- | --- |
| `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |
| `ghcr.io/apollographql/router:v2.13.0` | `sha256:fcb84b8780f56554b92dfcde92217000d0ba6eec81e87651345b672616c3876b` |
| `node:22-slim` | `sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` |

The router tag `v2.13.0` was chosen by guess and found to exist; whether it was the newest router was not checked.

### What the subgraph served

- **The wiring** is one `GraphQlSourceBuilderCustomizer` that calls `builder.schemaFactory(...)` and passes the registry and the wiring to `Federation.transform(registry, wiring).fetchEntities(...).resolveEntityType(...).build()`. Annotated `@QueryMapping` controllers worked unchanged beside it.
- **`_service { sdl }` answered.** The SDL declares `@link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key"])`, that is **Federation 2.0**, which is the version the schema file asked for. federation-jvm printed it as `schema @link(...)` and added the definitions of the federation directives it knows (`@key` with `resolvable`, `@federation__extends`, `@federation__external`, `@federation__override`, `@federation__provides`, `@federation__requires`, `@federation__shareable`, `@inaccessible`, `@tag`), `union _Entity`, `scalar _Any`, `_service` and `_entities`. Only `@key` and `@link` were used.
- **`_entities` answered** for a representation `{__typename: "Asset", assetId: "AST-0002"}` with the record, and returned `null` in that position for an unknown id (AST-9999). It does not raise an error for an unknown key.
- **Not tested:** `@shareable`, `@external`, `@requires`, `@provides`, `@override`, `@tag`, `@inaccessible` and composite keys. The library declares their definitions; whether it resolves entities that depend on them was not run.

### Composition and the router

- **Composition** with `rover supergraph compose --config supergraph.yaml` (`federation_version: =2.9.3`, two subgraphs with `routing_url` and a `schema.file` each) produced a supergraph with `join__*` directives. Both subgraphs, including the `resolvable: false` reference, composed without warnings.
- **No account was needed for composition or for the router.** No Apollo account, graph API key or graph ref was created, entered or set. Rover composed from local files and the router started with `--config` and `--supergraph` only; its log reports `UpdateLicense(Unlicensed)` and then serves GraphQL on port 4000. The router log line says it is "Licensed as ELv2" and that anonymous usage data is gathered; telemetry was switched off only for Rover (`APOLLO_TELEMETRY_DISABLED=1`), not for the router. The router needed a configuration file with `supergraph.listen: 0.0.0.0:4000` to be reachable from outside its container.
- **The ELv2 prompt** of Rover's composition plugin was accepted by the lead developer, who gave their acceptance in the session before the run; the run then set `APOLLO_ELV2_LICENSE=accept` in the disposable container only.
- **Rover 1.0.0 downloads its plugin on first use** from `rover.apollo.dev` and warns that a future version will stop doing so unless `APOLLO_ROVER_ALLOW_AUTOMATIC_DOWNLOAD` is set. The run used the automatic download.
- **`node:22-slim` has no CA certificates**, and Rover then fails with `No CA certificates were loaded from the system`. The run copied `/etc/ssl/certs/ca-certificates.crt` out of the Temurin image and set `SSL_CERT_FILE` to it. A Node image with certificates, or `apt-get install ca-certificates`, is the other way.
- **One query through `_entities` worked.** `{ mission(id: "M-1") { id title assets { assetId name status kind } } }` sent to the router returned the mission from `missions` and the asset fields from `assets`, and the `assets` adapter received the entity request.

### Failure behavior seen in the run (not a decision)

These were seen with the router's default configuration, and are relevant to [the failure semantics](FEDERATION-DESIGN.md#failure-semantics) as observations only.

- **An unknown key.** With `assets: [Asset!]!` in the `missions` schema, one unresolved reference nulled the whole `mission` (`data.mission` is `null`). With `assets: [Asset]!` the other two assets were returned and the unresolved one was `null`; in both cases the router added `extensions.valueCompletion` with the message `Null value found for non-nullable type String`, and no `errors` entry. This matches the open item that fields behind a service must be nullable.
- **An outage of `assets`** (the container stopped). The first query waited the router's default 30 seconds and returned `GATEWAY_TIMEOUT` with no data. A later query took about 14.5 seconds and returned HTTP data with the `mission` fields and `assets: [null, null, null]`, and three `errors` entries whose message is `Subgraph errors redacted`, each with its path and **no** `SERVICE_UNAVAILABLE` code. The router log named the cause (`tcp connect error`, `No route to host`). The HTTP status of that response was not recorded. Whether router configuration (for example including subgraph errors, or a shorter timeout) can produce the decided code and a prompt answer was **not tested**.

### Informal figures

- **Adapter image:** 523 MB (`docker images`), built from the two digests above in one multi-stage Dockerfile with a non-root user. **Router image:** 281 MB.
- **Start-up:** Spring reported `Started Application in 2.3` to `3.1` seconds in three starts; the router logged its GraphQL endpoint about 0.2 seconds after its container started.
- **Memory** (`docker stats` after start and a few requests, no limits set): adapter about 215 to 225 MiB, router about 27 MiB. Two adapter containers were running.
- **Build:** about 20 seconds for the Maven step with network access on an empty Maven cache. None of these figures is a benchmark.

### The pieces that matter

```xml
<parent> spring-boot-starter-parent 3.4.5 </parent>
<properties><java.version>21</java.version></properties>
<!-- spring-boot-starter-graphql, spring-boot-starter-web -->
<dependency>
  <groupId>com.apollographql.federation</groupId>
  <artifactId>federation-graphql-java-support</artifactId>
  <version>5.4.0</version>
</dependency>
```

```graphql
# assets subgraph
extend schema @link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key"])
type Query { asset(assetId: ID!): Asset }
type Asset @key(fields: "assetId") { assetId: ID! name: String! kind: String! category: String! status: String! }

# missions subgraph (reference stub)
type Mission { id: ID! title: String! assets: [Asset]! }
type Asset @key(fields: "assetId", resolvable: false) { assetId: ID! }
```

```yaml
# supergraph.yaml for rover
federation_version: =2.9.3
subgraphs:
  assets:   { routing_url: "http://assets-host:8085/graphql",   schema: { file: /work/assets.graphql } }
  missions: { routing_url: "http://missions-host:8086/graphql", schema: { file: /work/missions.graphql } }
# router.yaml
supergraph:
  listen: 0.0.0.0:4000
```

Reproduce, in a disposable folder outside the repository, with Docker only:

```sh
docker build -t fed1-adapter .          # multi-stage: maven digest, then eclipse-temurin digest
docker run -d --network fed1-net fed1-adapter                      # assets on 8085
docker run -d --network fed1-net -e SPRING_GRAPHQL_SCHEMA_LOCATIONS=classpath:graphql-refs/ -e SERVER_PORT=8086 fed1-adapter   # missions
# fetch both SDLs with: { _service { sdl } } ; then, in node@sha256:c3de60bf... with APOLLO_ELV2_LICENSE=accept and SSL_CERT_FILE set:
npm i @apollo/rover && rover supergraph compose --config supergraph.yaml --output supergraph.graphql
docker run -d -p 4000:4000 -v <dir>:/dist/config ghcr.io/apollographql/router@sha256:fcb84b87... --config /dist/config/router.yaml --supergraph /dist/config/supergraph.graphql
```

### Limits of this run

One machine, one run, stubbed data, two subgraphs, one entity, Federation 2.0 declared, the plain router with default configuration. Cosmo, Hive, the Federation features beyond `@key`, the real Assets service, the SOAP and XML adapters, container limits and any repeat measurement were not part of it.

## Federation experiment 2: the owning adapter produces the outcome, under three routers (2026-10-16)

Later context (2026-10-17): the experiment text below is kept as it was written. The id that the mapping subgraph contributes was called `astId` in the experiment and in the first adapters; the graph refinements Job renamed it `assetId`, removed the `id` field of the reference types and added `mappingOutcome` to the `@requires` set (see the section at the end of this document). Read `astId` below as today's `assetId`.

Status: executed once, in disposable containers outside the repository, and thrown away; the source is not committed. This section records interoperability findings only. It decides nothing, freezes no version and is not a benchmark: every size, time and memory figure is **informal** (one run, no repeats, no quiet-machine protocol, Docker Desktop on the lead developer's machine **before** the memory upgrade; the lead developer said it was not yet installed at the time of the run). The question it answers is whether direction B of the [federation design](FEDERATION-DESIGN.md#failure-semantics), in which the owning adapter produces the whole `{ id, resolution, asset }` outcome of a reference in one call, composes and runs with the fewest Federation features, and whether the same subgraphs behave the same under the Apollo, Cosmo and Hive routers. Each result is a fact the run showed, or says **not tested**. Experiment 1 is [above](#federation-experiment-1-a-spring-subgraph-under-the-apollo-router-2026-10-15).

### What was built

- **Subgraph `missions` (a stub):** `Mission.assets(release: String!)` returns five local asset references (SH-17, EQ-64, SH-18, XX-99, SH-19), each `{ localRef, release }`. It declares `AssetReference @key(fields: "localRef release", resolvable: false)`.
- **Subgraph `mapping`:** the entity `AssetReference @key(fields: "localRef release")` with one field, `astId: ID`. For release `1.0` it maps SH-17, EQ-64, SH-18, SH-19 to AST-0001, AST-0002, AST-0404 and AST-0500; XX-99 and any other release give `astId` null.
- **Subgraph `assets` (the owning adapter):** the same `AssetReference` key, with `astId: ID @external` and three fields that carry `@requires(fields: "astId")`: `id: ID`, `resolution: Resolution!` and `asset: Asset` (nullable). `Resolution` is `RESOLVED | UNRESOLVED | UNAVAILABLE | UNMAPPED`. The adapter computes the outcome **once per entity** with one HTTP call (client timeout 1.5 s, connect timeout 1 s): 200 gives RESOLVED with the asset, 404 whose body has `code` ASSET_NOT_FOUND gives UNRESOLVED, any other answer or failure gives UNAVAILABLE, and a null `astId` gives UNMAPPED without a call. For UNAVAILABLE the first field resolver of the entity returns a GraphQL error with `extensions.code` SERVICE_UNAVAILABLE, so one failed call makes one entry.
- **A stub REST service:** a fourth instance of the same jar. It serves the first four assets of the released Assets dataset 1.1 (AST-0001 to AST-0004), answers 404 `ASSET_NOT_FOUND` for AST-0404 and any other id, and answers AST-0500 after 6 seconds, to make a timeout.
- **Routers and composition:** Apollo router with Rover, Cosmo router with `wgc router compose`, Hive Router reading the supergraph that Rover produced. No account, key or token was created, entered or set for any of them.

### Versions and digests

Image digests resolved with `docker buildx imagetools inspect` on 2026-10-16 (tags move). The Java, Spring Boot, graphql-java and federation-jvm versions are those of experiment 1 and built and ran unchanged.

| Part | Version | Digest or source |
| --- | --- | --- |
| Apollo router | v2.18.0 (the newest release that is not a preview; `v3.0.0-preview.0` exists) | `ghcr.io/apollographql/router@sha256:5b02af03e8f0268b8fcf85132c9e54ea36a1029b0823b00bb9151f698a991215` |
| Rover | 1.0.0, composition plugin `supergraph` v2.9.3 | npm `@apollo/rover`; the plugin was downloaded by Rover |
| Cosmo router | 0.359.0 (released 2026-10-15) | `ghcr.io/wundergraph/cosmo/router@sha256:a125c80b7c759837901a080bb9f64518eb5826a979f7b2f512661cacf1caff6d` |
| Cosmo CLI | `wgc` 0.133.0 | npm `wgc` |
| Hive Router | 0.3.5 (released 2026-10-14) | `ghcr.io/graphql-hive/router@sha256:feaf52e70615f8516d86c4c07f6f29046d88e1b38f9cf6aa099d17b2b51f4827` |
| Build image | `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| Runtime image | `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |
| Node image | `node:22-slim` | `sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` |

The three build and Node digests are the ones of experiment 1: the tags had not moved in one day.

### The table

Each cell is what the run showed. "Redacted" means the message of the errors entry; every router answered HTTP 200.

| Question | Apollo router v2.18.0 | Cosmo router 0.359.0 | Hive Router 0.3.5 |
| --- | --- | --- | --- |
| Composition of the three subgraphs with `@key`, `@requires` and `@external` only | Composed by Rover, no warning | Composed by `wgc router compose`, output is a router execution config (JSON, 13 KB), no warning | Runs the supergraph that Rover composed; loaded without a message |
| A Federation feature beyond those three forced by composition | No | No | No |
| `@requires` input is null (UNMAPPED): the router still calls the adapter | Yes, the adapter answered UNMAPPED | Yes | Yes |
| RESOLVED, UNRESOLVED, UNMAPPED as data, `asset` null when not resolved | Yes | Yes | Yes |
| UNAVAILABLE as data for a slow service (client timeout 1.5 s) and for a stopped service, `asset` null | Yes, 1.5 s and 4.0 s | Yes, 1.6 s and 4.0 s | Yes, 1.5 s and 4.0 s |
| Partial result: the rest of the query answers, HTTP status | Yes, HTTP 200 with the mission and the other references | Yes, HTTP 200 | Yes, HTTP 200 |
| Nullable `asset` accepted in composition | Yes | Yes | Yes (the same supergraph) |
| Errors entry in the default configuration | One entry per failed call, message `Subgraph errors redacted`, path with the list index, **no code** | One entry for the whole fetch, message `Failed to fetch from Subgraph 'assets' at Path 'mission.assets'.`, no path and **no code at top level**; the subgraph's own error, with its message, path and code, sits inside `extensions.errors` | One entry per failed call, message `Unexpected error`, path with the list index, **code SERVICE_UNAVAILABLE kept** in `extensions` |
| The setting that passes the subgraph error through | `include_subgraph_errors: { all: true }` | `subgraph_error_propagation: { enabled: true, mode: pass-through, allow_all_extension_fields: true }` | `error_masking: { all: { enabled: false } }` |
| What the client sees with that setting | `message` "Assets service unavailable", the path with the index, `extensions.code` SERVICE_UNAVAILABLE, plus `classification` and `service`; one entry per failed call (four entries for four) | The same message, `extensions.code` SERVICE_UNAVAILABLE, plus `classification` and `serviceName`; the path has no list index and ends at `resolution`; four entries for four failed calls | The same message, the path with the index, `extensions.code` SERVICE_UNAVAILABLE, plus `service`, `affectedPath`, `classification` and `locations`; four entries for four failed calls |
| Runs with no account, token or key | Yes; log says `UpdateLicense(Unlicensed)` and "Licensed as ELv2", and that anonymous usage data is gathered | Yes; one warning: "No graph token provided", listing five disabled Cosmo Cloud features (Schema Usage Tracking, Persistent operations, Advanced Request Tracing, Cosmo Cloud Tracing, Cosmo Cloud Metrics) | Yes; no line about a license or a token at the default log level |
| Prompts met | The ELv2 prompt of Rover's plugin, accepted by the lead developer for this session; none from the router | None from `wgc` or the router | None |
| Image size | 286 MB | 145 MB | 132 MB |
| Resident memory, informal, after a few requests, no limits | 23 MiB | 25 MiB | 52 MiB |
| Time to serving, informal | about 0.24 s from the first log line to the GraphQL endpoint | about 0.04 s from the first log line to "Server initialized" | about 0.2 s from the first log line to "supergraph loaded" |

The adapter image was 523 MB and each adapter instance used 200 to 255 MiB of resident memory (informal). The slow service answered after 6 s and the client timeout was 1.5 s; the router's own subgraph timeout was never reached, so experiment 1's 30 s did not recur.

### Findings that matter for the design

- **The fewest features were enough.** `@key` (one composite key, `localRef release`, with `resolvable: false` on the reference stub), `@requires` and `@external` on `astId`. No `@shareable`, `@provides`, `@override`, `@tag` or `@inaccessible` was needed. `astId` is contributed by `mapping` and declared `@external` in `assets`; the key fields need no `@shareable`. The supergraph shows `astId` joined from both subgraphs and `id`, `resolution` and `asset` joined from `assets` with `requires: "astId"`.
- **The mapping release travels inside the key.** `@requires` takes a field set, which has no place for a variable of the client's query, so the release is a key field of the reference (`localRef release`) and `astId` has no argument. Whether a field with an argument can appear in a `@requires` set was **not tested**.
- **UNMAPPED works as a null input.** The mapping answers `astId` null; the router still asks the adapter, which derives UNMAPPED without calling the service. No router skipped the call.
- **The router does not produce the outcome; the adapter does.** All four values reached the client as data under all three routers, which matches the finding of experiment 1 that a router returns an entity or null and nothing more.
- **Passing the error through is configuration, and each router has its own.** The default of each router hides the code in a different way (Apollo redacts message and extensions; Cosmo wraps the subgraph error one level down; Hive masks the message but keeps the code). The three settings are in the table. With each setting the client receives the code, so the decided errors entry reaches it under all three routers, but its shape differs: Cosmo reports no list index in the path.
- **One entry per failed call needed adapter work.** The library's entity fetcher was not used to return an error per entity; the adapter attaches the error to whichever field of the entity is resolved first, so a client that selects none of `id`, `resolution` and `asset` gets no entry. Whether federation-jvm can return a per-entity error from the fetcher itself was **not tested**.
- **A stopped service answered in about 1 s per failed call**, and four failed calls took 4 s in total because the adapter resolves the entities one after another. Why a stopped container takes about a second to fail was not examined.
- **What the Hive Console would add was not tested.** The Hive Router read the supergraph from a file composed by Rover, so Apollo's composition output ran under it unchanged. The sources read on 2026-10-16 list the Console's CDN as another supergraph source that needs an endpoint and a key, and no local composition command of Hive was found or tried.
- **Telemetry:** Rover ran with `APOLLO_TELEMETRY_DISABLED=1` and `wgc` with `COSMO_TELEMETRY_DISABLED=1` (a name taken by analogy and **not verified** against Cosmo's documentation); the three routers ran with their default telemetry settings.

### Settings and where they were read

- Apollo: `include_subgraph_errors`, keys `all` and `subgraphs`, each a boolean or an object with `redact_message`, `allow_extensions_keys`, `deny_extensions_keys`, `exclude_global_keys`; the documented default for `all` is false (redacted). Page `apollographql.com/docs/graphos/routing/observability/subgraph-error-inclusion`, fetched 2026-10-16, which states no router version; the run used v2.18.0 and `all: true` produced the result above.
- Cosmo: `subgraph_error_propagation` with `enabled` (default false), `mode` (`wrapped` default, or `pass-through`), `allowed_fields`, `allowed_extension_fields` (default `["code"]`), `allow_all_extension_fields` (default false), `omit_extensions`, `omit_locations`, `rewrite_paths`, `propagate_status_codes`, `default_extension_code`, `attach_service_name`; environment variables with the prefix `SUBGRAPH_ERROR_PROPAGATION_`. Page `cosmo-docs.wundergraph.com/router/configuration`, fetched 2026-10-16; the run used router 0.359.0 and `CONFIG_PATH` for the file.
- Hive: `error_masking` with `enabled` (default true), `redacted_error_message` (default "Unexpected error"), `all.enabled` (default true) and `all.extensions` (`mode` allow or deny with `keys`), and per-subgraph overrides under `subgraphs`. Page `the-guild.dev/graphql/hive/docs/router/configuration/error_masking`, fetched 2026-10-16; the run used router 0.3.5. Supergraph source: `supergraph: { source: file, path: ./supergraph.graphql }` in `router.config.yaml`, both mounted under `/app`.

### The pieces that matter

```graphql
# missions (stub)
type Mission { id: ID! title: String! assets(release: String!): [AssetReference!]! }
type AssetReference @key(fields: "localRef release", resolvable: false) { localRef: ID! release: String! }

# mapping
type AssetReference @key(fields: "localRef release") { localRef: ID! release: String! astId: ID }

# assets (the owning adapter)
type AssetReference @key(fields: "localRef release") {
  localRef: ID!  release: String!
  astId: ID @external
  id: ID @requires(fields: "astId")
  resolution: Resolution! @requires(fields: "astId")
  asset: Asset @requires(fields: "astId")
}
```

```yaml
# Apollo router.yaml
supergraph: { listen: 0.0.0.0:4000 }
include_subgraph_errors: { all: true }
# Cosmo config.yaml, started with CONFIG_PATH, EXECUTION_CONFIG_FILE_PATH and LISTEN_ADDR
version: "1"
subgraph_error_propagation: { enabled: true, mode: pass-through, allow_all_extension_fields: true }
# Hive router.config.yaml, mounted at /app/router.config.yaml
supergraph: { source: file, path: ./supergraph.graphql }
error_masking: { all: { enabled: false } }
```

```sh
# composition (SDLs fetched with: { _service { sdl } } from each adapter)
rover supergraph compose --config supergraph.yaml --output supergraph.graphql          # Apollo and Hive; APOLLO_ELV2_LICENSE=accept
wgc router compose --input cosmo-graph.yaml --out cosmo-config.json                   # Cosmo, with subgraphs: name, routing_url, schema.file
# the query
{ mission(id: "M-1") { id title assets(release: "1.0") { localRef id resolution asset { assetId name status } } } }
```

The expected answer for the five references, in order, is RESOLVED (AST-0001), RESOLVED (AST-0002), UNRESOLVED (AST-0404, asset null), UNMAPPED (id null, asset null) and UNAVAILABLE (AST-0500, after the timeout). With the stub stopped, the first, second, third and fifth are UNAVAILABLE and the fourth stays UNMAPPED.

### Limits of this run

One machine, one run, stubbed data, one entity type, Federation 2.0 declared, router 2.18.0 for Apollo, one query shape. The crew pattern with Personnel v2, the SOAP and XML adapters, the real Assets service, a failure of the adapter itself (the router reports it, as the design already records), queries that omit `resolution` and `asset`, a `@requires` set with an argument, paging, container limits, router features that need a license, the Hive Console and any repeat measurement were not part of it.

## Federation graph refinements: findings of 2026-10-17 (Apollo router v2.18.0)

Recorded by the graph refinements Job on the stub-backend stack; one run, informal times, no benchmark. It decides nothing. The router table with the full detail is in [federation/routers/apollo/README.md](../federation/routers/apollo/README.md).

- **A `@requires` of two fields, one an enum from another subgraph, works under Apollo.** `@requires(fields: "assetId mappingOutcome")` (and the same for `personnelId mappingOutcome`) composed with Rover 1.0.0 / supergraph 2.9.3 without a warning, and the router passed both fields to the owning adapter in the representation. The enum `MappingOutcome` is declared identically in the three subgraphs that mention it and composed as one enum. This was a compatibility-matrix item for Cosmo and Hive too: it is still open for them (a later Job).
- **A refused release can be stated as data.** With `mappingOutcome` owned by the mapping subgraph and read through `@requires`, the data says RELEASE_REFUSED beside the `MAPPING_RELEASE_*` errors entry, where before it showed UNMAPPED.
- **An in-subgraph traversal needs no federation feature.** `Asset.parent`, resolved by the Assets adapter itself with one call per level, gives the parent chain in one query.
- **The router's subgraph timeout decides how a dead adapter looks.** With the 30 s default, HTTP 504 with data null; with 5 s, HTTP 200 and one `GATEWAY_TIMEOUT` entry per failed fetch, the nearest nullable ancestor of the non-null fields nulled, and roots of other subgraphs answered. Apollo has no setting that returns the rest of the object. Later the same day a nullable `resolution` did, see the next section.
- **A selection that omits `resolution` and `asset` does not call the owning adapter.** A query for `localRef release assetId mappingOutcome` was answered with the Assets adapter stopped. Selecting `resolution` alone still makes the router ask the mapping subgraph first, for the `@requires` input.

## Federation nullable resolution: findings of 2026-10-17 (Apollo router v2.18.0)

Recorded by the nullable resolution Job on the stub-backend stack; one run, informal times, no benchmark. It decides nothing for Cosmo or Hive. The router table is in [federation/routers/apollo/README.md](../federation/routers/apollo/README.md#a-null-resolution).

- **A nullable field is what keeps the rest of the object under Apollo.** With `resolution: Resolution` (not `Resolution!`) on `AssetReference` and `PersonnelReference` and the 5 s subgraph timeout, a dead owning adapter gives HTTP 200, the mission and every other field kept, `resolution` and `asset` (or `personnel`) null, and one `GATEWAY_TIMEOUT` entry per failed fetch whose `extensions.service` names the subgraph. The router needed no new setting. This answers the open item of the graph refinements findings above (no router setting returns partial data): the schema, not the router, decides how far a null climbs.
- **The rule the nullable field needs.** A null `resolution` means only that the router could not ask the owning adapter; the errors entry says why. Every other case stays an explicit value and the adapters never return null. A client must check the errors list whenever `resolution` is null.
- **Open for Cosmo and Hive:** whether they null only the field for a dead subgraph with the same schema, and their own timeout settings (a later Job).

## Federation Cosmo router: findings of 2026-10-18 (Cosmo router 0.359.0, wgc 0.133.0)

Recorded by the second router Job on the stub-backend stack; one run, informal times, no benchmark. It decides nothing for Hive. The tables are in [federation/routers/cosmo/README.md](../federation/routers/cosmo/README.md). Later context for the lines above that say the Cosmo and Hive behavior was open: the Cosmo half is answered here, and the earlier text stays as written.

- **The shared acceptance suite passes against Cosmo.** The 16 tests of Part 1 passed unchanged, and so did the 9 controlled cases of Part 3 once the settings object declared two more of Cosmo's own facts: the entry for a dead adapter has no `extensions` and names the subgraph only in its message, and a failed fetch is one entry where Apollo gives one per reference. The three settings of the suite (the code, the key naming the subgraph, the answer window) were not enough; they are five now and the Apollo values are the defaults.
- **A nullable field keeps the rest of the object under Cosmo too.** A stopped Assets, Personnel or both adapters gave HTTP 200 after about 5 seconds (`traffic_shaping.all.request_timeout: 5s`), the mission and the other subgraphs' fields kept, `resolution` and `asset` or `personnel` null. This answers the open item of the nullable resolution section above for Cosmo.
- **Cosmo's default retry changes the answer time of a dead adapter** (5 attempts, 3 s, a random wait up to 10 s): 5.1 s in one run and 21.0 s in the next with the timeout at 5 s. The build switched it off (`retry.enabled: false`).
- **The default error mode wraps, and `mode: pass-through` is the smallest setting that gives the code.** The default entry reads "Failed to fetch from Subgraph 'assets' at Path 'mission.assets'." with the subgraph's own errors under `extensions.errors`; with `pass-through` the entry is the subgraph's own, with `extensions.code` and `extensions.serviceName`. `allow_all_extension_fields` was not needed for the code. In 0.359.0 the schema marks `enabled` deprecated (errors are always propagated, with message and code only).
- **An error the router writes itself carries no `extensions`**, in either mode. That is the entry for a dead adapter.
- **`wgc router compose` composed the lab's four subgraphs offline** once its update check was switched off (`DISABLE_UPDATE_CHECK=true`; without it `wgc` fails under `--network none`). The output is an execution config of 59,540 bytes (indented, as the script writes it), byte-identical across runs, restarts and a second fetch, with a constant version and no timestamp. The reverse order of the subgraphs gave a different file, so the order is fixed.
- **Cosmo's composition and Rover's agree on the lab's schemas.** The client schema inside the execution config has the same types, fields (with arguments and nullability), enum values and union members as the Apollo supergraph; the two-field `@requires` with an enum from another subgraph composed without a warning and the router passed both fields to the owning adapter.
- **Cosmo found a restarted adapter again by itself** (16.4 s in the gate, about 11 s by hand); the Apollo router needed a restart.
- **The licence and the telemetry setting were read at the pinned versions' source.** Apache-2.0 at the tag `router@0.359.0` (root `LICENSE`, no enterprise folder) and at `wgc@0.133.0`; `COSMO_TELEMETRY_DISABLED=true` or `DO_NOT_TRACK=1` turns off the usage tracking of the router (`router/core/router.go`) and of `wgc` (`cli/src/core/telemetry.ts`). The guess of experiment 2 was right. Not legal advice.
- **Validation errors are HTTP 200 under Cosmo** (a query that omits a required argument gave an entry with no code); Apollo gives HTTP 400 `GRAPHQL_VALIDATION_FAILED`. Cosmo has `apollo_compatibility_flags` that move such behaviors toward Apollo's; none is used.
