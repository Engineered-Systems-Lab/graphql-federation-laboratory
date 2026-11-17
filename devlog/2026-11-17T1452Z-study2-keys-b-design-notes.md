# Study 2's keys B package held 49 design notes: 23 gave B access to answer guidance, and B's records show use on 3

Date: 2026-11-17T14:52Z
Subject: The Job `study2_keys_b_design_notes` classified the 49 design notes of study 2's keys B package (background, method or answer-bearing) and, for each answer-bearing note, looked for evidence that the second derivation used it, in its code, its records and its Codex transcript; the result is `study/corpus2/keys-b-design-notes.json`
Status: Historical / non-normative
Provenance: Written on 2026-11-17 (UTC) by the worker session of the Job (Anthropic Claude Code [Claude Opus 5.5], started by the Migration Coordinator), from the exact package handed to B, keys A at the package's lab commit, B's three files in the lab and the Codex transcript that the lead developer exported into the worker's session, which stays outside the repository (decision N3). The date is the time the first classification file was written. Every classification and finding was put to the lead developer in the preview before any commit (decision N2); the first preview's review changed three things, described below, and the commit waits for the lead developer's go on the corrected preview. The entry names tasks by id only and quotes no note or question.

## Why

Study 2 checked its answer keys (keys A) with a second, blind derivation (keys B), on the grounds that B saw only the questions, the schemas and the released data. The package also held each task's design note, written by the author of keys A. The study3_blind_inputs worker found them there. A note that states an answer, a decisive count or the accepted status gives B access to answer guidance for that task; whether B relied on it is a separate finding, and matching answers establish neither. The lead developer decided the scope one question at a time (N1 to N5): all 49 notes, a Claude worker classifies and the lead developer reviews every row, the transcript read if exportable, one record transaction, and the wording of study 2's corroboration decided later, from these counts (N5).

## How

- **The package.** `study/blind/blind.py verify` on `C:/esl/_blind-packages/6c18afa638ce/keys-b` reported no problems; its lab commit is `6c18afa638ce583dcd79125177ba9a210f5a3686`, and the package hash and the manifest file's SHA-256 are the ones recorded for the Job `study2_corpus_keys_b`. Every note was read from the package's own files, not from the lab's current ones, which the wording review changed after B.
- **The rubric** was written into the Job record before the first classification: background, method, answer-bearing, the strongest kind present winning, judged from the note alone against keys A at the package's lab commit. Every note was classified before any of B's files was read for evidence.
- **The findings** take one of three values: used (the code hard-codes a value or rule taken from the note where the question and data do not give it, or a basis, assumption, test or record cites the note), derived from data (computed by the question's rule, with no citation; reliance not excluded, only not shown) and undetermined.
- **The transcript.** The lead developer exported it into the worker's session; its part on the keys B derivation was read, not the later wording rounds of the same thread. It holds B's commands and narrative, not the commands' output. Among its first commands, before `derive_b.py` was written, B issued commands that print every task in full and then every task's design note; that the notes were displayed is inferred from those commands, since their output is not in the export. It added no citation beyond those in the code.

## The review of the first preview

A GPT reviewer's review of the first preview, which the lead developer relayed, raised three points. Each held when checked against the rubric and changed the record before the commit:

- **C12** was reclassified from answer-bearing to method. Its number is the size of the input, like those of G06 to G10. It constrains the sum of the three counts asked for, but it is not in the key and fixes no field of it.
- **Whole or part.** The rubric calls a disclosure whole only when the note alone gives the full key. C03 needs the schema's rule, and D01, D02, D05, D06, D10 and D11 need the stoppedService field, so they are now part. C02 alone stays whole.
- **What was observed.** This entry no longer states a review before it took place, and the access found in the transcript is stated as the commands B issued, not as what B displayed.

## The counts

| Set | Notes | Background | Method | Answer-bearing | Used | Derived from data | Undetermined |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pool | 39 | 5 | 16 | 18 | 3 | 6 | 9 |
| dev | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| ambiguity | 6 | 0 | 1 | 5 | 0 | 4 | 1 |
| all | 49 | 9 | 17 | 23 | 3 | 10 | 10 |
| scored | 30 | 4 | 11 | 15 | 1 | 7 | 7 |

The scored row counts the notes among study 2's 54 scored tasks (the 48 drawn pool tasks and the 6 ambiguity tasks of `study/corpus2/tasks.json`); 24 of those tasks have no note.

- **Answer-bearing (23):** C02, C03, G01, G05, D01, D02, D03, D04, D05, D06, D07, D08, D09, D10, D11, D12, D13, D14, F01, F03, F04, F05 and F06. Only C02's note fixes the whole key; the others fix a part.
- **Used (3):** C02, D04 and D09. B's code or its recorded assumptions cite the note, or what only the note says.
- **Derived from data (10):** G01, G05, D03, D08, D13, D14, F01, F04, F05 and F06.
- **Undetermined (10):** C03, D01, D02, D05, D06, D07, D10, D11, D12 and F03.
- **Scored and answer-bearing (15):** C03, G05, D03, D04, D05, D06, D10, D11, D12, D14, F01, F03, F04, F05 and F06; of these, D04 is used.
- **The seven decided differences** of `compare_keys.py`: four fall on an answer-bearing task, C02, D04, D07 and D09; F02 is method, and V04 and V06 are not answer-bearing (V04 has no note).
- **Borderline:** F02's note was classified method and flagged for the lead developer's review.

## What this changes and what it does not

The record adds the classification file and this entry. No key, no decision of the comparison, no frozen corpus 2 file, no analysis and no report changed. How study 2's report states the corroboration that keys B gave is decision N5, taken after this Job reports. Corpus 2's README does not name the notes among keys B's inputs and does not list the new file; both are left to the same decision.
