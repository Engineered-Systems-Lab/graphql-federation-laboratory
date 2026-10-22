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
| `federation/acceptance/*.json` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/acceptance/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/acceptance/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/*.graphqls` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/*.properties` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/Dockerfile.dockerignore` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/compose.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/start.sh` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/validation/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.graphqls` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.json` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.properties` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/Dockerfile.dockerignore` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/compose.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/start.sh` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/validation/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.graphqls` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.properties` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/Dockerfile.dockerignore` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/compose.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/start.sh` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/validation/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.graphqls` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.properties` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/Dockerfile.dockerignore` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/compose.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/start.sh` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/validation/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/common/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/common/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/mapping-releases/*.json` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/personnel-mapping/*.json` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/personnel-mapping/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/personnel-mapping/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/*.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/rover/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/rover/seed.graphql` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/supergraph.graphql` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/cosmo/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/cosmo/*.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/cosmo/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/cosmo/execution-config.json` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/cosmo/wgc/Dockerfile` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/stack/*.py` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/stack/*.yaml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/stack/README.md` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/stack/start.sh` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `scripts/assets.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `scripts/missions.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `scripts/personnel.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `scripts/tests/test_service_scripts.py` | tooling | service-scripts | - | - | - | - | - | - |
| `uss-enterprise/assets/.dockerignore` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/.env.example` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/Dockerfile` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/README.md` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/compose.yaml` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/contracts/*.json` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/datasets/*.json` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/datasets/*.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/fixtures/*.json` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/schema/*.sql` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/service/*.py` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/service/bootstrap.py` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/service/requirements.txt` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/start.sh` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/jsonschema_subset.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/run_service_gate.py` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/runtime/packaging/*.py` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/runtime/service/*.py` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_assets_contract.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_assets_dataset.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_jsonschema_subset.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_run_service_gate.py` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_service_logic.py` | runtime | assets-service | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/test_start_script.py` | runtime | assets-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/validate.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/validation/validate_dataset.py` | runtime | assets-contract | runtime | - | - | - | - | - |
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
| `uss-enterprise/missions/.dockerignore` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/Dockerfile` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/README.md` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/compose.yaml` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/contracts/*.xsd` | runtime | missions-contract | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.json` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.py` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.sql` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.xml` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/reset.sh` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/fixtures/*.xml` | runtime | missions-contract | runtime | - | - | - | - | - |
| `uss-enterprise/missions/pom.xml` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/schema/*.sql` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/src/*.java` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/missions_runtime.py` | tooling | missions-gates | - | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/data/*.py` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/packaging/*.py` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/service/*.py` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/test_missions_gates.py` | tooling | missions-gates | - | - | - | - | - | - |
| `uss-enterprise/missions/validation/validate.py` | runtime | missions-contract | runtime | - | - | - | - | - |
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
