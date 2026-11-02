# Round 2 change: E07 duty-status scope

The reviewer confirmed round 1 for all four tasks with no finding. Outside that brief, the reviewer identified a remaining E07 ambiguity: department membership could be read as ACTIVE-only, while the existing key counts all members. The lead developer directed this clarification in the same change.

E07 now explicitly qualifies department members with `regardless of their duty status`. Its round 1 closing instruction remains exactly unchanged. No other original wording is changed beyond that qualification and the previously proposed closing replacement. The added phrase is part of the count question, not a second question or request.

Exact changes from pool.json:

- Insert `, regardless of their duty status,` immediately after `Science department`.
- Replace `Give only the ranks that occur.` with `Give the count per rank, leaving out ranks with no such members.` (unchanged from round 1).

All ten Personnel pages were verified and read. The selected department contains 133 members, including 13 whose duty status is ON_LEAVE or INACTIVE. Counting all duty statuses reproduces the round 1 answer and the earlier keys-b.json main answer exactly. The full duty-status breakdown and ACTIVE-only comparison are recorded in PROPOSAL.md. No answer, schema, identifier, data or key changes are proposed.

E01, E03 and E06 proposal entries are byte for byte unchanged from round 1. Their PROPOSAL.md task sections are unchanged as well. proposal.json now has round 2; PROPOSAL.md updates the E07 section and the overall scope and validation statements.

The uncommitted standard-library check passed: original-question equality, exact allowed E07 changes, unchanged other entries and task sections, unchanged answers, schema validity, and the independent E07 recount. All manifest-listed package files and the package digest still match. No unresolved uncertainty remains.
