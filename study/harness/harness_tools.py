"""The two tools the harness offers beside a scenario's MCP tools, identical in every arm and run (docs/STUDY-2-DESIGN.md, the tools).

`calculate` computes over results the agent already obtained in the same run, named by result id. It never fetches: it has no network, file,
database, backend or answer-key access, and it never sees another run's results. Its operations are generic only (view, count, distinct,
group_by with count or sum, sort, filter by literal comparison of a value or of the elements of a list, union, intersection, difference and
arithmetic); none knows a domain term.

`ask_requester` logs the agent's question with its run and always returns the same fixed text.

Result ids. When `calculate` is offered, every result of a scenario tool and every successful `calculate` result gets an id `<tag>-<n>`:
`tag` is four hex digits unique to the run and its attempt, `n` counts from 1. The id is shown to the agent as the first line of the result,
`result_id: <id>`, and the result is stored in full in the run's `results.jsonl`, which the bundle checksum covers. An id with another tag
belongs to another run and is refused; an id with this run's tag that was never given is unknown and refused. Every refusal is a tool error,
logged like any other call.

Stored results (version 2). When `calculate` is offered, a scenario result longer than `storeAboveChars` characters is stored in full and is
not shown: the agent reads its id, its size and its shape, which is the result as `calculate` reads it with every list cut to its first
element and its length, every object to its first keys and every long text to its start (`preview`). The generic operation `view` reads any
part of a stored result, or of any other result. The rule is the same in every arm and knows no domain term.

Version 3. A `calculate` output longer than `storeAboveChars` characters is stored the same way: the agent reads its id, its size and its
shape, and `view` reads it page by page. A `view` page holds at most `viewPageChars` characters, so a page is always shown in full and is
never stored; `nextOffset` says where the next page starts. Every successful `calculate` output begins, after its id line, with one read
line: per source, in the order given, the result id, the path, the records it contributed and whether the path matched nothing. The line
never adds the sources up, because sources can overlap.

Version 4. A filter condition may carry `elements`: with `any` it holds when at least one value at its field satisfies the comparison, with
`none` when no value does. The values at the field are found as a source's path finds its records: `*` takes every element of a list, a
list at the end gives its elements, and an element that lacks the rest of the field is left out, so an empty list or a missing field has no
values (`any` does not hold, `none` does). A condition whose field has a path segment that is exactly `*` and no `elements` is refused
(`Wildcard fields require elements: "any" or "none".`): version 3 treated such a field as missing, which could silently include or
exclude records depending on the comparison. This
is the one deliberate exception to "existing conditions unchanged", asked for by the lead developer; every other condition without
`elements` is unchanged.

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

VERSION = 4
CALCULATE, ASK_REQUESTER = 'calculate', 'ask_requester'
NAMES = (CALCULATE, ASK_REQUESTER)
ASK_TEXT = 'No requester response is available during this evaluation.'
ID_LINE = 'result_id: %s\n'
OPERATIONS = ('view', 'count', 'distinct', 'group_by', 'sort', 'filter', 'union', 'intersection', 'difference', 'arithmetic')
COMPARISONS = ('eq', 'ne', 'lt', 'le', 'gt', 'ge')
ELEMENTS = ('any', 'none')
WILDCARD_REFUSAL = 'Wildcard fields require elements: "any" or "none".'
OPERATORS = ('add', 'subtract', 'multiply', 'divide')
LIMITS = {'maxSourceChars': 5_000_000, 'maxRecords': 100_000, 'maxStoredOutputChars': 5_000_000, 'maxSources': 100,
          'storeAboveChars': 5_000, 'viewPageChars': 5_000, 'previewChars': 1_500, 'previewKeys': 20, 'previewTextChars': 120}
STORED_LINE = ('stored, not shown: %d characters. Its shape as calculate reads it (a list shows its first element and its length):\n%s\n'
               'Read any part of it with calculate operation view: one source with a path, and offset and limit.')
STORED_RULE = ('a scenario result or a calculate output longer than storeAboveChars characters is stored in full and shown as its id, '
               'its size and its shape (lists cut to their first element and their length, objects to previewKeys keys, texts to '
               'previewTextChars characters, the whole within previewChars); view reads any part of any result, at most viewPageChars '
               'characters a page, with nextOffset for the next page, and a page is always shown in full; shorter results are shown in full')
READ_RULE = ('every successful calculate output begins, after its id line, with one line "read: " naming per source, in the order given, '
             'the result id, the path, the records it contributed and whether the path matched nothing; it never adds the sources up')
ELEMENTS_RULE = ('a filter condition with elements any holds when at least one value at its field satisfies its comparison, with elements '
                 'none when no value does; the values are found as a source path finds records (* takes every element of a list, a list '
                 'at the end gives its elements, an element lacking the rest of the field is left out), so an empty list or a missing '
                 'field has none; a condition whose field has a * path segment and no elements is refused; any other condition without '
                 'elements is unchanged')
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
                    'result_id: <id>. A result longer than 5000 characters, a calculate result included, is stored, not shown: you see '
                    'its size and its shape, where a list shows its first element and its length; read any part of it with view. Every '
                    'calculate result then has a line read: that names, for each source in turn, its result id, its path, the records it '
                    'gave and whether the path matched nothing; it does not add the sources up, as they can overlap. Name one or more '
                    'results in sources, each with an optional path to the part to use, and one generic operation. The records are the '
                    'elements found at the paths of all sources, one after the other. view: the part at the path of one source; offset '
                    'and limit page through a list, the keys of an object or the characters of a text; a page holds at most 5000 '
                    'characters and nextOffset gives the offset of the next page. count: the number of records. distinct: the distinct '
                    'values of field. group_by: groups by the fields in group_by, with aggregate count or '
                    'sum of sum_field. sort: the records ordered by field (descending optional). filter: the records for which every '
                    'condition holds (eq, ne, lt, le, gt, ge against a literal value); a condition with elements any holds when at least '
                    'one value at its field does, with elements none when no value does, where * in the field takes every element of a '
                    'list and a list at its end gives its elements (an empty list or a missing field has no values); a field with a * '
                    'segment needs elements any or none. union, '
                    'intersection, difference: set operations on '
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
                                                                     'value': _SCALAR, 'elements': {'type': 'string', 'enum': list(ELEMENTS)}},
                                                      'required': ['field', 'op', 'value']}},
            'descending': {'type': 'boolean'},
            'operator': {'type': 'string', 'enum': list(OPERATORS)},
            'operands': {'type': 'array', 'items': {'type': ['number', 'object']}},
            'fields': {'type': 'array', 'items': {'type': 'string'}},
            'limit': {'type': 'integer', 'minimum': 1},
            'offset': {'type': 'integer', 'minimum': 0},
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
                                      'every successful calculate result', 'operations': list(OPERATIONS), 'limits': dict(LIMITS),
                    'storedResults': STORED_RULE, 'readLine': READ_RULE, 'conditionElements': ELEMENTS_RULE})
    return out


def run_tag(run_key, attempt):
    """Four hex digits unique to one attempt of one run."""
    return sha256_bytes(('%s/%s' % (run_key, attempt)).encode('utf-8'))[:4]


class CalculationError(Exception):
    """A refused calculate call; its text goes back to the agent as a tool error."""


class PathMissing(CalculationError):
    """A step of a path that the value does not have, before the first `*`. A source's path refuses it like any other error; a condition
    with `elements` reads it as a field with no values. A text that cannot be read as JSON or XML is never this, so it is always refused."""


# ---------------------------------------------------------------------------------------------------------------- the result store
class ResultStore:
    """The tool results of one run attempt, kept in memory and appended to `path` (results.jsonl) as they arrive, through `redact` (the
    harness's key redactor) like everything else the harness writes."""

    def __init__(self, path, tag, redact=lambda value: value):
        self.path, self.tag, self.redact = Path(path), tag, redact
        self.items = {}
        self.count = 0

    def add(self, tool, arguments, text, is_error, shown_in_full=True, read_line=None):
        """Store `text` under the next id; `shown_in_full` records whether the agent read the whole text or only its shape, and
        `read_line`, for a calculate output, the read line the agent saw above it."""
        self.count += 1
        result_id = '%s-%d' % (self.tag, self.count)
        self.items[result_id] = text
        data = text.encode('utf-8')
        entry = {'resultId': result_id, 'at': utc_now(), 'tool': tool, 'arguments': arguments, 'isError': bool(is_error),
                 'bytes': len(data), 'sha256': sha256_bytes(data), 'shownInFull': bool(shown_in_full), 'text': text}
        if read_line is not None:
            entry['readLine'] = read_line
        append_jsonl(self.path, self.redact(entry))
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
                    raise PathMissing('path %r: %s' % (path, error.args[0]))
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


def field_values(record, field):
    """The values at `field` inside a record for a condition with `elements`, found as a source's path finds its records: `*` takes every
    element of a list, a list at the end gives its elements, and an element that lacks the rest of the field is left out. A record that
    lacks the field has no values. A text on the way that cannot be read (broken XML, a document type) is refused, never taken as missing."""
    try:
        values, _ = walk(record, field)
    except PathMissing:
        return []
    return [_decoded(value) for value in records_of(values)]  # a list at the end gives its elements read as * would read them


def has_wildcard(field):
    """Whether a field has a path segment that is exactly `*`; an asterisk inside a key name is part of that name."""
    return isinstance(field, str) and '*' in _segments(field)


def holds(record, condition):
    """Whether one filter condition holds for a record: a literal comparison of the value at its field or, with `elements`, of the values
    there (any: at least one holds; none: no value holds)."""
    elements = condition.get('elements')
    if elements is None:
        return compare(field_of(record, condition.get('field', '')), condition['op'], condition['value'])
    found = any(compare(value, condition['op'], condition['value']) for value in field_values(record, condition.get('field', '')))
    return found if elements == 'any' else not found


# ---------------------------------------------------------------------------------------------------------------- the read line
def _read(result_id, path, amount, matched, missing=0):
    """What one source contributed, for the read line: `amount` is a count of records or, for view and arithmetic, a phrase."""
    return {'resultId': result_id, 'path': path if isinstance(path, str) else '', 'records': amount, 'matchedNothing': not matched,
            'missing': missing}


def _records_phrase(amount):
    if isinstance(amount, str):
        return amount
    return '%d record%s' % (amount, '' if amount == 1 else 's')


def read_line(reads):
    """The line that starts every calculate output: per source, in the order given, the result id, the path, what it contributed and
    whether the path matched nothing. It never sums the sources: two sources can hold the same records."""
    if not reads:
        return 'read: no result (numbers only)'
    parts = []
    for item in reads:
        path = (item['path'] or '').strip()
        where = 'at %s' % json.dumps(path, ensure_ascii=False) if path else 'at the whole result'
        part = '%s %s: %s' % (item['resultId'], where, _records_phrase(item['records']))
        if item['matchedNothing']:
            part += ' (the path matched nothing)'
        if item['missing']:
            part += ' (%d element%s lacked the rest of the path)' % (item['missing'], '' if item['missing'] == 1 else 's')
        parts.append(part)
    return 'read: ' + '; '.join(parts)


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


# ---------------------------------------------------------------------------------------------------------------- the shape of a stored result
def _decoded_quietly(value):
    try:
        return _decoded(value)
    except CalculationError:
        return value


def shape(value, depth=0, max_depth=8):
    """`value` as calculate reads it, cut short: a list to its first element and its length, an object to its first previewKeys keys and
    their count, a text to its first previewTextChars characters and its length, and nothing deeper than `max_depth` levels."""
    value = _decoded_quietly(value) if isinstance(value, str) else value
    if isinstance(value, dict):
        if depth >= max_depth:
            return '{... %d keys}' % len(value)
        out = {k: shape(v, depth + 1, max_depth) for k, v in list(value.items())[:LIMITS['previewKeys']]}
        if len(value) > LIMITS['previewKeys']:
            out['...'] = '%d keys in all' % len(value)
        return out
    if isinstance(value, list):
        if not value:
            return []
        if depth >= max_depth:
            return '[... %d elements]' % len(value)
        return [shape(value[0], depth + 1, max_depth)] + (['... %d elements in all' % len(value)] if len(value) > 1 else [])
    if isinstance(value, str) and len(value) > LIMITS['previewTextChars']:
        return value[:LIMITS['previewTextChars']] + '... (%d characters)' % len(value)
    return plain(value)


def preview(text):
    """The shape of a result as the agent reads it in place of a stored result: within previewChars characters, cutting depth first."""
    for depth in (8, 6, 4, 3, 2, 1):
        body = json.dumps(shape(text, 0, depth), ensure_ascii=False)
        if len(body) <= LIMITS['previewChars']:
            return body
    return body[:LIMITS['previewChars']] + '...'


def stored_text(result_id, text, line=None):
    """What the agent reads of a stored result: its id line, for a calculate output its read line, its size and its shape."""
    return ID_LINE % result_id + ('%s\n' % line if line is not None else '') + STORED_LINE % (len(text), preview(text))


def _sort_key(values):
    numbers = [number(v) for v in values]
    if all(n is not None for n in numbers):
        return lambda i: (0, numbers[i])
    return lambda i: (0 if values[i] is not None else 1, canonical(values[i]))


def _page_text(output):
    return json.dumps(plain(output), ensure_ascii=False, sort_keys=True)


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
        out, ids, size, missing, reads = [], [], 0, 0, []
        for source in sources:
            if not isinstance(source, dict) or 'result_id' not in source:
                raise CalculationError('every source needs a result_id')
            text = self.store.get(source['result_id'])
            ids.append(source['result_id'])
            size += len(text.encode('utf-8'))
            values, lost = walk(read_text(text), source.get('path'))
            missing += lost
            records = records_of(values)
            reads.append(_read(source['result_id'], source.get('path'), len(records), bool(values), lost))
            out.append(records)
        if sum(len(r) for r in out) > LIMITS['maxRecords']:
            raise CalculationError('more than %d records' % LIMITS['maxRecords'])
        return out, ids, size, missing, reads

    @staticmethod
    def _shorten(records, arguments):
        fields = arguments.get('fields')
        if fields:
            records = [{f: field_of(r, f) for f in fields} for r in records]
        limit = arguments.get('limit')
        return records[:limit] if limit else records

    def run(self, arguments):
        """(output dict, result ids used, bytes read, reads for the read line). Raises CalculationError for a refused call."""
        if not isinstance(arguments, dict):
            raise CalculationError('the arguments must be an object')
        op = arguments.get('operation')
        if op not in OPERATIONS:
            raise CalculationError('unknown operation %r; the operations are %s' % (op, ', '.join(OPERATIONS)))
        if op == 'arithmetic':
            return self._arithmetic(arguments)
        if op == 'view':
            return self._view(arguments)
        per_source, ids, size, missing, reads = self._sources(arguments, 2 if op in ('union', 'intersection', 'difference') else 1)
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
                if 'elements' in condition and condition['elements'] not in ELEMENTS:
                    raise CalculationError('elements is %s, or left out' % ' or '.join(ELEMENTS))
                if 'elements' not in condition and has_wildcard(condition.get('field', '')):
                    raise CalculationError(WILDCARD_REFUSAL)
            kept = [r for r in records if all(holds(r, c) for c in conditions)]
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
        return out, ids, size, reads

    @staticmethod
    def _window(arguments):
        offset, limit = arguments.get('offset', 0), arguments.get('limit')
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CalculationError('offset is a whole number of 0 or more')
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise CalculationError('limit is a whole number of 1 or more')
        return offset, (offset + limit if limit else None)

    def _view(self, arguments):
        """One page of the part at the path of one source: a list (or the elements a * spreads) from offset with at most limit records, an
        object from its offset-th key with at most limit keys, a text from its offset-th character with at most limit characters, or one
        value. A page holds at most viewPageChars characters: it ends earlier when the window would be longer, and nextOffset names the
        offset of the next page whenever the part goes on. A single record or key longer than a page is shown as its shape (shapeOnly);
        a deeper path reads it."""
        sources = arguments.get('sources')
        if not isinstance(sources, list) or len(sources) != 1:
            raise CalculationError('view needs exactly one source')
        source = sources[0]
        if not isinstance(source, dict) or 'result_id' not in source:
            raise CalculationError('every source needs a result_id')
        text = self.store.get(source['result_id'])
        start, end = self._window(arguments)
        values, missing = walk(read_text(text), source.get('path'))
        spread = '*' in _segments(source.get('path'))
        value = values if spread or len(values) != 1 else values[0]
        rid, path = source['result_id'], source.get('path')
        extra = {'missing': missing} if missing else {}
        if isinstance(value, list):
            fields = arguments.get('fields')

            def build(n):
                return {'operation': 'view', 'offset': start, 'count': len(value),
                        'records': self._shorten(value[start:start + n], {'fields': fields})}
            out = self._page(build, len(value), start, end, 'records', extra)
            read = _read(rid, path, len(value), bool(values), missing)
        elif isinstance(value, dict):
            keys = list(value)

            def build(n):
                return {'operation': 'view', 'offset': start, 'keyCount': len(keys), 'value': {k: value[k] for k in keys[start:start + n]}}
            out = self._page(build, len(keys), start, end, 'value', extra)
            read = _read(rid, path, 'an object of %d keys' % len(keys), True, missing)
        elif isinstance(value, str):
            def build(n):
                return {'operation': 'view', 'offset': start, 'length': len(value), 'text': value[start:start + n]}
            out = self._page(build, len(value), start, end, 'text', extra)
            read = _read(rid, path, 'a text of %d characters' % len(value), True, missing)
        else:
            out = {'operation': 'view', 'value': value, **extra}
            read = _read(rid, path, 'one value', True, missing)
        return out, [rid], len(text.encode('utf-8')), [read]

    @staticmethod
    def _page(build, total, start, end, member, extra):
        """The longest window from `start` (up to `end`, or the end of the part) whose page fits viewPageChars, found by halving; with
        nextOffset when the part goes on after the page. Every key the page carries (`extra`, such as `missing`, and `nextOffset`) is
        counted when it is sized. When not even one item fits, that item's shape stands in for it, and a key longer than previewTextChars
        is shown as its start and its length, so the page always fits."""
        def paged(n):
            out = dict(build(n), **extra)
            if start + n < total:
                out['nextOffset'] = start + n
            return out

        def fits(out):
            return len(_page_text(out)) <= LIMITS['viewPageChars']
        end = total if end is None else min(end, total)
        wanted = max(end - start, 0)
        out = paged(wanted)
        if wanted and not fits(out):
            low, high = 0, wanted  # the longest n that fits lies in [low, high)
            while high - low > 1:
                middle = (low + high) // 2
                if fits(paged(middle)):
                    low = middle
                else:
                    high = middle
            if low:
                out = paged(low)
            else:
                one = paged(1)[member]
                for limit in (LIMITS['viewPageChars'] // 2, LIMITS['viewPageChars'] // 8, LIMITS['previewTextChars']):
                    out = paged(1)
                    if member == 'records':
                        out[member] = [bounded_shape(one[0], limit)]
                    else:
                        key = next(iter(one))
                        cut = LIMITS['previewTextChars']
                        shown = key if len(key) <= cut else key[:cut] + '... (%d characters)' % len(key)
                        out[member] = {shown: bounded_shape(one[key], limit)}
                    out['shapeOnly'] = [member]
                    if fits(out):
                        break
        return out

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
        values, ids, size, reads = [], [], 0, []
        for operand in operands:
            if isinstance(operand, dict):
                text = self.store.get(operand.get('result_id'))
                ids.append(operand['result_id'])
                size += len(text.encode('utf-8'))
                found, _ = walk(read_text(text), operand.get('path'))
                if len(found) != 1 or number(found[0]) is None:
                    raise CalculationError('the operand %s at %r is not one number' % (operand['result_id'], operand.get('path') or ''))
                values.append(number(found[0]))
                reads.append(_read(operand['result_id'], operand.get('path'), 'one number', True))
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
        return {'operation': 'arithmetic', 'value': self._rounded(result, arguments)}, ids, size, reads


def bounded_shape(value, limit=None):
    """The shape of `value` within `limit` characters (previewChars by default), cutting depth first; past that, the start of its JSON
    text."""
    limit = LIMITS['previewChars'] if limit is None else limit
    for depth in (8, 6, 4, 3, 2, 1):
        cut = shape(value, 0, depth)
        if len(json.dumps(cut, ensure_ascii=False)) <= limit:
            return cut
    return json.dumps(cut, ensure_ascii=False)[:limit] + '...'


def render(output, limit=None):
    """The output as JSON text, cut to `limit` characters (maxStoredOutputChars by default) by halving its longest list; when no list is
    left to cut, its longest object with more than one key (by keys) or text (by characters). What is still too long after that (an object
    with one long member, at any depth) is replaced by its bounded shape and named in `shapeOnly`, so no output passes the limit. Every
    output a calculation makes is far below the default, so the cut is a safeguard that keeps a stored output readable as a source."""
    limit = LIMITS['maxStoredOutputChars'] if limit is None else limit
    output = plain(output)
    text = json.dumps(output, ensure_ascii=False, sort_keys=True)
    while len(text) > limit:
        lists = [k for k, v in output.items() if isinstance(v, list) and v]
        if not lists:
            lists = [k for k, v in output.items() if isinstance(v, (dict, str)) and len(v) > 1 and k != 'operation']
        if not lists:
            break
        name = max(lists, key=lambda k: len(json.dumps(output[k], ensure_ascii=False)))
        value = output[name]
        output[name] = dict(list(value.items())[:len(value) // 2]) if isinstance(value, dict) else value[:len(value) // 2]
        output['truncated'] = True
        text = json.dumps(output, ensure_ascii=False, sort_keys=True)
    while len(text) > limit:
        fields = [k for k in output if k not in ('operation', 'truncated', 'shapeOnly') and k not in output.get('shapeOnly', [])]
        if not fields:
            return json.dumps({'operation': output.get('operation'), 'truncated': True, 'shapeOnly': output.get('shapeOnly', [])},
                              ensure_ascii=False, sort_keys=True)
        name = max(fields, key=lambda k: len(json.dumps(output[k], ensure_ascii=False)))
        output[name] = bounded_shape(output[name])
        output['shapeOnly'] = sorted(output.get('shapeOnly', []) + [name])
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
        if len(text) > LIMITS['storeAboveChars']:
            result_id = self.store.add(name, arguments, text, is_error, shown_in_full=False)
            shown = stored_text(result_id, text)
            self.last_details = {'tool': name, 'resultId': result_id, 'stored': True, 'storedChars': len(text), 'shownChars': len(shown)}
            return shown, is_error
        result_id = self.store.add(name, arguments, text, is_error)
        self.last_details = {'tool': name, 'resultId': result_id}
        return ID_LINE % result_id + text, is_error

    def _calculate(self, arguments):
        self.counts['calculate'] += 1
        began = self.clock()
        operation = arguments.get('operation') if isinstance(arguments, dict) else None
        try:
            output, ids, size, reads = self.calculator.run(arguments)
            text = render(output)
            line = read_line(reads)
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
        stored = len(text) > LIMITS['storeAboveChars']
        result_id = self.store.add(CALCULATE, arguments, text, False, shown_in_full=not stored, read_line=line)
        shown = stored_text(result_id, text, line) if stored else ID_LINE % result_id + line + '\n' + text
        self.last_details = {'tool': CALCULATE, 'operation': operation, 'resultIds': ids, 'resultId': result_id, 'error': None,
                             'calcSeconds': round(self.clock() - began, 3), 'inputBytes': size, 'outputBytes': len(shown.encode('utf-8')),
                             'addedTokensEstimate': estimate_tokens(shown), 'read': reads}
        if stored:
            self.last_details.update({'stored': True, 'storedChars': len(text), 'shownChars': len(shown)})
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
