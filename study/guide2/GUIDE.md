# Integration guide

Personnel owns roster/reporting, Missions assignments/history, Assets containment. No service checks another's references. Assignment/status/rank does not establish availability or authorization.

## Calls and results

- SOAP: `http://127.0.0.1:8082/soap/personnel-v2`, soap_request, SOAP 1.1/text/xml.
- XML: `http://127.0.0.1:8083/missions`, http_request GET.
- JSON: `http://127.0.0.1:8084/assets`, http_request GET.

HTTP/SOAP: status, contentType, truncated, string body. Parse body; match XML namespace/local name, not prefix. HTTP errors are ordinary results; isError means tool refusal/unreachability, never empty data. No response headers/ETags, HTTP writes, GraphQL or general file reader. HEAD normally gives bodyless 405: use GET.

read_mapping_release(release="1.3") lists files; add file="manifest.json", "crew.json", "participants.json" or "assets.json". Mapping results: truncated/string content; parse JSON. Unknown releases/files error; include .json.

Allowed headers: Accept, Accept-Language, Content-Type, SOAPAction. URLs stay under configured bases; userinfo, fragments, backslashes, encoded dots/slashes, dot segments, double slashes refused. Redirects not followed. Cap 200,000 characters: truncated=true means reduce page/refetch, not count partial data. No detail/mapping slicing.

## Personnel

Namespace `urn:graphql-federation-lab:personnel:v2`; qualify elements in order. Example:

```xml
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:p="urn:graphql-federation-lab:personnel:v2"><s:Body><p:GetPersonnelMemberRequest><p:personnelId>PRS-0003</p:personnelId></p:GetPersonnelMemberRequest></s:Body></s:Envelope>
```

soap_action: namespace + :GetPersonnelMember, or omit. List: ListPersonnelMembersRequest / :ListPersonnelMembers. Get body + List action returns 500 Server/InternalError: check mismatch before declaring outage; retry once correctly or without action.

Get takes personnelId, includes all statuses. List: optional department, dutyStatus, offset, limit, in order. Omit unused fields; empty/nil invalid. Offset 0..2147483647/default 0; limit 1..100/default 20. AND filters; department excludes civilians. No name/rank/clearance/subtype filter. Exact case-sensitive tokens:

- department: COMMAND, OPERATIONS, ENGINEERING, SCIENCE, MEDICAL, SECURITY, FLIGHT_OPERATIONS.
- dutyStatus: ACTIVE, ON_LEAVE, INACTIVE, DECEASED; omitted means all.
- rank: CAPTAIN, COMMANDER, LIEUTENANT_COMMANDER, LIEUTENANT, ENSIGN, CHIEF_PETTY_OFFICER, CREWMAN.
- clearance: NONE, SECRET, TOP_SECRET.

SOAP Body has GetPersonnelMemberResponse: datasetVersion/personnelMember; ListPersonnelMembersResponse: datasetVersion, direct personnelMember children, totalCount, offset, limit, hasMore. personnelId ASC; advance offset by count while hasMore. Beyond-end empty success. Changed datasetVersion: discard pages, restart at 0.

Member: personnelId, displayName, positionTitle, dutyStatus, one crewDetails/civilianDetails. Crew: rank, department, securityClearance, optional supervisorPersonnelId. Guinan's `<civilianDetails/>` is valid. IDs PRS-0001..PRS-9999 preserve case/padding. An ID keeps the same person through a subtype change; the current subtype is not evidence of an earlier one.

Supervisor omitted = none recorded; follow PRS IDs. Civilian/inactive/cross-department supervisors and multiple roots valid; no cycles. Large-004's 19 migrated civilians lost supervisor fields. Migrated crew clearance derived from rank: CAPTAIN TOP_SECRET; COMMANDER/LIEUTENANT_COMMANDER SECRET; others NONE, SECURITY at least SECRET. Use returned values; they are not independent authorization evidence.

Faults: HTTP 500, detail code/message/optional field. Client/PersonnelNotFound = absent valid ID; Client/InvalidRequest = fix request; Server/ServiceUnavailable = failure; InternalError can mean action mismatch. Protocol failures need not have business detail.

## Missions

GET /missions, /missions/{missionId}, /missions/{missionId}/changes; namespace `urn:starfleet:missions:v1`. Accept absent/application/xml works; application/json gives bodyless 406.

missionList/changeList: page, pageSize, totalCount, totalPages, direct mission/change children. Defaults 1/20; page>=1, size 1..50. Fetch through totalPages with fixed filters. Zero matches: totalPages=0; beyond-end empty success. No snapshot: report changing totals/duplicates; deduplication cannot recover skips.

AND filters: type, classification, status, priority, issuingAuthority, commandingOfficerId, assignedCrewId, assignedAssetId, locationType. One value each; unknown/repeated parameters invalid. No participant/title/time/search/sort filter. Exact case-sensitive values:

| Field | Values |
| --- | --- |
| type | DIPLOMATIC, EXPLORATION, SCIENTIFIC, FIRST_CONTACT, MEDICAL, RESCUE, HUMANITARIAN, SECURITY, TACTICAL, TRANSPORT, MAINTENANCE |
| classification | UNCLASSIFIED, SECRET, TOP_SECRET |
| status | PLANNED proposed; AUTHORIZED approved; ACTIVE underway; POSTPONED approved work deferred/suspended; COMPLETED, FAILED, CANCELLED distinct terminal outcomes |
| locationType | PLANET, STARBASE, VESSEL, SECTOR, DEEP_SPACE, ENTERPRISE, OTHER |
| issuingAuthority | STARFLEET_COMMAND, ENTERPRISE_COMMAND, STARFLEET_MEDICAL, STARFLEET_SCIENCE, STARFLEET_SECURITY, FEDERATION_COUNCIL |
| priority | Send the digit 1–5 (1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL, 5 ROUTINE) |

Cancellation can precede approval. Transition legality is not enforced: report process-forbidden transitions as recorded.

Mission order: missionId, title, type, classification, status, priority, stardate, durationHours, objective, location, issuingAuthority, commandingOfficerId, assignedCrewIds, participantIds, assignedAssetIds, estimatedCostCredits, actualCostCredits, outcome, lastUpdated. Commander optional in PLANNED/CANCELLED, required otherwise; need not be assigned. Location: type/name, optional opaque coordinates/travelVector.

Sort stardate/priority/missionId ASC. IDs `ST-[A-Z0-9]{9}` are opaque. Stardate: two decimals, 43000.00..48999.95, step 0.05; no Earth-date conversion. durationHours: integer 1..8760. lastUpdated/changedAt are UTC update times, independent of stardate.

C/P/O suffixes: unpadded positive decimals. C: commander, assignedCrewIds/crewId, changedBy/orderedBy; P/O: participantIds/participantId; assets: assignedAssetIds/assetId. Empty containers persist; lexical order (C-120 before C-92). Assignment filters test membership: crew/commander require C-n; assets local refs like EQ-64. AST-0004, C-085 or P/O commander filters give 400, not no matches: map first.

Costs: two decimals, absent ≠ 0.00. Estimate required except PLANNED/eligible PLANNED-origin CANCELLED. Actual required for COMPLETED/FAILED/CANCELLED, absent otherwise. Terminal outcome optional; no-estimate cancellation may have actual 0.00.

History sorts numeric changeId. CREATED/UPDATED: changedAt, changedBy (performer), orderedBy (orderer), newStatus, summary; UPDATED adds previousStatus even unchanged. Costs are balances; deltas need prior/resulting values. No full objective snapshots or authority proof. Across missions, older events may have larger IDs: sort changedAt, allowing ties; use changeId for per-mission mutation order.

108 missions have final participant-correction UPDATED entries dated 2368-12-23, by C-85/ordered C-78, unchanged status, zero deltas for present costs. Summary starts `Records clean-up: participants reclassified`; lastUpdated is correction time. Exclude from operational-event counts/dates (disclose); retain for audit counts.

Clearance policy: UNCLASSIFIED any; SECRET needs SECRET/TOP_SECRET; TOP_SECRET needs TOP_SECRET. Not enforced: assignments with insufficient clearance can be valid stored data. Classification is metadata, not access control.

400 INVALID_REQUEST: bad query; INVALID_MISSION_ID: bad ID. 404 MISSION_NOT_FOUND: valid ID absent; unknown path: bodyless 404. 500 INTERNAL_ERROR: backend failure, not absence.

## Assets

GET /assets or /assets/{assetId}. Fields: assetId, kind, category, name, description, status, parentAssetId. Parent: required, null/existing VEHICLE ID; no cycles. Containment is not assignment/location history.

VEHICLE kinds: STARSHIP, SHUTTLE, ROVER, ARMORED_VEHICLE. EQUIPMENT: PHASER, TRICORDER, COMMUNICATOR, SCIENTIFIC_INSTRUMENT, MUSICAL_INSTRUMENT.

ACTIVE/MAINTENANCE in fleet; DECOMMISSIONED retired; DESTROYED confirmed/final; MISSING whereabouts unknown, can return to ACTIVE. All resolve: AST-0006/MISSING, AST-0025/DESTROYED return 200. No status dates.

AND filters kind/category/status/parentAssetId. Offset>=0/default 0; limit 1..50/default 20. Response items/offset/limit/total; advance by count to total. Order prefix text/numeric suffix; no snapshot. Unknown/repeated parameters or offset=00 give 400 INVALID_REQUEST. Accept ignored: JSON.

Native IDs: uppercase/underscore prefix, positive suffix padded to four digits below 10000. Prefix does not imply kind. parentAssetId=EQ-64 gives 400; valid nonexistent AST-0097 selects nothing. Beyond-end: `{"items": [], "offset": 32, "limit": 1, "total": 32}`.

400 INVALID_ASSET_ID means bad lookup ID. 404 ASSET_NOT_FOUND means target absent; PATH_NOT_FOUND means wrong path. 500 INTERNAL_ERROR means failure, not absence.

## Mapping and reasoning

Missions dataset 1.2 is given context, not exposed on the wire. Personnel reports personnel-v2-large-004. Use mapping 1.3, whose manifest checks both. Changed Personnel version/deployment context: flag possible mismatch and ask.

Read manifest/sections; use entries, not controlledCases; pin release. 1.0: assets only; 1.1: 10 crew; 1.2: 800 crew/2 participants; 1.3: 800/58. All map 8 assets. No temporal/"latest" API; never merge releases/infer historical identity.

C (crew) uses crew.json, P participants.json, assets assets.json. P means roster non-crew; O outsider, refused by class. Every deployed P should map under 1.3; missing entry means mismatch. C-2372/C-3423/C-9938 and assets EQ-108/VS-12 are unmapped examples. C/P never overrides Personnel subtype: C-4752 and P-1068 both map to PRS-0003. Invert explicit entries for reverse filters; never infer IDs from names/suffixes.

Preserve references; distinguish unmapped, O refused, target absent (EQ-97 → AST-0097), resolved MISSING/DESTROYED, lookup failure. Keep incomplete joins/report coverage; unmapped ≠ nonexistent. Commander/assignment/participation stay separate unless scope requires union.

Inspect status/SOAP codes; messages are not stable keys. Validation is fail-fast without universal precedence. Correct requests; bounded retries for transient failure; persistent unknowns are not zero.

Use calculate after fetching all needed pages/mappings. Distinguish assignments/people, balances/deltas, absent costs/zero; state exclusions/denominators. ask_requester clarifies scope, identity, roles, release or unknown handling, not missing facts. No cross-service snapshot/historical roster lookup.
