# Corpus 3

The task corpus of study 3, strand 1: whether GraphQL federation reduces agent effort (tool calls, cost) on cross-system lookups, with accuracy only as a floor. It is study 2's checked pool and ambiguity set, carried byte for byte, plus 31 new tasks: 27 in the reverse group and 4 forward tasks that read all three systems. It is laid out like [corpus 2](../corpus2/README.md), so that `runner.py --corpus-dir study/corpus3` reads it. Corpus 2 and its frozen files are unchanged. The Job `study3_corpus3` built it under decisions C1 to C8.

**Not frozen.** The manifest's status is `draft, not frozen`. The second derivation of the new keys (keys B), a wording review if the comparison asks for one, answerability on the Oracle-backed stack in all five arms and the freeze are later Jobs.

**Blindness.** No task text leaves this folder and corpus 2's: no commit message, Job note, report or message quotes a task. `test_corpus3.py` checks that no tracked file outside this folder holds a new question, and corpus 2's leak check (`test_corpus2.py`, narrowed by decision C1) allows a corpus 2 question here only inside a JSON record byte-identical to its corpus 2 record. The new questions therefore use their own words for the definitions they share with corpus 2.

## Files

| File | Holds |
| --- | --- |
| `tasks.json` | The whole scored set, with no draw (decisions C2 and C7): corpus 2's 76 pool tasks, the 31 new tasks, then corpus 2's 6 ambiguity tasks (`set: ambiguity`, reported apart). A carried record is its corpus 2 record without its schema, byte for byte. `directions` gives every scored task its `direction` and `csl` (below). |
| `schemas.json`, `expected.json` | The submit_answer schema and the key of every scored task. |
| `keys-a.json` | The keys of the scored set and of the development set: corpus 2's keys byte for byte, and the keys of the new tasks. |
| `dev.json` | Corpus 2's development set, byte for byte. |
| `corpus-manifest.json` | The SHA-256 of the five files above (the runner's corpus check reads `files`), the SHA-256 of corpus 2's frozen manifest, the corpus 2 hashes every carried task is bound to (`carried`: record, schema and key, canonical JSON), the ids of the new tasks and the released inputs. |
| `derive_a3.py` | The first derivation: it reads the carried tasks from corpus 2's files, authors the new tasks with corpus 2's own helpers (its `World`, its schema and check helpers and `Corpus.add`), derives their keys from the released files and applies the direction rule. `--write` writes, without it compares. It refuses when corpus 2's manifest is not the frozen `c57081e3…` or a file it reads differs from it, and a `--write` never replaces a manifest that is not a draft. |
| `scoring.py` | Corpus 2's scorer, a byte-identical copy (the runner loads the scorer of the corpus folder); the tests check it. |
| `reference/` | The reference solutions and their runner (below). |
| `test_corpus3.py` | The offline tests, in the study gate as the suite `corpus3`. |

## The new tasks

By task id only. Categories keep study 2's letters (decision C4): a reverse lookup is B or C, a far-side aggregate is E.

| Group | Tasks |
| --- | --- |
| Reverse lookups from a person (10) | B16, B17, B18, B19, B20, B21, B22, B23, C13, C14 |
| Reverse lookups from an asset (8) | B24, B25, B26, B27, B28, B29, C15, C16 |
| Far-side aggregates (9) | E17, E18, E19, E20 (per asset or asset group); E21, E22, E23, E24, E25 (per person or Personnel group) |
| Forward, all three systems (4) | B30, B31, E26, E27 |

Sizes: 10 small, 17 medium, 4 large. Mapping cases: release 1.3 for most; release 1.1 with an entry (C13) and without one (C14); release 1.0's assets section (C16); a kind no reference maps to (C15). C14 and C15 have no mission to name and accept either `ANSWERED` or `CANNOT_BE_DETERMINED` with an empty list, as corpus 2's C02 does. Each question states its inclusion and membership rules: who counts as the people of a mission, when an asset reference counts, which groups are left out or kept with a zero.

A new task's `systems` lists the services its answer must read; the mapping release is not a service and is in `tags`. The anchor, the system the question starts from, is kept apart, in `directions`: B28, C16, E20 and E22 start from an asset or a person identifier, yet need only Missions and the mapping, so their `systems` is `missions` alone. Corpus 2's B10 and B12 list their anchor system in `systems`, and B11 lists Personnel, though all three answers read only Missions and the mapping (B11 gives the commanding officers' Personnel identifiers, which the mapping holds); their records stay as they are, and `directions` gives their required systems as `missions`. A test stops, for every scored task outside category D, each listed service in turn: only these three named one their answer did not need, and every new task needs each service it lists.

## The direction fields

Each entry of `directions` holds `direction`, `csl`, `anchor` (the system whose records the question starts from) and `requiredSystems` (the services the answer must read: the task's `systems`, except B10, B11 and B12, above). A join-width count reads `requiredSystems`, never the anchor. `classify` in `derive_a3.py` sets `direction` and `csl` from the set, the category, the required systems and the anchor (decision C5):

- the ambiguity set and category D (run under an outage): `direction: none`, `csl: null`;
- anchor a person or an asset, and the task must read Missions: `reverse`, with `csl: far-side-aggregate` for category E and `reverse-lookup` otherwise;
- anchor missions, category C, and the task must read another system: `none`, `csl: link-integrity` (outside the forward-against-reverse test, reported as its own group);
- anchor missions and another system to read: `forward`; anything else `none`.

The anchors of the new tasks are declared with each task. A carried task's anchor is missions, except B10 (personnel), B12 and E15 (assets). The result: 30 reverse (B10, B12, E15 and the 27 new; 20 reverse lookups and 10 far-side aggregates), 24 forward (20 carried and the 4 new), 4 link integrity (C04, C10, C11, C12) and 55 none. B11 is none: it starts from missions and needs Missions and the mapping alone.

## The reference solutions

`reference/solutions3.py` holds corpus 2's solvers of the carried tasks, imported from `study/corpus2/reference/solutions.py` and unchanged, and one solver per new task written against corpus 2's access interface; no new access method was needed. `reference/run_reference.py` is corpus 2's runner pointed at this folder: it imports corpus 2's arm layers, fakes, backend verification, probes and outage rules, and replaces only the task set, the keys, the solutions and the hashes. The runner loads this folder's `scoring.py` by its path (loading corpus 2's runner imports corpus 2's scorer under the plain name), and a report's `inputs` name and hash the scorer that ran. It refuses `--tasks` naming a task outside the chosen set, and a solver that returns no submission is an error, never correct. A report's `inputs` hash this folder's files, every reference file the solutions run (corpus 2's `reference/*.py` and this folder's, each and together) and the released datasets. A run against a stack is an operator action and needs the lead developer's go.

## Commands

From the repository root:

```sh
python -B study/corpus3/derive_a3.py            # compare with corpus 2 and the released files
python -B study/corpus3/derive_a3.py --write    # rewrite the derived files (review the diff)
python -B study/corpus3/reference/run_reference.py --arm gamma --fake --set all
python -B -m unittest discover -s study/corpus3 -p "test_corpus3.py"
```
