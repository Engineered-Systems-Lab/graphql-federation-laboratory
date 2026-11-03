"""Start, stop and interrupt the stack of one study scenario, with the Missions backend simulated or real.

    python -B study/launch/launch.py build --missions real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py up <scenario> --missions simulated|real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py down <scenario> --missions simulated|real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py service stop|start assets|personnel|missions <scenario> --missions simulated|real --state-dir <folder> [--dry-run]
    python -B study/launch/launch.py fingerprint --missions simulated|real --state-dir <folder>
    python -B study/launch/launch.py health <scenario> --missions simulated|real --state-dir <folder>

The last two only read, and are the commands the study config names for the harness (make_config.py writes them):

- `fingerprint` prints {"fingerprint": ..., "session": ...}, which the harness checks at every block start of study 2. On the real service
  the fingerprint is the SHA-256 of the preflight data step's reading of the Missions schema (study/preflight/preflight.py,
  read_data_fingerprint: the row counts, the clock row, the largest change id and lastUpdated; SELECT only, in a read-only transaction)
  and the session is the start time of the Oracle instance. On the simulator (decision F5 of the Job study2_build_followups) the
  fingerprint is the SHA-256 of its dataset release and the session the start time of its container from docker inspect, so a restarted
  simulator is a new session. It exits 1 when either cannot be read.
- `health` probes every backend of the scenario (missions, assets, personnel) and prints {"backends": {<name>: {"up": ..., "detail": ...}}}
  for the harness's void-block rule: a backend is up when its container is running and, where it has a healthcheck, healthy; the real
  Missions service must also answer GET /missions?pageSize=1. It reads docker inspect and sends that one GET, and exits 0 whatever it finds.

Scenarios are the internal letters alpha to epsilon (study/README.md has the names). Every scenario starts the whole federation stack,
as study 1 did; epsilon starts the Cosmo router instead of the Apollo one, and alpha and beta also publish the legacy services on their
loopback ports (study/mcp/legacy-ports.json) for the raw MCP server.

- simulated: the Missions simulator (missions-stub), study 1's setup, through federation/stack/start.sh unchanged.
- real: the real Missions service on Oracle. The operator starts Oracle and the service first (missions_operator.py and
  uss-enterprise/missions/compose.yaml); this script never starts, provisions, resets or removes either, and refuses to start a stack
  when the service is not up. missions-stub is not started, and the Missions adapter joins the service's own bridge network
  (missions-real.compose.yaml), never Oracle's internal one. The steps are those of start.sh with that file added to every compose call,
  except that a start never builds: see `build`.

`build` (real mode only) builds the six images federation/stack/compose.yaml builds itself (BUILT_IMAGES) once per study run, then, only
after a successful build, writes the run's image pin set to images.json in the state folder: the id of each of the six, and the id of the
operator's Missions service image, which is read and never built. make_config.py writes that pin set into every scenario's provenance,
and the harness checks it at every block. Every compose `up` of the real mode passes --no-build, and `up` refuses, naming the build
command, when one of the six images is missing. The backends are started with --force-recreate: Compose recreates a container only when
its configuration or its image's platform manifest changes, never for a new image id alone, so without it a container made from an
earlier build would keep running that build's image (study/launch/README.md has the cause).

In the real mode `up` first removes every container of the stack's compose project, of every profile, and `down` removes them the same
way instead of only stopping them (decision Q12 of the Job study2_preflight_final): the harness observes every container of the project,
so a stopped container another scenario left (the Apollo router in a Cosmo start, for example) would otherwise be part of what a start
reads, and would read differently after that other scenario ran. The removal is `docker compose --project-name starfleet-federation-stack
... --profile '*' down --remove-orphans` on the stack's own files (every real-mode compose call names the project, so an inherited
COMPOSE_PROJECT_NAME can never point it at another project): it never removes a volume, an image or the Missions service's external network, and never touches the
Missions project. The stack keeps no data in a container: the Assets database lives in memory (tmpfs) and is made again at every start.

The state folder is machine-local and outside the repository: the composed supergraph and the Cosmo execution config go there, so the
committed files are never rewritten. The Assets database passwords are made at random for each `up` unless STACK_ASSETS_DB_ADMIN_PASSWORD
and STACK_ASSETS_DB_SERVICE_PASSWORD are set; they are passed in the environment of the child commands only, and never printed or
written. The script handles no Missions login: the service already holds its own.

Environment: STUDY_LAUNCH_STATE_DIR (instead of --state-dir), STUDY_BASH (Git Bash, for the simulated mode; default: bash on PATH),
PYTHON (the interpreter start.sh and the composition scripts run under; default: this one), APOLLO_ELV2_LICENSE=accept (an Apollo start
needs it: Rover's composition plugin is under the Elastic License 2.0 and the operator accepts it), and the *_HOST_PORT variables of
start.sh. Nothing else is removed: no rm, no volume, no image, no prune.
"""
import argparse
import json
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


# The read-only commands of the harness: the dataset fingerprint and the health of every backend (`fingerprint`, `health`).
STACK_PROJECT = 'starfleet-federation-stack'
MISSIONS_RELEASE = ROOT / 'uss-enterprise' / 'missions' / 'datasets' / 'releases' / '1.2'
SIMULATOR_SERVICE = 'missions-stub'
HEALTH_BACKENDS = {'missions': {'simulated': SIMULATOR_SERVICE, 'real': None}, 'assets': 'assets-service', 'personnel': 'personnel-service'}
STATE_FORMAT = ('{"running":{{json .State.Running}},"status":{{json .State.Status}},'
                '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},"startedAt":{{json .State.StartedAt}}}')

# Outage services: the logical names of the corpus, mapped to compose services of the federation stack.
OUTAGE_SERVICES = {'assets': 'assets-service', 'personnel': 'personnel-service', 'missions': 'missions-stub'}

# The images federation/stack/compose.yaml builds itself (`build:` with an `image:` name), with the compose services that run each; the
# first service is the one `build` names. Every other image of the stack is pinned by digest in that file (a test pins both).
BUILT_IMAGES = {
    'starfleet-federation-stack-assets-service:1.0.0': ('assets-service', 'assets-bootstrap'),
    'starfleet-federation-stack-personnel-service:2.0.0': ('personnel-service',),
    'starfleet-federation-stack-missions-adapter:1.0.0': ('missions-adapter',),
    'starfleet-federation-stack-personnel-adapter:1.0.0': ('personnel-adapter',),
    'starfleet-federation-stack-assets-adapter:1.0.0': ('assets-adapter',),
    'starfleet-federation-stack-mapping-adapter:1.0.0': ('mapping-adapter',),
}
ONE_SHOT_SERVICES = ('assets-bootstrap',)  # restart: "no"; exited with code 0 is its normal completed state
MISSIONS_IMAGE = 'starfleet-missions-service:1.0.0'  # the operator's (uss-enterprise/missions/compose.yaml): read and pinned, never built
PINNED_IMAGES = tuple(BUILT_IMAGES) + (MISSIONS_IMAGE,)
PIN_FILE = 'images.json'
IMAGE_ID = re.compile(r'^sha256:[0-9a-f]{64}$')

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

    def pin_images(self, path):
        self.steps.append(('pin-images', [str(path)], {}))


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
        # The project is named, never left to the environment: an inherited COMPOSE_PROJECT_NAME outranks the file's `name:`, and a
        # removal with --remove-orphans under the Missions project's name would remove the operator's service.
        return ['docker', 'compose', '--project-name', STACK_PROJECT] + files + ['-f', REAL_OVERLAY]
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


def build_command(state_dir):
    return 'python -B study/launch/launch.py build --missions real --state-dir %s' % state_dir


def plan_build(mode, state_dir, environ):
    """Build the six images once, then pin them (and the Missions service image) in the state folder; real mode only."""
    if mode != 'real':
        raise Refused('build is for the real mode; the simulated mode builds its images in federation/stack/start.sh, unchanged')
    plan = Plan()
    env = dict(base_env(state_dir, None, mode), **assets_passwords(environ, placeholder='unused'))
    plan.checks += [('compose-version', None), ('missions-image', None)]
    plan.run(compose_files(mode) + ['build'] + [services[0] for services in BUILT_IMAGES.values()], env)
    plan.pin_images(state_dir / PIN_FILE)
    return plan


def remove_stack(mode):
    """The real mode's removal of every container of the stack's compose project, all profiles: no volume, image or external network."""
    return compose_files(mode) + ['--profile', '*', 'down', '--remove-orphans', '--timeout', '60']


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
    plan.checks += [('compose-version', None), ('images-present', str(state_dir)), ('missions-container', None), ('missions-network', None),
                    ('missions-answers', None), ('ports-free', router_ports(environ, scenario))]
    if router_of(scenario) == 'apollo':
        plan.checks.append(('elv2', None))
    # A clean project first, so a start reads only its own containers; then never a build, and every backend container is made again
    # from the pinned images (see the module text).
    plan.run(remove_stack(mode), env)
    plan.run(compose_files(mode) + ['up', '-d', '--no-build', '--force-recreate', '--wait', '--wait-timeout', '600'] + list(REAL_BACKENDS), env)
    if router_of(scenario) == 'cosmo':
        plan.run([env['PYTHON'], '-B', COMPOSE_EXECUTION_CONFIG, '--out', env['EXECUTION_CONFIG_FILE']], env)
        plan.run(compose_files(mode) + profile(scenario) + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '120', 'cosmo-router'], env)
    else:
        plan.run([env['PYTHON'], '-B', COMPOSE_SUPERGRAPH, '--out', env['SUPERGRAPH_FILE']], env)
        plan.run(compose_files(mode) + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '120', 'router'], env)
    if legacy:
        plan.run(compose_files(mode, legacy=True) + ['up', '-d', '--no-build', '--no-deps', '--wait'] + list(LEGACY_SERVICES[mode]), env)
    return plan


def plan_down(scenario, mode, state_dir, environ):
    plan = Plan()
    env = dict(base_env(state_dir, scenario, mode), **assets_passwords(environ, placeholder='unused'))
    if mode == 'simulated':
        plan.checks.append(('bash', None))
        plan.run(['{bash}', START_SH, 'stop'], env)
    else:
        # Removes the federation stack's containers only; the real Missions service and Oracle keep running.
        plan.run(remove_stack(mode), env)
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
        plan.run(files + ['up', '-d'] + (['--no-build'] if mode == 'real' else []) + ['--no-deps', '--no-recreate', '--wait', target], env)
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

    def oracle_sql(self):
        """(sql, schema, pdb) of the real Missions database, through the preflight's guarded SQLPlus session (SELECT only)."""
        sys.path.insert(0, str(ROOT / 'study' / 'preflight'))
        import preflight  # imported here: preflight imports this module
        env = preflight.oracle_environment()
        return preflight.Machine(env['container']).sql, env['schema'], env['pdb']

    def hash_folder(self, path):
        """The harness's own hash of a dataset folder (study/harness/provenance.py), so it equals the provenance declaration."""
        sys.path.insert(0, str(ROOT / 'study' / 'harness'))
        import provenance
        return provenance.hash_path(path)


def image_id(machine, ref):
    """The id of a local image, as `docker image inspect` gives it (read only), or None when the image does not exist."""
    code, out = machine.read(['docker', 'image', 'inspect', '--format', '{{.Id}}', ref])
    out = out.strip() if code == 0 else ''
    return out if IMAGE_ID.match(out) else None


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
    elif name == 'images-present':
        for ref in BUILT_IMAGES:
            if image_id(machine, ref) is None:
                raise Refused('the image %s is missing: a start never builds; build the images once for this study run first: %s'
                              % (ref, build_command(arg)))
    elif name == 'missions-image':
        if image_id(machine, MISSIONS_IMAGE) is None:
            raise Refused("the operator's Missions service image %s does not exist: the operator builds it with "
                          'uss-enterprise/missions/compose.yaml; this kit only reads it' % MISSIONS_IMAGE)
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


def write_pins(path, machine):
    """Read the id of every pinned image and write the pin set atomically; refuses, writing nothing, when an image cannot be read."""
    images = {}
    for ref in PINNED_IMAGES:
        images[ref] = image_id(machine, ref)
        if images[ref] is None:
            raise Refused('the image %s cannot be read after the build; no pin set was written' % ref)
    pins = {'about': 'The image pin set of one study run, written by study/launch/launch.py build after a successful build: the six images '
                     'the stack builds itself and the operator\'s Missions service image (read, never built). make_config.py writes it into '
                     'every scenario. Machine-local; do not commit it.',
            'schema': 1, 'written_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'images': images}
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with open(temporary, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(pins, handle, indent=2)
        handle.write('\n')
    os.replace(temporary, path)
    return pins


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
            out(('would write: %s' if kind == 'pin-images' else 'would run: %s') % show(argv))
            continue
        if kind == 'pin-images':
            pins = write_pins(argv[0], machine)
            out('wrote %s' % argv[0])
            for ref, value in pins['images'].items():
                out('  %s %s' % (value, ref))
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


def stack_container(machine, service):
    """The id of the federation stack's container of one compose service, or None (docker ps by its compose labels, read only)."""
    code, out = machine.read(['docker', 'ps', '--all', '--quiet', '--filter', 'label=com.docker.compose.project=%s' % STACK_PROJECT,
                              '--filter', 'label=com.docker.compose.service=%s' % service])
    ids = out.split() if code == 0 else []
    return ids[0] if len(ids) == 1 else None


def container_state(machine, ref):
    code, out = machine.read(['docker', 'inspect', '--format', STATE_FORMAT, ref])
    if code != 0:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def fingerprint(mode, machine):
    """{"fingerprint", "session"} of the Missions dataset (see the module text). Raises Refused when it cannot be read."""
    if mode == 'real':
        sys.path.insert(0, str(ROOT / 'study' / 'preflight'))
        import preflight  # imported here: preflight imports this module
        sql, schema, pdb = machine.oracle_sql()
        try:
            reading = preflight.read_data_fingerprint(sql, schema, pdb)
            started = preflight.read_instance_start(sql, pdb)
        except Exception as error:
            raise Refused('the Missions database could not be read: %s' % error)
        if reading['clock'] is None or any(count is None for count in reading['counts'].values()):
            raise Refused('the Missions database gave an incomplete reading: %s' % json.dumps(reading, sort_keys=True))
        return {'fingerprint': 'missions-db:' + preflight.fingerprint_sha256(reading), 'session': 'oracle-instance:' + started,
                'missions': mode, 'reading': reading}
    kind, digest = machine.hash_folder(MISSIONS_RELEASE)
    if kind != 'folder' or not digest:
        raise Refused('the Missions dataset release 1.2 cannot be read at %s' % MISSIONS_RELEASE)
    container = stack_container(machine, SIMULATOR_SERVICE)
    state = container_state(machine, container) if container else None
    if not state or not state.get('startedAt'):
        raise Refused('the Missions simulator (%s) has no container to read its start time from' % SIMULATOR_SERVICE)
    return {'fingerprint': 'missions-release-1.2:' + digest, 'session': '%s:%s' % (SIMULATOR_SERVICE, state['startedAt']), 'missions': mode}


def health(scenario, mode, machine):
    """{"backends": {name: {"up", "detail"}}} of the scenario's three backends (see the module text). Never raises for a backend down."""
    out = {}
    for name, service in HEALTH_BACKENDS.items():
        service = service[mode] if isinstance(service, dict) else service
        ref = MISSIONS_CONTAINER if service is None else stack_container(machine, service)
        label = MISSIONS_CONTAINER if service is None else service
        state = container_state(machine, ref) if ref else None
        if state is None:
            out[name] = {'up': False, 'detail': 'no container of %s' % label}
            continue
        up = state.get('running') is True and state.get('health') in (None, 'healthy')
        detail = '%s is %s%s' % (label, state.get('status'), ', health %s' % state['health'] if state.get('health') else '')
        if up and service is None:
            status = machine.http_status(MISSIONS_PROBE_URL)
            up = status == 200
            detail += ', GET %s answered %s' % (MISSIONS_PROBE_URL, status)
        out[name] = {'up': up, 'detail': detail}
    return {'scenario': scenario, 'missions': mode, 'backends': out}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)

    def common(p):
        p.add_argument('scenario', choices=SCENARIOS)
        p.add_argument('--missions', choices=MODES, required=True, help='the Missions backend: the simulator or the real service on Oracle')
        p.add_argument('--state-dir', help='machine-local folder outside the repository (default: STUDY_LAUNCH_STATE_DIR)')
        p.add_argument('--dry-run', action='store_true', help='print the checks and commands, run nothing')

    build = sub.add_parser('build', help='build the six images once for a study run and write their pin set (real mode)')
    build.add_argument('--missions', choices=MODES, required=True, help='real: the pin set is for the real-mode study')
    build.add_argument('--state-dir', help='machine-local folder outside the repository (default: STUDY_LAUNCH_STATE_DIR)')
    build.add_argument('--dry-run', action='store_true', help='print the checks and commands, run nothing')
    common(sub.add_parser('up', help='start the stack of a scenario (never builds)'))
    common(sub.add_parser('down', help='stop the stack of a scenario (real mode: its containers are removed)'))
    service = sub.add_parser('service', help='stop or start one backend, for a controlled outage')
    service.add_argument('action', choices=('stop', 'start'))
    service.add_argument('service', choices=tuple(OUTAGE_SERVICES))
    common(service)
    reading = sub.add_parser('fingerprint', help='print the dataset fingerprint and the database session (read only)')
    reading.add_argument('--missions', choices=MODES, required=True)
    reading.add_argument('--state-dir', help='accepted for the shape of the other commands; nothing is written')
    common(sub.add_parser('health', help='print the health of every backend of a scenario (read only)'))
    return parser


def main(argv=None, machine=None, environ=None, out=print):
    args = build_parser().parse_args(argv)
    environ = dict(os.environ if environ is None else environ)
    machine = machine or Machine()
    if args.command in ('fingerprint', 'health'):  # read only: no state folder is made or seeded
        try:
            if args.command == 'fingerprint':
                value = fingerprint(args.missions, machine)
            else:
                value = health(args.scenario, args.missions, machine)
        except Refused as error:
            print('launch.py: refused: %s' % error, file=sys.stderr)
            return 1
        out(json.dumps(value, sort_keys=True))
        return 0
    try:
        state = args.state_dir or environ.get('STUDY_LAUNCH_STATE_DIR')
        if not state:
            raise Refused('give --state-dir or set STUDY_LAUNCH_STATE_DIR (a machine-local folder outside the repository)')
        state_dir = outside_repository(state, 'the state folder')
        if args.command == 'build':
            plan = plan_build(args.missions, state_dir, environ)
        elif args.command == 'up':
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
