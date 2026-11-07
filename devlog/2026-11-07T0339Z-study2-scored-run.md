# Study 2's scored run completes: 540 runs in 17 blocks, with one stop on the token budget and one resume

Date: 2026-11-07T03:39Z
Subject: Ran study 2's paid scored run, study2-scored-1, on the frozen design and the code at commit `32e6b828d53a8f09bab55eff1a5703a65d50be58`, after a free rehearsal of the same config; carried the spend of the seven earlier paid study-2 runs against the ceilings; ran with the VPN off; stopped once on the Anthropic token budget and resumed with a higher token figure; and checked the watcher's dollar figure for an earlier run against its ledgers
Status: Historical / non-normative
Provenance: Written on 2026-11-07 (UTC) by the worker of the Job study2_scored_run, after the run's bundle said complete. Dated by the time the harness wrote the bundle (03:39:51Z). Sources: the Job record, the lead developer's answers in the worker's session, and the run folders, read after the runner had exited, in a machine-local results folder with their SHA-256 lists. The lead developer ran the launcher in their own terminal; the worker held no API key, ran the free rehearsal and the read-only watcher, and read no outcome. This entry holds no accuracy, no outcome per arm and no comparison: those belong to the analysis.

## The run

- **Run id:** `study2-scored-1`, launched by the lead developer on 2026-11-06 with `py -3 study/harness/launcher.py run -- --config <config> --run-id study2-scored-1`.
- **Dates:** the manifest at 23:51:43Z on 2026-11-06, the first block start at 23:52:27Z, the stop at 01:57:39Z on 2026-11-07, the resume at 02:03:49Z, the last block end at 03:38:44Z and the bundle at 03:39:51Z: 3 hours 47 minutes from the first block start, the stop and the 6-minute wait included.
- **Code:** commit `32e6b828d53a8f09bab55eff1a5703a65d50be58`, tree not dirty. The six frozen files hashed as frozen, and the 21 files the run executes hashed as the freeze record's `harnessAfterFreeze` lists them (`runner.py` `65f462a`), before the start and again before the go.
- **Plan hash:** `7d4ea34cfbbc6c1d5b8ba9285aa62d768575e177090588a9d1ffaaa74a9a9dec`, the same as the rehearsal's.
- **Bundle:** status `complete`, checksum `ba12c57484e850aeb379cd9876900ab9f3ba3eb285b5e5a07aaa5e69c047ac5a`.
- **Seed:** 20220213, named by the lead developer in the worker's session at 22:58:04Z on 2026-11-06, before the plan was written and before any schedule was drawn with it (decision X4). It differs from the dry runs' 20261106 and the development runs' 20261102.
- **Schedule:** the letters a beta, b gamma, c delta and d epsilon; the round order 4, 2, 3, 1; the Direct Access reference block last. 17 of 17 blocks ended, 540 of 540 runs, attempt 1 only, no void.
- **Health and provenance:** 150 health checks, all up; 18 provenance checks (one per block start, r1-beta twice), all a match. No vendor error and no retry for either vendor.

## Before the run

- **The backends.** Oracle and the Missions service were still up from the freeze's dry runs, and the dataset fingerprint read the same as theirs (Missions release 1.2, the same Oracle instance), so no Oracle, reset or service step was needed. The stack's six images were built once for the run, with a new pin set. Every federation stack was down at the start.
- **The carry (decision X1).** The seven paid study-2 runs were copied whole into the scored run's results folder, 914 files, each checked by SHA-256 against its source, with the sources left as they were. Their ledgers, priced with each run's own manifest, give 24.45 dollars for Anthropic and 13.74 for OpenAI. The manifest's `budgetCarry` shows the same totals, and they count against decision D's ceilings of 85 and 40 dollars.
- **The free rehearsal (decision X5).** `study2-scored-rehearsal-1`, the scored config with `--dry-run` (the fake vendor client, no key, no vendor call) in the same results folder, from 23:00 to 23:42Z on 2026-11-06. It ended complete with 17 of 17 blocks and 540 runs, the same carry and the plan hash above. It is not listed among the earlier runs, because its fake ledgers are not spend.
- **The go (decision X6).** One go for the whole run, given by the lead developer in the worker's session with the plan hash, the seed and schedule, the carry, the balances, the network path and main's hashes shown. The lead developer confirmed that keep-awake was on and no Windows Update was pending.

## The network path, a dated change

The design's list of what is held constant names the VPN exit (Ashburn), and study 1 ran through the VPN. This run ran with NordVPN off, from the rehearsal through the end, as the lead developer decided (decision X3): the egress was the direct path of the machine's internet connection, with its exit in Columbia, Maryland, United States. The worker checked it read only before the rehearsal, before the go and before the resume: the NordLynx adapter and NordVPN's OpenVPN adapter were disconnected, and the only default route was the Wi-Fi adapter. The reason is the 60-second cut that the Job study2_prerun_fixes found: on the VPN path a TCP connection that carries no bytes for about 60 seconds is closed, and every failed vendor request of the seven paid development runs was a connection error at 60.04 to 60.19 seconds. Every arm ran on the same path. This run had no vendor error.

## The stop and the resume

- **The stop.** At 01:57:39Z the run stopped with `budget_stop` in r1-beta, the thirteenth block, when a request of the run `beta__E14__claude-sonnet-5-5__r1` did not fit the budget. The cause was the Anthropic token budget, not the dollars: 11,969,853 of the plan's 12,000,000 tokens had been used, most of them cached reads (9,671,999), which count toward it, against 9.23 dollars spent. The 12,000,000 came from the dry runs' plan, where it was a nominal figure for the fake client, and the Job's scope had listed it; nobody noticed before the go that it would not cover the paid run. The stop was clean: blocks 1 to 12 had ended, the cut run's interrupted result was saved in its run folder, the stack was torn down and the stop's bundle was written.
- **The decision.** The token figure is not part of the plan identity, so a resume with another figure keeps the plan hash. The worker estimated that the whole run would need about 23.5 million Anthropic and 12.2 million OpenAI tokens. The lead developer decided: "Yes. raise both token budgets to 40,000,000 and resume." A second config differed from the first only in the two token figures; the dollar ceilings and their basis were unchanged.
- **The resume.** The lead developer resumed at 02:03:49Z with `--resume` and the second config. The harness kept 343 finished runs, recorded the unchanged ceilings, restarted r1-beta at attempt 1 with its missing runs and ran to the end. When it ran `beta__E14__claude-sonnet-5-5__r1` again, it moved the interrupted result into that run's `attempts/001` folder (the folder was made at 02:04:41Z, its files are those written at the stop) and kept the new result as the run's own. The watcher therefore reports r1-beta as started twice within one attempt.

## The dollars

| Vendor | This run | Tokens | Carried | Study 2 in all | Ceiling |
| --- | --- | --- | --- | --- | --- |
| Anthropic | 16.89 | 25,029,887 | 24.45 | 41.34 | 85 |
| OpenAI | 7.39 | 11,476,808 | 13.74 | 21.13 | 40 |

The figures are the harness's own estimate at the dated prices, from the bundle; they are not vendor invoices. The run started on balances of 60.00 and 25.90 dollars and needed no top-up (decision X2).

## The watcher's dollar check

The Job study2_run_watch left one check for this entry: on the development run `study2-dev-tool-1` the watcher gives 6.70 dollars for Anthropic and 3.87 for OpenAI, 10.57 in all, and the harness's `ledger_dollars` on the same two ledgers gives the same figures. The worker priced the ledgers again before the copy (6.7031 and 3.8718) and found them equal. During the scored run the watcher reported after every block, read only, and showed no outcome.

## What is kept, and where

Everything is machine-local, outside the repository, under `C:/esl/_study2-scored`. Each SHA-256 list names its files relative to the folder it sits in, and the lists verified against the files after the run:

| What | Where | Checksum list | SHA-256 of the list |
| --- | --- | --- | --- |
| The scored run (1,656 files) | `lab-results/study2-scored-1/` | `lab-results/SHA256SUMS-study2-scored-1` | `b6e47372633e688d3cceb71faa7207f26c03239d696132e8c39d8556d9cd6b35` |
| The rehearsal (1,112 files) | `lab-results/study2-scored-rehearsal-1/` | `lab-results/SHA256SUMS-study2-scored-rehearsal-1` | `2660096f92ed7356049d24899a10b3c2a0bf768027d9521443f34ed85cec9c49` |
| The seven copied runs (914 files) | `lab-results/<run id>/` | `lab-results/SHA256SUMS-carried` | `137803e3415db29048eb2063319d67565941ae840e47dee5fc0e804ccc7f3c9e` |
| The two plans and configs, the pin set and the logs | `config/`, `state/images.json`, `logs/` | `SHA256SUMS-setup` | `51750d0925dc042d873258978a6b9f87b82c25b780594855831eb8a26fa14dc4` |

In the scored run's list, `study2-scored-1/bundle.json` has the SHA-256 `de7f989b55caf20870ac73c92b11ab5caa5cca1d19e1c5c5e08030dbccc8299e`; the bundle's own checksum above is the harness's over the files it lists. After the run every federation stack was down, and at the lead developer's word the Missions service and Oracle were stopped with their containers kept.
