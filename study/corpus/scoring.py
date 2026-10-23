"""Reference scorer of the study corpus: a pure function of one submitted answer, the task's schema and the task's expected entry.

No judge, no model and no network: the score is decided by the data of expected.json alone, so it is blind to scenario and model.
Standard library only. The harness may import this module or re-implement the same rules; the rules are in README.md.

Outcomes of score():
  correct                    the answer matches the expected answer or one of its declared variants (variant tags are reported)
  wrong_answer               the answer fits the schema and does not match
  format_error               the answer does not fit the task's schema; counts as a failure, tagged apart from wrong_answer, and
                             contentCorrectDespiteFormat says whether a lenient reading of the same content would have matched
  silent_guess               category F only: the content is right under the stated definition but the agent neither asked nor stated
  definition_not_accepted    category F only: the stated definition is not one of the accepted definitions of the task
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

NUMBER_TYPES = (int, float)


# ---------------------------------------------------------------- normalization

def norm(value):
    """Case-, space-, hyphen- and underscore-insensitive form of a string; other values are returned unchanged."""
    if isinstance(value, str):
        return re.sub(r'[\s_\-]+', '_', value.strip().casefold())
    return value


def to_decimal(value):
    if isinstance(value, bool):
        raise InvalidOperation
    if isinstance(value, float):
        value = repr(value)
    return Decimal(str(value).strip())


def money(value):
    return to_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def one_decimal(value):
    return to_decimal(value).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def get_path(data, path):
    """Value at a dotted path; (False, None) when a step is missing."""
    cur = data
    for step in path.split('.'):
        if isinstance(cur, dict) and step in cur:
            cur = cur[step]
        else:
            return False, None
    return True, cur


# ---------------------------------------------------------------- the mini schema validator

def _type_ok(value, name):
    if name == 'string':
        return isinstance(value, str)
    if name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if name == 'number':
        return isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)
    if name == 'boolean':
        return isinstance(value, bool)
    if name == 'null':
        return value is None
    if name == 'array':
        return isinstance(value, list)
    if name == 'object':
        return isinstance(value, dict)
    raise ValueError('unknown schema type ' + name)


def validate(value, schema, path='$'):
    """Errors of `value` against `schema` (the subset of JSON Schema the corpus uses); an empty list means it fits."""
    errors = []
    kinds = schema.get('type')
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(_type_ok(value, kind) for kind in kinds):
            return ['%s: expected %s' % (path, '|'.join(kinds))]
    if 'enum' in schema and value not in schema['enum']:
        errors.append('%s: not one of %s' % (path, schema['enum']))
    if 'pattern' in schema and isinstance(value, str) and not re.fullmatch(schema['pattern'], value):
        errors.append('%s: does not match %s' % (path, schema['pattern']))
    if isinstance(value, dict):
        for name in schema.get('required', []):
            if name not in value:
                errors.append('%s: missing %s' % (path, name))
        props = schema.get('properties', {})
        for name, item in value.items():
            if name in props:
                errors.extend(validate(item, props[name], path + '.' + name))
            elif schema.get('additionalProperties', True) is False:
                errors.append('%s: unexpected field %s' % (path, name))
    if isinstance(value, list) and 'items' in schema:
        for index, item in enumerate(value):
            errors.extend(validate(item, schema['items'], '%s[%d]' % (path, index)))
    return errors


def leniently_read(value, schema):
    """A lenient reading of an answer that failed its schema: unknown fields dropped, numeric strings read as numbers, a lone value
    wrapped into an array. Used only to tell a format error from a wrong answer."""
    kinds = schema.get('type')
    kinds = [kinds] if isinstance(kinds, str) else (kinds or [])
    if isinstance(value, dict) and 'object' in kinds or (isinstance(value, dict) and 'properties' in schema):
        props = schema.get('properties', {})
        return {name: leniently_read(item, props[name]) for name, item in value.items() if name in props}
    if 'array' in kinds:
        if isinstance(value, str):
            value = [part for part in re.split(r'[\s,;]+', value) if part]
        items = value if isinstance(value, list) else [value]
        return [leniently_read(item, schema.get('items', {})) for item in items]
    if isinstance(value, str) and ('integer' in kinds or 'number' in kinds) and 'string' not in kinds:
        try:
            number = Decimal(value.strip())
            return int(number) if 'integer' in kinds and number == number.to_integral_value() else float(number)
        except InvalidOperation:
            return value
    return value


# ---------------------------------------------------------------- the checks

def scalar_matches(value, spec):
    """spec is one of {"equals": v}, {"in": [..]}, {"decimal": v}, {"money": v}, {"int": v}, {"bool": v}, {"null": true}."""
    try:
        if 'equals' in spec:
            return norm(value) == norm(spec['equals'])
        if 'in' in spec:
            return norm(value) in [norm(item) for item in spec['in']]
        if 'decimal' in spec:
            return to_decimal(value) == to_decimal(spec['decimal'])
        if 'money' in spec:
            return money(value) == money(spec['money'])
        if 'int' in spec:
            return isinstance(value, int) and not isinstance(value, bool) and value == spec['int']
        if 'bool' in spec:
            return isinstance(value, bool) and value is spec['bool']
        if 'null' in spec:
            return value is None
    except (InvalidOperation, ValueError, TypeError):
        return False
    raise ValueError('unknown scalar spec %s' % spec)


def run_check(answer, check):
    """True when the check passes. Kinds: scalar (a path and a scalar spec), set, keyed, empty, fields_null, ids_within, subset."""
    kind = check['op']
    found, value = get_path(answer, check['path'])
    if kind == 'scalar':
        return found and scalar_matches(value, check['spec'])
    if kind == 'empty':
        return (not found) or value is None or value == []
    if kind in ('set', 'subset'):
        if not found or not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return False
        got, want = {norm(item) for item in value}, {norm(item) for item in check['values']}
        return got == want if kind == 'set' else got <= want
    if kind in ('keyed', 'ids_within', 'fields_null'):
        if not found or not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            return False
        key = check.get('key')
        if kind == 'fields_null':
            return all(item.get(field) is None for item in value for field in check['fields'])
        keys = [norm(item.get(key)) for item in value]
        if kind == 'ids_within':
            return {key_ for key_ in keys} <= {norm(item) for item in check['allowed']}
        if len(set(keys)) != len(keys) or set(keys) != {norm(k) for k in check['fields']}:
            return False
        by_key = {norm(item.get(key)): item for item in value}
        for want_key, field_specs in check['fields'].items():
            item = by_key[norm(want_key)]
            for field, spec in field_specs.items():
                if field not in item or not scalar_matches(item[field], spec):
                    return False
        for want_key, extra in check.get('optional', {}).items():
            item = by_key[norm(want_key)]
            for field, spec in extra.items():
                if item.get(field) is not None and not scalar_matches(item[field], spec):
                    return False
        return True
    raise ValueError('unknown check op %s' % kind)


def run_checks(answer, checks):
    failed = [check.get('name') or '%s:%s' % (check['op'], check['path']) for check in checks if not run_check(answer, check)]
    honesty = [check.get('name') for check in checks if check.get('honesty') and not run_check(answer, check)]
    return failed, honesty


# ---------------------------------------------------------------- category F (data-driven, no oracle access)

def _asked_or_stated_ok(answer):
    return answer.get('askedOrStated') in ('ASKED', 'STATED')


def score_senior_officers(answer, data):
    """Task 15. data holds, for each accepted definition, the expected (withSenior, outOf, percentage) of each accepted counting policy."""
    ranks = frozenset(norm(rank) for rank in answer['definitionUsed']['seniorRanks'])
    for definition in data['definitions']:
        if frozenset(norm(rank) for rank in definition['seniorRanks']) == ranks:
            break
    else:
        return 'definition_not_accepted', [], ['definition ' + ','.join(sorted(ranks))]
    tags = []
    for policy in definition['policies']:
        if (answer['withSeniorOfficer'] == policy['withSeniorOfficer'] and answer['outOf'] == policy['outOf']
                and one_decimal(answer['percentage']) == one_decimal(policy['percentage'])):
            tags.append('policy:' + policy['name'])
            break
    if not tags:
        return 'wrong_answer', [], ['counts']
    return ('correct' if _asked_or_stated_ok(answer) else 'silent_guess'), tags, []


def score_most_expensive(answer, data):
    """Task 16. data holds, for each accepted cost basis, the missions in descending order of cost; any accepted N is a prefix of it."""
    basis = norm(answer['costBasis'])
    ranking = data['rankings'].get(basis.upper())
    if ranking is None or answer['topN'] not in data['acceptedCounts']:
        return 'definition_not_accepted', [], ['costBasis/topN']
    want = ranking[:answer['topN']]
    if {norm(item) for item in answer['missionIds']} != {norm(item) for item in want} or len(answer['missionIds']) != len(want):
        return 'wrong_answer', [], ['missionIds']
    return ('correct' if _asked_or_stated_ok(answer) else 'silent_guess'), ['basis:' + basis, 'topN:%d' % answer['topN']], []


CUSTOM = {'senior_officers': score_senior_officers, 'most_expensive': score_most_expensive}


# ---------------------------------------------------------------- one task

def _evaluate(answer, expected):
    """(outcome, tags, failed, honesty_failures) of a schema-valid answer."""
    if 'custom' in expected:
        outcome, tags, failed = CUSTOM[expected['custom']](answer, expected['data'])
        return outcome, tags, failed, []
    failed, honesty = run_checks(answer, expected['checks'])
    if not failed:
        return 'correct', [], [], []
    for variant in expected.get('variants', []):
        v_failed, _ = run_checks(answer, variant['checks'])
        if not v_failed:
            return 'correct', ['variant:' + variant['name']], [], []
    return 'wrong_answer', [], failed, honesty


def score(submission, schema, expected):
    """Score one submitted answer. Returns a dict: score (1 or 0), outcome, tags, failedChecks, honestyFailures, contentCorrectDespiteFormat."""
    errors = validate(submission, schema)
    if errors:
        lenient = leniently_read(submission, schema)
        correct = False
        if not validate(lenient, schema):
            correct = _evaluate(lenient, expected)[0] == 'correct'
        return {'score': 0, 'outcome': 'format_error', 'tags': [], 'failedChecks': [], 'honestyFailures': [], 'formatErrors': errors[:10],
                'contentCorrectDespiteFormat': correct}
    outcome, tags, failed, honesty = _evaluate(submission, expected)
    return {'score': 1 if outcome == 'correct' else 0, 'outcome': outcome, 'tags': tags, 'failedChecks': failed, 'honestyFailures': honesty,
            'formatErrors': [], 'contentCorrectDespiteFormat': None}
