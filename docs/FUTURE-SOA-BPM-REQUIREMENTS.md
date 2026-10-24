# Future SOA/BPM requirements

Status: WIP

Target: Oracle SOA Suite/BPM 12.2.1.4. This is the future integration/orchestration layer, not an implemented deployment, compatibility claim, finalized BPEL design or authorization to build it. Requirements identified during the Missions v1 design are collected here for later process design.

## Ownership and boundaries

Legacy services own resources and local invariants. Missions owns mission data, assignments and resource audit; Personnel owns personnel facts; future Assets owns its resources. SOA/BPM owns cross-system process integrity. Future GraphQL Federation owns the modern API and data composition. Analytics is not a SOA responsibility. Keep native services independent and unaware of GraphQL, under the [constraint that legacy systems stay unaware of the integration layer](../project-governance/CONSTRAINTS.md#legacy-systems-stay-unaware-of-the-integration-layer).

Direct Missions REST remains possible and can bypass process policy while satisfying local invariants. Resource audit assertions are not authenticated proof of authority. A valid legacy write alone does not prove a valid business process.

## Identified responsibilities

| Responsibility | Requirement and boundary |
| --- | --- |
| Mission lifecycle policy | Govern transition legality above Missions. In the intended process, POSTPONED is already approved work; no PLANNED -> POSTPONED transition. The complete transition graph remains future design. |
| Approvals and human workflow | Coordinate approval sequence, human tasks and decisions; distinguish proposed, authorized, active and terminal work. No task forms, roles or BPEL flow are specified yet. |
| Command authority | Determine who may order/authorize and validate command-chain policy. Keep the performer distinct from the authorizer; neither need be the mission commander. |
| Security-clearance policy | Evaluate mission classification against personnel clearance. UNCLASSIFIED requires no clearance; SECRET requires SECRET or TOP_SECRET; TOP_SECRET requires TOP_SECRET. Personnel v2 now supplies crew clearance NONE/SECRET/TOP_SECRET; process policy remains future work. Do not change Personnel v1. |
| Personnel ID translation | Translate independent Missions C/P/O references to stable Personnel PRS identity through D015's shared, versioned mapping component; the original C-2047 <-> CRW-2047 example remains v1 illustration only. Historical mapping context and field eligibility remain to be specified. Preserve unmapped/ambiguous/dangling outcomes; no heuristic joins or competing adapter mappings. |
| Asset validation | Check existence and availability using future asset-owning services. Missions reference syntax and assignments alone establish neither fact. Assets' API/model remains undesigned. |
| Cross-service orchestration | Coordinate Personnel SOAP, Missions REST/XML, future Assets and other resource owners, human workflow and rules while preserving each service's ownership. |
| Classified-duty compensation/bonuses | Drive compensation eligibility/approval from mission classification and process context; later determine policies and owning compensation system. No rates or payroll resource model are selected. |
| Cost authorization/approval | Coordinate authority and approvals for mission estimates, expenditure changes and actual costs. Missions enforces its local cost invariants and records changes; it does not establish spending authority. |
| Transformations | Mediate protocol and message shapes, identifiers and semantic differences at the integration boundary without redesigning legacy contracts. |
| Failure, recovery and compensation | Define process behavior for partial failure, retries, recovery and compensating actions across independently owned resources. A Missions database transaction is not a distributed transaction across services. Retry/idempotency and compensation policy remain future design. |
| Process-level audit | Record process instances, approvals, human decisions, orchestration steps and recovery/compensation evidence. Distinguish and later correlate this with the lightweight Missions resource audit; do not replace or inflate that audit into process history. |
| Legacy mediation | Shield process consumers from heterogeneous SOAP/REST/XML and later native interfaces while preserving native resource contracts and realistic inconsistencies. |

## Future GraphQL business commands

Process-sensitive GraphQL mutations should conceptually express business commands (for example, requesting authorization, starting, postponing or completing a mission), with process handling delegated to SOA/BPM. Conceptual command names are authorizeMission, activateMission, postponeMission, completeMission, failMission and cancelMission. These are business intentions, not finalized schemas or BPEL interfaces. A generic status PUT exposed through GraphQL is insufficient to express approval and process obligations. GraphQL still composes modern API/data views; it does not take resource ownership or turn native Missions into a process engine. Direct legacy REST remains available.

## Future design work

Specify lifecycle/approval rules, roles, identity propagation, process correlation, compensation ownership and recovery semantics when the process work is authorized. Select integration interfaces and verify target-version/runtime compatibility then. Do not design a full BPEL process, deploy SOA/BPM, implement GraphQL mutations, generate datasets or alter frozen Personnel v1 as part of this requirements record.

See [Missions v1](MISSIONS-V1-DESIGN.md), [Architecture](ARCHITECTURE.md), D015/D027/D028 in [Decisions](../project-governance/DECISIONS.md), and [Plan](PLAN.md).
