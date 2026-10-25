# Retrospective: the migration of the lab into this laboratory

Date: 2026-10-25T12:23Z
Subject: A retrospective of how this repository was started from the governance template and received the lab's systems, federation layer, study, decisions, documents and devlog between 2026-10-22 and 2026-10-25, with the three exceptions to the checkpoint workflow that it needed
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of this repository's own history, from its commits and decisions listed at the end. The date is the time of writing; the commit times in the text are UTC. Nothing was run again for it.

## What changed

The lab was developed first in a private repository, which stays as its archive. This repository was started from the governance template and received the lab's content as it stood at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`, slice by slice, each checked before the next. The lab's Git history was not carried: its commits are cited as lab commits, never as commits of this repository.

## The steps

1. **The start, 2026-10-22.** Commit `8e5ad2e1372d4f75da9a47a89a5d20569258917e` exported the template at release 0.2.0 into a new repository and ran its adoption helper once; commit `3c0d19f1cb80016e3705711857798ec38f276880` wrote the laboratory's README, with its licenses and notices; commit `eca0b8b4977d55250dbd7dd5fb2d83401841d749` added the project overlay with the lab's component profiles and commands.
2. **Two template fixes, 2026-10-22.** The first import stopped on defects of the template, so it was upgraded to release 0.2.2 (commit `a9f7cb0e1e4c35ea86d59dc0af8fb029701824aa`) and 0.2.3 (commit `d99e64fec7373104963d1c2874e0fab699ba91b1`), which fixed them.
3. **Crew & Personnel v1, through the workflow, 2026-10-22.** Commit `bb1231475c7be41a3c33a28825249db91e889b29` imported it under temporary open rows with no boundary, to be frozen later.
4. **The six set-up imports, 2026-10-22 and 2026-10-23.** Personnel v2 (commit `7ff9121406f3f9dfa0221cfe1abbb770780eaa44`), Missions (commit `c29f73d72574d0a8c753b09d5c2615ecf98f89e0`), Assets (commit `23faf6932b1ab6f91f362effa829d51c540aeedf`), the service scripts (commit `e958c9554f5fe330285ee6c71a02ebff548b097d`), the federation layer (commit `94f7e34494876b2953ee099b1b2a7653f380d91d`) and the study (commit `3acf04447a5095316168959bafa21daa4180e6dc`), outside the checkpoint workflow under D051.
5. **The recovery chain, 2026-10-23.** Commit `e7853c93f4214f859c92ec85f71f8960c6290caf`, one more commit outside the workflow under D052, named the federation import as the implementation checkpoint ([its entry](2026-10-22T2342Z-recovery-chain-adopted.md)); commit `49ca89b7e119de096e7c8d21844b3cfd7ca09c50` then declared the fact in the reconstruction contract through the workflow, after the framework upgrade to Comitas release 0.3.1 (commit `5187f6fd58ba7a40cd00f7e31266a2b05ca48593`), whose preparation gate accepts the adopting change.
6. **The history rewrite, under D053**, before the documents were imported (step 9).
7. **The frozen sets, 2026-10-23 to 2026-10-25.** Commit `8224a5784dd7c6156f205e2949a1b00e14b6136d` froze 167 files (all of Crew & Personnel v1, the frozen Missions and Assets contracts and fixtures, and the study's tasks and expected answers) and declared the frozen fact; commit `dbeae079860877585a6b60758d9efeb665e0a08d` froze the study guide; commit `e7a8effff0cafc044f2e7c578f20e76a1b5d7654` froze the Crew & Personnel v1 specification. The frozen manifest holds 169 files.
8. **The validation scope, 2026-10-23 to 2026-10-25.** Commit `dbeae079860877585a6b60758d9efeb665e0a08d` split the one federation profile into eight component profiles, so a change to one adapter no longer runs every federation gate; commit `f15c08e57aa2210096d9810f08efcdaf8ac8ebec` mapped the cross-system dependencies of the gates as nine project impact invariants, which Comitas release 0.4.0 (commit `2c47271ca319319e804c3867dbd04241f8ecf233`) made possible; and commit `e7a8effff0cafc044f2e7c578f20e76a1b5d7654` declared 33 selector expectations that hold those choices. No profile dropped a gate.
9. **The records slice, 2026-10-24.** After Comitas release 0.5.0 (commit `0dfb47dca9b9fe7f59caf6bf0f2538bff38e16b3`) and the move of the service scripts under `uss-enterprise/scripts/` (commit `1dc6ae45c1c76c786f3f4122866fc06bb34bb5e9`), commit `ff7dbf7230c4858e05185ded925a7e46442e336d` imported the lab's decisions D001 to D049, their rationale, its project constraints, 12 documents and 49 devlog entries, and added D050 to D053. The lead developer's quoted words were restated as dated rulings; the original wording stays in the lab.
10. **Comitas release 0.5.3, 2026-10-25** (commit `11c0bdefd5c968b522d0af8e2a46d64c877f9b3f`, which includes 0.5.1 and 0.5.2).

## The three exceptions

Everything above went through the checkpoint workflow except these, each approved expressly by the lead developer and recorded as a decision:

- **[D051](../project-governance/DECISIONS.md#d051---a-narrowly-scoped-bootstrap-exception-for-importing-the-labs-code-content-2026-10-22-accepted), the six set-up imports.** The recovery chain could not be adopted before the repository's first runtime commit existed, so the lab's code came in as set-up commits outside the workflow. The exception was narrow: only the enumerated imports; before each, every check its profile would select, the runtime gates included, ran by hand on the exact staged tree and passed; the lead developer approved the exact tree and message; and the evidence is kept outside the repository. D051 records its endpoint as reached on 2026-10-22, a local date; the last import's commit time is 00:07 UTC on 2026-10-23.
- **[D052](../project-governance/DECISIONS.md#d052---one-set-up-commit-to-start-the-recovery-chain-2026-10-22-accepted), one more set-up commit.** The adoption was meant to be the first governed transaction, but the checkpoint tool could not prepare it: once the classification table has runtime rows, every prepare requires the `implementation_checkpoint` row to be committed already, and that row is what the adoption adds. So exactly one more commit was made outside the workflow, holding only the row, the devlog entry that anchors it and its index line, checked by hand the same way.
- **[D053](../project-governance/DECISIONS.md#d053---the-commit-identity-is-rewritten-once-to-hide-the-lead-developers-email-2026-10-23-accepted), the history rewritten once.** So that no commit carries the lead developer's personal email, the author and committer email of the 13 commits then on main, from the start to the D052 commit, became their no-reply address. Names, dates, messages and contents stayed the same, except that the D052 commit cites the new ids of the commits it names. The rewrite was verified in a throwaway clone and approved before main moved. Every id of those commits in this entry is the rewritten one; the table of old and new ids is kept outside the repository.

## Why it mattered

The lab's history had to stay true while its systems moved. Historical Truth held through each step: the migrated entries keep their original dates and say where they came from, the lab's commits are never presented as this repository's, and each exception is a decision with its reasons in the [rationale](../project-governance/RATIONALE.md#set-up-imports-d051-d053) rather than a silent shortcut.

## Limits

No service has been run in this repository since the import, and no manual acceptance is recorded here; the runtime state is the one the lab verified ([Progress](../docs/PROGRESS.md)). The evidence of the hand-run checks of D051 and D052 and the id table of D053 are outside the repository and are not verified by this entry.

## Evidence

- The commits named above, all on main, and their messages.
- D050 to D053 in the project's [Decisions](../project-governance/DECISIONS.md), and [the recovery-chain entry](2026-10-22T2342Z-recovery-chain-adopted.md).
- The [README](../README.md), section History and provenance.
