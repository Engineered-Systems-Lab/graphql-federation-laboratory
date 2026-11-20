# Study 3's preflight runs live: corpus 3 is answerable on Oracle in every arm, and a paid run of the development tasks completes

Date: 2026-11-20T18:35Z
Subject: The Job `study3_preflight`, study 3's level 2 preflight before the freeze, on the code at commit `4d44f05b381b7b7cf6309632b95ffd4b19852174` and, for the paid run, `195be55d2e27a6d9d8a5ae378fc72cf62eaaab06`: corpus 3's answerability on the real Oracle-backed stack in all five arms with the three outages, a free dry run of the paid run's config with the legacy-load request log, and the paid run of the 8 development tasks with both models
Status: Historical / non-normative
Provenance: Written on 2026-11-20 (UTC) by the worker session of the Job (Anthropic Claude Code [Claude Opus 5.5], started by the Migration Coordinator), from the worker's own step logs, the reference and harness reports and the legacy-load sessions, which stay machine-local in `C:/esl/_study3/preflight/`, and from the two committed records `study/evidence/study-3-preflight/preflight-record-ab-20261120.json` and `preflight-record-c-20261120.json`. The date is the end of the paid run's last block, the Job's last paid step, read from the run's block log; the bundle was written about a minute later. Every go and decision named below was the lead developer's, typed in the worker session; the paid runs were started by the lead developer from their own terminal. The entry names tasks by id only, and no question, key, submission or transcript was read.

## What ran

Oracle's container and the Missions service were started with `docker start` on their existing containers, as for the kit check, at 05:48:41Z and 05:49:08Z. The dataset fingerprint was `missions-db:8aae139eea3d5ad9ff764bc15502c804ccae4f94b9504b687a163a6d0bf76dd1`, study 2's, in every step of the day, with one Oracle session, `oracle-instance:2026-11-20T05:48:52`. `launch.py build` passed and wrote the image pin set at 05:49:28Z; the Missions service image is unchanged at `01baf41`.

- **Phase A, answerability.** In each arm, `study/corpus3/reference/run_reference.py` ran every set and then each set under the Missions, Assets and Personnel outages, with a service restart, `launch.py ready` and `--check-services` after each outage. Every task was correct in all five arms: core 107 of 107, ambiguity 6 of 6 and development 8 of 8, outages included. Nothing went over the limits, every check after a restore passed and nothing was refused. The 90 task ids carried from corpus 2 were correct here as in study 2's preflight, and the 31 new core tasks were correct in every arm. The 20 reports are committed.
- **Phase B, the dry run.** `runner.py --dry-run` ran the paid run's config on the real stack as `study3-preflight-dry-1`. It was study 3's block schedule as it is, 64 runs in the four full arms plus the 16 runs of the Direct Access reference block, 80 in all, as the lead developer chose. All 17 blocks ended at attempt 1 with every provenance check matching and every health point up. The 80 runs ended `format_error`, the fake client's empty answers. The request log of the legacy systems saved 17 sessions whole, with clock offsets under 0.12 s. Placed by time, the 128 Missions and Personnel requests came before a block's first run and the 6 Assets requests in the restores after V04's Assets outage; none fell inside a run. `study/analysis3/legacy3.py` passed its bundle, sums, scorer, corpus, plan and schedule checks and stopped with exit 2: it reads only a bundle of the scored core set.
- **Phase C, the paid run.** The plan was the dry run's, with the 10 dollars of the scope split as 6.40 for Anthropic and 3.60 for OpenAI.

## The paid run

The first attempt, `study3-preflight-dev-1`, started at 14:39Z. The lead developer stopped it at the start of its eighth block, `r3-epsilon`, because the Anthropic key was invalid. Its score table holds 31 recorded outcomes: gpt-6.1-sol's 15 runs were scored and all correct, and claude-sonnet-5-5's 16 record 14 `vendor_error` and 2 `error` outcomes, with no score. It spent nothing on Anthropic and about 1.06 dollars on OpenAI. The Cosmo stack it left up was taken down with `launch.py down epsilon` on the lead developer's word, and its request log was saved whole.

The lead developer renewed the key and raised the ceiling to 11 dollars for the rerun, split by the same ratio as 7.04 and 3.96, with the first attempt's spend not counted against it. The config differed from the dry run's only in those ceilings. The rerun, `study3-preflight-dev-2`, ran from 17:18:58Z to 18:35:15Z and completed. The lead developer switched their VPN off after it started, and it left no mark: no run had a vendor error and the ledgers record no retry.

| Arm | Correct | Mean dollars per run | Study 2's step 9 |
| --- | --- | --- | --- |
| Direct Access | 7 of 16 | 0.099 | 9 of 16, 0.204 |
| Guided Direct Access | 16 of 16 | 0.097 | 14 of 16, 0.145 |
| GraphQL Adapters | 16 of 16 | 0.072 | 15 of 16, 0.103 |
| Apollo Federation | 16 of 16 | 0.037 | 13 of 16, 0.100 |
| Cosmo Federation | 15 of 16 | 0.036 | 13 of 16, 0.109 |

- **Outcomes.** 70 runs were correct, 8 `wrong_answer` and 2 `did_not_finish`, split evenly between the models: 35 correct each. Outside Direct Access, one run was not correct: V08 in Cosmo Federation with claude-sonnet-5-5. In Direct Access, V02 and V03 failed with both models, V05 hit the tool-call limit with both, V04 and V08 failed with gpt-6.1-sol and V06 with claude-sonnet-5-5.
- **By task.** V01 and V07 were correct in 10 of 10 runs, V04 and V06 in 9 of 10, and V02, V03, V05 and V08 in 8 of 10.
- **Limits.** Two runs reached the 80 tool calls. The longest run took 220.4 s of the 900 allowed, and the largest used 936,034 of the 1,000,000 tokens. The harness tools took 299 `calculate` calls, 23 of them errors, and 9 `ask_requester` calls.
- **Spend.** 3.3815 dollars on Anthropic and 2.0622 on OpenAI, 5.44 in all, about 0.068 per run. With the first attempt, the Job's paid total was about 6.50 dollars.
- **The checks around the run.** All 17 blocks ended at attempt 1 with no requeue or void, every provenance check matched, and all 45 health points were up.
- **The check before scoring.** The 17 sessions of the request log were saved whole, and the largest clock offset was 0.105 s. In every delta and epsilon block, Personnel answered 13 requests in a row with 200 before the first run, against the 11 the reader needs; over a whole session the longest such runs were 15 to 23, requests made during the runs included. The only answers other than 200 were three Assets 404s in each of the four delta and epsilon blocks of rounds 2 and 4.
- **legacy3.** On a verified copy of the rerun's 272 files, `legacy3.py` stopped with exit 2, as on the dry run.

## What went wrong, and the fixes

- **The first record preview.** A pasted review of the first record transaction's preview found two errors before the go. The 20 reports had been hashed as the machine-local CRLF files while Git stores them with LF, so every recorded hash was wrong. And the dry run's 6 Assets requests had been called initialization load. The reports were stored with LF and both hashes recorded, the requests were placed by time, and a new preview took the go.
- **An invalid key.** The first paid attempt ran with an invalid Anthropic key until the lead developer stopped it. The stop left the Cosmo stack up; it was taken down on their word.

## State left behind

No stack was left up and no study process was running. The Missions service and Oracle were stopped again with `docker stop` at 2026-11-20T19:36Z, Oracle with a 600-second timeout, and both exited as they were found. The configs, the reports, the run folders and the request logs stay in the Job's machine-local folder.

## What was not covered

The paid run covers the 8 development tasks only, so it gives no accuracy figure for the scored core set, and `legacy3.py` gave no figures. The dry run and the paid run checked the schedule, the stacks, the provenance, the budget and the legacy-load path. The kit, the corpus, the analysis and the frozen files are unchanged.
