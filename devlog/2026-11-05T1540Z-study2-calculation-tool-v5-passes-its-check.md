# The calculation tool's version 5 makes one strictness pass from an independent audit, and passes its declared check in its last round

Date: 2026-11-05T15:40Z
Subject: Built version 5 of study 2's calculation tool as one strictness pass from an independent audit of the four paid runs, replayed every stored call through it, ran its paid confirmation of V05 to V08 against the existing no-tool baseline, and recorded the declared check's first pass
Status: Historical / non-normative
Provenance: Written on 2026-11-05 (UTC) by the worker of the Job study2_calculate_v5, before the commit that carries it. Sources: the confirmation's score table and manifest (copied into `study/evidence/study-2-calculate-v5/`), the run folders and transcripts in the machine-local results folder, cited by checksum, the audit's committed part in `study/evidence/study-2-trap-audit/`, and the lead developer's decisions in the worker session. Dated by the time of writing, just after the verdict. The confirmation ran from 14:41Z to 15:15Z, from one line in the lead developer's terminal; the worker never held an API key.

## The audit and the last round

Versions 2, 3 and 4 had each repaired one trap and failed the declared check on the next. Before a fifth attempt, an independent audit looked at all of them at once. A GPT auditor, in a task started outside the laboratory, read-only, with no network, no model call and no answer key, replayed all 1,007 `calculate` calls of the four paid runs under each run's own version of the tool.

- **25 patterns** of silent or wasteful use, each with one generic fix. 24 were still possible in version 4.
- **Four were tied to an outcome:** a re-fetch used while more records were held, a total from two pages of three, conditions on fixed list positions, and a record field over plain ids.

The lead developer decided that version 5 would be one pass over every pattern and the last round of the tool: if it failed the check, it would be kept with a recorded deviation and no further redesign. The audit's readable part, its summary and its checksums are kept as evidence.

## Version 5

The output of a call that versions 4 and 5 both accept is what version 4 gave, with one exception: a step in brackets is new syntax and can give a value where version 4 gave null. What else changes is which calls are accepted and what the agent reads around the output.

- **Refusals.** A wrong use that the tool can see is refused, with every problem of the call named at once and the shapes of its sources. Examples are a field on a source of plain values, a field that no record has, and a `*` at an object.
- **A coverage line.** After the read line it says, only when there is something to say, how many records lack a field, the size of each set, and that the sources hold fewer records than the total a list states. It never says that a list is complete.
- **Warning lines.** At most two, never a refusal, for what only the agent can judge: a repeat, held pages left out, conditions on fixed list positions.
- **One addition.** The replay showed 15 calls that named a field no record has to get one total. The lead developer answered "Empty group_by", so an empty list gives one group over all records.

The draft went through five reviews before it landed. The fourth mattered most. Pages that did not repeat the total were counted apart from the page that stated it, so 121 of the 166 lines that said records were missing were wrong on the stored calls. After the fix none was. The fifth review ended the attempts to tell lists apart: nothing a result holds can show that two lists of one name are different lists, so they count together, and a list is called short only when all the records of its name are fewer than its total.

Version 5 landed in `c8ff35cecfa503284dbe41101285e6f61be29051`. The debug run on the live GraphQL Adapters stack then found one warning that called a result absent when only its other pages were left out. The lead developer chose to fix it first, in `7a64dc213667fb53354217a66e0b558225ab1e2b`.

The free replay of the stored calls, with the agents' calls held fixed, showed that version 5 refuses 71 calls that version 4 accepted and gives version 4's output for all 883 calls that both accept; none of them writes a step in brackets. Of the four patterns tied to an outcome, the replay shows three answered: the record field over plain ids is refused, and the fixed positions and the re-fetch are warned of. The total from two pages of three is not caught, because those stored results state neither a total nor `hasMore`. The replay cannot show what an agent does after a refusal or a new line.

## The paid confirmation

The run used the same shape and pins as version 4's confirmation, against the existing baseline `study2-baseline-totals-1`.

| | Run 1, no tool | Run 2, v1 | Confirm-1, v2 | Baseline, no tool | Confirm, v3 | Confirm, v4 | Confirm, v5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Correct | 22/32 | 23/32 | 27/32 | 24/32 | 31/32 | 31/32 | 30/32 |
| Tokens | 7.18 M | 10.78 M | 7.80 M | 8.90 M | 5.59 M | 5.99 M | 5.46 M |
| Runs at or over 1 M tokens | 1 | 7 | 2 | 4 | 0 | 0 | 1 |
| Dollars | | 6.44 | 4.71 | 6.11 of 8 | 3.56 of 10 | 3.66 of 6 | 3.45 of 6 |

The three runs that failed in earlier rounds are correct, version 4's among them, which finished in 58 calls. Version 5 refused 23 of 299 calls, against 12 of 308 in version 4, and 15 of the 23 were followed by an accepted call. All seven lines that said records were missing were right. All 24 graph-arm runs used `missionsPage`; none named a deprecated list.

## The check

- **Token-volume failures fell from 4 to 1.** Claude's V05 run in Guided Direct Access stopped at the 1 M token limit. The same run was correct in version 4 at 951 k tokens. Version 5's own text is estimated at about 10,500 of its tokens; the record attributes none of the others. Among its calls were one union naming 180 sources, refused for more than 100, two accepted unions of 90 sources each, and six views of about 5,000 characters.
- **Counting failures fell from 2 to 1.** Claude's V08 answer in Apollo gave 178 staff places where the key says 177. Its three `calculate` calls were right. It added 161 crew places and 17 commanding-officer places by hand and did not count a person once per mission.
- **Definitional failures stayed at 0.**
- **No new kind appeared.**

The worker proposed that the check passes on its letter and named what decides it: the V08 failure read as a count made by hand, as the baseline's two answers of 103 were. Read as definitional or as a new kind, the check fails. The lead developer's verdict: "Yes, it passes". Version 5 stays in the harness as committed, and no deviation is recorded. The limits stay at 80 tool calls, 1 M tokens, 900 s and 3 retries.

The record is `study/evidence/study-2-calculate-v5/v5-record-20261105T153306Z.json`.

## Limits

- **Not every audited pattern is caught.** A list whose results state no total and no `hasMore` gives the tool nothing to compare, so a total built from too few of its pages passes unremarked.
- **One trial of four tasks.** A single run moves each count, and this pass is weaker than the two rounds before it: 30 correct against 31, and one failure in each class that must fall where they had none.
- **The causes are read from calls, not reasoning.** The transcripts hold no reasoning text.
- **Lists of one name count together.** In the graph arms the missions and the personnel are both lists named `items`. In one correct run 10 calls therefore carry a true and useless line, that the records are more than the total of 300: nine name 1,300 records and one names 400. A shortfall of one list is also not said when another list of its name holds enough records to fill it; no stored or confirmed call was of that kind.
- **One count the tool cannot make in one call.** Records read through a list inside a list do not carry the record they belong to, so "a person once per mission" needs a call per mission or the agent's own count.
- **The token limit is close in Guided Direct Access.** The V05 run with Claude used 951 k tokens in version 4 and crossed 1 M in version 5.
