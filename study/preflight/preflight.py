"""The operator preflight of Abstraction ladder study 2: measure and record, one explicit step at a time.

    python -B study/preflight/preflight.py <step> [options] --results <folder> [--run]

Steps (docs/STUDY-2-DESIGN.md, Preflight steps; the README of this folder gives the order and what each needs):
  inventory                    1  the Oracle image by its digest, the service image, the compose memory limit, the disk reserve
  oracle                       2  Oracle's readiness time, its docker stats peak, the vmmem size, host free memory, the SGA and PGA views
  data --login <name>          3  the row counts, the dataset hash and the Missions clock after the operator's reset; the login cannot write
  service --target real|simulated  4  the raw behaviour of the Missions REST interface on 127.0.0.1:8083
  compare <record> <record>    4  the differences between the real service's and the simulator's records, for the decision-L gate
  stack <scenario> --missions real|simulated   5  heavy load, a soak and peak sampling of a stack started with study/launch/launch.py
  outage <scenario> --missions real|simulated --state-dir <folder>   6  stop and restore Assets, Personnel and Missions, timed
  provenance <scenario> --config <study config>   8  the harness's provenance check of the running stack, with no vendor client
  report                          the preflight record: the template filled from the step records

Without --run a step prints what it would do and does nothing. With --run it prints the same, runs, and writes one record into the
results folder, which must be outside the repository; a record is never overwritten. Every step only reads, except `outage`, which
stops and starts services through study/launch/launch.py, and `stack`, which sends read queries to the router and GET requests to
the Missions service. No step provisions, resets, starts or removes Oracle or the Missions service, writes to Oracle, makes a paid
request or changes a file of the stack. Docker is called through an allowlist of read-only forms; SQL is SELECT only, in a read-only
transaction; HTTP is GET only to loopback, plus GraphQL queries (never a mutation) to the router. No credential is read: the one
value taken from a container's environment is the service's login name, MISSIONS_DB_USER. Standard library only.
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'study' / 'launch'))
import launch  # noqa: E402  the kit owns the scenarios, the routers, the outage services and the Missions container's name

TEMPLATE = HERE / 'record-template.json'
ORACLE_ENVIRONMENT = ROOT / 'uss-enterprise' / 'missions' / 'datasets' / 'oracle-environment.json'
RELEASE = ROOT / 'uss-enterprise' / 'missions' / 'datasets' / 'releases' / '1.2'
MISSIONS_COMPOSE = ROOT / 'uss-enterprise' / 'missions' / 'compose.yaml'
HARNESS = ROOT / 'study' / 'harness'

SCHEMA = 1
SERVICE_IMAGE = 'starfleet-missions-service:1.0.0'
SERVICE_CONTAINER = launch.MISSIONS_CONTAINER
MISSIONS_URL = 'http://127.0.0.1:%d' % launch.MISSIONS_HOST_PORT
ROUTER_URLS = {'apollo': 'http://127.0.0.1:8170/', 'cosmo': 'http://127.0.0.1:8171/'}
STACK_PROJECT = 'starfleet-federation-stack'
COMPOSE_PROJECTS = (STACK_PROJECT, launch.MISSIONS_PROJECT)
TABLES = ('MISSIONS', 'MISSION_ASSIGNED_CREW', 'MISSION_PARTICIPANTS', 'MISSION_ASSIGNED_ASSETS', 'MISSION_CHANGES', 'MISSION_CLOCK')
MAPPING_RELEASE = '1.3'
DISK_RESERVE = 20 * 1024 ** 3
SECRET_MARKERS = ('PASSWORD', 'SECRET', 'TOKEN', 'KEY', 'PWD')
MASK = '[MASKED]'
LOGIN = re.compile(r'^[A-Z][A-Z0-9_$#]{0,29}$')

# The heaviest list a client can ask for in one call, as federation/acceptance/shared_suite.py asks it (FULL_PAGE; a test pins it).
FULL_PAGE = ('query($o: Int!, $a: String!, $r: String!) { missions(offset: $o, limit: 100) { missionId title status '
             'assets(release: $a) { localRef assetId mappingOutcome resolution asset { assetId kind name status parentAssetId } } '
             'commandingOfficer(release: $r) { localRef personnelId mappingOutcome resolution personnel { personnelId displayName details { __typename ... on CrewDetails { rank department securityClearance } } } } '
             'crew(release: $r) { localRef personnelId mappingOutcome resolution personnel { personnelId displayName details { __typename ... on CrewDetails { rank department securityClearance } } } } } }')
PAGE_OFFSETS = (0, 100, 200)

# One small read per outage service: it answers with data only when that backend is up.
OUTAGE_PROBES = {
    'missions': ('{ missions(limit: 1) { missionId } }', 'missions'),
    'assets': ('{ asset(assetId: "AST-0004") { assetId } }', 'asset'),
    'personnel': ('{ personnelMembers(limit: 1) { totalCount } }', 'personnelMembers'),
}

# Docker's Go template for the one environment value read: the login name, never the password.
ENV_USER_TEMPLATE = '{{range .Config.Env}}{{if eq (index (split . "=") 0) "MISSIONS_DB_USER"}}{{index (split . "=") 1}}{{end}}{{end}}'
STATE_TEMPLATE = ('{"name":{{json .Name}},"status":{{json .State.Status}},"startedAt":{{json .State.StartedAt}},'
                  '"oomKilled":{{json .State.OOMKilled}},"restarts":{{json .RestartCount}},"image":{{json .Config.Image}}}')


class Refused(Exception):
    """The step refuses to go on; nothing further is run or written."""


def oracle_environment():
    return json.loads(ORACLE_ENVIRONMENT.read_text(encoding='utf-8'))


def template():
    return json.loads(TEMPLATE.read_text(encoding='utf-8'))


def thresholds():
    return {item['id']: item for item in template()['thresholds']}


# ------------------------------------------------------------------------------------------------------------- redaction
_ASSIGNMENT = re.compile(r'(?i)\b([A-Z0-9_.-]*(?:PASSWORD|SECRET|TOKEN|KEY|PWD)[A-Z0-9_.-]*)(\s*[=:]\s*)("[^"]*"|\'[^\']*\'|[^\s,;}\]]+)')
_USERINFO = re.compile(r'(\b[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@')
_IDENTIFIED = re.compile(r'(?i)(\bIDENTIFIED\s+BY\s+)("[^"]*"|\S+)')


def redact_text(text):
    """Mask secret-named assignments, a URL's user:password part and an Oracle password clause."""
    text = _ASSIGNMENT.sub(lambda m: m.group(1) + m.group(2) + MASK, str(text))
    text = _USERINFO.sub(lambda m: m.group(1) + MASK + '@', text)
    return _IDENTIFIED.sub(lambda m: m.group(1) + MASK, text)


def redact(value, key=''):
    """The whole record, redacted: a value under a secret-named key is masked, every text is scanned."""
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    if isinstance(value, str):
        if any(marker in str(key).upper() for marker in SECRET_MARKERS):
            return MASK
        return redact_text(value)
    return value


# ------------------------------------------------------------------------------------------------------------- guards
_FORMAT_FREE = ('{{json .}}', STATE_TEMPLATE, ENV_USER_TEMPLATE)


def assert_docker_read(argv, oracle_container):
    """Refuse every docker command but the read-only forms the steps use (and the SQLPlus session that `sql_script` guards)."""
    argv = [str(a) for a in argv]
    exec_form = ['exec', '--user', 'oracle', '-i', '-e', 'NLS_LANG=.AL32UTF8', oracle_container, 'sqlplus', '-L', '-s', '/ as sysdba']
    if argv == exec_form:
        return
    if argv[:1] == ['ps'] and argv.count('--format') == 1:
        at = argv.index('--format') + 1
        _check_format(argv[at] if at < len(argv) else '')
        rest = argv[1:]
        while rest:
            if rest[0] in ('--all', '--no-trunc', '--quiet'):
                rest = rest[1:]
            elif rest[0] in ('--filter', '--format') and len(rest) > 1:
                rest = rest[2:]
            else:
                raise Refused('docker ps with an option this kit does not use: %s' % rest[0])
        return
    if len(argv) >= 4 and argv[2] == '--format' and (argv[:2] == ['image', 'inspect'] or argv[:2] == ['network', 'inspect']
                                                      or argv[:2] == ['system', 'df'] or argv[:2] == ['stats', '--no-stream']):
        _check_format(argv[3])
        if all(not a.startswith('-') for a in argv[4:]):
            return
    if len(argv) >= 4 and argv[0] == 'inspect' and argv[1] == '--format':
        _check_format(argv[2])
        if all(not a.startswith('-') for a in argv[3:]):
            return
    raise Refused('not a read-only docker command of the preflight: docker %s' % ' '.join(argv))


def _check_format(fmt):
    if 'Env' in fmt and fmt != ENV_USER_TEMPLATE:
        raise Refused('a docker format that reads a container environment is refused: only MISSIONS_DB_USER is read')
    if fmt.strip() == '{{json .}}' or fmt in _FORMAT_FREE:
        return
    if not fmt.startswith('{{') and not fmt.startswith('{"'):
        raise Refused('a docker format must be a Go template, not %r' % fmt)


_SELECT = re.compile(r'(?is)^\s*SELECT\b[^;]*$')
_WRITES = re.compile(r'(?i)\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|GRANT|REVOKE|TRUNCATE|EXECUTE|BEGIN|DECLARE|CALL|COMMIT|LOCK)\b|'
                     r'\bFOR\s+UPDATE\b|\bHOST\b|^\s*[!@]')


def sql_script(select, pdb):
    """The SQLPlus input for one SELECT: settings, the pluggable database, a read-only transaction, the query, a rollback."""
    if not _SELECT.match(select) or _WRITES.search(select):
        raise Refused('only one plain SELECT statement is allowed, not: %s' % select.strip()[:120])
    settings = '\n'.join('SET ' + s for s in ('ECHO OFF', 'FEEDBACK OFF', 'HEADING OFF', 'PAGESIZE 0', 'VERIFY OFF', 'DEFINE OFF',
                                                'LINESIZE 32767', 'TRIMSPOOL ON'))
    return ('WHENEVER OSERROR EXIT FAILURE ROLLBACK\nWHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK\n%s\nALTER SESSION SET CONTAINER = %s;\n'
            'SET TRANSACTION READ ONLY;\n%s;\nROLLBACK;\nEXIT SUCCESS\n' % (settings, pdb, select.strip()))


def loopback(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise Refused('only http URLs on this machine are allowed, not %s' % redact_text(url))
    return url


_OPERATION = re.compile(r'^\s*(query|mutation|subscription)?\s*[A-Za-z_0-9]*\s*(\(|\{)')


def assert_query(query):
    """A GraphQL document of one read operation: an anonymous selection or a `query`, never a mutation or a subscription."""
    match = _OPERATION.match(query)
    if not match or match.group(1) in ('mutation', 'subscription') or re.search(r'\b(mutation|subscription)\s*[A-Za-z_({]', query):
        raise Refused('only GraphQL queries are sent, never a mutation or a subscription')
    return query


def assert_http(method, url, body=None):
    """GET to this machine, or a POST of one GraphQL query to a router; nothing else is sent."""
    loopback(url)
    if method == 'GET' and body is None:
        return
    if method == 'POST' and url in ROUTER_URLS.values():
        try:
            assert_query(json.loads(body.decode('utf-8'))['query'])
        except (AttributeError, KeyError, TypeError, ValueError):
            raise Refused('a POST to the router carries one GraphQL query as JSON')
        return
    raise Refused('only GET requests (and GraphQL queries to the router) are sent, not %s %s' % (method, redact_text(url)))


def assert_launch(argv, scenario, mode, state_dir):
    """The one action of the kit a step runs: launch.py service stop|start <service> for the scenario and mode given."""
    argv = [str(a) for a in argv]
    ok = (len(argv) == 11 and argv[1:4] == ['-B', str(launch.HERE / 'launch.py'), 'service'] and argv[4] in ('stop', 'start')
          and argv[5] in launch.OUTAGE_SERVICES and argv[6:] == [scenario, '--missions', mode, '--state-dir', str(state_dir)])
    if not ok:
        raise Refused('not a launch.py service command of the outage step: %s' % ' '.join(argv))


# ------------------------------------------------------------------------------------------------------------- the machine
class Machine:
    """The real effects, each behind its guard. Tests replace it with a fake."""

    def __init__(self, oracle_container):
        self.oracle_container = oracle_container

    def docker(self, argv, input_text=None, timeout=120):
        assert_docker_read(argv, self.oracle_container)
        done = subprocess.run(['docker', *map(str, argv)], input=input_text, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout)
        return done.returncode, (done.stdout or '').strip(), redact_text((done.stderr or '').strip()[-400:])

    def sql(self, select, pdb):
        code, out, err = self.docker(['exec', '--user', 'oracle', '-i', '-e', 'NLS_LANG=.AL32UTF8', self.oracle_container, 'sqlplus', '-L',
                                      '-s', '/ as sysdba'], input_text=sql_script(select, pdb))
        if code != 0 or re.search(r'(?m)^(ORA-|SP2-|PLS-)', out):
            raise RuntimeError('SQL failed: %s' % redact_text((out + ' ' + err).strip()[-300:]))
        return [line.strip() for line in out.splitlines() if line.strip()]

    def http(self, method, url, headers=None, body=None, timeout=30):
        assert_http(method, url, body)
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data, status, seen = response.read(), response.status, dict(response.headers.items())
        except urllib.error.HTTPError as error:
            data, status, seen = error.read(), error.code, dict(error.headers.items())
        except (OSError, ValueError) as error:
            return None, {}, redact_text(str(error)).encode('utf-8'), time.monotonic() - start
        return status, seen, data, time.monotonic() - start

    def host_free_bytes(self):
        if os.name == 'nt':
            class Status(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong),
                            ('available', ctypes.c_ulonglong), ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                            ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                            ('available_extended', ctypes.c_ulonglong)]
            status = Status()
            status.length = ctypes.sizeof(Status)
            return status.available if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
        try:
            for line in Path('/proc/meminfo').read_text().splitlines():
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) * 1024
        except OSError:
            pass
        return None

    def vmmem_bytes(self):
        """The working set of the Windows vmmem process (WSL 2 and Docker Desktop), or None elsewhere."""
        if os.name != 'nt':
            return None
        done = subprocess.run(['tasklist', '/FO', 'CSV', '/NH', '/FI', 'IMAGENAME eq vmmem*'], capture_output=True, text=True)
        return parse_tasklist(done.stdout) if done.returncode == 0 else None

    def disk_free_bytes(self, path):
        return shutil.disk_usage(path).free

    def launch(self, argv):
        return subprocess.run([str(a) for a in argv]).returncode

    def provenance_docker(self, provenance):
        return provenance.DockerCli()

    def now(self):
        return time.monotonic()

    def wall(self):
        return datetime.now(timezone.utc)

    def sleep(self, seconds):
        time.sleep(seconds)


def parse_tasklist(text):
    total = None
    for line in (text or '').splitlines():
        cells = [c.strip('"') for c in line.split('","')]
        if len(cells) >= 5 and cells[0].lower().startswith('vmmem'):
            digits = re.sub(r'\D', '', cells[4])
            if digits:
                total = (total or 0) + int(digits) * 1024
    return total


_UNITS = {'b': 1, 'kb': 1000, 'mb': 1000 ** 2, 'gb': 1000 ** 3, 'tb': 1000 ** 4,
          'kib': 1024, 'mib': 1024 ** 2, 'gib': 1024 ** 3, 'tib': 1024 ** 4}


def parse_size(text):
    """Bytes of a docker size such as `1.5GiB`, `512MiB` or `120.3kB`; None when it cannot be read."""
    match = re.fullmatch(r'\s*([0-9.]+)\s*([A-Za-z]+)\s*', text or '')
    if not match or match.group(2).lower() not in _UNITS:
        return None
    return int(float(match.group(1)) * _UNITS[match.group(2).lower()])


def parse_started(text):
    """A docker timestamp (RFC 3339, nanoseconds) as an aware datetime, or None."""
    match = re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)', text or '')
    if not match or match.group(1).startswith('0001'):
        return None
    fraction = (match.group(2) or '0')[:6].ljust(6, '0')
    zone = '+00:00' if match.group(3) == 'Z' else match.group(3)
    return datetime.fromisoformat('%s.%s%s' % (match.group(1), fraction, zone))


def gib(value):
    return None if value is None else round(value / 1024 ** 3, 3)


# ------------------------------------------------------------------------------------------------------------- the step frame
class Step:
    """One step's plan, its measurements and its checks. `say` prints a line of the plan; `check` records one comparison."""

    def __init__(self, number, name, args, machine, out):
        self.number, self.name, self.args, self.machine, self.out = number, name, args, machine, out
        self.plan, self.commands, self.measurements, self.checks, self.notes = [], [], {}, [], []

    def say(self, line):
        self.plan.append(line)

    def ran(self, text):
        self.commands.append(redact_text(text))

    def check(self, check_id, text, observed, passed):
        result = 'not-measured' if passed is None else ('pass' if passed else 'fail')
        self.checks.append({'id': check_id, 'text': text, 'observed': observed, 'result': result})

    def docker(self, argv, **kw):
        self.ran('docker ' + ' '.join(map(str, argv)))
        return self.machine.docker(argv, **kw)

    def sql(self, select, pdb):
        self.ran('SQL (read-only transaction): ' + ' '.join(select.split()))
        return self.machine.sql(select, pdb)

    def record(self, started, finished, label=None):
        return redact({'schema': SCHEMA, 'step': self.name, 'stepNumber': self.number, 'label': label,
                       'startedAt': started.isoformat(), 'finishedAt': finished.isoformat(),
                       'host': {'platform': sys.platform, 'python': sys.version.split()[0]},
                       'plan': self.plan, 'commands': self.commands, 'measurements': self.measurements, 'checks': self.checks,
                       'notes': self.notes})


def results_folder(path):
    if not path:
        raise Refused('give --results, a machine-local folder outside the repository')
    folder = Path(path).resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise Refused('the results folder must be outside the repository, not %s' % folder)
    return folder


def write_record(folder, record, stamp):
    """Write the record as a new file; an existing file is never overwritten."""
    folder.mkdir(parents=True, exist_ok=True)
    label = ('-' + re.sub(r'[^a-z0-9-]+', '-', record['label'].lower())) if record.get('label') else ''
    name = '%02d-%s%s-%s.json' % (record['stepNumber'], record['step'], label, stamp)
    path = folder / name
    try:
        with open(path, 'x', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=False, ensure_ascii=False) + '\n')
    except FileExistsError:
        raise Refused('the record %s exists already and is never overwritten; run the step again' % name)
    return path


# ------------------------------------------------------------------------------------------------------------- step 1: inventory
def plan_inventory(step):
    env = oracle_environment()
    step.say('read the Oracle image %s@%s with docker image inspect' % (env['image'], env['digest']))
    step.say('read the service image %s with docker image inspect (absent until the operator builds it)' % SERVICE_IMAGE)
    step.say('read mem_limit and JAVA_TOOL_OPTIONS of uss-enterprise/missions/compose.yaml')
    step.say('read docker system df and the free disk at %s (the reserve is 20 GiB)' % (step.args.disk_path or 'the results folder'))


def run_inventory(step):
    env = oracle_environment()
    pinned = '%s@%s' % (env['image'], env['digest'])
    code, out, err = step.docker(['image', 'inspect', '--format', '{"id":{{json .Id}},"repoDigests":{{json .RepoDigests}},"size":{{json .Size}}}',
                                  pinned])
    oracle = json.loads(out) if code == 0 and out else None
    digests = (oracle or {}).get('repoDigests') or []
    present = any(d.endswith('@' + env['digest']) for d in digests)
    step.measurements['oracleImage'] = {'pinned': pinned, 'present': present, 'id': (oracle or {}).get('id'),
                                        'sizeGiB': gib((oracle or {}).get('size')), 'error': None if code == 0 else err}
    step.check('oracle-digest', 'the Oracle image is present by its pinned digest', present, present)
    code, out, err = step.docker(['image', 'inspect', '--format', '{"id":{{json .Id}},"created":{{json .Created}},"size":{{json .Size}}}',
                                  SERVICE_IMAGE])
    service = json.loads(out) if code == 0 and out else None
    step.measurements['serviceImage'] = {'ref': SERVICE_IMAGE, 'present': service is not None, 'id': (service or {}).get('id'),
                                         'created': (service or {}).get('created'), 'sizeGiB': gib((service or {}).get('size'))}
    step.check('service-image', 'the service image exists (the operator builds it)', service is not None, service is not None)
    limit = compose_limits(MISSIONS_COMPOSE.read_text(encoding='utf-8'))
    step.measurements['composeLimits'] = limit
    step.check('memory-limit', 'the Missions compose file sets mem_limit 768m (the separate memory-limit Job)', limit['mem_limit'],
               limit['mem_limit'] == '768m')
    if limit['mem_limit'] is None:
        step.notes.append('The Missions compose file sets no memory limit yet: the memory-limit Job has not landed.')
    code, out, err = step.docker(['system', 'df', '--format', '{{json .}}'])
    step.measurements['dockerSystemDf'] = [json.loads(line) for line in out.splitlines() if line.strip()] if code == 0 else err
    target = existing_ancestor(step.args.disk_path or step.args.results_dir)
    step.measurements['diskPath'] = target.name or str(target.anchor)
    free = step.machine.disk_free_bytes(str(target))
    step.measurements['diskFreeGiB'] = gib(free)
    step.check('disk-reserve', 'at least 20 GiB free for images and the database', gib(free), free >= DISK_RESERVE)


def existing_ancestor(path):
    """The folder itself, or its nearest existing parent: the results folder may not exist yet at the first step."""
    path = Path(path).resolve()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def compose_limits(text):
    """mem_limit and the JAVA_TOOL_OPTIONS value of the service in the Missions compose file, None where absent."""
    found = {}
    for key in ('mem_limit', 'JAVA_TOOL_OPTIONS'):
        match = re.search(r'(?m)^\s+%s:\s*"?([^"\n#]+?)"?\s*(?:#.*)?$' % re.escape(key), text)
        found[key] = match.group(1).strip() if match else None
    return found


# ------------------------------------------------------------------------------------------------------------- step 2: oracle
def plan_oracle(step):
    env = oracle_environment()
    step.say('read the state of the container %s (status, start time, OOM, restarts)' % env['container'])
    step.say('ask SELECT 1 FROM dual every %d s until it answers, at most %d s after the start (the pinned ready timeout)'
             % (step.args.interval, env['readyTimeoutSeconds']))
    step.say('sample docker stats, the vmmem size and host free memory every %d s for %d s' % (step.args.interval, step.args.window))
    step.say('read v$sgainfo and v$pgastat')


def container_state(step, name):
    code, out, err = step.docker(['inspect', '--format', STATE_TEMPLATE, name])
    if code != 0 or not out:
        return None
    return json.loads(out.splitlines()[0])


def run_oracle(step):
    env, machine = oracle_environment(), step.machine
    state = container_state(step, env['container'])
    if state is None or state['status'] != 'running':
        raise Refused('the Oracle container %s is not running: the operator starts it first (missions_operator.py)' % env['container'])
    started = parse_started(state['startedAt'])
    deadline = machine.now() + env['readyTimeoutSeconds']
    polls, ready_at = 0, None
    while True:
        polls += 1
        try:
            if step.sql('SELECT 1 FROM dual', env['pdb']) == ['1']:
                ready_at = machine.wall()
                break
        except RuntimeError:
            pass
        if machine.now() >= deadline:
            break
        machine.sleep(step.args.interval)
    seconds = (ready_at - started).total_seconds() if ready_at and started else None
    first_poll = polls == 1
    step.measurements['readiness'] = {'startedAt': state['startedAt'], 'readyAt': ready_at.isoformat() if ready_at else None,
                                      'seconds': None if seconds is None else round(seconds, 1), 'polls': polls,
                                      'upperBound': first_poll}
    if first_poll:
        step.notes.append('Oracle answered at the first poll: the readiness time is an upper bound (the time since the start).')
    limit = thresholds()['oracle-ready']['maxSeconds']
    passed = False if ready_at is None else (None if seconds is None else seconds <= limit)
    step.check('oracle-ready', 'Oracle ready within 15 minutes', step.measurements['readiness']['seconds'], passed)
    samples = sample(step, [env['container']], step.args.window, step.args.interval)
    step.measurements['samples'] = samples
    step.measurements['peaks'] = peaks(samples)
    after = container_state(step, env['container'])
    step.measurements['after'] = after
    step.check('oracle-no-oom', 'no OOM kill and no restart of Oracle', after,
               bool(after) and not after['oomKilled'] and after['restarts'] == state['restarts'] and after['startedAt'] == state['startedAt'])
    sga = [line.split('|') for line in step.sql("SELECT name||'|'||bytes FROM v$sgainfo", env['pdb'])]
    pga = [line.split('|') for line in step.sql("SELECT name||'|'||value||'|'||unit FROM v$pgastat WHERE name IN "
                                                "('total PGA allocated','maximum PGA allocated','aggregate PGA target parameter')", env['pdb'])]
    step.measurements['sga'] = {row[0]: int(row[1]) for row in sga if len(row) == 2 and row[1].isdigit()}
    step.measurements['pga'] = {row[0]: {'value': int(row[1]) if row[1].isdigit() else row[1], 'unit': row[2]} for row in pga if len(row) == 3}


def stats_once(step, names):
    code, out, err = step.docker(['stats', '--no-stream', '--format', '{{json .}}', *names])
    rows = {}
    if code == 0:
        for line in out.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            used = parse_size((item.get('MemUsage') or '').split('/')[0])
            rows[item.get('Name') or item.get('Container')] = used
    return rows


def sample_once(step, names):
    """One sample. It is complete only when docker stats gave a readable size for every container asked; an incomplete sample has
    no total, so a failed or partial reading can never pass as a low peak."""
    machine = step.machine
    rows = stats_once(step, names)
    complete = bool(names) and all(rows.get(name) is not None for name in names)
    return {'at': machine.wall().isoformat(), 'containers': rows, 'complete': complete,
            'totalBytes': sum(rows[name] for name in names) if complete else None,
            'hostFreeBytes': machine.host_free_bytes(), 'vmmemBytes': machine.vmmem_bytes()}


def sample(step, names, window, interval):
    machine, samples = step.machine, []
    end = machine.now() + window
    while True:
        samples.append(sample_once(step, names))
        if machine.now() >= end:
            return samples
        machine.sleep(interval)


def peaks(samples):
    per = {}
    for s in samples:
        for name, used in s['containers'].items():
            if used is not None:
                per[name] = max(per.get(name, 0), used)
    totals = [s['totalBytes'] for s in samples if s['totalBytes'] is not None]
    free = [s['hostFreeBytes'] for s in samples if s['hostFreeBytes'] is not None]
    vmmem = [s['vmmemBytes'] for s in samples if s['vmmemBytes'] is not None]
    return {'perContainerGiB': {k: gib(v) for k, v in sorted(per.items())}, 'totalGiB': gib(max(totals)) if totals else None,
            'hostFreeMinGiB': gib(min(free)) if free else None, 'vmmemMaxGiB': gib(max(vmmem)) if vmmem else None,
            'samples': len(samples), 'incompleteSamples': sum(1 for s in samples if not s['complete']),
            'samplesWithoutHostFree': sum(1 for s in samples if s['hostFreeBytes'] is None)}


def memory_checks(step, samples, top):
    """The two memory thresholds. A sample with a missing reading leaves its threshold not measured, never passed."""
    limits = thresholds()
    if not samples or top['incompleteSamples']:
        peak_passed = None
    else:
        peak_passed = max(s['totalBytes'] for s in samples) < limits['docker-peak']['limitBytes']
    if not samples or top['samplesWithoutHostFree']:
        free_passed = None
    else:
        free_passed = min(s['hostFreeBytes'] for s in samples) >= limits['host-free-min']['minBytes']
    step.check('docker-peak', limits['docker-peak']['text'],
               {'totalGiB': top['totalGiB'], 'incompleteSamples': top['incompleteSamples'], 'samples': top['samples']}, peak_passed)
    step.check('host-free-min', limits['host-free-min']['text'],
               {'hostFreeMinGiB': top['hostFreeMinGiB'], 'samplesWithoutHostFree': top['samplesWithoutHostFree']}, free_passed)
    if top['incompleteSamples']:
        step.notes.append('%d of %d memory samples are incomplete (docker stats failed or left a container out): the Docker peak is not '
                          'measured.' % (top['incompleteSamples'], top['samples']))


# ------------------------------------------------------------------------------------------------------------- step 3: data
def expected_release():
    """The counts and hash that the committed release 1.2 gives, from its own files."""
    manifest = json.loads((RELEASE / 'manifest.json').read_text(encoding='utf-8'))
    raw = (RELEASE / 'release.json').read_bytes()
    data = json.loads(raw.decode('utf-8'))
    missions = data['missions']
    return {'datasetVersion': manifest['datasetVersion'], 'releaseSha256': manifest['files']['release.json'],
            'committedReleaseSha256': hashlib.sha256(raw).hexdigest(), 'baseline': manifest['clock']['baseline'],
            'counts': {'MISSIONS': len(missions), 'MISSION_CHANGES': len(data['changes']),
                       'MISSION_ASSIGNED_CREW': sum(len(m['assignedCrewIds']) for m in missions),
                       'MISSION_PARTICIPANTS': sum(len(m['participantIds']) for m in missions),
                       'MISSION_ASSIGNED_ASSETS': sum(len(m['assignedAssetIds']) for m in missions), 'MISSION_CLOCK': 1}}


def login_name(text):
    name = (text or '').strip().upper()
    if not LOGIN.match(name):
        raise Refused('the login must be an Oracle user name (letters, digits, _ $ #, at most 30), not %r' % text)
    return name


def plan_data(step):
    env = oracle_environment()
    step.say('count the rows of the six tables of %s and read the clock row (version, release hash, counter, baseline)' % env['schema'])
    step.say('read the largest change id and lastUpdated, the fingerprint the Missions clock check compares')
    step.say('read the system privileges, roles and table privileges of the login %s' % step.args.login)
    step.say('read MISSIONS_DB_USER (and nothing else of its environment) of the container %s' % SERVICE_CONTAINER)
    if step.args.compare_to:
        step.say('compare the fingerprint with the record %s' % Path(step.args.compare_to).name)


def read_data_fingerprint(sql, schema, pdb):
    """The data fingerprint of the Missions schema, read with `sql(select, pdb)` (SELECT only, in a read-only transaction): the row counts
    of the six tables, the clock row, and the largest change id and lastUpdated. The data step records it, and the launch kit's
    `launch.py fingerprint` prints its hash at every block start of study 2."""
    counts = {}
    for table in TABLES:
        rows = sql('SELECT COUNT(*) FROM %s.%s' % (schema, table), pdb)
        counts[table] = int(rows[0]) if rows and rows[0].isdigit() else None
    clock = sql("SELECT dataset_version||'|'||release_sha256||'|'||counter||'|'||TO_CHAR(baseline,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"') "
                "FROM %s.mission_clock" % schema, pdb)
    parts = clock[0].split('|') if clock else []
    clock_row = dict(zip(('datasetVersion', 'releaseSha256', 'counter', 'baseline'), parts)) if len(parts) == 4 else None
    tops = sql("SELECT MAX(current_change_id)||'|'||TO_CHAR(MAX(last_updated),'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"') FROM %s.missions"
               % schema, pdb)
    top_change, top_updated = (tops[0].split('|') + [None, None])[:2] if tops else (None, None)
    return {'counts': counts, 'clock': clock_row, 'maxCurrentChangeId': top_change, 'maxLastUpdated': top_updated}


def fingerprint_sha256(fingerprint):
    return hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode('utf-8')).hexdigest()


def read_instance_start(sql, pdb):
    """The start time of the Oracle instance (v$instance), which names one continuous run of the database: the session of study 2."""
    rows = sql("SELECT TO_CHAR(startup_time,'YYYY-MM-DD\"T\"HH24:MI:SS') FROM v$instance", pdb)
    if not rows:
        raise RuntimeError('the instance start time could not be read')
    return rows[0]


def run_data(step):
    env = oracle_environment()
    schema, pdb, login = env['schema'], env['pdb'], login_name(step.args.login)
    expected = expected_release()
    step.measurements['expected'] = expected
    step.check('release-file', 'the committed release.json hashes to its manifest entry', expected['committedReleaseSha256'],
               expected['committedReleaseSha256'] == expected['releaseSha256'])
    fingerprint = read_data_fingerprint(step.sql, schema, pdb)
    counts, clock_row = fingerprint['counts'], fingerprint['clock']
    step.measurements['counts'] = counts
    step.check('row-counts', 'the six tables hold the counts of release 1.2', counts, counts == expected['counts'])
    step.measurements['clock'] = clock_row
    step.check('dataset-hash', 'the clock row names release 1.2 and its hash', clock_row,
               bool(clock_row) and clock_row['datasetVersion'] == expected['datasetVersion'] and clock_row['releaseSha256'] == expected['releaseSha256'])
    step.check('clock-unmoved', 'the Missions clock counter is 0: no write since the reset', None if not clock_row else clock_row['counter'],
               None if not clock_row else clock_row['counter'] == '0')
    step.measurements['fingerprint'] = fingerprint
    step.measurements['fingerprintSha256'] = fingerprint_sha256(fingerprint)
    if step.args.compare_to:
        earlier = json.loads(Path(step.args.compare_to).read_text(encoding='utf-8'))
        before = (earlier.get('measurements') or {}).get('fingerprintSha256')
        step.check('clock-check', 'the data fingerprint equals the earlier record (before and after a block)',
                   {'before': before, 'after': step.measurements['fingerprintSha256']}, before == step.measurements['fingerprintSha256'])
    privileges = {
        'system': step.sql("SELECT privilege FROM dba_sys_privs WHERE grantee='%s'" % login, pdb),
        'roles': step.sql("SELECT granted_role FROM dba_role_privs WHERE grantee='%s'" % login, pdb),
        'tables': step.sql("SELECT owner||'.'||table_name||'|'||privilege FROM dba_tab_privs WHERE grantee='%s'" % login, pdb),
    }
    step.measurements['login'] = {'name': login, 'privileges': privileges}
    step.check('login-read-only', 'the login has CREATE SESSION, no role and SELECT only, on the six tables only', privileges,
               read_only(privileges, schema))
    code, out, _ = step.docker(['inspect', '--format', ENV_USER_TEMPLATE, SERVICE_CONTAINER])
    in_use = out.strip().upper() if code == 0 and out.strip() else None
    step.measurements['login']['serviceContainerUser'] = in_use
    step.check('login-in-use', 'the service container uses this login', in_use, None if in_use is None else in_use == login)


def read_only(privileges, schema):
    allowed = {'%s.%s' % (schema, table) for table in TABLES}
    tables = [row.split('|') for row in privileges['tables']]
    return (sorted(privileges['system']) == ['CREATE SESSION'] and not privileges['roles'] and bool(tables)
            and all(len(row) == 2 and row[1] == 'SELECT' and row[0] in allowed for row in tables))


# ------------------------------------------------------------------------------------------------------------- step 4: service
UNKNOWN_ID = 'ST-ZZZZZZZZZ'
PROBES = (
    ('list-default', '/missions', {}),
    ('list-size-1', '/missions?pageSize=1', {}),
    ('list-beyond-end', '/missions?page=7&pageSize=50', {}),
    ('list-size-0', '/missions?pageSize=0', {}),
    ('list-size-51', '/missions?pageSize=51', {}),
    ('list-page-0', '/missions?page=0', {}),
    ('list-page-text', '/missions?page=abc', {}),
    ('list-page-repeated', '/missions?page=1&page=2', {}),
    ('list-unknown-param', '/missions?colour=red', {}),
    ('list-bad-status', '/missions?status=NOTASTATUS', {}),
    ('list-filter-active', '/missions?status=ACTIVE&pageSize=50', {}),
    ('list-no-match', '/missions?status=ACTIVE&priority=1&type=MAINTENANCE&classification=TOP_SECRET', {}),
    ('one-known', '/missions/{first}', {}),
    ('one-unknown', '/missions/' + UNKNOWN_ID, {}),
    ('one-malformed', '/missions/not-an-id', {}),
    ('changes-known', '/missions/{first}/changes', {}),
    ('changes-size-1', '/missions/{first}/changes?pageSize=1', {}),
    ('changes-unknown', '/missions/%s/changes' % UNKNOWN_ID, {}),
    ('path-unknown', '/nope', {}),
    ('path-trailing-slash', '/missions/', {}),
    ('path-root', '/', {}),
    ('accept-json', '/missions?pageSize=1', {'Accept': 'application/json'}),
    ('accept-xml', '/missions?pageSize=1', {'Accept': 'application/xml'}),
    ('accept-any', '/missions?pageSize=1', {'Accept': '*/*'}),
)
VARIABLE_HEADERS = ('date', 'keep-alive', 'connection')


def plan_service(step):
    base = loopback(step.args.base_url)
    step.say('walk GET %s/missions?page=1..6&pageSize=50 and count the missions (300 expected)' % base)
    for probe_id, path, headers in PROBES:
        step.say('GET %s%s%s  [%s]' % (base, path, ' with ' + json.dumps(headers) if headers else '', probe_id))
    step.say('only GET is sent: the requests change nothing in Oracle')


def summary(status, headers, body):
    text = body.decode('utf-8', 'replace')
    found = {name: (re.search(r'<%s>([^<]*)</%s>' % (name, name), text) or [None, None])[1]
             for name in ('code', 'page', 'pageSize', 'totalCount', 'totalPages')}
    return {'status': status, 'headers': {k.lower(): v for k, v in sorted(headers.items()) if k.lower() not in VARIABLE_HEADERS},
            'bodyBytes': len(body), 'bodySha256': hashlib.sha256(body).hexdigest(), 'body': text[:2000],
            'errorCode': found['code'], 'paging': {k: found[k] for k in ('page', 'pageSize', 'totalCount', 'totalPages')},
            'missionCount': len(re.findall(r'<mission>', text))}


def run_service(step):
    base, machine = loopback(step.args.base_url), step.machine
    ids, walk = [], []
    for page in range(1, 7):
        url = '%s/missions?page=%d&pageSize=50' % (base, page)
        step.ran('GET ' + url)
        status, headers, body, seconds = machine.http('GET', url)
        found = re.findall(r'<missionId>([^<]+)</missionId>', body.decode('utf-8', 'replace'))
        walk.append({'page': page, 'status': status, 'missions': len(found), 'seconds': round(seconds, 4)})
        ids += found
    step.ran('GET %s/missions?pageSize=1' % base)
    total = summary(*machine.http('GET', base + '/missions?pageSize=1')[:3])['paging']['totalCount']
    step.measurements['walk'] = {'pages': walk, 'missions': len(ids), 'totalCount': total,
                                 'idsSha256': hashlib.sha256('\n'.join(ids).encode('utf-8')).hexdigest()}
    step.check('three-hundred', 'GET /missions lists 300 missions', {'walked': len(ids), 'totalCount': total},
               len(ids) == 300 and total == '300')
    first = ids[0] if ids else UNKNOWN_ID
    probes = {}
    for probe_id, path, headers in PROBES:
        url = base + path.replace('{first}', first)
        step.ran('GET ' + url + (' ' + json.dumps(headers) if headers else ''))
        status, seen, body, seconds = machine.http('GET', url, headers=headers)
        probes[probe_id] = dict(summary(status, seen, body), url=path, seconds=round(seconds, 4))
    step.measurements['probes'] = probes
    step.measurements['target'] = step.args.target
    step.notes.append('HEAD is not probed: this kit sends GET only, while the raw MCP tool also allows HEAD (study/mcp/raw_server.py).')


def compare_records(a, b):
    """The differences between two service records, one entry each, with the empty slots of the decision-L gate."""
    differences = []
    left, right = a['measurements'], b['measurements']
    for key in ('missions', 'totalCount', 'idsSha256'):
        if left['walk'].get(key) != right['walk'].get(key):
            differences.append({'probe': 'walk', 'aspect': key, left['target']: left['walk'].get(key), right['target']: right['walk'].get(key)})
    for probe_id in sorted(set(left['probes']) | set(right['probes'])):
        one, two = left['probes'].get(probe_id), right['probes'].get(probe_id)
        if one is None or two is None:
            differences.append({'probe': probe_id, 'aspect': 'missing', left['target']: one is not None, right['target']: two is not None})
            continue
        for aspect in ('status', 'errorCode', 'paging', 'missionCount'):
            if one[aspect] != two[aspect]:
                differences.append({'probe': probe_id, 'aspect': aspect, left['target']: one[aspect], right['target']: two[aspect]})
        for name in sorted(set(one['headers']) | set(two['headers'])):
            if one['headers'].get(name) != two['headers'].get(name):
                differences.append({'probe': probe_id, 'aspect': 'header ' + name, left['target']: one['headers'].get(name),
                                    right['target']: two['headers'].get(name)})
        if one['bodySha256'] != two['bodySha256'] and one['status'] == two['status']:
            differences.append({'probe': probe_id, 'aspect': 'body', left['target']: one['bodySha256'][:12], right['target']: two['bodySha256'][:12]})
    for item in differences:
        item.update({'affects': {'contracts': None, 'toolBehaviour': None, 'guideAccuracy': None, 'answerability': None, 'expectedAnswers': None},
                     'evidence': [a.get('label'), b.get('label')], 'fix': None, 'smokeRerun': None, 'explained': None})
    return differences


def latency(left, right):
    out = {}
    for name, record in (('a', left), ('b', right)):
        values = [p['seconds'] for p in record['measurements']['probes'].values()] + [p['seconds'] for p in record['measurements']['walk']['pages']]
        out[record['measurements']['target']] = spread(values)
    return out


# ------------------------------------------------------------------------------------------------------------- step 5: stack
def spread(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return {'count': len(values), 'min': round(values[0], 4), 'median': round(statistics.median(values), 4),
            'p95': round(values[min(len(values) - 1, int(0.95 * len(values)))], 4), 'max': round(values[-1], 4)}


def graphql(step, router, query, variables=None, timeout=30):
    assert_query(query)
    body = json.dumps({'query': query, 'variables': variables or {}}).encode('utf-8')
    status, _, data, seconds = step.machine.http('POST', router, headers={'Content-Type': 'application/json'}, body=body, timeout=timeout)
    try:
        parsed = json.loads(data.decode('utf-8')) if data else None
    except ValueError:
        parsed = None
    return status, parsed, seconds


def stack_containers(step):
    names = []
    for project in COMPOSE_PROJECTS:
        code, out, _ = step.docker(['ps', '--filter', 'label=com.docker.compose.project=%s' % project, '--format', '{{.Names}}'])
        names += [line.strip() for line in out.splitlines() if code == 0 and line.strip()]
    env = oracle_environment()
    code, out, _ = step.docker(['ps', '--filter', 'name=^%s$' % env['container'], '--format', '{{.Names}}'])
    names += [line.strip() for line in out.splitlines() if code == 0 and line.strip()]
    return sorted(set(names))


def plan_stack(step):
    router = ROUTER_URLS[launch.router_of(step.args.scenario)]
    step.say('check that the %s router answers on %s (the operator started the stack with launch.py up %s --missions %s)'
             % (launch.router_of(step.args.scenario), router, step.args.scenario, step.args.missions))
    step.say('read the state of every container of %s and of Oracle, before and after' % ', '.join(COMPOSE_PROJECTS))
    step.say('heavy load: the full page (100 missions with assets, commanding officer and crew) at offsets 0, 100, 200, %d times'
             % step.args.heavy_repeats)
    step.say('soak for %d minutes: the full pages in turn and GET %s/missions?page=1..6&pageSize=50, sampling docker stats, vmmem and host '
             'free memory every %d s' % (step.args.minutes, MISSIONS_URL, step.args.interval))
    step.say('only GraphQL queries and GET requests are sent')


def run_stack(step):
    machine, router = step.machine, ROUTER_URLS[launch.router_of(step.args.scenario)]
    status, parsed, _ = graphql(step, router, '{ __typename }')
    if status != 200:
        raise Refused('the router does not answer on %s (status %s): start the stack first with study/launch/launch.py up' % (router, status))
    names = stack_containers(step)
    before = {name: container_state(step, name) for name in names}
    step.measurements['containersBefore'] = before
    variables = {'a': MAPPING_RELEASE, 'r': MAPPING_RELEASE}
    heavy, errors = [], 0
    for _ in range(step.args.heavy_repeats):
        for offset in PAGE_OFFSETS:
            status, parsed, seconds = graphql(step, router, FULL_PAGE, dict(variables, o=offset), timeout=60)
            bad = status != 200 or not parsed or parsed.get('errors') or not (parsed.get('data') or {}).get('missions')
            errors += 1 if bad else 0
            heavy.append(seconds)
    step.ran('POST %s FULL_PAGE x %d' % (router, step.args.heavy_repeats * len(PAGE_OFFSETS)))
    step.measurements['heavy'] = {'latency': spread(heavy), 'errors': errors}
    samples, router_times, rest_times, soak_errors, cycle = [], [], [], 0, 0
    end = machine.now() + step.args.minutes * 60
    next_sample = machine.now()
    while machine.now() < end:
        offset = PAGE_OFFSETS[cycle % len(PAGE_OFFSETS)]
        status, parsed, seconds = graphql(step, router, FULL_PAGE, dict(variables, o=offset), timeout=60)
        soak_errors += 1 if status != 200 or not parsed or parsed.get('errors') else 0
        router_times.append(seconds)
        status, _, _, seconds = machine.http('GET', '%s/missions?page=%d&pageSize=50' % (MISSIONS_URL, cycle % 6 + 1))
        soak_errors += 1 if status != 200 else 0
        rest_times.append(seconds)
        cycle += 1
        if machine.now() >= next_sample:
            samples.append(sample_once(step, names))
            next_sample = machine.now() + step.args.interval
    step.ran('soak: %d cycles of one full page and one GET %s/missions page' % (cycle, MISSIONS_URL))
    samples.append(sample_once(step, names))
    top = peaks(samples)
    step.measurements.update({'scenario': step.args.scenario, 'missions': step.args.missions, 'soakMinutes': step.args.minutes,
                              'soak': {'cycles': cycle, 'errors': soak_errors, 'routerLatency': spread(router_times),
                                       'missionsRestLatency': spread(rest_times)},
                              'samples': samples, 'peaks': top})
    after = {name: container_state(step, name) for name in names}
    step.measurements['containersAfter'] = after
    changed = sorted(name for name in names if not after.get(name) or not before.get(name) or after[name]['oomKilled']
                     or after[name]['restarts'] != before[name]['restarts'] or after[name]['startedAt'] != before[name]['startedAt']
                     or after[name]['status'] != 'running')
    memory_checks(step, samples, top)
    step.check('no-oom-restart', thresholds()['no-oom-restart']['text'], changed, not changed)
    step.check('load-errors', 'every heavy and soak request answered without an error', errors + soak_errors, errors + soak_errors == 0)
    step.notes.append('The acceptance list A and the adapter gates are not run by this step: the operator runs them with their own commands '
                      '(README of this folder).')


# ------------------------------------------------------------------------------------------------------------- step 6: outage
def launch_argv(action, service, args, state_dir):
    return [sys.executable, '-B', str(launch.HERE / 'launch.py'), 'service', action, service, args.scenario, '--missions', args.missions,
            '--state-dir', str(state_dir)]


def plan_outage(step):
    state_dir = launch.outside_repository(step.args.state_dir, 'the state folder')
    router = ROUTER_URLS[launch.router_of(step.args.scenario)]
    for service in step.args.services:
        query = OUTAGE_PROBES[service][0]
        step.say('probe %s through %s with %s' % (service, router, query))
        for action in ('stop', 'start'):
            step.say('run: ' + ' '.join(launch_argv(action, service, step.args, state_dir)))
        step.say('time until the probe answers again, at most %d s; the router is never restarted by this step' % step.args.timeout)


def probe_ok(step, router, service):
    query, field = OUTAGE_PROBES[service]
    status, parsed, seconds = graphql(step, router, query, timeout=10)
    data = (parsed or {}).get('data') or {}
    return status == 200 and not (parsed or {}).get('errors') and data.get(field) not in (None, []), seconds


def wait_for(step, router, service, want, timeout):
    machine = step.machine
    start = machine.now()
    while True:
        ok, _ = probe_ok(step, router, service)
        if ok == want:
            return round(machine.now() - start, 2)
        if machine.now() - start >= timeout:
            return None
        machine.sleep(1)


def run_outage(step):
    state_dir = launch.outside_repository(step.args.state_dir, 'the state folder')
    router = ROUTER_URLS[launch.router_of(step.args.scenario)]
    results = {}
    for service in step.args.services:
        ok, _ = probe_ok(step, router, service)
        if not ok:
            raise Refused('the %s probe does not answer before the outage: start the stack first, nothing was stopped' % service)
        entry = {'stopped': launch.MISSIONS_CONTAINER if service == 'missions' and step.args.missions == 'real' else launch.OUTAGE_SERVICES[service]}
        stop = launch_argv('stop', service, step.args, state_dir)
        start = launch_argv('start', service, step.args, state_dir)
        assert_launch(stop, step.args.scenario, step.args.missions, state_dir)
        assert_launch(start, step.args.scenario, step.args.missions, state_dir)
        restored = False
        try:
            step.ran(' '.join(stop))
            entry['stopExit'] = step.machine.launch(stop)
            entry['downAfterSeconds'] = wait_for(step, router, service, False, 60)
            step.ran(' '.join(start))
            started = step.machine.now()
            restored = True
            entry['startExit'] = step.machine.launch(start)
            entry['startCommandSeconds'] = round(step.machine.now() - started, 2)
        finally:
            if not restored:
                # Interrupted or failed after the stop: the service is started again before anything else happens.
                step.ran(' '.join(start) + '  (cleanup after an interruption)')
                step.machine.launch(start)
        entry['recoveredAfterStartSeconds'] = wait_for(step, router, service, True, step.args.timeout)
        entry['routerRecoveredWithoutRestart'] = entry['recoveredAfterStartSeconds'] is not None
        results[service] = entry
        step.check('outage-%s' % service, 'the router answers %s again after the restore, with no router restart' % service,
                   entry['recoveredAfterStartSeconds'], entry['stopExit'] == 0 and entry['startExit'] == 0 and entry['routerRecoveredWithoutRestart'])
        step.check('outage-%s-down' % service, 'stopping %s makes the router answer without its data (category D stops a backend)' % service,
                   entry['downAfterSeconds'], entry['downAfterSeconds'] is not None)
        if not entry['routerRecoveredWithoutRestart']:
            step.notes.append('%s: the router did not answer again within %d s. This step never restarts the router: the operator decides.'
                              % (service, step.args.timeout))
    step.measurements.update({'scenario': step.args.scenario, 'missions': step.args.missions, 'router': launch.router_of(step.args.scenario),
                              'services': results})


# ------------------------------------------------------------------------------------------------------------- step 8: provenance
def provenance_module():
    sys.path.insert(0, str(HARNESS))
    import provenance
    return provenance


def plan_provenance(step):
    step.say('read the provenance block of scenario %s from %s and check it with the harness validator' % (step.args.scenario,
                                                                                                         Path(step.args.config).name))
    step.say('observe the running stack with the harness: docker compose -p <project> ps --all --format json, docker inspect <ids>')
    step.say('compare the observation with the declaration; the intended Missions mode must be real and the observed one equal it')
    step.say('no vendor client is made and no request is sent to a model')


def observed_missions_mode(block, observation, provenance):
    backend = block['backends'].get('missions')
    if not backend:
        return None
    services = observation['stable']['services']
    key, error = provenance._resolve(services, backend['service'])
    if error:
        return None
    seen = services[key]
    adapter = services.get('%s/missions-adapter' % STACK_PROJECT) or {}
    url = (adapter.get('env') or {}).get('MISSIONS_SERVICE_URL')
    if key == '%s/missions-stub' % STACK_PROJECT and url == launch.MISSIONS_ADAPTER_URL['simulated'] and seen['state'] == 'running':
        return 'simulated'
    if (key == '%s/missions' % launch.MISSIONS_PROJECT and seen['imageRef'] == SERVICE_IMAGE and url == launch.MISSIONS_ADAPTER_URL['real']
            and seen['state'] == 'running'):
        return 'real'
    return 'unknown'


def run_provenance(step, docker=None):
    provenance = provenance_module()
    config = json.loads(Path(step.args.config).read_text(encoding='utf-8'))
    scenario_config = (config.get('scenarios') or {}).get(step.args.scenario)
    if not scenario_config:
        raise Refused('the study config has no scenario %s' % step.args.scenario)
    block = scenario_config.get('provenance')
    try:
        provenance.validate(step.args.scenario, block)
    except ValueError as error:
        raise Refused(str(error))
    intended = block['backends'].get('missions', {}).get('mode')
    step.ran('docker compose -p <project> ps --all --format json; docker inspect <ids> (the harness DockerCli)')
    observation = provenance.observe(step.args.scenario, scenario_config, docker or step.machine.provenance_docker(provenance))
    problems = provenance.compare(block, observation)
    observed = observed_missions_mode(block, observation, provenance)
    step.measurements.update({'scenario': step.args.scenario, 'intended': provenance.intended(block), 'fingerprint': observation['fingerprint'],
                              'problems': problems, 'missionsMode': {'intended': intended, 'observed': observed}})
    step.check('provenance-match', 'the observed stack matches the declaration', problems, not problems)
    step.check('missions-real', 'the intended Missions mode is real and the observed mode equals it', {'intended': intended, 'observed': observed},
               intended == 'real' and observed == 'real')



# ------------------------------------------------------------------------------------------------------------- report
def run_report(folder, out=print, stamp=None):
    records = []
    for path in sorted(folder.glob('*.json')):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if isinstance(record, dict) and record.get('schema') == SCHEMA and 'step' in record and record['step'] != 'report':
            records.append((path.name, record))
    filled = template()
    by_step = {}
    for name, record in records:
        by_step.setdefault(record['stepNumber'], []).append({'file': name, 'step': record['step'], 'label': record.get('label'),
                                                              'finishedAt': record['finishedAt'], 'checks': record['checks']})
    for item in filled['steps']:
        item['records'] = by_step.get(item['step'], [])
    measured = []
    for threshold in filled['thresholds']:
        results = [c['result'] for _, r in records for c in r['checks'] if c['id'] == threshold['id']]
        threshold['results'] = results
        threshold['status'] = 'not-measured' if not results else ('fail' if 'fail' in results else
                                                                  ('pass' if all(x == 'pass' for x in results) else 'not-measured'))
        if 'judgedBy' not in threshold:
            measured.append(threshold['status'])
    filled['decisionL']['differences'] = [d for _, r in records if r['step'] == 'compare' for d in r['measurements']['differences']]
    filled['goNoGo']['measured'] = {'allThresholdsPass': bool(measured) and all(s == 'pass' for s in measured),
                                    'statuses': {t['id']: t['status'] for t in filled['thresholds'] if 'judgedBy' not in t}}
    filled['generatedAt'] = datetime.now(timezone.utc).isoformat()
    stamp = stamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = folder / ('preflight-record-%s.json' % stamp)
    with open(path, 'x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(redact(filled), indent=2, ensure_ascii=False) + '\n')
    for threshold in filled['thresholds']:
        out('%-16s %-13s %s' % (threshold['id'], threshold['status'] if 'judgedBy' not in threshold else 'the lead developer', threshold['text']))
    out('decision-L differences recorded: %d (each to be classified; the judgement is the lead developer\'s)' % len(filled['decisionL']['differences']))
    out('wrote %s' % path.name)
    return path


# ------------------------------------------------------------------------------------------------------------- the command line
STEPS = {
    'inventory': (1, plan_inventory, run_inventory),
    'oracle': (2, plan_oracle, run_oracle),
    'data': (3, plan_data, run_data),
    'service': (4, plan_service, run_service),
    'stack': (5, plan_stack, run_stack),
    'outage': (6, plan_outage, run_outage),
    'provenance': (8, plan_provenance, run_provenance),
}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='step', required=True)

    def common(p):
        p.add_argument('--results', required=True, help='machine-local folder outside the repository for the records')
        p.add_argument('--run', action='store_true', help='run the step; without it the step only prints what it would do')

    p = sub.add_parser('inventory', help='step 1')
    p.add_argument('--disk-path', help='the drive or folder whose free space is the disk reserve (default: the results folder)')
    common(p)
    p = sub.add_parser('oracle', help='step 2')
    p.add_argument('--window', type=int, default=300, help='seconds of memory sampling after readiness (default 300)')
    p.add_argument('--interval', type=int, default=5, help='seconds between polls and samples (default 5)')
    common(p)
    p = sub.add_parser('data', help='step 3')
    p.add_argument('--login', required=True, help='the read-only service login (an Oracle user name, not a password)')
    p.add_argument('--compare-to', help='an earlier data record whose fingerprint must be equal (the Missions clock check)')
    common(p)
    p = sub.add_parser('service', help='step 4')
    p.add_argument('--target', choices=('real', 'simulated'), required=True, help='what answers on the base URL: the real service or the simulator')
    p.add_argument('--base-url', default=MISSIONS_URL)
    common(p)
    p = sub.add_parser('compare', help='step 4: the differences of two service records')
    p.add_argument('records', nargs=2)
    common(p)
    p = sub.add_parser('stack', help='step 5')
    p.add_argument('scenario', choices=launch.SCENARIOS)
    p.add_argument('--missions', choices=launch.MODES, required=True)
    p.add_argument('--minutes', type=int, default=30, help='soak minutes (default 30)')
    p.add_argument('--interval', type=int, default=15, help='seconds between memory samples (default 15)')
    p.add_argument('--heavy-repeats', type=int, default=3)
    common(p)
    p = sub.add_parser('outage', help='step 6')
    p.add_argument('scenario', choices=launch.SCENARIOS)
    p.add_argument('--missions', choices=launch.MODES, required=True)
    p.add_argument('--state-dir', required=True, help='the state folder of launch.py, outside the repository')
    p.add_argument('--services', nargs='+', choices=tuple(OUTAGE_PROBES), default=['assets', 'personnel', 'missions'])
    p.add_argument('--timeout', type=int, default=300, help='seconds to wait for the router to answer again (default 300)')
    common(p)
    p = sub.add_parser('provenance', help='step 8')
    p.add_argument('scenario', choices=launch.SCENARIOS)
    p.add_argument('--config', required=True, help='the machine-local study config written by study/launch/make_config.py')
    common(p)
    p = sub.add_parser('report', help='the preflight record from the step records')
    p.add_argument('--results', required=True)
    return parser


def main(argv=None, machine=None, out=print):
    args = build_parser().parse_args(argv)
    try:
        folder = results_folder(args.results)
        args.results_dir = folder
        if args.step == 'report':
            if not folder.is_dir():
                raise Refused('the results folder %s does not exist' % folder)
            run_report(folder, out=out)
            return 0
        machine = machine or Machine(oracle_environment()['container'])
        if args.step == 'compare':
            a, b = (json.loads(Path(p).read_text(encoding='utf-8')) for p in args.records)
            if a.get('step') != 'service' or b.get('step') != 'service' or a['measurements']['target'] == b['measurements']['target']:
                raise Refused('compare takes two service records of different targets (real and simulated)')
            out('would compare %s with %s' % (Path(args.records[0]).name, Path(args.records[1]).name))
            if not args.run:
                out('nothing was run: add --run to run this step')
                return 0
            started = machine.wall()
            step = Step(4, 'compare', args, machine, out)
            a['label'], b['label'] = Path(args.records[0]).name, Path(args.records[1]).name
            step.measurements = {'differences': compare_records(a, b), 'latency': latency(a, b)}
            step.notes.append('Every difference waits for its classification under decision L; latency differences are documented, not fixed.')
            path = write_record(folder, step.record(started, machine.wall(), 'real-vs-simulated'), started.strftime('%Y%m%dT%H%M%SZ'))
            out('%d differences; wrote %s' % (len(step.measurements['differences']), path.name))
            return 0
        number, plan, run = STEPS[args.step]
        step = Step(number, args.step, args, machine, out)
        plan(step)
        out('preflight step %d (%s) will:' % (number, args.step))
        for line in step.plan:
            out('  - ' + line)
        if not args.run:
            out('nothing was run: add --run to run this step')
            return 0
        started = machine.wall()
        run(step)
        label = getattr(args, 'target', None) or ('-'.join(filter(None, [getattr(args, 'scenario', None), getattr(args, 'missions', None)])) or None)
        path = write_record(folder, step.record(started, machine.wall(), label), started.strftime('%Y%m%dT%H%M%SZ'))
        for item in step.checks:
            out('%-6s %-20s %s' % (item['result'], item['id'], item['text']))
        out('wrote %s' % path.name)
        return 0 if all(c['result'] != 'fail' for c in step.checks) else 4
    except Refused as error:
        print('preflight.py: refused: %s' % redact_text(error), file=sys.stderr)
        return 1
    except launch.Refused as error:
        print('preflight.py: refused: %s' % redact_text(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
