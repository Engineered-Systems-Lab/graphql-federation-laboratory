# Study 2's analysis runs on the scored bundle with the primary GEE recorded as not estimable, on the lead developer's word after the stop

Date: 2026-11-07T14:46Z
Subject: Archived study 2's scored run and verified a copy of it, ran the frozen analysis on it, stopped twice (exit 2 on the sums-file form, then exit 3 on the unusable primary GEE), and after two code Jobs ran it again with the lead developer's decision that the primary is not estimable; committed the score table, manifest and analysis outputs as study/evidence/study-2/
Status: Historical / non-normative
Provenance: Written on 2026-11-07 (UTC) by the worker of the Job study2_analysis. Dated by the time the second of the two final analysis runs wrote its output (14:46:48Z; the first wrote at 14:46:41Z). Sources: the Job record, the lead developer's answers in the worker's session, the Coordinator's routed entries, the run logs and the outputs, all outside the repository. The worker held no API key, ran no stack and made no vendor call. The numbers below are quoted as `tables.md` writes them; this entry holds no interpretation of them.

## The departure from PLAN.md

- **What the plan says.** `study/analysis2/PLAN.md` (SHA-256 `46be3e4e3d71d9383fa5fee10c0018b2e2333a1087b6644fa0bd4498151f8bb5`, the manifest's `identity.analysisPlan`) stops the analysis when the primary GEE cannot be used and allows no fallback without the lead developer's word (section 4, rule 5). PLAN.md was not changed.
- **The stop.** At 05:34Z, on commit `010fc5255b5da878a1ab375a19380a7c8f38b1a1`, both runs stopped with exit 3 and wrote nothing: "statsmodels did not report convergence, or an estimate is not finite; the covariance is not finite; separation: cells all right or all wrong: beta/gpt-6.1-sol, gamma/gpt-6.1-sol, delta/gpt-6.1-sol, epsilon/gpt-6.1-sol". That message names the separated cells, so it says that GPT-6.1 Sol's cells in the four full arms are all right or all wrong.
- **The route was decided after the stop.** The lead developer chose in the worker's session to route the decision through the Coordinator ("Route via Coordinator"). The decision was then taken in the Coordinator session on 2026-11-07, after the stop: keep the stop, suspend judgement on accuracy, report the rest. The routed scope (entry 14 of the Job study2_analysis_not_estimable) records that a reviewer had seen the observed cell counts before the route was decided.
- **The decision text.** The lead developer confirmed it in the worker's session, with one change ("+/-10 percentage points"). It was passed verbatim to `--accept-primary-not-estimable` (SHA-256 of its UTF-8 bytes `d10f09d90d594fb1527838f3bf97a2634b981ed1f4690d48e44547ec961c13c8`):

  > Keep the stop: the primary GEE is not estimable, and study 2 makes no confirmatory accuracy claim (no P1 or P2 verdict, no equivalence at +/-10 percentage points, no Holm family of S1 to S6). Judgement on accuracy is suspended. Every other output the plan defines is still produced and reported under its own label. PLAN.md stays frozen. (The lead developer, Coordinator session, 2026-11-07; confirmed in the study2_analysis worker session, 2026-11-07)

- **What it adds that the plan did not define.** A logistic GEE of each model alone, labelled "exploratory, added after the primary stop", with unadjusted p-values and no equivalence claim. `figures/accuracy.svg` shows the observed share of correct answers with no interval, and `figures/comparisons.svg` is not written. The two code Jobs `study2_analysis_not_estimable` (`10580cad4d7fc30b090de22d16776f74945a60dd`) and `study2_analysis_contrasts` (`4bd895d4919e20f8f1aa1190254f52a267403cb2`) added them. Neither changed the plan, the fits or the usability rules.

## Before the analysis

- **The archive.** On the lead developer's go, `lab-results-study2-2026-11-07.zip` (3,720 members, SHA-256 `845197398ef7f0af89f74e14691a8f17701a4004a6bbb6b33111a718d3892d35`) and `setup-study2-2026-11-07.zip` (14 members, `dc39cc3800c69913634af929a8dd6640d7f3215c24656f15fa525b8a99813ad6`) were written outside every checkout, with every member checked against its sums. 38 archived files that no per-file sums file lists got their own sums file, `SHA256SUMS-unlisted` (`8264d800604b309028610ecd37b16612dda9d701cd2946ca15804ad7632ff41b`), on the lead developer's choice. The originals were only read.
- **The copy.** The run folder was copied outside every checkout and checked against `SHA256SUMS-study2-scored-1`: 1,656 files, none extra, missing or different. It was checked again before the last runs, with the bundle checksum `ba12c57484e850aeb379cd9876900ab9f3ba3eb285b5e5a07aaa5e69c047ac5a` and status `complete`.
- **The first stop, exit 2.** At 04:50Z, on commit `f40c477d5bea78b42ae5043157e60d2f6b6f42af`, the analysis refused the copy: "the sums file lists no file of study2-scored-1". The sums file uses the two-space form `<sha256>  <path>`, which `read_sums` did not read. On the lead developer's choice, a code Job made it read both forms (`010fc5255b5da878a1ab375a19380a7c8f38b1a1`).
- **The suite.** The analysis2 suite passed before each attempt: 48 tests on `f40c477`, 49 on `010fc52` and 62 on `4bd895d`.

## The analysis

- **Command.** `analyze2.py` on commit `4bd895d4919e20f8f1aa1190254f52a267403cb2`, with `--run-id study2-scored-1`, `--accept-primary-not-estimable` and the text above, on the lead developer's go.
- **Runs.** Two runs into fresh folders. Both exited 0, and their outputs are byte-identical. Both printed the same statsmodels RuntimeWarnings and PerfectSeparationWarnings.
- **`results.json`.** It records the option with `"needed": true`.
- **Primary.** Not estimable. There is no P1 or P2 verdict, no equivalence at +/-10 and no Holm family of S1 to S6.
- **Observed correct answers in the core set,** as `tables.md` writes them:

  | Arm | Claude Sonnet 5.5 | GPT-6.1 Sol |
  | --- | --- | --- |
  | Direct Access | 36/48 | 27/48 |
  | Guided Direct Access | 47/48 | 48/48 |
  | GraphQL Adapters | 45/48 | 48/48 |
  | Apollo Federation | 47/48 | 48/48 |
  | Cosmo Federation | 47/48 | 48/48 |

- **Bayesian mixed model** (the prespecified sensitivity analysis, decision S4):
  - Its fit facts record `converged: true`.
  - P1 is +2.1 [-2.6, +8.2] and P2 +0.1 [-4.3, +6.0] percentage points, posterior mean with 95% posterior interval. S1 to S4 are written too, and there is no S5 row.
  - Its label says the fixed-effect prior (fe_p=2) influences the estimates of the four separated cells and of the contrasts that use them. The run does not measure how much of each estimate comes from the prior and how much from the data.
- **Not estimable:**
  - the per-model exploratory fits of both models;
  - the sensitivity rows "vendor errors as wrong" and "bias-reduced covariance";
  - the honest-gap GEE;
  - Direct Access against each arm.
- **Cluster bootstrap.** Written, labelled "an unadjusted cross-check, not a bootstrap of the fitted GEE".
- **Also written:** the cost, time and tool-call ratios (exploratory, unadjusted p) and the descriptive sections.

## What is committed

- `study/evidence/study-2/scores.csv` and `manifest.json`: byte copies of the run folder's files.
- `results.json`, `tables.md` and `figures/accuracy.svg`, `cost.svg` and `seconds.svg`: the analysis output.
- `checksums.json`: the archive, sums-file, bundle, evidence and output digests, with the analysis commit, the plan hash and the decision hash.
- Two rows of the project's artifact classification table for `study/evidence/study-2/*.md` and `study/evidence/study-2/figures/*.svg`, classed as record.
- A `.gitattributes` rule, `whitespace=-blank-at-eof`, for `study/evidence/study-2/tables.md`. The file ends with a blank line as `analyze2.py` wrote it, and the rule lets the commit's whitespace check pass with the file kept byte for byte. The lead developer chose it after the first seal failed on that check.
- The raw run folder, the archives and the analysis copy stay outside the repository.
