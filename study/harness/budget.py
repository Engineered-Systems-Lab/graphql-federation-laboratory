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

Each request is priced on its own (decision L1 of the Job study3_openai_long_context). A price entry may hold `long_context`: the rates of
a request whose input total (input + cached read + cache write) is above its `above_input_tokens`, which then apply to the whole request;
every other request, and every request of an entry without them, is priced at the entry's own rates. A request's worst case takes the long
rates when its input estimate is above the threshold, and a reservation never settled takes the long output price when its recorded input
estimate is above it (decision N2; a reservation with no recorded estimate counts its whole reservation as input). Sums are kept per rate
set (`Spend`, `UnsettledSpend`), so a ledger with no long request is priced exactly as it was before the tier existed.

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
    """Dollar estimate of a usage under one rate set (USD per million tokens), with no tier: one request at these rates, or a sum of
    requests that were all priced at them. One request is priced by `request_dollars`, a sum of requests by `Spend`."""
    return (usage.input * price['input'] + usage.cached_read * price['cached_read'] + usage.cache_write * price['cache_write']
            + usage.output * price['output']) / 1_000_000


LONG_CONTEXT = 'long_context'
RATES = ('input', 'cached_read', 'cache_write', 'output')


def long_rates(price):
    """The long-context rates of a price entry, or None when it has none. A malformed tier raises ValueError, so an entry that names one
    is never read as if it had none."""
    tier = price.get(LONG_CONTEXT)
    if tier is None:
        return None
    threshold = tier.get('above_input_tokens') if isinstance(tier, dict) else None
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold <= 0:
        raise ValueError('The long-context rates of a price entry need above_input_tokens, a positive whole number of tokens')
    for rate in RATES:
        value = tier.get(rate)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('The long-context rates of a price entry need a finite non-negative %s rate' % rate)
    return tier


def input_total(usage):
    """The input total of one request: every input token, cached, written to the cache or neither (OpenAI's input_tokens)."""
    return usage.input + usage.cached_read + usage.cache_write


def rates_for(input_tokens, price):
    """The rate set of one request whose input total (or input estimate) is `input_tokens`: the entry's long-context rates when it has
    them and the input is above their threshold, else the entry's own rates."""
    tier = long_rates(price)
    if tier is not None and int(input_tokens) > tier['above_input_tokens']:
        return tier
    return price


def request_dollars(usage, price):
    """The price of one request, in full at the rate set its input total selects."""
    return dollars(usage, rates_for(input_total(usage), price))


class Spend:
    """Settled requests summed per rate set under one price entry: those priced at the entry's own rates and those priced at its
    long-context rates, each request added whole. Its dollars are the sum of `request_dollars` of its requests."""

    def __init__(self, price):
        self.price = price
        self.standard, self.long = Usage(), Usage()

    def add(self, usage):
        (self.standard if rates_for(input_total(usage), self.price) is self.price else self.long).add(usage)

    @property
    def total(self):
        return self.standard.total + self.long.total

    def dollars(self):
        out = dollars(self.standard, self.price)
        if self.long.total:
            out += dollars(self.long, long_rates(self.price))
        return out


def reservation_dollars(tokens, input_tokens, price):
    """One reservation never settled, counted high: all its tokens at the output price of the rate set its recorded input estimate
    selects, or, with no recorded estimate (None), with the whole reservation counted as input for that choice."""
    estimate = tokens if input_tokens is None else input_tokens
    return int(tokens) * rates_for(estimate, price)['output'] / 1_000_000


class UnsettledSpend:
    """Reservations never settled, summed per output price: each at the output price of the rate set its recorded input estimate
    selects, or, with no recorded estimate (None), the whole reservation counted as input for that choice."""

    def __init__(self, price):
        self.price = price
        self.standard, self.long = 0, 0

    def add(self, tokens, input_tokens):
        estimate = tokens if input_tokens is None else input_tokens
        if rates_for(estimate, self.price) is self.price:
            self.standard += int(tokens)
        else:
            self.long += int(tokens)

    @property
    def tokens(self):
        return self.standard + self.long

    def dollars(self):
        out = self.standard * self.price['output'] / 1_000_000
        if self.long:
            out += self.long * long_rates(self.price)['output'] / 1_000_000
        return out


def usage_dollars(usage, request_usage, price):
    """The price of one run record (decision N1 of the Job study3_openai_long_context): each request on its own when the record lists
    them (`requestUsage`), which must sum to its usage; without the list, its summed usage at the entry's own rates, which is exact only
    for an entry without long-context rates, so such an entry refuses. Raises ValueError."""
    if request_usage is None:
        if long_rates(price) is not None:
            raise ValueError('A run record without requestUsage cannot be priced per request under a price entry with long-context rates')
        return dollars(usage, price)
    if not isinstance(request_usage, list):
        raise ValueError('The requestUsage of a run record is a %s, not a list of request usages' % type(request_usage).__name__)
    spend, summed = Spend(price), Usage()
    for number, item in enumerate(request_usage, 1):
        if not isinstance(item, dict):
            raise ValueError('Request %d of the requestUsage of a run record is a %s, not an object' % (number, type(item).__name__))
        for name in TOKEN_CLASSES:
            value = item.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError('Request %d of the requestUsage of a run record needs %s, a non-negative whole number, not %r'
                                 % (number, name, value))
        one = Usage.from_dict(item)
        spend.add(one)
        summed.add(one)
    if summed.as_dict() != usage.as_dict():
        raise ValueError('The requestUsage of a run record sums to %s, not to its usage %s' % (summed.as_dict(), usage.as_dict()))
    return spend.dollars()


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
    """The most one request can cost, at the rate set its input estimate selects: its input at the highest input-side price (input,
    cached read or cache write) and its maximum output at the output price."""
    rates = rates_for(input_tokens, price)
    highest_input = max(rates['input'], rates['cached_read'], rates['cache_write'])
    return (int(input_tokens) * highest_input + int(max_output_tokens) * rates['output']) / 1_000_000


def ledger_dollars(path, price):
    """(dollars, tokens) of one ledger under one price entry, counted high: each settled request at its prices, and every reservation that
    was never settled at the output price its input estimate selects, because the vendor may have billed it."""
    spend, unsettled, reserved = Spend(price), UnsettledSpend(price), {}
    for entry in read_jsonl(path):
        if entry.get('event') == 'reserve':
            reserved[entry['seq']] = entry
        elif entry.get('event') == 'settle':
            reserved.pop(entry['seq'], None)
            spend.add(Usage.from_dict(entry['usage']))
        elif entry.get('event') == 'release':
            reserved.pop(entry['seq'], None)
    for entry in reserved.values():
        unsettled.add(entry['tokens'], entry.get('inputTokens'))
    return spend.dollars() + unsettled.dollars(), spend.total + unsettled.tokens


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
        long_rates(price)  # a malformed long-context tier refuses here, before any request
        self.ledger = Path(ledger_path)
        self.spent = Usage()
        self.spend = Spend(price)  # the same requests, per rate set: the dollars
        self.unsettled = 0
        self.unsettled_spend = UnsettledSpend(price)
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
                self.spend.add(Usage.from_dict(entry['usage']))
                if entry.get('retry'):
                    self.retries += 1
                    self.retry_tokens += Usage.from_dict(entry['usage']).total
            elif entry['event'] == 'release':
                reserved.pop(entry['seq'], None)
        for entry in reserved.values():
            # never settled: the vendor may have billed the whole reservation
            self.unsettled += entry['tokens']
            self.unsettled_spend.add(entry['tokens'], entry.get('inputTokens'))
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
        """The settled requests, each at its prices."""
        return self.spend.dollars()

    def unsettled_dollars(self):
        """This run's reservations that were never settled, at the output price their input estimate selects, as `ledger_dollars` counts
        them for the carry."""
        return self.unsettled_spend.dollars()

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
        self.spend.add(usage)
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
