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
        text, error = self.wrapped.call('calculate', arguments)
        if error:
            return text, None, True
        line, body = text.split('\n', 1)
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

    def test_a_long_output_is_cut_and_marked(self):
        many = self.s.fetch(json.dumps([{'n': i, 'pad': 'x' * 100} for i in range(2000)]))
        out, _, _ = self.s.calc(operation='sort', sources=[{'result_id': many, 'path': 'body'}], field='n')
        self.assertTrue(out['truncated'])
        self.assertEqual(out['count'], 2000)
        self.assertLess(len(json.dumps(out)), ht.LIMITS['maxOutputChars'] + 100)

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
        with self.assertRaisesRegex(ValueError, 'harness_tools'):
            ht.validate(['calculate', 'fetch'])
        with self.assertRaisesRegex(ValueError, 'harness_tools'):
            ht.validate(['calculate', 'calculate'])


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
