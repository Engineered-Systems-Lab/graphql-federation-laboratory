# Crew & Personnel dataset 003 design

Later status (2026-10-01): the lead developer's approval now releases the exact proposal bytes under `datasets/released/crew-v1-large-003/` and authorizes runtime registration/loading, retaining 002 as default. See the D016/D017 extension in [Decisions](../project-governance/DECISIONS.md) and current [Progress](PROGRESS.md). The proposal-phase scope/deferral statements below are preserved as historical design context; they no longer describe the current release/runtime state. The recipe and package format remain unchanged.

Status: implementation-authorized proposal, 2026-10-01. The lead developer authorized completing deterministic packaging definitions and implementing/testing an offline generator. The packaging completion below supersedes the original design-only status; it does not freeze, release, register or accept 003 for runtime use. No staging, commit or lab log is authorized. Current implementation evidence is owned by [Progress](PROGRESS.md).

## Authority and compatibility findings

Read with [AGENTS](../AGENTS.md), [Constraints](../project-governance/CONSTRAINTS.md), [Architecture](ARCHITECTURE.md), [Decisions](../project-governance/DECISIONS.md), the [frozen v1 specification](CREW-PERSONNEL-V1.md), and the current uncommitted [checkpoint workflow](../governance/CHECKPOINT-WORKFLOW.md). D014 permanent identity, D015 ownership, D017 hash rules and G018 checkpoint authority remain binding. Uncommitted design preparation alone warrants no historical transition log under [the devlog rules](../devlog/README.md).

The requested personnel choices fit v1: positionTitle is free nonblank text, rank does not dictate reporting, cross-department supervisors and multiple roots are permitted. Wesley's ENSIGN / Acting Ensign and Guinan's complete 002 representation remain valid. Data's changed primary assignment is permitted in a new immutable content version, without editing 001/002. Personnel is not a residency, family, physical-presence or mission-availability registry.

One material implementation conflict: [Dataset.java](../uss-enterprise/crew-personnel/src/main/java/lab/enterprise/crew/Dataset.java) registers only 001/002 and requires an entire snapshot in one list response, offset 0, limit 20, hasMore=false and totalCount <=20. The [frozen XSD](../uss-enterprise/crew-personnel/contracts/crew-personnel-v1.xsd) independently permits at most 100 records per list response. An 800-record response is invalid. The paged storage proposal below resolves the design issue without reopening v1; future aggregate loading requires separately authorized implementation and review of D016's registered-dataset policy. No runtime change is made here.

## Profile and scope

Proposed datasetVersion: `crew-v1-large-003`; human name: Enterprise-D Personnel 800. Exactly **800 personnel records** is a deliberate synthetic lab scale for pagination, filtering, reporting traversal, future federation and benchmarks. It is not a canonical population statistic.

Reference frame: Enterprise-D, 2366, immediately after TNG Season 3's `Ménage à Troi` / Wesley's promotion. This is the lab's chosen reference frame, not exhaustive canon reconstruction. Approximately 1,012 persons is a synthetic ship-complement assumption supplied for context, neither repository-established fact nor a claim of Star Trek canon. The conceptual remainder is approximately 212 non-personnel/dependents/guests. No records or invented employment facts are created for that remainder. Even ON_LEAVE/INACTIVE personnel remain personnel; 800 cannot be used to infer who is physically aboard. Civilian employees with real modeled jobs qualify; civilian residency alone does not.

## Named seed roster

Retain all twelve [002 records](../uss-enterprise/crew-personnel/fixtures/canonical/crew-v1-small-002.xml), including the already synthetic Mara Venn and Elias Renn. Their identities and all fields remain exactly as 002 except Data's department/title below. Add two recognizable background names; the rest are 786 deterministic synthetic personnel. These additional assignments/ranks are lab choices, not researched biographical assertions. No external canon research is necessary for this proposal.

IDs and supervisor entries below include the `CRW-` prefix. A dash means omit supervisorCrewId. All seeds are ACTIVE except Mara (ON_LEAVE) and Elias (INACTIVE).

| ID suffix | displayName | Rank | Department | positionTitle | Supervisor suffix |
| --- | --- | --- | --- | --- | --- |
| 1047 | Jean-Luc Picard | CAPTAIN | COMMAND | Commanding Officer | - |
| 1048 | William Riker | COMMANDER | COMMAND | First Officer | 1047 |
| 1049 | Geordi La Forge | LIEUTENANT_COMMANDER | ENGINEERING | Chief Engineer | 1048 |
| 1050 | Data | LIEUTENANT_COMMANDER | SCIENCE | Science Department Lead | 1048 |
| 1051 | Mara Venn | LIEUTENANT | FLIGHT_OPERATIONS | Shuttle Pilot | 1048 |
| 1052 | Elias Renn | ENSIGN | ENGINEERING | Engineering Technician | 1049 |
| 1053 | Beverly Crusher | COMMANDER | MEDICAL | Chief Medical Officer | 1047 |
| 1054 | Deanna Troi | LIEUTENANT_COMMANDER | MEDICAL | Ship's Counselor | 1047 |
| 1055 | Wesley Crusher | ENSIGN | OPERATIONS | Acting Ensign | 1050 |
| 1056 | Guinan | CIVILIAN | OPERATIONS | Bartender | - |
| 1057 | Reginald Barclay | LIEUTENANT | ENGINEERING | Systems Diagnostic Engineer | 1049 |
| 1058 | Worf | LIEUTENANT | SECURITY | Chief of Security | 1048 |
| 1100 | Miles O'Brien | CHIEF_PETTY_OFFICER | OPERATIONS | Transporter Chief | 1048 |
| 1101 | Sonya Gomez | ENSIGN | ENGINEERING | Engineering Officer | 1049 |

Data intentionally leads synthetic Science instead of his 001/002 Operations assignment / canonical Operations Manager role. His LIEUTENANT_COMMANDER rank stays unchanged. Wesley intentionally keeps ENSIGN / Acting Ensign and his reporting to Data (now cross-department); this does not assert exact post-promotion canon. Guinan stays CIVILIAN / OPERATIONS / Bartender / ACTIVE, no supervisor recorded. O'Brien serves as the lab's Operations reporting lead while retaining Transporter Chief as his primary position. Department leadership here is a generation rule, not a new wire field or authorization role.

## Exact distribution

Counts include seeds. Columns use the frozen rank order: CAPTAIN, COMMANDER, LIEUTENANT_COMMANDER, LIEUTENANT, ENSIGN, CHIEF_PETTY_OFFICER, CREWMAN, CIVILIAN. Whole numbers are workload choices for coverage and broadly plausible staffing, not measured proportions.

| Department | CAPTAIN | COMMANDER | LIEUTENANT_COMMANDER | LIEUTENANT | ENSIGN | CHIEF_PETTY_OFFICER | CREWMAN | CIVILIAN | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMMAND | 1 | 1 | 2 | 6 | 4 | 2 | 4 | 0 | 20 |
| OPERATIONS | 0 | 0 | 1 | 18 | 30 | 20 | 75 | 6 | 150 |
| ENGINEERING | 0 | 0 | 3 | 35 | 45 | 25 | 112 | 0 | 220 |
| SCIENCE | 0 | 0 | 3 | 30 | 35 | 8 | 58 | 6 | 140 |
| MEDICAL | 0 | 1 | 3 | 16 | 15 | 8 | 43 | 4 | 90 |
| SECURITY | 0 | 0 | 0 | 12 | 20 | 12 | 76 | 0 | 120 |
| FLIGHT_OPERATIONS | 0 | 0 | 1 | 12 | 11 | 5 | 27 | 4 | 60 |
| Total | 1 | 2 | 13 | 129 | 160 | 80 | 395 | 20 | 800 |

Subtract the seed counts from each cell, then allocate background slots in table row order, column order, and zero-based within-cell ordinal. Negative residuals fail; never silently rebalance. Residual department totals are 18, 147, 216, 139, 88, 119, 59 (786). No CAPTAIN/COMMANDER background slots result.

## Identity, generation and reporting recipe

Proposed generator identity `crew-personnel-003-v1`, algorithm identity `sha256-name-order-v1`, fixed UTF-8 seed `enterprise-d-2366-003-v1`. Use SHA-256 counter ordering as the pinned pseudorandom selection algorithm, with no language-library PRNG. The integer allocation/hierarchy rules below are independent of hash iteration order. The seed and algorithm are proposed pins for future implementation, not a claim that generator code exists.

Preserve CRW-1047 through CRW-1058 permanently. Propose new named IDs CRW-1100/1101; reserve 1100-1199 for explicitly reviewed named additions, without allocating the remainder. Background slot j (0..785) receives `CRW-` plus four-digit decimal (2000+j), exactly CRW-2000..CRW-2785. No matches for the proposed new ranges were found in current docs, component sources/fixtures or logs. Future freeze must still audit supported dataset identity history, including edge IDs CRW-0007..0010 and any concurrent reservations. Conflict means stop/review, never shift IDs opportunistically. Persist the slot-to-person ledger with the eventual release; later profiles must retain identities and never recycle an ID or rerun a changed naming algorithm onto existing identities. IDs are not external-system mappings.

Name inputs are these ordered ASCII lists, treated as invented tokens rather than demographic labels:

- Given: Aven, Bela, Cora, Daro, Evin, Fara, Galen, Hara, Iven, Jora, Kalen, Lira, Miro, Nara, Orin, Pera, Quin, Rena, Soren, Tavi, Ulan, Vela, Wren, Xara, Yori, Zena, Arlo, Brin, Ceri, Deni, Esra, Fenn.
- Family: Arden, Bex, Corin, Dalen, Eren, Falin, Goran, Halen, Irix, Jalen, Korr, Laren, Merin, Noran, Orel, Perrin, Quell, Ralin, Sarek, Toren, Urell, Varen, Wex, Xorin, Yaren, Zorin, Aster, Bren, Cadan, Doran, Elrin, Faren.

Enumerate k=0..1023: candidate is given[floor(k/32)] + one ASCII space + family[k mod 32]. Sort candidates by unsigned SHA-256 digest bytes of `seed + "|name|" + decimal(k)` (UTF-8, no newline, no leading zeroes), breaking digest ties by k. Remove exact case-sensitive duplicates and exact matches with seed displayNames, retaining the first candidate; assign the first 786 remaining names to j in order. Insufficient names fails. No locale sorting, network dictionaries, clock input or Unicode normalization. Duplicate display names remain legal under v1; avoidance here is only a profile convenience, never an identity rule.

Reporting rules, applied after all identities exist:

1. Preserve every named seed supervisor from the table. Picard and Guinan are the two no-supervisor-recorded roots; omission says nothing about physical presence or whether a real supervisor exists.
2. Reporting leads: Riker (COMMAND), O'Brien (OPERATIONS), Geordi (ENGINEERING), Data (SCIENCE), Beverly (MEDICAL), Worf (SECURITY). FLIGHT_OPERATIONS uses its lowest-ID generated LIEUTENANT_COMMANDER as lead, reporting to Riker; title `Flight Operations Lead`.
3. In each department choose its lowest-ID generated LIEUTENANT as section supervisor. Each reports to the department lead and is titled `Section Supervisor`. There is at least one such residual slot per row. These seven supervisors and the generated Flight lead are ACTIVE.
4. Sort other generated personnel within each department by crewId, after removing its lead/section supervisor. Zero-based local ordinal t divisible by 10 reports directly to the department lead; all others report to the section supervisor. This gives short, deterministic chains. Preserved named relationships are exceptions, including Troi to Picard and Wesley to Data. Rank does not constrain reporting (including Operations' officer reports to O'Brien).
5. For remaining generated records set dutyStatus by global j: j mod 20 = 0 gives INACTIVE; otherwise j mod 10 = 0 gives ON_LEAVE; otherwise ACTIVE. Lead/section-supervisor ACTIVE overrides take precedence. This supplies all statuses without interpreting status as residency, mission qualification or access permission.
6. Remaining positionTitle values by rank: LIEUTENANT_COMMANDER `Senior Specialist`, LIEUTENANT `Department Officer`, ENSIGN `Junior Officer`, CHIEF_PETTY_OFFICER `Technical Chief`, CREWMAN `Department Technician`, CIVILIAN `Civilian Specialist`. Every civilian slot represents a employed specialist role, not a dependent/guest. Department supplies job context; no unmodeled personal facts are inferred.

## Byte representation and release manifest

Fixed metadata reference clock: `2366-01-01T00:00:00Z`, an arbitrary reproducibility anchor, not the episode date. No generated field depends on dates; v1 has no timestamp field. Locale is invariant ASCII; timezone UTC; arithmetic uses exact integers. Future generator execution must pin its interpreter/toolchain and source SHA-256 in release metadata; it must use the explicit byte rules below, not serializer defaults. Host paths, current date, random UUIDs and timings never enter accepted artifacts.

Propose a new isolated canonical package for 003 containing `page-000.xml` through `page-007.xml` plus `manifest.json`. Each page is a frozen-schema-valid ListCrewMembersResponse with the same datasetVersion, exactly 100 records, totalCount=800, offset=100*p, limit=100, hasMore=true except false for p=7. The sorted 800-record sequence is sliced at those offsets. This package represents ONE dataset, not eight snapshots or a merge of versions. Validate supervisors against the complete aggregate; references may cross page boundaries. No 800-record XML response and no new public operation/schema are proposed.

XML bytes: UTF-8 without BOM, LF only, one final LF; declaration exactly `<?xml version='1.0' encoding='utf-8'?>`; root exactly `<cp:ListCrewMembersResponse xmlns:cp="urn:graphql-federation-lab:crew-personnel:v1">`. Two-space child indentation, four-space crew fields, one field per line, no blank lines/comments; explicit closing tags. Emit datasetVersion, crewMember elements, totalCount, offset, limit, hasMore in frozen order; each record uses frozen field order with omitted absent supervisor. Escape text ampersand, less-than, greater-than as `&amp;`, `&lt;`, `&gt;` respectively; leave apostrophes unchanged. Integer decimal has no sign/leading zeroes; booleans lowercase. Sort records by ordinal ASCII crewId. Prefix and formatting are pinned for fixture bytes only; SOAP acceptance remains semantic under v1.

Future manifest records format version, datasetVersion, count, full recipe inputs (including roster, distributions, name lists, identity ledger and reference clock), generator/source/toolchain identity and eight ordered page entries with relative filename, offset, count, byte length and lowercase SHA-256. Serialize manifest JSON recursively with ASCII-sorted keys, two-space indentation, separators comma and colon-space, ASCII escaping, no nonintegral numbers, LF/final LF and no BOM. Publish SHA-256 of those manifest bytes as the external package pin; the manifest must not contain its own hash. Per-page hashes transitively bind every record. Expected hash values are deliberately pending generation and independent verification; none are invented here. Use a separate 003 manifest rather than changing frozen 001/002 manifests. Accepted generation is LF byte-identical; D017 permits only CRLF-to-LF hash handling for checkout identity, not broad XML normalization or rewriting old fixtures.

## Future gates and deferred work

Before freeze, separately authorize implementation and review this proposal; pin the executable generator/toolchain and manifest schema, audit permanent identity reservations/history, then generate and independently validate. Require two clean runs with identical artifact bytes/hashes, preferably across Windows/Linux, with no clock/network inputs. Check exact count 800, every matrix cell, seed equality except the explicit Data change, ID/name algorithm outputs, all required/nonblank bounded strings, enums, status recipe, two roots, same-dataset references, acyclicity and no self-links. Assert Guinan's omission and Wesley/Data intentional assignments explicitly. Validate every page against frozen XSD, package hashes and full coverage/ordering with no duplicate/missing IDs or mixed versions. Negative tests must reject missing/tampered/reordered pages and dangling/cyclic references.

Future runtime work: register the reviewed immutable package and hashes; extend secure loading/readiness to aggregate validated pages before publication; review Maven resource packaging; remove the internal <=20 whole-snapshot assumption for the new format while preserving 001/002 loading and hashes. Keep SOAP limits/defaults, namespace, operation set and all v1 semantics unchanged. Review D016 and current-state records when support actually changes; do not silently change the default dataset. Future runtime acceptance includes Get for retained/new/inactive IDs, filters and AND combinations for every department/status, lexical pagination at limits 1/20/100, exact/beyond-end and max-int offsets, cross-page supervisor traversal, version-change restart, controlled profiles, and existing 001/002 regression checks. Shared external-ID mapping and benchmark thresholds remain separate work under D015 and Plan.

The original design preparation created no generator or artifacts. The subsequent implementation mandate authorizes the offline source, tests and proposed package described below. Freeze/release, runtime acceptance and checkpoint approval remain distinct later steps under G018.


## Deterministic packaging completion (2026-10-01)

The implementation choices below, authorized by the lead developer, resolve the original future manifest/toolchain definitions. All personnel, identity, hierarchy, distribution, XML and hash rules above remain unchanged. The proposal is generated under `uss-enterprise/crew-personnel/datasets/proposed/crew-v1-large-003/`; this isolated proposal remains outside the frozen fixtures inventory and does not establish release or runtime registration. No existing fixture or manifest is edited.

### Toolchain and source identity

The executable is the single self-contained standard-library file `uss-enterprise/crew-personnel/generator/generate_003.py`. Pin **CPython 3.12.14, stdlib-only**; generation and package validation fail closed on other interpreter implementations or versions. The pin is identical on Windows and Linux. Platform, executable path, build/compiler strings, locale, clock, environment variables and OpenSSL version are excluded from artifact metadata. SHA-256 is the standard digest, independent of its backend. Only the explicit constant recipe and this executable determine output; the design Markdown, tests, XSD validator and host environment are not implicit generation inputs.

Source identity is SHA-256 of this one file's UTF-8 bytes after replacing CRLF with LF, without any other transformation. Reject BOM and remaining bare CR. Preserve every other byte, including final newline. The manifest records the portable logical filename `generate_003.py`, never the checkout path. This is the new generator's source-identity rule, not a change to frozen fixtures or their hashing. Source edits change package identity and must be regenerated/reviewed before a release; once released, do not replace content under the same immutable dataset version.

The package contains exactly nine regular files: eight pages and `manifest.json`; no timestamps, checksums file, symlinks, directories or extra metadata. Root `.gitattributes` disables text conversion only for the new package's XML files and manifest. Package validation hashes and compares raw bytes: CRLF/BOM/reformatting is rejected, never normalized. This combines portable source hashing with preservation of exact package bytes across Windows checkouts. The generator refuses any already-existing destination, including an empty one; explicit output paths are required. No overwrite or registration option exists.

### Manifest format 1 (closed structural definition)

The following is the complete key/type definition. Objects admit only listed keys; arrays preserve the orders specified below. Integers are JSON integers (not booleans/floats); strings are exact case-sensitive values. Null is permitted only in named ledger entries. No manifest self-hash is stored. JSON serialization is the previously specified recursive ASCII-key order, two-space indentation, comma/colon-space separators, ASCII escaping, LF and one final LF. This serialization is named `dataset-003-json-v1`; the already specified XML byte serialization is named `dataset-003-xml-v1`. These are fixture format identifiers, not wire contract versions.

| Object | Exact keys and values |
| --- | --- |
| manifest | `formatVersion`: 1; `datasetVersion`: `crew-v1-large-003`; `count`: 800; `generator`: object below; `recipe`: object below; `pages`: eight page-entry objects in page-number order |
| generator | `identity`: `crew-personnel-003-v1`; `algorithm`: `sha256-name-order-v1`; `toolchain`: object below; `source`: object below |
| toolchain | `implementation`: `CPython`; `version`: `3.12.14`; `dependencies`: `stdlib-only` |
| source | `path`: `generate_003.py`; `hashing`: `sha256-crlf-to-lf-v1`; `sha256`: lowercase 64-hex digest defined above |
| page entry | `filename`: `page-000.xml` through `page-007.xml`; `offset`: page number times 100; `count`: 100; `byteLength`: raw UTF-8 byte length; `sha256`: lowercase 64-hex raw-page digest |
| seed record | All six required v1 field-name keys with exact table values; `supervisorCrewId` only when present; no extra keys |
| ledger entry | `crewId`: ID; `displayName`: assigned name; `slot`: background j or null for named personnel; `nameCandidate`: selected k or null for named personnel |

`recipe` has exactly the following keys:

- `seed`: `enterprise-d-2366-003-v1`; `referenceClock`: `2366-01-01T00:00:00Z`.
- `departments`, `ranks`: arrays in the distribution table's row and column order. `distribution`: seven arrays of eight integers, exactly the table cells (without totals).
- `givenNames`, `familyNames`: the ordered token arrays above. `roster`: fourteen seed-record objects in ascending crewId order. `identityLedger`: all 800 ledger entries in ascending crewId order, recording j and k for every generated identity.
- `positionTitles`: object mapping each of the six background ranks to the exact remaining-position titles above. `departmentLeads`: object mapping COMMAND, OPERATIONS, ENGINEERING, SCIENCE, MEDICAL and SECURITY to their named lead IDs above; generated Flight lead is described under `reporting`.
- `allocation`: object with `backgroundStart`: 2000, `backgroundCount`: 786, `namedReservation`: [1100, 1199] (inclusive), `order`: `department-rank-within-cell`.
- `names`: object with `candidateCount`: 1024, `familyRadix`: 32, `hashInput`: `seed|name|decimal(k)`, `order`: `unsigned-sha256-bytes-then-k`, `deduplicate`: `exact-case-sensitive`. The hashInput string is descriptive; actual concatenation is the recipe above.
- `reporting`: object with `flightLeadRank`: `LIEUTENANT_COMMANDER`, `flightLeadChoice`: `lowest-generated-ID`, `flightLeadSupervisor`: `CRW-1048`, `flightLeadTitle`: `Flight Operations Lead`, `sectionRank`: `LIEUTENANT`, `sectionChoice`: `lowest-generated-ID`, `sectionTitle`: `Section Supervisor`, `directLeadModulo`: 10, `localOrder`: `crewId-excluding-generated-lead-and-section`.
- `status`: object with `inactiveModulo`: 20, `onLeaveModulo`: 10, `precedence`: [`lead-section-ACTIVE`, `INACTIVE`, `ON_LEAVE`, `ACTIVE`]. Modulo tests use global j and equality to zero, with the override first.
- `serialization`: object with `xml`: `dataset-003-xml-v1`, `json`: `dataset-003-json-v1`, `pageSize`: 100, `recordOrder`: `ASCII-crewId`, `fieldOrder`: [`crewId`, `displayName`, `rank`, `department`, `positionTitle`, `dutyStatus`, `supervisorCrewId`].

The validator checks aggregate readiness and exact equality to recomputed canonical page and manifest bytes, enforcing this closed definition, recipe and source binding. A rehashed malformed or changed page does not become valid. This offline proposal validator deliberately does not implement future runtime package loading.

### Usage and release boundary

Run from the repository root with the pinned interpreter in place of `python`. Replace the quoted directory placeholders before use:

```sh
python -B uss-enterprise/crew-personnel/generator/generate_003.py generate '<new-directory>'
python -B uss-enterprise/crew-personnel/generator/generate_003.py validate '<package-directory>'
python -B -m unittest discover -s uss-enterprise/crew-personnel/validation/tests -p 'test_dataset_003.py' -v
python -B uss-enterprise/crew-personnel/validation/validate_003.py --package '<package-directory>'
```

The Python entry point additionally validates all eight pages with the unchanged frozen XSD using lxml, with DTDs and external resolution prohibited. Install `uss-enterprise/requirements.txt` (in the lab, `validation/requirements.txt`) into the pinned generator interpreter; package bytes and generator provenance are unchanged. Run existing root validation and the full Python suite separately. Independent generations must use fresh output directories/processes and compare all nine files byte-for-byte, plus the manifest SHA-256. Tests also generate from LF and CRLF source copies in different paths and with different hash seeds/timezone settings. Cross-platform support is designed into the byte rules; a Linux execution must not be claimed without running it.

The current audit found no prior allocation of proposed CRW-1100/1101 or CRW-2000..2785 in component files, docs, logs or reachable Git history. Existing edge IDs CRW-0007..0010 remain separate. Repeat the audit before eventual freeze/release to detect concurrent reservations. Frozen contracts/specifications, 001/002, runtime Java/loading/registration/defaults and command-continuity records are outside this implementation scope.
