"""Assets adapter acceptance against the REAL Assets service and a disposable PostgreSQL 17.

The Assets stack is started from the Assets compose file in a uniquely named project (random credentials, an ephemeral loopback
port); the adapter image is built from the committed Dockerfile and runs on that project's network, reaching the service by its
service name. The expected answers come from the released Assets dataset 1.1: the assets themselves and the expected mapping
with its three layers (the mapping, the Assets answer, the consumer). The last test stops the Assets service container to show
UNAVAILABLE as data with one SERVICE_UNAVAILABLE entry per failed call.

Everything is disposable and uniquely named per run; the gate removes only what it created. Missing Docker is a failure.
"""
from pathlib import Path
import json
import os
import secrets
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402

RELEASE = support.ROOT / 'uss-enterprise/assets/datasets/releases/1.1'
ASSETS_COMPOSE = support.ROOT / 'uss-enterprise/assets/compose.yaml'
STATE = {}
TIMINGS = {}
KEYS = ('assetId', 'kind', 'category', 'name', 'description', 'status', 'parentAssetId')


def assets_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ASSETS_', 'PG', 'COMPOSE_'))}
    env.update(COMPOSE_PROJECT_NAME=STATE['project'], ASSETS_IMAGE=STATE['service_image'], ASSETS_CONTAINER_NAME=STATE['service'],
               ASSETS_DB_CONTAINER_NAME=STATE['database'], ASSETS_HOST_PORT=str(STATE['service_port']),
               ASSETS_DB_ADMIN_PASSWORD=STATE['admin_password'], ASSETS_DB_SERVICE_PASSWORD=STATE['service_password'])
    return env


def assets_compose(args, timeout=900):
    return support.run(['docker', 'compose', '-f', str(ASSETS_COMPOSE)] + args, assets_env(), timeout)


def setUpModule():
    token = secrets.token_hex(6)
    STATE.update(token=token, project='fed-assets-svc-' + token, service_image='fed-assets-service-validation:' + token,
                 adapter_image='fed-assets-adapter-validation:' + token, service='fed-assets-svc-' + token, database='fed-assets-db-' + token,
                 adapter='fed-assets-adapter-' + token, service_port=support.free_port(), port=support.free_port(),
                 admin_password=secrets.token_hex(16), service_password=secrets.token_hex(16), started=time.monotonic())
    support.docker(['version', '--format', '{{.Server.Version}}'])
    started = time.monotonic()
    result = assets_compose(['up', '-d', '--build', '--wait', '--wait-timeout', '300'], timeout=1200)
    if result.returncode:
        raise RuntimeError('The Assets stack did not start: ' + (result.stderr or result.stdout)[-2000:])
    TIMINGS['assets stack'] = round(time.monotonic() - started, 1)
    started = time.monotonic()
    support.docker(['build', '--no-cache', '-t', STATE['adapter_image'], '-f', str(support.COMPONENT / 'Dockerfile'), str(support.FEDERATION)], timeout=1800)
    TIMINGS['adapter build'] = round(time.monotonic() - started, 1)
    support.docker(['run', '-d', '--name', STATE['adapter'], '--network', STATE['project'] + '_default', '-p', f"127.0.0.1:{STATE['port']}:8184",
                    '-e', 'ADAPTER_BIND_HOST=0.0.0.0', '-e', 'ASSETS_SERVICE_URL=http://assets:8084', STATE['adapter_image']])
    support.wait_for_graphql(STATE['port'])


def tearDownModule():
    problems = []
    result = support.run(['docker', 'rm', '--force', STATE['adapter']])
    if result.returncode and 'No such container' not in result.stderr:
        problems.append('adapter container: ' + result.stderr[-500:])
    result = assets_compose(['down', '--volumes', '--remove-orphans'], timeout=240)
    if result.returncode:
        problems.append('compose down: ' + result.stderr[-1500:])
    for image in (STATE['adapter_image'], STATE['service_image']):
        result = support.run(['docker', 'rmi', '--force', image])
        if result.returncode and 'No such image' not in result.stderr:
            problems.append('image: ' + result.stderr[-500:])
    TIMINGS['module total'] = round(time.monotonic() - STATE['started'], 1)
    print('assets-adapter service timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


def dataset():
    return json.loads((RELEASE / 'assets.json').read_text(encoding='utf-8'))['assets']


def expected_mapping():
    return json.loads((RELEASE / 'provenance.json').read_text(encoding='utf-8'))['expectedMapping']


def by_number(record):
    return int(record['assetId'].split('-')[1])


def pick(record):
    return {key: record[key] for key in KEYS}


def codes(answer):
    return [error['extensions']['code'] for error in answer.get('errors', [])]


class AdapterAgainstTheRealService(unittest.TestCase):
    def test_01_every_dataset_asset_is_served_by_its_id(self):
        for record in dataset():
            answer = support.graphql(STATE['port'], 'query($id: ID!) { asset(assetId: $id) { assetId kind category name description status parentAssetId } }',
                                     {'id': record['assetId']})
            self.assertNotIn('errors', answer)
            self.assertEqual(answer['data']['asset'], pick(record), record['assetId'])

    def test_02_a_page_above_fifty_takes_two_calls_and_returns_the_whole_dataset_in_order(self):
        answer = support.graphql(STATE['port'], '{ assets(limit: 100) { assetId kind category name description status parentAssetId } }')
        self.assertNotIn('errors', answer)
        self.assertEqual(answer['data']['assets'], [pick(r) for r in sorted(dataset(), key=by_number)])

    def test_03_offset_limit_and_filters_match_the_dataset(self):
        records = sorted(dataset(), key=by_number)
        page = support.graphql(STATE['port'], '{ assets(offset: 28, limit: 10) { assetId } }')['data']['assets']
        self.assertEqual([a['assetId'] for a in page], [r['assetId'] for r in records[28:38]])
        self.assertEqual(len(support.graphql(STATE['port'], '{ assets { assetId } }')['data']['assets']), 20)
        destroyed = support.graphql(STATE['port'], '{ assets(status: DESTROYED) { assetId } }')['data']['assets']
        self.assertEqual([a['assetId'] for a in destroyed], [r['assetId'] for r in records if r['status'] == 'DESTROYED'])
        vehicles = support.graphql(STATE['port'], '{ assets(category: VEHICLE, limit: 100) { assetId } }')['data']['assets']
        self.assertEqual([a['assetId'] for a in vehicles], [r['assetId'] for r in records if r['category'] == 'VEHICLE'])
        children = support.graphql(STATE['port'], '{ assets(parentAssetId: "AST-0029") { assetId } }')['data']['assets']
        self.assertEqual([a['assetId'] for a in children], [r['assetId'] for r in records if r['parentAssetId'] == 'AST-0029'])

    def test_04_the_expected_mapping_gives_the_expected_outcomes(self):
        by_id = {r['assetId']: r for r in dataset()}
        mapping = expected_mapping()
        answer = support.graphql(STATE['port'], support.REFERENCES, {'r': [support.reference(m['missionsReference'], m['mapsTo']) for m in mapping]})
        self.assertNotIn('errors', answer, 'UNRESOLVED and UNMAPPED are data and add no errors entry')
        wanted = {'RESOLVED': 'RESOLVED', 'UNRESOLVED': 'UNRESOLVED', 'NO_MAPPING': 'UNMAPPED'}
        seen = set()
        for entry, got in zip(mapping, answer['data']['_entities']):
            self.assertEqual(got['localRef'], entry['missionsReference'])
            self.assertEqual(got['resolution'], wanted[entry['resolution']], entry['missionsReference'])
            seen.add(got['resolution'])
            if got['resolution'] == 'RESOLVED':
                self.assertEqual(got['asset'], pick(by_id[entry['mapsTo']]))
                self.assertEqual(got['assetId'], entry['mapsTo'])
            else:
                self.assertIsNone(got['asset'])
        self.assertEqual(seen, {'RESOLVED', 'UNRESOLVED', 'UNMAPPED'}, 'the dataset covers the three outcomes the service can give')
        resolved_statuses = {got['asset']['status'] for got in answer['data']['_entities'] if got['asset']}
        self.assertTrue({'MISSING'} <= resolved_statuses, 'a MISSING asset resolves with its status')

    def test_05_a_missing_asset_is_null_and_a_malformed_id_is_bad_user_input(self):
        missing = support.graphql(STATE['port'], '{ asset(assetId: "AST-0097") { assetId } }')
        self.assertIsNone(missing['data']['asset'])
        self.assertNotIn('errors', missing)
        malformed = support.graphql(STATE['port'], '{ asset(assetId: "SH-17") { assetId } }')
        self.assertIsNone(malformed['data']['asset'])
        self.assertEqual(codes(malformed), ['BAD_USER_INPUT'])

    def test_09_with_the_service_stopped_references_are_unavailable_with_one_entry_per_failed_call(self):
        support.docker(['stop', '--time', '10', STATE['service']])
        mapping = [m for m in expected_mapping() if m['resolution'] != 'NO_MAPPING']
        references = [support.reference(m['missionsReference'], m['mapsTo']) for m in mapping[:3]] + [support.reference('EQ-108', None)]
        answer = support.graphql(STATE['port'], support.REFERENCES, {'r': references}, timeout=60)
        self.assertEqual([e['resolution'] for e in answer['data']['_entities']], ['UNAVAILABLE', 'UNAVAILABLE', 'UNAVAILABLE', 'UNMAPPED'])
        self.assertEqual([e['asset'] for e in answer['data']['_entities']], [None] * 4)
        self.assertEqual(codes(answer), ['SERVICE_UNAVAILABLE'] * 3)
        page = support.graphql(STATE['port'], '{ assets(limit: 100) { assetId } }')
        self.assertIsNone(page['data']['assets'])
        self.assertEqual(codes(page), ['SERVICE_UNAVAILABLE'])


if __name__ == '__main__':
    unittest.main()
