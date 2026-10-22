"""Assets adapter packaging acceptance, with no Assets service: the committed Dockerfile, Dockerfile.dockerignore, compose.yaml and
start.sh, through Docker and Docker Compose.

The image build is the offline test run: the Dockerfile's build stage runs `mvn verify`, so the unit and integration tests
(all four outcomes against a stub of the Assets service, the timeouts, the paging, the errors entries and the Federation entry
points) run inside Docker and no JDK is needed on the machine. This module checks what only the packaging owns: both bases pinned
by digest, a compose file with loopback publication, explicit limits and no secret, an image that holds only the jar and runs as
a non-root user, the start script's port rule on the real stack, and an adapter that answers GraphQL and reports an unreachable
service as UNAVAILABLE with one SERVICE_UNAVAILABLE entry per failed call.

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

STATE = {}
TIMINGS = {}


def project_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ASSETS_', 'COMPOSE_'))}
    env.update(COMPOSE_PROJECT_NAME=STATE['project'], ASSETS_ADAPTER_IMAGE=STATE['image'], ASSETS_ADAPTER_CONTAINER_NAME=STATE['container'],
               ASSETS_ADAPTER_HOST_PORT=str(STATE['port']), ASSETS_SERVICE_URL='http://127.0.0.1:9', ASSETS_READ_TIMEOUT_MS='1500')
    return env


def compose(args, timeout=900):
    return support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE)] + args, project_env(), timeout)


def start_script(command, dry_run=False, timeout=900):
    return support.run([support.bash(), str(support.START)] + (['--dry-run'] if dry_run else []) + [command], project_env(), timeout)


def setUpModule():
    token = secrets.token_hex(6)
    STATE.update(token=token, project='fed-assets-pkg-' + token, image='federation-assets-adapter-validation:' + token,
                 container='fed-assets-pkg-' + token, port=support.free_port(), started=time.monotonic())
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
    print('assets-adapter packaging timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    print('assets-adapter packaging: pinned ' + support.MAVEN_BASE + ' and ' + support.JRE_BASE + ' (resolved 2026-10-16)', flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


class PackagingAcceptance(unittest.TestCase):
    def test_01_committed_files_pin_both_bases_by_digest(self):
        dockerfile = (support.COMPONENT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'(?m)^FROM (\S+)', dockerfile), [support.MAVEN_BASE, support.JRE_BASE])
        self.assertRegex(dockerfile, r'(?m)^USER 10001:10001$')
        self.assertRegex(dockerfile, r'(?m)^EXPOSE 8184$')
        self.assertRegex(dockerfile, r'(?m)^ENV ADAPTER_BIND_HOST=0\.0\.0\.0 ADAPTER_PORT=8184$')
        self.assertIn('2026-10-16', dockerfile)
        self.assertIn('mvn -B -ntp -pl adapters/assets -am verify', dockerfile, 'the build stage runs the offline tests')
        ignore = (support.COMPONENT / 'Dockerfile.dockerignore').read_text(encoding='utf-8').split('\n')
        self.assertEqual(ignore[0], '*', 'the build context excludes everything but what it names')
        self.assertEqual(ignore[1:], ['!pom.xml', '!common/pom.xml', '!common/src', '!adapters/*/pom.xml', '!adapters/*/src', ''])

    def test_02_compose_publishes_on_loopback_with_limits_and_no_secret(self):
        result = compose(['config', '--format', 'json'])
        self.assertEqual(result.returncode, 0, result.stderr)
        service = json.loads(result.stdout)['services']['assets-adapter']
        self.assertEqual([(p['host_ip'], p['target']) for p in service['ports']], [('127.0.0.1', 8184)])
        self.assertEqual(service['mem_limit'], str(512 * 1024 * 1024))
        self.assertEqual(service['memswap_limit'], str(512 * 1024 * 1024))
        self.assertEqual(float(service['cpus']), 1.0)
        self.assertTrue(service['read_only'])
        self.assertEqual(service['cap_drop'], ['ALL'])
        text = support.COMPOSE_FILE.read_text(encoding='utf-8')
        code = ''.join(line + '\n' for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertNotRegex(code, r'(?i)password|secret|token|api[_-]?key')
        self.assertIn('${ASSETS_ADAPTER_HOST_PORT:-8184}', text)
        self.assertIn('${ASSETS_SERVICE_URL:-http://host.docker.internal:8084}', text)

    def test_03_the_image_builds_and_the_build_runs_the_tests(self):
        started = time.monotonic()
        result = compose(['build', '--no-cache', '--progress', 'plain'], timeout=1800)
        TIMINGS['build'] = round(time.monotonic() - started, 1)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        log = result.stdout + result.stderr
        self.assertRegex(log, r'Tests run: \d+, Failures: 0, Errors: 0, Skipped: 0')
        self.assertIn('BUILD SUCCESS', log)

    def test_04_the_image_holds_only_the_jar_and_runs_as_a_non_root_user(self):
        image = json.loads(support.docker(['inspect', STATE['image']]))[0]
        self.assertEqual(image['Config']['User'], '10001:10001')
        self.assertEqual(image['Config']['ExposedPorts'], {'8184/tcp': {}})
        listing = support.docker(['run', '--rm', '--entrypoint', 'ls', STATE['image'], '-A', '/app']).split()
        self.assertEqual(listing, ['adapter.jar'])
        self.assertEqual(support.docker(['run', '--rm', '--entrypoint', 'id', STATE['image'], '-u']).strip(), '10001')
        TIMINGS['image MB'] = round(image['Size'] / 1e6)

    def test_05_start_script_starts_the_adapter_and_it_answers_graphql(self):
        result = start_script('start')
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        support.wait_for_graphql(STATE['port'])
        sdl = support.graphql(STATE['port'], '{ _service { sdl } }')['data']['_service']['sdl']
        self.assertIn('https://specs.apollo.dev/federation/v2.0', sdl)
        for name in ('AssetReference', 'Asset', 'Resolution', 'UNMAPPED'):
            self.assertIn(name, sdl)
        container = json.loads(support.docker(['inspect', STATE['container']]))[0]
        self.assertEqual(container['HostConfig']['Memory'], 512 * 1024 * 1024)
        self.assertEqual(container['HostConfig']['NanoCpus'], 1_000_000_000)
        self.assertEqual(support.docker(['exec', STATE['container'], 'id', '-u']).strip(), '10001')

    def test_06_an_unreachable_service_is_unavailable_with_one_entry_per_failed_call_and_unmapped_needs_no_call(self):
        answer = support.graphql(STATE['port'], support.REFERENCES, {'r': [support.reference('SH-17', 'AST-0001'), support.reference('EQ-64', 'AST-0002'),
                                                                           support.reference('XX-99', None)]})
        entities = answer['data']['_entities']
        self.assertEqual([e['resolution'] for e in entities], ['UNAVAILABLE', 'UNAVAILABLE', 'UNMAPPED'])
        self.assertEqual([e['asset'] for e in entities], [None, None, None])
        self.assertEqual([e['extensions']['code'] for e in answer['errors']], ['SERVICE_UNAVAILABLE', 'SERVICE_UNAVAILABLE'])
        page = support.graphql(STATE['port'], '{ assets(limit: 75) { assetId } }')
        self.assertIsNone(page['data']['assets'])
        self.assertEqual([e['extensions']['code'] for e in page['errors']], ['SERVICE_UNAVAILABLE'])
        refused = support.graphql(STATE['port'], '{ assets(limit: 101) { assetId } }')
        self.assertEqual([e['extensions']['code'] for e in refused['errors']], ['BAD_USER_INPUT'])

    def test_07_a_second_start_is_refused_while_the_adapter_holds_the_port(self):
        result = start_script('start')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn('already in use', result.stderr)

    def test_08_stop_keeps_the_container_and_frees_the_port(self):
        result = start_script('stop')
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertIn('exited', support.docker(['inspect', '--format', '{{.State.Status}}', STATE['container']]))
        self.assertEqual(start_script('start', dry_run=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
