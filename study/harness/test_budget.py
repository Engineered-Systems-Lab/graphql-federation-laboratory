"""Tests of the token budget: reservation before each request, clean stop, ledger, resume, unsettled reservations."""
import tempfile
import unittest
from pathlib import Path

from budget import Budget, BudgetStop, Usage, dollars, estimate_tokens, ledger_dollars, ledger_totals
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


if __name__ == '__main__':
    unittest.main()
