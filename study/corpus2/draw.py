"""The stratified draw of corpus 2: 48 scored core tasks from the pool, by the design's quota table, with a recorded seed.

    python -B study/corpus2/draw.py --seed <integer> --answerability <report.json> [<report.json> ...] [--write]

NOT executed in the Job that wrote it: it runs in the final preflight, after every task has been confirmed answerable in every arm
against the Oracle-backed stack. Without --write it prints the selection and writes nothing.

- **Checked first:** the pool must have unique ids and every task its required metadata (id, set, category, size, systems, question,
  schema, tags, and for category D stoppedService and the tag fullyAnswerableWithoutStoppedService) and a key; anything else refuses.
- **Eligible:** a pool task is eligible only when the answerability reports (the JSON reports of reference/run_reference.py) show it
  correct in every one of the five arms. A task of category D counts from the report of its own outage. A task missing from an arm's
  reports is not eligible. Only a live report whose real backend the runner verified counts: its provenance record must be verified
  (the observed stack matched the real-mode declaration) and carry the dataset fingerprint of the Missions database, and every report
  must carry the same fingerprint, which the draw records. A simulator, fake, unverified or mixed-database report refuses. A report also
  binds to the current inputs: its scorer, reference code and dataset hashes must equal the current ones, and the question, schema and
  key hashes of every row it counts as evidence (a correct row) must equal the current task's; a report that differs refuses, so changed
  inputs invalidate their evidence. Rows that are not evidence (a task skipped outside its outage, a wrong row) are not counted.
- **The ambiguity set** passes the same gate: each of its 6 tasks must be correct in every arm, which means every accepted
  interpretation answered correctly, or the draw refuses; it is never drawn from, so it cannot be dropped instead.
- **Quotas:** each cell of category and size gets exactly its quota (QUOTAS). Within a category the draw also keeps the design's system
  coverage (COVERAGE): A has 2 tasks of each system; B has 4 Missions and Personnel, 4 Missions and Assets and 2 of all three; E has 4
  single-system and 6 cross-system tasks; D has 2 tasks with the Missions service stopped, 3 with Assets and 3 with Personnel, of which
  exactly 2 are fully answerable without the stopped service. C and G have no system quota.
- **Randomness:** `random.Random(seed)` alone, over the eligible ids in sorted order. Each category is drawn by rejection: the cells are
  sampled, and the sample is kept only when it meets the category's coverage; the first sample that does is the draw. The same seed and
  the same eligible set always give the same draw. Nothing is chosen for its expected effect.
- **Output** (with --write): tasks.json (the 48 drawn core tasks in pool order, then the 6 ambiguity tasks with set ambiguity, and the
  draw record: seed, pool and keys hashes, the eligible count, the hashes of the reports), schemas.json and expected.json (from
  keys-a.json). Before the draw these three files hold no task (EMPTY).
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'reference'))
from run_reference import input_hashes, task_hashes  # noqa: E402  (the same hashes the reports carry)

REQUIRED = ('id', 'set', 'category', 'size', 'systems', 'question', 'schema', 'tags')
BOUND_INPUTS = ('scoring.py', 'reference', 'datasets')
ARMS = ('alpha', 'beta', 'gamma', 'delta', 'epsilon')
QUOTAS = {('A', 'small'): 6, ('B', 'small'): 6, ('B', 'medium'): 4, ('C', 'small'): 5, ('C', 'medium'): 3, ('G', 'medium'): 3,
          ('G', 'large'): 3, ('E', 'small'): 3, ('E', 'medium'): 4, ('E', 'large'): 3, ('D', 'small'): 4, ('D', 'medium'): 4}
TOTAL = 48
MAX_TRIES = 200000


def systems_key(task):
    return '+'.join(sorted(task['systems']))


def coverage_ok(category, tasks):
    """The design's system coverage of one category's drawn tasks."""
    if category == 'A':
        return Counter(systems_key(t) for t in tasks) == Counter({'missions': 2, 'assets': 2, 'personnel': 2})
    if category == 'B':
        return Counter(systems_key(t) for t in tasks) == Counter({'missions+personnel': 4, 'assets+missions': 4, 'assets+missions+personnel': 2})
    if category == 'E':
        return Counter('single' if len(t['systems']) == 1 else 'cross' for t in tasks) == Counter({'single': 4, 'cross': 6})
    if category == 'D':
        return (Counter(t['stoppedService'] for t in tasks) == Counter({'missions': 2, 'assets': 3, 'personnel': 3})
                and sum(1 for t in tasks if t['tags'].get('fullyAnswerableWithoutStoppedService')) == 2)
    return True


EMPTY = {
    'tasks.json': {'about': 'The scored tasks of corpus 2, written by draw.py. Empty until the draw runs, in the final preflight.',
                   'draw': None, 'tasks': []},
    'schemas.json': {'about': 'The submit_answer JSON Schema of each scored task, written by draw.py. Empty until the draw runs.', 'schemas': {}},
    'expected.json': {'about': 'The key of each scored task (from keys-a.json), written by draw.py. Empty until the draw runs.', 'expected': {}},
}


def sha256_text(text):
    return hashlib.sha256(text.replace('\r\n', '\n').encode('utf-8')).hexdigest()


def render(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


def check_pool(pool, keys):
    """Refuse duplicate ids, missing metadata and missing keys."""
    ids = [t.get('id') for t in pool]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError('duplicate task ids in the pool: %s' % ', '.join(map(str, duplicates)))
    for task in pool:
        missing = [name for name in REQUIRED if name not in task]
        if task.get('category') == 'D':
            missing += [name for name in ('stoppedService',) if name not in task]
            if 'fullyAnswerableWithoutStoppedService' not in task.get('tags', {}):
                missing.append('tags.fullyAnswerableWithoutStoppedService')
        if task.get('set') != 'core':
            missing.append('set core')
        if (task.get('category'), task.get('size')) not in QUOTAS:
            missing.append('a cell of the quota table')
        if task.get('id') not in keys:
            missing.append('a key')
        if missing:
            raise ValueError('task %s lacks %s' % (task.get('id'), ', '.join(missing)))


def check_report(report, current):
    """Refuse a report that is not verified real-backend evidence bound to the current inputs; returns its dataset fingerprint."""
    arm = report.get('arm')
    if arm not in ARMS:
        raise ValueError('unknown arm %r in a report' % arm)
    if report.get('mode') != 'live' or report.get('backend') != 'real':
        raise ValueError('an answerability report must come from a live stack on the real backend, not %r on %r'
                         % (report.get('mode'), report.get('backend')))
    origin = report.get('provenance') or {}
    if not origin.get('verified') or origin.get('problems') or origin.get('mode') != 'real':
        raise ValueError('a report of %s carries no verified real-backend provenance' % arm)
    if (origin.get('intended') or {}).get('backends', {}).get('missions', {}).get('mode') != 'real':
        raise ValueError('a report of %s was not observed against the real Missions service' % arm)
    fingerprint = (origin.get('datasetFingerprint') or {}).get('fingerprint')
    if not fingerprint:
        raise ValueError('a report of %s carries no dataset fingerprint of the Missions database' % arm)
    stale = [name for name in BOUND_INPUTS if (report.get('inputs') or {}).get(name) != current[name]]
    if stale:
        raise ValueError('a report of %s was made with other %s than the current ones' % (arm, ', '.join(stale)))
    return fingerprint


def eligible_ids(tasks, reports, keys, current=None):
    """The ids of `tasks` (the pool, or the ambiguity set) that every arm's verified real-backend reports show correct (a D task from the
    report of its own outage), every counted row bound to the current task. Returns (ids, the one dataset fingerprint)."""
    current = input_hashes() if current is None else current
    expected = {t['id']: task_hashes(t, keys[t['id']]) for t in tasks}
    passed = {arm: set() for arm in ARMS}
    fingerprints = set()
    for report in reports:
        fingerprints.add(check_report(report, current))
        for row in report['tasks']:
            if row.get('outcome') != 'correct' or row['taskId'] not in expected:
                continue
            if row.get('hashes') != expected[row['taskId']]:
                raise ValueError('a report of %s tested another question, schema or key of %s' % (report['arm'], row['taskId']))
            passed[report['arm']].add((row['taskId'], report.get('outage')))
    if len(fingerprints) > 1:
        raise ValueError('the reports were made against %d different Missions databases' % len(fingerprints))
    out = set()
    for task in tasks:
        needed = (task['id'], task.get('stoppedService'))
        if all(needed in passed[arm] for arm in ARMS):
            out.add(task['id'])
    return out, (fingerprints.pop() if fingerprints else None)


def check_ambiguity(ambiguity, reports, keys, current=None):
    """Refuse unless every ambiguity task is correct, every accepted interpretation, in every arm."""
    if len(ambiguity) != 6 or len({t['id'] for t in ambiguity}) != 6:
        raise ValueError('the ambiguity set must hold 6 distinct tasks')
    for task in ambiguity:
        if task.get('set') != 'ambiguity' or task['id'] not in keys or 'rubric' not in keys[task['id']]:
            raise ValueError('ambiguity task %s lacks its set or its rubric' % task.get('id'))
    ok, _ = eligible_ids(ambiguity, reports, keys, current)
    missing = sorted({t['id'] for t in ambiguity} - ok)
    if missing:
        raise ValueError('ambiguity tasks without answerability evidence in every arm: %s' % ', '.join(missing))


def draw(pool, eligible, seed):
    """The drawn task ids, in pool order. Raises ValueError when a cell has too few eligible tasks or no sample meets the coverage."""
    rng = random.Random(seed)
    by_id = {t['id']: t for t in pool}
    chosen = []
    for category in sorted({c for c, _ in QUOTAS}):
        cells = [(size, n) for (c, size), n in sorted(QUOTAS.items()) if c == category]
        candidates = {size: sorted(i for i in eligible if by_id[i]['category'] == category and by_id[i]['size'] == size) for size, _ in cells}
        for size, n in cells:
            if len(candidates[size]) < n:
                raise ValueError('cell %s %s has %d eligible tasks for a quota of %d' % (category, size, len(candidates[size]), n))
        for _ in range(MAX_TRIES):
            sample = [i for size, n in cells for i in rng.sample(candidates[size], n)]
            if coverage_ok(category, [by_id[i] for i in sample]):
                chosen += sample
                break
        else:
            raise ValueError('no draw of category %s meets its system coverage in %d tries' % (category, MAX_TRIES))
    assert len(chosen) == TOTAL
    order = {t['id']: n for n, t in enumerate(pool)}
    return sorted(chosen, key=order.get)


def outputs(pool, ambiguity, keys, chosen, record):
    """The texts of tasks.json, schemas.json and expected.json for a draw."""
    by_id = {t['id']: t for t in pool}
    rows = [by_id[i] for i in chosen] + list(ambiguity)
    tasks = [{k: v for k, v in t.items() if k != 'schema'} for t in rows]
    return {
        'tasks.json': render({'about': 'The scored tasks of corpus 2: 48 core tasks drawn from pool.json by draw.py, then the 6 tasks of the '
                                       'ambiguity set. The question is asked word for word in every arm.', 'draw': record, 'tasks': tasks}),
        'schemas.json': render({'about': 'The submit_answer JSON Schema of each scored task.', 'schemas': {t['id']: t['schema'] for t in rows}}),
        'expected.json': render({'about': 'The key of each scored task, from keys-a.json (the first derivation).',
                                 'expected': {t['id']: keys[t['id']] for t in rows}}),
    }


def main(argv=None, folder=HERE):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--answerability', nargs='+', required=True, help='the reports of reference/run_reference.py, live, every arm')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    texts = {name: (folder / name).read_text(encoding='utf-8') for name in ('pool.json', 'ambiguity.json', 'keys-a.json')}
    pool = json.loads(texts['pool.json'])['tasks']
    ambiguity = json.loads(texts['ambiguity.json'])['tasks']
    keys = json.loads(texts['keys-a.json'])['keys']
    report_texts = [Path(p).read_text(encoding='utf-8') for p in args.answerability]
    check_pool(pool, keys)
    reports = [json.loads(t) for t in report_texts]
    current = input_hashes(folder)
    eligible, fingerprint = eligible_ids(pool, reports, keys, current)
    check_ambiguity(ambiguity, reports, keys, current)
    chosen = draw(pool, eligible, args.seed)
    record = {'seed': args.seed, 'poolSha256': sha256_text(texts['pool.json']), 'ambiguitySha256': sha256_text(texts['ambiguity.json']),
              'keysSha256': sha256_text(texts['keys-a.json']), 'eligible': len(eligible), 'poolTasks': len(pool),
              'missionsDatasetFingerprint': fingerprint,
              'answerabilityReports': sorted(sha256_text(t) for t in report_texts)}
    print('drawn:', ', '.join(chosen))
    if args.write:
        for name, text in outputs(pool, ambiguity, keys, chosen, record).items():
            (folder / name).write_bytes(text.encode('utf-8'))
        print('wrote tasks.json, schemas.json, expected.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
