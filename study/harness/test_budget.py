"""Tests of the token budget: reservation before each request, clean stop, ledger, resume, unsettled reservations."""
import json
import tempfile
import unittest
from pathlib import Path

from budget import (Budget, BudgetStop, Usage, dollars, estimate_tokens, input_total, ledger_dollars, ledger_totals, long_rates,
                    rates_for, request_dollars, reservation_dollars, usage_dollars, worst_dollars)
from study_common import read_jsonl

PRICE = {'input': 2.0, 'cached_read': 0.2, 'cache_write': 2.5, 'output': 10.0}


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / 'budget.jsonl'

    def make(self, limit=1000, ceiling=None):
        return Budget('v', 'm', limit, PRICE, '2026-10-20', self.ledger, dollar_ceiling=ceiling)

    def test_classes_are_counted_apart_and_never_twice(self):
        b = self.make()
        seq = b.reserve('r', 100, 100)
        b.settle(seq, Usage(input=50, cached_read=30, cache_write=5, output=15))
        snap = b.snapshot()
        self.assertEqual(snap['spent'], {'input': 50, 'cached_read': 30, 'cache_write': 5, 'output': 15})
        self.assertEqual(snap['spentTokens'], 100)
        self.assertAlmostEqual(dollars(b.spent, PRICE), (50 * 2.0 + 30 * 0.2 + 5 * 2.5 + 15 * 10.0) / 1e6)

    def test_reservation_counts_against_the_remaining_room(self):
        b = self.make(limit=500)
        seq = b.reserve('r', 200, 200)
        self.assertEqual(b.remaining_tokens, 100)
        with self.assertRaises(RuntimeError):
            b.reserve('r', 1, 1)
        b.release(seq)
        self.assertEqual(b.remaining_tokens, 500)

    def test_a_request_that_does_not_fit_is_a_clean_budget_stop(self):
        b = self.make(limit=300)
        b.settle(b.reserve('r', 100, 100), Usage(input=100, output=100))
        with self.assertRaises(BudgetStop) as stop:
            b.reserve('r', 60, 60)
        self.assertEqual(stop.exception.snapshot['spentTokens'], 200)
        self.assertEqual(b.spent.total, 200)

    def test_dollar_ceiling_stops_on_the_worst_case_of_the_request(self):
        b = self.make(limit=10_000_000, ceiling=0.01)
        with self.assertRaises(BudgetStop):
            b.reserve('r', 1000, 1000)  # 0.002 + 0.01 > 0.01

    def test_every_event_is_in_the_ledger_and_a_resume_reads_it(self):
        b = self.make()
        b.settle(b.reserve('r1', 10, 10), Usage(input=7, output=3))
        b.settle(b.reserve('r2', 10, 10), Usage(), retry=True, note='transient')
        again = self.make()
        self.assertEqual(again.spent.total, 10)
        self.assertEqual(again.retries, 1)
        self.assertEqual([e['event'] for e in read_jsonl(self.ledger)], ['reserve', 'settle', 'reserve', 'settle'])

    def test_a_reservation_never_settled_is_charged_in_full_on_resume(self):
        b = self.make(limit=1000)
        b.reserve('r', 300, 100)  # the process dies here
        again = self.make(limit=1000)
        self.assertEqual(again.unsettled, 400)
        self.assertEqual(again.remaining_tokens, 600)
        self.assertEqual(again.snapshot()['unsettledTokens'], 400)
        third = self.make(limit=1000)  # the unsettled amount is not charged twice
        self.assertEqual(third.remaining_tokens, 600 - 0)

    def test_the_budget_must_be_explicit(self):
        for bad in (0, -5, 1.5, None):
            with self.assertRaises(ValueError):
                Budget('v', 'm', bad, PRICE, 'd', self.ledger)
        # no token limit: the dollar ceiling is the only stop, so it must be there and able to stop (JSON reads 1e309 as infinity)
        for ceiling in (None, 0, -1.0, True, float('nan'), float('inf'), json.loads('1e309'), json.loads('NaN'),
                        json.loads('1' + '0' * 400)):  # the last is a whole number too large for a float
            with self.assertRaisesRegex(ValueError, 'without a token limit needs a finite positive dollar ceiling'):
                Budget('v', 'm', None, PRICE, 'd', self.ledger, dollar_ceiling=ceiling)

    # ------------------------------------------------------------------ no token limit (a scheduled run, decision T1 (a))
    def test_without_a_token_limit_only_the_dollar_ceiling_stops(self):
        b = self.make(limit=None, ceiling=1.0)
        for _ in range(20):  # 20 x 2,000 reserved tokens, far past any former token limit of this file; 20 x 0.0125 dollars at worst fit
            b.settle(b.reserve('r', 1000, 1000), Usage(input=1000, output=1000))
        self.assertEqual(b.spent.total, 40_000)
        self.assertIsNone(b.remaining_tokens)
        self.assertAlmostEqual(b.estimated_dollars(), 20 * 0.012)
        with self.assertRaisesRegex(BudgetStop, 'could cost 1.0025 dollars on top of 0.2400 spent, ceiling 1.00') as stop:
            b.reserve('r', 1000, 100_000)  # worst case 0.0025 (input at the cache-write price) + 1.0 dollars passes the ceiling
        self.assertEqual(stop.exception.snapshot['spentTokens'], 40_000)
        self.assertEqual(len(read_jsonl(self.ledger)), 40, 'a refused request writes nothing to the ledger')

    def test_without_a_token_limit_the_ledger_and_the_spent_tokens_are_as_before(self):
        def drive(budget):
            budget.settle(budget.reserve('r1', 100, 100), Usage(input=50, cached_read=30, cache_write=5, output=15))
            budget.settle(budget.reserve('r2', 10, 10), Usage(input=4), retry=True, note='transient')
            budget.release(budget.reserve('r3', 10, 10), note='never sent')
            budget.reserve('r4', 300, 100)  # the process dies here
        limited_ledger, self.ledger = self.ledger, Path(self.tmp.name) / 'unlimited.jsonl'
        drive(Budget('v', 'm', 10_000, PRICE, '2026-10-20', limited_ledger, dollar_ceiling=1.0))
        drive(self.make(limit=None, ceiling=1.0))
        strip = lambda path: [{k: v for k, v in e.items() if k != 'ts'} for e in read_jsonl(path)]
        self.assertEqual(strip(self.ledger), strip(limited_ledger))
        limited = Budget('v', 'm', 10_000, PRICE, '2026-10-20', limited_ledger, dollar_ceiling=1.0).snapshot()
        unlimited = self.make(limit=None, ceiling=1.0).snapshot()  # the resume charges the unsettled reservation, as before
        self.assertEqual(strip(self.ledger), strip(limited_ledger))
        self.assertEqual((unlimited['spentTokens'], unlimited['unsettledTokens'], unlimited['retries'], unlimited['retryTokens']),
                         (104, 400, 1, 4))
        self.assertNotIn('limitTokens', unlimited)
        self.assertNotIn('remainingTokens', unlimited)
        self.assertEqual({k: v for k, v in limited.items() if k not in ('limitTokens', 'remainingTokens')}, unlimited)

    def test_a_resume_counts_its_own_unsettled_reservations_against_the_ceiling(self):
        b = self.make(limit=None, ceiling=0.02)
        b.reserve('r', 0, 2000)  # 0.02 dollars at the output price; the process dies here
        again = self.make(limit=None, ceiling=0.02)
        self.assertEqual(again.unsettled, 2000)
        self.assertAlmostEqual(again.unsettled_dollars(), ledger_dollars(self.ledger, PRICE)[0])
        with self.assertRaisesRegex(BudgetStop, 'could cost 0.0010 dollars on top of 0.0000 spent, 0.0200 in unsettled reservations, '
                                                'ceiling 0.02'):
            again.reserve('r', 0, 100)
        fits = self.make(limit=None, ceiling=0.0211)  # the unsettled 0.02 plus this request's 0.001 fit under 0.0211
        fits.release(fits.reserve('r', 0, 100))

    def test_the_worst_case_prices_the_input_at_the_highest_input_side_price(self):
        self.assertAlmostEqual(worst_dollars(1000, 0, PRICE), 1000 * 2.5 / 1e6, msg='a cache write costs more than plain input')
        self.assertAlmostEqual(worst_dollars(1000, 0, {**PRICE, 'cached_read': 3.0}), 1000 * 3.0 / 1e6)
        ceiling = 0.01225  # between the request at the input price (0.012) and as a cache write (0.0125)
        b = self.make(limit=None, ceiling=ceiling)
        with self.assertRaises(BudgetStop):
            b.reserve('r', 1000, 1000)
        self.assertGreater(dollars(Usage(cache_write=1000, output=1000), PRICE), ceiling, 'it would have settled past the ceiling')
        self.assertEqual(read_jsonl(self.ledger), [])

    def test_estimate_is_a_high_estimate(self):
        self.assertGreaterEqual(estimate_tokens('x' * 300), 100)

    def test_a_ledger_is_read_without_writing_and_counted_high(self):
        b = self.make()
        seq = b.reserve('r', 100, 100)
        b.settle(seq, Usage(input=50, output=10))
        seq = b.reserve('r', 100, 100)
        b.release(seq)
        b.reserve('r', 300, 100)  # never settled: the process died during the request
        before = self.ledger.read_bytes()
        spent, unsettled = ledger_totals(self.ledger)
        self.assertEqual((spent.as_dict(), unsettled), ({'input': 50, 'cached_read': 0, 'cache_write': 0, 'output': 10}, 400))
        money, tokens = ledger_dollars(self.ledger, PRICE)
        self.assertAlmostEqual(money, (50 * 2.0 + 10 * 10.0 + 400 * 10.0) / 1e6)
        self.assertEqual(tokens, 460)
        self.assertEqual(self.ledger.read_bytes(), before, 'reading an earlier run writes nothing into its ledger')

    def test_carried_dollars_count_against_the_ceiling(self):
        b = Budget('v', 'm', 10_000_000, PRICE, 'd', self.ledger, dollar_ceiling=1.0, carried_dollars=0.999)
        with self.assertRaisesRegex(BudgetStop, 'carried from earlier study runs'):
            b.reserve('r', 100, 100)
        snap = b.snapshot()
        self.assertEqual((snap['carriedDollars'], snap['dollarCeiling']), (0.999, 1.0))
        self.assertNotIn('carriedDollars', self.make().snapshot(), 'without a carry the snapshot keeps its study-1 shape')
        Budget('v', 'm', 10_000_000, PRICE, 'd', self.ledger, dollar_ceiling=1.0, carried_dollars=0.5).reserve('r', 100, 100)


TABLE = json.loads((Path(__file__).resolve().parent / 'prices-20261121.json').read_text(encoding='utf-8'))
GPT = TABLE['models']['gpt-6.1-sol']
CLAUDE = TABLE['models']['claude-sonnet-5-5']


class LongContextTests(unittest.TestCase):
    """Decisions L1 to L3 and N2 of the Job study3_openai_long_context: a gpt-6.1-sol request whose input total is above 272,000 tokens is
    priced in full at the long-context rates, each request on its own; Claude's entry has no tier."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / 'budget.jsonl'

    def test_the_table_holds_the_long_rates_and_the_threshold_of_gpt_and_none_for_claude(self):
        self.assertEqual({k: v for k, v in long_rates(GPT).items() if k != 'source'},
                         {'above_input_tokens': 272000, 'input': 4.0, 'cached_read': 0.2, 'cache_write': 5.0, 'output': 15.0})
        self.assertIsNone(long_rates(CLAUDE))
        self.assertIn('platform.claude.com/docs/en/about-claude/pricing', CLAUDE['source'])

    def test_a_request_just_under_the_threshold_is_standard_and_one_just_over_is_long_in_full(self):
        # the input total counts every input class: 200,000 + 70,000 + 2,000 = 272,000 is not above the threshold
        under = Usage(input=200_000, cached_read=70_000, cache_write=2_000, output=1_000)
        over = Usage(input=200_001, cached_read=70_000, cache_write=2_000, output=1_000)
        self.assertEqual(input_total(under), 272_000)
        self.assertAlmostEqual(request_dollars(under, GPT), (200_000 * 2.0 + 70_000 * 0.1 + 2_000 * 2.5 + 1_000 * 10.0) / 1e6)
        self.assertAlmostEqual(request_dollars(over, GPT), (200_001 * 4.0 + 70_000 * 0.2 + 2_000 * 5.0 + 1_000 * 15.0) / 1e6,
                               msg='the whole request, output included, at the long rates')
        self.assertIs(rates_for(272_000, GPT), GPT)
        self.assertIs(rates_for(272_001, GPT), GPT['long_context'])

    def test_the_worst_case_of_a_request_above_the_threshold_uses_the_long_rates(self):
        self.assertAlmostEqual(worst_dollars(272_000, 1_000, GPT), (272_000 * 2.5 + 1_000 * 10.0) / 1e6)
        self.assertAlmostEqual(worst_dollars(272_001, 1_000, GPT), (272_001 * 5.0 + 1_000 * 15.0) / 1e6)
        ceiling = 1.5  # above the standard worst case of a 300,000-token request (0.79) and below its long one (1.56)
        budget = Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=ceiling)
        budget.release(budget.reserve('r', 250_000, 10_000))
        with self.assertRaisesRegex(BudgetStop, 'could cost 1.5600 dollars'):
            budget.reserve('r', 300_000, 4_000)

    def test_a_ledger_mixing_both_kinds_of_request_is_priced_per_request(self):
        short = [Usage(input=100_000, cached_read=50_000, cache_write=1_000, output=2_000), Usage(input=10_000, output=500)]
        long = [Usage(input=150_000, cached_read=150_000, cache_write=0, output=3_000)]
        budget = Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=100.0)
        for usage in short[:1] + long + short[1:]:
            budget.settle(budget.reserve('r', input_total(usage), 4_000), usage)
        expected = sum(request_dollars(u, GPT) for u in short + long)
        flat = sum(dollars(u, GPT) for u in short + long)
        self.assertGreater(expected, flat + 0.3, 'the long request costs more than at the standard rates')
        self.assertAlmostEqual(budget.estimated_dollars(), expected, places=12)
        self.assertAlmostEqual(ledger_dollars(self.ledger, GPT)[0], expected, places=12)
        again = Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=100.0)
        self.assertAlmostEqual(again.estimated_dollars(), expected, places=12, msg='a resume reads the ledger per request')
        self.assertEqual(again.snapshot()['estimatedDollars'], round(expected, 4))

    def test_without_a_long_request_a_ledger_is_priced_exactly_as_before(self):
        budget = Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=100.0)
        usages = [Usage(input=1234 * i, cached_read=777 * i, cache_write=55 * i, output=99 * i) for i in range(1, 30)]
        for usage in usages:
            budget.settle(budget.reserve('r', 10, 10), usage)
        summed = Usage()
        for usage in usages:
            summed.add(usage)
        self.assertEqual(budget.estimated_dollars(), dollars(summed, GPT), 'bit for bit the summed usage at the standard rates')
        self.assertEqual(ledger_dollars(self.ledger, GPT)[0], dollars(summed, GPT))

    def test_claude_is_priced_the_same_at_any_size(self):
        for size in (1_000, 272_000, 272_001, 900_000):
            usage = Usage(input=size // 2, cached_read=size // 4, cache_write=size - size // 2 - size // 4, output=5_000)
            self.assertEqual(request_dollars(usage, CLAUDE), dollars(usage, CLAUDE))
            self.assertEqual(worst_dollars(size, 5_000, CLAUDE), (size * 2.5 + 5_000 * 10.0) / 1e6)

    def test_a_reservation_never_settled_takes_the_output_price_its_input_estimate_selects(self):
        budget = Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=100.0)
        budget.reserve('r', 272_000, 8_000)  # never settled: 280,000 tokens at 10.00
        budget._open = None
        budget.reserve('r', 272_001, 8_000)  # never settled: 280,001 tokens at 15.00
        with open(self.ledger, 'a', encoding='utf-8', newline='\n') as handle:  # an older reserve event with no input estimate
            handle.write(json.dumps({'event': 'reserve', 'seq': 9, 'run': 'r', 'label': 'request', 'tokens': 300_000}) + '\n')
        expected = (280_000 * 10.0 + 280_001 * 15.0 + 300_000 * 15.0) / 1e6
        self.assertAlmostEqual(ledger_dollars(self.ledger, GPT)[0], expected)
        self.assertAlmostEqual(Budget('openai', 'gpt-6.1-sol', None, GPT, TABLE['dated'], self.ledger, dollar_ceiling=100.0).unsettled_dollars(),
                               expected)
        self.assertEqual(reservation_dollars(300_000, None, GPT), 300_000 * 15.0 / 1e6)
        self.assertEqual(reservation_dollars(300_000, 100_000, GPT), 300_000 * 10.0 / 1e6)

    def test_a_run_record_is_priced_from_its_requests_and_refused_without_them_under_a_tier(self):
        requests = [{'input': 280_000, 'cached_read': 0, 'cache_write': 0, 'output': 100}, {'input': 1_000, 'cached_read': 0, 'cache_write': 0,
                                                                                            'output': 100}]
        usage = Usage(input=281_000, output=200)
        self.assertAlmostEqual(usage_dollars(usage, requests, GPT), sum(request_dollars(Usage.from_dict(r), GPT) for r in requests))
        with self.assertRaisesRegex(ValueError, 'sums to'):
            usage_dollars(Usage(input=1), requests, GPT)
        with self.assertRaisesRegex(ValueError, 'without requestUsage'):
            usage_dollars(usage, None, GPT)
        self.assertEqual(usage_dollars(usage, None, CLAUDE), dollars(usage, CLAUDE), 'no tier: the summed usage is exact')

    def test_a_malformed_request_list_is_refused_with_a_value_error(self):
        whole = {'input': 1, 'cached_read': 0, 'cache_write': 0, 'output': 1}
        for request_usage, message in ((7, 'not a list'), ('x', 'not a list'), ({'input': 1}, 'not a list'), ([3], 'not an object'),
                                       ([None], 'not an object'), ([{**whole, 'input': None}], 'input, a non-negative'),
                                       ([{**whole, 'output': 1.5}], 'output, a non-negative'), ([{**whole, 'output': True}], 'output'),
                                       ([{**whole, 'cached_read': -1}], 'cached_read'), ([{'input': 1, 'output': 1}], 'cached_read')):
            with self.subTest(request_usage=request_usage), self.assertRaisesRegex(ValueError, message):
                usage_dollars(Usage(input=1, output=1), request_usage, GPT)

    def test_a_malformed_tier_is_refused(self):
        for tier in ({'input': 4.0}, {**GPT['long_context'], 'above_input_tokens': 0}, {**GPT['long_context'], 'output': float('nan')}):
            with self.assertRaises(ValueError):
                Budget('openai', 'gpt-6.1-sol', None, {**GPT, 'long_context': tier}, 'd', self.ledger, dollar_ceiling=1.0)


if __name__ == '__main__':
    unittest.main()
