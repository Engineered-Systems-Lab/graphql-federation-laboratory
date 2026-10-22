# Project artifact classification

The project's own table: what its paths are and which validation a change to them needs. It has the format of the framework's [artifact classification](../governance/ARTIFACT-CLASSIFICATION.md), which defines the columns and the rules, and the tools read the two tables as one: the framework's rows for everything under `governance/` and for the few files the tools own at the root, these rows for everything else. This table may not classify a path under `governance/` or under `project-governance/`: the loader refuses it, because the framework's table classifies all of both, and the project folder is graded `high` there since its files decide what a go may carry. A row may name a profile of the framework or one the project added in `config/checkpoint-profiles.json`.

The template ships the rows of its own documents. A project that starts from it keeps what applies and adds one row for each path of its own; every file Git tracks needs a row in one of the two tables, and a new file needs its row in the commit that adds it. An upgrade never touches this file.

## Rows

| Path | Class | Profile | Boundary | Bound | Invariants | Subclass | Reachable | Approval-sensitivity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `LICENSE` | record | record-only | - | - | - | - | - | - |
| `README.md` | record | record-only | - | - | guidance | - | yes | - |
| `devlog/*.md` | record | record-only | - | - | - | devlog | - | - |
| `devlog/CONVENTIONS.md` | governance | governance | - | yes | guidance | - | yes | - |
| `devlog/README.md` | record | record-only | - | - | - |  | yes | - |
| `docs/ARCHITECTURE.md` | governance | governance | - | - | guidance | architecture | yes | - |
| `docs/CREW-PERSONNEL-V1.md` | runtime | crew-offline | - | - | - | - | - | - |
| `docs/PLAN.md` | record | record-only | - | yes | guidance | plan | yes | - |
| `docs/PROGRESS.md` | record | record-only | - | yes | - | progress | yes | - |
| `docs/timings/*.jsonl` | record | record-only | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/.dockerignore` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/Dockerfile` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/README.md` | record | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/*.sh` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/*.xml` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/manual/README.md` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/compose.yaml` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/contracts/*.wsdl` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/contracts/*.xsd` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/datasets/released/*.json` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/datasets/released/*.xml` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/fixtures/*.json` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/fixtures/*.xml` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/generator/*.py` | tooling | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/pom.xml` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/src/*.java` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/src/*.wsdl` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/validation/*.py` | tooling | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/crew-personnel/validation/runtime_acceptance.py` | runtime | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/personnel-v2/Dockerfile` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/README.md` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/compose.yaml` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/contracts/*.wsdl` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/contracts/*.xsd` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/datasets/*.json` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/datasets/*.xml` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/pom.xml` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/src/*.java` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/src/*.wsdl` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/validation/*.py` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/validation/personnel_v2_runtime.py` | tooling | personnel-v2-runtime | - | - | - | - | - | - |
| `uss-enterprise/requirements.txt` | tooling | crew-offline | - | - | - | - | - | - |

## Historical paths

A deleted file keeps its Class and Subclass here, as the framework's [table](../governance/ARTIFACT-CLASSIFICATION.md#historical-paths) describes.

| Path | Class | Subclass |
| --- | --- | --- |
| `REFACTORING-NOTES.md` | record | - |
