# Federation whole-stack compose

The definition that runs the whole federation layer on one machine: the Apollo router, the four adapters (missions, mapping, assets and personnel) and the backends behind them. The router, its configuration and the composition of the supergraph are in [the Apollo router folder](../routers/apollo/README.md); this folder holds the compose file, its start script and the stub of the Missions service.

## Modes

- **Stub-backend mode (this folder).** Runs without Oracle. The Assets service (the real one, with its own PostgreSQL 17, loaded from the Assets dataset release 1.1) and the Personnel v2 service (the real one, no database, serving the snapshot `personnel-v2-large-004` by default: 1,000 people in ten pages of 100) are the real services. The Missions service is replaced by `missions-stub/server.py`, a tiny stub that serves the **released Missions dataset 1.2** (`uss-enterprise/missions/datasets/releases/1.2`, 300 missions in six pages of 50) with the contract's read operations, filters, paging and error bodies. The stub is not the Missions service; it makes no claim about the service's Oracle-backed behavior.
- **Real-service mode (not in this folder).** The real Missions service on Oracle (about 9 GB, minutes to start). Start it as its own component and give the Missions adapter its address through `MISSIONS_SERVICE_URL`. It is optional and was **not run** by the Job that wrote this folder.

## Ports (all on 127.0.0.1)

| Port | What |
| --- | --- |
| 8170 | The Apollo router (the one GraphQL endpoint) |
| 8171 | The Cosmo router (`FEDERATION_ROUTER=cosmo`; one router at a time) |
| 8182 | Personnel adapter |
| 8183 | Missions adapter |
| 8184 | Assets adapter |
| 8190 | Mapping adapter |

The backends (the Assets service and its database, the Personnel v2 service, the Missions stub) are published nowhere: only the other containers of the project reach them. 8180 stays free. Every start checks the five ports and refuses with one line when one is taken.

## Run

Docker only; no JDK, Maven or Node is needed on the machine. From Git Bash, with Docker running:

```sh
APOLLO_ELV2_LICENSE=accept bash federation/stack/start.sh start
```

`start.sh` builds the images, starts the backends and the four adapters, composes the supergraph from the adapters' own SDL with Rover into `federation/routers/apollo/supergraph.graphql` (a build product that is checked in: if a schema changed, `git diff` shows the change of the composition), and then starts the router. `APOLLO_ELV2_LICENSE=accept` is **your** acceptance of the Elastic License 2.0 of Rover's composition plugin; the script refuses without it. `start.sh stop` stops the containers and keeps them; `start.sh status` lists them. The script never removes a container, an image or a volume: to discard the stack, run `docker compose -f federation/stack/compose.yaml down --volumes` yourself.

Database credentials are random for the run unless `STACK_ASSETS_DB_ADMIN_PASSWORD` and `STACK_ASSETS_DB_SERVICE_PASSWORD` are set; none is kept in any file. The container limits are **provisional**, as in the adapters: the limits wait for the benchmark environment record.

## Acceptance

The router-neutral acceptance suite ([federation/acceptance](../acceptance/README.md)) runs against this stack through a router's address, for the Apollo router and for the Cosmo router. Its controlled cases stop and start the compose services `assets-service`, `assets-adapter`, `mapping-adapter` and `personnel-adapter` of this file, and restart the router service; the router's own test module supplies those calls.

## The Cosmo router

The Cosmo router ([README](../routers/cosmo/README.md)) is the service `cosmo-router` of the same compose file, under the compose profile `cosmo`, so a plain `docker compose` run is the Apollo stack as before and the Cosmo router is started by name with the profile. One router runs at a time; they share the four adapters and the backends. From Git Bash, with Docker running:

```sh
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh start
```

The script starts the same backends and adapters, composes the execution config with `wgc` into `federation/routers/cosmo/execution-config.json` (a build product that is checked in) and starts the Cosmo router on 127.0.0.1:8171. No license acceptance is needed. `stop` and `status` take the same switch. Because the Apollo router stays in the file, compose still asks for `SUPERGRAPH_FILE` when it reads it, which the script sets whatever the router.

## The large data

Since 2026-10-19 the stack serves the large data by default: Missions dataset release 1.1 (300 missions in six pages of 50), the Personnel v2 snapshot `personnel-v2-large-004`, and the acceptance suite asks mapping release 1.2 and pages every whole-list check (the graph's limit is at most 100, so three pages). Until then the default was the small data (Missions release 1.0 with 31 missions and the snapshot `personnel-v2-small-003`); the second compose file that opted in to release 1.1 was removed because 1.1 is now the default. The Missions stub takes the release folder, joins the numbered pages and lists the missions in the contract's order (stardate, priority, missionId); given a single file it still serves that file (release 1.0). `STACK_PERSONNEL_DATASET_VERSION` selects another registered snapshot. The expected outcomes of the acceptance suite are derived from the large data by `federation/acceptance/derive_expected.py`.

Since 2026-10-20 the default is Missions dataset release 1.2 (the same 300 missions with their participants reclassified as P and O; the stub serves the release folder unchanged) and the acceptance suite asks mapping release 1.3. The expected outcomes are derived again from them.

## Images

The images the compose file does not build are pinned by digest, resolved on 2026-10-16: the router `ghcr.io/apollographql/router` v2.18.0, `python:3.13-slim-bookworm` (the Missions stub) and `postgres:17-bookworm`; the Cosmo router `ghcr.io/wundergraph/cosmo/router` 0.359.0 was resolved on 2026-10-18. The adapters and the two real services are built from their own Dockerfiles with their own pinned bases. Tags move: resolve the digests again before changing a pin.
