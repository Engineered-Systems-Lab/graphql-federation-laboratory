# The Crew & Personnel executable contract is frozen

Date: 2026-09-30T18:00Z
Subject: Frozen SOAP contract, immutable datasets and executable offline validation checkpoint
Status: Historical / non-normative
Lab checkpoint: lab commit `9fdfba688094f3905997b345cfbdf44668c50bf3`
Provenance: Git author and committer timestamps both `2026-09-30T14:00:22-04:00`, equivalent to `2026-09-30T18:00:22Z`; seconds omitted from the date.
Migrated from lab log SD-2026.273-1800Z; originally written in the lab on 2026-10-01 (lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`).

## Meaningful state transition

Relative to the [16:54 design checkpoint](2026-09-30T1654Z-crew-personnel-design-dataset-001.md), this commit added the frozen WSDL/XSD, concrete six-record 001 and 12-record 002 snapshots, manifest, request/response/fault and negative fixtures, and PowerShell/Python offline validation. The contract had become executable and reviewable independently of a running Java service. The specification and Decisions now recorded freeze by user approval; the commit time establishes this repository state, not the exact moment of approval.

The [17:48 Dataset 002 and fixture review](2026-09-30T1748Z-crew-personnel-contract-dataset-fixture-review.md) preserves the detailed rationalization, reported check counts, replacement model and limitations. Those findings are not duplicated here. That report's time remains filesystem-only evidence; this commit does not authenticate its minute or independently prove every reported execution.

## Contemporary status preserved from Decisions

The following paragraph is preserved from the post-D014 status recorded in this commit and later carried under the historical freeze heading:

> Crew & Personnel Contract v1 is **FROZEN** by user approval. D014 and the pre-freeze discussion above are historical records. Executable XSD/WSDL, fixtures and offline checks now exist. The six-record 001 is immutable; 12-record 002 extends the dataset without changing the wire contract. Java/SOAP stack selection and runtime acceptance remain pending.

This status distinguishes immutable dataset growth from a breaking wire-contract change. It also records the then-pending Java stack and runtime acceptance. The committed component README and Progress described local schema/fixture and static WSDL checks, with the .NET supplementary-Unicode limitation; this checkpoint did not establish a running SOAP service.

## Evidence limits and later context

No separate committed state between 16:54 and 18:00 isolates first XSD/WSDL creation from Dataset 002 maturation. The report preserves the intermediate review without inventing another contract-freeze minute. Current uncommitted Java implementation, portability and governance work belongs to a future completed checkpoint; it is not retroactively part of this event.
