# Study 3 analysis

The scripts that turn a scored bundle of Abstraction ladder study 3 into its tables and figure, the seeded power and validation calculations, and the [draft analysis plan](PLAN.md) that says exactly what they compute. Study 2's analysis in [study/analysis2](../analysis2/README.md) and study 1's in [study/analysis](../analysis/README.md) are unchanged; this folder imports their functions read-only where they apply as they are.

**The plan is a draft and nothing here has seen a scored study-3 run.** The scripts are tested on simulated data, on one fake bundle that the harness writes on its fakes, and, for the power check, on study 2's committed scores. The freeze fills the plan's marked places and pins its hash.

**Blindness.** The analysis keys on a task's set, category, size and systems, the category-D tag and corpus 3's `directions` map (`direction`, `csl`, `anchor`, `requiredSystems`). It never reads a question, a schema, a key, a design note or a reference solution; a task id is a cluster label and nothing else.

## Files

| File | Holds |
| --- | --- |
| `analyze3.py` | The command line: verifies the copy, runs every analysis of the plan and writes `results.json`, `tables.md` and `figures/effort.svg`. |
| `data3.py` | Verification of a copy against this folder's plan, corpus 3's directions map, the groups of each task and the zero-cost rule. The counting rules are study 2's. |
| `stats3.py` | The accuracy floor, the effort families, the CSL family, their fallbacks and the selection procedure (`confirmatory`). |
| `power3.py` | The t-test stand-in for power, from study 2's committed scores. |
| `validate3.py` | The error rates, coverage and power of the implemented selection procedure on simulated studies. |
| `simulate3.py` | Seeded simulated studies and bundles at corpus 3's shape, with known effects. |
| `legacy3.py` | The legacy-load reader of plan section 10: the requests to Missions, Personnel and Assets per run and arm, descriptive only. It reads the bundle the analysis reads and the legacy-load folder the launch kit writes. |
| `test_analysis3.py` | The tests, offline. |
| `test_legacy3.py` | The reader's tests, offline, on simulated transcripts and session folders. |
| `PLAN.md` | The draft analysis plan. |

The statistics packages are study 1's pins ([study/analysis/requirements.txt](../analysis/requirements.txt)); no other package is used.

## Running it

The raw bundle stays outside the repository and is read-only. Copy the run folder somewhere outside every checkout, then run from the repository root with the study environment's Python (the one `STUDY_MCP_PYTHON` names), in Git Bash:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis3/analyze3.py --bundle '<copy>/study-3' --sums '<archive>/SHA256SUMS-study-3.txt' --bundle-checksum '<sha256 of the bundle>' --corpus-dir study/corpus3 --out '<folder outside the repository>' --study2-scores study/evidence/study-2/scores.csv
```

Any verification failure stops it with `STOP` and exit code 2, and nothing is written. An unusable fit does not stop it: the family switches to its prespecified fallback, and a family that cannot be estimated either way is reported as not estimable. The output folder must be outside the repository and must not exist yet. The same inputs give the same bytes.

The legacy-load reader takes the same copy and a copy of the launch kit's `legacy-load` folder from the state folder of the run ([the launch kit](../launch/README.md#the-legacy-load-record)). It writes `legacy-load.json` and `legacy-load.md` into a new folder outside the repository, and stops with `STOP` and exit code 2 as the analysis does:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis3/legacy3.py --bundle '<copy>/study-3' --sums '<archive>/SHA256SUMS-study-3.txt' --bundle-checksum '<sha256 of the bundle>' --corpus-dir study/corpus3 --legacy-dir '<copy of the state folder>/legacy-load' --out '<folder outside the repository>'
```

A block it cannot count is reported with its reasons, and every other output is still written. The analysis runs without the reader, and `analyze3.py`'s own results point to `legacy3.py` for the legacy load, with the command line above.

The power and validation calculations write to a file outside the repository:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis3/power3.py --out '<file outside the repository>'
"$STUDY_MCP_PYTHON" -B study/analysis3/validate3.py --out '<file outside the repository>' --sims 2000 --workers 14
```

## Tests

`test_analysis3.py` checks that the simulated shape equals corpus 3's metadata, verification and refusal, the counting rules, recovery of known effects across seeds, Holm, the floor's gate on both sides of the margin, the switch to each fallback, identical bytes from identical inputs, the loader on a bundle the harness writes, the power script against the reference figures and a small run of the validation. `test_legacy3.py` checks what the reader counts, the run windows, the block initialization load and the check before scoring, the clock limit, a missing, partial or altered log, the figures and their weights, its blindness, the same bytes twice and a session folder written by the launch kit itself. The study gate runs both as the `analysis3` suite under `STUDY_MCP_PYTHON`. It takes about three minutes.
