# Study 2 analysis

The scripts that turn a scored bundle of [Abstraction ladder study 2](../../docs/STUDY-2-DESIGN.md) into its tables and figures, the seeded power calculation, and the [frozen analysis plan](PLAN.md) that says exactly what they compute. Study 1's analysis is in [study/analysis](../analysis/README.md) and is unchanged, so study 1's report stays reproducible; this folder imports its plain helpers read-only (`data.verify_copy`, `data.dollars`, `stats.holm`, `stats.equivalence` and the figures of `svg.py`).

**The plan is frozen; the scripts are not, and nothing here has seen a scored study-2 run.** The Job `study2_freeze` froze the plan on 2026-11-06, before the first scored run, with the written justification of the ±10 margin, the final power figures and the limits; its hash is in the [freeze record](../evidence/study-2-freeze/freeze-record-20261106.json) and in every manifest (`identity.analysisPlan`), and the analysis stops when the two differ. The scripts are tested only on simulated bundles, on one fake bundle that the harness writes on its offline fakes, and, for the power check, on study 1's committed [evidence](../evidence/README.md).

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
| `PLAN.md` | The frozen analysis plan, rule by rule, with the justification of ±10, the final power figures, the limits and the changes made at the freeze. |

The statistics packages are study 1's pins, `statsmodels` 0.15.0 and `scipy` 1.18.1 ([study/analysis/requirements.txt](../analysis/requirements.txt), with their lock file beside it); no other package is used.

## Running it

The raw bundle stays outside the repository and is read-only. Copy the run folder somewhere outside every checkout, then run from the repository root with the study environment's Python (the one `STUDY_MCP_PYTHON` names), in Git Bash:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/analyze2.py --bundle '<copy>/study-2' --sums '<archive>/SHA256SUMS-study-2.txt' --bundle-checksum '<sha256 of the bundle>' --corpus-dir study/corpus2 --out '<folder outside the repository>'
```

Before it computes anything it checks the copy against the archive's per-file sums (no file missing or extra), recomputes the bundle checksum and compares it with `--bundle-checksum`, requires the manifest to name its scorer contract (version 2, with the scorer's hash), its corpus hash and its harness commit, requires its analysis plan hash (`identity.analysisPlan`, added 2026-11-06 by the Job `study2_freeze_code`) to be the raw-byte SHA-256 of the `PLAN.md` the analysis runs under, requires every score to name the honesty checks the scorer applied (`honestyChecks`, added 2026-11-05 by the Job `study2_prerun_fixes`: a failed honesty check must be among them, and a judged category D answer must have at least one, so an abstention and a judged answer that passed can no longer look alike; a run is honest only then), and checks that `--corpus-dir` is the corpus the bundle ran and that its corpus manifest lists the hash of `tasks.json` (corpus 2's manifest lists it since the Job `study2_freeze_code`). Any difference stops it with `STOP` and exit code 2, and nothing is written. If the primary GEE cannot be used (PLAN.md, section 4) it stops with `STOP` and exit code 3, names the problem, and nothing is written. The output folder must be outside the repository and must not exist yet, so no file of an earlier run stands beside the new ones. The same inputs give the same bytes.

`--accept-primary-not-estimable '<decision>'` (added 2026-11-07 by the Job `study2_analysis_not_estimable`) carries the lead developer's word for the case PLAN.md, section 4, rule 5 leaves to it, quoted with its date and source. With it, a primary GEE that cannot be used is recorded in `results.json` as not estimable, with its problems and the decision as given, and the run goes on: study 2 then makes no confirmatory accuracy claim (no marginals, no P1, P2 or S1 to S6, no equivalence verdict) and no other model takes the primary's place. Every other analysis is run and written as without the option; `tables.md` says in one paragraph why the planned sections are empty, the bootstrap and the Bayesian mixed model name the separated cells, `figures/comparisons.svg` is not written and `figures/accuracy.svg` shows the observed share of correct answers per arm and model with no interval. Each model alone gets a logistic GEE of its core runs, labelled exploratory and added after the primary stop, with unadjusted p-values and the whole-interval result at +/-10 and no equivalence claim; a model whose fit or a contrast of it cannot be used is reported as not estimable. With the option and a usable primary fit the outputs are those of the run without it, and `results.json` records that the option was given and not needed. The exploratory results state the +/-10 rule as `intervalInsideMargin` (the whole 95 percent interval inside the margin), never as equivalence.

The power calculation, on study 1's evidence by default (`--profiles` takes another table, such as one built from the development runs with `power.profiles_from_records`):

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/power.py --contrasts P1 P2 apollo-cosmo --differences 0 5 --holm
```

The per-contrast lines use the design's rule, so they reproduce its figures; `--holm` adds P1 and P2 under the plan's rules.

A simulated bundle, to try the command:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis2/simulate.py --out '<folder outside the repository>' --seed 1
```

## Tests

`test_analysis2.py` writes seeded simulated bundles (the Williams schedule and its halves from the harness's own `schedule.py`, both models, outage tasks, vendor errors and their requeue, the ambiguity set, two sessions with a boundary inside a round, a block resumed after a stop, and on request a void attempt repeated whole, a block restarted as a new attempt with no void event and the format without attempts, whose restart from nothing the analysis refuses), and one fake bundle by running `study/harness/runner.py` on its fakes. It tests verification and refusal, the counting rules, that the estimates recover the true effects across ten seeds, Holm and the equivalence rule at the boundary, that a non-converging primary fit stops, that the mixed model and the bootstrap run, that two runs give the same bytes, that a tampered copy stops before any output, and that the power script reproduces the design's figures within the simulation's error and runs the plan's Holm rule. The study gate runs it as the `analysis2` suite under `STUDY_MCP_PYTHON`. It takes about three minutes.
