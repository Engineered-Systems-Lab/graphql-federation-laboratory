# Corpus 2's keys are derived a second time, blind, and the two derivations are compared on every task

Date: 2026-10-31T11:57Z
Subject: Imported the blind second derivation of corpus 2's keys (`derive_b.py`, `keys-b.json` and its tests) byte for byte, added the comparison with the first derivation, and recorded the seven differences the lead developer decided
Status: Historical / non-normative
Provenance: Written on 2026-10-31 (UTC) by the phase C worker of the Job study2_corpus_keys_b, before the commit that carries it, from the Job record (its scope, decisions K1 to K7 and the phase B record the Migration Coordinator wrote from the GPT worker's report as the lead developer relayed it), the worker's own checks and the lead developer's decisions in the worker's session. Dated by the time of writing, after the last decision; the decisions were made earlier the same day (UTC) and their exact times were not recorded. Tasks are named by id only.

## The transition

Corpus 2 had one derivation of its keys, `derive_a.py` and `keys-a.json`, written by a Claude worker. Study 2's design asks for a second, independent derivation before the keys are trusted, and the lab became public on 2026-10-30, so the second deriver's blindness had to rest on its setup alone.

**Phase B (recorded in the Job record before this phase, per K6).** A GPT worker wrote `derive_b.py`, `keys-b.json` and `test_derive_b.py` in a Codex cloud task with internet access off, on the lead developer's private repository built only from the keys-b package (packageSha256 `2e25f8f`, built from lab commit `6c18afa638ce583dcd79125177ba9a210f5a3686`): the questions, the ambiguity set's accepted interpretations, the development set without its expected answers, the schemas and the released data. The model is reported as "GPT-6 Astra High" as the Codex desktop app shows it (self-reported as Codex, based on GPT-6; the exact build is not exposed); a first run on a lighter model was stopped before it committed and does not count. Its commit in that repository is 26131e7, which was never pushed: the task printed the three files as one encoded block, which the lead developer saved and the Migration Coordinator decoded outside the lab. The recorded SHA-256 of `derive_b.py` begins `1e3e568` and that of `keys-b.json` `5e05e49`; B reported 90 keys, 11 of them with declared variants (39 alternatives), no gaps, 8 assumptions and 18 passing tests.

**Phase C (this commit).** The worker checked both recorded hashes before reading anything else of B, reproduced B in a scratch copy of the package outside the lab (`derive_b.py` reported no difference and its 18 tests passed), and imported the three files into `study/corpus2/` byte for byte. `compare_keys.py` compares the two derivations under the corpus's scorer on all 90 tasks (K3), and `test_corpus2.py` checks that B's files are the recorded bytes, that every input B hashed is the lab's own file (the development set after the rewrite that dropped its expected answers, rebuilt from the lab's file, and apart from the package's own manifest and README, which the package hash covers), that B is correct under A on every task and interpretation, and that the differences are exactly the decided ones. Each decision is bound to the exact differences and to the hashes of its task and of both keys' entries, so a changed question, schema or key needs a new decision. No key, question or derivation was changed.

## What the comparison found and what was decided

B's answer scores correct against `keys-a.json` on every one of the 90 tasks, and on every ambiguity task each of B's interpretations scores correct under A's rubric as that interpretation, with the same names. Seven differences remained, and the worker brought them to the lead developer one at a time with both answers, its reading and a proposal (K4):

- D07: one derivation writes null for names that cannot be established during an outage, the other an empty list. Decided both acceptable, as proposed.
- C02: B declares a variant with the other answer status, which A's checks already accept. Decided both acceptable, as proposed.
- D04, D09 and V04: B declares every partial subset of the identifiers as a variant (7, 15 and 3), which A's honesty checks already accept. Each decided both acceptable, as proposed.
- F02: the two keys' example answers show different accepted readings of the ambiguity task, and both readings agree. Decided both acceptable, as proposed.
- V06 (development set, never scored): B declares a variant with zero-count groups, which A's key rejects. The worker proposed that A was right; the lead developer decided that the question is unclear: "The wording does not unambiguously specify whether to include zero-count groups. A and B agree on the positive counts. Clarifying the question should be a separate Job; preserve both imported derivations unchanged."

## Limits

`derive_b.py` and `test_derive_b.py` read the package's manifest, which is not in the lab, so they run only in a copy of the package and the study gate does not run them. The comparison does not cover A's auxiliary facts on four tasks, which are not answers. Agreement between two derivations from the same questions and data is evidence about the derivations, not about whether every arm can answer a task; that is the later answerability check on the Oracle-backed stack. Clarifying V06's wording is left to its own Job.
