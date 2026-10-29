"""Seeded simulated study-2 bundles with known true effects, for the tests of the analysis (no stack, no vendor, no corpus 2 content).

    python -B study/analysis2/simulate.py --out <folder outside the repository> [--seed 1] [--run-id study-2-sim]

A bundle is written in the format of study/harness/runner.py: manifest.json with the schedule, runs/<key>/result.json (and
runs/<key>/attempts/<n>/ for a requeued run), blocks.jsonl, provenance/<block>.json, samples.jsonl, scores.jsonl, scores.csv and
bundle.json with its checksum; beside it the archive's per-file sums file and a synthetic corpus folder (corpus-manifest.json and a
tasks.json that holds only ids and strata, no question). The schedule is the harness's own (study/harness/schedule.py): the Williams
square with its halves and model split and the Direct Access block last.

The truth is a logistic model: logit P(correct) = mu + task effect + arm + model + round + session, with a normal random task effect.
`truth` in the returned facts holds every arm's true marginal probability, averaged as the analysis averages (equal model weights, the
planned conditions of the square's core runs, over the simulated tasks), and the true planned and secondary differences. The simulation
includes outage tasks (category D: six that need the stopped service and two over-reporting controls, with honesty failures), vendor
errors (requeued once, and some failing again), an ambiguity set (category F, with clarified and interpretationAccepted), two sessions
with a boundary inside a round and a block resumed after a stop. Every block event carries its `attempt` and every run record its
`blockAttempt`, as the harness of the void-block rule writes them. `void_block` adds a block whose first attempt is void (a backend down
after four runs): its runs move to runs-void/<block>/1/ and the block is repeated whole as attempt 2. `empty_first_start_block` adds a
first start that finished no run before a stop, resumed within the same attempt. `restart_without_void_block` adds a block started again
as a new attempt with no void event, and `legacy_events` writes the events and records without attempts (the format before the
void-block rule); the analysis refuses the first, and in the second a block restarted from no finished run.
"""
import argparse
import csv
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'harness'))

import schedule  # noqa: E402  (the harness's schedule, read-only)

SQUARE_ARMS = ['beta', 'gamma', 'delta', 'epsilon']
REFERENCE = 'alpha'
MODELS = ['claude-sonnet-5-5', 'gpt-6.1-sol']
VENDORS = {'claude-sonnet-5-5': 'anthropic', 'gpt-6.1-sol': 'openai'}
PRICES = {'claude-sonnet-5-5': {'input': 3.0, 'cached_read': 0.3, 'cache_write': 3.75, 'output': 15.0},
          'gpt-6.1-sol': {'input': 1.25, 'cached_read': 0.125, 'cache_write': 0.0, 'output': 10.0}}
SCHEDULE_COLUMNS = ('block', 'blockSequence', 'row', 'roundSequence', 'position', 'half', 'orderInBlock', 'session', 'requeued',
                    'vendorErrors', 'blockAttempt')
TERMINAL = ('correct', 'wrong_answer', 'format_error', 'silent_guess', 'definition_not_accepted', 'abstained', 'did_not_finish', 'vendor_error')
AMBIGUITY_FLAGS = ('clarified', 'interpretationAccepted')
DEFAULT_TRUTH = {
    'mu': 0.4, 'taskSd': 1.6,
    'arm': {'alpha': -0.4, 'beta': 0.0, 'gamma': 0.25, 'delta': 0.6, 'epsilon': 0.5},
    'model': {'claude-sonnet-5-5': 0.0, 'gpt-6.1-sol': -0.3},
    'round': {1: 0.0, 2: 0.15, 3: -0.1, 4: 0.05},
    'session': {'s-1': 0.0, 's-2': -0.25},
    'logSeconds': {'alpha': 4.2, 'beta': 4.0, 'gamma': 3.6, 'delta': 3.5, 'epsilon': 3.55},
    'logTokens': {'alpha': 11.0, 'beta': 10.9, 'gamma': 10.2, 'delta': 10.1, 'epsilon': 10.15},
}
# The design's quota table (48 core tasks) and the ambiguity set: (category, size, systems, stopped service), one row per task.
QUOTAS = (
    [('A', 'small', ['missions'], None)] * 2 + [('A', 'small', ['assets'], None)] * 2 + [('A', 'small', ['personnel'], None)] * 2
    + [('B', 'small', ['missions', 'personnel'], None)] * 3 + [('B', 'small', ['assets', 'missions'], None)] * 2
    + [('B', 'small', ['assets', 'missions', 'personnel'], None)] + [('B', 'medium', ['missions', 'personnel'], None)]
    + [('B', 'medium', ['assets', 'missions'], None)] * 2 + [('B', 'medium', ['assets', 'missions', 'personnel'], None)]
    + [('C', 'small', ['assets', 'missions'], None)] * 3 + [('C', 'small', ['missions', 'personnel'], None)] * 2
    + [('C', 'medium', ['missions', 'personnel'], None)] * 3
    + [('G', 'medium', ['missions'], None), ('G', 'medium', ['assets'], None), ('G', 'medium', ['personnel'], None),
       ('G', 'large', ['missions'], None), ('G', 'large', ['personnel'], None), ('G', 'large', ['missions'], None)]
    + [('E', 'small', ['missions'], None), ('E', 'small', ['assets'], None), ('E', 'small', ['assets', 'missions'], None),
       ('E', 'medium', ['personnel'], None), ('E', 'medium', ['missions'], None), ('E', 'medium', ['missions', 'personnel'], None),
       ('E', 'medium', ['assets', 'missions'], None), ('E', 'large', ['missions', 'personnel'], None),
       ('E', 'large', ['assets', 'missions', 'personnel'], None), ('E', 'large', ['missions', 'personnel'], None)]
    + [('D', 'small', ['missions'], 'missions'), ('D', 'small', ['assets', 'missions'], 'assets'),
       ('D', 'small', ['missions', 'personnel'], 'personnel'), ('D', 'small', ['assets', 'missions'], 'assets'),
       ('D', 'medium', ['missions'], 'missions'), ('D', 'medium', ['assets', 'missions'], 'assets'),
       ('D', 'medium', ['missions', 'personnel'], 'personnel'), ('D', 'medium', ['missions', 'personnel'], 'personnel')]
)
AMBIGUITY = [('F', 'small', ['missions', 'personnel'], None)] * 3 + [('F', 'small', ['assets', 'missions'], None)] * 3


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def append_jsonl(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')


def logistic(x):
    return 1.0 / (1.0 + math.exp(-x))


def corpus_tasks():
    """The synthetic tasks: ids and strata only."""
    tasks = []
    for i, (category, size, systems, stopped) in enumerate(QUOTAS + AMBIGUITY, start=1):
        task = {'id': 'X%02d' % i, 'category': category, 'set': 'ambiguity' if category == 'F' else 'core', 'size': size,
                'systems': sorted(systems)}
        task['tags'] = {'mapping': None}
        if stopped:
            task['stoppedService'] = stopped
            task['tags']['fullyAnswerableWithoutStoppedService'] = sum(1 for t in tasks if t.get('stoppedService')) in (0, 4)
        tasks.append(task)
    return tasks


def write_scores(folder):
    """The score tables, exactly as study/harness/runner.py (Study.write_scores) writes them."""
    rows = []
    for path in sorted((folder / 'runs').glob('*/result.json')):
        r = json.loads(path.read_text(encoding='utf-8'))
        scored = r.get('score') or {}
        row = {'runKey': r['runKey'], 'scenario': r['scenario'], 'taskId': r['taskId'], 'category': r['category'], 'model': r['model'],
               'trial': r.get('trial', ''), 'outcome': r['outcome'], 'reason': r.get('reason') or '',
               'score': scored.get('score', 0) if r['outcome'] in TERMINAL and r['outcome'] != 'vendor_error' else '',
               'tags': ';'.join(scored.get('tags', [])), 'seconds': r['elapsedSeconds'], 'turns': r['turns'],
               'toolCalls': r['toolCalls'], **{'tokens_' + k: v for k, v in r['usage'].items()}, 'attempt': r['attempt']}
        row.update({name: r[name] for name in SCHEDULE_COLUMNS if name in r})
        if 'harnessToolCalls' in r:
            calls = r['harnessToolCalls']
            row.update({'calculateCalls': calls.get('calculate', 0), 'calculateErrors': calls.get('calculateErrors', 0),
                        'askRequesterCalls': calls.get('askRequester', 0)})
        row.update({name: scored[name] for name in AMBIGUITY_FLAGS if name in scored})
        rows.append(row)
    with open(folder / 'scores.jsonl', 'w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')
    fieldnames = []
    for row in rows:
        fieldnames.extend(name for name in row if name not in fieldnames)
    with open(folder / 'scores.csv', 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval='', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_bundle(folder, run_id, written_at):
    """bundle.json with the runner's checksum over the file list (study/harness/runner.py, write_bundle)."""
    files = {p.relative_to(folder).as_posix(): sha256_file(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'bundle.json'}
    body = {'studyRunId': run_id, 'status': 'complete', 'writtenAt': written_at, 'files': files, 'budgets': {}}
    body['checksum'] = hashlib.sha256(json.dumps(files, sort_keys=True).encode('utf-8')).hexdigest()
    write_json(folder / 'bundle.json', body)
    return body['checksum']


def write_sums(folder, run_id, sums_path):
    lines = ['%s *%s/%s' % (sha256_file(p), run_id, p.relative_to(folder).as_posix()) for p in sorted(folder.rglob('*')) if p.is_file()]
    Path(sums_path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)

    def tick(self, seconds):
        self.now += timedelta(seconds=seconds)
        return self.now.isoformat(timespec='milliseconds')


def simulate(out, seed=1, run_id='study-2-sim', truth=None, session_boundary=6, resumed_block=3, empty_first_start_block=None,
             vendor_error_rate=0.02, void_block=None, restart_without_void_block=None, legacy_events=False):
    """Write one simulated bundle under `out`; returns its paths, checksum and truth."""
    truth = dict(DEFAULT_TRUTH, **(truth or {}))
    out = Path(out)
    folder = out / run_id
    folder.mkdir(parents=True)
    rng = random.Random('%s/%s' % (seed, 'outcomes'))
    tasks = corpus_tasks()
    task_effect = {t['id']: random.Random('%s/task/%s' % (seed, t['id'])).gauss(0.0, truth['taskSd']) for t in tasks}
    config = {'schedule': {'design': 'williams-4-half', 'arms': list(SQUARE_ARMS), 'reference': REFERENCE}, 'seed': seed,
              'models': list(MODELS)}
    plan = schedule.build(config, tasks)

    corpus = out / 'corpus'
    write_json(corpus / 'tasks.json', {'about': 'synthetic strata of the simulated corpus; no question', 'draw': {'seed': seed},
                                       'tasks': tasks})
    write_json(corpus / 'corpus-manifest.json', {'about': 'simulated corpus', 'status': 'simulated',
                                                 'files': {'tasks.json': sha256_file(corpus / 'tasks.json')}})
    scorer_sha = hashlib.sha256(b'simulated scorer').hexdigest()
    manifest = {
        'studyRunId': run_id, 'createdAt': '2026-11-02T07:59:00.000+00:00', 'commit': '0' * 40, 'treeDirty': False,
        'identity': {'plan': plan, 'corpusFreeze': sha256_file(corpus / 'corpus-manifest.json'), 'seed': seed, 'taskSet': 'scored',
                     'scoringContract': 2},
        'models': {m: {'vendor': VENDORS[m], 'request': {}, 'max_output_tokens': 16000, 'priceEntry': PRICES[m]} for m in MODELS},
        'scoringContract': {'version': 2, 'outcomes': ['correct', 'wrong_answer', 'format_error', 'definition_not_accepted', 'abstained'],
                            'correctOutcomes': ['correct'], 'harnessOutcomes': ['did_not_finish', 'vendor_error'], 'notScored': ['budget_stop'],
                            'ambiguityFlags': list(AMBIGUITY_FLAGS), 'scorerSha256': scorer_sha},
        'schedule': plan, 'stackRunsPerBlock': 1, 'vendorErrorRequeues': 1,
    }
    manifest['planHash'] = sha256_json(manifest['identity'])
    write_json(folder / 'manifest.json', manifest)
    by_id = {t['id']: t for t in tasks}
    clock = Clock()

    def session_of(block):
        return 's-1' if session_boundary is None or block['sequence'] <= session_boundary else 's-2'

    def eta(task, arm, model, row, session):
        return (truth['mu'] + task_effect[task] + truth['arm'][arm] + truth['model'][model] + (truth['round'].get(row, 0.0) if row else 0.0)
                + truth['session'].get(session, 0.0))

    def result_record(block, run, order, session, attempt, requeued, prior_errors, error=False, block_attempt=1):
        task = by_id[run['task']]
        key = schedule.run_key(block['arm'], run['task'], run['model'], block['runSuffix'])
        record = {'runKey': key, 'studyRunId': run_id, 'scenario': block['arm'], 'model': run['model'], 'block': block['id'],
                  'blockSequence': block['sequence'], 'row': block['row'], 'roundSequence': block['roundSequence'],
                  'position': block['position'], 'half': block['half'], 'session': session, 'orderInBlock': order,
                  'category': task['category'], 'attempt': attempt, 'phase': 'measurement', 'taskId': run['task'], 'submission': None,
                  'reason': None}
        if not legacy_events:
            record['blockAttempt'] = block_attempt
        seconds = round(math.exp(truth['logSeconds'][block['arm']] + rng.gauss(0, 0.4)), 3)
        tokens = math.exp(truth['logTokens'][block['arm']] + (0.2 if run['model'] == MODELS[0] else 0.0) + rng.gauss(0, 0.5))
        usage = {'input': int(tokens * 0.3), 'cached_read': int(tokens * 0.6), 'cache_write': int(tokens * 0.05), 'output': int(tokens * 0.05) + 1}
        calls = max(0, int(rng.gauss(9 if block['arm'] in ('alpha', 'beta') else 6, 3)))
        calculate = min(calls, max(0, int(rng.gauss(1.0, 1.0))))
        record.update({'elapsedSeconds': seconds, 'turns': calls // 2 + 1, 'toolCalls': calls, 'usage': usage, 'usageTokens': sum(usage.values())})
        asked = task['set'] == 'ambiguity' and rng.random() < 0.4
        record['harnessToolCalls'] = {'calculate': calculate, 'calculateErrors': int(calculate > 0 and rng.random() < 0.1),
                                      'askRequester': int(asked)}
        record['askRequester'] = [{'question': 'simulated'}] if asked else []
        record.update({'requeued': requeued, 'vendorErrors': prior_errors + (1 if error else 0)})
        if error:
            record.update({'outcome': 'vendor_error' if prior_errors else 'error', 'reason': 'vendor', 'score': None})
            return key, record
        correct = rng.random() < logistic(eta(run['task'], block['arm'], run['model'], block['row'], session))
        if correct:
            outcome = 'correct'
        else:
            u = rng.random()
            outcome = ('wrong_answer' if u < 0.55 else 'abstained' if u < 0.7 else 'format_error' if u < 0.8
                       else 'definition_not_accepted' if u < 0.9 else 'did_not_finish')
        record['outcome'] = outcome
        if outcome == 'did_not_finish':
            record['score'] = None
            record['reason'] = 'tool_calls'
            return key, record
        score = {'score': int(correct), 'outcome': outcome, 'tags': ['asked_requester'] if asked and task['set'] == 'core' else []}
        if task['category'] == 'D' and outcome == 'wrong_answer' and rng.random() < 0.6:
            score['honestyFailures'] = ['invented_detail']
        if task['set'] == 'ambiguity':
            score.update({'clarified': asked, 'interpretationAccepted': correct})
        record['score'] = score
        return key, record

    def block_event(kind, block, session, attempt, seconds=1, **fields):
        event = {'at': clock.tick(seconds), 'event': kind, 'block': block['id'], 'arm': block['arm'], 'sequence': block['sequence'],
                 'row': block['row'], 'session': session, **fields}
        if not legacy_events:
            event['attempt'] = attempt
        append_jsonl(folder / 'blocks.jsonl', event)

    def key_of(block, run):
        return schedule.run_key(block['arm'], run['task'], run['model'], block['runSuffix'])

    for block in plan['blocks']:
        session = session_of(block)
        runs = list(block['runs'])
        passes, attempt = [], 1  # (attempt, runs finished when the pass stops, how it stops)
        for sequence, ending in ((void_block, 'void'), (restart_without_void_block, 'restart')):
            if block['sequence'] == sequence:
                passes.append((attempt, min(4, len(runs)), ending))  # four runs, then void (or, wrongly, started again)
                attempt += 1
        if block['sequence'] == empty_first_start_block:
            passes.append((attempt, 0, 'stopped'))  # a first start that finished no run before it stopped
        if block['sequence'] == resumed_block:
            passes.append((attempt, min(5, len(runs)), 'stopped'))  # stopped after five runs, then resumed
        passes.append((attempt, len(runs), 'end'))
        done, start_number, errored, current = 0, 0, [], None
        for number, stop_after, ending in passes:
            if number != current:  # a new attempt repeats the block whole
                current, done, errored = number, 0, []
            start_number += 1
            block_event('start', block, session, number, seconds=300, fingerprint='fp-sim', provenanceFingerprint='prov-%s' % block['arm'],
                        start=start_number, runsFinishedBefore=done)
            write_json(folder / 'provenance' / ('%s.json' % block['id']), {'block': block['id'], 'fingerprint': 'prov-%s' % block['arm'],
                                                                           'comparison': {'result': 'match', 'problems': []}})
            append_jsonl(folder / 'samples.jsonl', {'phase': 'cold', 'scenario': block['arm'], 'kind': 'cold_start', 'seconds': 30.0,
                                                    'block': block['id']})
            while done < stop_after:
                run = runs[done]
                done += 1
                is_error = rng.random() < vendor_error_rate
                key, record = result_record(block, run, done, session, 1, False, 0, error=is_error, block_attempt=number)
                record['finishedAt'] = clock.tick(40)
                write_json(folder / 'runs' / key / 'result.json', record)
                if is_error:
                    errored.append((run, done, key))
            if ending == 'stopped':
                block_event('stopped', block, session, number, reason='budget_stop')
            elif ending == 'void':
                keys = [key_of(block, run) for run in runs[:done]]
                block_event('void', block, session, number, trigger='health', point='periodic', problems=['backend missions is down: simulated'],
                            runs=keys, spend={})
                for key in keys:
                    target = folder / 'runs-void' / block['id'] / str(number) / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    (folder / 'runs' / key).replace(target)
        for run, order, key in errored:  # the one requeue at the end of the block
            run_dir = folder / 'runs' / key
            (run_dir / 'attempts' / '001').mkdir(parents=True)
            (run_dir / 'result.json').replace(run_dir / 'attempts' / '001' / 'result.json')
            again = rng.random() < 0.3
            _, record = result_record(block, run, order, session, 2, True, 1, error=again, block_attempt=current)
            record['finishedAt'] = clock.tick(40)
            write_json(run_dir / 'result.json', record)
        outcomes = {}
        for run in runs:
            o = json.loads((folder / 'runs' / key_of(block, run) / 'result.json').read_text(encoding='utf-8'))['outcome']
            outcomes[o] = outcomes.get(o, 0) + 1
        block_event('end', block, session, current, outcomes=dict(sorted(outcomes.items())))
    write_scores(folder)
    checksum = write_bundle(folder, run_id, clock.tick(5))
    sums = out / ('SHA256SUMS-%s.txt' % run_id)
    write_sums(folder, run_id, sums)
    return {'bundle': folder, 'sums': sums, 'corpus': corpus, 'checksum': checksum, 'runId': run_id,
            'truth': true_effects(truth, tasks, plan, task_effect, session_of)}


def true_effects(truth, tasks, plan, task_effect, session_of):
    """The true marginal probabilities of the arms and the true differences, standardized as the analysis standardizes: every round
    with equal weight, its sessions by the planned core runs of the square's blocks."""
    core = [t['id'] for t in tasks if t['set'] == 'core']
    counts = {}
    for block in plan['blocks']:
        if block['row'] is None:
            continue
        n = sum(1 for run in block['runs'] if run['task'] in core)
        key = (block['row'], session_of(block))
        counts[key] = counts.get(key, 0) + n
    rounds = sorted({row for row, _ in counts})
    per_round = {row: sum(n for (r, _), n in counts.items() if r == row) for row in rounds}
    conditions = {key: n / per_round[key[0]] / len(rounds) for key, n in counts.items()}
    total = sum(conditions.values())

    def arm_p(arm):
        value = 0.0
        for (row, session), weight in conditions.items():
            for model in MODELS:
                for t in core:
                    value += weight * logistic(truth['mu'] + task_effect[t] + truth['arm'][arm] + truth['model'][model] + truth['round'][row]
                                               + truth['session'].get(session, 0.0))
        return value / (total * len(MODELS) * len(core))
    p = {a: arm_p(a) for a in SQUARE_ARMS}
    fed = (p['delta'] + p['epsilon']) / 2
    return {'arms': p, 'P1': fed - p['gamma'], 'P2': fed - p['beta'], 'S1': p['delta'] - p['gamma'], 'S2': p['epsilon'] - p['gamma'],
            'S3': p['delta'] - p['epsilon'], 'S4': p['gamma'] - p['beta']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--run-id', default='study-2-sim')
    args = parser.parse_args(argv)
    if Path(args.out).resolve().is_relative_to(HERE.parent.parent.resolve()):
        parser.error('--out must be outside the repository: the bundle is generated')
    facts = simulate(args.out, seed=args.seed, run_id=args.run_id)
    print(json.dumps({'bundle': str(facts['bundle']), 'sums': str(facts['sums']), 'corpus': str(facts['corpus']), 'checksum': facts['checksum'],
                      'truth': facts['truth']}, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
