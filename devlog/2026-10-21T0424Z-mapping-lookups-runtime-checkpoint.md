# The mapping adapter gains plain lookups for the adapters-only scenario

Date: 2026-10-21T04:24Z
Subject: Committed the plain lookup queries of the mapping adapter for asset and personnel references, kept out of the supergraph with @inaccessible, so that the agent study's adapters-only scenario can translate the Missions references
Status: Historical / non-normative
Lab checkpoint: lab commit `766c09d24cd85e41df2af44b641cb0c3d53ceb73`
Provenance: Git committer timestamp `2026-10-21T00:24:22-04:00` (2026-10-21 04:24:22 UTC), converted to the prescribed UTC minute. The lead developer decided on Gamma-prime in the Federation thread on 2026-10-21, to be fair to Gamma; in the worker session they chose the batch of at most 100 references, the participant references not resolved and the new code MAPPING_CLASS_REFUSED in a dialog, accepted the Cosmo difference below in a second dialog, and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.294-0424Z; originally written in the lab on 2026-10-21 (lab commit `ace5e4b020ed2cf66a298ff24918943f4fb7c990`).

## Meaningful transition

In study-1 the Gamma scenario (the four adapters, no router) could not translate a Missions-local reference to a system id: the translation lived only on the `AssetReference` and `PersonnelReference` entities, reachable only through `_entities`, which the study's adapters MCP server refuses in Gamma by design; 11 of the 16 scored tasks need it. The mapping adapter now has `Query.assetReferences(release, localRefs)` and `Query.personnelReferences(release, localRefs)`, which give the entity's answer for up to 100 references in one call, with the release always an argument. Both fields are `@inaccessible`, so the routers' graphs stay as study-1 measured them. The commit is on the owned branch `tx/20261021-gamma-prime-lookup`, parent lab commit `20610ada0cb3a05e2193f6ecd485e83d099fe879`, tree `6e7211a`.

## Choices recorded

- **Same code as the entities.** The lookups and `_entities` share one method; the entities call it with the class rule off, so the router path answers as before.
- **Classes.** The personnel lookup does not resolve a participant reference (P-n; the federation design's question 77 stays open) and refuses an outsider reference (O-n) by class (D048); both answer `NO_ENTRY` with the new errors entry `MAPPING_CLASS_REFUSED`, added to the shared code list.
- **The header comment.** graphql-java turns the schema file's header comment into the description of `type Query`, and `wgc` took a longer mapping header as Query's description; the header was kept at its old text.
- **Not done here:** no DECISIONS entry for the three rulings of the worker session (they are in the Job record), and no Delta or Epsilon re-run.

## Retained evidence and limits

The worker started each pinned router on a scratch port with the study-1 file and with the recomposed file and compared the full introspection answers. Apollo router v2.18.0: identical. Cosmo router 0.359.0: the same types, fields, arguments and enum values, but `wgc` 0.133.0 writes a separate client schema when `@inaccessible` is used and leaves the descriptions of the three `MappingOutcome` values out of it; accepted by the lead developer and recorded in the federation design's compatibility matrix. The seal ran 13 checks, all passed, about 20 minutes, among them the four adapter offline gates, the Assets and Personnel service gates and both routers' offline and stack gates with the lead developer's standing ELv2 acceptance. Every adapter image is rebuilt from the changed shared library; only the mapping adapter behaves differently.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes; the Gamma-prime run itself is started by the lead developer. No push.
