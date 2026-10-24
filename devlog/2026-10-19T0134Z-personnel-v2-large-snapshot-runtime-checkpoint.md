# Personnel v2 gains the large snapshot of 1,000 people

Date: 2026-10-19T01:34Z
Subject: Committed the large Personnel v2 snapshot personnel-v2-large-004 (1,000 people: the 14 of personnel-v2-small-003, the other 787 people of the legacy crew release migrated by the federation process, and 199 generated civilians), the first step of the data scale-up
Status: Historical / non-normative
Lab checkpoint: lab commit `493d930d48983c12f1181616f04e735df4d8637c`
Provenance: Git committer timestamp `2026-10-18T21:34:46-04:00` (2026-10-19 01:34:46 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's words of 2026-10-18 (recorded verbatim in the Jobs `enterprise_scale_up` and `personnel_v2_large_snapshot`) or this later record preparation. The lead developer selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.292-0134Z; originally written in the lab on 2026-10-19 (lab commit `0797f59c53be460bb1ab5509c3dcba7fda9974cb`).

## Meaningful transition

The lab now has a Personnel v2 snapshot big enough to need paging. `personnel-v2-large-004` holds 1,000 people: the 14 records of `personnel-v2-small-003` byte for byte, the other 787 people of `crew-v1-large-003`, and 199 civilians (PRS-3001 to PRS-3199). The v2 contract (XSD, WSDL, paging rules) is unchanged; the default stays `personnel-v2-small-002` and the federation stack stays on `personnel-v2-small-003`. The commit is on the owned branch `tx/personnel-v2-large-snapshot`, parent lab commit `4a2b0b9b19e0f0610f420c46f1a914ceead0affa`, tree `3733b48`, 25 paths, +2069/-37. Exact subject: **Add the large Personnel v2 snapshot: all 800 people of the legacy crew release migrated by the federation process, plus 199 generated civilians**.

## Choices recorded

- **A paged package.** The contract returns at most 100 members per response, so 1,000 people cannot be one file. The snapshot is ten pages of the unchanged contract plus `manifest.json`. `Dataset.java` pins the raw bytes of the manifest and of every page; startup checks each page's paging fields, one strictly increasing id order across all pages, the count, unique ids and the reporting graph over the whole snapshot. The loader is the new `DatasetPackage.java`.
- **The existing process, in batch.** The `large` command of `crew_mapping.py` runs steps 2 and 3 of the existing process for each of the 800 people (the exceptions tables are about Missions references and take no part). 13 people were in Personnel v2 by exact name and keep their v2 id and record; 787 are migrated with the v1 number kept. Where v1 and v2 differ, v2 wins (Data is OPERATIONS in v2, SCIENCE in v1). The pins of the batch are in the new `large-pins.json`, so the pins of mapping release 1.1 stay as they are.
- **Civilians.** `civilians.py` generates 199 people from a fixed seed by SHA-256 order, standard library only: four inspired by the series (Alexander Rozhenko, Keiko O'Brien, Molly O'Brien, Mot; a name and a title, no episode facts, not checked against Memory Alpha) and generated families, residents and staff with invented names. The manifest records the seed, the algorithm and the hash of the generator. With the 20 civilians from v1 the snapshot has 219 civilians.
- **Civilian supervisors.** The Job allowed civilians with a supervisor, but the v2 civilian record is empty by contract, so none can have one; the 19 migrated v1 civilians lose the supervisor they had in v1.
- **Total of exactly 1,000.** 199 (not 200) generated civilians were chosen so that the snapshot holds exactly the 1,000 people aboard that the lead developer asked for.

## Retained evidence and limits

The seal ran 19 check entries, all passed: staged whitespace, continuity, the Mission Control generator, the runtime governance tests, the Personnel v2 offline validator, Maven clean verify for v1 and v2 (`runtime-java`, 66.2 s; the v2 module has 51 tests, 12 of them new), the container build (`runtime-container`), the container SOAP gate (`runtime-soap`), and the ten federation gates including `federation-router-apollo-stack` (286.8 s) and `federation-router-cosmo-stack` (315.6 s). The new `test_large_snapshot.py` has 13 tests: all 800 people re-derived by hand from the released files, the controlled failures (two matches, a taken number, a changed pin, no overwrite), byte reproducibility and the civilians. The Apollo gate ran with `APOLLO_ELV2_LICENSE=accept` from the lead developer's environment.

Limits: the container SOAP gate was not extended to the large snapshot (it would need about 1,000 calls at limit 1); the Java HTTP tests and the offline validator cover it. Missions, the mapping release and the acceptance outcomes were not touched; switching the stack to this snapshot is a later step of the scale-up. No benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
