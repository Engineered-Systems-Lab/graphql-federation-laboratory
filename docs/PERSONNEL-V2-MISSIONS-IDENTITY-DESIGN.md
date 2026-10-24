# Personnel v2 and Missions identity design

Status: design conclusions approved by the lead developer, 2026-10-02; documentation only. No executable contract, dataset release or runtime acceptance is established here.

Later implementation reconciliation (2026-10-02): [Personnel v2](PERSONNEL-V2.md) now specifies the lead developer's finalized PRS grammar, enums, common Get/List operations and executable mechanics; [validation evidence](PERSONNEL-V2-VALIDATION.md) distinguishes prepared work from acceptance. The original conclusions and then-open wording below remain dated provenance; Missions reconciliation remains pending.

## Authority and compatibility

This note records the lead developer's explicit instruction continuing the Data Improvement discussion. Current [Constraints](../project-governance/CONSTRAINTS.md), D014/D015/G018/G019 in [Decisions](../project-governance/DECISIONS.md), and the [checkpoint workflow](../governance/CHECKPOINT-WORKFLOW.md) apply. Personnel v1's [specification](CREW-PERSONNEL-V1.md), WSDL/XSD and immutable datasets remain unchanged. Future breaking wire changes require a new contract/namespace; new snapshot content requires a new dataset version. Do not retrofit these examples into historical snapshots.

No Personnel v2 specification or Missions specification exists in the inspected main checkout. The preserved `docs/MISSIONS-V1-DESIGN.md` at stash lab commit `a3e052f3b806b6a994b052babdc3be70b133b977` was inspected read-only. It describes C-only references and cites its own Missions G019 and SOA/BPM D020; those IDs conflict with current governance decisions. That preserved draft is not restored or silently revised here. This note records the newly approved identity direction; before executable Missions work, reconcile the preserved design and its references explicitly with current decisions. It does not reopen unrelated frozen design choices or adopt the draft wholesale.

## Personnel v2: identity survives classification

Use a stable parent `personnelId`, independent of subtype. Preserve the XML `xs:choice` direction: exactly one of `crewDetails` (CrewDetails) or `civilianDetails` (CivilianDetails) for a personnel record.

| Scope | Fields |
| --- | --- |
| Common parent | `personnelId`, `displayName`, `positionTitle`, `dutyStatus` |
| CrewDetails | `rank`, `department`, `securityClearance`, optional `supervisorPersonnelId` |
| CivilianDetails | Currently no required subtype-specific fields |

Do not require artificial rank, department or reporting facts for civilians. A subtype transition does not allocate a new Personnel identity. This note does not finalize ID grammar, XML namespace, operations, scalar types/enums or other unspecified wire rules.

Wesley Crusher is the canonical regression/example case: one Personnel identity survives a `CivilianDetails -> CrewDetails` transition between distinct snapshots. For illustration only, `PRS-0714` identifies Wesley in both snapshots; it is not a reserved key or approved ID grammar. The later classification does not modify the earlier immutable snapshot. This is a synthetic lab scenario, not a revision of Wesley's released v1 records or a claim about episode chronology.

## Missions: independent C/P/O references

Missions retains its independent C/P/O worldview. Its classification-dependent references need not have the same identity lifecycle as Personnel's stable parent key. The same Wesley may legitimately have historical `P-*` and later `C-*` references. Neither a prefix nor a matching numeric suffix proves correspondence with Personnel.

| Illustrative context | Missions reference | Explicit Personnel mapping |
| --- | --- | --- |
| Earlier Wesley reference | `P-0042` | `PRS-0714` |
| Later Wesley reference | `C-0197` | `PRS-0714` |

These are illustrative mappings, not released mapping entries. Under D015 the shared Integration & Benchmark layer owns mapping schema, versioned releases, validation and interpretation; mappings remain outside Personnel and individual adapters must follow shared rules. Preserve missing, ambiguous and dangling outcomes. Do not infer correspondence from names or string transformations.

Mapping design must account for historical context. Effective time and/or dataset/mapping-version semantics remain an explicit design question: specify them before implementing historical resolution, rather than assuming the latest classification applies to every mission. Do not treat dataset version labels as timestamps or evidence of freshness. Historical Missions references remain as recorded when Personnel later reclassifies Wesley. Many Missions references may explicitly map to one Personnel identity without either service being incorrect.

Subsequent Missions contract work must explicitly reconcile C/P/O with the preserved draft's C-only commander, assignment and audit-header rules; this note does not indiscriminately widen those fields or decide their eligibility rules.

## Missions-only background example

A subtle example is `O-0007`, labeled `Guest (Extra)` in Missions design/example context only. Other Entity means no ontology beyond what Missions knows: do not infer species, employment, crew/civilian status, Personnel membership or a Personnel mapping. The label is an Easter egg, not a new required wire field or a real biographical record. No Personnel record is created for the guest.

## Future regression expectations

- Two distinct Personnel v2 snapshots retain Wesley's same parent ID while selecting civilianDetails first and crewDetails later; each record has exactly one choice branch.
- Explicit historical P and later C mappings resolve to that same Personnel identity in their defined contexts; unmatched or ambiguous references are not guessed from suffixes or names.
- A later Personnel classification leaves earlier snapshots and historical Missions references unchanged.
- The guest O example remains Missions-only with no inferred ontology or Personnel identity.

These are design expectations, not executed runtime tests. Mapping temporal/version rules, complete v2 wire details and Missions field-specific C/P/O eligibility remain to be specified before implementation.
