"""Fakes for the harness tests: a scripted vendor client, a scripted stack. No SDK, no key, no network, no real API call."""
from budget import Usage
from vendors import Turn, VendorFatalError, VendorTransientError


class FakeVendorClient:
    """Returns the scripted steps in order. A step is a Turn, an exception instance to raise, or a function (system, transcript, tools) -> step."""

    vendor = 'fake'

    def __init__(self, steps, max_output_tokens=1000, model='fake-model'):
        self.steps, self.max_output_tokens, self.model, self.calls = list(steps), max_output_tokens, model, []

    def create(self, system, transcript, tools):
        self.calls.append((system, [dict(item) for item in transcript], [t['name'] for t in tools]))
        step = self.steps.pop(0)
        if callable(step):
            step = step(system, transcript, tools)
        if isinstance(step, Exception):
            raise step
        return step


def turn(text='', calls=(), usage=(10, 0, 0, 5), stop='end_turn'):
    """A neutral Turn. `calls` are (id, name, arguments). `usage` is (input, cached_read, cache_write, output)."""
    tool_calls = [{'id': i, 'name': n, 'arguments': a} for i, n, a in calls]
    return Turn(text, tool_calls, Usage(*usage), stop, [{'raw': True, 'calls': len(tool_calls)}], 'req-1')


def submit(answer, usage=(10, 0, 0, 5), call_id='c-submit'):
    return turn('', [(call_id, 'submit_answer', answer)], usage)


__all__ = ['FakeVendorClient', 'turn', 'submit', 'VendorFatalError', 'VendorTransientError']
