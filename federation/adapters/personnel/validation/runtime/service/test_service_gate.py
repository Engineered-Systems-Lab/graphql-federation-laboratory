"""Personnel adapter acceptance against the REAL Personnel v2 service (a light Java 17 container, no database).

The service image is built from the component's own Dockerfile (uss-enterprise/personnel-v2) and run on a private, uniquely named
Docker network with no published port, the way the component's compose file builds and runs it (that compose file publishes the
fixed host port 8082, which a gate must not take). The adapter image is built from the committed Dockerfile and runs on the same
network, reaching the service by its network alias. The expected answers are read from the two registered snapshots: the members,
the choice of details, the sorting, the filters, the paging, the Wesley case (one personnel identity, a civilian in 001 and crew in
002) and the datasetVersion of each snapshot. Then the service is restarted with the failure profiles unavailable and slow, and
stopped, to show UNAVAILABLE as data with one SERVICE_UNAVAILABLE entry per failed call.

Everything is disposable and uniquely named per run; the gate removes only what it created. Missing Docker is a failure.
"""
from pathlib import Path
import json
import secrets
import sys
import time
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402

SERVICE_DIR = support.ROOT / 'uss-enterprise/personnel-v2'
SNAPSHOTS = SERVICE_DIR / 'datasets'
NS = '{urn:graphql-federation-lab:personnel:v2}'
STATE = {}
TIMINGS = {}


def text(element, name):
    child = element.find(NS + name)
    return None if child is None else child.text


def member(element):
    crew = element.find(NS + 'crewDetails')
    if crew is None:
        details = {'__typename': 'CivilianDetails', 'placeholder': None}
    else:
        details = {'__typename': 'CrewDetails', 'rank': text(crew, 'rank'), 'department': text(crew, 'department'),
                   'securityClearance': text(crew, 'securityClearance'), 'supervisorPersonnelId': text(crew, 'supervisorPersonnelId')}
    return {'personnelId': text(element, 'personnelId'), 'displayName': text(element, 'displayName'), 'positionTitle': text(element, 'positionTitle'),
            'dutyStatus': text(element, 'dutyStatus'), 'details': details}


def snapshot(name):
    """The datasetVersion and the members of a registered snapshot, in the service's order."""
    root = ET.parse(SNAPSHOTS / (name + '.xml')).getroot()
    return text(root, 'datasetVersion'), [member(e) for e in root.findall(NS + 'personnelMember')]


def codes(answer):
    return [error['extensions']['code'] for error in answer.get('errors', [])]


def start_service(dataset, profile='normal'):
    support.run(['docker', 'rm', '--force', STATE['service']])  # only the container of this run, which may not exist yet
    support.docker(['run', '-d', '--name', STATE['service'], '--network', STATE['network'], '--network-alias', 'personnel',
                    '-e', 'PERSONNEL_DATASET_VERSION=' + dataset, '-e', 'PERSONNEL_FAILURE_PROFILE=' + profile, STATE['service_image']])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        logs = support.run(['docker', 'logs', STATE['service']])
        if 'dataset=' + dataset in logs.stdout + logs.stderr:
            return
        time.sleep(1)
    raise RuntimeError('The Personnel v2 service did not report that it was published')


def warm_up():
    """The first request of a cold JVM can exceed the adapter's 1.5 s read timeout; wait until the service answers one inside it."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if 'errors' not in support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0001'}, timeout=30):
            return
        time.sleep(1)
    raise RuntimeError('The Personnel v2 service did not answer through the adapter')


def setUpModule():
    token = secrets.token_hex(6)
    STATE.update(token=token, network='fed-personnel-svc-' + token, service_image='fed-personnel-service-validation:' + token,
                 adapter_image='fed-personnel-adapter-validation:' + token, service='fed-personnel-svc-' + token,
                 adapter='fed-personnel-adapter-' + token, port=support.free_port(), started=time.monotonic())
    support.docker(['version', '--format', '{{.Server.Version}}'])
    support.docker(['network', 'create', STATE['network']])
    started = time.monotonic()
    support.docker(['build', '-t', STATE['service_image'], str(SERVICE_DIR)], timeout=1800)
    TIMINGS['service build'] = round(time.monotonic() - started, 1)
    started = time.monotonic()
    support.build_image(STATE['adapter_image'])
    TIMINGS['adapter build'] = round(time.monotonic() - started, 1)
    start_service('personnel-v2-small-002')
    support.docker(['run', '-d', '--name', STATE['adapter'], '--network', STATE['network'], '-p', f"127.0.0.1:{STATE['port']}:8182",
                    '-e', 'ADAPTER_BIND_HOST=0.0.0.0', '-e', 'PERSONNEL_SERVICE_URL=http://personnel:8082/soap/personnel-v2', STATE['adapter_image']])
    support.wait_for_graphql(STATE['port'])
    warm_up()


def tearDownModule():
    problems = []
    for container in (STATE['adapter'], STATE['service']):
        result = support.run(['docker', 'rm', '--force', container])
        if result.returncode and 'No such container' not in result.stderr:
            problems.append('container: ' + result.stderr[-500:])
    result = support.run(['docker', 'network', 'rm', STATE['network']])
    if result.returncode and 'not found' not in result.stderr:
        problems.append('network: ' + result.stderr[-500:])
    for image in (STATE['adapter_image'], STATE['service_image']):
        result = support.run(['docker', 'rmi', '--force', image])
        if result.returncode and 'No such image' not in result.stderr:
            problems.append('image: ' + result.stderr[-500:])
    TIMINGS['module total'] = round(time.monotonic() - STATE['started'], 1)
    print('personnel-adapter service timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


class AdapterAgainstTheRealService(unittest.TestCase):
    def test_01_every_member_of_the_default_snapshot_is_served_by_its_id(self):
        version, members = snapshot('personnel-v2-small-002')
        self.assertEqual(len(members), 7)
        for expected in members:
            answer = support.graphql(STATE['port'], support.PERSONNEL, {'id': expected['personnelId']})
            self.assertNotIn('errors', answer)
            self.assertEqual(answer['data']['personnel'], expected, expected['personnelId'])

    def test_02_the_default_page_is_the_whole_snapshot_in_order_with_its_dataset_version(self):
        version, members = snapshot('personnel-v2-small-002')
        answer = support.graphql(STATE['port'], support.MEMBERS, {})
        self.assertNotIn('errors', answer)
        page = answer['data']['personnelMembers']
        self.assertEqual(page['datasetVersion'], version)
        self.assertEqual((page['totalCount'], page['offset'], page['limit'], page['hasMore']), (7, 0, 20, False))
        self.assertEqual(page['items'], members)

    def test_03_offset_limit_and_filters_match_the_snapshot(self):
        version, members = snapshot('personnel-v2-small-002')
        window = support.graphql(STATE['port'], support.MEMBERS, {'offset': 2, 'limit': 3})['data']['personnelMembers']
        self.assertEqual([m['personnelId'] for m in window['items']], [m['personnelId'] for m in members[2:5]])
        self.assertEqual((window['hasMore'], window['totalCount']), (True, 7))
        past = support.graphql(STATE['port'], support.MEMBERS, {'offset': 7, 'limit': 100})['data']['personnelMembers']
        self.assertEqual((past['items'], past['hasMore'], past['totalCount']), ([], False, 7))
        full = support.graphql(STATE['port'], support.MEMBERS, {'offset': 0, 'limit': 100})['data']['personnelMembers']
        self.assertEqual(full['items'], members)
        both = support.graphql(STATE['port'], support.MEMBERS, {'department': 'OPERATIONS', 'dutyStatus': 'ACTIVE'})['data']['personnelMembers']
        self.assertEqual([m['personnelId'] for m in both['items']], ['PRS-0002', 'PRS-0714'])
        leave = support.graphql(STATE['port'], support.MEMBERS, {'dutyStatus': 'ON_LEAVE'})['data']['personnelMembers']
        self.assertEqual([m['personnelId'] for m in leave['items']], [m['personnelId'] for m in members if m['dutyStatus'] == 'ON_LEAVE'])
        crew_only = support.graphql(STATE['port'], support.MEMBERS, {'department': 'COMMAND'})['data']['personnelMembers']
        self.assertEqual([m['personnelId'] for m in crew_only['items']], ['PRS-0001'], 'a department matches crew only')
        refused = support.graphql(STATE['port'], support.MEMBERS, {'offset': 0, 'limit': 101})
        self.assertIsNone(refused['data']['personnelMembers'])
        self.assertEqual(codes(refused), ['BAD_USER_INPUT'])

    def test_04_a_missing_member_is_null_and_a_malformed_id_is_bad_user_input(self):
        missing = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-9999'})
        self.assertIsNone(missing['data']['personnel'])
        self.assertNotIn('errors', missing)
        for bad in ('PRS-0000', 'x', 'prs-0001', '<PRS-0001>', 'PRS-0001 '):
            malformed = support.graphql(STATE['port'], support.PERSONNEL, {'id': bad})
            self.assertIsNone(malformed['data']['personnel'], bad)
            self.assertEqual(codes(malformed), ['BAD_USER_INPUT'], bad)

    def test_05_the_four_outcomes_of_a_crew_reference(self):
        version, members = snapshot('personnel-v2-small-002')
        by_id = {m['personnelId']: m for m in members}
        answer = support.graphql(STATE['port'], support.REFERENCES, {'r': [
            support.reference('C-1', 'PRS-0001'), support.reference('C-3', 'PRS-0003'), support.reference('C-404', 'PRS-9999'), support.reference('C-77', None)]})
        self.assertNotIn('errors', answer, 'UNRESOLVED and UNMAPPED are data and add no errors entry')
        entities = answer['data']['_entities']
        self.assertEqual([e['resolution'] for e in entities], ['RESOLVED', 'RESOLVED', 'UNRESOLVED', 'UNMAPPED'])
        self.assertEqual(entities[0]['personnel'], by_id['PRS-0001'])
        self.assertEqual(entities[1]['personnel'], by_id['PRS-0003'], 'a civilian resolves too')
        self.assertEqual([e['personnelId'] for e in entities], ['PRS-0001', 'PRS-0003', 'PRS-9999', None])
        self.assertEqual([e['personnel'] for e in entities[2:]], [None, None])
        a_member = support.graphql(STATE['port'], 'query($r: [_Any!]!) { _entities(representations: $r) { ... on Personnel { personnelId displayName } } }',
                                   {'r': [{'__typename': 'Personnel', 'personnelId': 'PRS-0004'}, {'__typename': 'Personnel', 'personnelId': 'PRS-9999'}]})
        self.assertEqual(a_member['data']['_entities'], [{'personnelId': 'PRS-0004', 'displayName': 'Mara Venn'}, None])
        self.assertNotIn('errors', a_member)

    def test_06_the_wesley_case_follows_the_snapshot_the_service_serves(self):
        crew = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0714'})['data']['personnel']
        self.assertEqual(crew['details'], {'__typename': 'CrewDetails', 'rank': 'ENSIGN', 'department': 'OPERATIONS', 'securityClearance': 'NONE',
                                           'supervisorPersonnelId': 'PRS-0002'})
        start_service('personnel-v2-small-001')
        version, members = snapshot('personnel-v2-small-001')
        civilian = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0714'})['data']['personnel']
        self.assertEqual(civilian['details'], {'__typename': 'CivilianDetails', 'placeholder': None})
        self.assertEqual(civilian['positionTitle'], 'Student')
        reference = support.graphql(STATE['port'], support.REFERENCES, {'r': [support.reference('C-714', 'PRS-0714')]})['data']['_entities'][0]
        self.assertEqual(reference['resolution'], 'RESOLVED')
        self.assertEqual(reference['personnel']['details']['__typename'], 'CivilianDetails')
        page = support.graphql(STATE['port'], support.MEMBERS, {})['data']['personnelMembers']
        self.assertEqual(page['datasetVersion'], version)
        self.assertNotEqual(version, snapshot('personnel-v2-small-002')[0], 'a client sees the snapshot change')
        self.assertEqual(page['items'], members)

    def test_07_a_service_that_reports_itself_unavailable_gives_unavailable_with_one_entry_per_failed_call(self):
        start_service('personnel-v2-small-002', 'unavailable')
        answer = support.graphql(STATE['port'], support.REFERENCES, {'r': [support.reference('C-1', 'PRS-0001'), support.reference('C-2', 'PRS-0002'),
                                                                           support.reference('C-3', None)]}, timeout=60)
        self.assertEqual([e['resolution'] for e in answer['data']['_entities']], ['UNAVAILABLE', 'UNAVAILABLE', 'UNMAPPED'])
        self.assertEqual([e['personnel'] for e in answer['data']['_entities']], [None] * 3)
        self.assertEqual(codes(answer), ['SERVICE_UNAVAILABLE'] * 2)
        single = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0001'})
        self.assertIsNone(single['data']['personnel'])
        self.assertEqual(codes(single), ['SERVICE_UNAVAILABLE'])
        page = support.graphql(STATE['port'], support.MEMBERS, {'limit': 100})
        self.assertIsNone(page['data']['personnelMembers'])
        self.assertEqual(codes(page), ['SERVICE_UNAVAILABLE'])
        invalid = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0000'})
        self.assertEqual(codes(invalid), ['BAD_USER_INPUT'], 'the service validates a request before it reports itself unavailable')

    def test_07b_the_whole_large_snapshot_is_read_in_pages_and_served_from_memory(self):
        start_service('personnel-v2-large-004')
        warm_up()
        members = {}
        version = None
        offset = 0
        while True:
            page = support.graphql(STATE['port'], support.MEMBERS, {'offset': offset, 'limit': 100})['data']['personnelMembers']
            version = version or page['datasetVersion']
            self.assertEqual(page['datasetVersion'], version)
            for item in page['items']:
                members[item['personnelId']] = item
            offset += len(page['items'])
            if not page['hasMore']:
                break
        ids = list(members)
        self.assertGreater(len(ids), 500, 'the large snapshot holds hundreds of people, which the adapter reads in several pages')
        self.assertEqual(ids, sorted(ids))
        absent = next('PRS-%04d' % number for number in range(9999, 0, -1) if 'PRS-%04d' % number not in members)
        asked = [ids[0], ids[len(ids) // 3], ids[len(ids) // 2], ids[-1]]
        references = [support.reference('C-%d' % index, personnel_id) for index, personnel_id in enumerate(asked)] + [support.reference('C-absent', absent)]
        started = time.monotonic()
        first = support.graphql(STATE['port'], support.REFERENCES, {'r': references}, timeout=60)
        TIMINGS['first batch, snapshot read'] = round(time.monotonic() - started, 2)
        self.assertNotIn('errors', first)
        self.assertEqual([e['resolution'] for e in first['data']['_entities']], ['RESOLVED'] * len(asked) + ['UNRESOLVED'])
        self.assertEqual([e['personnel'] for e in first['data']['_entities'][:len(asked)]], [members[i] for i in asked])
        started = time.monotonic()
        second = support.graphql(STATE['port'], support.REFERENCES, {'r': references}, timeout=60)
        TIMINGS['second batch, from memory'] = round(time.monotonic() - started, 2)
        self.assertEqual(second['data'], first['data'])
        self.assertNotIn('errors', second)
        a_member = support.graphql(STATE['port'], 'query($r: [_Any!]!) { _entities(representations: $r) { ... on Personnel { personnelId displayName } } }',
                                   {'r': [{'__typename': 'Personnel', 'personnelId': ids[-1]}, {'__typename': 'Personnel', 'personnelId': absent}]})
        self.assertEqual(a_member['data']['_entities'], [{'personnelId': ids[-1], 'displayName': members[ids[-1]]['displayName']}, None])
        self.assertNotIn('errors', a_member)

    def test_08_a_slow_service_is_a_timeout_and_a_stopped_one_is_a_refused_connection(self):
        start_service('personnel-v2-small-002', 'slow')
        started = time.monotonic()
        slow = support.graphql(STATE['port'], support.PERSONNEL, {'id': 'PRS-0001'}, timeout=60)
        TIMINGS['slow answer'] = round(time.monotonic() - started, 1)
        self.assertIsNone(slow['data']['personnel'])
        self.assertEqual(codes(slow), ['SERVICE_UNAVAILABLE'])
        support.docker(['stop', '--time', '10', STATE['service']])
        stopped = support.graphql(STATE['port'], support.REFERENCES, {'r': [support.reference('C-1', 'PRS-0001'), support.reference('C-2', 'PRS-0002')]}, timeout=60)
        self.assertEqual([e['resolution'] for e in stopped['data']['_entities']], ['UNAVAILABLE', 'UNAVAILABLE'])
        self.assertEqual(codes(stopped), ['SERVICE_UNAVAILABLE'] * 2)
        page = support.graphql(STATE['port'], support.MEMBERS, {'limit': 100})
        self.assertIsNone(page['data']['personnelMembers'])
        self.assertEqual(codes(page), ['SERVICE_UNAVAILABLE'])


if __name__ == '__main__':
    unittest.main()
