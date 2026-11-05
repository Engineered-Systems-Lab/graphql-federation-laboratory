"""Tests of the two harness tools with a fake tool session: result ids and their store, calculate's generic operations over JSON and XML
results, the refusal of foreign and unknown ids and of any operation that is not on the list, version 5's refusals, coverage line and
warning lines, ask_requester's fixed text and log, and the agent loop counting both tools in the tool-call cap. Invented data only; no
stack, key or network."""
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import harness_tools as ht
from agent import AgentRun, Limits
from budget import Budget
from fakes import FakeVendorClient, submit, turn
from mcp_client import FakeToolSession
from study_common import Redactor, read_jsonl

ROWS = [{'id': 'M1', 'status': 'ACTIVE', 'crew': 4, 'cost': '10.50', 'tags': ['x']},
        {'id': 'M2', 'status': 'CLOSED', 'crew': 2, 'cost': '4.25', 'tags': []},
        {'id': 'M3', 'status': 'ACTIVE', 'crew': 7, 'cost': '1.25'},
        {'id': 'M4', 'status': 'PLANNED', 'crew': 2}]
SOAP = ('<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
        '<p:listResponse xmlns:p="urn:example"><p:person rank="Lt"><p:id>P1</p:id><p:age>30</p:age></p:person>'
        '<p:person rank="Cdr"><p:id>P2</p:id><p:age>41</p:age></p:person><p:person rank="Lt"><p:id>P3</p:id><p:age>27</p:age></p:person>'
        '</p:listResponse></soap:Body></soap:Envelope>')
SINGLE = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><r><person><id>P9</id></person></r></soap:Body>'
          '</soap:Envelope>')


def mcp_text(body, status=200, ctype='application/json'):
    """A result in the shape the study's MCP servers return: status, content type and the body as text."""
    return json.dumps({'status': status, 'contentType': ctype, 'truncated': False, 'body': body})


class Session:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'results.jsonl'
        self.inner = FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}],
                                     {'lookup': lambda a: mcp_text(a['body'], ctype=a.get('ctype', 'application/json'))})
        self.wrapped = ht.HarnessToolSession(self.inner, ['calculate', 'ask_requester'], ht.ResultStore(self.path, 'ab12'), 'run-key-1')

    def fetch(self, body, **kw):
        text, error = self.wrapped.call('lookup', {'body': body, **kw})
        self.assert_line(text)
        return text.split('\n', 1)[0].split(': ', 1)[1]

    @staticmethod
    def assert_line(text):
        assert text.startswith('result_id: '), text

    def calc(self, **arguments):
        """(output, result id, error) of a calculate call shown in full; the read line goes to `self.read`, the coverage line to
        `self.coverage` (None when there is none) and the warning lines to `self.warnings`."""
        text, error = self.wrapped.call('calculate', arguments)
        self.read, self.coverage, self.warnings = None, None, []
        if error:
            return text, None, True
        line, read, body = text.split('\n', 2)
        assert read.startswith('read: '), text
        self.read = read
        return json.loads(self.notes(body)), line.split(': ', 1)[1], False

    def notes(self, body):
        """Take the coverage line and the warning lines off the start of `body`."""
        while body.startswith(('coverage: ', 'warning: ')):
            note, body = body.split('\n', 1)
            if note.startswith('coverage: '):
                self.coverage = note[len('coverage: '):]
            else:
                self.warnings.append(note[len('warning: '):])
        return body


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ht.ResultStore(Path(self.tmp.name) / 'results.jsonl', 'ab12')

    def test_ids_count_from_one_under_the_run_tag_and_every_result_is_stored(self):
        self.assertEqual(self.store.add('lookup', {'q': 1}, 'one', False), 'ab12-1')
        self.assertEqual(self.store.add('lookup', {'q': 2}, 'two', True), 'ab12-2')
        self.assertEqual(self.store.get('ab12-2'), 'two')
        lines = read_jsonl(Path(self.tmp.name) / 'results.jsonl')
        self.assertEqual([(e['resultId'], e['tool'], e['isError'], e['text']) for e in lines],
                         [('ab12-1', 'lookup', False, 'one'), ('ab12-2', 'lookup', True, 'two')])
        self.assertTrue(all(len(e['sha256']) == 64 for e in lines))
        self.assertEqual([e['shownInFull'] for e in lines], [True, True])

    def test_the_store_records_a_result_the_agent_saw_only_as_its_shape(self):
        self.store.add('lookup', {}, 'long text', False, shown_in_full=False)
        self.assertEqual(self.store.get('ab12-1'), 'long text')
        self.assertFalse(read_jsonl(Path(self.tmp.name) / 'results.jsonl')[0]['shownInFull'])

    def test_a_foreign_an_unknown_and_a_malformed_id_are_refused(self):
        self.store.add('lookup', {}, 'one', False)
        with self.assertRaisesRegex(ht.CalculationError, 'belongs to another run'):
            self.store.get('cd34-1')
        with self.assertRaisesRegex(ht.CalculationError, 'unknown in this task'):
            self.store.get('ab12-9')
        for bad in ('1', 'ab12', 'ab12-0', 'AB12-1', None, 7):
            with self.assertRaisesRegex(ht.CalculationError, 'is not a result id'):
                self.store.get(bad)

    def test_the_run_tag_depends_on_the_run_and_the_attempt(self):
        self.assertRegex(ht.run_tag('k', 1), r'^[0-9a-f]{4}$')
        self.assertEqual(ht.run_tag('k', 1), ht.run_tag('k', 1))
        self.assertNotEqual(ht.run_tag('k', 1), ht.run_tag('k', 2))
        self.assertNotEqual(ht.run_tag('k', 1), ht.run_tag('j', 1))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)

    def test_the_harness_tools_are_offered_after_the_scenario_tools(self):
        self.assertEqual([t['name'] for t in self.s.wrapped.tools()], ['lookup', 'calculate', 'ask_requester'])
        self.assertEqual(self.s.wrapped.tools()[1], ht.CALCULATE_TOOL)

    def test_a_scenario_tool_with_a_harness_name_is_refused(self):
        inner = FakeToolSession([{'name': 'calculate', 'description': 'd', 'input_schema': {}}], {})
        with self.assertRaisesRegex(ht.HarnessToolClash, 'calculate'):
            ht.HarnessToolSession(inner, ['calculate'], None, 'k').tools()

    def test_scenario_results_carry_their_id_and_are_stored_unchanged(self):
        text, error = self.s.wrapped.call('lookup', {'body': '[1]'})
        self.assertFalse(error)
        self.assertTrue(text.startswith('result_id: ab12-1\n'))
        stored = read_jsonl(self.s.path)[0]
        self.assertEqual(stored['text'], mcp_text('[1]'))
        self.assertEqual(stored['arguments'], {'body': '[1]'})
        self.assertEqual(self.s.wrapped.last_details, {'tool': 'lookup', 'resultId': 'ab12-1'})

    def test_without_calculate_no_id_is_shown_or_stored(self):
        wrapped = ht.HarnessToolSession(self.s.inner, ['ask_requester'], ht.ResultStore(self.s.path, 'ab12'), 'k')
        text, _ = wrapped.call('lookup', {'body': '[1]'})
        self.assertEqual(text, mcp_text('[1]'))
        self.assertFalse(self.s.path.exists())
        self.assertEqual([t['name'] for t in wrapped.tools()], ['lookup', 'ask_requester'])
        text, error = wrapped.call('calculate', {'operation': 'count'})
        self.assertTrue(error)  # not offered, so it goes to the scenario, which does not know it

    def test_ask_requester_always_returns_the_fixed_text_and_logs_the_question_with_the_run(self):
        for arguments in ({'question': 'Which ranks count as senior?'}, {'question': ''}, {}):
            self.assertEqual(self.s.wrapped.call('ask_requester', arguments), (ht.ASK_TEXT, False))
        self.assertEqual(ht.ASK_TEXT, 'No requester response is available during this evaluation.')
        self.assertEqual([q['question'] for q in self.s.wrapped.questions], ['Which ranks count as senior?', '', '{}'])
        self.assertTrue(all(q['runKey'] == 'run-key-1' for q in self.s.wrapped.questions))
        self.assertEqual(self.s.wrapped.counts['askRequester'], 3)
        self.assertEqual(self.s.inner.calls, [])

    def test_calculate_never_calls_the_scenario(self):
        rid = self.s.fetch(json.dumps(ROWS))
        calls = len(self.s.inner.calls)
        self.s.calc(operation='count', sources=[{'result_id': rid, 'path': 'body'}])
        self.assertEqual(len(self.s.inner.calls), calls)


LONG_PAGE = {'page': 1, 'pageSize': 60, 'totalCount': 240, 'items': [{'id': 'M%d' % i, 'status': 'ACTIVE', 'note': 'n' * 80} for i in range(60)]}


class StoredResultTests(unittest.TestCase):
    """Version 2: a scenario result longer than storeAboveChars is stored in full and the agent reads its id, size and shape."""

    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)

    def test_a_long_scenario_result_is_stored_in_full_and_shown_as_its_shape(self):
        body = json.dumps(LONG_PAGE)
        text, error = self.s.wrapped.call('lookup', {'body': body})
        self.assertFalse(error)
        full = mcp_text(body)
        self.assertGreater(len(full), ht.LIMITS['storeAboveChars'])
        self.assertTrue(text.startswith('result_id: ab12-1\nstored, not shown: %d characters.' % len(full)))
        self.assertLessEqual(len(text), ht.LIMITS['previewChars'] + 400)
        shape = json.loads(text.split('\n')[2])
        self.assertEqual(shape['body']['totalCount'], 240)
        self.assertEqual(shape['body']['items'][0]['id'], 'M0')
        self.assertEqual(shape['body']['items'][1], '... 60 elements in all')
        self.assertIn('calculate operation view', text)
        stored = read_jsonl(self.s.path)[0]
        self.assertEqual((stored['text'], stored['shownInFull']), (full, False))
        self.assertEqual(self.s.wrapped.last_details, {'tool': 'lookup', 'resultId': 'ab12-1', 'stored': True, 'storedChars': len(full),
                                                       'shownChars': len(text)})

    def test_a_result_at_the_threshold_is_shown_in_full(self):
        pad = ht.LIMITS['storeAboveChars'] - len(mcp_text(''))
        text, _ = self.s.wrapped.call('lookup', {'body': 'x' * pad})
        self.assertEqual(text, 'result_id: ab12-1\n' + mcp_text('x' * pad))
        text, _ = self.s.wrapped.call('lookup', {'body': 'x' * (pad + 1)})
        self.assertIn('stored, not shown', text)
        self.assertTrue(read_jsonl(self.s.path)[0]['shownInFull'])

    def test_calculate_reads_a_stored_result_in_full(self):
        rid = self.s.fetch(json.dumps(LONG_PAGE))
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': rid, 'path': 'body.items'}])
        self.assertEqual(out['count'], 60)

    def test_a_long_calculate_output_is_stored_and_shown_as_its_read_line_and_shape(self):
        """Version 3: a calculate output over storeAboveChars is stored in full, like a long scenario result."""
        rid = self.s.fetch(json.dumps(LONG_PAGE))
        text, error = self.s.wrapped.call('calculate', {'operation': 'sort', 'sources': [{'result_id': rid, 'path': 'body.items'}], 'field': 'id'})
        self.assertFalse(error)
        lines = text.split('\n')
        self.assertEqual(lines[0], 'result_id: ab12-2')
        self.assertEqual(lines[1], 'read: ab12-1 at "body.items": 60 records')
        stored = read_jsonl(self.s.path)[-1]
        self.assertEqual(lines[2], 'coverage: built from 60 of totalCount 240 at "items" (180 not among the sources)')
        self.assertTrue(lines[3].startswith('stored, not shown: %d characters.' % len(stored['text'])))
        self.assertGreater(len(stored['text']), ht.LIMITS['storeAboveChars'])
        self.assertLessEqual(len(text), ht.LIMITS['previewChars'] + 500 + len(lines[2]))
        shape = json.loads(lines[4])
        self.assertEqual((shape['count'], shape['records'][0]['id'], shape['records'][1]), (60, 'M0', '... 60 elements in all'))
        self.assertEqual((stored['shownInFull'], stored['readLine'], stored['coverageLine']), (False, lines[1], lines[2][len('coverage: '):]))
        self.assertEqual(len(json.loads(stored['text'])['records']), 60)  # stored whole
        details = self.s.wrapped.last_details
        self.assertEqual((details['stored'], details['storedChars'], details['shownChars']), (True, len(stored['text']), len(text)))
        self.assertEqual(details['read'], [{'resultId': 'ab12-1', 'path': 'body.items', 'records': 60, 'matchedNothing': False, 'missing': 0}])

    def test_a_stored_calculate_output_is_a_source_read_in_full(self):
        rid = self.s.fetch(json.dumps(LONG_PAGE))
        _, error = self.s.wrapped.call('calculate', {'operation': 'sort', 'sources': [{'result_id': rid, 'path': 'body.items'}], 'field': 'id'})
        self.assertFalse(error)
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': 'ab12-2', 'path': 'records'}])
        self.assertEqual(out['count'], 60)
        self.assertEqual(self.s.read, 'read: ab12-2 at "records": 60 records')

    def test_a_stored_calculate_output_is_read_page_by_page_and_never_only_as_its_shape(self):
        """Every page of a view is shown in full within viewPageChars, never stored, and nextOffset leads to the next page until the end."""
        rid = self.s.fetch(json.dumps(LONG_PAGE))
        self.s.wrapped.call('calculate', {'operation': 'sort', 'sources': [{'result_id': rid, 'path': 'body.items'}], 'field': 'id'})
        seen, offset, pages = [], 0, 0
        while offset is not None:
            text, error = self.s.wrapped.call('calculate', {'operation': 'view', 'sources': [{'result_id': 'ab12-2', 'path': 'records'}],
                                                            'offset': offset})
            self.assertFalse(error)
            self.assertNotIn('stored, not shown', text)
            body = self.s.notes(text.split('\n', 2)[2])  # the page stands below its coverage line and keeps version 4's size
            self.assertLessEqual(len(body), ht.LIMITS['viewPageChars'])
            out = json.loads(body)
            self.assertEqual((out['offset'], out['count']), (offset, 60))
            seen += [r['id'] for r in out['records']]
            self.assertTrue(read_jsonl(self.s.path)[-1]['shownInFull'])
            offset, pages = out.get('nextOffset'), pages + 1
        self.assertEqual(seen, sorted('M%d' % i for i in range(60)))  # every record once, in the sort's (text) order
        self.assertGreater(pages, 1)

    def test_the_stored_calculate_output_is_the_same_in_every_arm(self):
        shown = []
        for key, tag in (('beta__V05__m__t1', 'aa11'), ('epsilon__V05__m__t1', 'aa11')):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            inner = FakeToolSession([{'name': 'q', 'description': 'd', 'input_schema': {'type': 'object'}}], {'q': lambda a: mcp_text(json.dumps(LONG_PAGE))})
            wrapped = ht.HarnessToolSession(inner, ['calculate', 'ask_requester'], ht.ResultStore(Path(tmp.name) / 'r.jsonl', tag), key)
            wrapped.call('q', {})
            shown.append(wrapped.call('calculate', {'operation': 'filter', 'sources': [{'result_id': 'aa11-1', 'path': 'body.items'}],
                                                    'conditions': [{'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}]})[0])
        self.assertEqual(shown[0], shown[1])
        self.assertIn('stored, not shown', shown[0])

    def test_an_xml_result_shows_its_shape_with_local_names(self):
        people = ''.join('<p:person rank="Lt"><p:id>P%d</p:id><p:name>%s</p:name></p:person>' % (i, 'n' * 60) for i in range(80))
        envelope = SOAP.split('<p:listResponse')[0] + '<p:listResponse xmlns:p="urn:example">' + people + '</p:listResponse></soap:Body></soap:Envelope>'
        text, _ = self.s.wrapped.call('lookup', {'body': envelope, 'ctype': 'text/xml'})
        shape = json.loads(text.split('\n')[2])
        first = shape['body']['Envelope']['Body']['listResponse']['person']
        self.assertEqual(first[0], {'@rank': 'Lt', 'id': 'P0', 'name': 'n' * 60})
        self.assertEqual(first[1], '... 80 elements in all')

    def test_the_shape_cuts_objects_texts_and_depth_and_stays_within_its_limit(self):
        many_keys = {'k%03d' % i: i for i in range(50)}
        self.assertEqual(len(ht.shape(many_keys)), ht.LIMITS['previewKeys'] + 1)
        self.assertEqual(ht.shape(many_keys)['...'], '50 keys in all')
        self.assertEqual(ht.shape('t' * 500), 't' * ht.LIMITS['previewTextChars'] + '... (500 characters)')
        self.assertEqual(ht.shape([]), [])
        self.assertEqual(ht.shape([7]), [7])
        deep = {'a': {'b': {'c': [{'d': 'x' * 2000, 'e': {'f%d' % i: 'y' * 100 for i in range(30)}}] * 3}}}
        self.assertLessEqual(len(ht.preview(json.dumps(deep))), ht.LIMITS['previewChars'] + 3)
        self.assertEqual(ht.preview(json.dumps(deep)), ht.preview(json.dumps(deep)))
        self.assertEqual(ht.shape('{"a": [1, 2]}'), {'a': [1, '... 2 elements in all']})
        self.assertEqual(ht.shape('<!DOCTYPE x><x/>'), '<!DOCTYPE x><x/>')  # a text calculate refuses to read stays a text

    def test_the_stored_rule_is_the_same_in_every_arm(self):
        """The tools and the rule depend on nothing but the result: two sessions of different arms and runs show the same text for it."""
        shown = []
        for key, tag in (('beta__V05__m__t1', 'aa11'), ('epsilon__V05__m__t1', 'bb22')):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            inner = FakeToolSession([{'name': 'q', 'description': 'd', 'input_schema': {'type': 'object'}}], {'q': lambda a: mcp_text(json.dumps(LONG_PAGE))})
            wrapped = ht.HarnessToolSession(inner, ['calculate', 'ask_requester'], ht.ResultStore(Path(tmp.name) / 'r.jsonl', tag), key)
            self.assertEqual(wrapped.tools()[1:], [ht.CALCULATE_TOOL, ht.ASK_REQUESTER_TOOL])
            shown.append(wrapped.call('q', {})[0].split('\n', 1)[1])
        self.assertEqual(shown[0], shown[1])

    def test_the_tool_description_states_the_threshold_of_the_limits(self):
        self.assertIn('longer than %d characters' % ht.LIMITS['storeAboveChars'], ht.CALCULATE_TOOL['description'])
        self.assertIn('view', ht.CALCULATE_TOOL['input_schema']['properties']['operation']['enum'])

    def test_without_calculate_a_long_result_is_shown_in_full(self):
        wrapped = ht.HarnessToolSession(self.s.inner, ['ask_requester'], ht.ResultStore(self.s.path, 'ab12'), 'k')
        text, _ = wrapped.call('lookup', {'body': json.dumps(LONG_PAGE)})
        self.assertEqual(text, mcp_text(json.dumps(LONG_PAGE)))


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)
        self.page = self.s.fetch(json.dumps(LONG_PAGE))

    def view(self, path, **kw):
        return self.s.calc(operation='view', sources=[{'result_id': self.page, 'path': path}], **kw)

    def test_view_pages_through_a_list_with_offset_limit_and_fields(self):
        out, rid, error = self.view('body.items', offset=58, limit=5, fields=['id'])
        self.assertFalse(error)
        self.assertEqual(out, {'operation': 'view', 'offset': 58, 'count': 60, 'records': [{'id': 'M58'}, {'id': 'M59'}]})
        self.assertEqual(self.s.wrapped.last_details['resultIds'], [self.page])
        self.assertEqual(rid, 'ab12-2')

    def test_view_of_a_spread_path_lists_its_elements(self):
        out, _, _ = self.view('body.items.*.id', limit=3)
        self.assertEqual(out['records'], ['M0', 'M1', 'M2'])
        self.assertEqual((out['count'], out['nextOffset']), (60, 3))
        self.assertEqual(self.s.read, 'read: ab12-1 at "body.items.*.id": 60 records')

    def test_view_pages_through_the_keys_of_an_object(self):
        out, _, _ = self.view('body', offset=1, limit=2)
        self.assertEqual(out, {'operation': 'view', 'offset': 1, 'keyCount': 4, 'value': {'pageSize': 60, 'totalCount': 240}, 'nextOffset': 3})
        self.assertEqual(self.s.read, 'read: ab12-1 at "body": an object of 4 keys')

    def test_view_of_a_text_gives_its_characters_and_of_a_value_the_value(self):
        out, _, _ = self.view('body.items.3.note', offset=75, limit=10)
        self.assertEqual(out, {'operation': 'view', 'offset': 75, 'length': 80, 'text': 'nnnnn'})
        out, _, _ = self.view('body.totalCount')
        self.assertEqual(out, {'operation': 'view', 'value': 240})
        self.assertEqual(self.s.read, 'read: ab12-1 at "body.totalCount": one value')
        out, _, _ = self.view('')
        self.assertEqual(out['keyCount'], 4)  # the whole result: status, contentType, truncated, body
        self.assertEqual(self.s.read, 'read: ab12-1 at the whole result: an object of 4 keys')

    def test_a_long_view_ends_its_page_within_the_page_limit_and_names_the_next_offset(self):
        """Version 3: a page is at most viewPageChars characters, whatever limit asked for; nextOffset names where the next one starts."""
        big = self.s.fetch(json.dumps({'k%04d' % i: 'v' * 100 for i in range(1500)}))
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': big, 'path': 'body'}])
        self.assertEqual(out['keyCount'], 1500)
        self.assertLess(len(out['value']), 1500)
        self.assertEqual(out['nextOffset'], len(out['value']))
        self.assertLessEqual(len(ht.render(out)), ht.LIMITS['viewPageChars'])
        text = self.s.fetch(json.dumps({'t': 'w' * 120_000}))
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': text, 'path': 'body.t'}], offset=10)
        self.assertEqual(out['length'], 120_000)
        self.assertEqual(out['nextOffset'], 10 + len(out['text']))
        self.assertLessEqual(len(ht.render(out)), ht.LIMITS['viewPageChars'])
        self.assertGreater(len(out['text']), ht.LIMITS['viewPageChars'] - 200)  # the page is filled, not halved
        out, _, _ = self.view('body.items', limit=40)
        self.assertLess(len(out['records']), 40)
        self.assertEqual(out['nextOffset'], len(out['records']))
        out, _, _ = self.view('body.items', offset=59)
        self.assertEqual((len(out['records']), 'nextOffset' in out), (1, False))  # the last page names no next offset
        out, _, _ = self.view('body.items', offset=90)
        self.assertEqual((out['records'], 'nextOffset' in out), ([], False))

    def test_a_view_of_an_object_with_one_long_member_stays_within_the_page(self):
        """A single record or key longer than a page is shown as its shape, named in shapeOnly; a deeper path reads it."""
        long = 'p' * 60_000
        for body, path in (({'payload': long}, 'body'), ({'a': {'b': {'c': long}}}, 'body'), ({'a': {'b': {'c': long}}}, 'body.a'),
                           ({'x': long, 'y': long}, 'body'), ({'items': [{'note': long}]}, 'body'), ({'items': [{'note': long}]}, 'body.items')):
            rid = self.s.fetch(json.dumps(body))
            text, error = self.s.wrapped.call('calculate', {'operation': 'view', 'sources': [{'result_id': rid, 'path': path}]})
            self.assertFalse(error, body)
            self.assertNotIn('stored, not shown', text)
            self.assertLessEqual(len(text.split('\n', 2)[2]), ht.LIMITS['viewPageChars'], (body, path))
            self.assertNotIn(long, text)
        rid = self.s.fetch(json.dumps({'payload': long}))
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': rid, 'path': 'body'}])
        self.assertEqual(out['shapeOnly'], ['value'])
        self.assertEqual(out['value'], {'payload': 'p' * ht.LIMITS['previewTextChars'] + '... (60000 characters)'})
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': rid, 'path': 'body.payload'}], offset=100, limit=5)
        self.assertEqual(out['text'], 'ppppp')  # the long member is still readable piece by piece
        rid = self.s.fetch(json.dumps({'x': long, 'y': 1}))
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': rid, 'path': 'body'}])
        self.assertEqual((list(out['value']), out['shapeOnly'], out['nextOffset']), (['x'], ['value'], 1))

    def test_a_key_longer_than_a_page_is_shown_by_its_start_and_length_within_the_page(self):
        for key in ('k' * 6000, '{"a": [' + '1, ' * 3000 + '1]}'):  # a long key, and one that looks like JSON
            rid = self.s.fetch(json.dumps({key: 1, 'b': 2}))
            text, error = self.s.wrapped.call('calculate', {'operation': 'view', 'sources': [{'result_id': rid, 'path': 'body'}]})
            self.assertFalse(error)
            self.assertNotIn('stored, not shown', text)
            body = text.split('\n', 2)[2]
            self.assertLessEqual(len(body), ht.LIMITS['viewPageChars'])
            out = json.loads(body)
            self.assertEqual((out['shapeOnly'], out['nextOffset'], out['keyCount']), (['value'], 1, 2))
            self.assertEqual(list(out['value']), [key[:ht.LIMITS['previewTextChars']] + '... (%d characters)' % len(key)])

    def test_the_page_is_sized_with_every_key_it_carries(self):
        """missing and nextOffset are counted when the page is sized, so a full page is never pushed past the limit and stored."""
        rid = self.s.fetch(json.dumps([{'v': 'x'} for _ in range(3000)] + [{}]))
        offset, seen = 0, 0
        while offset is not None:
            text, error = self.s.wrapped.call('calculate', {'operation': 'view', 'sources': [{'result_id': rid, 'path': 'body.*.v'}],
                                                            'offset': offset})
            self.assertFalse(error)
            self.assertNotIn('stored, not shown', text)
            body = text.split('\n', 2)[2]
            self.assertLessEqual(len(body), ht.LIMITS['viewPageChars'])
            out = json.loads(body)
            self.assertEqual(out['missing'], 1)
            seen += len(out['records'])
            offset = out.get('nextOffset')
        self.assertEqual(seen, 3000)

    def test_render_never_passes_its_limit(self):
        long = 'q' * 70_000
        for output in ({'operation': 'view', 'value': {'k': long}}, {'operation': 'view', 'value': {'a': [{'b': {'c': long}}]}},
                       {'operation': 'view', 'value': long}, {'operation': 'sort', 'records': [{'n': long}]},
                       {'operation': 'view', 'value': {'k': long}, 'other': {'k': long}}):
            self.assertLessEqual(len(ht.render(output, 50_000)), 50_000, output.keys())
            self.assertEqual(json.loads(ht.render(output)), output)  # under maxStoredOutputChars nothing is cut
        self.assertEqual(ht.render({'operation': 'count', 'count': 3}), '{"count": 3, "operation": "count"}')  # short: unchanged
        self.assertEqual(ht.LIMITS['maxStoredOutputChars'], ht.LIMITS['maxSourceChars'])  # a stored output stays readable as a source

    def test_view_refuses_other_shapes_of_its_arguments(self):
        for arguments, message in (({'sources': []}, 'exactly one source'),
                                   ({'sources': [{'result_id': self.page}, {'result_id': self.page}]}, 'exactly one source'),
                                   ({'sources': [{'path': 'body'}]}, 'needs a result_id'),
                                   ({'sources': [{'result_id': self.page}], 'offset': -1}, 'offset is a whole number'),
                                   ({'sources': [{'result_id': self.page}], 'offset': '2'}, 'offset is a whole number'),
                                   ({'sources': [{'result_id': self.page}], 'limit': 0}, 'limit is a whole number'),
                                   ({'sources': [{'result_id': 'ff00-1'}]}, 'belongs to another run'),
                                   ({'sources': [{'result_id': self.page, 'path': 'body.nothing'}]}, 'has no key')):
            text, _, error = self.s.calc(operation='view', **arguments)
            self.assertTrue(error, arguments)
            self.assertIn(message, text)
        self.assertEqual(self.s.wrapped.counts['calculateErrors'], 8)


class CalculateTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)
        self.rows = self.s.fetch(json.dumps({'data': {'missions': {'items': ROWS}}}))

    def src(self, path='body.data.missions.items', rid=None):
        return [{'result_id': rid or self.rows, 'path': path}]

    def test_count_over_a_json_body_inside_the_result(self):
        out, rid, error = self.s.calc(operation='count', sources=self.src())
        self.assertFalse(error)
        self.assertEqual(out, {'operation': 'count', 'count': 4})
        self.assertEqual(rid, 'ab12-2')

    def test_count_over_several_pages(self):
        second = self.s.fetch(json.dumps({'data': {'missions': {'items': ROWS[:2]}}}))
        out, _, _ = self.s.calc(operation='count', sources=self.src() + self.src(rid=second))
        self.assertEqual(out['count'], 6)

    def test_distinct(self):
        out, _, _ = self.s.calc(operation='distinct', sources=self.src(), field='status')
        self.assertEqual(out, {'operation': 'distinct', 'count': 3, 'values': ['ACTIVE', 'CLOSED', 'PLANNED']})

    def test_group_by_with_count_and_with_sum(self):
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(), group_by=['status'])
        self.assertEqual(out['groups'], [{'key': {'status': 'ACTIVE'}, 'count': 2}, {'key': {'status': 'CLOSED'}, 'count': 1},
                                         {'key': {'status': 'PLANNED'}, 'count': 1}])
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(), group_by=['status'], aggregate='sum', sum_field='cost', round=2)
        self.assertEqual([(g['key']['status'], g['sum']) for g in out['groups']], [('ACTIVE', 11.75), ('CLOSED', 4.25), ('PLANNED', 0)])
        self.assertEqual(out['notNumeric'], 1)

    def test_sort_with_fields_and_limit(self):
        out, _, _ = self.s.calc(operation='sort', sources=self.src(), field='crew', descending=True, fields=['id', 'crew'], limit=2)
        self.assertEqual(out, {'operation': 'sort', 'count': 4, 'records': [{'id': 'M3', 'crew': 7}, {'id': 'M1', 'crew': 4}]})

    def test_filter_by_literal_comparisons_all_holding(self):
        out, _, _ = self.s.calc(operation='filter', sources=self.src(), fields=['id'],
                                conditions=[{'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}, {'field': 'crew', 'op': 'ge', 'value': 5}])
        self.assertEqual(out['records'], [{'id': 'M3'}])
        out, _, _ = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'cost', 'op': 'lt', 'value': 5}], fields=['id'])
        self.assertEqual(out['records'], [{'id': 'M2'}, {'id': 'M3'}])
        out, _, _ = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'cost', 'op': 'eq', 'value': None}], fields=['id'])
        self.assertEqual(out['records'], [{'id': 'M4'}])

    def test_set_operations_on_the_values_of_each_source(self):
        other = self.s.fetch(json.dumps([{'mission': 'M2'}, {'mission': 'M4'}, {'mission': 'M9'}]))
        a = {'result_id': self.rows, 'path': 'body.data.missions.items.*.id'}
        b = {'result_id': other, 'path': 'body.*.mission'}
        out, _, _ = self.s.calc(operation='union', sources=[a, b])
        self.assertEqual(out['values'], ['M1', 'M2', 'M3', 'M4', 'M9'])
        out, _, _ = self.s.calc(operation='intersection', sources=[a, b])
        self.assertEqual(out['values'], ['M2', 'M4'])
        out, _, _ = self.s.calc(operation='difference', sources=[a, b])
        self.assertEqual(out, {'operation': 'difference', 'count': 2, 'values': ['M1', 'M3']})

    def test_arithmetic_over_numbers_and_earlier_results(self):
        _, active, _ = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}])
        _, total, _ = self.s.calc(operation='count', sources=self.src())
        out, _, _ = self.s.calc(operation='arithmetic', operator='divide', round=1,
                                operands=[{'result_id': active, 'path': 'count'}, {'result_id': total, 'path': 'count'}])
        self.assertEqual(out, {'operation': 'arithmetic', 'value': 0.5})
        out, _, _ = self.s.calc(operation='arithmetic', operator='multiply', operands=[0.5, 100])
        self.assertEqual(out['value'], 50)
        text, _, error = self.s.calc(operation='arithmetic', operator='divide', operands=[1, 0])
        self.assertTrue(error)
        self.assertIn('division by zero', text)

    def test_a_numeric_failure_is_a_logged_tool_error_and_never_escapes(self):
        for arguments in ({'operation': 'arithmetic', 'operator': 'multiply', 'operands': [1e20, 1e20], 'round': 2},
                          {'operation': 'arithmetic', 'operator': 'multiply', 'operands': [1e300, 1e300, 1e300], 'round': 12},
                          {'operation': 'group_by', 'sources': self.src(), 'group_by': ['status'], 'aggregate': 'sum', 'sum_field': 'crew',
                           'round': 12}):
            self.s.calc(**arguments)  # returns a result or a tool error; nothing is raised
        text, _, error = self.s.calc(operation='arithmetic', operator='multiply', operands=[1e20, 1e20], round=2)
        self.assertTrue(error)
        self.assertIn('too many digits', text)
        self.assertEqual(self.s.wrapped.last_details['error'], text.split(': ', 1)[1])

    def test_a_calculate_result_can_be_the_source_of_another(self):
        _, filtered, _ = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'crew', 'op': 'eq', 'value': 2}])
        out, _, _ = self.s.calc(operation='distinct', sources=[{'result_id': filtered, 'path': 'records'}], field='status')
        self.assertEqual(out['values'], ['CLOSED', 'PLANNED'])

    def test_xml_is_read_generically_with_local_names_attributes_and_lists(self):
        rid = self.s.fetch(SOAP, ctype='text/xml')
        people = 'body.Envelope.Body.listResponse.person'
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': rid, 'path': people}])
        self.assertEqual(out['count'], 3)
        out, _, _ = self.s.calc(operation='filter', sources=[{'result_id': rid, 'path': people}], fields=['id'],
                                conditions=[{'field': '@rank', 'op': 'eq', 'value': 'Lt'}, {'field': 'age', 'op': 'gt', 'value': 28}])
        self.assertEqual(out['records'], [{'id': 'P1'}])
        out, _, _ = self.s.calc(operation='group_by', sources=[{'result_id': rid, 'path': people}], group_by=['@rank'], aggregate='sum',
                                sum_field='age')
        self.assertEqual([(g['key']['@rank'], g['count'], g['sum']) for g in out['groups']], [('Cdr', 1, 41), ('Lt', 2, 57)])

    def test_a_single_xml_element_counts_as_one_record(self):
        rid = self.s.fetch(SINGLE, ctype='text/xml')
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': rid, 'path': 'body.Envelope.Body.r.person.*'}])
        self.assertEqual(out['count'], 1)

    def test_elements_without_the_step_after_a_star_are_left_out_and_counted(self):
        out, _, _ = self.s.calc(operation='count', sources=self.src('body.data.missions.items.*.tags.*'))
        self.assertEqual(out, {'operation': 'count', 'count': 1, 'missing': 2})

    def test_a_foreign_or_unknown_id_is_a_logged_tool_error(self):
        for rid, message in (('ff00-1', 'belongs to another run'), ('ab12-99', 'unknown in this task'), ('M1', 'is not a result id')):
            text, _, error = self.s.calc(operation='count', sources=[{'result_id': rid}])
            self.assertTrue(error)
            self.assertIn(message, text)
            self.assertEqual(self.s.wrapped.last_details['error'], text.split(': ', 1)[1])
            self.assertEqual(self.s.wrapped.last_details['resultIds'], [rid])
        self.assertEqual(self.s.wrapped.counts, {'calculate': 3, 'calculateErrors': 3, 'askRequester': 0})

    def test_operations_that_are_not_on_the_list_are_refused(self):
        for operation in ('fetch', 'http', 'read_file', 'sql', 'eval', 'lookup', 'COUNT', None):
            text, _, error = self.s.calc(operation=operation, sources=self.src())
            self.assertTrue(error, operation)
            self.assertIn('unknown operation', text)
        text, _, error = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'crew', 'op': 'regex', 'value': '.*'}])
        self.assertTrue(error)
        text, _, error = self.s.calc(operation='arithmetic', operator='power', operands=[2, 3])
        self.assertTrue(error)
        text, _, error = self.s.calc(operation='filter', sources=self.src(), conditions=[{'field': 'crew', 'op': 'lt', 'value': True}])
        self.assertTrue(error)

    def test_malformed_arguments_from_the_model_are_logged_tool_errors(self):
        for arguments in ({'operation': 'count', 'sources': 1}, {'operation': 'count', 'sources': True}, {'operation': 'count', 'sources': 'ab12-1'},
                          {'operation': 'count', 'sources': [7]}, {'operation': 'count', 'sources': [{'result_id': ['ab12-1']}]},
                          {'operation': 'arithmetic', 'operator': 'add', 'operands': 5}, {'operation': 'arithmetic', 'operator': 'add', 'operands': [1, 'x']},
                          {'operation': 'sort', 'sources': self.src(), 'field': 'crew', 'fields': 5},
                          {'operation': 'sort', 'sources': self.src(), 'field': 'crew', 'limit': 'two'},
                          {'operation': 'filter', 'sources': self.src(), 'conditions': [{'field': 3, 'op': 'eq', 'value': 1}]},
                          {'operation': 'count', 'sources': [{'result_id': self.rows, 'path': 5}]},
                          {'operation': 'distinct', 'sources': self.src(), 'field': {'a': 1}},
                          {'operation': 'group_by', 'sources': self.src(), 'group_by': [['status']]},
                          {'operation': 'group_by', 'sources': self.src(), 'group_by': ['status'], 'aggregate': 'sum', 'sum_field': 'cost',
                           'round': 'two'}):
            text, error = self.s.wrapped.call('calculate', arguments)  # never raises
            self.assertIsInstance(text, str)
            self.assertNotIn('the calculation failed', text)  # version 5 names the argument and the form it takes
        text, error = self.s.wrapped.call('calculate', {'operation': 'count', 'sources': 1})
        self.assertTrue(error)
        self.assertEqual(self.s.wrapped.last_details['resultIds'], [])
        text, error = self.s.wrapped.call('calculate', 'not an object')
        self.assertTrue(error)

    def test_bad_paths_and_missing_sources_are_refused(self):
        for arguments, message in (({'operation': 'count', 'sources': self.src('body.data.nothing')}, 'has no key'),
                                   ({'operation': 'count', 'sources': self.src('body.data.missions.items.9')}, 'has no position'),
                                   ({'operation': 'count'}, 'at least 1 source'),
                                   ({'operation': 'union', 'sources': self.src()}, 'at least 2 sources'),
                                   ({'operation': 'group_by', 'sources': self.src()}, 'group_by needs')):
            text, _, error = self.s.calc(**arguments)
            self.assertTrue(error, arguments)
            self.assertIn(message, text)

    def test_xml_with_a_document_type_is_not_read(self):
        rid = self.s.fetch('<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>', ctype='text/xml')
        text, _, error = self.s.calc(operation='count', sources=[{'result_id': rid, 'path': 'body.x'}])
        self.assertTrue(error)
        self.assertIn('document type', text)

    def test_a_long_output_is_stored_whole_and_not_cut(self):
        many = self.s.fetch(json.dumps([{'n': i, 'pad': 'x' * 100} for i in range(2000)]))
        text, error = self.s.wrapped.call('calculate', {'operation': 'sort', 'sources': [{'result_id': many, 'path': 'body'}], 'field': 'n'})
        self.assertFalse(error)
        self.assertIn('stored, not shown', text)
        stored = json.loads(read_jsonl(self.s.path)[-1]['text'])
        self.assertEqual((stored['count'], len(stored['records']), 'truncated' in stored), (2000, 2000, False))

    def test_the_read_line_names_each_source_its_path_and_records_and_never_sums_them(self):
        second = self.s.fetch(json.dumps({'data': {'missions': {'items': ROWS[:2]}}}))
        empty = self.s.fetch(json.dumps({'data': {'missions': {'items': []}}}))
        out, _, _ = self.s.calc(operation='count', sources=self.src() + self.src(rid=second) + self.src(rid=self.rows))
        self.assertEqual(out['count'], 10)
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items": 4 records; %s at "body.data.missions.items": 2 records; '
                                      '%s at "body.data.missions.items": 4 records' % (self.rows, second, self.rows))
        self.assertNotIn('10', self.s.read)  # the sources are listed, never added up
        out, _, _ = self.s.calc(operation='union', sources=[{'result_id': self.rows, 'path': 'body.data.missions.items.*.id'},
                                                            {'result_id': empty, 'path': 'body.data.missions.items.*.id'}])
        self.assertEqual(out['count'], 4)
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items.*.id": 4 records; %s at "body.data.missions.items.*.id": 0 records '
                                      '(the path matched nothing)' % (self.rows, empty))
        self.s.calc(operation='count', sources=self.src(rid=empty))
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items": 0 records' % empty)  # an empty list is found, not unmatched
        self.s.calc(operation='count', sources=self.src('body.data.missions.items.*.tags.*'))
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items.*.tags.*": 1 record (2 elements lacked "tags" and were left out)'
                         % self.rows)
        self.s.calc(operation='count', sources=[{'result_id': self.rows}])
        self.assertEqual(self.s.read, 'read: %s at the whole result: 1 record' % self.rows)

    def test_the_read_line_of_arithmetic_names_its_results_and_stays_one_line(self):
        _, total, _ = self.s.calc(operation='count', sources=self.src())
        self.s.calc(operation='arithmetic', operator='add', operands=[{'result_id': total, 'path': 'count'}, 1])
        self.assertEqual(self.s.read, 'read: %s at "count": one number' % total)
        self.s.calc(operation='arithmetic', operator='add', operands=[2, 1])
        self.assertEqual(self.s.read, 'read: no result (numbers only)')
        text, error = self.s.wrapped.call('calculate', {'operation': 'count', 'sources': [{'result_id': self.rows, 'path': 'body\n.data'}]})
        self.assertTrue(error)
        self.assertNotIn('read: ', text)  # a refusal read nothing, so it has no read line
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': total, 'path': ' count '}])
        self.assertEqual(len(self.s.read.splitlines()), 1)

    def test_every_call_is_logged_with_ids_operation_bytes_and_tokens(self):
        out, rid, _ = self.s.calc(operation='count', sources=self.src())
        details = self.s.wrapped.last_details
        self.assertEqual((details['tool'], details['operation'], details['resultIds'], details['resultId']), ('calculate', 'count', [self.rows], rid))
        self.assertGreater(details['inputBytes'], 0)
        self.assertGreater(details['outputBytes'], 0)
        self.assertGreater(details['addedTokensEstimate'], 0)
        self.assertIsNone(details['error'])
        self.assertEqual(read_jsonl(self.s.path)[-1]['resultId'], rid)

    def test_describe_records_the_tools_text_and_limits(self):
        described = ht.describe(['ask_requester', 'calculate'])
        self.assertEqual(described['names'], ['calculate', 'ask_requester'])
        self.assertEqual(described['askRequesterText'], ht.ASK_TEXT)
        self.assertEqual(described['operations'], list(ht.OPERATIONS))
        self.assertEqual((described['version'], described['limits']['storeAboveChars'], described['storedResults']), (5, 5000, ht.STORED_RULE))
        self.assertEqual((described['refusals'], described['coverageLine'], described['warningLines']),
                         (ht.STRICT_RULE, ht.COVERAGE_RULE, ht.WARNING_RULE))
        self.assertEqual([described['limits'][name] for name in ('coverageLineChars', 'warningChars', 'maxWarnings', 'refusalChars',
                                                                 'repeatMinRecords')], [600, 300, 2, 1500, 10])
        self.assertEqual((described['limits']['viewPageChars'], described['readLine']), (5000, ht.READ_RULE))
        self.assertEqual(described['conditionElements'], ht.ELEMENTS_RULE)
        self.assertNotIn('maxOutputChars', described['limits'])
        description = ht.CALCULATE_TOOL['description']
        for words in ('a calculate result included', 'read:', 'does not add the sources up', 'at most 5000', 'nextOffset', 'elements any',
                      'elements none', 'an empty list or a missing field has no values', 'a field with a * segment needs elements any or none',
                      'an empty list gives one group over all records', 'is written in brackets: [a.b]', 'with every problem named at once',
                      'names fields that some records lack', 'records short of totalCount', 'coverage:', 'warning:'):
            self.assertIn(words, description)
        with self.assertRaisesRegex(ValueError, 'harness_tools'):
            ht.validate(['calculate', 'fetch'])
        with self.assertRaisesRegex(ValueError, 'harness_tools'):
            ht.validate(['calculate', 'calculate'])


def _held(status):
    return {'asset': {'status': status}}


# N1 has 50 elements, the two that are not ACTIVE at positions 24 and 27; N5's first element lacks the rest of the field
NESTED = [{'id': 'N1', 'assets': [_held('DESTROYED' if i == 24 else 'MISSING' if i == 27 else 'ACTIVE') for i in range(50)]},
          {'id': 'N2', 'assets': [_held('ACTIVE'), _held('ACTIVE')]},
          {'id': 'N3', 'assets': []},
          {'id': 'N4'},
          {'id': 'N5', 'assets': [{'note': 'no asset'}, _held('MISSING')]}]
LEGS = [{'id': 'L1', 'legs': [{'assets': [{'status': 'ACTIVE', 'crew': 1}]}, {'assets': [{'status': 'DESTROYED', 'crew': 3}]}]},
        {'id': 'L2', 'legs': [{'assets': [{'status': 'ACTIVE', 'crew': 2}]}, {'assets': []}]},
        {'id': 'L3', 'legs': []}]


class FilterElementsTests(unittest.TestCase):
    """Version 4: a filter condition with elements any or none tests the values at a list path. Version 5 keeps it, and refuses a field
    that no record has and a list compared with one value."""

    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)
        self.nested = self.s.fetch(json.dumps({'data': {'missions': {'items': NESTED}}}))
        self.legs = self.s.fetch(json.dumps({'data': {'missions': {'items': LEGS}}}))
        self.rows = self.s.fetch(json.dumps({'data': {'missions': {'items': ROWS}}}))

    def ids(self, rid, *conditions):
        out, _, error = self.s.calc(operation='filter', sources=[{'result_id': rid, 'path': 'body.data.missions.items'}], fields=['id'],
                                    conditions=list(conditions))
        self.assertFalse(error, out)
        return [r['id'] for r in out['records']]

    def test_any_holds_when_an_element_at_any_position_satisfies_the_comparison(self):
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'}), ['N1', 'N5'])
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'eq', 'value': 'DESTROYED'}), ['N1'])
        fixed = [{'field': 'assets.%d.asset.status' % i, 'op': 'eq', 'value': 'ACTIVE'} for i in range(4)]
        self.assertIn('N1', self.ids(self.nested, *fixed))  # fixed positions 0 to 3 cannot see positions 24 and 27

    def test_none_is_the_negation_and_holds_for_an_empty_list_and_a_missing_field(self):
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'none', 'op': 'ne', 'value': 'ACTIVE'}),
                         ['N2', 'N3', 'N4'])
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'eq', 'value': 'ACTIVE'}), ['N1', 'N2'])
        for elements in ('any', 'none'):  # version 4 read a field no record has as no values; version 5 refuses it
            text, _, error = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}],
                                         conditions=[{'field': 'nothing.*.here', 'elements': elements, 'op': 'ne', 'value': 'x'}])
            self.assertTrue(error)
            self.assertIn('no record has the field "nothing.*.here" (0 of 5 records)', text)

    def test_an_element_that_lacks_the_rest_of_the_field_is_left_out_and_never_read_as_null(self):
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'eq', 'value': None}), [])
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'none', 'op': 'eq', 'value': 'MISSING'}),
                         ['N2', 'N3', 'N4'])

    def test_nested_lists_and_numeric_comparisons(self):
        self.assertEqual(self.ids(self.legs, {'field': 'legs.*.assets.*.status', 'elements': 'any', 'op': 'eq', 'value': 'DESTROYED'}), ['L1'])
        self.assertEqual(self.ids(self.legs, {'field': 'legs.*.assets.*.crew', 'elements': 'any', 'op': 'ge', 'value': 2}), ['L1', 'L2'])
        self.assertEqual(self.ids(self.legs, {'field': 'legs.*.assets', 'elements': 'none', 'op': 'ne', 'value': 'x'}), ['L3'])

    def test_a_list_at_the_end_of_the_field_gives_its_elements(self):
        self.assertEqual(self.ids(self.rows, {'field': 'tags', 'elements': 'any', 'op': 'eq', 'value': 'x'}), ['M1'])
        self.assertEqual(self.ids(self.rows, {'field': 'tags.*', 'elements': 'any', 'op': 'eq', 'value': 'x'}), ['M1'])
        self.assertEqual(self.ids(self.rows, {'field': 'tags', 'elements': 'none', 'op': 'eq', 'value': 'x'}), ['M2', 'M3', 'M4'])
        self.assertEqual(self.ids(self.rows, {'field': 'status', 'elements': 'any', 'op': 'eq', 'value': 'ACTIVE'}), ['M1', 'M3'])

    def test_every_condition_must_hold_with_elements_beside_plain_ones(self):
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'},
                                  {'field': 'id', 'op': 'ne', 'value': 'N1'}), ['N5'])

    def test_an_ordinary_scalar_condition_without_elements_is_unchanged(self):
        self.assertEqual(self.ids(self.nested, {'field': 'assets.24.asset.status', 'op': 'eq', 'value': 'DESTROYED'}), ['N1'])
        self.assertEqual(self.ids(self.nested, {'field': 'assets.0.asset.status', 'op': 'ne', 'value': 'ACTIVE'}), ['N3', 'N4', 'N5'])
        self.assertEqual(self.ids(self.rows, {'field': 'crew', 'op': 'gt', 'value': 3}), ['M1', 'M3'])
        self.assertEqual(self.ids(self.rows, {'field': 'cost', 'op': 'eq', 'value': None}), ['M4'])
        starred = self.s.fetch(json.dumps({'data': {'missions': {'items': [{'id': 'S1', 'a*b': 1, 'x': {'*y': 2}}, {'id': 'S2', 'a*b': 2}]}}}))
        self.assertEqual(self.ids(starred, {'field': 'a*b', 'op': 'eq', 'value': 1}), ['S1'])  # an asterisk inside a key name
        self.assertEqual(self.ids(starred, {'field': 'x.*y', 'op': 'eq', 'value': 2}), ['S1'])

    def test_a_wildcard_field_without_elements_is_refused(self):
        for field in ('assets.*.asset.status', 'tags.*', '*', '*.id', 'legs.*.assets.*.status'):
            for op, value in (('eq', 'ACTIVE'), ('ne', 'ACTIVE'), ('gt', 1)):
                text, _, error = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}],
                                             conditions=[{'field': 'id', 'op': 'ne', 'value': 'x'}, {'field': field, 'op': op, 'value': value}])
                self.assertTrue(error, field)
                self.assertEqual(text, 'calculate refused: Wildcard fields require elements: "any" or "none".')
                self.assertNotIn('read: ', text)
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'}), ['N1', 'N5'])
        self.assertEqual(self.ids(self.nested, {'field': 'assets.*.asset.status', 'elements': 'none', 'op': 'ne', 'value': 'ACTIVE'}),
                         ['N2', 'N3', 'N4'])
        self.assertEqual(self.ids(self.rows, {'field': 'tags.*', 'elements': 'none', 'op': 'eq', 'value': 'x'}), ['M2', 'M3', 'M4'])

    def test_elements_other_than_any_or_none_are_refused(self):
        for elements in ('all', 'ANY', 'some', None, 1, True, ['any']):
            text, _, error = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}],
                                         conditions=[{'field': 'assets.*.asset.status', 'elements': elements, 'op': 'eq', 'value': 'x'}])
            self.assertTrue(error, elements)
            self.assertIn('elements is any or none', text)
            self.assertNotIn('read: ', text)
        for condition, message in (({'field': 'assets', 'elements': 'any', 'op': 'contains', 'value': 'x'}, 'a condition needs'),
                                   ({'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'lt', 'value': True}, 'use eq or ne'),
                                   ({'field': 'assets', 'elements': 'any', 'op': 'eq'}, 'a condition needs')):
            text, _, error = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}],
                                         conditions=[condition])
            self.assertTrue(error, condition)
            self.assertIn(message, text)
        self.assertEqual(self.s.wrapped.counts['calculateErrors'], 10)

    def test_a_text_that_cannot_be_read_is_refused_and_never_taken_as_a_missing_field(self):
        broken = self.s.fetch(json.dumps({'data': {'missions': {'items': [
            {'id': 'B1', 'values': ['hit', '<broken'], 'doc': '<broken', 'typed': ['<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>']}]}}}))
        for field, op, value, message in (('values.*', 'eq', 'hit', 'cannot be read'), ('values', 'eq', 'hit', 'cannot be read'),
                                          ('doc.x.*', 'ne', 'x', 'cannot be read'), ('typed.*', 'ne', 'x', 'document type')):
            for elements in ('any', 'none'):
                text, _, error = self.s.calc(operation='filter', sources=[{'result_id': broken, 'path': 'body.data.missions.items'}],
                                             conditions=[{'field': field, 'elements': elements, 'op': op, 'value': value}])
                self.assertTrue(error, (field, elements))
                self.assertIn(message, text)
        self.assertEqual(self.ids(broken, {'field': 'id.*', 'elements': 'none', 'op': 'eq', 'value': 'x'}), ['B1'])

    def test_the_read_line_the_output_and_the_stored_output_are_unchanged(self):
        out, _, _ = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}], fields=['id'],
                                conditions=[{'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'}])
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items": 5 records' % self.nested)
        self.assertEqual(out, {'operation': 'filter', 'count': 2, 'records': [{'id': 'N1'}, {'id': 'N5'}]})
        self.assertEqual(self.s.coverage, '"assets.*.asset.status" has values in 3 of 5 records (1 with an empty list, 1 without the '
                                          'field)')
        many = self.s.fetch(json.dumps([{'n': i, 'tags': ['a', 'b' if i % 2 else 'c'], 'pad': 'x' * 100} for i in range(400)]))
        text, error = self.s.wrapped.call('calculate', {'operation': 'filter', 'sources': [{'result_id': many, 'path': 'body'}],
                                                        'conditions': [{'field': 'tags', 'elements': 'any', 'op': 'eq', 'value': 'b'}]})
        self.assertFalse(error)
        lines = text.split('\n')
        self.assertEqual(lines[1], 'read: %s at "body": 400 records' % many)
        self.assertTrue(lines[2].startswith('stored, not shown: '))  # every record has values there: no coverage line
        stored = json.loads(read_jsonl(self.s.path)[-1]['text'])
        self.assertEqual((stored['count'], len(stored['records']), sorted(stored)), (200, 200, ['count', 'operation', 'records']))

    def test_the_schema_offers_elements_as_an_optional_key_of_a_condition(self):
        condition = ht.CALCULATE_TOOL['input_schema']['properties']['conditions']['items']
        self.assertEqual(condition['properties']['elements'], {'type': 'string', 'enum': ['any', 'none']})
        self.assertEqual((condition['required'], condition['additionalProperties']), (['field', 'op', 'value'], False))
        self.assertEqual(condition['properties']['op']['enum'], list(ht.COMPARISONS))


ITEMS = 'body.data.missions.items'
PAGE = 'body.data.missionsPage.items'
PEOPLE = [{'id': 'P1', 'details': {'rank': 'Lt'}}, {'id': 'P2', 'details': {'rank': 'Cdr'}}, {'id': 'P3', 'details': {'rank': 'Lt'}}]
HELD = [{'id': 'R%d' % i, 'v': i, 'tags': [i]} for i in range(12)]


def page(items, total=None, more=None):
    """A page of a list as a graph returns it: the items, and beside them totalCount and hasMore when given."""
    inner = {'items': items}
    if total is not None:
        inner['totalCount'] = total
    if more is not None:
        inner['hasMore'] = more
    return json.dumps({'data': {'missionsPage': inner}})


class Version5Tests(unittest.TestCase):
    """The base of version 5's tests: a session with the four invented rows."""

    def setUp(self):
        self.s = Session()
        self.addCleanup(self.s.tmp.cleanup)
        self.rows = self.s.fetch(json.dumps({'data': {'missions': {'items': ROWS}}}))

    def src(self, path=ITEMS, rid=None):
        return [{'result_id': rid or self.rows, 'path': path}]

    def refused(self, **arguments):
        """The text of a refused call, which has neither a read line nor a coverage line."""
        text, _, error = self.s.calc(**arguments)
        self.assertTrue(error, text)
        self.assertTrue(text.startswith('calculate refused: '), text)
        self.assertNotIn('read: ', text)
        self.assertNotIn('coverage: ', text)
        self.assertLessEqual(len(text), ht.LIMITS['refusalChars'] + len('calculate refused: '))
        return text[len('calculate refused: '):]

    def ids(self, *conditions, rid=None, path=ITEMS):
        out, _, error = self.s.calc(operation='filter', sources=self.src(path, rid), fields=['id'], conditions=list(conditions))
        self.assertFalse(error, out)
        return [r['id'] for r in out['records']]


class RefusalTests(Version5Tests):
    """Version 5 refuses the silent wrong uses the trap audit found, naming every problem of the call at once."""

    SHAPE = 'ab12-1 at "body.data.missions.items": 4 records with the keys id, status, crew, cost, tags'
    ABSENT = ': choose one of the keys named under Shapes, or correct the path of the source'

    def test_an_argument_that_does_not_apply_to_the_operation_is_refused(self):
        ids = {'result_id': self.rows, 'path': ITEMS + '.*.id'}
        for arguments, message in (
                ({'operation': 'union', 'sources': [ids, ids], 'fields': ['id']}, 'fields does not apply to union, which takes sources, field, limit'),
                ({'operation': 'filter', 'sources': self.src(), 'conditions': [{'field': 'crew', 'op': 'gt', 'value': 1}], 'offset': 6,
                  'field': 'id'}, 'offset, field do not apply to filter, which takes sources, conditions, fields, limit'),
                ({'operation': 'count', 'sources': self.src(), 'descending': True}, 'descending does not apply to count, which takes sources'),
                ({'operation': 'group_by', 'sources': self.src(), 'group_by': ['status'], 'sum_field': 'cost'},
                 'sum_field applies only with aggregate sum'),
                ({'operation': 'group_by', 'sources': self.src(), 'group_by': ['status'], 'aggregate': 'count', 'sum_field': 'cost', 'round': 2},
                 'sum_field and round apply only with aggregate sum'),
                ({'operation': 'arithmetic', 'operator': 'add', 'operands': [1, 2], 'sources': self.src()},
                 'sources does not apply to arithmetic, which takes operator, operands, round'),
                ({'operation': 'view', 'sources': self.src('body.data.missions'), 'fields': ['id']},
                 'fields shortens the records of a list, and the part at "body.data.missions" is not a list'),
                ({'operation': 'view', 'sources': self.src(ITEMS + '.0.crew'), 'limit': 5},
                 'offset and limit page through a list, an object or a text, and the part at "body.data.missions.items.0.crew" is one value')):
            self.assertEqual(self.refused(**arguments), message)

    def test_view_with_fields_takes_the_field_checks(self):
        """Review finding 2: view shortened records by fields without the checks every other operation makes."""
        plain = self.s.fetch(json.dumps(['P1', 'P2']))
        self.assertEqual(self.refused(operation='view', sources=[{'result_id': plain, 'path': 'body'}], fields=['personnelId']),
                         'the field "personnelId" cannot be read from ab12-2 at "body": it holds plain values, not records. Leave fields out '
                         'to read the values themselves. Shapes: ab12-2 at "body": 2 plain values, not records (the first is "P1")')
        self.assertEqual(self.refused(operation='view', sources=self.src(), fields=['id', 'statuz']),
                         'no record has the field "statuz" (0 of 4 records)' + self.ABSENT + '. Shapes: ' + self.SHAPE)
        people = self.s.fetch(json.dumps([{'id': 'P1', 'details.rank': 'Lt'}]))
        self.assertIn('write it in brackets, [details.rank]',
                      self.refused(operation='view', sources=[{'result_id': people, 'path': 'body'}], fields=['details.rank']))
        out, _, error = self.s.calc(operation='view', sources=self.src(), fields=['id', 'cost'], limit=2)
        self.assertEqual((out['records'], error), ([{'id': 'M1', 'cost': '10.50'}, {'id': 'M2', 'cost': '4.25'}], False))
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing)')  # of the whole list, not the page
        out, _, _ = self.s.calc(operation='view', sources=[{'result_id': plain, 'path': 'body'}])
        self.assertEqual((out['records'], self.s.coverage), (['P1', 'P2'], None))

    def test_an_argument_of_the_wrong_form_is_named_with_the_form_it_takes(self):
        """The audit's P05: version 4 answered `the calculation failed (TypeError)`, which names nothing to correct."""
        for arguments, message in (
                ({'operation': 'sort', 'limit': 'two'}, 'limit is a whole number of 1 or more (got "two")'),
                ({'operation': 'sort', 'limit': 0}, 'limit is a whole number of 1 or more (got 0)'),
                ({'operation': 'view', 'offset': -1}, 'offset is a whole number of 0 or more (got -1)'),
                ({'operation': 'sort', 'fields': 5}, 'fields is a list of field names, each a text (got 5)'),
                ({'operation': 'distinct', 'field': {'a': 1}}, 'field is a text (got {"a": 1})'),
                ({'operation': 'group_by', 'group_by': [['status']]}, 'group_by is a list of field names, each a text (got [["status"]])'),
                ({'operation': 'group_by', 'group_by': ['status'], 'aggregate': 'sum', 'sum_field': 'cost', 'round': 'two'},
                 'round is a whole number from 0 to 12 (got "two")'),
                ({'operation': 'sort', 'descending': 'yes'}, 'descending is true or false (got "yes")'),
                ({'operation': 'count', 'sources': 1}, 'sources is a list of {result_id, path} (got 1)'),
                ({'operation': 'count', 'sources': [7]}, 'a source is an object {result_id, path} (got 7)'),
                ({'operation': 'count', 'sources': [{'result_id': ['ab12-1']}]},
                 'result_id is the text on the first line of a result (got ["ab12-1"])'),
                ({'operation': 'count', 'sources': [{'result_id': self.rows, 'path': 5}]}, 'path is a text (got 5)'),
                ({'operation': 'filter', 'conditions': 'crew'}, 'conditions is a list of {field, op, value, elements} (got "crew")'),
                ({'operation': 'filter', 'conditions': [{'field': 3, 'op': 'eq', 'value': 1}]}, 'the field of a condition is a text (got 3)'),
                ({'operation': 'arithmetic', 'operator': 'add', 'operands': 5}, 'operands is a list of numbers or {result_id, path} (got 5)')):
            arguments.setdefault('sources', self.src())
            text = self.refused(**arguments)
            self.assertIn(message, text)
            self.assertNotIn('the calculation failed', text)
        text = self.refused(operation='sort', sources=self.src(), field=3, limit='two', offset=2)
        self.assertEqual(text, '3 problems: (1) field is a text (got 3); (2) limit is a whole number of 1 or more (got "two"); (3) offset does '
                               'not apply to sort, which takes sources, field, descending, fields, limit')

    def test_a_key_that_a_source_a_condition_or_an_operand_does_not_take_is_refused(self):
        """The audit's P14, inside the arguments: version 4 dropped such a key without a word."""
        text = self.refused(operation='distinct', sources=[{'result_id': self.rows, 'path': ITEMS, 'field': 'status'}])
        self.assertEqual(text, 'a source takes result_id and path, not field')
        text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': 'crew', 'op': 'gt', 'value': 1, 'operator': 'and'}])
        self.assertEqual(text, 'a condition takes field, op, value and elements, not operator')
        text = self.refused(operation='arithmetic', operator='add', operands=[{'result_id': self.rows, 'path': 'x', 'field': 'y'}, 1])
        self.assertEqual(text, 'an operand takes result_id and path, not field')

    def test_an_argument_that_says_nothing_is_not_refused(self):
        """Null, false, an empty text or list and offset 0 are what a model sends for an argument it does not use."""
        ids = {'result_id': self.rows, 'path': ITEMS + '.*.id'}
        out, _, error = self.s.calc(operation='union', sources=[ids, ids], field='', fields=[], offset=0, descending=False, sum_field=None,
                                    conditions=[], group_by=[])
        self.assertFalse(error, out)
        self.assertEqual(out['values'], ['M1', 'M2', 'M3', 'M4'])
        out, _, error = self.s.calc(operation='view', sources=self.src(ITEMS + '.0.crew'), offset=0)
        self.assertEqual((out, error), ({'operation': 'view', 'value': 4}, False))

    def test_a_field_on_a_source_of_plain_values_is_refused_with_the_path_to_use(self):
        """The audit's P08: version 4 read the field as null in every plain value and gave an empty intersection."""
        plain = self.s.fetch(json.dumps(['M2', 'M4', 'M9']))
        sources = [{'result_id': plain, 'path': 'body'}, {'result_id': self.rows, 'path': ITEMS}]
        self.assertEqual(self.refused(operation='intersection', sources=sources, field='id'),
                         'the field "id" cannot be read from ab12-2 at "body": it holds plain values, not records. Leave the field empty to '
                         'use the values themselves, and put it in the path of each source that holds records (for ab12-1: path '
                         '"body.data.missions.items.*.id"). Shapes: ab12-2 at "body": 3 plain values, not records (the first is "M2"); '
                         + self.SHAPE)
        out, _, error = self.s.calc(operation='intersection', sources=[sources[0], {'result_id': self.rows, 'path': ITEMS + '.*.id'}])
        self.assertEqual((out['values'], error), (['M2', 'M4'], False))  # the call the refusal names
        text = self.refused(operation='distinct', sources=sources[:1], field='id')
        self.assertIn('Leave the field empty to use the values themselves. Shapes:', text)
        one = self.s.fetch(json.dumps({'person': {'id': 'M2'}, 'people': [{'id': 'M4'}]}))  # review finding 5: * only where a list ends
        for path, named in (('body.person', 'body.person.id'), ('body.people', 'body.people.*.id'), ('body.people.*', 'body.people.*.id')):
            text = self.refused(operation='intersection', sources=[sources[0], {'result_id': one, 'path': path}], field='id')
            self.assertIn('(for %s: path "%s")' % (one, named), text)
            out, _, error = self.s.calc(operation='intersection', sources=[sources[0], {'result_id': one, 'path': named}])
            self.assertEqual((out['count'], error), (1, False), named)  # the path the refusal names is accepted
        text = self.refused(operation='filter', sources=sources[:1], conditions=[{'field': 'id', 'op': 'eq', 'value': 'M2'}])
        self.assertIn('the field "id" cannot be read from ab12-2 at "body"', text)
        out, _, error = self.s.calc(operation='filter', sources=sources[:1], conditions=[{'field': '', 'op': 'eq', 'value': 'M2'}])
        self.assertEqual((out['records'], error), (['M2'], False))  # an empty field is the value itself

    def test_a_field_that_no_record_has_is_refused(self):
        """The audit's P02: version 4 read the field as null in every record."""
        for arguments, fields in (({'operation': 'distinct', 'field': 'statuz'}, 'the field "statuz"'),
                                  ({'operation': 'sort', 'field': 'statuz'}, 'the field "statuz"'),
                                  ({'operation': 'filter', 'conditions': [{'field': 'statuz', 'op': 'eq', 'value': 'ACTIVE'}]}, 'the field "statuz"'),
                                  ({'operation': 'filter', 'conditions': [{'field': 'crew', 'op': 'gt', 'value': 1}], 'fields': ['idd', 'statuz']},
                                   'the fields "idd", "statuz"'),
                                  ({'operation': 'group_by', 'group_by': ['status'], 'aggregate': 'sum', 'sum_field': 'price'}, 'the field "price"'),
                                  ({'operation': 'union', 'field': 'statuz', 'sources': self.src() + self.src()}, 'the field "statuz"')):
            arguments.setdefault('sources', self.src())
            records = sum(4 for _ in arguments['sources'])
            self.assertEqual(self.refused(**arguments), 'no record has %s (0 of %d records)%s. Shapes: %s'
                             % (fields, records, self.ABSENT, self.SHAPE))
        many = self.refused(operation='sort', sources=self.src(), fields=['f%d' % i for i in range(9)])
        self.assertIn('no record has the fields "f0", "f1", "f2", "f3", "f4", "f5" and 3 more (0 of 4 records)', many)

    def test_a_field_that_some_records_have_and_an_empty_source_are_not_refused(self):
        out, _, error = self.s.calc(operation='distinct', sources=self.src(), field='cost')
        self.assertEqual((out['values'], error), (['1.25', '10.50', '4.25', None], False))
        empty = self.s.fetch(json.dumps({'data': {'missions': {'items': []}}}))
        out, _, error = self.s.calc(operation='distinct', sources=self.src(rid=empty), field='statuz')
        self.assertEqual((out, error, self.s.coverage), ({'operation': 'distinct', 'count': 0, 'values': []}, False, None))

    def test_an_empty_group_by_gives_one_group_over_all_records(self):
        """The lead developer's addition: the paid runs named a field no record has to get one total, which is now refused."""
        text = self.refused(operation='group_by', sources=self.src(), group_by=['__all'], aggregate='sum', sum_field='cost')
        self.assertEqual(text, 'no record has the field "__all" (0 of 4 records)' + self.ABSENT + '. To count or add up all records as one '
                               'group, give group_by as an empty list. Shapes: ' + self.SHAPE)
        out, _, error = self.s.calc(operation='group_by', sources=self.src(), group_by=[], aggregate='sum', sum_field='cost', round=2)
        self.assertEqual((out, error), ({'operation': 'group_by', 'groupCount': 1, 'groups': [{'key': {}, 'count': 4, 'sum': 16}],
                                         'notNumeric': 1}, False))
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing); the sum added 3 of 4 records; 1 had no number there')
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(), group_by=[])
        self.assertEqual((out['groups'], self.s.coverage), ([{'key': {}, 'count': 4}], None))
        self.assertEqual(self.refused(operation='group_by', sources=self.src()),
                         'group_by needs a list of fields in group_by; an empty list gives one group over all records')
        empty = self.s.fetch(json.dumps({'data': {'missions': {'items': []}}}))  # review finding 4: no records are still one group
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(rid=empty), group_by=[])
        self.assertEqual(out, {'operation': 'group_by', 'groupCount': 1, 'groups': [{'key': {}, 'count': 0}]})
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(rid=empty), group_by=[], aggregate='sum', sum_field='cost')
        self.assertEqual(out, {'operation': 'group_by', 'groupCount': 1, 'groups': [{'key': {}, 'count': 0, 'sum': 0}]})
        out, _, _ = self.s.calc(operation='group_by', sources=self.src(rid=empty), group_by=['status'])
        self.assertEqual(out, {'operation': 'group_by', 'groupCount': 0, 'groups': []})

    def test_a_star_in_a_field_outside_a_condition_with_elements_is_refused(self):
        """The audit's P25: version 4 refused it in a filter only."""
        rule = ' cannot have a * segment: * belongs in the path of a source, or in the field of a filter condition with elements any or none'
        for arguments, names in (({'operation': 'distinct', 'field': 'tags.*'}, 'field'), ({'operation': 'sort', 'field': 'tags.*'}, 'field'),
                                 ({'operation': 'group_by', 'group_by': ['status', 'tags.*']}, 'group_by'),
                                 ({'operation': 'group_by', 'group_by': ['tags.*'], 'aggregate': 'sum', 'sum_field': 'tags.*'}, 'group_by and sum_field'),
                                 ({'operation': 'sort', 'field': 'id', 'fields': ['tags.*']}, 'fields')):
            self.assertEqual(self.refused(sources=self.src(), **arguments), names + rule)
        out, _, _ = self.s.calc(operation='distinct', sources=self.src(ITEMS + '.*.tags.*'))
        self.assertEqual(out['values'], ['x'])  # the star belongs in the path
        text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': 'tags.*', 'op': 'eq', 'value': 'x'}])
        self.assertEqual(text, ht.WILDCARD_REFUSAL)  # version 4's refusal, word for word

    def test_a_star_at_an_object_is_refused_and_an_xml_element_that_occurs_once_is_a_list_of_one(self):
        """The audit's P10: version 4 took an object under * as one element, which a later step then left out."""
        text = self.refused(operation='count', sources=self.src('body.data.*.items'))
        self.assertTrue(text.startswith("path 'body.data.*.items': * takes the elements of a list, but body.data is an object (its keys are "
                                        "missions); name a key instead of *. Shapes: ab12-1 holds {"), text)
        self.assertIn('takes the elements of a list', self.refused(operation='view', sources=self.src('body.data.*')))
        text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': '*.x', 'elements': 'any', 'op': 'eq', 'value': 1}])
        self.assertIn('is an object (its keys are id, status, crew, cost, tags)', text)
        single = self.s.fetch(SINGLE, ctype='text/xml')
        out, _, error = self.s.calc(operation='distinct', sources=[{'result_id': single, 'path': 'body.Envelope.Body.r.person.*.id'}])
        self.assertEqual((out['values'], error), (['P9'], False))  # XML has no lists: one element is a list of one
        out, _, error = self.s.calc(operation='count', sources=self.src(ITEMS + '.0.status.*'))
        self.assertEqual((out['count'], error), (1, False))  # a single value under * is still a list of one

    def test_a_list_or_an_object_compared_with_one_value_is_refused_without_elements(self):
        """The audit's P17: version 4 answered that no list equals a value, so membership read as false."""
        text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': 'tags', 'op': 'eq', 'value': 'x'}])
        self.assertEqual(text, '"tags" holds a list or an object in 2 of 4 records, which one value never equals: say elements any or none '
                               'to compare the values inside it, or compare with null to test that the field is there. Shapes: ' + self.SHAPE)
        text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': '', 'op': 'ne', 'value': 'x'}])
        self.assertIn('the record itself holds a list or an object in 4 of 4 records', text)
        self.assertEqual(self.ids({'field': 'tags', 'op': 'eq', 'value': None}), ['M3', 'M4'])  # a test that the field is there
        self.assertEqual(self.ids({'field': 'tags', 'op': 'ne', 'value': None}), ['M1', 'M2'])
        self.assertEqual(self.ids({'field': 'tags', 'elements': 'any', 'op': 'eq', 'value': 'x'}), ['M1'])

    def test_conditions_that_contradict_each_other_are_refused(self):
        """The audit's P18: the zero they give is right, and the call cannot be what was meant."""
        tag = {'field': 'tags', 'op': 'eq', 'value': 'x'}
        text = self.refused(operation='filter', sources=self.src(), conditions=[dict(tag, elements='any'), dict(tag, elements='none')])
        self.assertEqual(text, 'the conditions "tags" eq "x" (elements any) and "tags" eq "x" (elements none) contradict each other, so no '
                               'record can meet both')
        for first, second, value in (('eq', 'ne', 'ACTIVE'), ('ne', 'eq', 'ACTIVE'), ('lt', 'ge', 'B'), ('gt', 'le', 'B')):
            text = self.refused(operation='filter', sources=self.src(), conditions=[{'field': 'status', 'op': first, 'value': value},
                                                                                    {'field': 'status', 'op': second, 'value': value}])
            self.assertIn('contradict each other', text)
        self.assertEqual(self.ids({'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}, {'field': 'status', 'op': 'ne', 'value': 'CLOSED'}),
                         ['M1', 'M3'])
        self.assertEqual(self.ids({'field': 'crew', 'op': 'lt', 'value': 5}, {'field': 'crew', 'op': 'gt', 'value': 2}), ['M1'])
        self.assertEqual(self.ids(dict(tag, elements='any'), {'field': 'tags', 'elements': 'any', 'op': 'ne', 'value': 'x'}), [])

    def test_a_key_with_a_dot_in_its_name_is_written_in_brackets(self):
        """The audit's P09: an output names a projected field `details.rank`, which version 4 then read as nested steps and so as null."""
        people = self.s.fetch(json.dumps(PEOPLE))
        _, projected, _ = self.s.calc(operation='sort', sources=[{'result_id': people, 'path': 'body'}], field='id', fields=['id', 'details.rank'])
        flat = [{'result_id': projected, 'path': 'records'}]
        refusal = ('the key "details.rank" has a dot in its name, so it is not the nested steps "details" then "rank": write it in brackets, '
                   '[details.rank]')
        self.assertEqual(self.refused(operation='group_by', sources=flat, group_by=['details.rank']),
                         refusal + '. Shapes: %s at "records": 3 records with the keys details.rank, id' % projected)
        self.assertEqual(self.refused(operation='distinct', sources=[{'result_id': projected, 'path': 'records.*.details.rank'}]), refusal)
        self.assertIn(refusal, self.refused(operation='filter', sources=flat, conditions=[{'field': 'details.rank', 'op': 'eq', 'value': 'Lt'}]))
        out, grouped, _ = self.s.calc(operation='group_by', sources=flat, group_by=['[details.rank]'])
        self.assertEqual(out['groups'], [{'key': {'[details.rank]': 'Cdr'}, 'count': 1}, {'key': {'[details.rank]': 'Lt'}, 'count': 2}])
        out, _, _ = self.s.calc(operation='filter', sources=flat, fields=['id'], conditions=[{'field': '[details.rank]', 'op': 'eq', 'value': 'Lt'}])
        self.assertEqual(out['records'], [{'id': 'P1'}, {'id': 'P3'}])
        out, _, _ = self.s.calc(operation='distinct', sources=[{'result_id': projected, 'path': 'records.*.[details.rank]'}])
        self.assertEqual(out['values'], ['Cdr', 'Lt'])
        out, _, _ = self.s.calc(operation='distinct', sources=[{'result_id': grouped, 'path': 'groups.*.key.[details.rank]'}])
        self.assertEqual(out['values'], ['Cdr', 'Lt'])
        out, _, _ = self.s.calc(operation='sort', sources=flat, field='id', fields=['[details.rank]'], limit=1)
        self.assertEqual(out['records'], [{'[details.rank]': 'Lt'}])  # an output names a field as it was written

    def test_a_comparison_with_null_of_a_field_no_record_has_is_answered(self):
        """Fourth review, finding 3: comparing with null is the test that a field is there, which version 4 answered and which the
        refusal of a list compared with one value itself advises."""
        rid = self.s.fetch(json.dumps([{'id': 1}, {'id': 2}]))
        source = [{'result_id': rid, 'path': 'body'}]
        out, _, error = self.s.calc(operation='filter', sources=source, conditions=[{'field': 'deletedAt', 'op': 'eq', 'value': None}])
        self.assertEqual((out['count'], error), (2, False))
        self.assertEqual(self.s.coverage, '"deletedAt" in 0 of 2 records (2 missing); "deletedAt" eq null holds for the 2 records without '
                                          'the field')
        out, _, error = self.s.calc(operation='filter', sources=source, conditions=[{'field': 'deletedAt', 'op': 'ne', 'value': None}])
        self.assertEqual((out['count'], error), (0, False))
        self.assertEqual(self.s.coverage, '"deletedAt" in 0 of 2 records (2 missing); no record of 2 met every condition (alone: '
                                          '"deletedAt" ne null holds for 0)')
        for condition in ({'field': 'deletedAt', 'op': 'eq', 'value': 'x'}, {'field': 'deletedAt', 'op': 'eq', 'value': None, 'elements': 'any'}):
            self.assertIn('no record has the field "deletedAt" (0 of 2 records)', self.refused(operation='filter', sources=source,
                                                                                               conditions=[condition]))
        self.assertIn('no record has the field "deletedAt"', self.refused(  # the same field read as a field is still refused
            operation='filter', sources=source, conditions=[{'field': 'deletedAt', 'op': 'eq', 'value': None}], fields=['deletedAt']))

    def test_a_step_in_brackets_keeps_version_4s_reading_and_two_readings_are_refused(self):
        """Review finding 3: version 4 read `[x]` as the key "[x]"; reading it as the key "x" changed an accepted call's answer, and
        naming an output `a.b` for both `a.b` and `[a.b]` made one overwrite the other."""
        def distinct(record, field):
            rid = self.s.fetch(json.dumps([record]))
            return self.s.calc(operation='distinct', sources=[{'result_id': rid, 'path': 'body'}], field=field)
        self.assertEqual(distinct({'[x]': 2}, '[x]')[0]['values'], [2])   # version 4's reading, and its answer
        self.assertEqual(distinct({'x': 1}, '[x]')[0]['values'], [1])     # the brackets name the key
        self.assertEqual(distinct({'[a': {'b]': 3}}, '[a.b]')[0]['values'], [3])  # version 4 read the dot as a step
        text, _, error = distinct({'x': 1, '[x]': 2}, '[x]')
        self.assertTrue(error)
        self.assertTrue(text.startswith('calculate refused: the step [x] of the field "[x]" has more than one reading among the objects of '
                                        'this call (the key "x" in 1, the key "[x]" in 1), so it is not read. Shapes: '), text)
        both = self.s.fetch(json.dumps([{'id': 1, 'a': {'b': 1}, 'a.b': 7}, {'id': 2, 'a': {'b': 2}, 'a.b': 7}]))
        source = [{'result_id': both, 'path': 'body'}]
        out, projected, _ = self.s.calc(operation='sort', sources=source, field='id', fields=['a.b', '[a.b]'])
        self.assertEqual(out['records'], [{'a.b': 1, '[a.b]': 7}, {'a.b': 2, '[a.b]': 7}])  # two fields, two keys
        out, _, _ = self.s.calc(operation='group_by', sources=source, group_by=['a.b', '[a.b]'])
        self.assertEqual(out['groups'], [{'key': {'a.b': 1, '[a.b]': 7}, 'count': 1}, {'key': {'a.b': 2, '[a.b]': 7}, 'count': 1}])
        text = self.refused(operation='distinct', sources=[{'result_id': projected, 'path': 'records'}], field='[a.b]')
        self.assertIn('the step [a.b] of the field "[a.b]" has more than one reading among the objects of this call (the key "a.b" in 2, '
                      'the key "[a.b]" in 2)', text)

    def test_a_step_in_brackets_is_read_one_way_in_a_whole_call(self):
        """Third review: the reading was chosen record by record, so the records [{"[x]": 2}, {"x": 1}] gave [1, 2] where version 4
        gave [2, null]. Neither record has two readings; the call has."""
        def body(value, at='body'):
            return [{'result_id': self.s.fetch(json.dumps(value)), 'path': at}]
        mixed = body([{'[x]': 2}, {'x': 1}])
        text = self.refused(operation='distinct', sources=mixed, field='[x]')
        self.assertTrue(text.startswith('the step [x] of the field "[x]" has more than one reading among the objects of this call (the key '
                                        '"[x]" in 1, the key "x" in 1), so it is not read. Shapes: '), text)
        for arguments in ({'operation': 'group_by', 'group_by': ['[x]']}, {'operation': 'sort', 'field': '[x]'},
                          {'operation': 'group_by', 'group_by': [], 'aggregate': 'sum', 'sum_field': '[x]'},
                          {'operation': 'filter', 'conditions': [{'field': '[x]', 'op': 'eq', 'value': 1}]},
                          {'operation': 'filter', 'conditions': [{'field': '[x]', 'op': 'eq', 'value': 1, 'elements': 'any'}]},
                          {'operation': 'view', 'fields': ['[x]']}):
            self.assertIn('the step [x] of the field "[x]" has more than one reading among the objects of this call',
                          self.refused(sources=mixed, **arguments), arguments)
        out, _, error = self.s.calc(operation='distinct', sources=body([{'[x]': 2}, {'y': 1}]), field='[x]')
        self.assertEqual((out['values'], error, self.s.coverage), ([2, None], False, '"[x]" in 1 of 2 records (1 missing); the 2 values '
                                                                                    'include null (1 not null)'))  # version 4's answer
        out, _, error = self.s.calc(operation='distinct', sources=body([{'x': 1}, {'y': 1}]), field='[x]')
        self.assertEqual((out['values'], error), ([1, None], False))  # no record has the key "[x]": the brackets name the key "x"
        text = self.refused(operation='distinct', sources=body([{'[a': {'b]': 5}}, {'a.b': 7}]), field='[a.b]')
        self.assertIn('the step [a.b] of the field "[a.b]" has more than one reading among the objects of this call (the key "[a" in 1, '
                      'the key "a.b" in 1)', text)
        text = self.refused(operation='filter', sources=body([{'l': [{'[x]': 2}]}, {'l': [{'x': 1}]}]),
                            conditions=[{'field': 'l.*.[x]', 'op': 'eq', 'value': 1, 'elements': 'any'}])
        self.assertIn('the step [x] of the field "l.*.[x]" has more than one reading among the objects of this call', text)

    def test_a_path_with_a_step_in_brackets_is_read_one_way_by_every_source_of_a_call(self):
        """Version 4 left out the elements that lack the key "[x]"; reading the key "x" in them would add records to its answer."""
        def held(value):
            return self.s.fetch(json.dumps(value))
        mixed, raw, named = held([{'[x]': 2}, {'x': 1}]), held([{'[x]': 2}]), held([{'x': 1}])
        text = self.refused(operation='count', sources=[{'result_id': mixed, 'path': 'body.*.[x]'}])
        self.assertIn('the step [x] of the path "body.*.[x]" has more than one reading among the objects of this call (the key "[x]" in 1, '
                      'the key "x" in 1), so it is not read', text)
        self.assertIn('has more than one reading', self.refused(operation='view', sources=[{'result_id': mixed, 'path': 'body.*.[x]'}]))
        text = self.refused(operation='union', sources=[{'result_id': mixed, 'path': 'body.*.[x]'}] * 3)
        self.assertTrue(text.startswith('the step [x] of the path '), text)  # one problem, said once, for the sources that share the path
        both = [{'result_id': raw, 'path': 'body.*.[x]'}, {'result_id': named, 'path': 'body.*.[x]'}]
        self.assertIn('the step [x] of the path "body.*.[x]" has more than one reading', self.refused(operation='union', sources=both))
        for source, value in ((both[0], 2), (both[1], 1)):  # the next call starts anew, and one key answers each of them
            out, _, error = self.s.calc(operation='distinct', sources=[source])
            self.assertEqual((out['values'], error), ([value], False))
        one, other = held({'[n]': 2}), held({'n': 3})
        text = self.refused(operation='arithmetic', operator='add',
                            operands=[{'result_id': one, 'path': 'body.[n]'}, {'result_id': other, 'path': 'body.[n]'}])
        self.assertIn('the step [n] of the path "body.[n]" has more than one reading', text)
        out, _, _ = self.s.calc(operation='arithmetic', operator='add', operands=[{'result_id': other, 'path': 'body.[n]'}, 1])
        self.assertEqual(out['value'], 4)

    def test_brackets_take_a_step_literally_and_only_a_whole_step(self):
        odd = self.s.fetch(json.dumps([{'a[b]': 1, '*': 5, 'x.y': {'z': 7}}]))
        for field, value in (('a[b]', 1), ('[*]', 5), ('[x.y].z', 7)):
            out, _, error = self.s.calc(operation='distinct', sources=[{'result_id': odd, 'path': 'body'}], field=field)
            self.assertEqual((out['values'], error), ([value], False), field)
        self.assertFalse(ht.has_wildcard('[*]'))
        self.assertTrue(ht.has_wildcard('a.*.[b.c]'))
        self.assertEqual([ht._segments(p) for p in ('a.b', '[a.b]', 'x.[a.b].c', 'a[b].c', '[a.b', 'a.')],
                         [['a', 'b'], ['a.b'], ['x', 'a.b', 'c'], ['a[b]', 'c'], ['[a', 'b'], ['a', '']])

    def test_an_output_too_long_to_keep_whole_is_refused_and_never_cut(self):
        """The audit's P12: version 4 cut such an output and marked it truncated."""
        with unittest.mock.patch.dict(ht.LIMITS, {'maxStoredOutputChars': 200}):
            text = self.refused(operation='sort', sources=self.src(), field='id')
            self.assertRegex(text, r'^the output would be \d+ characters, more than the 200 that can be kept whole: narrow it')
            out, _, error = self.s.calc(operation='sort', sources=self.src(), field='id', fields=['id'], limit=1)
            self.assertEqual((out['records'], error), ([{'id': 'M1'}], False))
        self.assertEqual(self.s.wrapped.counts['calculateErrors'], 1)

    def test_every_problem_of_a_call_is_named_at_once(self):
        """The audit's P05: version 4 named the first problem only, and the next call met the next one."""
        text = self.refused(operation='filter', sources=self.src(), offset=3,
                            conditions=[{'field': 'statuz', 'op': 'eq', 'value': 'A'}, {'field': 'tags', 'op': 'eq', 'value': 'x'}])
        self.assertEqual(text, '3 problems: (1) offset does not apply to filter, which takes sources, conditions, fields, limit; (2) "tags" '
                               'holds a list or an object in 2 of 4 records, which one value never equals: say elements any or none to compare '
                               'the values inside it, or compare with null to test that the field is there; (3) no record has the field '
                               '"statuz" (0 of 4 records)' + self.ABSENT + '. Shapes: ' + self.SHAPE)
        text = self.refused(operation='count', sources=self.src('body.data.nothing') + self.src('body.data.missions.item'))
        self.assertTrue(text.startswith("2 problems: (1) path 'body.data.nothing': body.data has no key 'nothing'; its keys are missions; "
                                        "(2) path 'body.data.missions.item': body.data.missions has no key 'item'; its keys are items. "
                                        'Shapes: ab12-1 holds {"status": 200, '), text)
        text = self.refused(operation='view', sources=self.src('body.data.nothing'), fields=['a.*'])
        self.assertTrue(text.startswith('2 problems: (1) fields cannot have a * segment'), text)
        self.assertIn("(2) path 'body.data.nothing': body.data has no key 'nothing'; its keys are missions. Shapes: ab12-1 holds {", text)

    def test_the_shapes_of_a_refusal_are_bounded(self):
        wide = self.s.fetch(json.dumps([{'k%03d' % i + 'x' * 60: i for i in range(80)}]))
        sources = [{'result_id': wide, 'path': 'body'}] * 6 + self.src()
        text = self.refused(operation='distinct', sources=sources, field='nothing')
        self.assertIn('. Shapes: ', text)
        self.assertEqual(text.count(' at "body": 1 record with the keys'), 1)  # a shape is said once
        self.assertLess(len(text), 900)


class CoverageTests(Version5Tests):
    """Version 5's coverage line: what the records a calculation read cover."""

    def test_each_field_read_says_how_many_records_have_it_lack_it_or_hold_null(self):
        """The audit's P02 and P04: the read line counted records, not the records that have the field."""
        self.s.calc(operation='count', sources=self.src())
        self.assertIsNone(self.s.coverage)  # a count reads no field
        self.s.calc(operation='distinct', sources=self.src(), field='status')
        self.assertIsNone(self.s.coverage)  # a field every record has is not named: the line speaks only of gaps
        self.s.calc(operation='sort', sources=self.src(), field='cost', fields=['id', 'tags'])
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing); "tags" in 2 of 4 records (2 missing)')
        nulls = self.s.fetch(json.dumps([{'id': 'A', 'v': None}, {'id': 'B', 'v': 1}, {'id': 'C'}]))
        self.s.calc(operation='distinct', sources=[{'result_id': nulls, 'path': 'body'}], field='v')
        self.assertEqual(self.s.coverage, '"v" in 1 of 3 records (1 missing, 1 null); the 2 values include null (1 not null)')

    def test_the_gaps_of_a_field_are_named_per_source_when_the_sources_differ(self):
        other = self.s.fetch(json.dumps([{'id': 'M9'}, {'id': 'M8', 'status': None}]))
        sources = self.src() + [{'result_id': other, 'path': 'body'}]
        self.s.calc(operation='distinct', sources=sources, field='status')
        self.assertEqual(self.s.coverage, '"status" in 4 of 6 records (1 missing, 1 null) [ab12-2: 1 missing, 1 null]; the 4 values include '
                                          'null (3 not null)')
        two = self.s.fetch(json.dumps({'a': [{'id': 1, 'status': 'A'}], 'b': [{'id': 2}]}))
        self.s.calc(operation='distinct', sources=[{'result_id': two, 'path': 'body.a'}, {'result_id': two, 'path': 'body.b'}], field='status')
        self.assertEqual(self.s.coverage, '"status" in 1 of 2 records (1 missing) [%s at "body.b": 1 missing]; the 2 values include null '
                                          '(1 not null)' % two)  # one result named twice: the path tells them apart

    def test_a_condition_that_holds_for_records_without_its_field_says_so(self):
        """The audit's P15: a missing field reads as null, which satisfies ne and eq null."""
        self.assertEqual(self.ids({'field': 'cost', 'op': 'ne', 'value': '10.50'}), ['M2', 'M3', 'M4'])
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing); "cost" ne "10.50" holds for the 1 record without the field')
        self.assertEqual(self.ids({'field': 'cost', 'op': 'eq', 'value': '10.50'}), ['M1'])
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing)')

    def test_a_filter_that_keeps_nothing_says_what_each_condition_did_alone(self):
        """The audit's P01: an empty output said nothing of why it was empty."""
        self.assertEqual(self.ids({'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}, {'field': 'crew', 'op': 'gt', 'value': 10}), [])
        self.assertEqual(self.s.coverage, 'no record of 4 met every condition (alone: "status" eq "ACTIVE" holds for 2, "crew" gt 10 holds '
                                          'for 0)')

    def test_a_condition_with_elements_says_which_records_have_values(self):
        nested = self.s.fetch(json.dumps({'data': {'missions': {'items': NESTED}}}))
        self.assertEqual(self.ids({'field': 'assets.*.asset.status', 'elements': 'none', 'op': 'eq', 'value': 'MISSING'}, rid=nested),
                         ['N2', 'N3', 'N4'])
        self.assertEqual(self.s.coverage, '"assets.*.asset.status" has values in 3 of 5 records (1 with an empty list, 1 without the field)')
        self.ids({'field': 'assets.*.note', 'elements': 'any', 'op': 'eq', 'value': 'no asset'}, rid=nested)
        self.assertEqual(self.s.coverage, '"assets.*.note" has values in 1 of 5 records (1 with an empty list, 2 whose elements lack the rest, '
                                          '1 without the field)')
        self.ids({'field': 'tags', 'elements': 'none', 'op': 'eq', 'value': 'q'}, {'field': 'cost', 'op': 'ne', 'value': None})
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing); "tags" has values in 1 of 4 records (1 with an empty list, '
                                          '2 without the field)')

    def test_a_sum_says_how_many_records_it_added(self):
        """The audit's P22: notNumeric said how many were skipped, not why."""
        self.s.calc(operation='group_by', sources=self.src(), group_by=['status'], aggregate='sum', sum_field='cost')
        self.assertEqual(self.s.coverage, '"cost" in 3 of 4 records (1 missing); the sum added 3 of 4 records; 1 had no number there')
        self.s.calc(operation='group_by', sources=self.src(), group_by=['status'], aggregate='sum', sum_field='crew')
        self.assertEqual(self.s.coverage, 'the sum added 4 of 4 records')

    def test_set_operations_say_the_size_of_each_set_and_a_null_among_the_values(self):
        """The audit's P11 and P19."""
        other = self.s.fetch(json.dumps([{'mission': 'M2'}, {'mission': 'M4'}, {'mission': 'M9'}]))
        a, b = {'result_id': self.rows, 'path': ITEMS + '.*.id'}, {'result_id': other, 'path': 'body.*.mission'}
        for operation in ('union', 'intersection', 'difference'):
            self.s.calc(operation=operation, sources=[a, b])
            self.assertEqual(self.s.coverage, '%s of sets of 4, 3 values' % operation)  # in the order of the read line's sources
        out, _, _ = self.s.calc(operation='union', sources=self.src() + self.src(), field='cost')
        self.assertEqual(out['count'], 4)
        self.assertEqual(self.s.coverage, '"cost" in 6 of 8 records (2 missing); union of sets of 4, 4 values; the 4 values include null '
                                          '(3 not null)')

    def test_groups_over_several_fields_say_that_they_are_not_unique_values_of_one_field(self):
        """The audit's P20: a count of such groups read as a count of ids."""
        pairs = self.s.fetch(json.dumps([{'p': 'A', 'r': 1}, {'p': 'A', 'r': 2}, {'p': 'B', 'r': 1}]))
        source = [{'result_id': pairs, 'path': 'body'}]
        out, _, _ = self.s.calc(operation='group_by', sources=source, group_by=['p', 'r'])
        self.assertEqual(out['groupCount'], 3)
        self.assertEqual(self.s.coverage, '3 groups over 2 fields are not unique values of one field (distinct values: "p" has 2, "r" has 2)')
        self.s.calc(operation='group_by', sources=source, group_by=['p'])
        self.assertIsNone(self.s.coverage)

    def test_the_read_line_names_the_step_that_left_out_elements_lacked(self):
        """The audit's P03."""
        rid = self.s.fetch(json.dumps([{'a': {'b': [1]}}, {'a': {}}, {}]))
        out, _, _ = self.s.calc(operation='count', sources=[{'result_id': rid, 'path': 'body.*.a.b'}])
        self.assertEqual(out, {'operation': 'count', 'count': 1, 'missing': 2})
        self.assertEqual(self.s.read, 'read: %s at "body.*.a.b": 1 record (2 elements were left out: 1 lacked "a", 1 lacked "b")' % rid)
        self.assertEqual(self.s.wrapped.last_details['read'][0]['lacked'], {'a': 1, 'b': 1})

    def test_records_that_do_not_cover_the_total_their_page_states_say_so(self):
        """The audit's P13 and P23: a total built from two pages of three read like any other."""
        first = self.s.fetch(page(ROWS[:2], total=4, more=True))
        out, _, _ = self.s.calc(operation='count', sources=self.src(PAGE, first))
        self.assertEqual((out, self.s.coverage), ({'operation': 'count', 'count': 2},
                                                  'built from 2 of totalCount 4 at "items" (2 not among the sources)'))
        self.s.calc(operation='count', sources=self.src(PAGE, first) + self.src(PAGE, first))
        self.assertEqual(self.s.coverage, 'built from 2 of totalCount 4 at "items" (2 not among the sources)')  # a page counts once
        second = self.s.fetch(page(ROWS[2:], total=4, more=False))
        self.s.calc(operation='distinct', sources=self.src(PAGE, first) + self.src(PAGE + '.*.id', second))
        self.assertIsNone(self.s.coverage)  # as many distinct records as the total: nothing is said, and never "complete"
        self.s.calc(operation='view', sources=self.src(PAGE + '.0', first))
        self.assertIsNone(self.s.coverage)  # one position of a list is not the list

    def test_the_coverage_of_pages_counts_distinct_records_and_never_says_complete(self):
        """Review finding 1: page lengths added up read two overlapping pages, or two lists of one name and total, as a whole list."""
        first, overlap = self.s.fetch(page(ROWS[:2], total=4, more=True)), self.s.fetch(page(ROWS[1:3], total=4, more=True))
        out, _, _ = self.s.calc(operation='count', sources=self.src(PAGE, first) + self.src(PAGE, overlap))
        self.assertEqual((out['count'], self.s.coverage), (4, 'built from 3 distinct of 4 records at "items", totalCount 4 (1 not among '
                                                              'the sources if pages overlap)'))
        two = [self.s.fetch(page(rows, total=2)) for rows in (ROWS[:2], ROWS[2:])]
        self.s.calc(operation='count', sources=self.src(PAGE, two[0]) + self.src(PAGE, two[1]))
        self.assertEqual(self.s.coverage, 'built from 4 distinct records at "items", more than the totalCount 2 their pages state')
        self.assertEqual(self.s.warnings, [])
        other = self.s.fetch(page([{'person': 'P1'}, {'person': 'P2'}], total=4, more=True))  # another list of the same name and total
        self.s.calc(operation='count', sources=self.src(PAGE, first) + self.src(PAGE, other))
        self.assertEqual(self.s.coverage, 'built from 4 records at "items", as many as totalCount 4, but none of their 2 pages is a last '
                                          'page (hasMore is true in each)')  # other fields may be other fields of the same records
        self.assertNotIn('all of', ht.COVERAGE_RULE + ht.CALCULATE_TOOL['description'])
        self.assertIn('it never says that a list is complete', ht.COVERAGE_RULE)

    def test_pages_at_one_place_that_share_no_record_are_named_and_never_set_apart(self):
        """Third review: two lists of one name, one total and the same record keys, each held in part, added up to the total and
        nothing was said. The path of a page is not the identity of its list: one result holds pages of one list under two keys.
        Fifth review: nor is the place a page states, so such pages are named and not counted as two lists short of their total."""
        first, rest, other = [{'id': 'A1'}, {'id': 'A2'}], [{'id': 'A3'}, {'id': 'A4'}], [{'id': 'B1'}, {'id': 'B2'}]

        def held(rows, **beside):
            return self.src(PAGE, self.s.fetch(json.dumps({'data': {'missionsPage': {'items': rows, 'totalCount': 4, **beside}}})))

        def coverage(sources):
            out, _, error = self.s.calc(operation='count', sources=sources)
            self.assertFalse(error, out)
            return self.s.coverage
        named = ('built from 4 distinct records of 2 pages at "items", as many as totalCount 4, but two of the pages state the same place, '
                 'or are each the last, and share no record')
        for beside in ({'offset': 0}, {'page': 1}, {'hasMore': False}, {'offset': '0', 'hasMore': True}):
            self.assertEqual(coverage(held(first, **beside) + held(other, **beside)), named, beside)
        self.assertEqual(coverage(held(first, offset=0)), 'built from 2 of totalCount 4 at "items" (2 not among the sources)')
        three = held(first, offset=0) + held(other[:1], offset=0)  # short whatever the pages are, and by how much is not known
        self.assertEqual(coverage(three), 'built from 3 of totalCount 4 at "items" (at least 1 not among the sources)')
        self.assertEqual(coverage(held(first, hasMore=True) + held(other, hasMore=True)),
                         'built from 4 distinct records at "items", as many as totalCount 4, but none of their 2 pages is a last page '
                         '(hasMore is true in each)')
        self.assertEqual(coverage(held(first) + held(other)),
                         'built from 4 distinct records of 2 pages at "items", as many as totalCount 4; no page states its place in a list '
                         '(offset, page or hasMore)')
        aliases = self.s.fetch(json.dumps({'data': {'a': {'items': first, 'totalCount': 4}, 'b': {'items': other, 'totalCount': 4}}}))
        two_keys = [{'result_id': aliases, 'path': 'body.data.%s.items' % key} for key in 'ab']
        self.assertEqual(coverage(two_keys), 'built from 4 distinct records of 2 pages at "items", as many as totalCount 4; no page states '
                                             'its place in a list (offset, page or hasMore)')
        # pages of one list: in two results, under two keys of one result, and asked for twice at one place with two lengths
        self.assertIsNone(coverage(held(first, offset=0, hasMore=True) + held(rest, offset=2, hasMore=False)))
        self.assertIsNone(coverage(held(first, page=1) + held(rest, page=2)))
        paged = self.s.fetch(json.dumps({'data': {'p1': {'items': first, 'totalCount': 4, 'hasMore': True},
                                                  'p2': {'items': rest, 'totalCount': 4, 'hasMore': False}}}))
        self.assertIsNone(coverage([{'result_id': paged, 'path': 'body.data.%s.items' % key} for key in ('p1', 'p2')]))
        self.assertEqual(coverage(held(first, offset=0) + held(first + rest[:1], offset=0)),
                         'built from 3 distinct of 5 records at "items", totalCount 4 (1 not among the sources if pages overlap)')
        self.assertIn('a list is short only when all the records of that name are fewer than its total', ht.COVERAGE_RULE)

    def test_a_page_that_states_no_total_is_a_page_of_the_list_whose_total_another_page_states(self):
        """Fourth review, finding 1: pages were grouped by their total, so the later pages of a list that were asked for without it
        stood apart, and a call that held every record was told that records were missing."""
        def held(inner):
            return self.src(PAGE, self.s.fetch(json.dumps({'data': {'missionsPage': inner}})))

        def coverage(sources):
            out, _, error = self.s.calc(operation='count', sources=sources)
            self.assertFalse(error, out)
            return self.s.coverage
        a, b, c, d = ({'id': n} for n in 'abcd')
        first = held({'totalCount': 4, 'hasMore': True, 'items': [a, b]})
        self.assertEqual(coverage(first), 'built from 2 of totalCount 4 at "items" (2 not among the sources)')
        self.assertIsNone(coverage(first + held({'hasMore': False, 'items': [c, d]})))  # the probe: every record is held
        self.assertIsNone(coverage(first + held({'items': [c, d]})))                    # a page may state nothing at all
        self.assertEqual(coverage(first + held({'items': [c]})), 'built from 3 of totalCount 4 at "items" (1 not among the sources)')
        self.assertEqual(coverage(held({'totalCount': 4, 'items': [a, b]}) + held({'items': [c, d]})),
                         'built from 4 distinct records of 2 pages at "items", as many as totalCount 4; no page states its place in a list '
                         '(offset, page or hasMore)')
        aliases = self.s.fetch(json.dumps({'data': {'p1': {'totalCount': 4, 'hasMore': True, 'items': [a, b]}, 'p2': {'items': [c, d]}}}))
        self.assertIsNone(coverage([{'result_id': aliases, 'path': 'body.data.%s.items.*.id' % key} for key in ('p1', 'p2')]))
        # two totals: the records of one list may be the records the other lacks, so only a certain shortfall is said
        four, loose = held({'totalCount': 4, 'items': [a, b]}), held({'items': [c, d]})
        self.assertIsNone(coverage(four + held({'totalCount': 6, 'items': [{'id': 'x'}, {'id': 'y'}]}) + loose))  # six records of six
        self.assertEqual(coverage(four + held({'totalCount': 8, 'items': [{'id': 'x'}, {'id': 'y'}]}) + loose),
                         'built from 2 of totalCount 8 at "items" (at least 2 not among the sources)')

    def test_records_read_as_elements_of_other_lists_of_the_name_may_fill_a_list(self):
        """Fourth review: a shortfall is said only when it is certain. Records that a source reads through deeper lists are not the
        elements of the list its path names, so they may be the records a list of their name is short of; lists of another name are not."""
        a, b, c, d = ({'id': n, 'tags': [n]} for n in 'abcd')
        first = self.src(PAGE, self.s.fetch(json.dumps({'data': {'missionsPage': {'totalCount': 4, 'items': [a, b]}}})))
        short = 'built from 2 of totalCount 4 at "items" (2 not among the sources)'

        def coverage(sources):
            out, _, error = self.s.calc(operation='count', sources=sources)
            self.assertFalse(error, out)
            return self.s.coverage
        nested = self.s.fetch(json.dumps({'data': {'groups': [{'items': [c]}, {'items': [d]}]}}))
        self.assertIsNone(coverage(first + [{'result_id': nested, 'path': 'body.data.groups.*.items'}]))  # they may be the other two
        self.assertIsNone(coverage(first + [{'result_id': nested, 'path': 'body.data.groups.*.items.*.id'}]))
        one = self.s.fetch(json.dumps({'data': {'groups': [{'items': [c]}]}}))
        self.assertEqual(coverage(first + [{'result_id': one, 'path': 'body.data.groups.*.items'}]),
                         'built from 2 of totalCount 4 at "items" (at least 1 not among the sources)')
        self.assertEqual(coverage(first + [{'result_id': nested, 'path': 'body.data.groups'}]), short)  # the groups are not items
        self.assertEqual(coverage(self.src(PAGE + '.*.tags', first[0]['result_id'])), short)            # nor are the tags
        self.assertEqual(coverage(self.src(PAGE + '.*.tags.*', first[0]['result_id'])), short)
        self.assertEqual(coverage(self.src(PAGE + '.*.id', first[0]['result_id'])), short)
        # XML: an element that occurs once is walked through, and the list inside it is the list read
        soap = self.s.fetch('<e><b><r><totalCount>3</totalCount><person><id>P1</id></person><person><id>P2</id></person></r></b></e>',
                            ctype='text/xml')
        for path in ('body.e.b.r.person', 'body.e.b.*.r.person.*.id', 'body.e.*.b.*.r.person'):
            self.s.calc(operation='count', sources=[{'result_id': soap, 'path': path}])
            self.assertEqual(self.s.coverage, 'built from 2 of totalCount 3 at "person" (1 not among the sources)', path)

    def test_records_alike_in_one_page_are_each_counted(self):
        """Fourth review, finding 2: records were counted by their value, so a page read with few of its fields read as short."""
        def coverage(inner, path=PAGE):
            rid = self.s.fetch(json.dumps({'data': {'missionsPage': inner}}))
            out, _, error = self.s.calc(operation='count', sources=self.src(path, rid))
            self.assertFalse(error, out)
            return self.s.coverage
        alike = [{'s': 'A'}, {'s': 'A'}, {'s': 'B'}]
        self.assertIsNone(coverage({'totalCount': 3, 'items': alike}))  # the probe: three records of three
        self.assertEqual(coverage({'totalCount': 5, 'items': alike}), 'built from 3 of totalCount 5 at "items" (2 not among the sources)')
        self.assertEqual(coverage({'totalCount': 2, 'items': alike}), 'built from 3 records at "items", more than the totalCount 2 their '
                                                                      'pages state')
        self.assertEqual(coverage({'hasMore': True, 'items': alike}), 'built from 3 records at "items" and no last page (hasMore is true)')
        pages = [self.s.fetch(json.dumps({'data': {'missionsPage': {'totalCount': 4, 'items': rows}}})) for rows in (alike[:2], alike[1:])]
        self.s.calc(operation='count', sources=self.src(PAGE, pages[0]) + self.src(PAGE, pages[1]))
        self.assertEqual(self.s.coverage, 'built from 4 records of 2 pages at "items", as many as totalCount 4; no page states its place in a '
                                          'list (offset, page or hasMore)')  # alike across pages too: no record is taken for another

    def test_two_selections_of_one_page_are_named_without_a_cause(self):
        """Fourth review, finding 4: the same page asked for with other fields holds other values, which read as records of two lists."""
        def held(rows, **beside):
            return self.src(PAGE, self.s.fetch(json.dumps({'data': {'missionsPage': {'items': rows, 'totalCount': 2, **beside}}})))
        ids, more = [{'id': 1}, {'id': 2}], [{'id': 1, 'status': 'A'}, {'id': 2, 'status': 'B'}]
        self.s.calc(operation='count', sources=held(ids) + held(more))
        self.assertEqual(self.s.coverage, 'built from 2 distinct records of 2 pages at "items", as many as totalCount 2; no page states its '
                                          'place in a list (offset, page or hasMore)')  # the same two records, told by the id both have
        self.assertNotIn('not pages of one list', ht.COVERAGE_RULE + self.s.coverage)
        self.s.calc(operation='count', sources=held(ids) + held([{'name': 'x'}, {'name': 'y'}]))
        self.assertEqual(self.s.coverage, 'built from 4 records at "items", more than the totalCount 2 their pages state')  # no value in common
        self.s.calc(operation='count', sources=held(ids, offset=0) + held(more, offset=0))
        self.assertIsNone(self.s.coverage)  # at one place and sharing no record they are counted apart, and each has its total

    def test_other_fields_of_the_same_records_do_not_make_a_list_short(self):
        """Fifth review, point 2: values that differ show that the returned objects differ, not that the records do. One request gave
        two of four records with their id, another all four with id and status, both at offset 0; the first read as two short."""
        def held(rows, **beside):
            return self.src(PAGE, self.s.fetch(json.dumps({'data': {'missionsPage': {'items': rows, 'totalCount': 4, **beside}}})))

        def coverage(sources):
            out, _, error = self.s.calc(operation='count', sources=sources)
            self.assertFalse(error, out)
            return self.s.coverage
        ids = [{'id': n} for n in (1, 2, 3, 4)]
        whole = [{'id': n, 'status': 'S%d' % n, 'crew': [n]} for n in (1, 2, 3, 4)]
        for sources in (held(ids[:2], offset=0) + held(whole, offset=0), held(whole, offset=0) + held(ids[:2], offset=0)):
            self.assertIsNone(coverage(sources))  # the probe, in either order: the whole list is among the sources
        # no field in common: the records cannot be told apart, so they are counted and nothing is said to be missing
        self.assertEqual(coverage(held(ids[:2], offset=0) + held([{'name': 'n%d' % n} for n in (1, 2, 3, 4)], offset=0)),
                         'built from 6 records at "items", more than the totalCount 4 their pages state')
        # the same list asked for in another order: two pages at offset 0 share no record, which is said and not taken for a shortfall
        self.assertEqual(coverage(held(ids[:2], offset=0, hasMore=True) + held(list(reversed(whole))[:2], offset=0, hasMore=True)
                                  + held(ids[2:], offset=2, hasMore=False)),
                         'built from 4 distinct records of 3 pages at "items", as many as totalCount 4, but two of the pages state the same '
                         'place, or are each the last, and share no record')
        self.assertEqual(coverage(held(ids[:2], offset=0) + held(whole[:1], offset=0)),
                         'built from 2 distinct of 3 records of totalCount 4 at "items" (at least 1 not among the sources)')

    def test_a_list_is_known_by_the_keys_that_lead_to_it(self):
        """Fifth review, point 1: a list under the key "a.b" and a list under the keys "a" and "b" were both kept as body.a.b, so one
        took the place of the other and the order of the sources chose which shortfall was said."""
        rid = self.s.fetch(json.dumps({'a.b': [{'id': 1}, {'id': 2}], 'totalCount': 4, 'a': {'b': [{'id': 9}], 'totalCount': 3}}))
        literal, nested = {'result_id': rid, 'path': 'body.[a.b]'}, {'result_id': rid, 'path': 'body.a.b'}
        parts = ['2 of totalCount 4 at "a.b" (2 not among the sources)', '1 of totalCount 3 at "b" (2 not among the sources)']
        out, _, _ = self.s.calc(operation='count', sources=[literal, nested])
        self.assertEqual((out['count'], self.s.coverage), (3, 'built from ' + ', '.join(parts)))
        out, _, _ = self.s.calc(operation='count', sources=[nested, literal])
        self.assertEqual((out['count'], self.s.coverage), (3, 'built from ' + ', '.join(reversed(parts))))
        self.assertEqual([path for path, _, _, _ in ht._collections(ht.read_text(self.s.wrapped.store.get(rid)))], ['body.[a.b]', 'body.a.b'])
        self.assertEqual(len({ht._identity(keys) for _, _, _, keys in ht._collections(ht.read_text(self.s.wrapped.store.get(rid)))}), 2)
        raw = self.s.fetch(json.dumps({'[x]': [{'id': 1}], 'totalCount': 3}))  # version 4's key, read by the same step
        self.s.calc(operation='count', sources=[{'result_id': raw, 'path': 'body.[x]'}])
        self.assertEqual(self.s.coverage, 'built from 1 of totalCount 3 at "x" (2 not among the sources)')

    def test_what_a_result_was_built_from_stays_with_every_output_built_from_it(self):
        first, second = self.s.fetch(page(ROWS[:2], total=4, more=True)), self.s.fetch(page(ROWS[2:], total=4, more=False))
        partial = 'built from 2 of totalCount 4 at "items" (2 not among the sources)'
        active = {'field': 'status', 'op': 'eq', 'value': 'ACTIVE'}
        _, one, _ = self.s.calc(operation='filter', sources=self.src(PAGE, first), conditions=[active])
        self.assertEqual(self.s.coverage, partial)
        _, counted, _ = self.s.calc(operation='count', sources=[{'result_id': one, 'path': 'records'}])
        self.assertEqual(self.s.coverage, partial)
        self.s.calc(operation='arithmetic', operator='add', operands=[{'result_id': counted, 'path': 'count'}, 1])
        self.assertEqual(self.s.coverage, partial)
        self.s.calc(operation='view', sources=[{'result_id': one, 'path': 'records'}])
        self.assertEqual(self.s.coverage, partial)
        _, two, _ = self.s.calc(operation='filter', sources=self.src(PAGE, second), conditions=[active])
        self.s.calc(operation='union', sources=[{'result_id': one, 'path': 'records.*.id'}, {'result_id': two, 'path': 'records.*.id'}])
        self.assertEqual(self.s.coverage, 'union of sets of 1, 1 values')  # both pages are behind it now: nothing is left to say

    def test_total_and_hasmore_and_an_xml_page_are_read_the_same_way(self):
        total = self.s.fetch(json.dumps({'items': ROWS[:2], 'total': 4}))
        self.s.calc(operation='count', sources=[{'result_id': total, 'path': 'body.items'}])
        self.assertEqual(self.s.coverage, 'built from 2 of total 4 at "items" (2 not among the sources)')
        more = self.s.fetch(json.dumps({'items': ROWS[:2], 'hasMore': True}))
        self.s.calc(operation='count', sources=[{'result_id': more, 'path': 'body.items'}])
        self.assertEqual(self.s.coverage, 'built from 2 distinct records at "items" and no last page (hasMore is true)')
        last = self.s.fetch(json.dumps({'items': ROWS[2:], 'hasMore': False}))
        self.s.calc(operation='count', sources=[{'result_id': more, 'path': 'body.items'}, {'result_id': last, 'path': 'body.items'}])
        self.assertIsNone(self.s.coverage)  # with a last page and no total, nothing is known to be left out
        soap = self.s.fetch('<r><totalCount>3</totalCount><hasMore>true</hasMore><person><id>P1</id></person><person><id>P2</id></person></r>',
                            ctype='text/xml')
        out, _, _ = self.s.calc(operation='distinct', sources=[{'result_id': soap, 'path': 'body.r.person.*.id'}])
        self.assertEqual((out['values'], self.s.coverage), (['P1', 'P2'], 'built from 2 of totalCount 3 at "person" (1 not among the sources)'))
        plain_list = self.s.fetch(json.dumps({'items': ROWS}))
        self.s.calc(operation='count', sources=[{'result_id': plain_list, 'path': 'body.items'}])
        self.assertIsNone(self.s.coverage)  # a list that states no total and no hasMore says nothing of its completeness

    def test_a_shortened_calculate_output_read_again_says_so(self):
        """The audit's P13: a limit or a view page shortens a list below the count beside it."""
        _, limited, _ = self.s.calc(operation='sort', sources=self.src(), field='id', limit=2)
        out, counted, _ = self.s.calc(operation='count', sources=[{'result_id': limited, 'path': 'records'}])
        self.assertEqual((out['count'], self.s.coverage), (2, 'not whole: %s holds 2 of its 4 records' % limited))
        self.s.calc(operation='arithmetic', operator='multiply', operands=[{'result_id': counted, 'path': 'count'}, 2])
        self.assertEqual(self.s.coverage, 'not whole: %s holds 2 of its 4 records' % limited)
        out, viewed, _ = self.s.calc(operation='view', sources=self.src(), limit=3)
        self.assertEqual((len(out['records']), out['nextOffset']), (3, 3))
        self.s.calc(operation='distinct', sources=[{'result_id': viewed, 'path': 'records'}], field='id')
        self.assertEqual(self.s.coverage, 'not whole: %s holds 3 of its 4 records' % viewed)
        _, grouped, _ = self.s.calc(operation='group_by', sources=self.src(), group_by=['status'], limit=1)
        self.s.calc(operation='count', sources=[{'result_id': grouped, 'path': 'groups'}])
        self.assertEqual(self.s.coverage, 'not whole: %s holds 1 of its 3 groups' % grouped)
        _, whole, _ = self.s.calc(operation='sort', sources=self.src(), field='id')
        self.s.calc(operation='count', sources=[{'result_id': whole, 'path': 'records'}])
        self.assertIsNone(self.s.coverage)

    def test_the_coverage_line_is_bounded_and_counts_toward_storing_an_output(self):
        keys = ['k%02d' % i + 'x' * 30 for i in range(40)]
        wide = self.s.fetch(json.dumps([dict({k: 1 for k in keys}, id='A'), {'id': 'B'}]))
        text, error = self.s.wrapped.call('calculate', {'operation': 'sort', 'sources': [{'result_id': wide, 'path': 'body'}], 'field': 'id',
                                                        'fields': keys, 'limit': 1})
        self.assertFalse(error)
        coverage = text.split('\n')[2]
        self.assertEqual((len(coverage), coverage[-3:]), (len('coverage: ') + ht.LIMITS['coverageLineChars'], '...'))
        notes = {'coverage': 'c' * 40, 'warnings': ['w' * 40]}
        self.assertFalse(ht.output_is_stored('x' * 4990, {}))
        self.assertTrue(ht.output_is_stored('x' * 4990, notes))       # the lines count toward storeAboveChars
        self.assertFalse(ht.output_is_stored('x' * 4990, notes, 'view'))  # a view page is sized to be shown in full
        self.assertEqual(ht.note_lines(notes), 'coverage: %s\nwarning: %s\n' % ('c' * 40, 'w' * 40))
        self.assertEqual(ht.note_lines({}), '')

    def test_a_view_page_keeps_its_size_below_its_coverage_line(self):
        paged = self.s.fetch(json.dumps(LONG_PAGE))
        text, error = self.s.wrapped.call('calculate', {'operation': 'view', 'sources': [{'result_id': paged, 'path': 'body.items'}]})
        self.assertFalse(error)
        lines = text.split('\n')
        self.assertEqual(lines[2], 'coverage: built from 60 of totalCount 240 at "items" (180 not among the sources)')
        self.assertNotIn('stored, not shown', text)
        self.assertLessEqual(len(lines[3]), ht.LIMITS['viewPageChars'])
        self.assertGreater(len(lines[3]), ht.LIMITS['viewPageChars'] - 200)  # the page is as full as version 4 made it
        self.assertTrue(read_jsonl(self.s.path)[-1]['shownInFull'])

    def test_the_lines_are_logged_with_the_output(self):
        first = self.s.fetch(page(ROWS[:2], total=4, more=True))
        self.s.fetch(page(ROWS[2:], total=4, more=False))
        _, rid, _ = self.s.calc(operation='distinct', sources=self.src(PAGE, first), field='status')
        entry, details = read_jsonl(self.s.path)[-1], self.s.wrapped.last_details
        self.assertEqual((entry['resultId'], entry['coverageLine'], entry['warnings']), (rid, self.s.coverage, self.s.warnings))
        self.assertEqual((details['coverage'], details['warnings']), (self.s.coverage, self.s.warnings))
        self.assertEqual(len(self.s.warnings), 1)
        self.s.calc(operation='count', sources=self.src())
        entry, details = read_jsonl(self.s.path)[-1], self.s.wrapped.last_details
        self.assertFalse({'coverageLine', 'warnings'} & set(entry))
        self.assertFalse({'coverage', 'warnings'} & set(details))


class WarningTests(Version5Tests):
    """Version 5's warning lines: what only the agent can judge is said, and never refused."""

    def test_a_calculation_that_repeats_one_already_held_names_it(self):
        """The audit's P24."""
        first, rid, _ = self.s.calc(operation='distinct', sources=self.src(), field='status')
        self.assertEqual(self.s.warnings, [])
        again, other, error = self.s.calc(field='status', sources=self.src(), operation='distinct')
        self.assertEqual((again, error, self.s.warnings), (first, False, ['this repeats the calculation that gave %s, which is still held' % rid]))
        self.assertNotEqual(other, rid)
        self.s.calc(operation='distinct', sources=self.src(), field='status')
        self.assertEqual(self.s.warnings, ['this repeats the calculation that gave %s, which is still held' % rid])  # the first one
        self.s.calc(operation='distinct', sources=self.src(), field='crew')
        self.assertEqual(self.s.warnings, [])
        self.refused(operation='distinct', sources=self.src(), field='statuz')
        self.refused(operation='distinct', sources=self.src(), field='statuz')  # a refused call is refused again, not warned

    def test_a_scenario_result_that_is_the_same_as_a_held_one_names_it(self):
        """The audit's P07, for a request that gives the same result again."""
        body = json.dumps(ROWS)
        self.s.fetch(body)
        text, error = self.s.wrapped.call('lookup', {'body': body})
        self.assertEqual((text, error), ('result_id: ab12-3\nwarning: this result is the same as ab12-2, which is still held\n' + mcp_text(body),
                                         False))
        self.assertEqual(read_jsonl(self.s.path)[-1]['warnings'], ['this result is the same as ab12-2, which is still held'])
        self.assertEqual(self.s.wrapped.last_details, {'tool': 'lookup', 'resultId': 'ab12-3',
                                                       'warnings': ['this result is the same as ab12-2, which is still held']})
        long = json.dumps(LONG_PAGE)
        self.s.fetch(long)
        lines = self.s.wrapped.call('lookup', {'body': long})[0].split('\n')
        self.assertEqual(lines[1], 'warning: this result is the same as ab12-4, which is still held')
        self.assertTrue(lines[2].startswith('stored, not shown: '))
        self.assertNotIn('warnings', read_jsonl(self.s.path)[0])  # a first result has none

    def test_a_list_whose_records_are_all_held_already_names_where(self):
        """The audit's P07, for a request that fetches again, with fewer fields, records the run already holds."""
        held = self.s.fetch(json.dumps({'data': {'all': HELD}}))
        fewer = [{'id': r['id'], 'tags': r['tags']} for r in HELD]
        text, _ = self.s.wrapped.call('lookup', {'body': json.dumps({'data': {'a': fewer[:10]}})})
        self.assertEqual(text.split('\n')[1], 'warning: the 10 records at "body.data.a" are already held in %s' % held)
        mixed = fewer[:9] + [{'tags': HELD[9]['tags']}]  # a record with no plain value is looked for in the lists that hold the others
        text, _ = self.s.wrapped.call('lookup', {'body': json.dumps({'data': {'b': mixed}})})
        self.assertIn('warning: the 10 records at "body.data.b" are already held in %s' % held, text)
        for records in (fewer[:9], fewer[:9] + [{'id': 'R9', 'tags': [99]}], [{'tags': r['tags']} for r in HELD[:10]],
                        [dict(r, extra=1) for r in fewer[:10]]):
            text, _ = self.s.wrapped.call('lookup', {'body': json.dumps({'data': {'c': records}})})
            self.assertNotIn('warning: ', text, records[-1])  # fewer than ten, a changed record, no plain value at all, a new field

    def test_held_pages_of_a_list_are_named_with_or_without_a_total_and_other_lists_are_not(self):
        """Fourth review, findings 1 and 5: a held page that states no total is a page left out too, and a list of the same name and
        total with other record keys is another list."""
        def held(inner):
            return self.s.fetch(json.dumps({'data': {'missionsPage': inner}}))
        first = held({'totalCount': 6, 'hasMore': True, 'items': [{'id': 1}, {'id': 2}]})
        second = held({'hasMore': True, 'items': [{'id': 3}, {'id': 4}]})
        held({'totalCount': 6, 'hasMore': True, 'items': [{'name': 'x'}, {'name': 'y'}]})  # another list: other keys
        self.s.calc(operation='count', sources=self.src(PAGE, first))
        self.assertEqual(self.s.coverage, 'built from 2 of totalCount 6 at "items" (4 not among the sources)')
        self.assertEqual(self.s.warnings, ['%s holds 1 more list at "items" with totalCount 6 or no total, not among the sources' % second])

    def test_a_result_that_is_among_the_sources_is_not_called_absent_for_its_other_pages(self):
        """Found by the debug against the live stack: one result held four pages of a list under four keys, a call read one of them,
        and the warning said that the result was not among the sources."""
        rows = [{'id': n} for n in range(6)]
        held = self.s.fetch(json.dumps({'data': {'p%d' % i: {'totalCount': 6, 'hasMore': i < 2, 'items': rows[2 * i:2 * i + 2]} for i in range(3)}}))
        pages = [{'result_id': held, 'path': 'body.data.p%d.items' % i} for i in range(3)]
        self.s.calc(operation='count', sources=pages[:1])
        self.assertEqual(self.s.coverage, 'built from 2 of totalCount 6 at "items" (4 not among the sources)')
        self.assertEqual(self.s.warnings, ['%s holds 2 more lists at "items" with totalCount 6, not among the sources' % held])
        self.s.calc(operation='count', sources=pages[:2])
        self.assertEqual(self.s.warnings, ['%s holds 1 more list at "items" with totalCount 6, not among the sources' % held])
        self.s.calc(operation='count', sources=pages)
        self.assertEqual((self.s.coverage, self.s.warnings), (None, []))

    def test_held_pages_that_are_not_among_the_sources_are_named(self):
        """The audit's P06, where the pages state their total."""
        first, second = self.s.fetch(page(ROWS[:2], total=4, more=True)), self.s.fetch(page(ROWS[2:], total=4, more=False))
        out, _, error = self.s.calc(operation='count', sources=self.src(PAGE, first))
        self.assertEqual((out['count'], error), (2, False))  # warned, never refused
        self.assertEqual(self.s.warnings, ['%s holds 1 more list at "items" with totalCount 4, not among the sources' % second])
        self.s.calc(operation='count', sources=self.src(PAGE, first) + self.src(PAGE, second))
        self.assertEqual(self.s.warnings, [])
        third = self.s.fetch(page(ROWS[:1], total=4, more=True))
        self.s.calc(operation='distinct', sources=self.src(PAGE, second), field='id')
        self.assertEqual(self.s.warnings, ['%s, %s hold 2 more lists at "items" with totalCount 4, not among the sources' % (first, third)])

    def test_held_records_that_the_sources_leave_out_are_named(self):
        """The audit's P06, where nothing states a total: the sources read a second copy of some records of a longer held list."""
        held = self.s.fetch(json.dumps({'data': {'all': HELD}}))
        again = self.s.fetch(json.dumps({'data': {'a': [{'id': r['id'], 'tags': r['tags']} for r in HELD[:10]]}}))
        out, _, error = self.s.calc(operation='distinct', sources=[{'result_id': again, 'path': 'body.data.a.*.id'}])
        self.assertEqual((out['count'], error), (10, False))
        self.assertEqual(self.s.warnings, ['%s holds the 10 records these sources read and 2 more of the same list; it is not among the sources'
                                           % held])
        self.s.calc(operation='distinct', sources=[{'result_id': again, 'path': 'body.data.a.*.id'}, {'result_id': held, 'path': 'body.data.all.*.id'}])
        self.assertEqual(self.s.warnings, [])  # the longer list is among the sources
        self.s.calc(operation='distinct', sources=[{'result_id': held, 'path': 'body.data.all.*.id'}])
        self.assertEqual(self.s.warnings, [])

    def test_conditions_on_fixed_positions_of_a_longer_list_name_the_elements_alternative(self):
        """The audit's P16: version 4 offered elements and still let a filter test positions 0 to 3 of 50."""
        nested = self.s.fetch(json.dumps({'data': {'missions': {'items': NESTED}}}))
        self.assertEqual(self.ids({'field': 'assets.0.asset.status', 'op': 'ne', 'value': 'ACTIVE'}, rid=nested), ['N3', 'N4', 'N5'])
        self.assertEqual(self.s.warnings, ['the conditions test position 0 of "assets", which has up to 50 elements; a condition with elements '
                                           'any or none and the field "assets.*.asset.status" tests every element'])
        self.ids({'field': 'assets.0.asset.status', 'op': 'eq', 'value': 'ACTIVE'}, {'field': 'assets.1.asset.status', 'op': 'eq', 'value': 'ACTIVE'},
                 rid=nested)
        self.assertIn('test positions 0, 1 of "assets", which has up to 50 elements', self.s.warnings[0])
        self.ids({'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'}, rid=nested)
        self.assertEqual(self.s.warnings, [])
        pairs = self.s.fetch(json.dumps([{'id': 'A', 'pair': [1, 2]}, {'id': 'B', 'pair': [3, 4]}]))
        self.ids({'field': 'pair.0', 'op': 'eq', 'value': 1}, {'field': 'pair.1', 'op': 'eq', 'value': 2}, rid=pairs, path='body')
        self.assertEqual(self.s.warnings, [])  # every position of the list is tested

    def test_warnings_are_bounded_in_number_and_length(self):
        notes = self.s.wrapped.calculator._notes({'operation': 'count'}, [], ht._empty_lineage(), ['w' * 500] * 5)
        self.assertEqual([len(w) for w in notes['warnings']], [ht.LIMITS['warningChars']] * ht.LIMITS['maxWarnings'])
        self.assertTrue(all(w.endswith('...') for w in notes['warnings']))


class AgentWithToolsTests(unittest.TestCase):
    """The agent loop with the wrapper: the harness tools count in the tool-call cap and their details go into the transcript."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.events = []
        inner = FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}],
                                {'lookup': lambda a: mcp_text(json.dumps(ROWS))})
        self.session = ht.HarnessToolSession(inner, ['calculate', 'ask_requester'], ht.ResultStore(Path(self.tmp.name) / 'r.jsonl', 'ab12'), 'k')

    def run_task(self, steps, limits=None):
        schema = {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value']}
        budget = Budget('fake', 'fake-model', 1_000_000, {'input': 1, 'cached_read': 1, 'cache_write': 1, 'output': 1}, 'd',
                        Path(self.tmp.name) / 'b.jsonl')
        agent = AgentRun(FakeVendorClient(steps), self.session, budget, limits or Limits(),
                         lambda s: {'score': 1, 'outcome': 'correct', 'tags': []}, self.events.append, Redactor(), sleep=lambda s: None)
        return agent.run({'id': 'X', 'question': 'invented', 'schema': schema})

    def test_harness_tool_calls_count_and_are_logged(self):
        result = self.run_task([turn('', [('a', 'lookup', {}), ('b', 'calculate', {'operation': 'count', 'sources': [{'result_id': 'ab12-1', 'path': 'body'}]})]),
                                turn('', [('c', 'ask_requester', {'question': 'Which?'})]), submit({'value': 'v'})])
        self.assertEqual(result['outcome'], 'correct')
        self.assertEqual(result['toolCalls'], 3)
        tools = [e for e in self.events if e['kind'] == 'tool']
        self.assertEqual([e['harness']['tool'] for e in tools], ['lookup', 'calculate', 'ask_requester'])
        self.assertEqual(tools[1]['harness']['resultIds'], ['ab12-1'])
        self.assertIn('"count": 4', tools[1]['text'])
        self.assertEqual(tools[2]['text'], ht.ASK_TEXT)
        self.assertIn('ask_requester', [n for n in self.events[0]['tools']])

    def test_calls_before_a_submission_in_the_same_turn_run_before_it_is_scored(self):
        seen = []

        def score(submission):
            seen.append([q['question'] for q in self.session.questions])
            return {'score': 1, 'outcome': 'correct', 'tags': []}
        schema = {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value']}
        budget = Budget('fake', 'fake-model', 1_000_000, {'input': 1, 'cached_read': 1, 'cache_write': 1, 'output': 1}, 'd',
                        Path(self.tmp.name) / 'b2.jsonl')
        steps = [turn('', [('a', 'ask_requester', {'question': 'Which?'}), ('s', 'submit_answer', {'value': 'v'}),
                           ('c', 'ask_requester', {'question': 'after'})])]
        result = AgentRun(FakeVendorClient(steps), self.session, budget, Limits(), score, self.events.append, Redactor(),
                          sleep=lambda s: None).run({'id': 'X', 'question': 'invented', 'schema': schema})
        self.assertEqual((result['outcome'], result['toolCalls']), ('correct', 1))
        self.assertEqual(seen, [['Which?']])
        self.assertEqual([q['question'] for q in self.session.questions], ['Which?'])

    def test_a_submission_after_the_cap_in_the_same_turn_still_stands(self):
        steps = [turn('', [('a', 'ask_requester', {'question': 'q1'}), ('b', 'ask_requester', {'question': 'q2'}), ('s', 'submit_answer', {'value': 'v'})])]
        result = self.run_task(steps, limits=Limits(max_tool_calls=1))
        self.assertEqual((result['outcome'], result['toolCalls']), ('correct', 1))

    def test_harness_tool_calls_reach_the_tool_call_cap(self):
        steps = [turn('', [('a', 'ask_requester', {'question': 'q'}), ('b', 'calculate', {'operation': 'count'})]),
                 turn('', [('c', 'ask_requester', {'question': 'q2'})])]
        result = self.run_task(steps, limits=Limits(max_tool_calls=2))
        self.assertEqual((result['outcome'], result['reason'], result['toolCalls']), ('did_not_finish', 'tool_calls', 2))


if __name__ == '__main__':
    unittest.main()
