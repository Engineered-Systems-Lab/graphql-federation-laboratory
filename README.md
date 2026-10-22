# GraphQL Federation Laboratory

A governed laboratory that federates heterogeneous legacy systems (SOAP/XML, REST/JSON, Oracle, PostgreSQL) behind one GraphQL graph with Apollo and Cosmo, and tests whether higher levels of abstraction give AI agents better tools for cross-system questions.

## Status

This repository is being assembled. It starts from a governance template and receives the laboratory's content in slices, each one checked before the next:

| Part | State |
| --- | --- |
| Governance framework (`governance/`, `project-governance/`) | in place, from the template |
| Legacy systems (`uss-enterprise/`) | to be imported |
| GraphQL federation (`federation/`) | to be imported |
| Project decisions, rules and rationale (`project-governance/`) | to be imported |
| Design and status documents (`docs/`) | to be imported |
| The Abstraction ladder study (`study/`) | to be imported |
| Development log (`devlog/`) | to be imported |

This section is updated as each part lands.

## What the laboratory holds

- **Legacy systems** of a fictional enterprise, each with its own technology and its own idea of the data: Personnel (Java, SOAP/XML), Missions (Java, REST/XML on Oracle) and Assets (REST/JSON on PostgreSQL), with versioned, hash-pinned datasets. Crew & Personnel v1, the first Personnel service, is kept frozen as a reference and is deprecated.
- **A GraphQL federation layer**: one adapter per system and a shared identity mapping, composed into one supergraph and served by the Apollo Router and by WunderGraph Cosmo, checked against one shared acceptance suite.
- **The Abstraction ladder study** ("The Abstraction Ladder: Evaluating AI-Agent Access to Legacy Systems"): AI agents answer the same cross-system questions through the raw systems, the raw systems with a written guide, the adapters alone, and the federated graph through each router. Study 1 is reported with its scored results and checksums.
- **A governance framework** for work by a human lead developer and AI agents together: a sealed checkpoint workflow with one person's exact approval, transaction-owned worktrees, a classification of every path, continuity checks, decision registries and a read-only Mission Control terminal. Start at [Project lifecycle](governance/PROJECT-LIFECYCLE.md); agents start at [AGENTS.md](AGENTS.md).

## Prerequisites

To be confirmed as each part is imported. Expected: Git (on Windows, run the shell commands from Git Bash), Python 3.13 or later for the governance tools and the study, Docker with Docker Compose for the services and the federation stack, a JDK and Maven for local Java builds, and Node.js only for the Mission Control terminal checks.

## History and provenance

The laboratory was developed first in a private repository (the "lab"), which remains its archive. This repository was started from the governance template at template commit `733f65a11f2d2639c7015f6c4b491712773db50a` and receives the lab's content as it stood at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`. The lab's Git history is not carried: commits of the lab or of the template are cited as `lab commit <id>` or `template commit <id>` and are never presented as commits of this repository. Development log entries migrated from the lab keep their original dates and say so. Files released before the migration call the lead developer "the Captain".

## License

Copyright (c) 2026 Gustavo Cavallin. Two sets of terms apply, by file:

- **The governance framework**: everything retained from the template, which is `governance/` and the starter files of the template that remain in this repository, is licensed under the PolyForm Noncommercial License 1.0.0 ([LICENSE](LICENSE), with its Required Notice in the first line; [governance/NOTICE](governance/NOTICE) for copies of `governance/`).
- **Everything else** (the legacy systems, the federation layer, the study, the documents, the development log and the project's own governance files): all rights reserved, except this **evaluation permission**: anyone, including prospective employers and clients, may view this repository, build it and run it locally to evaluate the author's work. The permission does not include copying, redistribution, modification for another use, offering it as a service, or any commercial use.

Third-party software and material keep their own licenses (see below). This summary is not legal advice.

## Third-party and fan material

- **Star Trek.** This is an independent fan and learning project. Star Trek and all related names, characters, ships, episodes and marks belong to their owners; the project is not affiliated with or endorsed by them. The enterprise, its crew records, missions and assets are fictional data built for testing.
- **Memory Alpha.** Some mission facts are paraphrased in the project's own words from [Memory Alpha](https://memory-alpha.fandom.com/), whose text is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/); each such record keeps its `sourceUrl` link to the page it came from.
- **Software.** Third-party components keep their own licenses. The two routers: the Apollo Router and Apollo's composition library are under the Elastic License 2.0 (ELv2), source-available but not open source, and Apollo's subgraph library is under MIT; WunderGraph Cosmo (the router and its `wgc` tool) is under the Apache License 2.0 at the pinned version. The other libraries and base images are listed with the components when they are imported.
