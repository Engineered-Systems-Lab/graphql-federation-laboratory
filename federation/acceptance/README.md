# Federation acceptance (router-neutral)

The acceptance checks of the federation layer that every router implementation must pass, the expected outcomes they compare with, and the script that derives those outcomes. Nothing here knows a router: Apollo and Cosmo run it today, Hive will run the same files. The design behind the questions is [the federation design](../../docs/FEDERATION-DESIGN.md); the rule for later routers is in the Acceptance-test approach of [the plan](../../docs/PLAN.md#acceptance-test-approach).

## Layout

- `expected-outcomes.json`: the expected outcomes of acceptance questions 2 to 6 and of the controlled cases, derived from the released large data (Missions release 1.2 with 300 missions, mapping release 1.3, the Assets dataset 1.1 and the Personnel v2 snapshot `personnel-v2-large-004`) and the controlled cases. They were derived before any router code existed and never come from a run; the small-data file stays in Git history.
- `derive_expected.py`: derives that file. The `offline` stage of a router's gate derives it again and fails when the file differs.
- `shared_suite.py`: the suite itself (list A): the GraphQL operation documents, variables and assertions of questions 2 to 6 (`AcceptanceQuestions`) and of the controlled cases, that is the outage, the dead adapters and the question 6 cases (`ControlledCases`). The classes are mixins and not test cases, so nothing runs until a router's test module composes them with `unittest.TestCase`; the test ids stay those of that module.
- `graphql_client.py`: one GraphQL POST that keeps the HTTP status, a wait for an endpoint and the codes of an errors list. Standard library only.

## What a router supplies

A router's test module starts its stack and then builds one `shared_suite.Router(url, controls, settings, facts)`:

- **`url`**: the router's address. This is the parameter of the suite.
- **`controls`** (`shared_suite.Controls`): how to stop one compose service, start it again until it is healthy, and restart the router. The controlled cases stop `assets-service`, `assets-adapter`, `mapping-adapter` and `personnel-adapter`, the names of [the whole-stack compose file](../stack/README.md).
- **`settings`** (`shared_suite.RouterSettings`): the few facts that are a router's own and are declared, never absorbed into a weaker assertion: the `extensions.code` of the errors entry for a fetch of a dead adapter (or `None` when the router gives that entry no code), the `extensions` key that names the subgraph (or `None` when the router names none there, so that the entries are matched by code and number only and the missing naming is reported as a platform detail), the time window in which that answer must arrive, which proves the router's subgraph timeout is in force, and, added for the Cosmo router, `subgraph_in_message` (a pattern that finds the subgraph in the entry's message, for a router that names it only there) and `entries_per` (`reference`, the default, or `subgraph_fetch`: how many entries one failed fetch gives). The first three were exercised only by Apollo; Cosmo showed they were not enough for the controlled cases, and the two new ones have the Apollo values as defaults, so the Apollo gate declares what it declared before and runs the same assertions. The suite reads them through the helper methods of its `Router` class (`failed_fetches`, `subgraphs`, `expected_entries` and the others), not in each test.
- **`facts`**: a dict that the suite fills with the facts for the router's README table.

```python
class ApolloRouter:
    router = property(lambda self: STATE['router'])

class Part1Acceptance(ApolloRouter, shared_suite.AcceptanceQuestions, unittest.TestCase): ...
class Part3Outage(ApolloRouter, shared_suite.ControlledCases, unittest.TestCase): ...
```

## The rule for later routers

The same operation documents, variables, fixtures and assertions run against each implementation. A router-specific difference is declared in its `RouterSettings` and reported; a shared assertion is never weakened for one router, and a semantic check is never made different. What stays in a router's own folder is what only that router has: its configuration and its settings, the composition (for Apollo, the determinism and freshness of the supergraph), and the restart step.

The Apollo gate (`federation/routers/apollo/validation/run_router_gate.py stack`) runs this suite against the Apollo router: 35 tests in its runs of 2026-10-26, 17 in Part 1, 7 in Part 2 (Apollo's composition, not shared), 9 in Part 3 and 2 in Part 4 (introspection through the router). The Cosmo gate (`federation/routers/cosmo/validation/run_router_gate.py stack`) runs the same Part 1 and Part 3 against the Cosmo router with its own settings object ([the Cosmo README](../routers/cosmo/README.md#the-acceptance-tests)): 36 tests in its runs of 2026-10-26, with 7 in its Part 2 (Cosmo's composition), 1 in its Part 4 (recovery after adapters restart) and 2 in its Part 5 (introspection through the router). It ran 30 before the two controlled question 6 tests were added (`test_14` and `test_15` of Part 1, which need no stack).

## Paging, the warm-up and the timeout

The data is 300 missions, so every whole-list check pages: offset 0, 100 and 200 with the graph's largest limit (a larger limit is refused, never raised). The Missions service serves 50 a call, so a page of 100 is two calls of the Missions adapter. Before its first assertion the suite asks the three heaviest pages once (`Router.warm_up`: the JVMs of the adapters are cold on a fresh stack) and keeps the cold figures as facts, not assertions. After that a normal page must answer well before the subgraph timeout in force, which is the least time a dead adapter takes, 4.5 s: a normal page that takes as long fails (`test_16`, and every paged whole-list check). A page asked while an adapter is down is checked as a list: every page inside the upper end of the declared window and at least one page that waited for the timeout, because a page that follows the first failures can meet a connection that is refused at once; a router declares the code of such an entry in `adapter_down_other_codes` (Apollo: `SUBREQUEST_HTTP_ERROR`), and a single answer stays strict. The 5 s timeout is unchanged.


## Question 6

The answer is three counts and one percentage, counted by the client over the query result (the graph has no aggregate field). The people checked are the mission's Starfleet personnel: the commanding officer (`commandingOfficer(release)`, null when the mission has none) and the assigned crew; the participants never count. A mission is **confirmed with** a senior officer when one of them is confirmed senior, **confirmed without** when every one is confirmed and none is senior, and **unconfirmed** when there is no confirmed senior and at least one is not RESOLVED (UNMAPPED, UNRESOLVED, RELEASE_REFUSED, UNAVAILABLE or a null resolution). The percentage is with / (with + without), one decimal, half up, and not a number (`null` in the expected file, `None` in the suite, never 0) when no mission is confirmed; the unconfirmed are never folded into either side.

Two rules decide which missions count and where (the lead developer, 2026-10-18; their words are in [the federation design](../../docs/FEDERATION-DESIGN.md#the-query-workload)). **A PLANNED mission** is unconfirmed unless it already has a confirmed senior officer: it can be confirmed with, never confirmed without, because its staffing is not final (a PLANNED mission with nobody at all is unconfirmed too). **A CANCELLED mission** is left out of the population: it is in none of the three counts and not in the percentage, its references are not looked at, and the number of cancelled missions not counted is reported beside the answer (`cancelledNotCounted`), never folded into any bucket. Every other status (AUTHORIZED, ACTIVE, POSTPONED, COMPLETED, FAILED) counts by its staffing as above, and a mission of one of them with nobody at all is confirmed without. The rules are the status tests of `bucket` and `buckets` in `derive_expected.py` and of `question_6` in `shared_suite.py`; the expected file states them as `plannedRule` and `cancelledRule`. Mapping releases 1.2 and 1.3 give the same answer on the large data (300 missions): 182 / 65 / 26 and 73.7 percent, 27 cancelled missions not counted, 12 references not resolved (9 crew references have no entry). Release 1.0 and the Personnel adapter down: 0 / 0 / 273, not a number, 27 cancelled missions not counted. The earlier small-data answer was 27 / 0 / 3 and 100.0 percent with 1 cancelled mission, which could not show the difference between a senior and a junior mission. (The superseded empty-mission options are not kept in the expected file; the design document records the history.)

`controlledBuckets` holds the small controlled missions (the PLANNED, CANCELLED and other-status cases among them) and percentage cases that `test_14` and `test_15` feed to the same client function, with no stack.
