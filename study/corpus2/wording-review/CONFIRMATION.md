# Confirmation — wording of E01, E03, E06, E07

Reviewer's confirmation of the author's round 1 proposal. Every task passes all six checks, and no finding was raised, so no review round was needed (there are no REVIEW or ANSWERS files).

- Round confirmed: **1**
- `wording/proposal.json` confirmed: SHA-256 `c2b260165632fc79cb1a757ce3ca5577647849b60bc1eb3bad71f57dd8d414fd`
- `wording/PROPOSAL.md` (the author's notes for that proposal): SHA-256 `f700f08cdab913bede840b9e1b182d0ba74bbf80bc07c185d5aa2328b83d87ef`

## Files checked

- Every file listed in `MANIFEST.json` (69 files, package `keys-b`, packageSha256 `2e25f8f03ce2d5876edd0e10e94d1de2b4ad1c86f5533358555a79553b1ab679`, lab commit `6c18afa638ce583dcd79125177ba9a210f5a3686`): SHA-256 and size match for all 69. No file is missing and none is unlisted. I also checked the SHA-256 of each Personnel page against the snapshot's own `manifest.json`: all 10 match.
- `packageSha256` equals the SHA-256 of `MANIFEST.json` without that field, serialised as sorted, compact JSON. This confirms the author's statement in PROPOSAL.md.
- The data manifests the mapping releases name as checked against match the files here: Assets 1.1 manifest `b59ec52d…`, Missions 1.2 manifest `ed6a5d76…`, Personnel `personnel-v2-large-004` manifest `d44e96b8…`.
- The author's two files, as relayed, match the SHA-256 values given in the AUTHOR ROUND 1 message:
  - `wording/proposal.json` `c2b26016…`
  - `wording/PROPOSAL.md` `f700f08c…`

  The block held only those two files. It was committed as relayed in `9c07000`.

Data read, all inside this repository:
- E01: `uss-enterprise/assets/datasets/releases/1.1/assets.json`.
- E03: `uss-enterprise/missions/datasets/releases/1.2/` (`missions-*.xml`, with `release.json` checked against it), `federation/mapping-releases/1.3/crew.json` and the ten pages of `uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/`.
- E06: the Missions 1.2 files.
- E07: the Personnel snapshot.

The answers were computed with short standard-library scripts of my own, which are not committed.

## The form asked for

The question asks for the count first. It then closes with one instruction on the answer's form: "give the count per [group], leaving out [groups] with no such [records]". This replaces the old closing instruction "Give only the [groups] that occur." Everything before the closing instruction stays as it is.

## E01: PASS

1. **oldQuestion equals pool.json exactly:** yes, character for character (190 characters, ASCII only).
2. **Only the closing instruction changed:** yes. newQuestion is the unchanged text up to and including "of each status? " followed by "Give the count per status, leaving out statuses with no such assets." No other character differs. There are no non-ASCII characters, double spaces or control characters.
3. **One fair reading:** yes. "Such assets" refers to the assets the question counts: those whose own record names AST-0029 as their parent.
   - Second reading tried: tie "such assets" to the nearest noun phrase, "the assets aboard those" (the 3 grandchildren, all ACTIVE). Under it MAINTENANCE would be dropped although it has a qualifying asset.
   - I reject it as unfair. That phrase is explicitly excluded ("not …"). Applying the closing instruction to an excluded set contradicts "give the count per status". In a closing instruction, "such" naturally refers back to the records being counted.
   - The change makes nothing else in the sentence less clear.
4. **One question, one instruction, natural:** yes. It reads naturally and follows the prescribed form.
5. **Answer:**
   - Statuses in the data: ACTIVE, MAINTENANCE, DECOMMISSIONED, DESTROYED, MISSING (the same five as `STATUSES` in the dataset's `generate.py`).
   - 11 assets qualify: AST-0001, 0005, 0007, 0008, 0015, 0018, 0019, 0021, 0023, 0024, 0026.
   - Left out as empty: DECOMMISSIONED, DESTROYED, MISSING.

   | | ACTIVE | MAINTENANCE |
   |---|---:|---:|
   | Author | 10 | 1 |
   | Reviewer | 10 | 1 |
6. **Schema:** the answer validates (answerStatus ANSWERED; `statuses` items have only `status` and `count`; counts are integers; no duplicate statuses).

## E03: PASS

1. **oldQuestion equals pool.json exactly:** yes (225 characters, ASCII only).
2. **Only the closing instruction changed:** yes. The text is unchanged up to "counted once)? ", followed by "Give the count per department, leaving out departments with no such people." Nothing else differs. The mapping rule ("Using mapping release 1.3") and both parentheses are untouched.
3. **One fair reading:** yes. "Such people" refers to the people the question counts: the commanding officer and assigned crew of ST-00000LD9F.
   - Second reading tried: tie "such people" to "its participants". I reject it: participants are explicitly excluded, and the mission has none, so every department would be left out.
   - Nothing else in the sentence became less clear.
4. **One question, one instruction, natural:** yes.
5. **Answer:**
   - Commanding officer C-78 plus 18 assigned crew gives 19 distinct references. All 19 are mapped in mapping 1.3 to 19 distinct Personnel ids, and all are in the snapshot with a department.
   - Departments in the snapshot: COMMAND, ENGINEERING, FLIGHT_OPERATIONS, MEDICAL, OPERATIONS, SCIENCE, SECURITY.
   - Left out as empty: ENGINEERING.

   | | COMMAND | FLIGHT_OPERATIONS | MEDICAL | OPERATIONS | SCIENCE | SECURITY |
   |---|---:|---:|---:|---:|---:|---:|
   | Author | 1 | 1 | 1 | 1 | 2 | 13 |
   | Reviewer | 1 | 1 | 1 | 1 | 2 | 13 |
6. **Schema:** the answer validates.

## E06: PASS

1. **oldQuestion equals pool.json exactly:** yes (115 characters, ASCII only).
2. **Only the closing instruction changed:** yes. The text is unchanged up to "of each status? ", followed by "Give the count per status, leaving out statuses with no such missions." Nothing else differs.
3. **One fair reading:** yes. "Such missions" refers to the missions issued by Starfleet Science (`issuingAuthority` STARFLEET_SCIENCE). I found no second reading, and nothing else became less clear.
4. **One question, one instruction, natural:** yes.
5. **Answer:**
   - 66 missions qualify. The XML pages and `release.json` give the same result.
   - Statuses in the data, and in `schema.sql`: ACTIVE, AUTHORIZED, CANCELLED, COMPLETED, FAILED, PLANNED, POSTPONED.
   - Left out as empty: none. Every status occurs, so for this task the old and new wording give the same answer under either reading.

   | | ACTIVE | AUTHORIZED | CANCELLED | COMPLETED | FAILED | PLANNED | POSTPONED |
   |---|---:|---:|---:|---:|---:|---:|---:|
   | Author | 6 | 6 | 4 | 24 | 8 | 11 | 7 |
   | Reviewer | 6 | 6 | 4 | 24 | 8 | 11 | 7 |
6. **Schema:** the answer validates.

## E07: PASS

1. **oldQuestion equals pool.json exactly:** yes (90 characters, ASCII only).
2. **Only the closing instruction changed:** yes. The text is unchanged up to "each rank? ", followed by "Give the count per rank, leaving out ranks with no such members." Nothing else differs.
3. **One fair reading:** yes. "Such members" refers to the members of the Science department, so the ranks left out are those no Science member holds. I found no second reading of which groups belong, and the change made nothing less clear. (See the note below on who counts as a member; that question is older than this change.)
4. **One question, one instruction, natural:** yes.
5. **Answer:**
   - 133 crew records have department SCIENCE.
   - Ranks in the snapshot: CAPTAIN, CHIEF_PETTY_OFFICER, COMMANDER, CREWMAN, ENSIGN, LIEUTENANT, LIEUTENANT_COMMANDER.
   - Left out as empty: CAPTAIN, COMMANDER.

   | | CHIEF_PETTY_OFFICER | CREWMAN | ENSIGN | LIEUTENANT | LIEUTENANT_COMMANDER |
   |---|---:|---:|---:|---:|---:|
   | Author | 8 | 58 | 35 | 30 | 2 |
   | Reviewer | 8 | 58 | 35 | 30 | 2 |
6. **Schema:** the answer validates.

## Findings

None were raised in round 1, so none needed settling.

## What I could not check

- **The earlier key file.** PROPOSAL.md says each answer equals "the corresponding main answer in study/corpus2/keys-b.json" and gives a SHA-256 for it from an earlier session. That file is not in this repository, so I cannot confirm that claim or the hash. My conclusion that no answer changes rests on my own computation instead. Under the reading the study keeps, each answer computed from the released data equals the author's answer. The new wording selects exactly that reading.
- **Groups outside the data.** "The groups the data knows" is taken from the values present in the released files. For Assets and Missions these equal the vocabularies in `generate.py` and `schema.sql`. The package has no Personnel contract, so I cannot say whether Personnel defines ranks or departments that no record holds. This does not affect any answer: an empty group is left out either way.
- **Ordering.** I did not see the scorer. I assume it compares groups as a set, as the brief says. The author's lists are in alphabetical order.

## Notes outside this review's scope (not findings)

These concern wording older than this change. The brief keeps everything before the closing instruction as it is, so they do not affect this confirmation.

- **E07, who is a member.** 13 of the 133 Science records are not ACTIVE (7 ON_LEAVE, 6 INACTIVE). Counting only active members gives CHIEF_PETTY_OFFICER 7, CREWMAN 52, ENSIGN 32, LIEUTENANT 27, LIEUTENANT_COMMANDER 2. The keyed answer counts all 133. The question does not say which. The lab may want to know this.
- **E01, the parenthesis.** "Assets whose own record names AST-0029" could literally include AST-0029 itself, because its record names it as `assetId`. The words before it, "directly aboard or part of AST-0029", rule that out on any fair reading, so I see no real second reading.

## Round 2

The lead developer decided to settle the E07 membership note above in this same change. In round 2, E07 states that every member of the department counts, whatever their duty status. The answer stays the round 1 count over all members. The proposal I confirm is now **round 2**.

- Round confirmed: **2**
- `wording/proposal.json` confirmed: SHA-256 `62dea2ef6f46483616ac5d2555149486771b2029fdd3ca67845d2247347685db`
- `wording/PROPOSAL.md` (author's notes, round 2): SHA-256 `4e35eff7f940a86dc01194bc7d36dbabe94c6a870be68710bf901bef18660a86`
- `wording/CHANGE-2.md` (author's note on the round 2 change): SHA-256 `47074dc7dca2b75a6f7c5e7d6b261add3b4772c31d29b1c5d653765d48d6ccc2`

### Relay

- The first AUTHOR ROUND 2 block was corrupt and could not be unpacked. Its deflate stream broke at compressed byte 314 of 4,117 (gzip CRC and length errors). I used nothing from it and committed nothing.
- The resent block was used instead:
  - Its base64 text has SHA-256 `8521b008b48950f19b109b824a5e30a9ae5d56564a6267344cbb24e987bc9156` (5,484 bytes), as the author stated.
  - It unpacked cleanly into an empty folder, holding only the three files above.
  - All three match the SHA-256 values given.
- It was committed as relayed in `e272802`.
- The author's message also linked files under `/tmp/wording-round2-transfer-…` on the author's machine. I did not use them; only the pasted text was used.

### E01, E03, E06: unchanged

Compared with the round 1 `proposal.json` I confirmed (SHA-256 `c2b26016…`, commit `9c07000`):
- The raw text of the E01, E03 and E06 entries is byte for byte identical.
- The two files differ in exactly two lines: `"round": 1` → `"round": 2`, and E07's `newQuestion`.
- The PROPOSAL.md sections for E01, E03 and E06 are unchanged as well.
- The round 1 results above stand for these three tasks.

### E07: PASS

1. **oldQuestion still equals pool.json exactly:** yes, character for character.
2. **Only the allowed changes:** yes. newQuestion equals pool.json's question with exactly two edits and nothing else:
   - ", regardless of their duty status," inserted directly after "Science department";
   - the closing instruction replaced by "Give the count per rank, leaving out ranks with no such members.", the same as round 1.

   There are no other character changes: no non-ASCII characters and no double spaces.
3. **Exactly one fair reading:**
   - **Who counts:** every record whose department is SCIENCE, whatever its `dutyStatus`. The words "duty status" match the field `dutyStatus` that Personnel records. I tried the possible second readings:
     - counting only ACTIVE members is now ruled out by the words;
     - excluding DECEASED members as "not members" changes nothing here: the snapshot's only DECEASED record is not in Science (Science members are 120 ACTIVE, 7 ON_LEAVE, 6 INACTIVE);
     - civilians have no department;
     - no record outside SCIENCE has a science-like title.

     I found no second reading of who counts.
   - **Which groups are given:** "such members" now refers to the Science members of every duty status, so the ranks left out are those none of them holds. There is no second reading.
   - **Anything else unclear:** "their" can only refer to the members. I found no new unclarity.
4. **One question, one instruction, natural:** yes. The qualification sits inside the question, which still asks for the count first, followed by the one closing instruction on the form. It reads naturally.
5. **Answer:** I recounted all ten Personnel pages, each checked against the snapshot manifest, with no duty-status filter. 133 members:

   | | CHIEF_PETTY_OFFICER | CREWMAN | ENSIGN | LIEUTENANT | LIEUTENANT_COMMANDER |
   |---|---:|---:|---:|---:|---:|
   | Author | 8 | 58 | 35 | 30 | 2 |
   | Reviewer | 8 | 58 | 35 | 30 | 2 |

   - Left out as empty: CAPTAIN, COMMANDER.
   - The answer is identical to round 1.
   - The author's ACTIVE-only comparison table (7, 52, 32, 27, 2) and duty breakdown (120 / 6 / 7) in PROPOSAL.md also match my count.
6. **Schema:** the answer validates against E07's schema.

### Findings

None were raised in round 2. The E07 membership note from round 1 was never a finding. It is settled by the round 2 wording, which now counts every member as the key already did.

### What I could not check (round 2)

As in round 1, PROPOSAL.md and CHANGE-2.md compare the answers with an earlier `keys-b.json` that is not in this repository, so I cannot confirm that comparison. My confirmation rests on my own count from the released data.
