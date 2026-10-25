# Retrospective: the Apollo and Cosmo routers

Date: 2026-10-25T12:20Z
Subject: A retrospective of the two routers of the federation layer, Apollo (2026-10-16) and Cosmo (2026-10-18), over the same four subgraphs and one router-neutral acceptance suite, with the introspection setting of 2026-10-20
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). Nothing was run again for it.

## What changed

- **2026-10-16, the Apollo router** (lab commit `1842bcc79cd80d9642b1ed685df7dc97391274c1`, [entry](2026-10-16T2113Z-federation-router-apollo-runtime-checkpoint.md)). The federation layer could be queried through one GraphQL endpoint for the first time: the Apollo router v2.18.0 on port 8170, the four subgraphs composed with Rover, a whole-stack compose file and the first end-to-end acceptance tests (questions 2 to 5 and the controlled cases), their expected outcomes derived from the released files before any router code. The composed supergraph is committed because a fixed build gave a byte-identical output and a one-field schema change gave a one-line diff; a stack test composes again and fails when the committed file differs.
- **2026-10-18, the Cosmo router** (lab commit `04e111ffd6faccb75198ce41949ee43f66a37633`, [entry](2026-10-18T1337Z-federation-cosmo-router-runtime-checkpoint.md)). The Cosmo router 0.359.0 runs self-hosted on port 8171 from an execution config composed locally by `wgc` 0.133.0, with no Cosmo Cloud, account or token. The acceptance suite, made router-neutral earlier the same day ([entry](2026-10-18T0350Z-federation-shared-acceptance-suite-runtime-checkpoint.md)), ran against it: its main part passed unchanged, and its controlled cases passed once the suite declared two more of Cosmo's own facts about error entries.
- **2026-10-20, introspection** (lab commit `c20dfbfd76585e5287bc3df4f576e1f7a68c2af7`, [entry](2026-10-20T1753Z-router-introspection-runtime-checkpoint.md)). The Apollo router refused schema queries, so a study scenario could not discover the schema through it. Both router configurations now enable introspection explicitly, and each stack gate tests it.

## What was decided

[D047](../project-governance/DECISIONS.md#d047---federation-cosmo-router-self-hosted-design-pinned-versions-and-subgraph-retries-off-2026-10-18-accepted-scope) records the lead developer's rulings on the second router: self-hosted with local composition, so that the comparison is router against router; the newest versions at build time, pinned by digest; the execution config committed only because it is byte-reproducible; the same 5 second subgraph timeout as Apollo's; and subgraph retries off. The last point was the worker's addition, ruled on afterwards: with Cosmo's default of 5 attempts a dead adapter answered after 5.1 s in one run and 21.0 s in the next, so the figures would have measured a retry policy and not the routing. Earlier, on 2026-10-16, the lead developer set the rule that the supergraph is committed only if its build is reproducible, and kept the acceptance of the Elastic License 2.0 of Rover's composition plugin with the person who runs it: the scripts refuse unless it is accepted on purpose.

## Why it mattered

D005 in [Decisions](../project-governance/DECISIONS.md) gates every performance comparison on shared acceptance tests: an incorrect response must not appear as a performance win. Two routers over the same subgraphs, passing the same assertions, are what such a comparison needs. The differences the suite had to declare are themselves findings, recorded in the compatibility matrix of [the federation design](../docs/FEDERATION-DESIGN.md#the-compatibility-matrix), each a fact of one run on stub data:

- For a dead adapter Cosmo writes an entry with no `extensions` at all, naming the subgraph only in its message, and one entry per failed fetch where Apollo writes one per reference. On the large data with the Assets adapter stopped, that was 596 entries under Apollo and 3 under Cosmo for the same 300 missions.
- Cosmo found restarted adapters by itself (16.4 s in the gate); Apollo needed a restart.
- Cosmo's composition output depends on the order of the subgraphs; Rover's does not. Both agree on the lab's schemas.
- A request with no release is HTTP 200 under Cosmo and HTTP 400 under Apollo.

## What was measured, and the limits

At their builds, the Apollo stack gate ran 20 tests (205.1 s) and the Cosmo stack gate 33 (556.9 s), with 33 and 40 offline tests. On the large data (from 2026-10-19), after the Personnel adapter cache, the first full pages of a cold stack took 3.11, 0.74 and 0.49 s under Apollo and 1.96, 0.64 and 0.62 s under Cosmo, and, once warm, 0.86, 0.49 and 0.49 s under Apollo and 0.49, 0.45 and 0.63 s under Cosmo; [the retrospective of the cache](2026-10-25T1222Z-retrospective-personnel-adapter-cache.md) has the figures before it. Every time is informal, from single runs on one machine, and no benchmark was made. Both routers ran only in stub-backend mode, with a simulator in place of the Oracle-backed Missions service. Hive is not built. The Apollo router at first kept its default telemetry; D047 records the two routers' telemetry as aligned since.

## Evidence

- The three migrated entries linked above, with their lab checkpoints lab commit `1842bcc79cd80d9642b1ed685df7dc97391274c1`, lab commit `04e111ffd6faccb75198ce41949ee43f66a37633` and lab commit `c20dfbfd76585e5287bc3df4f576e1f7a68c2af7`.
- The [Apollo router README](../federation/routers/apollo/README.md) and the [Cosmo router README](../federation/routers/cosmo/README.md), including their sections on the large data.
- D047, and the [federation design](../docs/FEDERATION-DESIGN.md#the-cosmo-router-of-2026-10-18).
