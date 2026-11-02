# Findings on draft/GUIDE.md

Reviewer's findings on the integration guide `draft/GUIDE.md` (11,909 bytes, SHA-256 `4d66ec5888f3c8b561ce882d931100ef1f36b0d1ad68bdf95d04225ab6dd6e06`). Line numbers are those of that file. "Author R1/R2" means the author's relay rounds in `author-relay/`. "Reviewer R1" means my relay round in `relay/` (requests `relay/round-001.requests.json`, answers `relay/round-001.answers.json`). Each request is cited by its `id`.

## 1. Files checked and the hash check

**Root manifest.** All 38 files listed in `MANIFEST.json` were checked against their SHA-256 and size. 37 matched as delivered. One did not:

- `author-relay/round-001.requests.json` was delivered as 6,560 bytes, SHA-256 `3615d4db…bbd1`.
- `MANIFEST.json` and the round 1 request hash in `author-relay/LEDGER.json` both give 6,591 bytes and `85e01233124764e15d98411cf56f25731fc69f8f2708b858331ad487d3935e33`.
- Cause: the file has 31 line breaks and was exactly 31 bytes short. The lead developer confirmed that Git on their machine (`core.autocrlf=true`) converted the file from CRLF to LF when the repository was committed, and that the CRLF bytes are the true ones.
- At the lead developer's instruction I restored the CRLF line endings, checked that the result matches both recorded hashes, and committed it as the restoration of the original bytes (commit `2315913`). Nothing else under `package/`, `draft/`, `author-relay/` or `evidence/` was changed.

**Package manifest.** All 29 files listed in `package/MANIFEST.json` matched their SHA-256.

**packageSha256.** `packageSha256` (`17d027e0…7684b`) matches. The manifest does not say how it is computed. It is the SHA-256 of `package/MANIFEST.json` with the `packageSha256` member removed, serialized as compact JSON with sorted keys.

**Files read in full or in the parts that bear on the guide:**

- every file of `package/`;
- `draft/GUIDE.md`;
- the requests, answers and ledger of `author-relay/`;
- both files of `evidence/`.

**My relay files:**

- `relay/round-001.requests.json`: SHA-256 `ac19be576ca7fc42d237d007c0d88198e8be7aef872b05791952efb7b3cd9920`.
- `relay/round-001.answers.json`: SHA-256 `983f5b88849639cb6415bbf97e87a91fb0bdc1cd277173c14fa0055619396724`.
- `relay/LEDGER.json`: SHA-256 `2e908c5afb218846808b0fd5cfac0048bbde8121bb6f170a1405576d4ff1dbc5`.

All three match the values the lead developer gave. The round's fingerprint was the same before and after the round. The Missions data was the same as in the author's rounds (dataset release 1.2, the same releaseSha256).

## 2. Accuracy findings

### A1. Citations of relay rounds, request IDs and relay files that the reader cannot open

- **Where:** the opening paragraph, line 5: "R1/R2 mark live checks in `relay/round-001.answers.json` / `round-002.answers.json`, identified by request ID". The same kind of citation appears throughout:
  - line 15 ("R1 Personnel 500 has `isError=false`", "R1 refused an extra header");
  - line 17 ("R1 contents match package bytes");
  - line 19 ("(R2)");
  - line 21 ("and in the relay");
  - lines 25, 31, 37, 39, 43, 45, 47, 51, 55, 59, 61, 63, 65, 82 and 88 (each "R1 …" or "R2 …");
  - line 94 ("not relay citation IDs or metadata");
  - line 98.
- **What is wrong:** the reader has no tool that opens these files. The rounds, their request IDs and "package bytes" are facts about how the guide was made, not about the systems. In this repository the author's files are under `author-relay/`, not `relay/`.
- **Source:**
  - `package/TOOLS.md`, "The sandbox", line 212: nothing reads a file for an agent except `read_mapping_release`, which serves only the mapping-release `.json` files.
  - `package/TOOLS.md` lines 9–31: the three MCP tools and their parameters.
- **How sure:** certain.
- **What correct text would say:** state each observed behaviour as a fact of the deployed service, with no round or ID. For example: "The Personnel service answers a fault with HTTP 500 and the tool reports it as a normal result, not a tool error." Drop the sentence about where the observations are recorded.

### A2. References to documents the reader never sees

- **Where:**
  - line 5: "Rules derive from package contracts/designs and TOOLS.md";
  - line 17: "Despite TOOLS.md's blanket wrapper wording";
  - line 21: "TOOLS.md restricts URLs …";
  - line 39: "not the README's small-002 default";
  - line 65: "Contract 1.1 replaces historical 1.0 grammar";
  - line 78: "superseding the Missions README's earlier deployment statement";
  - line 80: "Old identity-design padded examples are illustrative, not mappings".
- **What is wrong:** the reader knows its tools by their descriptions, not by a file called TOOLS.md. It has never seen the READMEs, the identity design or contract 1.0. A statement that corrects a document the reader has not read tells it nothing it can use.
- **Source:**
  - `package/README.md`, "What is here": these are the author's inputs.
  - `package/TOOLS.md` line 3: "The tools an agent is given, as the agent reads them".
- **How sure:**
  - Certain for the READMEs, the identity design and contract 1.0.
  - For "TOOLS.md", fairly sure. The reader sees the texts but not the file name. I cannot tell whether the reader is shown the two "From the MCP servers' README" sections of `package/TOOLS.md` (lines 195–213) or only the tool descriptions (see section 5).
- **What correct text would say:**
  - Give the rule itself: "Mapping results are `{"truncated", "content"}`, where `content` is the file's JSON as a string. They are not the `{status, contentType, truncated, body}` shape of the HTTP and SOAP tools."
  - Give the facts: "Personnel serves personnel-v2-large-004; mapping release 1.3 is the one checked against the deployed data."
  - Delete the comparisons with documents the reader does not have.

### A3. The "Limits" paragraph is about how the guide was made

- **Where:** "Errors and reasoning tools", line 98, the whole paragraph:
  - "Limits: outages, redirects, truncation and dataset changes were not exercised; handling is contractual."
  - "Calculation/requester tools were not relay-callable."
  - "Relay Missions releaseSha256 differs from the mapping manifest's checkedAgainst hash for 1.2; equivalence is unestablished."
  - "Missing linked documents were not reconstructed."
- **What is wrong:** none of this is about the systems. The relay's releaseSha256 appears only in the relay answer header (`fingerprint.before.reading.clock.releaseSha256`, `2c330ac2…7f66f`). No tool shows it to the reader, so the reader cannot act on the doubt.
- **Source:**
  - relay answer files, header `fingerprint` (author R1/R2 and reviewer R1);
  - `package/TOOLS.md` lines 9–31.
- **How sure:** certain that it is unusable. I could not settle whether the two hashes name the same release (see section 5).
- **What correct text would say:** delete the paragraph. Keep only "No service gives a historical view or a snapshot across calls", which lines 45 and 63 already say. If the release question needs saying, say it as a rule. See A4.

### A4. The reader is told to choose the mapping release by "observed" Missions 1.2, but it cannot observe the Missions dataset release

- **Where:** "Mapping and incomplete joins", line 78: "Use 1.3 for observed Missions 1.2/Personnel large-004 … Otherwise check version context/manifest; ask if unavailable."
- **What is wrong:** Missions puts no dataset version on the wire.
  - The Mission, missionList and changeList elements have no version element.
  - The design says the contract has no wire marker for its minor version, and that the contract version is independent of the dataset.
  - The release in service (1.2) appears only in the relay's fingerprint header, which the tools do not show.
  - Personnel, by contrast, returns `datasetVersion` in every response.
  - So the reader cannot "observe Missions 1.2", and "check version context" leaves it nothing to check for Missions.
- **Source:**
  - `package/uss-enterprise/missions/contracts/missions-v1.1.xsd` lines 221–271 (no dataset-version element);
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Contract evolution" ("There is no wire marker (header or element) for runtime discovery of the minor"; "The contract version is independent of any `datasetVersion`");
  - live: the header `fingerprint.before.reading.clock.datasetVersion` = "1.2" in author R1, author R2 and reviewer R1;
  - `package/federation/mapping-releases/1.3/manifest.json`, `checkedAgainst` (Missions release 1.2, personnel-v2-large-004).
- **How sure:** certain that Missions exposes no dataset version. Fairly sure of the correct text.
- **What correct text would say:** "The deployed Missions data is dataset release 1.2. Missions reports no dataset version, so take this as given. Personnel reports `datasetVersion` personnel-v2-large-004 in every response. For these deployments use mapping release 1.3, whose manifest names checks against Missions release 1.2 and personnel-v2-large-004. If a Personnel response reports another datasetVersion, say that the mapping may not fit, and ask."

### A5. A wrong SOAPAction produces a Server InternalError, which the guide tells the reader to treat as a service failure

- **Where:**
  - "Personnel", line 31: "Set `soap_action` to the application namespace plus `:GetPersonnelMember`. For lists use … `:ListPersonnelMembers`. R2's empty list also succeeded without action."
  - "Errors and reasoning tools", line 88: "Contractual Server faults ServiceUnavailable/InternalError mean service failure."
- **What is wrong:** live, a GetPersonnelMember envelope sent with the ListPersonnelMembers SOAPAction is answered with HTTP 500, `soap:Server` and code `InternalError`, with no `field`. A reader that follows line 88 will report an outage or missing data when the fault is in its own request. Omitting the action works (author R2). A mismatched action does not.
- **Source:**
  - live: reviewer R1 `p-get-with-list-action` (500, faultcode `soap:Server`, code `InternalError`);
  - live: author R2 `personnel-defaults-without-action` (no action, 200);
  - `package/uss-enterprise/personnel-v2/contracts/personnel-v2.wsdl` lines 42 and 48 (one soapAction per operation);
  - `package/docs/PERSONNEL-V2.md` line 28: unexpected errors are sanitized. The contract does not say that an action mismatch is an InternalError; the live answer is the behaviour.
- **How sure:** certain of the behaviour. I tested only this one mismatch: a Get body with the List action.
- **What correct text would say:** "`soap_action` must name the same operation as the request wrapper in the body, or be left out. A mismatched action is answered with 500 `soap:Server` `InternalError`. Before you treat an InternalError as a service failure, check that the action matches the body, and retry once without the action."

### A6. "Contract requires an existing VEHICLE parent and no cycles" (low impact)

- **Where:** "Assets", line 59.
- **What is wrong:** the contract states that a named parent exists. It says outright that it cannot express the VEHICLE rule. The VEHICLE-only and no-cycle rules come from the design and are enforced by the database. The behaviour the reader sees is the same, but the attribution is wrong.
- **Source:**
  - `package/uss-enterprise/assets/contracts/assets-v1.1.openapi.json`, `components.schemas.Asset.properties.parentAssetId.description`;
  - `package/docs/ASSETS-V1-DESIGN.md`, "The asset record", **Parent**;
  - `package/docs/ASSETS-V1-DESIGN.md`, "The read service", **Schema** (the trigger).
- **How sure:** certain. The impact on the reader is small.
- **What correct text would say:** "A named parent always exists and is always a VEHICLE (STARSHIP, SHUTTLE, ROVER or ARMORED_VEHICLE). Parent chains have no cycles."

## 3. Coverage findings

### C1. Missions enumeration values, and the names of priorities 2 to 4

- **Where:** "Missions", lines 47–49. The guide names the filters but gives none of their values, except priority 1 = CRITICAL and 5 = ROUTINE.
- **What is missing:** the reader cannot build a valid filter without the exact tokens. Values are case-sensitive: live, `status=completed` is 400 INVALID_REQUEST.
- **Source:**
  - `package/uss-enterprise/missions/contracts/missions-v1.1.xsd` lines 137–183;
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Mission model and cardinalities" (enum table and the priority row);
  - live: reviewer R1 `m-filter-lowercase-enum`, and `m-filter-locationType`, `m-filter-issuingAuthority`, `m-filter-classification` and `m-filter-priority` (all 200).
- **How sure:** certain.
- **What correct text would say:**
  - type: DIPLOMATIC, EXPLORATION, SCIENTIFIC, FIRST_CONTACT, MEDICAL, RESCUE, HUMANITARIAN, SECURITY, TACTICAL, TRANSPORT, MAINTENANCE.
  - classification: UNCLASSIFIED, SECRET, TOP_SECRET.
  - status: PLANNED, AUTHORIZED, ACTIVE, POSTPONED, COMPLETED, FAILED, CANCELLED.
  - locationType: PLANET, STARBASE, VESSEL, SECTOR, DEEP_SPACE, ENTERPRISE, OTHER.
  - issuingAuthority: STARFLEET_COMMAND, ENTERPRISE_COMMAND, STARFLEET_MEDICAL, STARFLEET_SCIENCE, STARFLEET_SECURITY, FEDERATION_COUNCIL.
  - priority: 1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL, 5 ROUTINE.
  - Tokens are exact and case-sensitive.

### C2. The Mission record: its fields, and when the commander is absent

- **Where:** "Missions", lines 51–53. The guide covers references and costs but never lists the Mission's fields. It does not say that the commander may be absent.
- **What is missing:**
  - The field order: missionId, title, type, classification, status, priority, stardate, durationHours, objective, location, issuingAuthority, then commandingOfficerId (optional), assignedCrewIds, participantIds, assignedAssetIds, then estimatedCostCredits, actualCostCredits and outcome (all optional), then lastUpdated.
  - location holds type, name, and optionally coordinates and travelVector.
  - commandingOfficerId may be absent in PLANNED and CANCELLED, and is present in every other status. Live, 26 of the 30 PLANNED missions and many CANCELLED ones have no commander. A CANCELLED mission without an estimate carries an actual cost of 0.00.
  - The commander need not appear in assignedCrewIds.
  - durationHours is a whole number from 1 to 8760.
  - stardate is text with exactly two decimals (in steps of 0.05), from 43000.00 to 48999.95. Being fixed-width, it sorts correctly as text.
  - Stardate and lastUpdated are separate facts: neither is derived from the other. lastUpdated years are in-universe (2366 to 2368).
- **Source:**
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Mission model and cardinalities" (field table; "A commander does **not** have to appear in assignedCrewIds"; "Stardate and lastUpdated serve different purposes");
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Lexical values" (stardate pattern);
  - `package/uss-enterprise/missions/contracts/missions-v1.1.xsd` lines 221–241;
  - live: reviewer R1 `m-planned-all` and `m-cancelled-all`.
- **How sure:** certain.
- **What correct text would say:** the list above, in a few lines.

### C3. What each mission status means, and that Missions does not enforce transitions

- **Where:** "Missions". The guide lists no statuses and says nothing of their meaning.
- **What is missing:**
  - PLANNED is proposed. AUTHORIZED is approved. ACTIVE is under way. POSTPONED is approved work that has been deferred or suspended.
  - COMPLETED, FAILED and CANCELLED are distinct terminal outcomes.
  - CANCELLED may come before approval, and then need not have a commander.
  - Missions does not enforce which transitions are legal (there is no INVALID_STATUS_TRANSITION). States that the business process would not allow, such as PLANNED to POSTPONED, can therefore exist in the data.
- **Source:** `package/docs/MISSIONS-V1-DESIGN.md`, "Resource integrity and future process integrity".
- **How sure:** certain.
- **What correct text would say:** the meanings above, in one or two sentences, plus: "A history may show transitions the business process forbids; report them as recorded, and do not treat them as errors."

### C4. History entries that correct the data, not mission events (Missions dataset release 1.2)

- **Where:** "Missions", line 55 (history), and line 53 ("lastUpdated/changedAt are UTC update times").
- **What is missing:**
  - Release 1.2 reclassified the participants of 108 missions.
  - Each of those missions got one appended UPDATED entry: changeIds 9906248 to 9906355, at one-minute intervals from 2368-12-23T09:00:00.000Z.
  - Each such entry is performed by C-85 and ordered by C-78. It has previousStatus equal to newStatus and cost changes of 0.00. Its summary begins "Records clean-up: participants reclassified".
  - The mission's lastUpdated is the time of that correction.
  - These entries record data administration, not something that happened in the mission. A reader that counts changes, or dates a mission's last activity, from history or lastUpdated will be wrong for those 108 missions.
- **Source:**
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Release 1.2: the participants reclassified (2026-10-19)", **Append rule** and **Composition**;
  - `package/uss-enterprise/missions/README.md`, "Release 1.2: the participants reclassified";
  - live: reviewer R1 `m-history-correction-entry` (changeId 9906248, 2368-12-23T09:00:00.000Z, C-85/C-78, POSTPONED→POSTPONED, "Records clean-up: participants reclassified under the P and O definitions …");
  - live: author R2 `mission-detail` (lastUpdated 2368-12-23T09:00:00.000Z on the same mission).
- **How sure:** certain.
- **What correct text would say:** "Missions whose participants were reclassified carry a final UPDATED entry dated 2368-12-23, by C-85 and ordered by C-78, with unchanged status and 0.00 cost changes, and a summary beginning 'Records clean-up: participants reclassified'. Their lastUpdated is that time. Leave these entries out when you count or date mission events, and say so."

### C5. Order of history across missions

- **Where:** "Missions", line 55: "History orders by numeric changeId, not timestamp."
- **What is missing:** within one mission, changeId order is chronological. Across missions it is not. Entries added in dataset release 1.1 got changeIds after all those of release 1.0, so a newer changeId can carry an older changedAt. Timestamps may tie. To put events of several missions in time order, use changedAt and accept ties. Do not use changeId.
- **Source:**
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Release 1.1: a larger appended release", **Append rule** ("A new entry can therefore be older than a carried one; each mission's own history is chronological");
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Audit / change log" ("Timestamp ties are permitted").
- **How sure:** certain of the rule. I did not look for a live pair of entries that shows it.
- **What correct text would say:** the sentences above.

### C6. Personnel rank and department values

- **Where:** "Personnel", lines 33 and 37. The guide names the department filter and the rank and department fields, but gives their values only for clearance and duty status.
- **What is missing:**
  - Rank: CAPTAIN, COMMANDER, LIEUTENANT_COMMANDER, LIEUTENANT, ENSIGN, CHIEF_PETTY_OFFICER, CREWMAN.
  - Department: COMMAND, OPERATIONS, ENGINEERING, SCIENCE, MEDICAL, SECURITY, FLIGHT_OPERATIONS.
  - Both are exact and case-sensitive. A wrong token is an InvalidRequest fault.
- **Source:**
  - `package/uss-enterprise/personnel-v2/contracts/personnel-v2.xsd` lines 35–54;
  - `package/docs/PERSONNEL-V2.md`, "Model and ownership".
- **How sure:** certain.
- **What correct text would say:** the two lists.

### C7. The reporting graph, and where some Personnel facts come from

- **Where:** "Personnel", line 37 ("Omitted supervisor means none recorded; follow present PRS IDs directly").
- **What is missing:**
  - Get returns a member whatever its duty status.
  - A supervisor may be a civilian, inactive or in another department. There may be several people at the top. There are no cycles.
  - In personnel-v2-large-004, the 19 people migrated from the legacy roster as civilians carry no supervisor, because it was not carried over.
  - For the people migrated from the legacy roster, securityClearance was set by a rule from rank during migration, not recorded separately. The rule: CAPTAIN TOP_SECRET; COMMANDER and LIEUTENANT_COMMANDER SECRET; any other rank NONE; at least SECRET in SECURITY.
  - The reader needs this so that it neither reads a missing supervisor as a data error nor treats clearance as an independent fact.
- **Source:** `package/docs/PERSONNEL-V2.md`, "Model and ownership" (paragraph on supervisors), "Mechanical choices" ("Get includes all statuses"), and "Snapshots and runtime" (the paragraphs on personnel-v2-small-003 and personnel-v2-large-004).
- **How sure:** certain of the source. Medium on how much of it the reader needs.
- **What correct text would say:** the points above, in two or three sentences.

### C8. How clearance relates to mission classification

- **Where:** the opening paragraph, line 3 ("rank, clearance … does not prove availability/authorization"), and "Personnel", line 37.
- **What is missing:**
  - The design states the intended relationship. UNCLASSIFIED: any clearance is sufficient. SECRET: SECRET or TOP_SECRET. TOP_SECRET: TOP_SECRET only.
  - It is future process policy. Missions does not check it, so assignments with insufficient clearance exist and are valid data.
  - Classification describes information, not access control.
  - Without this the reader has no stated basis for comparing a crew member's clearance with a mission's classification.
- **Source:**
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Personnel clearance relationship (original 2026-10-01 design)";
  - `package/docs/MISSIONS-V1-DESIGN.md`, "REST API and concurrency" ("Classification is metadata, not access control").
- **How sure:** certain of the source.
- **What correct text would say:** the table in one line, with "policy, not enforced; such assignments exist".

### C9. Which identifier each filter accepts, and how a wrong one fails

- **Where:**
  - "Missions", line 51;
  - "Assets", line 63 ("Unknown valid parent selects nothing");
  - "Assets", line 65.
- **What is missing:** a wrong kind of identifier is refused with 400, not answered with an empty result:
  - Missions `assignedAssetId` takes only the Missions-local grammar. A native asset ID such as AST-0004 is 400 INVALID_REQUEST.
  - A padded crew reference (C-085) is 400.
  - A P or O reference in `commandingOfficerId` is 400.
  - Assets `parentAssetId` with a Missions reference (EQ-64) is 400 INVALID_REQUEST. Only a well-formed native ID that names nothing gives an empty list.
  - Assets offsets and limits must be canonical: `offset=00` is 400.
  - The reader must translate references through the mapping in the right direction before filtering. It must not read a 400 as "no matches".
- **Source:**
  - live, reviewer R1: `m-filter-native-asset-id`, `m-filter-padded-crew-ref`, `m-filter-wrong-class-commander`, `a-parent-filter-missions-ref` and `a-offset-noncanonical` (all 400);
  - live, author R2: `assets-unlisted-parent-filter` (empty list);
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Ownership and identifiers";
  - `package/docs/ASSETS-V1-DESIGN.md`, "Contract 1.1: native identifiers and PATH_NOT_FOUND" ("so does every filter that names one").
- **How sure:** certain.
- **What correct text would say:** "Missions filters take Missions-local references (C-n, EQ-n and the like). Assets takes AST-nnnn. A reference in the wrong grammar is a 400, never an empty result; map it first."

### C10. What the mapping tables do and do not cover for the deployed data

- **Where:** "Mapping and incomplete joins", lines 71–84.
- **What is missing:**
  - In release 1.3, participants.json covers every P reference of the deployed Missions data. Its description says every P reference resolves, and that a P reference nobody places fails the build. So under 1.3 a P reference without an entry is a mismatch to report, not a routine "no mapping".
  - O references never have an entry (REFUSED_BY_CLASS).
  - crew.json in 1.2 and 1.3 was built from the crew of Missions release 1.1. Its UNMAPPED cases are C-2372, C-3423 and C-9938. Some crew references in Missions appear in no table at all.
  - assets.json maps only eight Missions references. Other asset references in the data (for example VS-12, seen in author R2 `missions-combined-filters`) have no entry.
  - One person can be reached by both a C and a P reference. PRS-0003 is the target of both C-4752 (crew.json) and P-1068 (participants.json).
- **Source:**
  - `package/federation/mapping-releases/1.3/participants.json`, `description` and `source`;
  - `package/federation/mapping-releases/1.3/crew.json`, `source` and `controlledCases.UNMAPPED`;
  - `package/federation/mapping-releases/1.3/assets.json`, `entries`;
  - `package/docs/MISSIONS-V1-DESIGN.md`, "Release 1.1", **Crew references** ("some references appear in no table at all");
  - live: author R2 `missions-combined-filters`.
- **How sure:** certain of the files. The VS-12 example is a single live sighting.
- **What correct text would say:** "Under 1.3 every P reference should have an entry, and a missing one is a mismatch to report. Many C and asset references have no entry. A person may have several references across classes (for example both a C and a P reference)."

### C11. What each asset status means

- **Where:** "Assets", line 61. The guide lists the statuses but not their meaning.
- **What is missing:**
  - ACTIVE and MAINTENANCE are assets in the fleet.
  - DECOMMISSIONED is a normal retirement.
  - DESTROYED is confirmed and final: the asset cannot return.
  - MISSING means the whereabouts are unknown: the asset can return to ACTIVE if found.
  - The record carries no date for any status.
- **Source:**
  - `package/uss-enterprise/assets/contracts/assets-v1.1.openapi.json`, `components.schemas.AssetStatus.description`;
  - `package/docs/ASSETS-V1-DESIGN.md`, "The asset record", **Status**.
- **How sure:** certain.
- **What correct text would say:** the sentence above.

## 4. Text that could go without losing anything the reader needs (size)

The guide is 11,909 bytes against a target of about 9 KB. The findings above add perhaps 1.5 to 2 KB. These cuts would more than pay for that:

1. Line 5, the second and third sentences (relay files, "deployment-specific").
2. Every evidence parenthesis that only proves a rule already stated:
   - "R1 Personnel 500 has `isError=false`" (line 15);
   - "R1 refused an extra header" (line 15);
   - "R1 contents match package bytes" (line 17);
   - "(R2)" (line 19);
   - "This exact R1 `personnel-civilian` envelope succeeded" (line 25): keep the envelope, drop the claim;
   - "R1 application/json returned 406, null contentType, empty body" (line 43): keep "406, no body";
   - "R1 size 2 returned totalCount=300" (line 45);
   - "(R2 commander C-85, assigned C-120/C-92)" (line 47);
   - "R2 returned unmapped C-2372/EQ-108 assignments successfully" (line 51);
   - "R2 returned deltas 0.00/2107.77" (line 55);
   - "R1 AST-0004 points to AST-0023; parentAssetId=AST-0023 returned that child" (line 59);
   - "R1 AST-0006/MISSING and AST-0025/DESTROYED returned 200" (line 61);
   - "R2: `{"items": [], …}`" (line 63);
   - "R1 EQ-64 returned 400" (line 65);
   - "R2 confirms PRS-3001/Alexander Rozhenko as civilian" (line 82);
   - "(R1 PRS-9999)" and "absent for R2's unknown rank filter" (line 88).
3. Line 65, "Contract 1.1 replaces historical 1.0 grammar, …": keep only "uppercase prefix (underscores allowed), hyphen, four or more digits".
4. Line 80, "Missions 1.0/1.1 used P for many outsiders; 1.2 reclassifies them." and "Old identity-design padded examples are illustrative, not mappings."
5. Line 39, "not the README's small-002 default", and line 78, "superseding the Missions README's earlier deployment statement".
6. Line 94, the restatement of what `calculate` does (operations, path syntax, `round` 0..12): the reader has the tool's own description. Keep the guidance: fetch all pages before counting, resolve mappings first, keep absent costs apart from zero, state exclusions.
7. Line 98, the whole "Limits" paragraph (see A3).
8. Line 21, the list of refused URL forms. Keep it only if the reader is not shown the sandbox section of the tool texts (see section 5).

## 5. What I could not check, and why

- **`calculate` and `ask_requester`.** Neither can be sent through the relay. I could not check how `calculate` reads XML text in a path: how it treats namespaces, whether it can reach the members inside a SOAP envelope, and its numeric precision. The guide's wording on `calculate` stays at the level of the tool description.
- **Truncation.** No response came near 200,000 characters. The largest I saw was 28,180 (reviewer R1 `m-cancelled-all`). A full Personnel page of 100 members is 20,538 (reviewer R1 `p-list-max-page`). I could not see the tool's behaviour when it truncates.
- **Failures.** Outages, the Personnel `slow` and `unavailable` profiles, and 500 answers from Missions and Assets were not observable. The deployments ran normally.
- **The two Missions release hashes.** I could not tell whether mapping release 1.3's `checkedAgainst` hash for Missions release 1.2 (`ed6a5d76…3664`, a "dataset release manifest") and the relay fingerprint's `releaseSha256` (`2c330ac2…7f66f`) name the same release. They may hash different artifacts. The Missions release files are not in this repository.
- **What the reader is shown.** I could not tell whether the reader sees the two "From the MCP servers' README" sections of `package/TOOLS.md` (lines 195–213) or only the tool descriptions and schemas. This affects A2 and size item 8.
- **Documents linked but missing.** These are linked from the sources but are not in this repository; I did not try to reconstruct them:
  - `docs/PERSONNEL-V2-VALIDATION.md`, `docs/FEDERATION-DESIGN.md`, `docs/FUTURE-SOA-BPM-REQUIREMENTS.md`, `docs/INTEGRATION-NOTES.md`, `docs/PLAN.md`, `docs/PROGRESS.md`;
  - the governance and decision files (`DECISIONS.md`, `CONSTRAINTS.md`, `CHECKPOINT-WORKFLOW.md`);
  - the Missions and Assets dataset releases and their provenance files;
  - `federation/personnel-mapping`.
- **The evidence records.** In `evidence/04-compare-real-vs-simulated-20261030T233054Z.json`, all 200 differences are still unclassified (every `affects` value is null), so I drew no conclusion from them. On the real side, `evidence/04-service-real-20261030T232712Z.json` agrees with the guide on every point it covers:
  - paging bounds;
  - 400, 404 and 406 codes;
  - bodyless 404 for unknown paths (including `/missions/` and `/`);
  - HEAD answered 405 with an `Allow` header.

  One exception: HEAD sent with `Accept: application/json` was answered 406, not 405 (`headProbes.accept-json`). This does not matter to a reader that uses only GET. The records also show that Missions sends an ETag header, which the tools do not pass to the reader (the guide says so on line 19).
