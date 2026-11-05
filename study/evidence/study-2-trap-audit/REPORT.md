# Study 2 calculate trap audit

Read-only audit completed 2026-11-04 (America/New_York). All scripts and output stay in C:/esl/_study2-trap-audit/. No answer keys, reference directory, no-tool runs, dry runs, network, vendor/model calls, Docker or services were used.

## Summary

Inventoried **176 runs, 3,259 tool calls, 1,007 calculate calls and 3,201 stored results**. All **956 successes and 51 refusals** replay exactly under historical code. All stored-result SHA-256 checks pass. LF-normalized source hashes match all four manifests.

The scalar-id/record-field trap predates V4: once in V2 and eight times in V4, across two V4 runs. Dotted output keys, dictionary wildcards, all-page intersections and incomplete collection selection are additional mechanisms.

Counting: one occurrence per call-pattern pair, except refusal loops (one episode). Categories overlap; do not add them as independent failures. **Exposure and disclosed-partial counts include legitimate optional fields, null probes and diagnostics.** C/G = Claude Sonnet 5.5 / GPT-6.1 Sol. Outcome-linked means an observed answer lineage or contribution to a limit stop, not a controlled counterfactual.

| Pattern | Total | V1 C/G | V2 C/G | V3 C/G | V4 C/G | Outcome-linked runs | Still allowed in V4 |
|---|---:|---:|---:|---:|---:|---|---|
| P01 Successful empty outputs | 27 | 1/0 | 7/1 | 4/1 | 12/1 | V4 gamma__V05__claude-sonnet-5-5__t1 | yes |
| P02 Missing operation fields accepted (exposures) | 343 | 9/34 | 54/58 | 58/39 | 64/27 | V4 gamma__V05__claude-sonnet-5-5__t1 | yes |
| P03 Wildcard source-path omissions (disclosed) | 63 | 6/18 | 5/16 | 2/6 | 2/8 | Not established | yes |
| P04 Read lines omit field coverage (exposures) | 188 | 0/0 | 0/0 | 58/39 | 64/27 | V4 gamma__V05__claude-sonnet-5-5__t1 | yes |
| P05 Refusal recovery loops | 11 | 3/0 | 0/1 | 2/2 | 0/3 | Not established | yes |
| P06 Wrong result selection while fuller data held | 1 | 0/0 | 1/0 | 0/0 | 0/0 | V2 gamma__V05__claude-sonnet-5-5__t1 | yes |
| P07 Re-fetch of already-held data | 9 | 0/0 | 3/1 | 2/2 | 1/0 | Not established | yes |
| P08 Record field applied to scalar IDs | 9 | 0/0 | 1/0 | 0/0 | 8/0 | V4 gamma__V05__claude-sonnet-5-5__t1 | yes |
| P09 Dotted output keys fail on reuse | 13 | 1/2 | 3/1 | 2/0 | 4/0 | Not established | yes |
| P10 Object wildcard is a one-item no-op | 15 | 0/4 | 2/3 | 1/2 | 0/3 | Not established | yes |
| P11 Intersection across page partitions | 2 | 0/0 | 1/0 | 1/0 | 0/0 | Not established | yes |
| P12 Stored output truncated | 18 | 0/6 | 0/12 | 0/0 | 0/0 | Not established | yes |
| P13 Shortened intermediate consumed | 16 | 0/3 | 1/12 | 0/0 | 0/0 | Not established | yes |
| P14 Arguments silently ignored | 8 | 0/3 | 0/3 | 1/1 | 0/0 | Not established | yes |
| P15 Absent field satisfies predicate (exposures) | 39 | 2/8 | 2/9 | 7/8 | 3/0 | Not established | yes |
| P16 Fixed positions for any-element task | 36 | 0/7 | 1/10 | 10/8 | 0/0 | V3 delta__V06__claude-sonnet-5-5__t1 | yes |
| P17 Scalar comparison against collection | 3 | 0/0 | 0/0 | 1/0 | 2/0 | Not established | yes |
| P18 Contradictory any/none conditions | 1 | 0/0 | 0/0 | 0/0 | 1/0 | Not established | yes |
| P19 Null counted as set member (exposures) | 79 | 4/6 | 7/17 | 9/11 | 15/10 | Not established | yes |
| P20 Composite groups split an ID (exposures) | 6 | 0/2 | 0/1 | 0/2 | 0/1 | Not established | yes |
| P21 Long calculate output shown in full | 101 | 7/22 | 24/48 | 0/0 | 0/0 | Not established | no |
| P22 Non-numeric sum inputs skipped (disclosed) | 25 | 4/5 | 3/3 | 3/3 | 2/2 | Not established | yes |
| P23 Incomplete collection drives final total | 1 | 0/0 | 1/0 | 0/0 | 0/0 | V2 epsilon__V05__claude-sonnet-5-5__t1 | yes |
| P24 Identical calculation repeated | 1 | 0/0 | 0/0 | 0/0 | 1/0 | Not established | yes |
| P25 Wildcard used as scalar field | 3 | 1/0 | 1/0 | 0/0 | 1/0 | Not established | yes |

V1 has 40 runs per model; V2-V4 have 16 each, so raw counts are not comparable rates. V4 still allows every listed mechanism except P21. P12 observed 50k cuts are repaired, but truncation remains above 5M characters. P25 is partly repaired: wildcard filter fields without elements refuse; wildcard fields on distinct remain accepted.

## Outcome evidence and costs

**V2 Gamma V05 Claude (P06):** calls 7 and 9 already hold 300 missions. Call 25 re-fetches 200 and call 27 selects only that result. Those pages contain 577 non-null local ids (tool count 578 including null), versus 629 across all held pages: 52 local ids are omitted. Subsequent mapping and roster calculations yield the submitted 569 people and wrong_answer. One repeated fetch is observable. See proofs.json and the exact evidence appendix for calls 7, 9, 25, 27, 33 and 45.

**V2 Epsilon V05 Claude (P23):** call 18 reads two mission pages, returning 570 distinct values including null; the answer is 569 people and wrong_answer. Needed third-page reference fields are not held. This is incomplete acquisition/coverage, separated from claiming a correct alternative result id existed. Other shape errors are recovered or worked around; their individual effect on the final undercount is not established.

**V3 Delta V06 Claude (P16):** independent traversal of all 300 missions in call 15 finds 72 qualifying missions. TRANSPORT ST-00000LDBG has qualifying statuses at zero-based positions 24 and 27 in a 50-element asset list. The position-0/1/2 calculations miss it. The final answer totals 71 and omits TRANSPORT, recorded as wrong_answer. Ten fixed-position calls in this run are observed effort; exact counterfactual total savings are unknown. V4 offers any/none but still allows index probes.

**V4 Gamma V05 Claude (P01/P02/P04/P08):** calls 71-77 apply personnelId to 620 scalar ids and return zero. Shape-consistent independent intersections yield **1, 69, 2, 297, 126, 110, 11**. Corrected calls 78-80 follow, then an 80-call limit stop. **Seven wasted calls are certain; guaranteed completion after their removal is not.** The same trap occurs in V4 Delta V05 Claude call 31 and V2 Epsilon V05 Claude call 31, both runs with submissions.

Other failed-run outcomes are recorded per occurrence without causal attribution. V2 Epsilon V07 Claude, for example, submits count 38 after one path refusal although its stored query contains 39 missions. The refusal and manual miscount are observed; a causal claim is unsupported. Token-stop associations similarly do not prove a particular output caused the stop.

## Empty-output census

All 27 successful empties replayed: 9 true empty results for the stated predicates, and 18 wrong shape/operation inputs or contradictory predicates. Contradictory input still produces a mathematically correct zero. No observed empty is explained by a case-only or numeric-string mismatch.

| Exact evidence | Cause | Explanation |
|---|---|---|
| [V1 epsilon__V06__claude-sonnet-5-5__r4 call 14](#e-v1-epsilon__V06__claude-sonnet-5-5__r4-c14) | unsupported_scalar_field_wildcard | field_of does not expand wildcard; all fields become missing and fail eq the literal status. |
| [V2 beta__V08__gpt-6.1-sol__t1 call 25](#e-v2-beta__V08__gpt-6.1-sol__t1-c25) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v2-delta__V05__claude-sonnet-5-5__t1-c29) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v2-delta__V05__claude-sonnet-5-5__t1-c30) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 14](#e-v2-delta__V06__claude-sonnet-5-5__t1-c14) | unsupported_scalar_field_wildcard | field_of does not expand wildcard; all fields become missing and fail eq the literal status. |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c19) | source_path_matched_nothing | Alias dictionary is one wildcard item; the later items step fails, dropping that item. |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c22) | literal_dot_key_read_as_nested_path | Literal dotted output key is read as nested keys and becomes None. |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c31) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c32) | all_sources_intersection | Intersection requires a member in every independent page/role set. |
| [V3 beta__V08__gpt-6.1-sol__t1 call 22](#e-v3-beta__V08__gpt-6.1-sol__t1-c22) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v3-delta__V05__claude-sonnet-5-5__t1-c30) | literal_dot_key_read_as_nested_path | Literal dotted output key is read as nested keys and becomes None. |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V06__claude-sonnet-5-5__t1-c28) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 66](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c66) | all_sources_intersection | Intersection requires a member in every independent page/role set. |
| [V3 gamma__V06__claude-sonnet-5-5__t1 call 27](#e-v3-gamma__V06__claude-sonnet-5-5__t1-c27) | list_scalar_type_mismatch | assignedAssetIds is a list; whole-list equality with EQ-86 is false even when membership would hold. |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 16](#e-v4-beta__V05__claude-sonnet-5-5__t1-c16) | true_empty_for_stated_predicates | none(ne zzz) rejects nonempty crew lists; the second condition rejects XML empty-string crew lists. |
| [V4 beta__V05__gpt-6.1-sol__t1 call 47](#e-v4-beta__V05__gpt-6.1-sol__t1-c47) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v4-delta__V05__claude-sonnet-5-5__t1-c31) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v4-delta__V06__claude-sonnet-5-5__t1-c13) | contradictory_predicates | Identical predicate required both any and none. The returned zero is mathematically correct. |
| [V4 epsilon__V06__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V06__claude-sonnet-5-5__t1-c18) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V4 epsilon__V06__claude-sonnet-5-5__t1 call 21](#e-v4-epsilon__V06__claude-sonnet-5-5__t1-c21) | true_empty | Replay finds no qualifying items or no remaining set members with valid field/path semantics. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 71](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c71) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 72](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c72) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 73](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c73) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 74](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c74) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 75](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c75) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 76](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c76) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 77](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c77) | absent_field_on_scalar_ids | Named record field is absent from scalar ids, becomes None, and intersects to empty. |

## Method and provenance

The allowlist consists of manifest.json, samples.jsonl and scores.csv from each specified folder, plus transcript.jsonl, results.jsonl and result.json for the 176 runs. input_hashes.json hashes these 540 files. Calls count kind=tool lines from 1. Findings contain folder, runKey, exact arguments, exact agent-visible output and stored output, cause, metrics, outcome evidence and call-cost limitations.

Read-only git show extracts V1 at 8b072fb^, V2 at 8b072fb, V3 at 683eca0 and V4 at 1c52d16. Source snapshots have Windows line endings; LF-normalized text hashes exactly match all manifest harness_tools.py hashes. The AST loader removes only unused budget/study_common imports and leaves calculator functions unchanged. Replay uses an in-memory store containing only earlier results in each run. ResultStore.add and HarnessToolSession are never invoked. No source/run files are written.

All 956 success strings and 51 refusal strings match historical replay exactly. All 3,201 stored-text hashes match. replay_mismatches.json and refusal_replay_mismatches.json are empty. integrity.json and source_checks.json preserve verification details. V4 replay checks original arguments against original earlier stored texts; it is not a fresh V4 agent run, and it does not reconstruct what a freshly generated intermediate would contain.

All observed filter comparisons were screened for case-only alternatives and numeric-text ordering differences: no such occurrences were found. Numeric literals already coerce numeric strings. Scalar/null/collection comparison and canonical set equality were inspected separately. No observed empty was traced to a numeric/string set mismatch.

Re-fetch screening requires an identical stored response or a top-level collection of at least 10 entities with a stable id and all returned fields held earlier. Nested crew-list coincidences are excluded. Gamma V2 call 25 is additionally verified manually by comparing the two projected mission pages against earlier results. A request may include both repeated and new data; exact whole-call savings are not inferred in that case.

## Pattern details and complete occurrence citations

### P01. Successful empty outputs

All successful zero counts/groupCounts and empty output lists; includes true empties, individually classified.

**V4 still allows:** yes. **Generic proposed fix:** Show source and field coverage and why nothing survived.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 epsilon__V06__claude-sonnet-5-5__r4 call 14](#e-v1-epsilon__V06__claude-sonnet-5-5__r4-c14) | unsupported_scalar_field_wildcard | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 25](#e-v2-beta__V08__gpt-6.1-sol__t1-c25) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v2-delta__V05__claude-sonnet-5-5__t1-c29) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v2-delta__V05__claude-sonnet-5-5__t1-c30) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 14](#e-v2-delta__V06__claude-sonnet-5-5__t1-c14) | unsupported_scalar_field_wildcard | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c19) | source_path_matched_nothing | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c22) | literal_dot_key_read_as_nested_path | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c31) | absent_field_on_scalar_ids | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c32) | all_sources_intersection | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 beta__V08__gpt-6.1-sol__t1 call 22](#e-v3-beta__V08__gpt-6.1-sol__t1-c22) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v3-delta__V05__claude-sonnet-5-5__t1-c30) | literal_dot_key_read_as_nested_path | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V06__claude-sonnet-5-5__t1-c28) | true_empty | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 66](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c66) | all_sources_intersection | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V06__claude-sonnet-5-5__t1 call 27](#e-v3-gamma__V06__claude-sonnet-5-5__t1-c27) | list_scalar_type_mismatch | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 16](#e-v4-beta__V05__claude-sonnet-5-5__t1-c16) | true_empty_for_stated_predicates | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 47](#e-v4-beta__V05__gpt-6.1-sol__t1-c47) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v4-delta__V05__claude-sonnet-5-5__t1-c31) | absent_field_on_scalar_ids | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v4-delta__V06__claude-sonnet-5-5__t1-c13) | contradictory_predicates | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V06__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V06__claude-sonnet-5-5__t1-c18) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V06__claude-sonnet-5-5__t1 call 21](#e-v4-epsilon__V06__claude-sonnet-5-5__t1-c21) | true_empty | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 71](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c71) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 72](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c72) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 73](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c73) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 74](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c74) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 75](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c75) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 76](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c76) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 77](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c77) | absent_field_on_scalar_ids | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |

### P02. Missing operation fields accepted (exposures)

A field used by the operation or list projection is absent from some input items. Includes optional fields, null probes and artificial aggregate keys; not automatically a failure.

**V4 still allows:** yes. **Generic proposed fix:** Report present/missing/null per field; refuse an entirely absent required field unless acknowledged.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 beta__V05__gpt-6.1-sol__r1 call 20](#e-v1-beta__V05__gpt-6.1-sol__r1-c20) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1; C-9938 absent 1/1 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 30](#e-v1-delta__V05__claude-sonnet-5-5__r3-c30) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 31](#e-v1-delta__V05__claude-sonnet-5-5__r3-c31) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 8](#e-v1-delta__V05__gpt-6.1-sol__r1-c8) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 9](#e-v1-delta__V05__gpt-6.1-sol__r1-c9) | personnelId absent 12/2377; details absent 12/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 10](#e-v1-delta__V05__gpt-6.1-sol__r1-c10) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 11](#e-v1-delta__V05__gpt-6.1-sol__r1-c11) | details.rank absent 621/621 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 12](#e-v1-delta__V05__gpt-6.1-sol__r1-c12) | personnelId absent 12/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 13](#e-v1-delta__V05__gpt-6.1-sol__r1-c13) | key.details.rank absent 2/249 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 15](#e-v1-delta__V05__gpt-6.1-sol__r1-c15) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 8](#e-v1-delta__V06__gpt-6.1-sol__r2-c8) | assets.0.mappingOutcome absent 8/300; assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 9](#e-v1-delta__V06__gpt-6.1-sol__r2-c9) | assets.1.mappingOutcome absent 75/300; assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 10](#e-v1-delta__V06__gpt-6.1-sol__r2-c10) | assets.2.mappingOutcome absent 269/300; assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 11](#e-v1-delta__V06__gpt-6.1-sol__r2-c11) | assets.24.mappingOutcome absent 99/100; assets.24.asset.status absent 99/100 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V07__claude-sonnet-5-5__r2 call 8](#e-v1-delta__V07__claude-sonnet-5-5__r2-c8) | __none absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V07__gpt-6.1-sol__r4 call 7](#e-v1-delta__V07__gpt-6.1-sol__r4-c7) | __all absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V08__gpt-6.1-sol__r3 call 7](#e-v1-delta__V08__gpt-6.1-sol__r3-c7) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V05__claude-sonnet-5-5__r3 call 20](#e-v1-epsilon__V05__claude-sonnet-5-5__r3-c20) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__claude-sonnet-5-5__r3 call 21](#e-v1-epsilon__V05__claude-sonnet-5-5__r3-c21) | key.details.rank absent 621/621 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 8](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c8) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 9](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c9) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 10](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c10) | details.rank absent 621/621 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 11](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c11) | personnelId absent 12/2377; details.rank absent 17/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | personnelId absent 12/2377; details absent 12/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 14](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c14) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V06__claude-sonnet-5-5__r4 call 14](#e-v1-epsilon__V06__claude-sonnet-5-5__r4-c14) | assets.*.asset.status absent 300/300 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 8](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c8) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 9](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c9) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 10](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c10) | assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V07__claude-sonnet-5-5__r2 call 8](#e-v1-epsilon__V07__claude-sonnet-5-5__r2-c8) | x absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V07__gpt-6.1-sol__r4 call 7](#e-v1-epsilon__V07__gpt-6.1-sol__r4-c7) | __all absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__claude-sonnet-5-5__r3 call 46](#e-v1-gamma__V05__claude-sonnet-5-5__r3-c46) | details.rank absent 119/900 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 40](#e-v1-gamma__V05__gpt-6.1-sol__r1-c40) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 41](#e-v1-gamma__V05__gpt-6.1-sol__r1-c41) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 42](#e-v1-gamma__V05__gpt-6.1-sol__r1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 43](#e-v1-gamma__V05__gpt-6.1-sol__r1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 44](#e-v1-gamma__V05__gpt-6.1-sol__r1-c44) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 45](#e-v1-gamma__V05__gpt-6.1-sol__r1-c45) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 46](#e-v1-gamma__V05__gpt-6.1-sol__r1-c46) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 47](#e-v1-gamma__V05__gpt-6.1-sol__r1-c47) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V07__claude-sonnet-5-5__r2 call 8](#e-v1-gamma__V07__claude-sonnet-5-5__r2-c8) | __typename absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V07__gpt-6.1-sol__r4 call 9](#e-v1-gamma__V07__gpt-6.1-sol__r4-c9) | __all absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 14](#e-v1-gamma__V08__gpt-6.1-sol__r3-c14) | localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 24](#e-v2-beta__V05__claude-sonnet-5-5__t1-c24) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 26](#e-v2-beta__V05__claude-sonnet-5-5__t1-c26) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 13](#e-v2-beta__V05__gpt-6.1-sol__t1-c13) | C-2372 absent 1/1 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 23](#e-v2-beta__V05__gpt-6.1-sol__t1-c23) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1; C-9938 absent 1/1 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 38](#e-v2-beta__V05__gpt-6.1-sol__t1-c38) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 39](#e-v2-beta__V05__gpt-6.1-sol__t1-c39) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 40](#e-v2-beta__V05__gpt-6.1-sol__t1-c40) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 41](#e-v2-beta__V05__gpt-6.1-sol__t1-c41) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 42](#e-v2-beta__V05__gpt-6.1-sol__t1-c42) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 43](#e-v2-beta__V05__gpt-6.1-sol__t1-c43) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 44](#e-v2-beta__V05__gpt-6.1-sol__t1-c44) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 45](#e-v2-beta__V05__gpt-6.1-sol__t1-c45) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 46](#e-v2-beta__V05__gpt-6.1-sol__t1-c46) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V08__claude-sonnet-5-5__t1 call 7](#e-v2-beta__V08__claude-sonnet-5-5__t1-c7) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 4](#e-v2-beta__V08__gpt-6.1-sol__t1-c4) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 18](#e-v2-delta__V05__claude-sonnet-5-5__t1-c18) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 19](#e-v2-delta__V05__claude-sonnet-5-5__t1-c19) | resolution absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 21](#e-v2-delta__V05__claude-sonnet-5-5__t1-c21) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 22](#e-v2-delta__V05__claude-sonnet-5-5__t1-c22) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 23](#e-v2-delta__V05__claude-sonnet-5-5__t1-c23) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 24](#e-v2-delta__V05__claude-sonnet-5-5__t1-c24) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v2-delta__V05__claude-sonnet-5-5__t1-c25) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v2-delta__V05__claude-sonnet-5-5__t1-c26) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v2-delta__V05__claude-sonnet-5-5__t1-c27) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v2-delta__V05__claude-sonnet-5-5__t1-c28) | details.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v2-delta__V05__claude-sonnet-5-5__t1-c29) | personnelId absent 44/2422 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v2-delta__V05__claude-sonnet-5-5__t1-c30) | personnelId absent 44/2423 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v2-delta__V05__claude-sonnet-5-5__t1-c31) | personnelId absent 44/2434 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 32](#e-v2-delta__V05__claude-sonnet-5-5__t1-c32) | personnelId absent 44/2551 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 33](#e-v2-delta__V05__claude-sonnet-5-5__t1-c33) | personnelId absent 44/2581 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 34](#e-v2-delta__V05__claude-sonnet-5-5__t1-c34) | personnelId absent 44/2501 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 35](#e-v2-delta__V05__claude-sonnet-5-5__t1-c35) | personnelId absent 44/2816 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 12](#e-v2-delta__V05__gpt-6.1-sol__t1-c12) | personnel absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 13](#e-v2-delta__V05__gpt-6.1-sol__t1-c13) | details.__typename absent 1/310; details.rank absent 5/310 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 14](#e-v2-delta__V05__gpt-6.1-sol__t1-c14) | personnel absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 15](#e-v2-delta__V05__gpt-6.1-sol__t1-c15) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 16](#e-v2-delta__V05__gpt-6.1-sol__t1-c16) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 17](#e-v2-delta__V05__gpt-6.1-sol__t1-c17) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 18](#e-v2-delta__V05__gpt-6.1-sol__t1-c18) | personnel.details.rank absent 17/1036; personnel absent 12/1036 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 19](#e-v2-delta__V05__gpt-6.1-sol__t1-c19) | personnel.details.rank absent 44/1385; personnel.personnelId absent 40/1385 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 20](#e-v2-delta__V05__gpt-6.1-sol__t1-c20) | personnel.details.rank absent 17/1036; personnel.personnelId absent 16/1036 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 21](#e-v2-delta__V05__gpt-6.1-sol__t1-c21) | personnel.details.rank absent 44/1385; personnel.personnelId absent 40/1385 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 22](#e-v2-delta__V05__gpt-6.1-sol__t1-c22) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v2-delta__V06__claude-sonnet-5-5__t1-c13) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 14](#e-v2-delta__V06__claude-sonnet-5-5__t1-c14) | assets.*.asset.status absent 300/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 16](#e-v2-delta__V06__claude-sonnet-5-5__t1-c16) | asset.status absent 108/596 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 11](#e-v2-delta__V06__gpt-6.1-sol__t1-c11) | assets.2 absent 269/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 12](#e-v2-delta__V06__gpt-6.1-sol__t1-c12) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 13](#e-v2-delta__V06__gpt-6.1-sol__t1-c13) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 14](#e-v2-delta__V06__gpt-6.1-sol__t1-c14) | assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 15](#e-v2-delta__V06__gpt-6.1-sol__t1-c15) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V08__gpt-6.1-sol__t1 call 11](#e-v2-delta__V08__gpt-6.1-sol__t1-c11) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c18) | personnelId absent 30/1626 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 20](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c20) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 21](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c21) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c22) | details.rank absent 781/781 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 23](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c23) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c24) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c25) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 26](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c26) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c27) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 28](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c28) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c29) | details.rank absent 219/1000 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c31) | personnelId absent 570/571 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c32) | personnelId absent 30/1627 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 33](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c33) | personnelId absent 30/1845 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 34](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c34) | personnelId absent 30/1756 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 35](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c35) | personnelId absent 30/1786 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 36](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c36) | personnelId absent 30/1706 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 37](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c37) | personnelId absent 30/2021 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 38](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c38) | personnelId absent 30/1639 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c10) | personnelId absent 12/2377; details.rank absent 17/2377; details.__typename absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c11) | details.rank absent 310/310 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 14](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c14) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 15](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c15) | details.rank absent 17/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 16](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c16) | details.rank absent 17/2377; personnelId absent 12/2377; details absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 18](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c18) | details.rank absent 5/310 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 19](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c19) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 20](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c20) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 21](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c21) | details.rank absent 17/2377; personnelId absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 25](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c25) | personnelId absent 12/2377 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__claude-sonnet-5-5__t1 call 14](#e-v2-epsilon__V06__claude-sonnet-5-5__t1-c14) | asset.assetId absent 69/234 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__claude-sonnet-5-5__t1 call 16](#e-v2-epsilon__V06__claude-sonnet-5-5__t1-c16) | asset.assetId absent 39/362; asset.status absent 39/362 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__claude-sonnet-5-5__t1 call 17](#e-v2-epsilon__V06__claude-sonnet-5-5__t1-c17) | asset.status absent 69/234 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 9](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c9) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c10) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c11) | assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c12) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c13) | assets.24.asset.status absent 1/2 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V07__gpt-6.1-sol__t1 call 7](#e-v2-epsilon__V07__gpt-6.1-sol__t1-c7) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 17](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c17) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c18) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 20](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c20) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 9](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c9) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c10) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c12) | personnelId absent 6/184; localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 40](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c40) | details.rank absent 119/900 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 41](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c41) | details.rank absent 1/1 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 42](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c42) | details.rank absent 119/900 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 43](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c43) | details.rank absent 569/569 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 45](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c45) | details.rank absent 2/569 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 33](#e-v2-gamma__V05__gpt-6.1-sol__t1-c33) | personnelId absent 3/3 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 36](#e-v2-gamma__V05__gpt-6.1-sol__t1-c36) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 38](#e-v2-gamma__V05__gpt-6.1-sol__t1-c38) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 39](#e-v2-gamma__V05__gpt-6.1-sol__t1-c39) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v2-gamma__V05__gpt-6.1-sol__t1-c40) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 41](#e-v2-gamma__V05__gpt-6.1-sol__t1-c41) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v2-gamma__V05__gpt-6.1-sol__t1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v2-gamma__V05__gpt-6.1-sol__t1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 44](#e-v2-gamma__V05__gpt-6.1-sol__t1-c44) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V07__claude-sonnet-5-5__t1 call 5](#e-v2-gamma__V07__claude-sonnet-5-5__t1-c5) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V07__gpt-6.1-sol__t1 call 9](#e-v2-gamma__V07__gpt-6.1-sol__t1-c9) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 27](#e-v3-beta__V05__claude-sonnet-5-5__t1-c27) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 31](#e-v3-beta__V05__claude-sonnet-5-5__t1-c31) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 32](#e-v3-beta__V05__claude-sonnet-5-5__t1-c32) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 33](#e-v3-beta__V05__claude-sonnet-5-5__t1-c33) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 34](#e-v3-beta__V05__claude-sonnet-5-5__t1-c34) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 35](#e-v3-beta__V05__claude-sonnet-5-5__t1-c35) | crewDetails.rank absent 19/800 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 23](#e-v3-beta__V05__gpt-6.1-sol__t1-c23) | C-2372 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 27](#e-v3-beta__V05__gpt-6.1-sol__t1-c27) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 33](#e-v3-beta__V05__gpt-6.1-sol__t1-c33) | C-9938 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 38](#e-v3-beta__V05__gpt-6.1-sol__t1-c38) | crewDetails.rank absent 219/1000; civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 40](#e-v3-beta__V05__gpt-6.1-sol__t1-c40) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 41](#e-v3-beta__V05__gpt-6.1-sol__t1-c41) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 42](#e-v3-beta__V05__gpt-6.1-sol__t1-c42) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 43](#e-v3-beta__V05__gpt-6.1-sol__t1-c43) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 44](#e-v3-beta__V05__gpt-6.1-sol__t1-c44) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 45](#e-v3-beta__V05__gpt-6.1-sol__t1-c45) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 46](#e-v3-beta__V05__gpt-6.1-sol__t1-c46) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 47](#e-v3-beta__V05__gpt-6.1-sol__t1-c47) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__claude-sonnet-5-5__t1 call 13](#e-v3-beta__V08__claude-sonnet-5-5__t1-c13) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__gpt-6.1-sol__t1 call 4](#e-v3-beta__V08__gpt-6.1-sol__t1-c4) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 20](#e-v3-delta__V05__claude-sonnet-5-5__t1-c20) | mappingOutcome absent 44/2421; resolution absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V05__claude-sonnet-5-5__t1-c21) | personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v3-delta__V05__claude-sonnet-5-5__t1-c25) | personnel.personnelId absent 56/2421; personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v3-delta__V05__claude-sonnet-5-5__t1-c26) | personnel.details.rank absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v3-delta__V05__claude-sonnet-5-5__t1-c27) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V05__claude-sonnet-5-5__t1-c28) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421; personnel.details.__typename absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v3-delta__V05__claude-sonnet-5-5__t1-c29) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v3-delta__V05__claude-sonnet-5-5__t1-c30) | personnel.details.rank absent 2360/2360 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v3-delta__V05__claude-sonnet-5-5__t1-c31) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 33](#e-v3-delta__V05__claude-sonnet-5-5__t1-c33) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 34](#e-v3-delta__V05__claude-sonnet-5-5__t1-c34) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 35](#e-v3-delta__V05__claude-sonnet-5-5__t1-c35) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 36](#e-v3-delta__V05__claude-sonnet-5-5__t1-c36) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 37](#e-v3-delta__V05__claude-sonnet-5-5__t1-c37) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 38](#e-v3-delta__V05__claude-sonnet-5-5__t1-c38) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__gpt-6.1-sol__t1 call 18](#e-v3-delta__V05__gpt-6.1-sol__t1-c18) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 16](#e-v3-delta__V06__claude-sonnet-5-5__t1-c16) | asset.status absent 108/596 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V06__claude-sonnet-5-5__t1-c17) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 18](#e-v3-delta__V06__claude-sonnet-5-5__t1-c18) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 19](#e-v3-delta__V06__claude-sonnet-5-5__t1-c19) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 20](#e-v3-delta__V06__claude-sonnet-5-5__t1-c20) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V06__claude-sonnet-5-5__t1-c21) | assets.2.mappingOutcome absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 22](#e-v3-delta__V06__claude-sonnet-5-5__t1-c22) | assets.2.resolution absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 23](#e-v3-delta__V06__claude-sonnet-5-5__t1-c23) | assets.2.resolution absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 24](#e-v3-delta__V06__claude-sonnet-5-5__t1-c24) | assets.3.resolution absent 298/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 11](#e-v3-delta__V06__gpt-6.1-sol__t1-c11) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 12](#e-v3-delta__V06__gpt-6.1-sol__t1-c12) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 13](#e-v3-delta__V06__gpt-6.1-sol__t1-c13) | assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 14](#e-v3-delta__V06__gpt-6.1-sol__t1-c14) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__claude-sonnet-5-5__t1 call 9](#e-v3-delta__V07__claude-sonnet-5-5__t1-c9) | hasCost absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__gpt-6.1-sol__t1 call 6](#e-v3-delta__V07__gpt-6.1-sol__t1-c6) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 13](#e-v3-delta__V08__claude-sonnet-5-5__t1-c13) | mappingOutcome absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 15](#e-v3-delta__V08__claude-sonnet-5-5__t1-c15) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V08__claude-sonnet-5-5__t1-c17) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 12](#e-v3-delta__V08__gpt-6.1-sol__t1-c12) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 13](#e-v3-delta__V08__gpt-6.1-sol__t1-c13) | personnelId absent 6/184; localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c19) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 20](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c20) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 21](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c21) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c22) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c24) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c25) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 26](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c26) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c27) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 28](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c28) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c29) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c30) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__gpt-6.1-sol__t1 call 17](#e-v3-epsilon__V05__gpt-6.1-sol__t1-c17) | personnel absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__gpt-6.1-sol__t1 call 19](#e-v3-epsilon__V05__gpt-6.1-sol__t1-c19) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__claude-sonnet-5-5__t1 call 15](#e-v3-epsilon__V06__claude-sonnet-5-5__t1-c15) | asset.status absent 108/596 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c10) | assets.0.asset.status absent 59/300; assets.0.mappingOutcome absent 8/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c11) | assets.1.asset.status absent 88/300; assets.1.mappingOutcome absent 75/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c12) | assets.2.asset.status absent 271/300; assets.2.mappingOutcome absent 269/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c13) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 15](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c15) | asset.status absent 44/50 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V07__claude-sonnet-5-5__t1 call 8](#e-v3-epsilon__V07__claude-sonnet-5-5__t1-c8) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__claude-sonnet-5-5__t1 call 13](#e-v3-epsilon__V08__claude-sonnet-5-5__t1-c13) | mappingOutcome absent 6/184; resolution absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__claude-sonnet-5-5__t1 call 14](#e-v3-epsilon__V08__claude-sonnet-5-5__t1-c14) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c11) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c12) | localRef absent 6/184; personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 57](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c57) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 58](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c58) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 59](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c59) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 60](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c60) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 61](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c61) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 62](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c62) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 63](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c63) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 64](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c64) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v3-gamma__V05__gpt-6.1-sol__t1-c40) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v3-gamma__V05__gpt-6.1-sol__t1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v3-gamma__V05__gpt-6.1-sol__t1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 44](#e-v3-gamma__V05__gpt-6.1-sol__t1-c44) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 45](#e-v3-gamma__V05__gpt-6.1-sol__t1-c45) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 46](#e-v3-gamma__V05__gpt-6.1-sol__t1-c46) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 47](#e-v3-gamma__V05__gpt-6.1-sol__t1-c47) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 48](#e-v3-gamma__V05__gpt-6.1-sol__t1-c48) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V07__gpt-6.1-sol__t1 call 9](#e-v3-gamma__V07__gpt-6.1-sol__t1-c9) | __all absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 9](#e-v4-beta__V05__claude-sonnet-5-5__t1-c9) | commandingOfficerId absent 44/300 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 10](#e-v4-beta__V05__claude-sonnet-5-5__t1-c10) | assignedCrewIds.crewId absent 17/300 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 29](#e-v4-beta__V05__claude-sonnet-5-5__t1-c29) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 35](#e-v4-beta__V05__claude-sonnet-5-5__t1-c35) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 37](#e-v4-beta__V05__claude-sonnet-5-5__t1-c37) | crewDetails.rank absent 801/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-beta__V05__claude-sonnet-5-5__t1-c38) | crewDetails.rank absent 801/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 39](#e-v4-beta__V05__claude-sonnet-5-5__t1-c39) | crewDetails absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 40](#e-v4-beta__V05__claude-sonnet-5-5__t1-c40) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 41](#e-v4-beta__V05__claude-sonnet-5-5__t1-c41) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 42](#e-v4-beta__V05__claude-sonnet-5-5__t1-c42) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 43](#e-v4-beta__V05__claude-sonnet-5-5__t1-c43) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 44](#e-v4-beta__V05__claude-sonnet-5-5__t1-c44) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 45](#e-v4-beta__V05__claude-sonnet-5-5__t1-c45) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 37](#e-v4-beta__V05__gpt-6.1-sol__t1-c37) | crewDetails.rank absent 219/1000; civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 39](#e-v4-beta__V05__gpt-6.1-sol__t1-c39) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 40](#e-v4-beta__V05__gpt-6.1-sol__t1-c40) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 41](#e-v4-beta__V05__gpt-6.1-sol__t1-c41) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 42](#e-v4-beta__V05__gpt-6.1-sol__t1-c42) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 43](#e-v4-beta__V05__gpt-6.1-sol__t1-c43) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 44](#e-v4-beta__V05__gpt-6.1-sol__t1-c44) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 45](#e-v4-beta__V05__gpt-6.1-sol__t1-c45) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 46](#e-v4-beta__V05__gpt-6.1-sol__t1-c46) | civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 56](#e-v4-beta__V05__gpt-6.1-sol__t1-c56) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1; C-9938 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__claude-sonnet-5-5__t1 call 4](#e-v4-beta__V08__claude-sonnet-5-5__t1-c4) | commandingOfficerId absent 6/23; assignedCrewIds.crewId absent 1/23 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__gpt-6.1-sol__t1 call 4](#e-v4-beta__V08__gpt-6.1-sol__t1-c4) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v4-delta__V05__claude-sonnet-5-5__t1-c25) | mappingOutcome absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v4-delta__V05__claude-sonnet-5-5__t1-c26) | resolution absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v4-delta__V05__claude-sonnet-5-5__t1-c27) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v4-delta__V05__claude-sonnet-5-5__t1-c29) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v4-delta__V05__claude-sonnet-5-5__t1-c30) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v4-delta__V05__claude-sonnet-5-5__t1-c31) | personnelId absent 621/721 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 33](#e-v4-delta__V05__claude-sonnet-5-5__t1-c33) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 34](#e-v4-delta__V05__claude-sonnet-5-5__t1-c34) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 35](#e-v4-delta__V05__claude-sonnet-5-5__t1-c35) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 36](#e-v4-delta__V05__claude-sonnet-5-5__t1-c36) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 37](#e-v4-delta__V05__claude-sonnet-5-5__t1-c37) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-delta__V05__claude-sonnet-5-5__t1-c38) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__gpt-6.1-sol__t1 call 17](#e-v4-delta__V05__gpt-6.1-sol__t1-c17) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 17](#e-v4-delta__V08__claude-sonnet-5-5__t1-c17) | mappingOutcome absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 19](#e-v4-delta__V08__claude-sonnet-5-5__t1-c19) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 22](#e-v4-delta__V08__claude-sonnet-5-5__t1-c22) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__gpt-6.1-sol__t1 call 14](#e-v4-delta__V08__gpt-6.1-sol__t1-c14) | personnelId absent 6/184; localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c18) | mappingOutcome absent 44/300; resolution absent 44/300 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c19) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 23](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c23) | personnel.personnelId absent 56/2421; personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c24) | key.personnel.details.rank absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c25) | key.personnel.personnelId absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 26](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c26) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c27) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 28](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c28) | personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c29) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c30) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c31) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c32) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 33](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c33) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 34](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c34) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 35](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c35) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__gpt-6.1-sol__t1 call 14](#e-v4-epsilon__V05__gpt-6.1-sol__t1-c14) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V07__gpt-6.1-sol__t1 call 7](#e-v4-epsilon__V07__gpt-6.1-sol__t1-c7) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c18) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 19](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c19) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 21](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c21) | resolution absent 6/184; mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 11](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c11) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c12) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 13](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c13) | localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 16](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c16) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 30](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c30) | assignedCrewIds.* absent 300/300 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 59](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c59) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 64](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c64) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 65](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c65) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 66](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c66) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 67](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c67) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 68](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c68) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 69](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c69) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 70](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c70) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 71](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c71) | personnelId absent 620/621 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 72](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c72) | personnelId absent 620/700 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 73](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c73) | personnelId absent 620/622 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 74](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c74) | personnelId absent 620/1015 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 75](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c75) | personnelId absent 620/780 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 76](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c76) | personnelId absent 620/750 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 77](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c77) | personnelId absent 620/633 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 34](#e-v4-gamma__V05__gpt-6.1-sol__t1-c34) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 37](#e-v4-gamma__V05__gpt-6.1-sol__t1-c37) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 38](#e-v4-gamma__V05__gpt-6.1-sol__t1-c38) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 39](#e-v4-gamma__V05__gpt-6.1-sol__t1-c39) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v4-gamma__V05__gpt-6.1-sol__t1-c40) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 41](#e-v4-gamma__V05__gpt-6.1-sol__t1-c41) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v4-gamma__V05__gpt-6.1-sol__t1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v4-gamma__V05__gpt-6.1-sol__t1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V07__claude-sonnet-5-5__t1 call 8](#e-v4-gamma__V07__claude-sonnet-5-5__t1-c8) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |

### P03. Wildcard source-path omissions (disclosed)

Source traversal drops elements lacking later path segments. Existing missing counters disclose these accepted partials.

**V4 still allows:** yes. **Generic proposed fix:** Show retained/omitted counts per source and the failing path segment.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V05__claude-sonnet-5-5__ref call 21](#e-v1-alpha__V05__claude-sonnet-5-5__ref-c21) | [{"id": "d373-15", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 alpha__V05__claude-sonnet-5-5__ref call 22](#e-v1-alpha__V05__claude-sonnet-5-5__ref-c22) | [{"id": "d373-15", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "d373-16", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "d373-17", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "d373-18", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "d373-19", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "d373-20", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 1}, {"id": "d373-15", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "d373-16", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "d373-17", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "d373-18", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "d373-19", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "d373-20", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 alpha__V05__gpt-6.1-sol__ref call 55](#e-v1-alpha__V05__gpt-6.1-sol__ref-c55) | [{"id": "ba98-47", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "ba98-47", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-48", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "ba98-48", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "ba98-49", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "ba98-49", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-50", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "ba98-50", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "ba98-51", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "ba98-51", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-52", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "ba98-52", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 alpha__V05__gpt-6.1-sol__ref call 56](#e-v1-alpha__V05__gpt-6.1-sol__ref-c56) | [{"id": "ba98-47", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "ba98-47", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-48", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "ba98-48", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "ba98-49", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "ba98-49", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-50", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "ba98-50", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "ba98-51", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "ba98-51", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "ba98-52", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "ba98-52", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__claude-sonnet-5-5__r3 call 9](#e-v1-beta__V05__claude-sonnet-5-5__r3-c9) | [{"id": "3b9e-2", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__claude-sonnet-5-5__r3 call 10](#e-v1-beta__V05__claude-sonnet-5-5__r3-c10) | [{"id": "3b9e-2", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "3b9e-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "3b9e-4", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "3b9e-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "3b9e-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "3b9e-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 1}, {"id": "3b9e-2", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "3b9e-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "3b9e-4", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "3b9e-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "3b9e-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "3b9e-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__gpt-6.1-sol__r1 call 14](#e-v1-beta__V05__gpt-6.1-sol__r1-c14) | [{"id": "47f5-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "47f5-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "47f5-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "47f5-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "47f5-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "47f5-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "47f5-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "47f5-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "47f5-8", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "47f5-8", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "47f5-9", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "47f5-9", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V08__gpt-6.1-sol__r3 call 4](#e-v1-beta__V08__gpt-6.1-sol__r3-c4) | [{"id": "2962-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}, {"id": "2962-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V08__gpt-6.1-sol__r3 call 5](#e-v1-beta__V08__gpt-6.1-sol__r3-c5) | [{"id": "2962-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V08__gpt-6.1-sol__r3 call 6](#e-v1-beta__V08__gpt-6.1-sol__r3-c6) | [{"id": "2962-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 18](#e-v1-delta__V05__claude-sonnet-5-5__r3-c18) | [{"id": "fc3c-14", "path": "body.data.missions.*.commandingOfficer.personnelId", "omitted": 12}, {"id": "fc3c-15", "path": "body.data.missions.*.commandingOfficer.personnelId", "omitted": 18}, {"id": "fc3c-16", "path": "body.data.missions.*.commandingOfficer.personnelId", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 8](#e-v1-delta__V05__gpt-6.1-sol__r1-c8) | [{"id": "7c44-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "7c44-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "7c44-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 9](#e-v1-delta__V05__gpt-6.1-sol__r1-c9) | [{"id": "7c44-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "7c44-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "7c44-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 10](#e-v1-delta__V05__gpt-6.1-sol__r1-c10) | [{"id": "7c44-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "7c44-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "7c44-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 12](#e-v1-delta__V05__gpt-6.1-sol__r1-c12) | [{"id": "7c44-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "7c44-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "7c44-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 15](#e-v1-delta__V05__gpt-6.1-sol__r1-c15) | [{"id": "7c44-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "7c44-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "7c44-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__claude-sonnet-5-5__r3 call 20](#e-v1-epsilon__V05__claude-sonnet-5-5__r3-c20) | [{"id": "2e6b-14", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2e6b-16", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2e6b-18", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 8](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c8) | [{"id": "af7a-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "af7a-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "af7a-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 9](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c9) | [{"id": "af7a-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "af7a-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "af7a-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 11](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c11) | [{"id": "af7a-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "af7a-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "af7a-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | [{"id": "af7a-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "af7a-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "af7a-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 14](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c14) | [{"id": "af7a-4", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "af7a-5", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "af7a-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V08__gpt-6.1-sol__r3 call 7](#e-v1-epsilon__V08__gpt-6.1-sol__r3-c7) | [{"id": "6fc4-4", "path": "body.data.missions.*.crew.*.personnel.personnelId", "omitted": 2}, {"id": "6fc4-4", "path": "body.data.missions.*.commandingOfficer.personnel.personnelId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 24](#e-v1-gamma__V08__gpt-6.1-sol__r3-c24) | [{"id": "7aeb-20", "path": "body.data.*.items", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 9](#e-v2-beta__V05__claude-sonnet-5-5__t1-c9) | [{"id": "2795-2", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "2795-4", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "2795-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "2795-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 10](#e-v2-beta__V05__claude-sonnet-5-5__t1-c10) | [{"id": "2795-2", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "2795-4", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "2795-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 10](#e-v2-beta__V05__gpt-6.1-sol__t1-c10) | [{"id": "532c-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "532c-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "532c-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-8", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "532c-8", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V08__claude-sonnet-5-5__t1 call 5](#e-v2-beta__V08__claude-sonnet-5-5__t1-c5) | [{"id": "b6bd-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__claude-sonnet-5-5__t1 call 8](#e-v2-beta__V08__claude-sonnet-5-5__t1-c8) | [{"id": "b6bd-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}, {"id": "b6bd-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 5](#e-v2-beta__V08__gpt-6.1-sol__t1-c5) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}, {"id": "0bb3-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 6](#e-v2-beta__V08__gpt-6.1-sol__t1-c6) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 9](#e-v2-beta__V08__gpt-6.1-sol__t1-c9) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V08__gpt-6.1-sol__t1 call 10](#e-v2-delta__V08__gpt-6.1-sol__t1-c10) | [{"id": "298e-7", "path": "body.data.missions.*.commandingOfficer.personnel.personnelId", "omitted": 6}, {"id": "298e-7", "path": "body.data.missions.*.crew.*.personnel.personnelId", "omitted": 2}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c19) | [{"id": "81c0-17", "path": "body.data.*.items.*", "omitted": 1}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c10) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c12) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c13) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 14](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c14) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 15](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c15) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 16](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c16) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 19](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c19) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 20](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c20) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 21](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c21) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 25](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c25) | [{"id": "2fba-6", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-7", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-8", "path": "body.data.missions.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 32](#e-v2-gamma__V05__gpt-6.1-sol__t1-c32) | [{"id": "910b-27", "path": "body.data.*.items", "omitted": 1}, {"id": "910b-28", "path": "body.data.*.items", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 9](#e-v3-beta__V05__claude-sonnet-5-5__t1-c9) | [{"id": "2795-2", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "2795-4", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "2795-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "2795-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "2795-2", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "2795-4", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "2795-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "2795-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 14](#e-v3-beta__V05__gpt-6.1-sol__t1-c14) | [{"id": "532c-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "532c-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "532c-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-8", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "532c-8", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__claude-sonnet-5-5__t1 call 5](#e-v3-beta__V08__claude-sonnet-5-5__t1-c5) | [{"id": "b6bd-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__gpt-6.1-sol__t1 call 5](#e-v3-beta__V08__gpt-6.1-sol__t1-c5) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}, {"id": "0bb3-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__gpt-6.1-sol__t1 call 16](#e-v3-delta__V05__gpt-6.1-sol__t1-c16) | [{"id": "f499-13", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 12}, {"id": "f499-14", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 18}, {"id": "f499-15", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 11](#e-v3-delta__V08__gpt-6.1-sol__t1-c11) | [{"id": "298e-7", "path": "body.data.missionsPage.items.*.crew.*.personnel.personnelId", "omitted": 2}, {"id": "298e-7", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel.personnelId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 10](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c10) | [{"id": "bd7e-6", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel.personnelId", "omitted": 6}, {"id": "bd7e-6", "path": "body.data.missionsPage.items.*.crew.*.personnel.personnelId", "omitted": 2}] | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 37](#e-v3-gamma__V05__gpt-6.1-sol__t1-c37) | [{"id": "910b-33", "path": "body.data.*.items", "omitted": 1}, {"id": "910b-34", "path": "body.data.*.items", "omitted": 1}, {"id": "910b-35", "path": "body.data.*.items", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 15](#e-v4-beta__V05__claude-sonnet-5-5__t1-c15) | [{"id": "2795-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "2795-4", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "2795-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "2795-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 2}, {"id": "2795-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 4}, {"id": "2795-8", "path": "body.missionList.mission.*.assignedCrewIds.crewId.*", "omitted": 1}, {"id": "2795-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-4", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "2795-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "2795-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "2795-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "2795-8", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 15](#e-v4-beta__V05__gpt-6.1-sol__t1-c15) | [{"id": "532c-3", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-3", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-5", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 5}, {"id": "532c-5", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-6", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 11}, {"id": "532c-6", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-7", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 7}, {"id": "532c-7", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 2}, {"id": "532c-8", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 10}, {"id": "532c-8", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 4}, {"id": "532c-9", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__gpt-6.1-sol__t1 call 5](#e-v4-beta__V08__gpt-6.1-sol__t1-c5) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}, {"id": "0bb3-1", "path": "body.missionList.mission.*.commandingOfficerId", "omitted": 6}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__gpt-6.1-sol__t1 call 6](#e-v4-beta__V08__gpt-6.1-sol__t1-c6) | [{"id": "0bb3-1", "path": "body.missionList.mission.*.assignedCrewIds.crewId", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__gpt-6.1-sol__t1 call 15](#e-v4-delta__V05__gpt-6.1-sol__t1-c15) | [{"id": "f499-12", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 12}, {"id": "f499-13", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 18}, {"id": "f499-14", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V06__claude-sonnet-5-5__t1 call 14](#e-v4-delta__V06__claude-sonnet-5-5__t1-c14) | [{"id": "def3-9", "path": "body.data.missionsPage.items.*.assets.*.asset.status", "omitted": 69}, {"id": "def3-10", "path": "body.data.missionsPage.items.*.assets.*.asset.status", "omitted": 16}, {"id": "def3-11", "path": "body.data.missionsPage.items.*.assets.*.asset.status", "omitted": 23}] | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__gpt-6.1-sol__t1 call 10](#e-v4-delta__V08__gpt-6.1-sol__t1-c10) | [{"id": "298e-8", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel.personnelId", "omitted": 6}, {"id": "298e-8", "path": "body.data.missionsPage.items.*.crew.*.personnel.personnelId", "omitted": 2}] | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v4-epsilon__V05__gpt-6.1-sol__t1-c12) | [{"id": "2fba-9", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 12}, {"id": "2fba-10", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 18}, {"id": "2fba-11", "path": "body.data.missionsPage.items.*.commandingOfficer.personnel", "omitted": 14}] | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 24](#e-v4-gamma__V05__gpt-6.1-sol__t1-c24) | [{"id": "910b-22", "path": "body.data.*.items.*.commandingOfficerId", "omitted": 1}, {"id": "910b-22", "path": "body.data.*.items.*.assignedCrewIds.*", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V08__gpt-6.1-sol__t1 call 31](#e-v4-gamma__V08__gpt-6.1-sol__t1-c31) | [{"id": "6b14-28", "path": "body.data.*.items", "omitted": 1}] | 1 observed; extra unknown | correct / not_established |

### P04. Read lines omit field coverage (exposures)

V3/V4 read lines count source records before operation-field validation; some named fields are absent. Optional fields remain exposures, not established misleading uses.

**V4 still allows:** yes. **Generic proposed fix:** Show usable field values and scalar/record shapes beside source cardinality.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V3 beta__V05__claude-sonnet-5-5__t1 call 27](#e-v3-beta__V05__claude-sonnet-5-5__t1-c27) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 31](#e-v3-beta__V05__claude-sonnet-5-5__t1-c31) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 32](#e-v3-beta__V05__claude-sonnet-5-5__t1-c32) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 33](#e-v3-beta__V05__claude-sonnet-5-5__t1-c33) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 34](#e-v3-beta__V05__claude-sonnet-5-5__t1-c34) | crewDetails.rank absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 35](#e-v3-beta__V05__claude-sonnet-5-5__t1-c35) | crewDetails.rank absent 19/800 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 23](#e-v3-beta__V05__gpt-6.1-sol__t1-c23) | C-2372 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 27](#e-v3-beta__V05__gpt-6.1-sol__t1-c27) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 33](#e-v3-beta__V05__gpt-6.1-sol__t1-c33) | C-9938 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 38](#e-v3-beta__V05__gpt-6.1-sol__t1-c38) | crewDetails.rank absent 219/1000; civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 40](#e-v3-beta__V05__gpt-6.1-sol__t1-c40) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 41](#e-v3-beta__V05__gpt-6.1-sol__t1-c41) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 42](#e-v3-beta__V05__gpt-6.1-sol__t1-c42) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 43](#e-v3-beta__V05__gpt-6.1-sol__t1-c43) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 44](#e-v3-beta__V05__gpt-6.1-sol__t1-c44) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 45](#e-v3-beta__V05__gpt-6.1-sol__t1-c45) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 46](#e-v3-beta__V05__gpt-6.1-sol__t1-c46) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 47](#e-v3-beta__V05__gpt-6.1-sol__t1-c47) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__claude-sonnet-5-5__t1 call 13](#e-v3-beta__V08__claude-sonnet-5-5__t1-c13) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V08__gpt-6.1-sol__t1 call 4](#e-v3-beta__V08__gpt-6.1-sol__t1-c4) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 20](#e-v3-delta__V05__claude-sonnet-5-5__t1-c20) | mappingOutcome absent 44/2421; resolution absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V05__claude-sonnet-5-5__t1-c21) | personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v3-delta__V05__claude-sonnet-5-5__t1-c25) | personnel.personnelId absent 56/2421; personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v3-delta__V05__claude-sonnet-5-5__t1-c26) | personnel.details.rank absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v3-delta__V05__claude-sonnet-5-5__t1-c27) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V05__claude-sonnet-5-5__t1-c28) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421; personnel.details.__typename absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v3-delta__V05__claude-sonnet-5-5__t1-c29) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v3-delta__V05__claude-sonnet-5-5__t1-c30) | personnel.details.rank absent 2360/2360 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v3-delta__V05__claude-sonnet-5-5__t1-c31) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 33](#e-v3-delta__V05__claude-sonnet-5-5__t1-c33) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 34](#e-v3-delta__V05__claude-sonnet-5-5__t1-c34) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 35](#e-v3-delta__V05__claude-sonnet-5-5__t1-c35) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 36](#e-v3-delta__V05__claude-sonnet-5-5__t1-c36) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 37](#e-v3-delta__V05__claude-sonnet-5-5__t1-c37) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 38](#e-v3-delta__V05__claude-sonnet-5-5__t1-c38) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__gpt-6.1-sol__t1 call 18](#e-v3-delta__V05__gpt-6.1-sol__t1-c18) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 16](#e-v3-delta__V06__claude-sonnet-5-5__t1-c16) | asset.status absent 108/596 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V06__claude-sonnet-5-5__t1-c17) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 18](#e-v3-delta__V06__claude-sonnet-5-5__t1-c18) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 19](#e-v3-delta__V06__claude-sonnet-5-5__t1-c19) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 20](#e-v3-delta__V06__claude-sonnet-5-5__t1-c20) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V06__claude-sonnet-5-5__t1-c21) | assets.2.mappingOutcome absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 22](#e-v3-delta__V06__claude-sonnet-5-5__t1-c22) | assets.2.resolution absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 23](#e-v3-delta__V06__claude-sonnet-5-5__t1-c23) | assets.2.resolution absent 269/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 24](#e-v3-delta__V06__claude-sonnet-5-5__t1-c24) | assets.3.resolution absent 298/300 | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 11](#e-v3-delta__V06__gpt-6.1-sol__t1-c11) | assets.0.asset.status absent 59/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 12](#e-v3-delta__V06__gpt-6.1-sol__t1-c12) | assets.1.asset.status absent 88/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 13](#e-v3-delta__V06__gpt-6.1-sol__t1-c13) | assets.2.asset.status absent 271/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 14](#e-v3-delta__V06__gpt-6.1-sol__t1-c14) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__claude-sonnet-5-5__t1 call 9](#e-v3-delta__V07__claude-sonnet-5-5__t1-c9) | hasCost absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__gpt-6.1-sol__t1 call 6](#e-v3-delta__V07__gpt-6.1-sol__t1-c6) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 13](#e-v3-delta__V08__claude-sonnet-5-5__t1-c13) | mappingOutcome absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 15](#e-v3-delta__V08__claude-sonnet-5-5__t1-c15) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V08__claude-sonnet-5-5__t1-c17) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 12](#e-v3-delta__V08__gpt-6.1-sol__t1-c12) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 13](#e-v3-delta__V08__gpt-6.1-sol__t1-c13) | personnelId absent 6/184; localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c19) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 20](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c20) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 21](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c21) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c22) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c24) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c25) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 26](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c26) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c27) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 28](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c28) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c29) | details.rank absent 1/100 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c30) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__gpt-6.1-sol__t1 call 17](#e-v3-epsilon__V05__gpt-6.1-sol__t1-c17) | personnel absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__gpt-6.1-sol__t1 call 19](#e-v3-epsilon__V05__gpt-6.1-sol__t1-c19) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__claude-sonnet-5-5__t1 call 15](#e-v3-epsilon__V06__claude-sonnet-5-5__t1-c15) | asset.status absent 108/596 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c10) | assets.0.asset.status absent 59/300; assets.0.mappingOutcome absent 8/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c11) | assets.1.asset.status absent 88/300; assets.1.mappingOutcome absent 75/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c12) | assets.2.asset.status absent 271/300; assets.2.mappingOutcome absent 269/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c13) | assets.3 absent 298/300 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 15](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c15) | asset.status absent 44/50 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V07__claude-sonnet-5-5__t1 call 8](#e-v3-epsilon__V07__claude-sonnet-5-5__t1-c8) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__claude-sonnet-5-5__t1 call 13](#e-v3-epsilon__V08__claude-sonnet-5-5__t1-c13) | mappingOutcome absent 6/184; resolution absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__claude-sonnet-5-5__t1 call 14](#e-v3-epsilon__V08__claude-sonnet-5-5__t1-c14) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c11) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c12) | localRef absent 6/184; personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 57](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c57) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 58](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c58) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 59](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c59) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 60](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c60) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 61](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c61) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 62](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c62) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 63](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c63) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 64](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c64) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v3-gamma__V05__gpt-6.1-sol__t1-c40) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v3-gamma__V05__gpt-6.1-sol__t1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v3-gamma__V05__gpt-6.1-sol__t1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 44](#e-v3-gamma__V05__gpt-6.1-sol__t1-c44) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 45](#e-v3-gamma__V05__gpt-6.1-sol__t1-c45) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 46](#e-v3-gamma__V05__gpt-6.1-sol__t1-c46) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 47](#e-v3-gamma__V05__gpt-6.1-sol__t1-c47) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 48](#e-v3-gamma__V05__gpt-6.1-sol__t1-c48) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V07__gpt-6.1-sol__t1 call 9](#e-v3-gamma__V07__gpt-6.1-sol__t1-c9) | __all absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 9](#e-v4-beta__V05__claude-sonnet-5-5__t1-c9) | commandingOfficerId absent 44/300 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 10](#e-v4-beta__V05__claude-sonnet-5-5__t1-c10) | assignedCrewIds.crewId absent 17/300 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 29](#e-v4-beta__V05__claude-sonnet-5-5__t1-c29) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 35](#e-v4-beta__V05__claude-sonnet-5-5__t1-c35) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 37](#e-v4-beta__V05__claude-sonnet-5-5__t1-c37) | crewDetails.rank absent 801/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-beta__V05__claude-sonnet-5-5__t1-c38) | crewDetails.rank absent 801/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 39](#e-v4-beta__V05__claude-sonnet-5-5__t1-c39) | crewDetails absent 119/900 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 40](#e-v4-beta__V05__claude-sonnet-5-5__t1-c40) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 41](#e-v4-beta__V05__claude-sonnet-5-5__t1-c41) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 42](#e-v4-beta__V05__claude-sonnet-5-5__t1-c42) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 43](#e-v4-beta__V05__claude-sonnet-5-5__t1-c43) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 44](#e-v4-beta__V05__claude-sonnet-5-5__t1-c44) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 45](#e-v4-beta__V05__claude-sonnet-5-5__t1-c45) | crewDetails.rank absent 20/801 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 37](#e-v4-beta__V05__gpt-6.1-sol__t1-c37) | crewDetails.rank absent 219/1000; civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 39](#e-v4-beta__V05__gpt-6.1-sol__t1-c39) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 40](#e-v4-beta__V05__gpt-6.1-sol__t1-c40) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 41](#e-v4-beta__V05__gpt-6.1-sol__t1-c41) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 42](#e-v4-beta__V05__gpt-6.1-sol__t1-c42) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 43](#e-v4-beta__V05__gpt-6.1-sol__t1-c43) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 44](#e-v4-beta__V05__gpt-6.1-sol__t1-c44) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 45](#e-v4-beta__V05__gpt-6.1-sol__t1-c45) | crewDetails.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 46](#e-v4-beta__V05__gpt-6.1-sol__t1-c46) | civilianDetails absent 781/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 56](#e-v4-beta__V05__gpt-6.1-sol__t1-c56) | C-10476 absent 1/1; C-13759 absent 1/1; C-16213 absent 1/1; C-17254 absent 1/1; C-17357 absent 1/1; C-19135 absent 1/1; C-2372 absent 1/1; C-3423 absent 1/1; C-9938 absent 1/1 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__claude-sonnet-5-5__t1 call 4](#e-v4-beta__V08__claude-sonnet-5-5__t1-c4) | commandingOfficerId absent 6/23; assignedCrewIds.crewId absent 1/23 | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V08__gpt-6.1-sol__t1 call 4](#e-v4-beta__V08__gpt-6.1-sol__t1-c4) | commandingOfficerId absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v4-delta__V05__claude-sonnet-5-5__t1-c25) | mappingOutcome absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v4-delta__V05__claude-sonnet-5-5__t1-c26) | resolution absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v4-delta__V05__claude-sonnet-5-5__t1-c27) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v4-delta__V05__claude-sonnet-5-5__t1-c29) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v4-delta__V05__claude-sonnet-5-5__t1-c30) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v4-delta__V05__claude-sonnet-5-5__t1-c31) | personnelId absent 621/721 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 33](#e-v4-delta__V05__claude-sonnet-5-5__t1-c33) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 34](#e-v4-delta__V05__claude-sonnet-5-5__t1-c34) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 35](#e-v4-delta__V05__claude-sonnet-5-5__t1-c35) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 36](#e-v4-delta__V05__claude-sonnet-5-5__t1-c36) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 37](#e-v4-delta__V05__claude-sonnet-5-5__t1-c37) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-delta__V05__claude-sonnet-5-5__t1-c38) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__gpt-6.1-sol__t1 call 17](#e-v4-delta__V05__gpt-6.1-sol__t1-c17) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 17](#e-v4-delta__V08__claude-sonnet-5-5__t1-c17) | mappingOutcome absent 6/23 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 19](#e-v4-delta__V08__claude-sonnet-5-5__t1-c19) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 22](#e-v4-delta__V08__claude-sonnet-5-5__t1-c22) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__gpt-6.1-sol__t1 call 14](#e-v4-delta__V08__gpt-6.1-sol__t1-c14) | personnelId absent 6/184; localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c18) | mappingOutcome absent 44/300; resolution absent 44/300 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c19) | personnelId absent 44/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 23](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c23) | personnel.personnelId absent 56/2421; personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c24) | key.personnel.details.rank absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c25) | key.personnel.personnelId absent 621/621 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 26](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c26) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c27) | personnel.details.rank absent 61/2421; personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 28](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c28) | personnel.personnelId absent 56/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c29) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c30) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c31) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c32) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 33](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c33) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 34](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c34) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 35](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c35) | personnel.details.rank absent 61/2421 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__gpt-6.1-sol__t1 call 14](#e-v4-epsilon__V05__gpt-6.1-sol__t1-c14) | details.rank absent 4/620 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V07__gpt-6.1-sol__t1 call 7](#e-v4-epsilon__V07__gpt-6.1-sol__t1-c7) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c18) | personnelId absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 19](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c19) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 21](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c21) | resolution absent 6/184; mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 11](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c11) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c12) | personnel.personnelId absent 8/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 13](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c13) | localRef absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 16](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c16) | mappingOutcome absent 6/184 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 30](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c30) | assignedCrewIds.* absent 300/300 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 59](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c59) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 64](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c64) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 65](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c65) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 66](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c66) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 67](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c67) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 68](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c68) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 69](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c69) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 70](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c70) | details.rank absent 219/1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 71](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c71) | personnelId absent 620/621 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 72](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c72) | personnelId absent 620/700 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 73](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c73) | personnelId absent 620/622 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 74](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c74) | personnelId absent 620/1015 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 75](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c75) | personnelId absent 620/780 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 76](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c76) | personnelId absent 620/750 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 77](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c77) | personnelId absent 620/633 | 1 observed; extra unknown | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 34](#e-v4-gamma__V05__gpt-6.1-sol__t1-c34) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 37](#e-v4-gamma__V05__gpt-6.1-sol__t1-c37) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 38](#e-v4-gamma__V05__gpt-6.1-sol__t1-c38) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 39](#e-v4-gamma__V05__gpt-6.1-sol__t1-c39) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v4-gamma__V05__gpt-6.1-sol__t1-c40) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 41](#e-v4-gamma__V05__gpt-6.1-sol__t1-c41) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v4-gamma__V05__gpt-6.1-sol__t1-c42) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v4-gamma__V05__gpt-6.1-sol__t1-c43) | details.rank absent 219/1000 | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V07__claude-sonnet-5-5__t1 call 8](#e-v4-gamma__V07__claude-sonnet-5-5__t1-c8) | type absent 39/39 | 1 observed; extra unknown | correct / not_established |

### P05. Refusal recovery loops

One episode begins with refusal, contains at least one further refused or structurally bad accepted call, then ends at the next structurally successful calculation or run end.

**V4 still allows:** yes. **Generic proposed fix:** Return all detectable argument problems together, with available source shapes and valid path examples.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V07__claude-sonnet-5-5__r2 call 6](#e-v1-delta__V07__claude-sonnet-5-5__r2-c6) | wrong calls [6, 7]; next structurally successful calculation 8; closed | extra=2 | correct / not_established |
| [V1 epsilon__V06__claude-sonnet-5-5__r4 call 13](#e-v1-epsilon__V06__claude-sonnet-5-5__r4-c13) | wrong calls [13, 14]; next structurally successful calculation None; unresolved | extra=2 | correct / not_established |
| [V1 epsilon__V07__claude-sonnet-5-5__r2 call 6](#e-v1-epsilon__V07__claude-sonnet-5-5__r2-c6) | wrong calls [6, 7]; next structurally successful calculation 8; closed | extra=2 | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 19](#e-v2-beta__V08__gpt-6.1-sol__t1-c19) | wrong calls [19, 20]; next structurally successful calculation 21; closed | extra=2 | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 25](#e-v3-beta__V05__claude-sonnet-5-5__t1-c25) | wrong calls [25, 26]; next structurally successful calculation 27; closed | extra=2 | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 25](#e-v3-beta__V05__gpt-6.1-sol__t1-c25) | wrong calls [25, 26]; next structurally successful calculation 27; closed | extra=2 | correct / not_established |
| [V3 beta__V08__gpt-6.1-sol__t1 call 8](#e-v3-beta__V08__gpt-6.1-sol__t1-c8) | wrong calls [8, 9]; next structurally successful calculation 10; closed | extra=2 | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 25](#e-v3-delta__V06__claude-sonnet-5-5__t1-c25) | wrong calls [25, 26]; next structurally successful calculation 27; closed | extra=2 | wrong_answer / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 23](#e-v4-beta__V05__gpt-6.1-sol__t1-c23) | wrong calls [23, 24]; next structurally successful calculation 25; closed | extra=2 | correct / not_established |
| [V4 beta__V08__gpt-6.1-sol__t1 call 9](#e-v4-beta__V08__gpt-6.1-sol__t1-c9) | wrong calls [9, 10]; next structurally successful calculation 11; closed | extra=2 | correct / not_established |
| [V4 epsilon__V07__gpt-6.1-sol__t1 call 5](#e-v4-epsilon__V07__gpt-6.1-sol__t1-c5) | wrong calls [5, 6]; next structurally successful calculation 7; closed | extra=2 | correct / not_established |

### P06. Wrong result selection while fuller data held

V2 Gamma V05 Claude call 27 selects a re-fetched 200-mission result although the missing 100 missions are already held.

**V4 still allows:** yes. **Generic proposed fix:** Warn when earlier compatible results contain omitted pages or records.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 27](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c27) | V2 Gamma V05 Claude call 27 selects a re-fetched 200-mission result although the missing 100 missions are already held. | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |

### P07. Re-fetch of already-held data

Identical stored reads or top-level returned collections with all returned fields held earlier. Nested crew coincidences are excluded. Motivation is unknown.

**V4 still allows:** yes. **Generic proposed fix:** Name earlier result ids and paths when a request repeats already-held data.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V2 beta__V05__claude-sonnet-5-5__t1 call 12](#e-v2-beta__V05__claude-sonnet-5-5__t1-c12) | [{"previous_call": 8, "previous_id": "2795-8", "kind": "identical request and stored text"}] | extra=1 | wrong_answer / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 17](#e-v2-delta__V06__claude-sonnet-5-5__t1-c17) | [{"path": "body.data.a", "records": 27, "identity_key": "missionId", "prior_sources": [{"call": 11, "id": "def3-11"}]}, {"path": "body.data.b", "records": 47, "identity_key": "missionId", "prior_sources": [{"call": 11, "id": "def3-11"}]}] | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V06__gpt-6.1-sol__t1 call 18](#e-v2-gamma__V06__gpt-6.1-sol__t1-c18) | [{"path": "body.data.a", "records": 47, "identity_key": "missionId", "prior_sources": [{"call": 10, "id": "f1a4-10"}, {"call": 13, "id": "f1a4-13"}]}, {"path": "body.data.b", "records": 27, "identity_key": "missionId", "prior_sources": [{"call": 10, "id": "f1a4-10"}, {"call": 13, "id": "f1a4-13"}]}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 11](#e-v3-delta__V08__claude-sonnet-5-5__t1-c11) | [{"path": "body.data.missionsPage.items", "records": 23, "identity_key": "missionId", "prior_sources": [{"call": 9, "id": "0039-9"}]}] | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V06__claude-sonnet-5-5__t1 call 28](#e-v3-gamma__V06__claude-sonnet-5-5__t1-c28) | [{"path": "body.data.a.items", "records": 47, "identity_key": "missionId", "prior_sources": [{"call": 20, "id": "13ed-20"}, {"call": 21, "id": "13ed-21"}, {"call": 22, "id": "13ed-22"}]}, {"path": "body.data.b.items", "records": 27, "identity_key": "missionId", "prior_sources": [{"call": 20, "id": "13ed-20"}, {"call": 21, "id": "13ed-21"}, {"call": 22, "id": "13ed-22"}]}] | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V06__gpt-6.1-sol__t1 call 23](#e-v3-gamma__V06__gpt-6.1-sol__t1-c23) | [{"path": "body.data.missionsPage.items", "records": 47, "identity_key": "missionId", "prior_sources": [{"call": 16, "id": "f1a4-16"}, {"call": 18, "id": "f1a4-18"}, {"call": 19, "id": "f1a4-19"}]}] | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V06__gpt-6.1-sol__t1 call 24](#e-v3-gamma__V06__gpt-6.1-sol__t1-c24) | [{"path": "body.data.missionsPage.items", "records": 27, "identity_key": "missionId", "prior_sources": [{"call": 16, "id": "f1a4-16"}, {"call": 18, "id": "f1a4-18"}, {"call": 19, "id": "f1a4-19"}]}] | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v4-delta__V05__claude-sonnet-5-5__t1-c28) | [{"path": "body.data.a.items", "records": 100, "identity_key": "personnelId", "prior_sources": [{"call": 17, "id": "f95b-17"}]}] | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 25](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c25) | [{"records": 200, "prior_sources": [{"call": 7, "id": "3932-7"}, {"call": 9, "id": "3932-9"}], "fields": ["commandingOfficerId", "assignedCrewIds"], "manually_verified": true}] | extra=1 | wrong_answer / not_established |

### P08. Record field applied to scalar IDs

A nonempty scalar-id set source is projected through a named record field, yielding None and silent empty intersections.

**V4 still allows:** yes. **Generic proposed fix:** Refuse named record fields on scalar-only sources and show the empty-field alternative.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 31](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c31) | shape-consistent count 1 | extra=1 | wrong_answer / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 31](#e-v4-delta__V05__claude-sonnet-5-5__t1-c31) | shape-consistent count 85 | extra=1 | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 71](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c71) | shape-consistent count 1 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 72](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c72) | shape-consistent count 69 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 73](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c73) | shape-consistent count 2 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 74](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c74) | shape-consistent count 297 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 75](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c75) | shape-consistent count 126 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 76](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c76) | shape-consistent count 110 | extra=1 | did_not_finish / contributed_to_limit_stop |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 77](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c77) | shape-consistent count 11 | extra=1 | did_not_finish / contributed_to_limit_stop |

### P09. Dotted output keys fail on reuse

Projection/grouping stores literal dotted keys; subsequent field traversal interprets them as nested keys and silently returns None.

**V4 still allows:** yes. **Generic proposed fix:** Preserve nesting or warn/refuse with a usable literal-key access syntax.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V05__gpt-6.1-sol__r1 call 11](#e-v1-delta__V05__gpt-6.1-sol__r1-c11) | details.rank absent 621/621 | extra=1 | did_not_finish / not_established |
| [V1 epsilon__V05__claude-sonnet-5-5__r3 call 21](#e-v1-epsilon__V05__claude-sonnet-5-5__r3-c21) | key.details.rank absent 621/621 | extra=1 | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 10](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c10) | details.rank absent 621/621 | extra=1 | did_not_finish / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 22](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c22) | details.rank absent 781/781 | extra=1 | wrong_answer / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c11) | details.rank absent 310/310 | extra=1 | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 41](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c41) | details.rank absent 1/1 | extra=1 | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 43](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c43) | details.rank absent 569/569 | extra=1 | wrong_answer / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v3-delta__V05__claude-sonnet-5-5__t1-c26) | personnel.details.rank absent 621/621 | extra=1 | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 30](#e-v3-delta__V05__claude-sonnet-5-5__t1-c30) | personnel.details.rank absent 2360/2360 | extra=1 | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 37](#e-v4-beta__V05__claude-sonnet-5-5__t1-c37) | crewDetails.rank absent 801/801 | extra=1 | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-beta__V05__claude-sonnet-5-5__t1-c38) | crewDetails.rank absent 801/801 | extra=1 | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 24](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c24) | key.personnel.details.rank absent 621/621 | extra=1 | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c25) | key.personnel.personnelId absent 621/621 | extra=1 | correct / not_established |

### P10. Object wildcard is a one-item no-op

Wildcard wraps a dictionary as one item instead of traversing its values. Later path steps can discard the whole item.

**V4 still allows:** yes. **Generic proposed fix:** Warn/refuse when wildcard targets an object, stating that only arrays expand.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 beta__V05__gpt-6.1-sol__r1 call 21](#e-v1-beta__V05__gpt-6.1-sol__r1-c21) | [{"source": {"path": "records.0.*", "result_id": "47f5-19"}, "prefix": "records.0", "objects": 1, "key_samples": ["C-1008", "C-1011", "C-1017", "C-1025", "C-10476"]}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V08__gpt-6.1-sol__r3 call 8](#e-v1-beta__V08__gpt-6.1-sol__r3-c8) | [{"source": {"path": "content.entries.*", "result_id": "2962-3"}, "prefix": "content.entries", "objects": 1, "key_samples": ["C-71", "C-78", "C-85", "C-92", "C-99"]}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 14](#e-v1-delta__V05__gpt-6.1-sol__r1-c14) | [{"source": {"path": "groups.*.key.*", "result_id": "7c44-10"}, "prefix": "groups.*.key", "objects": 621, "key_samples": ["details.rank", "personnelId"]}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 24](#e-v1-gamma__V08__gpt-6.1-sol__r3-c24) | [{"source": {"path": "body.data.*.items", "result_id": "7aeb-20"}, "prefix": "body.data", "objects": 1, "key_samples": ["p1", "p2", "p3", "p4", "p5"]}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 25](#e-v2-beta__V05__claude-sonnet-5-5__t1-c25) | [{"source": {"path": "value.*", "result_id": "2795-13"}, "prefix": "value", "objects": 1, "key_samples": ["C-1008", "C-1011", "C-1017", "C-1025", "C-1042"]}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 24](#e-v2-beta__V05__gpt-6.1-sol__t1-c24) | [{"source": {"path": "records.*.*", "result_id": "532c-22"}, "prefix": "records.*", "objects": 1, "key_samples": ["C-1008", "C-1011", "C-1017", "C-1025", "C-10476"]}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c19) | [{"source": {"path": "body.data.*.items.*", "result_id": "81c0-17"}, "prefix": "body.data", "objects": 1, "key_samples": ["p0", "p1", "p2", "p3", "p4"]}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 32](#e-v2-gamma__V05__gpt-6.1-sol__t1-c32) | [{"source": {"path": "body.data.*.items", "result_id": "910b-27"}, "prefix": "body.data", "objects": 1, "key_samples": ["a", "b", "c", "d"]}, {"source": {"path": "body.data.*.items", "result_id": "910b-28"}, "prefix": "body.data", "objects": 1, "key_samples": ["a", "b", "c", "d", "e"]}] | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 33](#e-v2-gamma__V05__gpt-6.1-sol__t1-c33) | [{"source": {"path": "body.data.*", "result_id": "910b-24"}, "prefix": "body.data", "objects": 1, "key_samples": ["a", "b"]}, {"source": {"path": "body.data.*", "result_id": "910b-25"}, "prefix": "body.data", "objects": 1, "key_samples": ["a", "b"]}, {"source": {"path": "body.data.*", "result_id": "910b-26"}, "prefix": "body.data", "objects": 1, "key_samples": ["a", "b", "c"]}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 26](#e-v3-beta__V05__claude-sonnet-5-5__t1-c26) | [{"source": {"path": "content.entries.*", "result_id": "2795-8"}, "prefix": "content.entries", "objects": 1, "key_samples": ["C-71", "C-78", "C-85", "C-92", "C-99"]}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 24](#e-v3-beta__V05__gpt-6.1-sol__t1-c24) | [{"source": {"path": "records.*.*", "result_id": "532c-22"}, "prefix": "records.*", "objects": 1, "key_samples": ["C-1008", "C-1011", "C-2372"]}] | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 37](#e-v3-gamma__V05__gpt-6.1-sol__t1-c37) | [{"source": {"path": "body.data.*.items", "result_id": "910b-33"}, "prefix": "body.data", "objects": 1, "key_samples": ["p1", "p2", "p3"]}, {"source": {"path": "body.data.*.items", "result_id": "910b-34"}, "prefix": "body.data", "objects": 1, "key_samples": ["p4", "p5", "p6"]}, {"source": {"path": "body.data.*.items", "result_id": "910b-35"}, "prefix": "body.data", "objects": 1, "key_samples": ["p7", "p8", "p9"]}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__gpt-6.1-sol__t1 call 14](#e-v4-beta__V05__gpt-6.1-sol__t1-c14) | [{"source": {"path": "content.entries.*", "result_id": "532c-2"}, "prefix": "content.entries", "objects": 1, "key_samples": ["C-71", "C-78", "C-85", "C-92", "C-99"]}] | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 24](#e-v4-gamma__V05__gpt-6.1-sol__t1-c24) | [{"source": {"path": "body.data.*.items.*.commandingOfficerId", "result_id": "910b-22"}, "prefix": "body.data", "objects": 1, "key_samples": ["p1", "p2"]}, {"source": {"path": "body.data.*.items.*.assignedCrewIds.*", "result_id": "910b-22"}, "prefix": "body.data", "objects": 1, "key_samples": ["p1", "p2"]}] | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V08__gpt-6.1-sol__t1 call 31](#e-v4-gamma__V08__gpt-6.1-sol__t1-c31) | [{"source": {"path": "body.data.*.items", "result_id": "6b14-28"}, "prefix": "body.data", "objects": 1, "key_samples": ["p1", "p2", "p3", "p4", "p5"]}] | 1 observed; extra unknown | correct / not_established |

### P11. Intersection across page partitions

An intersection intersects every page/role source independently instead of unioning partitions before intersecting a rank subset.

**V4 still allows:** yes. **Generic proposed fix:** Print the set algebra and per-source cardinalities; warn about disjoint partition-like inputs.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 32](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c32) | {"all_sources_count": 0, "rank_source_index_1based": 5, "rank_intersect_union_other_sources": 1} | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 66](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c66) | {"all_sources_count": 0, "rank_source_index_1based": 1, "rank_intersect_union_other_sources": 1} | 1 observed; extra unknown | correct / not_established |

### P12. Stored output truncated

Successful rendering cuts the stored list below its declared total. All observed producers use the old 50k-character cap; V4 retains a 5M cap.

**V4 still allows:** yes. **Generic proposed fix:** Preserve exact stored data and page display, or refuse when the exact result cannot be retained.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V06__gpt-6.1-sol__ref call 26](#e-v1-alpha__V06__gpt-6.1-sol__ref-c26) | true | 1 observed; extra unknown | correct / not_established |
| [V1 alpha__V06__gpt-6.1-sol__ref call 28](#e-v1-alpha__V06__gpt-6.1-sol__ref-c28) | true | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V06__gpt-6.1-sol__r2 call 8](#e-v1-beta__V06__gpt-6.1-sol__r2-c8) | true | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 9](#e-v1-delta__V05__gpt-6.1-sol__r1-c9) | true | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 11](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c11) | true | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | true | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 25](#e-v2-beta__V05__gpt-6.1-sol__t1-c25) | true | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 38](#e-v2-beta__V05__gpt-6.1-sol__t1-c38) | true | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V06__gpt-6.1-sol__t1 call 8](#e-v2-beta__V06__gpt-6.1-sol__t1-c8) | true | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 12](#e-v2-delta__V05__gpt-6.1-sol__t1-c12) | true | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 14](#e-v2-delta__V05__gpt-6.1-sol__t1-c14) | true | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 16](#e-v2-delta__V05__gpt-6.1-sol__t1-c16) | true | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c10) | true | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c12) | true | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c13) | true | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 16](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c16) | true | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 31](#e-v2-gamma__V05__gpt-6.1-sol__t1-c31) | true | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 34](#e-v2-gamma__V05__gpt-6.1-sol__t1-c34) | true | 1 observed; extra unknown | correct / not_established |

### P13. Shortened intermediate consumed

Later calculation reads a stored list shorter than its declared count because of a limit, view page or render cut. Not every limited use is wrong.

**V4 still allows:** yes. **Generic proposed fix:** Propagate completeness and lineage; warn/refuse totals computed from partial lists.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V06__gpt-6.1-sol__ref call 27](#e-v1-alpha__V06__gpt-6.1-sol__ref-c27) | producer call 26: 36 stored of 72 | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 13](#e-v1-delta__V05__gpt-6.1-sol__r1-c13) | producer call 9: 249 stored of 998 | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 13](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c13) | producer call 12: 249 stored of 998 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 37](#e-v2-beta__V05__gpt-6.1-sol__t1-c37) | producer call 25: 125 stored of 1000 | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 13](#e-v2-delta__V05__gpt-6.1-sol__t1-c13) | producer call 12: 310 stored of 621 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c11) | producer call 10: 310 stored of 621 | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 18](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c18) | producer call 12: 310 stored of 621 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 41](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c41) | producer call 40: 1 stored of 569 | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 38](#e-v2-gamma__V05__gpt-6.1-sol__t1-c38) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 39](#e-v2-gamma__V05__gpt-6.1-sol__t1-c39) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 40](#e-v2-gamma__V05__gpt-6.1-sol__t1-c40) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 41](#e-v2-gamma__V05__gpt-6.1-sol__t1-c41) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 42](#e-v2-gamma__V05__gpt-6.1-sol__t1-c42) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 43](#e-v2-gamma__V05__gpt-6.1-sol__t1-c43) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 44](#e-v2-gamma__V05__gpt-6.1-sol__t1-c44) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 45](#e-v2-gamma__V05__gpt-6.1-sol__t1-c45) | producer call 34: 500 stored of 1000; producer call 37: 500 stored of 1000 | 1 observed; extra unknown | correct / not_established |

### P14. Arguments silently ignored

Nonempty arguments have no effect for the selected operation, including fields or offset on unsupported operations.

**V4 still allows:** yes. **Generic proposed fix:** Refuse parameters that do not apply to the chosen operation.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V06__gpt-6.1-sol__ref call 28](#e-v1-alpha__V06__gpt-6.1-sol__ref-c28) | {"fields": ["missionId", "type"]} | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V06__gpt-6.1-sol__r2 call 8](#e-v1-beta__V06__gpt-6.1-sol__r2-c8) | {"fields": ["missionId", "type"]} | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | {"fields": ["key"]} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V06__gpt-6.1-sol__t1 call 8](#e-v2-beta__V06__gpt-6.1-sol__t1-c8) | {"fields": ["missionId", "type"]} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 8](#e-v2-beta__V08__gpt-6.1-sol__t1-c8) | {"fields": ["C-106", "C-113", "C-1262", "C-1610", "C-1615", "C-1638", "C-17254", "C-1769", "C-2006", "C-2237", "C-2364", "C-2372", "C-258", "C-2776", "C-2782", "C-2850", "C-3104", "C-3145", "C-3237", "C-3380", "C-3500", "C-3635", "C-3690", "C-3703", "C-3717", "C-3727", "C-3754", "C-382", "C-3887", "C-4014", "C-4111", "C-4155", "C-4165", "C-4225", "C-4333", "C-4469", "C-4488", "C-4514", "C-4562", "C-4766", "C-4809", "C-4828", "C-5006", "C-5161", "C-5280", "C-5408", "C-5412", "C-5490", "C-5610", "C-5782", "C-594", "C-599", "C-602", "C-6029", "C-6069", "C-6313", "C-6671", "C-6721", "C-6737", "C-6741", "C-6798", "C-6851", "C-699", "C-7019", "C-7042", "C-71", "C-7116", "C-7316", "C-7401", "C-7653", "C-7738", "C-78", "C-7892", "C-7927", "C-7952", "C-8037", "C-8112", "C-8116", "C-8158", "C-8163", "C-8173", "C-8229", "C-8280", "C-832", "C-8380", "C-8382", "C-8564", "C-8565", "C-8603", "C-8607", "C-8755", "C-8761", "C-881", "C-8831", "C-9137", "C-92", "C-9267", "C-9285", "C-960", "C-965", "C-9705", "C-9829", "C-99", "C-9927", "C-9933", "C-9994"]} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 17](#e-v2-delta__V05__gpt-6.1-sol__t1-c17) | {"offset": 310} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__gpt-6.1-sol__t1 call 3](#e-v3-delta__V05__gpt-6.1-sol__t1-c3) | {"offset": 6} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V06__claude-sonnet-5-5__t1 call 27](#e-v3-gamma__V06__claude-sonnet-5-5__t1-c27) | {"field": "assignedAssetIds"} | 1 observed; extra unknown | correct / not_established |

### P15. Absent field satisfies predicate (exposures)

Missing is converted to None and satisfies eq null or ne a non-null literal. Intentional null tests are included as exposures.

**V4 still allows:** yes. **Generic proposed fix:** Distinguish missing from explicit null and report missing-field matches.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V05__claude-sonnet-5-5__r3 call 30](#e-v1-delta__V05__claude-sonnet-5-5__r3-c30) | [{"condition": {"field": "details.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 31](#e-v1-delta__V05__claude-sonnet-5-5__r3-c31) | [{"condition": {"field": "details.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 8](#e-v1-delta__V06__gpt-6.1-sol__r2-c8) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 9](#e-v1-delta__V06__gpt-6.1-sol__r2-c9) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 10](#e-v1-delta__V06__gpt-6.1-sol__r2-c10) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 11](#e-v1-delta__V06__gpt-6.1-sol__r2-c11) | [{"condition": {"field": "assets.24.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 99}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 8](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c8) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 9](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c9) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 10](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c10) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 47](#e-v1-gamma__V05__gpt-6.1-sol__r1-c47) | [{"condition": {"field": "details.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 26](#e-v2-beta__V05__claude-sonnet-5-5__t1-c26) | [{"condition": {"field": "crewDetails.rank", "op": "ne", "value": "CREWMAN"}, "records": 119}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 43](#e-v2-beta__V05__gpt-6.1-sol__t1-c43) | [{"condition": {"field": "crewDetails.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v2-delta__V06__claude-sonnet-5-5__t1-c13) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 12](#e-v2-delta__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 13](#e-v2-delta__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 14](#e-v2-delta__V06__gpt-6.1-sol__t1-c14) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 16](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c16) | [{"condition": {"field": "details.rank", "op": "ne", "value": "CREWMAN"}, "records": 17}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 9](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c9) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c10) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.24.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 1}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 31](#e-v3-beta__V05__claude-sonnet-5-5__t1-c31) | [{"condition": {"field": "crewDetails.rank", "op": "ne", "value": "CREWMAN"}, "records": 119}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__claude-sonnet-5-5__t1 call 35](#e-v3-beta__V05__claude-sonnet-5-5__t1-c35) | [{"condition": {"field": "crewDetails.rank", "op": "ne", "value": "CREWMAN"}, "records": 19}, {"condition": {"field": "crewDetails.rank", "op": "ne", "value": "CHIEF_PETTY_OFFICER"}, "records": 19}, {"condition": {"field": "crewDetails.rank", "op": "ne", "value": "LIEUTENANT"}, "records": 19}, {"condition": {"field": "crewDetails.rank", "op": "ne", "value": "ENSIGN"}, "records": 19}] | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 47](#e-v3-beta__V05__gpt-6.1-sol__t1-c47) | [{"condition": {"field": "crewDetails.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V05__claude-sonnet-5-5__t1-c28) | [{"condition": {"field": "personnel.details.rank", "op": "eq", "value": null}, "records": 61}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V06__claude-sonnet-5-5__t1-c21) | [{"condition": {"field": "assets.2.mappingOutcome", "op": "ne", "value": "x"}, "records": 269}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 23](#e-v3-delta__V06__claude-sonnet-5-5__t1-c23) | [{"condition": {"field": "assets.2.resolution", "op": "ne", "value": "RESOLVED"}, "records": 269}, {"condition": {"field": "assets.2.resolution", "op": "ne", "value": "zzz"}, "records": 269}] | 1 observed; extra unknown | wrong_answer / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 11](#e-v3-delta__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 12](#e-v3-delta__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 13](#e-v3-delta__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c30) | [{"condition": {"field": "details.rank", "op": "eq", "value": null}, "records": 219}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__claude-sonnet-5-5__t1 call 15](#e-v3-epsilon__V06__claude-sonnet-5-5__t1-c15) | [{"condition": {"field": "asset.status", "op": "ne", "value": "ACTIVE"}, "records": 108}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c10) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 59}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 88}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "records": 271}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 15](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c15) | [{"condition": {"field": "asset.status", "op": "ne", "value": "ACTIVE"}, "records": 44}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 44](#e-v4-beta__V05__claude-sonnet-5-5__t1-c44) | [{"condition": {"field": "crewDetails.rank", "op": "eq", "value": null}, "records": 20}] | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 25](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c25) | [{"condition": {"field": "key.personnel.personnelId", "op": "eq", "value": null}, "records": 621}] | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 27](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c27) | [{"condition": {"field": "personnel.details.rank", "op": "eq", "value": null}, "records": 61}] | 1 observed; extra unknown | correct / not_established |

### P16. Fixed positions for any-element task

V06 filters inspect numeric list positions although the task asks about any asset. Individual calls are exposures; a later complete union can repair them.

**V4 still allows:** yes. **Generic proposed fix:** Warn about position-only coverage, observed list lengths and the any-element alternative.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V06__gpt-6.1-sol__r2 call 8](#e-v1-delta__V06__gpt-6.1-sol__r2-c8) | [{"condition": {"field": "assets.0.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 9](#e-v1-delta__V06__gpt-6.1-sol__r2-c9) | [{"condition": {"field": "assets.1.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 10](#e-v1-delta__V06__gpt-6.1-sol__r2-c10) | [{"condition": {"field": "assets.2.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V06__gpt-6.1-sol__r2 call 11](#e-v1-delta__V06__gpt-6.1-sol__r2-c11) | [{"condition": {"field": "assets.24.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}, {"condition": {"field": "assets.24.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.24.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 8](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c8) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 9](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c9) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V06__gpt-6.1-sol__r2 call 10](#e-v1-epsilon__V06__gpt-6.1-sol__r2-c10) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v2-delta__V06__claude-sonnet-5-5__t1-c13) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 11](#e-v2-delta__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.2", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 12](#e-v2-delta__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 13](#e-v2-delta__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 14](#e-v2-delta__V06__gpt-6.1-sol__t1-c14) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 15](#e-v2-delta__V06__gpt-6.1-sol__t1-c15) | [{"condition": {"field": "assets.3", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 9](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c9) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c10) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.3", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.24.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.24.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V06__claude-sonnet-5-5__t1-c17) | [{"condition": {"field": "assets.0.asset.status", "op": "eq", "value": "DESTROYED"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 18](#e-v3-delta__V06__claude-sonnet-5-5__t1-c18) | [{"condition": {"field": "assets.0.asset.status", "op": "eq", "value": "MISSING"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 19](#e-v3-delta__V06__claude-sonnet-5-5__t1-c19) | [{"condition": {"field": "assets.1.asset.status", "op": "eq", "value": "DESTROYED"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 20](#e-v3-delta__V06__claude-sonnet-5-5__t1-c20) | [{"condition": {"field": "assets.1.asset.status", "op": "eq", "value": "MISSING"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V06__claude-sonnet-5-5__t1-c21) | [{"condition": {"field": "assets.2.mappingOutcome", "op": "ne", "value": "x"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 22](#e-v3-delta__V06__claude-sonnet-5-5__t1-c22) | [{"condition": {"field": "assets.2.resolution", "op": "eq", "value": "RESOLVED"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 23](#e-v3-delta__V06__claude-sonnet-5-5__t1-c23) | [{"condition": {"field": "assets.2.resolution", "op": "ne", "value": "RESOLVED"}, "max_list_length": 50}, {"condition": {"field": "assets.2.resolution", "op": "ne", "value": "zzz"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 24](#e-v3-delta__V06__claude-sonnet-5-5__t1-c24) | [{"condition": {"field": "assets.3.resolution", "op": "eq", "value": "RESOLVED"}, "max_list_length": 50}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 27](#e-v3-delta__V06__claude-sonnet-5-5__t1-c27) | [{"condition": {"field": "assets.2.asset.status", "op": "eq", "value": "DESTROYED"}, "max_list_length": 4}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__claude-sonnet-5-5__t1 call 28](#e-v3-delta__V06__claude-sonnet-5-5__t1-c28) | [{"condition": {"field": "assets.2.asset.status", "op": "eq", "value": "MISSING"}, "max_list_length": 4}] | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |
| [V3 delta__V06__gpt-6.1-sol__t1 call 11](#e-v3-delta__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 12](#e-v3-delta__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 13](#e-v3-delta__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V06__gpt-6.1-sol__t1 call 14](#e-v3-delta__V06__gpt-6.1-sol__t1-c14) | [{"condition": {"field": "assets.3", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 10](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c10) | [{"condition": {"field": "assets.0.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.0.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.0.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 11](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c11) | [{"condition": {"field": "assets.1.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.1.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.1.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c12) | [{"condition": {"field": "assets.2.asset.status", "op": "ne", "value": null}, "max_list_length": 50}, {"condition": {"field": "assets.2.asset.status", "op": "ne", "value": "ACTIVE"}, "max_list_length": 50}, {"condition": {"field": "assets.2.mappingOutcome", "op": "eq", "value": "MAPPED"}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V06__gpt-6.1-sol__t1 call 13](#e-v3-epsilon__V06__gpt-6.1-sol__t1-c13) | [{"condition": {"field": "assets.3", "op": "ne", "value": null}, "max_list_length": 50}] | 1 observed; extra unknown | correct / not_established |

### P17. Scalar comparison against collection

Non-null scalar literal compared to a list/object without elements. Null existence tests are excluded.

**V4 still allows:** yes. **Generic proposed fix:** Refuse collection/scalar comparison unless explicitly requested.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V3 gamma__V06__claude-sonnet-5-5__t1 call 27](#e-v3-gamma__V06__claude-sonnet-5-5__t1-c27) | [{"condition": {"field": "assignedAssetIds", "op": "eq", "value": "EQ-86"}, "collection_values": 300}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 16](#e-v4-beta__V05__claude-sonnet-5-5__t1-c16) | [{"condition": {"field": "assignedCrewIds", "op": "ne", "value": ""}, "collection_values": 283}] | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 17](#e-v4-beta__V05__claude-sonnet-5-5__t1-c17) | [{"condition": {"field": "assignedCrewIds", "op": "eq", "value": ""}, "collection_values": 283}] | 1 observed; extra unknown | correct / not_established |

### P18. Contradictory any/none conditions

Identical field/op/value is required with both any and none. Zero is mathematically correct, but the impossible input is silently accepted.

**V4 still allows:** yes. **Generic proposed fix:** Refuse directly contradictory predicates and show the conflicting pair.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V4 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v4-delta__V06__claude-sonnet-5-5__t1-c13) | [[{"elements": "any", "field": "assets.*.asset.status", "op": "ne", "value": "ACTIVE"}, {"elements": "none", "field": "assets.*.asset.status", "op": "ne", "value": "ACTIVE"}]] | extra=1 | correct / not_established |

### P19. Null counted as set member (exposures)

Pre-render distinct/set output contains a null member counted in count, sometimes corrected later.

**V4 still allows:** yes. **Generic proposed fix:** Report null members separately from non-null cardinality.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V05__claude-sonnet-5-5__r3 call 18](#e-v1-delta__V05__claude-sonnet-5-5__r3-c18) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V08__gpt-6.1-sol__r3 call 7](#e-v1-delta__V08__gpt-6.1-sol__r3-c7) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__claude-sonnet-5-5__r3 call 31](#e-v1-gamma__V05__claude-sonnet-5-5__r3-c31) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__claude-sonnet-5-5__r3 call 43](#e-v1-gamma__V05__claude-sonnet-5-5__r3-c43) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 20](#e-v1-gamma__V05__gpt-6.1-sol__r1-c20) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 38](#e-v1-gamma__V05__gpt-6.1-sol__r1-c38) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__claude-sonnet-5-5__r1 call 20](#e-v1-gamma__V08__claude-sonnet-5-5__r1-c20) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 14](#e-v1-gamma__V08__gpt-6.1-sol__r3-c14) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 21](#e-v1-gamma__V08__gpt-6.1-sol__r3-c21) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V08__gpt-6.1-sol__r3 call 26](#e-v1-gamma__V08__gpt-6.1-sol__r3-c26) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 29](#e-v2-beta__V05__gpt-6.1-sol__t1-c29) | {"count": 95, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 30](#e-v2-beta__V05__gpt-6.1-sol__t1-c30) | {"count": 99, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 35](#e-v2-beta__V05__gpt-6.1-sol__t1-c35) | {"count": 29, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 36](#e-v2-beta__V05__gpt-6.1-sol__t1-c36) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 18](#e-v2-delta__V05__claude-sonnet-5-5__t1-c18) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 12](#e-v2-delta__V05__gpt-6.1-sol__t1-c12) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 14](#e-v2-delta__V05__gpt-6.1-sol__t1-c14) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V08__gpt-6.1-sol__t1 call 12](#e-v2-delta__V08__gpt-6.1-sol__t1-c12) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c18) | {"count": 570, "contains_null": true} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c12) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c13) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 17](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c17) | {"count": 3, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c18) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 20](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c20) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c10) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 27](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c27) | {"count": 578, "contains_null": true} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 33](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c33) | {"count": 570, "contains_null": true} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 17](#e-v2-gamma__V05__gpt-6.1-sol__t1-c17) | {"count": 497, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 22](#e-v2-gamma__V05__gpt-6.1-sol__t1-c22) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 29](#e-v2-gamma__V05__gpt-6.1-sol__t1-c29) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 33](#e-v2-gamma__V05__gpt-6.1-sol__t1-c33) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 35](#e-v2-gamma__V05__gpt-6.1-sol__t1-c35) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V08__gpt-6.1-sol__t1 call 19](#e-v2-gamma__V08__gpt-6.1-sol__t1-c19) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V08__gpt-6.1-sol__t1 call 35](#e-v2-gamma__V08__gpt-6.1-sol__t1-c35) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 28](#e-v3-beta__V05__gpt-6.1-sol__t1-c28) | {"count": 95, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 29](#e-v3-beta__V05__gpt-6.1-sol__t1-c29) | {"count": 99, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 36](#e-v3-beta__V05__gpt-6.1-sol__t1-c36) | {"count": 29, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 37](#e-v3-beta__V05__gpt-6.1-sol__t1-c37) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V05__gpt-6.1-sol__t1 call 48](#e-v3-beta__V05__gpt-6.1-sol__t1-c48) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__claude-sonnet-5-5__t1 call 21](#e-v3-delta__V05__claude-sonnet-5-5__t1-c21) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V05__gpt-6.1-sol__t1 call 16](#e-v3-delta__V05__gpt-6.1-sol__t1-c16) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 15](#e-v3-delta__V08__claude-sonnet-5-5__t1-c15) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__claude-sonnet-5-5__t1 call 17](#e-v3-delta__V08__claude-sonnet-5-5__t1-c17) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v3-epsilon__V05__claude-sonnet-5-5__t1-c19) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V05__gpt-6.1-sol__t1 call 17](#e-v3-epsilon__V05__gpt-6.1-sol__t1-c17) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__claude-sonnet-5-5__t1 call 14](#e-v3-epsilon__V08__claude-sonnet-5-5__t1-c14) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 29](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c29) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 42](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c42) | {"count": 2, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__claude-sonnet-5-5__t1 call 44](#e-v3-gamma__V05__claude-sonnet-5-5__t1-c44) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 20](#e-v3-gamma__V05__gpt-6.1-sol__t1-c20) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V05__gpt-6.1-sol__t1 call 36](#e-v3-gamma__V05__gpt-6.1-sol__t1-c36) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V08__claude-sonnet-5-5__t1 call 22](#e-v3-gamma__V08__claude-sonnet-5-5__t1-c22) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V08__gpt-6.1-sol__t1 call 14](#e-v3-gamma__V08__gpt-6.1-sol__t1-c14) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V08__gpt-6.1-sol__t1 call 20](#e-v3-gamma__V08__gpt-6.1-sol__t1-c20) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 9](#e-v4-beta__V05__claude-sonnet-5-5__t1-c9) | {"count": 87, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 10](#e-v4-beta__V05__claude-sonnet-5-5__t1-c10) | {"count": 274, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V05__claude-sonnet-5-5__t1 call 12](#e-v4-beta__V05__claude-sonnet-5-5__t1-c12) | {"count": 352, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 25](#e-v4-delta__V05__claude-sonnet-5-5__t1-c25) | {"count": 3, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 26](#e-v4-delta__V05__claude-sonnet-5-5__t1-c26) | {"count": 3, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 27](#e-v4-delta__V05__claude-sonnet-5-5__t1-c27) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__claude-sonnet-5-5__t1 call 29](#e-v4-delta__V05__claude-sonnet-5-5__t1-c29) | {"count": 8, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V05__gpt-6.1-sol__t1 call 15](#e-v4-delta__V05__gpt-6.1-sol__t1-c15) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 19](#e-v4-delta__V08__claude-sonnet-5-5__t1-c19) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__claude-sonnet-5-5__t1 call 22](#e-v4-delta__V08__claude-sonnet-5-5__t1-c22) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__claude-sonnet-5-5__t1 call 19](#e-v4-epsilon__V05__claude-sonnet-5-5__t1-c19) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v4-epsilon__V05__gpt-6.1-sol__t1-c12) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__claude-sonnet-5-5__t1 call 18](#e-v4-epsilon__V08__claude-sonnet-5-5__t1-c18) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c12) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V08__gpt-6.1-sol__t1 call 13](#e-v4-epsilon__V08__gpt-6.1-sol__t1-c13) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 29](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c29) | {"count": 87, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 30](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c30) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 31](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c31) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 62](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c62) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | did_not_finish / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 24](#e-v4-gamma__V05__gpt-6.1-sol__t1-c24) | {"count": 497, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 25](#e-v4-gamma__V05__gpt-6.1-sol__t1-c25) | {"count": 630, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 31](#e-v4-gamma__V05__gpt-6.1-sol__t1-c31) | {"count": 621, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__gpt-6.1-sol__t1 call 35](#e-v4-gamma__V05__gpt-6.1-sol__t1-c35) | {"count": 1, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V08__gpt-6.1-sol__t1 call 20](#e-v4-gamma__V08__gpt-6.1-sol__t1-c20) | {"count": 107, "contains_null": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V08__gpt-6.1-sol__t1 call 26](#e-v4-gamma__V08__gpt-6.1-sol__t1-c26) | {"count": 105, "contains_null": true} | 1 observed; extra unknown | correct / not_established |

### P20. Composite groups split an ID (exposures)

group_by includes a personnelId plus other attributes and multiple groups share an id, including null. Some V08 diagnostics deliberately do this.

**V4 still allows:** yes. **Generic proposed fix:** Show component-key cardinalities and warn that composite groups are not unique ids.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 delta__V05__gpt-6.1-sol__r1 call 9](#e-v1-delta__V05__gpt-6.1-sol__r1-c9) | {"groups": 998, "identity_values": 621, "identity_field": "personnelId"} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | {"groups": 998, "identity_values": 621, "identity_field": "personnelId"} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c12) | {"groups": 107, "identity_values": 105, "identity_field": "personnelId"} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V08__gpt-6.1-sol__t1 call 13](#e-v3-delta__V08__gpt-6.1-sol__t1-c13) | {"groups": 107, "identity_values": 105, "identity_field": "personnelId"} | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v3-epsilon__V08__gpt-6.1-sol__t1-c12) | {"groups": 107, "identity_values": 105, "identity_field": "personnelId"} | 1 observed; extra unknown | correct / not_established |
| [V4 delta__V08__gpt-6.1-sol__t1 call 14](#e-v4-delta__V08__gpt-6.1-sol__t1-c14) | {"groups": 107, "identity_values": 105, "identity_field": "personnelId"} | 1 observed; extra unknown | correct / not_established |

### P21. Long calculate output shown in full

V1/V2 successful calculation text exceeds 5000 characters and is displayed in full. V3/V4 remove this behavior.

**V4 still allows:** no. **Generic proposed fix:** Keep exact data in storage with a bounded preview and page access.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V05__claude-sonnet-5-5__ref call 22](#e-v1-alpha__V05__claude-sonnet-5-5__ref-c22) | {"characters": 6313, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 alpha__V05__gpt-6.1-sol__ref call 56](#e-v1-alpha__V05__gpt-6.1-sol__ref-c56) | {"characters": 6313, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 alpha__V06__gpt-6.1-sol__ref call 26](#e-v1-alpha__V06__gpt-6.1-sol__ref-c26) | {"characters": 31015, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 alpha__V06__gpt-6.1-sol__ref call 28](#e-v1-alpha__V06__gpt-6.1-sol__ref-c28) | {"characters": 31015, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V05__claude-sonnet-5-5__r3 call 10](#e-v1-beta__V05__claude-sonnet-5-5__r3-c10) | {"characters": 6316, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__gpt-6.1-sol__r1 call 14](#e-v1-beta__V05__gpt-6.1-sol__r1-c14) | {"characters": 6313, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__gpt-6.1-sol__r1 call 20](#e-v1-beta__V05__gpt-6.1-sol__r1-c20) | {"characters": 13792, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V05__gpt-6.1-sol__r1 call 21](#e-v1-beta__V05__gpt-6.1-sol__r1-c21) | {"characters": 13795, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 beta__V06__gpt-6.1-sol__r2 call 8](#e-v1-beta__V06__gpt-6.1-sol__r2-c8) | {"characters": 31014, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V06__gpt-6.1-sol__r2 call 9](#e-v1-beta__V06__gpt-6.1-sol__r2-c9) | {"characters": 5369, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V08__gpt-6.1-sol__r3 call 8](#e-v1-beta__V08__gpt-6.1-sol__r3-c8) | {"characters": 17582, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 18](#e-v1-delta__V05__claude-sonnet-5-5__r3-c18) | {"characters": 7528, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__claude-sonnet-5-5__r3 call 31](#e-v1-delta__V05__claude-sonnet-5-5__r3-c31) | {"characters": 6420, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 9](#e-v1-delta__V05__gpt-6.1-sol__r1-c9) | {"characters": 28386, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 10](#e-v1-delta__V05__gpt-6.1-sol__r1-c10) | {"characters": 49073, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 delta__V05__gpt-6.1-sol__r1 call 15](#e-v1-delta__V05__gpt-6.1-sol__r1-c15) | {"characters": 22675, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__claude-sonnet-5-5__r3 call 20](#e-v1-epsilon__V05__claude-sonnet-5-5__r3-c20) | {"characters": 49073, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 9](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c9) | {"characters": 49072, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 11](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c11) | {"characters": 35013, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 12](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c12) | {"characters": 28387, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 epsilon__V05__gpt-6.1-sol__r1 call 14](#e-v1-epsilon__V05__gpt-6.1-sol__r1-c14) | {"characters": 13946, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__claude-sonnet-5-5__r3 call 31](#e-v1-gamma__V05__claude-sonnet-5-5__r3-c31) | {"characters": 6304, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__claude-sonnet-5-5__r3 call 43](#e-v1-gamma__V05__claude-sonnet-5-5__r3-c43) | {"characters": 7516, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 20](#e-v1-gamma__V05__gpt-6.1-sol__r1-c20) | {"characters": 6304, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 38](#e-v1-gamma__V05__gpt-6.1-sol__r1-c38) | {"characters": 7513, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 39](#e-v1-gamma__V05__gpt-6.1-sol__r1-c39) | {"characters": 18070, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 46](#e-v1-gamma__V05__gpt-6.1-sol__r1-c46) | {"characters": 11524, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V05__gpt-6.1-sol__r1 call 47](#e-v1-gamma__V05__gpt-6.1-sol__r1-c47) | {"characters": 6420, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V06__gpt-6.1-sol__r2 call 18](#e-v1-gamma__V06__gpt-6.1-sol__r2-c18) | {"characters": 5370, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 10](#e-v2-beta__V05__claude-sonnet-5-5__t1-c10) | {"characters": 6287, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 11](#e-v2-beta__V05__claude-sonnet-5-5__t1-c11) | {"characters": 6298, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 13](#e-v2-beta__V05__claude-sonnet-5-5__t1-c13) | {"characters": 17594, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 25](#e-v2-beta__V05__claude-sonnet-5-5__t1-c25) | {"characters": 17585, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__claude-sonnet-5-5__t1 call 26](#e-v2-beta__V05__claude-sonnet-5-5__t1-c26) | {"characters": 31137, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 10](#e-v2-beta__V05__gpt-6.1-sol__t1-c10) | {"characters": 6313, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 23](#e-v2-beta__V05__gpt-6.1-sol__t1-c23) | {"characters": 13794, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 24](#e-v2-beta__V05__gpt-6.1-sol__t1-c24) | {"characters": 13795, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 25](#e-v2-beta__V05__gpt-6.1-sol__t1-c25) | {"characters": 31567, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 27](#e-v2-beta__V05__gpt-6.1-sol__t1-c27) | {"characters": 13792, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 36](#e-v2-beta__V05__gpt-6.1-sol__t1-c36) | {"characters": 7513, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 38](#e-v2-beta__V05__gpt-6.1-sol__t1-c38) | {"characters": 31015, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 39](#e-v2-beta__V05__gpt-6.1-sol__t1-c39) | {"characters": 11524, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V05__gpt-6.1-sol__t1 call 43](#e-v2-beta__V05__gpt-6.1-sol__t1-c43) | {"characters": 6420, "stored_only": false} | 1 observed; extra unknown | did_not_finish / not_established |
| [V2 beta__V06__gpt-6.1-sol__t1 call 8](#e-v2-beta__V06__gpt-6.1-sol__t1-c8) | {"characters": 31014, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__claude-sonnet-5-5__t1 call 6](#e-v2-beta__V08__claude-sonnet-5-5__t1-c6) | {"characters": 17593, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 8](#e-v2-beta__V08__gpt-6.1-sol__t1-c8) | {"characters": 17593, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V08__gpt-6.1-sol__t1 call 24](#e-v2-beta__V08__gpt-6.1-sol__t1-c24) | {"characters": 12068, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 18](#e-v2-delta__V05__claude-sonnet-5-5__t1-c18) | {"characters": 7513, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__claude-sonnet-5-5__t1 call 28](#e-v2-delta__V05__claude-sonnet-5-5__t1-c28) | {"characters": 11524, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 3](#e-v2-delta__V05__gpt-6.1-sol__t1-c3) | {"characters": 14850, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 12](#e-v2-delta__V05__gpt-6.1-sol__t1-c12) | {"characters": 28674, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 14](#e-v2-delta__V05__gpt-6.1-sol__t1-c14) | {"characters": 28674, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 16](#e-v2-delta__V05__gpt-6.1-sol__t1-c16) | {"characters": 31005, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 17](#e-v2-delta__V05__gpt-6.1-sol__t1-c17) | {"characters": 30986, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 18](#e-v2-delta__V05__gpt-6.1-sol__t1-c18) | {"characters": 22429, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 19](#e-v2-delta__V05__gpt-6.1-sol__t1-c19) | {"characters": 8649, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 20](#e-v2-delta__V05__gpt-6.1-sol__t1-c20) | {"characters": 7518, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 21](#e-v2-delta__V05__gpt-6.1-sol__t1-c21) | {"characters": 11262, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 22](#e-v2-delta__V05__gpt-6.1-sol__t1-c22) | {"characters": 7713, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V05__gpt-6.1-sol__t1 call 23](#e-v2-delta__V05__gpt-6.1-sol__t1-c23) | {"characters": 8465, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 13](#e-v2-delta__V06__claude-sonnet-5-5__t1-c13) | {"characters": 22019, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 16](#e-v2-delta__V06__claude-sonnet-5-5__t1-c16) | {"characters": 6500, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 11](#e-v2-delta__V06__gpt-6.1-sol__t1-c11) | {"characters": 5092, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__gpt-6.1-sol__t1 call 16](#e-v2-delta__V06__gpt-6.1-sol__t1-c16) | {"characters": 5370, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V08__claude-sonnet-5-5__t1 call 8](#e-v2-delta__V08__claude-sonnet-5-5__t1-c8) | {"characters": 15543, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c18) | {"characters": 6904, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 21](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c21) | {"characters": 45168, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 29](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c29) | {"characters": 11524, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 30](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c30) | {"characters": 6420, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 3](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c3) | {"characters": 10091, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 10](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c10) | {"characters": 36286, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c12) | {"characters": 28689, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 13](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c13) | {"characters": 28689, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 14](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c14) | {"characters": 22675, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 16](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c16) | {"characters": 37609, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 19](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c19) | {"characters": 12699, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 20](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c20) | {"characters": 13946, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V05__gpt-6.1-sol__t1 call 21](#e-v2-epsilon__V05__gpt-6.1-sol__t1-c21) | {"characters": 5768, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__claude-sonnet-5-5__t1 call 14](#e-v2-epsilon__V06__claude-sonnet-5-5__t1-c14) | {"characters": 7741, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 3](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c3) | {"characters": 13699, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V06__gpt-6.1-sol__t1 call 14](#e-v2-epsilon__V06__gpt-6.1-sol__t1-c14) | {"characters": 5370, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__claude-sonnet-5-5__t1 call 9](#e-v2-epsilon__V08__claude-sonnet-5-5__t1-c9) | {"characters": 6059, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V08__gpt-6.1-sol__t1 call 12](#e-v2-epsilon__V08__gpt-6.1-sol__t1-c12) | {"characters": 7738, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 26](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c26) | {"characters": 14773, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 27](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c27) | {"characters": 5795, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 33](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c33) | {"characters": 6904, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 38](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c38) | {"characters": 12068, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 39](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c39) | {"characters": 5244, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 42](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c42) | {"characters": 17688, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__claude-sonnet-5-5__t1 call 44](#e-v2-gamma__V05__claude-sonnet-5-5__t1-c44) | {"characters": 37014, "stored_only": false} | 1 observed; extra unknown | wrong_answer / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 22](#e-v2-gamma__V05__gpt-6.1-sol__t1-c22) | {"characters": 6304, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 31](#e-v2-gamma__V05__gpt-6.1-sol__t1-c31) | {"characters": 42766, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 32](#e-v2-gamma__V05__gpt-6.1-sol__t1-c32) | {"characters": 9460, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 34](#e-v2-gamma__V05__gpt-6.1-sol__t1-c34) | {"characters": 45953, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 35](#e-v2-gamma__V05__gpt-6.1-sol__t1-c35) | {"characters": 7513, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 37](#e-v2-gamma__V05__gpt-6.1-sol__t1-c37) | {"characters": 42280, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 44](#e-v2-gamma__V05__gpt-6.1-sol__t1-c44) | {"characters": 11524, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V05__gpt-6.1-sol__t1 call 45](#e-v2-gamma__V05__gpt-6.1-sol__t1-c45) | {"characters": 6420, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V08__gpt-6.1-sol__t1 call 10](#e-v2-gamma__V08__gpt-6.1-sol__t1-c10) | {"characters": 9399, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V08__gpt-6.1-sol__t1 call 26](#e-v2-gamma__V08__gpt-6.1-sol__t1-c26) | {"characters": 5319, "stored_only": false} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V08__gpt-6.1-sol__t1 call 34](#e-v2-gamma__V08__gpt-6.1-sol__t1-c34) | {"characters": 12068, "stored_only": false} | 1 observed; extra unknown | correct / not_established |

### P22. Non-numeric sum inputs skipped (disclosed)

group_by sum reports notNumeric and sums fewer values than its input record count. V07 explicitly allows absent costs.

**V4 still allows:** yes. **Generic proposed fix:** Show numeric, null, missing and non-numeric counts per group.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 alpha__V07__claude-sonnet-5-5__ref call 14](#e-v1-alpha__V07__claude-sonnet-5-5__ref-c14) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 alpha__V07__gpt-6.1-sol__ref call 16](#e-v1-alpha__V07__gpt-6.1-sol__ref-c16) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 beta__V07__gpt-6.1-sol__r4 call 2](#e-v1-beta__V07__gpt-6.1-sol__r4-c2) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V07__claude-sonnet-5-5__r2 call 8](#e-v1-delta__V07__claude-sonnet-5-5__r2-c8) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 delta__V07__gpt-6.1-sol__r4 call 7](#e-v1-delta__V07__gpt-6.1-sol__r4-c7) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V07__claude-sonnet-5-5__r2 call 8](#e-v1-epsilon__V07__claude-sonnet-5-5__r2-c8) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 epsilon__V07__gpt-6.1-sol__r4 call 7](#e-v1-epsilon__V07__gpt-6.1-sol__r4-c7) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V07__claude-sonnet-5-5__r2 call 8](#e-v1-gamma__V07__claude-sonnet-5-5__r2-c8) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V1 gamma__V07__gpt-6.1-sol__r4 call 9](#e-v1-gamma__V07__gpt-6.1-sol__r4-c9) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V07__claude-sonnet-5-5__t1 call 2](#e-v2-beta__V07__claude-sonnet-5-5__t1-c2) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 beta__V07__gpt-6.1-sol__t1 call 2](#e-v2-beta__V07__gpt-6.1-sol__t1-c2) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V07__claude-sonnet-5-5__t1 call 7](#e-v2-delta__V07__claude-sonnet-5-5__t1-c7) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 epsilon__V07__gpt-6.1-sol__t1 call 7](#e-v2-epsilon__V07__gpt-6.1-sol__t1-c7) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V07__claude-sonnet-5-5__t1 call 5](#e-v2-gamma__V07__claude-sonnet-5-5__t1-c5) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V2 gamma__V07__gpt-6.1-sol__t1 call 9](#e-v2-gamma__V07__gpt-6.1-sol__t1-c9) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V07__claude-sonnet-5-5__t1 call 3](#e-v3-beta__V07__claude-sonnet-5-5__t1-c3) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 beta__V07__gpt-6.1-sol__t1 call 3](#e-v3-beta__V07__gpt-6.1-sol__t1-c3) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__claude-sonnet-5-5__t1 call 9](#e-v3-delta__V07__claude-sonnet-5-5__t1-c9) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 delta__V07__gpt-6.1-sol__t1 call 6](#e-v3-delta__V07__gpt-6.1-sol__t1-c6) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 epsilon__V07__claude-sonnet-5-5__t1 call 8](#e-v3-epsilon__V07__claude-sonnet-5-5__t1-c8) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V3 gamma__V07__gpt-6.1-sol__t1 call 9](#e-v3-gamma__V07__gpt-6.1-sol__t1-c9) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V07__claude-sonnet-5-5__t1 call 3](#e-v4-beta__V07__claude-sonnet-5-5__t1-c3) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V4 beta__V07__gpt-6.1-sol__t1 call 2](#e-v4-beta__V07__gpt-6.1-sol__t1-c2) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V4 epsilon__V07__gpt-6.1-sol__t1 call 7](#e-v4-epsilon__V07__gpt-6.1-sol__t1-c7) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V07__claude-sonnet-5-5__t1 call 8](#e-v4-gamma__V07__claude-sonnet-5-5__t1-c8) | {"notNumeric": 6, "disclosed": true} | 1 observed; extra unknown | correct / not_established |

### P23. Incomplete collection drives final total

V2 Epsilon V05 Claude deduplicates two mission pages and submits the matching 569-person undercount. Needed third-page reference data is not held in that run.

**V4 still allows:** yes. **Generic proposed fix:** Propagate page coverage and total/hasMore metadata and warn if completeness is unverified.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V2 epsilon__V05__claude-sonnet-5-5__t1 call 18](#e-v2-epsilon__V05__claude-sonnet-5-5__t1-c18) | V2 Epsilon V05 Claude deduplicates two mission pages and submits the matching 569-person undercount. Needed third-page reference data is not held in that run. | 1 observed; extra unknown | wrong_answer / wrong_answer_lineage |

### P24. Identical calculation repeated

Exact calculate arguments are submitted again in the same run.

**V4 still allows:** yes. **Generic proposed fix:** Name the previous calculation result id before repeating the identical request.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V4 beta__V05__claude-sonnet-5-5__t1 call 38](#e-v4-beta__V05__claude-sonnet-5-5__t1-c38) | {"version": 4, "runKey": "beta__V05__claude-sonnet-5-5__t1", "call": 38, "previous_call": 37} | extra=1 | correct / not_established |

### P25. Wildcard used as scalar field

Scalar field_of receives wildcard syntax. V4 now refuses the two historical filter calls, but still accepts the observed distinct call.

**V4 still allows:** yes. **Generic proposed fix:** Refuse unsupported wildcard field syntax consistently across operations.

| Exact evidence | Cause/metrics | Calls cost | Observed outcome / supported effect |
|---|---|---|---|
| [V1 epsilon__V06__claude-sonnet-5-5__r4 call 14](#e-v1-epsilon__V06__claude-sonnet-5-5__r4-c14) | true | 1 observed; extra unknown | correct / not_established |
| [V2 delta__V06__claude-sonnet-5-5__t1 call 14](#e-v2-delta__V06__claude-sonnet-5-5__t1-c14) | true | 1 observed; extra unknown | correct / not_established |
| [V4 gamma__V05__claude-sonnet-5-5__t1 call 30](#e-v4-gamma__V05__claude-sonnet-5-5__t1-c30) | true | 1 observed; extra unknown | did_not_finish / not_established |

## Reproduce and verify

Python 3.13+ with -B, standard library only; this audit used Python 3.14.8. Run inventory.py, replay.py, classify.py, prove.py, verify.py, extra.py, report.py in that order. inspect_audit.py, explore.py and focus.py are optional evidence viewers. patterns.py supplies report definitions. source_v1.py through source_v4.py are source evidence, not scripts to run directly. All writes stay in the audit folder. SHA256SUMS covers REPORT.md, findings.json, scripts and all intermediate files.

## What could not be checked, and why

- Hidden reasoning and intent: transcripts contain calls and answers. No motivation is invented for probes, null tests or re-fetches. Exposure counts are not failure counts.
- Controlled counterfactual outcomes or exact token savings: no new model calls are authorized. Seven wasted calls in the V4 limit case are certain; whether an altered trajectory completes is unknown. Extra-call costs are null where the trace does not prove them.
- Every semantic wrong result id: completeness depends on task requirements and which needed pages/fields were ever fetched. One wrong-id lineage and one incomplete-collection lineage are supported; this is not proof every other selection is correct.
- Answer-key/scorer correctness, hidden references, no-tool trajectories, fake dry runs and unobserved inputs: deliberately excluded. Existing result.json outcomes were read; keys and reference files were not.
- Every possible shape-caused re-fetch: identical requests and stable-id projection matches detect observed repeated data; arbitrary query rewrites and records without stable ids are not fully decidable by these rules. The nine counted cases are evidence-backed observations; causal motivation is unobservable.
- The overall fit criterion cannot be re-certified causally from calculator replay: the datasets differ in scope and trajectories, and no fresh baseline experiment was authorized. Observed wrong-operation and wrong-selection mechanisms are sufficient to reject the no-new-kind clause, but a full causal decomposition of counting, token-volume and definitional failures is unavailable.
