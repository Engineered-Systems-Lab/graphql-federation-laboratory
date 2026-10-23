# Guide to the Enterprise legacy systems

Three independent systems hold the facts, and a set of mapping releases links their identifiers. Read this before you call anything.

## Ground rules

- Each system owns its own facts and its own identifiers. None embeds another system's records, and none checks another system's references, so a reference in one can point at nothing in another.
- Identifiers are exact strings: no case folding, trimming or padding. A matching number or name in two systems proves nothing. Never turn a reference from one system into another system's identifier by its number or its name. The only bridge is a mapping release.
- Every answer is one of: found, not mapped, refused by class, mapped but not found, or the service was unavailable. Report which one. Never guess, fill a gap or substitute a near match.
- Lists are paged. A page is a part, so read every page you need and use the system's own total to know when you are done. Each system's default, maximum and ordering are below.

## Personnel v2 (SOAP, port 8082)

Endpoint `/soap/personnel-v2` (WSDL at `?wsdl`), namespace `urn:graphql-federation-lab:personnel:v2`, SOAP 1.1 document/literal. Two operations, with request and response elements named `<Operation>Request` and `<Operation>Response`:

- `GetPersonnelMember`: child `personnelId`. Returns `datasetVersion` and one `personnelMember`.
- `ListPersonnelMembers`: optional children `department`, `dutyStatus`, `offset` (default 0), `limit` (default 20, 1 to 100). Returns `datasetVersion`, up to 100 `personnelMember`, `totalCount`, `offset`, `limit` and `hasMore`. Order is `personnelId` ascending. Filters combine with AND.

A `personnelMember` has `personnelId` (`PRS-0001` to `PRS-9999`), `displayName`, `positionTitle`, `dutyStatus` (ACTIVE, ON_LEAVE, INACTIVE, DECEASED) and exactly one of two branches. `crewDetails` carries `rank`, `department`, `securityClearance` (NONE, SECRET, TOP_SECRET) and an optional `supervisorPersonnelId`. `civilianDetails` is empty. A `department` filter matches crew only, so a list without it includes civilians. A missing supervisor means none is recorded.

Faults: `PersonnelNotFound` for a well-formed id that names nobody (HTTP 500, SOAP Client), `InvalidRequest`, `ServiceUnavailable` and `InternalError`. A fault is an outcome, not an empty result.

Every response carries `datasetVersion`, an opaque identifier of an immutable snapshot. If it changes between pages, start again at offset 0. The large snapshot, `personnel-v2-large-004`, holds 1,000 people.

## Missions (REST/XML, port 8083)

Namespace `urn:starfleet:missions:v1`; the service answers `application/xml`. Read operations:

- `GET /missions`: filters `type`, `classification`, `status`, `priority`, `issuingAuthority`, `commandingOfficerId`, `assignedCrewId`, `assignedAssetId`, `locationType`, combined with AND, one value each. Paging `page` (from 1, default 1) and `pageSize` (1 to 50, default 20). Order is stardate, then priority, then `missionId`. Answer: `missionList` with `page`, `pageSize`, `totalCount`, `totalPages`, then `mission` members. A page past the end is empty, and zero matches give `totalPages` 0.
- `GET /missions/{missionId}`: one mission, with its ETag.
- `GET /missions/{missionId}/changes`: the mission's audit trail, same paging, ordered by `changeId`.

An unknown or repeated query parameter or a bad value is 400 `INVALID_REQUEST`, a malformed id 400 `INVALID_MISSION_ID`, an unknown mission 404 `MISSION_NOT_FOUND`. Error bodies are `<error><code/><message/></error>`. There is no participant filter and no free-text search: to find missions by anything else, page through the list and read the fields.

A `mission` has `missionId` (`ST-` and nine capitals or digits), `title`, `type`, `classification`, `status` (PLANNED, AUTHORIZED, ACTIVE, POSTPONED, COMPLETED, FAILED, CANCELLED), `priority` (1 most urgent to 5), `stardate`, `durationHours`, `objective`, `location` (`type`, `name`, optional `coordinates` and `travelVector`), `issuingAuthority`, optional `commandingOfficerId`, then three collections that are always present, possibly empty: `assignedCrewIds` (`crewId`), `participantIds` (`participantId`) and `assignedAssetIds` (`assetId`). Then the optional `estimatedCostCredits`, `actualCostCredits` and `outcome`, and `lastUpdated`. Collections are sorted as text, so `C-10` comes before `C-2`. The commander need not be among the assigned crew. A planned or cancelled mission may have no commander.

Missions references are local to Missions and carry a class by their letter:

- `C-n` is crew. Used for the commander, the assigned crew and in audit actors. Never a participant.
- `P-n` is a person who works on board and is not crew (a civilian on the Personnel roster).
- `O-n` is an outsider: anyone not on the ship's roster.
- `XX-n` with two to five capitals (for example an equipment, shuttle or vessel prefix) is an asset reference.

Participants are `P` or `O` only. The number after the letter means nothing outside Missions.

## Assets (REST/JSON, port 8084)

`GET /assets/{assetId}` and `GET /assets`; any other method is 405 and any other path is 404 `PATH_NOT_FOUND`. The service always answers JSON and holds no mission data.

- An asset has exactly `assetId` (native form `AST-0017`: capitals, a hyphen, at least four digits), `kind`, `category` (VEHICLE or EQUIPMENT, derived from the kind), `name`, `description`, `status` (ACTIVE, MAINTENANCE, DECOMMISSIONED, DESTROYED, MISSING) and `parentAssetId` (an asset id or null). DESTROYED and MISSING assets are still returned with that status.
- `GET /assets` filters `kind`, `category`, `status`, `parentAssetId` (one value each, ANDed), paging `offset` (default 0) and `limit` (1 to 50, default 20), ordered by `assetId`. Answer: `{items, offset, limit, total}`.
- Errors are `{code, message}`: 400 `INVALID_ASSET_ID` (a malformed id, and a Missions-style reference such as one with an equipment prefix is malformed here), 400 `INVALID_REQUEST`, 404 `ASSET_NOT_FOUND` (a well-formed id that names nothing), 404 `PATH_NOT_FOUND` (you built a wrong path), 405, 500.

## Mapping releases

A mapping release is a folder named by its version (`1.0` to `1.3`), immutable once published, with a `manifest.json` and up to three JSON files. Each file has an `entries` object from a Missions reference to the owner's identifier, which is the mapping; its other members only describe the file:

- `crew.json`: `C-n` to `PRS-nnnn` (Personnel).
- `participants.json`: `P-n` to `PRS-nnnn`. Present from release 1.2; only 1.3 matches the current P and O classes.
- `assets.json`: asset reference to `AST-nnnn`.

Name the release you used. Pick the one built for the Missions dataset in use; for the current data that is `1.3`. Earlier releases cover earlier data (release 1.1 holds only a handful of crew references) and are kept as they were. Do not mix sections of different releases without saying so.

To go from a Missions reference to a Personnel or Assets record:

1. Read the reference's class from its letter.
2. Look it up in the matching section's `entries`, exactly as written.
3. Found: query the owning system with the mapped identifier, and report the record.
4. Not in `entries`: the outcome is **unmapped**. Do not search by name, do not ask the owner, do not infer from the number.
5. An `O` reference is **refused by class**: it never has an entry, even when the name equals someone on the roster. Do not look for that person yourself.
6. Mapped but the owner says not found (`PersonnelNotFound`, `ASSET_NOT_FOUND`): **mapped but not found**, a dangling reference. This differs from unmapped.
7. A timeout, a 5xx, `ServiceUnavailable`, `InternalError`, a 400 or a `PATH_NOT_FOUND` is a failed lookup: report **unavailable** or the error. It is never "not found" and never "unmapped".

What the owner then tells you is its own fact: the mapping says who a reference is, and the record says what that person is. A mapped `C` reference can lead to a record with `civilianDetails`, and a person's duty status, clearance or supervisor is whatever Personnel returns now, not what Missions implies. Likewise a mission lists an asset whatever its status.

## Pitfalls

- Order and filters are the system's own: do not assume a filter that is not listed above, and do not sort a page yourself and call it the system's order.
- A total counts all matches before paging. A short page does not mean the end; compare with the total, `hasMore` or `totalPages`.
- The default page is 20 everywhere. The maximum is 100 for Personnel and 50 for Missions and Assets; ask for the maximum when you page through many records.
- Data is a live view of one dataset version. Do not combine counts taken from different versions.
- State your evidence: for each answer say which calls and which mapping entries it rests on.
