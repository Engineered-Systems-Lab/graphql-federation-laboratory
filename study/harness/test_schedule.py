"""Tests of the study-2 block schedule against the design page's Williams square: balance of positions and of predecessors, the halves on
their pairs of rows, the model split, the order inside a block, the reference block last, and the same seed giving the same schedule.
Invented task ids only; no corpus, stack or key."""
import itertools
import unittest
from collections import Counter

import schedule

MODELS = ['claude-sonnet-5-5', 'gpt-6.1-sol']
ARMS = ['beta', 'gamma', 'delta', 'epsilon']
SCENARIOS = {name: {} for name in ARMS + ['alpha']}
# 48 core tasks in the design page's categories and sizes, plus 6 in the ambiguity set; ids and systems are invented
CORE = [('A', 'small', 6), ('B', 'small', 6), ('B', 'medium', 4), ('C', 'small', 5), ('C', 'medium', 3), ('P', 'medium', 3), ('P', 'large', 3),
        ('E', 'small', 3), ('E', 'medium', 4), ('E', 'large', 3), ('D', 'small', 4), ('D', 'medium', 4)]


def tasks():
    out, n = [], 0
    for category, size, count in CORE:
        for i in range(count):
            n += 1
            out.append({'id': 'X%02d' % n, 'category': category, 'size': size, 'systems': [['missions'], ['assets', 'missions']][i % 2]})
    for i in range(6):
        n += 1
        out.append({'id': 'X%02d' % n, 'category': 'F', 'set': 'ambiguity', 'size': 'small', 'systems': ['personnel']})
    return out


def config(seed=20261027):
    return {'seed': seed, 'models': list(MODELS), 'schedule': {'design': 'williams-4-half', 'arms': list(ARMS), 'reference': 'alpha'}}


class SquareTests(unittest.TestCase):
    def test_every_letter_stands_once_in_every_position(self):
        for column in range(4):
            self.assertEqual(sorted(row[column] for row in schedule.SQUARE), list(schedule.LETTERS))
        for row in schedule.SQUARE:
            self.assertEqual(sorted(row), list(schedule.LETTERS))

    def test_each_letter_directly_follows_each_other_letter_exactly_once(self):
        pairs = [(row[i], row[i + 1]) for row in schedule.SQUARE for i in range(3)]
        self.assertEqual(len(pairs), 12)
        self.assertEqual(set(pairs), {(x, y) for x in schedule.LETTERS for y in schedule.LETTERS if x != y})

    def test_only_rows_1_and_3_and_rows_2_and_4_give_every_letter_the_same_position_total(self):
        def totals(r1, r2):
            return {letter: schedule.SQUARE[r1 - 1].index(letter) + schedule.SQUARE[r2 - 1].index(letter) + 2 for letter in schedule.LETTERS}
        for r1, r2 in itertools.combinations([1, 2, 3, 4], 2):
            even = set(totals(r1, r2).values()) == {5}
            self.assertEqual(even, (r1, r2) in ((1, 3), (2, 4)), (r1, r2))
        self.assertEqual(schedule.ROWS_OF_HALF, {'H1': (1, 3), 'H2': (2, 4)})


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tasks = tasks()
        self.plan = schedule.build(config(), self.tasks)
        self.square = [b for b in self.plan['blocks'] if b['row'] is not None]

    def test_sixteen_blocks_then_the_reference_block_last(self):
        blocks = self.plan['blocks']
        self.assertEqual(len(blocks), 17)
        self.assertEqual([b['sequence'] for b in blocks], list(range(1, 18)))
        self.assertEqual(blocks[-1]['arm'], 'alpha')
        self.assertEqual(blocks[-1]['id'], 'ref-alpha')
        self.assertTrue(all(b['arm'] != 'alpha' for b in blocks[:-1]))
        self.assertEqual(Counter(b['arm'] for b in self.square), {arm: 4 for arm in ARMS})

    def test_letters_and_round_order_are_permutations(self):
        self.assertEqual(sorted(self.plan['letters']), list(schedule.LETTERS))
        self.assertEqual(sorted(self.plan['letters'].values()), sorted(ARMS))
        self.assertEqual(sorted(self.plan['roundOrder']), [1, 2, 3, 4])
        rows_in_time = [b['row'] for b in self.square[::4]]
        self.assertEqual(rows_in_time, self.plan['roundOrder'])

    def test_blocks_follow_the_square_through_the_letters(self):
        for block in self.square:
            self.assertEqual(block['letter'], schedule.SQUARE[block['row'] - 1][block['position'] - 1])
            self.assertEqual(self.plan['letters'][block['letter']], block['arm'])

    def test_every_arm_holds_every_position_once(self):
        for arm in ARMS:
            self.assertEqual(sorted(b['position'] for b in self.square if b['arm'] == arm), [1, 2, 3, 4])

    def test_every_arm_directly_precedes_every_other_arm_once_within_a_round(self):
        pairs = []
        for start in range(0, 16, 4):
            rnd = self.square[start:start + 4]
            pairs.extend((rnd[i]['arm'], rnd[i + 1]['arm']) for i in range(3))
        self.assertEqual(Counter(pairs), {(x, y): 1 for x in ARMS for y in ARMS if x != y})

    def test_halves_are_complementary_stratified_and_stay_on_their_rows(self):
        h1, h2 = set(self.plan['halves']['H1']), set(self.plan['halves']['H2'])
        self.assertEqual(h1 | h2, {t['id'] for t in self.tasks})
        self.assertFalse(h1 & h2)
        self.assertEqual((len(h1), len(h2)), (27, 27))
        strata = Counter(schedule.stratum(t) for t in self.tasks)
        for name, count in strata.items():
            in_h1 = sum(1 for t in self.tasks if schedule.stratum(t) == name and t['id'] in h1)
            self.assertLessEqual(abs(in_h1 - (count - in_h1)), 1, name)
        for block in self.square:
            expected = h1 if block['row'] in (1, 3) else h2
            self.assertEqual({r['task'] for r in block['runs']}, expected)
            self.assertEqual(block['half'], 'H1' if block['row'] in (1, 3) else 'H2')

    def test_halves_stay_on_their_rows_whatever_the_round_order(self):
        for seed in range(30):
            plan = schedule.build(config(seed), self.tasks)
            for block in plan['blocks'][:-1]:
                self.assertEqual(block['half'], schedule.HALF_OF_ROW[block['row']])
                self.assertEqual({r['task'] for r in block['runs']}, set(plan['halves'][block['half']]))

    def test_every_arm_runs_every_task_once_per_model_in_two_different_rounds(self):
        for arm in ARMS:
            runs = [(r['task'], r['model'], b['row']) for b in self.square if b['arm'] == arm for r in b['runs']]
            self.assertEqual(Counter((t, m) for t, m, _ in runs), {(t['id'], m): 1 for t in self.tasks for m in MODELS})
            for task in self.tasks:
                rows = {row for t, _, row in runs if t == task['id']}
                self.assertEqual(len(rows), 2)

    def test_the_model_of_a_task_is_the_same_for_all_arms_of_a_row(self):
        for row in (1, 2, 3, 4):
            blocks = [b for b in self.square if b['row'] == row]
            assignments = [{r['task']: r['model'] for r in b['runs']} for b in blocks]
            self.assertTrue(all(a == assignments[0] for a in assignments))
            self.assertEqual(assignments[0], self.plan['modelOfTask'][str(row)])

    def test_the_model_split_is_balanced_by_category_within_each_half(self):
        by_id = {t['id']: t for t in self.tasks}
        for half, (first, _) in schedule.ROWS_OF_HALF.items():
            per_category = Counter()
            for task_id in self.plan['halves'][half]:
                model = self.plan['modelOfTask'][str(first)][task_id]
                per_category[(by_id[task_id]['category'], model)] += 1
            for category in {t['category'] for t in self.tasks}:
                self.assertLessEqual(abs(per_category[(category, MODELS[0])] - per_category[(category, MODELS[1])]), 1, (half, category))

    def test_models_alternate_inside_a_block(self):
        for block in self.square:
            models = [r['model'] for r in block['runs']]
            self.assertTrue(all(a != b for a, b in zip(models, models[1:])), block['id'])

    def test_the_task_order_differs_between_blocks(self):
        orders = {tuple(r['task'] for r in b['runs']) for b in self.square}
        self.assertGreater(len(orders), 8)

    def test_the_reference_block_runs_every_task_with_both_models_interleaved(self):
        ref = self.plan['blocks'][-1]
        self.assertEqual(len(ref['runs']), 108)
        self.assertEqual(Counter((r['task'], r['model']) for r in ref['runs']), {(t['id'], m): 1 for t in self.tasks for m in MODELS})
        for i in range(0, 108, 2):
            self.assertEqual(ref['runs'][i]['task'], ref['runs'][i + 1]['task'])
        firsts = Counter(ref['runs'][i]['model'] for i in range(0, 108, 2))
        self.assertLessEqual(abs(firsts[MODELS[0]] - firsts[MODELS[1]]), 1)
        self.assertEqual(ref['runSuffix'], 'ref')

    def test_the_same_seed_gives_the_same_schedule_and_another_seed_another(self):
        self.assertEqual(schedule.build(config(), self.tasks), self.plan)
        self.assertEqual(schedule.build(config(), list(reversed(self.tasks))), self.plan)
        other = schedule.build(config(7), self.tasks)
        self.assertNotEqual(other, self.plan)

    def test_run_keys_name_the_row_or_the_reference_block(self):
        block = self.square[0]
        run = block['runs'][0]
        self.assertEqual(schedule.run_key(block['arm'], run['task'], run['model'], block['runSuffix']),
                         '%s__%s__%s__r%d' % (block['arm'], run['task'], run['model'], block['row']))
        keys = [schedule.run_key(b['arm'], r['task'], r['model'], b['runSuffix']) for b in self.plan['blocks'] for r in b['runs']]
        self.assertEqual(len(keys), len(set(keys)))


class ValidationTests(unittest.TestCase):
    def check(self, block, message, models=MODELS):
        with self.assertRaisesRegex(ValueError, message):
            schedule.validate(block, SCENARIOS, models)

    def test_a_good_block_passes(self):
        schedule.validate(config()['schedule'], SCENARIOS, MODELS)

    def test_malformed_blocks_are_refused(self):
        good = config()['schedule']
        self.check({**good, 'design': 'latin'}, 'design')
        self.check({**good, 'arms': ARMS[:3]}, 'four different')
        self.check({**good, 'arms': ['beta', 'beta', 'gamma', 'delta']}, 'four different')
        self.check({**good, 'reference': 'beta'}, 'must not be one of')
        self.check({**good, 'arms': ['beta', 'gamma', 'delta', 'zeta']}, 'does not declare')
        self.check({**good, 'extra': 1}, 'unknown keys')
        self.check(good, 'exactly two models', models=MODELS + ['third'])


if __name__ == '__main__':
    unittest.main()
