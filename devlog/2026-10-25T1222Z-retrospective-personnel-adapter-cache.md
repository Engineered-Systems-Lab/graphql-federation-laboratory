# Retrospective: the Personnel adapter cache and its measured numbers

Date: 2026-10-25T12:22Z
Subject: A retrospective of the Personnel adapter's snapshot cache, committed on 2026-10-19 after pages of 100 missions hit the routers' 5 s subgraph timeout on the large data, with the page times measured before and after
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). The page times below come from the measurement notes of the work, which are kept outside the repository; only their figures are quoted. Nothing was run again for this entry.

## What changed

On 2026-10-19 at 19:06 UTC the lab committed lab commit `32279dc6bb407a9b8a0d8be5f6e13f5d92a015d4` ([the migrated entry](2026-10-19T1906Z-personnel-adapter-cache-runtime-checkpoint.md)). The Personnel adapter had made one SOAP call per person. It now reads each immutable Personnel v2 snapshot once, in pages of 100 through the list operation (ten calls for `personnel-v2-large-004`), keyed by `datasetVersion`, and answers every person lookup of that version from memory.

Two rules keep an outage an outage. A copy is never served without a probe that has just succeeded: one cheap list call (offset 0, limit 1) per batch of lookups, which proves the service answers and names the version it serves. And a new version empties the copy and reads again; a version that changes between pages restarts the read, three times at most. One behaviour changed: an outage is now per batch, not per person.

## Why it was needed

When the federation stack was first switched to the large data, a page of 100 missions with assets, commanding officer and crew held 1,258, 750 or 965 references (offsets 0, 100 and 200). The first full pages after a start took 5.1 to 5.6 s through both routers, which is the 5 s subgraph timeout: Cosmo answered 5.61, 5.12 and 5.15 s with 2, 2 and 0 error entries, Apollo 5.64, 5.18 and 5.13 s with 936, 490 and 695 (one per reference). Warm, the same pages took 0.8 to 3.5 s. Measured on warm Cosmo pages, missions alone took 0.02 to 0.08 s, assets 0.4 to 0.6 s, and the crew with each Personnel record 0.7 to 1.4 s, so the Personnel lookups, one call per person, were the main cost, with cold JVMs at the first request. The work stopped there, as its scope required, and offered four options that kept the timeout: warm the stack before measuring, page smaller, cache or batch the Personnel calls, or raise the adapters' CPU limits ([the scale-up](2026-10-25T1222Z-retrospective-data-scale-up.md)).

## What was decided

[D049](../project-governance/DECISIONS.md#d049---federation-personnel-adapter-snapshot-cache-and-the-warm-up-of-the-acceptance-suite-2026-10-19-accepted-scope) records the lead developer's choice: the timeout stays 5 seconds; option A, the shared acceptance suite warms the stack before its first assertion and reports the cold figure as a finding; and option C, this cache. Smaller pages were not chosen because they hide the problem, and higher CPU limits because they change the benchmark environment. A read of the snapshot at adapter start was not added either: it would blur the cold-start metric, and it is reconsidered only if acceptance runs fail. The cache is the caching that an earlier ruling, on 2026-10-16, had deferred until the need became apparent.

## What was measured

Four rounds of the three pages, right after the stack was ready (round 0 cold), on the large data (Missions release 1.1, mapping release 1.2, `personnel-v2-large-004`), one compose project per router and per run, the provisional container limits (1 CPU and 512 MB per adapter), on one Windows workstation with Docker Desktop. Seconds per page:

| Router | Before the cache, cold rounds | Before, last round | After the cache, first page of a cold stack | After, every other page |
| --- | --- | --- | --- | --- |
| Cosmo | 5.1 to 7.7 s, 2 error entries a page | 1.3 to 2.7 s | 3.6 s | 0.5 to 0.7 s |
| Apollo | 5.1 to 7.0 s, 490 to 936 error entries a page | 1.7 to 3.8 s | 4.2 s | 0.5 to 0.9 s |

After the change none of the 24 pages carried an error entry, and every page resolved the same references as the warm pages before (offset 0: 1,185 RESOLVED, 66 UNMAPPED and 7 UNRESOLVED; offset 100: 729, 19 and 2; offset 200: 939, 23 and 3). The first page of a cold stack stayed the slow one: it holds the snapshot read (about 0.3 s against the real service) and the first requests of cold JVMs. Under Apollo its margin below 5 s was about 0.8 s.

## What followed, and the limits

The warm-up landed with the stack on the large data (2026-10-19, lab commit `e68dbc0f06a1c41b31832a1a9e5b4f1193a9e025`). In its stack gates the first pages took 3.11, 0.74 and 0.49 s under Apollo and 1.96, 0.64 and 0.62 s under Cosmo. These are single runs on one machine, not a benchmark, and nothing says the first page of a cold stack always stays below 5 s. The adapter now holds state, one snapshot at a time, which the earlier adapters did not.

## Evidence

- [The Personnel adapter reads each snapshot once](2026-10-19T1906Z-personnel-adapter-cache-runtime-checkpoint.md), migrated from the lab, lab commit `32279dc6bb407a9b8a0d8be5f6e13f5d92a015d4`; its records commit lab commit `81b759eecc0726994958788a7dc1b49e2c5f948e`.
- D049, and [the federation design](../docs/FEDERATION-DESIGN.md#the-personnel-adapter-cache-and-the-warm-up).
- The two measurement notes of the work (the stop at the timeout, and the page times before and after), kept outside the repository; their figures agree with the migrated entry.
