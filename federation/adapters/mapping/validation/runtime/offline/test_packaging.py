"""Mapping adapter packaging acceptance: the committed Dockerfile, Dockerfile.dockerignore, compose.yaml and start.sh, through Docker
and Docker Compose.

The image build is the offline test run: the Dockerfile's build stage runs `mvn verify`, so the unit and integration tests (the
entity through _entities, the release errors, the independence of releases, the hash of every release file) run inside Docker and no
JDK is needed on the machine. This module checks what only the packaging owns: both bases pinned by digest, a compose file with
loopback publication, explicit limits and no secret, an image that holds only the jar and the releases and runs as a non-root user,
the start script's port rule on the real stack, and an adapter that answers GraphQL with the real release 1.0 baked into the image.

Everything is disposable and uniquely named per run: one compose project, one image tag, one container name and an ephemeral
loopback port. Missing Docker or Compose is a failure, never a skip.
"""
from pathlib import Path
import json
import os
import re
import secrets
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402
import release_check as check  # noqa: E402

STATE = {}
TIMINGS = {}


def project_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MAPPING_', 'COMPOSE_'))}
    env.update(COMPOSE_PROJECT_NAME=STATE['project'], MAPPING_ADAPTER_IMAGE=STATE['image'], MAPPING_ADAPTER_CONTAINER_NAME=STATE['container'],
               MAPPING_ADAPTER_HOST_PORT=str(STATE['port']))
    return env


def compose(args, timeout=900):
    return support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE)] + args, project_env(), timeout)


def start_script(command, dry_run=False, timeout=900):
    return support.run([support.bash(), str(support.START)] + (['--dry-run'] if dry_run else []) + [command], project_env(), timeout)


def setUpModule():
    token = secrets.token_hex(6)
    STATE.update(token=token, project='fed-mapping-pkg-' + token, image='federation-mapping-adapter-validation:' + token,
                 container='fed-mapping-pkg-' + token, port=support.free_port(), started=time.monotonic())
    support.docker(['version', '--format', '{{.Server.Version}}'])


def tearDownModule():
    problems = []
    result = compose(['down', '--remove-orphans'], timeout=240)
    if result.returncode:
        problems.append('compose down: ' + result.stderr[-1500:])
    result = support.run(['docker', 'rmi', '--force', STATE['image']])
    if result.returncode and 'No such image' not in result.stderr:
        problems.append('image: ' + result.stderr[-500:])
    TIMINGS['module total'] = round(time.monotonic() - STATE['started'], 1)
    print('mapping-adapter packaging timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    print('mapping-adapter packaging: pinned ' + support.MAVEN_BASE + ' and ' + support.JRE_BASE + ' (resolved 2026-10-16)', flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


class PackagingAcceptance(unittest.TestCase):
    def test_01_committed_files_pin_both_bases_by_digest(self):
        dockerfile = (support.COMPONENT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'(?m)^FROM (\S+)', dockerfile), [support.MAVEN_BASE, support.JRE_BASE])
        self.assertRegex(dockerfile, r'(?m)^USER 10001:10001$')
        self.assertRegex(dockerfile, r'(?m)^EXPOSE 8190$')
        self.assertRegex(dockerfile, r'(?m)^ENV ADAPTER_BIND_HOST=0\.0\.0\.0 ADAPTER_PORT=8190 MAPPING_RELEASES_DIR=/app/mapping-releases$')
        self.assertIn('2026-10-16', dockerfile)
        self.assertIn('mvn -B -ntp -pl adapters/mapping -am verify', dockerfile, 'the build stage runs the offline tests')
        self.assertEqual(len(re.findall(r'(?m)^COPY mapping-releases \./mapping-releases$', dockerfile)), 2,
                         'the releases reach the build stage (the tests) and the image')
        ignore = (support.COMPONENT / 'Dockerfile.dockerignore').read_text(encoding='utf-8').split('\n')
        self.assertEqual(ignore[0], '*', 'the build context excludes everything but what it names')
        self.assertEqual(ignore[1:], ['!pom.xml', '!common/pom.xml', '!common/src', '!adapters/*/pom.xml',
                                      '!adapters/*/src', '!mapping-releases', ''])

    def test_02_compose_publishes_on_loopback_with_limits_and_no_secret(self):
        result = compose(['config', '--format', 'json'])
        self.assertEqual(result.returncode, 0, result.stderr)
        service = json.loads(result.stdout)['services']['mapping-adapter']
        self.assertEqual([(p['host_ip'], p['target']) for p in service['ports']], [('127.0.0.1', 8190)])
        self.assertEqual(service['mem_limit'], str(512 * 1024 * 1024))
        self.assertEqual(service['memswap_limit'], str(512 * 1024 * 1024))
        self.assertEqual(float(service['cpus']), 1.0)
        self.assertTrue(service['read_only'])
        self.assertEqual(service['cap_drop'], ['ALL'])
        text = support.COMPOSE_FILE.read_text(encoding='utf-8')
        code = ''.join(line + '\n' for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertNotRegex(code, r'(?i)password|secret|token|api[_-]?key')
        self.assertIn('${MAPPING_ADAPTER_HOST_PORT:-8190}', text)
        self.assertNotIn('SERVICE_URL', code, 'the mapping adapter makes no outbound call')

    def test_03_the_image_builds_and_the_build_runs_the_tests(self):
        started = time.monotonic()
        result = compose(['build', '--no-cache', '--progress', 'plain'], timeout=1800)
        TIMINGS['build'] = round(time.monotonic() - started, 1)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        log = result.stdout + result.stderr
        self.assertRegex(log, r'Tests run: \d+, Failures: 0, Errors: 0, Skipped: 0')
        self.assertIn('BUILD SUCCESS', log)

    def test_04_the_image_holds_only_the_jar_and_the_releases_and_runs_as_a_non_root_user(self):
        image = json.loads(support.docker(['inspect', STATE['image']]))[0]
        self.assertEqual(image['Config']['User'], '10001:10001')
        self.assertEqual(image['Config']['ExposedPorts'], {'8190/tcp': {}})
        listing = support.docker(['run', '--rm', '--entrypoint', 'ls', STATE['image'], '-A', '/app']).split()
        self.assertEqual(sorted(listing), ['adapter.jar', 'mapping-releases'])
        files = support.docker(['run', '--rm', '--entrypoint', 'find', STATE['image'], '/app/mapping-releases', '-type', 'f']).split()
        self.assertEqual(sorted(files), ['/app/mapping-releases/1.0/assets.json', '/app/mapping-releases/1.0/manifest.json',
                                         '/app/mapping-releases/1.1/assets.json', '/app/mapping-releases/1.1/crew.json',
                                         '/app/mapping-releases/1.1/manifest.json',
                                         '/app/mapping-releases/1.2/assets.json', '/app/mapping-releases/1.2/crew.json',
                                         '/app/mapping-releases/1.2/manifest.json', '/app/mapping-releases/1.2/participants.json',
                                         '/app/mapping-releases/1.3/assets.json', '/app/mapping-releases/1.3/crew.json',
                                         '/app/mapping-releases/1.3/manifest.json', '/app/mapping-releases/1.3/participants.json'])
        self.assertEqual(support.docker(['run', '--rm', '--entrypoint', 'id', STATE['image'], '-u']).strip(), '10001')
        TIMINGS['image MB'] = round(image['Size'] / 1e6)

    def test_05_the_baked_in_files_are_the_committed_release(self):
        for folder in check.release_folders(support.ROOT):
            for path in sorted(folder.iterdir()):
                inside = support.docker(['run', '--rm', '--entrypoint', 'cat', STATE['image'], '/app/mapping-releases/' + folder.name + '/' + path.name])
                expected = path.read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
                self.assertEqual(inside, expected, folder.name + '/' + path.name)

    def test_06_start_script_starts_the_adapter_and_it_answers_graphql(self):
        result = start_script('start')
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        support.wait_for_graphql(STATE['port'])
        sdl = support.graphql(STATE['port'], '{ _service { sdl } }')['data']['_service']['sdl']
        self.assertIn('https://specs.apollo.dev/federation/v2.0', sdl)
        for name in ('AssetReference', 'assetId', 'MappingRelease'):
            self.assertIn(name, sdl)
        container = json.loads(support.docker(['inspect', STATE['container']]))[0]
        self.assertEqual(container['HostConfig']['Memory'], 512 * 1024 * 1024)
        self.assertEqual(container['HostConfig']['NanoCpus'], 1_000_000_000)
        self.assertEqual(support.docker(['exec', STATE['container'], 'id', '-u']).strip(), '10001')

    def test_07_the_running_adapter_serves_releases_1_0_1_1_1_2_and_1_3_and_refuses_what_it_must(self):
        references = ['EQ-64', 'EQ-75', 'EQ-86', 'EQ-97', 'EQ-108', 'EQ-119', 'SH-42', 'SH-53', 'VS-31']
        answer = support.graphql(STATE['port'], support.ENTITIES, {'r': [support.reference(r) for r in references]})
        self.assertNotIn('errors', answer)
        self.assertEqual([e['assetId'] for e in answer['data']['_entities']],
                         ['AST-0004', 'AST-0005', 'AST-0006', 'AST-0097', None, 'AST-0007', 'AST-0024', 'AST-0025', 'AST-0029'])
        self.assertEqual([e['mappingOutcome'] for e in answer['data']['_entities']], ['MAPPED'] * 4 + ['NO_ENTRY'] + ['MAPPED'] * 4)
        blank = support.graphql(STATE['port'], support.ENTITIES, {'r': [support.reference('EQ-64', ''), support.reference('SH-42', '')]})
        self.assertEqual([e['extensions']['code'] for e in blank['errors']], ['MAPPING_RELEASE_REQUIRED'])
        self.assertEqual([e['mappingOutcome'] for e in blank['data']['_entities']], ['RELEASE_REFUSED', 'RELEASE_REFUSED'])
        unknown = support.graphql(STATE['port'], support.ENTITIES, {'r': [support.reference('EQ-64', '2.0')]})
        self.assertEqual([e['extensions']['code'] for e in unknown['errors']], ['MAPPING_RELEASE_NOT_FOUND'])
        self.assertEqual([e['mappingOutcome'] for e in unknown['data']['_entities']], ['RELEASE_REFUSED'])
        listed = support.graphql(STATE['port'], '{ mappingReleases { release sections checkedAgainst { system version } } }')
        self.assertEqual([(r['release'], r['sections']) for r in listed['data']['mappingReleases']],
                         [('1.0', ['assets']), ('1.1', ['assets', 'crew']), ('1.2', ['assets', 'crew', 'participants']),
                          ('1.3', ['assets', 'crew', 'participants'])])
        crew = ['C-71', 'C-78', 'C-85', 'C-92', 'C-99', 'C-106', 'C-113', 'C-120', 'C-127', 'C-134']
        answer = support.graphql(STATE['port'], support.CREW_ENTITIES, {'r': [support.crew_reference(r) for r in crew]})
        self.assertNotIn('errors', answer)
        self.assertEqual([e['personnelId'] for e in answer['data']['_entities']],
                         ['PRS-0001', 'PRS-1048', 'PRS-0002', 'PRS-1049', 'PRS-1058', 'PRS-1053', 'PRS-1054', 'PRS-0714', 'PRS-1057', 'PRS-1100'])
        older = support.graphql(STATE['port'], support.CREW_ENTITIES, {'r': [support.crew_reference('C-71', '1.0'), support.crew_reference('C-999')]})
        self.assertEqual([e['personnelId'] for e in older['data']['_entities']], [None, None])
        self.assertEqual([e['mappingOutcome'] for e in older['data']['_entities']], ['NO_ENTRY', 'NO_ENTRY'])
        # Release 1.2 answers the references of Missions dataset release 1.1: the cast of 1.1 unchanged, a generated crew reference
        # against the large snapshot, Wesley Crusher the crew member, and the three crew references that must stay unmapped.
        large = ['C-71', 'C-120', 'C-9329', 'C-2372', 'C-3423', 'C-9938']
        answer = support.graphql(STATE['port'], support.CREW_ENTITIES, {'r': [support.crew_reference(r, '1.2') for r in large]})
        self.assertNotIn('errors', answer)
        self.assertEqual([e['personnelId'] for e in answer['data']['_entities']], ['PRS-0001', 'PRS-0714', 'PRS-2707', None, None, None])
        self.assertEqual([e['mappingOutcome'] for e in answer['data']['_entities']], ['MAPPED'] * 3 + ['NO_ENTRY'] * 3)
        # Release 1.3 answers the same crew references as 1.2 (its crew section is 1.2's, byte for byte).
        again = support.graphql(STATE['port'], support.CREW_ENTITIES, {'r': [support.crew_reference(r, '1.3') for r in large]})
        self.assertNotIn('errors', again)
        self.assertEqual([(e['personnelId'], e['mappingOutcome']) for e in again['data']['_entities']],
                         [(e['personnelId'], e['mappingOutcome']) for e in answer['data']['_entities']])

    def test_07b_the_running_adapter_answers_the_plain_lookups_for_a_mapped_an_unmapped_and_a_refused_reference(self):
        assets = support.graphql(STATE['port'], '{ assetReferences(release: "1.3", localRefs: ["EQ-64", "EQ-108"]) { assetId mappingOutcome } }')
        self.assertNotIn('errors', assets)
        self.assertEqual([(e['assetId'], e['mappingOutcome']) for e in assets['data']['assetReferences']], [('AST-0004', 'MAPPED'), (None, 'NO_ENTRY')])
        crew = support.graphql(STATE['port'], '{ personnelReferences(release: "1.3", localRefs: ["C-120", "C-2372", "O-860"]) { personnelId mappingOutcome } }')
        self.assertEqual([(e['personnelId'], e['mappingOutcome']) for e in crew['data']['personnelReferences']],
                         [('PRS-0714', 'MAPPED'), (None, 'NO_ENTRY'), (None, 'NO_ENTRY')])
        self.assertEqual([e['extensions']['code'] for e in crew['errors']], ['MAPPING_CLASS_REFUSED'])
        unknown = support.graphql(STATE['port'], '{ assetReferences(release: "latest", localRefs: ["EQ-64"]) { mappingOutcome } }')
        self.assertEqual([e['extensions']['code'] for e in unknown['errors']], ['MAPPING_RELEASE_NOT_FOUND'])
        sdl = support.graphql(STATE['port'], '{ _service { sdl } }')['data']['_service']['sdl']
        self.assertRegex(sdl, r'assetReferences\([^)]*\): \[AssetReference!\] @inaccessible')
        self.assertRegex(sdl, r'personnelReferences\([^)]*\): \[PersonnelReference!\] @inaccessible')

    def test_08_a_second_start_is_refused_while_the_adapter_holds_the_port(self):
        result = start_script('start')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn('already in use', result.stderr)

    def test_09_stop_keeps_the_container_and_frees_the_port(self):
        result = start_script('stop')
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertIn('exited', support.docker(['inspect', '--format', '{{.State.Status}}', STATE['container']]))
        self.assertEqual(start_script('start', dry_run=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
