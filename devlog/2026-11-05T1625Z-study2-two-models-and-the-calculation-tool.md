# The two pinned models used the calculation tool differently across its rounds, and GPT-6.1 Sol answered every run of versions 3 to 5 correctly

Date: 2026-11-05T16:25Z
Subject: Recorded how Claude Sonnet 5.5 and GPT-6.1 Sol used study 2's calculation tool across its rounds, with version 5's result by model, the trap audit's outcome-linked runs, one contrasting pair, who audited and reviewed, a third-party summary labelled unverified and the Coordinator's reading
Status: Historical / non-normative
Provenance: Written on 2026-11-05 (UTC) by the worker of the Job study2_model_behaviour_devlog, before the commit that carries it, on main at `fa6a8d7b4e327c598a11b70ea5b0eecd337c0a76`. Every figure was recomputed from the committed score tables in `study/evidence/` (the seven runs named below), the audit's committed part in `study/evidence/study-2-trap-audit/`, the version 5 record, the harness's price table and the earlier entries of this devlog. One transcript was also read: Claude's GraphQL Adapters V05 run of `study2-confirm-v5-1`, in the machine-local results folder, whose run bundle is cited by checksum in `study/evidence/study-2-calculate-v5/checksums.json`. No answer key was read. The lead developer's Codex review of the draft (tree 035bec7) added the narrower context after the Coordinator's reading and the note on the study's cost basis. Three figures in the Job's approved scope differed from these records. The lead developer settled each one in the worker session on 2026-11-05, and the entry follows those decisions. The lead developer pasted the third-party summary on 2026-11-05. The Coordinator's reading comes from the Job's approved scope. Dated by the time of writing. No stack, run, network or vendor call was made for this entry, and it changes no design.

## Why an entry

The study pins two models: "Claude Sonnet 5.5 and GPT-6.1 Sol at medium effort, pinned" (`docs/STUDY-2-DESIGN.md`, line 32). The design compares architectures, not models, and states no tier comparison. Across the calculation tool's rounds the two models still behaved differently with the tool:

- **From version 3 on, every failure that decided a check was Claude's.** That holds for versions 3 and 4 and for both failures of version 5's passing confirmation.
- **Version 2 was different.** Its check failed on two counts. One was a new kind of failure, two Claude V05 answers. The other was token volume that did not fall, and that one failure was GPT's V05 run in Guided Direct Access, at 1.04 M tokens ([the version 2 entry](2026-11-04T1456Z-study2-calculation-tool-v2-fails-its-check.md)).
- **GPT answered all 48 runs of versions 3, 4 and 5 correctly.**

The lead developer asked whether the two models are of one tier, and found a third-party summary that calls them peers. This entry records the evidence, its limits, that summary and a reading of it before the freeze.

## Correct answers by model

These are V05 to V08 in Guided Direct Access, GraphQL Adapters, Apollo Federation and Cosmo Federation, one trial each, 16 runs per model. This is the basis of every check and of the earlier tool entries. Runs 1 and 2 also ran V01 to V04, and run 2 also ran Direct Access. In the four arms both models answered V01 to V04 correctly in both runs, so the misses below are all of their misses there.

| Run | Calculation tool | Claude correct | GPT correct | Claude's misses | GPT's misses |
| --- | --- | --- | --- | --- | --- |
| `study2-dev-notool-1` (run 1) | none | 10/16 | 12/16 | V05 in all four arms (two connection errors, one token stop, one abstention); V06 and V07 in Apollo | V05 in all four arms (wrong answers) |
| `study2-dev-tool-1` (run 2) | version 1 | 10/16 | 13/16 | V05 in all four arms (token stops); V06 in Apollo; V08 in Cosmo | V05 in Guided Direct Access, Apollo and Cosmo (token stops) |
| `study2-confirm-1` | version 2 | 12/16 | 15/16 | V05 in Guided Direct Access, GraphQL Adapters and Cosmo; V07 in Cosmo (all wrong answers) | V05 in Guided Direct Access (token stop) |
| `study2-baseline-totals-1` | none, graph with totals | 11/16 | 13/16 | V05 in all four arms (connection errors in Guided Direct Access and Apollo, token stops in GraphQL Adapters and Cosmo); V08 in Cosmo | V05 in Guided Direct Access and GraphQL Adapters (token stops); V08 in Guided Direct Access |
| `study2-confirm-v3-1` | version 3 | 15/16 | 16/16 | V06 in Apollo (conditions on fixed list positions) | none |
| `study2-confirm-v4-1` | version 4 | 15/16 | 16/16 | V05 in GraphQL Adapters (seven silent zero intersections, then the 80-call stop) | none |
| `study2-confirm-v5-1` | version 5 | 14/16 | 16/16 | V05 in Guided Direct Access (token stop at 1.055 M; 951 k and correct in version 4); V08 in Apollo (178 staff places against the key's 177, a count added by hand; its three `calculate` calls were right) | none |

The score tables are under `study/evidence/` (`study-2-preflight/09-*`, `study-2-calculate-redesign/`, `study-2-calculate-v3/`, `study-2-calculate-v4/` and `study-2-calculate-v5/`). The V08 count comes from [the version 5 entry](2026-11-05T1540Z-study2-calculation-tool-v5-passes-its-check.md).

## Tokens and calls by model

The last four runs share one graph (the adapters 1.1.0 with page totals), one set of pins and one set of tasks: V05 to V08, four arms, one trial.

| Run | Claude tokens | GPT tokens | Claude tool calls | GPT tool calls |
| --- | --- | --- | --- | --- |
| `study2-baseline-totals-1` (no tool) | 4.69 M | 4.21 M | 195 | 150 |
| `study2-confirm-v3-1` | 3.42 M | 2.17 M | 374 | 332 |
| `study2-confirm-v4-1` | 3.88 M | 2.11 M | 387 | 318 |
| `study2-confirm-v5-1` | 3.48 M | 1.97 M | 355 | 312 |

## Version 5 by model

- **Result.** GPT answered all 16 runs correctly. Claude answered 14, and both of its failures are in the table above.
- **Refusals.** Both models met refusals at about the same rate. Claude had 11 of its 144 `calculate` calls refused and GPT 12 of 155, 23 of 299 in all, as the version 5 entry records. Claude's token stop came after three refusals in 31 `calculate` calls.

The V05 runs, by arm and model:

| Arm | Claude | GPT |
| --- | --- | --- |
| Guided Direct Access | 49 calls, 26 turns, 1.055 M tokens, token stop | 55 calls, 23 turns, 0.70 M tokens, correct |
| GraphQL Adapters | 58 calls, 24 turns, 0.53 M tokens, correct | 56 calls, 19 turns, 0.25 M tokens, correct |
| Apollo Federation | 37 calls, 18 turns, 0.26 M tokens, correct | 17 calls, 17 turns, 0.10 M tokens, correct |
| Cosmo Federation | 49 calls, 25 turns, 0.37 M tokens, correct | 20 calls, 19 turns, 0.12 M tokens, correct |

## The trap audit and one contrasting pair

The audit replayed all 1,007 `calculate` calls of the four paid runs that offered the tool. It found four runs where a pattern was tied to an outcome, and all four are Claude's:

- version 2, GraphQL Adapters, V05;
- version 2, Cosmo, V05;
- version 3, Apollo, V06;
- version 4, GraphQL Adapters, V05.

GPT met some of the same mechanisms, for example exposures to P02, P15 and P19, with no outcome tied to them (`study/evidence/study-2-trap-audit/REPORT.md`, its summary table).

One pair shows the difference on the same task and arm: version 4, GraphQL Adapters, V05.

- **Claude** made 80 calls in 33 turns: 53 graph queries and 27 `calculate` calls. Calls 71 to 77 were seven intersections that returned zero without a refusal. It stopped at the 80-call limit.
- **GPT** made 52 calls in 20 turns: 20 graph queries and 32 `calculate` calls. It answered correctly.

## Who audited and reviewed

- **The trap audit** was made by a GPT auditor in Codex, read-only, outside the laboratory.
- **The reviews.** The version 5 record lists five reviews of version 5's code. Reviews 1, 2, 3 and 5 were the lead developer's, made with GPT-6.1 Sol in Codex. The model reviewed each candidate read-only and graded its findings P1 to P3. The lead developer coordinated, challenged, reviewed, and ultimately approved every change. Review 4 was the Coordinator's. Earlier rounds, versions 2 to 4, and their records were reviewed the same way.
- **Claude models** were the Migration Coordinator and the Job workers.

GPT-6.1 Sol is also one of the two pinned models. As a reviewer it read code and records, not runs of its own. None of these roles is a pinned model's run, and none looked at the pinned models' behaviour beyond the calls that the transcripts hold.

## A third-party summary, unverified

The lead developer pasted a web search summary on 2026-11-05. It cites anthropic.com, benchlm.ai, artificialanalysis.ai and emergent.sh. The project has not checked any of its claims, and they are given here as the summary gave them:

- **Price:** identical base list prices, 2 dollars per million input tokens and 10 per million output tokens.
- **Context windows:** about 1,000,000 and 1,050,000 tokens.
- **Benchmarks:** Sonnet ahead on coding benchmarks and in output speed and latency; Sol ahead on an overall benchmark score and cheaper on cached input.
- **Practical testing**, in its words: Sonnet "tends to warn and attempt execution on unconventional parameters", and Sol "may trigger stricter refusals".

**The study's own cost basis** is not that summary. The harness's dated price table (`study/harness/prices.json`, 2026-10-20) gives both models the same prices per million tokens: 2 dollars for input, 0.10 for cached reads and 10 for output. Cache writes are priced separately, at 2.50 for Claude Sonnet 5.5 and 0 for GPT-6.1 Sol, whose interface reports no cache-write tokens. The study's dollar figures come from this table. The summary's claim that Sol is cheaper on cached input is not reflected in it.

## The Coordinator's reading

This reading is the Coordinator's, from 2026-11-05. It is not a finding of the study.

**Before version 5.** The two models are offered as peers by price and by that summary. So the gap that the runs show is one of behaviour with this tool, not of tier. Claude pressed on with unconventional tool uses: fixed list positions, a record field over plain ids, and repeated empty results before changing course. GPT took fewer and cleaner steps. Version 5's strictness pass, which refuses or flags silent wrong uses, bears on exactly that.

**After version 5.** The refusals removed Claude's silent wrong uses, and the version 4 GraphQL Adapters V05 run is now correct. Both models met refusals at the same rate. Claude still spends more tokens and calls per V05 run, about 1.8 times GPT's tokens over all 16 runs, and that is what left its Guided Direct Access V05 run over the token limit.

For that ratio, the committed tables give 1.77 over all 16 runs (3,482,921 tokens against 1,972,941) and 1.88 over the four V05 runs.

### What the evidence supports, more narrowly

This is later context from the lead developer's Codex review of this entry's draft, checked by the worker against the run files. The reading above stays as the Coordinator wrote it.

- **Price and the summary explain nothing.** Equal list prices and an unverified benchmark summary say nothing about why the runs differed. They cannot settle whether the gap is one of tier or of behaviour.
- **"Fewer and cleaner steps" holds for the contrasting pair, not across the rounds.** In version 2's confirmation GPT made 327 tool calls and Claude 280.
- **What one transcript shows.** Version 5's GraphQL Adapters V05 run with Claude shows the refusal at work:
  - Call 50 was an intersection with a record field over a source of plain ids, and version 5 refused it.
  - Call 51 put the field in the source's path instead and was accepted.
  - Calls 51 to 57 returned 1, 69, 2, 297, 126, 110 and 11. These are the counts the audit computed independently for the seven intersections that returned zero in version 4.
  - The run finished correctly.
- **What one trial cannot show.** It cannot show how much the refusal contributed to that outcome. Nor can it show why the Guided Direct Access V05 run crossed the token limit in version 5 after staying under it in version 4.

## Limits

- **One trial** per task and arm. A single run moves each count.
- **Four aggregation tasks.** V05 to V08 are the calculation tool's stress test, not the mix of the scored corpus, which has 10 aggregation tasks among its 48 core tasks.
- **Behaviour is read from calls.** The transcripts hold no reasoning text.
- **No model comparison.** The study does not compare the two models and makes no claim that one is better. This entry records an observation about one tool, four tasks and a few runs.
