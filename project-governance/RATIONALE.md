# Why the project's decisions exist

Status: Explanatory / non-normative

This is the project's own rationale, beside the framework's [rationale](../governance/RATIONALE.md). It explains the decisions in [Decisions](DECISIONS.md) and decides nothing. Each decision gets one row in the audit table below and one section whose heading names it after a colon, for example `## Checkpoints: D001`; an entry states the decision in one line, then why (each reason labeled supplied by the lead developer, source-stated or agent-reasoned), the alternatives considered, the tradeoffs, the evidence and when to revisit it.

## Evidence audit

**Explicit** means a source states the reason. **Recoverable** means the explanation can be assembled from committed context without assigning an undocumented motive. **Inferred** means a plausible explanation is offered as inference, not historical intent. **Missing** means the inspected evidence records the choice but does not explain why it was preferred.

The rows and sections for D001 to D049 were carried from the lab's rationale (the lab path `governance/rationale/README.md`, at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`) for the decisions the project kept, with the statuses the lab's audit gave them: a reason it recorded as missing stays missing. Their dates of inspection and the commits they cite are the lab's.

| Decision | Rationale status | Finding / reading location |
| --- | --- | --- |
| D001 | explicit | A shared synthetic enterprise supports understandable, repeatable comparison; naming superseded by D009. |
| D002 | recoverable | Shared benchmark inputs isolate platform differences; see Fair comparisons. |
| D003 | missing | The three-platform scope is recorded; why these three rather than another set is not documented in the inspected sources. See Fair comparisons. |
| D004 | explicit | A seed alone does not establish reproducibility; see Repeatable data. |
| D005 | explicit | Incorrect responses must not count as performance wins; see Fair comparisons. |
| D006 | recoverable | Agent tasks and router measurements answer different questions; see Fair comparisons. |
| D008 | missing | The initial customer/order domain list is recorded without a comparative selection rationale; superseded by D010. |
| D009 | explicit | The Enterprise framing connects the portfolio to asking a messy enterprise "Computer..."; see Stable enterprise. |
| D010 | recoverable | Heterogeneous native systems establish the integration problem before adapters; see Stable enterprise. Exact technology-assignment rationale is missing. |
| D011 | recoverable | Stable native systems, explicit mismatches and controlled failures preserve the same challenge across approaches; see Stable enterprise. |
| D013 | recoverable | The bounded read-only roster follows the Personnel ownership boundary; superseded by D014. |
| D014 | recoverable | Precise identity, version and XML rules establish a common executable baseline; see Frozen contracts. |
| D015 | recoverable | One owner for facts and shared mapping rules prevents adapters from redefining the problem; see Ownership. |
| D016 | explicit | A traditional SOAP service and contract-driven Java preserve the selected legacy boundary; see SOAP runtime. Comparative reasons for every library choice are not recorded. |
| D017 | explicit | Canonical hashing fixes checkout-dependent startup without changing frozen data; see Repeatable data. |
| D016/D017 extension | recoverable | Release 003 expands workload size while retaining the frozen wire contract; see Repeatable data. |
| D021 | explicit | Preserve each system's meanings even when a unified model could remove disagreement; see Ownership. |
| D022 | recoverable | Stable Personnel identity supports subtype changes without changing v1; see Ownership. |
| D032 | explicit | Assignment implies Starfleet responsibility and participation does not; see Crew assignment and mutation authority. |
| D033 | explicit | One versioned contract needs exact observable behavior, not framework defaults; see Missions v1 wire precision. |
| D034 | explicit | Each residual wire choice has a stated reason: the Outlook 2010 stardate analogy, code points as in Personnel, the MAJOR.MINOR contract-evolution rule, and three YAGNI deferrals (HEAD/OPTIONS, release-only mapping semantics, and no patch level or wire version marker); see Missions v1 residual wire precision. |
| D036 | explicit | Each part of the contract has a stated reason, most in the lead developer's own words: a read-only service in a different technology, OpenAPI, Python, a derived category, STARSHIP, equipment kinds of their own and the vehicle-only parent rule; the Missions evolution rule is applied without a `frozen` mark; see Assets contract 1.0. |
| D037 | explicit | The lead developer agreed to freeze after the implementation and asked for contract and fixtures only, and whether this allows a 1.2; the exact-path design answers it; see Missions contract 1.0 and 1.1 frozen. |
| D038 | explicit | Every part has a stated reason in the lead developer's own words: a distinct code for a path outside the contract, an Assets identifier of its own with an underscore allowed in the prefix, and the exception that keeps the change in 1.1; see Assets contract 1.1. |
| D039 | explicit | The lead developer agreed to freeze after the implementation and asked for contract and fixtures only; the exact-path design of D037 answers whether a 1.2 stays possible; see Assets contract 1.0 frozen, 1.1 follows. |
| D041 | explicit | The lead developer's words give the release in the key, the paging maximum, all or nothing for a page, the Personnel type, the new folder and every port range; the shared constraints are source-stated; see Federation graph design. |
| D042 | explicit | The lead developer ordered the migration, named the recipe as the source of truth, ruled on the exceptions tables, the clearance table and the file names, and the id rule and the checks are source-stated; see Federation crew mapping. |
| D043 | explicit | The lead developer chose each refinement in their own words (the explicit outcome and its names, the asset id, the parent field, the timeout rule and the nullable field) and the measurements that led to them are source-stated; see Federation graph refinements. |
| D044 | explicit | The lead developer chose each part in their own words: the larger release, its composition with Season 5 added, appending instead of renumbering, and, through dialog choices, the repair-cost exception and the page files; the rest is source-stated; see Missions larger release. |
| D045 | explicit | The lead developer defined the classes in their own words, ordered the clean-up and chose the form of the correction, the treatment of the carried missions and of the off-roster civilian through dialog options; the rules for the generated missions are agent-reasoned and labeled; see Missions participant classes. |
| D046 | explicit | The lead developer gave every rule of question 6 in their own words (the people counted, the three counts and the percentage of the confirmed, half up, the PLANNED rule and leaving the CANCELLED missions out); the arithmetic of the expected answers is source-stated by script; see Federation question 6. |
| D047 | explicit | The lead developer answered each of the nine design points of the Cosmo router in their own words (the comparison on equal terms, the newest versions, the committed execution config, the error passthrough, the timeout and the dead-adapter check, the port and the stack, the licence re-check, the telemetry of both routers, the rest of the Job) and ruled on the retry setting; the entry that held the wording was pruned with its Job and the words were restored on 2026-10-20 from the conversation into the kept design record; see Federation Cosmo router. |
| D048 | explicit | The lead developer ruled that an O reference is refused by class and that a P reference is allowed, chose the exception of the one participant and the failure for a name only a crew member holds; the strict mode of release 1.3 follows the definitions and is agent-reasoned; see Federation class mapping. |
| D049 | explicit | The lead developer chose the warm-up and the cache in their own words (options A and C) and ruled against a read of the snapshot at start; the figures are source-stated; see Federation Personnel cache. |
| D027 oversized reference extension | explicit | The lead developer chose a proper client error code over a 500 and kept the physical columns; the 422 code was proposed by the Coordinator and accepted with the header fix; see Missions oversized reference. |
| D027 schema and dataset extension | explicit | Accepted local design promoted before runtime; source/provisional distinctions and YAGNI limitations retained; see Missions schema and dataset. |
| D027 | explicit | The lead developer supplied the original intent for the legacy stack, the DEFCON-like priority scale, the mission-type set (based on the mission types TNG portrayed, with TACTICAL and no OTHER by YAGNI), deferred finance, and the 20-mission and 60-change dataset sizes; the repository records the era reason, exact values and shapes, and finance boundary, but not these reasons, and nothing contradicts them. Status, classification, issuing-authority and location-type membership, field bounds and cardinalities remain unknown (reason not recalled). Parts are superseded by D033 and D034; see Missions legacy stack and SOA/BPM layer. |
| D028 | explicit | The resource-versus-process split and the WIP 12.2.1.4 target are recorded in D028; the lead developer supplied why that version fits the lab's mature-enterprise setting. See Missions legacy stack and SOA/BPM layer. |
| D050 | explicit | The lead developer decided to freeze and deprecate Crew & Personnel v1 and to keep dataset 003 by checksum; carried systems still depend on it, so it stays; see Deprecation. |
| D051 | explicit | The lead developer approved a narrow, enumerated exception because the recovery chain could not be adopted before the first runtime commit; see Set-up imports. |
| D052 | explicit | The checkpoint tool could not prepare any transaction until the implementation checkpoint row was on main; the lead developer approved one more set-up commit; see Set-up imports. |
| D053 | explicit | The lead developer chose to rewrite the commit email once to keep it private, keeping authorship, dates and content; see Set-up imports. |

## Fair comparisons: D002, D003, D005, D006

**Decision / what we do.** Share contracts, fixtures, operations, assertions and measurement rules; isolate platform-specific adapters. Compare pinned Apollo, Cosmo and Hive configurations only after shared correctness checks. Evaluate later MCP/AI task behavior separately from router performance. An adapter is the part that connects the shared lab to a particular platform.

**Why.** If each adapter changes the workload, a timing difference no longer answers the same question. D005 states the clearest case: a fast incorrect answer is not a performance win. Agent task success also includes choices and tool use beyond routing, so it needs its own evaluation. The sources establish this separation; they do not establish a preferred vendor or why the shortlist contains exactly those three.

**Tradeoffs or costs.** Shared tests and comparable configurations take work. Platform-specific features need separate experiments rather than silently changing a common run.

**Evidence.** [Architecture: logical boundaries and measurement](../docs/ARCHITECTURE.md), [Plan: acceptance and benchmark protocol](../docs/PLAN.md), and D002-D006 in Decisions; initial committed baseline lab commit `d40be91584fb4a88a2d0e1ea40f585fd5b978c54`.

**Revisit when.** A required scenario cannot be compared fairly across the pinned configurations, or the research question changes. Record unsupported behavior before changing shared semantics.

**Rationale status.** D002/D006 recoverable; D005 explicit; D003 missing for shortlist selection.

## Stable enterprise: D009-D011

**Decision / what we do.** Use the USS Enterprise scenario with independently meaningful native systems and inconsistent identifiers. Validate the native environment before adding integration layers; keep the enterprise stable while swapping those layers.

**Why.** D009 explicitly frames the portfolio around asking a messy enterprise "Computer...". Architecture supplies a concrete cross-system question: a shuttle is unavailable because maintenance needs a component that inventory lacks and logistics has not delivered. The integration must connect those facts. Making every source share the same identifiers or GraphQL-shaped interface would remove part of that problem. Controlled failures are repeatable inputs, not accidental outages.

**Tradeoffs or costs.** Multiple native technologies and explicit identifier mappings make setup and diagnosis more involved. The inspected sources do not explain why each particular technology was assigned to each subsystem rather than plausible alternatives.

**Evidence.** [Architecture: stable enterprise and controlled failures](../docs/ARCHITECTURE.md), [Legacy systems stay unaware of the integration layer](CONSTRAINTS.md#legacy-systems-stay-unaware-of-the-integration-layer), D009-D011; initial baseline lab commit `d40be91584fb4a88a2d0e1ea40f585fd5b978c54`. This explanation does not adopt any uncommitted Missions design.

**Revisit when.** A native scenario no longer tests the intended integration problem. Any change would need an explicit shared contract/version decision, not an adapter convenience fix.

**Rationale status.** D009 explicit; D010/D011 recoverable, with the selection gap above.

## Frozen contracts: D013-D014

**Decision / what we do.** Personnel v1 is a read-only roster with precise identity, supervisor, pagination and XML rules. Its frozen specification and executable contracts outrank implementation convenience. Dataset content and wire contracts have separate versions.

**Why.** A shared baseline needs agreement about meaning as well as field names. An omitted supervisor means no supervisor recorded; it does not prove that none exists. A changed dataset between pages requires restarting, otherwise a consumer could combine different snapshots. The executable schema and fixtures make these distinctions checkable before choosing an integration platform. The reason for every individual bound or enum is not recorded and is not reconstructed here.

**Tradeoffs or costs.** Strict compatibility limits convenient extensions. For example, adding a breaking field or changing XML meaning requires a new contract version rather than quietly adjusting the frozen service.

**Evidence.** [V1 specification](../docs/CREW-PERSONNEL-V1.md), [design log](../devlog/2026-09-30T1654Z-crew-personnel-design-dataset-001.md), [executable-contract log](../devlog/2026-09-30T1800Z-crew-personnel-frozen-executable-contract.md). lab commit `748c3bb987848b9757e5f4f5da806069685921ba` still contained pending-freeze wording despite its title; lab commit `9fdfba688094f3905997b345cfbdf44668c50bf3` records the frozen executable state. Neither establishes the exact discussion time of approval.

**Revisit when.** A new native business requirement cannot be represented faithfully in v1. Preserve released versions while considering a separately approved successor.

**Rationale status.** D013/D014 recoverable.

## SOAP runtime: D016

**Decision / what we do.** Use Java 17, Maven and CXF with Java interfaces generated from the frozen WSDL/XSD. WSDL describes the SOAP interface; XSD defines its XML data rules. A separate deployment descriptor adds the service address. No Spring application framework is used.

**Why.** D016 explicitly describes a traditional enterprise SOAP integration and the selected Java/CXF baseline. Starting from the contract keeps generated Java subordinate to the agreed wire behavior. Containers provide reproducible lab deployment without claiming that the fictional original system was containerized. No comparative evaluation explaining CXF versus every alternative, or the no-Spring choice by itself, was found.

**Tradeoffs or costs.** Generated types and deployment metadata require build discipline; framework convenience cannot justify editing the frozen contract. Generated output cannot replace source contracts as evidence.

**Evidence.** D016, [runtime report](../docs/CREW-PERSONNEL-JAVA-V1-VALIDATION.md), [implementation log](../devlog/2026-10-01T0048Z-crew-personnel-java-service-checkpoint.md); implementation checkpoint lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`.

**Revisit when.** Runtime support or a required contract feature makes the stack unsuitable, with compatibility and reproducibility reviewed explicitly.

**Rationale status.** Explicit for the stated legacy/contract rationale; comparative selection gaps remain missing.

## Repeatable data: D004, D017 and the D016/D017 extension

**Decision / what we do.** Pin generated-data inputs and hashes. Keep published snapshots immutable. For legacy 001/002, normalize only CR immediately before LF while hashing canonical Git content; parse the original bytes. Released 003 instead uses exact raw-byte identity and eight storage pages loaded as one 800-person snapshot.

**Why.** A fixed seed is insufficient if the clock, generator or ordering changes. D017 addresses a demonstrated problem: checkout line endings made the same frozen content start successfully in one environment and fail in another. Its narrow hash rule fixes that problem without rewriting the datasets. The 003 design identifies a different pressure: a larger dataset must not become an oversized SOAP response. Internal storage pages allow a larger aggregate while preserving the public 100-record response limit.

**Tradeoffs or costs.** Supporting old and new byte-identity rules requires care; D017 is not permission to normalize 003 or v2. Loading 003 fully before publication costs startup time and memory, and rejects an invalid package instead of serving a partial roster.

**Evidence.** [Integration notes: immutable dataset identity](../docs/INTEGRATION-NOTES.md#immutable-dataset-identity-and-checkout-line-endings), [003 design](../docs/CREW-PERSONNEL-DATASET-003-DESIGN.md), [003 release log](../devlog/2026-10-01T2048Z-personnel-003-runtime-release.md). D017 is committed at lab commit `b77b23acaa84178931b2cd1cc09b4d14dd956d5b`; release extension at lab commit `03abf8c17c1a78dec88885fdc77392577a2ade9a`.

**Revisit when.** Dataset size makes eager loading impractical, or a new package format is needed. Revisit the new format rather than reinterpreting already published bytes.

**Rationale status.** D004/D017 explicit; release extension recoverable.

## Ownership and differing meanings: D015, D021, D022

**Decision / what we do.** Personnel owns people and reporting; Missions owns participation and assignments. The shared Integration & Benchmark layer owns external-ID mappings. Preserve each system's own meanings. Personnel v2 gives a person a stable PRS identity with exactly one crew or civilian detail branch, alongside unchanged v1.

**Why.** A bounded context is a system's area of responsibility, within which its terms have defined meanings. Two systems need not classify the same person alike. The committed Wesley example makes this concrete: `PRS-0714` survives a civilian-to-crew transition, while Missions may retain different historical references. Matching numeric suffixes prove nothing. Explicit mappings can report missing, ambiguous or dangling references instead of guessing. Civilians need no artificial rank or department merely to fit a crew model.

**Tradeoffs or costs.** Integration must carry disagreement and unresolved mappings. Historical mapping time/version rules remain a design question; this rationale does not implement them. V1 and v2 require separate compatible deployments and evidence.

**Evidence.** D015/D021/D022; [approved identity design](../docs/PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md), [v2 specification](../docs/PERSONNEL-V2.md), [v2 runtime log](../devlog/2026-10-02T1151Z-personnel-v2-runtime-continuity.md). Design checkpoint lab commit `100cdb22b13d61127d8a39adabbfdcab962d258e`; runtime lab commit `5270c98d20102c1d1b38470ebe3df1563adbe369`. The preserved Missions stash is not adopted as current authority.

**Revisit when.** Native ownership or identity requirements change, or historical mapping semantics need implementation. A simpler unified model alone is not a reason to erase disagreement under D021.

**Rationale status.** D015/D022 recoverable; D021 explicit.

## Missions legacy stack and SOA/BPM layer: D027, D028

**Rationale status.** Explicit, with provenance kept separate. The lead developer is the authority on original design intent. Repository records, logs and commits are supporting evidence: they corroborate or refine the lead developer's recollection and show what was already recorded, and their absence is a provenance limitation, not evidence that the recollection is invalid. Three labels are used below. *Repository-recorded rationale* is stated directly in D027, D028, the Missions design or other committed sources. *Supplied by the lead developer / reconstructed original design intent* is original intent supplied on October 6, 2026, partly retrieved from a ChatGPT Codex chat that was not inspected here, and never previously recorded; it is explanatory only, is not a Decision or binding rule and does not extend D027 or D028. *Still unknown / reason not recalled* means neither source provides a reason.

**Decision / what we do.** As recorded in D027: Missions uses REST/HTTP with application/xml, Java/JAX-RS with Jersey, JAXB/XML and Apache Tomcat, with Oracle Database 18c through plain JDBC, superseding D010's REST/JSON choice for Missions only; runtime version selection is deferred. As recorded in D028: a separate Oracle SOA Suite/BPM 12.2.1.4 layer, requirements WIP, owns cross-system process integrity.

**Repository-recorded rationale.**

- *Era and stack.* D027 states the reason: preserve circa-2010-or-earlier native architecture and javax-era concepts in the 2366 / TNG Season 3 setting without requiring unsafe ancient binaries. The [Missions design](../docs/MISSIONS-V1-DESIGN.md#historical-premise-and-native-technology) adds that technology era and fictional calendar are separate and that exact compatible versions are implementation-time choices.
- *Resource versus process.* D027 and D028 state that Missions owns resource integrity and future SOA/BPM owns process integrity; no lifecycle transition graph is enforced in Missions.
- *Priority and ordering.* The design records the exact scale, 1 CRITICAL, 2 URGENT, 3 HIGH, 4 NORMAL and 5 ROUTINE, and the collection order stardate ascending, priority ascending, then missionId ascending, so the most urgent missions sort first within a stardate. It does not state why the scale is inverted or where it comes from.
- *Mission types.* The exact ten values are DIPLOMATIC, EXPLORATION, SCIENTIFIC, FIRST_CONTACT, MEDICAL, RESCUE, HUMANITARIAN, SECURITY, TACTICAL and TRANSPORT, identical in the preserved Missions stash's design text. SECURITY and TACTICAL are distinct values. The design defines no semantics for any type, and type is an ordinary client-supplied field replaced by PUT; no rule derives or validates it from events.
- *Statuses and classification.* The design records the meaning of each status (PLANNED proposed, AUTHORIZED approved, ACTIVE underway, POSTPONED approved work deferred or suspended, and three distinct terminal states). It records that mission classification describes information while clearance describes a person, so their enums intentionally differ.
- *Cost and finance.* No Missions rule makes cost depend on mission type: the cost lifecycle depends only on the resulting status, costs are single estimate and actual amounts, and "No currency-conversion or finance-line-item model is introduced." The design's audit rules refer to Finance's special cost history, recording the new resulting cost plus a signed change without expanding the audit into full snapshots or arbitrary diffs; it does not otherwise explain the cost model. The [future SOA/BPM requirements](../docs/FUTURE-SOA-BPM-REQUIREMENTS.md) place classified-duty compensation and bonuses in that layer, driven "from mission classification and process context", with policies and the owning compensation system still to be determined and no rates or payroll model selected, and state that Missions "does not establish spending authority."
- *Dataset size and shape.* The design requires exactly 20 curated missions and at least 60 audit/change entries, superseding an earlier roughly 10-20 proposal. Histories vary naturally, not three mechanically assigned changes per mission, and records are connected through recurring officers and assets, varied classifications, realistic overruns and underruns, and distinct FAILED and CANCELLED scenarios.

**Supplied by the lead developer / reconstructed original design intent.**

- *Stack (D027).* Missions intentionally models a mature Java enterprise REST service rather than a modern greenfield application. Jersey/JAX-RS, JAXB/XML, Tomcat and Oracle 18c were chosen to preserve that architectural character: a `javax.*`-era REST/XML programming model, servlet-container deployment, explicit wire contracts, and a database-backed enterprise application style representative of long-lived production estates. The objective is architectural and historical fidelity, not the use of obsolete or unsafe binaries; compatible supported implementations may be used while preserving the intended external behavior and technology boundaries. Oracle 18c also reflects a realistic enterprise environment in which application, middleware and database generations do not necessarily advance together.
- *Orchestration layer (D028).* Oracle SOA Suite/BPM 12.2.1.4 represents a separate enterprise orchestration and process layer above the existing bounded systems. It does not replace them or collapse their ownership boundaries: Personnel remains a SOAP/XML service and Missions a REST/XML service. The layer can later coordinate cross-service workflows, approvals and human tasks, transformations, business-process rules, recovery or compensation, and process-level audit. Version 12.2.1.4 fits the lab's mature-enterprise setting and is a realistic example of the long-lived middleware still found beside legacy application estates. The purpose is to test integration and orchestration across independently owned systems, not to make SOA/BPM the source of truth for their domain data.
- *Priority.* The 1..5 scale is deliberately DEFCON-like, with a lower number meaning higher urgency. The inversion is intentional and useful for deterministic ordering (stardate ascending, priority ascending, missionId ascending). It is not an arbitrary numeric range. The repository contains no DEFCON reference.
- *Mission types and TACTICAL.* The ten types cover materially different operational classes, not flavor text. The set is based on the typical mission types the ST:TNG series portrayed, which is why these types exist. TACTICAL is the Starfleet euphemism for a mission with expected armed engagement or direct military-style action, deliberately distinct from SECURITY. It describes the mission's intended or expected operational character; a mission is not reclassified as TACTICAL merely because combat happens unexpectedly. The repository supports only that the two values are distinct and that type is a client-managed field that no rule derives. No catch-all OTHER mission type was added, following YAGNI: the set covers the portrayed mission types, an unusual premise can use the nearest type (an anomaly investigation can be SCIENTIFIC), and a new type is added only if a real need appears. The location-type enum, which does have OTHER, differs deliberately. Adding a value later would be a compatible minor addition under D034's contract-evolution rule.
- *Finance deferred.* Financial rules were intentionally deferred and are not Missions behavior. Design discussion used phaser recharge or weapons-energy consumption and damage-repair costs as examples, with illustrative values of 4,800.00 and 87,300.00; the repository contains neither the concepts nor the values, so they are not dataset values and no cost model is derived from them. The intended model is that mission type gives operational context while the actual events and resources consumed produce the resulting costs, so TACTICAL carries no fixed surcharge and is not intrinsically more expensive. Any future personnel compensation or bonus logic, including effects of sensitive work such as TOP_SECRET missions, belongs in a later finance, SOA or BPM layer, not in Missions.
- *The 20-mission fixture.* The size was not arbitrary: it takes the approximate scale of a Star Trek: The Next Generation season and rounds to a manageable canonical fixture, using public ST:TNG episode data as source material. The intent was to mine a larger episode corpus and derive or curate 20 mission-like records from it, not invent every mission from scratch, while keeping the dataset deterministic, varied and small enough to inspect by hand. It balances TNG grounding, enough variety for filters, ordering, history and relationships, deterministic testing and human auditability. The repository records no episode corpus, source or parsing method.
- *The 60-change target.* It aims at about three changes per mission on average (60 / 20 = 3), but the changes are deliberately not uniform: some missions have little or no history and others several updates, so the history looks deterministic but realistic rather than an obviously synthetic fixture. The repository directly supports the non-uniform shape and the minimum of 60 but not the average-of-three derivation.

**Tensions noticed, not contradictions.** Nothing in the repository contradicts the intent supplied by the lead developer. Two points need dataset-design attention, and neither is resolved here. First, the design says the premise "is not episode chronology" and also says to preserve Season 3 decimal stardates; deriving records from a multi-season episode corpus is compatible with the first as source material, but the dataset design must decide which stardates those records use, and D034's stardate range now spans 43000.00 to 49000.00. Second, "little or no history" must be reconciled with POST semantics: if every seeded mission carries a CREATED entry, as the audit rules imply, then "no history" can only mean no UPDATED entries beyond it, and the minimum of 60 entries includes those CREATED entries.

**Still unknown / reason not recalled.** Neither the repository nor the lead developer's account gives a reason for: why exactly these seven status values (their meanings are recorded, their membership rationale is not); why classification has exactly three levels beyond its intentional difference from clearance; the issuing-authority enum membership (STARFLEET_COMMAND, ENTERPRISE_COMMAND, STARFLEET_MEDICAL, STARFLEET_SCIENCE, STARFLEET_SECURITY, FEDERATION_COUNCIL); the location-type enum membership (PLANET, STARBASE, VESSEL, SECTOR, DEEP_SPACE, ENTERPRISE, OTHER); the individual field length and range bounds (for example 120 and 2000 characters); and the cardinalities, including 0..100 Crew and 0..50 assets. The search covered the Missions, identity and SOA/BPM designs, the decision registry, the lab logs, the preserved Missions stash's design text and every registered worktree's Markdown, text and JSON files. These stay unresolved unless the lead developer supplies them.

**Tradeoffs or costs.** D027 defers runtime version selection, so compatible pins remain implementation-time choices. D016's no-Spring rule applies to Personnel; D027 establishes no no-Spring or no-JPA rule for Missions, and any Missions framework constraint would need its own support or decision. D028 requirements remain WIP: no BPEL implementation, complete workflow or compatibility claim exists. The intent supplied by the lead developer explains why the design looks as it does; it neither describes implemented behavior nor adds a requirement.

**Evidence.** [D027 and D028](DECISIONS.md#d027---missions-v1-design-freeze-2026-10-01-accepted-design-frozen), the [Missions design](../docs/MISSIONS-V1-DESIGN.md), the [future SOA/BPM requirements](../docs/FUTURE-SOA-BPM-REQUIREMENTS.md) and the preserved stash's design text for the repository-recorded items; the lead developer's October 6, 2026 account for the labeled intent. This explanation grants no approval, implementation authority or acceptance and introduces no new constraint.

## Crew assignment and mutation authority: D032

**Rationale status.** Explicit.

**Decision / what we do.** D032 separates formal C-only Starfleet assignment and mutation actors from non-Crew P/O participation in Missions v1.

**Why.** The lead developer's October 3, 2026 design clarification states that assignment implies Starfleet responsibility and participation does not. Naming assignedCrewIds makes that responsibility visible; participantIds permits contextual involvement without implying assignment obligations or mutation authority.

**Tradeoffs or costs.** Future wire work must specify participant structure and lexical details. Local C/P/O classes still require explicit contextual identity mappings; syntax cannot prove Personnel identity or authenticated authority, and O implies no Personnel membership or richer ontology.

**Evidence.** The lead developer's explicit design-only request, inspected main lab commit `d17fd9a2642d68e6b35e3384d41a1c27b57ada0b`, [D027/D028/D032](DECISIONS.md#d032---crew-assignment-and-mission-mutation-authority-2026-10-03-accepted), the [Missions reconciliation](../docs/MISSIONS-V1-DESIGN.md#current-identity-reconciliation-2026-10-03) and the dated [identity design](../docs/PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md#missions-independent-cpo-references). This explanation grants no commit authority or runtime acceptance.

## Missions v1 wire precision: D033

**Rationale status.** Explicit.

**Decision / what we do.** Record the lead developer's seven wire clarifications as one bounded decision linked to the owning Missions design. Retain D027's historical agreement and identify the few conflicting earlier rules as superseded; retain D032's assignment responsibility and independent identity semantics.

**Why.** An implementer needs exact observable behavior, not Jersey defaults or a mixture of old and new agreements. One versioned contract has one coherent precision package; seven registry entries would fragment its history and duplicate its specification. The lead developer explicitly requested canonical identifiers, deterministic XML/media/errors, numeric mutation order, database time and summary metadata outside resource state.

**Tradeoffs or costs.** Earlier padded references, caller ordering, a separate ETag identity and optional summary no longer describe current v1. Future implementations must obey the current design, while historical artifacts preserve the original forms. Remaining list shapes, lexical counting/scale and media grammar details still need explicit resolution; this decision cannot honestly claim that the entire executable-contract blocker is cleared.

**Evidence.** The lead developer's October 3, 2026 design-only order; inspected main lab commit `1060f8195bf3922bc18e2ef4d2f6f3538d82b438`; [D027/D033](DECISIONS.md#d033---missions-v1-wire-precision-2026-10-03-accepted-scope), [current design and residual questions](../docs/MISSIONS-V1-DESIGN.md#remaining-precision-and-governance), architecture, Plan and Progress. The initial inspection was at lab commit `37bd08fc57623478e946874caed05712f4db7202`; the intervening unrelated Personal Log commit was inspected before owned-worktree creation. This explanation grants no checkpoint approval or runtime acceptance.

## Missions v1 residual wire precision: D034

**Rationale status.** Explicit.

**Decision / what we do.** Record the lead developer's October 6, 2026 settlements as one bounded decision linked to the owning Missions design: list and container structure, code-point lexical bounds with state-dependent `outcome` and the stardate pattern, strict media grammar, unsupported HEAD/OPTIONS with a path-accurate `Allow` header, MAJOR.MINOR contract evolution, and the move of historical mapping time/version semantics to the Integration & Benchmark layer.

**Why: the narrative.** Missions is a circa-2010-or-earlier native system aboard the Enterprise-D in 2366; technology era and fictional calendar are deliberately separate. The lead developer therefore chose specifications a 2010-era enterprise system would plausibly have, and reasoned by analogy to everyday 2010 software. The clearest case is the stardate, below. Three choices follow the YAGNI principle (add complexity only when a need appears); each is marked.

**Why: each specification.**

- **List and container structure.** Metadata (`page`, `pageSize`, `totalCount`, `totalPages`) comes first so a reader sees paging state before the members. Members follow directly with no extra wrapper, because the list element already is the collection. The ID containers use `crewId`, `participantId` and `assetId`, never a generic `id`: each name can carry its own XSD simple type, so a Crew reference in the wrong container fails schema validation (400) instead of surfacing as a later domain failure, which keeps D032's disjoint assignment and participation sets visible in the wire format.
- **Code points for length.** Personnel already counts code points on Java 17 (D016 and its tests), and the lead developer saw no gain in drifting from it. One counting unit across services means no per-service surprises for supplementary characters.
- **Non-whitespace rule and `outcome`.** The existing title/objective rule is applied to every minimum-1 string so there is one blank rule. `outcome` depends on status because it describes a result: optional in the three terminal states, forbidden in the four non-terminal ones. "Expected" for COMPLETED/FAILED has no wire effect, so it is guidance for dataset authors, not a service requirement.
- **Stardate, by analogy to Outlook 2010.** The lead developer's reference was the Outlook 2010 appointment dialog, whose start-time drop-down offers fixed half-hour slots (1:00 PM, 1:30 PM, 2:00 PM and so on); the screenshot was pasted into the design session and is not stored in the repository. A mission's stardate is a scheduled or actual commencement, and a 2010-era scheduling tool would offer a coarse grid, not minute precision. On the common fan rule of 1000 stardate units per year, 0.05 is about 26 minutes, so a 0.05 grid roughly matches those 30-minute slots. This is an analogy for the resolution only, not a stardate-to-Earth-time conversion, which the design still declines to define. The pattern `^4[3-8][0-9]{3}\.[0-9][05]$` keeps exactly two fractional digits so each value has one spelling, consistent with the fixed two-digit costs and the no-silent-normalization rule. The ceiling of 49000.00 covers the whole TNG run (the series finale is about 47988) with headroom, and the lead developer preferred a simple bound over tracking each season.
- **Strict media grammar.** The lead developer's rule was no ambiguity: the only Content-Type parameter is `charset`, Accept honors `q`, and malformed headers fail with 400 instead of being guessed at. This follows the earlier design stance not to infer permissive matching from a Jersey version.
- **HEAD and OPTIONS unsupported (YAGNI, first use).** Nothing in the lab needs them yet, so they are not designed. They return 405 with an `Allow` header listing only that path's supported methods, and the framework's automatic handling must be disabled so it cannot answer them. They are added only if and when a need arises.
- **Mapping semantics moved out (YAGNI, second use).** Missions stores reference strings only and never resolves them, and D015 gives mapping rules to the Integration & Benchmark layer. For that layer the lead developer chose the simplest direction that mirrors Personnel's proven dataset versioning: immutable versioned releases, an explicit release in every resolution request, and no effective-interval axis. Time lives only in the choice of release. Intervals, with their overlap and gap rules, can arrive later as a new release schema version if a scenario needs them.
- **Contract evolution: MAJOR.MINOR (YAGNI, third use).** The lead developer's position is that adding something does not require a new version, while removing it is a different matter, and wanted flexibility for additions. Putting only the major in the namespace means additive changes (new enum values, widened bounds, new optional filters, endpoints, error codes and elements) never force consumers onto a new namespace, while removals, renames, narrowing and semantic changes still do. The repository's existing rule said breaking changes need a new version but never defined "breaking"; this defines it for Missions only. Each minor is an immutable XSD revision so consumers can pin a known contract. Two things are deliberately left out until a need appears: a patch level, and a wire version marker for runtime discovery.

**Tradeoffs or costs.** The stardate grid and 49000.00 ceiling depart from canon and from D027's original 44000.0 range, and the 0.05 grid rejects values such as `43125.83`. Strict header handling rejects some tolerant clients, and refusing HEAD/OPTIONS means the framework's automatic handling must be disabled. A release-only mapping model cannot answer "what did this reference mean at mission time T" without the caller choosing the matching release. Oracle byte limits for 2000-code-point text remain an implementation concern. Strictly validating consumers must refresh a pinned XSD when a minor revision adds values or elements, and each minor needs its own immutable XSD file.

**Evidence.** The lead developer's October 6, 2026 order and the Outlook 2010 screenshot pasted during the session; inspected main lab commit `a1fb35b89aa3d561a4aa6807563212ae925863c6`; [D034](DECISIONS.md#d034---missions-v1-residual-wire-precision-2026-10-06-accepted-scope), the [Missions design](../docs/MISSIONS-V1-DESIGN.md), the [identity design](../docs/PERSONNEL-V2-MISSIONS-IDENTITY-DESIGN.md#missions-independent-cpo-references) and Personnel v2 versioning. This explanation grants no checkpoint approval or runtime acceptance.

## Missions oversized reference: D027 oversized reference extension

**Decision / what we do.** A valid reference longer than 50 UTF-8 bytes answers 422
DOMAIN_VALIDATION_FAILED with the XML error body; nothing is stored or truncated and
the columns keep their width. A control character in a header value, refused by the
container itself, answers the XML 400 INVALID_REQUEST instead of the container's HTML page.

**Why.** Supplied by the lead developer, in the main-console session on 2026-10-15: option 1 for the oversized
reference, a proper error code with the column left as it is, and, after the Coordinator proposed 422 DOMAIN_VALIDATION_FAILED and fixing the control-character headers, acceptance of both, to be recorded and queued at priority 3. Source-stated: the design
and the schema fix the column at `VARCHAR2(50 BYTE)`, so an unchecked longer reference reached the database and
failed as 500, which the design says domain failures must not do. Agent-reasoned: counting bytes
keeps a non-ASCII reference of fewer than 50 characters but more than 50 bytes from reaching the database; the
existing 422 code avoids a contract revision.

**Alternatives.** Chosen by the lead developer: a proper error code with the columns unchanged. Proposed by the
Coordinator and accepted: the existing 422 code. Rejected by the lead developer: widening the columns. Not
considered: a new error code (it would need a contract 1.2) and a 400, which the design reserves for grammar failures.
The XML body for the control-character case was chosen by the lead developer over leaving the container's page.

**Tradeoffs or costs.** The design's earlier "no 400/422 mapping" sentence is superseded and kept as history. A
custom error valve ties the service to Tomcat's valve API. Other container-generated errors still show Tomcat's page.

**Evidence.** Job records `missions_open_questions` and `missions_conformance`; inspected
`docs/MISSIONS-V1-DESIGN.md`, `uss-enterprise/missions/schema/schema.sql`, `MissionRules.java`,
`MutationHeaders.java`, `XmlErrorReportValve.java` and the write acceptance gate.

**Revisit when.** The columns are widened, a contract 1.2 is published for another reason, or other container-level
errors need the XML body.

## Missions schema and dataset: D027 schema and dataset extension

**Decision / what we do.** Promote the accepted Missions schema/dataset design
requirements before implementing them; preserve immutable 1.0 and publish the
MAINTENANCE addition separately as compatible 1.1.

**Why.** Supplied by the lead developer, as attributed in the primary missions_schema_dataset
Job on October 8: useful mission-worthy activities determine 20..100 content
from Season 3 onward; histories should contain sensible operational changes,
not mechanically padded transitions. The lead developer asked for reproducible random
increments and category reseeding so additions to one category do not disrupt
the others, and accepted seed 1701 and the timing/cost batches. Costs are lab
invention because TNG supplies no accounting; tactical work also consumes
resources. The lead developer chose YAGNI for 50-character DB references and explained
human-text headroom: the constraint is in XML, not the DB. Purpose continuity and
varied recorder styles provide future extraction material without a premature
semantic validator. Source-stated: D027/D032-D034 and the inspected immutable
1.0 schema retain wire authority, resource/process boundaries and explicit
contract evolution. Agent-reasoned: promotion before runtime prevents local
notes from silently overriding frozen design and makes limitations reviewable.

**Alternatives.** Chosen by the lead developer: useful variable content, independently seeded
categories, six tables and a transactional clock, explicit immutable releases/
reset, bounded physical references with ordinary composite keys, and narrative
objective/causal evidence. Superseded: exact 20/Season-3-only content and one
shared cross-category random stream. Not adopted: 100-character reference
storage, LOB/internal collection keys, a new wire bound/major namespace,
ENGINEERING, mandatory type immutability, structured relationship fields and
automatic objective-drift enforcement. Exact generator derivation, release
metadata/events, Oracle image and operator mechanics remain deferred to a
concrete implementation preview; none is silently selected by this record.

**Tradeoffs or costs.** Valid unbounded wire references longer than 50 cannot fit
the accepted storage; this remains an explicit lab limitation with no fabricated
error mapping or full-conformance claim. Summary text cannot retain every allowed
objective, so incomplete extraction must remain unknown. Oracle reset DDL cannot
promise whole-operation rollback; failure must leave the service stopped. A
singleton lock serializes writes. Synthetic timing/costs are reproducible lab
content rather than canon, and deterministic publication requires more than a
seed. Each runtime slice needs real phase-specific evidence and its separate
fresh-worker continuity record transaction.

**Evidence.** Inspected main 6b27907d70e1a61634945be3ac033b1e8e42b502,
[Missions design](../docs/MISSIONS-V1-DESIGN.md),
[contract 1.0](../uss-enterprise/missions/contracts/missions-v1.0.xsd),
[D027](DECISIONS.md#d027---missions-v1-design-freeze-2026-10-01-accepted-design-frozen),
phase gates (lab path `governance/CHECKPOINT-TOOL.md#missions-incremental-runtime-gates`, at lab commit `0f9b1dbd416bc90428d2dc1d3e4c700f19dd7e66`) and
[worktree workflow](../governance/WORKTREE-WORKFLOW.md); full primary Job worksheet,
chronological attributed decisions and consolidated handoff read on October 9.
The Job remains local unfinished evidence; this record does not turn provisional
agent metadata into seed records approved by the lead developer or claim test execution.

**Revisit when.** Concrete release review exposes metadata/timing conflicts,
larger valid references become necessary, a semantic analysis requires structured
evidence, or measured write/query load justifies more storage/indexing machinery.
No revisit condition supplies execution authority.

## Assets contract 1.0: D036

**Rationale status.** Explicit.

**Decision / what we do.** Settle the Assets contract 1.0 as a read-only REST/JSON service on Python and PostgreSQL, with an OpenAPI 3.1 contract, nine kinds, a derived category, a vehicle-only parent rule and no location, and treat its published file as immutable by the Missions evolution rule, stated in words and not marked `frozen` yet.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: a slightly different technology with REST and JSON, so that the legacy mix has a third differently built system; Python, chosen with enthusiasm; OpenAPI for Assets; a nullable parentAssetId; a derived category and the ROVER kind; ARMORED_VEHICLE; on the first kind, the question whether a shuttle is a SHIP, followed by the Starship Enterprise, which renamed SHIP to STARSHIP because a shuttle is a small craft and the word SHIP read as the generic one; and on equipment, that phaser and tricorder were meant to be kinds of their own in the category EQUIPMENT, with a specific MUSICAL_INSTRUMENT instead of a generic instrument and COMMUNICATOR kept, so that the generic kind EQUIPMENT was removed and the category kept. On the freeze they said that the Missions contract is not frozen by a mechanism and told the worker to avoid freezing Assets if possible, and that the freeze is reasonable once the implementation exists.
- Source-stated: the Missions design leaves asset facts to asset-owning services; D034 sets the MAJOR.MINOR evolution rule that Assets applies; the Boundary column of the artifact classification table and `frozen_invariants` in the continuity checker make a `frozen` path immutable for every later checkpoint, as Personnel's contracts are.
- Agent-reasoned: the Missions contract and fixtures carry only the runtime boundary and are immutable by decision and rule, so Assets follows that precedent; a `frozen` mark now would have the continuity checker refuse any later change to the contract, including a legitimate correction found while the service is built. The generic kind was a gap between the earlier talks and the landed contract (no recorded decision listed equipment kinds), which the lead developer chose to fix before the contract was settled.

**Alternatives.** The `frozen` mark now, as Personnel (rejected by the lead developer for now; planned after the service exists). A byte pin of the contract in the validator (not chosen: Missions has none, and the offline validator already checks the decided surface). A generic INSTRUMENT kind (rejected by the lead developer as ambiguous between musical and scientific). A fallback generic EQUIPMENT kind (rejected: every asset must fit a named kind). Plain JSON without a contract file, or GraphQL as the contract (rejected by the lead developer in favor of OpenAPI). Java on the Missions stack (not chosen: it would reduce the heterogeneity the service exists to add). GROUND_VEHICLE as one kind, the acronym AFV and the name SHIP (each superseded by the lead developer's choices recorded in the design).

**Tradeoffs or costs.** Until the mark is added, nothing mechanical stops an edit of the published contract file; the rule and review are the guard, as for Missions. The kind list is longer and a later kind (a station, a medical device) is one enum value and one table row, a compatible minor change, but a dataset needs at least one asset of each kind. The category name VEHICLE was the Coordinator's proposal and the lead developer did not object.

**Evidence.** The [Assets design](../docs/ASSETS-V1-DESIGN.md), the [contract](../uss-enterprise/assets/contracts/assets-v1.0.openapi.json), the runtime commits lab commit `1e915acb267ab4d05694d661f170f9bf77b8f558` and lab commit `dc73e9f40fe010e9f5a4c7331fb23008fedf1c6a`, the Job records of the design talks, the Missions contract rows of the artifact classification table, `frozen_invariants` in `governance/tools/continuity/validate_continuity.py` and [D036](DECISIONS.md#d036---assets-contract-10-2026-10-15-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** The Assets service exists and passes its gate, when the `frozen` mark is added; a scenario needs a location, a station kind, another equipment kind or another compatible addition; or a breaking change makes a new major necessary.

## Missions contract 1.0 and 1.1 frozen: D037

**Rationale status.** Explicit.

**Decision / what we do.** Mark the exact Missions contract files `missions-v1.0.xsd` and `missions-v1.1.xsd` and the fixture folders `fixtures/valid/` and `fixtures/v1.1/` as `frozen, runtime` in the artifact classification table, leave their enclosing folders runtime only, and leave the design document unfrozen.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: freezing is reasonable once the implementation exists; to queue the freeze for the contract and fixtures only; and the question whether this still allows a 1.2.
- Source-stated: the Boundary column of the artifact classification table and `frozen_invariants` in `governance/tools/continuity/validate_continuity.py` refuse a changed frozen file and a changed inventory under a frozen path, and a child row may not clear `frozen`; D034 sets the rule that a minor is a new immutable file.
- Agent-reasoned: marking the exact paths keeps a new file beside them unfrozen, so a 1.2 is possible; the design stays unfrozen because the lead developer did not ask for it and freezing it would turn every amendment into an explicit unfreeze.

**Alternatives.** Freeze the enclosing `contracts/` and `fixtures/` folders (rejected by the agent and the Coordinator: it blocks a 1.2; the lead developer chose the outcome that allows one). Also freeze the design document (not chosen: the lead developer asked for contract and fixtures only). Keep the rule without a mark (rejected: the lead developer asked for the freeze after the implementation). Whether a 1.2 stays possible was checked in a disposable repository: editing a frozen file or adding a file inside `fixtures/valid/` fails the frozen check, and adding `contracts/missions-v1.2.xsd` or `fixtures/v1.2/` does not.

**Tradeoffs or costs.** A legitimate correction to a frozen file needs the lead developer to lift the mark first. Each new minor needs its own rows when published. The golden file pins the new boundary of `missions-v1.0.xsd`.

**Evidence.** The [Missions contract](../uss-enterprise/missions/contracts/missions-v1.1.xsd), the [design](../docs/MISSIONS-V1-DESIGN.md), the artifact classification table, `frozen_invariants` in `governance/tools/continuity/validate_continuity.py`, the runtime commits of the Missions service and [D037](DECISIONS.md#d037---missions-contract-10-and-11-frozen-2026-10-15-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A 1.2 or a breaking 2.0 is published (new rows), or a defect in a frozen file needs the mark lifted.

## Assets contract 1.1: native identifiers and PATH_NOT_FOUND: D038

**Rationale status.** Explicit.

**Decision / what we do.** Publish Assets contract 1.1 as a new immutable file beside 1.0, with a distinct error code PATH_NOT_FOUND for a path outside the contract and a native Assets identifier grammar (AST-0017), with a new dataset release 1.1 and an expected mapping from the Missions references written in its provenance; record the change of the grammar in 1.1 as one exception to the evolution rule.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the choice of the distinct code, option A, PATH_NOT_FOUND; that they expected the Assets system to have its own identifier like Personnel, confirmed in answer to the question of native ids, with a prefix that allows an underscore even though none is used yet, and contract 1.1 to make the change; and the version, option A, 1.1 with the recorded exception, after the three options were put to them.
- Source-stated: Missions answers an unknown path with a bodyless 404 because its frozen contract has no code for it; the Assets contract says every response body is JSON; the Personnel ids PRS-0042 and CRW-1058 are a system prefix and a zero-padded number; D015 and D034 put the mapping, its releases and its interpretation in the integration layer and forbid guessing a missing, ambiguous or dangling outcome.
- Agent-reasoned: the single code ASSET_NOT_FOUND for both cases would let a wrong path pass for an unresolved asset, so the demonstration of the dangling reference would succeed for the wrong reason; the rule of one canonical spelling per identifier follows the Missions grammar; single underscores only, because a second spelling would add nothing; the numbering by the order of the release 1.0 identifiers is the simplest rule that is stated, deterministic and checkable; the expected mapping has an unmapped and a mapped-but-not-found case so that a failure of the mapping layer is told apart from a missing asset. These are the worker's reasons and the lead developer accepted the plan; they did not give them.

**Alternatives.** Edit the 1.0 file in place (not chosen: the evolution rule says a published file is never edited, and the dataset release pins its hash). Publish 2.0 as a new component and a new endpoint, as Personnel v2 stands beside v1 (not chosen by the lead developer: 1.0 never had a consumer). A bodyless 404 as Missions does (the Coordinator's second option, not chosen). Leave the answer as it was (not recommended and not chosen). Keep the Missions grammar for Assets ids and map nothing (not chosen: the lead developer expected a native identifier). A mapping field in the asset record or a mapping service (not chosen: the mapping is the integration layer's work).

**Tradeoffs or costs.** The 1.1 identifiers are not a superset of the 1.0 ones, so a consumer that validated strictly against 1.0 must refresh; there was none. Two contract files and two fixture sets are kept and validated. A second dataset release and a second review by the lead developer were needed. The exception is a precedent that the record keeps single: it is stated once and the rule is unchanged.

**Evidence.** The [Assets design](../docs/ASSETS-V1-DESIGN.md#contract-11-native-identifiers-and-path_not_found), the [contract 1.1](../uss-enterprise/assets/contracts/assets-v1.1.openapi.json), the dataset release 1.1, the Job records of the change and [D038](DECISIONS.md#d038---assets-contract-11-native-identifiers-and-path_not_found-2026-10-15-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A consumer exists that needs another prefix, the mapping layer is built and finds a gap in the expected mapping, the exact files of both versions are frozen, or another breaking change tempts a second exception.

## Assets contract 1.0 frozen, 1.1 follows: D039

**Rationale status.** Explicit.

**Decision / what we do.** Mark the exact Assets contract file `assets-v1.0.openapi.json` and the fixture folders `fixtures/valid/` and `fixtures/invalid/` as `frozen, runtime` in the artifact classification table, leave their enclosing folders runtime only, leave the design document and the dataset releases unmarked, and mark the 1.1 contract file and `fixtures/v1.1/` by their own rows after the next runtime checkpoint.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: freezing is reasonable once the implementation exists, as recorded in the rationale of D036 (D036 planned this step); the order to queue the freeze for the contract and its fixtures once the service exists; and the choice of 1.1 as a new version, which makes the 1.1 contract and its fixtures part of what is to be frozen. When the checker conflict was put to them, they chose to freeze 1.0 now and 1.1 later.
- Source-stated: the Boundary column of the artifact classification table and `frozen_invariants` in `governance/tools/continuity/validate_continuity.py` refuse a changed frozen file and a changed inventory under a frozen path, and a child row may not clear `frozen`; D034 and D036 set the rule that a minor is a new immutable file; the dataset releases are immutable by their own manifests.
- Agent-reasoned: marking the exact paths keeps a new file beside them unfrozen, as D037 did for Missions, so a 1.2 is possible; the design document stays unfrozen because freezing it would turn every amendment into an explicit unfreeze.

**Alternatives.** Freeze the enclosing `contracts/` and `fixtures/` folders (rejected: it blocks a 1.2). Freeze both versions now (not possible: `frozen_invariants` refuses an implementation checkpoint that changed a frozen path, and the checkpoint lab commit `c717e3cbb46b2a200609837f9ca33d306cf9bfe4` added the 1.1 files; continuity failed with that message when tried). Wait for the next runtime checkpoint and freeze both together (not chosen by the lead developer). Change `frozen_invariants` so that it tolerates the checkpoint that first adds a frozen path (a separate tooling change, not made here). Also freeze the design document or mark the dataset releases (not chosen: the lead developer asked for contract and fixtures, and the releases are already immutable by manifest). Keep the rule without a mark (rejected: D036 planned the mark after the service exists). The effect was checked in a disposable repository: editing a frozen file or adding or removing a file inside a frozen fixture folder fails the frozen check, and adding `contracts/assets-v1.2.openapi.json` or `fixtures/v1.2/` does not.

**Tradeoffs or costs.** A legitimate correction to a frozen file needs the lead developer to lift the mark first. Each new minor needs its own rows when published. The golden file pins the new boundary of `assets-v1.0.openapi.json`. Until the 1.1 rows are added, nothing mechanical stops an edit of the 1.1 files.

**Evidence.** The [Assets design](../docs/ASSETS-V1-DESIGN.md), the [contract 1.0](../uss-enterprise/assets/contracts/assets-v1.0.openapi.json), the artifact classification table, `frozen_invariants` in `governance/tools/continuity/validate_continuity.py`, the runtime commits of the Assets service and [D039](DECISIONS.md#d039---assets-contract-10-frozen-11-follows-2026-10-15-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A 1.2 or a breaking 2.0 is published (new rows), or a defect in a frozen file needs the mark lifted.

## Federation graph design: D041

**Rationale status.** Explicit.

**Decision / what we do.** Confirm that the mapping release is both an argument of the field that returns the references and a key field of the reference type; page at the graph level with offset and limit (default 20, maximum 100) and make a page all or nothing; use the owning system's vocabulary for names and a `Personnel` type with a `details` union of `CrewDetails` and `CivilianDetails`; fix the extensions codes; put the federation layer in a top-level `federation/` folder; and fix the port plan.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the confirmation of the release in the key (point 1, then points 2 to 4 together); the paging maximum of 100, just in case, and all or nothing, after they asked whether a code was needed for an incomplete response; the person type, put as a question (a Personnel type rather than CrewMember, with some form of inheritance or choice like Personnel v2) and settled with option A; the new folder and the 100 offset for the ports, to distinguish the federation clearly from the legacy systems, then mirrored ports, the tree approved and the Job to be created; the mapping adapter's separate block at 8190, unless the federation would need more ports or services; the confirmation of the ranges; and the router block, all routers in one block: Apollo 8170, Cosmo 8171, Hive 8172.
- Source-stated: `@requires` takes a field set with no place for a variable of the client's query (the second federation experiment); the Personnel v2 contract already has a choice of `CrewDetails` or `CivilianDetails` and allows 100 per call, while Missions and Assets allow 50 per call; the backing services are offset-based; the legacy services keep ports 8081 to 8084 and the lab's rule is that different services keep different ports.
- Agent-reasoned: cursor connections would be synthetic over offset-based services; an interface for `Personnel` would need the entity-interface feature, which no router was tested with; a list that is complete or absent cannot be mistaken for the whole answer, so no partial-result code is needed; a folder outside `uss-enterprise/` keeps the legacy systems visibly separate from the graph layer, as the constraint that legacy systems stay unaware of the integration layer requires; mirroring the legacy last digit lets a port name its twin.

**Alternatives.** Cursor connections (considered, not chosen). An interface `Personnel` implemented by separate crew and civilian types (Option B; not chosen, and it may be tried as a later compatibility-matrix item). Partial pages with a PARTIAL_RESULT code and the expected and returned counts (not chosen after the lead developer's all-or-nothing ruling). A renaming layer for field names (not chosen: the owning vocabulary is used as is). Ports numbered in sequence from 8180 (not chosen: the lead developer chose mirroring). Port 8185 for the mapping adapter (replaced by 8190, because 8185 would be the twin of a possible fifth legacy service). The Apollo router on 8180 with Cosmo and Hive on 8170 and 8171 (replaced at the lead developer's word by one router block). A layout under `uss-enterprise/` (not chosen).

**Tradeoffs or costs.** A page above 50 takes two calls to Missions and Assets. An all-or-nothing page hides a page that could have been shown in part. Civilians are now in the graph, so a consumer must handle both kinds of details and the absence of a rank. The port plan leaves 8180 unused and needs the lead developer's word for a port outside the ranges. The new paths are on the runtime boundary, so each build is an implementation checkpoint.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md), the runtime commits lab commit `7dd97753e2b5f91bb70c6ec9906845e25c7f4360`, lab commit `9e97bc73170726a45c067658d54a8cb626293d2e`, lab commit `c7423336003d5bda1aa31b3bbbb71e0347ead1a6`, lab commit `21a76328252304759b761001eb0c2ffa6a54ec0f` and lab commit `1842bcc79cd80d9642b1ed685df7dc97391274c1`, the READMEs under `federation/`, the machine-local Job record of the design talk (where the lead developer's words were recorded as said, with typos corrected) and [D041](DECISIONS.md#d041---federation-graph-design-release-key-paging-names-codes-ports-and-layout-2026-10-16-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A consumer needs a partial page; an entity-interface experiment passes on every router; the Cosmo and Hive routers are built and need the block; or a port outside the ranges is needed.

## Federation crew mapping: D042

**Rationale status.** Explicit.

**Decision / what we do.** Map Missions crew references to Personnel v2 identifiers by a four-step process with a mapping exceptions table and a migration exceptions table, migrate the people the process marks into a new Personnel v2 snapshot keeping the number of their v1 id, give them a clearance by rank, and publish the crew section in mapping release 1.1 beside the assets section with the file names unchanged.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the migration itself, to bring everyone to v2, after they said the small overlap between the Missions crew and Personnel v2 could not be right because all the main characters had been added to Personnel (they had been added to the legacy v1 system); the recipe as the source of truth for the mission side of the migration; the order of the process; that the mapping exceptions table must not reference v1 and that its targets must exist in v2, since otherwise a migration has to happen, which is a different thing; that a step-1 exception is added after a migration; the clearance by rank, as proposed, with every security officer at SECRET whatever the rank, corrected to SECRET as the minimum for security officers; and the file names, with no 2.0 for the names alone.
- Source-stated: Missions holds only opaque C-n references and its recipe lists the names; the Personnel v2 snapshots held seven people; identifiers in v2 are PRS- only, so a CRW id cannot be a person id; the v1 numbers (1047 to 2785) and the v2 numbers (0001 to 0006 and 0714) do not overlap; release 1.0 is published and immutable and its manifest pins `assets.json` by hash; the mapping release rule that a MAJOR changes the shape of the mapping.
- Agent-reasoned: more than one name match must be a reported failure and never a pick, because a pick would be a guess; pinning every input by hash lets a run refuse to start on drift; a rename of files inside a section could be read as a change of shape and so a MAJOR, which is why the question was put to the lead developer; a single script serving both the migration and the build keeps the two from disagreeing.

**Alternatives.** Migrate every v1 record (not chosen: only the people the process marks are migrated). Assign new PRS numbers (not chosen: keeping the v1 number was the lead developer's ruling on the id rule). Clearance one level lower for non-cast and a security rule of "secret or more" or exactly SECRET (the first dropped, the others replaced by the minimum rule). A rename to `personnel-mapping.json` and `assets-mapping.json` (not chosen, because it would need release 2.0; it can be reconsidered at a future MAJOR for other reasons). Separate manifests for assets and crew (not chosen: one manifest in release 1.1). Mapping exceptions that point to v1 (rejected).

**Tradeoffs or costs.** Personnel v2 now holds seven migrated records that the legacy system also holds, a duplication of people across the two systems that the migration creates; the legacy systems stay independent and unaware. The migrated clearances are assigned by rule, not recorded facts. The mapping exceptions grow by one entry per name that does not match exactly.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#shared-identity), the process README `federation/personnel-mapping/README.md`, the mapping release 1.1 manifest, the runtime lab commit `21ea3a9cf8eec146e877a143218fbca9d625526e`, the machine-local Job record of the crew mapping talk and [D042](DECISIONS.md#d042---federation-crew-mapping-and-mapping-release-11-2026-10-16-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A new Missions release adds crew references; a name matches in more than one place; the live Personnel path is built and question 6 runs; or a MAJOR mapping release is made for another reason and the file names can change with it.

## Federation graph refinements: D043

**Rationale status.** Explicit.

**Decision / what we do.** Have the mapping state its outcome in `mappingOutcome` and add the resolution value RELEASE_REFUSED; rename the mapping's external asset id to `assetId` and drop the redundant `id` field of the reference types; add `Asset.parent` without caching or batching; set the router's subgraph timeout to 5 seconds; and make `resolution` nullable so that a dead subgraph costs the fields it owns and not the mission.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the fifth value and the explicit outcome (option B), for a clean design and implementation with fewer guesses; the names `RELEASE_REFUSED` and `mappingOutcome`, both judged clear; the rename of `astId`, judged a poor choice, to `assetId`; the removal of the duplicate id, first as a question whether the duplication could introduce uncertainty into the design, to be explored, and then the order to record the design; the parent field (option A), to get as much value out of the graphs as possible, and the deferral of caching to a later improvement when and if the need becomes apparent, with their belief that batching is not implemented in the legacy Assets service; the timeout rule (option B if Apollo supports it cleanly, otherwise option A); the nullable field, which they read as letting a dead subgraph keep the rest of the mission and asked whether that reading was right, then decided to do it; and that the timeout as an environment variable is added if and when it is needed.
- Source-stated: the first end-to-end run showed a refused release as UNMAPPED in the data because the owning adapter inferred the cause from a null id; the `id` field duplicated the mapped id and `asset.assetId`; the router answered HTTP 504 after 30 seconds for a dead adapter, and with 5 seconds answered HTTP 200 but nulled `data.mission` because `resolution` was non-null; Apollo has no setting that returns the rest of the object; with a nullable `resolution` the same run kept the mission, its crew and every other field; 5 seconds is about four times the slowest normal answer measured (1.3 seconds for the whole list).
- Agent-reasoned: stating the outcome in the mapping removes a guess at the owning adapter and keeps one place that knows why an id is missing; an in-subgraph traversal needs no new Federation feature; the 5 second value was proposed by the build from its measurement and accepted by the lead developer.

**Alternatives.** Keep the refused release as UNMAPPED and document it (rejected by the lead developer). Fail the whole request on a refused release (not chosen). Keep the `id` field (dropped after the exploration). Resolve the parent chain with caching or batching (deferred). Leave the 30 second default and document it (not chosen), or use a 3 second timeout (measured, not chosen). The timeout as an environment variable (deferred, not planned). Keep `resolution` non-null and accept that a dead adapter nulls the mission (replaced by the nullable field).

**Tradeoffs or costs.** The schema no longer guarantees that `resolution` is present, so a client must check the errors list whenever it is null, and reading a null as UNRESOLVED or UNMAPPED is wrong. A long parent chain is one call per level. The 5 seconds is fixed in the router configuration. Cosmo and Hive may behave differently with the same schema, and the dead-adapter timeout of each is a separate setting. After a restart of the adapters, the Apollo router did not find them again within 60 seconds in one run; its cause is not verified.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#failure-semantics), [the Apollo router README](../federation/routers/apollo/README.md), the findings sections of [Integration notes](../docs/INTEGRATION-NOTES.md#federation-graph-refinements-findings-of-2026-10-17-apollo-router-v2180), the runtime commits lab commit `ac35ce686cb62f08ca7e010d8e146868b4adfe81` and lab commit `f86e4a61ead2f752a212931d0ae0352c820548ef`, the machine-local Job record of the design talk and [D043](DECISIONS.md#d043---federation-graph-refinements-mapping-outcome-asset-id-parent-timeout-and-nullable-resolution-2026-10-17-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** The Cosmo and Hive routers are built and show another result for a dead subgraph; a client misreads a null `resolution`; a long parent chain or a repeated parent makes caching worth adding; or the timeout needs to differ by environment.

## Missions larger release: D044

**Rationale status.** Explicit.

**Decision / what we do.** Replace D027's range of 20..100 missions per release by at least 20, with a curated canon core and generated missions labelled synthetic; publish release 1.1 as an append to release 1.0 with 300 missions (31 carried unchanged, 57 new curated canon missions from TNG Seasons 4 and 5, 45 generated maintenance missions and 167 generated routine missions), six pages of 50, deliberate edge cases recorded in a ledger, and crew references numbered by the generator.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the aim, data big enough that a single call does not get everything, so that the approaches can show differences, with more missions and edge cases; the choice to amend the range (option B); the canon core widened with Season 5, if that was not too taxing; the maintenance and repair work, not carried by senior officers, with an imagined complexity although there is no complexity field; and the append rule: no insertion in time order, append, because the mission ids need not follow a sequence and the stardates can still be correct. On a returning visitor they ruled that P is for Personnel and that a person who returns to the Enterprise is not part of the crew but an outsider, entity because an outsider could be anything, a human included, so the returning Wesley Crusher of two Season 5 missions is an O participant. At the build they chose, by selecting options in a dialog, to accept the repair-cost exception, to write six real pages and not to re-read the carried missions' other source observations.
- Source-stated: 31 missions fit one call and a 100-mission release would barely exercise paging; D033 says the change id, not the timestamp, orders mutations, which makes an appended entry with an older timestamp legal; the generator reproduces the carried missions byte for byte, which the release test compares; Memory Alpha stardates of the carried missions were re-read and match.
- Agent-reasoned: appending keeps every 1.0 identity, which the earlier MAJOR proposal would have changed; independent category streams keep an added category from shifting another; marking edge cases in a ledger makes them testable instead of accidental; senior officers are few in the 800 (16), so staffing by rank makes most generated missions have no senior officer, which is realistic and changes the shape of the senior-officer question.

**Alternatives.** Stay at 100 or fewer missions (rejected by the lead developer's choice). A MAJOR release 2.0 with all new identities and a change-id order by time (proposed by the worker, replaced by the lead developer's append ruling). One `missions.xml` as in 1.0 (not chosen: its page metadata would not describe 300 missions). D027's maintenance band for every repair (not chosen). Re-reading the other source observations of the 31 carried missions before the build (not chosen).

**Tradeoffs or costs.** Most missions are synthetic, so the dataset says so in its provenance and nothing in it is a claim about canon orders or finance. A change entry can be older than a lower change id, which a client sorting by id and a client sorting by time read differently. The expected outcomes of the federation acceptance suite, the Missions adapter's own stub and the mapping release still describe release 1.0 and need a later re-derivation.

**Evidence.** The [Missions design](../docs/MISSIONS-V1-DESIGN.md) (section Release 1.1), the manifest and provenance of release 1.1 under `uss-enterprise/missions/datasets/releases/1.1/`, the data acceptance tests of the Missions component, the machine-local Job records of the scale-up talk and [D044](DECISIONS.md#d044---missions-dataset-release-11-300-missions-appended-to-release-10-2026-10-18-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A client needs time-ordered change ids; the mapping release for the new references shows that the numbering needs another rule; the share of synthetic missions hides a result the comparison needs; or a larger release is wanted.

## Missions participant classes: D045

**Rationale status.** Explicit.

**Decision / what we do.** State what the Missions reference classes mean (C crew, P on-board non-crew Personnel, O outsiders) and publish Missions dataset release 1.2 as an append to release 1.1 that reclassifies the participants by those meanings: outsiders become O, placeholders become civilians of `personnel-v2-large-004` as P or named synthetic outsiders as O, every identity of 1.1 is kept, and 108 appended UPDATED entries record the correction.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the definitions (P is Personnel, the people on the Enterprise who work there and are not crew members; O is not for groups and objects but for Outsiders, the Others, and says entities because Star Trek has all sorts of creatures, humanoids and other entities), the finding that the Tau Cygna V colonists should have been O, the ruling for clean data (option A) and the order to write the participant clean-up Job for Missions now. At the build they chose by selecting dialog options: appended correction entries as release 1.2 and not direct edits as a MAJOR release, the same correction for the 31 carried missions, and outsiders by necessity for canon on-board civilians missing from the roster.
- Source-stated: only two of 118 distinct P references resolved to the roster, about 100 were placeholders, and the mapping refuses an O class; the Missions contract enforces no lifecycle transitions, so an UPDATED entry with an unchanged status is a valid audit entry (the design, section Resource integrity); D033 orders mutations by change id.
- Agent-reasoned: the rules that give each generated mission its class by its title and template (drills, screening, technical and scientific work with civilians as P; transfers, escorts, relief, clinics, searches and patrols with outsiders as O), the exclusion of the 20 roster civilians who are also crew in the legacy Crew system from the P draws (so a person is never both an assigned crew member and a participant of one mission), the performer and orderer of the correction entries (Data and Riker, synthetic), the numbering of the new references and the sizes of the outsider pools.

**Alternatives.** Direct edits of the mission records as a MAJOR release 2.0 (offered to the lead developer, not chosen). Keeping the 31 carried missions as the legacy system's historical misclassification (offered, not chosen). Replacing the off-roster civilian by a roster civilian (offered, not chosen). A change to Personnel so that the missing civilians exist (kept out of scope by the lead developer's order). Reusing the suffixes of the old references for the new classes (not chosen: a matching suffix would suggest a correspondence, D021).

**Tradeoffs or costs.** The correction entries are synthetic audit entries; a client that reads the history sees 108 clean-up updates and a later `lastUpdated` for those missions. Most P participants of generated missions are drawn at random from the roster, so their roles are plausible rather than meaningful. The federation mapping release, the stack and the acceptance outcomes still describe release 1.1 or 1.0 until their own Jobs.

**Evidence.** The [Missions design](../docs/MISSIONS-V1-DESIGN.md) (sections The reference classes C, P and O and Release 1.2), the manifest and provenance of release 1.2 under `uss-enterprise/missions/datasets/releases/1.2/`, the data acceptance tests of the Missions component, the machine-local Job records of the Federation thread and [D045](DECISIONS.md#d045---missions-dataset-release-12-participants-reclassified-as-p-and-o-2026-10-19-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A later Personnel snapshot adds the on-board civilians who are missing, so that their references become P; the mapping release shows that the draws need another rule; or the comparison needs participants with meaningful roles.

## Federation question 6: D046

**Rationale status.** Explicit.

**Decision / what we do.** Answer baseline question 6 over the commanding officer and the assigned crew, in three counts (confirmed with a senior officer, confirmed without, unconfirmed) and one percentage of the confirmed missions (one decimal, half up); treat a PLANNED mission as unconfirmed unless it already has a confirmed senior officer; leave CANCELLED missions out of the population and report their number beside the answer; derive the expected answers by script from the released files.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the honesty rule and the shape of the answer (to be honest, an unconfirmed mission counts neither as having a senior officer nor as not having one; the answer shows the number confirmed with a senior officer, the number confirmed without one, the number unconfirmed and the percentage of the confirmed); the rounding, half up; the commanding officer, who is assigned too, not as a member of `assignedCrewIds` but because someone assigned them to the mission or they volunteered; the first rule for a mission with nobody at all (D) and its widening to every PLANNED mission, because the rule is consistent only that way; and the cancelled missions, on which they were undecided and asked what purpose it serves to know whether senior officers are assigned to them, then agreed with the answer and asked for it to be recorded.
- Source-stated: the commanding officer is a separate field and is never also in `assignedCrewIds` (0 of the 27 missions of the small data that have one), and the contract requires one from AUTHORIZED on; with the commander left out the four crew-less missions counted as confirmed without; the only confirmed-without mission of the small data was PLANNED and partly staffed, so "without" was a premature no; the graph has no aggregate field, so the client counts. An estimate given with the cancelled-missions ruling (28, 0 and 2) was wrong, and the script derived 27, 0 and 3; on the large data the script derives 182, 65, 26, 73.7 percent and 27 cancelled missions, and the figures did not change when Missions release 1.2 and mapping release 1.3 replaced release 1.1 and mapping 1.2.
- Agent-reasoned: the bucket rule behind the three counts was put to the lead developer with the question and accepted by their answer as a whole; the reason a cancelled mission is out (it never ran, so its staffing describes a dropped plan and counting it either way answers another question) was offered to them and they agreed with it.

**Alternatives.** The percentage over all missions whatever their status (the decision of October 15, superseded). Counting an unconfirmed person as senior or as not senior, and a lower-bound reading (rejected by the lead developer's honesty rule). Leaving the commanding officer out (their own earlier ruling, replaced). Counting a mission with nobody at all as unconfirmed only while PLANNED (rule D, widened). Counting CANCELLED missions by their staffing (the lead developer was undecided and chose to leave them out).

**Tradeoffs or costs.** The answer is three numbers and a percentage instead of one number, and a client that wants the percentage over all missions must compute it. With the commander counted and the PLANNED rule, the share of unconfirmed missions depends on how many missions are still planned. On the large data only 16 of the 800 crew are senior, so most generated missions have no senior officer; the question changed character from a nearly all-yes answer to a spread.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#the-query-workload), [the acceptance README](../federation/acceptance/README.md#question-6), `federation/acceptance/derive_expected.py` and `expected-outcomes.json`, the runtime commits lab commit `0439bcf5ead7c8aa5ce16813f8d69d5acf0176bd`, lab commit `184f7002290451f5e65a35019c476e410c5b23ac` and lab commit `d9f27ddcce0375d077f4e840813bf22a7375a179`, the machine-local Job record of the design talk and [D046](DECISIONS.md#d046---federation-question-6-the-people-counted-the-three-counts-and-the-status-rules-2026-10-18-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** A baseline question needs the percentage over all missions; the PLANNED or CANCELLED rule hides a result the comparison needs; or the agent corpus asks question 6 in its natural form and needs another accepted definition of senior.

## Federation Cosmo router: D047

**Rationale status.** Explicit.

**Decision / what we do.** Build the Cosmo router self-hosted with local composition and no Cosmo Cloud, on the newest router and `wgc` at build time pinned by digest, with the execution config committed only because it is byte-reproducible, the smallest error-passthrough setting, the same 5 second subgraph timeout as Apollo, port 8171 in the same whole-stack compose with a router switch, the licence re-checked at the pinned source, telemetry off, and subgraph retries off for the comparison.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer, their answers of 2026-10-18 to the nine design points: the pieces, local composition and no control plane, the comparison on equal terms for this round; the version, the newest router and `wgc` at build time; the execution config committed only if it is byte-reproducible, the same rule as Apollo; the error passthrough as the smallest setting; the same 5 second timeout and the dead-adapter check; the port and the stack; the licence re-checked at the pinned version; the telemetry setting of both routers, to be noted and kept alike before test runs; the point already in the Job, which holds the effort capture, the shared suite and the matrix rows; and, decided the same day, the retry setting, kept off and recorded that way. The answers to the nine points are kept in the local design record of the federation, restored there on 2026-10-20 from the conversation after the Job record that first held them was pruned.
- Source-stated: Rover composes locally without GraphOS and `wgc router compose` composes locally without the control plane; with no graph token five Cosmo Cloud features are off and the router says so; the pass-through mode is the smallest setting that delivered `extensions.code`; with the default retry (5 attempts, 3 seconds, a random wait up to 10 seconds) and a 5 second timeout the answer for a stopped adapter took 5.1 seconds in one run and 21.0 in the next; the pinned Apollo router has no subgraph-request retry setting (its configuration schema lists only reload retries); the licence and telemetry setting were read at the pinned version's source.
- Agent-reasoned: committing the execution config under the freshness-test rule that Apollo's supergraph follows keeps the two routers alike; the retry setting went in as the build's addition, outside the first points, and became the lead developer's ruling when they agreed.

**Alternatives.** Cosmo Cloud, Studio or the CDN (deferred to a later round, not decided). Retries left on (not chosen: the figures would measure Cosmo's retry policy and not its routing). The default error mode (not chosen: it wraps the subgraph's errors one level down and the code is not at the top level). A pre-release router (not chosen).

**Tradeoffs or costs.** Retry is a real resilience feature in Cosmo's favour that the comparison switches off, so it must be reported with the figures. Which failures Cosmo retries is not verified. Cosmo's composition output depends on the order of the subgraphs, so the order is fixed.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#the-cosmo-router-of-2026-10-18), [the Cosmo router README](../federation/routers/cosmo/README.md), the runtime lab commit `04e111ffd6faccb75198ce41949ee43f66a37633`, the machine-local Job records of the design talk and [D047](DECISIONS.md#d047---federation-cosmo-router-self-hosted-design-pinned-versions-and-subgraph-retries-off-2026-10-18-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** The managed Cosmo pieces are compared; resilience is tested deliberately with retries on; or a newer router changes a setting or the licence.

## Federation class mapping: D048

**Rationale status.** Explicit.

**Decision / what we do.** In the crew mapping process, refuse every O reference by class, allow P references that map to non-crew people of the Personnel v2 roster (by the participant exceptions table or an exact name), and, from mapping release 1.3, make a P that nothing places a build failure.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: that O references are refused by class, to be recorded in the scale-up design record of that Job, and that P must be allowed; the definitions that give the rules their meaning (P is Personnel, the people on the Enterprise who work there and are not crew members; O is not for groups and objects but for Outsiders, the Others); a P whose only exact name match is a crew member is a failure and not UNMAPPED (point f.1); the six redundant exception rows are cleaned up only when a later mapping release touches that table anyway (point 3); and, through a dialog, the exception of P-1003 to PRS-3001.
- Source-stated: the Missions design says an O reference carries no Personnel membership claim and that explicit mappings may relate historical P and later C references to one PRS identity; the returning Wesley Crusher of two Season 5 missions is an O participant and the same human as a crew member, so a name-based rule would link an outsider to a crew identity; D021 says matching suffixes imply no correspondence; release 1.2 maps two participants and refuses 28 O references, release 1.3 maps 58 P references (57 by exact name) and refuses 153 O references.
- Agent-reasoned: refusing by class is safer than a table of exceptions, because it protects every outsider who shares a name with a roster person without anyone listing them; the strict mode of release 1.3 follows from the lead developer's definition that every P is on the roster, and it went in under the lead developer's go at the preview.

**Alternatives.** Exception rows for the outsiders who share a roster name (not chosen: it protects only the ones someone remembers). Mapping an O by name when no roster person has it (not chosen: the class carries no membership claim). Keeping an unplaced P as UNMAPPED (kept in release 1.2, which is immutable; replaced by the failure in 1.3). Exposing a resolved participant in the graph now (deferred by the lead developer until the agent corpus needs it).

**Tradeoffs or costs.** An outsider is never mapped even if the roster later gains the same person, so a change of class needs a new Missions release and a new mapping release. A canon on-board civilian missing from the roster stays an outsider. The six old exception rows still describe the first recipe.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#shared-identity), [the crew mapping README](../federation/personnel-mapping/README.md), the runtime commits lab commit `60ac091090f41690097075851705a4c124036176` and lab commit `0b7ee2481dc7b9e5af7f30a364abef04e678714d`, the machine-local Job records of the scale-up and [D048](DECISIONS.md#d048---federation-mapping-of-the-missions-reference-classes-o-refused-by-class-and-p-to-non-crew-personnel-2026-10-19-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** The graph exposes a resolved participant; the roster gains the missing civilians; or an outsider has to become a member of the roster.

## Federation Personnel cache: D049

**Rationale status.** Explicit.

**Decision / what we do.** Keep the 5 second subgraph timeout; warm the stack before the shared acceptance suite measures and report the cold figure as a finding; and make the Personnel adapter read each immutable snapshot once, in pages, keyed by `datasetVersion`, serving its entity lookups from memory after one probe per batch, with no read at adapter start.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the options A and C; that nothing is read at start (point d); and the earlier condition for caching, a later improvement when and if the need becomes apparent, which the need now met.
- Source-stated: on the large data a page of 100 missions with assets, commanding officer and crew took 5.1 to 5.6 seconds on the first pages after a start and 0.8 to 3.5 seconds warm through both routers; the main cost was one SOAP call per person; after the cache, 24 pages on a cold stack carried no errors entry, a cold first page took 3.6 seconds (Cosmo) and 4.2 seconds (Apollo) in the measurement and 1.96 and 3.11 seconds in the stack gate, and warm pages took about 0.5 seconds; a Personnel v2 snapshot is immutable by its contract and every answer names its `datasetVersion`.
- Agent-reasoned: the cache keyed by `datasetVersion` with a probe per batch keeps an outage an outage (a copy is never served without a probe that just succeeded); smaller pages hide the problem and higher CPU limits change the benchmark environment; a read at start would add margin to the first page but blur the cold-start metric, which the lead developer accepted.

**Alternatives.** Smaller pages (not chosen: they hide the problem). Higher CPU limits for the adapters (not chosen: a change of the benchmark environment). Both were set aside by the lead developer's choice of A and C. A higher timeout (rejected: the 5 seconds is the lead developer's value). A read of the snapshot when the adapter starts (rejected for now).

**Tradeoffs or costs.** The adapter holds state, one snapshot at a time. The first page of a cold stack still takes 3 to 4 seconds, about one second under the timeout on Apollo, so a slower machine could meet the stop again. The warm-up means the suite reports correctness and not cold latency; the cold figures are facts, not assertions.

**Evidence.** The [federation design](../docs/FEDERATION-DESIGN.md#what-is-built), [the Personnel adapter README](../federation/adapters/personnel/README.md#the-snapshot-in-memory), [the acceptance README](../federation/acceptance/README.md#paging-the-warm-up-and-the-timeout), the runtime commits lab commit `32279dc6bb407a9b8a0d8be5f6e13f5d92a015d4` and lab commit `e68dbc0f06a1c41b31832a1a9e5b4f1193a9e025`, the machine-local Job records of the scale-up and [D049](DECISIONS.md#d049---federation-personnel-adapter-snapshot-cache-and-the-warm-up-of-the-acceptance-suite-2026-10-19-accepted-scope). This explanation grants no approval and implements nothing.

**Revisit when.** Acceptance runs fail at the 5 second stop; the benchmark protocol needs a cold-start metric that the cache changes; or the Personnel snapshot grows far beyond a thousand members.

## Deprecation: D050

**Rationale status.** Explicit.

**Decision / what we do.** Keep Crew & Personnel v1 in the repository, frozen by checksum and marked deprecated: readable and runnable as a reference, with no new work built on it.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer (2026-10-21): the whole of Crew & Personnel v1 is to be frozen and should not be used any more, reading it is fine, and freezing or deprecating it is fine; and, for dataset 003, a hash that keeps it the same, because no one ever changes it, instead of carrying its CPython 3.12.14 reproducibility exception.
- Source-stated: carried systems still depend on v1. The released dataset 003 is read by the federation crew-mapping pins and tests and by the Missions data test and is an input of the Personnel v2 snapshot `personnel-v2-large-004`, and the Missions and Personnel v2 validators import the shared helper `xml_validation.py` from `crew-personnel/validation/`. The federation stack does not run the v1 service, and the study's MCP servers do not use it.
- Agent-reasoned: a freeze makes every change to v1 fail the continuity check and puts any change of the manifest behind the sealed Approve, which is as close to "no one ever changes it" as the framework allows; Git itself cannot forbid a commit.

**Alternatives.** Removing v1 (rejected: it would break the carried systems above). Regenerating dataset 003 under the pinned CPython 3.12.14 and carrying the lab's legacy exception (rejected by the lead developer in favor of the checksum). Carrying the proposed copy of 003 beside the released one (not carried: its nine files are byte-identical to the released ones and nothing reads them; the lab keeps it). Moving the shared helper out of `crew-personnel/` now (deferred: nothing needs a change there yet).

**Tradeoffs or costs.** The repository proves that dataset 003 is unchanged, not that it can be rebuilt. The shared helper is frozen with v1, so a change that Missions or Personnel v2 might need there must first move it. The specification `docs/CREW-PERSONNEL-V1.md` carries the deprecation note but is frozen only by a later change, because a frozen path cannot enter a checkpoint.

**Evidence.** The import under open rows in commit `bb1231475c7be41a3c33a28825249db91e889b29`, the freeze of the laboratory's frozen set in commit `8224a5784dd7c6156f205e2949a1b00e14b6136d`, the rows of the [project's classification table](ARTIFACT-CLASSIFICATION.md), the frozen manifest and the migration path map and decision map (residue R-A) in the private provenance record. This explanation grants no approval and implements nothing.

**Revisit when.** A carried system needs a change inside `crew-personnel/`, the shared helper needs a change, or nothing depends on v1 any more and it could be removed.

## Set-up imports: D051-D053

**Rationale status.** Explicit.

**Decision / what we do.** Import the lab's remaining code content as set-up commits outside the checkpoint workflow under a narrow, enumerated exception (D051); make exactly one more such commit to start the recovery chain (D052); and rewrite the commit email of the history once for the lead developer's privacy (D053). Everything else follows the checkpoint workflow.

**Why.** The reasons are labeled by who gave them.
- Supplied by the lead developer: the exception with the scope as drafted (2026-10-22), clarified the same day as explicit authority, exact content and a definite endpoint; the one recovery-chain commit as the option recorded as D052 (2026-10-22); and the rewrite (2026-10-23), with the statement that Historical Truth about the repository and who authored it is kept and that the rewrite only protects their privacy.
- Source-stated: importing everything through the workflow, chosen on 2026-10-21, met two kinds of friction in the first real imports: three template defects, fixed in template releases 0.2.1 to 0.2.3, and the recovery chain, which a project adopts in one change naming its latest runtime commit, while this repository had no runtime commit before its first runtime import; the three system workers stopped on it on 2026-10-22. Once the classification table had runtime rows, every prepare required the committed `implementation_checkpoint` row in Progress, which only the adoption adds, so no transaction of any Job could be prepared, and a template upgrade is itself a prepared transaction. The first commits carried the lead developer's personal email, and a push makes every commit's email visible.
- Agent-reasoned: running every check the workflow would select by hand on the exact tree, and approving the exact tree and message, keeps the substance of the workflow's evidence and approval while the tool cannot run; an enumerated list with a definite endpoint keeps the exception from becoming a habit; a rewrite before the documents and devlog entries are imported changes the fewest citations.

**Alternatives.** Importing every system through the workflow under temporary open rows with no runtime boundary, as Crew & Personnel v1 was (the earlier choice, replaced by D051 for the remaining imports). Adopting the recovery chain first (not possible: it names a runtime commit that did not exist yet). For D052, waiting for a template fix (rejected: a template upgrade is itself a prepared transaction, so it could not unblock this repository); the other option the worker put forward is not recorded in the inspected sources. For D053, keeping the history as it was (rejected by the lead developer), or rewriting just before the first push (rejected in favor of rewriting before more records cite commit ids).

**Tradeoffs or costs.** Seven commits of the repository were made outside the checkpoint tool, so their evidence is the by-hand record kept in the private provenance repository and not a sealed packet; their messages and the recovery-chain devlog entry say so. The rewrite changed every commit id of the first 13 commits, so any copy of an old id outside this repository must be read through the private old-to-new table, and the old history remains in private backups that are never pushed.

**Evidence.** The set-up commits `7ff9121406f3f9dfa0221cfe1abbb770780eaa44`, `c29f73d72574d0a8c753b09d5c2615ecf98f89e0`, `23faf6932b1ab6f91f362effa829d51c540aeedf`, `e958c9554f5fe330285ee6c71a02ebff548b097d`, `94f7e34494876b2953ee099b1b2a7653f380d91d` and `3acf04447a5095316168959bafa21daa4180e6dc`; the recovery-chain commit `e7853c93f4214f859c92ec85f71f8960c6290caf` and the [devlog entry](../devlog/2026-10-22T2342Z-recovery-chain-adopted.md) it added; the reconstruction contract's fact in commit `49ca89b7e119de096e7c8d21844b3cfd7ca09c50`; the deadlock in `governance/tools/lifecycle/checkpoint_lifecycle.py` (`preparation_gate`, `committed_checkpoint`); and, in the private provenance record, the exception's record, the by-hand evidence of each commit and the verification of the rewrite (13 commits, same names, dates, messages and trees apart from the D052 commit, no old email left on main). These decisions were recorded on 2026-10-24 in the import of the project's records, after the commits that put them into effect, as D051 itself foresaw. This explanation grants no approval and implements nothing.

**Revisit when.** Never for new work: the endpoint of D051 is reached and D052 and D053 were one-time. Reread them if a later record seems to rely on a set-up commit as if it had been sealed, or if the old history must be consulted.
