"""Token budget of one vendor in one pilot or study run.

The budget is in TOKENS (input not cached, cached read, cache write and output counted apart, never twice). Dollars are derived from a dated
price table and are shown beside the tokens. Before each API request the harness RESERVES room for that request's possible cost (the current
input plus its maximum output); a request that does not fit is a clean BUDGET STOP. Every reservation, settlement and retry is appended to a
ledger file at once, so a stopped or crashed run keeps its cost and a resume starts from what was really spent. A reservation that was never
settled (the process died during a request) is charged at the amount reserved, because the vendor may have billed it.
"""
from pathlib import Path

from study_common import append_jsonl, read_jsonl, utc_now

TOKEN_CLASSES = ('input', 'cached_read', 'cache_write', 'output')


class BudgetStop(Exception):
    """The next request does not fit in the remaining budget. Carries the numbers for the record."""

    def __init__(self, message, snapshot):
        super().__init__(message)
        self.snapshot = snapshot


class Usage:
    """Token counters of one response, in four classes that never overlap: `input` is the uncached input."""

    __slots__ = ('input', 'cached_read', 'cache_write', 'output')

    def __init__(self, input=0, cached_read=0, cache_write=0, output=0):
        self.input, self.cached_read, self.cache_write, self.output = int(input), int(cached_read), int(cache_write), int(output)

    @property
    def total(self):
        return self.input + self.cached_read + self.cache_write + self.output

    def as_dict(self):
        return {name: getattr(self, name) for name in TOKEN_CLASSES}

    def add(self, other):
        for name in TOKEN_CLASSES:
            setattr(self, name, getattr(self, name) + getattr(other, name))

    @classmethod
    def from_dict(cls, data):
        return cls(**{name: data.get(name, 0) for name in TOKEN_CLASSES})


def estimate_tokens(value):
    """A deliberately high estimate of the tokens of a JSON-like value: one token per 3 characters, since JSON and identifiers tokenize densely."""
    import json
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return len(text) // 3 + 1


def dollars(usage, price):
    """Dollar estimate of a usage under one price entry (USD per million tokens)."""
    return (usage.input * price['input'] + usage.cached_read * price['cached_read'] + usage.cache_write * price['cache_write']
            + usage.output * price['output']) / 1_000_000


class Budget:
    def __init__(self, vendor, model, limit_tokens, price, price_date, ledger_path, dollar_ceiling=None):
        if not isinstance(limit_tokens, int) or limit_tokens <= 0:
            raise ValueError('The token budget of %s must be a positive whole number of tokens' % vendor)
        self.vendor, self.model, self.limit = vendor, model, limit_tokens
        self.price, self.price_date, self.dollar_ceiling = price, price_date, dollar_ceiling
        self.ledger = Path(ledger_path)
        self.spent = Usage()
        self.unsettled = 0
        self.retries = 0
        self.retry_tokens = 0
        self._open = None
        self._counter = 0
        self._load()

    # ------------------------------------------------------------------ ledger
    def _load(self):
        reserved = {}
        for entry in read_jsonl(self.ledger):
            self._counter = max(self._counter, entry.get('seq', 0))
            if entry['event'] == 'reserve':
                reserved[entry['seq']] = entry
            elif entry['event'] == 'settle':
                reserved.pop(entry['seq'], None)
                self.spent.add(Usage.from_dict(entry['usage']))
                if entry.get('retry'):
                    self.retries += 1
                    self.retry_tokens += Usage.from_dict(entry['usage']).total
            elif entry['event'] == 'release':
                reserved.pop(entry['seq'], None)
        for entry in reserved.values():
            # never settled: the vendor may have billed the whole reservation
            self.unsettled += entry['tokens']
            append_jsonl(self.ledger, {'event': 'unsettled', 'seq': entry['seq'], 'tokens': entry['tokens'], 'ts': utc_now()})

    def _write(self, entry):
        entry['ts'] = utc_now()
        append_jsonl(self.ledger, entry)

    # ------------------------------------------------------------------ state
    @property
    def used_tokens(self):
        return self.spent.total + self.unsettled

    @property
    def remaining_tokens(self):
        return self.limit - self.used_tokens - (self._open['tokens'] if self._open else 0)

    def estimated_dollars(self):
        return dollars(self.spent, self.price)

    def snapshot(self):
        return {'vendor': self.vendor, 'model': self.model, 'limitTokens': self.limit, 'spent': self.spent.as_dict(),
                'spentTokens': self.spent.total, 'unsettledTokens': self.unsettled, 'remainingTokens': self.remaining_tokens,
                'retries': self.retries, 'retryTokens': self.retry_tokens, 'estimatedDollars': round(self.estimated_dollars(), 4),
                'priceDate': self.price_date}

    # ------------------------------------------------------------------ reserve and settle
    def reserve(self, run_id, input_tokens, max_output_tokens, label='request'):
        """Reserve room for one request: the current input plus the maximum output, all priced as output would be at worst."""
        if self._open is not None:
            raise RuntimeError('A reservation is already open: settle or release it first')
        tokens = int(input_tokens) + int(max_output_tokens)
        if tokens > self.remaining_tokens:
            raise BudgetStop('Budget stop: the request needs %d tokens and %d remain of %d (%s)'
                             % (tokens, self.remaining_tokens, self.limit, self.vendor), self.snapshot())
        if self.dollar_ceiling is not None:
            worst = (int(input_tokens) * self.price['input'] + int(max_output_tokens) * self.price['output']) / 1_000_000
            if self.estimated_dollars() + worst > self.dollar_ceiling:
                raise BudgetStop('Budget stop: the request could cost %.4f dollars on top of %.4f spent, ceiling %.2f (%s)'
                                 % (worst, self.estimated_dollars(), self.dollar_ceiling, self.vendor), self.snapshot())
        self._counter += 1
        self._open = {'seq': self._counter, 'tokens': tokens}
        self._write({'event': 'reserve', 'seq': self._counter, 'run': run_id, 'label': label, 'tokens': tokens,
                     'inputTokens': int(input_tokens), 'maxOutputTokens': int(max_output_tokens)})
        return self._open['seq']

    def settle(self, seq, usage, retry=False, note=None, timing=None):
        """`timing`, when given, is the request's own start, end and seconds; it is stored in the ledger entry and used for nothing else."""
        self._expect(seq)
        self.spent.add(usage)
        if retry:
            self.retries += 1
            self.retry_tokens += usage.total
        self._open = None
        self._write({'event': 'settle', 'seq': seq, 'usage': usage.as_dict(), 'retry': bool(retry), 'note': note, **(timing or {})})

    def release(self, seq, note=None):
        """Give a reservation back when the request is known not to have reached the vendor."""
        self._expect(seq)
        self._open = None
        self._write({'event': 'release', 'seq': seq, 'note': note})

    def _expect(self, seq):
        if self._open is None or self._open['seq'] != seq:
            raise RuntimeError('No such open reservation: %s' % seq)
