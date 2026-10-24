# Mapping release 1.2 maps Missions release 1.1 to the large Personnel snapshot

Date: 2026-10-19T14:18Z
Subject: Committed mapping release 1.2, which maps the 800 crew references and the participants of Missions dataset release 1.1 to personnel-v2-large-004 with the existing crew mapping process and refuses every O-reference by class, the third step of the data scale-up
Status: Historical / non-normative
Lab checkpoint: lab commit `60ac091090f41690097075851705a4c124036176`
Provenance: Git committer timestamp `2026-10-19T10:18:59-04:00` (2026-10-19 14:18:59 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the lead developer's words of 2026-10-18 (recorded verbatim in the Jobs `enterprise_scale_up` and `mapping_release_large`) or this later record preparation. The lead developer selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.292-1418Z; originally written in the lab on 2026-10-19 (lab commit `53ed1735821e835217f88c8f8f8fa94ea016a696`).

## Meaningful transition

Missions release 1.1 and the large Personnel snapshot now meet in a mapping release. Release 1.2 is a MINOR (the lead developer chose 1.2 over 2.0 in a dialog): the written rule lets a MINOR add entries and a section, the ten crew entries of release 1.1 keep their targets, and the checked-against list repeats the list of 1.1 and adds Missions dataset release 1.1 and `personnel-v2-large-004`. The commit is on the owned branch `tx/mapping-release-large`, parent lab commit `325d47493ea8f8d75818d377910877313dc9c3cf`, tree `47f9315`, 15 paths, +2615/-38. Exact subject: **Add mapping release 1.2: the 800 crew references and the participants of Missions release 1.1 mapped to the large Personnel v2 snapshot, with O-references refused by class**.

## Choices recorded

- **One process.** The existing crew mapping process builds both sections; its steps and the mapping exceptions tables are unchanged (the six rows of the table still resolve by exception, to the people the full names would give). The new inputs are pinned in their own file, as the large snapshot's were.
- **Classes first.** A reference is classified before any name is read. C goes to the crew section; P goes to the participants section and maps only to a non-crew person (the lead developer ruled that P must be allowed), by the participant exceptions table or an exact name; O is refused by class and no table can name one (the lead developer's ruling). A test feeds an O with a roster name and proves it refused.
- **The result.** 794 crew references by exact name and 6 by exception; 20 of the 800 reach people who are civilians in the roster (the 19 migrated civilians and Guinan). The three `unmappedCrew` (Ro Laren, Alyssa Ogawa, Hubbell) are not offered to the process and have no entry; the build fails if one of those names ever turns up in the roster. Of 118 P participants only Guinan (by name, the same person as her crew reference) and Alexander (by the one row of the participant exceptions table, which the lead developer approved in a dialog) are placed; Sarek, Perrin and Lwaxana Troi share a surname with roster people and stay unmapped. All 28 O-references, the returning Wesley Crusher O-860 among them, have no entry.
- **Two choices of the worker, reported.** A P whose only exact match is a crew member is a failure, not UNMAPPED, so that a human decides (it does not occur in the data); and two list assertions of the shared acceptance suite changed because the adapter now lists three releases, with no outcome re-derived.

## Retained evidence and limits

The seal ran the 12 checks of the federation profile, all passed, the Apollo gate with the lead developer's ELv2 acceptance for this Job. Before the seal, the mapping adapter gate passed (107 tests) on the second run: the first run failed on a broken string escape in the new Java test, which the worker fixed.

Limits: nothing in the graph resolves a participant (the `participants` section is loaded, hash-checked and listed, and nothing more); the stack default, the expected outcomes of the federation acceptance suite and the Missions adapter's own stub and tests still describe the earlier releases; the Personnel container SOAP gate does not cover the large snapshot. No benchmark, human acceptance or `frozen` mark is claimed.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
