# Project Constraints

The project's own active MUST and MUST NOT rules. They add to the framework's [Governance Constraints](../governance/CONSTRAINTS.md) and never override them: where the two disagree on the governed workflow, the framework's rules prevail. The decisions behind these rules are recorded in [Decisions](DECISIONS.md).

This file belongs to the project. An upgrade of the framework replaces `governance/` and never touches it. Write each rule as a section with a short heading, state it with MUST or MUST NOT, and record the decision behind it in the project's decision registry in the same change. A project that has no rules of its own yet leaves the section below as it is.

## Project rules

### Legacy systems stay unaware of the integration layer

**The integration platform must adapt to the enterprise; the enterprise must not be redesigned to accommodate the integration platform.**

Integration technologies MUST adapt above the legacy-system boundary. Legacy systems MUST remain unaware of GraphQL, federation, MCP and AI unless the simulation explicitly defines otherwise. Do not retrofit them for an integration technology's convenience. Legitimate fixes to a legacy system's own bugs or contract compliance remain possible. This makes explicit the stable-enterprise boundary in Architecture and D010-D011.

### Contracts, ownership and reproducibility

- Frozen contracts/specifications MUST outrank implementation convenience; implementations MUST adapt to them. Crew & Personnel Contract v1 is frozen (D014 freeze status and [specification](../docs/CREW-PERSONNEL-V1.md)).
- Published immutable dataset versions MUST NOT be mutated or reused for different content. Content changes require a new datasetVersion; breaking wire changes require a new contract/namespace version. Dataset versions do not imply freshness. Consumers MUST restart pagination on version change (Architecture; component specification).
- Cross-system external-ID mapping MUST belong to the shared Integration & Benchmark layer, including schema, releases, validation and interpretation. Individual legacy systems and adapters MUST NOT invent competing reconciliation rules (D015).
- Authoritative ownership MUST NOT be duplicated merely to simplify integration: Personnel owns personnel facts/reporting; Mission Operations owns mission participation/assignments (D015).
- Shared acceptance correctness MUST precede performance comparison; adapters MUST preserve shared scenario/fixture semantics. MCP/AI evaluation remains separate from router benchmarks (D002, D005-D006, D011).
- Generated Java MUST stay under ignored `target/` and MUST NOT be committed or used as a source of truth; caches, logs and transient audit files are not engineering specifications (D016; repository ignore conventions). The framework's rule on generated and transient artifacts, the Mission Control datasets included, is in the [Governance Constraints](../governance/CONSTRAINTS.md#contracts-ownership-and-reproducibility).

### Bounded-context semantic disagreement

Semantic disagreement between bounded contexts MUST NOT be erased merely because a canonical model could make them agree. Preserve each owner's meanings, identity lifecycle and classifications; integration MUST represent disagreement and explicit mapping outcomes rather than silently reconciling source facts. Personnel MUST NOT depend on Missions C/P/O identity or classification, and matching ID suffixes MUST NOT imply correspondence (D021).

### Crew & Personnel runtime

D016 establishes Java 17, Maven, WSDL-first JAX-WS and Apache CXF 4.2.3 (4.2.x), with no Spring application framework (including Spring Boot or Spring Web Services). Frozen WSDL/XSD MUST drive generated types/interfaces. The deployment WSDL MUST import the frozen binding and add only deployment import/service/port/address metadata, without local types/message/portType/binding declarations.

Startup MUST validate the selected registered immutable snapshot before publication, including integrity, schema/version, counts, unique IDs and supervisor readiness. Snapshots MUST NOT be merged. D017 permits CRLF-to-LF normalization for hashing ONLY against canonical Git-content SHA-256; parser input remains the original bytes. No broad whitespace/XML normalization or dataset rewrite is permitted.

Frozen `maxLength=100` remains unchanged. Configured Java 17 validation MUST honor XML code-point length; the known .NET offline-validator limitation does not change the contract. See [Integration notes](../docs/INTEGRATION-NOTES.md).
