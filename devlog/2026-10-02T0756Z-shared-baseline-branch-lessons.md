# The shared baseline teaches branch ownership by content

Date: 2026-10-02T07:56Z
Subject: Semantic ownership and recovery-fixture correction before sibling feature work
Status: Historical / non-normative
Lab checkpoint: lab commit `f8b31eb05770d1f6ee59bfac0be0d2e88382b9b8`
Provenance: Local main reflog records the fast-forward at `2026-10-02 03:56:18 -0400` (07:56:18 UTC). This date is that of the promotion, not every preceding action. Commit objects establish content and ancestry; local branch reflogs establish branch operations and are not permanent Git history. Later context below was verified during record preparation on October 2.
Migrated from lab log SD-2026.275-0756Z; originally written in the lab on 2026-10-02 (lab commit `ab83cde13621bad2d24ab997eae3cc7c412895e3`).

## Shared checkpoint recovered

`feature/missions-v1` was created for Missions work from Personnel 003 runtime checkpoint lab commit `03abf8c17c1a78dec88885fdc77392577a2ade9a`. Its next two commits were shared Personnel/governance/continuity work, not Missions implementation or design: lab commit `cf114eb821e76a61cbc2311443681c2e2b466e6b` updated Personnel recovery status and indexed the release log; lab commit `f8b31eb05770d1f6ee59bfac0be0d2e88382b9b8` corrected a reconstruction test fixture. Their single-parent ancestry runs directly from 03abf8c through cf114eb to f8b31eb.

Actual Missions v1 design remained uncommitted, preserved in stash lab commit `a3e052f3b806b6a994b052babdc3be70b133b977`, based on cf114eb. Read-only inspection confirmed the Missions design and associated documentation remain recoverable there. The stash was not applied, popped or dropped during this preparation. No Missions work was lost.

Commit content and ancestry established semantic ownership despite the branch name. Main could therefore fast-forward from 03abf8c through f8b31eb, retaining the original commits without a merge commit, cherry-pick duplication, rebase or history rewrite. The local main reflog confirms that fast-forward.

## Discovery and later context

The reconstruction fixture in `validation/test_continuity.py` still expected old runtime checkpoint lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b` after Personnel recovery status advanced. Commit f8b31eb changed only that current expectation to lab commit `03abf8c17c1a78dec88885fdc77392577a2ade9a`; historical b77b23a references were preserved. Its recorded evidence reports continuity and all 17 continuity regressions passing, with full-profile limits from missing lxml and Python subprocess launch errors; those are historical results, not new executions by this log.

Earlier PLAN/PROGRESS working-tree or deferred wording was narration drift across completed checkpoints, not a circular implementation dependency. The Personnel runtime commit precedes its continuity record and fixture correction; the preserved Missions design is separate. No circular dependency was introduced. Current truth remains owned by [Progress](../docs/PROGRESS.md); this record neither revises design nor rewrites contemporary history.

Later preparation context: `feature/personnel-v2` was created at f8b31eb before this shared historical record was prepared. It had zero unique commits. Preparation returned to main while leaving both feature pointers at f8b31eb and the Missions stash intact. Promotion of this record and subsequent feature-branch advancement remain separate authorized actions.

## Lessons

- Branch purpose does not determine commit semantic ownership; inspect content and ancestry before moving branch points.
- Establish and promote shared governance/continuity checkpoints before sibling feature work.
- Validate recovery fixtures when runtime checkpoints advance, while preserving historical references.

Under [G018](../governance/DECISIONS.md#g018---delegated-checkpoint-authority-and-continuity-2026-10-01-accepted), this record-only transaction does not recursively require another devlog entry.
