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
(`Wildcard fields require elements: "any" or "none".`).

Version 5. One strictness pass from the independent trap audit of the four paid runs (study/evidence/study-2-trap-audit/). The output of a
call that both versions accept is what version 4 gave, with one exception that is new syntax: a step in brackets, which version 4 read
as a key with the brackets in its name, names the key inside them where no object of the call has version 4's key. What else changes
is which calls are accepted and what the agent reads around the output.
- Refused, with every problem of the call named at once and, where the problem is one of shape, the shapes of the sources: an argument
  of the wrong form, named with the form it takes; a key that a source, a condition or an operand does not take; an argument
  that does not apply to the operation; a field on a source of plain values; a field that no record of any source has (a condition
  that compares it with null is the test that a field is there, and is answered); a `*` in a field
  outside a filter condition with `elements`; a `*` at an object (only a list has elements; an XML element that occurs once still counts
  as a list of one); a comparison of a list or an object with one value without `elements`; conditions that contradict each other; a key
  with a dot in its name spelled as nested steps (it is written in brackets, `[a.b]`); a step in brackets that the objects of one call
  answer by more than one key; an output too long to keep whole.
- A line `coverage: ` after the read line, only when it has something to say: per field that some records lack or hold null, how many
  have it; what each condition did alone when a filter kept nothing; the records a sum added; a null among distinct values; the size of
  each set, in the order of the sources; groups that are not unique values of one field; and, when a source carries `totalCount` (or
  `total`) or `hasMore`, or is a shortened calculate output, that the sources hold fewer records than the total it states (or
  more). That fact stays with every output built from the source. It never says that a list is complete, and it says that records
  are missing only when that is certain. The tool cannot see which request gave a list: one result can hold several pages of one
  list under different keys, a page need not repeat the total, and two requests can ask for other fields of the same records or
  for another order. So the lists that the sources read count together when they have the same name, and a list is short only when
  all the records of that name are fewer than the total it states. Records are counted as the pages hold them; where the plain
  values that every record has tell them apart, a record that two pages hold is seen as one. When several pages hold as many
  records as the total, it says so only where pages at one place share no record, where every page says `hasMore`, or where no page
  states its place in a list.
- A line `warning: ` for what only the agent can judge, never a refusal: a request or a calculation that repeats one already held, held
  pages of the same collection that are not among the sources, and conditions on fixed list positions.
- One addition, decided by the lead developer on the replay of the stored calls: an empty `group_by` list gives one group over all
  records, so a total needs no field that no record has (which the paid runs used for it, and which is now refused).

Reading a result. A source names a result id and an optional path: dot-separated keys or list positions, where `*` takes every element of a
list. A segment in brackets is one key taken literally, dots included; an output names a field as it was written, brackets included, and the
same field in brackets reads it back. Such a segment is read one way in a whole call. A text met while walking the path, or at its end, is
read as JSON when it starts with `{` or `[`, or as XML when it starts with `<`. XML is read generically: local tag names without namespaces,
attributes as `@name`, an element's own text as `#text` beside children or attributes, a leaf as its text, and an element name that repeats
under one parent as a list.

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

VERSION = 5
CALCULATE, ASK_REQUESTER = 'calculate', 'ask_requester'
NAMES = (CALCULATE, ASK_REQUESTER)
ASK_TEXT = 'No requester response is available during this evaluation.'
ID_LINE = 'result_id: %s\n'
OPERATIONS = ('view', 'count', 'distinct', 'group_by', 'sort', 'filter', 'union', 'intersection', 'difference', 'arithmetic')
SET_OPERATIONS = ('union', 'intersection', 'difference')
COMPARISONS = ('eq', 'ne', 'lt', 'le', 'gt', 'ge')
OPPOSITES = {'eq': 'ne', 'ne': 'eq', 'lt': 'ge', 'ge': 'lt', 'gt': 'le', 'le': 'gt'}
ELEMENTS = ('any', 'none')
WILDCARD_REFUSAL = 'Wildcard fields require elements: "any" or "none".'
OPERATORS = ('add', 'subtract', 'multiply', 'divide')
APPLIES = {'view': ('sources', 'offset', 'limit', 'fields'), 'count': ('sources',), 'distinct': ('sources', 'field', 'limit'),
           'group_by': ('sources', 'group_by', 'aggregate', 'sum_field', 'round', 'limit'),
           'sort': ('sources', 'field', 'descending', 'fields', 'limit'), 'filter': ('sources', 'conditions', 'fields', 'limit'),
           'union': ('sources', 'field', 'limit'), 'intersection': ('sources', 'field', 'limit'), 'difference': ('sources', 'field', 'limit'),
           'arithmetic': ('operator', 'operands', 'round')}
TOTAL_KEYS, MORE_KEY, PLACE_KEYS = ('totalCount', 'total'), 'hasMore', ('offset', 'page')
OUTPUT_LISTS = {'records': 'count', 'values': 'count', 'groups': 'groupCount'}
LIMITS = {'maxSourceChars': 5_000_000, 'maxRecords': 100_000, 'maxStoredOutputChars': 5_000_000, 'maxSources': 100,
          'storeAboveChars': 5_000, 'viewPageChars': 5_000, 'previewChars': 1_500, 'previewKeys': 20, 'previewTextChars': 120,
          'coverageLineChars': 600, 'warningChars': 300, 'maxWarnings': 2, 'refusalChars': 1_500, 'repeatMinRecords': 10}
STORED_LINE = ('stored, not shown: %d characters. Its shape as calculate reads it (a list shows its first element and its length):\n%s\n'
               'Read any part of it with calculate operation view: one source with a path, and offset and limit.')
STORED_RULE = ('a scenario result or a calculate output longer than storeAboveChars characters is stored in full and shown as its id, '
               'its size and its shape (lists cut to their first element and their length, objects to previewKeys keys, texts to '
               'previewTextChars characters, the whole within previewChars); view reads any part of any result, at most viewPageChars '
               'characters a page, with nextOffset for the next page, and a page is always shown in full; shorter results are shown in full; '
               'the coverage and warning lines of a calculate output count toward storeAboveChars, and a view page carries its lines '
               'above it')
READ_RULE = ('every successful calculate output begins, after its id line, with one line "read: " naming per source, in the order given, '
             'the result id, the path, the records it contributed, whether the path matched nothing and how many elements were left out '
             'for lacking which step of the path; it never adds the sources up')
ELEMENTS_RULE = ('a filter condition with elements any holds when at least one value at its field satisfies its comparison, with elements '
                 'none when no value does; the values are found as a source path finds records (* takes every element of a list, a list '
                 'at the end gives its elements, an element lacking the rest of the field is left out), so an empty list or a missing '
                 'field has none; a condition whose field has a * path segment and no elements is refused; any other condition without '
                 'elements is unchanged')
STRICT_RULE = ('refused, with every problem of the call named at once and the shapes of the sources where the problem is one of shape: an '
               'argument of the wrong form, named with the form it takes; a key that a source, a condition or an operand does not take; an '
               'argument that does not apply to the operation; a field on a source of plain values; a field that no record of any source '
               'has, except in a condition that compares it with null; a * in a field outside a filter condition with elements; a * at an object (an XML element that occurs once counts as '
               'a list of one); a comparison of a list or an object with one value without elements; conditions that contradict each '
               'other; a key with a dot in its name spelled as nested steps (written in brackets, [a.b]); a step in brackets that the '
               'objects of one call answer by more than one key; an output longer than maxStoredOutputChars characters')
COVERAGE_RULE = ('after the read line, when there is something to say, one line "coverage: " of at most coverageLineChars characters: '
                 'per field that some records lack or hold null, how many have it; what each condition did alone when a filter kept '
                 'nothing; the records a sum added; a null among distinct values; the size of each set in the order of the sources; '
                 'groups that are not unique values of one field; and, when a source carries totalCount, total or hasMore or is a '
                 'shortened calculate output, that the sources hold fewer (or more) records than the total it states, or as many from '
                 'several pages of which two at one place share no record, none states its place in a list (offset, page, hasMore) '
                 'or each says hasMore, which stays with every output built from it; the lists the sources read count together when '
                 'they have the same name, with or without a total and whatever their fields, and a list is short only when all the '
                 'records of that name are fewer than its total; a record that two pages hold is seen as one only where the plain '
                 'values that every record has tell the records of each page apart; it never says that a list is complete')
WARNING_RULE = ('at most maxWarnings lines "warning: " of at most warningChars characters, never a refusal: a request or a calculation '
                'that repeats one already held, with the earlier result id; held pages of the same collection that are not among the '
                'sources; conditions on fixed list positions where elements would test the whole list')
_ID = re.compile(r'^([0-9a-f]{4})-([1-9][0-9]*)$')
_NUMBER = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$')
_POSITION = re.compile(r'-?\d+')
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
                    'values of field. group_by: groups by the fields in group_by (an empty list gives one group over all records), '
                    'with aggregate count or '
                    'sum of sum_field. sort: the records ordered by field (descending optional). filter: the records for which every '
                    'condition holds (eq, ne, lt, le, gt, ge against a literal value); a condition with elements any holds when at least '
                    'one value at its field does, with elements none when no value does, where * in the field takes every element of a '
                    'list and a list at its end gives its elements (an empty list or a missing field has no values); a field with a * '
                    'segment needs elements any or none. union, '
                    'intersection, difference: set operations on '
                    'the values of field taken per source (difference: the first source minus the others). arithmetic: operator add, '
                    'subtract, multiply or divide over operands, each a number or {result_id, path} naming one number. fields and limit '
                    'shorten a list of records; round sets decimal places. A field is a dot-separated path inside a record; empty means the '
                    'record itself. A key with a dot in its name is written in brackets: [a.b]. The result has a result_id of its own. '
                    'A wrong use is refused with every problem named at once. After read:, a line coverage: names fields that some '
                    'records lack, the size of each set and records short of totalCount; a line warning: flags repeats, held pages '
                    'left out and fixed list positions.'),
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
                    'storedResults': STORED_RULE, 'readLine': READ_RULE, 'conditionElements': ELEMENTS_RULE, 'refusals': STRICT_RULE,
                    'coverageLine': COVERAGE_RULE, 'warningLines': WARNING_RULE})
    return out


def run_tag(run_key, attempt):
    """Four hex digits unique to one attempt of one run."""
    return sha256_bytes(('%s/%s' % (run_key, attempt)).encode('utf-8'))[:4]


class CalculationError(Exception):
    """A refused calculate call; its text goes back to the agent as a tool error."""


class PathMissing(CalculationError):
    """A step of a path that the value does not have, before the first `*`. A source's path refuses it like any other error; a condition
    with `elements` reads it as a field with no values. A text that cannot be read as JSON or XML is never this, so it is always refused."""


class _Xml(dict):
    """An object read from an XML element. XML has no lists, so an element that occurs once is an object where a repeated one is a list:
    `*` takes it as a list of one, where it refuses any other object."""


class _Key(str):
    """A path segment written in brackets: one key taken literally, dots included; never `*` and never a position."""


class Ambiguous(CalculationError):
    """A step in brackets that an object answers in more than one way."""


def _empty_lineage():
    """What an output was built from: the lists its sources read (`pages`), the calculate outputs they read shortened (`cuts`), and the
    records they read as elements of lists that are not among `pages` (`loose`: a path -> the name of those lists and the records),
    which may be records that a list of that name is short of."""
    return {'pages': {}, 'cuts': [], 'loose': {}}


# ---------------------------------------------------------------------------------------------------------------- the result store
class ResultStore:
    """The tool results of one run attempt, kept in memory and appended to `path` (results.jsonl) as they arrive, through `redact` (the
    harness's key redactor) like everything else the harness writes. Beside each text it keeps what version 5's coverage and warning
    lines need and nothing the agent did not obtain: the tool that gave the result, what a calculate output was built from (`lineage`),
    the calculations already made and, of the scenario results, their paged lists and their records by value."""

    def __init__(self, path, tag, redact=lambda value: value):
        self.path, self.tag, self.redact = Path(path), tag, redact
        self.items = {}
        self.count = 0
        self.meta = {}        # result id -> {'tool', 'sha', 'lineage'}
        self.calculations = {}  # canonical arguments -> the id of the first successful calculation with them
        self.texts = {}       # sha256 of a scenario result's text -> its id
        self.paged = []       # (result id, sha, the list's identity, its name, total, hasMore, n, record keys) of every paged list
        self.postings = {}    # (key, canonical value) -> [(result id, path, record)] over the lists of objects of the scenario results
        self.lists = {}       # (result id, path) -> the records of that list
        self.repeated = {}    # (result id, path) of a list whose records are all held earlier -> the (result id, path) lists holding them
        self.pages = {}       # (result id, path) -> the list that path reads, as `_paging` found it
        self.listed = {}      # (result id, the list's identity) -> that list, kept once however many paths read it

    def add(self, tool, arguments, text, is_error, shown_in_full=True, read_line=None, notes=None):
        """Store `text` under the next id; `shown_in_full` records whether the agent read the whole text or only its shape,
        `read_line`, for a calculate output, the read line the agent saw above it, and `notes` its coverage line, its warnings and what
        it was built from."""
        self.count += 1
        result_id = '%s-%d' % (self.tag, self.count)
        data = text.encode('utf-8')
        entry = {'resultId': result_id, 'at': utc_now(), 'tool': tool, 'arguments': arguments, 'isError': bool(is_error),
                 'bytes': len(data), 'sha256': sha256_bytes(data), 'shownInFull': bool(shown_in_full), 'text': text}
        if read_line is not None:
            entry['readLine'] = read_line
        notes = notes or {}
        if notes.get('coverage'):
            entry['coverageLine'] = notes['coverage']
        if notes.get('warnings'):
            entry['warnings'] = list(notes['warnings'])
        self.remember(result_id, tool, text, notes.get('lineage'), entry['sha256'])
        append_jsonl(self.path, self.redact(entry))
        return result_id

    def remember(self, result_id, tool, text, lineage=None, sha=None):
        """Hold `text` under `result_id` with what later calls need to know of it."""
        self.items[result_id] = text
        self.meta[result_id] = {'tool': tool, 'sha': sha or sha256_bytes(text.encode('utf-8')), 'lineage': lineage or _empty_lineage()}

    def get(self, result_id):
        match = _ID.match(str(result_id))
        if not match:
            raise CalculationError('%r is not a result id: an id looks like %s-1 and is shown as the first line of a result' % (result_id, self.tag))
        if match.group(1) != self.tag:
            raise CalculationError('the result id %s belongs to another run: only results of this task can be used' % result_id)
        if result_id not in self.items:
            raise CalculationError('the result id %s is unknown in this task' % result_id)
        return self.items[result_id]

    # ------------------------------------------------------------------ scenario results: repeats and pages
    def examine(self, text):
        """(warnings, found) for a scenario result about to be stored: a warning when it repeats what is already held, and what
        `index` then keeps of it. It reads only this run's results."""
        sha = sha256_bytes(text.encode('utf-8'))
        found = {'sha': sha, 'collections': [], 'repeated': {}}
        if sha in self.texts:
            return ['this result is the same as %s, which is still held' % self.texts[sha]], found
        try:
            value = read_text(text)
        except CalculationError:
            return [], found
        found['collections'] = list(_collections(value))
        repeats = []
        for path, _, records, _ in found['collections']:
            if len(records) < LIMITS['repeatMinRecords']:
                continue
            holders = self._holders(records)
            if holders:
                found['repeated'][path] = holders
                repeats.append('the %d records at %s are already held in %s' % (len(records), json.dumps(path, ensure_ascii=False),
                                                                                 _listed(dict.fromkeys(rid for rid, _ in holders), 4)))
        return (['; '.join(repeats[:2])] if repeats else []), found

    def _holders(self, records):
        """The (result id, path) lists of earlier results that hold every one of `records`, each with all its keys and the same values;
        empty when a record is not held."""
        holders, later = [], []
        for record in records:
            pairs = [(k, canonical(v)) for k, v in record.items() if v is not None and not isinstance(v, (dict, list))]
            if not pairs:
                later.append(record)  # no plain value to look it up by: it is looked for in the lists that hold the others
                continue
            postings = [self.postings.get(pair) for pair in pairs]
            if any(p is None for p in postings):
                return []
            whole = {k: canonical(v) for k, v in record.items()}
            for result_id, path, held in min(postings, key=len)[:200]:
                if all(k in held and canonical(held[k]) == v for k, v in whole.items()):
                    if (result_id, path) not in holders:
                        holders.append((result_id, path))
                    break
            else:
                return []
        for record in later:
            whole = {k: canonical(v) for k, v in record.items()}
            if not any(all(k in held and canonical(held[k]) == v for k, v in whole.items())
                       for holder in holders for held in self.lists.get(holder, [])):
                return []
        return holders

    def index(self, result_id, found):
        """Keep what `examine` found of a stored scenario result, for the warnings of later calls."""
        self.texts.setdefault(found['sha'], result_id)
        for path, holders in found['repeated'].items():
            self.repeated[(result_id, path)] = holders
        for path, parent, records, keys in found['collections']:
            self.lists[(result_id, path)] = records
            total, more = _paging_keys(parent)
            if total is not None or more is not None:
                self.paged.append((result_id, found['sha'], _identity(keys), keys[-1], total, more, len(records),
                                   frozenset(key for record in records for key in record)))
            for record in records:
                for key, value in record.items():
                    if value is not None and not isinstance(value, (dict, list)):
                        self.postings.setdefault((key, canonical(value)), []).append((result_id, path, record))


def _listed(names, most):
    names = list(names)
    return ', '.join(names[:most]) + (' and %d more' % (len(names) - most) if len(names) > most else '')


def _identity(keys):
    """The identity of a part of a result: the keys and positions that lead to it. A path text is not one, because a key with a dot
    in its name and two nested keys can be written alike."""
    return json.dumps(list(keys), ensure_ascii=False)


def _path_text(keys):
    """The keys that lead to a part of a result, written as a path that reads it: a key with a dot in its name, or the key `*`, in
    brackets."""
    return '.'.join('[%s]' % key if '.' in key or key == '*' else key for key in keys)


def _collections(value, keys=(), depth=0):
    """(path, parent object, records, keys) for every list of objects of a result that is reached through object keys only; `keys`
    are the keys that lead to it and `path` is their path text."""
    value = _decoded_quietly(value) if isinstance(value, str) else value
    if not isinstance(value, dict) or depth > 8:
        return
    for key, child in value.items():
        child = _decoded_quietly(child) if isinstance(child, str) else child
        where = tuple(keys) + (key,)
        if isinstance(child, list):
            if child and all(isinstance(item, dict) for item in child):
                yield _path_text(where), value, child, where
        elif isinstance(child, dict):
            yield from _collections(child, where, depth + 1)


def _paging_keys(parent, named=False):
    """(total, hasMore) as an object beside a list states them; None for what it does not state. With `named`, the key that states
    the total comes third."""
    name = next((k for k in TOTAL_KEYS if k in parent and number(parent[k]) is not None), None)
    total = number(parent[name]) if name else None
    more = parent.get(MORE_KEY)
    if isinstance(more, str) and more.strip().lower() in ('true', 'false'):
        more = more.strip().lower() == 'true'
    total = int(total) if total is not None and total == total.to_integral_value() else None
    more = more if isinstance(more, bool) else None
    return (total, more, name if total is not None else None) if named else (total, more)


def _place(parent):
    """(key, whole number) when an object beside a list states the place of its page in the list (`offset` or `page`); None otherwise."""
    for key in PLACE_KEYS:
        value = number(parent[key]) if key in parent else None
        if value is not None and value == value.to_integral_value():
            return key, int(value)
    return None


# ---------------------------------------------------------------------------------------------------------------- reading results
def _local(tag):
    return tag.rsplit('}', 1)[-1].split(':')[-1]


def _xml_value(element):
    children, attributes = list(element), {'@' + _local(k): v for k, v in element.attrib.items()}
    text = (element.text or '').strip()
    if not children and not attributes:
        return text
    out, repeated = _Xml(attributes), set()
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
        return _Xml({_local(root.tag): _xml_value(root)})
    return text


def _decoded(value):
    return read_text(value) if isinstance(value, str) else value


def _segments(path):
    """The steps of a path or a field: split at dots, except that a step in brackets is one key taken literally (`[a.b]`)."""
    path = (path or '').strip()
    if not path:
        return []
    if '[' not in path:
        return path.split('.')
    out, start, length = [], 0, len(path)
    while start <= length:
        if start < length and path[start] == '[':
            end = path.find(']', start + 1)
            if end != -1 and (end + 1 == length or path[end + 1] == '.'):
                out.append(_Key(path[start + 1:end]))
                start = end + 2
                continue
        dot = path.find('.', start)
        dot = length if dot == -1 else dot
        out.append(path[start:dot])
        start = dot + 1
    return out


def _is_star(segment):
    return segment == '*' and not isinstance(segment, _Key)


def _keys_text(value):
    keys = [k if len(k) <= 40 else k[:40] + '...' for k in list(value)[:LIMITS['previewKeys']]]
    return ', '.join(keys) + (' (%d keys in all)' % len(value) if len(value) > LIMITS['previewKeys'] else '') if keys else 'none'


def _readings(value, segment):
    """The keys by which an object answers a step written in brackets, `[k]`. There are three: the key `k`; the key `[k]` itself, which
    is how version 4 read such a step when `k` has no dot and how an output names a field given in brackets; and, when `k` has a dot,
    the first key of version 4's reading of the text as nested steps (`[a.b]` as the key `[a` and then `b]`)."""
    raw = '[%s]' % segment
    first = raw.split('.')[0]
    return [key for key, there in ((str(segment), segment in value), (raw, raw in value), (first, first != raw and first in value)) if there]


def _bracketed(value, segment, where):
    """The value of an object at a step written in brackets, by the one key that answers it (`_readings`), so a call that version 4
    answered keeps its answer; an object with more than one is refused, never read by a silent choice. The objects of a whole call are
    held to one key before any of them is read (`note_readings`)."""
    raw = '[%s]' % segment
    keys = _readings(value, segment)
    if len(keys) > 1:
        raise Ambiguous('%s has the keys %s, so the step %s has more than one reading and is not read'
                        % (where or 'the result', ' and '.join(json.dumps(key, ensure_ascii=False) for key in keys), raw))
    if not keys:
        raise KeyError('%s has no key %r; its keys are %s' % (where or 'the result', str(segment), _keys_text(value)))
    if keys[0] in (str(segment), raw):
        return value[keys[0]]
    for piece in raw.split('.'):
        value = _step(value, piece, where)
    return value


def note_readings(items, path, seen):
    """Counts in `seen`, for every step of `path` written in brackets, by which key the objects found at that step answer it:
    {the step's position: {'step': '[k]', 'keys': {key: objects}}}. `items` are walked together, as a source's path walks a result and
    a field walks a record; what cannot be walked is passed over here, because the walk that follows refuses it or counts it missing."""
    segments = _segments(path)
    if not any(isinstance(segment, _Key) for segment in segments):
        return
    current = list(items)
    for index, segment in enumerate(segments):
        star, nxt = _is_star(segment), []
        entry = seen.setdefault(index, {'step': '[%s]' % segment, 'keys': {}}) if isinstance(segment, _Key) else None
        for item in current:
            try:
                item = _decoded(item)
            except CalculationError:
                continue
            if star:
                if not isinstance(item, dict) or isinstance(item, _Xml):
                    nxt.extend(item if isinstance(item, list) else [item])
                continue
            if entry is not None and isinstance(item, dict):
                for key in _readings(item, segment):
                    entry['keys'][key] = entry['keys'].get(key, 0) + 1
            try:
                nxt.append(_step(item, segment, ''))
            except (KeyError, CalculationError):
                pass
        current = nxt


def _step(value, segment, where):
    value = _decoded(value)
    if isinstance(value, dict):
        if isinstance(segment, _Key):
            return _bracketed(value, segment, where)
        if segment in value:
            return value[segment]
        raise KeyError('%s has no key %r; its keys are %s' % (where or 'the result', str(segment), _keys_text(value)))
    if isinstance(value, list):
        if not isinstance(segment, _Key) and _POSITION.fullmatch(segment):
            index = int(segment)
            if -len(value) <= index < len(value):
                return value[index]
            raise KeyError('%s has no position %s (it has %d elements)' % (where or 'the result', segment, len(value)))
        raise KeyError('%s is a list: use a position or * instead of %r' % (where or 'the result', str(segment)))
    raise KeyError('%s is a single value, so it has no %r' % (where or 'the result', str(segment)))


def _dotted_key(value, segments, index):
    """The key of the object `value` whose name has dots and which the path, from `index` on, spells as nested steps; None otherwise."""
    if not isinstance(value, dict) or isinstance(segments[index], _Key):
        return None
    rest = '.'.join(segments[index:])
    for key in value:
        if '.' in key and (rest == key or rest.startswith(key + '.')):
            return key
    return None


def _dotted_refusal(key):
    return CalculationError('the key %s has a dot in its name, so it is not the nested steps %s: write it in brackets, [%s]'
                            % (json.dumps(key, ensure_ascii=False), ' then '.join(json.dumps(part, ensure_ascii=False) for part in key.split('.')), key))


def walk_detail(value, path):
    """(values, lacked): the values at `path` inside `value`. Before the first `*` a missing step is an error; after it, an element that
    lacks the step is left out and counted in `lacked` under that step. `*` takes the elements of a list; an object is refused, except
    one read from an XML element, which counts as a list of one like any single value."""
    segments = _segments(path)
    current, spread, lacked, where = [value], False, {}, ''
    for index, segment in enumerate(segments):
        star, nxt = _is_star(segment), []
        for item in current:
            item = _decoded(item)
            if star:
                if isinstance(item, dict) and not isinstance(item, _Xml):
                    raise CalculationError('path %r: * takes the elements of a list, but %s is an object (its keys are %s); name a key '
                                           'instead of *' % (path, where or 'the result', _keys_text(item)))
                nxt.extend(item if isinstance(item, list) else [item])
                continue
            try:
                nxt.append(_step(item, segment, where))
            except KeyError as error:
                dotted = _dotted_key(item, segments, index)
                if dotted:
                    raise _dotted_refusal(dotted)
                if not spread:
                    raise PathMissing('path %r: %s' % (path, error.args[0]))
                lacked[str(segment)] = lacked.get(str(segment), 0) + 1
        if star:
            spread = True
        current = nxt
        where = (where + '.' + segment) if where else str(segment)
    return [_decoded(v) for v in current], lacked


def walk(value, path):
    """(values, missing): as `walk_detail`, with the elements left out counted together."""
    values, lacked = walk_detail(value, path)
    return values, sum(lacked.values())


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


def locate(record, segments):
    """Whether a record has the field of `segments`: 'present', 'null' (it has it and it is null) or 'missing'. A key with a dot in its
    name that the field spells as nested steps is refused, because that reads as missing in every record."""
    value = record
    for index, segment in enumerate(segments):
        try:
            value = _step(value, segment, '')
        except KeyError:
            dotted = _dotted_key(_decoded_quietly(value) if isinstance(value, str) else value, segments, index)
            if dotted:
                raise _dotted_refusal(dotted)
            return 'missing'
        except Ambiguous:
            raise
        except CalculationError:
            return 'missing'
    return 'null' if value is None else 'present'


def field_values(record, field):
    """The values at `field` inside a record for a condition with `elements`, found as a source's path finds its records: `*` takes every
    element of a list, a list at the end gives its elements, and an element that lacks the rest of the field is left out. A record that
    lacks the field has no values. A text on the way that cannot be read (broken XML, a document type) is refused, never taken as missing."""
    return element_values(record, field)[0]


def element_values(record, field):
    """(values, state) of `field_values`: 'values', 'empty' (the field is there and holds no element), 'lacking' (its elements lack the
    rest of the field) or 'missing' (the record lacks the field)."""
    try:
        values, lacked = walk_detail(record, field)
    except PathMissing:
        return [], 'missing'
    values = [_decoded(value) for value in records_of(values)]  # a list at the end gives its elements read as * would read them
    return values, ('values' if values else 'lacking' if lacked else 'empty')


def has_wildcard(field):
    """Whether a field has a path segment that is exactly `*`; an asterisk inside a key name, or in brackets, is part of that name."""
    return isinstance(field, str) and any(_is_star(segment) for segment in _segments(field))


def holds(record, condition):
    """Whether one filter condition holds for a record: a literal comparison of the value at its field or, with `elements`, of the values
    there (any: at least one holds; none: no value holds)."""
    elements = condition.get('elements')
    if elements is None:
        return compare(field_of(record, condition.get('field', '')), condition['op'], condition['value'])
    found = any(compare(value, condition['op'], condition['value']) for value in field_values(record, condition.get('field', '')))
    return found if elements == 'any' else not found


# ---------------------------------------------------------------------------------------------------------------- the read line
def _read(result_id, path, amount, matched, missing=0, lacked=None):
    """What one source contributed, for the read line: `amount` is a count of records or, for view and arithmetic, a phrase."""
    out = {'resultId': result_id, 'path': path if isinstance(path, str) else '', 'records': amount, 'matchedNothing': not matched,
           'missing': missing}
    if lacked:
        out['lacked'] = dict(lacked)
    return out


def _records_phrase(amount):
    if isinstance(amount, str):
        return amount
    return '%d record%s' % (amount, '' if amount == 1 else 's')


def _where(path):
    path = (path or '').strip() if isinstance(path, str) else ''
    return 'at %s' % json.dumps(path, ensure_ascii=False) if path else 'at the whole result'


def read_line(reads):
    """The line that starts every calculate output: per source, in the order given, the result id, the path, what it contributed,
    whether the path matched nothing and the elements left out with the step they lacked. It never sums the sources: two sources can hold
    the same records."""
    if not reads:
        return 'read: no result (numbers only)'
    parts = []
    for item in reads:
        part = '%s %s: %s' % (item['resultId'], _where(item['path']), _records_phrase(item['records']))
        if item['matchedNothing']:
            part += ' (the path matched nothing)'
        if item['missing']:
            lacked = item.get('lacked') or {}
            if not lacked:
                part += ' (%d element%s lacked the rest of the path)' % (item['missing'], '' if item['missing'] == 1 else 's')
            elif len(lacked) == 1:
                name = next(iter(lacked))
                part += ' (%d element%s lacked %s and %s left out)' % (item['missing'], '' if item['missing'] == 1 else 's',
                                                                         json.dumps(name, ensure_ascii=False),
                                                                         'was' if item['missing'] == 1 else 'were')
            else:
                part += ' (%d elements were left out: %s)' % (item['missing'], ', '.join(
                    '%d lacked %s' % (n, json.dumps(name, ensure_ascii=False)) for name, n in lacked.items()))
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


def note_lines(notes):
    """The coverage line and the warning lines of a calculate output or of a scenario result, each ending in a line break."""
    notes = notes or {}
    lines = ['coverage: %s' % notes['coverage']] if notes.get('coverage') else []
    lines += ['warning: %s' % warning for warning in notes.get('warnings') or []]
    return ''.join('%s\n' % line for line in lines)


def stored_text(result_id, text, line=None, notes=None):
    """What the agent reads of a stored result: its id line, for a calculate output its read line, its coverage and warning lines, its
    size and its shape."""
    return ID_LINE % result_id + ('%s\n' % line if line is not None else '') + note_lines(notes) + STORED_LINE % (len(text), preview(text))


def _sort_key(values):
    numbers = [number(v) for v in values]
    if all(n is not None for n in numbers):
        return lambda i: (0, numbers[i])
    return lambda i: (0 if values[i] is not None else 1, canonical(values[i]))


def _page_text(output):
    return json.dumps(plain(output), ensure_ascii=False, sort_keys=True)


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit - 3] + '...'


def _quoted(text):
    return json.dumps(text, ensure_ascii=False)


# ---------------------------------------------------------------------------------------------------------------- what a source is
class _Source:
    """One source of a call as it was read: its records, what its path left out, and what it says about how complete it is."""

    def __init__(self, result_id, path, records, matched, lacked, size, lineage, listed=False):
        self.result_id, self.path, self.records, self.matched, self.lacked, self.size = result_id, path, records, matched, lacked, size
        self.lineage, self.listed = lineage, listed  # listed: the path ends at a list, whose elements are the records
        self.kinds = None

    def count_kinds(self):
        """How many records are objects, lists and plain values."""
        if self.kinds is None:
            kinds = {'object': 0, 'list': 0, 'plain': 0}
            for record in self.records:
                record = _decoded_quietly(record) if isinstance(record, str) else record
                kinds['object' if isinstance(record, dict) else 'list' if isinstance(record, list) else 'plain'] += 1
            self.kinds = kinds
        return self.kinds

    @property
    def plain(self):
        """Whether the source holds plain values only (and at least one)."""
        return bool(self.records) and self.count_kinds()['plain'] == len(self.records)

    @property
    def name(self):
        return '%s %s' % (self.result_id, _where(self.path))

    def shape(self):
        kinds, total = self.count_kinds(), len(self.records)
        if not total:
            return '%s: no records' % self.name
        if kinds['plain'] == total:
            return '%s: %d plain value%s, not records (the first is %s)' % (self.name, total, '' if total == 1 else 's',
                                                                           _cut(json.dumps(plain(self.records[0]), ensure_ascii=False), 40))
        first = next((_decoded_quietly(r) if isinstance(r, str) else r for r in self.records
                      if isinstance(_decoded_quietly(r) if isinstance(r, str) else r, dict)), None)
        if kinds['object'] == total:
            return '%s: %d record%s with the keys %s' % (self.name, total, '' if total == 1 else 's', _keys_text(first))
        mixed = ', '.join('%d %s%s' % (n, kind if kind != 'plain' else 'plain value', '' if n == 1 else 's')
                          for kind, n in kinds.items() if n)
        return '%s: %d records (%s)%s' % (self.name, total, mixed, '; the objects have the keys %s' % _keys_text(first) if first else '')


def _shapes(sources):
    """The shapes of the sources of a refused call, each said once and at most three of them."""
    shapes = list(dict.fromkeys(_cut(source.shape(), 260) for source in sources))
    return shapes[:3] + (['and %d more' % (len(shapes) - 3)] if len(shapes) > 3 else [])


def _row(record):
    """What tells one record from another whatever fields were asked for: its plain values by key. A list or an object inside it
    is left out, because it may be another selection of the same thing. A plain value is its own row."""
    if isinstance(record, dict):
        return frozenset((key, canonical(value)) for key, value in record.items() if not isinstance(value, (dict, list)))
    return frozenset({('', canonical(record))})


def _paging(value, segments):
    """The list a source's path takes its records from: the first list on the way, before any `*`, when the path ends at it or goes on
    with `*`, with what the object that holds it states of it (a total, hasMore, an offset or a page number; a list need state none
    of them to be a page of a list whose other pages do). None when there is none, or when the path picks one position of it. An
    XML element that occurs once, which `*` takes as a list of one, is such a list only when the object that holds it states a total
    or hasMore (a page of one record); otherwise the path is followed through it. The list is known by the keys that lead to it
    (`ident`), as the path really reads them: a step in brackets is the key it names or the key with the brackets, whichever the
    object has."""
    current, keys = value, []
    for index, segment in enumerate(segments):
        if _is_star(segment):
            if isinstance(current, _Xml):
                continue
            return None
        current = _decoded_quietly(current) if isinstance(current, str) else current
        actual = None
        if isinstance(current, dict):
            if isinstance(segment, _Key):
                found = _readings(current, segment)
                actual = found[0] if len(found) == 1 and found[0] in (str(segment), '[%s]' % segment) else None
            elif segment in current:
                actual = str(segment)
        if actual is None:
            if isinstance(current, list) and not isinstance(segment, _Key) and _POSITION.fullmatch(segment) \
                    and -len(current) <= int(segment) < len(current):
                keys.append(str(int(segment) % len(current)))
                current = current[int(segment)]
                continue
            return None
        keys.append(actual)
        child = current[actual]
        child = _decoded_quietly(child) if isinstance(child, str) else child
        following = segments[index + 1] if index + 1 < len(segments) else None
        whole = following is None or _is_star(following)
        total, more, name = _paging_keys(current, named=True) if isinstance(child, (list, _Xml)) else (None, None, None)
        single = isinstance(child, _Xml) and following is not None and _is_star(following) and (total is not None or more is not None)
        if (isinstance(child, list) and whole) or single:
            records = child if isinstance(child, list) else [child]
            rows = [_row(record) for record in records]
            return {'prefix': _path_text(keys), 'ident': _identity(keys), 'key': str(segment), 'total': total, 'more': more,
                    'totalKey': name, 'shape': frozenset(key for record in records if isinstance(record, dict) for key in record),
                    'place': _place(current), 'count': len(records), 'rows': rows,
                    'names': frozenset.intersection(*(frozenset(key for key, _ in row) for row in rows)) if rows else None}
        current = child
    return None


def _records_name(segments, listed):
    """The name of the lists whose elements a path reads: its last key when it ends at lists (`listed`) or has no `*`, else the last
    key before its last `*`. Empty when it names no key."""
    stars = [index for index, segment in enumerate(segments) if _is_star(segment)]
    upto = segments if listed or not stars else segments[:stars[-1]]
    keys = [str(segment) for segment in upto if not _is_star(segment) and (isinstance(segment, _Key) or not _POSITION.fullmatch(segment))]
    return keys[-1] if keys else ''


def _shortened(value, segments, result_id):
    """A sentence when a source reads the list of a calculate output that holds fewer elements than the output says there are (a limit
    or a view page shortened it); None otherwise."""
    if not (isinstance(value, dict) and segments and str(segments[0]) in OUTPUT_LISTS and not isinstance(segments[0], _Key)):
        return None
    held, said = value.get(str(segments[0])), value.get(OUTPUT_LISTS[str(segments[0])])
    if isinstance(held, list) and isinstance(said, int) and not isinstance(said, bool) and len(held) < said:
        return '%s holds %d of its %d %s' % (result_id, len(held), said, segments[0])
    return None


def merge_lineage(lineages):
    out = _empty_lineage()
    for lineage in lineages:
        out['pages'].update(lineage.get('pages') or {})
        out['cuts'] += [cut for cut in lineage.get('cuts') or [] if cut not in out['cuts']]
        out['loose'].update(lineage.get('loose') or {})
    return out


def _held(pages):
    """(records, distinct, told, rows): the records the pages hold; how many of them are distinct; whether the pages tell their
    records apart; and, per page, its records as they are told apart. Two pages may hold the same records with other fields, so
    records are compared by the plain values that every record of every page has. Where there is no such value, or a page holds two
    records alike in them, a value is not an identity: every record counts, and `told` is false."""
    records = sum(page['count'] for page in pages)
    names = [page['names'] for page in pages if page['names'] is not None]
    common = frozenset.intersection(*names) if names else frozenset()
    if not common:
        return records, records, False, None
    rows = [[frozenset(pair for pair in row if pair[0] in common) for row in page['rows']] for page in pages]
    if any(len(set(mine)) != len(mine) for mine in rows):
        return records, records, False, None
    return records, len(set().union(*rows)), True, [set(mine) for mine in rows]


def _clash(pages, rows):
    """Whether two of the pages hold records, share none, and state the same place in the list (the same offset or page number) or
    each say that they are the last. They may be pages of two lists; they may as well be one list asked for in another order, so
    this is said, never concluded."""
    if rows is None:
        return False
    for index, page in enumerate(pages):
        for later in range(index + 1, len(pages)):
            other = pages[later]
            if not rows[index] or not rows[later] or rows[index] & rows[later]:
                continue
            if (page.get('place') is not None and page.get('place') == other.get('place')) or (page['more'] is False and other['more'] is False):
                return True
    return False


def lineage_part(lineage):
    """(coverage parts, incomplete lists): what the lists and shortened outputs a result was built from cover. It never says that a
    list is complete, and it says that records are missing only when that is certain.

    Which lists are pages of one list is not something a result says, and nothing a result holds can show that two lists of one
    name are not. One request can give several pages of one list under different keys of one result, so the path does not tell
    them apart. A page need not state the total, or anything at all. Two requests can ask for other fields of the same records, so
    neither the keys of the records nor their values do; and they can ask for another order, so the place a page states does not
    either. So every list a source reads is taken (`_paging`), and the lists of one name count together, with the records the
    sources read as elements of other lists of that name (`loose`).

    A list is short only when all of these records are fewer than the total it states. Where the lists state several totals, the
    line says "at least", because the records of one may be the records another lacks.

    With one total and as many records as it states, or more: more distinct records than the total are said as they are, with no
    cause; fewer distinct records are said with the condition that makes them a shortfall (pages overlap); and as many are named
    only when two pages at one place share no record, when every page says hasMore, or when no page says where it stands. What is
    left cannot be told apart: pages of two lists of one name and total that state different places."""
    built, incomplete, loose_records = [], [], lineage.get('loose') or {}
    for key in dict.fromkeys(page['key'] for page in lineage['pages'].values()):
        pages = [page for page in lineage['pages'].values() if page['key'] == key]
        where, loose = _quoted(key), sum(count for name, count in loose_records.values() if name == key)
        records, distinct, told, rows = _held(pages)
        noun, clash = 'distinct records' if told else 'records', _clash(pages, rows)
        totals = list(dict.fromkeys(page['total'] for page in pages if page['total'] is not None))
        if not totals:
            if all(page['more'] for page in pages) and not loose:
                built.append('%d %s%s at %s and no last page (hasMore is true)' % (distinct, 'distinct ' if told else '',
                                                                                  'record' if distinct == 1 else 'records', where))
                incomplete.append((key, None, pages[0].get('tool'), pages[0].get('shape') or frozenset()))
            continue
        said = {total: '%s %d' % (next(page for page in pages if page['total'] == total).get('totalKey') or TOTAL_KEYS[0], total)
                for total in totals}
        for total in totals:
            if records + loose >= total:
                continue
            own = [page for page in pages if page['total'] == total]
            exact = len(totals) == 1 and not loose and distinct == records and not clash
            if len(totals) > 1:
                count = '%d' % sum(page['count'] for page in own)
            else:
                count = '%d' % records if distinct == records else '%d distinct of %d records' % (distinct, records)
            built.append('%s of %s at %s (%s%d not among the sources)' % (count, said[total], where, '' if exact else 'at least ',
                                                                          total - records - loose))
            incomplete.append((key, total, own[0].get('tool'), frozenset().union(*(page.get('shape') or frozenset() for page in own))))
        if len(totals) != 1 or loose or records < totals[0]:
            continue
        total, entry = totals[0], (key, totals[0], pages[0].get('tool'), frozenset().union(*(page.get('shape') or frozenset() for page in pages)))
        if distinct > total:
            built.append('%d %s at %s, more than the %s their pages state' % (distinct, noun, where, said[total]))
        elif distinct < total:
            built.append('%d distinct of %d records at %s, %s (%d not among the sources if pages overlap)'
                         % (distinct, records, where, said[total], total - distinct))
            incomplete.append(entry)
        elif len(pages) > 1 and clash:
            built.append('%d %s of %d pages at %s, as many as %s, but two of the pages state the same place, or are each the last, and '
                         'share no record' % (distinct, noun, len(pages), where, said[total]))
            incomplete.append(entry)
        elif len(pages) > 1 and all(page['more'] is True for page in pages):
            built.append('%d %s at %s, as many as %s, but none of their %d pages is a last page (hasMore is true in each)'
                         % (distinct, noun, where, said[total], len(pages)))
            incomplete.append(entry)
        elif len(pages) > 1 and not any(page.get('place') is not None or page['more'] is not None for page in pages):
            built.append('%d %s of %d pages at %s, as many as %s; no page states its place in a list (offset, page or hasMore)'
                         % (distinct, noun, len(pages), where, said[total]))
    parts = ['built from ' + ', '.join(built)] if built else []
    if lineage['cuts']:
        parts.append('not whole: ' + ', '.join(lineage['cuts']))
    return parts, incomplete


def _given(name, value):
    """Whether an argument was really given: null, false, an empty text or list and offset 0 say nothing."""
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, dict)) and not value:
        return False
    return not (name == 'offset' and value == 0)


def _got(value):
    try:
        return _cut(json.dumps(value, ensure_ascii=False), 40)
    except (TypeError, ValueError):
        return type(value).__name__


def _keys_problem(what, item, takes):
    """A problem when an object of the arguments has a key it does not take; None otherwise."""
    extra = [str(key) for key in item if key not in takes]
    if not extra:
        return None
    return '%s takes %s, not %s' % (what, ' and '.join([', '.join(takes[:-1]), takes[-1]]) if len(takes) > 1 else takes[0], ', '.join(extra))


def form_problems(arguments):
    """The problems of form of a call's arguments, each naming the argument and the form it takes: a wrong type, and a key that a
    source, a condition or an operand does not take. Null is an argument left out."""
    problems = []

    def check(name, good, form):
        value = arguments.get(name)
        if value is not None and not good(value):
            problems.append('%s is %s (got %s)' % (name, form, _got(value)))

    def whole(value, least, most=None):
        return isinstance(value, int) and not isinstance(value, bool) and value >= least and (most is None or value <= most)

    for name in ('field', 'sum_field'):
        check(name, lambda v: isinstance(v, str), 'a text')
    for name in ('group_by', 'fields'):
        check(name, lambda v: isinstance(v, list) and all(isinstance(item, str) for item in v), 'a list of field names, each a text')
    check('descending', lambda v: isinstance(v, bool), 'true or false')
    check('limit', lambda v: whole(v, 1), 'a whole number of 1 or more')
    check('offset', lambda v: whole(v, 0), 'a whole number of 0 or more')
    check('round', lambda v: whole(v, 0, 12), 'a whole number from 0 to 12')
    check('sources', lambda v: isinstance(v, list), 'a list of {result_id, path}')
    check('conditions', lambda v: isinstance(v, list), 'a list of {field, op, value, elements}')
    check('operands', lambda v: isinstance(v, list), 'a list of numbers or {result_id, path}')
    for name, what in (('sources', 'a source'), ('operands', 'an operand')):
        for item in arguments.get(name) if isinstance(arguments.get(name), list) else []:
            if not isinstance(item, dict):
                if name == 'sources':
                    problems.append('a source is an object {result_id, path} (got %s)' % _got(item))
                continue
            problems.append(_keys_problem(what, item, ('result_id', 'path')))
            if 'result_id' in item and not isinstance(item['result_id'], str):
                problems.append('result_id is the text on the first line of a result (got %s)' % _got(item['result_id']))
            if item.get('path') is not None and not isinstance(item['path'], str):
                problems.append('path is a text (got %s)' % _got(item['path']))
    for item in arguments.get('conditions') if isinstance(arguments.get('conditions'), list) else []:
        if isinstance(item, dict):
            problems.append(_keys_problem('a condition', item, ('field', 'op', 'value', 'elements')))
            if item.get('field') is not None and not isinstance(item['field'], str):
                problems.append('the field of a condition is a text (got %s)' % _got(item['field']))
    return list(dict.fromkeys(problem for problem in problems if problem))


def _names(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _condition_text(condition):
    text = '%s %s %s' % (_quoted(condition.get('field', '')), condition['op'], json.dumps(condition['value'], ensure_ascii=False))
    return text + (' (elements %s)' % condition['elements'] if condition.get('elements') else '')


class Refusal(CalculationError):
    """A refused call with every problem found; `shapes` carries the shapes of the sources when a problem is one of shape."""

    def __init__(self, problems, shapes=()):
        problems, self.shapes = list(dict.fromkeys(problems)), list(shapes)
        text = problems[0] if len(problems) == 1 else '%d problems: %s' % (
            len(problems), '; '.join('(%d) %s' % (n, problem.rstrip('.')) for n, problem in enumerate(problems, 1)))
        if shapes:
            text = text.rstrip('.') + '. Shapes: ' + '; '.join(shapes)
        super().__init__(_cut(text, LIMITS['refusalChars']))
        self.problems = problems


# ---------------------------------------------------------------------------------------------------------------- calculate
class Calculator:
    def __init__(self, store):
        self.store = store
        self.readings = {}  # of the call being run: (path or field, its text) -> what `note_readings` counted

    def _one_reading(self, kind, items, path):
        """Refuses a step in brackets that the objects of this call answer by more than one key. A step is read one way in a whole
        call: by every record for a field, by every source and operand for a path. Version 4 read `[k]` as the key `[k]` only; to read
        it as the key `k` in a record that has that key instead would change the answer version 4 gave for the records beside it."""
        if not isinstance(path, str) or '[' not in path:
            return
        name = (kind, path.strip())
        seen = self.readings.setdefault(name, {'steps': {}, 'refusal': None, 'walked': False})
        if seen['refusal']:
            raise Ambiguous(seen['refusal'])  # said once, in the same words, however many sources share the path
        if kind == 'path' or not seen['walked']:  # the records of a call are walked once for a field, every source for its path
            note_readings(items, path, seen['steps'])
            seen['walked'] = True
        for entry in seen['steps'].values():
            if len(entry['keys']) > 1:
                keys = ', '.join('the key %s in %d' % (json.dumps(key, ensure_ascii=False), n) for key, n in entry['keys'].items())
                seen['refusal'] = ('the step %s of the %s %s has more than one reading among the objects of this call (%s), so it is not '
                                   'read' % (entry['step'], kind, _quoted(path.strip()), keys))
                raise Ambiguous(seen['refusal'])

    # ------------------------------------------------------------------ arguments
    @staticmethod
    def _argument_problems(op, arguments):
        """The problems of a call that its arguments alone show."""
        problems = []
        extra = [name for name in arguments if name != 'operation' and name not in APPLIES[op] and _given(name, arguments[name])]
        if extra:
            problems.append('%s %s not apply to %s, which takes %s' % (', '.join(extra), 'does' if len(extra) == 1 else 'do', op,
                                                                       ', '.join(APPLIES[op])))
        if op == 'group_by' and arguments.get('aggregate', 'count') == 'count':
            late = [name for name in ('sum_field', 'round') if _given(name, arguments.get(name))]
            if late:
                problems.append('%s %s only with aggregate sum' % (' and '.join(late), 'applies' if len(late) == 1 else 'apply'))
        starred = []
        if op in ('distinct', 'sort') + SET_OPERATIONS and has_wildcard(arguments.get('field')):
            starred.append('field')
        if op == 'group_by':
            starred += ['group_by'] if any(has_wildcard(key) for key in _names(arguments.get('group_by'))) else []
            starred += ['sum_field'] if has_wildcard(arguments.get('sum_field')) else []
        if op in ('view', 'sort', 'filter') and any(has_wildcard(name) for name in _names(arguments.get('fields'))):
            starred.append('fields')
        if starred:
            problems.append('%s cannot have a * segment: * belongs in the path of a source, or in the field of a filter condition with '
                            'elements any or none' % ' and '.join(starred))
        if op == 'filter':
            problems += Calculator._condition_problems(arguments.get('conditions'))
        if op == 'group_by':
            keys = arguments.get('group_by')
            if not (isinstance(keys, list) and all(isinstance(k, str) for k in keys)):
                problems.append('group_by needs a list of fields in group_by; an empty list gives one group over all records')
            if arguments.get('aggregate', 'count') not in ('count', 'sum'):
                problems.append('aggregate is count or sum')
        return problems

    @staticmethod
    def _condition_problems(conditions):
        if not isinstance(conditions, list) or not conditions:
            return ['filter needs at least one condition']
        problems, sound = [], []
        for condition in conditions:
            if not isinstance(condition, dict) or condition.get('op') not in COMPARISONS or 'value' not in condition:
                problems.append('a condition needs field, op (%s) and value' % ', '.join(COMPARISONS))
            elif 'elements' in condition and condition['elements'] not in ELEMENTS:
                problems.append('elements is %s, or left out' % ' or '.join(ELEMENTS))
            elif 'elements' not in condition and has_wildcard(condition.get('field', '')):
                problems.append(WILDCARD_REFUSAL)
            elif (isinstance(condition['value'], bool) or condition['value'] is None) and condition['op'] not in ('eq', 'ne'):
                problems.append('%s cannot compare with %s; use eq or ne' % (condition['op'], json.dumps(condition['value'])))
            elif not (isinstance(condition['value'], (str, int, float)) or condition['value'] is None):
                problems.append('a condition value must be a text, a number, true, false or null')
            else:
                sound.append(condition)
        seen = {}
        for condition in sound:
            field, value = condition.get('field', ''), canonical(condition['value'])
            if not isinstance(field, str):
                continue
            key = (field.strip(), value)
            for other in seen.get(key, []):
                same_test = other['op'] == condition['op'] and {other.get('elements'), condition.get('elements')} == set(ELEMENTS)
                opposite = OPPOSITES[other['op']] == condition['op'] and other.get('elements') is None and condition.get('elements') is None
                if same_test or opposite:
                    problems.append('the conditions %s and %s contradict each other, so no record can meet both'
                                    % (_condition_text(other), _condition_text(condition)))
            seen.setdefault(key, []).append(condition)
        return problems

    # ------------------------------------------------------------------ sources
    def _source(self, source):
        """One source read: its text, its records and what it says about its own completeness. Raises CalculationError."""
        text = self.store.get(source['result_id'])
        value = read_text(text)
        self._one_reading('path', [value], source.get('path'))
        values, lacked = walk_detail(value, source.get('path'))
        records, listed = records_of(values), any(isinstance(found, list) for found in values)
        lineage = self._lineage(source['result_id'], value, source.get('path'), len(records), listed)
        return _Source(source['result_id'], source.get('path'), records, bool(values), lacked, len(text.encode('utf-8')), lineage, listed)

    def _meta(self, result_id):
        return (getattr(self.store, 'meta', None) or {}).get(result_id) or {}

    def _lineage(self, result_id, value, path, count=0, listed=False):
        """What the part of a result at `path` was built from: what the result itself was built from, plus the list the path reads (of
        a scenario result) or the shortened list (of a calculate output). When the `count` records the path reads are not the
        elements of that list (the path goes on into deeper lists, or reaches its records through a `*` before any list), they are
        kept as loose records under the name of the lists they are elements of."""
        meta = self._meta(result_id)
        lineage = merge_lineage([meta.get('lineage') or _empty_lineage()])
        segments = _segments(path)
        if meta.get('tool') == CALCULATE:
            cut = _shortened(value, segments, result_id)
            if cut and cut not in lineage['cuts']:
                lineage['cuts'].append(cut)
        else:
            cache = getattr(self.store, 'pages', None)
            known = (result_id, path if isinstance(path, str) else '')
            if cache is not None and known in cache:
                page = cache[known]
            else:
                page = _paging(value, segments)
                if page:
                    page['tool'] = meta.get('tool')
                    once = getattr(self.store, 'listed', None)
                    page = once.setdefault((result_id, page['ident']), page) if once is not None else page
                if cache is not None:
                    cache[known] = page
            if page:
                lineage['pages']['%s %s' % (meta.get('sha'), page['ident'])] = page
            name = _records_name(segments, listed)
            if count and not (page and name == page['key']):
                lineage['loose']['%s %s' % (meta.get('sha'), known[1].strip())] = (name, count)
        return lineage

    def _hint(self, result_id):
        """The shape of a result whose path could not be read, as a way to a valid path."""
        try:
            return '%s holds %s' % (result_id, json.dumps(bounded_shape(self.store.get(result_id), 400), ensure_ascii=False))
        except CalculationError:
            return None

    def _sources(self, arguments, minimum, problems, shapes):
        sources = arguments.get('sources')
        if not isinstance(sources, list) or len(sources) < minimum:
            problems.append('%s needs at least %d source%s' % (arguments.get('operation'), minimum, '' if minimum == 1 else 's'))
            return None
        if len(sources) > LIMITS['maxSources']:
            problems.append('at most %d sources' % LIMITS['maxSources'])
            return None
        out, failed = [], False
        for source in sources:
            if not isinstance(source, dict) or 'result_id' not in source:
                problems.append('every source needs a result_id')
                failed = True
                continue
            try:
                out.append(self._source(source))
            except CalculationError as error:
                problems.append(str(error))
                failed = True
                hint = self._hint(source['result_id']) if isinstance(error, PathMissing) or 'takes the elements of a list' in str(error) else None
                if hint and hint not in shapes and len(shapes) < 3:
                    shapes.append(hint)
        if failed:
            return None
        if sum(len(s.records) for s in out) > LIMITS['maxRecords']:
            problems.append('more than %d records' % LIMITS['maxRecords'])
            return None
        return out

    # ------------------------------------------------------------------ fields
    @staticmethod
    def _fields_used(op, arguments):
        """(argument, field) for every field the operation reads from a record, conditions apart; empty fields are the record itself."""
        used = []
        if op in ('distinct', 'sort') + SET_OPERATIONS:
            used.append(('field', arguments.get('field', '')))
        if op == 'group_by':
            used += [('group_by', key) for key in _names(arguments.get('group_by'))]
            if arguments.get('aggregate') == 'sum':
                used.append(('sum_field', arguments.get('sum_field', '')))
        if op in ('sort', 'filter', 'view'):
            used += [('fields', name) for name in _names(arguments.get('fields'))]
        seen, out = set(), []
        for label, field in used:
            if isinstance(field, str) and field.strip() and field.strip() not in seen and not has_wildcard(field):
                seen.add(field.strip())
                out.append((label, field.strip()))
        return out

    @staticmethod
    def _fields_text(fields):
        fields = list(dict.fromkeys(fields))
        return 'the field%s %s' % ('' if len(fields) == 1 else 's', _listed([_quoted(field) for field in fields], 6))

    @staticmethod
    def _plain_problem(fields, sources):
        """The refusal of named fields on sources of plain values, with the way to say it; None when no source holds plain values only."""
        plain_sources = [s for s in sources if s.plain]
        if not plain_sources or not fields:
            return None
        text = '%s cannot be read from %s: %s plain values, not records' % (
            Calculator._fields_text(fields), _listed([s.name for s in plain_sources], 3), 'it holds' if len(plain_sources) == 1 else 'they hold')
        other = next((s for s in sources if s.records and not s.plain), None)
        if other is None:
            return text + '. Leave the field empty to use the values themselves'
        path = (other.path or '').strip() if isinstance(other.path, str) else ''
        example = '.'.join(part for part in (path, '*' if other.listed else '', fields[0]) if part)  # * only at a list
        return text + ('. Leave the field empty to use the values themselves, and put it in the path of each source that holds '
                       'records (for %s: path %s)' % (other.result_id, _quoted(example)))

    def _absent_problem(self, op, arguments, absent, sources):
        """The refusal of fields that no record of any source has."""
        records = sum(len(source.records) for source in sources)
        total = op == 'group_by' and any(field in _names(arguments.get('group_by')) for field in absent)
        return 'no record has %s (0 of %d record%s): choose one of the keys named under Shapes, or correct the path of the source%s' % (
            self._fields_text(absent), records, '' if records == 1 else 's',
            '. To count or add up all records as one group, give group_by as an empty list' if total else '')

    def _field_coverage(self, op, arguments, sources, problems, absent):
        """Per field read, per source, how many records have it, lack it or hold null. A key with a dot spelled as nested steps goes to
        `problems`, a field no record has to `absent`."""
        coverage, records = [], sum(len(s.records) for s in sources)
        for label, field in self._fields_used(op, arguments):
            segments = _segments(field)
            try:
                self._one_reading('field', [record for source in sources for record in source.records], field)
                per = []
                for source in sources:
                    counts = {'present': 0, 'null': 0, 'missing': 0}
                    for record in source.records:
                        counts[locate(record, segments)] += 1
                    per.append(counts)
            except CalculationError as error:
                problems.append(str(error))
                continue
            if records and not any(c['present'] or c['null'] for c in per):
                absent.append(field)
            coverage.append({'field': field, 'per': per})
        return coverage

    def _condition_coverage(self, conditions, sources, problems, absent):
        """Per condition, how its field is covered: for a plain condition present, null and missing, and the records where the field
        holds a list or an object; for one with elements, the records with values, with an empty list, with elements that lack the rest
        and without the field. A field no record has goes to `absent`, the other refusals of fields to `problems`."""
        coverage, records = [], sum(len(s.records) for s in sources)
        for condition in conditions:
            field = condition.get('field', '')
            field = field.strip() if isinstance(field, str) else ''
            entry = {'field': field, 'elements': condition.get('elements'), 'condition': condition}
            try:
                self._one_reading('field', [record for source in sources for record in source.records], field)
                if condition.get('elements'):
                    states = {'values': 0, 'empty': 0, 'lacking': 0, 'missing': 0}
                    for source in sources:
                        for record in source.records:
                            states[element_values(record, field)[1]] += 1
                    entry['states'] = states
                    problem = None
                    if field and records and not states['values'] and not states['empty']:
                        absent.append(field)
                else:
                    segments, per, collections = _segments(field), [], 0
                    for source in sources:
                        counts = {'present': 0, 'null': 0, 'missing': 0}
                        for record in source.records:
                            counts[locate(record, segments)] += 1
                            collections += isinstance(field_of(record, field), (dict, list))
                        per.append(counts)
                    entry['per'] = per
                    problem = None
                    if field and records and not any(c['present'] or c['null'] for c in per):
                        if condition['value'] is not None:  # a comparison with null is the test that a field is there, and is answered
                            absent.append(field)
                    elif collections and condition['value'] is not None:
                        problem = ('%s holds a list or an object in %d of %d record%s, which one value never equals: say elements any or '
                                   'none to compare the values inside it, or compare with null to test that the field is there'
                                   % (_quoted(field) if field else 'the record itself', collections, records, '' if records == 1 else 's'))
            except CalculationError as error:
                problems.append(str(error))
                continue
            if problem:
                problems.append(problem)
            coverage.append(entry)
        return coverage

    @staticmethod
    def _gaps(counts):
        return ', '.join('%d %s' % (counts[name], name) for name in ('missing', 'null') if counts[name])

    def _field_parts(self, entries, sources):
        """The coverage parts of the fields read: one per field that some records lack or hold null. A field every record has is
        not named, so that the line stays short."""
        gaps = [self._field_part(entry, sources) for entry in entries
                if any(counts['missing'] or counts['null'] for counts in entry['per'])]
        return list(dict.fromkeys(gaps))

    def _field_part(self, entry, sources):
        per = entry['per']
        total = {name: sum(c[name] for c in per) for name in ('present', 'null', 'missing')}
        records = sum(total.values())
        text = '%s in %d of %d records (%s)' % (_quoted(entry['field']), total['present'], records, self._gaps(total))
        if len(sources) > 1:
            unique = len({source.result_id for source in sources}) == len(sources)
            gaps = ['%s: %s' % (source.result_id if unique else source.name, self._gaps(counts))
                    for source, counts in zip(sources, per) if counts['missing'] or counts['null']]
            if len(gaps) < len(sources):
                text += ' [%s]' % _listed(gaps, 3)
        return text

    @staticmethod
    def _elements_part(entry):
        states = entry['states']
        records = sum(states.values())
        if states['values'] == records:
            return None
        gaps = ', '.join('%d %s' % (states[name], words) for name, words in (
            ('empty', 'with an empty list'), ('lacking', 'whose elements lack the rest'), ('missing', 'without the field')) if states[name])
        return '%s has values in %d of %d records (%s)' % (_quoted(entry['field']), states['values'], records, gaps)

    @staticmethod
    def _shorten(records, arguments):
        fields = arguments.get('fields')
        if fields:
            records = [{f: field_of(r, f) for f in fields} for r in records]
        limit = arguments.get('limit')
        return records[:limit] if limit else records

    # ------------------------------------------------------------------ the call
    def run(self, arguments):
        """(output dict, result ids used, bytes read, reads for the read line, notes). `notes` holds the coverage line, the warnings
        and what the output was built from. Raises CalculationError for a refused call, with every problem found."""
        if not isinstance(arguments, dict):
            raise CalculationError('the arguments must be an object')
        op = arguments.get('operation')
        if op not in OPERATIONS:
            raise CalculationError('unknown operation %r; the operations are %s' % (op, ', '.join(OPERATIONS)))
        self.readings = {}
        form = form_problems(arguments)
        problems, shapes = form + self._argument_problems(op, arguments), []
        if form:  # the rest of the call cannot be read until its arguments have their form
            raise Refusal(problems)
        if op in ('arithmetic', 'view'):
            try:
                out, ids, size, reads, lineage, parts = self._arithmetic(arguments) if op == 'arithmetic' else self._view(arguments)
            except Refusal as error:
                raise Refusal(problems + error.problems, error.shapes)
            except CalculationError as error:
                problems.append(str(error))
                hint = getattr(error, 'hint', None)
                raise Refusal(problems, [hint] if hint else [])
            if problems:
                raise Refusal(problems)
            return out, ids, size, reads, self._notes(arguments, parts, lineage, [])
        sources = self._sources(arguments, 2 if op in SET_OPERATIONS else 1, problems, shapes)
        fields = conditions = []
        if sources is not None:
            before, absent, sound = len(problems), [], []
            fields = self._field_coverage(op, arguments, sources, problems, absent)
            if op == 'filter' and isinstance(arguments.get('conditions'), list):
                sound = [c for c in arguments['conditions'] if isinstance(c, dict) and not self._condition_problems([c])]
                conditions = self._condition_coverage(sound, sources, problems, absent)
            named = [entry['field'] for entry in fields] + [entry['field'] for entry in conditions if entry['field']]
            plain_problem = self._plain_problem(named, sources)
            if plain_problem:
                problems.append(plain_problem)
            elif absent:
                problems.append(self._absent_problem(op, arguments, absent, sources))
            if len(problems) > before:
                shapes += _shapes(sources)
        if problems:
            raise Refusal(problems, shapes)
        per_source = [source.records for source in sources]
        records = [r for group in per_source for r in group]
        ids, size = [source.result_id for source in sources], sum(source.size for source in sources)
        missing = sum(sum(source.lacked.values()) for source in sources)
        reads = [_read(s.result_id, s.path, len(s.records), s.matched, sum(s.lacked.values()), s.lacked) for s in sources]
        field = arguments.get('field', '')
        plain_conditions = [entry for entry in conditions if not entry.get('elements') and entry['field']]
        out, parts, warnings = {'operation': op}, self._field_parts(fields + plain_conditions, sources) if records else [], []
        if op == 'count':
            out['count'] = len(records)
        elif op == 'distinct':
            seen = {}
            for record in records:
                value = field_of(record, field)
                seen.setdefault(canonical(value), value)
            values = [seen[k] for k in sorted(seen)]
            out.update({'count': len(values), 'values': values[:arguments['limit']] if arguments.get('limit') else values})
            parts += self._null_part(values)
        elif op == 'group_by':
            grouped, more = self._group_by(records, arguments)
            out.update(grouped)
            parts += more
        elif op == 'sort':
            values = [field_of(r, field) for r in records]
            order = sorted(range(len(records)), key=_sort_key(values), reverse=bool(arguments.get('descending')))
            out.update({'count': len(records), 'records': self._shorten([records[i] for i in order], arguments)})
        elif op == 'filter':
            conditions_given = arguments['conditions']
            held = [0] * len(conditions_given)
            kept = []
            for record in records:
                verdicts = [holds(record, c) for c in conditions_given]
                held = [n + bool(v) for n, v in zip(held, verdicts)]
                if all(verdicts):
                    kept.append(record)
            out.update({'count': len(kept), 'records': self._shorten(kept, arguments)})
            parts += self._filter_parts(conditions, conditions_given, held, len(records), len(kept)) if records else []
            warnings += self._position_warnings(conditions_given, records)
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
            parts.append('%s of sets of %s values' % (op, _listed([str(len(values_)) for values_ in sets], 6)))
            parts += self._null_part(values)
        if missing:
            out['missing'] = missing
        lineage = merge_lineage([source.lineage for source in sources])
        return out, ids, size, reads, self._notes(arguments, parts, lineage, warnings)

    # ------------------------------------------------------------------ coverage and warnings
    @staticmethod
    def _null_part(values):
        if not any(value is None for value in values):
            return []
        return ['the %d value%s include null (%d not null)' % (len(values), '' if len(values) == 1 else 's', len(values) - 1)]

    def _filter_parts(self, conditions, given, held, records, kept):
        parts = []
        for entry in conditions:
            if entry.get('elements'):
                parts += [part for part in [self._elements_part(entry)] if part]
            elif entry['field']:
                missing = sum(c['missing'] for c in entry['per'])
                if missing and compare(None, entry['condition']['op'], entry['condition']['value']):
                    parts.append('%s holds for the %d record%s without the field' % (_condition_text(entry['condition']), missing,
                                                                                    '' if missing == 1 else 's'))
        if records and not kept:
            alone = ['%s holds for %d' % (_condition_text(c), n) for c, n in zip(given, held)]
            parts.append('no record of %d met every condition (alone: %s)' % (records, _listed(alone, 6)))
        return parts

    @staticmethod
    def _position_warnings(conditions, records):
        """A warning when conditions test fixed positions of a list that has more elements than the positions tested."""
        tested = {}
        for condition in conditions:
            if condition.get('elements') or not isinstance(condition.get('field'), str):
                continue
            segments = _segments(condition['field'])
            for index, segment in enumerate(segments):
                if not isinstance(segment, _Key) and _POSITION.fullmatch(segment):
                    prefix = '.'.join(str(s) for s in segments[:index])
                    tested.setdefault(prefix, {'positions': set(), 'rest': '.'.join(str(s) for s in segments[index + 1:])})
                    tested[prefix]['positions'].add(int(segment))
                    break
        warnings = []
        for prefix, entry in tested.items():
            longest = 0
            for record in records:
                value = field_of(record, prefix) if prefix else (_decoded_quietly(record) if isinstance(record, str) else record)
                if isinstance(value, list):
                    longest = max(longest, len(value))
            if longest > len(entry['positions']):
                positions = sorted(entry['positions'])
                field = '.'.join(part for part in (prefix, '*', entry['rest']) if part)
                warnings.append('the conditions test position%s %s of %s, which has up to %d elements; a condition with elements any or '
                                'none and the field %s tests every element'
                                % ('' if len(positions) == 1 else 's', ', '.join(str(p) for p in positions),
                                   _quoted(prefix) if prefix else 'the record', longest, _quoted(field)))
        return warnings

    def _notes(self, arguments, parts, lineage, warnings):
        """The notes of a successful call: its coverage line, its warnings and what its output was built from."""
        built, incomplete = lineage_part(lineage)
        parts = list(dict.fromkeys(list(parts) + built))
        warnings = list(warnings)
        try:
            earlier = (getattr(self.store, 'calculations', None) or {}).get(canonical(arguments))
            if earlier:
                warnings.insert(0, 'this repeats the calculation that gave %s, which is still held' % earlier)
            warnings += self._other_pages(lineage, incomplete) + self._held_more(arguments)
        except Exception:  # a warning is advice: it never fails a calculation that is otherwise sound
            pass
        return {'coverage': _cut('; '.join(parts), LIMITS['coverageLineChars']) if parts else None,
                'warnings': [_cut(warning, LIMITS['warningChars']) for warning in warnings[:LIMITS['maxWarnings']]], 'lineage': lineage}

    def _other_pages(self, lineage, incomplete):
        """A warning naming the held results that have pages of a list the sources leave short and are not among the sources: lists of
        the same tool, name and record keys that state the same total, or none."""
        warnings, used, meta = [], set(lineage['pages']), getattr(self.store, 'meta', None) or {}
        for key, total, tool, shape in dict.fromkeys(incomplete):
            others, unstated = [], False
            for result_id, sha, ident, name, said, _, _, keys in getattr(self.store, 'paged', []):
                if name != key or said not in (total, None) or '%s %s' % (sha, ident) in used:
                    continue
                if (meta.get(result_id) or {}).get('tool') != tool or not (keys <= shape or shape <= keys):
                    continue
                others.append(result_id)
                unstated = unstated or (said is None and total is not None)
            others = list(dict.fromkeys(others))
            if others:
                stated = 'hasMore' if total is None else 'totalCount %d' % total + (' or no total' if unstated else '')
                warnings.append('%s also hold%s records at %s with %s and %s not among the sources'
                                % (_listed(others, 5), 's' if len(others) == 1 else '', _quoted(key), stated,
                                   'is' if len(others) == 1 else 'are'))
        return warnings

    def _held_more(self, arguments):
        """A warning when the sources read lists whose records are all held in earlier results, and those earlier lists hold more
        records than the lists the sources read."""
        repeated, lists = getattr(self.store, 'repeated', None) or {}, getattr(self.store, 'lists', None) or {}
        used, holders = set(), set()
        for source in arguments.get('sources') or []:
            if not isinstance(source, dict) or not isinstance(source.get('path'), str):
                continue
            for (result_id, path), held in repeated.items():
                if result_id == source.get('result_id') and (source['path'].strip() + '.').startswith(path + '.'):
                    used.add((result_id, path))
                    holders.update(held)
        named = {source.get('result_id') for source in arguments.get('sources') or [] if isinstance(source, dict)}
        holders = {holder for holder in holders if holder[0] not in named}
        for result_id, path in list(holders):  # a holding result's other lists of records with the same keys are pages of the same list
            keys = set(lists[(result_id, path)][0]) if lists.get((result_id, path)) else None
            holders.update(other for other, records in lists.items() if other[0] == result_id and records and set(records[0]) == keys)
        have, more = sum(len(lists.get(key, [])) for key in used), sum(len(lists.get(key, [])) for key in holders)
        if not holders or more <= have:
            return []
        ids = sorted({holder[0] for holder in holders})
        return ['%s hold%s the %d records these sources read and %d more of the same list%s; %s not among the sources'
                % (_listed(ids, 5), 's' if len(ids) == 1 else '', have, more - have, '' if len(holders) == 1 else 's',
                   'it is' if len(ids) == 1 else 'they are')]

    # ------------------------------------------------------------------ view
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
        a deeper path reads it. The page is what version 4 gave; its coverage and warning lines stand above it."""
        sources = arguments.get('sources')
        if not isinstance(sources, list) or len(sources) != 1:
            raise CalculationError('view needs exactly one source')
        source = sources[0]
        if not isinstance(source, dict) or 'result_id' not in source:
            raise CalculationError('every source needs a result_id')
        text = self.store.get(source['result_id'])
        start, end = self._window(arguments)
        try:
            whole = read_text(text)
            self._one_reading('path', [whole], source.get('path'))
            values, lacked = walk_detail(whole, source.get('path'))
            lineage = self._lineage(source['result_id'], whole, source.get('path'), len(records_of(values)),
                                    any(isinstance(found, list) for found in values))
        except CalculationError as error:
            if isinstance(error, PathMissing) or 'takes the elements of a list' in str(error):
                error.hint = self._hint(source['result_id'])
            raise
        missing = sum(lacked.values())
        spread = any(_is_star(segment) for segment in _segments(source.get('path')))
        value = values if spread or len(values) != 1 else values[0]
        rid, path = source['result_id'], source.get('path')
        extra = {'missing': missing} if missing else {}
        fields = arguments.get('fields')
        if fields and not isinstance(value, list):
            raise CalculationError('fields shortens the records of a list, and the part %s is not a list' % _where(path))
        if not isinstance(value, (list, dict, str)) and (start or end is not None):
            raise CalculationError('offset and limit page through a list, an object or a text, and the part %s is one value' % _where(path))
        parts = []
        if fields and isinstance(value, list):  # fields reads the records as any other operation does, so it takes the same checks
            listed, problems, absent = _Source(rid, path, value, bool(values), lacked, 0, lineage, True), [], []
            coverage = self._field_coverage('view', arguments, [listed], problems, absent)
            if listed.plain and coverage:
                problems.append('%s cannot be read from %s: it holds plain values, not records. Leave fields out to read the values '
                                'themselves' % (self._fields_text([entry['field'] for entry in coverage]), listed.name))
            elif absent:
                problems.append(self._absent_problem('view', arguments, absent, [listed]))
            if problems:
                raise Refusal(problems, _shapes([listed]))
            parts = self._field_parts(coverage, [listed]) if value else []
        if isinstance(value, list):
            def build(n):
                return {'operation': 'view', 'offset': start, 'count': len(value),
                        'records': self._shorten(value[start:start + n], {'fields': fields})}
            out = self._page(build, len(value), start, end, 'records', extra)
            reads = _read(rid, path, len(value), bool(values), missing, lacked)
        elif isinstance(value, dict):
            keys = list(value)

            def build(n):
                return {'operation': 'view', 'offset': start, 'keyCount': len(keys), 'value': {k: value[k] for k in keys[start:start + n]}}
            out = self._page(build, len(keys), start, end, 'value', extra)
            reads = _read(rid, path, 'an object of %d keys' % len(keys), True, missing, lacked)
        elif isinstance(value, str):
            def build(n):
                return {'operation': 'view', 'offset': start, 'length': len(value), 'text': value[start:start + n]}
            out = self._page(build, len(value), start, end, 'text', extra)
            reads = _read(rid, path, 'a text of %d characters' % len(value), True, missing, lacked)
        else:
            out = {'operation': 'view', 'value': value, **extra}
            reads = _read(rid, path, 'one value', True, missing, lacked)
        return out, [rid], len(text.encode('utf-8')), [reads], lineage, parts

    @staticmethod
    def _page(build, total, start, end, member, extra):
        """The longest window from `start` (up to `end`, or the end of the part) whose page fits viewPageChars, found by halving; with
        nextOffset when the part goes on after the page. Every key the page carries (`extra`, such as `missing`, and `nextOffset`) is
        counted when it is sized. When not even one item fits, that item's shape stands in for it, and a key longer than previewTextChars
        is shown as its start and its length, so the page always fits."""
        room = LIMITS['viewPageChars']

        def paged(n):
            out = dict(build(n), **extra)
            if start + n < total:
                out['nextOffset'] = start + n
            return out

        def fits(out):
            return len(_page_text(out)) <= room
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
                for limit in (room // 2, room // 8, LIMITS['previewTextChars']):
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
        """(the groups of the output, the coverage parts of the sum and of groups that are not unique values of one field)."""
        keys = arguments.get('group_by')
        aggregate = arguments.get('aggregate', 'count')
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
        if not keys and not groups:  # one group over all records, also when there are none
            groups[canonical({})] = {'key': {}, 'count': 0, 'sum': Decimal(0)}
        rows = []
        for name in sorted(groups):
            entry = groups[name]
            row = {'key': entry['key'], 'count': entry['count']}
            if aggregate == 'sum':
                row['sum'] = self._rounded(entry['sum'], arguments)
            rows.append(row)
        out = {'groupCount': len(rows), 'groups': rows[:arguments['limit']] if arguments.get('limit') else rows}
        parts = []
        if aggregate == 'sum':
            if skipped:
                out['notNumeric'] = skipped
            parts.append('the sum added %d of %d record%s%s' % (len(records) - skipped, len(records), '' if len(records) == 1 else 's',
                                                                '; %d had no number there' % skipped if skipped else ''))
        if len(keys) > 1 and len(rows) > 1:
            shared = []
            for key in keys:
                distinct = len({canonical(entry['key'][key]) for entry in groups.values()})
                if distinct < len(rows):
                    shared.append('%s has %d' % (_quoted(key), distinct))
            if shared:
                parts.append('%d groups over %d fields are not unique values of one field (distinct values: %s)'
                             % (len(rows), len(keys), ', '.join(shared)))
        return out, parts

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
        values, ids, size, reads, lineages = [], [], 0, [], []
        for operand in operands:
            if isinstance(operand, dict):
                text = self.store.get(operand.get('result_id'))
                ids.append(operand['result_id'])
                size += len(text.encode('utf-8'))
                whole = read_text(text)
                self._one_reading('path', [whole], operand.get('path'))
                found, _ = walk(whole, operand.get('path'))
                if len(found) != 1 or number(found[0]) is None:
                    raise CalculationError('the operand %s at %r is not one number' % (operand['result_id'], operand.get('path') or ''))
                values.append(number(found[0]))
                reads.append(_read(operand['result_id'], operand.get('path'), 'one number', True))
                lineages.append(self._meta(operand['result_id']).get('lineage') or _empty_lineage())
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
        return {'operation': 'arithmetic', 'value': self._rounded(result, arguments)}, ids, size, reads, merge_lineage(lineages), []


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
    with one long member, at any depth) is replaced by its bounded shape and named in `shapeOnly`, so no output passes the limit. Since
    version 5 the session refuses an output that would pass maxStoredOutputChars, so no calculate output is cut any more; the cut stays
    for a caller that asks for a smaller limit."""
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


def whole_text(output):
    """The output as JSON text, kept whole; an output longer than maxStoredOutputChars characters is refused, never cut."""
    text = json.dumps(plain(output), ensure_ascii=False, sort_keys=True)
    if len(text) > LIMITS['maxStoredOutputChars']:
        raise CalculationError('the output would be %d characters, more than the %d that can be kept whole: narrow it with fields, limit '
                               'or conditions, or use fewer sources' % (len(text), LIMITS['maxStoredOutputChars']))
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
        return scenario_result(self, name, arguments, text, is_error), is_error

    def _calculate(self, arguments):
        self.counts['calculate'] += 1
        began = self.clock()
        operation = arguments.get('operation') if isinstance(arguments, dict) else None
        try:
            output, ids, size, reads, notes = self.calculator.run(arguments)
            text = whole_text(output)
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
        shown, result_id, stored = shown_output(self.store, arguments, text, line, notes)
        self.last_details = {'tool': CALCULATE, 'operation': operation, 'resultIds': ids, 'resultId': result_id, 'error': None,
                             'calcSeconds': round(self.clock() - began, 3), 'inputBytes': size, 'outputBytes': len(shown.encode('utf-8')),
                             'addedTokensEstimate': estimate_tokens(shown), 'read': reads}
        if notes.get('coverage'):
            self.last_details['coverage'] = notes['coverage']
        if notes.get('warnings'):
            self.last_details['warnings'] = notes['warnings']
        if stored:
            self.last_details.update({'stored': True, 'storedChars': len(text), 'shownChars': len(shown)})
        return shown, False

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def shown_output(store, arguments, text, line, notes):
    """(what the agent reads, the result id, whether it was stored) for a successful calculate output. The output is stored, not shown,
    when it and its coverage and warning lines together pass storeAboveChars characters."""
    stored = output_is_stored(text, notes, arguments.get('operation'))
    result_id = store.add(CALCULATE, arguments, text, False, shown_in_full=not stored, read_line=line, notes=notes)
    try:
        store.calculations.setdefault(canonical(arguments), result_id)
    except (TypeError, ValueError):
        pass
    return output_text(result_id, text, line, notes, stored), result_id, stored


def output_is_stored(text, notes, operation=None):
    """Whether a calculate output is stored, not shown: when it and its coverage and warning lines together pass storeAboveChars. A
    view page is sized to be shown in full, so its lines never store it."""
    return len(text) + (0 if operation == 'view' else len(note_lines(notes))) > LIMITS['storeAboveChars']


def output_text(result_id, text, line, notes, stored):
    """What the agent reads of a successful calculate output: its id line, its read line, its coverage and warning lines, then the
    output or, when it is stored, its size and its shape."""
    return stored_text(result_id, text, line, notes) if stored else ID_LINE % result_id + line + '\n' + note_lines(notes) + text


def scenario_result(session, name, arguments, text, is_error):
    """What the agent reads of a scenario tool's result, stored under its id: in full, or as its shape when it is longer than
    storeAboveChars, after a warning line when it repeats what is already held."""
    store = session.store
    warnings, found = [], None
    if not is_error:
        try:
            warnings, found = store.examine(text)
        except Exception:  # a warning is advice: it never fails the scenario's own call
            warnings, found = [], None
    notes = {'warnings': [_cut(warning, LIMITS['warningChars']) for warning in warnings]}
    stored = len(text) > LIMITS['storeAboveChars']
    result_id = store.add(name, arguments, text, is_error, shown_in_full=not stored, notes=notes)
    if found is not None:
        try:
            store.index(result_id, found)
        except Exception:
            pass
    shown = scenario_text(result_id, text, notes, stored)
    session.last_details = {'tool': name, 'resultId': result_id}
    if stored:
        session.last_details.update({'stored': True, 'storedChars': len(text), 'shownChars': len(shown)})
    if notes['warnings']:
        session.last_details['warnings'] = notes['warnings']
    return shown


def scenario_text(result_id, text, notes, stored):
    """What the agent reads of a scenario result: its id line, a warning line when it repeats what is held, then the result or, when
    it is stored, its size and its shape."""
    return stored_text(result_id, text, notes=notes) if stored else ID_LINE % result_id + note_lines(notes) + text


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
