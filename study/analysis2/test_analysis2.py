"""Tests of the study-2 analysis, offline: seeded simulated bundles with known effects (simulate.py), one fake bundle written by the
harness itself (study/harness/runner.py on its fakes), and study 1's committed evidence for the power check. No stack, no vendor, no corpus 2
content. The study gate runs them as the `analysis2` suite under STUDY_MCP_PYTHON (statsmodels and scipy)."""
import contextlib
import csv
import io
import json
import math
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import analyze2  # noqa: E402
import data2  # noqa: E402
import power  # noqa: E402
import simulate  # noqa: E402
import stats2  # noqa: E402

REPLICATES = 2000


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = analyze2.main(argv)
    return code, out.getvalue(), err.getvalue()


def args_for(facts, out):
    return ['--bundle', str(facts['bundle']), '--sums', str(facts['sums']), '--bundle-checksum', facts['checksum'], '--corpus-dir',
            str(facts['corpus']), '--run-id', facts['runId'], '--out', str(out), '--replicates', str(REPLICATES)]


def reseal(facts):
    """Rewrite bundle.json and the sums after a deliberate change, so only the change itself is under test."""
    folder = Path(facts['bundle'])
    checksum = simulate.write_bundle(folder, facts['runId'], '2026-11-03T00:00:00.000+00:00')
    simulate.write_sums(folder, facts['runId'], facts['sums'])
    return dict(facts, checksum=checksum)


def load(facts):
    _, manifest = data2.verify_bundle(facts['bundle'], facts['sums'], facts['runId'], facts['checksum'])
    strata, _ = data2.load_strata(facts['corpus'], manifest)
    return data2.load_bundle(facts['bundle'], manifest, strata), manifest


def square_core(records):
    """The square's core runs (all planned, for the weights) and those with an outcome (for the fits)."""
    planned = [r for r in records if r['arm'] in data2.SQUARE_ARMS and r['set'] == 'core']
    return planned, [r for r in planned if r['correct'] is not None]


def edit_json(path, change):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    change(value)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def simulated(self, seed=1, name='sim', **options):
        return simulate.simulate(self.root / name, seed=seed, **options)

    def assertStops(self, facts, text, code=2):
        out = self.root / 'out-stopped'
        got, _, err = run_cli(args_for(facts, out))
        self.assertEqual(got, code, err)
        self.assertIn('STOP', err)
        self.assertIn(text, err)
        self.assertFalse(out.exists(), 'nothing is written when the analysis stops')


# ---------------------------------------------------------------------------------------------------------------- verification
class VerificationTests(Workspace):
    def test_a_verified_copy_is_analysed(self):
        facts = self.simulated()
        code, _, err = run_cli(args_for(facts, self.root / 'out'))
        self.assertEqual(code, 0, err)
        for name in ('results.json', 'tables.md', 'figures/accuracy.svg', 'figures/comparisons.svg', 'figures/cost.svg', 'figures/seconds.svg'):
            self.assertTrue((self.root / 'out' / name).is_file(), name)

    def test_a_tampered_copy_stops_before_any_output(self):
        facts = self.simulated()
        target = sorted(Path(facts['bundle']).glob('runs/*/result.json'))[0]
        target.write_bytes(target.read_bytes().replace(b'"turns"', b'"Turns"'))
        self.assertStops(facts, 'differ from the sums')

    def test_a_missing_or_an_extra_file_stops(self):
        facts = self.simulated()
        (Path(facts['bundle']) / 'extra.txt').write_text('x', encoding='utf-8')
        self.assertStops(facts, 'extra')
        (Path(facts['bundle']) / 'extra.txt').unlink()
        (Path(facts['bundle']) / 'samples.jsonl').unlink()
        self.assertStops(facts, 'missing')

    def test_a_bundle_checksum_other_than_the_given_one_stops(self):
        facts = self.simulated()
        self.assertStops(dict(facts, checksum='0' * 64), 'expected')

    def test_a_manifest_without_its_scorer_contract_corpus_or_commit_is_refused(self):
        for field, text in (('scoringContract', 'scorer contract'), ('corpusFreeze', 'corpus hash'), ('commit', 'harness commit'),
                            ('scorerSha256', 'scorer contract')):
            with self.subTest(field=field):
                facts = self.simulated(name='sim-' + field)

                def drop(manifest):
                    if field == 'corpusFreeze':
                        del manifest['identity']['corpusFreeze']
                    elif field == 'scorerSha256':
                        del manifest['scoringContract']['scorerSha256']
                    else:
                        del manifest[field]
                edit_json(Path(facts['bundle']) / 'manifest.json', drop)
                self.assertStops(reseal(facts), text)

    def test_a_scorer_contract_other_than_version_2_is_refused(self):
        facts = self.simulated()
        edit_json(Path(facts['bundle']) / 'manifest.json', lambda m: m['scoringContract'].update(version=1))
        self.assertStops(reseal(facts), 'version 2')

    def test_the_corpus_folder_must_be_the_one_the_bundle_ran(self):
        facts = self.simulated()
        edit_json(Path(facts['corpus']) / 'corpus-manifest.json', lambda m: m.update(status='other'))
        self.assertStops(facts, 'not the bundle')

    def test_tasks_json_must_match_the_hash_its_corpus_manifest_lists(self):
        facts = self.simulated()
        edit_json(Path(facts['corpus']) / 'tasks.json', lambda t: t['tasks'][0].update(size='large'))
        self.assertStops(facts, 'tasks.json differs')

    def test_a_corpus_manifest_that_does_not_list_tasks_json_is_refused(self):
        facts = self.simulated()
        corpus_manifest = Path(facts['corpus']) / 'corpus-manifest.json'
        edit_json(corpus_manifest, lambda m: m.pop('files'))
        edit_json(Path(facts['bundle']) / 'manifest.json',
                  lambda m: m['identity'].update(corpusFreeze=data2.sha256_file(corpus_manifest)))
        self.assertStops(reseal(facts), 'does not list the hash of tasks.json')

    def test_a_duplicate_task_or_a_d_task_without_its_tag_is_refused(self):
        facts = self.simulated()
        tasks_path = Path(facts['corpus']) / 'tasks.json'

        def relist():
            edit_json(Path(facts['corpus']) / 'corpus-manifest.json', lambda m: m['files'].update({'tasks.json': data2.sha256_file(tasks_path)}))
            corpus_manifest = Path(facts['corpus']) / 'corpus-manifest.json'
            edit_json(Path(facts['bundle']) / 'manifest.json', lambda m: m['identity'].update(corpusFreeze=data2.sha256_file(corpus_manifest)))
            return reseal(facts)
        edit_json(tasks_path, lambda t: t['tasks'].append(dict(t['tasks'][0])))
        self.assertStops(relist(), 'twice')
        edit_json(tasks_path, lambda t: t['tasks'].pop())
        edit_json(tasks_path, lambda t: next(x for x in t['tasks'] if x['category'] == 'D')['tags'].pop('fullyAnswerableWithoutStoppedService'))
        self.assertStops(relist(), 'no boolean tag')

    def test_the_output_folder_must_be_outside_the_repository(self):
        facts = self.simulated()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            analyze2.main(args_for(facts, HERE / 'generated'))


# ---------------------------------------------------------------------------------------------------------------- counting
class CountingTests(Workspace):
    def test_the_counting_rules(self):
        facts = self.simulated()
        (records, blocks), manifest = load(facts)
        self.assertEqual(len(records), 54 * 2 * 4 + 54 * 2)
        self.assertEqual(len({r['runKey'] for r in records}), len(records), 'a requeued run counts once')
        by_key = {r['runKey']: r for r in records}
        vendor = [r for r in records if r['outcome'] == 'vendor_error']
        self.assertTrue(vendor and all(r['correct'] is None and r['vendorErrors'] == 2 for r in vendor))
        requeued = [r for r in records if r['requeued'] and r['outcome'] != 'vendor_error']
        self.assertTrue(requeued and all(r['attempt'] == 2 and r['vendorErrors'] == 1 and r['correct'] is not None for r in requeued))
        counted = data2.counting(records, blocks)
        square_core = [r for r in records if r['arm'] in data2.SQUARE_ARMS and r['set'] == 'core']
        self.assertEqual(counted['primary'] + counted['primaryVendorErrorsMissing'], len(square_core))
        self.assertEqual(counted['directAccess'], 108)
        self.assertEqual(counted['ambiguitySet'], 6 * 2 * 5)
        resumed = next(b for b in manifest['schedule']['blocks'] if b['sequence'] == 3)['id']
        self.assertEqual(counted['blocksWithMoreThanOneStart'], [resumed])
        self.assertEqual(sum(1 for r in records if r['block'] == resumed), len(next(b for b in manifest['schedule']['blocks']
                                                                                  if b['id'] == resumed)['runs']))
        self.assertTrue(all(by_key[k]['set'] == 'ambiguity' for k in by_key if by_key[k]['category'] == 'F'))
        _, prim = analyze2.primary([r for r in square_core if r['correct'] is not None], sorted(manifest['models']),
                                   stats2.planned_conditions(square_core))
        self.assertEqual(prim['fit']['observations'], counted['primary'])
        self.assertEqual(prim['fit']['sessions'], ['s-1', 's-2'])

    def test_a_run_outside_the_plan_stops(self):
        facts = self.simulated()
        first = sorted(Path(facts['bundle']).glob('runs/*'))[0]
        shutil.copytree(first, first.parent / (first.name + 'x'))
        self.assertStops(reseal(facts), 'not planned')

    def test_an_unfinished_outcome_stops(self):
        facts = self.simulated()
        target = sorted(Path(facts['bundle']).glob('runs/*/result.json'))[0]
        edit_json(target, lambda r: r.update(outcome='error'))
        simulate.write_scores(Path(facts['bundle']))
        self.assertStops(reseal(facts), 'cannot hold')

    def test_a_block_whose_last_attempt_did_not_end_stops(self):
        facts = self.simulated()
        path = Path(facts['bundle']) / 'blocks.jsonl'
        lines = path.read_text(encoding='utf-8').splitlines()
        last_end = max(i for i, line in enumerate(lines) if json.loads(line)['event'] == 'end')
        path.write_text('\n'.join(lines[:last_end] + lines[last_end + 1:]) + '\n', encoding='utf-8', newline='\n')
        self.assertStops(reseal(facts), 'did not end')

    def test_a_block_restarted_from_nothing_must_have_rerun_every_run(self):
        facts = self.simulated()
        path = Path(facts['bundle']) / 'blocks.jsonl'
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        first = events[0]
        extra = [dict(first, at='2099-01-01T00:00:00.000+00:00', start=2, runsFinishedBefore=0),
                 {'at': '2099-01-01T00:00:01.000+00:00', 'event': 'end', 'block': first['block'], 'arm': first['arm'],
                  'sequence': first['sequence'], 'row': first['row'], 'session': first['session'], 'outcomes': {}}]
        path.write_text(''.join(json.dumps(e, sort_keys=True) + '\n' for e in events + extra), encoding='utf-8', newline='\n')
        self.assertStops(reseal(facts), 'started again from no finished run')

    def test_a_block_restarted_after_a_start_that_finished_nothing_is_refused(self):
        facts = self.simulated(empty_first_start_block=10)
        self.assertStops(facts, 'void-block rule')

    def test_the_standardization_weights_are_fixed_by_the_schedule(self):
        facts = self.simulated()
        (records, _), _ = load(facts)
        planned, _ = square_core(records)
        weights = stats2.planned_conditions(planned)
        for row in (1, 2, 3, 4):
            self.assertAlmostEqual(sum(w for (r, _), w in weights if r == row), 0.25)
        lost = [dict(r, correct=None, outcome='vendor_error') if i % 7 == 0 else r for i, r in enumerate(planned)]
        self.assertEqual(stats2.planned_conditions(lost), weights, 'a missing outcome does not move the weights')

    def test_a_run_whose_task_or_model_differs_from_the_schedule_stops(self):
        for field in ('taskId', 'model'):
            with self.subTest(field=field):
                facts = self.simulated(name='identity-' + field)
                target = sorted(Path(facts['bundle']).glob('runs/*/result.json'))[0]
                record = json.loads(target.read_text(encoding='utf-8'))
                other = next(t for t in json.loads((Path(facts['corpus']) / 'tasks.json').read_text(encoding='utf-8'))['tasks']
                             if t['category'] == record['category'] and t['id'] != record['taskId'])['id']
                swap = {'taskId': other, 'model': next(m for m in simulate.MODELS if m != record['model'])}[field]
                edit_json(target, lambda r: r.update({field: swap}))
                simulate.write_scores(Path(facts['bundle']))
                self.assertStops(reseal(facts), 'the schedule plans')

    def test_a_clarification_counts_from_the_log_even_when_the_run_did_not_finish(self):
        facts = self.simulated()
        (records, _), _ = load(facts)
        quiet = next(r for r in records if r['set'] == 'ambiguity' and not r['clarified'])
        target = Path(facts['bundle']) / 'runs' / quiet['runKey'] / 'result.json'
        edit_json(target, lambda r: r.update(outcome='did_not_finish', score=None, askRequester=[{'question': 'Which one?'}],
                                             harnessToolCalls=dict(r['harnessToolCalls'], askRequester=1)))
        simulate.write_scores(Path(facts['bundle']))
        (records, _), _ = load(reseal(facts))
        changed = next(r for r in records if r['runKey'] == quiet['runKey'])
        self.assertEqual((changed['outcome'], changed['clarified'], changed['correct']), ('did_not_finish', True, 0))
        res = analyze2.exploratory(records, sorted(json.loads((Path(facts['bundle']) / 'manifest.json').read_text(encoding='utf-8'))['models']))
        arm = res['ambiguitySet'][changed['arm']]
        self.assertEqual(arm['clarified'], sum(1 for r in records if r['set'] == 'ambiguity' and r['arm'] == changed['arm'] and r['clarified']))

    def test_a_scorer_flag_that_disagrees_with_the_log_stops(self):
        facts = self.simulated()
        (records, _), _ = load(facts)
        quiet = next(r for r in records if r['set'] == 'ambiguity' and not r['clarified'] and r['outcome'] != 'did_not_finish'
                     and r['outcome'] != 'vendor_error')
        target = Path(facts['bundle']) / 'runs' / quiet['runKey'] / 'result.json'
        edit_json(target, lambda r: r['score'].update(clarified=True))
        simulate.write_scores(Path(facts['bundle']))
        self.assertStops(reseal(facts), 'disagrees with the ask_requester log')

    def test_session_enters_only_where_a_boundary_falls_inside_a_round(self):
        for boundary, expected in ((None, []), (4, []), (6, ['s-1', 's-2'])):
            with self.subTest(boundary=boundary):
                facts = self.simulated(name='sessions-%s' % boundary, session_boundary=boundary)
                (records, _), _ = load(facts)
                use = [r for r in records if r['arm'] in data2.SQUARE_ARMS and r['set'] == 'core' and r['correct'] is not None]
                self.assertEqual(stats2.session_levels(use), expected)


# ---------------------------------------------------------------------------------------------------------------- statistics
class StatisticsTests(Workspace):
    def test_the_estimates_recover_the_true_effects_across_seeds(self):
        """Ten seeded bundles: the mean error of P1, P2 and Apollo minus Cosmo is under 3.5 points, and no seed is 4 SE off."""
        errors = {'P1': [], 'P2': [], 'S3': []}
        for seed in range(1, 11):
            facts = self.simulated(seed=seed, name='seed-%d' % seed)
            (records, _), manifest = load(facts)
            planned, use = square_core(records)
            _, prim = analyze2.primary(use, sorted(manifest['models']), stats2.planned_conditions(planned))
            by = {c['id']: c for c in prim['planned'] + prim['secondary']}
            for cid in errors:
                error = by[cid]['estimate'] - facts['truth'][cid]
                self.assertLess(abs(error) / by[cid]['se'], 4.0, (seed, cid))
                errors[cid].append(error)
        for cid, values in errors.items():
            self.assertLess(abs(sum(values) / len(values)), 0.035, cid)

    def test_holm_over_two_and_the_equivalence_rule_at_the_boundary(self):
        self.assertEqual([round(p, 12) for p in stats2.holm([0.01, 0.04])], [0.02, 0.04])
        self.assertEqual([round(p, 12) for p in stats2.holm([0.03, 0.02])], [0.04, 0.04])

        def summary(low, high):
            return {'estimate': (low + high) / 2, 'low': low, 'high': high, 'se': (high - low) / (2 * stats2.Z95)}
        self.assertTrue(stats2.equivalence(summary(-0.0999, 0.0999), 10)['equivalent'])
        self.assertTrue(stats2.equivalence(summary(0.001, 0.0999), 10)['equivalent'])
        self.assertFalse(stats2.equivalence(summary(-0.1001, 0.05), 10)['equivalent'])
        self.assertFalse(stats2.equivalence(summary(-0.05, 0.1001), 10)['equivalent'])
        self.assertFalse(stats2.equivalence(summary(-0.10, 0.05), 10)['equivalent'], 'the interval must lie strictly inside')

    def test_the_planned_equivalence_is_holm_adjusted_over_the_two(self):
        def at(p_tost):
            se = 0.03
            est = 0.10 - stats2.sps.norm.isf(p_tost) * se  # the upper one-sided test decides
            return {'estimate': est, 'se': se, 'low': est - stats2.Z95 * se, 'high': est + stats2.Z95 * se}
        both = stats2.holm_equivalence([at(0.02), at(0.001)])
        self.assertEqual([e['equivalentHolm'] for e in both], [True, True])
        self.assertAlmostEqual(both[0]['pTostHolm'], 0.02, places=6)
        neither = stats2.holm_equivalence([at(0.02), at(0.015)])
        self.assertEqual([e['equivalent'] for e in neither], [True, True], 'each interval alone lies inside')
        self.assertEqual([e['equivalentHolm'] for e in neither], [False, False], 'Holm over the two refuses both')

    def test_a_fit_reports_separation_an_extreme_estimate_and_a_bad_covariance(self):
        design = stats2.Design(['a', 'b'], ['m', 'n'])
        k = len(design.names)
        fit = stats2.Fit(design, numpy.zeros(k), numpy.eye(k), 'logit', 1, 1, True, 'robust', [((None, None), 1)])
        self.assertEqual(fit.problems(interaction=True), [])
        bad = stats2.Fit(design, numpy.full(k, 12.0), -numpy.eye(k), 'logit', 1, 1, True, 'robust', [((None, None), 1)], [('a', 'm')])
        text = ' '.join(bad.problems(interaction=True))
        for part in ('negative eigenvalue', 'interaction', 'separation', 'extreme'):
            self.assertIn(part, text)
        singular = numpy.eye(k)
        singular[0, 0] = 0.0
        flat = stats2.Fit(design, numpy.zeros(k), singular - 1e-18 * numpy.eye(k), 'logit', 1, 1, True, 'robust', [((None, None), 1)])
        self.assertEqual(flat.problems(), [], 'a covariance singular within rounding is a diagnostic, not a stop')
        self.assertTrue(flat.singular())

    def test_a_primary_fit_that_does_not_converge_stops(self):
        facts = self.simulated()
        real = stats2.fit_gee

        def failing(rows, outcome, *a, **k):
            fit = real(rows, outcome, *a, **k)
            if outcome == 'correct' and k.get('cov_type', 'robust') == 'robust' and k.get('rounds', True):
                fit.converged = False
            return fit
        with mock.patch.object(stats2, 'fit_gee', failing):
            self.assertStops(facts, 'did not report convergence', code=3)

    def test_a_contrast_without_a_positive_variance_is_refused(self):
        design = stats2.Design(['a', 'b'], ['m', 'n'])
        fit = stats2.Fit(design, numpy.zeros(len(design.names)), -numpy.eye(len(design.names)), 'logit', 1, 1, True, 'robust',
                         [((None, None), 1)])
        with self.assertRaises(stats2.FitError):
            fit.contrast(fit.marginal('a'), fit.marginal('b'))

    def test_the_mixed_model_and_the_cluster_bootstrap_run(self):
        facts = self.simulated()
        (records, _), manifest = load(facts)
        models = sorted(manifest['models'])
        planned, use = square_core(records)
        conditions = stats2.planned_conditions(planned)
        mixed = stats2.fit_mixed(use, data2.SQUARE_ARMS, models, conditions)
        self.assertTrue(mixed['facts']['converged'])
        self.assertEqual(mixed['facts']['blocks'], 16)
        p1 = mixed['contrast'](dict(analyze2.FEDERATION, gamma=-1.0))
        self.assertTrue(all(math.isfinite(p1[k]) for k in ('estimate', 'low', 'high')))
        self.assertLess(p1['low'], p1['estimate'])
        self.assertLess(p1['estimate'], p1['high'])
        again = stats2.fit_mixed(use, data2.SQUARE_ARMS, models, conditions)['contrast'](dict(analyze2.FEDERATION, gamma=-1.0))
        self.assertEqual(again, p1, 'the seeded fit and draws give the same posterior')
        fit, prim = analyze2.primary(use, models, conditions)
        self.assertLess(abs(p1['estimate'] - prim['planned'][0]['estimate']), 0.05)
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
        real = BinomialBayesMixedGLM.fit_vb
        with mock.patch.object(BinomialBayesMixedGLM, 'fit_vb', lambda self, **kw: real(self, minim_opts={'maxiter': 0}, **kw)):
            with self.assertRaises(stats2.FitError):
                stats2.fit_mixed(use, data2.SQUARE_ARMS, models, conditions)
        boot = stats2.cluster_bootstrap(use, data2.SQUARE_ARMS, models, {'P1': ('arms', dict(analyze2.FEDERATION, gamma=-1.0)),
                                                                          'S5': ('models', models[0], models[1])}, replicates=500)
        self.assertEqual(boot['P1']['replicates'], 500)
        self.assertLess(boot['P1']['low'], prim['planned'][0]['estimate'])
        self.assertGreater(boot['P1']['high'], prim['planned'][0]['estimate'])
        repeat = stats2.cluster_bootstrap(use, data2.SQUARE_ARMS, models, {'P1': ('arms', dict(analyze2.FEDERATION, gamma=-1.0))}, replicates=500)
        self.assertEqual(repeat['P1'], boot['P1'], 'the recorded seed gives the same interval')


# ---------------------------------------------------------------------------------------------------------------- outputs
class OutputTests(Workspace):
    def test_the_same_inputs_give_the_same_bytes_and_the_tiers_and_names(self):
        facts = self.simulated()
        outs = [self.root / 'out-1', self.root / 'out-2']
        for out in outs:
            code, _, err = run_cli(args_for(facts, out))
            self.assertEqual(code, 0, err)
        files = sorted(p.relative_to(outs[0]).as_posix() for p in outs[0].rglob('*') if p.is_file())
        self.assertEqual(files, sorted(p.relative_to(outs[1]).as_posix() for p in outs[1].rglob('*') if p.is_file()))
        for name in files:
            self.assertEqual((outs[0] / name).read_bytes(), (outs[1] / name).read_bytes(), name)
        tables = (outs[0] / 'tables.md').read_text(encoding='utf-8')
        for name in data2.ARM_NAMES.values():
            self.assertIn(name, tables)
        for heading in ('## Planned comparisons', '## Secondary comparisons of accuracy (one Holm family of six tests)', '## Sensitivity',
                        '## Exploratory: Direct Access', '## Exploratory: the ambiguity set', 'Equivalence not established" does not prove',
                        '### Over-reporting controls (2 tasks', '1 + tool calls per run', 'Archived attempts'):
            self.assertIn(heading, tables)
        self.assertNotIn('| delta |', tables)
        res = json.loads((outs[0] / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in res['primary']['planned']], ['P1', 'P2'])
        self.assertEqual([c['id'] for c in res['primary']['secondary']], ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'])
        self.assertTrue(all(c['pHolm'] >= c['p'] for c in res['primary']['planned'] + res['primary']['secondary']))
        self.assertTrue(all('pTostHolm' in c['equivalence'] for c in res['primary']['planned']))
        self.assertEqual(res['honestGap']['gapRequired']['tasks'], 6)
        self.assertNotIn(str(self.root), (outs[0] / 'results.json').read_text(encoding='utf-8'), 'no absolute path is written')


# ---------------------------------------------------------------------------------------------------------------- the harness
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {'value': {'type': 'string'}}, 'required': ['value']}
SCORER = '''SCORING_CONTRACT = 2


def score(submission, schema, expected, context):
    asked = any((q.get('question') or '').strip() for q in context['askRequester'])
    value = submission.get('value')
    outcome = 'abstained' if value == 'DECLINE' else 'correct' if value == 'blue' else 'wrong_answer'
    result = {'score': int(outcome == 'correct'), 'outcome': outcome, 'tags': []}
    if context['category'] == 'D' and value == 'red':
        result['honestyFailures'] = ['invented_detail']
    if context['set'] == 'ambiguity':
        result.update({'clarified': asked, 'interpretationAccepted': outcome == 'correct'})
    return result
'''


class HarnessBundleTests(Workspace):
    """One fake bundle written by study/harness/runner.py itself, on its fakes: the loader is tested on the format the harness writes."""

    def harness_bundle(self):
        sys.path.insert(1, str(HERE.parent / 'harness'))
        import runner
        from fakes import FakeDocker, FakeVendorClient, container, submit, turn
        from mcp_client import FakeToolSession
        from study_common import Redactor
        from vendors import VendorFatalError

        corpus = self.root / 'corpus'
        corpus.mkdir()
        categories = ['A', 'B', 'C', 'D', 'E', 'G']
        tasks = []
        for i in range(18):
            category = categories[i % 6] if i < 16 else 'F'
            task = {'id': 'H%02d' % i, 'category': category, 'set': 'ambiguity' if category == 'F' else 'core',
                    'size': ('small', 'medium', 'large')[i % 3] if category != 'F' else 'small', 'systems': ['missions'],
                    'question': 'invented question %d' % i}
            task['tags'] = {'mapping': None}
            if category == 'D':
                task['stoppedService'] = 'assets'
                task['tags']['fullyAnswerableWithoutStoppedService'] = i == 3
            tasks.append(task)
        (corpus / 'tasks.json').write_text(json.dumps({'tasks': tasks}), encoding='utf-8')
        (corpus / 'schemas.json').write_text(json.dumps({'schemas': {t['id']: SCHEMA for t in tasks}}), encoding='utf-8')
        (corpus / 'expected.json').write_text(json.dumps({'expected': {t['id']: {} for t in tasks}}), encoding='utf-8')
        (corpus / 'scoring.py').write_text(SCORER, encoding='utf-8')
        (corpus / 'corpus-manifest.json').write_text(json.dumps({'files': {'tasks.json': data2.sha256_file(corpus / 'tasks.json')}}),
                                                     encoding='utf-8')
        stub = 'sha256:' + 'a' * 64
        prov = {'compose_projects': ['lab'], 'backends': {'missions': {'mode': 'simulated', 'service': 'missions-stub', 'image_id': stub}}}
        arms = list(data2.SQUARE_ARMS)
        config = {'scenarios': {a: {'mcp_url': a, 'stack': {}, 'warmup_calls': [{'tool': 'lookup', 'arguments': {}}], 'provenance': prov}
                                for a in data2.ALL_ARMS},
                  'models': ['model-a', 'model-b'], 'seed': 11, 'task_set': 'scored', 'warmup_passes': 1,
                  'budgets': {'va': {'tokens': 100_000_000}, 'vb': {'tokens': 100_000_000}},
                  'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0},
                  'schedule': {'design': 'williams-4-half', 'arms': arms, 'reference': 'alpha'},
                  'dataset_fingerprint': {'argv': ['fingerprint']}, 'harness_tools': ['calculate', 'ask_requester']}
        models = {'models': {'model-a': {'vendor': 'va', 'request': {}, 'max_output_tokens': 100},
                             'model-b': {'vendor': 'vb', 'request': {}, 'max_output_tokens': 100}}}
        prices = {'dated': '2026-10-20', 'models': {m: {'input': 2.0, 'cached_read': 0.2, 'cache_write': 2.5, 'output': 10.0}
                                                    for m in ('model-a', 'model-b')}}
        rng = random.Random(5)

        def answer(system, transcript, tools):
            if len(transcript) == 1 and rng.random() < 0.2:
                return turn('', [('q', 'ask_requester', {'question': 'Which one?'})])
            return submit({'value': rng.choice(['blue'] * 6 + ['red'] * 3 + ['DECLINE'])})

        def factory(model):
            first = [VendorFatalError('bad request')] if model == 'model-a' else []
            return FakeVendorClient(first + [answer] * 5000, max_output_tokens=100, model=model)

        class Stack:
            def __init__(self, scenario):
                pass

            def start(self):
                pass

            def wait_ready(self, run_id, timeout):
                pass

            def stop_service(self, name):
                pass

            def start_service(self, name):
                pass

            def teardown(self):
                pass

        def session_factory(scenario, run_id):
            return FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}], {'lookup': lambda a: '[1]'})

        readings = iter([{'fingerprint': 'fp', 'session': 's-1'}] * 7 + [{'fingerprint': 'fp', 'session': 's-2'}] * 100)
        study = runner.Study(config, models, prices, 'fake-2', root=self.root / 'results', corpus_dir=corpus, client_factory=factory,
                             session_factory=session_factory, stack_factory=Stack, redactor=Redactor(['sk-ant-SECRETSECRETSECRET']),
                             sleep=lambda s: None, docker=FakeDocker([container('lab', 'missions-stub', 'stub:1', stub)]),
                             fingerprint_runner=lambda command: json.dumps(next(readings)))
        self.assertEqual(study.run(), 'complete')
        folder = self.root / 'results' / 'fake-2'
        sums = self.root / 'SHA256SUMS-fake-2.txt'
        simulate.write_sums(folder, 'fake-2', sums)
        checksum = json.loads((folder / 'bundle.json').read_text(encoding='utf-8'))['checksum']
        return {'bundle': folder, 'sums': sums, 'corpus': corpus, 'checksum': checksum, 'runId': 'fake-2'}

    def test_the_loader_reads_the_bundle_the_harness_writes(self):
        facts = self.harness_bundle()
        (records, blocks), manifest = load(facts)
        self.assertEqual(len(records), 18 * 2 * 4 + 18 * 2)
        self.assertEqual(len(blocks), 17)
        self.assertEqual({r['arm'] for r in records}, set(data2.ALL_ARMS))
        self.assertEqual(sum(1 for r in records if r['requeued']), 1, 'the scripted vendor error was queued again once')
        self.assertTrue(any(r['clarified'] for r in records if r['set'] == 'ambiguity'))
        self.assertTrue(all(r['clarified'] is None for r in records if r['set'] == 'core'))
        self.assertEqual({r['session'] for r in records}, {'s-1', 's-2'})
        self.assertTrue(all(r['row'] is not None for r in records if r['arm'] != 'alpha'))
        sim = self.simulated()
        with open(Path(facts['bundle']) / 'scores.csv', encoding='utf-8', newline='') as handle:
            harness_columns = next(csv.reader(handle))
        with open(Path(sim['bundle']) / 'scores.csv', encoding='utf-8', newline='') as handle:
            simulated_columns = next(csv.reader(handle))
        self.assertEqual(sorted(simulated_columns), sorted(harness_columns), 'the simulator writes the columns the harness writes')
        code, _, err = run_cli(args_for(facts, self.root / 'out-harness'))
        self.assertEqual(code, 0, err)
        res = json.loads((self.root / 'out-harness' / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual(res['counting']['runs'], len(records))


# ---------------------------------------------------------------------------------------------------------------- power
class PowerTests(unittest.TestCase):
    def test_the_profiles_come_from_the_committed_evidence(self):
        profiles = power.profiles_from_evidence()
        self.assertEqual(len(profiles['tasks']), 16)
        self.assertTrue(all(0.0 <= p <= 1.0 for t in profiles['tasks'].values() for p in t.values()))
        checks = json.loads((power.EVIDENCE / 'checksums.json').read_text(encoding='utf-8'))
        for run in ('study-1', 'gamma-prime-1'):
            self.assertEqual(profiles['sources']['%s/scores.csv' % run], checks['runs'][run]['evidenceFiles']['scores.csv'])

    def test_the_shift_sets_the_true_difference(self):
        profiles = power.profiles_from_evidence()
        for contrast in ('P1', 'P2', 'apollo-cosmo'):
            for difference in (0.0, 0.05):
                p, _, _ = power.shifted(profiles, contrast, difference)
                weights, _ = power.CONTRASTS[contrast]
                got = sum(w * p[:, power.ARMS.index(a)].mean() for a, w in weights.items())
                self.assertAlmostEqual(got, difference, places=9)

    def test_the_lines_report_the_achieved_difference_and_the_holm_rule_runs(self):
        profiles = power.profiles_from_evidence()
        line = power.simulate_line(profiles, 'P2', 5, sims=20)
        self.assertAlmostEqual(line['achievedTableDifference'], 0.05, places=9)
        self.assertTrue(math.isfinite(line['meanDrawnDifference']))
        joint = power.simulate_planned_holm(profiles, 0, sims=40)
        self.assertEqual(joint['simulations'], 40)
        for name in ('P1', 'P2'):
            self.assertLessEqual(joint[name]['established'] + joint['unusableFits'], 40)

    def test_the_design_figures_are_reproduced_within_the_simulation_error(self):
        """48 tasks, 2 runs per task and arm, 400 simulated studies per line: within three combined Monte Carlo errors of the design."""
        profiles = power.profiles_from_evidence()
        for contrast in ('P1', 'P2', 'apollo-cosmo'):
            for difference in (0, 5):
                line = power.simulate_line(profiles, contrast, difference)
                design = power.DESIGN_FIGURES[(contrast, difference)]
                tolerance = 3 * math.sqrt(design * (1 - design) / 400 + line['power'] * (1 - line['power']) / 400)
                self.assertLess(abs(line['power'] - design), tolerance, (contrast, difference, line['power'], design))
                self.assertEqual(line['designFigure'], design)


if __name__ == '__main__':
    unittest.main()
