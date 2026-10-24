# A deterministic 800-person dataset is proposed and validation becomes portable

Date: 2026-10-01T15:08Z
Subject: Deterministic 800-person proposal and portable validation
Status: Historical / non-normative
Lab checkpoint: lab commit `aa2357ae7679091c83e2d02370148c8d40760429`
Provenance: Reconstructed from this commit's dataset design, proposed manifest/generator, Progress, portability changes and Integration Notes. Git committer time is 2026-10-01T11:08:55-04:00 (15:08:55 UTC); the date is that of the combined commit. Later local transaction evidence is labeled separately below.
Migrated from lab log SD-2026.274-1508Z; originally written in the lab on 2026-10-01 (lab commit `b58c15c7361acee76e8b0a7e03b05188b9b6e53c`).

## Dataset proposal

The checkpoint committed the deterministic offline `crew-v1-large-003` proposal: 800 personnel in eight 100-record pages, `page-000.xml` through `page-007.xml`, plus `manifest.json`. The pages describe one aggregate dataset, with cross-page supervisor validation; they are not eight snapshots. The frozen 100-record response ceiling remained binding, with no 800-record response or new wire operation.

The standard-library generator identity is `crew-personnel-003-v1`, algorithm `sha256-name-order-v1`, seed `enterprise-d-2366-003-v1`, and fixed reference clock `2366-01-01T00:00:00Z`. Manifest format 1 binds recipe, all identities, page bytes/hashes and CPython 3.12.14 provenance. Canonical CRLF-to-LF source identity for `generate_003.py` is SHA-256 `2f295b9b5d9b42573265ba347774e2fd874a4a8a55a1764bb0bf7149cfe63b40`; package bytes remain raw, without normalization. Narrow attributes preserve the proposed package across checkouts.

The package pin (SHA-256 of manifest bytes, transitively binding all pages) is `c06125dbe6883981293b485497474c46a0128372056efca389d7421f35ba2690`. The committed completion report records two independent fresh CLI processes in separate directories producing 9/9 byte-identical files, 10 focused tests and 88 full Python regression tests passing. It includes LF/CRLF-source generations, negative package mutations, reporting-graph checks and all eight pages passing the unchanged XSD. Initial placement under fixtures was rejected by frozen-inventory validation and corrected to `datasets/proposed/` without weakening that validation.

Those are the then-current preparation results, including their original uncommitted-status wording and .NET warning; this reconstructed entry does not replace them with later counts. Linux execution and Java/Docker/SOAP acceptance were not rerun.

003 remained a proposal: no freeze/release, runtime registration or loading, default change, or runtime acceptance. Frozen contracts and immutable 001/002 were unchanged. Future loader work still had to aggregate pages and remove its internal <=20 whole-snapshot assumption while preserving existing loading/hashes and the public 100-record ceiling. Maven resource packaging, release review and runtime acceptance remained future gates.

## Python portability

The same checkpoint migrated active root/component validation and SOAP smoke entry points from PowerShell to Python, aligned operator examples and checkpoint profiles with Python, and introduced shared secure XML validation with pinned `lxml==6.1.1`. This dependency is for validation; the pinned generator itself remains standard-library-only. DTDs and external resolution are prohibited.

The active Python/lxml offline validator accepts 100 supplementary XML characters and rejects 101 against the unchanged frozen XSD. Integration Notes explicitly distinguish this improvement from the former .NET limitation, which remains accurate in historical reports. Portability implementation and offline checks do not establish Linux execution or new Java/Docker/SOAP acceptance.

## Later context: local checkpoint evidence

During reconstruction, the local mutable `.git/checkpoint-v1/transaction.json` packet for transaction `0251643bc820cc28438dddca42d6369c` remained in `commit-attempted` state. It records successful Git commit creation and tooling-profile preparation evidence: staged whitespace, continuity, 104 Python regressions and component offline checks passed, including the 100/101 supplementary-character boundary. Its recorded parent lab commit `641647e983e042017b9f9dd02ad0162bf44aeaa0` and tree `tree 1c18d23d9478ff503c2031f3d5a7ceeb522dafc3` match the immutable lab commit `aa2357a` commit; exact message bytes also match.

This is explicitly later local provenance, not committed contemporary evidence or a replacement for the historical 88-test claim. Post-commit Data verification/handoff did not complete; the packet contains no completed result SHA or post-continuity record. Successful commit creation is not a verified Data lifecycle. Local metadata is mutable and does not provide immutable proof of approval or lifecycle completion.
