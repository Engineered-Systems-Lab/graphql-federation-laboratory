# Study 2 analysis plan (draft)

Status: **draft, not frozen.** It says, rule by rule and in the order of the outputs, what [analyze2.py](analyze2.py) computes from a study-2 bundle. It follows the [study 2 design](../../docs/STUDY-2-DESIGN.md#hypotheses-and-analysis) and says so wherever it settles a point the design leaves open; where it and the design differ it says so. The lead developer settled the multiplicity families, the equivalence rule over the planned pair, the honest-gap rate and the standardization weights on 2026-10-28, after a review of the first draft. The frozen plan is made from this draft by a later Job before the first scored run, with its hash in every manifest; that Job fills the two places marked **TO BE FILLED AT THE FREEZE** and may revise any rule, each revision recorded. Nothing here has seen a study-2 run.

## 1. Inputs and verification

1. The input is a copy of one study-2 run folder, its archive's per-file sums file, its bundle checksum and the corpus folder it ran. The raw folder stays outside the repository and read-only.
2. The copy is verified before anything is computed, as study 1's are: every file against the sums, no file missing or extra, the bundle checksum recomputed from the bundle's file list and equal to the one given, and a bundle of status `complete` of the named run.
3. The manifest must name its scorer contract (version 2, with the scorer's hash), its corpus hash (`identity.corpusFreeze`) and its harness commit, and hold a `williams-4-half` schedule of the four full arms with Direct Access as the reference block.
4. The corpus folder's `corpus-manifest.json` must hash to the corpus hash and must list the hash of `tasks.json`, which must match; `tasks.json` must hold exactly the tasks of the schedule, each once, every category-D task with its tag (section 2), and every run's category must equal its task's. Today's corpus 2 manifest does not list `tasks.json`, so the analysis refuses it until the freeze adds that hash.
5. Any failure stops the analysis with `STOP` and exit code 2, and nothing is written.

## 2. What is read about a task

Only a task's category, set, size and systems, the service a category-D task stops, and of its tags only `fullyAnswerableWithoutStoppedService` (category D), from the corpus's `tasks.json`; never a question, a schema, a key or a reference solution. The analysis keys only on category, set, size and systems, and splits category D by that tag (the lead developer's decision); a task id is a cluster label. Categories are named in the outputs: A single-system lookup, B cross-system join, C mapping-dependent, D honesty under failure, E aggregation, G pagination and completeness (the design's P), F the ambiguity set.

## 3. Which runs count

1. Every run the manifest's schedule plans has exactly one record (its last attempt), and no other run appears; each record and its score row carry the task, the model, the arm and the block the schedule plans for that run key; otherwise the analysis stops.
2. A complete bundle holds only the outcomes correct, wrong answer, format error, definition not accepted, abstained, did not finish and vendor error; any other stops it.
3. **Blocks (provisional).** A block has one attempt: its first start and the resumes that continue it (a resume after a budget stop finds finished runs and keeps them, as the harness does), ending with an `end` event, every counted run finished after it began. A later start that finds no finished run of the block, after an earlier start, is refused: the bundle cannot say whether that was a void block repeated whole or a resume after a stop that finished nothing. This rule is an adapter until the void-block rule exists (open points), not the final validity rule.
4. **Arms.** The four full arms of the square (Guided Direct Access, GraphQL Adapters, Apollo Federation, Cosmo Federation) enter the planned and secondary analyses. Direct Access enters only the exploratory results.
5. **Sets.** The core set (categories A to E and G) enters the primary accuracy. The ambiguity set (F) is analysed apart and never enters it.
6. **Outcomes.** Primary accuracy counts only `correct`. Wrong answer, format error, definition not accepted, abstained and did not finish count as incorrect, and each is reported; abstained is its own column. A vendor error (a run that failed at the vendor again after its one requeue) is missing in the main analysis and wrong in a sensitivity analysis. A requeued run that then finished counts once, with its last attempt; the cost of the attempts the harness archived is reported apart as operational spend and enters no outcome, denominator or retry count.

## 4. The primary model

1. Correct (1 or 0) ~ arm × model + round + session: logistic GEE clustered by task, exchangeable working correlation, robust (sandwich) covariance.
2. Round is the square's row (1 to 4), treatment coded. Session enters only when a session boundary falls inside a round of the square (a boundary between rounds is absorbed by round), and only when the design with it has full rank; when it has not, the session terms are left out and the output says so. No term is kept or dropped by its p-value.
3. **Standardization (the lead developer's decision):** an arm's probability is the model's predicted probability averaged with equal weight over the two models and over fixed planned conditions: each round of the square with weight 1/4 and, within a round, its sessions weighted by the planned core runs of the square's blocks in each session. The weights come from the schedule and the block sessions, are the same for every arm and do not move when a vendor error removes a run. Probabilities are averaged first, then differenced. Intervals of an arm's probability are taken on the logit scale.
4. **A usable fit** (the lead developer's review asked for more than convergence): statsmodels reports it converged; parameters and covariance are finite; the covariance has no negative eigenvalue beyond rounding (below −1e-10 times the largest); no arm × model cell is all right or all wrong; no estimate is extreme (|b| > 10 on the logit scale); the covariance block of the interaction terms is positive definite; and every planned and secondary contrast has a positive variance. A covariance that is singular within rounding but not negative is recorded as a diagnostic and does not stop the fit: the robust sandwich of a balanced design is often exactly singular in one direction (in the power simulations about 37 percent of the fits, with eigenvalues of about −1e-17 against a largest of about 0.5).
5. If the primary GEE is not usable the analysis stops with `STOP` and exit code 3, names the problem, and writes nothing. There is no fallback without the lead developer's word.

## 5. Planned comparisons (decision C)

1. **P1:** the mean of Apollo Federation and Cosmo Federation minus GraphQL Adapters, in accuracy.
2. **P2:** the mean of Apollo Federation and Cosmo Federation minus Guided Direct Access, in accuracy.
3. Each is a difference in percentage points with its 95 percent interval by the delta method and a two-sided Wald test of the same difference; Holm's correction over the two, family α 0.05.
4. **Equivalence (decision K, with the lead developer's multiplicity decision):** at ±10 percentage points only. The design's rule, the whole 95 percent interval inside ±10, is the two one-sided tests at 2.5 percent each. For P1 and P2 the one-sided p-value of each (the larger of its two) is Holm-adjusted over the two, and equivalence is established only when the adjusted value is under 0.025. The whole-interval verdict of each alone is shown beside it. Differences and intervals are reported whether or not equivalence holds; "equivalence not established" does not prove a difference.
5. **The justification of ±10.** **TO BE FILLED AT THE FREEZE.** The design's draft, quoted as a draft: "a difference under 10 percentage points is fewer than one more correct answer in ten business questions, and the comparisons of cost, time and outage handling would then decide."
6. The meaningful effect is 10 percentage points.

## 6. Secondary comparisons of accuracy (one Holm family of six)

From the same fit, Holm-corrected together, six tests: S1 Apollo Federation minus GraphQL Adapters; S2 Cosmo Federation minus GraphQL Adapters; S3 Apollo Federation minus Cosmo Federation; S4 GraphQL Adapters minus Guided Direct Access; S5 the model effect, the first model minus the second in the manifest's order (Claude minus GPT), averaged over the four arms; S6 the arm × model interaction (Wald, 3 degrees of freedom). The directions are the order the design names them in; for two-sided tests they change only the sign. S3's equivalence at ±10 is reported by the whole-interval rule with no multiplicity control, and labelled so.

**A clarification of the design.** The design lists cost, time, tool calls and the honest-gap rate under its heading "Secondary, Holm-corrected as one family". The lead developer decided that the family is the six accuracy tests above, and that those measures are reported as exploratory with unadjusted p-values (section 7).

## 7. Measures reported as exploratory

1. **Cost, time and tool calls** per run of the core set in the four arms, on the log scale with the same GEE structure (Gaussian, the same terms, the same standardization), as ratios of geometric means with 95 percent intervals, for P1, P2, S1 to S4 and the model effect, for all runs and for correct runs only, a vendor error left out. A run with a cost or a time that is not positive is left out and counted. Tool calls can be zero (the count excludes the submission), so they are fitted as log(1 + calls), and their geometric means and ratios are of **1 + calls**, not of calls; the mean and median calls per arm and the runs with none are given beside them. Cost is computed from each run's token usage and its model's price entry in the manifest, with the harness's formula. P-values are unadjusted; the meaningful ratio is 1.25.
2. **The honest-gap rate on category D (the lead developer's decision):** reported apart for the tasks that need the stopped service and for the over-reporting controls (the tasks fully answerable without it, by the tag of section 2). A run is honest only when the scorer judged an answer (correct, wrong answer or definition not accepted) and it failed no honesty check; abstained, did not finish and a format error count as not honest; a vendor error is left out. Per arm: honest, correct, runs with an honesty failure, runs not judged and vendor errors. For the gap-required tasks, comparisons (P1, P2, S1 to S4) come from a logistic GEE with arm and model only, clustered by task, with the bias-reduced covariance for few clusters, when the fit is usable; otherwise the rate stays descriptive. With about six task clusters these intervals are unreliable, which the output says. The meaningful effect is 15 percentage points. The scorer does not yet say which honesty checks it ran (open points).

## 8. Sensitivity analyses

1. **Vendor errors as wrong:** the primary model again, with each vendor error counted incorrect.
2. **Bias-reduced covariance:** the primary model with statsmodels' bias-reduced covariance for few clusters, as study 1.
3. **Cluster bootstrap of pooled proportions:** 10,000 resamples of whole tasks with replacement (all of a task's arms, models and rounds together), seed 20261028; the cell proportions are pooled over the resampled tasks and averaged with equal model weights, without a refit and without round or session. It is an unadjusted cross-check of a different, simpler estimator, not a bootstrap of the fitted GEE; its whole-interval verdict is shown beside the GEE's, and the GEE decides.
4. **Bayesian mixed model (decision S4 of the Job record):** statsmodels' `BinomialBayesMixedGLM`, logistic, with a random intercept per task and per block, priors `vcp_p=1` and `fe_p=2`, fitted by mean-field variational Bayes (`fit_vb`, BFGS with statsmodels' default options, its starting values from the seed 20261028); its Laplace fit (`fit_map`) does not converge on study-2-shaped data. It is an approximate Bayesian analysis, not a frequentist mixed model. Its arm × model cells take one parameter each and round and session are coded to sum to zero. Its results come from 4,000 seeded draws of the variational posterior, the variance components included: each draw's cell probability is standardized over the same planned conditions as the GEE and integrated over that draw's task and block random effects (normal, Gauss–Hermite quadrature). The estimate is the posterior mean and the interval the 2.5 and 97.5 percent posterior quantiles. The fit is used only when its optimizer reports success and every estimate is finite; otherwise this analysis is reported as not estimable.

## 9. Exploratory results, labelled so

Unadjusted, no confirmatory claim:

1. **Direct Access against each arm:** a logistic GEE of the core set in all five arms, arm × model, clustered by task, without round or session (the reference block has no round). Its single block ran last, so its results are confounded with that time window, which every output says. The ±10 whole-interval verdict is shown.
2. **The ambiguity set,** per arm, Direct Access included: runs, clarified, interpretation accepted (the correct outcome), both, clarified only, and the outcomes. Clarified is read only from the run's `ask_requester` log (any call with a non-empty question), whatever the outcome, so a run that asked and then did not finish still counts as clarified; a scorer flag that disagrees with the log stops the analysis. A request alone is never success.
3. **The size strata** (small, medium, large): correct runs per arm and, where the fit is usable, P1 and P2 from a GEE of the stratum without round or session.
4. **Per category:** correct runs per arm.
5. **The calculation tool:** per arm, the runs that used it, its calls and errors, and the correct runs with and without it; the `ask_requester` calls.

## 10. Descriptive

The counting (runs counted and set aside, by rule, and the blocks resumed after a stop); correct answers of the core set by arm and model with the vendor errors; outcomes of the core set by arm; spend by arm, counted runs and archived attempts apart; the schedule (the letters of the arms, the order of the rounds, each block's starts and sessions).

## 11. Outputs

`results.json`, `tables.md` and `figures/accuracy.svg`, `comparisons.svg`, `cost.svg` and `seconds.svg`, written outside the repository. The arms and categories carry their descriptive names; the letters are internal identifiers. Every float is rounded to six decimals and every random draw is seeded, so the same inputs give the same bytes; no absolute path is written.

## 12. Power (decision K)

1. **What power means:** the chance that the study establishes equivalence under the stated assumptions; not the probability that the arms are equivalent. A failure to establish equivalence authorizes no extra tasks, runs or spending.
2. **The method** ([power.py](power.py)): simulated studies of k core tasks with 2 runs per task and arm (one per model); task profiles drawn with replacement from a table of per-task accuracies, so a task keeps its accuracy in every arm (pairing and heterogeneity kept); a true difference set by shifting the subtracted arm by one constant on the probability scale, clipped to 0 and 1, so the difference over the table equals it; each simulated study analysed with the planned GEE (arm × model, clustered by task; round and session left out, as in the design); 400 studies per line, seed 20261027. Each line reports the requested difference, the difference the shifted table achieves, the mean true difference of the drawn tasks, the Monte Carlo standard error and the fits that could not be used, apart.
3. **Reproduced from study 1's evidence** (Guided Direct Access, Apollo Federation and Cosmo Federation from study-1's Beta, Delta and Epsilon, GraphQL Adapters from gamma-prime-1's Gamma, both models and trials pooled), at 48 tasks, with the design's rule (each contrast alone, whole interval inside ±10, study 1's fit rule), against the design's simulation figures:

   | Contrast | True difference 0: this script / the design | 5 points: this script / the design |
   | --- | --- | --- |
   | P1 federation − GraphQL Adapters | 65.7 / 68 percent | 36.7 / 32 percent |
   | P2 federation − Guided Direct Access | 52.5 / 53 percent | 29.7 / 29 percent |
   | Apollo − Cosmo Federation | 90.0 / 91 percent | 47.2 / 46 percent |
   | Apollo − Guided Direct Access (reference) | 39.8 / 37 percent | 23.5 / 22 percent |
   | Cosmo − Guided Direct Access (reference) | 54.7 / 58 percent | 27.3 / 30 percent |

   Each line's Monte Carlo standard error is about 1.5 to 2.5 points; every line is within two combined standard errors of the design's. This agreement shows that the script reproduces the design's calculation; it does not validate the rules.
4. **Under this draft's rules** (P1 and P2 from one fit, both at the same true difference, the Holm-adjusted two one-sided tests, the full fit usability rule; `power.py --holm`), at 48 tasks: P1 65.0 and P2 51.7 percent at a true difference of 0, 32.5 and 22.0 percent at 5 points; no fit was refused.
5. **The final power figures.** **TO BE FILLED AT THE FREEZE**, from the development runs (`power.profiles_from_records`), under the frozen rules, with the task count fixed then.

## Open points for the freeze

- **The void-block rule** is not yet built in the harness. The counting rule needs from it: an explicit attempt identity on every block event and every run record; a recorded event that names a void attempt and its declared trigger; a repeat that starts with no finished run of the block, the void attempt's runs archived and never left as a run's current result; and the void attempt's spending kept apart. The analysis will then count only the runs of the one attempt not declared void, and keep refusing any history it cannot resolve.
- **`tasks.json` and the corpus hash.** The frozen corpus manifest must list the hash of `tasks.json`; until it does, the analysis refuses the corpus.
- **The honesty checks.** The scorer returns `honestyFailures` but not which honesty checks it applied, so an abstention and a judged answer that passed look alike. The analysis now counts only a judged answer (correct, wrong answer, definition not accepted) as honest; the freeze should have the scorer report the checks it applied, and the analysis should then require them.
