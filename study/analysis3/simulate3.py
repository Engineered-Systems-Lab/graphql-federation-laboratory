"""Seeded simulated study-3 data with known effects, at corpus 3's real shape (no question, key or task id of corpus 3 is used).

`SHAPE` holds corpus 3's task metadata as counts of combinations, and test_analysis3.py checks it against study/corpus3/tasks.json.
`study_records` draws one simulated study as the records the analysis reads, for validate3.py. `write_bundle` writes the same draw as a
bundle in the harness's format, for the tests of the loader, the counting rules and the command line.

The truth. For a run of task t in arm a, with model m in round k:
    log(1 + calls) = 2.2 + model + round + b_t + c_ta + e   (calls rounded and capped at 80)
    log(cost)      = -3.5 + model + round + b'_t + c'_ta + e'
b is the task's level, c the task's response to the arm (shared by the task's two runs in that arm) and e the run's noise. The standard
deviations come from study 2's spread. The comparison arms carry the effects: GraphQL Adapters' mean is minus the task's P1 log ratio and
Guided Direct Access' minus its P2 log ratio, so federation's ratios are the stated ones. Accuracy follows the scenario named in `accuracy`.
"""
import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'analysis2'))
sys.path.insert(0, str(HERE.parent / 'harness'))

import schedule  # noqa: E402  (the harness's schedule, read-only)
import simulate as simulate2  # noqa: E402  (study 2's bundle writers, read-only)

import data3  # noqa: E402

ARMS = data3.SQUARE_ARMS
REFERENCE = data3.REFERENCE_ARM
MODELS = ['claude-sonnet-5-5', 'gpt-6.1-sol']
PRICES = {m: {'input': 2.0, 'cached_read': 0.1, 'cache_write': 2.5, 'output': 10.0} for m in MODELS}
# Corpus 3 as counts: category, size, systems, required systems, direction, csl kind, anchor, stopped service, the D tag, tasks.
SHAPE = (
    ('A', 'small', 'assets', 'assets', 'none', None, 'missions', None, None, 3),
    ('A', 'small', 'missions', 'missions', 'none', None, 'missions', None, None, 3),
    ('A', 'small', 'personnel', 'personnel', 'none', None, 'missions', None, None, 3),
    ('B', 'medium', 'assets+missions', 'assets+missions', 'forward', None, 'missions', None, None, 2),
    ('B', 'medium', 'assets+missions', 'assets+missions', 'reverse', 'reverse-lookup', 'assets', None, None, 5),
    ('B', 'medium', 'assets+missions', 'missions', 'reverse', 'reverse-lookup', 'assets', None, None, 1),
    ('B', 'medium', 'assets+missions+personnel', 'assets+missions+personnel', 'forward', None, 'missions', None, None, 2),
    ('B', 'medium', 'missions', 'missions', 'reverse', 'reverse-lookup', 'assets', None, None, 1),
    ('B', 'medium', 'missions+personnel', 'missions', 'none', None, 'missions', None, None, 1),
    ('B', 'medium', 'missions+personnel', 'missions', 'reverse', 'reverse-lookup', 'personnel', None, None, 1),
    ('B', 'medium', 'missions+personnel', 'missions+personnel', 'reverse', 'reverse-lookup', 'personnel', None, None, 4),
    ('B', 'small', 'assets+missions', 'assets+missions', 'forward', None, 'missions', None, None, 3),
    ('B', 'small', 'assets+missions+personnel', 'assets+missions+personnel', 'forward', None, 'missions', None, None, 3),
    ('B', 'small', 'missions+personnel', 'missions+personnel', 'forward', None, 'missions', None, None, 4),
    ('B', 'small', 'missions+personnel', 'missions+personnel', 'reverse', 'reverse-lookup', 'personnel', None, None, 4),
    ('C', 'medium', 'assets+missions', 'assets+missions', 'none', 'link-integrity', 'missions', None, None, 2),
    ('C', 'medium', 'missions', 'missions', 'none', None, 'missions', None, None, 2),
    ('C', 'medium', 'missions', 'missions', 'reverse', 'reverse-lookup', 'assets', None, None, 1),
    ('C', 'medium', 'missions+personnel', 'missions+personnel', 'none', 'link-integrity', 'missions', None, None, 1),
    ('C', 'small', '', '', 'none', None, 'missions', None, None, 2),
    ('C', 'small', 'assets+missions', 'assets+missions', 'none', 'link-integrity', 'missions', None, None, 1),
    ('C', 'small', 'assets+missions', 'assets+missions', 'reverse', 'reverse-lookup', 'assets', None, None, 1),
    ('C', 'small', 'missions', 'missions', 'none', None, 'missions', None, None, 4),
    ('C', 'small', 'missions+personnel', 'missions+personnel', 'reverse', 'reverse-lookup', 'personnel', None, None, 2),
    ('D', 'medium', 'assets+missions', 'assets+missions', 'none', None, 'missions', 'assets', False, 2),
    ('D', 'medium', 'missions', 'missions', 'none', None, 'missions', 'missions', False, 1),
    ('D', 'medium', 'missions+personnel', 'missions+personnel', 'none', None, 'missions', 'personnel', False, 2),
    ('D', 'medium', 'personnel', 'personnel', 'none', None, 'missions', 'missions', True, 1),
    ('D', 'small', 'assets', 'assets', 'none', None, 'missions', 'assets', False, 1),
    ('D', 'small', 'assets+missions', 'assets+missions', 'none', None, 'missions', 'assets', False, 1),
    ('D', 'small', 'assets+missions', 'assets+missions', 'none', None, 'missions', 'personnel', True, 1),
    ('D', 'small', 'missions+personnel', 'missions+personnel', 'none', None, 'missions', 'assets', True, 1),
    ('D', 'small', 'missions+personnel', 'missions+personnel', 'none', None, 'missions', 'missions', False, 1),
    ('D', 'small', 'missions+personnel', 'missions+personnel', 'none', None, 'missions', 'personnel', False, 1),
    ('D', 'small', 'personnel', 'personnel', 'none', None, 'missions', 'missions', True, 1),
    ('D', 'small', 'personnel', 'personnel', 'none', None, 'missions', 'personnel', False, 1),
    ('E', 'large', 'assets+missions', 'assets+missions', 'reverse', 'far-side-aggregate', 'assets', None, None, 3),
    ('E', 'large', 'missions', 'missions', 'none', None, 'missions', None, None, 1),
    ('E', 'large', 'missions+personnel', 'missions+personnel', 'forward', None, 'missions', None, None, 2),
    ('E', 'large', 'missions+personnel', 'missions+personnel', 'reverse', 'far-side-aggregate', 'personnel', None, None, 2),
    ('E', 'large', 'personnel', 'personnel', 'none', None, 'missions', None, None, 1),
    ('E', 'medium', 'assets+missions', 'assets+missions', 'forward', None, 'missions', None, None, 1),
    ('E', 'medium', 'assets+missions', 'assets+missions', 'reverse', 'far-side-aggregate', 'assets', None, None, 1),
    ('E', 'medium', 'assets+missions+personnel', 'assets+missions+personnel', 'forward', None, 'missions', None, None, 1),
    ('E', 'medium', 'missions', 'missions', 'none', None, 'missions', None, None, 2),
    ('E', 'medium', 'missions', 'missions', 'reverse', 'far-side-aggregate', 'assets', None, None, 1),
    ('E', 'medium', 'missions+personnel', 'missions+personnel', 'forward', None, 'missions', None, None, 2),
    ('E', 'medium', 'missions+personnel', 'missions+personnel', 'reverse', 'far-side-aggregate', 'personnel', None, None, 2),
    ('E', 'medium', 'personnel', 'personnel', 'none', None, 'missions', None, None, 1),
    ('E', 'small', 'assets', 'assets', 'none', None, 'missions', None, None, 1),
    ('E', 'small', 'assets+missions', 'assets+missions', 'forward', None, 'missions', None, None, 1),
    ('E', 'small', 'assets+missions+personnel', 'assets+missions+personnel', 'forward', None, 'missions', None, None, 1),
    ('E', 'small', 'missions', 'missions', 'none', None, 'missions', None, None, 1),
    ('E', 'small', 'missions', 'missions', 'reverse', 'far-side-aggregate', 'personnel', None, None, 1),
    ('E', 'small', 'missions+personnel', 'missions+personnel', 'forward', None, 'missions', None, None, 2),
    ('F', 'small', 'assets', 'assets', 'none', None, 'missions', None, None, 2),
    ('F', 'small', 'missions', 'missions', 'none', None, 'missions', None, None, 3),
    ('F', 'small', 'missions+personnel', 'missions+personnel', 'none', None, 'missions', None, None, 1),
    ('G', 'large', 'missions', 'missions', 'none', None, 'missions', None, None, 3),
    ('G', 'large', 'personnel', 'personnel', 'none', None, 'missions', None, None, 2),
    ('G', 'medium', 'assets', 'assets', 'none', None, 'missions', None, None, 1),
    ('G', 'medium', 'missions', 'missions', 'none', None, 'missions', None, None, 2),
    ('G', 'medium', 'personnel', 'personnel', 'none', None, 'missions', None, None, 2),
)
# Study 2's observed log ratios of federation over each comparison arm (study/evidence/study-2, power3.py computes them), and the join
# width difference of A18. They are the 100 percent effects.
STUDY2 = {'toolCalls': {'P1': -0.2390, 'P2': 0.2567}, 'cost': {'P1': -0.1591, 'P2': -0.2627}, 'joinWidth': -0.180}
SD = {'toolCalls': {'task': 0.50, 'arm': {'beta': 0.45, 'gamma': 0.18, 'delta': 0.18, 'epsilon': 0.18}, 'run': 0.27},
      'cost': {'task': 0.55, 'arm': {'beta': 0.33, 'gamma': 0.22, 'delta': 0.22, 'epsilon': 0.22}, 'run': 0.28}}
CORRELATION = 0.7  # between a task's or a run's tool calls and cost
MODEL_SHIFT = {'toolCalls': {MODELS[0]: 0.05, MODELS[1]: -0.05}, 'cost': {MODELS[0]: 0.39, MODELS[1]: -0.39}}
ROUND_SHIFT = {1: 0.0, 2: 0.03, 3: -0.02, 4: 0.01}
SESSION_SHIFT = 0.05
NULL = {'P1': {'toolCalls': 0.0, 'cost': 0.0}, 'P2': {'toolCalls': 0.0, 'cost': 0.0}, 'reverseMinusForward': 0.0, 'severalMinusOne': 0.0}


def tasks_of_shape():
    """The synthetic tasks: ids T001 onwards, strata and directions only."""
    tasks, directions = [], {}
    for category, size, systems, required, direction, csl, anchor, stopped, tag, count in SHAPE:
        for _ in range(count):
            task_id = 'T%03d' % (len(tasks) + 1)
            task = {'id': task_id, 'category': category, 'set': 'ambiguity' if category == 'F' else 'core', 'size': size,
                    'systems': systems.split('+') if systems else [], 'tags': {'mapping': None}}
            if stopped:
                task['stoppedService'] = stopped
                task['tags']['fullyAnswerableWithoutStoppedService'] = tag
            tasks.append(task)
            directions[task_id] = {'direction': direction, 'csl': csl, 'anchor': anchor, 'requiredSystems': required.split('+') if required else []}
    return tasks, directions


def effects_at(percent, reverse_gone=False, join=False):
    """The effects at a share of study 2's. `reverse_gone`: the forward group has P1's effect and the reverse group none. `join`: the
    several-systems group's advantage exceeds the one-system group's by the share of A18's difference."""
    share = percent / 100.0
    out = {'P1': {k: share * STUDY2[k]['P1'] for k in ('toolCalls', 'cost')}, 'P2': {k: share * STUDY2[k]['P2'] for k in ('toolCalls', 'cost')},
           'reverseMinusForward': -share * STUDY2['toolCalls']['P1'] if reverse_gone else 0.0,
           'severalMinusOne': share * STUDY2['joinWidth'] if join else 0.0}
    return out


def task_p1(effects, entry, outcome):
    """The task's P1 log ratio: the family's effect, with the group differences added to tool calls only."""
    value = effects['P1'][outcome]
    if outcome == 'toolCalls':
        if entry['direction'] == 'reverse':
            value += effects['reverseMinusForward']
        if entry['joinGroup'] == 'several':
            value += effects['severalMinusOne']
    return value


def accuracy_draw(kind, rng, count):
    """Per task, the probability of a correct run in the federated arms and in each comparison arm. Every kind has task-level dependence:
    a task's federated arms share one probability, and each comparison arm has its own.
    - near: every arm 97 to 100 percent, with a task effect;
    - boundary-100: the comparison arms at 100 percent, federation Beta(9, 1) per task (mean 90 percent);
    - boundary-shift: the comparison arms 96 to 100 percent, federation exactly 10 points lower on every task;
    - boundary-tasks: the comparison arms at 100 percent, and each task wrong in every federated run with probability 0.10."""
    if kind == 'near':
        base = rng.uniform(0.97, 1.0, count)
        return base, {'beta': base, 'gamma': base}
    if kind == 'boundary-100':
        return rng.beta(9.0, 1.0, count), {'beta': np.ones(count), 'gamma': np.ones(count)}
    if kind == 'boundary-shift':
        base = rng.uniform(0.96, 1.0, count)
        return base - 0.10, {'beta': base, 'gamma': base}
    if kind == 'boundary-tasks':
        return np.where(rng.random(count) < 0.10, 0.0, 1.0), {'beta': np.ones(count), 'gamma': np.ones(count)}
    raise ValueError('unknown accuracy scenario %r' % kind)


def build_plan(seed, tasks):
    config = {'schedule': {'design': 'williams-4-half', 'arms': list(ARMS), 'reference': REFERENCE}, 'seed': seed, 'models': list(MODELS)}
    return schedule.build(config, tasks)


def study_records(seed, effects=NULL, accuracy='near', missing=0.02, plan_seed=None, shape=None, session_boundary=None):
    """One simulated study as the analysis's records of the square's core runs, vendor errors included as `correct` None. `session_boundary`
    is the sequence number of the last block of the first session: the later blocks form a second session whose effort is SESSION_SHIFT
    higher on the log scale."""
    tasks, directions = shape or tasks_of_shape()
    rng = np.random.default_rng([20261118, seed])
    core = [t for t in tasks if t['set'] == 'core']
    plan = build_plan(seed if plan_seed is None else plan_seed, tasks)
    entries = {}
    for task in core:
        d = directions[task['id']]
        entries[task['id']] = dict(d, category=task['category'], cslGroup=d['direction'] if d['direction'] in ('forward', 'reverse') else None,
                                   joinGroup=data3.join_group(task['category'], d['requiredSystems']))
    ids = [t['id'] for t in core]
    index = {t: i for i, t in enumerate(ids)}
    shared = rng.standard_normal((len(ids), 2))
    level = {'toolCalls': SD['toolCalls']['task'] * shared[:, 0],
             'cost': SD['cost']['task'] * (CORRELATION * shared[:, 0] + math.sqrt(1 - CORRELATION ** 2) * shared[:, 1])}
    response = {o: {a: SD[o]['arm'][a] * rng.standard_normal(len(ids)) for a in ARMS} for o in ('toolCalls', 'cost')}
    federated, comparison = accuracy_draw(accuracy, rng, len(ids))
    records = []
    for block in plan['blocks']:
        if block['row'] is None:
            continue
        for order, run in enumerate(block['runs'], start=1):
            if run['task'] not in index:
                continue
            i, arm, model, row = index[run['task']], block['arm'], run['model'], block['row']
            entry = entries[run['task']]
            noise = rng.standard_normal(2)
            later = session_boundary is not None and block['sequence'] > session_boundary
            values = {}
            for outcome, centre, run_noise in (('toolCalls', 2.2, noise[0]), ('cost', -3.5, CORRELATION * noise[0] + math.sqrt(1 - CORRELATION ** 2) * noise[1])):
                effect = -task_p1(effects, entry, outcome) if arm == 'gamma' else -effects['P2'][outcome] if arm == 'beta' else 0.0
                values[outcome] = (centre + effect + MODEL_SHIFT[outcome][model] + ROUND_SHIFT[row] + level[outcome][i] + response[outcome][arm][i]
                                   + SD[outcome]['run'] * run_noise + (SESSION_SHIFT if later else 0.0))
            calls = min(80, max(0, int(round(math.expm1(values['toolCalls'])))))
            probability = federated[i] if arm in ('delta', 'epsilon') else comparison[arm][i]
            vendor_error = bool(rng.random() < missing)
            correct = None if vendor_error else int(rng.random() < probability)
            records.append({'runKey': schedule.run_key(arm, run['task'], model, block['runSuffix']), 'arm': arm, 'task': run['task'], 'model': model,
                            'category': entry['category'], 'set': 'core', 'block': block['id'], 'blockSequence': block['sequence'], 'row': row,
                            'session': 's-2' if later else 's-1', 'orderInBlock': order, 'outcome': 'vendor_error' if vendor_error else 'correct' if correct else 'wrong_answer',
                            'correct': correct, 'toolCalls': calls, 'cost': math.exp(values['cost']), 'seconds': math.exp(3.5 + 0.3 * rng.standard_normal()),
                            'direction': entry['direction'], 'csl': entry['csl'], 'anchor': entry['anchor'], 'cslGroup': entry['cslGroup'],
                            'joinGroup': entry['joinGroup']})
    return records, {t: entries[t]['direction'] for t in ids}


# ------------------------------------------------------------------------------------------------------------------ bundles
class Clock:
    def __init__(self):
        self.now = datetime(2026, 12, 1, 8, 0, 0, tzinfo=timezone.utc)

    def tick(self, seconds):
        self.now += timedelta(seconds=seconds)
        return self.now.isoformat(timespec='milliseconds')


def write_bundle(out, seed=1, run_id='study-3-sim', effects=NULL, accuracy='near', vendor_error_rate=0.02, void_block=None, zero_cost_runs=0,
                 analysis_plan=None, plan_seed=None, requeue_failure=0.3):
    """One simulated bundle in the harness's format; returns its paths, checksum and the effects. A run that hits a vendor error is queued
    again once at the end of its block, and fails again with the chance `requeue_failure`. `void_block` voids the first attempt of that block's
    sequence number after four runs; `zero_cost_runs` gives that many scored runs a usage of zero tokens."""
    out = Path(out)
    folder = out / run_id
    folder.mkdir(parents=True)
    tasks, directions = tasks_of_shape()
    corpus = out / 'corpus'
    simulate2.write_json(corpus / 'tasks.json', {'about': 'synthetic strata of a simulated corpus 3; no question', 'tasks': tasks, 'directions': directions})
    simulate2.write_json(corpus / 'corpus-manifest.json', {'about': 'simulated corpus', 'status': 'simulated',
                                                           'files': {'tasks.json': simulate2.sha256_file(corpus / 'tasks.json')}})
    plan = build_plan(seed if plan_seed is None else plan_seed, tasks)
    drawn, _ = study_records(seed, effects, accuracy, missing=0.0, plan_seed=seed if plan_seed is None else plan_seed, shape=(tasks, directions))
    truth = {r['runKey']: r for r in drawn}
    rng = random.Random('%s/bundle' % seed)
    manifest = {
        'studyRunId': run_id, 'createdAt': '2026-12-01T07:59:00.000+00:00', 'commit': '0' * 40, 'treeDirty': False,
        'identity': {'plan': plan, 'corpusFreeze': simulate2.sha256_file(corpus / 'corpus-manifest.json'), 'seed': seed, 'taskSet': 'scored',
                     'scoringContract': 2, 'analysisPlan': analysis_plan or data3.sha256_file(data3.PLAN)},
        'models': {m: {'vendor': 'simulated', 'request': {}, 'max_output_tokens': 16000, 'priceEntry': PRICES[m]} for m in MODELS},
        'scoringContract': {'version': 2, 'outcomes': list(data3.data2.SCORER_OUTCOMES), 'correctOutcomes': ['correct'],
                            'harnessOutcomes': list(data3.data2.HARNESS_OUTCOMES), 'notScored': ['budget_stop'],
                            'ambiguityFlags': list(simulate2.AMBIGUITY_FLAGS), 'scorerSha256': '0' * 64},
        'schedule': plan, 'stackRunsPerBlock': 1, 'vendorErrorRequeues': 1,
    }
    manifest['planHash'] = simulate2.sha256_json(manifest['identity'])
    simulate2.write_json(folder / 'manifest.json', manifest)
    by_id = {t['id']: t for t in tasks}
    clock = Clock()
    zero_left = zero_cost_runs

    def result_of(block, run, order, attempt, requeued, prior, error, block_attempt):
        nonlocal zero_left
        task = by_id[run['task']]
        key = schedule.run_key(block['arm'], run['task'], run['model'], block['runSuffix'])
        known = truth.get(key)
        cost = known['cost'] if known else math.exp(-3.5 + 0.5 * rng.gauss(0, 1))
        calls = known['toolCalls'] if known else max(0, int(rng.gauss(8, 3)))
        output = max(1, int(round(cost * 1e6 / PRICES[run['model']]['output'])))
        record = {'runKey': key, 'studyRunId': run_id, 'scenario': block['arm'], 'model': run['model'], 'block': block['id'], 'blockSequence': block['sequence'],
                  'row': block['row'], 'roundSequence': block['roundSequence'], 'position': block['position'], 'half': block['half'], 'session': 's-1',
                  'orderInBlock': order, 'category': task['category'], 'attempt': attempt, 'phase': 'measurement', 'taskId': run['task'], 'submission': None,
                  'reason': None, 'blockAttempt': block_attempt, 'elapsedSeconds': round(math.exp(3.5 + 0.3 * rng.gauss(0, 1)), 3), 'turns': calls // 2 + 1,
                  'toolCalls': calls, 'requeued': requeued, 'vendorErrors': prior + int(error), 'askRequester': [],
                  'harnessToolCalls': {'calculate': 0, 'calculateErrors': 0, 'askRequester': 0}}
        if error:
            usage = {'input': 0, 'cached_read': 0, 'cache_write': 0, 'output': 1}
            record.update({'outcome': 'vendor_error' if prior else 'error', 'reason': 'vendor', 'score': None, 'usage': usage, 'usageTokens': 1})
            return key, record
        if zero_left > 0 and known:
            output, zero_left = 0, zero_left - 1
        usage = {'input': 0, 'cached_read': 0, 'cache_write': 0, 'output': output}
        correct = bool(known['correct']) if known else rng.random() < 0.8
        outcome = 'correct' if correct else 'wrong_answer'
        score = {'score': int(correct), 'outcome': outcome, 'tags': [], 'honestyChecks': ['invented_detail'] if task['category'] == 'D' else []}
        if task['set'] == 'ambiguity':
            score.update({'clarified': False, 'interpretationAccepted': correct})
        record.update({'outcome': outcome, 'score': score, 'usage': usage, 'usageTokens': sum(usage.values())})
        return key, record

    def event(kind, block, attempt, seconds=1, **fields):
        simulate2.append_jsonl(folder / 'blocks.jsonl', {'at': clock.tick(seconds), 'event': kind, 'block': block['id'], 'arm': block['arm'], 'sequence': block['sequence'],
                                                         'row': block['row'], 'session': 's-1', 'attempt': attempt, **fields})

    for block in plan['blocks']:
        runs, attempt = list(block['runs']), 1
        if block['sequence'] == void_block:
            event('start', block, attempt, seconds=300, start=1, runsFinishedBefore=0)
            keys = []
            for order, run in enumerate(runs[:4], start=1):
                key, record = result_of(block, run, order, 1, False, 0, False, attempt)
                record['finishedAt'] = clock.tick(40)
                simulate2.write_json(folder / 'runs-void' / block['id'] / str(attempt) / key / 'result.json', record)
                keys.append(key)
            event('void', block, attempt, trigger='health', point='periodic', problems=['simulated'], runs=keys, spend={})
            attempt = 2
        event('start', block, attempt, seconds=300, start=attempt, runsFinishedBefore=0)
        errored = []
        for order, run in enumerate(runs, start=1):
            error = rng.random() < vendor_error_rate
            key, record = result_of(block, run, order, 1, False, 0, error, attempt)
            record['finishedAt'] = clock.tick(40)
            simulate2.write_json(folder / 'runs' / key / 'result.json', record)
            if error:
                errored.append((run, order, key))
        for run, order, key in errored:
            run_dir = folder / 'runs' / key
            (run_dir / 'attempts' / '001').mkdir(parents=True)
            (run_dir / 'result.json').replace(run_dir / 'attempts' / '001' / 'result.json')
            _, record = result_of(block, run, order, 2, True, 1, rng.random() < requeue_failure, attempt)
            record['finishedAt'] = clock.tick(40)
            simulate2.write_json(run_dir / 'result.json', record)
        event('end', block, attempt, outcomes={})
    simulate2.write_scores(folder)
    checksum = simulate2.write_bundle(folder, run_id, clock.tick(5))
    sums = out / ('SHA256SUMS-%s.txt' % run_id)
    simulate2.write_sums(folder, run_id, sums)
    return {'bundle': folder, 'sums': sums, 'corpus': corpus, 'checksum': checksum, 'runId': run_id, 'effects': effects}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--percent', type=float, default=100.0, help="the share of study 2's effects")
    args = parser.parse_args(argv)
    if Path(args.out).resolve().is_relative_to(HERE.parent.parent.resolve()):
        parser.error('--out must be outside the repository: the bundle is generated')
    facts = write_bundle(args.out, seed=args.seed, effects=effects_at(args.percent))
    print(json.dumps({k: str(v) for k, v in facts.items() if k != 'effects'}, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
