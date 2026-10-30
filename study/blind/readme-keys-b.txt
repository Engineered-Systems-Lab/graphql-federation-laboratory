# Your inputs

This folder is everything you get for the second derivation of the corpus 2 keys.

It was built from the laboratory's commit {commit}. Every file keeps its path in the laboratory. `MANIFEST.json` lists each file with its SHA-256. A link in a document to a file that is not here leads nowhere: that file is not part of your inputs.

## What is here

- `study/corpus2/pool.json`: the candidate pool, every core task with its question and answer schema.
- `study/corpus2/ambiguity.json`: the ambiguity set; `acceptedInterpretations` defines each accepted reading without its answer.
- `study/corpus2/dev.json`: the development set, with its questions and schemas only (see below).
- `study/corpus2/schemas.json`: the answer schemas.
- The released data the tasks name: the Missions release 1.2 (`uss-enterprise/missions/datasets/releases/1.2/`), the mapping releases 1.0 to 1.3 (`federation/mapping-releases/`), the Assets dataset 1.1 (`uss-enterprise/assets/datasets/releases/1.1/`) and the Personnel v2 snapshot `personnel-v2-large-004` (`uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/`).

## What was left out, and why

The keys must come from the questions and the released data alone, so that the two derivations are independent. Left out until your keys are recorded:

- `study/corpus2/keys-a.json` and `study/corpus2/expected.json`: the keys of the first derivation.
- `study/corpus2/derive_a.py`: the first derivation itself.
- `study/corpus2/reference/`: the reference solutions, which are scored against the first keys.
- The `expected` entry of every task in `study/corpus2/dev.json`: it carries the first derivation's development key. The file here is the laboratory's file with that one key removed from each task and nothing else changed; `MANIFEST.json` records the rewrite and the hash of the original.
