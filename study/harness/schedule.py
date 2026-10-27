"""The block schedule of study 2: a Williams square of four rounds for the four full arms, then the Direct Access reference block.

Everything is computed from the config and its seed, so the same seed gives the same schedule (docs/STUDY-2-DESIGN.md, the schedule):

- The square is fixed: rows `a b d c`, `b c a d`, `c d b a`, `d a c b`. Every letter stands once in every position, and each letter directly
  follows each other letter exactly once.
- A seeded draw assigns the four arms to the letters, and a seeded draw orders the four rows (the rounds) in time.
- The tasks are split into two halves, stratified by set, category, size and systems. Rows 1 and 3 run half H1 and rows 2 and 4 run H2,
  whatever order the rows run in, because only those pairs give every arm the same position total (5).
- Within a half, a draw balanced by category gives each task one model in one of the half's two rows and the other model in the other row.
  The model of a task is the same for all four arms of a row, so the comparisons stay paired within a round.
- Inside a block the tasks are shuffled from a seed of their own (which also places the outage tasks) with the models alternating.
- The Direct Access reference block comes last: every task with both models, the models interleaved per task.

Standard library only. A sub-seed is the text '<seed>/<label>', as in the study-1 plan.
"""
import random

DESIGN = 'williams-4-half'
LETTERS = ('a', 'b', 'c', 'd')
SQUARE = (('a', 'b', 'd', 'c'),
          ('b', 'c', 'a', 'd'),
          ('c', 'd', 'b', 'a'),
          ('d', 'a', 'c', 'b'))
HALF_OF_ROW = {1: 'H1', 2: 'H2', 3: 'H1', 4: 'H2'}
ROWS_OF_HALF = {'H1': (1, 3), 'H2': (2, 4)}
REFERENCE = 'ref'
_KEYS = {'design', 'arms', 'reference'}


def validate(block, scenarios, models):
    """Refuse a malformed `schedule` block, naming the field. `scenarios` are the config's scenario names, `models` its models."""
    if not isinstance(block, dict):
        raise ValueError('schedule must be an object')
    unknown = sorted(set(block) - _KEYS)
    if unknown:
        raise ValueError('schedule has unknown keys: %s' % ', '.join(unknown))
    if block.get('design') != DESIGN:
        raise ValueError('schedule.design must be %s' % DESIGN)
    arms = block.get('arms')
    if not (isinstance(arms, list) and len(arms) == 4 and len(set(arms)) == 4 and all(isinstance(a, str) for a in arms)):
        raise ValueError('schedule.arms must name four different scenarios')
    reference = block.get('reference')
    if not (isinstance(reference, str) and reference):
        raise ValueError('schedule.reference must name the scenario of the reference block')
    if reference in arms:
        raise ValueError('schedule.reference must not be one of schedule.arms')
    for name in arms + [reference]:
        if name not in scenarios:
            raise ValueError('schedule names the scenario %s, which the config does not declare' % name)
    if len(models) != 2 or len(set(models)) != 2:
        raise ValueError('the schedule splits the tasks between exactly two models')


def scenarios_of(block):
    """The scenarios the schedule uses, the reference last."""
    return list(block['arms']) + [block['reference']]


def _rng(seed, label):
    return random.Random('%s/%s' % (seed, label))


def stratum(task):
    """The stratum of a task for the split into halves: set, category, size and systems (missing fields count as empty)."""
    systems = task.get('systems') or []
    return (str(task.get('set') or 'core'), str(task.get('category') or ''), str(task.get('size') or ''), '+'.join(sorted(str(s) for s in systems)))


def deal(items, key, rng):
    """Group `items` by `key`, shuffle each group with `rng`, put the groups one after the other in sorted key order and number the result.
    Dealing the numbers alternately to two sides splits every group evenly, within one item, and the whole list too."""
    groups = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    out = []
    for name in sorted(groups):
        group = sorted(groups[name])
        rng.shuffle(group)
        out.extend(group)
    return out


def interleave(first, second, rng):
    """Alternate two lists that differ in length by at most one, starting with the longer one, or with a seeded choice when they are equal."""
    if len(first) < len(second) or (len(first) == len(second) and rng.random() < 0.5):
        first, second = second, first
    out = []
    for i in range(len(first)):
        out.append(first[i])
        if i < len(second):
            out.append(second[i])
    return out


def build(config, tasks):
    """The whole schedule as data. `tasks` are the task dicts of the corpus (id, category and optionally set, size and systems)."""
    block = config['schedule']
    seed = config['seed']
    models = list(config['models'])
    by_id = {t['id']: t for t in tasks}
    arms = list(block['arms'])
    _rng(seed, 'letters').shuffle(arms)
    letters = dict(zip(LETTERS, arms))
    order = [1, 2, 3, 4]
    _rng(seed, 'rounds').shuffle(order)

    dealt = deal(list(by_id), lambda task_id: stratum(by_id[task_id]), _rng(seed, 'halves'))
    halves = {'H1': sorted(dealt[0::2]), 'H2': sorted(dealt[1::2])}

    model_of = {}  # row -> task -> model
    for half, (first_row, second_row) in sorted(ROWS_OF_HALF.items()):
        rng = _rng(seed, 'models/' + half)
        pair = list(models)
        rng.shuffle(pair)
        split = deal(halves[half], lambda task_id: str(by_id[task_id].get('category') or ''), rng)
        model_of.setdefault(first_row, {})
        model_of.setdefault(second_row, {})
        for index, task_id in enumerate(split):
            one, other = (pair[0], pair[1]) if index % 2 == 0 else (pair[1], pair[0])
            model_of[first_row][task_id] = one
            model_of[second_row][task_id] = other

    blocks = []
    for sequence_in_rounds, row in enumerate(order):
        half = HALF_OF_ROW[row]
        for position, letter in enumerate(SQUARE[row - 1], start=1):
            arm = letters[letter]
            rng = _rng(seed, 'order/r%d/%s' % (row, arm))
            per_model = {m: sorted(t for t in halves[half] if model_of[row][t] == m) for m in models}
            for m in models:
                rng.shuffle(per_model[m])
            runs = interleave(per_model[models[0]], per_model[models[1]], rng)
            runs = [{'task': task_id, 'model': model_of[row][task_id]} for task_id in runs]
            blocks.append({'id': 'r%d-%s' % (row, arm), 'sequence': len(blocks) + 1, 'roundSequence': sequence_in_rounds + 1, 'row': row,
                           'position': position, 'letter': letter, 'arm': arm, 'half': half, 'runSuffix': 'r%d' % row, 'runs': runs})

    reference = block['reference']
    rng = _rng(seed, 'order/' + REFERENCE)
    ids = sorted(by_id)
    rng.shuffle(ids)
    offset = rng.randrange(2)
    runs = []
    for index, task_id in enumerate(ids):
        pair = models if (offset + index) % 2 == 0 else list(reversed(models))
        runs.extend({'task': task_id, 'model': m} for m in pair)
    blocks.append({'id': '%s-%s' % (REFERENCE, reference), 'sequence': len(blocks) + 1, 'roundSequence': None, 'row': None, 'position': None,
                   'letter': None, 'arm': reference, 'half': None, 'runSuffix': REFERENCE, 'runs': runs})

    return {'design': DESIGN, 'seed': seed, 'square': [list(row) for row in SQUARE], 'letters': letters, 'roundOrder': order,
            'halfOfRow': {str(row): half for row, half in sorted(HALF_OF_ROW.items())}, 'halves': halves,
            'modelOfTask': {str(row): dict(sorted(model_of[row].items())) for row in sorted(model_of)}, 'reference': reference,
            'blocks': blocks}


def run_key(arm, task_id, model, suffix):
    """The key of one run of the schedule: `<arm>__<task>__<model>__r<row>`, or `__ref` in the reference block."""
    return '%s__%s__%s__%s' % (arm, task_id, model, suffix)
