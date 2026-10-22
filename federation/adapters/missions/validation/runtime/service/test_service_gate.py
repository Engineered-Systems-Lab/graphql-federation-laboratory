"""Missions adapter acceptance against the REAL Missions service on Oracle 18c.

It reuses the harness of the Missions service gates (uss-enterprise/missions/validation/runtime/service/service_harness.py): a
uniquely named MS_TEST_ schema loaded with release 1.2, a read-only login, the Missions service image built from its own
Dockerfile, and two service containers, one with the right database password and one with a wrong one (which answers 500). The
adapter image is built from the committed adapter Dockerfile and runs on the default bridge beside them, reaching a service by
its bridge address, so nothing is published beyond ephemeral loopback ports.

The expected answers come from released dataset 1.2 (300 missions, the participants reclassified as P and O) as the Missions harness loads it: every mission with every field, the
service's order, the paging windows, every filter, the not-found, malformed and refused cases, the asset reference stubs, a
real 500 and a stopped service.

THE REVIEWED ORACLE CONTAINER MUST ALREADY BE RUNNING, as for the Missions gates (about 9 GB, minutes to start; the lead developer
keeps it stopped, so this stage is never part of a checkpoint). Everything this stage creates is disposable and removed by it;
Oracle itself is not started, stopped or changed beyond the disposable schema and login. Missing Docker or Oracle is a failure.
"""
from pathlib import Path
import json
import secrets
import sys
import time

COMPONENT = Path(__file__).resolve().parents[3]
ROOT = COMPONENT.parents[2]
sys.path.insert(0, str(COMPONENT / 'validation/runtime'))
sys.path.insert(0, str(ROOT / 'uss-enterprise/missions/validation/runtime/service'))
import adapter_support as support  # noqa: E402
import service_harness as harness  # noqa: E402

operator = harness.operator
TIMINGS = {}
RELEASE = '1.2'   # the Missions dataset release this stage loads; the adapter serves it only
PAGE_LIMIT = 100  # the largest page the adapter accepts


def shape(mission):
    """The adapter's answer in the harness's shape: optional values that are null are left out."""
    shaped = {key: value for key, value in mission.items() if value is not None}
    shaped['location'] = {key: value for key, value in mission['location'].items() if value is not None}
    return shaped


def codes(answer):
    return [error['extensions']['code'] for error in answer.get('errors', [])]


class AdapterAgainstTheRealService(harness.ServiceCase):
    KIND = 'adapter'

    @classmethod
    def grants(cls):
        return ['GRANT SELECT ON ' + cls.schema + '.' + table + ' TO ' + cls.login + ';' for table in operator.TABLES]

    @classmethod
    def prepare(cls):
        # The shared Missions harness loads release 1.0 for its own service gates and has no seam for another release; this stage
        # asks it for RELEASE instead, for the length of the call only, so the Missions component is left untouched.
        reset, validate = harness.operator.reset, harness.validation.validate_release
        harness.operator.reset = lambda version, *args, **kwargs: reset(RELEASE if version == '1.0' else version, *args, **kwargs)
        harness.validation.validate_release = lambda version, *args, **kwargs: validate(RELEASE if version == '1.0' else version, *args, **kwargs)
        try:
            super().prepare()
        finally:
            harness.operator.reset, harness.validation.validate_release = reset, validate
        if cls.manifest.get('datasetVersion') != RELEASE or len(cls.data['missions']) != 300:
            raise RuntimeError('The harness did not load release ' + RELEASE + ' with its 300 missions')
        started = time.monotonic()
        cls.adapter_image = 'federation-missions-adapter-validation:' + cls.run_id
        support.build_image(cls.adapter_image)
        TIMINGS['adapter build'] = round(time.monotonic() - started, 1)
        started = time.monotonic()
        cls.adapter = cls.start_adapter('correct', cls.containers[0])
        cls.bad_adapter = cls.start_adapter('wrong', cls.containers[1])
        TIMINGS['adapters ready'] = round(time.monotonic() - started, 1)
        # The first call through the service opens its database pool; it is not part of what the tests time.
        cls.warm_up()

    @classmethod
    def start_adapter(cls, which, service):
        address = json.loads(harness.docker(['inspect', service]))[0]['NetworkSettings']['Networks']['bridge']['IPAddress']
        name = 'fed-missions-adapter-' + which + '-' + cls.run_id
        harness.docker(['create', '--name', name, '--label', 'starfleet.federation.missions-adapter-validation=' + cls.run_id, '-p', '127.0.0.1::8183',
                        '-e', 'ADAPTER_BIND_HOST=0.0.0.0', '-e', 'MISSIONS_SERVICE_URL=http://' + address + ':8083', '-e', 'MISSIONS_READ_TIMEOUT_MS=5000',
                        cls.adapter_image])
        cls.containers.append(name)
        harness.docker(['start', name])
        binding = json.loads(harness.docker(['inspect', name]))[0]['NetworkSettings']['Ports']['8183/tcp'][0]
        if binding['HostIp'] != '127.0.0.1':
            raise RuntimeError('Adapter publication must be loopback only')
        port = int(binding['HostPort'])
        support.wait_for_graphql(port)
        return port

    @classmethod
    def warm_up(cls):
        deadline = time.monotonic() + 60
        while True:
            answer = support.graphql(cls.adapter, support.MISSION, {'id': cls.data['missions'][0]['missionId']}, timeout=30)
            if answer['data']['mission'] and not answer.get('errors'):
                return
            if time.monotonic() >= deadline:
                raise RuntimeError('The adapter could not read a mission through the service: ' + json.dumps(answer)[:500])
            time.sleep(1)

    @classmethod
    def cleanup(cls):
        try:
            super().cleanup()
        finally:
            result = support.run(['docker', 'rmi', '--force', 'federation-missions-adapter-validation:' + cls.run_id])
            if result.returncode and 'No such image' not in result.stderr:
                print('missions-adapter: image was not removed: ' + result.stderr[-300:], file=sys.stderr, flush=True)
            print('missions-adapter service timings (seconds): ' + json.dumps(TIMINGS), flush=True)

    # --- helpers -----------------------------------------------------------------------------------------

    def gql(self, query, variables=None, port=None):
        return support.graphql(port or self.adapter, query, variables, timeout=60)

    def all_missions(self, filters=''):
        """Every mission a filter selects, read page by page at the adapter's largest page."""
        found = []
        while True:
            page = self.missions(len(found), PAGE_LIMIT, filters)
            found += page
            if len(page) < PAGE_LIMIT:
                return found

    def missions(self, offset=0, limit=20, filters=''):
        query = 'query($offset: Int, $limit: Int) { missions(' + filters + ' offset: $offset, limit: $limit) { ' + support.MISSION_FIELDS + ' } }'
        answer = self.gql(query, {'offset': offset, 'limit': limit})
        self.assertNotIn('errors', answer, answer)
        return [shape(m) for m in answer['data']['missions']]

    # --- acceptance --------------------------------------------------------------------------------------

    def test_01_every_mission_equals_the_release_with_every_field_as_the_service_sent_it(self):
        self.assertEqual(len(self.data['missions']), 300)
        for mission in self.data['missions']:
            answer = self.gql(support.MISSION, {'id': mission['missionId']})
            self.assertNotIn('errors', answer, answer)
            self.assertEqual(shape(answer['data']['mission']), self.expected(mission), mission['missionId'])

    def test_02_every_paging_window_equals_the_slice_of_the_services_order(self):
        ordered = [self.expected(m) for m in self.ordered()]
        self.assertEqual(self.missions(), ordered[:20])
        self.assertEqual(self.missions(20, 20), ordered[20:40])
        self.assertEqual(self.missions(290, 20), ordered[290:])
        self.assertEqual(self.missions(300, 20), [])
        self.assertEqual(self.missions(2000000000, 5), [])
        self.assertEqual(self.all_missions(), ordered)
        for offset in sorted({*range(0, 306, 17), 99, 100, 101, 199, 200, 201, 298, 299, 300, 301}):
            for limit in (1, 4, 9, 20, 31, 50, 51, 75, 100):
                with self.subTest(offset=offset, limit=limit):
                    self.assertEqual(self.missions(offset, limit), ordered[offset:offset + limit])

    def test_03_every_filter_and_their_conjunction(self):
        missions = self.data['missions']
        selectors = {
            'type': lambda m, v: m['type'] == v, 'classification': lambda m, v: m['classification'] == v, 'status': lambda m, v: m['status'] == v,
            'priority': lambda m, v: str(m['priority']) == v, 'issuingAuthority': lambda m, v: m['issuingAuthority'] == v,
            'commandingOfficerId': lambda m, v: m.get('commandingOfficerId') == v, 'assignedCrewId': lambda m, v: v in m['assignedCrewIds'],
            'assignedAssetId': lambda m, v: v in m['assignedAssetIds'], 'locationType': lambda m, v: m['location']['type'] == v}
        values = {
            'type': {m['type'] for m in missions}, 'classification': {m['classification'] for m in missions}, 'status': {m['status'] for m in missions},
            'priority': {str(m['priority']) for m in missions}, 'issuingAuthority': {m['issuingAuthority'] for m in missions},
            'commandingOfficerId': {m['commandingOfficerId'] for m in missions if 'commandingOfficerId' in m},
            'assignedCrewId': {c for m in missions for c in m['assignedCrewIds']}, 'assignedAssetId': {a for m in missions for a in m['assignedAssetIds']},
            'locationType': {m['location']['type'] for m in missions}}
        bare = ('type', 'classification', 'status', 'issuingAuthority', 'locationType', 'priority')   # enums and the integer are written without quotes
        checked = 0
        for name, choices in values.items():
            for value in sorted(choices):
                literal = value if name in bare else json.dumps(value)
                expected = [self.expected(m) for m in self.ordered([m for m in missions if selectors[name](m, value)])]
                with self.subTest(filter=name, value=value):
                    self.assertEqual(self.all_missions(name + ': ' + literal + ','), expected)
                checked += 1
        self.assertGreater(checked, 40)
        both = [self.expected(m) for m in self.ordered([m for m in missions if m['status'] == 'COMPLETED' and 'EQ-64' in m['assignedAssetIds']])]
        self.assertEqual(len(both), 40)
        self.assertEqual(self.all_missions('status: COMPLETED, assignedAssetId: "EQ-64",'), both)

    def test_04_not_found_is_null_with_no_entry_and_malformed_input_is_bad_user_input(self):
        missing = self.gql(support.MISSION, {'id': 'ST-ZZZZZZZZZ'})
        self.assertIsNone(missing['data']['mission'])
        self.assertNotIn('errors', missing)
        malformed = self.gql(support.MISSION, {'id': 'sh-17'})
        self.assertIsNone(malformed['data']['mission'])
        self.assertEqual(codes(malformed), ['BAD_USER_INPUT'])
        for arguments in ('priority: 9', 'commandingOfficerId: "x"', 'assignedAssetId: "eq-64"'):
            answer = self.gql('{ missions(' + arguments + ') { missionId } }')
            self.assertIsNone(answer['data']['missions'], arguments)
            self.assertEqual(codes(answer), ['BAD_USER_INPUT'], arguments)

    def test_05_the_asset_stubs_are_the_references_as_stored_with_the_named_release(self):
        for mission in self.data['missions']:
            answer = self.gql(support.ASSETS, {'id': mission['missionId'], 'release': '1.0'})
            self.assertNotIn('errors', answer, answer)
            self.assertEqual(answer['data']['mission']['assets'], [{'localRef': ref, 'release': '1.0'} for ref in mission['assignedAssetIds']], mission['missionId'])

    def test_06_the_mission_entity_resolves_by_its_key_and_an_unknown_key_is_null(self):
        known = self.data['missions'][3]['missionId']
        answer = self.gql('query($r: [_Any!]!) { _entities(representations: $r) { ... on Mission { missionId title status } } }',
                          {'r': [{'__typename': 'Mission', 'missionId': known}, {'__typename': 'Mission', 'missionId': 'ST-ZZZZZZZZZ'}]})
        self.assertNotIn('errors', answer, answer)
        self.assertEqual(answer['data']['_entities'][0], {'missionId': known, 'title': self.data['missions'][3]['title'], 'status': self.data['missions'][3]['status']})
        self.assertIsNone(answer['data']['_entities'][1])

    def test_07_a_real_500_from_the_service_is_service_unavailable_with_one_entry(self):
        answer = self.gql(support.MISSION, {'id': self.data['missions'][0]['missionId']}, self.bad_adapter)
        self.assertIsNone(answer['data']['mission'])
        self.assertEqual(codes(answer), ['SERVICE_UNAVAILABLE'])
        page = self.gql('{ missions(limit: 75) { missionId } }', None, self.bad_adapter)
        self.assertIsNone(page['data']['missions'])
        self.assertEqual(codes(page), ['SERVICE_UNAVAILABLE'])

    def test_08_an_id_that_cannot_be_one_path_segment_is_bad_user_input_and_odd_characters_reach_the_service_encoded(self):
        for text in ('ST-0/1', '../missions', '..', 'ST-0?1', 'ST-0%1', 'ST- 1', 'ST-\u00e9'):
            answer = self.gql(support.MISSION, {'id': text})
            self.assertIsNone(answer['data']['mission'], text)
            self.assertEqual(codes(answer), ['BAD_USER_INPUT'], text)

    def test_09_with_the_service_stopped_the_mission_is_unavailable_as_data(self):
        harness.docker(['stop', '--time', '10', self.containers[0]])
        started = time.monotonic()
        answer = self.gql(support.MISSION, {'id': self.data['missions'][0]['missionId']})
        self.assertIsNone(answer['data']['mission'])
        self.assertEqual(codes(answer), ['SERVICE_UNAVAILABLE'])
        page = self.gql('{ missions(limit: 100) { missionId } }')
        self.assertIsNone(page['data']['missions'])
        self.assertEqual(codes(page), ['SERVICE_UNAVAILABLE'])
        TIMINGS['two failed calls with the service stopped'] = round(time.monotonic() - started, 1)


if __name__ == '__main__':
    import unittest
    unittest.main()
