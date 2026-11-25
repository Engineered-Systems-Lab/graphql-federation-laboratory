# Study 3's scored run completes: 1,130 runs in 17 blocks, with no stop

Date: 2026-11-25T05:42Z
Subject: Ran study 3's paid scored run, study3-scored-1, on the frozen plan and corpus 3 at commit `37124bdb3767d8f244e14c3c28832006a7e5b3ea`, after a free rehearsal of the same config; carried the preflight's spend against the ceilings for all of study 3; ran with the VPN off; restarted the machine for a Windows Update before the go; topped up OpenAI during the run when its balance came within the alert margin; and ran legacy3.py on a checked copy of the bundle
Status: Historical / non-normative
Provenance: Written on 2026-11-25 (UTC) by the worker of the Job study3_scored_run, after the run's bundle said complete. Dated by the time the harness wrote the bundle (05:42:33Z). Sources: the Job record; the worker's session, with the lead developer's answers, the worker's reports and the times its log gives; and the run folders, read after the runner had exited, in a machine-local results folder with their SHA-256 lists. The lead developer ran the launcher in their own terminal; the worker held no API key, ran the free rehearsal and the read-only watcher, and read no outcome. This entry holds no accuracy, no outcome per arm and no comparison: those belong to the analysis.

## The run

- **Run id:** `study3-scored-1`, launched by the lead developer on 2026-11-24 from PowerShell with `$env:LAB_RESULTS_DIR='<results folder>'; py -3 study/harness/launcher.py run -- --config <config> --run-id study3-scored-1`.
- **Dates:** the manifest at 18:00:23Z on 2026-11-24, the first block start at 18:01:08Z, the last block end at 05:41:14Z on 2026-11-25 and the bundle at 05:42:33Z: 11 hours 40 minutes from the first block start to the last block end.
- **Code:** commit `37124bdb3767d8f244e14c3c28832006a7e5b3ea`, tree not dirty. The 11 frozen files hashed as the freeze record lists them, and the 21 files the run executes hashed as its `codeFiles` list them, unchanged since `c5c4d9656daec97268462d3ba04752482ce40912`; the worker checked both before the containers started and again before the go.
- **Plan hash:** `8c873c6e26607a34805ac1e695a0a9f1a72529d2640a9c19aeebc402381f8fb5`, the same as the rehearsal's, with the same identity and schedule in both manifests.
- **Bundle:** status `complete`, checksum `457ce298d1426a4d762bd217dd314a302e8da7ec9b73061c0a1c4e6a64133f06`, no void attempt.
- **Seed:** 19810803, as the lead developer gave it in decision S5. The plan differs from the second freeze dry run's in four fields only: the seed (19810803 against the dry run's 20261120), the budgets (the dollar ceilings of 70 and 45 with their basis, decision S2, against the dry run's nominal 6.40 and 3.60), `earlier_study_runs` (the two earlier runs it carries, decision S1, against none) and its `about` text, which describes the plan.
- **Schedule:** `williams-4-half`, the letters a beta, b delta, c epsilon and d gamma; the round order 3, 4, 1, 2; the Direct Access reference block last. 17 of 17 blocks ended in the manifest's order, 1,130 of 1,130 runs, attempt 1 only, in one launcher session.
- **Health:** 266 health checks, all up. The dataset fingerprint at every block start was `missions-db:8aae139eea3d5ad9ff764bc15502c804ccae4f94b9504b687a163a6d0bf76dd1`, study 2's. No vendor error, no retry and no requeued run for either vendor.

## Before the run

- **The backends.** Oracle and the Missions service had been stopped since the freeze. The worker started them at 13:50:47Z on 2026-11-24, and the dataset fingerprint read the same as study 2's and the freeze's. The stack's six images were built once for the run, from 13:51:39Z to 13:51:46Z, with a new pin set. Every federation stack was down at the start.
- **The carry (decision S1).** The two paid preflight runs, `study3-preflight-dev-1` and `study3-preflight-dev-2`, were copied whole into the scored run's results folder, 400 files, each checked by SHA-256 against its source, with the sources left as they were. Their ledgers, priced with each run's own manifest, give 3.38 dollars for Anthropic and 3.13 for OpenAI. The manifest's `budgetCarry` shows the same totals, and they count against decision S2's ceilings of 70 and 45 dollars for all of study 3.
- **The free rehearsal (decision S6).** `study3-scored-rehearsal-1`, the scored config with `--dry-run` (the fake vendor client, no key, no vendor call) in the same results folder, from 15:27:32Z to 16:21:33Z on 2026-11-24. It ended complete with 17 of 17 blocks and 1,130 runs, the same carry and the plan hash above. It is not listed among the earlier runs, because its fake ledgers are not spend.
- **A Windows restart before the go.** This was a restart of the machine, not of the study: the rehearsal had ended at 16:21:33Z, the paid run had not started, and the paid run later had no stop and no resume. When the go was prepared the lead developer said that keep-awake was off and that Windows Update was installing and would need a restart. At the lead developer's word the worker stopped the Missions service and Oracle cleanly at 17:43Z, and Windows restarted (the machine reports its boot at 17:45:41Z). The lead developer set sleep and hibernate on AC to never, on a desktop machine. With a second go the worker started Oracle at 17:50:51Z and the Missions service at 17:51:08Z; the fingerprint read the same as at 13:51Z, and the seven pinned image ids were still present and unchanged, so nothing was rebuilt.
- **The go (decision S7).** One go for the whole run. The worker asked for it at 17:52Z, after the restart above, with the plan hash, the seed and schedule, the carry, the ceilings, the balances, the watcher command, the network check and main's hashes shown. The lead developer answered "Go" in the worker's session and ran the launcher in their own terminal. The manifest gives 18:00:23.754Z, and the session's log wrote the go at 18:00:24.056Z, 0.3 seconds later, both by the machine's clock. The log's time is when the message was written to the session's log, not when it was typed or sent, and no record gives the time the launcher command was entered, so the records do not show whether the go was typed before the launch. The worker wrote down the time of the go at 18:00:31Z.

## The network path

The run ran with NordVPN off, from the rehearsal through the end, as decision S4 has it: the egress was the direct path of the machine's internet connection, with its exit in Columbia, Maryland, United States, the same path as study 2's scored run. The worker checked it read only. The first check, at 13:52:57Z, found the VPN on: the NordLynx adapter was up and held a default route, and the exit read Ashburn. Nothing ran on the network path until the lead developer had turned it off. The checks at 13:56:12Z before the rehearsal, at 15:27Z when the rehearsal started and after the restart before the go found the NordLynx adapter and NordVPN's OpenVPN adapter disconnected and the only default route on the Wi-Fi adapter.

## The balances, and no stop

The run started on the balances the lead developer read and stated in the worker's session at 17:42Z on 2026-11-24, before the machine's restart and 18 minutes before the go: 112.70 dollars for Anthropic and 23.20 for OpenAI, equal to their reading of 2026-11-22 (decision S3). No run called a vendor between that reading and the go: the rehearsal had used the fake client, and the paid run had not started. Decision S3 has two alert lines for each vendor: the room under its balance falling under the estimated rest of the run plus 5 dollars, or under 10 dollars. The read-only watcher reported after every block with the room under each balance and its estimate of the rest, and the worker gave the lead developer both figures in the session at every block end. Anthropic's room stayed above both lines.

- **Before the top-up.** After block 1 OpenAI's room exceeded the estimated rest by 8.42 dollars. After block 2 the room (21.09 dollars) fell under the estimated rest plus 5 dollars (19.21 plus 5), and the worker told the lead developer, in the session and by a push notification. From block 2 to block 8 the room exceeded the estimated rest by 1.88 to 3.89 dollars, and the worker sent two more push notifications, after blocks 5 and 6.
- **The top-up.** The lead developer bought OpenAI credits during the run and said: "I purchased OpenAI credits, new balance is $19.20". The worker restarted the watcher with that balance at 22:24Z, during block 9. The restarted watcher's first report, at 22:24Z, gave OpenAI's spend as 9.25 dollars and its room as 18.98 (the stated balance less what the run settled since the restart and what its open requests may still cost), against an estimated rest of 12.83: 6.15 dollars over it. For Anthropic it passed 94.51 dollars, the stated balance less the run's spend at that time, not a new reading.
- **After the top-up.** From block 9 to block 16 OpenAI's room exceeded the estimated rest by 4.59 to 5.56 dollars. It was under 5 dollars at the ends of blocks 9, 11, 12, 13 and 14; the worker reported each of these margins in the session and named the first three as under the alert line, with no push notification. The lead developer did not top up again.
- **The reference block.** The worker priced the reference block's first runs from the ledgers, by usage only, at 02:44Z and 03:19Z on 2026-11-25. They cost more per run than the watcher's mean, which put OpenAI's margin at about 3 dollars and its room at about 9.50 and then about 8.21 dollars. The worker told the lead developer in the session that the margin was under the 5-dollar line. At the end of block 17, the last, with no run left to price, OpenAI's room was 2.76 dollars, and the worker reported it in the session.
- **The 10-dollar line.** The watcher gave OpenAI's room as 10.10 dollars at the end of block 16 and 2.76 at the end of block 17, its next report. By the worker's own pricing from the ledgers the room was already under 10 dollars at 02:44Z, about 9.50. The worker's 02:44Z report gave that figure but named the notice for the 5-dollar line only. The worker first named the 10-dollar line at the end of block 17, saying the room fell under it "at the very end", which was not exact.

OpenAI's room never fell under the estimated rest, so the run had no stop and no resume. Anthropic's room stayed above 66 dollars.

## The dollars

| Vendor | This run | Tokens | Carried | Study 3 in all | Ceiling |
| --- | --- | --- | --- | --- | --- |
| Anthropic | 46.24 | 71,139,091 | 3.38 | 49.63 | 70 |
| OpenAI | 25.47 | 38,452,879 | 3.13 | 28.60 | 45 |

The figures are the harness's own estimate at the dated prices, from the bundle; they are not vendor invoices. Most of the tokens are cached reads: 60,696,202 for Anthropic and 32,434,173 for OpenAI.

## After the run

- **legacy3.** The worker copied the run folder and checked the copy file by file against its SHA-256 list (3,422 files), copied the stack's legacy-load folder (136 files, 34 sessions: the rehearsal's 17 and the run's 17) and ran `study/analysis3/legacy3.py` on the copies with the study's MCP interpreter, `--run-id study3-scored-1` and the bundle checksum. A first call stopped with exit 2 because the worker had made the output folder beforehand, a usage slip; the second exited 0, with 34 sessions read, all 17 blocks countable and the tier descriptive. Its output stays machine-local and was not read for figures.
- **The backends.** Every federation stack was down after the run. At the lead developer's word the Missions service and Oracle were stopped at 11:33Z to 11:34Z on 2026-11-25, with their containers kept.

## What is kept, and where

Everything is machine-local, outside the repository, under `C:/esl/_study3/scored`. Each SHA-256 list names its files relative to the folder it sits in, and the lists verified against the files after the run:

| What | Where | Checksum list | SHA-256 of the list |
| --- | --- | --- | --- |
| The scored run (3,422 files) | `lab-results/study3-scored-1/` | `lab-results/SHA256SUMS-study3-scored-1.txt` | `c6da89d8beee91671c947238f05ec1d0cbd40c4397fb77a66428ead72308fb9c` |
| The rehearsal (2,292 files) | `lab-results/study3-scored-rehearsal-1/` | `lab-results/SHA256SUMS-study3-scored-rehearsal-1.txt` | `b5d87023695d6ea563ed2930bded5747e6758f72620f73ba4876c97503b98248` |
| The two copied runs (400 files) | `lab-results/<run id>/` | `lab-results/SHA256SUMS-carried` | `c81e64d1e7ecb22bc9c78ffd9a3eb1bb89f1610f45d2b9c59dc554a0b3e0e129` |
| The plan and config, the pin set and the logs | `config/`, `state/images.json`, `logs/` | `SHA256SUMS-setup` | `159eb292ebe9fbbd5339fc673ad7b46ef69d12fb3dac7b809fb4e40d722826fe` |

In the scored run's list, `study3-scored-1/bundle.json` has the SHA-256 `80ec1fdc9f3afe21ed6c5268e2a8675d914ce29df31eff1e3902a1ae039c434b`; the bundle's own checksum above is the harness's over the files it lists. legacy3's output is in `legacy3/out/`: `legacy-load.json` with the SHA-256 `74cd99afc684cdc03a5d200ecaad7ab6dc3119723dc6fe417f15e571b8254cb7` and `legacy-load.md` with `34340372101b33fdc91081e6f10c31aeba51d2c095942c8bb57c7d704cb358f9`.
