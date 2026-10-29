"""Run provenance: what each scenario is meant to run against, what it actually runs against, and the check between them.

Declare: the machine-local config gives every scenario a `provenance` block: the compose projects to observe, the intended backends (logical
service, mode `real` or `simulated`, the compose service that serves it, the expected image, the dataset), the expected routing (the
agent-facing upstream endpoints and each adapter's backend URL variables) and the launch files to hash.

Observe: after the stack is ready and before the first paid request, the harness reads the running stack with two read-only commands,
`docker compose -p <project> ps --all --format json` and `docker inspect <containers>`, hashes the datasets, the bind mounts it can read and
the launch files, and records a redacted launch configuration.

Compare: any difference between the declaration and the observation refuses the scenario, naming each difference. On resume the new
observation is also compared with the stored one, and any drift refuses.

Redact: environment values whose names contain PASSWORD, SECRET, TOKEN or KEY are masked, the user:password part of a URL is masked, host
absolute paths are reduced to their last component, and a script is only ever hashed, never copied. Standard library only.
"""
import json
import re
import subprocess
from pathlib import Path

from study_common import child_environment, sha256_bytes, sha256_file, sha256_json, utc_now

SCHEMA = 1
MODES = ('real', 'simulated')
MASK = '[MASKED]'
SECRET_MARKERS = ('PASSWORD', 'SECRET', 'TOKEN', 'KEY')
ROUTING_SUFFIXES = ('_URL', '_HOST', '_PORT')
LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '[::1]')
OBSERVATION_COMMANDS = ['docker compose -p <project> ps --all --format json', 'docker inspect <container id> ...']

_DECLARATION_KEYS = {'compose_projects', 'backends', 'routing', 'launch_files'}
_BACKEND_KEYS = {'mode', 'service', 'image_id', 'image_ref', 'dataset'}
_DATASET_KEYS = {'id', 'path', 'sha256', 'mount'}
_ROUTING_KEYS = {'endpoints', 'env'}
_IMAGE_ID = re.compile(r'^sha256:[0-9a-f]{64}$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_WINDOWS_PATH = re.compile(r'(?:\b[A-Za-z]:[\\/]|\\\\)(?:[^\\/\s"\'<>|;,]+[\\/])*([^\\/\s"\'<>|;,]*)')
_POSIX_PATH = re.compile(r'(?<![\w:/.~<>-])/(?:[^\s/:"\';,]+/)+([^\s/:"\';,]*)')
_URL_USERINFO = re.compile(r'(\b[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@')


class ProvenanceRefused(RuntimeError):
    """The scenario does not run: its observed provenance differs from the declared one, from the stored one, or could not be observed."""

    def __init__(self, scenario, kind, problems):
        self.scenario, self.kind, self.problems = scenario, kind, list(problems)
        super().__init__('Provenance %s in scenario %s, refused before any paid request:\n- %s' % (kind, scenario, '\n- '.join(self.problems)))


# ---------------------------------------------------------------------------------------------------------------- declare
def validate(scenario, block):
    """Refuse a missing or malformed declaration, naming the scenario and the field."""
    where = 'scenario %s: provenance' % scenario
    if not isinstance(block, dict):
        raise ValueError('%s is missing: every scenario declares its intended backends (see study-config.example.json)' % where)
    _known(where, block, _DECLARATION_KEYS)
    projects = block.get('compose_projects')
    if not (isinstance(projects, list) and projects and all(isinstance(p, str) and p for p in projects)):
        raise ValueError('%s.compose_projects must be a non-empty list of compose project names' % where)
    backends = block.get('backends')
    if not (isinstance(backends, dict) and backends):
        raise ValueError('%s.backends must name at least one backend' % where)
    for name, backend in backends.items():
        at = '%s.backends.%s' % (where, name)
        if not isinstance(backend, dict):
            raise ValueError('%s must be an object' % at)
        _known(at, backend, _BACKEND_KEYS)
        if backend.get('mode') not in MODES:
            raise ValueError('%s.mode must be one of %s' % (at, ', '.join(MODES)))
        _text(at + '.service', backend.get('service'))
        if 'image_id' not in backend and 'image_ref' not in backend:
            raise ValueError('%s needs image_id or image_ref (or both)' % at)
        if 'image_id' in backend and not _IMAGE_ID.match(str(backend['image_id'])):
            raise ValueError('%s.image_id must be sha256:<64 lowercase hex>' % at)
        if 'image_ref' in backend:
            _text(at + '.image_ref', backend['image_ref'])
        if 'dataset' in backend:
            dataset = backend['dataset']
            if not isinstance(dataset, dict):
                raise ValueError('%s.dataset must be an object' % at)
            _known(at + '.dataset', dataset, _DATASET_KEYS)
            _text(at + '.dataset.id', dataset.get('id'))
            _text(at + '.dataset.path', dataset.get('path'))
            if not _SHA256.match(str(dataset.get('sha256'))):
                raise ValueError('%s.dataset.sha256 must be 64 lowercase hex' % at)
            if 'mount' in dataset and not (isinstance(dataset['mount'], str) and dataset['mount'].startswith('/')):
                raise ValueError('%s.dataset.mount must be a container path starting with /' % at)
    routing = block.get('routing', {})
    if not isinstance(routing, dict):
        raise ValueError('%s.routing must be an object' % where)
    _known(where + '.routing', routing, _ROUTING_KEYS)
    for url, service in routing.get('endpoints', {}).items():
        if _port_of(url) is None:
            raise ValueError('%s.routing.endpoints: %s is not an http(s) URL' % (where, redact_value(url)))
        if _host_of(url) not in LOOPBACK_HOSTS:
            raise ValueError('%s.routing.endpoints: %s does not name a loopback host (%s); only ports published on this machine can be '
                             'verified' % (where, redact_value(url), ', '.join(LOOPBACK_HOSTS)))
        _text('%s.routing.endpoints[%s]' % (where, url), service)
    for service, variables in routing.get('env', {}).items():
        if not (isinstance(variables, dict) and variables and all(isinstance(v, str) for v in variables.values())):
            raise ValueError('%s.routing.env.%s must map variable names to expected text values' % (where, service))
    files = block.get('launch_files', {})
    if not (isinstance(files, dict) and all(isinstance(v, str) and v for v in files.values())):
        raise ValueError('%s.launch_files must map labels to file paths' % where)


def _known(where, value, allowed):
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError('%s has unknown keys: %s' % (where, ', '.join(unknown)))


def _text(where, value):
    if not (isinstance(value, str) and value):
        raise ValueError('%s must be a non-empty text' % where)


def intended(block):
    """The declaration as the manifest keeps it: host paths reduced, secret-named routing values and URL credentials masked."""
    out = json.loads(json.dumps(block))
    for backend in out['backends'].values():
        if 'dataset' in backend:
            backend['dataset']['path'] = reduce_paths(backend['dataset']['path'])
    out['launch_files'] = {label: reduce_paths(path) for label, path in out.get('launch_files', {}).items()}
    routing = out.get('routing')
    if routing is not None:
        if 'endpoints' in routing:
            routing['endpoints'] = {redact_value(url): service for url, service in routing['endpoints'].items()}
        if 'env' in routing:
            routing['env'] = {service: {name: redact_env(name, value) for name, value in variables.items()}
                              for service, variables in routing['env'].items()}
    return out


# ---------------------------------------------------------------------------------------------------------------- redact
def is_secret_name(name):
    upper = str(name).upper()
    return any(marker in upper for marker in SECRET_MARKERS)


def reduce_paths(text):
    """Host absolute paths in `text` become <path>/<last component>, so nothing written names a folder of the machine."""
    text = _WINDOWS_PATH.sub(lambda m: '<path>/' + m.group(1), str(text))
    return _POSIX_PATH.sub(lambda m: '<path>/' + m.group(1), text)


def redact_value(text):
    return reduce_paths(_URL_USERINFO.sub(lambda m: m.group(1) + MASK + '@', str(text)))


def redact_env(name, value):
    return MASK if is_secret_name(name) else redact_value(value)


def redact_argv(argv):
    """A command line with the value of every secret-named option masked (`--db-password x`, `--db-password=x`) and paths reduced."""
    out, mask_next = [], False
    for arg in argv:
        arg = str(arg)
        if mask_next:
            out.append(MASK)
            mask_next = False
            continue
        if arg.startswith('-') and is_secret_name(arg.split('=', 1)[0]):
            if '=' in arg:
                out.append(arg.split('=', 1)[0] + '=' + MASK)
            else:
                out.append(arg)
                mask_next = True
            continue
        out.append(redact_value(arg))
    return out


def redact_command(command):
    out = {'argv': redact_argv(command.get('argv', []))}
    if command.get('cwd'):
        out['cwd'] = reduce_paths(command['cwd'])
    if command.get('env'):
        out['env'] = {name: redact_env(name, value) for name, value in sorted(command['env'].items())}
    if command.get('background'):
        out['background'] = True
    return out


def launch_configuration(stack):
    """The scenario's stack commands, redacted."""
    stack = stack or {}
    out = {}
    for phase in ('start', 'teardown'):
        out[phase] = [redact_command(c) for c in stack.get(phase, [])]
    for phase in ('stop_service', 'start_service'):
        out[phase] = {name: [redact_command(c) for c in commands] for name, commands in sorted(stack.get(phase, {}).items())}
    return out


# ---------------------------------------------------------------------------------------------------------------- observe
class DockerCli:
    """Runs the two read-only Docker commands and nothing else. The environment has no API keys."""

    def __init__(self, timeout=60, run=subprocess.run):
        self.timeout, self.run = timeout, run

    def __call__(self, argv):
        assert_read_only(argv)
        done = self.run(['docker', *argv], capture_output=True, text=True, encoding='utf-8', env=child_environment(), timeout=self.timeout)
        if done.returncode != 0:
            raise RuntimeError('docker %s failed: %s' % (argv[0], redact_value((done.stderr or done.stdout or '').strip()[-300:])))
        return done.stdout


def assert_read_only(argv):
    argv = list(argv)
    if len(argv) == 7 and argv[:2] == ['compose', '-p'] and argv[3:] == ['ps', '--all', '--format', 'json']:
        return
    if len(argv) >= 2 and argv[0] == 'inspect' and all(not a.startswith('-') for a in argv[1:]):
        return
    raise ValueError('Only docker compose ps and docker inspect are allowed for provenance, not: docker %s' % ' '.join(argv))


def parse_ps(text):
    """`docker compose ps --format json` prints a JSON array (older Compose) or one object per line (newer Compose)."""
    text = (text or '').strip()
    if not text:
        return []
    if text.startswith('['):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def hash_path(path):
    """(kind, sha256) of a file or a folder (a folder hashes the sorted list of its files' relative paths and hashes); (None, None) when
    the path cannot be read from here."""
    path = Path(path)
    try:
        if path.is_file():
            return 'file', sha256_file(path)
        if path.is_dir():
            lines = ['%s\t%s\n' % (p.relative_to(path).as_posix(), sha256_file(p)) for p in sorted(path.rglob('*')) if p.is_file()]
            return 'folder', sha256_bytes(''.join(lines).encode('utf-8'))
    except OSError:
        pass
    return None, None


def _container(doc, wanted_env, hasher):
    config = doc.get('Config') or {}
    env = {}
    for item in config.get('Env') or []:
        name, _, value = item.partition('=')
        if name.endswith(ROUTING_SUFFIXES) or name in wanted_env:
            env[name] = redact_env(name, value)
    ports = []
    for container_port, bindings in sorted(((doc.get('NetworkSettings') or {}).get('Ports') or {}).items()):
        for binding in bindings or []:
            ports.append('%s:%s->%s' % (binding.get('HostIp', ''), binding.get('HostPort', ''), container_port))
    mounts = []
    for mount in doc.get('Mounts') or []:
        if mount.get('Type') != 'bind':
            continue
        kind, digest = hasher(mount.get('Source', ''))
        mounts.append({'destination': mount.get('Destination'), 'readOnly': not mount.get('RW', True), 'kind': kind, 'sha256': digest})
    mounts.sort(key=lambda m: m['destination'] or '')
    return {'state': (doc.get('State') or {}).get('Status'), 'imageRef': config.get('Image'), 'imageId': doc.get('Image'),
            'env': dict(sorted(env.items())), 'ports': sorted(ports), 'mounts': mounts}


def observe(scenario, scenario_config, docker, hasher=hash_path):
    """Read the running stack of one scenario. Returns the observation; `stable` is the part a resume compares, `fingerprint` its hash."""
    block = scenario_config['provenance']
    wanted_env = {name for variables in block.get('routing', {}).get('env', {}).values() for name in variables}
    services, containers = {}, {}
    for project in block['compose_projects']:
        ids = [item.get('ID') for item in parse_ps(docker(['compose', '-p', project, 'ps', '--all', '--format', 'json'])) if item.get('ID')]
        if not ids:
            continue
        for doc in json.loads(docker(['inspect', *ids])):
            labels = (doc.get('Config') or {}).get('Labels') or {}
            key = '%s/%s' % (project, labels.get('com.docker.compose.service') or doc.get('Name', '').lstrip('/'))
            if key in services:
                key += '#' + str(labels.get('com.docker.compose.container-number') or len(services))
            services[key] = _container(doc, wanted_env, hasher)
            containers[key] = doc.get('Name', '').lstrip('/')
    datasets = {}
    for name, backend in sorted(block['backends'].items()):
        if 'dataset' in backend:
            kind, digest = hasher(backend['dataset']['path'])
            datasets[name] = {'id': backend['dataset']['id'], 'kind': kind, 'sha256': digest}
    launch_files = {label: hasher(path)[1] for label, path in sorted(block.get('launch_files', {}).items())}
    mcp_url = scenario_config.get('mcp_url')
    stable = {'mcpUrl': redact_value(mcp_url) if mcp_url is not None else None, 'services': dict(sorted(services.items())), 'datasets': datasets,
              'launchFiles': launch_files, 'launchConfiguration': launch_configuration(scenario_config.get('stack'))}
    return {'schema': SCHEMA, 'scenario': scenario, 'observedAt': utc_now(), 'commands': OBSERVATION_COMMANDS,
            'containers': dict(sorted(containers.items())), 'stable': stable, 'fingerprint': sha256_json(stable)}


# ---------------------------------------------------------------------------------------------------------------- compare
def _resolve(services, name):
    if '/' in name:
        return (name, None) if name in services else (None, 'service %s is not among the observed containers' % name)
    matches = [key for key in services if key.split('/', 1)[1].split('#', 1)[0] == name]
    if not matches:
        return None, 'service %s is not among the observed containers (%s)' % (name, ', '.join(sorted(services)) or 'none')
    if len(matches) > 1:
        return None, 'service %s is ambiguous (%s); name it project/service' % (name, ', '.join(sorted(matches)))
    return matches[0], None


def _host_of(url):
    match = re.match(r'^https?://(?:[^/@]*@)?(\[[^\]]+\]|[^/:]+)', str(url))
    return match.group(1).lower() if match else None


def _serves(binding_ip, host):
    """True when a port published on `binding_ip` answers a request to the loopback `host`."""
    binding_ip = binding_ip.strip('[]')
    if host == '[::1]':
        return binding_ip in ('', '::', '::1')
    if host == '127.0.0.1':
        return binding_ip in ('', '0.0.0.0', '127.0.0.1')
    return binding_ip in ('', '0.0.0.0', '127.0.0.1', '::', '::1')  # localhost resolves to either family


def _port_of(url):
    match = re.match(r'^(https?)://(?:[^/@]*@)?(\[[^\]]+\]|[^/:]+)(?::(\d+))?(?:/|$)', str(url))
    if not match:
        return None
    return int(match.group(3)) if match.group(3) else (443 if match.group(1) == 'https' else 80)


def down_backends(block, observation):
    """The declared backends the observation finds down, one line each: no container serves the backend's service, or its container is
    not running. These are the problems of `compare` that the void-block rule of the schedule treats as a backend down (a declared trigger,
    not a judgement); every other problem stays a mismatch that refuses the block."""
    services = observation['stable']['services']
    down, missing, stopped = [], set(), set()
    for name, backend in sorted(block['backends'].items()):
        key, error = _resolve(services, backend['service'])
        if error and 'is not among the observed containers' in error:
            down.append('backend %s (%s): %s' % (name, backend['mode'], error))
            missing.add(backend['service'])
        elif key is not None and services[key]['state'] != 'running':
            down.append('backend %s (%s): %s is %s, not running' % (name, backend['mode'], key, services[key]['state']))
            stopped.add(key)
    # The routing lines that the same down backends cause: an endpoint or routing variable declared on a backend's service that is
    # missing (the same resolution error), or an endpoint whose service is a stopped backend container (a stopped container publishes no
    # port). A routing line about any other service stays a mismatch.
    routing = block.get('routing', {})
    for url, service in sorted(routing.get('endpoints', {}).items()):
        key, error = _resolve(services, service)
        if (error and service in missing) or (key is not None and key in stopped):
            down.extend(_endpoint_lines(url, services, key, error, caused_by_down=True))
    for service in sorted(routing.get('env', {})):
        key, error = _resolve(services, service)
        if error and service in missing:
            down.append('routing of %s: %s' % (service, error))
    return down


def _endpoint_lines(url, services, key, error, caused_by_down=False):
    """The line compare() writes for one declared endpoint, or none when the endpoint checks out. With `caused_by_down` a host that is
    not a loopback host gives no line: that is a fault of the declaration, not of a backend down, and stays a mismatch."""
    if error:
        return ['endpoint %s: %s' % (redact_value(url), error)]
    port, host = str(_port_of(url)), _host_of(url)
    if host not in LOOPBACK_HOSTS:
        if caused_by_down:
            return []
        return ['endpoint %s: the host %s is not a loopback host, so the endpoint cannot be verified' % (redact_value(url), host)]
    published = [p for p in services[key]['ports'] if p.split('->', 1)[0].rsplit(':', 1)[-1] == port
                 and _serves(p.split('->', 1)[0].rsplit(':', 1)[0], host)]
    if published:
        return []
    return ['endpoint %s: %s does not publish port %s for %s (it publishes %s)' % (
        redact_value(url), key, port, host, ', '.join(services[key]['ports']) or 'nothing')]


def compare(block, observation):
    """Every difference between the declaration and the observation, as one line each. An empty list is a match."""
    stable = observation['stable']
    services = stable['services']
    problems = []
    for name, backend in sorted(block['backends'].items()):
        key, error = _resolve(services, backend['service'])
        if error:
            problems.append('backend %s (%s): %s' % (name, backend['mode'], error))
            continue
        seen = services[key]
        if seen['state'] != 'running':
            problems.append('backend %s (%s): %s is %s, not running' % (name, backend['mode'], key, seen['state']))
        if 'image_id' in backend and seen['imageId'] != backend['image_id']:
            problems.append('backend %s (%s): %s runs image id %s, expected %s' % (name, backend['mode'], key, seen['imageId'], backend['image_id']))
        if 'image_ref' in backend and seen['imageRef'] != backend['image_ref']:
            problems.append('backend %s (%s): %s runs image %s, expected %s' % (name, backend['mode'], key, seen['imageRef'], backend['image_ref']))
        dataset = backend.get('dataset')
        if dataset:
            got = stable['datasets'].get(name, {})
            if got.get('sha256') is None:
                problems.append('backend %s: dataset %s could not be read at %s' % (name, dataset['id'], reduce_paths(dataset['path'])))
            elif got['sha256'] != dataset['sha256']:
                problems.append('backend %s: dataset %s hashes to %s, expected %s' % (name, dataset['id'], got['sha256'], dataset['sha256']))
            if 'mount' in dataset:
                mount = next((m for m in seen['mounts'] if m['destination'] == dataset['mount']), None)
                if mount is None:
                    problems.append('backend %s: %s has no bind mount at %s' % (name, key, dataset['mount']))
                elif mount['sha256'] is None:
                    problems.append('backend %s: the mount %s of %s cannot be read from the harness, so its dataset is unverified; declare no '
                                    'mount when the source is not readable here' % (name, dataset['mount'], key))
                elif mount['sha256'] != dataset['sha256']:
                    problems.append('backend %s: the mount %s of %s hashes to %s, expected %s' % (name, dataset['mount'], key, mount['sha256'],
                                                                                              dataset['sha256']))
    routing = block.get('routing', {})
    for service, variables in sorted(routing.get('env', {}).items()):
        key, error = _resolve(services, service)
        if error:
            problems.append('routing of %s: %s' % (service, error))
            continue
        for variable, expected in sorted(variables.items()):
            seen = services[key]['env'].get(variable)
            want = redact_env(variable, expected)
            if seen != want:
                problems.append('routing of %s: %s is %s, expected %s' % (key, variable, 'unset' if seen is None else seen, want))
    for url, service in sorted(routing.get('endpoints', {}).items()):
        key, error = _resolve(services, service)
        problems.extend(_endpoint_lines(url, services, key, error))
    for label, digest in sorted(stable['launchFiles'].items()):
        if digest is None:
            problems.append('launch file %s could not be read at %s' % (label, reduce_paths(block['launch_files'][label])))
    return problems


def drift(stored, current, prefix=''):
    """The differences between two stable observations (or two declarations), one line each, naming the path of each change."""
    if isinstance(stored, dict) and isinstance(current, dict):
        out = []
        for key in sorted(set(stored) | set(current)):
            where = '%s.%s' % (prefix, key) if prefix else str(key)
            if key not in current:
                out.append('%s: removed (was %s)' % (where, _short(stored[key])))
            elif key not in stored:
                out.append('%s: added (%s)' % (where, _short(current[key])))
            else:
                out.extend(drift(stored[key], current[key], where))
        return out
    if stored != current:
        return ['%s: %s -> %s' % (prefix or '(whole)', _short(stored), _short(current))]
    return []


def _short(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return text if len(text) <= 200 else text[:197] + '...'
