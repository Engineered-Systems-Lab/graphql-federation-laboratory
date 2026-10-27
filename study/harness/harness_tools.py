"""The two tools the harness offers beside a scenario's MCP tools, identical in every arm and run (docs/STUDY-2-DESIGN.md, the tools).

`calculate` computes over results the agent already obtained in the same run, named by result id. It never fetches: it has no network, file,
database, backend or answer-key access, and it never sees another run's results. Its operations are generic only (count, distinct, group_by
with count or sum, sort, filter by literal comparison, union, intersection, difference and arithmetic); none knows a domain term.

`ask_requester` logs the agent's question with its run and always returns the same fixed text.

Result ids. When `calculate` is offered, every result of a scenario tool and every successful `calculate` result gets an id `<tag>-<n>`:
`tag` is four hex digits unique to the run and its attempt, `n` counts from 1. The id is shown to the agent as the first line of the result,
`result_id: <id>`, and the result is stored in the run's `results.jsonl`, which the bundle checksum covers. An id with another tag belongs to
another run and is refused; an id with this run's tag that was never given is unknown and refused. Every refusal is a tool error, logged like
any other call.

Reading a result. A source names a result id and an optional path: dot-separated keys or list positions, where `*` takes every element of a
list (any other value counts as a list of one). A text met while walking the path, or at its end, is read as JSON when it starts with `{` or
`[`, or as XML when it starts with `<`. XML is read generically: local tag names without namespaces, attributes as `@name`, an element's own
text as `#text` beside children or attributes, a leaf as its text, and an element name that repeats under one parent as a list.

Standard library only.
"""
import json
import re
import time
import xml.etree.ElementTree as ElementTree
from decimal import Decimal, InvalidOperation
from pathlib import Path

from budget import estimate_tokens
from study_common import append_jsonl, sha256_bytes, utc_now

VERSION = 1
CALCULATE, ASK_REQUESTER = 'calculate', 'ask_requester'
NAMES = (CALCULATE, ASK_REQUESTER)
ASK_TEXT = 'No requester response is available during this evaluation.'
ID_LINE = 'result_id: %s\n'
OPERATIONS = ('count', 'distinct', 'group_by', 'sort', 'filter', 'union', 'intersection', 'difference', 'arithmetic')
COMPARISONS = ('eq', 'ne', 'lt', 'le', 'gt', 'ge')
OPERATORS = ('add', 'subtract', 'multiply', 'divide')
LIMITS = {'maxSourceChars': 5_000_000, 'maxRecords': 100_000, 'maxOutputChars': 50_000, 'maxSources': 100}
_ID = re.compile(r'^([0-9a-f]{4})-([1-9][0-9]*)$')
_NUMBER = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$')
_SCALAR = {'type': ['string', 'number', 'boolean', 'null']}
_SOURCE = {'type': 'object', 'additionalProperties': False,
           'properties': {'result_id': {'type': 'string', 'description': 'The id from the first line of an earlier result of this task.'},
                          'path': {'type': 'string', 'description': 'Optional. Dot-separated keys or list positions into that result; * takes '
                                   'every element of a list. A text that holds JSON or XML is read as such. Empty means the whole result.'}},
           'required': ['result_id']}

CALCULATE_TOOL = {
    'name': CALCULATE,
    'description': ('Compute over results you already obtained in this task; it fetches nothing. Every tool result starts with a line '
                    'result_id: <id>. Name one or more results in sources, each with an optional path to the part to use, and one generic '
                    'operation. The records are the elements found at the paths of all sources, one after the other. count: the number of '
                    'records. distinct: the distinct values of field. group_by: groups by the fields in group_by, with aggregate count or '
                    'sum of sum_field. sort: the records ordered by field (descending optional). filter: the records for which every '
                    'condition holds (eq, ne, lt, le, gt, ge against a literal value). union, intersection, difference: set operations on '
                    'the values of field taken per source (difference: the first source minus the others). arithmetic: operator add, '
                    'subtract, multiply or divide over operands, each a number or {result_id, path} naming one number. fields and limit '
                    'shorten a list of records; round sets decimal places. A field is a dot-separated path inside a record; empty means the '
                    'record itself. The result has a result_id of its own.'),
    'input_schema': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'operation': {'type': 'string', 'enum': list(OPERATIONS)},
            'sources': {'type': 'array', 'items': _SOURCE},
            'field': {'type': 'string'},
            'group_by': {'type': 'array', 'items': {'type': 'string'}},
            'aggregate': {'type': 'string', 'enum': ['count', 'sum']},
            'sum_field': {'type': 'string'},
            'conditions': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                                      'properties': {'field': {'type': 'string'}, 'op': {'type': 'string', 'enum': list(COMPARISONS)},
                                                                     'value': _SCALAR},
                                                      'required': ['field', 'op', 'value']}},
            'descending': {'type': 'boolean'},
            'operator': {'type': 'string', 'enum': list(OPERATORS)},
            'operands': {'type': 'array', 'items': {'type': ['number', 'object']}},
            'fields': {'type': 'array', 'items': {'type': 'string'}},
            'limit': {'type': 'integer', 'minimum': 1},
            'round': {'type': 'integer', 'minimum': 0, 'maximum': 12},
        },
        'required': ['operation'],
    },
}

ASK_REQUESTER_TOOL = {
    'name': ASK_REQUESTER,
    'description': 'Ask the person who requested this task a clarifying question about what they mean.',
    'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {'question': {'type': 'string'}}, 'required': ['question']},
}

TOOLS = {CALCULATE: CALCULATE_TOOL, ASK_REQUESTER: ASK_REQUESTER_TOOL}


def validate(names):
    """Refuse an unknown or repeated harness tool name in the config's `harness_tools`."""
    if not (isinstance(names, list) and all(isinstance(n, str) for n in names)):
        raise ValueError('harness_tools must be a list of tool names')
    unknown = sorted(set(names) - set(NAMES))
    if unknown or len(set(names)) != len(names):
        raise ValueError('harness_tools may name each of %s once (got %s)' % (', '.join(NAMES), ', '.join(names)))


def describe(names):
    """The harness tools as the manifest and the plan identity record them."""
    names = [n for n in NAMES if n in names]
    out = {'version': VERSION, 'names': names, 'tools': [TOOLS[n] for n in names]}
    if ASK_REQUESTER in names:
        out['askRequesterText'] = ASK_TEXT
    if CALCULATE in names:
        out.update({'resultIdFormat': '<4 hex run tag>-<n>, shown as the first line "result_id: <id>" of every scenario tool result and '
                                      'every successful calculate result', 'operations': list(OPERATIONS), 'limits': dict(LIMITS)})
    return out


def run_tag(run_key, attempt):
    """Four hex digits unique to one attempt of one run."""
    return sha256_bytes(('%s/%s' % (run_key, attempt)).encode('utf-8'))[:4]


class CalculationError(Exception):
    """A refused calculate call; its text goes back to the agent as a tool error."""


# ---------------------------------------------------------------------------------------------------------------- the result store
class ResultStore:
    """The tool results of one run attempt, kept in memory and appended to `path` (results.jsonl) as they arrive, through `redact` (the
    harness's key redactor) like everything else the harness writes."""

    def __init__(self, path, tag, redact=lambda value: value):
        self.path, self.tag, self.redact = Path(path), tag, redact
        self.items = {}
        self.count = 0

    def add(self, tool, arguments, text, is_error):
        self.count += 1
        result_id = '%s-%d' % (self.tag, self.count)
        self.items[result_id] = text
        data = text.encode('utf-8')
        append_jsonl(self.path, self.redact({'resultId': result_id, 'at': utc_now(), 'tool': tool, 'arguments': arguments,
                                             'isError': bool(is_error), 'bytes': len(data), 'sha256': sha256_bytes(data), 'text': text}))
        return result_id

    def get(self, result_id):
        match = _ID.match(str(result_id))
        if not match:
            raise CalculationError('%r is not a result id: an id looks like %s-1 and is shown as the first line of a result' % (result_id, self.tag))
        if match.group(1) != self.tag:
            raise CalculationError('the result id %s belongs to another run: only results of this task can be used' % result_id)
        if result_id not in self.items:
            raise CalculationError('the result id %s is unknown in this task' % result_id)
        return self.items[result_id]


# ---------------------------------------------------------------------------------------------------------------- reading results
def _local(tag):
    return tag.rsplit('}', 1)[-1].split(':')[-1]


def _xml_value(element):
    children, attributes = list(element), {'@' + _local(k): v for k, v in element.attrib.items()}
    text = (element.text or '').strip()
    if not children and not attributes:
        return text
    out, repeated = dict(attributes), set()
    for child in children:
        name, value = _local(child.tag), _xml_value(child)
        if name in repeated:
            out[name].append(value)
        elif name in out:
            out[name] = [out[name], value]
            repeated.add(name)
        else:
            out[name] = value
    if text:
        out['#text'] = text
    return out


def read_text(text):
    """A text holding JSON or XML as data; any other text stays text."""
    stripped = text.strip()
    if len(stripped) > LIMITS['maxSourceChars']:
        raise CalculationError('the result is longer than %d characters' % LIMITS['maxSourceChars'])
    if stripped[:1] in ('{', '['):
        try:
            return json.loads(stripped, parse_float=Decimal)
        except ValueError:
            return text
    if stripped[:1] == '<':
        if '<!DOCTYPE' in stripped.upper() or '<!ENTITY' in stripped.upper():
            raise CalculationError('an XML text with a document type or entity declarations is not read')
        try:
            root = ElementTree.fromstring(stripped)
        except ElementTree.ParseError as error:
            raise CalculationError('the XML text cannot be read: %s' % error)
        return {_local(root.tag): _xml_value(root)}
    return text


def _decoded(value):
    return read_text(value) if isinstance(value, str) else value


def _segments(path):
    path = (path or '').strip()
    return [s for s in path.split('.')] if path else []


def _step(value, segment, where):
    value = _decoded(value)
    if isinstance(value, dict):
        if segment in value:
            return value[segment]
        raise KeyError('%s has no key %r' % (where or 'the result', segment))
    if isinstance(value, list):
        if re.fullmatch(r'-?\d+', segment):
            index = int(segment)
            if -len(value) <= index < len(value):
                return value[index]
            raise KeyError('%s has no position %s (it has %d elements)' % (where or 'the result', segment, len(value)))
        raise KeyError('%s is a list: use a position or * instead of %r' % (where or 'the result', segment))
    raise KeyError('%s is a single value, so it has no %r' % (where or 'the result', segment))


def walk(value, path):
    """(values, missing): the values at `path` inside `value`. Before the first `*` a missing step is an error; after it, an element that
    lacks the step is left out and counted in `missing`."""
    current, spread, missing, where = [value], False, 0, ''
    for segment in _segments(path):
        nxt = []
        for item in current:
            if segment == '*':
                item = _decoded(item)
                nxt.extend(item if isinstance(item, list) else [item])
                continue
            try:
                nxt.append(_step(item, segment, where))
            except KeyError as error:
                if not spread:
                    raise CalculationError('path %r: %s' % (path, error.args[0]))
                missing += 1
        if segment == '*':
            spread = True
        current = nxt
        where = (where + '.' + segment) if where else segment
    return [_decoded(v) for v in current], missing


def records_of(values):
    """The records of a source: a list at the end of the path gives its elements, anything else counts as one record."""
    out = []
    for value in values:
        out.extend(value if isinstance(value, list) else [value])
    return out


def field_of(record, field):
    """The value at a dot-separated `field` inside a record, or None when it is missing."""
    value = record
    for segment in _segments(field):
        try:
            value = _step(value, segment, '')
        except (KeyError, CalculationError):
            return None
    return _decoded(value) if isinstance(value, str) and value.strip()[:1] in ('{', '[', '<') else value


# ---------------------------------------------------------------------------------------------------------------- values
def number(value):
    """A Decimal for a number or a numeric text; None for anything else (booleans included)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str) and _NUMBER.match(value.strip()):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


def plain(value):
    """A value made ready for JSON: Decimals become whole numbers or floats."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            return str(value)
        return int(value) if value == value.to_integral_value() and abs(value) < 10 ** 18 else float(value)
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def canonical(value):
    return json.dumps(plain(value), sort_keys=True, ensure_ascii=False)


def compare(value, op, literal):
    """A literal comparison. A numeric literal compares numerically with numbers and numeric texts; a text literal compares with the value
    as text; true, false and null compare by equality only."""
    if isinstance(literal, bool) or literal is None:
        if op not in ('eq', 'ne'):
            raise CalculationError('%s cannot compare with %s; use eq or ne' % (op, json.dumps(literal)))
        equal = (value is literal) or (isinstance(value, str) and literal is not None and value.strip().lower() == str(literal).lower())
        return equal if op == 'eq' else not equal
    if isinstance(value, (dict, list)) or value is None:
        return op == 'ne'
    if isinstance(literal, (int, float)):
        left, right = number(value), number(literal)
        if left is None:
            return op == 'ne'
    elif isinstance(literal, str):
        left, right = (plain(value) if not isinstance(value, str) else value), literal
        left = left if isinstance(left, str) else json.dumps(left)
    else:
        raise CalculationError('a condition value must be a text, a number, true, false or null')
    return {'eq': left == right, 'ne': left != right, 'lt': left < right, 'le': left <= right, 'gt': left > right, 'ge': left >= right}[op]


def _sort_key(values):
    numbers = [number(v) for v in values]
    if all(n is not None for n in numbers):
        return lambda i: (0, numbers[i])
    return lambda i: (0 if values[i] is not None else 1, canonical(values[i]))


# ---------------------------------------------------------------------------------------------------------------- calculate
class Calculator:
    def __init__(self, store):
        self.store = store

    def _sources(self, arguments, minimum=1):
        sources = arguments.get('sources')
        if not isinstance(sources, list) or len(sources) < minimum:
            raise CalculationError('%s needs at least %d source%s' % (arguments.get('operation'), minimum, '' if minimum == 1 else 's'))
        if len(sources) > LIMITS['maxSources']:
            raise CalculationError('at most %d sources' % LIMITS['maxSources'])
        out, ids, size, missing = [], [], 0, 0
        for source in sources:
            if not isinstance(source, dict) or 'result_id' not in source:
                raise CalculationError('every source needs a result_id')
            text = self.store.get(source['result_id'])
            ids.append(source['result_id'])
            size += len(text.encode('utf-8'))
            values, lost = walk(read_text(text), source.get('path'))
            missing += lost
            out.append(records_of(values))
        if sum(len(r) for r in out) > LIMITS['maxRecords']:
            raise CalculationError('more than %d records' % LIMITS['maxRecords'])
        return out, ids, size, missing

    @staticmethod
    def _shorten(records, arguments):
        fields = arguments.get('fields')
        if fields:
            records = [{f: field_of(r, f) for f in fields} for r in records]
        limit = arguments.get('limit')
        return records[:limit] if limit else records

    def run(self, arguments):
        """(output dict, result ids used, bytes read). Raises CalculationError for a refused call."""
        if not isinstance(arguments, dict):
            raise CalculationError('the arguments must be an object')
        op = arguments.get('operation')
        if op not in OPERATIONS:
            raise CalculationError('unknown operation %r; the operations are %s' % (op, ', '.join(OPERATIONS)))
        if op == 'arithmetic':
            return self._arithmetic(arguments)
        per_source, ids, size, missing = self._sources(arguments, 2 if op in ('union', 'intersection', 'difference') else 1)
        records = [r for group in per_source for r in group]
        field = arguments.get('field', '')
        out = {'operation': op}
        if op == 'count':
            out['count'] = len(records)
        elif op == 'distinct':
            seen = {}
            for record in records:
                value = field_of(record, field)
                seen.setdefault(canonical(value), value)
            values = [seen[k] for k in sorted(seen)]
            out.update({'count': len(values), 'values': values[:arguments['limit']] if arguments.get('limit') else values})
        elif op == 'group_by':
            out.update(self._group_by(records, arguments))
        elif op == 'sort':
            values = [field_of(r, field) for r in records]
            order = sorted(range(len(records)), key=_sort_key(values), reverse=bool(arguments.get('descending')))
            out.update({'count': len(records), 'records': self._shorten([records[i] for i in order], arguments)})
        elif op == 'filter':
            conditions = arguments.get('conditions')
            if not isinstance(conditions, list) or not conditions:
                raise CalculationError('filter needs at least one condition')
            for condition in conditions:
                if not isinstance(condition, dict) or condition.get('op') not in COMPARISONS or 'value' not in condition:
                    raise CalculationError('a condition needs field, op (%s) and value' % ', '.join(COMPARISONS))
            kept = [r for r in records if all(compare(field_of(r, c.get('field', '')), c['op'], c['value']) for c in conditions)]
            out.update({'count': len(kept), 'records': self._shorten(kept, arguments)})
        else:
            sets = []
            for group in per_source:
                values = {}
                for record in group:
                    value = field_of(record, field)
                    values.setdefault(canonical(value), value)
                sets.append(values)
            keys = set(sets[0])
            for other in sets[1:]:
                keys = keys | set(other) if op == 'union' else (keys & set(other) if op == 'intersection' else keys - set(other))
            merged = {}
            for values in sets:
                merged.update(values)
            values = [merged[k] for k in sorted(keys)]
            out.update({'count': len(values), 'values': values[:arguments['limit']] if arguments.get('limit') else values})
        if missing:
            out['missing'] = missing
        return out, ids, size

    def _group_by(self, records, arguments):
        keys = arguments.get('group_by')
        if not (isinstance(keys, list) and keys and all(isinstance(k, str) for k in keys)):
            raise CalculationError('group_by needs a list of fields in group_by')
        aggregate = arguments.get('aggregate', 'count')
        if aggregate not in ('count', 'sum'):
            raise CalculationError('aggregate is count or sum')
        groups = {}
        skipped = 0
        for record in records:
            key = {k: field_of(record, k) for k in keys}
            entry = groups.setdefault(canonical(key), {'key': key, 'count': 0, 'sum': Decimal(0)})
            entry['count'] += 1
            if aggregate == 'sum':
                value = number(field_of(record, arguments.get('sum_field', '')))
                if value is None:
                    skipped += 1
                else:
                    entry['sum'] += value
        rows = []
        for name in sorted(groups):
            entry = groups[name]
            row = {'key': entry['key'], 'count': entry['count']}
            if aggregate == 'sum':
                row['sum'] = self._rounded(entry['sum'], arguments)
            rows.append(row)
        out = {'groupCount': len(rows), 'groups': rows[:arguments['limit']] if arguments.get('limit') else rows}
        if aggregate == 'sum' and skipped:
            out['notNumeric'] = skipped
        return out

    @staticmethod
    def _rounded(value, arguments):
        digits = arguments.get('round')
        if isinstance(digits, int) and not isinstance(digits, bool):
            try:
                return value.quantize(Decimal(1).scaleb(-digits))
            except InvalidOperation:
                raise CalculationError('the value %s has too many digits to round to %d decimal places' % (value, digits))
        return value

    def _arithmetic(self, arguments):
        operator = arguments.get('operator')
        if operator not in OPERATORS:
            raise CalculationError('arithmetic needs operator %s' % ', '.join(OPERATORS))
        operands = arguments.get('operands')
        if not isinstance(operands, list) or len(operands) < 2:
            raise CalculationError('arithmetic needs at least two operands')
        values, ids, size = [], [], 0
        for operand in operands:
            if isinstance(operand, dict):
                text = self.store.get(operand.get('result_id'))
                ids.append(operand['result_id'])
                size += len(text.encode('utf-8'))
                found, _ = walk(read_text(text), operand.get('path'))
                if len(found) != 1 or number(found[0]) is None:
                    raise CalculationError('the operand %s at %r is not one number' % (operand['result_id'], operand.get('path') or ''))
                values.append(number(found[0]))
            elif number(operand) is not None and not isinstance(operand, str):
                values.append(number(operand))
            else:
                raise CalculationError('an operand is a number or {result_id, path}')
        result = values[0]
        for value in values[1:]:
            if operator == 'add':
                result += value
            elif operator == 'subtract':
                result -= value
            elif operator == 'multiply':
                result *= value
            else:
                if value == 0:
                    raise CalculationError('division by zero')
                result /= value
        return {'operation': 'arithmetic', 'value': self._rounded(result, arguments)}, ids, size


def render(output):
    """The output as the agent reads it, cut to the output limit by shortening its longest list."""
    output = plain(output)
    text = json.dumps(output, ensure_ascii=False, sort_keys=True)
    while len(text) > LIMITS['maxOutputChars']:
        lists = [k for k, v in output.items() if isinstance(v, list) and v]
        if not lists:
            break
        name = max(lists, key=lambda k: len(json.dumps(output[k], ensure_ascii=False)))
        output[name] = output[name][:len(output[name]) // 2]
        output['truncated'] = True
        text = json.dumps(output, ensure_ascii=False, sort_keys=True)
    return text


# ---------------------------------------------------------------------------------------------------------------- the session
class HarnessToolClash(ValueError):
    """A scenario's MCP server offers a tool with the name of a harness tool."""


class HarnessToolSession:
    """Wraps a scenario's tool session: offers its tools plus the harness tools, stores results under ids, and keeps the details of the
    last call in `last_details` for the transcript. `questions` is the run's ask_requester log; `counts` counts the harness tool calls."""

    def __init__(self, session, names, store, run_key, clock=time.monotonic):
        self.session, self.names, self.store, self.run_key, self.clock = session, [n for n in NAMES if n in names], store, run_key, clock
        self.calculator = Calculator(store)
        self.questions = []
        self.counts = {'calculate': 0, 'calculateErrors': 0, 'askRequester': 0}
        self.last_details = None

    def tools(self):
        offered = self.session.tools()
        clash = sorted({t['name'] for t in offered} & set(self.names))
        if clash:
            raise HarnessToolClash('the scenario already offers a tool named %s, which is a harness tool' % ', '.join(clash))
        return offered + [TOOLS[n] for n in self.names]

    @property
    def ids_shown(self):
        return CALCULATE in self.names

    def call(self, name, arguments):
        if name == CALCULATE and CALCULATE in self.names:
            return self._calculate(arguments)
        if name == ASK_REQUESTER and ASK_REQUESTER in self.names:
            self.counts['askRequester'] += 1
            question = arguments.get('question') if isinstance(arguments, dict) else None
            entry = {'runKey': self.run_key, 'at': utc_now(), 'question': question if isinstance(question, str) else json.dumps(arguments)}
            self.questions.append(entry)
            self.last_details = {'tool': ASK_REQUESTER, **entry, 'outputBytes': len(ASK_TEXT.encode('utf-8')),
                                 'addedTokensEstimate': estimate_tokens(ASK_TEXT)}
            return ASK_TEXT, False
        text, is_error = self.session.call(name, arguments)
        if not self.ids_shown:
            self.last_details = None
            return text, is_error
        result_id = self.store.add(name, arguments, text, is_error)
        self.last_details = {'tool': name, 'resultId': result_id}
        return ID_LINE % result_id + text, is_error

    def _calculate(self, arguments):
        self.counts['calculate'] += 1
        began = self.clock()
        operation = arguments.get('operation') if isinstance(arguments, dict) else None
        try:
            output, ids, size = self.calculator.run(arguments)
            text = render(output)
        except Exception as error:
            # the arguments come from the model unchecked and the calculator reads only this run's results, so every failure of the
            # calculation (a refusal, a numeric failure or an argument of the wrong type) is a logged tool error, never a stop of the study
            if not isinstance(error, CalculationError):
                error = CalculationError('the calculation failed (%s)' % type(error).__name__)
            self.counts['calculateErrors'] += 1
            text = 'calculate refused: %s' % error
            self.last_details = {'tool': CALCULATE, 'operation': operation, 'resultIds': _named_ids(arguments), 'resultId': None,
                                 'error': str(error), 'calcSeconds': round(self.clock() - began, 3), 'inputBytes': 0,
                                 'outputBytes': len(text.encode('utf-8')), 'addedTokensEstimate': estimate_tokens(text)}
            return text, True
        result_id = self.store.add(CALCULATE, arguments, text, False)
        shown = ID_LINE % result_id + text
        self.last_details = {'tool': CALCULATE, 'operation': operation, 'resultIds': ids, 'resultId': result_id, 'error': None,
                             'calcSeconds': round(self.clock() - began, 3), 'inputBytes': size, 'outputBytes': len(shown.encode('utf-8')),
                             'addedTokensEstimate': estimate_tokens(shown)}
        return shown, False

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _named_ids(arguments):
    """The result ids a refused call named, for its log. The arguments come from the model unchecked, so only lists are read."""
    if not isinstance(arguments, dict):
        return []
    named = []
    for name in ('sources', 'operands'):
        items = arguments.get(name)
        if isinstance(items, list):
            named += [item.get('result_id') for item in items if isinstance(item, dict)]
    return [n for n in named if n is not None]
