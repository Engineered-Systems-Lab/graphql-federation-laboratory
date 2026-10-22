# Assets

Assets is the read-only REST/JSON service that owns the facts of starships,
shuttles, ground vehicles and equipment, on PostgreSQL. Normative authority is the
[Assets design](../../docs/ASSETS-V1-DESIGN.md). This component is at its fourth slice:
the executable contracts 1.0 and 1.1 with their examples and offline validator, the dataset releases 1.0 and 1.1
with their generator and offline checks, the read service with its PostgreSQL schema, load script and a gate
against a real disposable PostgreSQL 17 container, and its packaging: a Dockerfile, a compose file, a
start script and a packaging gate.

## What exists

- [Contract 1.0](contracts/assets-v1.0.openapi.json): OpenAPI 3.1 in one JSON file, with
  JSON Schema inside it. Settled on 2026-10-15 ([D036](../../governance/DECISIONS.md#d036---assets-contract-10-2026-10-15-accepted-scope)):
  a published contract file is never edited, and a compatible minor is a new file. It is stated in
  words and not yet marked `frozen`; that mark is planned for after the service exists.
- [Contract 1.1](contracts/assets-v1.1.openapi.json), the current contract and the one the service implements: a new
  immutable file beside 1.0 that gives Assets its own identifier (`AST-0017`: a prefix of capital letters, with single
  underscores allowed, a hyphen and a zero-padded number of at least four digits, one spelling each) and adds the error code
  PATH_NOT_FOUND, the 404 answer for a path outside the two paths (ASSET_NOT_FOUND keeps one meaning: a well-formed asset
  lookup that found nothing). The change of the identifier grammar is breaking and is made in 1.1 by an exception recorded once
  in [D038](../../governance/DECISIONS.md#d038---assets-contract-11-native-identifiers-and-path_not_found-2026-10-15-accepted-scope);
  the 1.0 file is unchanged. Its examples are in `fixtures/v1.1/valid` and `fixtures/v1.1/invalid`.
- Valid examples of 1.0 in `fixtures/valid`, for instance [a list page](fixtures/valid/asset-list.json): one JSON body per case, each linked from the contract
  by `externalValue`: an asset of each of the nine kinds (starship, shuttle, rover, armored vehicle, phaser, tricorder, communicator, scientific instrument and musical instrument), of each
  category and of each status, equipment with a parent, a list filtered by category, the list page, an empty
  list, a page beyond the end and each error.
- Invalid examples of 1.0 in `fixtures/invalid`, for instance [a lower-case identifier](fixtures/invalid/asset-invalid-id-lowercase.json): bodies the validator must reject, for a bad
  identifier, an unknown status, a missing or empty field, a parent that is not an
  identifier, an omitted parent, an extra member, a negative total, an unknown error code, a category that
  disagrees with the kind (a starship with the category EQUIPMENT and a phaser with the category VEHICLE), a missing category, the removed GROUND_VEHICLE kind, the renamed SHIP kind and the removed generic EQUIPMENT kind.
- [Validator](validation/validate.py) and its [JSON Schema subset checker](validation/jsonschema_subset.py):
  standard library only. The checker implements the keywords the contract uses and fails on
  any other.
- [Dataset release 1.0](datasets/releases/1.0/manifest.json), immutable like the Missions releases: 32 assets
  covering the nine kinds, in `assets.json`, with `provenance.json` (the controlled cases and the expected outcome
  of each of the nine ids that the released Missions dataset references), the `curation.json` it is derived from, its
  own `generate.py` and a manifest of content hashes. Never edited: a change is a new release folder.
  [`datasets/generate.py`](datasets/generate.py) writes a candidate release and a static, self-contained review page
  (`review --output <new folder>`), and publishes a release only with `release --lead-reviewed`. Releases 1.0 and 1.1 were
  published with the flag's earlier name, `--captain-reviewed`, which their own frozen copies of the generator keep.
- [Dataset release 1.1](datasets/releases/1.1/manifest.json), immutable and new: the same 32 assets as release 1.0 under native
  identifiers AST-0001 to AST-0032, assigned by a stated rule (the order of the release 1.0 identifiers, one step each), with
  the expected mapping from the nine Missions references to them written in `provenance.json` in three layers (what the mapping
  says, what Assets answers, what the consumer shows): five NORMAL, one DESTROYED, one MISSING, one MAPPED BUT NOT FOUND and
  one UNMAPPED. The mapping is not a field of the record and not a service. The `datasets/generate.py` and `curation.json` at
  this level are those of release 1.1.
- [Dataset validator](validation/validate_dataset.py): every record against the contract schema, the kind-to-category
  table, ids, parents (they exist, are vehicles, no cycle), the Missions cross-check (nine ids, 68 references, which
  resolve and which dangle against the expected outcomes), the manifest hashes and an exact regeneration of the
  release from its own curation file.
- Three test modules, [the checker](validation/test_jsonschema_subset.py),
  [the validator](validation/test_assets_contract.py) and [the dataset](validation/test_assets_dataset.py).

- [Schema](schema/schema.sql) for PostgreSQL 17: the `assets` table keyed by identifier with the grammar as a
  CHECK, the lookup tables `asset_kinds` (the one kind-to-category table of the service), `asset_categories` and
  `asset_statuses`, the view `asset_records` that derives the category, and the rules the contract cannot express
  (the parent exists, only a VEHICLE may be a parent, no cycle).
- [Load script](service/load_release.py): checks a release against its manifest and loads it deterministically.
- [Service](service/assets_service.py): `GET /assets/{assetId}` and `GET /assets`, Python standard library for
  HTTP and psycopg 3 for PostgreSQL ([logic](service/assets_logic.py), [database access](service/assets_store.py)).
  Pinned requirements are in [requirements.txt](service/requirements.txt).
- [Service gate](validation/run_service_gate.py) and [its suite](validation/runtime/service/test_service_gate.py):
  the service against a real disposable `postgres:17-bookworm` container pinned by digest.
  Unit tests that need no database: [service logic](validation/test_service_logic.py) and
  [the gate runner](validation/test_run_service_gate.py).

- [Dockerfile](Dockerfile), [.dockerignore](.dockerignore), [compose.yaml](compose.yaml),
  [.env.example](.env.example), [bootstrap](service/bootstrap.py) and [start.sh](start.sh): see Packaging below.
- [Packaging gate](validation/runtime/packaging/test_packaging.py) and [the start script's tests](validation/test_start_script.py).

## What does not exist

The federation, and any write endpoint. The service gate establishes the service on the Python that runs the gate
(not on Python 3.13 itself) against PostgreSQL 17; the packaging gate runs it on Python 3.13 in the image.

## Packaging

One command starts the service with its database, from the committed files, on loopback, with the dataset
release 1.1 loaded. From Git Bash at the repository root:

```sh
export ASSETS_DB_ADMIN_PASSWORD='<your choice>' ASSETS_DB_SERVICE_PASSWORD='<your choice>'   # see .env.example
bash uss-enterprise/assets/start.sh start      # the service answers on 127.0.0.1:8084
bash uss-enterprise/assets/start.sh status
bash uss-enterprise/assets/start.sh stop       # 60 seconds for the database; containers and data are kept
```

`start.sh --dry-run <command>` checks the port and prints the command it would run. The script never removes a
container, an image or a volume. Resetting the data is your own command: `docker compose -f
uss-enterprise/assets/compose.yaml down --volumes`. The files are `Dockerfile` (one stage), `compose.yaml` and the
one-shot `service/bootstrap.py`. After a change of code, `docker compose -f uss-enterprise/assets/compose.yaml build`
refreshes the image before the next start. The executable bit cannot be set through the governed staging on this
machine (`core.filemode` is false and every committed script is mode 100644), so the script is run with `bash`.

- **Containers.** `database` (`postgres:17-bookworm`), `bootstrap` (the service image, one-shot) and `assets` (the
  service). The database is published nowhere: only the containers of the project reach it. The service is published on
  `127.0.0.1:8084` only (`ASSETS_HOST_PORT` changes the host port). The image runs as the user `10001:10001` and holds
  only the service code, the schema, the load script, the contract 1.1 the load script checks and release 1.1: no tests and
  no credentials. The service containers have a read-only root file system and no capabilities.
- **Environment.** `ASSETS_DB_ADMIN_PASSWORD` and `ASSETS_DB_SERVICE_PASSWORD` are required, with no default: compose
  refuses to start without them. The administrator password reaches only the database (the first time it initialises its
  volume) and the bootstrap container; the service holds only the read-only login `assets_service`, whose password the
  bootstrap sets on every start. Optional: `ASSETS_HOST_PORT`, `ASSETS_IMAGE`, `ASSETS_CONTAINER_NAME`,
  `ASSETS_DB_IMAGE`, `ASSETS_DB_CONTAINER_NAME` and `COMPOSE_PROJECT_NAME`. A changed administrator password needs a reset
  of the volume.
- **Bootstrap, idempotent.** With no schema it applies the schema and loads the release; with a schema and no assets it
  loads the release; with assets present it verifies that they are exactly the release and changes nothing. A difference
  is a failure, not a repair. So a second start duplicates nothing.
- **Data.** A named volume (`assets-pgdata`) keeps the data between a stop and a start, which is what makes the second
  start worth checking. The dataset release stays the source of truth and the volume is disposable.
- **Limits.** Explicit CPU and memory limits, memory and swap alike, so that every run starts from the same
  conditions: database 1 CPU and 512 MB, service 0.5 CPU and 256 MB, bootstrap 0.5 CPU and 256 MB. The machine has
  15.6 GB of RAM (32 GB expected). The benchmark design (the Job `benchmark_environment`) wants the machine facts and
  these limits in every run manifest.
- **The port rule.** One copy of the service runs at a time, and every start checks that its port is free: a connect
  attempt on 127.0.0.1 (Windows lets a second listener bind a taken port without an error, so a bind is not a test) and
  one clear refusal line when the port is taken. A different service keeps its own port (Personnel 8082, Missions 8083,
  Assets 8084).
- **Pinned images.** Both bases are pinned by the digest of their OCI image index, resolved on 2026-10-15 with
  `docker buildx imagetools inspect`: `python:3.13-slim-bookworm` is
  `sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641` and `postgres:17-bookworm` is
  `sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826`. Tags move: resolve again before changing
  a pin and record the date. The dependencies are pinned in [requirements.txt](service/requirements.txt).

## Run the packaging gate

Needs Docker and Compose, from Git Bash at the repository root:

```sh
python -B uss-enterprise/assets/validation/run_service_gate.py packaging
```

It builds the image from the committed files, starts the stack on an ephemeral loopback port with random
credentials and a unique project name, runs the HTTP checks of the service gate against the published service,
checks the non-root user, the image contents, the publication, the limits, the second start and the clean
teardown, and removes only what it created. A missing Docker is a failure, never a skip.

## Run the validator

From the repository root, in Git Bash, with Python 3.13 or later:

```sh
python -B uss-enterprise/assets/validation/validate.py
python -B uss-enterprise/assets/validation/validate_dataset.py
python -B governance/tools/run_tests.py -s uss-enterprise/assets/validation -p 'test_*.py' -v
```

The first prints `PASS` and the limits of what it establishes, or `FAIL` with the first
violation, and exits non-zero. Neither needs Docker, a database or a network.

## Run the service gate

Needs Docker running and the pinned driver installed in the Python you run it with, from Git Bash at the repository root:

```sh
python -m pip install -r uss-enterprise/assets/service/requirements.txt
python -B uss-enterprise/assets/validation/run_service_gate.py
```

The gate pulls the pinned image on first use (the index digest of `postgres:17-bookworm`, resolved on
2026-10-15), starts one container bound to loopback on an ephemeral port with a random password from
the process environment, and always removes it. A missing Docker, image or driver is a failure, never a
skip. It does not touch any other container.

## Run the service locally

Create an empty database, apply the schema, load the release and start the service. The database login
comes only from the libpq environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`):
use an administrative login for the first two steps and the read-only login for the service.

```sh
python -B uss-enterprise/assets/service/load_release.py --with-schema
```

Then, as an administrator, create the service's login (the password comes from your environment, never from
a file) and start the service with that login in the environment:

```sql
CREATE ROLE assets_service LOGIN PASSWORD '<from the environment>' IN ROLE assets_reader;
ALTER ROLE assets_service SET default_transaction_read_only = on;
```

```sh
python -B uss-enterprise/assets/service/assets_service.py
```

It listens on 127.0.0.1:8084 (`ASSETS_HOST` and `ASSETS_PORT` or `--host` and `--port` change that) and
prints `LISTENING <host>:<port>`.
