# Confirmation of the revised guide

This is my check of the author's revision against my findings (`findings/FINDINGS.md`, SHA-256 `f80a2ed813aabd66fa104a402d1924cdeb0af8226271fcbd1ee13df369b2b235`).

## The file checked

- **File:** `draft/GUIDE-revised.md`, from the author's commit `794eb1a577c2f3e67210678e01a22b57faa18757`.
- **Size:** 10,889 bytes.
- **SHA-256:** `0cf9368b2ef9df980bdc5cf4dc4c53f735b4b06875afaff3d7d389c61c859fe3`. Both match the values the lead developer gave.
- **Line numbers:** below they are those of `draft/GUIDE-revised.md`.

The author disputed no finding, so there is no disagreement to weigh.

The lead developer answered my open question in section 5 of the findings: the reader sees only the tools' own descriptions and parameters, not the README sections of TOOLS.md. I took that answer into account. The rules found only in those README sections are now stated by the guide itself:

- HTTP errors come back as ordinary results;
- `isError` marks a tool refusal or an unreachable service;
- redirects are not followed;
- URL forms that are refused;
- the 200,000-character cap and `truncated`;
- the mapping-result shape and errors for an unknown release or file.

They appear on lines 11, 13 and 15. They are right to stay, so size item 8 of my findings no longer applies.

## Finding by finding

| Finding | Fixed? | What the revision says, and where |
| --- | --- | --- |
| A1 | Fixed | No relay round, request ID or relay file is mentioned. Observations are stated as facts of the services (for example line 83, AST-0006 and AST-0025 return 200, and line 87, the beyond-end page). |
| A2 | Fixed | No mention of TOOLS.md, the READMEs, the identity design or contract 1.0. The rules are stated directly (lines 11, 13, 15, 87). |
| A3 | Fixed | The "Limits" paragraph and the release-hash discussion are gone. The usable part survives on line 103: no cross-service snapshot and no historical roster lookup. |
| A4 | Fixed | Line 93: Missions release 1.2 is given context, not exposed on the wire. Personnel reports personnel-v2-large-004. Use mapping 1.3, whose manifest names checks against both. If either context changes, flag it and ask. |
| A5 | Fixed | Line 25: a Get body sent with the List action returns 500 Server InternalError; check for a mismatch before declaring an outage, and retry once, correctly or without an action. Line 40: InternalError can mean an action mismatch. |
| A6 | Fixed | Line 79: the parent is required, null or an existing VEHICLE ID; no cycles. No attribution to the contract. |
| C1 | Fixed | Lines 48–57: every filter's values, exact and case-sensitive, and the names of priorities 1 to 5. See W2 for one wording point. |
| C2 | Fixed | Line 61: the Mission's field order; commander optional in PLANNED and CANCELLED and required otherwise, and need not be assigned; location parts. Line 63: stardate format and range, durationHours bounds, and that lastUpdated is independent of stardate. Line 67: optional costs and outcome; a no-estimate cancellation may carry actual 0.00. |
| C3 | Fixed | Line 54: each status's meaning. Line 59: cancellation can precede approval, and transitions are not enforced, so report them as recorded. |
| C4 | Fixed | Line 71: the 108 participant-correction entries (2368-12-23, C-85, ordered by C-78, unchanged status, zero deltas, the summary prefix), and that lastUpdated is the correction time. Leave them out of operational counts and dates, say so, and keep them for audit counts. |
| C5 | Fixed | Line 69: across missions, older events may have larger changeIds, so sort by changedAt and allow ties. Use changeId for one mission's mutation order. |
| C6 | Fixed | Lines 29–32: department, duty-status, rank and clearance values. Line 27 still says there is no rank or clearance filter, so listing rank among the "tokens" does not suggest a filter. |
| C7 | Fixed | Line 27: Get returns all statuses. Line 38: civilian, inactive and cross-department supervisors and several roots are valid, with no cycles; the 19 migrated civilians have no supervisor; migrated clearance comes from the rank rule (stated in full); clearance is not independent evidence of authorization. |
| C8 | Fixed | Line 73: the thresholds for each classification; not enforced, so stored assignments may have insufficient clearance; classification is metadata, not access control. |
| C9 | Fixed | Line 65: Missions filters take C-n and local asset references; AST-0004, C-085 or a P or O commander gives 400, not "no matches", so map first. Line 85: offset=00 gives 400. Line 87: parentAssetId=EQ-64 gives 400, while a well-formed absent AST-0097 selects nothing. |
| C10 | Fixed | Line 95: every release maps 8 assets. Line 97: every deployed P should map under 1.3, and a missing entry is a mismatch; C-2372, C-3423, C-9938, EQ-108 and VS-12 are examples of unmapped references; C-4752 and P-1068 both map to PRS-0003. |
| C11 | Fixed | Line 83: the meaning of each asset status; all of them resolve; there are no status dates. |

All 17 findings are fixed. The size list was applied as well: every evidence parenthesis, the 1.0 grammar note, the reclassification history and the "Limits" paragraph are gone, and the description of `calculate` is cut down to guidance (line 103).

## Errors the revision introduced

None. I checked every new or reworded statement of the revision against the sources and the live answers (my round 1 and the author's rounds), and found no claim that a source contradicts. The statements checked:

- the enums;
- the field order;
- the stardate and duration bounds;
- the commander rule;
- the cost rules;
- the correction entries;
- the clearance rule for migrated people and the classification thresholds;
- the identifier grammar;
- the 400 cases;
- the mapping counts and examples;
- the use of release 1.3.

## Wording the revision made unclear

These are not factual errors. In each case the shorter wording can be misread, and a reader that misreads it would act wrongly. Each is small, and the author can fix it in a few words.

### W1. Line 36: "identity survives subtype changes, not evidence of historical subtype"

- **Problem:** the compression drops the subject of the second clause. As written, it reads as if the identity, or the ID, were not evidence of anything. The original meant that a person's current subtype is not evidence of their subtype in the past: for example, Wesley Crusher (PRS-0714) is crew now and was a civilian in an earlier snapshot.
- **Source:** `package/docs/PERSONNEL-V2.md`, "Model and ownership" (IDs "survive subtype changes"); `package/docs/PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md`, "Personnel v2: identity survives classification".
- **Suggested text:** "An ID keeps the same person through a subtype change; the current subtype is not evidence of an earlier one."

### W2. Line 57: the priority row of the table "Exact case-sensitive values"

- **Problem:** the row reads "1 CRITICAL, 2 URGENT, …". Under that heading a reader may send `priority=CRITICAL`. The filter and the field take only the digit 1 to 5; the names are meanings.
- **Source:** `package/uss-enterprise/missions/contracts/missions-v1.1.xsd` line 95 (pattern `[1-5]`); live, my round 1 `m-filter-priority` (`priority=1`, 200); `m-filter-lowercase-enum` shows that a token other than the exact value is refused with 400.
- **Suggested text:** "priority: send the digit 1–5 (1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL, 5 ROUTINE)."

### W3. Line 3: one rule was lost in shortening

- **Problem:** the original opening said the three services "do not validate each other's references". The revision drops this. Its parts survive elsewhere: line 97 says many references are unmapped, line 99 says "target absent" and "unmapped ≠ nonexistent", and line 73 says clearance is not enforced. What no longer appears is the general rule: a mission's crew or asset reference may name something that does not exist, and a reader should not assume it was checked.
- **Source:** `package/docs/MISSIONS-V1-DESIGN.md`, "Ownership and identifiers" (no cross-service existence, availability or clearance validation; inconsistent references are possible); `package/uss-enterprise/assets/contracts/assets-v1.1.openapi.json`, `info.description` ("never checks the assets that other services reference").
- **How sure:** sure that the sentence is gone. A careful reader can piece the rule together from lines 97 and 99, so its impact is low.
- **Suggested text:** restore "No service checks another's references." in the opening line.

## Size

The revision is 10,889 bytes: under the 20 KB limit and about 1.9 KB over the 9 KB target. The three wording fixes above add fewer than 150 bytes. If the author wants to get closer to the target, it could cut:

- on line 11, "HEAD normally gives bodyless 405:", keeping only "Use GET";
- the beyond-end JSON example on line 87, since line 85 already states the rule.

These are optional; nothing the reader needs depends on them.

## Second revision

### The file checked

- **File:** `draft/GUIDE-revised-2.md`.
- **Size:** 10,990 bytes.
- **SHA-256:** `e9a4c12620fea0b924683666f20f44a60a4d8888088b583038e1e47cd0b3fade`. Both match the values the lead developer gave.
- **Encoding:** the file is valid UTF-8 with LF line endings, like the first revision. It has the same 103 lines.
- **The dash on line 57:** it is U+2013, an en dash. The author's answer to W2 showed it as "ΓÇô" when it was pasted, but the file itself holds the correct character.

### What changed

A line-by-line comparison with `draft/GUIDE-revised.md` shows exactly three changed lines: 3, 36 and 57. Every other line is byte for byte the same. The author took neither optional size cut, so nothing else needed checking.

### W1 to W3

| Point | Fixed? | Line | The revised text, and the check |
| --- | --- | --- | --- |
| W1 | Fixed | 36 | "IDs PRS-0001..PRS-9999 preserve case/padding. An ID keeps the same person through a subtype change; the current subtype is not evidence of an earlier one." Each clause now has its subject, and the rule matches `package/docs/PERSONNEL-V2.md`, "Model and ownership" (IDs "survive subtype changes"), and the Wesley Crusher case (PRS-0714 is a civilian in personnel-v2-small-001 and crew in personnel-v2-small-002 and in the deployed personnel-v2-large-004, author R2 `personnel-mapped-wesley`). |
| W2 | Fixed | 57 | "Send the digit 1–5 (1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL, 5 ROUTINE)". The token to send is now explicit and the names are marked as meanings. It agrees with `package/uss-enterprise/missions/contracts/missions-v1.1.xsd` line 95 (pattern `[1-5]`) and with my round 1 `m-filter-priority` (`priority=1`, 200). |
| W3 | Fixed | 3 | "No service checks another's references." This agrees with `package/docs/MISSIONS-V1-DESIGN.md`, "Ownership and identifiers" (no cross-service existence, availability or clearance validation), with `package/uss-enterprise/assets/contracts/assets-v1.1.openapi.json`, `info.description` (Assets "never checks the assets that other services reference"), and with `package/docs/PERSONNEL-V2.md`, "Model and ownership" (Personnel never consumes Missions classifications). The parent check inside Assets (line 79) is a check within one service, so the two lines do not conflict. |

### Errors introduced

None. Each changed line states only what its sources and the live answers support. No other line changed.

### Size

The guide is now 10,990 bytes: 101 bytes more than the first revision, under the 20 KB limit, and about 2 KB over the 9 KB target. The two optional cuts named above still apply if the author wants them.

All 17 findings and the three wording points W1 to W3 are now fixed.
