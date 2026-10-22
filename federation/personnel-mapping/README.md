# Federation crew mapping

The process that maps the crew references of Missions (`C-n`) to Personnel v2 identifiers (`PRS-nnnn`), and the tables and pins it stands on. It belongs to the federation layer, not to a legacy system: it reads the legacy datasets as released files and shares no code or identifier with them. One script, [crew_mapping.py](crew_mapping.py), serves both the **migration** of the cast into Personnel v2 and the **build** of the crew section of the mapping release, so the two cannot disagree. The design is the crew mapping talk recorded in the Job `federation_design` (2026-10-16); the release it feeds is described in the [mapping adapter](../adapters/mapping/README.md).

## The process

For each Missions crew reference of the Missions recipe (`uss-enterprise/missions/datasets/recipe.json`, `references.crew`, the source of truth for the Missions side):

1. **The mapping exceptions table** ([mapping-exceptions.json](mapping-exceptions.json), `C-n` to `PRS-nnnn`). Every target must exist in the pinned Personnel v2 snapshot, and the table never names v1. A match stops the process.
2. **An exact name match in the pinned Personnel v2 snapshot.** Found: stop. The match is exact (no case folding, no trimming, no partial match).
3. **An exact name match in the pinned v1 release** (`crew-v1-large-003`), or the **migration exceptions table** ([migration-exceptions.json](migration-exceptions.json), `C-n` to `CRW-nnnn`, used only here, and it wins over a name): that person **must be migrated** to Personnel v2.
4. Otherwise the process fails and reports.

More than one match is a failure that reports every match, never a pick. The same process builds the table in two modes: *live* never runs step 3 and ends an unplaced reference in UNMAPPED; the *static* build (the release) fails on an unplaced reference and on a reference that still needs a migration, and prints the report. All inputs are pinned by hash in [pins.json](pins.json) and the release repeats the pins in `crew.json`; a run refuses to start when one differs.

## The migration

`personnel-v2-small-003` is the migration output: the seven records of `personnel-v2-small-002` byte for byte, plus the people the process marks for migration, and nothing else (the other 790 people of the v1 release are not migrated). The Personnel v2 contract (XSD, WSDL) does not change, and the two released snapshots stay as they are.

- **Identifier.** A migrated person keeps the number of the v1 id: `CRW-1048` becomes `PRS-1048`. People already in v2 keep their ids and are not migrated (Picard stays `PRS-0001` and is a mapping exception; Data `PRS-0002` and Wesley `PRS-0714` match by name). A taken identifier is a failure.
- **Supervisors** are remapped to Personnel v2 identifiers: to a person migrated in the same run, or to a person found once by exact name in v2 (Picard). A supervisor that is neither is a failure; only the people the process marks are migrated.
- **Clearance** (v1 has none, v2 requires one): by rank, CAPTAIN `TOP_SECRET`, COMMANDER and LIEUTENANT_COMMANDER `SECRET`, every rank below `NONE`; department SECURITY at least `SECRET` (the lead developer's rulings of 2026-10-16: a minimum, so a security captain keeps `TOP_SECRET`).
- **Other fields** (name, title, department, duty status) are copied; a v1 civilian becomes a civilian record.
- **A pending exception.** After a migration the mapping exceptions of the migrated people name ids that the *source* snapshot does not hold yet. The migration accepts such an entry only when this very run migrates that person to exactly that id; the mapping build then checks every target against the target snapshot.
- **Result today:** William Riker `CRW-1048`, Geordi La Forge `CRW-1049`, Beverly Crusher `CRW-1053`, Deanna Troi `CRW-1054`, Reginald Barclay `CRW-1057`, Worf `CRW-1058` and Miles O'Brien `CRW-1100`. Riker, La Forge, Troi, Barclay and O'Brien do not match the recipe names exactly (the recipe writes Riker, La Forge, Troi, Barclay and O'Brien), so they have migration exceptions and, after the migration, mapping exceptions.

## The batch mode and the large snapshot

`personnel-v2-large-004` is the second migration output and the first one that takes the whole v1 release. `python -B federation/personnel-mapping/crew_mapping.py large` runs the same steps for every person of `crew-v1-large-003` instead of for the Missions references: step 2 (an exact name in the source snapshot `personnel-v2-small-003`: the person is in Personnel v2 already, the id and the v2 record stand, byte for byte) and step 3 (otherwise the person is migrated and keeps the number of the v1 id). The two exceptions tables are about the Missions references and take no part. The identifier, supervisor, clearance and field rules above apply unchanged, and the same failures too: more than one match (in v2 or in the v1 release) is reported and stops the run, and so does a migrated number that Personnel v2 holds. Result: 13 of the 800 people are in Personnel v2 already (Picard, Data, Guinan, Mara Venn, Elias Renn, Wesley Crusher and the seven migrated for 003), 787 are migrated, and the v2 record wins where it differs from v1 (Data is OPERATIONS in v2 and SCIENCE in v1). A v1 civilian becomes a civilian record, which holds no supervisor, so the supervisor of the 19 migrated v1 civilians is dropped.

The 199 civilians come from [civilians.py](civilians.py): four inspired by the television series (a name and a title only, no episode facts) and the rest generated families, residents and civilian staff with invented names, ids PRS-3001 to PRS-3199 (above the migrated numbers 1047 to 2785), by the order of a SHA-256 over a fixed seed, with the standard library only. Every name in the snapshot is unique, so the exact-name steps never see two matches.

The snapshot is a package, because the Personnel v2 contract returns at most 100 members per response: ten pages of the unchanged contract and `manifest.json` (the pinned inputs, the kept people, the civilians' seed and algorithm and the hash of `civilians.py`, and every page's hash). The inputs are pinned in [large-pins.json](large-pins.json), separately from [pins.json](pins.json), whose users (the mapping release 1.1) stay as they are. `large` compares the package on disk with what the batch builds and reports any difference; `large --write` writes it and refuses to overwrite an existing folder, because a published dataset never changes. The tests are `federation/adapters/mapping/validation/runtime/offline/test_large_snapshot.py`: the rules re-derived by hand for all 800 people, the controlled failures, and byte reproducibility.

## The mapping release 1.2 and the reference classes

`python -B federation/personnel-mapping/crew_mapping.py release-large` builds mapping release 1.2 from the same steps. Its inputs are pinned in [release-large-pins.json](release-large-pins.json): the recipe of Missions dataset release 1.1 (`uss-enterprise/missions/datasets/releases/1.1/recipe.json`), the legacy crew release, the manifest of `personnel-v2-large-004` (each page is checked against the hash the manifest holds) and the three exceptions tables. The crew section maps the 800 `references.crew` against the large snapshot, by the steps above in static mode (the two crew tables are unchanged, six rows still resolve by exception to the same people the names would). `references.unmappedCrew` (Ro Laren, Alyssa Ogawa, Hubbell) is **not offered** to the process: their outcome is no entry, and the build fails if one of those names turns up in the roster.

The process knows three classes of Missions-local reference, decided before any name is read:

- **C** is crew and goes to the crew section.
- **P** is a participant. It goes to the participants section and maps only to a **non-crew** person of the roster: by the [participant exceptions table](participant-exceptions.json) (`P-n` to `PRS-nnnn`, which wins) or by an exact name; more than one match is a failure that reports every match, a name that only a crew member holds is a failure (a participant exception decides it), and a P nobody places is UNMAPPED, with no entry.
- **O** is an outsider and is **refused by class**: the process never accepts an O-reference, whatever its name, and no table can name one. This protects the returning Wesley Crusher (O-860, a visitor of Season 5 who is the same human as the crew member PRS-0714) and every outsider who shares a name with someone on the roster.

`release-large --write` writes the folder and refuses to overwrite one, and `check-large` compares the folder on disk with what the process builds. The tests are `test_release_1_2.py` of the [mapping adapter](../adapters/mapping/README.md).

## The mapping release 1.3 and the strict participants

`python -B federation/personnel-mapping/crew_mapping.py release-13` builds mapping release 1.3 for **Missions dataset release 1.2**, which reclassified the participants by definition: **P** is an on-board non-crew person (Personnel) and **O** an outsider. The crew side and the assets are release 1.2's, byte for byte (the build fails if the crew section differs). The participants come from the `participants.json` of the Missions release (each reference with its class), pinned with the other inputs in [release-1-3-pins.json](release-1-3-pins.json). The participant step is the same, with one change: it runs in **strict** mode, because under the definitions every P must resolve. A P that is not placed by the exceptions table or by an exact name among the non-crew people is a **failure** that names the reference, not an UNMAPPED outcome; a name that only a crew member holds and more than one match remain failures; an O-reference is still refused by class and no table can name one. Result: 58 P-references resolved (57 by exact name, P-1003 by the exceptions table) and 153 O-references refused. `release-13 --write` writes the folder and refuses to overwrite one, and `check-13` compares the folder on disk with what the process builds. The tests are `test_release_1_3.py` of the [mapping adapter](../adapters/mapping/README.md).

The participant exceptions table is unchanged (it is pinned for release 1.2 too, and a published release never changes): its one entry, P-1003, was written when the Missions data held only the first name, and the full name now also matches the roster by exact name, so the entry decides nothing the name would not decide.

## Commands

From the repository root (nothing is written without `--write`):

```sh
python -B federation/personnel-mapping/crew_mapping.py check               # the pins, the migration and the mapping release 1.1
python -B federation/personnel-mapping/crew_mapping.py migrate             # compare; --write writes personnel-v2-small-003.xml
python -B federation/personnel-mapping/crew_mapping.py build-crew          # print the crew section
python -B federation/personnel-mapping/crew_mapping.py release --write     # write federation/mapping-releases/1.1
python -B federation/personnel-mapping/crew_mapping.py pins --write        # a deliberate re-pin of the inputs
python -B federation/personnel-mapping/crew_mapping.py large               # the batch: compare personnel-v2-large-004 with a fresh build
python -B federation/personnel-mapping/crew_mapping.py release-large       # print the files of mapping release 1.2; --write writes the folder
python -B federation/personnel-mapping/crew_mapping.py check-large         # the pins of release 1.2 and the folder against a fresh build
python -B federation/personnel-mapping/crew_mapping.py release-13          # print the files of mapping release 1.3 (strict participants); --write writes the folder
python -B federation/personnel-mapping/crew_mapping.py check-13            # the pins of release 1.3 and the folder against a fresh build
```

The tests are the mapping adapter gate (`federation/adapters/mapping/validation/runtime/offline/test_crew_mapping.py` and `test_release.py`); the Personnel v2 side is pinned in `Dataset.java` and checked by `uss-enterprise/personnel-v2/validation/validate.py` and the Java tests. The scripts need Python 3.13 or later and the standard library only. Nothing here ships in an image: only the output, `crew.json`, does.

## Limits

The table of release 1.1 is the ten references of the Missions recipe 1.0: no reference of that released Missions data is unmapped, so the UNMAPPED outcome is covered by small controlled inputs in the test and not by an entry of the release (a reference with no entry has no mapping). Question 6 of the demo questions (senior officers among the assigned crew) was not part of this work; the live crew path now exists and the question is answered and tested under the Apollo router (see the [Apollo router README](../routers/apollo/README.md)).
