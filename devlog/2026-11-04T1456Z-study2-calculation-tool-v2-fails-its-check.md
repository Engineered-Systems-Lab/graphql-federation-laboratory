# The calculation tool's version 2 cuts the token volume by a quarter, and still fails its declared check

Date: 2026-11-04T14:56Z
Subject: Compared candidate designs for study 2's calculation tool offline, built the one the lead developer chose, confirmed it in one paid run of V05 to V08, and recorded the declared check's second failure
Status: Historical / non-normative
Provenance: Written on 2026-11-04 (UTC) by the worker of the Job study2_calculate_redesign, before the commit that carries it. Sources: the replay's output and the confirmation's score table and manifest, the latter copied into `study/evidence/study-2-calculate-redesign/`; the run folders and transcripts in the machine-local results folder, cited by checksum; the lead developer's decisions in the worker session. Dated by the time of writing, just after the verdict. The confirmation ran from 13:59Z to 14:49Z; the lead developer started it from their own terminal, and the worker never held an API key.

## The redesign

Version 1 of the calculation tool failed its check on token volume (decision Q7 of the Job study2_preflight_final). Every fetched result still entered the conversation in full, and V05, which needs all 300 missions, ran into the 1,000,000-token task limit seven times.

- **The replay.** Run 2's 32 runs of V05 to V08 were replayed offline through each candidate, with the agents' calls held fixed. Making the tool's outputs smaller (tool-side) saved little: 10.59 M projected tokens against version 1's 10.78 M. Storing long results and showing only their shape (result-side) cut the total to about 4.8 M, with no V05 run left at the limit.
- **The choice.** The lead developer chose R5000 (decision R1): a result over 5,000 characters is stored in full, and the agent sees its id, its size and its shape, then reads any part through a new generic `view` operation.
- **Version 2** was built with tests and a task-subset option for the harness, in `8b072fb72e13ceb8caa0e09c779a684613b5fe0e`. Before the go the lead developer found that `view` could still pass the output limit with an object of one long member; the fix went into the same commit.
- **Before the paid run.** A debug run against the live gamma stack showed every operation and refusal working on real data. A fake-client dry run of the confirmation then passed provenance in all four arms. The dry run's first attempt stopped before any stack: the worker had written the config without study 2's corpus folder.

## The confirmation

`study2-confirm-1`: V05 to V08 in Guided Direct Access, GraphQL Adapters, Apollo and Cosmo, both models, one trial, 32 runs, 4.71 dollars of a 10-dollar ceiling. Provenance matched in every arm.

| | Run 1, no tool | Run 2, version 1 | Confirmation, version 2 |
| --- | --- | --- | --- |
| Correct | 22/32 | 23/32 | 27/32 |
| Tokens | 7.18 M | 10.78 M | 7.80 M |
| Runs at or over 1 M tokens | 1 | 7 | 2 |
| Calculate calls (refused) | – | 118 (12) | 262 (11) |

Version 2 kept 4.79 M characters of scenario results out of the conversation and showed 274 k characters of scenario results in full. Calculate's own outputs are always shown in full: 1.36 M characters in 251 calls, against 0.51 M in run 2. So most of the result characters that now enter the conversation are the tool's outputs, not the fetched data. The agents made twice as many calculate calls as in run 2, so the real total stayed above the replay's projection.

## The check

The design's rule: the counting failures and the token-volume failures must fall against run 1, the definitional failures stay the same, and no new kind appears.

- **Counting failures fell from 7 to 2.** Both were hand tallies by Claude: a crew-to-person join done by hand, with one civilian counted as a crewman, and a count of 38 transport missions instead of 39 after a refused call.
- **Definitional failures stayed at 0.**
- **Token-volume failures did not fall: 1 against run 1's 1.** It was GPT on V05 in Guided Direct Access, at 1.04 M tokens.
- **A new kind appeared.** Two Claude V05 answers, in GraphQL Adapters and Cosmo, were the same wrong 569, each built from 200 of the 300 missions. In one, the agent had fetched the third hundred but left that result out of its calculation; in the other, it never fetched it.

The worker proposed that the check fails, and the lead developer decided: "The check fails". Under the design the tool design returns to the lead developer before the corpus freeze, and `study2_freeze` keeps waiting. Version 2 stays in the harness as committed. The limits stay at 80 tool calls, 1 M tokens, 900 s and 3 retries (decision Q4): the one token stop equals run 1's without the tool.

The record is `study/evidence/study-2-calculate-redesign/redesign-record-20261104T145628Z.json`.

## Limits

- **One trial of four tasks.** The confirmation is not an estimate of any arm's accuracy; a single run moves each count.
- **The causes are read from calls, not reasoning.** The transcripts hold no reasoning text, so each failure is classified from the agent's calls, results and answer.
- **"A choice of result ids" is the worker's reading.** It is the basis for counting the GraphQL Adapters V05 answer as a new kind; the Cosmo answer of the same shape had no tool part.
- **The replay held the agents' behaviour fixed.** With version 2 the agents called the tool more often than in run 2, which the replay could not show.
