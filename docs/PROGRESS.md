# Progress

Status: template placeholder. Replace this document with the verified current state of your project.

Progress records what is verified now, with no task lists and no history; history is in [devlog entries](../devlog/README.md) and in Git, direction is in [Plan](PLAN.md).

## Current state

The Comitas governance framework has been adopted, and the lab's systems, its federation layer and the Abstraction ladder study have been imported; the recovery chain guards runtime history from the implementation checkpoint below.

## Recovery facts

These current-state fields keep the exact table format consumed by [continuity verification](../governance/COMMAND-CONTINUITY.md) and the [v1 reconstruction contract](../governance/config/reconstruction-contract-v1.json).

| Fact | Value |
| --- | --- |
| service | Imported, not recorded as running: Personnel v2, Missions, Assets and the federation layer are on the runtime boundary |
| manual_acceptance | Not recorded |
| implementation_checkpoint | 94f7e34494876b2953ee099b1b2a7653f380d91d |
| next_authorized_action | None recorded here: each action requires its own applicable checkpoint authorization |

A project that declares a runtime boundary in the classification table also adds an `implementation_checkpoint` row (a full Git SHA) and the matching fact in the reconstruction contract; see [Command continuity](../governance/COMMAND-CONTINUITY.md#adopting-the-recovery-chain). Record, governance and tooling transactions do not advance the implementation checkpoint.
