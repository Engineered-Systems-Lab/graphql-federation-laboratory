# Study 2's graph arms pass step 7 again on the adapters 1.1.0, and every graph total equals its paged count

Date: 2026-11-04T19:53Z
Subject: Ran step 7 again for GraphQL Adapters, Apollo Federation and Cosmo Federation on the new images of the Missions and Assets adapters 1.1.0, ran the graph-arm totals check in each, and checked that the draw accepts the new reports and draws the same tasks
Status: Historical / non-normative
Provenance: Written on 2026-11-04 (UTC) by the worker of the Job study2_graph_totals, before the commit that carries it, from the reports in `study/evidence/study-2-preflight/graph-totals/`, the record `graph-totals-record-20261104T1953Z.json` there and the machine-local run files it names by checksum. Dated by the end of the last arm's run (epsilon), 2026-11-04 19:53 UTC by the machine clock (the driver logged 14:53:35 local time, UTC-5).

## The transition

The runtime commit `eb196ce59540d8e619618277132553276f8b1527` ([its entry](2026-11-04T1909Z-graph-page-totals-runtime-checkpoint.md)) gave the graph's Missions and Assets lists page fields with the services' totals and deprecated the old lists ([the D041 page totals revision](../project-governance/DECISIONS.md#d041-page-totals-revision-2026-11-04-accepted-scope)). Step 7's reports bind the observed stack through an observation fingerprint, which changes with the adapters' new images, so the reports of the three graph arms were stale. Under decision G2 of the Job the reference solutions stayed unchanged, so every hash that binds the reports held, and the direct arms' evidence stayed valid.

- **Images and configs.** The six images the stack builds were built and pinned once (2026-11-04 19:22 UTC), the adapters at 1.1.0, and the study configs were written from that pin set. Every rebuilt image got a new id, the Assets and Personnel services included, whose sources did not change; only the operator's Missions service image kept its id. The image ids are recorded in the pin set and in the dry run's provenance, not in the step 7 reports, which hold the observation fingerprint and the image tags only; the new graph-arm reports were therefore observed on newer builds of those two services than the original direct-arm reports.
- **The dry run.** A fake-client dry run (no key, no cost) of V05 to V08 in the three graph arms, both models: 24 runs, complete, and each arm's provenance matched the pin set.
- **Step 7.** The reference solutions ran in each graph arm on the real Oracle-backed stack with every set and each outage, on the lead developer's go for each arm: in every arm 75 tasks correct, and 4, 6 and 5 correct in the Missions, Assets and Personnel outages, the counts of the original reports, every report verified, with the original dataset fingerprint. Delta's first attempt stopped at the driver's own check that the Missions service was back, about 7 seconds after its restart ("missions is down, not up"); nothing was retried, and on the lead developer's choice delta ran again in full from a fresh stack, with that check asked up to 12 times. Every check of the second attempt passed at once. The worker reads the first stop as a readiness race; that is not verified.
- **The totals check.** In each arm, every total of `missionsPage` and `assetsPage` equals the paged count, unfiltered and for every value of every enum filter, the items equal the deprecated lists', and each filter's totals add up to the whole: 57 selections and 9 sums per arm, no problems, 300 missions and 32 assets.
- **The draw.** `draw.py --seed 313`, without writing, accepts the 8 original direct-arm reports with the 12 new ones, finds all 76 pool tasks eligible and draws the same 48 tasks as the committed `tasks.json`. The draw is not repeated, and its files and reports stay as they are.

## Not run or not covered

- No paid run: the new baseline without the tool belongs to the Job study2_calculate_v3.
- The direct arms were not run again; their reports and the stack they observed are the original ones.
- No model has used the page fields yet.

After the runs every stack was down and only Oracle and the Missions service were running.
