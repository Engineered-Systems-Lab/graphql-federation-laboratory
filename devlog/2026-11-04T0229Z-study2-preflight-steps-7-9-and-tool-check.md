# Study 2's steps 7 and 9 pass on the real stack, and the calculation tool fails its declared check

Date: 2026-11-04T02:29Z
Subject: Ran step 7 (answerability) on the real Oracle-backed stack, drew the 48 scored tasks with seed 313, ran the two paid development runs, and recorded the tool check's failure and the lead developer's decisions
Status: Historical / non-normative
Provenance: Written on 2026-11-04 (UTC) by the worker of the Job study2_preflight_final, before the commit that carries it. Sources: the step 7 reports and the development runs' score tables and manifests, copied into `study/evidence/study-2-preflight/`; the run folders and transcripts in the machine-local results folder, cited by checksum; the lead developer's decisions in the worker session. Dated by the time of writing, just after decision Q7. Step 7 ran on 2026-11-02, run 1 on 2026-11-03 from 00:39Z to 01:22Z, and run 2 from 17:34Z to 18:48Z. The lead developer started both paid runs from their own terminal; the worker never held an API key.

## The transition

The backend preflight's go for the real Missions backend had two conditions: steps 7 and 9 had to pass. This Job ran both, made the draw, and ran the calculation tool's development check.

- **Step 7.** The reference solutions of all five arms ran on the real stack with every set and each outage. Every pool, ambiguity and development task was correct in every arm, with one dataset fingerprint across all 20 reports. One finding: Cosmo Federation read Assets as down for a few seconds after its restart, which step 6 had not seen. The lead developer asked for a re-check, which passed, and the pass continued.
- **The draw.** All 76 pool tasks were eligible. The lead developer stated the seed, 313, and `draw.py` wrote the 48 scored tasks once, in `f33ec6b101aa7bdb5d8ac061b0ddc54e5a395338`.
- **Run 1** (`study2-dev-notool-1`): the 8 development tasks in four arms, without the tool, 64 runs, 6.12 dollars. Two Claude V05 runs ended in a connection error after a request was cut at 60 s. The lead developer recorded them as harness errors: no score, not model failures, no re-run.
- **Run 2** (`study2-dev-tool-1`): study 2's block schedule with the tool in all five arms, 80 runs, 10.57 dollars. The Job spent 16.70 dollars of its 28.
- **Defects found on the way.** Run 2's dry runs exposed two defects in the launch kit, both before any paid request.
  - The Assets image was rebuilt with a new id at every stack start. The Job study2_launch_images fixed it in `3baac2193e34c339ae3d5f77661dbcc4046ca951`.
  - Stopped containers of other arms stayed in the stack project and were read by the provenance check. This Job fixed that in `4e88460fdb1dece0e8689b84d9a486eb824efc30`.

  The third dry run passed every block.

## The tool check

The design declares that the tool is fit only if two kinds of failure fall (the agent cannot count, and token volume), the definitional failures stay the same, and no new kind appears. The check compares V05 to V08 in Guided Direct Access, GraphQL Adapters, Apollo and Cosmo, with both models.

- **Counting failures fell from 7 to 2.** The two left were hand tallies in runs that never called the tool.
- **Definitional failures stayed at 0.**
- **No new kind appeared.** Twelve refused calculate calls were each corrected on the next call.
- **Token-volume failures rose from 1 to 7, all on V05.**

The cause: fetched results still enter the conversation in full, the tool calls add turns that read that context again, and `distinct` returns every value. With the tool, the models stopped guessing and ran out of tokens instead.

The lead developer decided: "The check fails. Record it and proceed". Under the design, the tool design returns to the lead developer before the corpus freeze. The redesign is a separate Job. The lead developer agreed on how a redesign is tested: an offline replay of run 2's stored results, a worker exercising the tool, a fake-client dry run, then one paid confirmation of V05 to V08.

## Step 9 and the go

Run 2's behaviour per arm matches study 1 and gamma-prime-1.

| Arm | Correct | Cost per run (dollars) |
| --- | --- | --- |
| GraphQL Adapters | 15/16 | 0.103 |
| Guided Direct Access | 14/16 | 0.145 |
| Apollo Federation | 13/16 | 0.100 |
| Cosmo Federation | 13/16 | 0.109 |
| Direct Access | 9/16 | 0.204 |

Guided Direct Access costs 1.33 to 1.45 times as much per run as the access layers, a smaller gap than study 1's (1.90 to 1.95 times).

Direct Access's seven failures have three causes:

- **Endpoint discovery:** four wrong answers had no successful answer from any service.
- **Token limit after reaching the data:** two V05 runs.
- **Token limit during a mostly failed search:** one V02 run, where discovery's share is not established.

The go now reads:

- **The backend:** the conditional go holds, with steps 7 and 9 passed.
- **The tool:** no-go as built, so the freeze waits for a redesigned tool that passes.

The record is `study/evidence/study-2-preflight/preflight-record-steps-7-9-20261104T022919Z.json`.

## Limits

- **The measurements hold for the current tool.** The tool's overhead (about 970 tokens per request for Claude, 480 for GPT) and the tokens per run (×1.21 to ×1.70) must be measured again after the redesign.
- **The budget estimate leans high.** The scored runs come to about 71 dollars at run 2's cost per run, but the dev set is half aggregation tasks.
- **The 60 s request cut is not explained.** It hit both vendors (nine attempts in run 1, one in run 2), and no request over 60 s succeeded in either run.
- **Step 9's verdict was the worker's proposal.** It was accepted with decision Q7.
- **Run 2 is one trial of a small set.** It is not an estimate of any arm's accuracy.
