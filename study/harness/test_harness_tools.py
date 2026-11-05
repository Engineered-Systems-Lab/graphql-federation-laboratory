"""Tests of the two harness tools with a fake tool session: result ids and their store, calculate's generic operations over JSON and XML
results, the refusal of foreign and unknown ids and of any operation that is not on the list, ask_requester's fixed text and log, and the
agent loop counting both tools in the tool-call cap. Invented data only; no stack, key or network."""
import json
import tempfile
import unittest
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
        """(output, result id, error) of a calculate call shown in full; the read line goes to `self.read`."""
        text, error = self.wrapped.call('calculate', arguments)
        self.read = None
        if error:
            return text, None, True
        line, read, body = text.split('\n', 2)
        assert read.startswith('read: '), text
        self.read = read
        return json.loads(body), line.split(': ', 1)[1], False


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
        self.assertTrue(lines[2].startswith('stored, not shown: %d characters.' % len(stored['text'])))
        self.assertGreater(len(stored['text']), ht.LIMITS['storeAboveChars'])
        self.assertLessEqual(len(text), ht.LIMITS['previewChars'] + 500)
        shape = json.loads(lines[3])
        self.assertEqual((shape['count'], shape['records'][0]['id'], shape['records'][1]), (60, 'M0', '... 60 elements in all'))
        self.assertEqual((stored['shownInFull'], stored['readLine']), (False, lines[1]))
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
            body = text.split('\n', 2)[2]
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
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items.*.tags.*": 1 record (2 elements lacked the rest of the path)'
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
        self.assertEqual((described['version'], described['limits']['storeAboveChars'], described['storedResults']), (4, 5000, ht.STORED_RULE))
        self.assertEqual((described['limits']['viewPageChars'], described['readLine']), (5000, ht.READ_RULE))
        self.assertEqual(described['conditionElements'], ht.ELEMENTS_RULE)
        self.assertNotIn('maxOutputChars', described['limits'])
        description = ht.CALCULATE_TOOL['description']
        for words in ('a calculate result included', 'read:', 'does not add the sources up', 'at most 5000', 'nextOffset', 'elements any',
                      'elements none', 'an empty list or a missing field has no values', 'a field with a * segment needs elements any or none'):
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
    """Version 4: a filter condition with elements any or none tests the values at a list path."""

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
        self.assertEqual(self.ids(self.nested, {'field': 'nothing.*.here', 'elements': 'any', 'op': 'ne', 'value': 'x'}), [])
        self.assertEqual(self.ids(self.nested, {'field': 'nothing.*.here', 'elements': 'none', 'op': 'ne', 'value': 'x'}),
                         ['N1', 'N2', 'N3', 'N4', 'N5'])

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
        self.assertEqual(self.ids(self.rows, {'field': 'tags', 'op': 'eq', 'value': 'x'}), [])  # a list compares as no scalar, as before
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
        self.assertEqual(self.ids(broken, {'field': 'absent.*.x', 'elements': 'none', 'op': 'eq', 'value': 'x'}), ['B1'])

    def test_the_read_line_the_output_and_the_stored_output_are_unchanged(self):
        out, _, _ = self.s.calc(operation='filter', sources=[{'result_id': self.nested, 'path': 'body.data.missions.items'}], fields=['id'],
                                conditions=[{'field': 'assets.*.asset.status', 'elements': 'any', 'op': 'ne', 'value': 'ACTIVE'}])
        self.assertEqual(self.s.read, 'read: %s at "body.data.missions.items": 5 records' % self.nested)
        self.assertEqual(out, {'operation': 'filter', 'count': 2, 'records': [{'id': 'N1'}, {'id': 'N5'}]})
        many = self.s.fetch(json.dumps([{'n': i, 'tags': ['a', 'b' if i % 2 else 'c'], 'pad': 'x' * 100} for i in range(400)]))
        text, error = self.s.wrapped.call('calculate', {'operation': 'filter', 'sources': [{'result_id': many, 'path': 'body'}],
                                                        'conditions': [{'field': 'tags', 'elements': 'any', 'op': 'eq', 'value': 'b'}]})
        self.assertFalse(error)
        lines = text.split('\n')
        self.assertEqual(lines[1], 'read: %s at "body": 400 records' % many)
        self.assertTrue(lines[2].startswith('stored, not shown: '))
        stored = json.loads(read_jsonl(self.s.path)[-1]['text'])
        self.assertEqual((stored['count'], len(stored['records']), sorted(stored)), (200, 200, ['count', 'operation', 'records']))

    def test_the_schema_offers_elements_as_an_optional_key_of_a_condition(self):
        condition = ht.CALCULATE_TOOL['input_schema']['properties']['conditions']['items']
        self.assertEqual(condition['properties']['elements'], {'type': 'string', 'enum': ['any', 'none']})
        self.assertEqual((condition['required'], condition['additionalProperties']), (['field', 'op', 'value'], False))
        self.assertEqual(condition['properties']['op']['enum'], list(ht.COMPARISONS))


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
