# Study 2 reached the ceiling: what its design measured and what it did not

Date: 2026-11-08T20:34Z
Subject: A review after study 2's results page landed at commit `114b9b48f391725ed5a804ec2bca81cc0482ac3c`: why the planned accuracy comparison had no room to work, what the design measured instead, and how GraphQL vendors frame their products against what the two studies measured
Status: Historical / non-normative
Provenance: Drafted on 2026-11-08 (UTC) by the Migration Coordinator from a conversation with the lead developer in the Coordinator session, dated by the time the first draft was finished, and revised the same day after a review by another vendor's model (GPT), which raised two P2 and two P3 points and a note on a study 3; all were taken. A second GPT review, of the candidate at its first preview (tree `5cfdae7`), raised one P2 and three P3 points, and its follow-up on the second preview (tree `d6377e5`) one more P3 attribution; all were taken in the worker session, and the vendor corrections rest on that review, because the worker read no vendor page. Sources: the two reports, the study 2 design, `study/analysis2/PLAN.md`, `study/corpus2/README.md`, and `study/evidence/study-2/tables.md` and `scores.csv` at commit `114b9b48f391725ed5a804ec2bca81cc0482ac3c`, read only; vendor pages read on 2026-11-08. The counts marked "Coordinator's count" were read from the committed `scores.csv` for this entry; they are descriptive, are not part of the frozen analysis and change no reported result. The explanations offered below are hypotheses that the scored run did not test; everything under "Reading" is interpretation after the results were seen, not a finding of either study.

## What happened

- **The four full arms reached the observed ceiling.** In the core set, GPT-6.1 Sol answered 48 of 48 in every full arm; Claude Sonnet 5.5 answered 45 to 47 of 48 (study 2's report, the descriptive table). High observed accuracy is not a finding that the arms do not differ: the planned comparison that would test that could not be computed.
- **The primary model could not be fitted.** The logistic GEE needs wrong answers in its cells; with GPT's cells all right, it is not estimable (separation), and study 2 makes no accuracy verdict.
- **What the plan prespecified for this case.** It stops when the primary is not usable, with "no fallback without the lead developer's word" (section 4, rule 5), and it has no replacement primary estimator. It did prespecify two sensitivities that can run on such data, a cluster bootstrap of pooled proportions and a Bayesian mixed model (section 8, rules 3 and 4), and the plan lets neither decide.
- **Fit failure was foreseeable.** The frozen power figures come from study 1's table at 48 tasks: P1 65.0 and P2 51.7 percent to establish equivalence at a true difference of 0, with no fit refused. The development runs' table, given in the plan for information, had 49 of its 400 simulated fits unusable at a true difference of 0 (section 12, rule 5). The plan thus left the confirmatory verdict unavailable in a case its own simulation showed could occur.
- **Study 1 had more spread.** Its confirmatory model gave Alpha 60.9 percent, Beta 83.1, Delta 86.5 and Epsilon 84.6. The design names one limit of carrying that over: "a corpus with a calculation tool may spread differently".

## Three questions the lead developer asked

### Were the questions tuned too far?

Nothing in the record shows it. The 48 core tasks were drawn by a seeded stratified draw from a pool of 76 questions in the enterprise's words, after a scripted reference solution showed each one answerable in each arm. What changed between the studies was the support every arm got:

- **`calculate`,** in every arm, frozen at version 5 after a declared check (the devlog entries of 2026-11-05);
- **page fields with totals** in the three graph arms, an outcome-informed change made before the freeze: development answers to a task that needs all 300 missions counted 200 of them (the design, "The arms");
- **a guide** for Guided Direct Access, written blind for study 2;
- **the standalone lookups** in GraphQL Adapters, which study 1's Gamma lacked as built.

Each answered a failure seen in development or in study 1. A hypothesis, which the scored run did not isolate, is that together they removed most of the ways a full arm could fail.

### Were the questions made too clear?

In part, by design. Study 1 scored its deliberately ambiguous tasks with the rest; no run of its T15 was scored correct under the frozen key in any scenario, and its report lists a wording mismatch on it. Study 2 kept ambiguity in a separate set of 6 tasks on small data, "so the ambiguity is the only difficulty", scored apart and exploratory (decision I), with an `ask_requester` tool in every arm.

Under its rubric a run is correct exactly when its stated interpretation is on the task's closed list and its answer matches that interpretation's key; whether it asked is recorded apart and never changes the outcome (`study/corpus2/README.md`, rule 3). The six tasks by arm and model (Coordinator's count):

| Arm | Claude: correct | Claude: asked | GPT: correct | GPT: asked |
| --- | --- | --- | --- | --- |
| Direct Access | 4/6 | 1 | 5/6 | 5 |
| Guided Direct Access | 5/6 | 1 | 6/6 | 5 |
| GraphQL Adapters | 6/6 | 0 | 6/6 | 5 |
| Apollo Federation | 6/6 | 0 | 6/6 | 5 |
| Cosmo Federation | 6/6 | 0 | 6/6 | 5 |

- GPT was correct on 6 of 6 in every full arm, so adding these six observed outcomes to the core counts would still leave its cells all correct. That says nothing about what a different scored ambiguity set would have done.
- The models behaved differently: GPT asked in 5 of the 6 tasks in every arm, and Claude almost never asked. The asking is behaviour, not score.

### Was the primary measure the wrong one?

This is the main lesson. Accuracy left little room in the observed data: GPT was right on 48 of 48 in every full arm and Claude on 45 to 47, so the counts can be described, but the planned GEE refuses cells that are all right and could not judge the planned accuracy contrasts; the exploratory effort measures did separate the arms. On cost, time and 1 + tool calls (exploratory, unadjusted p; study 2's report), federation over GraphQL Adapters was 0.85 [0.77, 0.94], 0.90 [0.82, 0.99] and 0.79 [0.72, 0.86]; federation over Guided Direct Access was 0.77 [0.68, 0.87], 1.33 [1.14, 1.55] and 1.29 [1.10, 1.52].

What these measure: the agent's tool calls, which include `calculate` and `ask_requester` calls (the design, the scoring contract, "Usage"), the elapsed time of a run, and the model cost estimated from its tokens at the dated prices. They are not counts of backend round trips or of client-side stitching.

## Where the misses fell

The data was the same in every arm: two identifier systems joined through a mapping with release rules, SOAP and REST interfaces, stopped services, and lists of 300 or more records. The corpus rule required a scripted path through it in every arm.

| Category | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation | Direct Access (Coordinator's count) |
| --- | --- | --- | --- | --- | --- |
| Single-system lookup | 12/12 | 12/12 | 12/12 | 12/12 | 8/12 |
| Cross-system join | 20/20 | 18/20 | 20/20 | 20/20 | 13/20 |
| Mapping-dependent | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| Honesty under failure | 15/16 | 16/16 | 16/16 | 16/16 | 7/16 |
| Aggregation | 20/20 | 20/20 | 19/20 | 19/20 | 10/20 |
| Pagination and completeness | 12/12 | 11/12 | 12/12 | 12/12 | 9/12 |

The four full arms come from `tables.md`, "Exploratory: results per category".

- The six misses in the four full arms were all Claude's, spread over joins, pagination, aggregation and one outage task (Coordinator's count).
- Direct Access had `calculate` and `ask_requester` like every arm, and no guide or adapters. It was lower than the full arms in every category except mapping-dependent. It ran as one block, last, so its counts are confounded with that window: they support no comparison, and they cannot show that the guide or the adapters closed those gaps. That is a hypothesis.

## How GraphQL vendors frame their products

Read from the vendors' own pages on 2026-11-08; this is their framing, not evidence:

- **API sprawl and team scale.** One composed graph over many services; federation lets each team own its subgraph, the platform composes the subgraphs into one schema and the router plans and executes queries against it, with schema checks, guardrails and observability for platform teams ([WunderGraph Cosmo](https://wundergraph.com/cosmo), [What is WunderGraph?](https://wundergraph.com/answers)). Cosmo Connect advertises fronting REST, gRPC or SOAP services without rewriting them.
- **The governed entry point for agents.** Apollo's MCP Server turns chosen GraphQL operations into agent tools, and its pitch is that a supergraph makes every subgraph reachable by agents without one MCP server per API ([Apollo MCP Server](https://apollographql.com/apollo-mcp-server), [Apollo Summit 2026](https://www.apollographql.com/blog/announcement/apollo-summit-2026-turn-your-api-platform-into-your-ai-platform)).
- **Reliable and accurate agent behaviour.** Apollo's article on orchestrating APIs for an agent says its approach "produces the most reliable agent behavior", crediting live schema discovery, explicit types and focused responses, with no measured evidence in the article ([Apollo](https://www.apollographql.com/blog/how-to-orchestrate-multiple-apis-for-your-llm-agent)). Hasura's PromptQL sells accuracy on enterprise data by running the model's plan outside the model ([PromptQL](https://hasura.io/promptql)); the authors of the Data Agent Benchmark report that agents usually choose the right data and then fail at the computation ([the benchmark paper, section 3.3.3](https://arxiv.org/html/2603.20576v1#S3.SS3.SSS3)), an observation that PromptQL's write-up quotes in its own framing ([PromptQL's write-up](https://promptql.io/blog/berkeley-data-agent-benchmark-will-text-to-sql-ever-be-good-enough)) and a third-party review relays ([review](https://www.eesel.ai/blog/promptql-review)), the kind of failure `calculate` addressed in every arm of study 2.

Set against what the two studies measured:

| Product claim | What the studies measured |
| --- | --- |
| Many teams, independent ownership, composition | Nothing: one synthetic estate and no teams |
| Governance: schema checks, access control, what an agent may call | Nothing; field-level authorization is open in [the plan](../docs/PLAN.md) |
| API evolution over time | Nothing: one frozen release of each system |
| Reliable or accurate agent behaviour | Study 1, confirmatory: the adapters behind the Apollo router over raw access, the combination and not the router alone; study 2, the primary, not estimable at the observed ceiling |
| Efficiency for the agent | Study 2, exploratory: the agent's tool calls, elapsed time and estimated model cost, not backend round trips |

## Reading

Interpretation after the results were seen, recorded as the conversation's conclusion and not as a finding:

- With the support every arm had, both models answered almost every core task through any of the four full arms. Why is a hypothesis: the support added between the studies may have closed the failure modes that study 1 measured, but the scored run did not isolate any of it.
- The largest observed difference in accuracy, raw access against the rest, came from an exploratory block run last, and it cannot carry a claim.
- Study 2 does not show that federation fails to help accuracy, nor that the arms are equal in accuracy. It shows that the design could not turn the observed counts into a verdict, and that the plan, by its own rule, left no verdict in that case.
- The product claims that the lab measured least are the broader ones: governance, team ownership and API evolution. Reliability for agents is claimed too, and study 2 put its confirmatory test there.

## Open choices for a study 3

Listed as the conversation left them; whether there is a study 3, and its design, is the lead developer's decision.

- A primary measure that can vary when every arm can answer: the effort to a correct answer (cost, time or tool calls), with accuracy as a floor each arm must clear. Such a measure needs a prespecified rule for failed runs: comparing correct runs only can make an arm look efficient when it fails on the tasks that would have cost it the most.
- Difficulty that no arm resolves fully: messier data, or an arm in the confirmatory set that leaves part of the difficulty in place.
- Ambiguity back in the scored set, as clean tasks where it is the only difficulty, with a rubric that accepts any reading the data supports and the clarification tool kept.
- A prespecified method for cells that are all right or all wrong, with the simulated rate of unusable fits reported and a rule for what then decides.
- A weaker model, or a lower effort setting, to leave room for the architecture to matter.
- Questions closer to the broader product claims: what each layer lets a team control or change over time, not only whether the answer is right.
