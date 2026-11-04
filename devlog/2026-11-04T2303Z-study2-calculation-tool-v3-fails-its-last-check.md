# The calculation tool's version 3 answers 31 of 32 with no token stop, and fails its last declared check on one new failure

Date: 2026-11-04T23:03Z
Subject: Replayed and built version 3 of study 2's calculation tool, ran a new no-tool baseline and a paid confirmation of V05 to V08 on the graph with totals, and recorded the declared check's third and last failure
Status: Historical / non-normative
Provenance: Written on 2026-11-04 (UTC) by the worker of the Job study2_calculate_v3, before the commit that carries it. Sources: the replay's output, both paid runs' score tables and manifests (copied into `study/evidence/study-2-calculate-v3/`), and the run folders and transcripts in the machine-local results folder, cited by checksum; the lead developer's decisions in the worker session. Dated by the time of writing, just after the verdict. The baseline ran from 21:28Z to 22:07Z and the confirmation from 22:07Z to 22:43Z, from one line in the lead developer's terminal; the worker never held an API key.

## Version 3

Version 2 of the calculation tool kept long fetched results out of the conversation, but its own outputs were always shown in full, 1.36 M characters in study2-confirm-1. Version 3 changes three things:

- **Long outputs are stored.** A calculate output over 5,000 characters is now stored like a long scenario result and shown by its shape.
- **A read line.** Every calculate output begins with one line naming, per source, the result id, the path and the records it contributed, never summed.
- **Bounded view pages.** A `view` page holds at most 5,000 characters and carries `nextOffset` while the part goes on.

- **The replay.** study2-confirm-1's 32 runs were replayed offline with the agents' calls held fixed. Version 3 projected 5.01 M to 7.09 M tokens against version 2's real 7.80 M, with no V05 run at the 1 M limit. The lead developer chose to build it as replayed and to leave the guide unchanged.
- **The commit.** Version 3 landed in `683eca07c4b5c3db2b17c3c110bab9ab7749c7f8`. Before the go, the lead developer found two ways a view page could pass its limit: an uncounted `missing` key, and one very long object key. Both were fixed with tests in the same commit.
- **Before the paid runs.** A debug run on the live GraphQL Adapters stack showed the read line, the stored outputs and the pages working on real data. Then both paid configs passed a fake-client dry run, with provenance matching in every arm.

## The two paid runs

Both runs used the adapters 1.1.0 graph and the same pins. The graph change has two effects, and both were live: `missionsPage` and `assetsPage` give the services' totals beside the lists, and the deprecated `missions` and `assets` lists are hidden from default introspection. Every one of the 48 graph-arm runs used `missionsPage`. None named a deprecated list.

| | Run 1, no tool | Run 2, v1 | Confirm-1, v2 | New baseline, no tool | Confirmation, v3 |
| --- | --- | --- | --- | --- | --- |
| Correct | 22/32 | 23/32 | 27/32 | 24/32 | 31/32 |
| Tokens | 7.18 M | 10.78 M | 7.80 M | 8.90 M | 5.59 M |
| Runs at or over 1 M tokens | 1 | 7 | 2 | 4 | 0 |
| Dollars | | 6.44 | 4.71 | 6.11 of 8 | 3.56 of 10 |

## The check

The design's rule: the counting failures and the token-volume failures must fall, the definitional failures stay the same, and no new kind of failure appears. This time it was run against the new baseline.

- **Token-volume failures fell from 4 to 0.** All four baseline stops were V05.
- **Counting failures fell from 2 to 0.** Both baseline failures were V08 answers of 103 instead of 104, counted by hand.
- **Definitional failures stayed at 0.**
- **One new kind appeared**, in Claude's V06 answer in Apollo. It left out the one TRANSPORT mission. The agent filtered missions on fixed asset positions 0 to 3 and joined the outputs by hand, but that mission has 50 assets, with its non-active ones at positions 24 and 27. A filter condition cannot say "any element of this list", so the question had no direct filter.

The worker proposed that the check fails on that clause, and the lead developer decided: "The check fails". Under the Job, the work stops here. The fallback is decided as a later Job (decision Q3), and `study2_freeze` keeps waiting. Version 3 stays in the harness as committed. The limits stay at 80 tool calls, 1 M tokens, 900 s and 3 retries (decision Q4). The largest confirmation run used 75 calls.

The record is `study/evidence/study-2-calculate-v3/v3-record-20261104T230250Z.json`.

## Limits

- **One trial of four tasks.** Neither run estimates an arm's accuracy; a single run moves each count.
- **The causes are read from calls, not reasoning.** The transcripts hold no reasoning text, so each failure is classified from the agent's calls, results and answer.
- **The baseline lost two V05 runs to connection errors.** Those runs could not show a token stop or an answer.
