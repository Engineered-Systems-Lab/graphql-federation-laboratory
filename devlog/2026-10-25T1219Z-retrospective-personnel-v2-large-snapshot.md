# Retrospective: the Personnel v2 large snapshot

Date: 2026-10-25T12:19Z
Subject: A retrospective of personnel-v2-large-004, the Personnel v2 snapshot of 1,000 people committed on 2026-10-19 as the first step of the data scale-up, and of what the federation layer later built on it
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). Nothing was run again for it.

## What changed

On 2026-10-19 at 01:34 UTC the lab committed `personnel-v2-large-004`, lab commit `493d930d48983c12f1181616f04e735df4d8637c` ([the migrated entry](2026-10-19T0134Z-personnel-v2-large-snapshot-runtime-checkpoint.md)). Until then the largest Personnel v2 snapshot, `personnel-v2-small-003`, held 14 people. The new one holds 1,000:

- the 14 records of `personnel-v2-small-003`, byte for byte;
- the other 787 people of the legacy crew release `crew-v1-large-003`, migrated by the batch mode of the existing federation crew mapping process (13 of the 800 people of that release were already in Personnel v2 by exact name and kept their v2 record, so the v2 record wins where the two differ);
- 199 generated civilians, `PRS-3001` to `PRS-3199`, made by a standard-library script from a fixed seed. Four are inspired by the television series, with no episode facts; the rest have invented names. 199 rather than 200, so that the total is exactly the 1,000 people the lead developer asked for.

The Personnel v2 contract did not change. Because it returns at most 100 members per response, the snapshot is a package: ten pages of the unchanged list response and a `manifest.json` with the pinned inputs, the seed, the algorithm and the hash of the generator. The service pins the raw bytes of the manifest and of every page, and at startup it checks each page's paging fields, one increasing identifier order across the pages, the count, unique identifiers and the reporting graph over the whole snapshot.

## Why it mattered

It was the first step of the [data scale-up](2026-10-25T1222Z-retrospective-data-scale-up.md). The lead developer wanted data that needs paging, so that the approaches compared later could show differences, and wanted Missions to use all the people that had been created ([the federation design](../docs/FEDERATION-DESIGN.md#the-data-scale-up)). With 14 people, one call returned everything.

One consequence was found, not decided: a Personnel v2 civilian record holds no reporting fields, so the 19 migrated v1 civilians lost the supervisor they had in v1.

## What was measured, and the limits

The seal ran 19 checks, all passed, among them the Personnel v2 offline validator, the Maven build of v1 and v2 (the v2 module with 51 tests, 12 of them new), the container build and SOAP gate, and the ten federation gates. The new `test_large_snapshot.py` has 13 tests: all 800 people derived again by hand from the released files, the controlled failures (two matches, a taken number, a changed pin, no overwrite), byte reproducibility and the civilians. The container SOAP gate did not cover the large snapshot at that time; Missions, the mapping and the acceptance outcomes were not touched in that commit.

## What followed

Later context, from the later entries:

- Mapping release 1.2 (2026-10-19, lab commit `60ac091090f41690097075851705a4c124036176`) mapped the 800 crew references of Missions release 1.1 to this snapshot; 20 of them reach people who are civilians in the roster.
- The stack moved to it on 2026-10-19 (lab commit `e68dbc0f06a1c41b31832a1a9e5b4f1193a9e025`), and the container SOAP gate was extended to it in the same commit (2,864 exchanges, the paged package compared page by page with the authoritative pages).
- Missions release 1.2 (2026-10-20, lab commit `1740ef3ca4cb484a66b12028366d56c9e776d22a`) makes every P reference name one civilian of this snapshot by exact display name.
- Abstraction ladder study 1 ran against the real Personnel v2 service serving this snapshot ([the study entry](2026-10-21T0242Z-agent-study-1-complete.md#later-context-2026-10-21-the-study-testbed)).

No benchmark, human acceptance or freeze of the snapshot is recorded. In this repository it arrived with the Personnel v2 import (commit `7ff9121406f3f9dfa0221cfe1abbb770780eaa44`) and has not been served again here.

## Evidence

- [Personnel v2 gains the large snapshot of 1,000 people](2026-10-19T0134Z-personnel-v2-large-snapshot-runtime-checkpoint.md), migrated from the lab, lab commit `493d930d48983c12f1181616f04e735df4d8637c`.
- [Personnel v2](../docs/PERSONNEL-V2.md), the section on the snapshots.
- [The federation crew mapping](../federation/personnel-mapping/README.md#the-batch-mode-and-the-large-snapshot), the batch mode and the large snapshot.
- The later entries named above.
