# The calculation tool's version 4 answers the any-element question, and fails its declared check on one silent wrong operation

Date: 2026-11-05T02:15Z
Subject: Built version 4 of study 2's calculation tool with an any-element filter condition, ran its paid confirmation of V05 to V08 against the existing no-tool baseline, and recorded the declared check's fourth failure
Status: Historical / non-normative
Provenance: Written on 2026-11-05 (UTC) by the worker of the Job study2_calculate_v4, before the commit that carries it. Sources: the confirmation's score table and manifest (copied into `study/evidence/study-2-calculate-v4/`), the run folders and transcripts in the machine-local results folder, cited by checksum, and the lead developer's decisions in the worker session. Dated by the time of writing, just after the verdict. The confirmation ran from 01:18Z to 01:55Z, from one line in the lead developer's terminal; the worker never held an API key.

## Version 4

Version 3 failed its check on one V06 answer, which filtered missions on fixed list positions because a filter condition could not say "any element of this list". Version 4 adds one key to a filter condition, and changes nothing else of version 3:

- **`elements` any or none.** With `any` a condition holds when at least one value at its field passes the comparison; with `none`, when no value does. The values are found as a source path finds records, `*` taking every element of a list, so an empty list or a missing field has no values.
- **A `*` field needs `elements`.** The lead developer asked for this before the preview, as the one deliberate exception to keeping every existing condition unchanged. Version 3 treated such a field as missing, which could silently include or exclude records depending on the comparison.
- **Unreadable text is refused.** A review finding of the lead developer: a text on a condition's field that cannot be read as JSON or XML was taken as missing. It is now refused.

Version 4 landed in `1c52d16f28d0ff1546eb37965432e1d7ce198833`, on the lead developer's go at its third preview; two wording corrections of theirs came before the go. The earlier paid runs held three plain `*` conditions, in two correct V06 runs, both of which returned 0 records; the records do not show whether either agent relied on that. A debug run on the live GraphQL Adapters stack counted 40 missions referencing asset EQ-108, the number the graph itself reports, and the fake-client dry run matched provenance in every arm.

## The paid confirmation

The run used the same shape and pins as version 3's confirmation, against the existing baseline `study2-baseline-totals-1`.

| | Run 1, no tool | Run 2, v1 | Confirm-1, v2 | Baseline, no tool | Confirm, v3 | Confirm, v4 |
| --- | --- | --- | --- | --- | --- | --- |
| Correct | 22/32 | 23/32 | 27/32 | 24/32 | 31/32 | 31/32 |
| Tokens | 7.18 M | 10.78 M | 7.80 M | 8.90 M | 5.59 M | 5.99 M |
| Runs at or over 1 M tokens | 1 | 7 | 2 | 4 | 0 | 0 |
| Dollars | | 6.44 | 4.71 | 6.11 of 8 | 3.56 of 10 | 3.66 of 6 |

The new condition was used 28 times in 8 runs, and version 3's failing V06 answer in Apollo is correct. All 24 graph-arm runs used `missionsPage`; none named a deprecated list.

## The check

- **Token-volume failures fell from 4 to 0.** The largest run used 951 k tokens.
- **Counting failures fell from 2 to 0.**
- **Definitional failures stayed at 0.**
- **One new kind appeared**, in Claude's V05 answer in GraphQL Adapters, which stopped at the 80 tool-call limit. It had two causes. Seven intersections each applied a field to a source of plain ids, so each silently returned 0, and the agent only changed the path at call 78. It also spent 53 graph queries where GPT, correct in the same arm, spent 20.

The lead developer first judged the stop an agent-strategy limit stop and the check passed, then corrected the classification: a wrong operation that the tool accepted silently, which the check counts as a new kind. Their verdict: "Yes, the check fails". Under decision V4 the design returns to them, and `study2_freeze` keeps waiting. Version 4 stays in the harness as committed. The limits stay at 80 tool calls, 1 M tokens, 900 s and 3 retries: in the lead developer's words, "the limit did not cause the stop, the lost calls did".

The record is `study/evidence/study-2-calculate-v4/v4-record-20261105T021508Z.json`.

## Limits

- **One trial of four tasks.** A single run moves each count.
- **The causes are read from calls, not reasoning.** The transcripts hold no reasoning text, so the failure is classified from the agent's calls, results and stop.
- **The silent zero is not fixed.** A field that does not apply to a source of plain values is read as null, the same shape as the wildcard case version 4 refuses. It is left for the lead developer to decide.
