# The lab's systems, federation layer and study are in the repository, and the recovery chain is adopted

Date: 2026-10-22T23:42Z
Subject: The set-up imports of the lab and the adoption of the runtime recovery chain
Status: Historical / non-normative
Provenance: Written on 2026-10-22 when the recovery chain was adopted, after the imports it describes; dated by the committer time of the checkpoint commit (2026-10-22T23:42:29Z), as the devlog rule for the checkpoint entry requires. The facts come from the commits named below and their messages.
Repository checkpoint: `94f7e34494876b2953ee099b1b2a7653f380d91d`

## The transition

The laboratory's systems, its federation layer and the Abstraction ladder study are now in this repository, and the recovery chain guards its runtime history. Progress names the federation import as the implementation checkpoint: it is the latest commit that touched a path on the runtime boundary. The study import after it touched only `study/` and `project-governance/`, none of them on the runtime boundary. From the adoption on, every runtime commit enters the continuity-follow-up-pending phase of the checkpoint workflow until its Progress and devlog records land.

## The commits that brought them

- `bb1231475c7be41a3c33a28825249db91e889b29` imported Crew & Personnel v1 through the checkpoint workflow, under temporary open rows with no boundary.
- `7ff9121406f3f9dfa0221cfe1abbb770780eaa44` imported Personnel v2.
- `c29f73d72574d0a8c753b09d5c2615ecf98f89e0` imported Missions.
- `23faf6932b1ab6f91f362effa829d51c540aeedf` imported Assets.
- `e958c9554f5fe330285ee6c71a02ebff548b097d` imported the service scripts.
- `94f7e34494876b2953ee099b1b2a7653f380d91d` imported the federation layer; it is the implementation checkpoint.
- `3acf04447a5095316168959bafa21daa4180e6dc` imported the Abstraction ladder study.

The last six were set-up commits made outside the checkpoint workflow, under the lead developer's narrowly scoped bootstrap exception. Before each was approved, every check the workflow would have selected ran by hand on its exact tree and passed; that evidence is kept outside the repository.

## How the adoption landed

The adoption was meant to be the first governed transaction after those imports, in one change. Its worker found that the checkpoint tool cannot prepare it: once the classification table has runtime rows, every prepare requires the `implementation_checkpoint` row to be already committed in Progress, and that row is what the adoption adds. No transaction of any Job could be prepared until the row was on main. The lead developer therefore approved one more commit outside the workflow, holding only this entry, its index line and the Progress row, checked by hand like the set-up commits. The reconstruction contract's `implementation_checkpoint` fact and the rest of the adoption follow through the checkpoint workflow.

## Limits

- The bootstrap exception and its two decisions, D051 for the imports and D052 for this commit, are recorded with the project's decisions in a later Job, so this entry names them without linking to them.
- Until the contract declares the `implementation_checkpoint` fact, the continuity check does not yet compare the checkpoint with runtime history; the checkpoint tool already reads the committed row.
- Manual acceptance is not recorded.
