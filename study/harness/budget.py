"""Budget of one vendor in one pilot or study run.

The tokens are counted in four classes (input not cached, cached read, cache write and output), never twice, and dollars are derived from
a dated price table. Before each API request the harness RESERVES room for that request's possible cost (the current input plus its
maximum output); a request that does not fit is a clean BUDGET STOP. What it must fit in depends on the shape of the run:

- under a schedule (study 2 and later) the only overall stop is the DOLLAR CEILING, and the budget has no token limit (`limit_tokens` is
  None; decision T1 (a) of the Job study_budget_dollars_only). The tokens are still counted, written to the ledger and reported;
- without a schedule (the study-1 shape) the budget is in TOKENS, a positive whole number, and that token limit is its only stop.

Every reservation, settlement and retry is appended to a ledger file at once, so a stopped or crashed run keeps its cost and a resume starts
from what was really spent. A reservation that was never settled (the process died during a request) is charged at the amount reserved,
because the vendor may have billed it: in tokens against a token limit, and at the output price against a dollar ceiling, as
`ledger_dollars` counts it.

The dollar ceiling is a finite positive number. A request's worst case prices its input at the highest input-side price of the entry (a
cache write costs more than plain input, and the Claude client asks for prompt caching) and its maximum output at the output price.

Study 2's dollar ceiling is for all of study 2 (decision F1 of the Job study2_build_followups): the dollars that earlier study runs spent
(`carried_dollars`, read from their ledgers by `ledger_dollars`) count against the ceiling before the first request of this run.
"""
import math
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


def ledger_totals(path):
    """What one ledger file records as spent, read only (nothing is appended): the settled usage and the tokens of the reservations that
    were never settled or released. Returns (Usage, unsettled tokens)."""
    spent, reserved = Usage(), {}
    for entry in read_jsonl(path):
        if entry.get('event') == 'reserve':
            reserved[entry['seq']] = entry
        elif entry.get('event') == 'settle':
            reserved.pop(entry['seq'], None)
            spent.add(Usage.from_dict(entry['usage']))
        elif entry.get('event') == 'release':
            reserved.pop(entry['seq'], None)
    return spent, sum(int(entry['tokens']) for entry in reserved.values())


def valid_ceiling(value):
    """True for a dollar ceiling that can stop a run: a finite positive number (not a bool, NaN or infinity, which JSON gives for 1e309,
    and not a whole number too large for a float, which JSON gives for a long run of digits)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except OverflowError:
        return False
    return math.isfinite(number) and number > 0


def worst_dollars(input_tokens, max_output_tokens, price):
    """The most one request can cost: its input at the highest input-side price (input, cached read or cache write) and its maximum output
    at the output price."""
    highest_input = max(price['input'], price['cached_read'], price['cache_write'])
    return (int(input_tokens) * highest_input + int(max_output_tokens) * price['output']) / 1_000_000


def ledger_dollars(path, price):
    """(dollars, tokens) of one ledger under one price entry, counted high: the settled usage at its prices, and every reservation that
    was never settled at the output price, because the vendor may have billed it."""
    spent, unsettled = ledger_totals(path)
    return dollars(spent, price) + unsettled * price['output'] / 1_000_000, spent.total + unsettled


class Budget:
    def __init__(self, vendor, model, limit_tokens, price, price_date, ledger_path, dollar_ceiling=None, carried_dollars=None):
        """`limit_tokens` None: no token limit, and then the dollar ceiling, which must be given, is the only stop (a scheduled run)."""
        if limit_tokens is None:
            if not valid_ceiling(dollar_ceiling):
                raise ValueError('A budget of %s without a token limit needs a finite positive dollar ceiling: the ceiling is its only stop'
                                 % vendor)
        elif not isinstance(limit_tokens, int) or limit_tokens <= 0:
            raise ValueError('The token budget of %s must be a positive whole number of tokens' % vendor)
        self.vendor, self.model, self.limit = vendor, model, limit_tokens
        self.price, self.price_date, self.dollar_ceiling = price, price_date, dollar_ceiling
        self.carried_dollars = carried_dollars  # None: nothing carried (the study-1 shape of the snapshot is kept)
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
        """None when the budget has no token limit."""
        if self.limit is None:
            return None
        return self.limit - self.used_tokens - (self._open['tokens'] if self._open else 0)

    def estimated_dollars(self):
        return dollars(self.spent, self.price)

    def unsettled_dollars(self):
        """This run's reservations that were never settled, at the output price, as `ledger_dollars` counts them for the carry."""
        return self.unsettled * self.price['output'] / 1_000_000

    def snapshot(self):
        out = {'vendor': self.vendor, 'model': self.model, 'limitTokens': self.limit, 'spent': self.spent.as_dict(),
               'spentTokens': self.spent.total, 'unsettledTokens': self.unsettled, 'remainingTokens': self.remaining_tokens,
               'retries': self.retries, 'retryTokens': self.retry_tokens, 'estimatedDollars': round(self.estimated_dollars(), 4),
               'priceDate': self.price_date}
        if self.limit is None:  # no token limit: the spent and unsettled tokens are reported, no limit and no room
            del out['limitTokens'], out['remainingTokens']
        if self.carried_dollars is not None:
            out.update({'carriedDollars': round(self.carried_dollars, 4), 'dollarCeiling': self.dollar_ceiling})
        return out

    # ------------------------------------------------------------------ reserve and settle
    def reserve(self, run_id, input_tokens, max_output_tokens, label='request'):
        """Reserve room for one request: the current input plus the maximum output. Against a dollar ceiling the request is priced at its
        worst (`worst_dollars`) on top of the carried dollars, the settled spend and this run's unsettled reservations."""
        if self._open is not None:
            raise RuntimeError('A reservation is already open: settle or release it first')
        tokens = int(input_tokens) + int(max_output_tokens)
        if self.limit is not None and tokens > self.remaining_tokens:
            raise BudgetStop('Budget stop: the request needs %d tokens and %d remain of %d (%s)'
                             % (tokens, self.remaining_tokens, self.limit, self.vendor), self.snapshot())
        if self.dollar_ceiling is not None:
            worst = worst_dollars(input_tokens, max_output_tokens, self.price)
            carried = self.carried_dollars or 0.0
            unsettled = self.unsettled_dollars()
            if carried + self.estimated_dollars() + unsettled + worst > self.dollar_ceiling:
                raise BudgetStop('Budget stop: the request could cost %.4f dollars on top of %.4f spent%s%s, ceiling %.2f (%s)'
                                 % (worst, self.estimated_dollars(),
                                    ', %.4f in unsettled reservations' % unsettled if unsettled else '',
                                    ' and %.4f carried from earlier study runs' % carried if carried else '',
                                    self.dollar_ceiling, self.vendor), self.snapshot())
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
