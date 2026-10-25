# Retrospective: the governed checkpoint infrastructure

Date: 2026-10-25T12:19Z
Subject: A retrospective of the lab's governed checkpoint preparation and its automation, committed on 2026-10-01, and of the framework decisions that extended it afterwards
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). Nothing was run again for it.

## What changed

On 2026-10-01 the lab committed its governed checkpoint preparation and the tool that automates it in one transition, lab commit `641647e983e042017b9f9dd02ad0162bf44aeaa0` ([the migrated entry](2026-10-01T1414Z-governed-checkpoint-infrastructure.md)). It came with [G018](../governance/DECISIONS.md#g018---delegated-checkpoint-authority-and-continuity-2026-10-01-accepted), dated the same day. From then on the lab's changes had a fixed shape:

- **The lead developer owns the scope and the commit.** A worker prepares only what the lead developer authorized, and the lead developer approves the full exact commit message and the exact sealed transaction before anything is committed.
- **Tools prove mechanical facts and never infer authorization.** The standard-library checkpoint tool stages selectively from an empty index, checks that the staged paths match an explicit manifest, runs and captures the checks, seals the transaction locally, records the approval, and verifies the commit (parent, tree and exact message) afterwards. A changed fact after the seal makes the approval void, and only a new preparation and a new approval go on.
- **A runtime commit is not finished when it is committed.** The workflow defined the phase "checkpoint committed; continuity follow-up pending": the commit exists, but Progress and its devlog entry still name the previous checkpoint, and the continuity check fails until a separately approved record transaction lands. Pending is never reported as PASS.

## Why it mattered

It made the lab's history checkable. Each runtime entry of this devlog from the Personnel dataset 003 release of 2026-10-01 onwards records its continuity follow-up, and the runtime entries of the federation work (from 2026-10-16) also say how the lead developer's go or Approve was given, and most of them list the checks of their seal. That record is the material the other retrospectives of this day are written from.

## What was measured, and the limits

The migrated entry keeps the contemporary report: 41 checkpoint tests and 17 continuity tests (58 in all), three targeted path and commit checks after a guard for Windows reserved paths, continuity validation, and the component's offline evidence (71 schema and security checks, 300 nil probes, 67 scalar probes, 26 structure, readiness and protocol cases and 20 semantic exchanges). Line-ending failures of fixtures and a misplaced test call were corrected before the passing results were reported. The Java, Docker and SOAP checks were not run again for this tooling work. The fresh-worker devlog step and reviewed runtime profiles were left for later, and the first tooling profile refused runtime scope. No runtime acceptance came from this checkpoint.

## What followed

The framework's decision register records how the rules grew from there, each as a dated decision:

- G018 itself was extended: the deterministic approve or reject decision (2026-10-05), its equivalence whether the decision is selected or typed (2026-10-05), the review before the seal (2026-10-08), the approval words (2026-10-10, and [G040](../governance/DECISIONS.md#g040---approval-words-2026-10-16-accepted) on 2026-10-16), the early conditional approval (2026-10-10) and the diff-bound approval that survives a moved main (2026-10-14).
- Beside it came [G023](../governance/DECISIONS.md#g023---validation-scope-2026-10-03-accepted) (validation scope must match change scope), [G025](../governance/DECISIONS.md#g025---transaction-owned-git-worktrees-2026-10-03-accepted) (one worktree, index and branch per transaction), [G026](../governance/DECISIONS.md#g026---change-classification-and-validation-scope-2026-10-03-accepted) (change classification, later one table of every path) and [G031](../governance/DECISIONS.md#g031---bounded-stale-base-reconciliation-2026-10-03-accepted) (bounded reconciliation of a stale base), all dated 2026-10-03.

Later context: the framework is now kept as Comitas, and this laboratory runs on its release 0.5.3 (commit `11c0bdefd5c968b522d0af8e2a46d64c877f9b3f`). Every commit of this repository went through the same workflow, except the seven set-up commits and the one history rewrite that D051 to D053 allowed; [the retrospective of the migration](2026-10-25T1223Z-retrospective-migration-into-the-laboratory.md) states them.

## Evidence

- [Governed checkpoint preparation and its automation are committed](2026-10-01T1414Z-governed-checkpoint-infrastructure.md), migrated from the lab, with its lab checkpoint lab commit `641647e983e042017b9f9dd02ad0162bf44aeaa0`.
- [G018](../governance/DECISIONS.md#g018---delegated-checkpoint-authority-and-continuity-2026-10-01-accepted) and its dated extensions, G023, G025, G026, G031 and G040 in the framework's [Decisions](../governance/DECISIONS.md).
- The [checkpoint workflow](../governance/CHECKPOINT-WORKFLOW.md) as it stands today.
