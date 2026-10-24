# Assets gains its kinds, a derived category and the parent rule

Date: 2026-10-15T14:06Z
Subject: Committed amendment of the Assets contract 1.0 before the freeze: the rover and armored vehicle kinds, the derived category with its filter, and the vehicle-only parent rule
Status: Historical / non-normative
Lab checkpoint: lab commit `dc73e9f40fe010e9f5a4c7331fb23008fedf1c6a`
Provenance: Git committer timestamp `2026-10-15T10:06:08-04:00` (2026-10-15 14:06:08 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the review talk that decided the content or this later record preparation. Transaction `9e9082d848e41817ee9dd45f29bb9e83` was approved by the lead developer's typed go at the preview (early conditional approval, receipt bound to prepared digest `be624e5d7ff5477130a39737b52dbb72b49e8c84d82f9712cd2191304e797cac`), which the tool accepted because the sealed result equalled the previewed candidate and every check passed.
Migrated from lab log SD-2026.288-1406Z; originally written in the lab on 2026-10-15 (lab commit `9a9002058a8fe7b0559e1e15fc984fe52d7133df`).

## Meaningful transition

The lead developer's review of the Assets contract answered the open points of the first slice and widened the model before any freeze. The commit is the second slice of the Assets service, on the owned branch `tx/assets-amendment`, parent lab commit `e55750b4360b5f769cc74d6c531ee5943f4f7133`, tree `0379b99`, 27 paths, +339/-42. Exact subject: **Add the rover and armored vehicle kinds, the derived category and the vehicle-only parent rule to the Assets contract**. At the time of this record the commit is not integrated into main. The contract stays version 1.0 and unfrozen, and was edited in place.

What changed: the kind enum is SHIP, SHUTTLE, ROVER, ARMORED_VEHICLE and EQUIPMENT, each with a one-line definition in the contract and in [the design document](../docs/ASSETS-V1-DESIGN.md); a required `category` member (VEHICLE or EQUIPMENT) is computed from the kind by one table, so the record has seven members; `GET /assets` has a `category` filter with the rules of the other enum filters; and only a VEHICLE can be a parent. Four valid examples were added (a rover, an armored vehicle, equipment aboard a rover and a list filtered by category, 18 valid in all) and three invalid ones were added (a category that disagrees with its kind, a missing category and the removed GROUND_VEHICLE kind, 13 invalid in all). The offline validator checks every record against the table, fails if a kind has no table row, and checks that the parents its own examples name are vehicles; it has 47 tests across its two modules.

## Decisions carried into the design

The lead developer's words are in the decision table of the design document, typos corrected as they asked and the corrections shown to them.

- "derived category it is, and ROVER." The category is derived and never stored apart from the kind.
- ARMORED_VEHICLE was chosen over the acronym AFV because the plain words need no description; the lead developer's definition is "Land-based vehicles built for active combat zones and mechanized warfare". GROUND_VEHICLE, first proposed, is not used. No STATION kind was added.
- The name VEHICLE for the category was the Coordinator's proposal; the lead developer did not object in two exchanges, and the design treats it as agreed unless they object at the review. The definitions of SHIP, SHUTTLE and EQUIPMENT are the worker's wording and were shown to them at the preview.
- The other review answers: offset and limit paging stays, the text bounds stay, a numbered decision follows (one entry, at the freeze) and the freeze waits.

## Retained evidence and limits

Pre-commit checks, all exit 0: staged whitespace, continuity (42.5 s), `assets-offline` (0.3 s) and `assets-offline-tests`; the profile was `assets-contract+governance`, with the design document the only governance path. The validator proves the contract is well-formed OpenAPI of the decided surface and that its examples, rejected fixtures and probes behave, including the category table; it does not establish service behavior, ordering, filtering, the `Allow` header, or any rule across records. An equipment used as a parent is not checkable by the contract, and no fixture shows it. The worker's wait for a clear execution window timed out because another mission held a window, and a shell pipe hid the failure, so the prepare ran anyway; the protected set was unaffected and the sealed result equalled the preview. No dataset, PostgreSQL schema, service, container, contract freeze or manual acceptance exists.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. The freeze, its numbered decision and the [Plan](../docs/PLAN.md) line that still calls Assets open belong to a later freeze records transaction. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
