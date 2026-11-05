"""Offline tests of the study launch kit: argument handling, the commands each scenario and mode would run, the real-mode refusals and
the generated config. A fake machine stands in for Docker; nothing is started, stopped or inspected, and no network is used."""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import launch  # noqa: E402
import make_config  # noqa: E402
import provenance  # noqa: E402  (study/harness, put on the path by make_config)
import runner  # noqa: E402  (study/harness: the harness reads what these commands print)

sys.path.insert(0, str(HERE.parent / 'preflight'))
import preflight  # noqa: E402

ROOT = launch.ROOT
COMMITTED = sorted(p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py', '.md', '.yaml'))
WSL_BASH = 'C' + ':' + '\\'.join(('', 'Windows', 'System32', 'bash.exe'))  # built from pieces, so the path scan below needs no exception
# A credential-named variable in upper case (environment or compose) given a value that is neither a reference nor the placeholder, or a
# credential-named Python name given a quoted literal. Prose such as "the passwords: the operator's" is neither. The tested values
# below are split so this file does not match itself.
CREDENTIAL = re.compile(r'[A-Z_]*(PASSWORD|SECRET|TOKEN)[A-Z_]*[ \t]*[=:][ \t]*[\'"]?(?!\$|unused\b|\[)[A-Za-z0-9]'
                        r'|\b\w*(password|secret|token)\w*[ \t]*=[ \t]*[\'"](?!unused\b|operator-)[A-Za-z0-9]')


# The image ids the fake Docker answers: one distinct id per pinned image.
IMAGE_IDS = {ref: 'sha256:%064x' % (index + 1) for index, ref in enumerate(launch.PINNED_IMAGES)}


class FakeMachine:
    """Answers the read-only probes from a table and records every command instead of running it. `images` maps an image name to the id
    `docker image inspect` gives (a name that is absent does not exist); `log` holds the reads and calls in their order."""

    def __init__(self, compose='2.29.1', container='true', network=True, missions_status=200, taken=(), fail=None, images=None):
        self.compose, self.container, self.network = compose, container, network
        self.missions_status, self.taken, self.fail = missions_status, set(taken), fail
        self.images = dict(IMAGE_IDS if images is None else images)
        self.reads, self.calls, self.sleeps, self.log = [], [], 0, []

    def read(self, argv):
        self.reads.append(argv)
        self.log.append(('read', argv))
        if argv[:3] == ['docker', 'image', 'inspect']:
            assert argv[3:5] == ['--format', '{{.Id}}'], argv
            return (0, self.images[argv[-1]]) if argv[-1] in self.images else (1, '')
        if argv[:3] == ['docker', 'compose', 'version']:
            return (0, self.compose) if self.compose else (1, '')
        if argv[:2] == ['docker', 'inspect']:
            return (0, self.container) if self.container is not None else (1, '')
        if argv[:3] == ['docker', 'network', 'inspect']:
            return (0, launch.MISSIONS_NETWORK) if self.network else (1, '')
        raise AssertionError(argv)

    def call(self, argv, env):
        self.calls.append((argv, env))
        self.log.append(('call', argv))
        return 1 if self.fail and self.fail in argv else 0

    def http_status(self, url):
        return self.missions_status

    def port_taken(self, port):
        return port in self.taken

    def sleep(self, seconds):
        self.sleeps += 1


def run(argv, machine=None, environ=None):
    machine = machine or FakeMachine()
    environ = dict({'STUDY_BASH': 'bash', 'APOLLO_ELV2_LICENSE': 'accept'}, **(environ or {}))
    lines, err = [], io.StringIO()
    with redirect_stderr(err):
        code = launch.main(argv, machine=machine, environ=environ, out=lines.append)
    return code, machine, lines, err.getvalue()


class StateDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = str(Path(self.tmp.name) / 'state')

    def tearDown(self):
        self.tmp.cleanup()


class ArgumentTests(StateDir):
    def test_unknown_scenario_mode_or_service_is_a_usage_error(self):
        for argv in (['up', 'zeta', '--missions', 'real'], ['up', 'alpha', '--missions', 'stub'], ['up', 'alpha'],
                     ['service', 'stop', 'router', 'alpha', '--missions', 'real'], ['service', 'pause', 'assets', 'alpha', '--missions', 'real']):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                launch.main(argv + ['--state-dir', self.state], machine=FakeMachine(), environ={})
            self.assertEqual(raised.exception.code, 2)

    def test_state_dir_is_required_and_must_be_outside_the_repository(self):
        code, machine, _, err = run(['up', 'gamma', '--missions', 'simulated'])
        self.assertEqual(code, 1)
        self.assertIn('STUDY_LAUNCH_STATE_DIR', err)
        code, machine, _, err = run(['up', 'gamma', '--missions', 'simulated', '--state-dir', str(ROOT / 'tmp-state')])
        self.assertEqual(code, 1)
        self.assertIn('outside the repository', err)
        self.assertEqual(machine.calls, [])

    def test_state_dir_from_the_environment(self):
        code, machine, _, _ = run(['up', 'gamma', '--missions', 'simulated'], environ={'STUDY_LAUNCH_STATE_DIR': self.state})
        self.assertEqual(code, 0)
        self.assertTrue((Path(self.state) / 'supergraph.graphql').is_file())

    def test_dry_run_runs_nothing_and_creates_no_state(self):
        code, machine, lines, _ = run(['up', 'alpha', '--missions', 'real', '--state-dir', self.state, '--dry-run'])
        self.assertEqual(code, 0)
        self.assertEqual(machine.calls, [])
        self.assertEqual(machine.reads, [])
        self.assertFalse(Path(self.state).exists())
        self.assertTrue(any(line.startswith('would run: docker compose') for line in lines))

    def test_wsl_bash_is_refused_on_windows(self):
        if os.name != 'nt':
            self.skipTest('Windows only')
        code, machine, _, err = run(['up', 'gamma', '--missions', 'simulated', '--state-dir', self.state],
                                    environ={'STUDY_BASH': WSL_BASH})
        self.assertEqual(code, 1)
        self.assertIn('WSL', err)
        self.assertEqual(machine.calls, [])


class SimulatedModeTests(StateDir):
    def test_up_runs_start_sh_and_publishes_the_legacy_ports_for_alpha_and_beta(self):
        for scenario in launch.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, machine, _, _ = run(['up', scenario, '--missions', 'simulated', '--state-dir', self.state])
                self.assertEqual(code, 0)
                first, env = machine.calls[0]
                self.assertEqual(first, ['bash', str(launch.START_SH), 'start'])
                self.assertEqual(env['FEDERATION_ROUTER'], 'cosmo' if scenario == 'epsilon' else 'apollo')
                self.assertEqual(env['SUPERGRAPH_FILE'], str(Path(self.state).resolve() / 'supergraph.graphql'))
                if scenario in ('alpha', 'beta'):
                    self.assertEqual(len(machine.calls), 2)
                    argv = machine.calls[1][0]
                    self.assertIn(str(launch.LEGACY_PORTS), argv)
                    self.assertEqual(argv[-3:], ['personnel-service', 'missions-stub', 'assets-service'])
                else:
                    self.assertEqual(len(machine.calls), 1)

    def test_down_runs_start_sh_stop(self):
        code, machine, _, _ = run(['down', 'epsilon', '--missions', 'simulated', '--state-dir', self.state])
        self.assertEqual(code, 0)
        argv, env = machine.calls[0]
        self.assertEqual(argv[1:], [str(launch.START_SH), 'stop'])
        self.assertEqual(env['FEDERATION_ROUTER'], 'cosmo')

    def test_missions_outage_stops_and_starts_the_stub(self):
        code, machine, _, _ = run(['service', 'stop', 'missions', 'gamma', '--missions', 'simulated', '--state-dir', self.state])
        self.assertEqual(machine.calls[0][0][-2:], ['stop', 'missions-stub'])
        code, machine, _, _ = run(['service', 'start', 'missions', 'alpha', '--missions', 'simulated', '--state-dir', self.state])
        argv = machine.calls[0][0]
        self.assertIn(str(launch.LEGACY_PORTS), argv)
        self.assertEqual(argv[-6:], ['up', '-d', '--no-deps', '--no-recreate', '--wait', 'missions-stub'])


REMOVAL = [str(part) for part in launch.remove_stack('real')]  # as the plan runs it


class RealModeTests(StateDir):
    def test_up_never_starts_missions_stub_and_adds_the_overlay_to_every_compose_call(self):
        for scenario in launch.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, machine, _, err = run(['up', scenario, '--missions', 'real', '--state-dir', self.state])
                self.assertEqual(code, 0, err)
                compose_calls = [argv for argv, _ in machine.calls if argv[:2] == ['docker', 'compose']]
                self.assertTrue(compose_calls)
                for argv in machine.calls:
                    self.assertNotIn('missions-stub', argv[0])
                    self.assertNotIn(str(launch.START_SH), argv[0])
                for argv in compose_calls:
                    self.assertEqual(argv[argv.index(str(launch.REAL_OVERLAY)) - 1], '-f')
                    self.assertNotIn(str(ROOT / 'uss-enterprise' / 'missions' / 'compose.yaml'), argv)
                self.assertEqual(compose_calls[0], REMOVAL)
                self.assertEqual(compose_calls[1][-len(launch.REAL_BACKENDS):], list(launch.REAL_BACKENDS))
                router = 'cosmo-router' if scenario == 'epsilon' else 'router'
                self.assertTrue(any(argv[-1] == router for argv in compose_calls))
                if scenario in ('alpha', 'beta'):
                    self.assertEqual(compose_calls[-1][-2:], ['personnel-service', 'assets-service'])
                    self.assertIn(str(launch.LEGACY_PORTS), compose_calls[-1])

    def test_composition_writes_into_the_state_folder(self):
        code, machine, _, _ = run(['up', 'epsilon', '--missions', 'real', '--state-dir', self.state])
        composed = [argv for argv, _ in machine.calls if str(launch.COMPOSE_EXECUTION_CONFIG) in argv]
        self.assertEqual(composed[0][-2:], ['--out', str(Path(self.state).resolve() / 'execution-config.json')])
        code, machine, _, _ = run(['up', 'delta', '--missions', 'real', '--state-dir', self.state])
        composed = [argv for argv, _ in machine.calls if str(launch.COMPOSE_SUPERGRAPH) in argv]
        self.assertEqual(composed[0][-2:], ['--out', str(Path(self.state).resolve() / 'supergraph.graphql')])

    def test_up_refuses_without_the_operator_started_service(self):
        cases = [(FakeMachine(container=None), 'does not exist'), (FakeMachine(container='false'), 'not running'),
                 (FakeMachine(network=False), 'network'), (FakeMachine(missions_status=None), 'does not answer'),
                 (FakeMachine(missions_status=503), 'does not answer'), (FakeMachine(compose='2.23.0'), '2.24.4'),
                 (FakeMachine(compose=None), '2.24.4'), (FakeMachine(taken={8183}), '127.0.0.1:8183')]
        for machine, words in cases:
            with self.subTest(words=words):
                code, machine, _, err = run(['up', 'gamma', '--missions', 'real', '--state-dir', self.state], machine=machine)
                self.assertEqual(code, 1)
                self.assertIn(words, err)
                self.assertEqual(machine.calls, [])

    def test_apollo_needs_the_elv2_acceptance_and_cosmo_does_not(self):
        code, machine, _, err = run(['up', 'delta', '--missions', 'real', '--state-dir', self.state], environ={'APOLLO_ELV2_LICENSE': ''})
        self.assertEqual(code, 1)
        self.assertIn('Elastic License', err)
        code, machine, _, err = run(['up', 'epsilon', '--missions', 'real', '--state-dir', self.state], environ={'APOLLO_ELV2_LICENSE': ''})
        self.assertEqual(code, 0, err)

    def test_down_removes_the_federation_stack_s_containers_only(self):
        for scenario in launch.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, machine, _, err = run(['down', scenario, '--missions', 'real', '--state-dir', self.state])
                self.assertEqual(code, 0, err)
                self.assertEqual(len(machine.calls), 1)
                argv = machine.calls[0][0]
                self.assertEqual(argv, REMOVAL)
                self.assertEqual(argv[-6:], ['--profile', '*', 'down', '--remove-orphans', '--timeout', '60'])
                self.assertEqual(argv[argv.index('--profile') + 1], '*', 'every profile, so the Cosmo router goes too')
                self.assertEqual(argv[argv.index(str(launch.REAL_OVERLAY)) - 1], '-f')
                self.assertEqual(argv[2:4], ['--project-name', launch.STACK_PROJECT])
                for kept in ('-v', '--volumes', '--rmi', '-p', launch.MISSIONS_CONTAINER, launch.MISSIONS_PROJECT):
                    self.assertNotIn(kept, argv)
                self.assertEqual(argv.count('--project-name'), 1)
                self.assertNotIn(str(ROOT / 'uss-enterprise' / 'missions' / 'compose.yaml'), argv)

    def test_an_inherited_compose_project_name_never_redirects_a_real_mode_compose_call(self):
        stray = {'COMPOSE_PROJECT_NAME': launch.MISSIONS_PROJECT}
        for command in (['build'], ['up', 'alpha'], ['up', 'delta'], ['up', 'epsilon'], ['down', 'epsilon'],
                        ['service', 'stop', 'assets', 'beta'], ['service', 'start', 'personnel', 'gamma']):
            with self.subTest(command=command):
                code, machine, _, err = run(command + ['--missions', 'real', '--state-dir', self.state], environ=stray)
                self.assertEqual(code, 0, err)
                composes = [argv for argv, _ in machine.calls if argv[:2] == ['docker', 'compose']]
                self.assertTrue(composes)
                for argv in composes:
                    self.assertEqual(argv[2:4], ['--project-name', launch.STACK_PROJECT], argv)
                    self.assertNotIn(launch.MISSIONS_PROJECT, argv)

    def test_a_real_mode_up_starts_from_an_empty_stack_project(self):
        for scenario in launch.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, machine, _, err = run(['up', scenario, '--missions', 'real', '--state-dir', self.state])
                self.assertEqual(code, 0, err)
                calls = [argv for argv, _ in machine.calls]
                self.assertEqual(calls[0], REMOVAL, 'the removal comes before every start')
                self.assertEqual([argv for argv in calls if 'down' in argv], [calls[0]])
                self.assertIn('up', calls[1])
        code, machine, _, _ = run(['up', 'gamma', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(container=None))
        self.assertEqual(machine.calls, [], 'a refused start removes nothing')
        for command in (['up', 'alpha'], ['down', 'alpha']):
            code, machine, _, _ = run(command + ['--missions', 'simulated', '--state-dir', self.state])
            self.assertFalse([argv for argv, _ in machine.calls if 'down' in argv], 'the simulated mode is unchanged')

    def test_missions_outage_stops_and_starts_the_operator_container_by_name(self):
        code, machine, _, _ = run(['service', 'stop', 'missions', 'delta', '--missions', 'real', '--state-dir', self.state])
        self.assertEqual([argv for argv, _ in machine.calls], [['docker', 'stop', launch.MISSIONS_CONTAINER]])
        code, machine, _, _ = run(['service', 'start', 'missions', 'delta', '--missions', 'real', '--state-dir', self.state])
        self.assertEqual([argv for argv, _ in machine.calls], [['docker', 'start', launch.MISSIONS_CONTAINER]])
        code, machine, _, err = run(['service', 'start', 'missions', 'delta', '--missions', 'real', '--state-dir', self.state],
                                    machine=FakeMachine(container=None))
        self.assertEqual(code, 1)
        self.assertEqual(machine.calls, [])

    def test_backend_outage_keeps_the_overlay_and_never_recreates(self):
        code, machine, _, _ = run(['service', 'start', 'assets', 'beta', '--missions', 'real', '--state-dir', self.state])
        argv = machine.calls[0][0]
        self.assertIn(str(launch.REAL_OVERLAY), argv)
        self.assertIn(str(launch.LEGACY_PORTS), argv)
        self.assertEqual(argv[-7:], ['up', '-d', '--no-build', '--no-deps', '--no-recreate', '--wait', 'assets-service'])

    def test_every_real_mode_up_passes_no_build_and_the_backends_are_made_again(self):
        for scenario in launch.SCENARIOS:
            with self.subTest(scenario=scenario):
                code, machine, _, err = run(['up', scenario, '--missions', 'real', '--state-dir', self.state])
                self.assertEqual(code, 0, err)
                ups = [argv for argv, _ in machine.calls if argv[:2] == ['docker', 'compose'] and 'up' in argv]
                self.assertEqual(len(ups), 3 if scenario in launch.LEGACY_SCENARIOS else 2)
                for argv in ups:
                    self.assertIn('--no-build', argv)
                    self.assertNotIn('--build', argv)
                self.assertEqual(ups[0][ups[0].index('up'):ups[0].index('up') + 6], ['up', '-d', '--no-build', '--force-recreate', '--wait',
                                                                                      '--wait-timeout'])
                self.assertEqual([argv for argv in ups if '--force-recreate' in argv], [ups[0]], 'only the backends are made again')
        for service in ('assets', 'personnel'):
            code, machine, _, _ = run(['service', 'start', service, 'gamma', '--missions', 'real', '--state-dir', self.state])
            self.assertIn('--no-build', machine.calls[0][0])
        code, machine, _, _ = run(['up', 'alpha', '--missions', 'simulated', '--state-dir', self.state])
        self.assertNotIn('--no-build', machine.calls[1][0], 'the simulated mode is unchanged: start.sh still builds')

    def test_up_refuses_when_a_built_image_is_missing_and_names_the_build_command(self):
        for ref in launch.BUILT_IMAGES:
            with self.subTest(ref=ref):
                images = {name: value for name, value in IMAGE_IDS.items() if name != ref}
                code, machine, _, err = run(['up', 'delta', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(images=images))
                self.assertEqual(code, 1)
                self.assertIn('the image %s is missing' % ref, err)
                self.assertIn('python -B study/launch/launch.py build --missions real --state-dir %s' % Path(self.state).resolve(), err)
                self.assertEqual(machine.calls, [])
        images = {name: value for name, value in IMAGE_IDS.items() if name != launch.MISSIONS_IMAGE}
        self.assertEqual(run(['up', 'delta', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(images=images))[0], 0,
                         'a start checks the six built images; the running Missions service is checked by its own probes')

    def test_a_failing_command_stops_the_plan(self):
        code, machine, _, err = run(['up', 'delta', '--missions', 'real', '--state-dir', self.state],
                                    machine=FakeMachine(fail=str(launch.COMPOSE_SUPERGRAPH)))
        self.assertEqual(code, 1)
        self.assertIn('exit code 1', err)
        self.assertEqual(len(machine.calls), 3)


class BuildTests(StateDir):
    def pins(self):
        return json.loads((Path(self.state) / launch.PIN_FILE).read_text(encoding='utf-8'))

    def test_build_builds_the_six_images_once_then_writes_the_pin_set(self):
        code, machine, lines, err = run(['build', '--missions', 'real', '--state-dir', self.state])
        self.assertEqual(code, 0, err)
        self.assertEqual(len(machine.calls), 1)
        argv, env = machine.calls[0]
        self.assertEqual(argv[:2], ['docker', 'compose'])
        self.assertEqual(argv[argv.index(str(launch.REAL_OVERLAY)) - 1], '-f')
        self.assertEqual(argv[argv.index('build'):], ['build', 'assets-service', 'personnel-service', 'missions-adapter', 'personnel-adapter',
                                                      'assets-adapter', 'mapping-adapter'])
        self.assertEqual({env[name] for name in launch.ASSETS_PASSWORDS}, {'unused'})
        pins = self.pins()
        self.assertEqual(pins['images'], IMAGE_IDS)
        self.assertEqual(pins['schema'], 1)
        built = [i for i, (kind, argv) in enumerate(machine.log) if kind == 'call']
        pinned = [i for i, (kind, argv) in enumerate(machine.log) if kind == 'read' and argv[:3] == ['docker', 'image', 'inspect']
                  and argv[-1] in launch.BUILT_IMAGES]
        self.assertTrue(pinned and min(pinned) > built[0], 'the built images are read after the build')
        self.assertTrue(any(line.endswith(launch.PIN_FILE) for line in lines))

    def test_a_failed_build_writes_no_pin_set(self):
        code, machine, _, err = run(['build', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(fail='build'))
        self.assertEqual(code, 1)
        self.assertIn('exit code 1', err)
        self.assertFalse((Path(self.state) / launch.PIN_FILE).exists())

    def test_an_image_that_cannot_be_read_after_the_build_writes_no_pin_set(self):
        images = {name: value for name, value in IMAGE_IDS.items() if name != 'starfleet-federation-stack-mapping-adapter:1.0.0'}
        code, machine, _, err = run(['build', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(images=images))
        self.assertEqual(code, 1)
        self.assertIn('no pin set was written', err)
        self.assertFalse((Path(self.state) / launch.PIN_FILE).exists())
        self.assertFalse((Path(self.state) / (launch.PIN_FILE + '.tmp')).exists())

    def test_build_refuses_without_the_operators_missions_image_and_never_builds_it(self):
        images = {name: value for name, value in IMAGE_IDS.items() if name != launch.MISSIONS_IMAGE}
        code, machine, _, err = run(['build', '--missions', 'real', '--state-dir', self.state], machine=FakeMachine(images=images))
        self.assertEqual(code, 1)
        self.assertIn(launch.MISSIONS_IMAGE, err)
        self.assertEqual(machine.calls, [])
        code, machine, _, _ = run(['build', '--missions', 'real', '--state-dir', self.state])
        self.assertNotIn('missions', [word for argv, _ in machine.calls for word in argv[argv.index('build'):] if word.startswith('missions')
                                      and word != 'missions-adapter'])

    def test_build_is_for_the_real_mode_only(self):
        code, machine, _, err = run(['build', '--missions', 'simulated', '--state-dir', self.state])
        self.assertEqual(code, 1)
        self.assertIn('real mode', err)
        self.assertEqual(machine.calls, [])

    def test_a_dry_run_builds_and_writes_nothing(self):
        code, machine, lines, _ = run(['build', '--missions', 'real', '--state-dir', self.state, '--dry-run'])
        self.assertEqual(code, 0)
        self.assertEqual((machine.calls, machine.reads), ([], []))
        self.assertFalse(Path(self.state).exists())
        self.assertTrue(any(line.startswith('would run: docker compose') and ' build ' in line for line in lines))
        self.assertIn('would write: %s' % (Path(self.state).resolve() / launch.PIN_FILE), lines)


class RoutingTests(StateDir):
    def test_inherited_backend_urls_never_reach_the_stack(self):
        stray = {variable: 'http://elsewhere:9' for variable, _ in launch.ADAPTER_BACKEND_URLS.values()}
        for mode in launch.MODES:
            for argv in (['up', 'alpha'], ['down', 'alpha'], ['service', 'start', 'assets', 'alpha']):
                with self.subTest(mode=mode, argv=argv):
                    code, machine, _, err = run(argv + ['--missions', mode, '--state-dir', self.state], environ=stray)
                    self.assertEqual(code, 0, err)
                    self.assertTrue(machine.calls)
                    for _, env in machine.calls:
                        self.assertEqual({name: env[name] for name in stray}, launch.adapter_backend_env(mode))


class CredentialTests(StateDir):
    def test_assets_passwords_are_random_per_up_unless_set(self):
        _, first, _, _ = run(['up', 'alpha', '--missions', 'simulated', '--state-dir', self.state])
        _, second, _, _ = run(['up', 'alpha', '--missions', 'simulated', '--state-dir', self.state])
        a = {name: first.calls[0][1][name] for name in launch.ASSETS_PASSWORDS}
        b = {name: second.calls[0][1][name] for name in launch.ASSETS_PASSWORDS}
        self.assertNotEqual(a, b)
        self.assertNotEqual(*a.values())
        for value in a.values():
            self.assertRegex(value, r'^[0-9a-f]{32}$')
        self.assertEqual({first.calls[1][1][name] for name in launch.ASSETS_PASSWORDS}, set(a.values()))
        _, given, _, _ = run(['up', 'alpha', '--missions', 'simulated', '--state-dir', self.state],
                             environ={name: 'operator-value' for name in launch.ASSETS_PASSWORDS})
        self.assertEqual({given.calls[0][1][name] for name in launch.ASSETS_PASSWORDS}, {'operator-value'})

    def test_no_password_reaches_an_argument_or_the_output(self):
        secret = 'operator-secret-value'
        code, machine, lines, err = run(['up', 'alpha', '--missions', 'real', '--state-dir', self.state],
                                        environ={name: secret for name in launch.ASSETS_PASSWORDS})
        for argv, _ in machine.calls:
            self.assertNotIn(secret, ' '.join(argv))
        code, machine, lines, err = run(['up', 'alpha', '--missions', 'real', '--state-dir', self.state, '--dry-run'],
                                        environ={name: secret for name in launch.ASSETS_PASSWORDS})
        self.assertNotIn(secret, '\n'.join(lines) + err)


class PinTests(unittest.TestCase):
    """The kit's copies of facts owned elsewhere, compared with their owners as text."""

    def test_real_backends_are_start_sh_backends_without_the_stub(self):
        text = launch.START_SH.read_text(encoding='utf-8')
        backends = re.search(r'^BACKENDS="([^"]+)"', text, re.M).group(1).split()
        self.assertEqual(tuple(backends), launch.STACK_BACKENDS)
        self.assertNotIn('missions-stub', launch.REAL_BACKENDS)

    def test_missions_constants_match_the_missions_compose_file(self):
        text = (ROOT / 'uss-enterprise' / 'missions' / 'compose.yaml').read_text(encoding='utf-8')
        self.assertIn('name: %s\n' % launch.MISSIONS_PROJECT, text)
        self.assertIn('${MISSIONS_CONTAINER_NAME:-%s}' % launch.MISSIONS_CONTAINER, text)
        self.assertIn('"127.0.0.1:${MISSIONS_HOST_PORT:-%d}:8083"' % launch.MISSIONS_HOST_PORT, text)
        self.assertIn('${MISSIONS_IMAGE:-%s}' % make_config.IMAGES['missions-real'], text)
        self.assertRegex(text, r'networks:\n\s+- default\n\s+- oracle')

    def test_overlay_names_the_service_network_and_url_and_publishes_nothing(self):
        text = launch.REAL_OVERLAY.read_text(encoding='utf-8')
        body = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertIn('name: %s' % launch.MISSIONS_NETWORK, body)
        self.assertIn('MISSIONS_SERVICE_URL: %s' % launch.MISSIONS_ADAPTER_URL['real'], body)
        self.assertIn('depends_on: !reset {}', body)
        self.assertIn('external: true', body)
        self.assertNotIn('ports', body)
        self.assertNotIn('starfleet-missions-data', body)
        self.assertEqual(re.findall(r'^  (\S+):$', body.split('networks:\n  ')[0], re.M), ['missions-adapter'])

    def test_stack_images_match_the_stack_compose_file(self):
        text = launch.STACK_COMPOSE.read_text(encoding='utf-8')
        self.assertIn('image: %s\n' % make_config.IMAGES['missions-stub'], text)
        self.assertIn('${STACK_ASSETS_SERVICE_IMAGE:-%s}' % make_config.IMAGES['assets-service'], text)
        self.assertIn('${STACK_PERSONNEL_SERVICE_IMAGE:-%s}' % make_config.IMAGES['personnel-service'], text)
        for variable, urls in launch.ADAPTER_BACKEND_URLS.values():
            self.assertIn('%s: ${%s:-%s}' % (variable, variable, urls['simulated']), text)
        self.assertEqual(sorted(re.findall(r'^\s+(\w+_SERVICE_URL): ', text, re.M)),
                         sorted(variable for variable, _ in launch.ADAPTER_BACKEND_URLS.values()))

    def test_the_built_images_are_the_images_the_stack_compose_file_builds(self):
        text = launch.STACK_COMPOSE.read_text(encoding='utf-8')
        anchor = re.search(r'^x-assets-image: &assets-image\n((?:  .*\n)+)', text, re.M).group(1)
        services = dict(re.findall(r'^  ([a-z-]+):\n((?:    .*\n|\n)*)', text.split('\nservices:\n', 1)[1], re.M))
        built, one_shot = {}, []
        for name, body in services.items():
            if '<<: *assets-image' in body:
                body = anchor + body
            if re.search(r'^\s+build:', body, re.M):
                image = re.search(r'image: \$\{\w+:-([^}]+)\}', body).group(1)
                built.setdefault(image, []).append(name)
            if 'restart: "no"' in body:
                one_shot.append(name)
        self.assertEqual({image: sorted(names) for image, names in built.items()},
                         {image: sorted(names) for image, names in launch.BUILT_IMAGES.items()})
        self.assertEqual(tuple(one_shot), launch.ONE_SHOT_SERVICES)
        for name, body in services.items():
            if not any(name in names for names in launch.BUILT_IMAGES.values()):
                self.assertRegex(body, r'image: \S+@sha256:[0-9a-f]{64}\n', '%s is pinned by digest' % name)

    def test_committed_files_hold_no_machine_path_or_credential(self):
        # Built from pieces, so that this file does not match its own patterns.
        drive = re.compile(r'(?<![A-Za-z])[A-Za-z]:[\\/]|' + '|'.join(re.escape(x) for x in ('/' + 'c/', 'Us' + 'ers', '/ho' + 'me/')))
        for path in COMMITTED:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                self.assertIsNone(drive.search(text))
                self.assertIsNone(CREDENTIAL.search(text))

    def test_the_credential_scan_finds_assignments_and_not_prose(self):
        for leak in ('STACK_ASSETS_DB_ADMIN_PASS' + 'WORD=abc', 'MISSIONS_DB_PASS' + 'WORD: "abc"', 'db_pass' + "word = 'abc'"):
            self.assertTrue(CREDENTIAL.search(leak), leak)
        for fine in ('PASS' + 'WORD: ${X}', 'the pass' + "words: the operator's", 'PASS' + 'WORD=unused', 'pass' + "words = {}"):
            self.assertIsNone(CREDENTIAL.search(fine), fine)


class ReadingMachine:
    """The read-only probes of `fingerprint` and `health`: docker ps and docker inspect from a table of containers, the dataset hash, the
    Missions GET and the Oracle SELECTs. Anything that would change something fails the test."""

    def __init__(self, containers=None, missions_status=200, rows=None, digest='d' * 64):
        self.containers = {'missions-stub': {'running': True, 'status': 'running', 'health': 'healthy', 'startedAt': '2026-11-02T08:00:00Z'},
                           'assets-service': {'running': True, 'status': 'running', 'health': 'healthy', 'startedAt': 't'},
                           'personnel-service': {'running': True, 'status': 'running', 'health': 'healthy', 'startedAt': 't'},
                           launch.MISSIONS_CONTAINER: {'running': True, 'status': 'running', 'health': None, 'startedAt': 't'}}
        if containers:
            self.containers.update(containers)
        self.missions_status, self.digest, self.reads, self.selects = missions_status, digest, [], []
        self.rows = rows if rows is not None else {}

    def read(self, argv):
        self.reads.append(argv)
        if argv[:2] == ['docker', 'ps']:
            service = argv[-1].rsplit('=', 1)[1]
            return 0, ('id-' + service) if self.containers.get(service) else ''
        if argv[:3] == ['docker', 'inspect', '--format']:
            name = argv[-1][3:] if argv[-1].startswith('id-') else argv[-1]
            state = self.containers.get(name)
            return (0, json.dumps(state)) if state else (1, '')
        raise AssertionError(argv)

    def call(self, argv, env):
        raise AssertionError('a read-only command ran %s' % argv)

    def http_status(self, url):
        assert url == launch.MISSIONS_PROBE_URL
        return self.missions_status

    def hash_folder(self, path):
        return ('folder', self.digest) if self.digest else ('missing', None)

    def oracle_sql(self):
        def sql(select, pdb):
            preflight.sql_script(select, pdb)  # the preflight's own guard: one plain SELECT, read only
            self.selects.append(select)
            for marker, rows in self.rows.items():
                if marker in select:
                    return list(rows)
            return []
        return sql, 'MISSIONS_LAB', 'XEPDB1'


ORACLE_ROWS = {'COUNT(*) FROM MISSIONS_LAB.MISSIONS': ['300'], 'COUNT(*) FROM MISSIONS_LAB.MISSION_ASSIGNED_CREW': ['900'],
               'COUNT(*) FROM MISSIONS_LAB.MISSION_PARTICIPANTS': ['600'], 'COUNT(*) FROM MISSIONS_LAB.MISSION_ASSIGNED_ASSETS': ['450'],
               'COUNT(*) FROM MISSIONS_LAB.MISSION_CHANGES': ['1200'], 'COUNT(*) FROM MISSIONS_LAB.MISSION_CLOCK': ['1'],
               'mission_clock': ['1.2|abc|0|2026-10-09T00:00:00.000Z'], 'MAX(current_change_id)': ['1200|2026-10-09T00:00:00.000Z'],
               'v$instance': ['2026-11-02T07:00:00']}


class ReadingCommandTests(StateDir):
    def run_main(self, *argv, machine=None):
        lines, err = [], io.StringIO()
        with redirect_stderr(err):
            code = launch.main(list(argv) + ['--state-dir', str(self.state)], machine=machine, environ={}, out=lines.append)
        return code, (json.loads(lines[0]) if lines else None), err.getvalue()

    def test_the_simulator_fingerprint_is_its_release_hash_and_its_container_start(self):
        machine = ReadingMachine()
        code, value, err = self.run_main('fingerprint', '--missions', 'simulated', machine=machine)
        self.assertEqual(code, 0, err)
        self.assertEqual(value['fingerprint'], 'missions-release-1.2:' + 'd' * 64)
        self.assertEqual(value['session'], 'missions-stub:2026-11-02T08:00:00Z')
        self.assertFalse(Path(self.state).exists(), 'a read-only command makes no state folder')
        machine.containers['missions-stub']['startedAt'] = '2026-11-02T09:00:00Z'
        self.assertNotEqual(self.run_main('fingerprint', '--missions', 'simulated', machine=machine)[1]['session'], value['session'],
                            'a restarted simulator is a new session')
        self.assertEqual(self.run_main('fingerprint', '--missions', 'simulated', machine=ReadingMachine(containers={'missions-stub': None}))[0], 1)
        self.assertEqual(self.run_main('fingerprint', '--missions', 'simulated', machine=ReadingMachine(digest=None))[0], 1)

    def test_the_simulator_release_hash_is_the_provenance_hash(self):
        kind, digest = launch.Machine().hash_folder(launch.MISSIONS_RELEASE)
        self.assertEqual(kind, 'folder')
        self.assertEqual(digest, make_config.missions_backend('simulated')['dataset']['sha256'])

    def test_the_real_fingerprint_reuses_the_preflight_reading_and_the_instance_start(self):
        machine = ReadingMachine(rows=ORACLE_ROWS)
        code, value, err = self.run_main('fingerprint', '--missions', 'real', machine=machine)
        self.assertEqual(code, 0, err)
        reading = preflight.read_data_fingerprint(machine.oracle_sql()[0], 'MISSIONS_LAB', 'XEPDB1')
        self.assertEqual(value['fingerprint'], 'missions-db:' + preflight.fingerprint_sha256(reading))
        self.assertEqual(value['reading'], reading)
        self.assertEqual(value['session'], 'oracle-instance:2026-11-02T07:00:00')
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in machine.selects))
        rows = dict(ORACLE_ROWS, mission_clock=[])
        self.assertEqual(self.run_main('fingerprint', '--missions', 'real', machine=ReadingMachine(rows=rows))[0], 1)
        rows = {k: v for k, v in ORACLE_ROWS.items() if k != 'v$instance'}
        self.assertEqual(self.run_main('fingerprint', '--missions', 'real', machine=ReadingMachine(rows=rows))[0], 1)

    def test_health_reports_every_backend_and_exits_0(self):
        code, value, _ = self.run_main('health', 'gamma', '--missions', 'simulated', machine=ReadingMachine())
        self.assertEqual(code, 0)
        self.assertEqual({n: b['up'] for n, b in value['backends'].items()}, {'missions': True, 'assets': True, 'personnel': True})
        down = ReadingMachine(containers={'assets-service': {'running': True, 'status': 'running', 'health': 'unhealthy', 'startedAt': 't'},
                                          'personnel-service': None})
        code, value, _ = self.run_main('health', 'gamma', '--missions', 'simulated', machine=down)
        self.assertEqual(code, 0)
        self.assertEqual({n: b['up'] for n, b in value['backends'].items()}, {'missions': True, 'assets': False, 'personnel': False})
        self.assertIn('unhealthy', value['backends']['assets']['detail'])
        self.assertFalse(Path(self.state).exists())

    def test_health_of_the_real_service_also_needs_its_get_to_answer(self):
        machine = ReadingMachine(containers={'missions-stub': None})
        code, value, _ = self.run_main('health', 'delta', '--missions', 'real', machine=machine)
        self.assertTrue(value['backends']['missions']['up'])
        machine.missions_status = 503
        code, value, _ = self.run_main('health', 'delta', '--missions', 'real', machine=machine)
        self.assertFalse(value['backends']['missions']['up'])
        self.assertIn('answered 503', value['backends']['missions']['detail'])
        stopped = ReadingMachine(containers={launch.MISSIONS_CONTAINER: {'running': False, 'status': 'exited', 'health': None, 'startedAt': 't'}})
        self.assertFalse(self.run_main('health', 'delta', '--missions', 'real', machine=stopped)[1]['backends']['missions']['up'])

    def test_the_output_is_what_the_harness_reads(self):
        code, value, _ = self.run_main('health', 'alpha', '--missions', 'simulated', machine=ReadingMachine())
        self.assertEqual(runner.parse_health(json.dumps(value), ['assets', 'missions', 'personnel'])['missions']['up'], True)
        code, value, _ = self.run_main('fingerprint', '--missions', 'simulated', machine=ReadingMachine())
        self.assertEqual(runner.parse_fingerprint(json.dumps(value))['session'], value['session'])


class AnsweringMachine(ReadingMachine):
    """ReadingMachine plus `request`: each URL answers from `answers` ({url: (status, text)}); every request is recorded."""

    def __init__(self, answers=None, **kw):
        super().__init__(**kw)
        self.answers, self.requests = dict(answers or {}), []

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, body, dict(headers or {})))
        return self.answers.get(url, (None, 'URLError'))


class ReadyTests(StateDir):
    def run_main(self, *argv, machine):
        lines, err = [], io.StringIO()
        with redirect_stderr(err):
            code = launch.main(list(argv) + ['--state-dir', self.state], machine=machine, environ={}, out=lines.append)
        return code, (json.loads(lines[0]) if lines else None), err.getvalue()

    def test_a_graph_arm_asks_its_router_for_the_service(self):
        ok = (200, json.dumps({'data': {'assetsPage': {'totalCount': 32}}}))
        for scenario, url in (('delta', 'http://127.0.0.1:8170/'), ('epsilon', 'http://127.0.0.1:8171/graphql')):
            machine = AnsweringMachine({url: ok})
            code, value, _ = self.run_main('ready', 'assets', scenario, '--missions', 'real', machine=machine)
            self.assertEqual((code, value['ready']), (0, True))
            (method, asked, body, headers), = machine.requests
            self.assertEqual((method, asked, json.loads(body)), ('POST', url, {'query': launch.READY_QUERIES['assets']}))
            self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertFalse(Path(self.state).exists(), 'read only: no state folder is made')

    def test_an_error_null_data_or_no_answer_is_not_ready(self):
        url = 'http://127.0.0.1:8170/'
        unavailable = json.dumps({'data': {'assetsPage': None}, 'errors': [{'message': 'down', 'extensions': {'code': 'SERVICE_UNAVAILABLE'}}]})
        for answer, words in (((200, unavailable), 'SERVICE_UNAVAILABLE'), ((200, json.dumps({'data': {'assetsPage': None}})), 'without data'),
                              ((200, json.dumps({'data': {}})), 'without data'), ((503, 'busy'), 'answered 503'),
                              ((None, 'URLError'), 'answered None')):
            code, value, _ = self.run_main('ready', 'assets', 'delta', '--missions', 'real', machine=AnsweringMachine({url: answer}))
            self.assertEqual((code, value['ready']), (0, False), answer)
            self.assertIn(words, value['detail'])

    def test_gamma_asks_the_service_adapter(self):
        for service, url in launch.ADAPTER_URLS.items():
            page = {'missions': 'missionsPage', 'assets': 'assetsPage', 'personnel': 'personnelMembers'}[service]
            machine = AnsweringMachine({url: (200, json.dumps({'data': {page: {'totalCount': 1}}}))})
            code, value, _ = self.run_main('ready', service, 'gamma', '--missions', 'simulated', machine=machine)
            self.assertTrue(value['ready'], service)
            self.assertIn(page, json.loads(machine.requests[0][2])['query'])

    def test_the_direct_arms_ask_the_service_itself(self):
        for scenario in ('alpha', 'beta'):
            for service, (method, url, body, headers) in launch.SERVICE_READY.items():
                machine = AnsweringMachine({url: (200, '')})
                code, value, _ = self.run_main('ready', service, scenario, '--missions', 'real', machine=machine)
                self.assertTrue(value['ready'], (scenario, service))
                self.assertEqual(machine.requests, [(method, url, body, headers)])
                code, value, _ = self.run_main('ready', service, scenario, '--missions', 'real', machine=AnsweringMachine({url: (500, '')}))
                self.assertFalse(value['ready'])
        self.assertIn('<limit>1</limit>', launch.SERVICE_READY['personnel'][2])

    def test_the_entry_points_are_the_ones_the_mcp_servers_use(self):
        for scenario, url in launch.ROUTER_URLS.items():
            self.assertEqual(make_config.SERVERS[scenario]['router_url'], url)
        self.assertEqual({launch.ADAPTER_URLS[s] for s in launch.ADAPTER_URLS},
                         {u for u, name in make_config.UPSTREAMS['adapters'].items() if name != 'mapping-adapter'})
        for service, (_, url, _, _) in launch.SERVICE_READY.items():
            self.assertTrue(url.startswith(make_config.UPSTREAMS['raw'][service]), service)

    def test_the_output_is_what_the_harness_reads(self):
        url = 'http://127.0.0.1:8183/graphql'
        code, value, _ = self.run_main('ready', 'missions', 'gamma', '--missions', 'real',
                                       machine=AnsweringMachine({url: (200, json.dumps({'data': {'missionsPage': {'totalCount': 3}}}))}))
        self.assertEqual(runner.parse_ready(json.dumps(value)), (True, value['detail']))


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.plan = {'task_set': 'dev', 'scenario_order': list(launch.SCENARIOS), 'models': ['claude-sonnet-5-5', 'gpt-6.1-sol'],
                     'trials': 1, 'seed': 1, 'warmup_passes': 1, 'limits': {'max_tool_calls': 80}, 'budgets': {'anthropic': {'tokens': 1}}}
        (self.dir / 'plan.json').write_text(json.dumps(self.plan), encoding='utf-8')
        (self.dir / 'guide.md').write_text('guide', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def write_pins(self, images=None):
        state = self.dir / 'state'
        state.mkdir(exist_ok=True)
        (state / launch.PIN_FILE).write_text(json.dumps({'schema': 1, 'images': dict(IMAGE_IDS if images is None else images)}), encoding='utf-8')

    def generate(self, mode, *extra, output='config.json', machine=None, pins=True):
        if mode == 'real' and pins:
            self.write_pins()
        argv = ['--output', str(self.dir / output), '--plan', str(self.dir / 'plan.json'), '--missions', mode,
                '--state-dir', str(self.dir / 'state'), '--mcp-python', str(self.dir / 'venv-python'), '--guide-file',
                str(self.dir / 'guide.md'), *extra]
        err = io.StringIO()
        with redirect_stderr(err):
            code = make_config.main(argv, machine=machine or FakeMachine())
        config = json.loads((self.dir / output).read_text(encoding='utf-8')) if code == 0 else None
        return code, config, err.getvalue()

    def test_both_modes_give_a_valid_provenance_block_per_scenario(self):
        for mode in launch.MODES:
            with self.subTest(mode=mode):
                code, config, err = self.generate(mode, output=mode + '.json')
                self.assertEqual(code, 0, err)
                self.assertEqual(list(config['scenarios']), list(launch.SCENARIOS))
                for name, scenario in config['scenarios'].items():
                    block = scenario['provenance']
                    provenance.validate(name, block)
                    self.assertEqual(block['backends']['missions']['mode'], mode)
                    self.assertEqual(block['backends']['assets']['mode'], 'real')
                    self.assertEqual(block['backends']['personnel']['mode'], 'real')
                    self.assertEqual(block['routing']['env'],
                                     {adapter: {variable: urls[mode]} for adapter, (variable, urls) in launch.ADAPTER_BACKEND_URLS.items()})
                    self.assertEqual(block['routing']['env']['missions-adapter']['MISSIONS_SERVICE_URL'], launch.MISSIONS_ADAPTER_URL[mode])
                    self.assertEqual(launch.MISSIONS_PROJECT in block['compose_projects'], mode == 'real')
                    labels = set(block['launch_files'])
                    self.assertEqual('missions_real_overlay' in labels, mode == 'real')
                    self.assertEqual('legacy_ports' in labels, name in ('alpha', 'beta'))
                    for path in block['launch_files'].values():
                        self.assertTrue(Path(path).is_file(), path)

    def test_the_stack_commands_carry_the_mode_and_the_state_folder(self):
        code, config, _ = self.generate('real')
        stack = config['scenarios']['beta']['stack']
        up = stack['start'][0]['argv']
        self.assertEqual(up[2:5], [str(launch.HERE / 'launch.py'), 'up', 'beta'])
        self.assertEqual(up[-4:], ['--missions', 'real', '--state-dir', str((self.dir / 'state').resolve())])
        self.assertTrue(stack['start'][1]['background'])
        self.assertEqual(stack['start'][1]['argv'][0], str(self.dir / 'venv-python'))
        self.assertEqual(sorted(stack['stop_service']), ['assets', 'missions', 'personnel'])
        self.assertEqual(config['scenarios']['beta']['guide_file'], str((self.dir / 'guide.md').resolve()))
        self.assertNotIn('guide_file', config['scenarios']['alpha'])
        self.assertNotIn('env', stack['start'][0])
        code, config, _ = self.generate('real', '--accept-apollo-elv2', output='elv2.json')
        self.assertEqual(config['scenarios']['delta']['stack']['start'][0]['env'], {'APOLLO_ELV2_LICENSE': 'accept'})

    def test_the_plan_is_copied_and_nothing_else_is_taken_from_it(self):
        code, config, _ = self.generate('simulated')
        for key in make_config.PLAN_KEYS:
            self.assertEqual(config[key], self.plan[key])
        for bad, words in (({'scenarios': {}}, 'remove scenarios'), ({'scenario_order': ['zeta']}, 'scenario_order')):
            (self.dir / 'plan.json').write_text(json.dumps(dict(self.plan, **bad)), encoding='utf-8')
            code, _, err = self.generate('simulated', output='bad.json')
            self.assertEqual(code, 1)
            self.assertIn(words, err)
        (self.dir / 'plan.json').write_text(json.dumps({'task_set': 'dev'}), encoding='utf-8')
        code, _, err = self.generate('simulated', output='bad.json')
        self.assertIn('lacks', err)

    def schedule_plan(self, **over):
        plan = {'schedule': {'design': 'williams-4-half', 'arms': ['beta', 'gamma', 'delta', 'epsilon'], 'reference': 'alpha'},
                'task_set': 'scored', 'models': ['claude-sonnet-5-5', 'gpt-6.1-sol'], 'seed': 20261027, 'warmup_passes': 3,
                'limits': {'max_tool_calls': 80},
                'budgets': {'anthropic': {'tokens': 1, 'dollar_ceiling': 85.0, 'ceiling_basis': 'decision D'}},
                'harness_tools': ['calculate', 'ask_requester'], 'health_every_runs': 10, 'earlier_study_runs': ['dev-1']}
        plan.update(over)
        (self.dir / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
        return plan

    def test_a_schedule_plan_writes_the_fingerprint_health_and_corpus(self):
        plan = self.schedule_plan()
        code, config, err = self.generate('simulated')
        self.assertEqual(code, 0, err)
        for key in make_config.SCHEDULE_PLAN_KEYS + ('harness_tools', 'health_every_runs', 'earlier_study_runs'):
            self.assertEqual(config[key], plan[key])
        self.assertNotIn('scenario_order', config)
        self.assertNotIn('trials', config)
        self.assertEqual(list(config['scenarios']), ['beta', 'gamma', 'delta', 'epsilon', 'alpha'])
        self.assertEqual(config['corpus_dir'], str(ROOT / 'study' / 'corpus2'))
        state = str((self.dir / 'state').resolve())
        self.assertEqual(config['dataset_fingerprint']['argv'][2:], [str(launch.HERE / 'launch.py'), 'fingerprint', '--missions',
                                                                      'simulated', '--state-dir', state])
        for name, scenario in config['scenarios'].items():
            self.assertEqual(scenario['health']['argv'][2:], [str(launch.HERE / 'launch.py'), 'health', name, '--missions', 'simulated',
                                                              '--state-dir', state])
            runner.validate_command(scenario['health'], name)
            self.assertEqual(sorted(scenario['ready']), sorted(launch.OUTAGE_SERVICES))
            for service, command in scenario['ready'].items():
                self.assertEqual(command['argv'][2:], [str(launch.HERE / 'launch.py'), 'ready', service, name, '--missions', 'simulated',
                                                       '--state-dir', state])
            runner.validate_ready(scenario['ready'], sorted(launch.OUTAGE_SERVICES), name)
        runner.validate_command(config['dataset_fingerprint'], 'fingerprint')
        path = self.dir / 'config.json'
        self.assertEqual(runner.load_config(path)['schedule'], plan['schedule'])
        self.assertEqual(runner.corpus_of(runner.load_config(path)), ROOT / 'study' / 'corpus2')

    def test_a_schedule_plan_refuses_the_study_1_keys_and_a_bad_schedule(self):
        for over, words in (({'scenario_order': ['alpha']}, 'holds no scenario_order or trials'), ({'trials': 2}, 'holds no scenario_order'),
                            ({'schedule': {'design': 'latin', 'arms': [], 'reference': 'alpha'}}, 'schedule.design'),
                            ({'schedule': {'design': 'williams-4-half', 'arms': ['beta', 'gamma', 'delta', 'zeta'], 'reference': 'alpha'}},
                             'zeta')):
            self.schedule_plan(**over)
            code, _, err = self.generate('simulated', output='bad.json')
            self.assertEqual(code, 1, over)
            self.assertIn(words, err)
        plan = self.schedule_plan()
        del plan['seed']
        (self.dir / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
        self.assertIn('lacks seed', self.generate('simulated', output='bad.json')[2])

    def test_the_corpus_folder_is_recorded(self):
        code, config, _ = self.generate('simulated')
        self.assertEqual(config['corpus_dir'], str(ROOT / 'study' / 'corpus'), 'a study-1 plan reads study 1\'s corpus')
        code, config, _ = self.generate('simulated', '--corpus-dir', str(ROOT / 'study' / 'corpus2'), output='c2.json')
        self.assertEqual(config['corpus_dir'], str(ROOT / 'study' / 'corpus2'))
        code, _, err = self.generate('simulated', '--corpus-dir', str(self.dir), output='bad.json')
        self.assertEqual(code, 1)
        self.assertIn('no scoring.py', err)

    def test_the_real_mode_refuses_a_missing_or_bad_pin_set_a_missing_image_and_a_changed_id(self):
        build = 'python -B study/launch/launch.py build --missions real --state-dir %s' % (self.dir / 'state').resolve()
        code, _, err = self.generate('real', pins=False)
        self.assertEqual(code, 1)
        self.assertIn('there is no image pin set at', err)
        self.assertIn(build, err)
        self.write_pins({ref: value for ref, value in IMAGE_IDS.items() if ref != launch.MISSIONS_IMAGE})
        code, _, err = self.generate('real', pins=False)
        self.assertIn('does not hold one sha256 id for each of', err)
        for ref in launch.PINNED_IMAGES:
            with self.subTest(ref=ref):
                missing = FakeMachine(images={name: value for name, value in IMAGE_IDS.items() if name != ref})
                code, _, err = self.generate('real', machine=missing)
                self.assertEqual(code, 1)
                self.assertIn('the pinned image %s is missing; build again, which writes a new pin set: %s' % (ref, build), err)
                rebuilt = FakeMachine(images=dict(IMAGE_IDS, **{ref: 'sha256:' + 'f' * 64}))
                code, _, err = self.generate('real', machine=rebuilt)
                self.assertEqual(code, 1)
                self.assertIn('the image %s is now %s, not its pinned %s; build again' % (ref, 'sha256:' + 'f' * 64, IMAGE_IDS[ref]), err)
        self.assertFalse((self.dir / 'config.json').exists())

    def test_every_arm_declares_the_identical_pin_set(self):
        self.schedule_plan()
        code, config, err = self.generate('real')
        self.assertEqual(code, 0, err)

        def pin_set(block):
            return {'backends': {name: (backend.get('image_ref'), backend.get('image_id')) for name, backend in block['backends'].items()},
                    'service_images': block.get('service_images')}
        assets, personnel = make_config.IMAGES['assets-service'], make_config.IMAGES['personnel-service']
        adapters = {ref: names[0] for ref, names in launch.BUILT_IMAGES.items() if names[0].endswith('-adapter')}
        expected = {'backends': {'missions': (launch.MISSIONS_IMAGE, IMAGE_IDS[launch.MISSIONS_IMAGE]), 'assets': (assets, IMAGE_IDS[assets]),
                                 'personnel': (personnel, IMAGE_IDS[personnel])},
                    'service_images': {'assets-bootstrap': {'image_id': IMAGE_IDS[assets], 'image_ref': assets, 'one_shot': True},
                                       **{name: {'image_id': IMAGE_IDS[ref], 'image_ref': ref} for ref, name in adapters.items()}}}
        self.assertEqual({name: pin_set(scenario['provenance']) for name, scenario in config['scenarios'].items()},
                         dict.fromkeys(launch.SCENARIOS, expected))

    def test_the_pinned_config_passes_the_harness_check_of_a_stack_on_the_pinned_images(self):
        code, config, err = self.generate('real')
        self.assertEqual(code, 0, err)
        block = config['scenarios']['delta']['provenance']
        services = dict(block['service_images'])
        observed = {'starfleet-federation-stack/%s' % name: {'state': 'exited' if pin.get('one_shot') else 'running', 'exitCode': 0,
                                                              'imageId': pin['image_id'], 'imageRef': pin['image_ref'], 'env': {}, 'ports': [],
                                                              'mounts': []} for name, pin in services.items()}
        problems = [p for p in provenance.compare(block, {'stable': {'services': observed, 'datasets': {}, 'launchFiles': {}}})
                    if p.startswith('pinned image of')]
        self.assertEqual(problems, [])
        observed['starfleet-federation-stack/assets-bootstrap']['exitCode'] = 1
        observed['starfleet-federation-stack/mapping-adapter']['imageId'] = 'sha256:' + 'f' * 64
        problems = [p for p in provenance.compare(block, {'stable': {'services': observed, 'datasets': {}, 'launchFiles': {}}})
                    if p.startswith('pinned image of')]
        self.assertEqual(len(problems), 2, problems)

    def test_the_simulated_mode_pins_nothing(self):
        code, config, err = self.generate('simulated')
        self.assertEqual(code, 0, err)
        for scenario in config['scenarios'].values():
            block = scenario['provenance']
            self.assertNotIn('service_images', block)
            self.assertNotIn('image_id', block['backends']['assets'])
            self.assertNotIn('image_id', block['backends']['personnel'])

    def test_the_config_holds_no_credential(self):
        code, config, _ = self.generate('real')
        text = json.dumps(config)
        self.assertIsNone(re.search(r'PASSWORD|SECRET|TOKEN"|MISSIONS_DB_', text, re.I))

    def test_output_inside_the_repository_or_an_existing_file_is_refused(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = make_config.main(['--output', str(ROOT / 'study-config.json'), '--plan', str(self.dir / 'plan.json'), '--missions', 'real',
                                     '--state-dir', str(self.dir / 'state'), '--mcp-python', 'py', '--guide-file', str(self.dir / 'guide.md')])
        self.assertEqual(code, 1)
        self.assertIn('outside the repository', err.getvalue())
        self.assertFalse((ROOT / 'study-config.json').exists())
        self.assertEqual(self.generate('real')[0], 0)
        code, _, err = self.generate('real')
        self.assertEqual(code, 1)
        self.assertIn('--replace', err)
        self.assertEqual(self.generate('real', '--replace')[0], 0)


if __name__ == '__main__':
    unittest.main()
