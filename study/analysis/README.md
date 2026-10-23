# Study analysis

The scripts that turn the scored runs of the [Abstraction ladder study](../README.md) into every table and figure of its report. They implement the analysis plan the lead developer agreed on 2026-10-21; the method and the scenarios are in the [agent scenario design](../../docs/PLAN.md#agent-scenario-design), and the committed evidence they check against is in [evidence](../evidence/README.md).

## Files

| File | Holds |
| --- | --- |
| `analyze.py` | The command line: verifies the copies, runs every analysis and writes `results.json`, `tables.md` and `figures/*.svg`. |
| `data.py` | Verification of a copy of a run folder and the loading of one record per agent run. |
| `stats.py` | The GEE fits, the marginal contrasts, Holm, the equivalence rule, the exact paired tests and the task bootstrap. |
| `t15.py` | Task 15 under the assigned-crew-only reading, the post-hoc sensitivity line. |
| `svg.py` | The figures, as hand-written SVG. |
| `requirements.txt` | The pinned statistics packages: `statsmodels` 0.15.0 and `scipy` 1.18.1. |
| `requirements-lock.txt` | The packages pip added with them; the tests ran with exactly these. |
| `test_analysis.py` | The tests, on a synthetic fixture they write themselves, and the checks of the committed evidence. |

## Running it

The raw run folders stay outside the repository and are read-only. Copy the two run folders somewhere outside every checkout, then run the analysis from the repository root with the study environment's Python (the one `STUDY_MCP_PYTHON` names, with `requirements.txt` installed), in Git Bash:

```sh
"$STUDY_MCP_PYTHON" -B study/analysis/analyze.py --study-1 '<copy>/study-1' --gamma-prime-1 '<copy>/gamma-prime-1' --sums-study-1 '<archive>/SHA256SUMS-2026-10-21.txt' --sums-gamma-prime-1 '<archive>/SHA256SUMS-gamma-prime-1.txt' --out '<folder outside the repository>'
```

Before it computes anything it checks each copy against the archive's per-file sums (no file missing or extra), recomputes the bundle checksum from the bundle's file list and compares it with [the evidence checksums](../evidence/checksums.json), and compares the copy's score table and manifest with the committed evidence. Any difference stops it with `STOP` and exit code 2, and nothing is written. The output folder must be outside the repository, because everything in it is generated. The same inputs give the same bytes.

## What it computes

- **Confirmatory.** Alpha, Beta, Delta and Epsilon of study-1. Correct (yes or no) by scenario and model, logistic, fitted with GEE clustered by task (exchangeable working correlation, robust covariance). Each scenario's probability is averaged over the two models with equal weight. The six named comparisons (i to vi) are differences in percentage points with 95 percent intervals (delta method), with Holm-corrected p-values. Comparison v is the model effect averaged over the four scenarios; the scenario x model interaction is reported beside it and is not in the Holm family. Equivalence for Beta and Delta, Beta and Epsilon, and Delta and Epsilon holds at a margin only if the whole 95 percent interval lies inside it, at +/-10 (primary) and +/-15 (secondary). The GEE interval decides; the bootstrap decision is shown beside it.
- **Cross-checks.** Cochran's Q over the four scenarios and exact McNemar tests on runs matched by task, model and trial; 95 percent percentile intervals from 10,000 bootstrap resamples of the tasks (seed 20261021).
- **Outcome rules.** Did not finish and a definition not accepted count as wrong. The 3 vendor errors are missing in the main analysis and wrong in a sensitivity analysis. No re-runs. T15 counts as scored.
- **Sensitivity.** Errors as wrong; the bias-reduced covariance for few clusters; T15 with the crew-only reading (exploratory).
- **Secondary.** Run time, tool calls, cost and tokens on the log scale with the same GEE structure, as ratios of geometric means, for all runs and for correct runs only. Request latency and the cache-hit share per scenario and vendor are descriptive. Dollars come from the price entries in each run's manifest, with the harness's own formula.
- **Exploratory, labelled as such.** Gamma-prime against Alpha and Beta (a separate run, not interleaved); structure over kind (the guide or a graph against raw access, and the graph against the guide); the outage tasks T10 and T11; T07; raw access costing most (from the secondary cost fit); T15 with the assigned crew only.
- **Descriptive only.** Gamma as built, beside Gamma-prime and split by the corpus tag `mappingNeeded`, with no test: it is the design error described in the report, not a finding.

If the primary GEE does not converge, the command stops; the plan says to ask the lead developer before any fallback.

## Tests

`test_analysis.py` writes two small synthetic run folders in the shapes the harness writes, with their sums files and a fixture evidence folder, and tests verification, loading, the statistics against known answers, the T15 recount from the released files and the whole command end to end, including that two runs give the same bytes and that a tampered copy stops before any output. It also checks the committed evidence against its checksums. The study gate runs it as the `analysis` suite under `STUDY_MCP_PYTHON`.
