# Federation mapping adapter

The mapping subgraph of the federation layer: a Java 21 Spring Boot adapter that serves the immutable mapping releases from files and answers, for a Missions-local asset reference and an explicit release, the mapped Assets identifier (`AST-nnnn`). It has no database, holds no state and makes no outbound call. It is not a legacy system: it lives under `federation/`, beside the shared library `federation/common` and the Assets adapter. The design it implements is [the federation design](../../../docs/FEDERATION-DESIGN.md); the findings it builds on are the two federation experiments in [Integration notes](../../../docs/INTEGRATION-NOTES.md).

## Layout and ports

- `federation/adapters/mapping/`: this adapter (`Dockerfile`, `compose.yaml`, `start.sh`, `src`, `validation`).
- `federation/personnel-mapping/`: the process that builds the crew section (and migrated the cast into Personnel v2). It does not ship in the image; its output, `crew.json`, does.
- `federation/mapping-releases/<MAJOR.MINOR>/`: the releases, one folder each, baked into the image at `/app/mapping-releases`.
- **Port 8190.** The adapters of the legacy services mirror the legacy last digits in the block 8181 to 8189 (Personnel 8182, Missions 8183, Assets 8184; the routers 8170 to 8172; 8180 is kept free). The mapping adapter has no legacy twin, so it lives in the block 8190 to 8199 for federation-only services, by the lead developer's word of 2026-10-16. The GraphQL endpoint is `http://127.0.0.1:8190/graphql`.

## The releases

A release is a folder named `MAJOR.MINOR` that never changes after it is published; a correction is a new release. A MINOR adds entries or controlled cases only; a MAJOR changes what an existing reference maps to, or the shape of the mapping. The mapping version and the version of any system are independent.

```
federation/mapping-releases/1.0/
  manifest.json   the release number, the SHA-256 of every file, and the checked-against list
  assets.json     the section for asset references: Missions-local reference to AST-nnnn
federation/mapping-releases/1.1/
  manifest.json   the same, with the Personnel v2 snapshot added to the checked-against list
  assets.json     the 1.0 file, byte for byte
  crew.json       the section for crew references: Missions-local reference (C-n) to PRS-nnnn, the full resulting table
federation/mapping-releases/1.2/
  manifest.json   the same, with Missions dataset release 1.1 and the large Personnel v2 snapshot added to the checked-against list
  assets.json     the 1.1 file, byte for byte
  crew.json       the 800 crew references of Missions dataset release 1.1 against personnel-v2-large-004
  participants.json  the section for participant references: Missions-local reference (P-n) to PRS-nnnn, only where the roster places a non-crew person
federation/mapping-releases/1.3/
  manifest.json   the same, with Missions dataset release 1.2 added to the checked-against list
  assets.json     the 1.2 file, byte for byte
  crew.json       the 1.2 file, byte for byte
  participants.json  the 58 P-references of Missions dataset release 1.2, every one resolved to a non-crew person of personnel-v2-large-004
```

- **A section per kind of reference.** One file per kind, named by the kind (`assets.json`; `crew.json` from release 1.1, a MINOR). The adapter loads and hash-checks every file the manifest lists and serves the `assets` and `crew` sections. A lookup in a release that has no such section (1.0 has no `crew`) gives no entry, never an error.
- **Release 1.0 is assets only and stays untouched.** `assets.json` holds the eight entries of the expected mapping of the Assets dataset release 1.1 (`uss-enterprise/assets/datasets/releases/1.1/provenance.json`, key `expectedMapping`): EQ-64, EQ-75, EQ-119, SH-42 and VS-31 (NORMAL), EQ-86 (MISSING), SH-53 (DESTROYED) and EQ-97, which maps to `AST-0097`, an id Assets does not hold (MAPPED BUT NOT FOUND, UNRESOLVED downstream). EQ-108 has **no entry** on purpose (UNMAPPED). No entry is invented: a gate re-derives the section from that provenance and fails on any difference. The file also repeats the controlled cases of the source for the reader.
- **Release 1.1 adds the crew section.** `assets.json` is the 1.0 file unchanged (a test compares the bytes). `crew.json` holds the ten Missions crew references of the recipe: Picard C-71 to PRS-0001, Riker C-78 to PRS-1048, Data C-85 to PRS-0002, La Forge C-92 to PRS-1049, Worf C-99 to PRS-1058, Beverly Crusher C-106 to PRS-1053, Troi C-113 to PRS-1054, Wesley Crusher C-120 to PRS-0714, Barclay C-127 to PRS-1057 and O'Brien C-134 to PRS-1100. It is built by [the crew mapping process](../../personnel-mapping/README.md), with its pinned inputs repeated in the file (`inputs`) and the controlled cases (`NORMAL`, `EXCEPTION`, `MIGRATED`); a gate re-derives the whole file and fails on any difference. A reference with no entry has no mapping (UNMAPPED). The checked-against list of 1.1 adds the Personnel v2 snapshot `personnel-v2-small-003`.
- **Release 1.2 maps Missions dataset release 1.1 to the large Personnel v2 snapshot.** A MINOR: the ten crew entries of 1.1 keep their targets, 790 crew entries and a `participants` section are added, `assets.json` is the 1.1 file unchanged (the nine asset references of the recipe are the same; the dangling and unmapped asset references of the edge-case ledger have no entry), and `checkedAgainst` repeats the list of 1.1 and adds Missions dataset release 1.1 and `personnel-v2-large-004`. `crew.json` holds the 800 references of `references.crew` (exact names of the legacy release, 794 by exact name and 6 by the mapping exceptions table, 20 of them people who are civilians in the roster); the three `unmappedCrew` references are not offered to the process and have no entry. `participants.json` holds the P-references that the roster places as non-crew people (Guinan P-1068 to PRS-0003 by exact name, Alexander P-1003 to PRS-3001 by the participant exceptions table); a P-reference nobody places has no entry (UNMAPPED). **O-references are refused by class**: the process never accepts one whatever its name, so the returning Wesley Crusher (O-860) never reaches PRS-0714. Nothing in the graph reads the `participants` section yet; the adapter loads and hash-checks it like any other file and lists it in `mappingReleases`.
- **Release 1.3 maps the participants of Missions dataset release 1.2.** A MINOR, built for the reclassified participants: Missions dataset release 1.2 holds 211 participant references, each with its class in its `participants.json` (58 P, the on-board non-crew personnel, and 153 O, the outsiders). `assets.json` and `crew.json` are the files of release 1.2 byte for byte (the crew side did not change, and the build fails if the crew section it derives ever differs from 1.2's). `participants.json` holds an entry for **every** P-reference: 56 roster civilians and Guinan by exact name, and P-1003 Alexander Rozhenko by the participant exceptions table (the entry predates the full name in the Missions data and still gives the same person). Under the definitions of the Missions data a P is an on-board person and must resolve, so the build runs the participant step in strict mode: a P that nobody places is a **failure** that names it, not an UNMAPPED to accept. No O-reference has an entry, whatever its name; this protects the returning Wesley Crusher O-860 and the off-roster civilian Clara Sutter O-2836. `checkedAgainst` repeats the list of 1.2 and adds Missions dataset release 1.2. The graph does not resolve a participant yet: the section is data, and the adapter serves it like the others.
- **A release may be excused, by an explicit list.** The check that fails when the repository holds a system release the mapping was not checked against excused Missions dataset release 1.1 through an explicit list, `PENDING_MAPPING` in `release_check.py`, until release 1.2 listed it, and Missions dataset release 1.2 the same way until release 1.3 listed it. The list is empty now and stays the one place where a system release may wait for its mapping release. Nothing else is excused.
- **The manifest.** `files` maps each file name to its SHA-256, taken over the LF-normalized bytes (the repository's canonical Git-content form, kept by `.gitattributes`). `checkedAgainst` lists what the release was built for, each with the hash of the file it stands on: the Missions dataset release 1.0 (its manifest), the Assets contract 1.1 (its file) and the Assets dataset release 1.1 (its manifest).
- **Immutability is checked twice.** The adapter refuses to start when a file differs from its hash, when a file is missing or unlisted, when the manifest names another release or when a folder is not named `MAJOR.MINOR`. A test hashes the real files against the manifest.
- **The checked-against rule.** The gate fails when a system file differs from the hash a release holds. The newest release must also name the newest Missions dataset release, Assets contract, Assets dataset release and Personnel v2 snapshot the repository holds; an older release is immutable and only has to stay true to what it lists. It surfaces the probable need for a new mapping release instead of leaving it to memory.

## The schema

The schema file is `src/main/resources/graphql/schema.graphqls`. It declares Federation 2.0 (`@link`) and uses `@key`, and `@inaccessible` on the two plain lookups and nowhere else.

- `AssetReference` (entity, `@key(fields: "localRef release")`): `localRef`, `release`, `assetId` and `mappingOutcome`. The Assets adapter declares both `@external` and uses `@requires(fields: "assetId mappingOutcome")` (experiment 2 used one field; two fields, one of them an enum from another subgraph, were tested under Apollo in the graph refinements Job). `mappingOutcome: MappingOutcome!` states what the mapping did, so that no owning adapter infers the cause from a null id: `MAPPED` (the release has an entry), `NO_ENTRY` (a valid release without an entry, or without a section for the kind, for example crew in release 1.0) or `RELEASE_REFUSED` (a blank or unknown release; the `MAPPING_RELEASE_REQUIRED` / `MAPPING_RELEASE_NOT_FOUND` errors entry stays and says which). The id was called `astId` until 2026-10-17. The mapping release is a key field and also the argument of the field that returns the references (`Mission.assets(release: String!)`, owned by the Missions adapter).
- `PersonnelReference` (entity, `@key(fields: "localRef release")`): `localRef`, `release` and `personnelId`, the Personnel v2 identifier from the `crew` section of the named release, or **null** when the release has no crew section (1.0) or no entry for the reference. It exists because the Personnel adapter declares `personnelId` `@external` and Federation composition then needs one subgraph that owns the field (`EXTERNAL_MISSING_ON_BASE` otherwise, found by the router Job). A crew reference keeps the release rules of an asset reference: a blank release is `MAPPING_RELEASE_REQUIRED` and an unknown one `MAPPING_RELEASE_NOT_FOUND`. The Personnel adapter turns the null into UNMAPPED.
- `Query.mappingReleases`: a diagnostic list of the releases served, with their sections and checked-against lists. It is not needed by the router.
- `Query.assetReferences(release: String!, localRefs: [ID!]!)` and `Query.personnelReferences(release: String!, localRefs: [ID!]!)`: the plain lookups, added 2026-10-21 for the Abstraction ladder study's adapters-only scenario (Gamma), where a client calls this adapter directly and `_entities` is not offered. Each gives, for every reference in the order given, the answer the entity gives: the same type (`AssetReference`, `PersonnelReference`), the same fields, the same `mappingOutcome` and the same release rules, from the same code. The release is always an argument (there is no implicit latest), and a call takes at most 100 references, the page limit of the other adapters' queries. The personnel lookup resolves crew references (`C-n`) from the crew section; it does not look up a participant reference (`P-n`, which the graph does not resolve yet, open question 77 of the federation design) and it refuses an outsider reference (`O-n`) by class ([D048](../../../project-governance/DECISIONS.md#d048---federation-mapping-of-the-missions-reference-classes-o-refused-by-class-and-p-to-non-crew-personnel-2026-10-19-accepted-scope)): both answer `NO_ENTRY` with the errors entry `MAPPING_CLASS_REFUSED`, which the entities never give. Both fields are `@inaccessible`, so they are left out of the supergraph's API schema: a router's graph is the one it served before them.

## Outcomes and errors

| Representation the router sends | Answer | Errors entry |
| --- | --- | --- |
| a reference with an entry in the named release | the entity with its `assetId` (or `personnelId` for a crew reference) | none |
| a reference with no entry in the named release | the entity with `assetId` null and `mappingOutcome` `NO_ENTRY` | none: UNMAPPED is data |
| a release that is missing, empty or blank | the entity with no id and `mappingOutcome` `RELEASE_REFUSED` | `MAPPING_RELEASE_REQUIRED` |
| a release that is not served (`2.0`, `latest`, `1`, ` 1.0`) | the entity with no id and `mappingOutcome` `RELEASE_REFUSED` | `MAPPING_RELEASE_NOT_FOUND` |
| a representation with no `localRef`, or another type | the call fails | `INTERNAL_SERVER_ERROR` |

There is no implicit latest and no partial match: the number is compared whole. One errors entry is made per distinct cause in one `_entities` call, not per representation. The other representations of the call still answer.

The plain lookups answer each reference as the table says and add three rows of their own:

| A lookup call with | Answer | Errors entry |
| --- | --- | --- |
| an outsider reference (`O-n`) in `personnelReferences` | the reference with no id and `mappingOutcome` `NO_ENTRY` | `MAPPING_CLASS_REFUSED` (refused by class) |
| a participant reference (`P-n`) in `personnelReferences` | the reference with no id and `mappingOutcome` `NO_ENTRY` | `MAPPING_CLASS_REFUSED` (not resolved by the graph) |
| more than 100 references | the list is null | `BAD_USER_INPUT` |

The release rules come first: a refused release gives `RELEASE_REFUSED` for every reference of the call, whatever its class. As in `_entities`, one errors entry is made per distinct cause, and the other references of the call still answer. A missing `release` argument is a validation error of the query and never an implicit latest.

What the adapter itself sees: the router rejects a query that gives `release: String!` no value or null before it reaches any subgraph, so the adapter never sees a null release from a client query. It does see an empty or blank string (`String!` accepts it) and a representation without the field when `_entities` is called directly; both are `MAPPING_RELEASE_REQUIRED`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAPPING_RELEASES_DIR` | `/app/mapping-releases` (the image) | The folder of the releases. The host has no default folder: set it. |
| `ADAPTER_PORT`, `ADAPTER_BIND_HOST` | 8190, 127.0.0.1 (0.0.0.0 in the image) | Where the adapter listens. |
| `MAPPING_ADAPTER_HOST_PORT` | 8190 | The loopback port compose publishes (`start.sh`, `compose.yaml`). |

No secret is needed or kept in any file.

## Run

Docker only; no JDK or Maven is needed on the machine. From Git Bash:

```sh
bash federation/adapters/mapping/start.sh start
```

`start.sh` refuses with one line when 127.0.0.1:8190 is taken (the Assets precedent), and never removes a container, an image or a volume. The container limits (1 CPU, 512 MB, read-only filesystem, no capabilities) are **provisional**, the same as the Assets adapter's: the limits of the adapters wait for the benchmark environment record.

## Versions and digests (resolved 2026-10-16)

The same as the Assets adapter, through the shared parent pom: Spring Boot 3.4.13, graphql-java held at 22.3, federation-graphql-java-support 5.4.0 (the lead developer stays on it until the other adapters exist), Java 21 on Temurin. No new dependency.

| Image | Digest |
| --- | --- |
| `maven:3.9-eclipse-temurin-21` | `sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| `eclipse-temurin:21-jre` | `sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef` |

Tags move; resolve the digests again before changing a pin.

## Validation

`validation/run_adapter_gate.py offline` is the only stage (there is no service behind the adapter) and fails closed (a skip, an empty suite or a missing Docker is a failure):

- the build stage of the Dockerfile runs `mvn verify`: the entity through `_entities` with the representations the router sends, UNMAPPED, the two release errors, the independence of releases on a second fake release, a release without an `assets` section, the crew references answered from the `crew` section of the named release (and null when it has none or has no entry), the loader's refusals, the hash of every real release file against its manifest, the ten crew references of release 1.1 as the crew mapping says, release 1.2 (its three sections, its 800 crew entries, its two participant entries and its checked-against list), the plain lookups (the entity's answer for a mapped and an unmapped reference in the order given, the crew section of the named release, the outsider and participant classes refused with one errors entry each, the release rules first, the release always an argument, at most 100 references, and release 1.3 itself) and the Federation features limited to `@key` and to `@inaccessible` on the two lookups;
- `test_release.py` checks the real releases against the repository: the file hashes, the checked-against lists (the newest release must name the newest version of every system artifact, the Personnel v2 snapshot included), release 1.0 byte for byte as published, the equality of `assets.json` with the expected mapping of the Assets dataset, and the equality of `crew.json` with what the crew mapping process builds from its pinned inputs (and the same checks on a temporary copy that is changed on purpose);
- `test_release_1_2.py` is the acceptance test of release 1.2, written by hand from the Missions recipe 1.1 and the pages of `personnel-v2-large-004`: the 800 crew references, the three unmapped, Guinan and Alexander among the participants, no entry for any O-reference, the controlled cases of the classes, and the checks on a temporary copy that is changed on purpose;
- `test_release_1_3.py` is the acceptance test of release 1.3, written by hand from the `participants.json` of Missions dataset release 1.2 and the pages of `personnel-v2-large-004`: every one of the 58 P-references resolved to the non-crew person of that exact name, no entry for any of the 153 O-references (the returning Wesley and Clara Sutter among them), the crew and assets sections equal to 1.2's, the controlled cases of the strict mode (a P that nobody places is a failure) and the checks on a temporary copy that is changed on purpose;
- `test_crew_mapping.py` is the acceptance test of the crew mapping: the expected table of the ten references written by hand from the released datasets, the migration reproducing `personnel-v2-small-003` byte for byte, and the controlled cases (a normal match, an exception match, a migrated person, an UNMAPPED reference, more than one match, a changed pin);
- the image, the compose file and the start script are checked and run on an ephemeral loopback port, and the running container answers with the real releases 1.0, 1.1, 1.2 and 1.3.

```sh
python -B federation/adapters/mapping/validation/run_adapter_gate.py offline
```

## Limits

Since 2026-10-19 the whole-stack default for Personnel is `personnel-v2-large-004` and the router acceptance asks release 1.3, built for Missions dataset release 1.2 (it asked 1.2 until the participants were reclassified; before that it was `personnel-v2-small-002` until the snapshot 003 and then 003; a crew reference mapped by release 1.1 to a migrated person resolves only when the Personnel service serves a snapshot that holds the person). The routers and the whole-stack compose are in `federation/routers/apollo` and `federation/stack`. The adapter folder builds from the `federation/` context. The Dockerfile copies the pom and the sources of every adapter, because the parent pom lists every module, so a later adapter changes the parent's module list and nothing in this folder. The profile `federation-adapter-runtime` runs the offline gates of the Assets, mapping and Missions adapters and the Assets service gate whichever federation path changes.
