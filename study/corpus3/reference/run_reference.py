"""Run the scripted reference solutions of corpus 3 in one arm and compare each result with its key.

    python -B study/corpus3/reference/run_reference.py --arm <alpha|beta|gamma|delta|epsilon> [--mcp-url URL]
        [--set core|ambiguity|dev|all] [--tasks B16,E17,...] [--outage missions|assets|personnel] [--output <report.json outside the repository>]
        (--backend simulated|real [--config <machine-local study config>] | --fake) [--check-services]

It is corpus 2's runner (study/corpus2/reference/run_reference.py) pointed at corpus 3: the arms' access layers, the fakes, the backend
verification, the service probes and the outage rules are corpus 2's, imported and unchanged; what is corpus 3's is the task set (the
scored tasks of tasks.json with schemas.json, `core` or `ambiguity`, and the development set dev.json), the keys (keys-a.json), the
solutions (solutions3.py: corpus 2's solvers for the carried tasks, one new solver per new task) and the hashes a report binds itself to.
A run against a stack is an operator action and needs the lead developer's go; corpus 2's runner documents the evidence and the outages.

The evidence. The report's `inputs` hold the hashes of corpus 3's files (tasks.json, schemas.json, expected.json, keys-a.json, dev.json,
corpus-manifest.json, scoring.py), of every reference file the solutions run (corpus 2's reference/*.py and this folder's *.py, one hash
each and one over all of them) and of the released datasets; every task row holds the hashes of its question, schema and key.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent
REPO = CORPUS.parents[1]
CORPUS2_REFERENCE = REPO / 'study' / 'corpus2' / 'reference'


def _load_corpus2_runner():
    spec = importlib.util.spec_from_file_location('corpus2_run_reference', CORPUS2_REFERENCE / 'run_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # it puts corpus 2's folder and reference/ on sys.path and imports corpus 2's solutions
    return module


def _load_scorer():
    """This folder's scoring.py, loaded by its path under its own name. Loading corpus 2's runner has already imported corpus 2's
    scoring.py as `scoring`, so a plain import would reuse that module: the scorer a report hashes must be the one that runs."""
    spec = importlib.util.spec_from_file_location('corpus3_scoring', CORPUS / 'scoring.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R2 = _load_corpus2_runner()
scoring = _load_scorer()
sys.path.insert(0, str(HERE))

from common import ReleaseRefused, ToolFailure, Unavailable  # noqa: E402
from solutions3 import SOLVERS  # noqa: E402

digest, LIMITS = R2.digest, R2.LIMITS
INPUT_FILES = ('tasks.json', 'schemas.json', 'expected.json', 'keys-a.json', 'dev.json', 'corpus-manifest.json', 'scoring.py')
SETS = ('core', 'ambiguity', 'dev')


def reference_files():
    """Every reference file the solutions run: corpus 2's reference/*.py and this folder's *.py, by repository path."""
    return sorted(list(CORPUS2_REFERENCE.glob('*.py')) + list(HERE.glob('*.py')), key=lambda p: p.relative_to(REPO).as_posix())


def input_hashes(folder=CORPUS):
    out = {name: digest((folder / name).read_bytes()) for name in INPUT_FILES}
    scorer = Path(scoring.__file__).resolve()
    out['scorer'] = {'path': scorer.relative_to(REPO).as_posix(), 'sha256': digest(scorer.read_bytes())}  # the scorer that runs
    files = reference_files()
    out['referenceFiles'] = {p.relative_to(REPO).as_posix(): digest(p.read_bytes()) for p in files}
    out['reference'] = digest(b''.join(p.relative_to(REPO).as_posix().encode('utf-8') + b'\0' + p.read_bytes().replace(b'\r\n', b'\n')
                                       for p in files))
    out['datasets'] = digest(json.loads((folder / 'keys-a.json').read_text(encoding='utf-8'))['derivedFrom'])
    return out


def load_tasks(sets, folder=CORPUS):
    scored = json.loads((folder / 'tasks.json').read_text(encoding='utf-8'))['tasks']
    schemas = json.loads((folder / 'schemas.json').read_text(encoding='utf-8'))['schemas']
    out = []
    for name in sets:
        if name == 'dev':
            out += [dict(t, group='dev') for t in json.loads((folder / 'dev.json').read_text(encoding='utf-8'))['tasks']]
        else:
            out += [dict(t, schema=schemas[t['id']], group=name) for t in scored if t['set'] == name]
    return out


def load_keys(folder=CORPUS):
    return json.loads((folder / 'keys-a.json').read_text(encoding='utf-8'))['keys']


def run_task(module, call, task, key):
    counting = R2.Counting(call)
    access = module.ACCESS(counting)
    started = time.monotonic()
    row = {'taskId': task['id'], 'set': task['group'], 'category': task['category'], 'hashes': R2.task_hashes(task, key)}
    try:
        result = SOLVERS[task['id']](access)
    except (ToolFailure, Unavailable, ReleaseRefused, KeyError, TypeError, ValueError) as error:
        row.update(outcome='error', error='%s: %s' % (type(error).__name__, error), toolCalls=counting.count,
                   seconds=round(time.monotonic() - started, 3))
        return row
    submissions = result if isinstance(result, list) else [result]
    if not submissions:
        row.update(outcome='error', error='the solver returned no submission', toolCalls=counting.count,
                   seconds=round(time.monotonic() - started, 3))
        return row
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


def build_report(module, rows, states, backend, mode, origin=None):
    over = [{'taskId': r['taskId'], 'toolCalls': r.get('toolCalls'), 'seconds': r.get('seconds')} for r in rows
            if (r.get('toolCalls') or 0) > LIMITS['toolCalls'] or (r.get('seconds') or 0) > LIMITS['seconds']]
    return {'corpus': 'corpus3', 'arm': module.ARM, 'name': module.NAME, 'mode': mode, 'backend': backend, 'outage': states.get('outage'),
            'serviceStates': states.get('services'), 'provenance': origin, 'inputs': input_hashes(), 'limits': LIMITS, 'overLimits': over,
            'summary': R2.summary(rows), 'tasks': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--arm', required=True)
    parser.add_argument('--mcp-url', help='the arm\'s MCP endpoint (default: the arm\'s port on 127.0.0.1)')
    parser.add_argument('--set', default='all', choices=('all',) + SETS)
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
    module = R2.arm_module(args.arm)
    tasks = load_tasks(list(SETS) if args.set == 'all' else [args.set])
    if args.tasks is not None:  # an explicit empty --tasks names nothing and is refused below, never read as every task
        wanted = [t for t in args.tasks.split(',') if t]
        unknown = sorted(set(wanted) - {t['id'] for t in tasks})
        if unknown or not wanted:
            parser.error('--tasks names tasks that are not in the set %s: %s' % (args.set, ', '.join(unknown) or '(none named)'))
        tasks = [t for t in tasks if t['id'] in set(wanted)]
    if not args.check_services and not any(t.get('stoppedService') == args.outage for t in tasks):
        # every selected task would be skipped: nothing would be checked, so the run cannot pass
        parser.error('no selected task runs %s: %s' % ('under the outage of %s' % args.outage if args.outage else 'without an outage',
                                                       ', '.join(t['id'] for t in tasks) or '(none)'))
    keys = load_keys()
    output = R2.outside_repository(args.output) if args.output else None

    def execute(call):
        states = R2.probe(module, call)
        problems = R2.outage_problems(states, None if args.check_services else args.outage)
        if problems:
            print('services not in the intended state: %s' % '; '.join(problems))
            return states, None
        if args.check_services:
            print('every service answers: %s' % json.dumps(states))
            return states, []
        return states, run(module, call, tasks, keys, args.outage)
    if args.fake:
        states, rows = execute(corpus2_fakes().FakeEnterprise(R2_world(), down=[args.outage] if args.outage else []).call)
        origin = None
    else:
        config = json.loads(Path(args.config).read_text(encoding='utf-8')) if args.config else None
        origin, problems = R2.verify_backend(module.ARM, args.backend, config=config, outage=args.outage, mcp_url=args.mcp_url)
        if problems:
            print('the running stack is not the declared %s backend of %s:\n- %s' % (args.backend, module.NAME, '\n- '.join(problems)))
            return 4
        sys.path.insert(0, str(REPO / 'study' / 'harness'))
        from mcp_client import McpSession
        with McpSession(origin['mcpUrl'], 'corpus3-reference-%s' % module.ARM) as session:
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
                          origin)
    if output:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for row in rows:
        if row['outcome'] not in ('correct', 'skipped'):
            print('%s %s: %s' % (row['taskId'], row['outcome'], row.get('error') or [s['failedChecks'] for s in row['submissions']]))
    for row in report['overLimits']:
        print('%s over the study limits: %s tool calls, %s s' % (row['taskId'], row['toolCalls'], row['seconds']))
    print('corpus 3, %s (%s, %s%s): %s' % (module.NAME, module.ARM, report['backend'], ', outage ' + args.outage if args.outage else '',
                                           json.dumps(report['summary'])))
    return 0 if all(row['outcome'] in ('correct', 'skipped') for row in rows) else 1


def corpus2_fakes():
    """Corpus 2's reference/fakes.py, loaded by its path (study/harness has a fakes.py of its own)."""
    spec = importlib.util.spec_from_file_location('corpus2_fakes', CORPUS2_REFERENCE / 'fakes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def R2_world():
    """The released data for the fakes: corpus 2's World (its derive_a.py, loaded under its own name by derive_a3.py)."""
    sys.path.insert(0, str(CORPUS))
    import derive_a3
    return derive_a3.D2.World()


if __name__ == '__main__':
    sys.exit(main())
