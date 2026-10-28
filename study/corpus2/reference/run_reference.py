"""Run the scripted reference solutions of corpus 2 in one arm and compare each result with its key.

    python -B study/corpus2/reference/run_reference.py --arm <alpha|beta|gamma|delta|epsilon> [--mcp-url URL] [--set pool|ambiguity|dev|all]
        [--tasks A01,B02,...] [--outage missions|assets|personnel] [--output <report.json outside the repository>]
        (--backend simulated|real [--config <machine-local study config>] | --fake) [--check-services]

Against a live stack (the default) it opens one MCP session to the arm's server (the harness's client, study/harness/mcp_client.py,
which needs the pinned `mcp` package: run it with the interpreter of study/mcp/requirements.txt) and calls only that server's tools.
--fake answers the same tools from the released files instead (reference/fakes.py), with no stack.

A task of category D runs only with --outage naming its stopped service: the operator stops that service first (study/launch/launch.py
service stop ...) and starts it again after. Without --outage the D tasks are skipped and reported as such; with it only the D tasks of
that service run. Every submission is scored by the corpus's own scorer (scoring.py) against keys-a.json; an ambiguity task runs once per
accepted interpretation and each must be correct. The report names every task, its outcome per submission, its failed checks and the
number of tool calls; the exit status is 0 only when every task that ran is correct. Starting a stack or an MCP server is an operator
action, and so is this run against one: it needs the lead developer's go.

The evidence. A live run names the backend it expects (`--backend simulated` or `real`), and the runner verifies it before any task: it
observes the running stack with the harness's own read-only provenance observer (study/harness/provenance.py: `docker compose ps` and
`docker inspect`) and compares it with the declaration that study/launch/make_config.py generates for that arm and mode; any difference
refuses the run (exit 4). A real-backend run also needs `--config`, the machine-local study config, whose `dataset_fingerprint` command
(the one the harness runs at every block start) reads the running Missions database; its fingerprint and session go into the report. Only
a verified real-backend report can establish answerability for the draw, and a simulator report never does. During an outage run
the check allows exactly the declared outage: the stopped service's container must not be running (and so publishes no port), and
everything else (the identity and image of every backend, the routing of every adapter, every other endpoint) must still match. The MCP
endpoint is the arm's declared one (`mcp_url` of the make_config scenario, `http://127.0.0.1:<port>/mcp`); any other `--mcp-url`
refuses, and the endpoint is recorded with the observation. Which upstream a running MCP server forwards to is fixed by its start
command, the make_config `mcp_server` command, which the report records; the runner cannot observe it. The report binds itself to what it tested: the hashes of the corpus files,
the scorer, the reference code and the released datasets (`inputs`), and for every task the hashes of its question, schema and key. A
changed input therefore invalidates the evidence that depends on it (draw.py refuses a report whose hashes differ from the current files).
A run past the study's limits (LIMITS: tool calls and seconds per task) is reported in `overLimits`; it is a note on feasibility, not a
failure, and the arms are not required to perform alike.

The outages. Before an outage's tasks run, the runner probes every service through the arm's own tools and refuses to run them unless
the intended service is unavailable and the other two answer (exit 3). `--check-services` only probes and requires every service to
answer: the operator runs it after restoring a service.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent
REPO = CORPUS.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CORPUS))

import scoring  # noqa: E402
from common import ReleaseRefused, ToolFailure, Unavailable  # noqa: E402
from solutions import SOLVERS  # noqa: E402

ARMS = {'alpha': 'direct_access', 'beta': 'guided_direct_access', 'gamma': 'graphql_adapters', 'delta': 'apollo_federation',
        'epsilon': 'cosmo_federation'}
NAMES = {'direct': 'alpha', 'guided': 'beta', 'adapters': 'gamma', 'apollo': 'delta', 'cosmo': 'epsilon'}
SETS = {'pool': 'pool.json', 'ambiguity': 'ambiguity.json', 'dev': 'dev.json'}
LIMITS = {'toolCalls': 80, 'seconds': 900}
INPUT_FILES = ('pool.json', 'ambiguity.json', 'dev.json', 'keys-a.json', 'scoring.py')
PROBES = {'missions': lambda acc: acc.get_mission('ST-00000LD4Q'), 'assets': lambda acc: acc.get_asset('AST-0001'),
          'personnel': lambda acc: acc.get_person('PRS-0001')}


def digest(data):
    """SHA-256 of bytes (LF line ends) or of canonical JSON."""
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def input_hashes(folder=CORPUS):
    """The hashes that bind a report to what it tested: the corpus files, the scorer, the reference code and the released datasets."""
    out = {name: digest((folder / name).read_bytes()) for name in INPUT_FILES}
    code = sorted((folder / 'reference').glob('*.py'))
    out['reference'] = digest(b''.join(p.name.encode('utf-8') + b'\0' + p.read_bytes().replace(b'\r\n', b'\n') for p in code))
    out['datasets'] = digest(json.loads((folder / 'keys-a.json').read_text(encoding='utf-8'))['derivedFrom'])
    return out


def task_hashes(task, key):
    return {'question': digest(task['question'].encode('utf-8')), 'schema': digest(task['schema']), 'key': digest(key)}


def probe(module, call):
    """{service: 'up', 'down' or 'error: ...'} through the arm's own tools."""
    states = {}
    for service, step in PROBES.items():
        try:
            step(module.ACCESS(call))
            states[service] = 'up'
        except Unavailable:
            states[service] = 'down'
        except (ToolFailure, ReleaseRefused, KeyError, TypeError, ValueError) as error:
            states[service] = 'error: %s' % error
    return states


def declared_mcp_url(arm):
    for folder in (REPO / 'study' / 'harness', REPO / 'study' / 'launch'):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    import make_config
    return 'http://127.0.0.1:%d/mcp' % make_config.SERVERS[arm]['port']


def outage_allowance(block, observation, outage):
    """The comparison lines that the declared outage explains (its backend's container not running, so publishing no port), and the
    problem when that container is still running."""
    import provenance
    backend = block['backends'][outage]
    key, error = provenance._resolve(observation['stable']['services'], backend['service'])
    if error:
        return [], []
    state = observation['stable']['services'][key]['state']
    if state == 'running':
        return [], ['the declared outage of %s is not in effect: %s is running' % (outage, key)]
    allowed = ['backend %s (%s): %s is %s, not running' % (outage, backend['mode'], key, state)]
    allowed += [line for line in provenance.compare(block, observation) if line.startswith('endpoint ') and (': %s does not publish' % key) in line]
    return allowed, []


def verify_backend(arm, mode, docker=None, config=None, fingerprint_runner=None, outage=None, mcp_url=None):
    """The verified provenance of the running stack for `arm` in `mode` (with `outage` stopped, when given), with the dataset fingerprint
    of the real Missions database. Returns (record, problems); a non-empty problems list refuses the run."""
    declared = declared_mcp_url(arm)
    import make_config
    import provenance
    block = make_config.provenance_block(arm, mode)
    provenance.validate(arm, block)
    observation = provenance.observe(arm, {'provenance': block, 'mcp_url': declared}, docker or provenance.DockerCli())
    problems = provenance.compare(block, observation)
    allowed = []
    if outage:
        allowed, extra = outage_allowance(block, observation, outage)
        problems = [line for line in problems if line not in allowed] + extra
    if mcp_url is not None and mcp_url != declared:
        problems.append('the MCP endpoint %s is not the declared endpoint of %s, %s' % (mcp_url, arm, declared))
    record = {'verified': not problems, 'mode': mode, 'intended': provenance.intended(block), 'observationFingerprint': observation['fingerprint'],
              'mcpUrl': declared, 'mcpServerCommand': provenance.redact_argv(make_config.mcp_server(arm, '<STUDY_MCP_PYTHON>')['argv']),
              'outage': outage, 'allowedForOutage': allowed, 'containers': observation['containers'],
              'datasets': observation['stable']['datasets'], 'problems': problems, 'datasetFingerprint': None}
    if mode == 'real':
        command = (config or {}).get('dataset_fingerprint')
        if not command:
            problems = problems + ['a real-backend run needs --config with the dataset_fingerprint command of the Missions database']
        else:
            import runner
            try:
                record['datasetFingerprint'] = runner.parse_fingerprint((fingerprint_runner or runner.run_fingerprint_command)(command))
            except (RuntimeError, ValueError, OSError) as error:
                problems = problems + ['the dataset fingerprint could not be read: %s' % error]
        record['problems'], record['verified'] = problems, not problems
    return record, problems


def build_report(module, rows, states, backend, mode, origin=None):
    """The report of one run: `origin` is the verified provenance record of a live run (None on the fakes)."""
    over = [{'taskId': r['taskId'], 'toolCalls': r.get('toolCalls'), 'seconds': r.get('seconds')} for r in rows
            if (r.get('toolCalls') or 0) > LIMITS['toolCalls'] or (r.get('seconds') or 0) > LIMITS['seconds']]
    return {'arm': module.ARM, 'name': module.NAME, 'mode': mode, 'backend': backend, 'outage': states.get('outage'),
            'serviceStates': states.get('services'), 'provenance': origin, 'inputs': input_hashes(), 'limits': LIMITS, 'overLimits': over,
            'summary': summary(rows), 'tasks': rows}


def outage_problems(states, outage):
    """Why the services are not in the intended state: only `outage` (or nothing) down, every other service answering."""
    return ['%s is %s, not %s' % (service, state, 'down' if service == outage else 'up')
            for service, state in states.items() if state != ('down' if service == outage else 'up')]


def arm_module(arm):
    arm = NAMES.get(arm, arm)
    if arm not in ARMS:
        raise SystemExit('unknown arm %r: one of %s' % (arm, ', '.join(list(ARMS) + list(NAMES))))
    return __import__(ARMS[arm])


def load_tasks(sets):
    out = []
    for name in sets:
        for task in json.loads((CORPUS / SETS[name]).read_text(encoding='utf-8'))['tasks']:
            out.append(dict(task, group=name))
    return out


def load_keys():
    return json.loads((CORPUS / 'keys-a.json').read_text(encoding='utf-8'))['keys']


class Counting:
    """Wraps the call function and counts the tool calls of the current task."""

    def __init__(self, call):
        self.inner, self.count = call, 0

    def __call__(self, tool, arguments):
        self.count += 1
        return self.inner(tool, arguments)


def run_task(module, call, task, key):
    counting = Counting(call)
    access = module.ACCESS(counting)
    started = time.monotonic()
    row = {'taskId': task['id'], 'set': task['group'], 'category': task['category'], 'hashes': task_hashes(task, key)}
    try:
        result = SOLVERS[task['id']](access)
    except (ToolFailure, Unavailable, ReleaseRefused, KeyError, TypeError, ValueError) as error:
        row.update(outcome='error', error='%s: %s' % (type(error).__name__, error), toolCalls=counting.count,
                   seconds=round(time.monotonic() - started, 3))
        return row
    submissions = result if isinstance(result, list) else [result]
    context = {'taskId': task['id'], 'set': 'ambiguity' if task['group'] == 'ambiguity' else 'core', 'category': task['category'],
               'askRequester': []}
    scores = [scoring.score(sub, task['schema'], key, context) for sub in submissions]
    row.update(outcome='correct' if all(s['outcome'] == 'correct' for s in scores) else 'wrong',
               submissions=[{'outcome': s['outcome'], 'tags': s['tags'], 'failedChecks': s['failedChecks'],
                             'honestyFailures': s['honestyFailures'], 'formatErrors': s['formatErrors']} for s in scores],
               toolCalls=counting.count, seconds=round(time.monotonic() - started, 3))
    if row['outcome'] != 'correct':
        row['submitted'] = submissions
    return row


def run(module, call, tasks, keys, outage=None):
    rows = []
    for task in tasks:
        stopped = task.get('stoppedService')
        if stopped != outage:
            if stopped:
                rows.append({'taskId': task['id'], 'set': task['group'], 'category': task['category'], 'outcome': 'skipped',
                             'reason': 'needs the outage of %s' % stopped})
            continue
        rows.append(run_task(module, call, task, keys[task['id']]))
    return rows


def summary(rows):
    counts = {}
    for row in rows:
        counts[row['outcome']] = counts.get(row['outcome'], 0) + 1
    return counts


def outside_repository(path):
    path = Path(path).resolve()
    if path == REPO or REPO in path.parents:
        raise SystemExit('the report must be written outside the repository: %s' % path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--arm', required=True)
    parser.add_argument('--mcp-url', help='the arm\'s MCP endpoint (default: the arm\'s port on 127.0.0.1)')
    parser.add_argument('--set', default='all', choices=['all'] + list(SETS))
    parser.add_argument('--tasks', help='comma-separated task ids (default: every task of the set)')
    parser.add_argument('--outage', choices=['missions', 'assets', 'personnel'], help='run only the D tasks of this stopped service')
    parser.add_argument('--output', help='write the JSON report here (outside the repository)')
    parser.add_argument('--fake', action='store_true', help='answer the tools from the released files instead of a live stack')
    parser.add_argument('--backend', choices=['simulated', 'real'], help='which Missions backend the live stack runs (required when live)')
    parser.add_argument('--check-services', action='store_true', help='only probe the services; every one must answer')
    parser.add_argument('--config', help='the machine-local study config (for its dataset_fingerprint command); needed with --backend real')
    args = parser.parse_args(argv)
    if args.fake == bool(args.backend):
        parser.error('give exactly one of --fake and --backend')
    module = arm_module(args.arm)
    tasks = load_tasks(list(SETS) if args.set == 'all' else [args.set])
    if args.tasks:
        wanted = set(args.tasks.split(','))
        tasks = [t for t in tasks if t['id'] in wanted]
    keys = load_keys()
    output = outside_repository(args.output) if args.output else None
    def execute(call):
        states = probe(module, call)
        problems = outage_problems(states, None if args.check_services else args.outage)
        if problems:
            print('services not in the intended state: %s' % '; '.join(problems))
            return states, None
        if args.check_services:
            print('every service answers: %s' % json.dumps(states))
            return states, []
        return states, run(module, call, tasks, keys, args.outage)
    if args.fake:
        import derive_a
        from fakes import FakeEnterprise
        states, rows = execute(FakeEnterprise(derive_a.World(), down=[args.outage] if args.outage else []).call)
    else:
        config = json.loads(Path(args.config).read_text(encoding='utf-8')) if args.config else None
        origin, problems = verify_backend(module.ARM, args.backend, config=config, outage=args.outage, mcp_url=args.mcp_url)
        if problems:
            print('the running stack is not the declared %s backend of %s:\n- %s' % (args.backend, module.NAME, '\n- '.join(problems)))
            return 4
        sys.path.insert(0, str(REPO / 'study' / 'harness'))
        from mcp_client import McpSession
        with McpSession(origin['mcpUrl'], 'corpus2-reference-%s' % module.ARM) as session:
            names = {t['name'] for t in session.tools()}
            if names != set(module.TOOLS):
                raise SystemExit('the server at %s offers %s, not the tools of %s (%s)' % (origin['mcpUrl'], sorted(names),
                                                                                          module.NAME, ', '.join(module.TOOLS)))
            states, rows = execute(session.call)
    if rows is None:
        return 3
    if args.check_services:
        return 0
    report = build_report(module, rows, {'outage': args.outage, 'services': states}, args.backend or 'fake', 'fake' if args.fake else 'live',
                          None if args.fake else origin)
    over = report['overLimits']
    if output:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for row in rows:
        if row['outcome'] not in ('correct', 'skipped'):
            print('%s %s: %s' % (row['taskId'], row['outcome'], row.get('error') or [s['failedChecks'] for s in row['submissions']]))
    for row in over:
        print('%s over the study limits: %s tool calls, %s s' % (row['taskId'], row['toolCalls'], row['seconds']))
    print('%s (%s, %s%s): %s' % (module.NAME, module.ARM, report['backend'], ', outage ' + args.outage if args.outage else '',
                                 json.dumps(report['summary'])))
    return 0 if all(row['outcome'] in ('correct', 'skipped') for row in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
