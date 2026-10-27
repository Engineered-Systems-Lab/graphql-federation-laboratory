# GraphQL Federation Laboratory

A governed laboratory that federates heterogeneous legacy systems (SOAP/XML, REST/JSON, Oracle, PostgreSQL) behind one GraphQL graph with Apollo and Cosmo, and tests whether higher levels of abstraction give AI agents better tools for cross-system questions.

## What the laboratory holds

- **Legacy systems** of a fictional enterprise, each with its own technology and its own idea of the data: Personnel (Java, SOAP/XML), Missions (Java, REST/XML on Oracle) and Assets (REST/JSON on PostgreSQL), with versioned, hash-pinned datasets. Crew & Personnel v1, the first Personnel service, is kept frozen as a reference and is deprecated.
- **A GraphQL federation layer**: one adapter per system and a shared identity mapping, composed into one supergraph and served by the Apollo Router and by WunderGraph Cosmo, checked against one shared acceptance suite.
- **The Abstraction ladder study** ("The Abstraction Ladder: Evaluating AI-Agent Access to Legacy Systems"): AI agents answer the same cross-system questions through the raw systems, the raw systems with a written guide, the adapters alone, and the federated graph through each router. Study 1 is reported with its scored results and checksums.
- **A governance framework** for work by a human lead developer and AI agents together: a sealed checkpoint workflow with one person's exact approval, transaction-owned worktrees, a classification of every path, continuity checks, decision registries and a read-only Mission Control terminal. Start at [Project lifecycle](governance/PROJECT-LIFECYCLE.md); agents start at [AGENTS.md](AGENTS.md).

## Architecture in short

The legacy systems live in `uss-enterprise/` and know nothing of GraphQL, federation or AI: the integration adapts to them, never the other way round. Each system keeps its own identifiers and meanings. The federation layer in `federation/` puts one Java adapter in front of each system (Missions, Assets, Personnel) and one more for the shared external-ID mapping, which owns the versioned mapping releases that say which Missions reference names which asset or person. The four adapters are subgraphs of one supergraph, served by either router, one at a time. The study in `study/` puts AI agents on top of each level of that ladder through local MCP servers. The whole picture, with the logical boundaries and the controlled failures, is in [Architecture](docs/ARCHITECTURE.md); the federation itself is in [the federation design](docs/FEDERATION-DESIGN.md).

## Prerequisites

- **Git**, and on Windows **Git Bash** for every shell command in this repository.
- **Python 3.13 or later** for the governance tools, the gates and the study's offline tests.
- **Docker with Docker Compose** for the services, the federation stack and the stack gates. The Java services and adapters are built inside their images, so the stack needs no JDK or Maven on the machine.
- **A JDK and Maven** only for local Java builds outside Docker (JDK 17 for the legacy Java services, JDK 21 for the adapters; Maven 3.9 or later).
- **Node.js** only for the Mission Control terminal checks.
- **The study environment** only for the study's MCP part and its analysis: a Python with the study's pinned packages (`mcp` for the MCP servers, `statsmodels` and `scipy` for the analysis), named by the machine-local variable `STUDY_MCP_PYTHON`. Scored runs also need the vendors' API keys, from the environment only.

## Starting the stack

The whole federation layer runs on one machine in stub-backend mode, with no Oracle: the real Assets service on PostgreSQL, the real Personnel v2 service, a stub that serves the released Missions dataset, the four adapters and one router, all on loopback. One router runs at a time, because the two share the adapters' ports: start one of the two below, and stop it before starting the other. From Git Bash, with Docker running.

With the Apollo router, on 127.0.0.1:8170:

```sh
APOLLO_ELV2_LICENSE=accept bash federation/stack/start.sh start
```

and to stop it:

```sh
bash federation/stack/start.sh stop
```

Or with the Cosmo router, on 127.0.0.1:8171:

```sh
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh start
```

and to stop it:

```sh
FEDERATION_ROUTER=cosmo bash federation/stack/start.sh stop
```

**The ELv2 note:** the Apollo Router and Apollo's composition library are under the Elastic License 2.0; `APOLLO_ELV2_LICENSE=accept` is your own acceptance of it for Rover's composition plugin, and the script refuses an Apollo start without it. Cosmo needs no license acceptance and no account. `stop` keeps the containers, and the Assets data lives only while its database container runs, so the next start loads it again. Ports, data and images are in [the stack README](federation/stack/README.md).

## Demonstrations

- **The cross-system questions.** The router-neutral [acceptance suite](federation/acceptance/README.md) asks questions 2 to 6 of the federation design through a router (which missions used a destroyed or missing asset, which have unresolved assets, the parent chain of an asset in one query, a mission that still answers with partial data while the Assets service is down, and how many missions are confirmed with a senior officer among their crew) and runs the controlled cases: an outage of the Assets service, dead adapters and the recovery when they come back, each answered with errors entries beside the data that is still there, never with a guess. The stack gates below run it against each router on a disposable stack.
- **The Abstraction ladder study.** The [study](study/README.md) holds the task corpus, the MCP servers, the harness, the written guide, the analysis and the compact evidence; the results are in [the study report](docs/AGENT-STUDY-REPORT.md).

## Validation

Each command runs from the repository root in Git Bash; its result is what it prints.

| Check | Command |
| --- | --- |
| Continuity (documents, links, records, frozen files) | `python -B governance/tools/validate_continuity.py` |
| The full governance suite | `python -B governance/tools/run_tests.py -s governance/tests -s governance/config -p 'test_*.py'` |
| The Apollo router gates, offline and on a disposable stack | `python -B federation/routers/apollo/validation/run_router_gate.py offline` and `APOLLO_ELV2_LICENSE=accept python -B federation/routers/apollo/validation/run_router_gate.py stack` |
| The Cosmo router gates | `python -B federation/routers/cosmo/validation/run_router_gate.py offline` and `python -B federation/routers/cosmo/validation/run_router_gate.py stack` |
| The study gate (offline; the MCP part runs under `STUDY_MCP_PYTHON`, `--require-mcp` makes its absence a failure) | `python -B study/harness/study_gate.py` |
| The analysis reproduction (needs the raw run bundles) | the command in [the analysis README](study/analysis/README.md#running-it) |

The gates of every other component are named in the project's checkpoint policy (`project-governance/config/checkpoint-policy.json`) and in each component's README.

## Limitations

- In study 1 and gamma-prime-1, the study's Missions was a simulator, not the Oracle-backed Missions service ([the report's correction](docs/AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed)).
- The stack's default Missions is a stub serving the released dataset; the real-service mode (Missions on Oracle) has not been run in this repository.
- The raw study bundles stay outside the repository and are cited by checksum, so the analysis cannot be reproduced without them.
- The container limits are provisional: they wait for the benchmark environment record.
- Crew & Personnel v1 is frozen and deprecated: it stays readable and runnable as a reference, and no new work builds on it.
- The original lab repository's own full and runtime test suites were not run at the commit this repository was imported from; the results here come from this repository's own checks.
- Dataset 003 of Crew & Personnel v1 is not regenerated in this repository; its released package is the reference.
- The MCP part of the study gate needs the study environment.

## History and provenance

The laboratory was developed first in a private repository (the "lab"), which remains its archive. This repository was started from the governance template at template commit `733f65a11f2d2639c7015f6c4b491712773db50a` and receives the lab's content as it stood at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`. The lab's Git history is not carried: commits of the lab or of the template are cited as `lab commit <id>` or `template commit <id>` and are never presented as commits of this repository. Development log entries migrated from the lab keep their original dates and say so. Files released before the migration call the lead developer "the Captain".

The governance framework was taken in these commits of this repository:

| Framework release | Taken in commit | From |
| --- | --- | --- |
| Template 0.2.0 | `8e5ad2e1372d4f75da9a47a89a5d20569258917e` (the start) | template commit `733f65a11f2d2639c7015f6c4b491712773db50a` |
| Template 0.2.2 | `a9f7cb0e1e4c35ea86d59dc0af8fb029701824aa` | template commit `b855b24347e40af711e32b4607d93f131cf27b20` |
| Template 0.2.3 | `d99e64fec7373104963d1c2874e0fab699ba91b1` | template commit `bb721a95b04d2398dc2c912e2ed6e97b25c1efc5` |
| Comitas 0.3.1 | `5187f6fd58ba7a40cd00f7e31266a2b05ca48593` | comitas commit `74091f01d1671ebd9e84642ce21f82bec570f620` |
| Comitas 0.4.0 | `2c47271ca319319e804c3867dbd04241f8ecf233` | comitas commit `c789d56f562721aa38a600c253c6e3d0a1a416c0` |
| Comitas 0.5.0 | `0dfb47dca9b9fe7f59caf6bf0f2538bff38e16b3` | comitas commit `77cf783c26fdc080863e263e04b37b8f8957f1bf` |
| Comitas 0.5.3 | `11c0bdefd5c968b522d0af8e2a46d64c877f9b3f` | comitas commit `1ba8333f7c55c1195d7ea9fff61eea9b58fbbd46` |
| Comitas 0.6.1 | `3fdb0d5bdd44faa98ca833113a10a7b00a173eb5` | comitas commit `86417dc6f66f3f364774d0697a53c2c5f3e49462` |
| Comitas 0.6.2 | `b52f9affb1709e550ed2a8a9bdfb70d022b9f559` | comitas commit `09d433ebaacbbd8a76a2935551a0eb885d196f87` |
| Comitas 0.7.0 | `0aaf56c0b040b642fb382f75741ee61b81e47973` | comitas commit `b3c928347b8c58fa7b6f2f9e8d1084123e4018a0` |

## License

Copyright (c) 2026 Gustavo Cavallin. Two sets of terms apply, by file:

- **The governance framework**: everything retained from the template, which is `governance/` and the starter files of the template that remain in this repository, is licensed under the PolyForm Noncommercial License 1.0.0 ([LICENSE](LICENSE), with its Required Notice in the first line; [governance/NOTICE](governance/NOTICE) for copies of `governance/`).
- **Everything else** (the legacy systems, the federation layer, the study, the documents, the development log and the project's own governance files): all rights reserved, except this **evaluation permission**: anyone, including prospective employers and clients, may view this repository, build it and run it locally to evaluate the author's work. The permission does not include copying, redistribution, modification for another use, offering it as a service, or any commercial use.

Third-party software and material keep their own licenses (see below). This summary is not legal advice.

## Third-party and fan material

- **Star Trek.** This is an independent fan and learning project. Star Trek and all related names, characters, ships, episodes and marks belong to their owners; the project is not affiliated with or endorsed by them. The enterprise, its crew records, missions and assets are fictional data built for testing.
- **Memory Alpha.** Some mission facts are paraphrased in the project's own words from [Memory Alpha](https://memory-alpha.fandom.com/), whose text is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/); each such record keeps its `sourceUrl` link to the page it came from.
- **Software.** Third-party components keep their own licenses. The two routers: the Apollo Router and Apollo's composition library are under the Elastic License 2.0 (ELv2), source-available but not open source, and Apollo's subgraph library is under MIT; WunderGraph Cosmo (the router and its `wgc` tool) is under the Apache License 2.0 at the pinned version. The other libraries and base images are pinned in each component's build files (its `pom.xml`, `Dockerfile` or `requirements.txt`, and the stack's `compose.yaml`) and keep their own licenses.
