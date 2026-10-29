"""Reading a study-2 bundle for the analysis: verify a copy, read the task strata, load one record per run and apply the counting rules.

The raw bundle stays outside the repository and is read-only; the analysis reads a COPY. Before anything is read the copy is checked as
study 1's are (study/analysis/data.py, verify_copy, used unchanged): every file against the archive's per-file sums, no file missing or
extra, and the bundle checksum recomputed from the bundle's file list and compared with the one given on the command line. Then the
manifest must name its scorer contract (version 2, with the scorer's hash), its corpus (the hash of corpus-manifest.json) and its harness
commit, and the corpus folder given must be that corpus. A failure of any check raises VerificationError and the analysis stops.

The strata of a task (set, size and systems) are not in the bundle's score rows, so they are read from the corpus's tasks.json, whose
fields id, category, set, size, systems and stoppedService, and of its tags only fullyAnswerableWithoutStoppedService (category D), are
the only ones read: no question, schema, key or reference solution. tasks.json must be bound to the bundle: the corpus manifest the
bundle names must list its hash. The analysis keys only on category, set, size and systems, and splits category D by that tag (the
lead developer's decision of 2026-10-28); a task id is a cluster label and nothing else.

The counting rules (PLAN.md, "Which runs count"):
- the four full arms of the square (Guided Direct Access, GraphQL Adapters, Apollo Federation, Cosmo Federation) enter the confirmatory and
  secondary fits; Direct Access (its reference block) only the exploratory results;
- the core set enters the primary accuracy; the ambiguity set is analysed apart;
- every run the manifest's schedule plans must have exactly one record, and no other run may appear;
- a vendor error (the harness's `vendor_error`, a run that failed at the vendor again after its one requeue) is missing in the main
  analysis and wrong in a sensitivity analysis; a requeued run that then finished counts once, with its last attempt;
- the attempts of a block. The harness of the void-block rule numbers them: every block event carries `attempt`, every run record
  `blockAttempt`, and a `void` event names a void attempt with its declared trigger, whose runs the harness moved to
  runs-void/<block>/<attempt>/. Then the current attempt (the last) counts: it has no void event, it starts with no finished run when an
  attempt was void before it, it ends with an `end` event, and every one of its runs is recorded under it and finished after it began. A
  void attempt is excluded and its cost is reported apart. Attempts that are not numbered 1, 2, ... in order, an attempt followed by
  another without a void event (a block restarted with no void event), events of an attempt after its void event, and a later start of
  the current attempt that found no finished run while runs of it had finished are refused;
- a bundle whose block events carry no attempt (written before the void-block rule) keeps the provisional rule: the block has ONE attempt,
  its first start and the resumes that continue it (`runsFinishedBefore` above 0), and a later start that found no finished run is
  refused, because without the void events the analysis cannot tell a void block repeated whole from a resume after a stop that finished
  no run;
- the cost of attempts the harness archived (a run queued again after a vendor error) is kept apart as operational spend, and so is the
  cost of void attempts.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'analysis'))

import data  # noqa: E402  (study 1's reader, used read-only: verify_copy, sha256_file, dollars, VerificationError)

VerificationError = data.VerificationError

# The arms by their internal identifiers (the scenario names of the configuration) and their descriptive names (docs/STUDY-2-DESIGN.md).
SQUARE_ARMS = ['beta', 'gamma', 'delta', 'epsilon']
REFERENCE_ARM = 'alpha'
ALL_ARMS = SQUARE_ARMS + [REFERENCE_ARM]
ARM_NAMES = {'alpha': 'Direct Access', 'beta': 'Guided Direct Access', 'gamma': 'GraphQL Adapters', 'delta': 'Apollo Federation',
             'epsilon': 'Cosmo Federation'}
CATEGORY_NAMES = {'A': 'Single-system lookup', 'B': 'Cross-system join', 'C': 'Mapping-dependent', 'D': 'Honesty under failure',
                  'E': 'Aggregation', 'F': 'Ambiguity', 'G': 'Pagination and completeness'}
CORE_CATEGORIES = ('A', 'B', 'C', 'D', 'E', 'G')
AMBIGUITY_CATEGORY = 'F'
SIZES = ('small', 'medium', 'large')
# The outcomes a complete study-2 bundle may hold: the scorer's (contract version 2) and the two the harness decides itself.
SCORER_OUTCOMES = ('correct', 'wrong_answer', 'format_error', 'definition_not_accepted', 'abstained')
HARNESS_OUTCOMES = ('did_not_finish', 'vendor_error')
OUTCOMES = SCORER_OUTCOMES + HARNESS_OUTCOMES
STRATA_FIELDS = ('id', 'category', 'set', 'size', 'systems', 'stoppedService')
GAP_TAG = 'fullyAnswerableWithoutStoppedService'
HONEST_OUTCOMES = ('correct', 'wrong_answer', 'definition_not_accepted')
USAGE_KINDS = data.USAGE_KINDS


def sha256_file(path):
    return data.sha256_file(path)


def run_key(arm, task, model, suffix):
    """The key of a run of the schedule, as study/harness/schedule.py writes it."""
    return '%s__%s__%s__%s' % (arm, task, model, suffix)


# ------------------------------------------------------------------------------------------------------------------ verification
def verify_bundle(folder, sums_file, run_id, bundle_checksum):
    """Verify a copy of a study-2 run folder and its manifest; returns the verified facts and the manifest."""
    if not bundle_checksum:
        raise VerificationError('the bundle checksum must be given')
    facts = data.verify_copy(folder, sums_file, run_id, bundle_checksum)
    manifest = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
    contract = manifest.get('scoringContract')
    if not isinstance(contract, dict) or contract.get('version') is None or not contract.get('scorerSha256'):
        raise VerificationError('%s: the manifest names no scorer contract with the scorer hash' % run_id)
    if contract.get('version') != 2:
        raise VerificationError('%s: scorer contract version %r; the study-2 analysis reads version 2' % (run_id, contract.get('version')))
    corpus = (manifest.get('identity') or {}).get('corpusFreeze')
    if not corpus:
        raise VerificationError('%s: the manifest names no corpus hash (identity.corpusFreeze)' % run_id)
    if not manifest.get('commit'):
        raise VerificationError('%s: the manifest names no harness commit' % run_id)
    plan = manifest.get('schedule')
    if not isinstance(plan, dict) or plan.get('design') != 'williams-4-half':
        raise VerificationError('%s: the manifest holds no williams-4-half schedule' % run_id)
    arms = sorted({b['arm'] for b in plan['blocks'] if b.get('row') is not None})
    if arms != sorted(SQUARE_ARMS) or plan.get('reference') != REFERENCE_ARM:
        raise VerificationError('%s: the schedule runs %s with the reference %s; the analysis expects %s and %s'
                                % (run_id, arms, plan.get('reference'), sorted(SQUARE_ARMS), REFERENCE_ARM))
    if len(manifest.get('models') or {}) != 2:
        raise VerificationError('%s: the manifest does not name exactly two models' % run_id)
    facts.update({'scoringContract': contract['version'], 'scorerSha256': contract['scorerSha256'], 'corpusFreeze': corpus,
                  'harnessCommit': manifest['commit'], 'treeDirty': manifest.get('treeDirty'), 'planHash': manifest.get('planHash')})
    return facts, manifest


def load_strata(corpus_dir, manifest):
    """{task id: {category, set, size, systems, stoppedService}} from the corpus folder the bundle ran, read field by field.

    The corpus is the bundle's when the hash of its corpus-manifest.json equals the manifest's identity.corpusFreeze, and the corpus
    manifest must list the hash of tasks.json, which must match. tasks.json must hold exactly the tasks of the schedule, each once."""
    corpus_dir = Path(corpus_dir)
    freeze = sha256_file(corpus_dir / 'corpus-manifest.json')
    if freeze != manifest['identity']['corpusFreeze']:
        raise VerificationError('the corpus folder is not the bundle\'s: corpus-manifest.json hashes to %s, the manifest names %s'
                                % (freeze, manifest['identity']['corpusFreeze']))
    corpus_manifest = json.loads((corpus_dir / 'corpus-manifest.json').read_text(encoding='utf-8'))
    listed = (corpus_manifest.get('files') or {}).get('tasks.json')
    tasks_path = corpus_dir / 'tasks.json'
    if listed is None:
        raise VerificationError('the corpus manifest does not list the hash of tasks.json, so the strata are not bound to the bundle')
    if sha256_file(tasks_path) != listed:
        raise VerificationError('tasks.json differs from the hash its corpus manifest lists')
    tasks = json.loads(tasks_path.read_text(encoding='utf-8'))['tasks']
    strata = {}
    for task in tasks:
        entry = {name: task.get(name) for name in STRATA_FIELDS}
        tag = (task.get('tags') or {}).get(GAP_TAG) if isinstance(task.get('tags'), dict) else None
        if entry['category'] == 'D' and not isinstance(tag, bool):
            raise VerificationError('category-D task %s has no boolean tag %s' % (entry['id'], GAP_TAG))
        entry['gapRequired'] = (not tag) if entry['category'] == 'D' else None
        if entry['id'] in strata:
            raise VerificationError('tasks.json lists the task %s twice' % entry['id'])
        if entry['category'] not in CORE_CATEGORIES + (AMBIGUITY_CATEGORY,):
            raise VerificationError('task %s has the unknown category %r' % (entry['id'], entry['category']))
        entry['set'] = entry['set'] or 'core'
        if (entry['set'] == 'ambiguity') != (entry['category'] == AMBIGUITY_CATEGORY):
            raise VerificationError('task %s: category %s and set %s disagree' % (entry['id'], entry['category'], entry['set']))
        if entry['size'] not in SIZES:
            raise VerificationError('task %s has the unknown size %r' % (entry['id'], entry['size']))
        entry['systems'] = sorted(entry['systems'] or [])
        strata[entry.pop('id')] = entry
    planned = set(manifest['schedule']['halves']['H1']) | set(manifest['schedule']['halves']['H2'])
    if planned != set(strata):
        raise VerificationError('tasks.json and the schedule hold different tasks (%d in tasks.json, %d in the schedule)'
                                % (len(strata), len(planned)))
    return strata, {'corpusFreeze': freeze, 'tasksJsonSha256': sha256_file(tasks_path), 'tasks': len(strata)}


# ------------------------------------------------------------------------------------------------------------------ loading
def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def block_attempts(events, block_id):
    """The starts of a block grouped into attempts. An attempt opens with a start that found no finished run of the block and goes on
    through the resumes after it. Returns a list of attempts, each {'starts': [start events], 'ended': bool, 'stopped': n}."""
    attempts = []
    for event in events:
        if event.get('block') != block_id:
            continue
        kind = event.get('event')
        if kind == 'start':
            if not attempts or int(event.get('runsFinishedBefore') or 0) == 0:
                attempts.append({'starts': [], 'ended': False, 'stopped': 0})
            attempts[-1]['starts'].append(event)
            attempts[-1]['ended'] = False
        elif kind == 'end' and attempts:
            attempts[-1]['ended'] = True
        elif kind == 'stopped' and attempts:
            attempts[-1]['stopped'] += 1
    return attempts


BLOCK_EVENTS = ('start', 'end', 'stopped', 'void')
VOID_FOLDER = 'runs-void'


def numbered_attempts(events, block_id):
    """The attempts of a block whose events carry `attempt` (the void-block rule), checked: {number: {'starts', 'ended', 'stopped',
    'void'}} in order. Raises VerificationError for numbers out of order, a void attempt without its void event, events after a void
    event, a repeat that did not start from no finished run and a current attempt that is void."""
    attempts = {}
    for event in events:
        if event.get('block') != block_id or event.get('event') not in BLOCK_EVENTS:
            continue
        number = event['attempt']
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise VerificationError('block %s: an event carries the attempt %r' % (block_id, number))
        if attempts and number < max(attempts):
            raise VerificationError('block %s: an event of attempt %d follows attempt %d' % (block_id, number, max(attempts)))
        if number not in attempts:
            if number != len(attempts) + 1:
                raise VerificationError('block %s: attempt %d follows attempt %d' % (block_id, number, len(attempts)))
            if attempts and attempts[number - 1]['void'] is None:
                raise VerificationError('block %s was started again as attempt %d with no void event for attempt %d: a block restarted '
                                        'with no void event cannot be counted' % (block_id, number, number - 1))
            attempts[number] = {'starts': [], 'ended': False, 'stopped': 0, 'void': None}
        attempt = attempts[number]
        if attempt['void'] is not None:
            raise VerificationError('block %s: attempt %d has events after its void event' % (block_id, number))
        kind = event['event']
        if kind == 'start':
            if not attempt['starts'] and number > 1 and int(event.get('runsFinishedBefore') or 0) != 0:
                raise VerificationError('block %s: attempt %d, the repeat of a void attempt, did not start from no finished run'
                                        % (block_id, number))
            attempt['starts'].append(event)
            attempt['ended'] = False
        elif kind == 'end':
            attempt['ended'] = True
        elif kind == 'stopped':
            attempt['stopped'] += 1
        else:
            attempt['void'] = event
    if attempts and attempts[max(attempts)]['void'] is not None:
        raise VerificationError('block %s: its last attempt (%d) is void and was not repeated' % (block_id, max(attempts)))
    return attempts


def void_costs(folder, block_id, attempts, prices):
    """[{attempt, trigger, point, runs, cost}] of the void attempts of a block, read from runs-void/<block>/<attempt>/ (the current
    results and the archived attempts of each run there). The runs there must be the ones the void event names."""
    out = []
    root = Path(folder) / VOID_FOLDER / block_id
    numbers = {str(n) for n, a in attempts.items() if a['void'] is not None}
    present = {p.name for p in root.iterdir()} if root.exists() else set()
    if present - numbers:
        raise VerificationError('block %s: %s holds attempts that no void event names (%s)' % (block_id, VOID_FOLDER,
                                                                                            ', '.join(sorted(present - numbers))))
    for number, attempt in sorted(attempts.items()):
        void = attempt['void']
        if void is None:
            continue
        where = root / str(number)
        keys = sorted(p.name for p in where.iterdir()) if where.exists() else []
        if keys != sorted(void.get('runs') or []):
            raise VerificationError('block %s: the void event of attempt %d names other runs than %s/%s/%d holds'
                                    % (block_id, number, VOID_FOLDER, block_id, number))
        cost = 0.0
        for key in keys:
            for path in [where / key / 'result.json'] + sorted((where / key / 'attempts').glob('*/result.json')):
                if path.exists():
                    record = json.loads(path.read_text(encoding='utf-8'))
                    cost += data.dollars({kind: int(record['usage'][kind]) for kind in USAGE_KINDS}, prices[record['model']])
        out.append({'attempt': number, 'trigger': void.get('trigger'), 'point': void.get('point'), 'runs': len(keys), 'cost': cost})
    return out


def load_bundle(folder, manifest, strata):
    """One record per planned run of a verified copy, with the counting facts; raises VerificationError when the bundle breaks a rule."""
    folder = Path(folder)
    prices = {model: entry['priceEntry'] for model, entry in manifest['models'].items()}
    with open(folder / 'scores.csv', encoding='utf-8', newline='') as handle:
        scores = {row['runKey']: row for row in csv.DictReader(handle)}
    events = read_jsonl(folder / 'blocks.jsonl')
    planned, blocks = {}, []
    for block in manifest['schedule']['blocks']:
        own = [e for e in events if e.get('block') == block['id'] and e.get('event') in BLOCK_EVENTS]
        numbered = [('attempt' in e) for e in own]
        if any(numbered) and not all(numbered):
            raise VerificationError('block %s: some of its events carry an attempt and some do not' % block['id'])
        if own and all(numbered):
            numbers = numbered_attempts(events, block['id'])
            attempts = [numbers[n] for n in sorted(numbers)]
            voids = void_costs(folder, block['id'], numbers, prices)
            counted = max(numbers)
        else:
            if (folder / VOID_FOLDER / block['id']).exists():
                raise VerificationError('block %s has void runs but its events carry no attempt' % block['id'])
            attempts = block_attempts(events, block['id'])
            voids, counted = [], None
            if len(attempts) > 1:
                raise VerificationError('block %s was started again from no finished run after an earlier start; without the void '
                                        'events of the void-block rule the analysis cannot tell which attempt counts' % block['id'])
        if not attempts:
            raise VerificationError('block %s has no recorded start' % block['id'])
        last = attempts[-1]
        if not last['starts']:
            raise VerificationError('block %s: its last attempt has no start' % block['id'])
        if not last['ended']:
            raise VerificationError('block %s: its last attempt did not end' % block['id'])
        since = last['starts'][0]['at']
        restarts = [s['at'] for s in last['starts'][1:] if int(s.get('runsFinishedBefore') or 0) == 0]
        blocks.append({'id': block['id'], 'arm': block['arm'], 'row': block['row'], 'sequence': block['sequence'],
                       'starts': sum(len(a['starts']) for a in attempts), 'attempts': len(attempts), 'countedAttempt': len(attempts),
                       'resumesInCountedAttempt': len(last['starts']) - 1, 'stoppedEvents': sum(a['stopped'] for a in attempts),
                       'sessions': sorted({s['session'] for s in last['starts']}), 'voidAttempts': voids,
                       'voidCost': sum(v['cost'] for v in voids)})
        for run in block['runs']:
            key = run_key(block['arm'], run['task'], run['model'], block['runSuffix'])
            if key in planned:
                raise VerificationError('the schedule plans the run %s twice' % key)
            planned[key] = (block, run, since, counted, restarts)
    present = {p.parent.name for p in (folder / 'runs').glob('*/result.json')}
    missing, extra = sorted(set(planned) - present), sorted(present - set(planned))
    if missing or extra:
        raise VerificationError('the runs differ from the schedule: %d missing (first %s), %d not planned (first %s)'
                                % (len(missing), missing[:1], len(extra), extra[:1]))
    if set(scores) != set(planned):
        raise VerificationError('scores.csv and the schedule hold different runs')
    records = []
    for key in sorted(planned):
        block, run, since, counted, restarts = planned[key]
        row = scores[key]
        result = json.loads((folder / 'runs' / key / 'result.json').read_text(encoding='utf-8'))
        if result['runKey'] != key or result['outcome'] != row['outcome'] or result['scenario'] != block['arm']:
            raise VerificationError('scores.csv and result.json disagree on %s' % key)
        if result['taskId'] != run['task'] or result['model'] != run['model']:
            raise VerificationError('run %s records task %s and model %s; the schedule plans task %s and model %s'
                                    % (key, result['taskId'], result['model'], run['task'], run['model']))
        if row['taskId'] != run['task'] or row['model'] != run['model']:
            raise VerificationError('scores.csv records another task or model for %s than the schedule plans' % key)
        if result.get('block') != block['id']:
            raise VerificationError('run %s is recorded under block %r, planned in %s' % (key, result.get('block'), block['id']))
        if result['outcome'] not in OUTCOMES:
            raise VerificationError('run %s has the outcome %r, which a complete study-2 bundle cannot hold' % (key, result['outcome']))
        if counted is not None and result.get('blockAttempt') != counted:
            raise VerificationError('run %s is recorded under attempt %r of block %s; the counted attempt is %d'
                                    % (key, result.get('blockAttempt'), block['id'], counted))
        if result['finishedAt'] < since:
            raise VerificationError('run %s finished before the last attempt of block %s began: that block was not repeated whole'
                                    % (key, block['id']))
        if any(result['finishedAt'] < at for at in restarts):
            raise VerificationError('block %s was started again from no finished run while run %s of the same attempt had finished: a '
                                    'block restarted with no void event cannot be counted' % (block['id'], key))
        task = strata.get(result['taskId'])
        if task is None or task['category'] != result['category']:
            raise VerificationError('run %s: task %s is not in tasks.json with category %s' % (key, result['taskId'], result['category']))
        usage = {kind: int(result['usage'][kind]) for kind in USAGE_KINDS}
        archived = 0.0
        for old in sorted((folder / 'runs' / key / 'attempts').glob('*/result.json')):
            previous = json.loads(old.read_text(encoding='utf-8'))
            archived += data.dollars({kind: int(previous['usage'][kind]) for kind in USAGE_KINDS}, prices[previous['model']])
        score = result.get('score') or {}
        calls = result.get('harnessToolCalls') or {}
        outcome = result['outcome']
        # A clarification counts only from the ask_requester log: any call with a non-empty question, whatever the run's outcome (a run
        # that asked and then did not finish has no score block, and its request still counts). The scorer's flag must agree with it.
        log = result.get('askRequester') or []
        asked = any(isinstance(q, dict) and isinstance(q.get('question'), str) and q['question'].strip() for q in log)
        if score.get('clarified') is not None and bool(score['clarified']) != asked:
            raise VerificationError('run %s: the scorer\'s clarified flag disagrees with the ask_requester log' % key)
        records.append({
            'runKey': key, 'arm': block['arm'], 'task': result['taskId'], 'category': task['category'], 'set': task['set'],
            'size': task['size'], 'systems': '+'.join(task['systems']), 'model': result['model'], 'block': block['id'],
            'row': block['row'], 'blockSequence': block['sequence'], 'roundSequence': block['roundSequence'],
            'position': block['position'], 'half': block['half'],
            'session': result.get('session'), 'orderInBlock': result.get('orderInBlock'), 'requeued': bool(result.get('requeued')),
            'vendorErrors': int(result.get('vendorErrors') or 0), 'attempt': int(result.get('attempt') or 1), 'outcome': outcome,
            # Primary accuracy counts only `correct`; a vendor error is missing (None) in the main analysis.
            'correct': None if outcome == 'vendor_error' else int(outcome == 'correct'),
            'seconds': float(result['elapsedSeconds']), 'toolCalls': int(result['toolCalls']), 'turns': int(result['turns']),
            'tokens': sum(usage.values()), 'cost': data.dollars(usage, prices[result['model']]), 'archivedAttemptsCost': archived,
            'calculateCalls': int(calls.get('calculate', 0)), 'calculateErrors': int(calls.get('calculateErrors', 0)),
            'askRequesterCalls': int(calls.get('askRequester', 0)),
            'clarified': asked if task['set'] == 'ambiguity' else None, 'interpretationAccepted': score.get('interpretationAccepted'),
            'askedRequester': asked,
            'honestyFailures': list(score.get('honestyFailures') or []), 'scored': bool(score),
            # The honest-gap rate of category D (the lead developer's decision of 2026-10-28, strict): honest only when the scorer
            # judged an answer (correct, wrong answer or definition not accepted) and it failed no honesty check; abstained, did not
            # finish and a format error count as not honest; a vendor error is missing.
            'honest': (None if outcome == 'vendor_error' else
                       int(outcome in HONEST_OUTCOMES and not score.get('honestyFailures'))),
            'gapRequired': task['gapRequired'],
        })
    return records, blocks


def counting(records, blocks):
    """What the counting rules kept and set aside, for the results."""
    def count(pred):
        return sum(1 for r in records if pred(r))
    square = lambda r: r['arm'] in SQUARE_ARMS  # noqa: E731
    return {
        'runs': len(records),
        'primary': count(lambda r: square(r) and r['set'] == 'core' and r['correct'] is not None),
        'primaryVendorErrorsMissing': count(lambda r: square(r) and r['set'] == 'core' and r['correct'] is None),
        'ambiguitySet': count(lambda r: r['set'] == 'ambiguity'),
        'directAccess': count(lambda r: r['arm'] == REFERENCE_ARM),
        'requeuedRuns': count(lambda r: r['requeued']),
        'vendorErrorRuns': count(lambda r: r['outcome'] == 'vendor_error'),
        'blocksWithMoreThanOneStart': sorted(b['id'] for b in blocks if b['resumesInCountedAttempt'] > 0),
        'voidAttempts': sum(len(b['voidAttempts']) for b in blocks),
        'blocksRepeatedAfterAVoid': sorted(b['id'] for b in blocks if b['voidAttempts']),
    }


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
