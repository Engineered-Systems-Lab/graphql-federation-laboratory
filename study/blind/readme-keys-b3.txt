# Your inputs

This folder is everything you get for the blind derivation of the keys of corpus 3's 31 new tasks.

It was built from the laboratory's commit {commit}. Every file keeps its path in the laboratory. `MANIFEST.json` lists each file with its SHA-256. A link in a document to a file that is not here leads nowhere: that file is not part of your inputs.

## What is here

- `study/corpus3/tasks.json`: the 31 new tasks, each record as it stands in the laboratory without its design note, with its question.
- `study/corpus3/schemas.json`: the answer schema of each of the 31 new tasks.
- `study/corpus2/derive_b.py` and `study/corpus2/test_derive_b.py`: your own earlier work, the second derivation of the corpus 2 keys in study 2, written blind to the first derivation and never edited since. They are given to reuse: their readers of the released data and their output format. `derive_b.py` checks its inputs against the `MANIFEST.json` of study 2's package and under corpus 2's paths, so it does not run here as it is: adapt a copy of it to these inputs. The corpus 2 files it reads are not here.
- The released data the tasks name: the Missions release 1.2 (`uss-enterprise/missions/datasets/releases/1.2/`), the mapping releases 1.0 to 1.3 (`federation/mapping-releases/`), the Assets dataset 1.1 (`uss-enterprise/assets/datasets/releases/1.1/`) and the Personnel v2 snapshot `personnel-v2-large-004` (`uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/`).

## What was left out, and why

The keys must come from the questions and the released data alone, so that the two derivations are independent. The new tasks are all you get.

- `study/corpus3/tasks.json` and `study/corpus3/schemas.json` are the laboratory's files with every task that is not new removed: the 76 tasks carried from corpus 2 already have both derivations, and so do the 6 ambiguity tasks. The `directions` map of `tasks.json` is removed too: it is the first derivation's reading of each task's direction, anchor and the systems its answer needs, and you take that from the question. So is the `designNote` of each task: the author's notes on how the task was built, some of which state an answer, an accepted reading or a count. Nothing else in either file is changed; the top-level `about` of each file is the laboratory's own and describes the whole file. `MANIFEST.json` records each rewrite, the ids kept and the hash of the original.
- The development set: its 8 tasks already have both derivations.
- The first derivation of corpus 2 and of corpus 3: `keys-a.json`, `expected.json`, `derive_a.py` and `derive_a3.py`, and `reference/`, the reference solutions, which are scored against the first keys.
- Your corpus 2 keys (`study/corpus2/keys-b.json`): they are keys of tasks that are not new.
