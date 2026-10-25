# Retrospective: federation question 6

Date: 2026-10-25T12:21Z
Subject: A retrospective of baseline question 6 of the federation (how many missions had one or more senior officers among their Starfleet personnel, and what percentage is that), answered in three runtime commits on 2026-10-18, and of what its answer became on the large data
Status: Historical / non-normative
Provenance: Written in the laboratory on 2026-10-25 as a retrospective of events in the lab, from the evidence listed at the end. The date is the time of writing; the events it describes are dated in the text (UTC). Nothing was run again for it.

## What changed

Question 6 crosses three systems: Missions says who is on a mission, the crew mapping says which Personnel record a crew reference names, and Personnel v2 holds the rank. A senior officer is a rank of CAPTAIN, COMMANDER or LIEUTENANT_COMMANDER, the lab's own definition. The question landed in three steps on 2026-10-18:

1. **One count and a share of all missions** (02:25 UTC, lab commit `0439bcf5ead7c8aa5ce16813f8d69d5acf0176bd`, [entry](2026-10-18T0225Z-federation-question-6-runtime-checkpoint.md)). It needed no new adapter code: the crew path of mapping release 1.1 already resolved all 56 crew references. With only the assigned crew counted, 25 of the 31 missions had a senior officer, 80.6 percent.
2. **Three counts** (10:18 UTC, lab commit `184f7002290451f5e65a35019c476e410c5b23ac`, [entry](2026-10-18T1018Z-federation-question-6-three-counts-runtime-checkpoint.md)). The answer became confirmed with a senior officer, confirmed without, and unconfirmed, with the percentage over the confirmed missions only. The commanding officer now counts with the assigned crew, which needed one new graph field, `Mission.commandingOfficer(release)`. With mapping release 1.1: 28, 1 and 2, 96.6 percent.
3. **The final rules** (14:45 UTC, lab commit `d9f27ddcce0375d077f4e840813bf22a7375a179`, [entry](2026-10-18T1445Z-federation-question-6-final-rules-runtime-checkpoint.md)). A PLANNED mission is never confirmed without a senior officer, because its staffing is not final. A CANCELLED mission is left out of the population and counted beside the answer. With mapping release 1.1: 27, 0 and 3, 100.0 percent, 1 cancelled mission not counted. The suite passed under Apollo and Cosmo with the same assertions.

## What was decided

The rules are the lead developer's, recorded in [D046](../project-governance/DECISIONS.md#d046---federation-question-6-the-people-counted-the-three-counts-and-the-status-rules-2026-10-18-accepted-scope) and [the query workload](../docs/FEDERATION-DESIGN.md#the-query-workload). The reason for three counts: an unconfirmed mission, one with no confirmed senior officer and at least one person whose reference is UNMAPPED, UNRESOLVED, refused or unavailable, counts neither as having a senior officer nor as not having one, so it is shown beside the percentage and never folded into either side. The percentage rounds half up and is not a number when no mission is confirmed. A cancelled mission never ran, so its staffing describes a dropped plan; the lead developer agreed with that reasoning when it was put to them.

Two practices held through all three steps: the expected answers were derived by script from the released files before the suite changed, never from a run; and controlled cases built from small inputs (39 controlled missions and the percentage cases at the end) run through the same client function as the live answer. The graph has no aggregate field, so the client counts.

## Why it mattered

The answer depends on three systems and a mapping that can fail in several ways, so an honest answer has to say what it could not confirm instead of guessing. The question also showed that figures given with a ruling are estimates until a script derives them. The final ruling came with 28, 0 and 2 for mapping release 1.1; the derivation gave 27, 0 and 3, and the design document says so.

## What followed

On the large data (Missions release 1.2, mapping release 1.3, `personnel-v2-large-004`) the derivation gives 182 confirmed with a senior officer, 65 confirmed without, 26 unconfirmed, 73.7 percent and 27 cancelled missions not counted; release 1.1 with mapping release 1.2 gave the same. Only 16 of the 800 crew are senior, which is why 100.0 percent on the small data became a spread ([the scale-up](2026-10-25T1222Z-retrospective-data-scale-up.md)). With the Personnel adapter down, all 273 counted missions are unconfirmed and the percentage is not a number.

Later context: the Abstraction ladder study's task T15 was scored against accepted answers that count the commanding officer with the assigned crew, while its question says "among their crew"; no run of T15 was correct, and the study records it as a wording mismatch of the frozen corpus, not an agent failure ([the study entry](2026-10-21T0242Z-agent-study-1-complete.md)).

Limits: stub-backend mode only, so the Oracle-backed Missions service never answered question 6; it is not tested under Hive, which is not built. No benchmark or human acceptance is claimed.

## Evidence

- The three migrated entries linked above, with their lab checkpoints lab commit `0439bcf5ead7c8aa5ce16813f8d69d5acf0176bd`, lab commit `184f7002290451f5e65a35019c476e410c5b23ac` and lab commit `d9f27ddcce0375d077f4e840813bf22a7375a179`.
- D046, and [the query workload](../docs/FEDERATION-DESIGN.md#the-query-workload) of the federation design.
- [The federation acceptance README](../federation/acceptance/README.md#question-6).
