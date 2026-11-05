# The calculation tool failed its declared check in four rounds, each in a new place, and the lead developer asks whether a calculation tool is realistic for a federated graph

Date: 2026-11-05T02:45Z
Subject: Recorded the four rounds of study 2's calculation tool with their commits and the graph change between them, the pattern across the rounds, the lead developer's question whether a calculation tool is realistic for a federated graph with the Coordinator's reading of it, and the planned trap audit
Status: Historical / non-normative
Provenance: Written on 2026-11-05 (UTC) by the worker of the Job study2_calculate_devlog, before the commit that carries it. Sources, read on main at `bbf523a8306df94546957fea41d0dc9494a39ef9`: the commits named below, the four tool entries and the two graph entries of this devlog, the records in `study/evidence/` they name, the study 2 design and the D041 page totals revision. The lead developer's question, their decisions L1 and L2 and the Coordinator's reading come from the Job's approved scope of 2026-11-05. Dated by the time of writing. No stack, run or network call was made for this entry, and it changes no design.

## The transition

Each of the four tool entries records one round. None records what the rounds show together, nor the question the lead developer raised on 2026-11-05: whether a calculation tool is realistic for a federated graph at all. After the fourth failure the tool design is with the lead developer (decision V4 of the Job study2_calculate_v4), and `study2_freeze` keeps waiting. The Coordinator named the choices open to them: patch `calculate` again, keep a version with a recorded deviation, offer a code tool, or offer no tool. None is chosen here.

## The rounds

Every round's check compared V05 to V08 in Guided Direct Access, GraphQL Adapters, Apollo Federation and Cosmo Federation, with both models and one trial, 32 runs: for version 1 those 32 of the 80 runs of its development run, for the later versions one paid confirmation each. The check applied the design's rule: the counting and token-volume failures must fall, the definitional failures stay the same, and no new kind of failure appears.

| Round | Tool commit | Record | What the check found |
| --- | --- | --- | --- |
| Version 1 | `e8f0e5bc1e2e325aa921dcf1fcd7eccbc529ddbf`, study 2's harness, committed 2026-10-27 | `f1198f51cb8e3d47f7986886d684b2bd580278d6`, [its entry](2026-11-04T0229Z-study2-preflight-steps-7-9-and-tool-check.md) (Job study2_preflight_final) | Every fetched result entered the conversation in full. Against run 1 without the tool: counting failures fell from 7 to 2, token-volume failures rose from 1 to 7, all on V05. Fails on token volume (decision Q7). |
| Version 2 | `8b072fb72e13ceb8caa0e09c779a684613b5fe0e` | `abc3abc099dbd5c3862c4716166a5fec5ac71f65`, [its entry](2026-11-04T1456Z-study2-calculation-tool-v2-fails-its-check.md) (Job study2_calculate_redesign) | A result over 5,000 characters is stored and shown by its shape, and read through `view`. 27 of 32 correct (run 1: 22), 7.80 M tokens (version 1: 10.78 M). Counting fell from 7 to 2; token volume did not fall below run 1 (1 against 1). A new kind: two Claude V05 answers built from 200 of the 300 missions, one leaving a fetched result out of its calculation (its worker's reading: a choice of result ids), the other never fetching it. Fails. |
| Graph totals | `eb196ce59540d8e619618277132553276f8b1527`, with its records `923d9f9174e9a052409fb3558a022442688ef0a4` | `5539b1aea3ec4b7ee6c396f786b2e2b8ac6eeff8`, [the runtime entry](2026-11-04T1909Z-graph-page-totals-runtime-checkpoint.md) and [the step 7 entry](2026-11-04T1953Z-graph-arms-step7-on-adapters-1-1.md) | Not a tool round. The graph's Missions and Assets lists gained `missionsPage` and `assetsPage` with the services' totals, shaped like the existing `PersonnelPage`, and the old lists were deprecated, in the [D041 page totals revision](../project-governance/DECISIONS.md#d041-page-totals-revision-2026-11-04-accepted-scope). Version 2's 200-of-300 answers motivated it; the revision records missing totals as a contributing weakness, not an established common root cause. Step 7 passed again in the three graph arms, with every total equal to its paged count. |
| Version 3 | `683eca07c4b5c3db2b17c3c110bab9ab7749c7f8` | `70df028e1afb507dec6ecfbd78f3b500425effdb`, [its entry](2026-11-04T2303Z-study2-calculation-tool-v3-fails-its-last-check.md) (Job study2_calculate_v3) | Long `calculate` outputs are stored too, every output starts with a read line, and a `view` page holds at most 5,000 characters. Against a new no-tool baseline on the graph with totals (`study2-baseline-totals-1`, 24 of 32): 31 of 32, token volume 4 to 0, counting 2 to 0, definitional 0. A new kind: Claude's V06 answer in Apollo filtered missions on fixed list positions 0 to 3, because a filter condition could not say "any element of this list", and left out the one TRANSPORT mission, which has 50 assets. Fails. |
| Version 4 | `1c52d16f28d0ff1546eb37965432e1d7ce198833` | `bbf523a8306df94546957fea41d0dc9494a39ef9`, [its entry](2026-11-05T0215Z-study2-calculation-tool-v4-fails-its-check.md) (Job study2_calculate_v4) | A filter condition can say `elements` `any` or `none`, a `*` field without it is refused, and unreadable text on a condition's field is refused. Against the same baseline: 31 of 32, token volume 4 to 0, counting 2 to 0, and version 3's V06 answer is correct. A new kind: Claude's V05 answer in GraphQL Adapters stopped at the 80 tool-call limit. Calls 71 to 77 were seven `intersection` calls with the field `personnelId` over a source of plain id values, and each returned 0 without a refusal; beside it, as the lead developer classified the stop, an inefficient strategy (53 graph queries, where GPT, correct in the same arm, used 20). Fails (decision V4). |

## The pattern across the rounds

This is the Coordinator's reading of 2026-11-05, which this worker checked against the records above.

- **Each fix removed the failure it targeted.** Version 2 took version 1's token stops from 7 back to 1, though not below run 1's 1, so the token-volume clause still failed. Version 3 took the token stops and the counting failures to 0. Version 4 answered the any-element question.
- **Each next run found another place where the narrow tool let a wrong use pass silently, or could not express a generic need:** an incomplete input that the output did not show (version 2), a list condition the filter could not state (version 3), and a field over plain values that silently gave 0 (version 4).
- **The paid confirmations found them one at a time.** The fake-client dry runs that came before each paid run cannot find them, because no real model calls the tool in a dry run.

## The independent trap audit

On decision L1 (a) of the lead developer, 2026-11-05, this entry names the audit as planned and leaves its findings to a later record, with the decision they inform. Planned on 2026-11-05: a GPT auditor in a local Codex task, read-only and outside this repository, with its prompt kept in the private provenance repository, lists every such pattern in the four paid runs at once. No finding of it is part of this entry.

## Is a calculation tool realistic for a federated graph?

The question is the lead developer's, raised on 2026-11-05. What follows is the Coordinator's reading of it on the same day. Its statements about other products are general knowledge, not lab evidence, and were not checked against any source in this repository.

- **What a federated graph provides.** Entities joined across services by key, lists with paging and filters, and often a list's total. Apollo Federation and Cosmo Federation have no built-in aggregation. Single-source GraphQL engines sometimes have one (for example Hasura's `aggregate` and Prisma's `_count`), within one source only. Distinct counts and group-bys across services are usually computed in the client, by a purpose-built field, or in a warehouse or BI layer.
- **Where a real agent computes.** In the client, most often through a code interpreter. Language models count large sets poorly by hand: run 1, without the tool, had 7 counting failures.
- **Why study 2 has one generic tool.** The study 2 design records decision B (2026-10-21) as "one shared calculation tool, the same in every arm", with no reason stated. The Coordinator's reading of the reason: aggregation fields built for the tasks would favour the graph arms for their API design, not for federation; the direct arms need the same help; so the arms differ only in how data is reached. `calculate` is then a narrow, controlled stand-in for a code interpreter, and its narrowness is what each round hit.

On decision L2 (a) of the lead developer, 2026-11-05, this reading stays in this entry only, historical and non-normative. The design changes only if decision B changes, which is the lead developer's coming choice.

## The state it leaves

- **The tool design is with the lead developer** under decision V4, and `study2_freeze` keeps waiting.
- **Version 4 stays in the harness as committed.** The silent zero over plain values is not fixed and is left for the lead developer to decide.
- **The limits stay** at 80 tool calls, 1 M tokens, 900 s and 3 retries (decision Q4).
- **The trap audit is planned,** and its findings belong to a later record.

## Limits

- **Every confirmation is one trial of four tasks.** A single run moves each count.
- **The causes are read from calls, not reasoning.** The transcripts hold no reasoning text.
- **Version 1 and version 2 were judged against run 1, versions 3 and 4 against the new baseline** on the graph with totals, so the rounds' counts are not one series.
- **The realism reading is not a finding of the lab.** No run tested a code tool or a graph without `calculate`.
