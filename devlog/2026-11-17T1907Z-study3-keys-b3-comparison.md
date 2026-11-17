# Study 3's second derivation of the new keys agrees with keys A on all 31 new tasks, with no difference to decide

Date: 2026-11-17T19:07Z
Subject: The Job `study3_corpus_keys_b` brought the blind second derivation of corpus 3's 31 new keys (keys B) into the lab byte for byte and compared it with keys A in the new `study/corpus3/compare_keys3.py`; the comparison found no difference
Status: Historical / non-normative
Provenance: Written on 2026-11-17 (UTC) by the phase C worker session of the Job (Anthropic Claude Code [Claude Opus 5.5], started by the Migration Coordinator), from the Job record, B's three files as published, the keys-b3 package rebuilt from Git and corpus 3's files. The date is the first run of `compare_keys3.py`, between the copy of B's files (19:05Z) and the worker's own reading of five tasks (19:08Z), to within two minutes. The entry names tasks by id only and quotes no question or answer.

## Why

Corpus 3's 31 new tasks (B16 to B31, C13 to C16, E17 to E27) had only keys A, derived in the lab by `derive_a3.py`. Study 2 checked every key with a second, blind derivation and decided every difference; decision C6 gives the new tasks the same check. The lead developer decided the scope one question at a time (J1 to J7): a GPT worker in a new Codex cloud task with no network, on a private repository made from the keys-b3 package alone (phase B), then a governed Claude lab worker that brings B's files in and compares them with keys A, every difference decided by the lead developer one at a time (phase C).

## Phase B, as the Job record holds it

- **Where:** the private repository's final commit b7dde8e0f475a88378adcb2bf316173ece13c39c, on branch work, on top of the package's 70 files; it adds exactly the three files. It is also recorded in `compare_keys3.py` (`B_RECORD`). Model: GPT-6 Astra High, as the lead developer reports, in a Codex cloud task with network access None. Date: 2026-11-17.
- **What B received:** the keys-b3 package, built by `study/blind/blind.py` from lab commit `4e90e5c90cc2c5ee6a221e14358261204b049011`: the 31 new tasks without their design notes and without the `directions` map, their schemas, the released data and B's own study 2 derivation, given to reuse. It held no first-derivation file, no design note and no carried, ambiguity or development task.
- **What B produced:** 31 keys with no variants and no gaps, and three assumptions (one on all 31 tasks, one on B17, one on C13 to C16). B reported that it was least sure of B17, C14 and C15.
- **The transcript** is kept outside the lab (J6). No question about B's inputs arose, and it was not read.

## Phase C

- **B's files.** `derive_b3.py`, `keys-b3.json` and `test_derive_b3.py` were checked against the SHA-256 in the Job record before and after the copy into the worktree, LF only, and are committed as published.
- **B's inputs.** `compare_keys3.py` rebuilds the keys-b3 package in memory from Git at the package's lab commit with the `plan` and `manifest_of` of `blind.py` as that commit holds it, loaded from Git. The rebuilt package has the recorded package hash and manifest SHA-256, each of the 70 inputs B hashed hashes as its file there, and the lab's current files are still the ones B received. `blind.py` and corpus 3's task, schema and manifest files are unchanged since that commit.
- **B's own checks.** In a copy of the package with the three files added, `derive_b3.py` reported no difference and `test_derive_b3.py` ran 11 tests that passed, as in the Coordinator's earlier check. The study gate does not run them, because they read the package's `MANIFEST.json`.
- **The comparison** imports corpus 2's `compare_keys.py`, unchanged, and runs its comparison of core tasks on the new tasks with corpus 3's scorer. It found no difference: on all 31 tasks B's answer scores correct under keys A and equals A's answer after the scorer's folding, and neither side declares a variant. `DECIDED` is empty, and nothing was put to the lead developer for a decision.
- **The worker's own reading.** For B17 and C13 to C16, which B's assumptions name, the worker read the question and the released data with its own code and found the answers both keys give. On B17 the person is never commanding officer or participant, so B's assumption on membership does not change the answer. On C14 and C15 no mission qualifies, and both keys give an answered empty list, which keys A accepts with either status.
- **The tests.** `test_corpus3.py` gains the class `TheSecondDerivation`: B's files are the recorded bytes, B's inputs are the rebuilt package's files, the builder is the lab commit's, B is correct under keys A on every new task, the differences are exactly the decided ones, and an undecided or changed difference fails the comparison. The corpus 3 suite ran 43 tests that passed.

## The review of the first preview

A review of the first preview, which the lead developer relayed, found that the reconstruction read the package definition from Git at the lab commit but ran it through the working tree's `blind.py`: a later change of the builder, such as a fourth package name, would make the reconstruction refuse the original definition although B's inputs were unchanged. The result was right on the day, because `blind.py` and its definitions are unchanged since that commit, but it depended on that. The builder is now loaded from Git at the lab commit, and the check of the current files reads the builder's folder from the same commit and only the packaged files from the working tree. Two tests pin both.

## What this changes and what it does not

The record adds B's three files, `compare_keys3.py`, the new tests, the README's paragraphs on the second derivation and the comparison, and this entry. No key, question, derivation, schema or check changed, corpus 2's files are unchanged, and corpus 3 stays `draft, not frozen`. Answerability on the Oracle-backed stack and the freeze remain later Jobs.
