# Study 2 analysis

The scripts that turn a scored bundle of [Abstraction ladder study 2](../../docs/STUDY-2-DESIGN.md) into its tables and figures, the seeded power calculation, and the [draft analysis plan](PLAN.md) that says exactly what they compute. Study 1's analysis is in [study/analysis](../analysis/README.md) and is unchanged, so study 1's report stays reproducible; this folder imports its plain helpers read-only (`data.verify_copy`, `data.dollars`, `stats.holm`, `stats.equivalence` and the figures of `svg.py`).

**Nothing here is frozen and nothing here has seen a study-2 run.** The plan is a draft: a later Job freezes it with the written justification of the ±10 margin and the final power figures from the development runs, before the first scored run. The scripts are tested only on simulated bundles, on one fake bundle that the harness writes on its offline fakes, and, for the power check, on study 1's committed [evidence](../evidence/README.md).

**Blindness.** The analysis keys only on a task's category, set, size and systems, and splits category D by the tag `fullyAnswerableWithoutStoppedService`. It reads corpus 2's `tasks.json` field by field (id, category, set, size, systems, stopped service and that one tag) and never a question, a schema, a key or a reference solution; a task id is a cluster label and nothing else.

## Files

| File | Holds |
| --- | --- |
| `analyze2.py` | The command line: verifies the copy, runs every analysis of the plan and writes `results.json`, `tables.md` and `figures/*.svg`. |
| `data2.py` | Verification of a copy of a study-2 bundle and of its corpus, the loading of one record per run and the counting rules. |
| `stats2.py` | The study-2 fits: the GEE with arm × model, round and session, the standardized marginals, the cluster bootstrap and the mixed model. |
| `power.py` | The power to establish equivalence at ±10 points under the planned GEE, seeded, from a table of per-task accuracies. |
| `simulate.py` | Seeded simulated bundles in the harness's format with known true effects. |
| `test_analysis2.py` | The tests, offline. |
| `PLAN.md` | The draft analysis plan, rule by rule, with the two places a later Job fills before the freeze. |

The statistics packages are study 1's pins, `statsmodels` 0.15.0 and `scipy` 1.18.1 ([study/analysis/requirements.txt](../analysis/requirements.txt), with their lock file beside it); no other package is used.

## Running it

The raw bundle stays outside the repository and is read-only. Copy the run folder somewhere outside every checkout, then run from the repository root with the study environment's Python (the one `STUDY_MCP_PYTHON` names), in Git Bash:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/analyze2.py --bundle '<copy>/study-2' --sums '<archive>/SHA256SUMS-study-2.txt' --bundle-checksum '<sha256 of the bundle>' --corpus-dir study/corpus2 --out '<folder outside the repository>'
```

Before it computes anything it checks the copy against the archive's per-file sums (no file missing or extra), recomputes the bundle checksum and compares it with `--bundle-checksum`, requires the manifest to name its scorer contract (version 2, with the scorer's hash), its corpus hash and its harness commit, and checks that `--corpus-dir` is the corpus the bundle ran and that its corpus manifest lists the hash of `tasks.json` (today's corpus 2 does not yet, so the analysis refuses it until the freeze adds it). Any difference stops it with `STOP` and exit code 2, and nothing is written. If the primary GEE cannot be used (PLAN.md, section 4) it stops with `STOP` and exit code 3, names the problem, and nothing is written. The output folder must be outside the repository. The same inputs give the same bytes.

The power calculation, on study 1's evidence by default (`--profiles` takes another table, such as one built from the development runs with `power.profiles_from_records`):

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/power.py --contrasts P1 P2 apollo-cosmo --differences 0 5 --holm
```

The per-contrast lines use the design's rule, so they reproduce its figures; `--holm` adds P1 and P2 under this draft's rules.

A simulated bundle, to try the command:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/simulate.py --out '<folder outside the repository>' --seed 1
```

## Tests

`test_analysis2.py` writes seeded simulated bundles (the Williams schedule and its halves from the harness's own `schedule.py`, both models, outage tasks, vendor errors and their requeue, the ambiguity set, two sessions with a boundary inside a round, a block resumed after a stop, and on request a block restarted from nothing, which the analysis refuses), and one fake bundle by running `study/harness/runner.py` on its fakes. It tests verification and refusal, the counting rules, that the estimates recover the true effects across ten seeds, Holm and the equivalence rule at the boundary, that a non-converging primary fit stops, that the mixed model and the bootstrap run, that two runs give the same bytes, that a tampered copy stops before any output, and that the power script reproduces the design's figures within the simulation's error and runs the plan's Holm rule. The study gate runs it as the `analysis2` suite under `STUDY_MCP_PYTHON`. It takes about three minutes.
