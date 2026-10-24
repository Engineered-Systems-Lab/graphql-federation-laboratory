# The Missions executable contract 1.0 is committed

Date: 2026-10-07T00:50Z
Subject: Committed Missions XSD 1.0, the rulings reached while drafting it, and the per-component runtime-gate policy
Status: Historical / non-normative
Lab checkpoint: lab commit `6e24dae9844c4f18fd76dc9ba1024e48295b27fa`
Provenance: Git committer timestamp `2026-10-06T20:50:32-04:00` (2026-10-07 00:50:32 UTC), converted to the prescribed UTC minute. This dates the runtime commit, not the earlier review conversation or this later record preparation. Transaction `8e482bfe7b8dce179411d30579552482` was approved by the lead developer's typed `APPROVE` against prepared digest `c87701e98997bc5616bc54a7845fb233f3899070e565126ce410447bb35457d4`.
Migrated from lab log SD-2026.280-0050Z; originally written in the lab on 2026-10-07 (lab commit `cb81b3fc46818caba0922e25d28d466fbdedc40b`).

## Meaningful transition

The Missions v1 design, frozen as documentation on October 6 by D027, D032, D033 and D034, now has an executable counterpart: contract version 1.0 of namespace `urn:starfleet:missions:v1`, committed as a runtime checkpoint on the owned branch `tx/20261006-missions-xsd-v1`. Parent: lab commit `4190e7299a83b4d10265467d921e25c2adbeceda`. Tree object: dcfa891e72d288b574c352c3b645d2fe3098d82d. Exact subject: **Add the executable Missions contract 1.0 and its runtime-gate policy**. At the time of this record the commit is not integrated into main.

What exists: the XSD, six illustrative valid fixtures (synthetic content, not dataset records) and an offline validator with several hundred accept/reject probes, under `uss-enterprise/missions`. What does not: a Missions service, a dataset, an Oracle schema, a contract freeze or any manual acceptance. Domain rules (status-dependent commander, outcome and cost rules, duplicate references, whitespace-only request text and the request-role presence of `missionId` and `lastUpdated`) stay outside the schema by design.

## Rulings reached while drafting

The lead developer settled six points the design left implicit, recorded as a D034 extension and in the design. Reasons below are as the lead developer gave them, not repository-derived.

- Because one `mission` element serves POST, PUT and responses, a request carrying a service-owned element it must omit, or omitting `missionId` on PUT, is 422. A reference of the wrong class or malformed grammar stays a grammar-level 400, as the design already said; the 422 row's "ineligible reference class" was clarified. A PUT `missionId` differing from the URI stays 409.
- The year of a timestamp is not constrained. The lead developer's reason: what is loaded into the system is the project's business, and the 2366 wording had been recorded as a design constraint when the intent concerned dataset content.
- The error `message` is 1 to 1000 code points, chosen as roughly double Personnel's 512, with stack traces explicitly excluded.
- The stored change `summary` must contain a non-whitespace character. The lead developer's reason: it is the only field that explains what a change was about, since the audit otherwise records only operation, status and cost movement.
- "Whitespace" is Java's `Character.isWhitespace` set, pinned as an explicit code-point list so a Unicode update cannot change the contract, with JDK 17 as the comparison baseline. The lead developer chose Java's definition over Personnel's XML-only one; Missions is an independent bounded context.
- The minimum supported Java for Missions is JDK 17. This narrows D034's "no runtime pin" only for that floor.

## Policy: a runtime path with its own gates

The lead developer ruled that Missions is a runtime path like Personnel, but that Personnel tests are not needed for Missions. Inspection showed the runtime lifecycle is driven by `runtime_paths` and the continuity validator's `RUNTIME` list, not by change category, and that the policy-global `runtime_checks` demanded Personnel's Java, container and SOAP gates from every runtime packet. The resolution: each runtime profile now declares the gates it owns, version 3 policy has no shared default, and a runtime path whose profile declares none is refused, so neither component inherits the other's gates. A manifest mixing both requires both sets. Historical sealed packets keep a legacy fallback to a policy-level list, which the shipped policy no longer defines.

The lead developer also stated the governing principle: run the tests that verify the modified system and no more; cross-system changes justify testing the affected systems. Applying it exposed one place this transaction was broader than needed: an edited test file with no impact mapping fell back to the broad profile, pulling in the largest regression family. It now maps to its own suite.

## Retained evidence and limits

Pre-commit checks, all exit 0: staged whitespace, continuity, `missions-offline`, `checkpoint-invariants` (74 tests), `checkpoint-selector` (39), `commit-metadata` (20), `checkpoint-evidence` (11), `checkpoint-reconcile` (18), `runtime-governance` (2) and `continuity-regressions` (26). No Personnel Java, container or SOAP gate was run, by design.

Limits and discoveries preserved as they occurred. Whitespace behavior was compared on JDK 8, 11, 21 and 26; JDK 17 was not installed locally, so its agreement is inferred from 11 and 21, which agree. JDK 8 differs by U+180E, which is why the set is pinned. The admitted interpreter lacked `lxml`, and the repository-pinned requirement was installed into it. The known `GIT_EDITOR=true` host quirk required unsetting that single variable for governed commands. The selection and gate logic were tested against the real policy; the checkpoint suites use fixture policies, so no end-to-end preparation existed before this transaction's own. An initial draft added a redundant select-time validation, removed once the existing check was found to cover it.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state, preserving the stale-checkpoint failure honestly until this separately delegated Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. [Plan](../docs/PLAN.md) still describes the contract as the next step and needs its own record transaction; it was outside the paths a pending runtime permits. The guarded `finish`, integration of the exact tip and removal of the owned worktree follow only after continuity passes. No push. Historical-record commits do not recursively require another devlog entry.
