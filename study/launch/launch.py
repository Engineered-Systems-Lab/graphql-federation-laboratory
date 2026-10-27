"""Start, stop and interrupt the stack of one study scenario, with the Missions backend simulated or real.

    python -B study/launch/launch.py up <scenario> --missions simulated|real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py down <scenario> --missions simulated|real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py service stop|start assets|personnel|missions <scenario> --missions simulated|real --state-dir <folder> [--dry-run]

Scenarios are the internal letters alpha to epsilon (study/README.md has the names). Every scenario starts the whole federation stack,
as study 1 did; epsilon starts the Cosmo router instead of the Apollo one, and alpha and beta also publish the legacy services on their
loopback ports (study/mcp/legacy-ports.json) for the raw MCP server.

- simulated: the Missions simulator (missions-stub), study 1's setup, through federation/stack/start.sh unchanged.
- real: the real Missions service on Oracle. The operator starts Oracle and the service first (missions_operator.py and
  uss-enterprise/missions/compose.yaml); this script never starts, provisions, resets or removes either, and refuses to start a stack
  when the service is not up. missions-stub is not started, and the Missions adapter joins the service's own bridge network
  (missions-real.compose.yaml), never Oracle's internal one. The steps are those of start.sh with that file added to every compose call.

The state folder is machine-local and outside the repository: the composed supergraph and the Cosmo execution config go there, so the
committed files are never rewritten. The Assets database passwords are made at random for each `up` unless STACK_ASSETS_DB_ADMIN_PASSWORD
and STACK_ASSETS_DB_SERVICE_PASSWORD are set; they are passed in the environment of the child commands only, and never printed or
written. The script handles no Missions login: the service already holds its own.

Environment: STUDY_LAUNCH_STATE_DIR (instead of --state-dir), STUDY_BASH (Git Bash, for the simulated mode; default: bash on PATH),
PYTHON (the interpreter start.sh and the composition scripts run under; default: this one), APOLLO_ELV2_LICENSE=accept (an Apollo start
needs it: Rover's composition plugin is under the Elastic License 2.0 and the operator accepts it), and the *_HOST_PORT variables of
start.sh. Nothing is removed: no rm, no down, no prune.
"""
import argparse
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STACK_COMPOSE = ROOT / 'federation' / 'stack' / 'compose.yaml'
START_SH = ROOT / 'federation' / 'stack' / 'start.sh'
LEGACY_PORTS = ROOT / 'study' / 'mcp' / 'legacy-ports.json'
REAL_OVERLAY = HERE / 'missions-real.compose.yaml'
SUPERGRAPH_SOURCE = ROOT / 'federation' / 'routers' / 'apollo' / 'supergraph.graphql'
EXECUTION_CONFIG_SOURCE = ROOT / 'federation' / 'routers' / 'cosmo' / 'execution-config.json'
COMPOSE_SUPERGRAPH = ROOT / 'federation' / 'routers' / 'apollo' / 'compose_supergraph.py'
COMPOSE_EXECUTION_CONFIG = ROOT / 'federation' / 'routers' / 'cosmo' / 'compose_execution_config.py'

SCENARIOS = ('alpha', 'beta', 'gamma', 'delta', 'epsilon')
LEGACY_SCENARIOS = ('alpha', 'beta')
MODES = ('simulated', 'real')

# The backends of federation/stack/start.sh in its order; the real mode starts the same list without missions-stub (a test pins it).
STACK_BACKENDS = ('assets-db', 'assets-bootstrap', 'assets-service', 'personnel-service', 'missions-stub', 'missions-adapter',
                  'personnel-adapter', 'assets-adapter', 'mapping-adapter')
REAL_BACKENDS = tuple(name for name in STACK_BACKENDS if name != 'missions-stub')
LEGACY_SERVICES = {'simulated': ('personnel-service', 'missions-stub', 'assets-service'), 'real': ('personnel-service', 'assets-service')}

# The real Missions service, as uss-enterprise/missions/compose.yaml starts it with its defaults (a test pins these against that file).
MISSIONS_PROJECT = 'starfleet-missions'
MISSIONS_CONTAINER = 'starfleet-missions-service'
MISSIONS_NETWORK = MISSIONS_PROJECT + '_default'
MISSIONS_HOST_PORT = 8083
MISSIONS_PROBE_URL = 'http://127.0.0.1:%d/missions?pageSize=1' % MISSIONS_HOST_PORT
MISSIONS_ADAPTER_URL = {'simulated': 'http://missions-stub:8083', 'real': 'http://%s:8083' % MISSIONS_CONTAINER}

# The backend URL of each adapter, as federation/stack/compose.yaml defaults them (a test pins them). launch.py sets them in every child
# environment, so an inherited value cannot point an adapter elsewhere, and make_config.py declares them for the harness to check.
ADAPTER_BACKEND_URLS = {
    'missions-adapter': ('MISSIONS_SERVICE_URL', MISSIONS_ADAPTER_URL),
    'personnel-adapter': ('PERSONNEL_SERVICE_URL', dict.fromkeys(MODES, 'http://personnel-service:8082/soap/personnel-v2')),
    'assets-adapter': ('ASSETS_SERVICE_URL', dict.fromkeys(MODES, 'http://assets-service:8084')),
}


def adapter_backend_env(mode):
    return {variable: urls[mode] for variable, urls in ADAPTER_BACKEND_URLS.values()}

# Outage services: the logical names of the corpus, mapped to compose services of the federation stack.
OUTAGE_SERVICES = {'assets': 'assets-service', 'personnel': 'personnel-service', 'missions': 'missions-stub'}

MIN_COMPOSE = (2, 24, 4)  # the first Compose with the !reset tag that missions-real.compose.yaml uses
ASSETS_PASSWORDS = ('STACK_ASSETS_DB_ADMIN_PASSWORD', 'STACK_ASSETS_DB_SERVICE_PASSWORD')


class Refused(Exception):
    """The script refuses to go on; nothing further is run."""


def router_of(scenario):
    return 'cosmo' if scenario == 'epsilon' else 'apollo'


def outside_repository(path, what):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise Refused('%s must be outside the repository, not %s' % (what, path))
    return path


class Plan:
    """The commands of one invocation: each step is (argv, extra environment). `checks` run first, in order, and may refuse."""

    def __init__(self):
        self.checks = []
        self.steps = []

    def run(self, argv, env=None):
        self.steps.append(('run', list(map(str, argv)), dict(env or {})))

    def wait_missions(self, timeout):
        self.steps.append(('wait-missions', [MISSIONS_PROBE_URL, str(timeout)], {}))


def base_env(state_dir, scenario, mode):
    env = dict(adapter_backend_env(mode))
    env.update({'SUPERGRAPH_FILE': str(state_dir / 'supergraph.graphql'), 'EXECUTION_CONFIG_FILE': str(state_dir / 'execution-config.json'),
           'FEDERATION_ROUTER': router_of(scenario), 'APOLLO_TELEMETRY_DISABLED': '1', 'COSMO_TELEMETRY_DISABLED': '1',
           'PYTHON': os.environ.get('PYTHON') or sys.executable})
    return env


def compose_files(mode, legacy=False):
    files = ['-f', STACK_COMPOSE]
    if legacy:
        files += ['-f', LEGACY_PORTS]
    if mode == 'real':
        files += ['-f', REAL_OVERLAY]
    return ['docker', 'compose'] + files


def profile(scenario):
    return ['--profile', 'cosmo'] if router_of(scenario) == 'cosmo' else []


def assets_passwords(environ, placeholder=None):
    """The two Assets database passwords, the operator's when set, else random for this run (or the placeholder compose needs to parse)."""
    out = {}
    for name in ASSETS_PASSWORDS:
        out[name] = environ.get(name) or placeholder or secrets.token_hex(16)
    return out


def router_ports(environ, scenario):
    router = environ.get('COSMO_ROUTER_HOST_PORT', '8171') if router_of(scenario) == 'cosmo' else environ.get('ROUTER_HOST_PORT', '8170')
    ports = [router] + [environ.get(name, default) for name, default in (('PERSONNEL_ADAPTER_HOST_PORT', '8182'),
                                                                          ('MISSIONS_ADAPTER_HOST_PORT', '8183'),
                                                                          ('ASSETS_ADAPTER_HOST_PORT', '8184'),
                                                                          ('MAPPING_ADAPTER_HOST_PORT', '8190'))]
    for port in ports:
        if not str(port).isdigit():
            raise Refused('a host port must be a number, not %r' % port)
    return [int(port) for port in ports]


def plan_up(scenario, mode, state_dir, environ):
    plan = Plan()
    env = dict(base_env(state_dir, scenario, mode), **assets_passwords(environ))
    legacy = scenario in LEGACY_SCENARIOS
    if mode == 'simulated':
        plan.checks.append(('bash', None))
        plan.run(['{bash}', START_SH, 'start'], env)
        if legacy:
            plan.run(compose_files(mode, legacy=True) + ['up', '-d', '--no-deps', '--wait'] + list(LEGACY_SERVICES[mode]), env)
        return plan
    plan.checks += [('compose-version', None), ('missions-container', None), ('missions-network', None), ('missions-answers', None),
                    ('ports-free', router_ports(environ, scenario))]
    if router_of(scenario) == 'apollo':
        plan.checks.append(('elv2', None))
    plan.run(compose_files(mode) + ['up', '-d', '--build', '--wait', '--wait-timeout', '600'] + list(REAL_BACKENDS), env)
    if router_of(scenario) == 'cosmo':
        plan.run([env['PYTHON'], '-B', COMPOSE_EXECUTION_CONFIG, '--out', env['EXECUTION_CONFIG_FILE']], env)
        plan.run(compose_files(mode) + profile(scenario) + ['up', '-d', '--wait', '--wait-timeout', '120', 'cosmo-router'], env)
    else:
        plan.run([env['PYTHON'], '-B', COMPOSE_SUPERGRAPH, '--out', env['SUPERGRAPH_FILE']], env)
        plan.run(compose_files(mode) + ['up', '-d', '--wait', '--wait-timeout', '120', 'router'], env)
    if legacy:
        plan.run(compose_files(mode, legacy=True) + ['up', '-d', '--no-deps', '--wait'] + list(LEGACY_SERVICES[mode]), env)
    return plan


def plan_down(scenario, mode, state_dir, environ):
    plan = Plan()
    env = dict(base_env(state_dir, scenario, mode), **assets_passwords(environ, placeholder='unused'))
    if mode == 'simulated':
        plan.checks.append(('bash', None))
        plan.run(['{bash}', START_SH, 'stop'], env)
    else:
        # Stops the federation stack only; the real Missions service and Oracle keep running.
        plan.run(compose_files(mode) + profile(scenario) + ['stop', '--timeout', '60'], env)
    return plan


def plan_service(action, service, scenario, mode, state_dir, environ):
    plan = Plan()
    if service not in OUTAGE_SERVICES:
        raise Refused('service must be one of %s, not %r' % (', '.join(OUTAGE_SERVICES), service))
    if service == 'missions' and mode == 'real':
        # The outage of the real service stops and starts the container the operator made, by name: never compose up, never a new one.
        plan.checks.append(('missions-container-exists', None))
        if action == 'stop':
            plan.run(['docker', 'stop', MISSIONS_CONTAINER])
        else:
            plan.run(['docker', 'start', MISSIONS_CONTAINER])
            plan.wait_missions(300)
        return plan
    # The passwords only let compose parse the file: --no-recreate starts the stopped container as it was, with its own credentials.
    env = dict(base_env(state_dir, scenario, mode), **assets_passwords(environ, placeholder='unused'))
    files = compose_files(mode, legacy=scenario in LEGACY_SCENARIOS) + profile(scenario)
    target = OUTAGE_SERVICES[service]
    if action == 'stop':
        plan.run(files + ['stop', target], env)
    else:
        plan.run(files + ['up', '-d', '--no-deps', '--no-recreate', '--wait', target], env)
    return plan


# ------------------------------------------------------------------------------------------------------------------ execution
def find_bash(environ):
    bash = environ.get('STUDY_BASH') or shutil.which('bash')
    if not bash:
        raise Refused('no bash found: set STUDY_BASH to the bash of Git Bash')
    if os.name == 'nt' and 'system32' in str(Path(bash)).lower():
        raise Refused('bash resolves to %s, the WSL launcher; set STUDY_BASH to the bash of Git Bash' % bash)
    return bash


def parse_version(text):
    numbers = re.findall(r'\d+', text or '')
    return tuple(int(n) for n in numbers[:3]) if len(numbers) >= 3 else None


class Machine:
    """The real effects: run a command, read docker, probe a URL or a port. Tests replace it with a fake."""

    def read(self, argv):
        done = subprocess.run(argv, capture_output=True, text=True)
        return done.returncode, (done.stdout or '').strip()

    def call(self, argv, env):
        return subprocess.run(argv, env=env).returncode

    def http_status(self, url):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code
        except (OSError, ValueError):
            return None

    def port_taken(self, port):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except OSError:
            return False

    def sleep(self, seconds):
        time.sleep(seconds)


def check(name, arg, machine, environ, context):
    if name == 'bash':
        context['bash'] = find_bash(environ)
    elif name == 'compose-version':
        code, out = machine.read(['docker', 'compose', 'version', '--short'])
        version = parse_version(out) if code == 0 else None
        if version is None or version < MIN_COMPOSE:
            raise Refused('the real mode needs Docker Compose %s or later (the !reset tag); found %s'
                          % ('.'.join(map(str, MIN_COMPOSE)), out or 'none'))
    elif name in ('missions-container', 'missions-container-exists'):
        code, out = machine.read(['docker', 'inspect', '--format', '{{.State.Running}}', MISSIONS_CONTAINER])
        if code != 0:
            raise Refused('the real Missions service container %s does not exist: the operator starts it first with '
                          'uss-enterprise/missions/compose.yaml (and Oracle with missions_operator.py)' % MISSIONS_CONTAINER)
        if name == 'missions-container' and out != 'true':
            raise Refused('the real Missions service container %s is not running: the operator starts it first' % MISSIONS_CONTAINER)
    elif name == 'missions-network':
        code, _ = machine.read(['docker', 'network', 'inspect', '--format', '{{.Name}}', MISSIONS_NETWORK])
        if code != 0:
            raise Refused('the network %s of the real Missions service does not exist: the operator starts the service first with '
                          'uss-enterprise/missions/compose.yaml' % MISSIONS_NETWORK)
    elif name == 'missions-answers':
        status = machine.http_status(MISSIONS_PROBE_URL)
        if status != 200:
            raise Refused('the real Missions service does not answer %s (status %s)' % (MISSIONS_PROBE_URL, status))
    elif name == 'ports-free':
        for port in arg:
            if machine.port_taken(port):
                raise Refused('127.0.0.1:%d is already in use (stop what listens there, or set its *_HOST_PORT variable)' % port)
    elif name == 'elv2':
        if environ.get('APOLLO_ELV2_LICENSE') != 'accept':
            raise Refused("Rover's composition plugin is under the Elastic License 2.0; set APOLLO_ELV2_LICENSE=accept to accept it")
    else:
        raise AssertionError(name)


def seed_state(state_dir):
    """Make the state folder and seed it with the committed composed files, which compose mounts and start.sh composes again."""
    state_dir.mkdir(parents=True, exist_ok=True)
    for source, name in ((SUPERGRAPH_SOURCE, 'supergraph.graphql'), (EXECUTION_CONFIG_SOURCE, 'execution-config.json')):
        target = state_dir / name
        if not target.exists():
            shutil.copyfile(source, target)


def show(argv):
    return ' '.join(argv)


def execute(plan, machine, environ, dry_run=False, out=print):
    context = {}
    for name, arg in plan.checks:
        if dry_run and name not in ('bash', 'elv2'):
            out('would check: %s' % name)
            continue
        check(name, arg, machine, environ, context)
    for kind, argv, extra in plan.steps:
        argv = [context.get('bash', 'bash') if part == '{bash}' else part for part in argv]
        if dry_run:
            out('would run: %s' % show(argv))
            continue
        if kind == 'wait-missions':
            url, timeout = argv[0], float(argv[1])
            deadline = time.monotonic() + timeout
            while machine.http_status(url) != 200:
                if time.monotonic() > deadline:
                    raise Refused('the real Missions service did not answer %s within %d s' % (url, timeout))
                machine.sleep(2)
            continue
        code = machine.call(argv, dict(environ, **extra))
        if code != 0:
            raise Refused('command failed with exit code %d: %s' % (code, show(argv)))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)

    def common(p):
        p.add_argument('scenario', choices=SCENARIOS)
        p.add_argument('--missions', choices=MODES, required=True, help='the Missions backend: the simulator or the real service on Oracle')
        p.add_argument('--state-dir', help='machine-local folder outside the repository (default: STUDY_LAUNCH_STATE_DIR)')
        p.add_argument('--dry-run', action='store_true', help='print the checks and commands, run nothing')

    common(sub.add_parser('up', help='start the stack of a scenario'))
    common(sub.add_parser('down', help='stop the stack of a scenario (the containers are kept)'))
    service = sub.add_parser('service', help='stop or start one backend, for a controlled outage')
    service.add_argument('action', choices=('stop', 'start'))
    service.add_argument('service', choices=tuple(OUTAGE_SERVICES))
    common(service)
    return parser


def main(argv=None, machine=None, environ=None, out=print):
    args = build_parser().parse_args(argv)
    environ = dict(os.environ if environ is None else environ)
    machine = machine or Machine()
    try:
        state = args.state_dir or environ.get('STUDY_LAUNCH_STATE_DIR')
        if not state:
            raise Refused('give --state-dir or set STUDY_LAUNCH_STATE_DIR (a machine-local folder outside the repository)')
        state_dir = outside_repository(state, 'the state folder')
        if args.command == 'up':
            plan = plan_up(args.scenario, args.missions, state_dir, environ)
        elif args.command == 'down':
            plan = plan_down(args.scenario, args.missions, state_dir, environ)
        else:
            plan = plan_service(args.action, args.service, args.scenario, args.missions, state_dir, environ)
        if not args.dry_run:
            seed_state(state_dir)
        execute(plan, machine, environ, dry_run=args.dry_run, out=out)
    except Refused as error:
        print('launch.py: refused: %s' % error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
