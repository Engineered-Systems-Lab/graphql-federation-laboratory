# Study 3 gets a readable design page, written after its scored run from pre-run sources only and never as pre-registration

Date: 2026-11-26T12:11Z
Subject: The Job `study3_design` added `docs/STUDY-3-DESIGN.md`, study 3's design page in study 2's form, written results-blind from sources frozen or decided before the scored run `study3-scored-1`, with its row in the project's artifact classification table and a line naming it in `study/README.md` and `docs/STUDY-OVERVIEW.md`
Status: Historical / non-normative
Provenance: Written on 2026-11-26 (UTC) by the worker session of the Job (Anthropic Claude Code [Claude Opus 5.5], started by the Migration Coordinator), before the commit that carries it, from the Job record and the sources the page names. Dated by the time this entry was written, read with `date -u`; the page was written a few minutes before it. The lead developer decided the scope as G1 to G4 in the Coordinator session; the wording of the line in `docs/STUDY-OVERVIEW.md` was their choice in the worker session. The worker read no output of the scored run and no record dated after the freeze devlog of 2026-11-22T02:30Z.

## Why

Studies 1 and 2 each had a readable design page; study 3 had none in `docs/`. Its design was committed, but spread over the frozen analysis plan, decisions D068 to D074 and their rationale, the corpus 3 and launch kit READMEs, the study 3 analysis README and the freeze record. The page puts it in one place.

The page comes after the results are known, unlike study 2's, which was published before its run. So it says in its status line that it is not pre-registration: study 3's pre-registration is the frozen plan, D068 to D074 and the freeze record, and they bind. To keep hindsight out of the text, its writer did not read the results (decision G2 (a)): it describes the design as frozen, not as later corrected.

## What the page holds

- **Form (G1 (a)):** study 2's sections where they apply: the question and what "better" means, the arms, the corpus, the tools and the guide, the experimental design (the schedule, the counting rules, the floor, the effort and CSL families, the claims, power and validation), the backend and the legacy-load record, cost as planned before the run, the freeze and the decisions D068 to D074. Each section links its source.
- **Sources:** the frozen plan; the study 3 analysis README as it stood at the scored run (the text of commit `9a2459ba416199495999b892847834a03d7f9524`, read with `git show 5a19c3d:study/analysis3/README.md`, the same bytes); D068 to D074 and the rationale section "Study 3 design: D068-D074"; the corpus 3 and launch kit READMEs; the freeze record; and the four study 3 devlog entries up to the freeze. They were read at main `94b11c974f919798b21fc56aa75e846ec87eaef5`, where the Coordinator had checked by path history that each one other than the analysis README was unchanged since the freeze.
- **Corpus-blind:** no task text, key, design note or reference solution; the corpus is given by counts and fields only, and the new tasks by group, without their ids.
- **What the sources leave out:** the freeze left the scored run's seed, budget and any top-up to the scored run's Job, so the page names them as not described.
- **A difference between two sources,** stated and not settled: DECISIONS says that D068 to D074 were recorded as project decisions on 2026-11-22, and the rationale's evidence line says 2026-11-21. The rationale is non-normative, so DECISIONS binds.

## The links (G3 (a))

`study/README.md` names the page after study 2's report, as written after study 3's scored run from sources frozen or decided before it. In `docs/STUDY-OVERVIEW.md` the list of documents that govern gains a "Study 3" bullet: the frozen plan, D068 to D074 and the freeze record, then the page, with the same note and marked non-normative, so that the list's opening sentence stays true. No other page changes; study 2's design page is unchanged.

## The review (G4 (a))

A Claude review of the first preview (`02c7142954de95abdd01fe1259499737`), run with `review_step.py run --reviewer claude`, checked the page against its sources. It was not saved, because it reported its own coverage as partial: it had no Git, so it could not read the analysis README at `9a2459b`, and it did not read the dry-run tallies of the freeze record. It found no blocker or major, 5 minors and 6 notes. On the lead developer's word ("Fix them all, please") the page was corrected:
- the freeze's commit ids are no longer credited to the freeze devlog;
- the plan's changes at the freeze are listed whole;
- the rationale's estimate of about 850 runs is set beside the freeze record's 904 in the four full arms, with the freeze record binding;
- study 2's page is named as a pointer only;
- the writer is named as the Job's AI worker;
- the rule for "DECISIONS binds" is now the project rationale's own status line;
- the analysis README's text is named by its `git show` command;
- `prices.json`'s cache write is given as 0.00;
- the D074 line is cut to strand 1 and strand 2's postponement.

The bullet in `docs/STUDY-OVERVIEW.md` stays as the lead developer chose it, and the last note needed no change.

A Codex review of the second preview (`bcd7aa408ad0f2eea6baeb779a32a4f9`), which the lead developer asked for, was saved with complete coverage. It found 3 majors and 4 minors, and on the lead developer's word ("All seven") the page was corrected:
- D071's wording is set beside the wider frozen scored set;
- the analysis README is cited by its text at `9a2459b`;
- the legacy-load figures are said to count the core set's counted runs;
- an unreadable log row is added to what makes a block not countable;
- the scoring contract is named by `study/harness/scoring_contract.py`;
- the sentence on decision 7 and the quote of D074's first answer are cut;
- this entry says the freeze left the seed, the budget and any top-up to the scored run's Job.

A Claude review of the third preview (`7958deae3596e91b1e55a421496e06b9`), the second round, found the seven fixes handled, plus 1 minor and 1 note. The minor noted that no committed rule names whether D071's wording or the frozen `tasks.json` binds. The lead developer chose to state both and name neither ("State both, no ruling"), and the note's link now points to plan section 3.

## What this changes and what it does not

The commit adds the page, its classification row (record, record-only, as study 2's design page), the two lines and this entry. The plan, the corpus, the scripts, `study/evidence/` and every frozen file are unchanged, and no run, stack, vendor call or key was used.
