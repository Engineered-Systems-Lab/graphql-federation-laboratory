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
| `docs/AGENT-STUDY-REPORT.md` | record | record-only | - | - | - | - | - | - |
| `docs/ARCHITECTURE.md` | governance | governance | - | - | guidance | architecture | yes | - |
| `docs/ASSETS-V1-DESIGN.md` | governance | governance | - | - | guidance | - | - | - |
| `docs/CREW-PERSONNEL-DATASET-003-DESIGN.md` | governance | governance | - | - | guidance | - | yes | - |
| `docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md` | record | record-only | - | - | - | - | yes | - |
| `docs/CREW-PERSONNEL-V1.md` | runtime | blocked | frozen | - | - | - | - | - |
| `docs/FEDERATION-DESIGN.md` | record | record-only | - | - | guidance | - | yes | - |
| `docs/FUTURE-SOA-BPM-REQUIREMENTS.md` | governance | governance | - | - | guidance | - | - | - |
| `docs/INTEGRATION-NOTES.md` | record | record-only | - | - | - | - | yes | - |
| `docs/INTERFACE-CONVENTIONS.md` | record | record-only | - | - | - | - | yes | - |
| `docs/MISSIONS-V1-DESIGN.md` | governance | governance | - | - | guidance | - | - | - |
| `docs/PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md` | governance | governance | - | - | guidance | - | - | - |
| `docs/PERSONNEL-V2-VALIDATION.md` | record | record-only | - | - | - | - | - | - |
| `docs/PERSONNEL-V2.md` | governance | governance | - | - | guidance | - | - | - |
| `docs/PLAN.md` | record | record-only | - | yes | guidance | plan | yes | - |
| `docs/PROGRESS.md` | record | record-only | - | yes | - | progress | yes | - |
| `docs/SERVICE-SCRIPTS.md` | record | record-only | - | - | - | - | - | - |
| `docs/STUDY-2-DESIGN.md` | record | record-only | - | - | - | - | yes | - |
| `docs/agent-study/*.svg` | record | record-only | - | - | - | - | - | - |
| `docs/timings/*.jsonl` | record | record-only | - | - | - | - | - | - |
| `federation/acceptance/*.json` | runtime | federation-integration | runtime | - | - | - | - | - |
| `federation/acceptance/*.py` | runtime | federation-integration | runtime | - | - | - | - | - |
| `federation/acceptance/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/adapters/assets/*.graphqls` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/*.java` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/*.properties` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/Dockerfile` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/Dockerfile.dockerignore` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/adapters/assets/compose.yaml` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/assets/start.sh` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/assets/validation/*.py` | runtime | federation-assets-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.graphqls` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.java` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.json` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/*.properties` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/Dockerfile` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/Dockerfile.dockerignore` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/adapters/mapping/compose.yaml` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/mapping/start.sh` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/mapping/validation/*.py` | runtime | federation-mapping-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.graphqls` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.java` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/*.properties` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/Dockerfile` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/Dockerfile.dockerignore` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/adapters/missions/compose.yaml` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/missions/start.sh` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/missions/validation/*.py` | runtime | federation-missions-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.graphqls` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.java` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/*.properties` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/Dockerfile` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/Dockerfile.dockerignore` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/adapters/personnel/compose.yaml` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/adapters/personnel/start.sh` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/adapters/personnel/validation/*.py` | runtime | federation-personnel-adapter | runtime | - | - | - | - | - |
| `federation/common/*.java` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/common/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/mapping-releases/*.json` | runtime | federation-mapping-data | runtime | - | - | - | - | - |
| `federation/personnel-mapping/*.json` | runtime | federation-mapping-data | runtime | - | - | - | - | - |
| `federation/personnel-mapping/*.py` | runtime | federation-mapping-data | runtime | - | - | - | - | - |
| `federation/personnel-mapping/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/pom.xml` | runtime | federation-adapter-runtime | runtime | - | - | - | - | - |
| `federation/routers/apollo/*.py` | runtime | federation-apollo | runtime | - | - | - | - | - |
| `federation/routers/apollo/*.yaml` | runtime | federation-apollo | runtime | - | - | - | - | - |
| `federation/routers/apollo/README.md` | record | federation-apollo | - | - | - | - | - | - |
| `federation/routers/apollo/rover/Dockerfile` | runtime | federation-apollo | runtime | - | - | - | - | - |
| `federation/routers/apollo/rover/seed.graphql` | runtime | federation-apollo | runtime | - | - | - | - | - |
| `federation/routers/apollo/supergraph.graphql` | runtime | federation-apollo | runtime | - | - | - | - | - |
| `federation/routers/cosmo/*.py` | runtime | federation-cosmo | runtime | - | - | - | - | - |
| `federation/routers/cosmo/*.yaml` | runtime | federation-cosmo | runtime | - | - | - | - | - |
| `federation/routers/cosmo/README.md` | record | federation-cosmo | - | - | - | - | - | - |
| `federation/routers/cosmo/execution-config.json` | runtime | federation-cosmo | runtime | - | - | - | - | - |
| `federation/routers/cosmo/wgc/Dockerfile` | runtime | federation-cosmo | runtime | - | - | - | - | - |
| `federation/stack/*.py` | runtime | federation-integration | runtime | - | - | - | - | - |
| `federation/stack/*.yaml` | runtime | federation-integration | runtime | - | - | - | - | - |
| `federation/stack/README.md` | record | record-only | - | - | - | - | - | - |
| `federation/stack/start.sh` | runtime | federation-integration | runtime | - | - | - | - | - |
| `study/README.md` | record | record-only | - | - | - | - | - | - |
| `study/analysis/*.py` | tooling | study | - | - | - | - | - | - |
| `study/analysis/*.txt` | tooling | study | - | - | - | - | - | - |
| `study/analysis/README.md` | record | record-only | - | - | - | - | - | - |
| `study/corpus/*.json` | tooling | study | - | - | - | - | - | - |
| `study/corpus/*.py` | tooling | study | - | - | - | - | - | - |
| `study/corpus/README.md` | record | record-only | - | - | - | - | - | - |
| `study/corpus/expected.json` | tooling | study | frozen | - | - | - | - | - |
| `study/corpus/tasks.json` | tooling | study | frozen | - | - | - | - | - |
| `study/corpus2/*.json` | tooling | study | - | - | - | - | - | - |
| `study/corpus2/*.py` | tooling | study | - | - | - | - | - | - |
| `study/corpus2/README.md` | record | record-only | - | - | - | - | - | - |
| `study/evidence/*.csv` | record | record-only | - | - | - | - | - | - |
| `study/evidence/*.json` | record | record-only | - | - | - | - | - | - |
| `study/evidence/README.md` | record | record-only | - | - | - | - | - | - |
| `study/guide/*.md` | tooling | study | - | - | - | - | - | - |
| `study/guide/README.md` | record | record-only | - | - | - | - | - | - |
| `study/guide/enterprise-legacy-systems-guide.md` | tooling | study | frozen | - | - | - | - | - |
| `study/harness/*.json` | tooling | study | - | - | - | - | - | - |
| `study/harness/*.py` | tooling | study | - | - | - | - | - | - |
| `study/harness/*.txt` | tooling | study | - | - | - | - | - | - |
| `study/harness/README.md` | record | record-only | - | - | - | - | - | - |
| `study/launch/*.py` | tooling | study | - | - | - | - | - | - |
| `study/launch/*.yaml` | tooling | study | - | - | - | - | - | - |
| `study/launch/README.md` | record | record-only | - | - | - | - | - | - |
| `study/mcp/*.json` | tooling | study | - | - | - | - | - | - |
| `study/mcp/*.py` | tooling | study | - | - | - | - | - | - |
| `study/mcp/*.txt` | tooling | study | - | - | - | - | - | - |
| `study/mcp/README.md` | record | record-only | - | - | - | - | - | - |
| `study/preflight/*.json` | tooling | study | - | - | - | - | - | - |
| `study/preflight/*.py` | tooling | study | - | - | - | - | - | - |
| `study/preflight/README.md` | record | record-only | - | - | - | - | - | - |
| `uss-enterprise/assets/.dockerignore` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/.env.example` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/Dockerfile` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/README.md` | record | assets-packaging | - | - | - | - | - | - |
| `uss-enterprise/assets/compose.yaml` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/contracts/*.json` | runtime | assets-contract | runtime | - | federation-assets-adapter-readers | - | - | - |
| `uss-enterprise/assets/contracts/assets-v1.0.openapi.json` | runtime | assets-contract | frozen, runtime | - | - | - | - | - |
| `uss-enterprise/assets/datasets/*.json` | runtime | assets-contract | runtime | - | released-data-readers | - | - | - |
| `uss-enterprise/assets/datasets/*.py` | runtime | assets-contract | runtime | - | - | - | - | - |
| `uss-enterprise/assets/fixtures/*.json` | runtime | assets-contract | runtime | - | federation-assets-adapter-readers | - | - | - |
| `uss-enterprise/assets/fixtures/invalid/*.json` | runtime | assets-contract | frozen, runtime | - | - | - | - | - |
| `uss-enterprise/assets/fixtures/valid/*.json` | runtime | assets-contract | frozen, runtime | - | - | - | - | - |
| `uss-enterprise/assets/schema/*.sql` | runtime | assets-service | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/service/*.py` | runtime | assets-service | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/service/bootstrap.py` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/service/requirements.txt` | runtime | assets-service | runtime | - | federation-assets-service-readers | - | - | - |
| `uss-enterprise/assets/start.sh` | runtime | assets-packaging | runtime | - | federation-assets-service-readers | - | - | - |
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
| `uss-enterprise/crew-personnel/.dockerignore` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/Dockerfile` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/README.md` | record | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/*.sh` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/*.xml` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/acceptance/manual/README.md` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/compose.yaml` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/contracts/*.wsdl` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/contracts/*.xsd` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/datasets/released/*.json` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/datasets/released/*.xml` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/fixtures/*.json` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/fixtures/*.xml` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/generator/*.py` | tooling | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/pom.xml` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/src/*.java` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/src/*.wsdl` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/validation/*.py` | tooling | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/crew-personnel/validation/runtime_acceptance.py` | runtime | blocked | frozen | - | - | - | - | - |
| `uss-enterprise/missions/.dockerignore` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/Dockerfile` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/README.md` | record | record-only | - | - | - | - | - | - |
| `uss-enterprise/missions/compose.yaml` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/contracts/*.xsd` | runtime | missions-contract | frozen, runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.json` | runtime | missions-data | runtime | - | missions-release-readers | - | - | - |
| `uss-enterprise/missions/datasets/*.py` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.sql` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/datasets/*.xml` | runtime | missions-data | runtime | - | missions-release-readers | - | - | - |
| `uss-enterprise/missions/datasets/reset.sh` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/fixtures/*.xml` | runtime | missions-contract | frozen, runtime | - | - | - | - | - |
| `uss-enterprise/missions/pom.xml` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/schema/*.sql` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/src/*.java` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/missions_runtime.py` | tooling | missions-gates | - | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/data/*.py` | runtime | missions-data | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/packaging/*.py` | runtime | missions-packaging | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/runtime/service/*.py` | runtime | missions-service | runtime | - | - | - | - | - |
| `uss-enterprise/missions/validation/test_missions_gates.py` | tooling | missions-gates | - | - | - | - | - | - |
| `uss-enterprise/missions/validation/validate.py` | runtime | missions-contract | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/Dockerfile` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-service-readers | - | - | - |
| `uss-enterprise/personnel-v2/README.md` | record | record-only | - | - | - | - | - | - |
| `uss-enterprise/personnel-v2/compose.yaml` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-service-readers | - | - | - |
| `uss-enterprise/personnel-v2/contracts/*.wsdl` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-adapter-readers | - | - | - |
| `uss-enterprise/personnel-v2/contracts/*.xsd` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-adapter-readers | - | - | - |
| `uss-enterprise/personnel-v2/datasets/*.json` | runtime | personnel-v2-runtime | runtime | - | personnel-data-readers | - | - | - |
| `uss-enterprise/personnel-v2/datasets/*.xml` | runtime | personnel-v2-runtime | runtime | - | personnel-data-readers | - | - | - |
| `uss-enterprise/personnel-v2/pom.xml` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-service-readers | - | - | - |
| `uss-enterprise/personnel-v2/src/*.java` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-service-readers | - | - | - |
| `uss-enterprise/personnel-v2/src/*.wsdl` | runtime | personnel-v2-runtime | runtime | - | federation-personnel-service-readers | - | - | - |
| `uss-enterprise/personnel-v2/validation/*.py` | runtime | personnel-v2-runtime | runtime | - | - | - | - | - |
| `uss-enterprise/personnel-v2/validation/personnel_v2_runtime.py` | tooling | personnel-v2-runtime | - | - | - | - | - | - |
| `uss-enterprise/requirements.txt` | tooling | crew-offline | - | - | - | - | - | - |
| `uss-enterprise/scripts/assets.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `uss-enterprise/scripts/missions.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `uss-enterprise/scripts/personnel.sh` | tooling | service-scripts | - | - | - | - | - | - |
| `uss-enterprise/scripts/tests/test_service_scripts.py` | tooling | service-scripts | - | - | - | - | - | - |

## Historical paths

A deleted file keeps its Class and Subclass here, as the framework's [table](../governance/ARTIFACT-CLASSIFICATION.md#historical-paths) describes.

| Path | Class | Subclass |
| --- | --- | --- |
| `REFACTORING-NOTES.md` | record | - |
| `scripts/assets.sh` | tooling | - |
| `scripts/missions.sh` | tooling | - |
| `scripts/personnel.sh` | tooling | - |
| `scripts/tests/test_service_scripts.py` | tooling | - |
