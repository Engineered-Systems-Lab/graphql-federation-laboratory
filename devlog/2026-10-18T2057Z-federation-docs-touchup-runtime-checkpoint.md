# Two stale federation texts are corrected

Date: 2026-10-18T20:57Z
Subject: Committed the correction of two stale federation texts: the Cosmo subgraph retry ruling (kept off, the lead developer's decision) and the claim that the Apollo router runs with its default telemetry
Status: Historical / non-normative
Lab checkpoint: lab commit `c25b423a3090fdb5152766d092e69fcc3edd28b1`
Provenance: Git committer timestamp `2026-10-18T16:57:46-04:00` (2026-10-18 20:57:46 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's ruling on the retry setting (2026-10-18, recorded verbatim in the Job `federation_design`) or this later record preparation. The lead developer selected "go" at the preview through the host's question control; the early conditional approval carried it to the commit after all 11 checks passed.
Migrated from lab log SD-2026.291-2057Z; originally written in the lab on 2026-10-18 (lab commit `4a2b0b9b19e0f0610f420c46f1a914ceead0affa`).

## Meaningful transition

Two texts that had gone stale are now true. The Cosmo retry setting `retry.enabled: false` was recorded as the worker's addition and the lead developer's to keep or change; the lead developer decided on 2026-10-18 to keep it off for the comparison, and the federation design (row 68 and the Cosmo findings), the Cosmo README and the comment in `config.yaml` now say so. The claim that the Apollo router still runs with its default telemetry was wrong: both routers already run with anonymous telemetry off in the stack, `APOLLO_TELEMETRY_DISABLED` since the Apollo router commit of 2026-10-16 and `COSMO_TELEMETRY_DISABLED` since the Cosmo router commit. No setting value, test or behavior changed. The commit is on the owned branch `tx/20261018-federation-docs-touchup`, parent lab commit `118e9dfd9037dc50c6ec6406c7147cb69468aec3`, tree `688d09c`.

## Choices recorded

- **The retry setting is decided.** The lead developer agreed to keep the retries off and to record it that way, as the federation design records.
- **A compatibility-matrix row was added for the retry of a failed subgraph request.** Cosmo supports it and has it on by default (5 attempts, 3 s interval, a random wait of up to 10 s); the pinned Apollo router v2.18.0 has no subgraph-request retry setting (its configuration schema, read with `router config schema` from the pinned image, lists only reload retries). It is a production-resilience feature in Cosmo's favour, switched off for fair tests. Which failures Cosmo retries is not verified. The Apollo schema reading is the Coordinator's finding; the records worker did not repeat it.
- **The telemetry correction is a finding of the Coordinator.** The Apollo router has an anonymous usage ping (`--anonymous-telemetry-disabled`, environment `APOLLO_TELEMETRY_DISABLED`, read from the pinned image's help), and `federation/stack/compose.yaml` sets it on the router service. The wrong sentence came from the throwaway containers of experiment 2. The run manifest of a benchmark must record that both are off.
- **Later context, not a rewrite.** The experiment 2 text in Integration notes and the telemetry sentence of the Cosmo router log (`SD-2026.291-1337Z`) keep their contemporary wording; this entry is the later context for the latter. The three corrected texts are the federation design, the Cosmo README and the comment in `config.yaml`.

## Retained evidence and limits

All 11 checks of the seal passed (times from the packet): staged whitespace (0.0 s), continuity (15.9 s), the four adapters' offline gates and the Assets and Personnel service gates (53.2, 56.7, 55.0, 65.9, 66.6 and 68.7 s), `federation-router-apollo-offline` (24.1 s), `federation-router-apollo-stack` (270.0 s), `federation-router-cosmo-offline` (34.8 s) and `federation-router-cosmo-stack` (294.0 s). The estimate was about 18m 41s. Post-commit continuity failed as expected with `Stale implementation checkpoint: runtime history has advanced`, the obligation the Progress change of this record resolves.

Two paths of the manifest are runtime-class, so the full federation gate list ran for a change of comments and prose. One interrupted command (the commit, stopped by the lead developer at a tool prompt) left an operation lock behind; the commit itself had completed, and the lead developer approved deleting the stale lock after no checkpoint process was found. Limits: stub-backend mode only; no benchmark or human acceptance claim.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until the separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
