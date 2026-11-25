"""Tests of the study-3 analysis, offline: seeded simulated studies and bundles at corpus 3's shape, one fake bundle written by the harness on
its fakes, and study 2's committed scores for the power check. No stack, no vendor, and of corpus 3 only its metadata. The study gate runs
them as the `analysis3` suite under STUDY_MCP_PYTHON (statsmodels and scipy)."""
import collections
import contextlib
import io
import json
import math
import re
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import analyze3  # noqa: E402
import data3  # noqa: E402
import legacy3  # noqa: E402
import power3  # noqa: E402
import simulate3  # noqa: E402
import stats3  # noqa: E402
import validate3  # noqa: E402

import simulate as simulate2  # noqa: E402  (study 2's bundle writers)
import stats2  # noqa: E402

REPLICATES = 500
MODELS = simulate3.MODELS


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = analyze3.main(argv)
    return code, out.getvalue(), err.getvalue()


def args_for(facts, out):
    return ['--bundle', str(facts['bundle']), '--sums', str(facts['sums']), '--bundle-checksum', facts['checksum'], '--corpus-dir', str(facts['corpus']),
            '--run-id', facts['runId'], '--out', str(out), '--replicates', str(REPLICATES)]


def reseal(facts):
    folder = Path(facts['bundle'])
    checksum = simulate2.write_bundle(folder, facts['runId'], '2026-12-02T00:00:00.000+00:00')
    simulate2.write_sums(folder, facts['runId'], facts['sums'])
    return dict(facts, checksum=checksum)


def edit_json(path, change):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    change(value)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def bundle(self, name='sim', **options):
        return simulate3.write_bundle(self.root / name, **options)

    def assertStops(self, facts, text):
        out = self.root / 'out-stopped'
        code, _, err = run_cli(args_for(facts, out))
        self.assertEqual(code, 2, err)
        self.assertIn('STOP', err)
        self.assertIn(text, err)
        self.assertFalse(out.exists(), 'nothing is written when the analysis stops')


class ShapeTests(unittest.TestCase):
    def test_the_simulated_shape_is_corpus_3s_metadata(self):
        raw = json.loads((HERE.parent / 'corpus3' / 'tasks.json').read_text(encoding='utf-8'))
        real = collections.Counter()
        for t in raw['tasks']:
            d = raw['directions'][t['id']]
            tag = (t.get('tags') or {}).get('fullyAnswerableWithoutStoppedService') if t['category'] == 'D' else None
            real[(t['category'], t['size'], '+'.join(sorted(t['systems'] or [])), '+'.join(sorted(d['requiredSystems'] or [])), d['direction'], d['csl'],
                  d['anchor'], t.get('stoppedService'), tag)] += 1
        self.assertEqual(real, collections.Counter({row[:-1]: row[-1] for row in simulate3.SHAPE}))

    def test_the_groups_have_the_decided_sizes(self):
        tasks, directions = simulate3.tasks_of_shape()
        core = [t for t in tasks if t['set'] == 'core']
        self.assertEqual(len(core), 107)
        count = collections.Counter(directions[t['id']]['direction'] for t in core)
        self.assertEqual((count['forward'], count['reverse'], count['none']), (24, 30, 53))
        join = collections.Counter(data3.join_group(t['category'], directions[t['id']]['requiredSystems']) for t in core)
        self.assertEqual((join['one'], join['several'], join[None]), (39, 52, 16), 'join width reads requiredSystems, without D and the mapping-only tasks')

    def test_the_forward_aggregates_are_ten_core_tasks_on_corpus_3(self):
        raw = json.loads((HERE.parent / 'corpus3' / 'tasks.json').read_text(encoding='utf-8'))
        real = [t['id'] for t in raw['tasks']
                if data3.forward_aggregate(t.get('set') or 'core', t['category'], raw['directions'][t['id']]['direction'])]
        self.assertEqual(len(real), 10)
        self.assertEqual({raw['directions'][t]['csl'] for t in real}, {None}, 'a forward aggregate is no CSL kind')
        tasks, directions = simulate3.tasks_of_shape()
        simulated = [t['id'] for t in tasks if data3.forward_aggregate(t['set'], t['category'], directions[t['id']]['direction'])]
        self.assertEqual(len(simulated), 10)

    def test_the_schedule_takes_the_core_tasks_unchanged(self):
        tasks, _ = simulate3.tasks_of_shape()
        plan = simulate3.build_plan(313, tasks)
        core = {t['id'] for t in tasks if t['set'] == 'core'}
        runs = [run for block in plan['blocks'] if block['row'] for run in block['runs'] if run['task'] in core]
        self.assertEqual(len(runs), 107 * 8)


class VerificationTests(Workspace):
    def test_a_verified_copy_is_analysed(self):
        facts = self.bundle()
        code, _, err = run_cli(args_for(facts, self.root / 'out'))
        self.assertEqual(code, 0, err)
        for name in ('results.json', 'tables.md', 'figures/effort.svg'):
            self.assertTrue((self.root / 'out' / name).is_file(), name)

    def test_a_tampered_copy_stops_before_any_output(self):
        facts = self.bundle()
        target = sorted(Path(facts['bundle']).glob('runs/*/result.json'))[0]
        target.write_bytes(target.read_bytes().replace(b'"turns"', b'"Turns"'))
        self.assertStops(facts, 'differ from the sums')

    def test_the_manifest_must_name_contract_corpus_commit_and_this_plan(self):
        for name, change, text in (('contract', lambda m: m.pop('scoringContract'), 'scorer contract'),
                                   ('corpus', lambda m: m['identity'].pop('corpusFreeze'), 'corpus hash'),
                                   ('commit', lambda m: m.pop('commit'), 'harness commit'),
                                   ('no-plan', lambda m: m['identity'].pop('analysisPlan'), 'names no analysis plan hash'),
                                   ('other-plan', lambda m: m['identity'].update(analysisPlan='0' * 64), 'is not the hash of the plan')):
            with self.subTest(name=name):
                facts = self.bundle(name=name)
                edit_json(Path(facts['bundle']) / 'manifest.json', change)
                self.assertStops(reseal(facts), text)

    def test_a_corpus_without_a_full_directions_map_is_refused(self):
        facts = self.bundle()
        corpus = Path(facts['corpus'])
        edit_json(corpus / 'tasks.json', lambda t: t['directions'].pop('T001'))
        edit_json(corpus / 'corpus-manifest.json', lambda m: m['files'].update({'tasks.json': data3.sha256_file(corpus / 'tasks.json')}))
        edit_json(Path(facts['bundle']) / 'manifest.json', lambda m: m['identity'].update(corpusFreeze=data3.sha256_file(corpus / 'corpus-manifest.json')))
        self.assertStops(reseal(facts), 'no directions entry')


class CountingTests(Workspace):
    def loaded(self, **options):
        facts = self.bundle(**options)
        return data3.load(facts['bundle'], facts['sums'], facts['runId'], facts['checksum'], facts['corpus'])

    def test_vendor_errors_are_missing_and_a_requeued_run_counts_once(self):
        *_, records, _, _ = self.loaded(vendor_error_rate=0.05)
        self.assertEqual(len({r['runKey'] for r in records}), len(records))
        self.assertTrue(any(r['requeued'] and r['correct'] is not None for r in records))
        self.assertTrue(all(r['correct'] is None for r in records if r['outcome'] == 'vendor_error'))
        self.assertTrue(any(r['outcome'] == 'vendor_error' for r in records))

    def test_a_void_attempt_is_left_out_and_its_cost_is_kept_apart(self):
        *_, records, blocks, _ = self.loaded(void_block=2)
        block = next(b for b in blocks if b['sequence'] == 2)
        self.assertEqual(block['countedAttempt'], 2)
        self.assertGreater(block['voidCost'], 0)
        self.assertEqual(sum(1 for r in records if r['block'] == block['id']), len({r['runKey'] for r in records if r['block'] == block['id']}))

    def test_a_zero_cost_takes_the_smallest_positive_cost_of_the_scored_runs(self):
        *_, records, _, zero = self.loaded(zero_cost_runs=3, vendor_error_rate=0.0)
        self.assertEqual(zero['runsWithZeroCost'], 3)
        replaced = [r for r in records if r['costAsRecorded'] == 0]
        self.assertEqual(len(replaced), 3)
        smallest = min(r['costAsRecorded'] for r in records if r['costAsRecorded'] > 0)
        self.assertTrue(all(r['cost'] == smallest for r in replaced))

    def test_each_record_carries_its_groups(self):
        *_, records, _, _ = self.loaded()
        core = {r['task']: r for r in records if r['set'] == 'core'}
        self.assertEqual(collections.Counter(r['cslGroup'] for r in core.values())['forward'], 24)
        self.assertEqual(collections.Counter(r['joinGroup'] for r in core.values())['one'], 39)
        self.assertEqual(collections.Counter(r['forwardAggregate'] for r in core.values())[True], 10)


class StatisticsTests(unittest.TestCase):
    def test_the_estimates_recover_the_true_effects_across_seeds(self):
        effects = simulate3.effects_at(100, reverse_gone=True)
        found = collections.defaultdict(list)
        for seed in range(1, 13):
            records, strata = simulate3.study_records(seed, effects)
            result = stats3.confirmatory(records, MODELS, strata, REPLICATES)
            for outcome, family in result['effort'].items():
                self.assertEqual(family['method'], 'gee')
                for e in family['comparisons']:
                    found[(outcome, e['id'])].append(e['logRatio'])
            found['reverseMinusForward'].append(result['csl']['tests'][0]['estimate'])
        self.assertAlmostEqual(np.mean(found[('toolCalls', 'P2')]), effects['P2']['toolCalls'], delta=0.05)
        self.assertAlmostEqual(np.mean(found[('cost', 'P1')]), effects['P1']['cost'], delta=0.05)
        self.assertAlmostEqual(np.mean(found[('cost', 'P2')]), effects['P2']['cost'], delta=0.05)
        self.assertAlmostEqual(np.mean(found['reverseMinusForward']), effects['reverseMinusForward'], delta=0.05)

    def test_the_csl_tests_have_the_predicted_sign_and_size(self):
        effects = simulate3.effects_at(100, reverse_gone=True, join=True)
        values = collections.defaultdict(list)
        for seed in range(1, 11):
            records, strata = simulate3.study_records(seed, effects)
            for test in stats3.csl_family([r for r in records if r['correct'] is not None], records, MODELS, REPLICATES)['tests']:
                values[test['id']].append(test['estimate'])
        self.assertGreater(np.mean(values['forwardReverse']), 0.1)
        self.assertLess(np.mean(values['joinWidth']), -0.08)

    def test_holm_is_over_the_two_comparisons_of_a_family(self):
        records, strata = simulate3.study_records(3, simulate3.effects_at(50))
        family = stats3.confirmatory(records, MODELS, strata, REPLICATES)['effort']['toolCalls']
        ps = [e['p'] for e in family['comparisons']]
        self.assertEqual([e['pHolm'] for e in family['comparisons']], stats2.holm(ps))

    def test_the_interval_excludes_zero_exactly_when_p_is_below_005(self):
        rng = np.random.default_rng(5)
        for valid in (199, 999, 9999, 1000):
            for _ in range(200):
                delta = float(rng.normal(0, 1))
                s = stats3.two_sided_summary(delta, delta + rng.normal(0, 1, valid))
                self.assertEqual(s['p'] < 0.05, s['low'] > 0 or s['high'] < 0)

    def test_the_one_sided_bound_matches_its_test(self):
        rng = np.random.default_rng(6)
        for sign in (1, -1):
            for _ in range(300):
                delta = float(rng.normal(0, 1))
                s = stats3.one_sided_summary(delta, delta + rng.normal(0, 1, 999), sign)
                self.assertEqual(s['p'] < 0.05, sign * s['bound'] > 0)

    def test_the_csl_gees_use_the_bias_reduced_covariance(self):
        records, _ = simulate3.study_records(5)
        rows = [r for r in records if r['correct'] is not None]
        fit = stats3.group_gee(rows, 'cslGroup', 'forward', 'reverse', MODELS, stats2.planned_conditions(records))
        self.assertEqual(fit.cov_kind, 'bias_reduced')

    def test_the_csl_fallback_widens_each_groups_deviations(self):
        stars = np.array([1.0, 2.0, 3.0])
        np.testing.assert_allclose(stats3.rescaled(stars, 2.0, 5), 2.0 + math.sqrt(5 / 4) * (stars - 2.0))
        np.testing.assert_allclose(stats3.rescaled(stars, 2.0, 5, 1.1), 2.0 + 1.1 * math.sqrt(5 / 4) * (stars - 2.0))

    def test_the_csl_wald_test_uses_a_t_reference_on_the_tasks_minus_one(self):
        records, _ = simulate3.study_records(5)
        rows = [r for r in records if r['correct'] is not None]
        fit = stats3.group_gee(rows, 'cslGroup', 'forward', 'reverse', MODELS, stats2.planned_conditions(records))
        wald = stats3.csl_wald(fit, 1)
        self.assertEqual(wald['df'], 53)
        self.assertAlmostEqual(wald['p'], float(stats3.sps.t.sf(wald['estimate'] / wald['se'], 53)))
        self.assertAlmostEqual(wald['bound'], wald['estimate'] - float(stats3.sps.t.ppf(0.95, 53)) * wald['se'])

    def test_the_bca_bound_is_the_percentile_bound_without_bias_or_skew(self):
        rng = np.random.default_rng(8)
        stars = rng.normal(0.0, 1.0, 200001)
        self.assertAlmostEqual(stats3.bca_lower(stars, float(np.median(stars)), 0.0), float(np.quantile(stars, 0.025)), places=2)

    def test_the_bca_bound_moves_down_when_the_acceleration_is_negative(self):
        rng = np.random.default_rng(9)
        stars = rng.normal(0.0, 1.0, 20001)
        self.assertLess(stats3.bca_lower(stars, 0.0, -0.1), float(np.quantile(stars, 0.025)))

    def test_the_bca_bound_of_identical_replicates_is_the_estimate(self):
        self.assertAlmostEqual(stats3.bca_lower(np.full(100, -0.05), -0.05, 0.0), -0.05)

    def test_the_acceleration_uses_deviations_within_each_stratum(self):
        """With one run per task and arm the estimate is the mean of the tasks' differences, so the multisample jackknife has a closed form:
        (1/6) sum(e^3) / sum(e^2)^1.5, e each task's difference from its stratum's mean. Between-stratum differences must not enter."""
        rng = np.random.default_rng(10)
        sizes = (24, 30, 53)
        shifts = (-0.30, 0.0, 0.25)
        differences = np.concatenate([shift + rng.binomial(1, 0.15, size) * -0.5 for size, shift in zip(sizes, shifts)])
        tasks = ['T%03d' % i for i in range(len(differences))]
        rows = [{'task': t, 'arm': a, 'model': MODELS[0], 'row': 1, 'value': float(d) if a in ('delta', 'epsilon') else 0.0}
                for t, d in zip(tasks, differences) for a in stats3.ARMS]
        table = stats3.CellTable(rows, lambda r: r['value'], [MODELS[0]], [1], tasks)
        edges = np.cumsum((0,) + sizes)
        strata = [np.arange(edges[i], edges[i + 1]) for i in range(3)]
        within = np.concatenate([differences[s] - differences[s].mean() for s in strata])
        expected = float(np.sum(within ** 3)) / (6.0 * float(np.sum(within ** 2)) ** 1.5)
        self.assertAlmostEqual(stats3.stratified_acceleration(table, 'gamma', strata), expected, places=10)
        pooled = differences - differences.mean()
        self.assertNotAlmostEqual(expected, float(np.sum(pooled ** 3)) / (6.0 * float(np.sum(pooled ** 2)) ** 1.5), places=3)

    def floor_rows(self, difference):
        """Every task has the same accuracy in each arm, so every replicate equals the estimate and the bound is the difference itself."""
        records, strata = simulate3.study_records(1, missing=0.0)
        return [dict(r, correct=1.0 + difference if r['arm'] in ('delta', 'epsilon') else 1.0) for r in records], strata

    def test_the_floor_gates_at_the_margin(self):
        for difference, cleared in ((-0.0999, True), (-0.1001, False)):
            rows, strata = self.floor_rows(difference)
            floor = stats3.accuracy_floor(rows, 'gamma', MODELS, strata, REPLICATES)
            self.assertAlmostEqual(floor['lower'], difference, places=6)
            self.assertEqual(floor['cleared'], cleared)

    def test_an_arm_that_fails_the_floor_is_reported_but_not_claimed_and_holm_is_unchanged(self):
        records, strata = simulate3.study_records(2, simulate3.effects_at(100))
        before = stats3.confirmatory(records, MODELS, strata, REPLICATES)
        real = stats3.accuracy_floor

        def failing(rows, comparator, *args, **kwargs):
            return dict(real(rows, comparator, *args, **kwargs), cleared=comparator != 'gamma')

        with mock.patch.object(stats3, 'accuracy_floor', failing):
            after = stats3.confirmatory(records, MODELS, strata, REPLICATES)
        for outcome in stats3.EFFORT_FAMILIES:
            first, second = after['effort'][outcome]['comparisons']
            self.assertEqual([e['pHolm'] for e in after['effort'][outcome]['comparisons']], [e['pHolm'] for e in before['effort'][outcome]['comparisons']])
            self.assertTrue(first['rejected'])
            self.assertFalse(first['claimed'], 'P1 compares with GraphQL Adapters, whose floor failed')
            self.assertEqual(second['claimed'], second['rejected'])
        self.assertTrue(all(not t['claimed'] for t in after['csl']['tests']), 'the CSL family is gated by the floor against GraphQL Adapters')


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.records, self.strata = simulate3.study_records(4, simulate3.effects_at(100))

    def test_each_effort_family_switches_on_its_own(self):
        real = stats3.effort_gee

        def broken(rows, outcome, *args, **kwargs):
            if outcome == 'cost':
                raise stats2.FitError('simulated unusable fit')
            return real(rows, outcome, *args, **kwargs)

        with mock.patch.object(stats3, 'effort_gee', broken):
            result = stats3.confirmatory(self.records, MODELS, self.strata, REPLICATES)
        self.assertEqual(result['effort']['toolCalls']['method'], 'gee')
        self.assertEqual(result['effort']['cost']['method'], 'bootstrap')
        self.assertEqual(result['csl']['method'], 'gee')
        self.assertEqual(len(result['effort']['cost']['comparisons']), 2)

    def test_one_unusable_csl_fit_moves_both_csl_tests_to_the_fallback(self):
        real = stats3.group_gee

        def broken(rows, field, *args, **kwargs):
            if field == 'joinGroup':
                raise stats2.FitError('simulated unusable fit')
            return real(rows, field, *args, **kwargs)

        with mock.patch.object(stats3, 'group_gee', broken):
            csl = stats3.confirmatory(self.records, MODELS, self.strata, REPLICATES)['csl']
        self.assertEqual(csl['method'], 'bootstrap')
        self.assertEqual([t['id'] for t in csl['tests']], ['forwardReverse', 'joinWidth'])
        self.assertEqual([t['pHolm'] for t in csl['tests']], stats2.holm([t['p'] for t in csl['tests']]))

    def test_the_csl_fallback_has_no_empty_cell_on_the_schedule_that_defeated_cell_means(self):
        records, strata = simulate3.study_records(4, simulate3.effects_at(100, reverse_gone=True), missing=0.0, plan_seed=313)
        csl = stats3.csl_family([r for r in records if r['correct'] is not None], records, MODELS, REPLICATES, force_fallback=True)
        self.assertEqual(csl['method'], 'bootstrap')
        self.assertTrue(all(t['usable'] == REPLICATES for t in csl['tests']))

    def test_more_than_one_percent_unusable_replicates_makes_a_family_not_estimable_and_the_rest_is_produced(self):
        with mock.patch.object(stats3, 'effort_gee', side_effect=stats2.FitError('simulated')), mock.patch.object(stats3, 'UNUSABLE_LIMIT', -1.0):
            result = stats3.confirmatory(self.records, MODELS, self.strata, REPLICATES)
        self.assertEqual(result['effort']['toolCalls']['method'], 'notEstimable')
        self.assertEqual(result['effort']['toolCalls']['comparisons'], [])
        self.assertEqual(result['csl']['method'], 'gee')

    @staticmethod
    def unusable(count, replicates):
        """CellTable.arm_means with the first `count` of the `replicates` bootstrap replicates emptied in every arm."""
        real = stats3.CellTable.arm_means

        def emptied(table, weights):
            arms = real(table, weights)
            if weights.shape[0] == replicates:
                for values in arms.values():
                    values[:count] = np.nan
            return arms

        return mock.patch.object(stats3.CellTable, 'arm_means', emptied)

    def test_exactly_one_percent_unusable_replicates_passes_the_effort_fallback_and_one_more_does_not(self):
        rows = [r for r in self.records if r['correct'] is not None]
        for replicates in (10000, 2000):
            for count, estimable in ((replicates // 100, True), (replicates // 100 + 1, False)):
                with self.unusable(count, replicates):
                    family = stats3.effort_fallback(rows, 'cost', MODELS, self.strata, replicates)
                self.assertEqual((family['usable'], family['estimable']), (replicates - count, estimable), (replicates, count))

    def test_exactly_one_percent_unusable_replicates_passes_the_floor_and_one_more_does_not(self):
        rows = [r for r in self.records if r['correct'] is not None]
        for replicates in (10000, 2000):
            for count, estimable in ((replicates // 100, True), (replicates // 100 + 1, False)):
                with self.unusable(count, replicates):
                    floor = stats3.accuracy_floor(rows, 'gamma', MODELS, self.strata, replicates)
                self.assertEqual((floor['usable'], floor['estimable']), (replicates - count, estimable), (replicates, count))

    def test_the_effort_fallback_widens_its_deviations_by_the_small_sample_factor(self):
        self.assertAlmostEqual(stats3.small_sample_factor(107, 3), math.sqrt(107 / 104) * float(stats3.sps.t.ppf(0.975, 104) / stats3.sps.norm.ppf(0.975)))
        rows = [r for r in self.records if r['correct'] is not None]
        widened = stats3.effort_fallback(rows, 'cost', MODELS, self.strata, REPLICATES)
        with mock.patch.object(stats3, 'small_sample_factor', return_value=1.0):
            plain = stats3.effort_fallback(rows, 'cost', MODELS, self.strata, REPLICATES)
        first, second = widened['comparisons']['P1'], plain['comparisons']['P1']
        self.assertEqual(first['estimate'], second['estimate'])
        self.assertAlmostEqual((first['high'] - first['low']) / (second['high'] - second['low']), stats3.small_sample_factor(107, 3), places=6)

    def test_the_fallback_recovers_the_effect(self):
        found = []
        for seed in range(1, 9):
            records, strata = simulate3.study_records(seed, simulate3.effects_at(100))
            rows = [r for r in records if r['correct'] is not None]
            found.append(stats3.effort_fallback(rows, 'cost', MODELS, strata, REPLICATES)['comparisons']['P2']['estimate'])
        self.assertAlmostEqual(np.mean(found), simulate3.STUDY2['cost']['P2'], delta=0.05)


class OutputTests(Workspace):
    def test_the_same_inputs_give_the_same_bytes(self):
        facts = self.bundle(effects=simulate3.effects_at(100))
        for name in ('one', 'two'):
            self.assertEqual(run_cli(args_for(facts, self.root / name))[0], 0)
        for name in ('results.json', 'tables.md', 'figures/effort.svg'):
            self.assertEqual((self.root / 'one' / name).read_bytes(), (self.root / 'two' / name).read_bytes(), name)

    def test_the_tiers_and_the_legacy_load_pointer_are_in_the_results(self):
        facts = self.bundle(effects=simulate3.effects_at(100))
        self.assertEqual(run_cli(args_for(facts, self.root / 'out'))[0], 0)
        res = json.loads((self.root / 'out' / 'results.json').read_text(encoding='utf-8'))
        command = next(line for line in (HERE / 'README.md').read_text(encoding='utf-8').splitlines() if 'analysis3/legacy3.py --run-id' in line)
        legacy = res['descriptive']['legacyLoad']
        self.assertEqual(set(legacy), {'status', 'measure'})
        self.assertIn('Reported by legacy3.py', legacy['status'])
        run = facts['runId']
        self.assertIn('`%s`' % command.replace("'<run id>'", shlex.quote(run)).replace('<run id>', run), legacy['status'],
                      "the README's command line with the run id the analysis read")
        self.assertIn('## Descriptive: legacy load\n\n%s\n' % legacy['status'], (self.root / 'out' / 'tables.md').read_text(encoding='utf-8'))
        self.assertEqual(set(res['confirmatory']), {'floors', 'effort', 'csl'})
        self.assertEqual(set(res['cslGroupAccuracy']['groups']), {'forward', 'reverse', 'one', 'several'})
        self.assertEqual(res['exploratory']['study2Tasks']['compared'], False)
        self.assertEqual(res['about'], 'Abstraction ladder study 3 analysis under the plan study/analysis3/PLAN.md. Generated; do not edit.')
        self.assertNotIn('draft', analyze3.__doc__.splitlines()[0])
        self.assertEqual(set(res['descriptive']['perStratum']), {'anchor', 'csl', 'category', 'size', 'forwardAggregates'})


def section_rows(text, heading):
    """The table rows of one section of tables.md, as lists of cells, header and rule left out."""
    lines = text.split('\n## ')
    body = next(part for part in lines if part.split('\n', 1)[0] == heading[3:])
    rows = [line for line in body.splitlines() if line.startswith('| ')]
    return [[cell.strip() for cell in row.strip('|').split(' | ')] for row in rows[2:]]


class LegacyCommandAndInputSectionsTests(Workspace):
    """The legacy-load command names the run the analysis read, and tables.md prints the verification, the counting and the spend of
    results.json as they stand, in the plan's order."""
    VERIFICATION = '## Inputs: the verification (PLAN.md, section 1)'
    COUNTING = '## Inputs: which runs count (PLAN.md, section 3)'
    SPEND = '## Descriptive: spend by arm (USD, prices of the manifest)'

    def run_analysis(self, run_id, give_run_id, **options):
        facts = self.bundle(name=run_id, run_id=run_id, **options)
        argv = args_for(facts, self.root / ('out-' + run_id))
        if not give_run_id:
            at = argv.index('--run-id')
            del argv[at:at + 2]
        code, _, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        out = self.root / ('out-' + run_id)
        return json.loads((out / 'results.json').read_text(encoding='utf-8')), (out / 'tables.md').read_text(encoding='utf-8')

    def check_command(self, res, text, run_id):
        status = res['descriptive']['legacyLoad']['status']
        self.assertIn('## Descriptive: legacy load\n\n%s\n' % status, text)
        self.check_status(status, run_id)

    def check_status(self, status, run_id):
        opening = re.match('[^`]*(`+)', status)
        fence = opening.group(1)
        self.assertTrue(status.endswith(fence) and len(fence) > max(map(len, re.findall('`+', run_id)), default=0),
                        'the code span is closed by its own delimiter, longer than any backticks of the run id')
        tokens = shlex.split(status[opening.end():-len(fence)])
        self.assertEqual(tokens[:3], ['$STUDY_MCP_PYTHON', '-B', 'study/analysis3/legacy3.py'])
        args = legacy3.build_parser().parse_args(tokens[3:])
        self.assertEqual(args.run_id, run_id, "legacy3.py's own parser reads the run id the analysis read")
        self.assertEqual((args.bundle, args.sums), ('<copy>/%s' % run_id, '<archive>/SHA256SUMS-%s.txt' % run_id))
        self.assertEqual((args.bundle_checksum, args.corpus_dir, args.legacy_dir, args.out),
                         ('<sha256 of the bundle>', 'study/corpus3', '<copy of the state folder>/legacy-load', '<folder outside the repository>'))

    def check_sections(self, res, text):
        headings = [line for line in text.splitlines() if line.startswith('## ')]
        self.assertEqual(headings[:3], [self.VERIFICATION, self.COUNTING, '## Confirmatory: the accuracy floor (federation minus the arm, points; '
                                                                         'one-sided 0.025; margin -10)'])
        self.assertLess(headings.index('## Descriptive: time per run (ratios of geometric means)'), headings.index(self.SPEND))
        self.assertEqual(headings[-2:], [self.SPEND, '## Descriptive: legacy load'])

        def recorded(value):
            return value if isinstance(value, str) else json.dumps(value)

        bundle, corpus = res['inputs']['bundle'], res['inputs']['corpus']
        self.assertEqual((set(analyze3.BUNDLE_LABELS), set(analyze3.CORPUS_LABELS)), (set(bundle), set(corpus)), 'every recorded fact is printed')
        rows = section_rows(text, self.VERIFICATION)
        self.assertEqual([r[1] for r in rows], [recorded(bundle[k]) for k in analyze3.BUNDLE_LABELS] + [recorded(corpus[k]) for k in analyze3.CORPUS_LABELS])
        self.assertEqual([r[0] for r in rows], ['bundle: ' + v for v in analyze3.BUNDLE_LABELS.values()] + ['corpus: ' + v for v in analyze3.CORPUS_LABELS.values()])
        for name in ('run', 'bundleChecksum', 'sumsFile', 'sumsFileSha256', 'corpusFreeze', 'planHash'):
            self.assertIn(bundle[name], [r[1] for r in rows], name)

        counting = res['counting']
        rows = section_rows(text, self.COUNTING)
        plain = list(analyze3.COUNTING_LABELS)
        self.assertEqual((set(plain) | {'zeroCost'}, set(analyze3.ZERO_COST_LABELS)), (set(counting), set(counting['zeroCost'])), 'every count is printed')
        self.assertEqual(len(rows), len(plain) + len(counting['zeroCost']))
        for row, key in zip(rows, plain):
            value = counting[key]
            self.assertEqual(row[1], (', '.join(value) or 'none') if isinstance(value, list) else str(value), key)
        zero = counting['zeroCost']
        self.assertEqual(rows[len(plain)][1], str(zero['runsWithZeroCost']))
        if zero['replacedBy'] is None:
            self.assertEqual(rows[len(plain) + 1][1], 'none')
        else:
            self.assertEqual(float(rows[len(plain) + 1][1]), zero['replacedBy'])

        spend = res['descriptive']['spend']
        rows = section_rows(text, self.SPEND)
        self.assertEqual(set(spend), set(data3.ALL_ARMS))
        self.assertEqual([r[0] for r in rows], [analyze3.NAMES[a] for a in data3.ALL_ARMS])
        for row, entry in zip(rows, (spend[a] for a in data3.ALL_ARMS)):
            self.assertEqual([float(c) for c in row[1:]], [entry['countedRuns'], entry['archivedAttempts'], entry['voidAttempts']])

    def test_a_run_id_with_quotes_spaces_backticks_or_a_leading_hyphen_parses_back_whole(self):
        for run_id in ("operator's-run", 'run "two"', 'a run', '-archive-test', '--x', 'run`tick', 'a``b`'):
            self.check_status(analyze3.legacy_load(run_id), run_id)
        self.assertIn(' --run-id study3-scored-1 ', analyze3.legacy_load('study3-scored-1'), 'an ordinary run id keeps the form of C1')
        self.assertTrue(analyze3.legacy_load('study3-scored-1').endswith("'<folder outside the repository>'`"))

    def test_the_default_run_id_is_named_in_the_command_and_the_sections_are_printed(self):
        res, text = self.run_analysis('study-3', give_run_id=False)
        self.assertEqual(res['inputs']['bundle']['run'], 'study-3')
        self.check_command(res, text, 'study-3')
        self.check_sections(res, text)

    def test_another_run_id_is_named_in_the_command_and_a_zero_cost_is_printed(self):
        res, text = self.run_analysis('study3-scored-1', give_run_id=True, zero_cost_runs=2)
        self.assertEqual(res['inputs']['bundle']['run'], 'study3-scored-1')
        self.assertEqual(res['counting']['zeroCost']['runsWithZeroCost'], 2)
        self.assertIsNotNone(res['counting']['zeroCost']['replacedBy'])
        self.check_command(res, text, 'study3-scored-1')
        self.check_sections(res, text)


class ForwardAggregateTests(Workspace):
    def test_the_forward_aggregates_are_reported_with_their_tasks_and_ratio(self):
        tasks, directions = simulate3.tasks_of_shape()
        expected = {t['id'] for t in tasks if t['set'] == 'core' and t['category'] == 'E' and directions[t['id']]['direction'] == 'forward'}
        facts = self.bundle(vendor_error_rate=0.0)
        folder = Path(facts['bundle'])
        calls = {'delta': 9, 'epsilon': 9, 'gamma': 19}  # federation over GraphQL Adapters: (1 + 9) / (1 + 19) = 0.5 on every pair
        for path in sorted(folder.glob('runs/*/result.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record['taskId'] in expected and record['scenario'] in calls:
                edit_json(path, lambda r: r.update(toolCalls=calls[r['scenario']]))
        simulate2.write_scores(folder)
        facts = reseal(facts)
        *_, records, _, _ = data3.load(facts['bundle'], facts['sums'], facts['runId'], facts['checksum'], facts['corpus'])
        self.assertEqual({r['task'] for r in records if r['forwardAggregate']}, expected)
        self.assertEqual(run_cli(args_for(facts, self.root / 'out'))[0], 0)
        res = json.loads((self.root / 'out' / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual(res['descriptive']['perStratum']['forwardAggregates'], {'tasks': 10, 'p1Ratio': 0.5})

    def test_a_group_with_no_complete_runs_is_not_estimable(self):
        group = analyze3.per_stratum([], MODELS)['forwardAggregates']
        self.assertEqual((group['tasks'], group['estimable']), (0, False))


class AllRunsMissingTests(Workspace):
    def test_a_bundle_with_every_run_a_vendor_error_still_writes_its_outputs(self):
        facts = self.bundle(vendor_error_rate=1.0, requeue_failure=1.0)
        code, _, err = run_cli(args_for(facts, self.root / 'out'))
        self.assertEqual(code, 0, err)
        res = json.loads((self.root / 'out' / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual(res['confirmatory']['effort']['toolCalls']['method'], 'notEstimable')
        self.assertEqual(res['confirmatory']['csl']['method'], 'notEstimable')
        self.assertFalse(res['confirmatory']['floors']['gamma']['cleared'])
        self.assertTrue((self.root / 'out' / 'tables.md').is_file())


class HarnessBundleTests(Workspace):
    """One fake bundle written by study/harness/runner.py on its fakes (study 2's fixture), with a directions map added to its corpus."""

    def test_the_analysis_reads_the_bundle_the_harness_writes(self):
        import test_analysis2
        with mock.patch.object(test_analysis2.data2, 'PLAN', data3.PLAN):
            facts = test_analysis2.HarnessBundleTests.harness_bundle(self)
        corpus = Path(facts['corpus'])
        directions = ('forward', 'reverse', 'none')

        def add(document):
            document['directions'] = {t['id']: {'direction': directions[i % 3], 'csl': None, 'anchor': 'missions',
                                                'requiredSystems': ['missions'] if i % 2 else ['assets', 'missions']} for i, t in enumerate(document['tasks'])}

        edit_json(corpus / 'tasks.json', add)
        edit_json(corpus / 'corpus-manifest.json', lambda m: m['files'].update({'tasks.json': data3.sha256_file(corpus / 'tasks.json')}))
        edit_json(Path(facts['bundle']) / 'manifest.json', lambda m: m['identity'].update(corpusFreeze=data3.sha256_file(corpus / 'corpus-manifest.json')))
        facts = reseal(facts)
        code, _, err = run_cli(args_for(facts, self.root / 'out-harness'))
        self.assertEqual(code, 0, err)
        res = json.loads((self.root / 'out-harness' / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual(res['counting']['runs'], 18 * 2 * 4 + 18 * 2)


class ReviewRegressionTests(unittest.TestCase):
    """The defects a review of the analysis found, each as the case that exposed it."""

    @staticmethod
    def runs(task, arms):
        """A task's two model-and-round pairs, with the tool calls of each arm given."""
        return [{'task': task, 'arm': arm, 'model': model, 'row': row, 'toolCalls': calls} for model, row in ((MODELS[0], 1), (MODELS[1], 3)) for arm, calls in arms.items()]

    def test_a_missing_federated_arm_never_changes_the_federation_weights(self):
        complete = self.runs('T1', {'delta': 1, 'epsilon': 49, 'gamma': 9})
        self.assertAlmostEqual(stats3.per_task_contrasts(complete, MODELS)['T1'], 0.0, places=9)
        one_pair_lost = [r for r in complete if not (r['arm'] == 'epsilon' and r['row'] == 1)]
        self.assertAlmostEqual(stats3.per_task_contrasts(one_pair_lost, MODELS)['T1'], 0.0, places=9, msg='the pair without Cosmo is left out')
        self.assertNotIn('T1', stats3.per_task_contrasts([r for r in complete if r['arm'] != 'epsilon'], MODELS))

    def test_a_round_with_no_runs_is_an_empty_required_cell_and_not_a_smaller_standard(self):
        records, strata = simulate3.study_records(4, simulate3.effects_at(100), missing=0.0)
        lost = [dict(r, correct=None, outcome='vendor_error') if r['row'] == 4 else r for r in records]
        result = stats3.confirmatory(lost, MODELS, strata, REPLICATES)
        for floor in result['floors'].values():
            self.assertFalse(floor['estimable'])
            self.assertFalse(floor['cleared'])
        for family in result['effort'].values():
            self.assertEqual(family['method'], 'notEstimable')
            self.assertEqual(family['comparisons'], [])

    def test_the_coverage_truth_follows_the_effects_each_task_was_given(self):
        for options, expected in (({'reverse_gone': True}, -0.2389 * (1 - 30 / 107)), ({'join': True}, -0.2389 - 0.18 * 52 / 107)):
            found = validate3.true_log_ratio(simulate3.effects_at(100, **options), 'toolCalls', 'P1', draws=400000)
            self.assertAlmostEqual(found, expected, delta=0.006, msg=str(options))

    def test_a_study_that_cannot_be_estimated_counts_as_no_claim(self):
        estimated = {'method': 'gee', 'comparisons': [{'id': 'P1', 'rejected': True, 'claimed': True, 'logLow': -1.0, 'logHigh': 1.0},
                                                      {'id': 'P2', 'rejected': False, 'claimed': False, 'logLow': -1.0, 'logHigh': 1.0}]}
        absent = {'method': 'notEstimable', 'comparisons': []}
        csl = {'method': 'notEstimable', 'tests': []}
        floors = {'gamma': {'cleared': True, 'estimable': True}}
        truth = {(o, c): 0.0 for o in stats3.EFFORT_FAMILIES for c in ('P1', 'P2')}
        results = [validate3.summarize_one({'effort': {'toolCalls': family, 'cost': family}, 'csl': csl, 'floors': floors}, truth) for family in (estimated, absent)]
        tallied = validate3.tally(results)
        self.assertEqual(tallied['toolCalls.P1.claimed'], 0.5)
        self.assertEqual(tallied['toolCalls.P1.rejected'], 0.5)
        self.assertEqual(tallied['toolCalls.P1.estimable'], 0.5)
        self.assertEqual(tallied['toolCalls.P1.covered'], 1.0, 'coverage is conditional on an estimate, and its availability is reported beside it')
        self.assertEqual(tallied['csl.forwardReverse.rejected'], 0.0)

    def test_a_csl_false_positive_is_listed_wherever_the_csl_effects_are_null(self):
        clean = {'toolCalls.any': 0.05, 'cost.any': 0.05, 'csl.any': 0.05, 'csl.forwardReverse.alone': 0.05, 'csl.joinWidth.alone': 0.05, 'toolCalls.P1.covered': 0.95}
        floors = {'selected': {'floor.gamma.cleared': 0.02, 'floor.beta.cleared': 0.02}}
        report = {name: {'selected': dict(clean), 'forced': dict(clean)} for name in ('null', 'effort-100', 'effort-75', 'effort-50')}
        report.update({name: floors for name in validate3.BOUNDARY})
        report['effort-75']['selected']['csl.any'] = 0.50
        self.assertIn(('effort-75/selected', 'csl.any'), {(e['scenario'], e['measure']) for e in validate3.checks(report)})

    def test_a_session_boundary_inside_a_round_enters_the_fits(self):
        records, strata = simulate3.study_records(6, session_boundary=validate3.SESSION_BOUNDARY)
        self.assertEqual({r['session'] for r in records}, {'s-1', 's-2'})
        self.assertTrue(any(len({r['session'] for r in records if r['row'] == row}) == 2 for row in (1, 2, 3, 4)))
        family = stats3.confirmatory(records, MODELS, strata, REPLICATES)['effort']['toolCalls']
        self.assertEqual(family['method'], 'gee')
        self.assertEqual(len(family['fit']['sessions']), 2)

    def test_the_boundary_scenarios_run_the_whole_procedure(self):
        report = validate3.run(sims=2, workers=1, replicates=200, only=('boundary-100',))
        self.assertIn('toolCalls.method', report['boundary-100']['selected'])
        self.assertIn('csl.joinWidth.claimed', report['boundary-100']['selected'])

    def test_the_master_seed_changes_the_simulated_studies(self):
        spec = validate3.scenarios()['null']
        truth = {(o, c): 0.0 for o in stats3.EFFORT_FAMILIES for c in ('P1', 'P2')}
        self.assertEqual(validate3.one_study(('null', spec, 0, 100, truth, 1)), validate3.one_study(('null', spec, 0, 100, truth, 1)))
        drawn = []
        real = simulate3.study_records

        def recording(seed, *args, **kwargs):
            drawn.append((seed, kwargs['plan_seed']))
            return real(seed, *args, **kwargs)

        with mock.patch.object(simulate3, 'study_records', recording):
            for master in (1, 2):
                validate3.one_study(('null', spec, 0, 100, truth, master))
        self.assertNotEqual(drawn[0][0], drawn[1][0])
        self.assertNotEqual(drawn[0][1], drawn[1][1])
        self.assertEqual(sorted(validate3.code_hashes()), sorted(validate3.CODE))

    def test_a_study_with_every_core_run_missing_is_reported_as_not_estimable(self):
        records, strata = simulate3.study_records(4, missing=0.0)
        result = stats3.confirmatory([dict(r, correct=None, outcome='vendor_error') for r in records], MODELS, strata, REPLICATES)
        for floor in result['floors'].values():
            self.assertFalse(floor['estimable'])
            self.assertFalse(floor['cleared'])
        for family in result['effort'].values():
            self.assertEqual(family['method'], 'notEstimable')
        self.assertEqual(result['csl']['method'], 'notEstimable')

    def test_the_effort_fallback_needs_more_tasks_than_strata(self):
        records, _ = simulate3.study_records(4, missing=0.0)
        tasks = sorted({r['task'] for r in records})[:2]
        rows = [r for r in records if r['task'] in tasks]
        fallback = stats3.effort_fallback(rows, 'cost', MODELS, {t: t for t in tasks}, REPLICATES, rounds=[1, 2, 3, 4])
        self.assertFalse(fallback['estimable'])

    def test_coverage_is_checked_in_the_scenarios_with_csl_effects(self):
        clean = {'toolCalls.any': 0.05, 'cost.any': 0.05, 'csl.any': 0.05, 'csl.forwardReverse.alone': 0.05, 'csl.joinWidth.alone': 0.05, 'toolCalls.P1.covered': 0.95}
        floors = {'selected': {'floor.gamma.cleared': 0.02, 'floor.beta.cleared': 0.02}}
        report = {name: {'selected': dict(clean), 'forced': dict(clean)} for name in ('null', 'effort-100', 'effort-75', 'effort-50')}
        report.update({name: floors for name in validate3.BOUNDARY})
        report['both-100'] = {'selected': {'toolCalls.P1.covered': 0.80}, 'forced': {'toolCalls.P1.covered': 0.95}}
        self.assertIn(('both-100/selected', 'toolCalls.P1.covered'), {(e['scenario'], e['measure']) for e in validate3.checks(report)})


class PowerTests(unittest.TestCase):
    def test_the_power_script_reproduces_the_calculation_within_its_error(self):
        contrasts, _ = power3.load_contrasts()
        for line in power3.reproduction(contrasts):
            self.assertLess(abs(line['thisScript'] - line['reference']), 0.02, line['figure'])

    def test_the_join_width_difference_is_the_decided_one(self):
        contrasts, tasks = power3.load_contrasts()
        self.assertAlmostEqual(power3.join_width_difference(contrasts, tasks)['difference'], simulate3.STUDY2['joinWidth'], places=2)

    def test_the_100_percent_effects_are_study_2s(self):
        contrasts, _ = power3.load_contrasts()
        for outcome in ('toolCalls', 'cost'):
            for label in ('P1', 'P2'):
                self.assertAlmostEqual(float(contrasts[(outcome, label)].mean()), simulate3.STUDY2[outcome][label], places=3)


class ValidationTests(unittest.TestCase):
    def test_the_small_validation_runs_the_whole_procedure(self):
        report = validate3.run(sims=4, workers=1, replicates=200, only=('null', 'boundary-tasks'))
        self.assertIn('toolCalls.method', report['null']['selected'])
        self.assertIn('csl.joinWidth.alone', report['null']['forced'])
        self.assertEqual(report['null']['forced']['toolCalls.method'], {'bootstrap': 1.0})
        self.assertIn('floor.gamma.cleared', report['boundary-tasks']['selected'])

    def test_each_scenario_reports_the_group_differences_it_generates(self):
        alone = validate3.generated_effects(simulate3.effects_at(100, join=True))
        both = validate3.generated_effects(simulate3.effects_at(100, reverse_gone=True, join=True))
        self.assertAlmostEqual(alone['severalMinusOne'], simulate3.STUDY2['joinWidth'], places=6)
        self.assertGreater(both['severalMinusOne'], alone['severalMinusOne'], 'direction contributes to the difference between the join-width groups')
        self.assertAlmostEqual(both['reverseMinusForward'] - alone['reverseMinusForward'], -simulate3.STUDY2['toolCalls']['P1'], delta=0.1)

    def test_a_rate_past_a_threshold_is_listed(self):
        clean = {'toolCalls.any': 0.05, 'cost.any': 0.05, 'csl.any': 0.05, 'csl.forwardReverse.alone': 0.05, 'csl.joinWidth.alone': 0.05, 'toolCalls.P1.covered': 0.95}
        floors = {'selected': {'floor.gamma.cleared': 0.02, 'floor.beta.cleared': 0.02}}
        report = {name: {'selected': dict(clean), 'forced': dict(clean)} for name in ('null', 'effort-100', 'effort-75', 'effort-50')}
        report.update({name: floors for name in validate3.BOUNDARY})
        self.assertEqual(validate3.checks(report), [])
        report['null']['selected']['cost.any'] = 0.07
        report['effort-75']['forced']['toolCalls.P1.covered'] = 0.92
        report['boundary-100'] = {'selected': {'floor.gamma.cleared': 0.04, 'floor.beta.cleared': 0.02}}
        self.assertEqual({(e['scenario'], e['measure']) for e in validate3.checks(report)},
                         {('null/selected', 'cost.any'), ('effort-75/forced', 'toolCalls.P1.covered'), ('boundary-100', 'floor.gamma.cleared')})


class LongContextCostTests(Workspace):
    """Decisions L1 and N1 of the Job study3_openai_long_context: each run's cost is the sum of its requests' prices, a request above the
    threshold of its model's long-context rates priced at them in full."""

    def tiered(self, facts, long_key=None, drop_list=False):
        """The bundle with gpt-6.1-sol's long-context rates in its manifest and requestUsage in every record; the record of `long_key`
        holds one request of 280,000 input tokens."""
        folder = Path(facts['bundle'])
        tier = {'above_input_tokens': 272000, 'input': 4.0, 'cached_read': 0.2, 'cache_write': 5.0, 'output': 15.0}
        edit_json(folder / 'manifest.json', lambda m: m['models']['gpt-6.1-sol']['priceEntry'].update(long_context=tier))

        def listed(record):
            usage = record['usage']
            if record['runKey'] == long_key:
                usage.update(input=usage['input'] + 280_000)
                record['usageTokens'] = sum(usage.values())
                record['requestUsage'] = [{'input': 280_000, 'cached_read': 0, 'cache_write': 0, 'output': 0},
                                          {**usage, 'input': usage['input'] - 280_000}]
            elif not drop_list:
                record['requestUsage'] = [dict(usage)]
        for path in folder.glob('runs*/**/result.json'):
            edit_json(path, listed)
        return reseal(facts)

    def test_a_runs_cost_is_the_sum_of_its_requests_prices(self):
        plain = self.bundle(name='plain', vendor_error_rate=0.0)
        *_, before, _, _ = data3.load(plain['bundle'], plain['sums'], plain['runId'], plain['checksum'], plain['corpus'])
        key = next(r['runKey'] for r in before if r['model'] == 'gpt-6.1-sol' and r['cost'] > 0)
        facts = self.tiered(self.bundle(name='tiered', vendor_error_rate=0.0), long_key=key)
        *_, records, _, _ = data3.load(facts['bundle'], facts['sums'], facts['runId'], facts['checksum'], facts['corpus'])
        result = json.loads((Path(facts['bundle']) / 'runs' / key / 'result.json').read_text(encoding='utf-8'))
        price = simulate3.PRICES['gpt-6.1-sol']
        rest = result['requestUsage'][1]
        expected = 280_000 * 4.0 / 1e6 + sum(rest[k] * price[k] for k in ('input', 'cached_read', 'cache_write', 'output')) / 1e6
        long_run = next(r for r in records if r['runKey'] == key)
        self.assertAlmostEqual(long_run['cost'], expected, places=12)
        self.assertGreater(long_run['cost'], 280_000 * 2.0 / 1e6 + next(r for r in before if r['runKey'] == key)['cost'] + 0.5)
        others = {r['runKey']: r['cost'] for r in records if r['runKey'] != key}
        self.assertEqual(others, {r['runKey']: r['cost'] for r in before if r['runKey'] != key},
                         'every run with no long request is priced exactly as before')

    def test_a_record_without_its_requests_under_a_tier_stops_the_analysis(self):
        facts = self.tiered(self.bundle(vendor_error_rate=0.0), drop_list=True)
        with self.assertRaisesRegex(data3.VerificationError, 'without requestUsage'):
            data3.load(facts['bundle'], facts['sums'], facts['runId'], facts['checksum'], facts['corpus'])

    def test_a_malformed_request_list_stops_the_analysis_naming_its_record(self):
        usage = {'input': 10, 'cached_read': 0, 'cache_write': 0, 'output': 5}
        prices = {'gpt-6.1-sol': simulate3.PRICES['gpt-6.1-sol']}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            for request_usage in (12, 'usage', [7], [{**usage, 'output': None}]):
                path.write_text(json.dumps({'model': 'gpt-6.1-sol', 'usage': usage, 'requestUsage': request_usage}), encoding='utf-8')
                with self.subTest(request_usage=request_usage), self.assertRaisesRegex(data3.VerificationError, 'result.json: .*requestUsage'):
                    data3.record_cost(path, prices)

    def test_power3_refuses_a_tiered_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp)
            (evidence / 'scores.csv').write_bytes((power3.EVIDENCE / 'scores.csv').read_bytes())
            manifest = json.loads((power3.EVIDENCE / 'manifest.json').read_text(encoding='utf-8'))
            manifest['models']['gpt-6.1-sol']['priceEntry']['long_context'] = {'above_input_tokens': 272000, 'input': 4.0, 'cached_read': 0.2,
                                                                               'cache_write': 5.0, 'output': 15.0}
            (evidence / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'long-context rates'):
                power3.load_contrasts(evidence)


if __name__ == '__main__':
    unittest.main()
