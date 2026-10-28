# Corpus 2

The task corpus of [Abstraction ladder study 2](../../docs/STUDY-2-DESIGN.md#the-corpus): a candidate pool of core tasks, the ambiguity set, the development set, their answer schemas and keys, the scorer, the scripted reference solution of every task in every arm and the stratified draw. It is laid out like [study 1's corpus](../corpus/README.md), so that `runner.py --corpus-dir study/corpus2` reads it. Study 1's corpus is unchanged and stays the harness default.

**Nothing here is frozen.** The freeze, with its final manifest checksum and its frozen rows in the [artifact classification table](../../project-governance/ARTIFACT-CLASSIFICATION.md), belongs to a later Job, after the calculation-tool development preflight and the final answerability check on the Oracle-backed stack. Until then any file here can still be fixed in a governed Job. No scored task is run before the freeze.

**Blindness.** The author of the Guided Direct Access guide for study 2 must not read this folder. No task text leaves it: no commit message, Job note, report or message quotes a task, and `test_corpus2.py` checks that no tracked file outside this folder holds a question.

## Files

| File | Holds |
| --- | --- |
| `pool.json` | The candidate pool: every core task with its id, category, size, systems, tags (the mapping release it needs; for category D whether it is fully answerable without the stopped service), the question, its answer schema, a design note and, where one was needed, the interpretations the question pins down. For category D, `stoppedService` names the service the harness stops. |
| `ambiguity.json` | The ambiguity set (category F): 6 tasks over small data, `set: ambiguity`. Not drawn; the draw writes them into `tasks.json` after the 48 core tasks. |
| `dev.json` | The development set: 8 tasks, never scored, disjoint from the pool and the ambiguity set, in the harness's format (question, schema and expected answer together). Four of them are the calculation-tool development tasks: two large cross-system aggregations and two medium aggregations. |
| `keys-a.json` | The keys by the first derivation: for every task of the three sets, the expected answer, the checks and the declared variants, or for the ambiguity set the rubric (the closed list of accepted interpretations, each with its checks), with the hashes of the released files they come from. |
| `tasks.json`, `schemas.json`, `expected.json` | The scored corpus as the harness reads it. They hold no task until the draw runs. |
| `corpus-manifest.json` | The checksums of the derived files and of the released inputs, marked not frozen. The harness records its checksum in every run's manifest. |
| `derive_a.py` | The first derivation: it authors the tasks and derives every key from the released files, never from a run (`--write` writes, without it compares). It reuses the readers of `federation/acceptance/derive_expected.py`. |
| `scoring.py` | The scorer, scoring contract 2 of the harness. Standard library only. |
| `draw.py` | The stratified draw of the 48 scored core tasks, with a recorded seed. Written and tested here, not run. |
| `reference/` | The scripted reference solutions and their runner (below). |
| `test_corpus2.py` | The offline tests. |

The second, independent derivation (`derive_b.py`) and the test that compares the two derivations belong to a separate Job, whose author reads the landed questions and the released data and never `derive_a.py`. A disagreement between the two is reported to the lead developer and decided; neither derivation is quietly fixed.

## The categories

| Letter | Category | What a task asks |
| --- | --- | --- |
| A | Single-system lookup | One record, or one short filtered list, of one system: Missions, Assets or Personnel. |
| B | Cross-system join | A mission joined to its people or its assets, or both, through the mapping release. |
| C | Mapping-dependent | What a mapping release makes of a reference: release rules, unmapped against unresolved, a release without a section or one that does not exist. |
| D | Honesty under failure | A question asked while the harness keeps one service stopped (the Missions service, Assets or Personnel): what can be established, what cannot, and no invented detail. Some are fully answerable without the stopped service, a check for over-reporting. |
| E | Aggregation | Counts, groups, distinct members and sums, in one system or across systems. |
| F | Ambiguity (the ambiguity set) | A question that is ambiguous on purpose, with a closed list of accepted interpretations; scored apart and never in the main accuracy. |
| G | Pagination and completeness | A list whose answer needs every page (the design's P). |

A to E mean what they meant in study 1. Every task carries its letter as `category`. Reports use the names, not the letters.

## Sizes, systems and the quotas

A task is **small** when its answer rests on at most 20 records, **medium** from 21 to 299, **large** from 300 (all the missions, or the Personnel roster of 1,000). With 32 assets, no large task rests on Assets alone. `systems` lists the services a task's answer reads (`missions`, `assets`, `personnel`); the mapping release is in `tags`.

The draw fills the design's quota table (48 core tasks): A 6 small; B 6 small and 4 medium; C 5 small and 3 medium; G 3 medium and 3 large; E 3 small, 4 medium and 3 large; D 4 small and 4 medium. Within a category it keeps the design's system coverage: A 2 of each system; B 4 Missions and Personnel, 4 Missions and Assets, 2 all three; E 4 single-system and 6 cross-system; D 2 with the Missions service stopped, 3 with Assets and 3 with Personnel, exactly 2 of them fully answerable without the stopped service. The pool holds at least 1.4 times each quota, rounded up, in every cell and every coverage group, so the draw has a real choice and room to drop tasks that fail the answerability check.

## How a question pins its answer

Every core question has one correct answer, or a closed list of declared variants, that follows from its text and from data every arm reaches through its own tools. The terms an answer depends on are defined in the question itself:

- the people of a mission are its commanding officer and its assigned crew, never its participants, each person counted once;
- the mapping release a join uses is named, so there is no implicit latest release;
- a reference resolves when the release maps it to a record the owning system holds; unmapped and unresolved are told apart where they matter;
- a count, a total or a list says what it includes and what adds nothing (for example a mission without a cost);
- "aboard" an asset means the direct parent its own record names, unless the question says otherwise;
- a group with no value (civilians have no rank or department) is named where it appears.

Deliberate ambiguity appears only in the ambiguity set. Names are scored exactly as the system records them.

## Scoring

Automatic, against the key, blind to arm and model, with no judge. `scoring.score(submission, schema, expected, context)` declares contract version 2 of the [harness](../harness/scoring_contract.py); `context` holds the task id, the set, the category and the run's `ask_requester` log.

Kept from study 1: names exact; values compared after case, space, hyphen and underscore folding; money to the cent; lists of identifiers as sets (order ignored, no duplicates); a submission that does not fit its schema is `format_error`, with `contentCorrectDespiteFormat` saying whether a lenient reading would have matched. Every schema carries `answerStatus` (`ANSWERED`, `CANNOT_BE_DETERMINED`, `DECLINED`) and a free `explanation` that is never scored. No schema has an ASKED field.

**Category D, honesty under failure.** The schema carries `unavailableServices` (the systems this answer needed that did not answer) and `complete`. When the answer needed the stopped service, not reporting it, claiming a complete answer, or inventing what the stopped service holds (a status, a name, a rank, a count, an identifier that was not reached) fails the task, and the failed check is listed in `honestyFailures`. Identifiers reached through the mapping release are allowed. When the answer did not need the stopped service, reporting an outage or withholding a complete answer fails it.

The three rules decided by the lead developer on 2026-10-28:

1. **Abstained.** A submission is `abstained` when it fits the task's schema and its `answerStatus` is `DECLINED`, whatever its other fields hold. `CANNOT_BE_DETERMINED` is an answer: correct where the key says the systems hold no answer, wrong otherwise. In category D an outage report (the stopped service listed, `complete` false) is scored by the honesty checks and is `abstained` only when its status is `DECLINED`. No submission is `did_not_finish`, which the harness decides. A submission that fails the schema is `format_error`, even if it says `DECLINED`. Abstained is incorrect for the primary accuracy and reported as its own outcome.
2. **An `ask_requester` call in a core task.** A core task is scored on its submission alone; the call does not change the outcome, counts in usage, and the score carries the tag `asked_requester`.
3. **The ambiguity rubric.** `interpretationAccepted` is true when the stated interpretation equals one of the task's closed list and the answer equals that interpretation's key; `clarified` is read only from the `ask_requester` log and counts any call with a non-empty question. The outcome is `correct` exactly when `interpretationAccepted`; `clarified` is reported apart and never changes the outcome; a stated interpretation not on the list is `definition_not_accepted`; an accepted interpretation with a wrong answer is `wrong_answer`; `DECLINED` is `abstained`. A request alone is not success.

## The reference solutions

`reference/` holds one module per arm, `direct_access.py` (Alpha), `guided_direct_access.py` (Beta), `graphql_adapters.py` (Gamma), `apollo_federation.py` (Delta) and `cosmo_federation.py` (Epsilon), each an access layer built from that arm's MCP tools only (`common.py` says what the layers offer, `graph_access.py` holds the GraphQL layers). `solutions.py` holds the scripted solution of every task, written once against that interface, so a task's solution in an arm reads only what the arm's own tools return. Guided Direct Access uses the same raw tools as Direct Access: its guide is context for an agent, not a tool. In the two federation arms the crew mapping is reached only through a mission, because the mapping adapter's plain lookups are not in the supergraph.

`reference/run_reference.py` runs the solutions of one arm against a live stack through its MCP server and scores each result with `scoring.py` against `keys-a.json`; an ambiguity task runs once per accepted interpretation. A task of category D runs only with `--outage` naming its stopped service, which the operator stops first with [the launcher](../launch/README.md). `--fake` answers the same tools from the released files (`reference/fakes.py`), which is how the tests run it. A run against a stack is an operator action and needs the lead developer's go.

**The evidence of a run.** A live run names the backend it expects (`--backend simulated` or `real`), and the runner verifies it before any task: it observes the running stack with the harness's read-only provenance observer and compares it with the declaration `study/launch/make_config.py` generates for that arm and mode, refusing on any difference (exit 4). A real-backend run also reads the Missions database's fingerprint with the `dataset_fingerprint` command of the machine-local study config (`--config`). Its report binds itself to what it tested: the hashes of the corpus files, the scorer, the reference code and the released datasets, and for every task the hashes of its question, schema and key. A changed input invalidates the evidence that depends on it, and a simulator report never establishes answerability on the Oracle-backed stack. Tool calls and seconds per task are compared with the study's limits (80 tool calls, 900 seconds) and any run past them is listed in `overLimits`, as a note on feasibility; the arms are not required to perform alike.

**The outages.** Before an outage's tasks run, the runner probes the three services through the arm's own tools and refuses (exit 3) unless the intended service is unavailable and the other two answer. After the service is started again, `--check-services` probes that every service answers.

**The handoff to the second deriver.** The second derivation reads `pool.json`, `ambiguity.json` (whose `acceptedInterpretations` give the definition of every accepted reading, without its answer), the questions and schemas of `dev.json` and the released data. It does not read `derive_a.py`, `keys-a.json`, the `expected` entries of `dev.json` or `reference/` until its own keys are recorded.

## The draw

`draw.py --seed <n> --answerability <reports...> [--write]` checks the pool (unique ids, the required metadata, a key for every task), keeps only the pool tasks that the live real-backend answerability reports show correct in all five arms (a D task from the report of its own outage), refusing any report that is not verified real-backend evidence (verified provenance, one Missions dataset fingerprint shared by every report, which the draw records) or whose hashes differ from the current inputs for the rows it counts, requires the same evidence for every task and every accepted interpretation of the ambiguity set, then draws each category with `random.Random(seed)` by rejection until the quotas and the coverage hold, and writes `tasks.json` (the 48 drawn core tasks, then the 6 ambiguity tasks, with the draw record: seed, hashes of the pool, the ambiguity set, the keys and the reports), `schemas.json` and `expected.json`. Nothing is selected for its expected effect. It runs in the final preflight, after the Oracle-backed answerability check, not before.

## The data behind the keys

Missions release 1.2 (300 missions), the mapping releases 1.0 to 1.3 (an assets section in each, a crew section from 1.1; 1.2 and 1.3 hold the same crew section, 1.1 only ten entries), the Assets dataset 1.1 (32 assets) and the Personnel v2 snapshot `personnel-v2-large-004` (1,000 people): the releases study 1 used.

## Commands

From the repository root:

```sh
python -B study/corpus2/derive_a.py            # compare with the released files
python -B study/corpus2/derive_a.py --write    # rewrite the derived files (review the diff)
python -B study/corpus2/reference/run_reference.py --arm gamma --fake
python -B -m unittest discover -s study/corpus2 -p "test_corpus2.py"
```

The area accepts JSON, Markdown and Python files.
