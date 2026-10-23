"""The two vendor clients behind one neutral interface.

The agent loop speaks a neutral transcript; each client converts it to its vendor's native function calling and back. SDK retries are
switched off (max_retries=0) so that every retry is the harness's own, recorded and costed. The SDKs are imported only when a real client is
built, so the tests (which use fake clients) need neither SDK nor a key.

Neutral transcript items:
  {'role': 'user', 'text': str}
  {'role': 'assistant', 'text': str, 'tool_calls': [{'id', 'name', 'arguments': dict}], 'raw': <vendor items, replayed verbatim>}
  {'role': 'tool', 'call_id': str, 'name': str, 'content': str, 'is_error': bool}
Neutral tool: {'name', 'description', 'input_schema'}.
"""
import json
import os

from budget import Usage


class VendorTransientError(Exception):
    """A rate limit, a server error or a lost connection: worth a recorded retry."""


class VendorFatalError(Exception):
    """A rejected request (bad key, unknown model, invalid request): no retry."""


class MissingCredentialError(Exception):
    """The environment variable that carries a vendor key is not set. Names the variable, never a value."""


class Turn:
    """One response in neutral form."""

    def __init__(self, text, tool_calls, usage, stop_reason, raw, request_id=None):
        self.text, self.tool_calls, self.usage, self.stop_reason, self.raw, self.request_id = text, tool_calls, usage, stop_reason, raw, request_id


def dump(obj):
    """A plain JSON-able copy of an SDK object (or of a plain dict)."""
    if hasattr(obj, 'model_dump'):
        return obj.model_dump(mode='json', exclude_none=True)
    return json.loads(json.dumps(obj, default=str))


def classify_error(error):
    """Maps an SDK exception to transient or fatal without importing the SDK: by status code and by the exception's class name."""
    status = getattr(error, 'status_code', None)
    name = type(error).__name__
    if status in (408, 409, 429) or (isinstance(status, int) and status >= 500) or name in (
            'APIConnectionError', 'APITimeoutError', 'RateLimitError', 'InternalServerError', 'OverloadedError'):
        return VendorTransientError(str(error))
    return VendorFatalError(str(error))


class AnthropicClient:
    vendor = 'anthropic'
    key_variable = 'ANTHROPIC_API_KEY'

    def __init__(self, model, request, max_output_tokens, sdk=None):
        self.model, self.request, self.max_output_tokens = model, dict(request), max_output_tokens
        self.sdk = sdk if sdk is not None else self._build()

    def _build(self):
        key = os.environ.get(self.key_variable)
        if not key:
            raise MissingCredentialError('%s is not set: start the harness through the launcher (or inject the variable into its process)'
                                         % self.key_variable)
        import anthropic
        return anthropic.Anthropic(api_key=key, max_retries=0)

    def _messages(self, transcript):
        out = []
        for item in transcript:
            if item['role'] == 'user':
                out.append({'role': 'user', 'content': item['text']})
            elif item['role'] == 'assistant':
                out.append({'role': 'assistant', 'content': item['raw']})
            else:
                block = {'type': 'tool_result', 'tool_use_id': item['call_id'], 'content': item['content'], 'is_error': item['is_error']}
                if out and out[-1]['role'] == 'user' and isinstance(out[-1]['content'], list):
                    out[-1]['content'].append(block)
                else:
                    out.append({'role': 'user', 'content': [block]})
        return out

    @staticmethod
    def _with_cache_breakpoint(messages):
        """Prompt caching is opt-in on this API (the other vendor caches by itself): mark the end of the last message, so that each turn of
        the loop reads the earlier turns from the cache. Copies the last message and its last block; the stored transcript is never changed."""
        if not messages:
            return messages
        last = messages[-1]
        blocks = [{'type': 'text', 'text': last['content']}] if isinstance(last['content'], str) else [dict(b) for b in last['content']]
        if not blocks:
            return messages
        blocks[-1]['cache_control'] = {'type': 'ephemeral'}
        return messages[:-1] + [{'role': last['role'], 'content': blocks}]

    def create(self, system, transcript, tools):
        tool_list = [{'name': t['name'], 'description': t['description'], 'input_schema': t['input_schema']} for t in tools]
        try:
            response = self.sdk.messages.create(model=self.model, max_tokens=self.max_output_tokens, system=system,
                                                messages=self._with_cache_breakpoint(self._messages(transcript)), tools=tool_list,
                                                **self.request)
        except Exception as error:  # classified, never swallowed
            raise classify_error(error) from error
        content = [dump(block) for block in response.content]
        text = ''.join(b.get('text', '') for b in content if b.get('type') == 'text')
        calls = [{'id': b['id'], 'name': b['name'], 'arguments': b.get('input') or {}} for b in content if b.get('type') == 'tool_use']
        u = response.usage
        usage = Usage(input=getattr(u, 'input_tokens', 0) or 0, cached_read=getattr(u, 'cache_read_input_tokens', 0) or 0,
                      cache_write=getattr(u, 'cache_creation_input_tokens', 0) or 0, output=getattr(u, 'output_tokens', 0) or 0)
        return Turn(text, calls, usage, getattr(response, 'stop_reason', None), content, getattr(response, 'id', None))


class OpenAIClient:
    """GPT-6.1 Sol: tool calling goes through the Responses API only."""
    vendor = 'openai'
    key_variable = 'OPENAI_API_KEY'

    def __init__(self, model, request, max_output_tokens, sdk=None):
        self.model, self.request, self.max_output_tokens = model, dict(request), max_output_tokens
        self.sdk = sdk if sdk is not None else self._build()

    def _build(self):
        key = os.environ.get(self.key_variable)
        if not key:
            raise MissingCredentialError('%s is not set: start the harness through the launcher (or inject the variable into its process)'
                                         % self.key_variable)
        import openai
        return openai.OpenAI(api_key=key, max_retries=0)

    def _input(self, transcript):
        out = []
        for item in transcript:
            if item['role'] == 'user':
                out.append({'role': 'user', 'content': item['text']})
            elif item['role'] == 'assistant':
                out.extend(item['raw'])
            else:
                content = item['content'] if not item['is_error'] else 'ERROR: ' + item['content']
                out.append({'type': 'function_call_output', 'call_id': item['call_id'], 'output': content})
        return out

    def create(self, system, transcript, tools):
        tool_list = [{'type': 'function', 'name': t['name'], 'description': t['description'], 'parameters': t['input_schema'], 'strict': False}
                     for t in tools]
        try:
            response = self.sdk.responses.create(model=self.model, instructions=system, input=self._input(transcript), tools=tool_list,
                                                 max_output_tokens=self.max_output_tokens, **self.request)
        except Exception as error:
            raise classify_error(error) from error
        items = [dump(item) for item in response.output]
        text = ''.join(part.get('text', '') for item in items if item.get('type') == 'message' for part in item.get('content', [])
                       if part.get('type') == 'output_text')
        calls = []
        for item in items:
            if item.get('type') == 'function_call':
                try:
                    arguments = json.loads(item.get('arguments') or '{}')
                except json.JSONDecodeError:
                    arguments = {'__unparsed_arguments__': item.get('arguments')}
                calls.append({'id': item['call_id'], 'name': item['name'], 'arguments': arguments})
        u = response.usage
        details = getattr(u, 'input_tokens_details', None)
        cached = (getattr(details, 'cached_tokens', 0) if details is not None else 0) or 0
        usage = Usage(input=(getattr(u, 'input_tokens', 0) or 0) - cached, cached_read=cached, output=getattr(u, 'output_tokens', 0) or 0)
        incomplete = getattr(response, 'incomplete_details', None)
        stop = getattr(incomplete, 'reason', None) if incomplete is not None else getattr(response, 'status', None)
        return Turn(text, calls, usage, stop, items, getattr(response, 'id', None))


CLIENTS = {'anthropic': AnthropicClient, 'openai': OpenAIClient}


def build_client(model_id, models_config, sdk=None):
    entry = models_config['models'][model_id]
    return CLIENTS[entry['vendor']](model_id, entry['request'], entry['max_output_tokens'], sdk=sdk)
