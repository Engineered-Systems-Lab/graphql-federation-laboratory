# Federation whole-stack compose

The definition that runs the whole federation layer on one machine: a router (Apollo or Cosmo), the four adapters (missions, mapping, assets and personnel) and the backends behind them. This folder holds the compose file, its start script and the stub of the Missions service. The routers, their configuration and their composition are in [the Apollo router folder](../routers/apollo/README.md) and [the Cosmo router folder](../routers/cosmo/README.md).

## What runs

This folder is the **stub-backend mode**: it runs without Oracle.

| Service | What it is | Data it serves |
| --- | --- | --- |
| `router` or `cosmo-router` | The Apollo router v2.18.0 or the Cosmo router 0.359.0, one at a time | the composed graph of the four adapters |
| `missions-adapter`, `assets-adapter`, `personnel-adapter`, `mapping-adapter` | The four subgraphs (Java 21 adapters) | the mapping adapter serves the mapping releases 1.0 to 1.3 |
| `missions-stub` | A tiny stub in place of the Missions service | Missions dataset release **1.2** (300 missions, six pages of 50) |
| `assets-service` with `assets-db` and `assets-bootstrap` | The real Assets read service on its own PostgreSQL 17 | Assets dataset release **1.1** |
| `personnel-service` | The real Personnel v2 SOAP service, with no database | the snapshot **`personnel-v2-large-004`** (1,000 people in ten pages of 100) |

The acceptance suite asks mapping release **1.3**. The Missions service is replaced by `missions-stub/server.py`, a tiny stub that serves the **released Missions dataset 1.2** (`uss-enterprise/missions/datasets/releases/1.2`) with the contract's read operations, filters, paging and error bodies. The stub is not the Missions service; it makes no claim about the service's Oracle-backed behavior.

The **real-service mode** is not in this folder: the real Missions service on Oracle (about 9 GB, minutes to start) is started as its own component, and the Missions adapter is given its address through `MISSIONS_SERVICE_URL`. It is optional and has not been run in this repository.

Everything is published on 127.0.0.1 only:

| Port | What |
| --- | --- |
| 8170 | The Apollo router (the one GraphQL endpoint) |
| 8171 | The Cosmo router (`FEDERATION_ROUTER=cosmo`; one router at a time) |
| 8182 | Personnel adapter |
| 8183 | Missions adapter |
| 8184 | Assets adapter |
| 8190 | Mapping adapter |

The backends (the Assets service and its database, the Personnel v2 service, the Missions stub) are published nowhere: only the other containers of the project reach them. 8180 stays free. Every start checks the five ports of its router and refuses with one line when one is taken.

## Prerequisites

- **Docker with Docker Compose**, running. The images of the adapters and of the two real services are built by `start.sh` from their own Dockerfiles, so no JDK, Maven or Node is needed on the machine.
- **Bash**: on Windows, Git Bash. The script uses Bash's `/dev/tcp` for the port check.
- **Python 3.13 or later** on the path as `python` (or named by `PYTHON`): `start.sh` runs the composition scripts with it, and they run Rover or `wgc` in Docker images they build.
- **`curl`** for the verification query below (Git Bash has it).
- **For an Apollo start only**, your acceptance of the Elastic License 2.0 (below).

## Quickstart

From the repository root, in Git Bash, with Docker running. With the Apollo router:

```sh
APOLLO_ELV2_LICENSE=accept bash federation/stack/start.sh start
```

With the Cosmo router instead (no license acceptance, no account and no token):

```sh
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh start
```

`start.sh start` builds the images, starts the backends and the four adapters, composes the graph from the adapters' own SDL and then starts the router, waiting until each service is healthy. For Apollo it composes the supergraph with Rover into `federation/routers/apollo/supergraph.graphql`; for Cosmo, the execution config with `wgc` into `federation/routers/cosmo/execution-config.json`. Both are build products that are checked in: when a schema changed, `git diff` shows the change of the composition, and otherwise the file is unchanged. `APOLLO_ELV2_LICENSE=accept` is **your** acceptance of the Elastic License 2.0 of Rover's composition plugin; the script refuses an Apollo start without it. `--dry-run` checks the ports and prints the commands it would run, and runs nothing.

## Verification

One query that crosses three services: a mission from the Missions stub, its asset references resolved through mapping release 1.3, and the parent chain of an asset from the Assets service on PostgreSQL. Through the Apollo router:

```sh
curl -s http://127.0.0.1:8170/ -H 'Content-Type: application/json' -d '{"query":"{ mission(missionId: \"ST-00000LDBE\") { missionId assets(release: \"1.3\") { localRef mappingOutcome asset { assetId parent { assetId parent { assetId } } } } } }"}'
```

Through the Cosmo router, the same query on its own address:

```sh
curl -s http://127.0.0.1:8171/graphql -H 'Content-Type: application/json' -d '{"query":"{ mission(missionId: \"ST-00000LDBE\") { missionId assets(release: \"1.3\") { localRef mappingOutcome asset { assetId parent { assetId parent { assetId } } } } } }"}'
```

Both routers answer with exactly this JSON, with no `errors` entry:

```json
{"data":{"mission":{"missionId":"ST-00000LDBE","assets":[{"localRef":"EQ-64","mappingOutcome":"MAPPED","asset":{"assetId":"AST-0004","parent":{"assetId":"AST-0023","parent":{"assetId":"AST-0029"}}}},{"localRef":"VS-31","mappingOutcome":"MAPPED","asset":{"assetId":"AST-0029","parent":null}}]}}}
```

The mission's asset reference `EQ-64` is mapped to `AST-0004`, whose parent is `AST-0023`, whose parent is `AST-0029`; its other reference, `VS-31`, is mapped to `AST-0029`, the top of the chain, which has no parent. The whole acceptance suite runs through the router gates, each on a disposable stack of its own ([the acceptance suite](../acceptance/README.md)).

## Status, stop and reset

```sh
bash federation/stack/start.sh status
bash federation/stack/start.sh stop
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh status
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh stop
```

`status` lists the containers (`docker compose ps`). `stop` stops them and keeps them. Run the Cosmo forms for a Cosmo stack, so that the `cosmo` profile is included. The script never removes a container, an image or a volume.

**The data.** The Assets database keeps its data in memory: a `tmpfs` of 128m at the data directory of the PostgreSQL image (`/var/lib/postgresql/data`), counted within the database container's limit of 512 MB. So the data lives only while the database container runs: after `stop`, the next `start` initializes the database again and loads the Assets dataset release 1.1, and a second and every later start of the same project succeeds with new random credentials. Database credentials are random for the run unless `STACK_ASSETS_DB_ADMIN_PASSWORD` and `STACK_ASSETS_DB_SERVICE_PASSWORD` are set; the scripts create no credentials file. To reset the data, stop and start again.

**Removing the stack** is your command, not the script's. Compose reads the whole file, so it needs the variables the file requires, set here to placeholders because `down` reads no supergraph and uses no password, and the `cosmo` profile so that a Cosmo router container is removed too. Run it with the same `COMPOSE_PROJECT_NAME` as the start, if you set one:

```sh
SUPERGRAPH_FILE=./unused STACK_ASSETS_DB_ADMIN_PASSWORD=unused STACK_ASSETS_DB_SERVICE_PASSWORD=unused docker compose -f federation/stack/compose.yaml --profile cosmo down --volumes
```

It removes the project's containers, its network and any volume of the project; the images stay.

## Configuration

All settings are environment variables of `start.sh` (`bash federation/stack/start.sh --help` lists them):

| Variable | Default | What it does |
| --- | --- | --- |
| `FEDERATION_ROUTER` | `apollo` | `apollo` or `cosmo`; one router at a time |
| `APOLLO_ELV2_LICENSE` | unset | `accept` is needed for an Apollo start |
| `COMPOSE_PROJECT_NAME` | `starfleet-federation-stack` | the compose project; give the same name to `status`, `stop` and the removal |
| `ROUTER_HOST_PORT`, `COSMO_ROUTER_HOST_PORT` | 8170, 8171 | the router's port |
| `PERSONNEL_ADAPTER_HOST_PORT`, `MISSIONS_ADAPTER_HOST_PORT`, `ASSETS_ADAPTER_HOST_PORT`, `MAPPING_ADAPTER_HOST_PORT` | 8182, 8183, 8184, 8190 | the adapters' ports |
| `SUPERGRAPH_FILE`, `EXECUTION_CONFIG_FILE` | the committed files | where the composition is written and read from |
| `STACK_ASSETS_DB_ADMIN_PASSWORD`, `STACK_ASSETS_DB_SERVICE_PASSWORD` | random for the run | the Assets database credentials |
| `STACK_PERSONNEL_DATASET_VERSION` | `personnel-v2-large-004` | another registered Personnel v2 snapshot |
| `MISSIONS_SERVICE_URL` | the stub | the real-service mode |
| `PYTHON` | `python` | the interpreter of the composition scripts |

Because the Apollo router stays in the compose file, compose asks for `SUPERGRAPH_FILE` whenever it reads the file, even for a Cosmo run; the script sets it whatever the router.

The images the compose file does not build are pinned by digest, resolved on 2026-10-16: the router `ghcr.io/apollographql/router` v2.18.0, `python:3.13-slim-bookworm` (the Missions stub) and `postgres:17-bookworm`; the Cosmo router `ghcr.io/wundergraph/cosmo/router` 0.359.0 was resolved on 2026-10-18. The adapters and the two real services are built from their own Dockerfiles with their own pinned bases. Tags move: resolve the digests again before changing a pin.

## Limitations

- The Missions service is a stub serving the released dataset; the real-service mode (Missions on Oracle) has not been run in this repository.
- The container limits are **provisional**, as in the adapters: the limits wait for the benchmark environment record.
- One router runs at a time; the two share the four adapters and the backends.
- The Assets data does not survive a stop of its database container, by design (see the data, above).

## History

- **2026-10-19:** the stack served the large data by default: Missions dataset release 1.1 (300 missions in six pages of 50), the Personnel v2 snapshot `personnel-v2-large-004`, and the acceptance suite asked mapping release 1.2 and paged every whole-list check (the graph's limit is at most 100, so three pages). Until then the default was the small data (Missions release 1.0 with 31 missions and the snapshot `personnel-v2-small-003`); the second compose file that opted in to release 1.1 was removed because 1.1 became the default. The Missions stub takes the release folder, joins the numbered pages and lists the missions in the contract's order (stardate, priority, missionId); given a single file it still serves that file (release 1.0).
- **2026-10-20:** the default became Missions dataset release 1.2 (the same 300 missions with their participants reclassified as P and O; the stub serves the release folder unchanged), and the acceptance suite asks mapping release 1.3. The expected outcomes were derived again from them by `federation/acceptance/derive_expected.py`.
- **2026-10-26:** the Assets database moved to memory, so that a second start of the same project succeeds with new random credentials; before, its data stayed in an anonymous volume that rejected the new password.
