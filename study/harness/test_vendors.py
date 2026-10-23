"""Tests of the vendor clients against fake SDK objects: native tool calling both ways, usage classes, error classes, missing keys.

No SDK is imported and nothing is sent anywhere.
"""
import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from vendors import (AnthropicClient, MissingCredentialError, OpenAIClient, VendorFatalError, VendorTransientError, build_client, classify_error)

TOOLS = [{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object', 'properties': {}}}]
CONFIG = json.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models.json'), encoding='utf-8').read())


class Block:
    def __init__(self, **kw):
        self.kw = kw

    def model_dump(self, mode=None, exclude_none=False):
        return dict(self.kw)


class FakeAnthropic:
    def __init__(self, response=None, error=None):
        self.sent, self.response, self.error = [], response, error
        self.messages = NS(create=self.create)

    def create(self, **kwargs):
        self.sent.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeOpenAI:
    def __init__(self, response=None, error=None):
        self.sent, self.response, self.error = [], response, error
        self.responses = NS(create=self.create)

    def create(self, **kwargs):
        self.sent.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class AnthropicTests(unittest.TestCase):
    def test_request_and_response_in_native_form(self):
        response = NS(content=[Block(type='thinking', thinking='t', signature='s'), Block(type='text', text='hi'),
                               Block(type='tool_use', id='tu1', name='lookup', input={'q': 1})],
                      usage=NS(input_tokens=11, cache_read_input_tokens=7, cache_creation_input_tokens=3, output_tokens=5),
                      stop_reason='tool_use', id='msg1')
        sdk = FakeAnthropic(response)
        client = build_client('claude-sonnet-5-5', CONFIG, sdk=sdk)
        turn = client.create('SYS', [{'role': 'user', 'text': 'q'}], TOOLS)
        sent = sdk.sent[0]
        self.assertEqual(sent['model'], 'claude-sonnet-5-5')
        self.assertEqual(sent['thinking'], {'type': 'adaptive'})
        self.assertEqual(sent['output_config'], {'effort': 'medium'})
        self.assertEqual(sent['tools'], [{'name': 'lookup', 'description': 'd', 'input_schema': TOOLS[0]['input_schema']}])
        self.assertEqual(sent['messages'], [{'role': 'user', 'content': [{'type': 'text', 'text': 'q', 'cache_control': {'type': 'ephemeral'}}]}])
        self.assertEqual(turn.tool_calls, [{'id': 'tu1', 'name': 'lookup', 'arguments': {'q': 1}}])
        self.assertEqual(turn.text, 'hi')
        self.assertEqual(turn.usage.as_dict(), {'input': 11, 'cached_read': 7, 'cache_write': 3, 'output': 5})

    def test_the_whole_assistant_turn_is_replayed_and_results_are_grouped(self):
        sdk = FakeAnthropic(NS(content=[], usage=NS(input_tokens=0, output_tokens=0), stop_reason='end_turn', id='m'))
        client = build_client('claude-sonnet-5-5', CONFIG, sdk=sdk)
        raw = [{'type': 'thinking', 'thinking': 't', 'signature': 's'}, {'type': 'tool_use', 'id': 'a', 'name': 'lookup', 'input': {}},
               {'type': 'tool_use', 'id': 'b', 'name': 'lookup', 'input': {}}]
        client.create('S', [{'role': 'user', 'text': 'q'}, {'role': 'assistant', 'text': '', 'tool_calls': [], 'raw': raw},
                            {'role': 'tool', 'call_id': 'a', 'name': 'lookup', 'content': 'ra', 'is_error': False},
                            {'role': 'tool', 'call_id': 'b', 'name': 'lookup', 'content': 'rb', 'is_error': True}], TOOLS)
        messages = sdk.sent[0]['messages']
        self.assertEqual(messages[1], {'role': 'assistant', 'content': raw})
        self.assertEqual([b['tool_use_id'] for b in messages[2]['content']], ['a', 'b'])
        self.assertTrue(messages[2]['content'][1]['is_error'])

    def test_only_the_last_block_carries_the_cache_breakpoint_and_the_transcript_is_not_changed(self):
        sdk = FakeAnthropic(NS(content=[], usage=NS(input_tokens=0, output_tokens=0), stop_reason='end_turn', id='m'))
        client = build_client('claude-sonnet-5-5', CONFIG, sdk=sdk)
        raw = [{'type': 'tool_use', 'id': 'a', 'name': 'lookup', 'input': {}}]
        transcript = [{'role': 'user', 'text': 'q'}, {'role': 'assistant', 'text': '', 'tool_calls': [], 'raw': raw},
                      {'role': 'tool', 'call_id': 'a', 'name': 'lookup', 'content': 'ra', 'is_error': False}]
        client.create('S', transcript, TOOLS)
        messages = sdk.sent[0]['messages']
        marked = [b for m in messages if isinstance(m['content'], list) for b in m['content'] if 'cache_control' in b]
        self.assertEqual(marked, [messages[2]['content'][-1]])
        self.assertEqual(marked[0]['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(raw, [{'type': 'tool_use', 'id': 'a', 'name': 'lookup', 'input': {}}])
        self.assertEqual(transcript[0], {'role': 'user', 'text': 'q'})
        # the next turn marks its own last block and the earlier tool result no longer carries one
        client.create('S', transcript + [{'role': 'assistant', 'text': '', 'tool_calls': [], 'raw': raw},
                                         {'role': 'tool', 'call_id': 'a', 'name': 'lookup', 'content': 'rb', 'is_error': False}], TOOLS)
        again = sdk.sent[1]['messages']
        self.assertEqual(sum('cache_control' in b for m in again if isinstance(m['content'], list) for b in m['content']), 1)
        self.assertIn('cache_control', again[-1]['content'][-1])


class OpenAITests(unittest.TestCase):
    def test_responses_api_with_native_function_calling(self):
        response = NS(output=[Block(type='reasoning', id='rs', encrypted_content='x'),
                              Block(type='function_call', call_id='fc1', name='lookup', arguments='{"q": 2}'),
                              Block(type='message', content=[{'type': 'output_text', 'text': 'hello'}])],
                      usage=NS(input_tokens=100, input_tokens_details=NS(cached_tokens=40), output_tokens=9), status='completed',
                      incomplete_details=None, id='resp1')
        sdk = FakeOpenAI(response)
        client = build_client('gpt-6.1-sol', CONFIG, sdk=sdk)
        turn = client.create('SYS', [{'role': 'user', 'text': 'q'}], TOOLS)
        sent = sdk.sent[0]
        self.assertEqual(sent['model'], 'gpt-6.1-sol')
        self.assertEqual(sent['instructions'], 'SYS')
        self.assertEqual(sent['reasoning'], {'effort': 'medium'})
        self.assertFalse(sent['store'])
        self.assertEqual(sent['tools'][0]['type'], 'function')
        self.assertEqual(turn.tool_calls, [{'id': 'fc1', 'name': 'lookup', 'arguments': {'q': 2}}])
        self.assertEqual(turn.text, 'hello')
        # cached tokens are part of input_tokens for this vendor: counted once, in their own class
        self.assertEqual(turn.usage.as_dict(), {'input': 60, 'cached_read': 40, 'cache_write': 0, 'output': 9})

    def test_function_call_outputs_follow_the_replayed_items(self):
        sdk = FakeOpenAI(NS(output=[], usage=NS(input_tokens=1, input_tokens_details=None, output_tokens=1), status='completed',
                            incomplete_details=None, id='r'))
        client = build_client('gpt-6.1-sol', CONFIG, sdk=sdk)
        raw = [{'type': 'function_call', 'call_id': 'fc1', 'name': 'lookup', 'arguments': '{}'}]
        client.create('S', [{'role': 'user', 'text': 'q'}, {'role': 'assistant', 'text': '', 'tool_calls': [], 'raw': raw},
                            {'role': 'tool', 'call_id': 'fc1', 'name': 'lookup', 'content': 'boom', 'is_error': True}], TOOLS)
        items = sdk.sent[0]['input']
        self.assertEqual(items[1], raw[0])
        self.assertEqual(items[2], {'type': 'function_call_output', 'call_id': 'fc1', 'output': 'ERROR: boom'})

    def test_unparsable_arguments_are_kept_visible(self):
        response = NS(output=[Block(type='function_call', call_id='c', name='lookup', arguments='{oops')],
                      usage=NS(input_tokens=1, input_tokens_details=None, output_tokens=1), status='completed', incomplete_details=None, id='r')
        turn = build_client('gpt-6.1-sol', CONFIG, sdk=FakeOpenAI(response)).create('S', [{'role': 'user', 'text': 'q'}], TOOLS)
        self.assertEqual(turn.tool_calls[0]['arguments'], {'__unparsed_arguments__': '{oops'})


class ErrorTests(unittest.TestCase):
    def test_classification_by_status_and_name_without_the_sdk(self):
        for status in (408, 429, 500, 503):
            self.assertIsInstance(classify_error(_Err(status)), VendorTransientError)
        for status in (400, 401, 404):
            self.assertIsInstance(classify_error(_Err(status)), VendorFatalError)
        self.assertIsInstance(classify_error(type('APIConnectionError', (Exception,), {})('down')), VendorTransientError)

    def test_clients_raise_the_classified_error(self):
        client = build_client('claude-sonnet-5-5', CONFIG, sdk=FakeAnthropic(error=_Err(429)))
        with self.assertRaises(VendorTransientError):
            client.create('S', [{'role': 'user', 'text': 'q'}], TOOLS)

    def test_a_missing_key_is_a_clear_error_that_names_only_the_variable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for model, variable in (('claude-sonnet-5-5', 'ANTHROPIC_API_KEY'), ('gpt-6.1-sol', 'OPENAI_API_KEY')):
                with self.assertRaises(MissingCredentialError) as caught:
                    build_client(model, CONFIG)
                self.assertIn(variable, str(caught.exception))

    def test_the_pinned_models_and_one_fixed_setting_each(self):
        self.assertEqual(sorted(CONFIG['models']), ['claude-sonnet-5-5', 'gpt-6.1-sol'])
        self.assertEqual(CONFIG['models']['claude-sonnet-5-5']['request']['output_config'], {'effort': 'medium'})
        self.assertEqual(CONFIG['models']['gpt-6.1-sol']['request']['reasoning'], {'effort': 'medium'})
        self.assertEqual(set(CONFIG['sdk_pins']), {'anthropic', 'openai', 'mcp'})


class _Err(Exception):
    def __init__(self, status):
        super().__init__('status %s' % status)
        self.status_code = status


if __name__ == '__main__':
    unittest.main()
