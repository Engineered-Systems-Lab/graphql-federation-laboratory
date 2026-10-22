"""The router-neutral acceptance suite of the federation layer (list A: questions 2 to 6 and the controlled cases).

Every router implementation (Apollo and Cosmo today; Hive later) runs THESE operation documents, variables, fixtures and assertions
against the expected outcomes in expected-outcomes.json (derived from the released datasets and the mapping releases by
derive_expected.py before any router code existed, never from a run). The suite does not know a router. A router's test module
binds it with one `Router` object and its own test classes:

    class Part1Acceptance(RouterBound, shared_suite.AcceptanceQuestions, unittest.TestCase): ...
    class Part3Outage(RouterBound, shared_suite.ControlledCases, unittest.TestCase): ...

The suite classes are mixins on purpose (they are not TestCase subclasses): nothing runs until a router's module composes them with
unittest.TestCase, and the test ids stay those of that module.

What a router may differ in is DECLARED, never absorbed into a weaker assertion: `RouterSettings` holds the few facts that are a
router's own (the code and the subgraph name of the errors entry a dead adapter produces, and the time window in which that answer
must arrive, which proves that the subgraph timeout of the router is in force). Everything else is asserted identically for every
router. What the suite needs from the stack (stop and restore one service, restart the router) it takes from `Controls`.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import re
import time

from graphql_client import codes, post

EXPECTED_FILE = Path(__file__).resolve().parent / 'expected-outcomes.json'
EXPECTED = json.loads(EXPECTED_FILE.read_text(encoding='utf-8'))

# The mapping release the questions ask (the assets and the crew sections), and the largest list the graph returns in one call. The data
# is 300 missions, so every whole-list check PAGES: offset 0, 100 and 200 with the largest limit, never a larger one (the graph refuses
# it). The Missions service serves 50 a call, so a page of 100 is two calls of the Missions adapter; the Personnel adapter serves 100.
RELEASE = EXPECTED['mappingRelease']
PAGE = 100

ALL_MISSIONS = ('query($o: Int!, $r: String!) { missions(offset: $o, limit: 100) { missionId assets(release: $r) { localRef release assetId mappingOutcome '
                'resolution asset { assetId kind name status parentAssetId } } } }')
ALL_CREW = ('query($o: Int!, $r: String!) { missions(offset: $o, limit: 100) { missionId crew(release: $r) { localRef release personnelId mappingOutcome '
            'resolution personnel { personnelId displayName details { __typename ... on CrewDetails { rank department securityClearance } } } } } }')


QUESTION_6 = ('query($o: Int!, $r: String!) { missions(offset: $o, limit: 100) { missionId status '
              'commandingOfficer(release: $r) { localRef personnelId mappingOutcome resolution personnel { details { __typename ... on CrewDetails { rank } } } } '
              'crew(release: $r) { localRef personnelId mappingOutcome resolution personnel { details { __typename ... on CrewDetails { rank } } } } } }')

# The heaviest list a client can ask for in one call: 100 missions, each with its assets (and their records), its commanding officer and
# its whole crew (and their records). The timing test measures it through the router.
FULL_PAGE = ('query($o: Int!, $a: String!, $r: String!) { missions(offset: $o, limit: 100) { missionId title status '
             'assets(release: $a) { localRef assetId mappingOutcome resolution asset { assetId kind name status parentAssetId } } '
             'commandingOfficer(release: $r) { localRef personnelId mappingOutcome resolution personnel { personnelId displayName details { __typename ... on CrewDetails { rank department securityClearance } } } } '
             'crew(release: $r) { localRef personnelId mappingOutcome resolution personnel { personnelId displayName details { __typename ... on CrewDetails { rank department securityClearance } } } } } }')


def page_offsets():
    """The offsets of the pages that cover the dataset: 0, 100 and 200 for 300 missions."""
    return list(range(0, len(EXPECTED['missionOrder']), PAGE))


def personnel_of(mission):
    """The references of a mission's Starfleet personnel in the query result: the commanding officer (null when the mission has none) and the crew."""
    return ([mission['commandingOfficer']] if mission['commandingOfficer'] else []) + mission['crew']


def question_6(missions):
    """Question 6 as a client computes it over the query result (the graph has no aggregate field): three counts and one percentage,
    with the cancelled missions counted beside.

    The people checked are the mission's Starfleet personnel: the commanding officer (when it has one) and the assigned crew; the
    participants are never counted. A senior officer is a RESOLVED reference whose details are CrewDetails with a senior rank. A CANCELLED
    mission is left out of the population (it never ran, its staffing is a dropped plan): it is in no bucket, its references are not
    counted, and its number is reported as `cancelledNotCounted`. Every other mission is CONFIRMED WITH a senior officer when one of its
    people is confirmed senior (the others do not matter then); a PLANNED mission is otherwise UNCONFIRMED, whatever its staffing, because
    its staffing is not final (it can be confirmed with, never confirmed without); any other mission is CONFIRMED WITHOUT when every one is
    RESOLVED and none is senior (also when it has nobody at all), and UNCONFIRMED when a person's resolution is not RESOLVED (UNMAPPED,
    UNRESOLVED, RELEASE_REFUSED, UNAVAILABLE or null). The percentage is with / (with + without), one decimal, half up; it is None, never
    0, when no mission is confirmed. The unconfirmed missions are in neither side.
    """
    senior_ranks = EXPECTED['question6']['seniorRanks']
    found = {'with': [], 'without': [], 'unconfirmed': [], 'cancelled': []}
    not_resolved = 0
    for mission in missions:
        if mission['status'] == 'CANCELLED':
            found['cancelled'].append(mission['missionId'])
            continue
        confirmed_senior = False
        # A planned mission is not final: it cannot be confirmed without a senior officer, whoever is assigned so far.
        unconfirmed = mission['status'] == 'PLANNED'
        for reference in personnel_of(mission):
            if reference['resolution'] != 'RESOLVED':
                not_resolved += 1
                unconfirmed = True
                continue
            details = reference['personnel']['details']
            confirmed_senior = confirmed_senior or (details['__typename'] == 'CrewDetails' and details['rank'] in senior_ranks)
        found['with' if confirmed_senior else 'unconfirmed' if unconfirmed else 'without'].append(mission['missionId'])
    confirmed = len(found['with']) + len(found['without'])
    share = None if confirmed == 0 else float((Decimal(len(found['with'])) * 100 / Decimal(confirmed)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
    return {'withSeniorMissionIds': found['with'], 'withoutSeniorMissionIds': found['without'], 'unconfirmedMissionIds': found['unconfirmed'],
            'cancelledMissionIds': found['cancelled'],
            'confirmedWithSenior': len(found['with']), 'confirmedWithoutSenior': len(found['without']), 'unconfirmed': len(found['unconfirmed']),
            'cancelledNotCounted': len(found['cancelled']),
            'percentage': share, 'totalMissions': len(missions), 'notResolvedReferences': not_resolved}


def counts_of(answer):
    """The three counts, the percentage and the cancelled missions not counted of an answer or of an expected section, as one tuple to compare."""
    return (answer['confirmedWithSenior'], answer['confirmedWithoutSenior'], answer['unconfirmed'], answer['percentage'], answer['cancelledNotCounted'])


def query_result_of(name, crew, commander=None, status='ACTIVE'):
    """A mission as the query returns it, built from a controlled case: each person has localRef, resolution and rank (None for a civilian)."""
    def reference(person):
        personnel = None
        if person['resolution'] == 'RESOLVED':
            details = {'__typename': 'CivilianDetails'} if person['rank'] is None else {'__typename': 'CrewDetails', 'rank': person['rank']}
            personnel = {'details': details}
        return {'localRef': person['localRef'], 'resolution': person['resolution'], 'personnel': personnel}
    return {'missionId': name, 'status': status, 'commandingOfficer': None if commander is None else reference(commander),
            'crew': [reference(c) for c in crew]}


@dataclass(frozen=True)
class RouterSettings:
    """What is a router's own, declared by the router's test module.

    adapter_down_code: the `extensions.code` of the errors entry the router produces for a fetch of an adapter that is down, or None
        when the router attaches no code to that entry (the entry is then matched by its naming and its number).
    subgraph_key: the `extensions` key that names the subgraph of such an entry, or None when the router names none there (the entries
        are then matched by their code and their number only, and the missing naming is reported as a platform detail), unless the
        message names it (`subgraph_in_message`).
    adapter_down_seconds: (least, most) seconds that the answer takes when an adapter is down: the subgraph timeout in force.
    subgraph_in_message: a regular expression with one group that finds the subgraph in the `message` of such an entry, for a router
        that names it only there; None when the router does not (added for the Cosmo router, which names it only in the message).
    entries_per: how many entries a failed fetch gives: 'reference' (default, Apollo) is one entry per reference whose owning
        subgraph could not be asked, and 'subgraph_fetch' (Cosmo) is one entry per failed fetch of a subgraph, the router sending the
        references of one list to a subgraph in one request. The cases of the suite have one list per subgraph.
    adapter_down_other_codes: the other `extensions.code` values the router may give, in a list asked page by page, to a fetch of a dead
        adapter that fails at once instead of waiting for the timeout (a refused connection after the first requests, not a timeout).
        A single answer of the suite is strict and takes only `adapter_down_code`; a whole list over several pages takes these too.
        Added with the paging of the large data, where the Apollo router showed it; empty for a router that gives one code.
    """
    adapter_down_code: str
    subgraph_key: str
    adapter_down_seconds: tuple
    subgraph_in_message: str = None
    entries_per: str = 'reference'
    adapter_down_other_codes: tuple = ()


class Controls:
    """What the suite asks of the stack it runs against. A router's test module implements it over its own compose project."""

    def stop(self, service):
        """Stop one compose service: a backend such as 'assets-service' or an adapter such as 'assets-adapter'."""
        raise NotImplementedError

    def restore(self, service):
        """Start the service again and return once it is healthy (an adapter: once it answers GraphQL)."""
        raise NotImplementedError

    def restart_router(self):
        """Restart the router and return once it answers GraphQL. Adapters that were stopped can get new addresses, and a router
        may keep the old ones until it is restarted; a router that does not need this does nothing."""
        raise NotImplementedError


class Router:
    """The router under test: its address, the stack controls, its declared settings and the facts collected for its README."""

    def __init__(self, url, controls, settings, facts=None):
        self.url, self.controls, self.settings = url, controls, settings
        self.facts = {} if facts is None else facts
        self.cache = {}

    def ask(self, query, variables=None, timeout=60):
        # A query names the mapping release the questions ask as @RELEASE@; a test that needs another release passes it as a variable.
        return post(self.url, query.replace('@RELEASE@', RELEASE), variables, timeout)

    def warm_up(self):
        """Ask the three full pages once, before any assertion: the JVMs of the adapters are cold on a fresh stack, and the first page of a
        cold stack takes much longer than any later one. The cold figure is kept as a fact (a finding), never hidden, and the wait for a
        stack to be ready is not what the later assertions measure. Done once per router."""
        if 'warm' not in self.cache:
            rows = []
            for offset in page_offsets():
                status, body, seconds = self.ask(FULL_PAGE, {'o': offset, 'a': RELEASE, 'r': RELEASE}, timeout=120)
                rows.append({'offset': offset, 'http': status, 'seconds': round(seconds, 2), 'errors': len((body or {}).get('errors', []))})
            self.cache['warm'] = rows
            self.facts['cold first page pages (100 missions with assets, commanding officer and crew), not asserted'] = self.cache['warm']

    def ok(self, query, variables=None):
        """A query that must answer HTTP 200 with data and no errors entry."""
        status, body, _ = self.ask(query, variables)
        assert status == 200, (status, body)
        assert 'errors' not in body, body['errors']
        return body['data']

    def pages(self, query, variables=None):
        """A whole-list query asked page by page (offset 0, 100, 200 with the limit of the query). Returns (status, body, seconds) of each page."""
        return [self.ask(query, {**(variables or {}), 'o': offset}) for offset in page_offsets()]

    def ok_pages(self, query, variables=None):
        """The missions of every page of a whole-list query that must answer HTTP 200 with data and no errors entry, joined in page order,
        and the seconds of each page. A normal answer must come well before the subgraph timeout in force, so a page that takes as long as
        the least time a dead adapter takes (the router waiting for its timeout) is a failure and not a slow pass."""
        missions, seconds = [], []
        for status, body, taken in self.pages(query, variables):
            assert status == 200, (status, body)
            assert 'errors' not in body, body['errors']
            assert taken < self.settings.adapter_down_seconds[0], ('a normal page answered in %.2f s, near the subgraph timeout' % taken)
            missions += body['data']['missions']
            seconds.append(round(taken, 2))
        return missions, seconds

    def joined_pages(self, query, variables=None):
        """The missions of every page of a whole-list query, joined in page order, and the errors entries of all the pages, and the seconds
        of each page. Every page must answer HTTP 200."""
        missions, errors, seconds = [], [], []
        for status, body, taken in self.pages(query, variables):
            assert status == 200, (status, body)
            missions += body['data']['missions']
            errors += body.get('errors', [])
            seconds.append(taken)
        return missions, errors, seconds

    @property
    def names_subgraph(self):
        """Whether the entry of a dead adapter names the subgraph, in an `extensions` key or in its message."""
        return bool(self.settings.subgraph_key or self.settings.subgraph_in_message)

    @staticmethod
    def code_of(entry):
        return (entry.get('extensions') or {}).get('code')

    def codes_of(self, entries):
        return {self.code_of(e) for e in entries}

    def subgraph_of(self, entry):
        """The subgraph an entry names, where the router declares it, else None."""
        key, pattern = self.settings.subgraph_key, self.settings.subgraph_in_message
        if key:
            return entry['extensions'][key]
        if pattern:
            found = re.search(pattern, entry['message'])
            assert found, ('the entry does not name its subgraph in its message', entry)
            return found.group(1)
        return None

    def failed_fetches(self, entries):
        """The (code, subgraph) pairs of an errors list; the subgraph is None when the router declares no naming."""
        return {(self.code_of(e), self.subgraph_of(e)) for e in entries}

    def expected_failures_in_pages(self, subgraph):
        """The pairs a list asked page by page may yield for a dead adapter: the strict one and the declared other codes."""
        return {self.expected_failure(subgraph)} | {(code, subgraph if self.names_subgraph else None) for code in self.settings.adapter_down_other_codes}

    def expected_failure(self, subgraph):
        """The pair that `failed_fetches` yields for a fetch of that subgraph that failed because its adapter is down."""
        return (self.settings.adapter_down_code, subgraph if self.names_subgraph else None)

    def subgraphs(self, entries):
        return sorted((self.subgraph_of(e) for e in entries), key=str)

    def expected_subgraphs(self, names):
        """The subgraphs the entries name, given one name per reference whose owning subgraph could not be asked."""
        if self.settings.entries_per == 'subgraph_fetch':
            names = sorted(set(names))
        return sorted(names if self.names_subgraph else [None] * len(names), key=str)

    def expected_entries(self, references):
        """The number of entries for one list of that many references whose owning subgraph could not be asked."""
        return references if self.settings.entries_per == 'reference' else 1


class SuiteBase:
    """Base of the suite classes: the router comes from the concrete class (`router`)."""
    maxDiff = None
    router = None

    def ask(self, query, variables=None, timeout=60):
        return self.router.ask(query, variables, timeout)

    def ok(self, query, variables=None):
        return self.router.ok(query, variables)

    def setUp(self):
        super().setUp()
        self.router.warm_up()

    @property
    def facts(self):
        return self.router.facts


class AcceptanceQuestions(SuiteBase):

    def missions(self):
        if 'missions' not in self.router.cache:
            joined, seconds = self.router.ok_pages(ALL_MISSIONS, {'r': RELEASE})
            self.router.cache['missions'] = {m['missionId']: m for m in joined}
            self.facts['seconds of each page: all missions with their assets'] = seconds
        return self.router.cache['missions']

    def test_01_each_subgraph_answers_through_the_one_endpoint(self):
        data = self.ok('{ mappingReleases { release sections } '
                       'asset(assetId: "AST-0029") { assetId name status } '
                       'personnel(personnelId: "PRS-0001") { personnelId displayName details { __typename } } '
                       'mission(missionId: "ST-00000LD4O") { missionId title } }')
        self.assertEqual(data['mappingReleases'], [{'release': '1.0', 'sections': ['assets']},
                                                   {'release': '1.1', 'sections': ['assets', 'crew']},
                                                   {'release': '1.2', 'sections': ['assets', 'crew', 'participants']},
                                                   {'release': '1.3', 'sections': ['assets', 'crew', 'participants']}])
        self.assertEqual(data['asset'], {'assetId': 'AST-0029', 'name': 'USS Enterprise NCC-1701-D', 'status': 'ACTIVE'})
        self.assertEqual(data['personnel']['personnelId'], 'PRS-0001')
        self.assertIn(data['personnel']['details']['__typename'], ('CrewDetails', 'CivilianDetails'))
        self.assertEqual(data['mission']['missionId'], 'ST-00000LD4O')

    def test_02_the_missions_list_is_the_released_dataset_in_the_service_order_and_pages_without_loss_or_repeat(self):
        missions = self.missions()
        order = EXPECTED['missionOrder']
        self.assertEqual(list(missions), order)
        self.assertEqual(len(missions), 300)
        # Windows across a page of the Missions service (50 a call), across a page of the graph (100) and across both, at the end and
        # of one: none loses or repeats a mission.
        windows = ((45, 10), (95, 10), (195, 10), (99, 2), (0, 100), (250, 50), (290, 20), (299, 1))
        for offset, limit in windows:
            page = self.ok('query($o: Int!, $l: Int!) { missions(offset: $o, limit: $l) { missionId } }', {'o': offset, 'l': limit})['missions']
            self.assertEqual([m['missionId'] for m in page], order[offset:offset + limit], (offset, limit))
        past = self.ok('{ missions(offset: 300, limit: 100) { missionId } }')['missions']
        self.assertEqual(past, [], 'past the end is an empty list, not an error')
        self.assertEqual([m['missionId'] for m in self.ok('{ missions { missionId } }')['missions']], order[:20], 'the default limit is 20')
        self.facts['paging windows checked'] = len(windows) + 2

    def test_03_every_reference_of_every_mission_has_the_expected_outcome(self):
        for mission_id, mission in self.missions().items():
            expected_refs = EXPECTED['missions'][mission_id]['assetRefs']
            self.assertEqual([a['localRef'] for a in mission['assets']], expected_refs, mission_id)
            for reference in mission['assets']:
                expected = EXPECTED['references'][reference['localRef']]
                with self.subTest(mission=mission_id, reference=reference['localRef']):
                    self.assertEqual(reference['resolution'], expected['resolution'])
                    self.assertEqual(reference['mappingOutcome'], expected['mappingOutcome'])
                    self.assertEqual(reference['assetId'], expected['assetId'])
                    if expected['resolution'] == 'RESOLVED':
                        self.assertEqual(reference['asset']['status'], expected['status'])
                        self.assertEqual(reference['asset']['assetId'], expected['assetId'])
                    else:
                        self.assertIsNone(reference['asset'])

    def test_04_question_2_which_missions_used_a_destroyed_or_missing_asset(self):
        answer = sorted(mission_id for mission_id, mission in self.missions().items()
                        if any(a['asset'] and a['asset']['status'] in EXPECTED['question2']['badStatuses'] for a in mission['assets']))
        self.assertEqual(answer, EXPECTED['question2']['missionIds'])
        for local_ref, mission_ids in EXPECTED['question2']['referencesByAsset'].items():
            self.assertEqual(sorted(m for m, mission in self.missions().items() if local_ref in [a['localRef'] for a in mission['assets']]), sorted(mission_ids))

    def test_05_question_3_which_missions_have_unresolved_assets_and_the_unmapped_are_not_counted(self):
        unresolved = sorted(m for m, mission in self.missions().items() if any(a['resolution'] == 'UNRESOLVED' for a in mission['assets']))
        unmapped = sorted(m for m, mission in self.missions().items() if any(a['resolution'] == 'UNMAPPED' for a in mission['assets']))
        self.assertEqual(unresolved, EXPECTED['question3']['unresolvedMissionIds'])
        self.assertEqual(unmapped, EXPECTED['question3']['notCountedUnmappedMissionIds'])
        for status, body, _ in self.router.pages(ALL_MISSIONS, {'r': RELEASE}):
            self.assertEqual((status, 'errors' in body), (200, False), 'UNRESOLVED and UNMAPPED are data and add no errors entry')

    def test_06_question_4_the_parent_chain_of_an_asset_in_one_query(self):
        chain_expected = EXPECTED['question4']['chains'][0]
        self.assertTrue(EXPECTED['question4']['oneQuery'])
        first_mission = chain_expected['missionIds'][0]
        query = ('query($id: ID!) { mission(missionId: $id) { assets(release: "@RELEASE@") { localRef asset { assetId name '
                 'parent { assetId name parent { assetId name parent { assetId name parent { assetId } } } } } } } }')
        mission = self.ok(query, {'id': first_mission})['mission']
        reference = next(a for a in mission['assets'] if a['localRef'] == chain_expected['fromReference'])
        chain = []
        node = reference['asset']
        while node:
            chain.append(node['assetId'])
            node = node.get('parent')
        self.assertEqual(chain, chain_expected['chain'])
        self.assertIsNone(reference['asset']['parent']['parent']['parent'], 'the top of the chain has no parent')
        self.facts['question 4'] = 'one query: Asset.parent, resolved by the Assets adapter, one call per level'

    def test_07_a_crew_reference_asked_in_release_1_0_has_no_entry_and_is_unmapped_with_no_errors_entry(self):
        seen = 0
        for status, body, _ in self.router.pages(ALL_CREW, {'r': '1.0'}):
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'NO_ENTRY is data: no errors entry')
            for mission in body['data']['missions']:
                self.assertEqual([c['localRef'] for c in mission['crew']], EXPECTED['missions'][mission['missionId']]['crewRefs'])
                for reference in mission['crew']:
                    seen += 1
                    self.assertEqual(reference['mappingOutcome'], EXPECTED['crewInRelease1.0']['mappingOutcome'])
                    self.assertEqual(reference['resolution'], EXPECTED['crewInRelease1.0']['resolution'])
                    self.assertIsNone(reference['personnel'])
                    self.assertIsNone(reference['personnelId'])
        self.assertEqual(seen, EXPECTED['crew']['occurrencesInMissions'])
        self.facts['crew references checked in release 1.0'] = seen

    def test_07b_the_crew_references_asked_in_the_mapping_release_resolve_against_the_snapshot_004_and_the_unmapped_are_data(self):
        seen = unmapped = civilians = 0
        for status, body, _ in self.router.pages(ALL_CREW, {'r': EXPECTED['crew']['release']}):
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'RESOLVED and UNMAPPED are data: no errors entry')
            for mission in body['data']['missions']:
                self.assertEqual([c['localRef'] for c in mission['crew']], EXPECTED['missions'][mission['missionId']]['crewRefs'])
                for reference in mission['crew']:
                    seen += 1
                    expected = EXPECTED['crew']['references'][reference['localRef']]
                    with self.subTest(mission=mission['missionId'], reference=reference['localRef']):
                        self.assertEqual(reference['mappingOutcome'], expected['mappingOutcome'])
                        self.assertEqual(reference['personnelId'], expected['personnelId'])
                        self.assertEqual(reference['resolution'], expected['resolution'])
                        person = reference['personnel']
                        if expected['resolution'] != 'RESOLVED':
                            unmapped += 1
                            self.assertIsNone(person, 'a reference with no entry is never guessed')
                            continue
                        self.assertEqual(person['personnelId'], expected['personnelId'])
                        self.assertEqual(person['displayName'], expected['displayName'])
                        if expected['rank'] is None:
                            civilians += 1
                            self.assertEqual(person['details'], {'__typename': 'CivilianDetails'}, 'a migrated civilian has no rank, department or clearance')
                            continue
                        self.assertEqual(person['details'], {'__typename': 'CrewDetails', 'rank': expected['rank'], 'department': expected['department'],
                                                             'securityClearance': expected['securityClearance']})
        self.assertEqual(seen, EXPECTED['crew']['occurrencesInMissions'])
        self.assertEqual(unmapped, sum(1 for m in EXPECTED['missions'].values() for r in m['crewRefs'] if EXPECTED['crew']['references'][r]['resolution'] != 'RESOLVED'))
        self.facts['crew references checked in release ' + EXPECTED['crew']['release']] = {'references': seen, 'not resolved (data)': unmapped, 'civilians (no rank)': civilians}

    def test_08_a_blank_or_unknown_release_is_refused_with_its_code_and_a_missing_release_is_refused_by_graphql(self):
        for release, code in [('', EXPECTED['releaseErrors']['blankRelease'])] + [(r, EXPECTED['releaseErrors']['unknownCode']) for r in EXPECTED['releaseErrors']['unknownReleases']]:
            with self.subTest(release=release):
                status, body, _ = self.ask('query($r: String!) { mission(missionId: "ST-00000LD4O") { missionId assets(release: $r) { localRef assetId mappingOutcome resolution asset { assetId } } } }', {'r': release})
                self.assertIn(code, codes(body), body)
                self.assertEqual(status, 200)
                references = body['data']['mission']['assets']
                self.assertTrue(references)
                for reference in references:
                    self.assertEqual(reference['mappingOutcome'], EXPECTED['releaseErrors']['mappingOutcome'])
                    self.assertEqual(reference['resolution'], EXPECTED['releaseErrors']['resolution'], 'a refused release is not UNMAPPED')
                    self.assertIsNone(reference['assetId'])
                    self.assertIsNone(reference['asset'])
                self.facts[f'release {release!r}'] = {'http': status, 'codes': codes(body), 'data': body.get('data')}
        status, body, _ = self.ask('{ mission(missionId: "ST-00000LD4O") { missionId assets { localRef } } }')
        self.assertIn(status, (200, 400))
        self.assertTrue(body.get('errors'), 'a request that names no release is refused, never guessed')
        self.assertFalse(body.get('data'))
        self.facts['release omitted'] = {'http': status, 'codes': codes(body)}
        crew_status, crew_body, _ = self.ask('query($r: String!) { mission(missionId: "ST-00000LD4O") { crew(release: $r) { localRef personnelId mappingOutcome resolution personnel { personnelId } } } }', {'r': 'latest'})
        self.assertIn(EXPECTED['releaseErrors']['unknownCode'], codes(crew_body))
        for reference in crew_body['data']['mission']['crew']:
            self.assertEqual((reference['mappingOutcome'], reference['resolution']), ('RELEASE_REFUSED', 'RELEASE_REFUSED'))
            self.assertIsNone(reference['personnel'])

    def test_09_a_malformed_paging_argument_is_refused_with_bad_user_input(self):
        status, body, _ = self.ask('{ missions(limit: 101) { missionId } }')
        self.assertIn('BAD_USER_INPUT', codes(body))
        self.facts['limit above 100'] = {'http': status, 'data': body.get('data')}

    def test_10_queries_that_omit_resolution_and_asset_keep_the_honest_result_rules(self):
        """The fields the mapping owns are answered by the mapping alone; what the owning adapter adds is only what is selected."""
        reference_ids = EXPECTED['missions']['ST-00000LD4O']['assetRefs']
        shapes = {
            'only the key': 'localRef release',
            'the mapped id and the outcome': 'localRef release assetId mappingOutcome',
            'only the outcome': 'mappingOutcome',
            'only resolution': 'resolution',
            'only asset': 'asset { assetId }',
        }
        for name, selection in shapes.items():
            with self.subTest(shape=name):
                data = self.ok('{ mission(missionId: "ST-00000LD4O") { assets(release: "@RELEASE@") { ' + selection + ' } } }')
                references = data['mission']['assets']
                self.assertEqual(len(references), len(reference_ids))
                for index, reference in enumerate(references):
                    expected = EXPECTED['references'][reference_ids[index]]
                    if 'localRef' in selection:
                        self.assertEqual(reference['localRef'], reference_ids[index])
                    if 'assetId' in selection and 'asset {' not in selection:
                        self.assertEqual(reference['assetId'], expected['assetId'])
                    if 'mappingOutcome' in selection:
                        self.assertEqual(reference['mappingOutcome'], expected['mappingOutcome'])
                    if 'resolution' in selection:
                        self.assertEqual(reference['resolution'], expected['resolution'])
                    if 'asset {' in selection:
                        self.assertEqual((reference['asset'] or {}).get('assetId'), expected['assetId'] if expected['resolution'] == 'RESOLVED' else None)

    def test_11_a_reference_is_never_hidden_or_guessed_when_only_the_mapping_fields_are_selected(self):
        unmapped = next(r for r, v in EXPECTED['references'].items() if v['resolution'] == 'UNMAPPED')
        unresolved = next(r for r, v in EXPECTED['references'].items() if v['resolution'] == 'UNRESOLVED')
        for ref in (unmapped, unresolved):
            mission_id = next(m for m, v in EXPECTED['missions'].items() if ref in v['assetRefs'])
            data = self.ok('query($id: ID!) { mission(missionId: $id) { assets(release: "@RELEASE@") { localRef assetId mappingOutcome } } }', {'id': mission_id})
            found = [a for a in data['mission']['assets'] if a['localRef'] == ref]
            self.assertEqual(len(found), 1, 'the reference is listed, never dropped')
            self.assertEqual(found[0]['assetId'], EXPECTED['references'][ref]['assetId'])
            self.assertEqual(found[0]['mappingOutcome'], EXPECTED['references'][ref]['mappingOutcome'])

    def test_12_question_6_three_counts_among_the_assigned_crew_and_the_percentage_of_the_confirmed(self):
        expected = EXPECTED['question6']
        missions, seconds = self.router.ok_pages(QUESTION_6, {'r': EXPECTED['crew']['release']})
        self.facts['seconds of each page: question 6'] = seconds
        self.assertEqual([m['missionId'] for m in missions], EXPECTED['missionOrder'])
        for mission in missions:
            # Only assignedCrewIds count: the crew field lists exactly those references, not the commanding officer or the participants.
            self.assertEqual([c['localRef'] for c in mission['crew']], EXPECTED['missions'][mission['missionId']]['crewRefs'])
            # The commanding officer is the other person checked: one reference, or null when the mission has none.
            wanted = EXPECTED['missions'][mission['missionId']]['commandingOfficerRef']
            self.assertEqual(mission['commandingOfficer'] and mission['commandingOfficer']['localRef'], wanted)
            self.assertEqual(mission['status'], EXPECTED['missions'][mission['missionId']]['status'])
        answer = question_6(missions)
        self.assertEqual(answer['withSeniorMissionIds'], expected['confirmedWithSeniorMissionIds'])
        self.assertEqual(answer['withoutSeniorMissionIds'], expected['confirmedWithoutSeniorMissionIds'])
        self.assertEqual(answer['unconfirmedMissionIds'], expected['unconfirmedMissionIds'])
        self.assertEqual(answer['cancelledMissionIds'], expected['cancelledMissionIds'])
        self.assertEqual(counts_of(answer), counts_of(expected))
        self.assertEqual((answer['totalMissions'], answer['notResolvedReferences']), (expected['totalMissions'], expected['notResolvedReferences']))
        self.facts['question 6 (release ' + EXPECTED['crew']['release'] + ')'] = {'confirmed with a senior officer': answer['confirmedWithSenior'], 'confirmed without': answer['confirmedWithoutSenior'],
                                                  'unconfirmed': answer['unconfirmed'], 'percentage of the confirmed': answer['percentage'],
                                                  'cancelled missions not counted': answer['cancelledNotCounted']}

    def test_13_question_6_a_mission_whose_only_senior_member_is_unresolved_is_never_confirmed_with_a_senior_officer(self):
        expected = EXPECTED['question6']
        controlled = expected['controlledCase']
        mission_id, only_senior = controlled['missionId'], controlled['onlySeniorReference']
        # The member (the commanding officer or an assigned crew member) is senior in release 1.1: the mission is confirmed with a senior officer, and the member is its only senior reference.
        released = {m['missionId']: m for m in self.router.ok_pages(QUESTION_6, {'r': EXPECTED['crew']['release']})[0]}[mission_id]
        senior = [c['localRef'] for c in personnel_of(released)
                  if c['resolution'] == 'RESOLVED' and c['personnel']['details'].get('rank') in expected['seniorRanks']]
        self.assertEqual(senior, [only_senior])
        self.assertEqual(next(c for c in personnel_of(released) if c['localRef'] == only_senior)['personnel']['details']['rank'], controlled['seniorRank'])
        self.assertIn(mission_id, expected['confirmedWithSeniorMissionIds'])
        # In release 1.0 the same member is UNMAPPED: not guessed, not counted, nothing added to the errors list.
        missions = []
        for status, body, _ in self.router.pages(QUESTION_6, {'r': '1.0'}):
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'UNMAPPED is data: no errors entry')
            missions += body['data']['missions']
        by_id = {m['missionId']: m for m in missions}
        self.assertEqual({c['localRef']: (c['resolution'], c['personnel']) for c in personnel_of(by_id[mission_id])},
                         {ref: ('UNMAPPED', None) for ref in controlled['personnelRefs']})
        answer = question_6(missions)
        want = controlled['release1.0']
        self.assertEqual(counts_of(answer), counts_of(want))
        self.assertEqual(answer['notResolvedReferences'], want['notResolvedReferences'])
        self.assertIn(mission_id, answer['unconfirmedMissionIds'])
        self.facts['question 6 (release 1.0, all unmapped)'] = {'confirmed with': answer['confirmedWithSenior'], 'confirmed without': answer['confirmedWithoutSenior'],
                                                                'unconfirmed': answer['unconfirmed'], 'percentage of the confirmed': answer['percentage'],
                                                                'cancelled missions not counted': answer['cancelledNotCounted'],
                                                                'references not resolved': answer['notResolvedReferences']}

    def test_14_question_6_each_controlled_mission_lands_in_its_bucket(self):
        # Small controlled inputs (the query-result shape, one mission each): no stack is asked, the client function is.
        cases = EXPECTED['question6']['controlledBuckets']['missions']
        for case in cases:
            answer = question_6([query_result_of(case['name'], case['crew'], case['commandingOfficer'], case['status'])])
            landed = [name for name, key in (('with', 'withSeniorMissionIds'), ('without', 'withoutSeniorMissionIds'), ('unconfirmed', 'unconfirmedMissionIds'),
                                             ('cancelled', 'cancelledMissionIds')) if answer[key]]
            self.assertEqual(landed, [case['bucket']], case['name'])
            # A cancelled mission is in none of the three counts and is the one number reported beside them.
            self.assertEqual(answer['cancelledNotCounted'], int(case['bucket'] == 'cancelled'), case['name'])
            if case['bucket'] == 'cancelled':
                self.assertEqual(answer['notResolvedReferences'], 0, 'the references of a cancelled mission are not looked at')
        self.facts['question 6 controlled missions'] = {'cases': len(cases)}

    def test_15_question_6_the_percentage_is_over_the_confirmed_missions_half_up_and_not_a_number_when_none_is_confirmed(self):
        cases = EXPECTED['question6']['controlledBuckets']['percentages']
        for case in cases:
            crews = ([[{'localRef': 'C-1', 'resolution': 'RESOLVED', 'rank': 'CAPTAIN'}]] * case['confirmedWithSenior']
                     + [[{'localRef': 'C-1', 'resolution': 'RESOLVED', 'rank': 'ENSIGN'}]] * case['confirmedWithoutSenior']
                     + [[{'localRef': 'C-1', 'resolution': 'UNMAPPED', 'rank': None}]] * case['unconfirmed'])
            # The cancelled missions carry a confirmed senior officer and an unmapped one: counted in none of the buckets, whoever is on them.
            cancelled = [[{'localRef': 'C-1', 'resolution': 'RESOLVED', 'rank': 'CAPTAIN'}, {'localRef': 'C-2', 'resolution': 'UNMAPPED', 'rank': None}]] * case['cancelledNotCounted']
            result = [query_result_of('M-' + str(i), crew) for i, crew in enumerate(crews)]
            result += [query_result_of('X-' + str(i), crew, status='CANCELLED') for i, crew in enumerate(cancelled)]
            answer = question_6(result)
            self.assertEqual(counts_of(answer), counts_of(case), case['name'])
        self.assertEqual([c['percentage'] for c in cases], [6.3, 6.3, 100.0, 0.0, None, 75.0, None],
                         'a tie goes up; none confirmed is None, never 0; the cancelled missions change nothing')
        self.facts['question 6 controlled percentages'] = {'cases': len(cases)}

    def test_16_a_full_page_of_100_missions_with_their_crew_and_assets_answers_inside_the_subgraph_timeout(self):
        """The heaviest list a client can ask for in one call, through the router, page by page. A normal answer must come well before
        the subgraph timeout in force (the least time a dead adapter takes), with no errors entry, and every reference as expected. The
        stack was warmed before the first assertion (`warm_up`), and the cold figure is a fact of the router, not asserted."""
        least = self.router.settings.adapter_down_seconds[0]
        rows = []
        for offset in page_offsets():
            status, body, seconds = self.ask(FULL_PAGE, {'o': offset, 'a': RELEASE, 'r': RELEASE})
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'a normal full page has no errors entry')
            missions = body['data']['missions']
            self.assertEqual([m['missionId'] for m in missions], EXPECTED['missionOrder'][offset:offset + PAGE])
            references = 0
            for mission in missions:
                for reference in mission['assets']:
                    references += 1
                    self.assertEqual(reference['resolution'], EXPECTED['references'][reference['localRef']]['resolution'])
                for reference in personnel_of(mission):
                    references += 1
                    self.assertEqual(reference['resolution'], {**EXPECTED['crew']['references'], **EXPECTED['commandingOfficers']['references']}[reference['localRef']]['resolution'])
            self.assertLess(seconds, least, 'a normal full page answered in %.2f s, near the subgraph timeout' % seconds)
            rows.append({'offset': offset, 'seconds': round(seconds, 2), 'missions': len(missions), 'references': references})
        self.facts['full pages (100 missions with assets, commanding officer and crew), warm'] = rows


class ControlledCases(SuiteBase):
    """The outages and the dead adapters. They stop and restore services of the stack, so they run in the order of their names."""

    def adapter_down_answer_time(self, seconds):
        least, most = self.router.settings.adapter_down_seconds
        self.assertGreaterEqual(seconds, least)
        self.assertLess(seconds, most, 'the default subgraph timeout of the router is not in force')

    def adapter_down_pages_time(self, pages):
        """The same proof for a list asked page by page: every page answers inside the declared window's upper end, and at least one of
        them waited for the timeout in force (a page whose fetch fails at once, or at the dial, may come earlier than the timeout)."""
        least, most = self.router.settings.adapter_down_seconds
        for seconds in pages:
            self.assertLess(seconds, most, 'the default subgraph timeout of the router is not in force')
        self.assertGreaterEqual(max(pages), least, 'no page waited for the subgraph timeout of the router')

    def test_01_question_5_with_the_assets_service_down_a_mission_answers_with_partial_data(self):
        self.router.controls.stop('assets-service')
        for mission_id in ('ST-00000LD4O', 'ST-00000LD4Y'):
            expected = EXPECTED['missions'][mission_id]
            status, body, seconds = self.ask('query($id: ID!) { mission(missionId: $id) { missionId title status assets(release: "@RELEASE@") { localRef assetId mappingOutcome resolution asset { assetId } } } }',
                                             {'id': mission_id})
            with self.subTest(mission=mission_id):
                self.assertEqual(status, EXPECTED['question5']['httpStatus'])
                mission = body['data']['mission']
                self.assertEqual(mission['missionId'], mission_id)
                self.assertTrue(mission['title'])
                for reference in mission['assets']:
                    wanted = 'UNMAPPED' if EXPECTED['references'][reference['localRef']]['assetId'] is None else 'UNAVAILABLE'
                    self.assertEqual(reference['resolution'], wanted, reference['localRef'])
                    self.assertIsNone(reference['asset'])
                entries = body['errors']
                self.assertEqual(len(entries), expected['failedCallsWhenAssetsDown'], 'one errors entry per failed call')
                self.assertEqual({e['extensions']['code'] for e in entries}, {EXPECTED['question5']['unavailableCode']})
                self.facts[f'outage {mission_id}'] = {'http': status, 'seconds': round(seconds, 2), 'entries': len(entries),
                                                      'entry shape': {k: (v if k != 'extensions' else sorted(v)) for k, v in entries[0].items()}}
        self.facts['outage entry example'] = body['errors'][0]

    def test_02_the_whole_list_in_an_outage_has_one_entry_per_failed_call_and_every_entry_has_the_code(self):
        rows = []
        for offset, (status, body, seconds) in zip(page_offsets(), self.router.pages(ALL_MISSIONS, {'r': RELEASE})):
            self.assertEqual(status, 200)
            ids = EXPECTED['missionOrder'][offset:offset + PAGE]
            self.assertEqual([m['missionId'] for m in body['data']['missions']], ids, 'a dead service costs fields, never a mission')
            mapped = sum(1 for i in ids for r in EXPECTED['missions'][i]['assetRefs'] if EXPECTED['references'][r]['assetId'] is not None)
            self.assertGreater(len(body['errors']), 0)
            self.assertLessEqual(len(body['errors']), mapped)
            self.assertEqual({e['extensions']['code'] for e in body['errors']}, {'SERVICE_UNAVAILABLE'})
            rows.append({'offset': offset, 'http': status, 'seconds': round(seconds, 2), 'entries': len(body['errors']), 'mapped references in the page': mapped})
        self.facts['outage whole list'] = rows

    def test_03_the_graph_recovers_when_the_service_is_back(self):
        self.router.controls.restore('assets-service')
        deadline = time.monotonic() + 60
        answer = None
        while time.monotonic() < deadline:
            status, body, _ = self.ask('{ mission(missionId: "ST-00000LD4O") { assets(release: "@RELEASE@") { localRef resolution } } }')
            answer = body
            if status == 200 and 'errors' not in body:
                break
            time.sleep(2)
        self.assertNotIn('errors', answer)
        self.assertEqual([a['resolution'] for a in answer['data']['mission']['assets']], ['RESOLVED', 'RESOLVED'])

    def test_04_when_an_adapter_itself_is_down_the_router_answers_as_the_recorded_setting_says(self):
        controls, router = self.router.controls, self.router
        controls.stop('assets-adapter')
        try:
            query = '{ mission(missionId: "ST-00000LD4O") { missionId title assets(release: "@RELEASE@") { localRef assetId mappingOutcome resolution asset { assetId } } } }'
            status, body, seconds = self.ask(query)
            self.facts['assets adapter down'] = {'http': status, 'seconds': round(seconds, 2), 'data': body.get('data'),
                                                 'errors': [{'message': e.get('message'), 'code': e.get('extensions', {}).get('code'), 'path': e.get('path')}
                                                            for e in body.get('errors', [])]}
            # The recorded setting of the router: a subgraph request waits for the time the router declares. The router then answers
            # HTTP 200 with one errors entry per failed fetch (and names the subgraph when the router declares how). `resolution` is
            # nullable, so the null stops at the field and the rest of the mission is kept. A null resolution means only that the
            # router could not ask the owning adapter.
            self.assertEqual(status, 200)
            self.adapter_down_answer_time(seconds)
            mission = body['data']['mission']
            self.assertEqual(mission['missionId'], 'ST-00000LD4O')
            self.assertTrue(mission['title'])
            self.assertEqual([a['localRef'] for a in mission['assets']], EXPECTED['missions']['ST-00000LD4O']['assetRefs'])
            for reference in mission['assets']:
                expected = EXPECTED['references'][reference['localRef']]
                self.assertEqual((reference['assetId'], reference['mappingOutcome']), (expected['assetId'], expected['mappingOutcome']),
                                 'the fields the mapping owns are kept')
                self.assertIsNone(reference['resolution'], 'a null resolution: the router could not ask the owning adapter')
                self.assertIsNone(reference['asset'])
            self.assertEqual(len(body['errors']), router.expected_entries(2), 'one entry per failed fetch, counted as the router declares')
            self.assertEqual(router.failed_fetches(body['errors']), {router.expected_failure('assets')})
            # The other subgraphs keep their fields beside the failed fetches: the mapping releases, the Missions fields and the crew.
            status, body, seconds = self.ask('{ mappingReleases { release } mission(missionId: "ST-00000LD4O") { title status assets(release: "@RELEASE@") { localRef resolution } '
                                             'crew(release: "@RELEASE@") { localRef resolution personnel { personnelId } } } }')
            self.assertEqual(status, 200)
            self.assertEqual([r['release'] for r in body['data']['mappingReleases']], ['1.0', '1.1', '1.2', '1.3'])
            mission = body['data']['mission']
            self.assertTrue(mission['title'] and mission['status'])
            self.assertEqual([c['resolution'] for c in mission['crew']], ['RESOLVED', 'RESOLVED'], 'the Personnel subgraph is up and still answers')
            self.assertEqual([c['personnel']['personnelId'] for c in mission['crew']],
                             [EXPECTED['crew']['references'][r]['personnelId'] for r in EXPECTED['missions']['ST-00000LD4O']['crewRefs']])
            self.assertEqual([a['resolution'] for a in mission['assets']], [None, None])
            self.assertEqual(router.failed_fetches(body['errors']), {router.expected_failure('assets')},
                             'the errors entry names the dead subgraph')
            self.facts['assets adapter down, another subgraph beside it'] = {'http': status, 'seconds': round(seconds, 2),
                                                                             'data kept': ['mappingReleases', 'mission fields', 'crew']}
            # The whole list keeps every mission: a dead subgraph costs the fields it owns, never a mission.
            missions, entries, taken = self.router.joined_pages(ALL_MISSIONS, {'r': RELEASE})
            self.adapter_down_pages_time(taken)
            self.assertEqual([m['missionId'] for m in missions], EXPECTED['missionOrder'])
            self.assertTrue(all(a['resolution'] is None and a['asset'] is None for m in missions for a in m['assets']))
            self.assertLessEqual(router.failed_fetches(entries), router.expected_failures_in_pages('assets'))
            self.assertIn(router.expected_failure('assets'), router.failed_fetches(entries), 'some page waited for the timeout')
            self.facts['assets adapter down, whole list'] = {'http': 200, 'seconds of each page': [round(t, 2) for t in taken], 'entries': len(entries)}
            # The fields the mapping owns need no call to the dead adapter: the answer is complete and has no errors entry.
            status, body, seconds = self.ask('{ mission(missionId: "ST-00000LD4O") { missionId assets(release: "@RELEASE@") { localRef release assetId mappingOutcome } } }')
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'the owning adapter was not called, so its being down is not seen')
            self.assertEqual([a['assetId'] for a in body['data']['mission']['assets']],
                             [EXPECTED['references'][r]['assetId'] for r in EXPECTED['missions']['ST-00000LD4O']['assetRefs']])
            self.facts['assets adapter down, mapping fields only'] = {'http': status, 'seconds': round(seconds, 2), 'errors': 0}
        finally:
            controls.restore('assets-adapter')
        time.sleep(2)
        status, body, _ = self.ask('{ mission(missionId: "ST-00000LD4O") { assets(release: "@RELEASE@") { resolution } } }')
        self.assertEqual(status, 200)
        self.assertNotIn('errors', body)

    def test_05_when_the_mapping_adapter_is_down_a_query_without_its_fields_is_still_answered(self):
        controls, router = self.router.controls, self.router
        controls.stop('mapping-adapter')
        try:
            status, body, seconds = self.ask('{ mission(missionId: "ST-00000LD4O") { missionId title assets(release: "@RELEASE@") { localRef release } } }')
            self.assertEqual(status, 200)
            self.assertNotIn('errors', body, 'the mapping was not called, so its being down is not seen')
            self.facts['mapping adapter down, key fields only'] = {'http': status, 'seconds': round(seconds, 2)}
            # Selecting only `resolution` still needs the mapping subgraph: the router fetches the @requires input (assetId and
            # mappingOutcome) from it first, although the client did not ask for them.
            status, body, seconds = self.ask('{ mission(missionId: "ST-00000LD4O") { assets(release: "@RELEASE@") { localRef resolution } } }')
            self.assertEqual(status, 200)
            self.assertEqual(router.failed_fetches(body['errors']), {router.expected_failure('mapping')})
            self.facts['mapping adapter down, resolution selected'] = {'http': status, 'seconds': round(seconds, 2), 'service named in the errors': 'mapping'}
        finally:
            controls.restore('mapping-adapter')
        time.sleep(2)

    CREW_AND_ASSETS = ('{ mission(missionId: "ST-00000LD4O") { missionId title status assets(release: "@RELEASE@") { localRef assetId mappingOutcome resolution asset { assetId } } '
                       'crew(release: "@RELEASE@") { localRef personnelId mappingOutcome resolution personnel { personnelId } } } }')

    def check_kept(self, body, assets_down, personnel_down):
        mission = body['data']['mission']
        self.assertEqual(mission['missionId'], 'ST-00000LD4O')
        self.assertTrue(mission['title'] and mission['status'])
        for reference in mission['assets']:
            expected = EXPECTED['references'][reference['localRef']]
            self.assertEqual((reference['assetId'], reference['mappingOutcome']), (expected['assetId'], expected['mappingOutcome']))
            if assets_down:
                self.assertEqual((reference['resolution'], reference['asset']), (None, None))
            else:
                self.assertEqual(reference['resolution'], expected['resolution'])
        for reference in mission['crew']:
            expected = EXPECTED['crew']['references'][reference['localRef']]
            self.assertEqual((reference['personnelId'], reference['mappingOutcome']), (expected['personnelId'], expected['mappingOutcome']))
            if personnel_down:
                self.assertEqual((reference['resolution'], reference['personnel']), (None, None))
            else:
                self.assertEqual((reference['resolution'], reference['personnel']['personnelId']), (expected['resolution'], expected['personnelId']))
        failed = (['assets'] * len(mission['assets']) if assets_down else []) + (['personnel'] * len(mission['crew']) if personnel_down else [])
        entries = body.get('errors', [])
        self.assertEqual(self.router.subgraphs(entries), self.router.expected_subgraphs(failed), 'one entry per failed fetch, naming its subgraph')
        self.assertEqual(self.router.codes_of(entries), {self.router.settings.adapter_down_code} if failed else set())

    def run_with_stopped(self, names, check, query=None, variables=None, paged=False):
        """Stop the adapters, ask, check the answer, start them again. A paged query is asked page by page: each page waits for the
        subgraph timeout once, so each page must answer within the declared window, and the check sees the pages joined."""
        controls = self.router.controls
        for name in names:
            controls.stop(name + '-adapter')
        try:
            if paged:
                missions, entries, seconds = self.router.joined_pages(query, variables)
                self.adapter_down_pages_time(seconds)
                check({'data': {'missions': missions}, 'errors': entries})
                return [round(each, 2) for each in seconds]
            status, body, seconds = self.ask(query or self.CREW_AND_ASSETS, variables)
            self.assertEqual(status, 200)
            self.adapter_down_answer_time(seconds)
            check(body)
            return seconds
        finally:
            for name in names:
                controls.restore(name + '-adapter')
            time.sleep(2)

    def test_06_when_the_personnel_adapter_is_down_the_mission_keeps_everything_but_the_crew_resolution(self):
        seconds = self.run_with_stopped(['personnel'], lambda body: self.check_kept(body, False, True))
        self.facts['personnel adapter down'] = {'http': 200, 'seconds': round(seconds, 2), 'kept': 'mission fields, assets, crew personnelId and mappingOutcome'}

    def test_06b_question_6_with_the_personnel_adapter_down_nothing_is_guessed_and_the_missions_are_unconfirmed(self):
        controlled = EXPECTED['question6']['controlledCase']
        want = controlled['personnelDown']

        def check(body):
            missions = body['data']['missions']
            self.assertEqual([m['missionId'] for m in missions], EXPECTED['missionOrder'], 'a dead subgraph costs fields, never a mission')
            released = {**EXPECTED['crew']['references'], **EXPECTED['commandingOfficers']['references']}
            for mission in missions:
                for reference in personnel_of(mission):
                    expected = released[reference['localRef']]
                    self.assertEqual((reference['personnelId'], reference['mappingOutcome']), (expected['personnelId'], expected['mappingOutcome']))
                    self.assertEqual((reference['resolution'], reference['personnel']), (want['resolution'], None))
            # The controlled case: the only senior-ranked member of the mission is unresolved, so the mission is unconfirmed.
            controlled_mission = next(m for m in missions if m['missionId'] == controlled['missionId'])
            self.assertIsNone(next(c for c in personnel_of(controlled_mission) if c['localRef'] == controlled['onlySeniorReference'])['resolution'])
            answer = question_6(missions)
            self.assertIn(controlled['missionId'], answer['unconfirmedMissionIds'])
            self.assertEqual(counts_of(answer), counts_of(want))
            self.assertEqual(answer['notResolvedReferences'], want['notResolvedReferences'])
            self.assertLessEqual(self.router.failed_fetches(body['errors']), self.router.expected_failures_in_pages('personnel'))
            self.assertIn(self.router.expected_failure('personnel'), self.router.failed_fetches(body['errors']), 'some page waited for the timeout')
            self.facts['question 6, Personnel adapter down'] = {'confirmed with': answer['confirmedWithSenior'], 'confirmed without': answer['confirmedWithoutSenior'],
                                                                'unconfirmed': answer['unconfirmed'], 'percentage of the confirmed': answer['percentage'],
                                                                'cancelled missions not counted': answer['cancelledNotCounted'], 'references not resolved': answer['notResolvedReferences'], 'errors entries': len(body['errors'])}

        seconds = self.run_with_stopped(['personnel'], check, QUESTION_6, {'r': EXPECTED['crew']['release']}, paged=True)
        self.facts['question 6, Personnel adapter down: seconds of each page'] = seconds

    def test_07_when_both_owning_adapters_are_down_the_mission_still_answers_with_its_own_fields_and_the_mapping(self):
        seconds = self.run_with_stopped(['assets', 'personnel'], lambda body: self.check_kept(body, True, True))
        self.facts['assets and personnel adapters down'] = {'http': 200, 'seconds': round(seconds, 2)}

    def test_08_every_case_is_unchanged_once_the_adapters_are_back(self):
        # Adapters that were stopped and started again can get new addresses, and a router may keep the old ones until it is
        # restarted. That is the stack's behavior, not the graph's, so the router is restarted first (a router that needs none does nothing).
        self.router.controls.restart_router()
        status, body, _ = self.ask(self.CREW_AND_ASSETS)
        self.assertEqual(status, 200)
        self.assertNotIn('errors', body)
        self.check_kept(body, False, False)
