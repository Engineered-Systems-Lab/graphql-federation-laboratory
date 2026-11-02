# Wording proposal — author round 2

Scope: retain the round 1 closing-instruction replacements for E01, E03, E06 and E07, and add a duty-status qualification to E07 only. Every other character of the original questions, all mapping rules, schemas, identifiers, released data and answer keys remain unchanged. E01, E03 and E06 proposal entries remain byte for byte identical to round 1. The package itself is not edited.

All 69 manifest-listed files passed SHA-256 and size verification before use; packageSha256 also matched the canonical manifest without its packageSha256 field. The earlier generated keys-b.json is not listed in MANIFEST.json; for the explicitly requested comparison, its SHA-256 was checked against the previously recorded session value, 5e05e494fd61b31f1776991c892189c6f8da4f7296ce9d51fb5c1b19391fdb72.

Each answer below was independently recomputed from the released data and equals the corresponding main answer in study/corpus2/keys-b.json exactly. No answer or key change is proposed.

For the group inventories below, “known groups” means the distinct non-null values actually present in the relevant complete released dataset: asset statuses, Personnel departments, mission statuses, or Personnel ranks. Civilians without a department or rank do not create additional department or rank values. The zero-count rows are explanatory inventory only; they are not included in the proposed answers.

## E01

Old closing instruction: Give only the statuses that occur.

New closing instruction: Give the count per status, leaving out statuses with no such assets.

The existing question first asks for counts and defines the qualifying assets. The replacement is one instruction on the answer form: one count per status, explicitly excluding every status with no qualifying assets. “Such assets” refers to the selection already defined by the unchanged question. Listing an empty status at zero would contradict that instruction.

Derivation: Assets release 1.1, assets.json: select records whose parentAssetId equals AST-0029, then count by status. This includes 11 direct children and excludes indirect descendants.

| Known group | Qualifying count | In answer |
| --- | ---: | --- |
| ACTIVE | 10 | Yes |
| DECOMMISSIONED | 0 | No |
| DESTROYED | 0 | No |
| MAINTENANCE | 1 | Yes |
| MISSING | 0 | No |

Empty groups left out: DECOMMISSIONED, DESTROYED, MISSING.

Answer (exactly equal to the earlier main key):

```json
{
  "answerStatus": "ANSWERED",
  "statuses": [
    {
      "status": "ACTIVE",
      "count": 10
    },
    {
      "status": "MAINTENANCE",
      "count": 1
    }
  ]
}
```

## E03

Old closing instruction: Give only the departments that occur.

New closing instruction: Give the count per department, leaving out departments with no such people.

The existing question first asks for counts and defines the qualifying people. The replacement is one instruction on the answer form: one count per department, explicitly excluding every department with no qualifying people. “Such people” refers to the selection already defined by the unchanged question. Listing an empty department at zero would contradict that instruction.

Derivation: Missions release 1.2, release.json: select ST-00000LD9F, take the union of commandingOfficerId and assignedCrewIds, and exclude participants. Resolve those references through mapping release 1.3, crew.json, then join to all ten pages of Personnel snapshot personnel-v2-large-004. Count distinct Personnel identifiers by department. All 19 selected references resolve to 19 distinct people.

| Known group | Qualifying count | In answer |
| --- | ---: | --- |
| COMMAND | 1 | Yes |
| ENGINEERING | 0 | No |
| FLIGHT_OPERATIONS | 1 | Yes |
| MEDICAL | 1 | Yes |
| OPERATIONS | 1 | Yes |
| SCIENCE | 2 | Yes |
| SECURITY | 13 | Yes |

Empty groups left out: ENGINEERING.

Answer (exactly equal to the earlier main key):

```json
{
  "answerStatus": "ANSWERED",
  "departments": [
    {
      "department": "COMMAND",
      "count": 1
    },
    {
      "department": "FLIGHT_OPERATIONS",
      "count": 1
    },
    {
      "department": "MEDICAL",
      "count": 1
    },
    {
      "department": "OPERATIONS",
      "count": 1
    },
    {
      "department": "SCIENCE",
      "count": 2
    },
    {
      "department": "SECURITY",
      "count": 13
    }
  ]
}
```

## E06

Old closing instruction: Give only the statuses that occur.

New closing instruction: Give the count per status, leaving out statuses with no such missions.

The existing question first asks for counts and defines the qualifying missions. The replacement is one instruction on the answer form: one count per status, explicitly excluding every status with no qualifying missions. “Such missions” refers to the selection already defined by the unchanged question. Listing an empty status at zero would contradict that instruction.

Derivation: Missions release 1.2, release.json: select issuingAuthority STARFLEET_SCIENCE, then count by status. There are 66 qualifying missions.

| Known group | Qualifying count | In answer |
| --- | ---: | --- |
| ACTIVE | 6 | Yes |
| AUTHORIZED | 6 | Yes |
| CANCELLED | 4 | Yes |
| COMPLETED | 24 | Yes |
| FAILED | 8 | Yes |
| PLANNED | 11 | Yes |
| POSTPONED | 7 | Yes |

Empty groups left out: none; every recorded status has at least one qualifying mission.

Answer (exactly equal to the earlier main key):

```json
{
  "answerStatus": "ANSWERED",
  "statuses": [
    {
      "status": "ACTIVE",
      "count": 6
    },
    {
      "status": "AUTHORIZED",
      "count": 6
    },
    {
      "status": "CANCELLED",
      "count": 4
    },
    {
      "status": "COMPLETED",
      "count": 24
    },
    {
      "status": "FAILED",
      "count": 8
    },
    {
      "status": "PLANNED",
      "count": 11
    },
    {
      "status": "POSTPONED",
      "count": 7
    }
  ]
}
```

## E07

Old question (exactly as pool.json): How many members of the Science department hold each rank? Give only the ranks that occur.

New question (round 2): How many members of the Science department, regardless of their duty status, hold each rank? Give the count per rank, leaving out ranks with no such members.

Old closing instruction: Give only the ranks that occur.

New closing instruction: Give the count per rank, leaving out ranks with no such members.

The question now explicitly counts Science department members regardless of their duty status. ACTIVE, ON_LEAVE and INACTIVE members all count; an ACTIVE-only filter contradicts that qualification. The unchanged round 1 closing instruction requires one count per rank and excludes ranks with no such members. “Such members” therefore refers to every Science department member, whatever their duty status. Listing an empty rank at zero contradicts that instruction. There remains one question followed by one instruction on the answer form.

Derivation: Read all ten pages of Personnel snapshot personnel-v2-large-004, select crewDetails.department SCIENCE, then count by crewDetails.rank. There are 133 qualifying members, with no duty-status filter.

| Known group | Qualifying count | In answer |
| --- | ---: | --- |
| CAPTAIN | 0 | No |
| CHIEF_PETTY_OFFICER | 8 | Yes |
| COMMANDER | 0 | No |
| CREWMAN | 58 | Yes |
| ENSIGN | 35 | Yes |
| LIEUTENANT | 30 | Yes |
| LIEUTENANT_COMMANDER | 2 | Yes |

Empty groups left out: CAPTAIN, COMMANDER.

Duty-status check (all 133 selected members):

| Duty status | Count |
| --- | ---: |
| ACTIVE | 120 |
| INACTIVE | 6 |
| ON_LEAVE | 7 |

There are 13 non-ACTIVE members. Their inclusion is required by the revised wording and preserves the existing answer. For audit, the rank counts with and without that inclusion are:

| Rank | All duty statuses (answer) | ACTIVE only (excluded reading) |
| --- | ---: | ---: |
| CHIEF_PETTY_OFFICER | 8 | 7 |
| CREWMAN | 58 | 52 |
| ENSIGN | 35 | 32 |
| LIEUTENANT | 30 | 27 |
| LIEUTENANT_COMMANDER | 2 | 2 |

Exact changes from pool.json: insert `, regardless of their duty status,` immediately after `Science department`; replace `Give only the ranks that occur.` with `Give the count per rank, leaving out ranks with no such members.` No other character changes.

Answer (exactly equal to round 1 and the earlier main key):

```json
{
  "answerStatus": "ANSWERED",
  "ranks": [
    {
      "rank": "CHIEF_PETTY_OFFICER",
      "count": 8
    },
    {
      "rank": "CREWMAN",
      "count": 58
    },
    {
      "rank": "ENSIGN",
      "count": 35
    },
    {
      "rank": "LIEUTENANT",
      "count": 30
    },
    {
      "rank": "LIEUTENANT_COMMANDER",
      "count": 2
    }
  ]
}
```

## Validation and uncertainty

The uncommitted standard-library check verified round 2 and exactly E01, E03, E06 and E07 in that order; every oldQuestion equals pool.json character for character; E01, E03 and E06 entries are byte for byte identical to round 1; and E07 differs from pool.json only by the documented duty-status insertion and the retained closing-instruction replacement. Every answer passes the unchanged task schema and equals both round 1 and the earlier main key. E07 was independently recounted from all ten verified Personnel pages: 133 members, including 13 with non-ACTIVE duty status. All checks passed.

No unresolved wording or data uncertainty remains in this proposal. E06 retains every known mission status because none is empty in its selected subset; the new exclusion rule is explicit even though it removes no group for this task.
