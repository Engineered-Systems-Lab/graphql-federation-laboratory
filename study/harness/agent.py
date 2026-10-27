"""One agent run: one model attempting one task in one scenario.

The loop is the same for every scenario and model: send the shared system prompt, the task question and the tools (the scenario's MCP tools
plus `submit_answer` with the task's fixed schema), execute the tool calls the model asks for, and stop when the model submits. The answer is
scored automatically by the corpus scorer (no judge). A cap on tool calls, wall-clock time or tokens ends the run as `did_not_finish`, with
everything it spent counted. A budget stop ends it as `budget_stop`, which is not a score: the run is incomplete and a resume repeats it.
A vendor error ends it as `error`; the runner of the block schedule queues it again once and records a second one as `vendor_error`.

The tool session may be the harness's wrapper (harness_tools.py), which adds `calculate` and `ask_requester`: their calls count in the
tool-call cap like any other, and the wrapper's `last_details` of each call goes into the transcript event as `harness`.
"""
import time

from budget import BudgetStop, Usage, estimate_tokens
from study_common import utc_now
from vendors import VendorFatalError, VendorTransientError

SYSTEM_PROMPT = (
    'You answer questions about the legacy systems of the USS Enterprise using only the tools you have. '
    'Work out the answer with the tools, then call submit_answer with it. '
    'If something cannot be determined with your tools, or a service does not answer, say so in the answer instead of guessing. '
    'Finish every task by calling submit_answer exactly once.')

NUDGE = 'You have not called submit_answer. Call submit_answer now with your answer.'

TERMINAL = ('correct', 'wrong_answer', 'format_error', 'silent_guess', 'definition_not_accepted', 'abstained', 'did_not_finish', 'vendor_error')


class Limits:
    """The same for every scenario and model. Set from the pilot (about twice Alpha's worst pilot run)."""

    def __init__(self, max_tool_calls=40, max_wall_seconds=900, max_task_tokens=400_000, max_nudges=2, max_retries=3, retry_backoff_seconds=5.0):
        self.max_tool_calls, self.max_wall_seconds, self.max_task_tokens = max_tool_calls, max_wall_seconds, max_task_tokens
        self.max_nudges, self.max_retries, self.retry_backoff_seconds = max_nudges, max_retries, retry_backoff_seconds

    def as_dict(self):
        return dict(vars(self))


def submit_tool(schema):
    return {'name': 'submit_answer', 'description': 'Submit the final answer to the task. The arguments must fit the schema exactly. '
            'The explanation field is for reading only and is never scored.', 'input_schema': schema}


def request_tokens(system, transcript, tools):
    return estimate_tokens(system) + estimate_tokens(transcript) + estimate_tokens(tools)


class AgentRun:
    """Runs one task. `score` is a function (submission) -> dict from the corpus scorer. `sink(event)` receives every transcript event at once."""

    def __init__(self, client, session, budget, limits, score, sink, redactor, clock=time.monotonic, sleep=time.sleep, run_id='run'):
        self.client, self.session, self.budget, self.limits = client, session, budget, limits
        self.score, self.sink, self.redactor, self.clock, self.sleep, self.run_id = score, sink, redactor, clock, sleep, run_id

    def emit(self, kind, **fields):
        self.sink(self.redactor.deep({'ts': utc_now(), 'kind': kind, **fields}))

    def _request(self, system, transcript, tools, usage):
        """One recorded, costed request with the retries that are allowed; returns a Turn."""
        attempt = 0
        while True:
            seq = self.budget.reserve(self.run_id, request_tokens(system, transcript, tools), self.client.max_output_tokens, label='request')
            began, began_at = self.clock(), utc_now()
            try:
                turn = self.client.create(system, transcript, tools)
            except VendorTransientError as error:
                timing = self._timing(began, began_at)
                # the vendor may have billed part of it: the reservation stays charged as unknown cost, recorded as a retry
                self.budget.settle(seq, Usage(), retry=True, note='transient: ' + self.redactor.text(str(error))[:200], timing=timing)
                attempt += 1
                self.emit('retry', attempt=attempt, error=str(error)[:300], requestSeconds=timing['requestSeconds'])
                if attempt > self.limits.max_retries:
                    raise
                self.sleep(self.limits.retry_backoff_seconds * attempt)
                continue
            except VendorFatalError:
                self.budget.release(seq, note='fatal')
                raise
            turn.timing = self._timing(began, began_at)
            self.budget.settle(seq, turn.usage, note=('after %d retries' % attempt) if attempt else None, timing=turn.timing)
            usage.add(turn.usage)
            return turn

    def _timing(self, began, began_at):
        """The vendor call alone: its start and end (UTC) and its duration on the run clock, with no tool, ledger or scoring time in it."""
        return {'requestStart': began_at, 'requestEnd': utc_now(), 'requestSeconds': round(self.clock() - began, 3)}

    def run(self, task):
        """`task`: {'id', 'question', 'schema', 'expected'}. Returns the result record."""
        started = self.clock()
        usage, tool_calls, turns, nudges = Usage(), 0, 0, 0
        tools = self.session.tools() + [submit_tool(task['schema'])]
        system = task.get('system', SYSTEM_PROMPT)
        transcript = [{'role': 'user', 'text': task['question']}]
        self.emit('start', task=task['id'], tools=[t['name'] for t in tools])
        self.emit('message', role='user', text=task['question'])
        result = {'taskId': task['id'], 'submission': None, 'reason': None}

        def finish(outcome, reason=None, score=None):
            result.update({'outcome': outcome, 'reason': reason, 'elapsedSeconds': round(self.clock() - started, 3), 'turns': turns,
                           'toolCalls': tool_calls, 'usage': usage.as_dict(), 'usageTokens': usage.total, 'score': score})
            self.emit('end', outcome=outcome, reason=reason)
            return result

        try:
            while True:
                if self.clock() - started >= self.limits.max_wall_seconds:
                    return finish('did_not_finish', 'wall_clock')
                if usage.total >= self.limits.max_task_tokens:
                    return finish('did_not_finish', 'tokens')
                turn = self._request(system, transcript, tools, usage)
                turns += 1
                transcript.append({'role': 'assistant', 'text': turn.text, 'tool_calls': turn.tool_calls, 'raw': turn.raw})
                self.emit('message', role='assistant', text=turn.text, toolCalls=turn.tool_calls, usage=turn.usage.as_dict(),
                          stopReason=turn.stop_reason, requestId=turn.request_id, **turn.timing)
                if not turn.tool_calls:
                    nudges += 1
                    if nudges > self.limits.max_nudges:
                        return finish('did_not_finish', 'no_submission')
                    transcript.append({'role': 'user', 'text': NUDGE})
                    self.emit('message', role='user', text=NUDGE)
                    continue
                at = next((i for i, c in enumerate(turn.tool_calls) if c['name'] == 'submit_answer'), None)
                # the calls that come before submit_answer in the same turn run first (an ask_requester call is then in the log the
                # scorer reads); the calls after it are never run
                for call in turn.tool_calls[:at]:
                    if tool_calls >= self.limits.max_tool_calls:
                        if at is not None:
                            break  # the submission still stands; the calls beyond the cap are not run
                        return finish('did_not_finish', 'tool_calls')
                    tool_calls += 1
                    began = self.clock()
                    text, is_error = self.session.call(call['name'], call['arguments'])
                    details = getattr(self.session, 'last_details', None)
                    self.emit('tool', id=call['id'], name=call['name'], arguments=call['arguments'], isError=is_error,
                              resultChars=len(text), seconds=round(self.clock() - began, 3), text=text,
                              **({'harness': details} if details else {}))
                    transcript.append({'role': 'tool', 'call_id': call['id'], 'name': call['name'], 'content': text, 'is_error': is_error})
                if at is not None:
                    submit = turn.tool_calls[at]
                    scored = self.score(submit['arguments'])
                    result['submission'] = submit['arguments']
                    return finish(scored['outcome'], None, scored)
        except BudgetStop as stop:
            self.emit('budget_stop', message=str(stop), budget=stop.snapshot)
            return finish('budget_stop', str(stop))
        except (VendorTransientError, VendorFatalError) as error:
            self.emit('error', error=type(error).__name__, message=str(error)[:500])
            return finish('error', type(error).__name__ + ': ' + str(error)[:300])
