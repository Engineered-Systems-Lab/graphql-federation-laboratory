# Corpus 2

The task corpus of [Abstraction ladder study 2](../../docs/STUDY-2-DESIGN.md#the-corpus): a candidate pool of core tasks, the ambiguity set, the development set, their answer schemas and keys, the scorer, the scripted reference solution of every task in every arm and the stratified draw. It is laid out like [study 1's corpus](../corpus/README.md), so that `runner.py --corpus-dir study/corpus2` reads it. Study 1's corpus is unchanged and stays the harness default.

**The corpus is frozen by its manifest** (the Job `study2_freeze`, 2026-11-06): `corpus-manifest.json` has the status `frozen-2026-11-06` and SHA-256 `c57081e3fbcaaf298fc3591b486930fa4fb5dd88a0772f3c29798e26a1a354bb`, and it binds the four derived files, the three drawn files and the released inputs. The manifest's status governs: `pool.json`, `ambiguity.json`, `dev.json` and `keys-a.json` keep the stamp `draft, not frozen` and their bytes, because the draw record in `tasks.json` binds them (below). No task, key, schema or wording changed at the freeze. The frozen rows of the corpus in the [artifact classification table](../../project-governance/ARTIFACT-CLASSIFICATION.md) follow in the freeze's second transaction, because a frozen path cannot enter a checkpoint. No scored task was run before the freeze; the [freeze record](../evidence/study-2-freeze/freeze-record-20261106.json) holds every frozen hash.

**Blindness.** The author of the Guided Direct Access guide for study 2 must not read this folder. No task text leaves it: no commit message, Job note, report or message quotes a task, and `test_corpus2.py` checks that no tracked file outside this folder holds a question.

## Files

| File | Holds |
| --- | --- |
| `pool.json` | The candidate pool: every core task with its id, category, size, systems, tags (the mapping release it needs; for category D whether it is fully answerable without the stopped service), the question, its answer schema, a design note and, where one was needed, the interpretations the question pins down. For category D, `stoppedService` names the service the harness stops. |
| `ambiguity.json` | The ambiguity set (category F): 6 tasks over small data, `set: ambiguity`. Not drawn; the draw writes them into `tasks.json` after the 48 core tasks. |
| `dev.json` | The development set: 8 tasks, never scored, disjoint from the pool and the ambiguity set, in the harness's format (question, schema and expected answer together). Four of them are the calculation-tool development tasks: two large cross-system aggregations and two medium aggregations. |
| `keys-a.json` | The keys by the first derivation: for every task of the three sets, the expected answer, the checks and the declared variants, or for the ambiguity set the rubric (the closed list of accepted interpretations, each with its checks), with the hashes of the released files they come from. |
| `tasks.json`, `schemas.json`, `expected.json` | The scored corpus as the harness reads it: the draw of seed 313, the 48 drawn core tasks, then the 6 tasks of the ambiguity set. |
| `corpus-manifest.json` | The checksums of the four derived files, of the three drawn files `tasks.json`, `schemas.json` and `expected.json` as committed, and of the released inputs, with its status (below). The harness records its checksum in every run's plan identity (`corpusFreeze`), so the plan hash binds the manifest, which pins every file the scored run reads; the runner loads `tasks.json`, `schemas.json` and `expected.json` without checking them against it (a check reported at the freeze, for before the paid run). The analysis refuses a corpus whose manifest does not list the hash of `tasks.json`, or whose `tasks.json` differs from it. |
| `derive_a.py` | The first derivation: it authors the tasks and derives every key from the released files, never from a run (`--write` writes, without it compares). It reuses the readers of `federation/acceptance/derive_expected.py`. |
| `keys-b.json`, `derive_b.py`, `test_derive_b.py` | The second derivation, blind to the first (below), with its own tests, as its author wrote them. |
| `compare_keys.py` | The comparison of the two derivations and the cases the lead developer decided (below). |
| `wording-review/` | The review of the clarified closing instruction of five tasks (below): the author's proposal, its change note and the checker's confirmation, as they were given. |
| `scoring.py` | The scorer, scoring contract 2 of the harness. Standard library only. |
| `draw.py` | The stratified draw of the 48 scored core tasks, with a recorded seed. Run once, with seed 313. |
| `reference/` | The scripted reference solutions and their runner (below). |
| `test_corpus2.py` | The offline tests. |

**The manifest's status.** It was `draft, not frozen` until the freeze, which wrote `frozen-2026-11-06` with `derive_a.py --write --frozen 2026-11-06` on 2026-11-06 (the Job study2_freeze; the option is decision C1 of the Job study2_freeze_code). Only the manifest changes: `pool.json`, `ambiguity.json`, `dev.json` and `keys-a.json` keep their status `draft, not frozen` and their bytes, because the draw record in `tasks.json` holds the hashes of the pool and the keys (decision C2). The manifest's status governs. The freeze writes `corpus-manifest.json` alone, and refuses, writing nothing, when the manifest is already frozen (it names the held status) or when any derived or drawn file differs from the derivation (it names them). Without `--write` the check accepts either well-formed status and compares every file with the derivation under the status the committed manifest holds; any other status, and any hand edit, fails. A `--write` without `--frozen` refuses to replace a frozen manifest. `test_corpus2.py` covers both statuses, a malformed one, a hand edit of either, a second freeze and a freeze over a drifted file.

**The second derivation.** `derive_b.py` and `keys-b.json` were written by a GPT worker in a Codex cloud task with network access off, on a private repository that held only the keys-b package (the questions, `pool.json`, `ambiguity.json`, `dev.json` without its `expected` entries, `schemas.json` and the released data, built from lab commit `6c18afa638ce583dcd79125177ba9a210f5a3686`); it never saw `derive_a.py`, `keys-a.json` or `reference/`. Its commit there, the model, the date and the SHA-256 of both files are in `compare_keys.py` (`B_RECORD`), and the three files are here byte for byte as that task wrote them; neither derivation is edited. B's own format gives, per task, the answer, its basis, every declared variant with its reason and, for the ambiguity set, one answer per accepted interpretation, with the hash of every input and the assumptions it made. `derive_b.py` checks its inputs against the package's `MANIFEST.json`, which is not in the lab, so it and `test_derive_b.py` run only in a copy of the package (copy the package, add the three files to its `study/corpus2/`, run `python -B study/corpus2/derive_b.py` there); the study gate does not run them. `test_corpus2.py` checks instead that B's files are the recorded bytes and that every input B hashed is the lab's file as it was at the package's lab commit, read from Git (`compare_keys.input_problems`), `dev.json` after the rewrite that dropped its `expected` entries (rebuilt from that file), and apart from the package's own manifest and README, which the package hash covers; the lab's current question files may differ from what B received (below).

**The comparison.** `compare_keys.py` compares the two on all 90 tasks under the scorer: B's answer must score correct against `keys-a.json`, A's answer must equal B's after the scorer's folding or be one of B's variants, the declared variants are compared as sets, and the ambiguity set is compared per interpretation. Each difference went to the lead developer, who decided it on 2026-10-31; `DECIDED` names them with the decision, each bound to the exact differences and to the SHA-256 of its task and of both keys' entries, and `test_corpus2.py` passes only when the differences found are exactly those, on those same inputs; a changed question, schema or key needs a new decision. Six are both acceptable: one answer that writes null where the other writes an empty list, four tasks whose variants in B the checks of A already accept, and one ambiguity task whose example answer shows another accepted reading. One, a task of the development set where B declares a variant that A rejects, was decided a question left unclear; the clarification below decided it again. No key or derivation was changed by the comparison.

**The clarified closing instruction (2026-11-02).** The closing instruction of V06 of the development set and of E01, E03, E06 and E07 of the pool did not say whether groups with no qualifying records belong in the answer, and the scorer's `keyed` check refuses an answer that lists them. The lead developer decided (Job study2_corpus_wording, decisions Z1 to Z5) that they are left out, as both keys already give: each of the five questions now asks for the count per group, leaving out the groups with no such records, and E07 also says that members count whatever their duty status. Only those five questions changed; no answer, key, schema, check or data changed, and `keys-a.json` regenerates byte for byte. The four pool questions were written by the keys-B author task and confirmed by an independent Claude checker in two rounds, both with no network and without `derive_a.py`, `keys-a.json` or the guide; their files are in [wording-review/](wording-review/) (the proposal `proposal.json` has SHA-256 `62dea2ef6f46483616ac5d2555149486771b2029fdd3ca67845d2247347685db`), and the checker could not compare with `keys-b.json`, so it counted from the released data. V06 takes the same form in its own words and had no separate review. `compare_keys.py` reads B's inputs from Git at the package's lab commit, so B's recorded hashes still hold, and V06's decision is now `question clarified`, bound to the new task: B's variant that lists every type with a zero count is no longer a fair reading.

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

`draw.py --seed <n> --answerability <reports...> [--write]` checks the pool (unique ids, the required metadata, a key for every task), keeps only the pool tasks that the live real-backend answerability reports show correct in all five arms (a D task from the report of its own outage), refusing any report that is not verified real-backend evidence (verified provenance, one Missions dataset fingerprint shared by every report, which the draw records) or whose hashes differ from the current inputs for the rows it counts, requires the same evidence for every task and every accepted interpretation of the ambiguity set, then draws each category with `random.Random(seed)` by rejection until the quotas and the coverage hold, and writes `tasks.json` (the 48 drawn core tasks, then the 6 ambiguity tasks, with the draw record: seed, hashes of the pool, the ambiguity set, the keys and the reports), `schemas.json` and `expected.json`. Nothing is selected for its expected effect. It ran once, in the final preflight (the Job study2_preflight_final, 2026-11-02), after the Oracle-backed answerability check: seed 313, all 76 pool tasks eligible, from the 20 step 7 reports in [study/evidence/study-2-preflight/](../evidence/study-2-preflight/) (`07-answerability-*`). `test_corpus2.py` checks that the three files are byte for byte what `draw.py` writes from those reports and that seed, recomputed in memory.

## The data behind the keys

Missions release 1.2 (300 missions), the mapping releases 1.0 to 1.3 (an assets section in each, a crew section from 1.1; 1.2 and 1.3 hold the same crew section, 1.1 only ten entries), the Assets dataset 1.1 (32 assets) and the Personnel v2 snapshot `personnel-v2-large-004` (1,000 people): the releases study 1 used.

## Commands

From the repository root:

```sh
python -B study/corpus2/derive_a.py            # compare with the released files
python -B study/corpus2/derive_a.py --write    # rewrite the derived files (review the diff)
python -B study/corpus2/derive_a.py --write --frozen <YYYY-MM-DD>   # at the freeze only: the manifest's frozen status
python -B study/corpus2/compare_keys.py        # compare keys-a.json with keys-b.json; exit 0 when every difference is decided
python -B study/corpus2/reference/run_reference.py --arm gamma --fake
python -B -m unittest discover -s study/corpus2 -p "test_corpus2.py"
```

The area accepts JSON, Markdown and Python files.
