"""Tests of the Abstraction ladder study analysis on a small synthetic fixture: no raw run data, no network, no stack.

The fixture is two run folders written into a temporary folder in the shapes the harness writes (scores.csv, runs/*/result.json, the
budget ledgers, samples.jsonl, manifest.json, bundle.json with its checksum) and their sums files. They need statsmodels and scipy, which
live in the study virtual environment; the study gate runs this file under STUDY_MCP_PYTHON.
"""
import csv
import hashlib
import io
import json
import random
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import analyze
import data
import stats
import svg
import t15

MODELS = analyze.MODELS
PRICES = {'claude-sonnet-5-5': {'vendor': 'anthropic', 'input': 2.0, 'cached_read': 0.1, 'cache_write': 2.5, 'output': 10.0},
          'gpt-6.1-sol': {'vendor': 'openai', 'input': 2.0, 'cached_read': 0.1, 'cache_write': 0.0, 'output': 10.0}}
TASKS = ['T%02d' % i for i in range(1, 17)]
# Probability of a correct answer by scenario in the fixture: chosen so that no cell is all right or all wrong.
P_CORRECT = {'alpha': 0.55, 'beta': 0.8, 'gamma': 0.45, 'delta': 0.85, 'epsilon': 0.8}
LAB_116 = {'withSeniorOfficer': 116, 'outOf': 300, 'percentage': 38.7, 'askedOrStated': 'STATED',
           'definitionUsed': {'seniorRanks': ['CAPTAIN', 'COMMANDER', 'LIEUTENANT_COMMANDER']}, 'explanation': 'crew only'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_run(root, run_id, scenarios, seed):
    """Write a synthetic run folder; returns its path."""
    rng = random.Random(seed)
    folder = Path(root) / run_id
    (folder / 'runs').mkdir(parents=True)
    rows, ledgers, seq = [], {'anthropic': [], 'openai': []}, {'anthropic': 0, 'openai': 0}
    for s in scenarios:
        for t in TASKS:
            for m in MODELS:
                for trial in (1, 2):
                    key = '%s__%s__%s__t%d' % (s, t, m, trial)
                    if t == 'T14' and m == 'gpt-6.1-sol' and trial == 1 and s == 'beta':
                        outcome = 'error'
                    elif t == 'T15':
                        outcome = 'wrong_answer'
                    else:
                        outcome = 'correct' if rng.random() < P_CORRECT[s.replace('_prime', '')] else 'wrong_answer'
                    usage = {'input': rng.randint(100, 5000), 'cached_read': rng.randint(0, 20000), 'output': rng.randint(50, 2000),
                             'cache_write': rng.randint(0, 3000) if m.startswith('claude') else 0}
                    if t == 'T15':  # a schema-valid answer: the crew-only count in Delta, a count no reading accepts elsewhere
                        submission = dict(LAB_116) if s == 'delta' else dict(LAB_116, withSeniorOfficer=115)
                    else:
                        submission = {'explanation': 'x'}
                    result = {'runKey': key, 'outcome': outcome, 'elapsedSeconds': round(rng.uniform(5, 90), 3),
                              'toolCalls': rng.randint(1, 40), 'turns': rng.randint(2, 15), 'usage': usage, 'submission': submission,
                              'score': None if outcome == 'error' else {'failedChecks': [], 'honestyFailures': [], 'tags': []}}
                    (folder / 'runs' / key).mkdir()
                    (folder / 'runs' / key / 'result.json').write_text(json.dumps(result), encoding='utf-8', newline='\n')
                    vendor = PRICES[m]['vendor']
                    for _ in range(2):
                        seq[vendor] += 1
                        ledgers[vendor].append({'event': 'reserve', 'run': key, 'seq': seq[vendor], 'label': 'request'})
                        ledgers[vendor].append({'event': 'settle', 'seq': seq[vendor], 'requestSeconds': round(rng.uniform(0.5, 6), 3),
                                                'retry': False, 'usage': {k: v // 2 for k, v in usage.items()}})
                    rows.append({'runKey': key, 'scenario': s.replace('_prime', ''), 'taskId': t, 'category': 'A', 'model': m,
                                 'trial': trial, 'outcome': outcome, 'tags': ''})
    with open(folder / 'scores.csv', 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    for vendor, events in ledgers.items():
        (folder / ('budget-%s.jsonl' % vendor)).write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8', newline='\n')
    (folder / 'samples.jsonl').write_text(''.join(json.dumps({'kind': 'cold_start', 'scenario': s.replace('_prime', ''), 'seconds': 50.0}) + '\n'
                                                  for s in scenarios), encoding='utf-8', newline='\n')
    manifest = {k: None for k in ('createdAt', 'commit', 'treeDirty', 'machine', 'stackFacts', 'limits', 'sdkVersions', 'declaredSettings',
                                  'telemetry', 'pricesTableDate', 'stackRunsPerScenario', 'planHash')}
    manifest['models'] = {m: {'priceEntry': PRICES[m], 'request': {}, 'vendor': PRICES[m]['vendor']} for m in MODELS}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    files = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    checksum = hashlib.sha256(json.dumps(files, sort_keys=True).encode('utf-8')).hexdigest()
    bundle = {'studyRunId': run_id, 'status': 'complete', 'writtenAt': '2026-10-21T00:00:00+00:00', 'files': files, 'checksum': checksum}
    (folder / 'bundle.json').write_text(json.dumps(bundle), encoding='utf-8', newline='\n')
    return folder


def write_sums(root, run_id, folder):
    path = Path(root) / ('SHA256SUMS-%s.txt' % run_id)
    lines = ['%s *%s/%s' % (sha(p), run_id, p.relative_to(folder).as_posix()) for p in sorted(folder.rglob('*')) if p.is_file()]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return path


def write_evidence(root, runs):
    """A fixture evidence folder in the shape of study/evidence for the given {run id: (folder, sums file)}."""
    evidence = Path(root) / 'evidence'
    checks = {'runs': {}}
    for run_id, (folder, sums) in runs.items():
        (evidence / run_id).mkdir(parents=True)
        for name in ('scores.csv', 'manifest.json'):
            shutil.copyfile(folder / name, evidence / run_id / name)
        bundle = json.loads((folder / 'bundle.json').read_text(encoding='utf-8'))
        checks['runs'][run_id] = {'bundleChecksum': bundle['checksum'], 'sumsFile': {'name': sums.name, 'sha256': sha(sums)},
                                  'evidenceFiles': {n: sha(folder / n) for n in ('scores.csv', 'manifest.json')}}
    (evidence / 'checksums.json').write_text(json.dumps(checks), encoding='utf-8', newline='\n')
    return evidence


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='study-analysis-'))
        cls.s1 = make_run(cls.tmp, 'study-1', ['alpha', 'beta', 'gamma', 'delta', 'epsilon'], seed=1)
        cls.gp = make_run(cls.tmp, 'gamma-prime-1', ['gamma_prime'], seed=2)
        cls.sums1 = write_sums(cls.tmp, 'study-1', cls.s1)
        cls.sums2 = write_sums(cls.tmp, 'gamma-prime-1', cls.gp)
        cls.evidence = write_evidence(cls.tmp, {'study-1': (cls.s1, cls.sums1), 'gamma-prime-1': (cls.gp, cls.sums2)})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy_of(self, folder):
        target = Path(tempfile.mkdtemp(prefix='copy-', dir=self.tmp)) / folder.name
        shutil.copytree(folder, target)
        return target

    def argv(self, out, study_1=None, replicates=200):
        return ['--study-1', str(study_1 or self.s1), '--gamma-prime-1', str(self.gp), '--sums-study-1', str(self.sums1),
                '--sums-gamma-prime-1', str(self.sums2), '--out', str(out), '--replicates', str(replicates), '--evidence', str(self.evidence)]


class VerificationTests(Fixture):
    def test_a_good_copy_verifies(self):
        facts = data.verify_copy(self.s1, self.sums1, 'study-1')
        self.assertEqual(facts['files'], sum(1 for p in self.s1.rglob('*') if p.is_file()))

    def test_a_changed_file_stops(self):
        copy = self.copy_of(self.s1)
        (copy / 'scores.csv').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(data.VerificationError, 'differ from the sums'):
            data.verify_copy(copy, self.sums1, 'study-1')

    def test_a_missing_or_extra_file_stops(self):
        copy = self.copy_of(self.s1)
        (copy / 'samples.jsonl').unlink()
        with self.assertRaisesRegex(data.VerificationError, 'missing'):
            data.verify_copy(copy, self.sums1, 'study-1')
        copy = self.copy_of(self.s1)
        (copy / 'extra.txt').write_text('x', encoding='utf-8')
        with self.assertRaisesRegex(data.VerificationError, 'extra'):
            data.verify_copy(copy, self.sums1, 'study-1')

    def test_a_different_bundle_checksum_stops(self):
        with self.assertRaisesRegex(data.VerificationError, 'expected'):
            data.verify_copy(self.s1, self.sums1, 'study-1', expected_checksum='0' * 64)


class LoadTests(Fixture):
    def test_records_follow_the_outcome_rules_and_the_cost_formula(self):
        records, _ = data.load_run(self.s1, 'study-1')
        self.assertEqual(len(records), 5 * 16 * 2 * 2)
        error = [r for r in records if r['outcome'] == 'error']
        self.assertEqual(len(error), 1)
        self.assertIsNone(error[0]['correct'])
        r = records[0]
        price = PRICES[r['model']]
        self.assertAlmostEqual(r['cost'], sum(r['usage'][k] * price[k] for k in data.USAGE_KINDS) / 1e6)
        self.assertEqual(r['tokens'], sum(r['usage'].values()))

    def test_gamma_prime_is_kept_apart_from_gamma(self):
        records, _ = data.load_run(self.gp, 'gamma-prime-1')
        self.assertEqual({r['scenario'] for r in records}, {'gamma_prime'})

    def test_the_request_log_pairs_reserve_and_settle(self):
        log = data.request_log(self.s1)
        self.assertEqual(len(log), 2 * 5 * 16 * 2 * 2)
        copy = self.copy_of(self.s1)
        path = copy / 'budget-openai.jsonl'
        lines = path.read_text(encoding='utf-8').splitlines()
        path.write_text('\n'.join(lines + [lines[1]]) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(data.VerificationError, 'settled twice'):
            data.request_log(copy)


class StatsTests(unittest.TestCase):
    def balanced(self, shares, n=8, tasks=8):
        """Rows where every (scenario, model) cell has the given share of correct runs, spread evenly over the tasks."""
        rows = []
        for s, by_model in shares.items():
            for m, share in by_model.items():
                k = round(share * n * tasks)
                for i in range(n * tasks):
                    rows.append({'scenario': s, 'model': m, 'task': 'T%02d' % (i % tasks), 'trial': i // tasks, 'correct': int(i < k)})
        return rows

    def test_the_saturated_gee_reproduces_the_cell_shares(self):
        shares = {'a': {'m1': 0.5, 'm2': 0.75}, 'b': {'m1': 0.875, 'm2': 0.625}}
        fit = stats.fit_gee(self.balanced(shares), 'correct', ['a', 'b'], ['m1', 'm2'])
        self.assertTrue(fit.converged)
        for s, by_model in shares.items():
            for m, share in by_model.items():
                self.assertAlmostEqual(fit.cell(s, m)[0], share, places=4)
        diff = fit.contrast(fit.marginal('b'), fit.marginal('a'))
        self.assertAlmostEqual(diff['estimate'], 0.125, places=4)
        self.assertLess(diff['low'], diff['estimate'])
        self.assertGreater(diff['high'], diff['estimate'])

    def test_holm(self):
        self.assertEqual([round(p, 6) for p in stats.holm([0.01, 0.04, 0.03, 0.5])], [0.04, 0.09, 0.09, 0.5])

    def test_equivalence_needs_the_whole_interval_inside_the_margin(self):
        inside = {'estimate': 0.0, 'se': 0.03, 'low': -0.0588, 'high': 0.0588}
        self.assertTrue(stats.equivalence(inside, 10)['equivalent'])
        self.assertFalse(stats.equivalence(inside, 5)['equivalent'])
        touching = {'estimate': 0.05, 'se': 0.0255, 'low': 0.0, 'high': 0.10}
        self.assertFalse(stats.equivalence(touching, 10)['equivalent'])

    def test_mcnemar_is_the_exact_binomial_on_discordant_pairs(self):
        pairs = [(1, 0)] * 17 + [(0, 1)] * 3 + [(1, 1)] * 40
        result = stats.mcnemar_exact(pairs)
        self.assertEqual((result['aOnly'], result['bOnly']), (17, 3))
        self.assertAlmostEqual(result['p'], 0.002577, places=6)
        self.assertEqual(stats.mcnemar_exact([(1, 1)])['p'], 1.0)

    def test_matched_pairs_drop_missing_runs(self):
        rows = [{'scenario': 'a', 'task': 'T1', 'correct': 1}, {'scenario': 'b', 'task': 'T1', 'correct': None},
                {'scenario': 'a', 'task': 'T2', 'correct': 0}, {'scenario': 'b', 'task': 'T2', 'correct': 1}]
        pairs = stats.matched(rows, lambda r: r['scenario'] == 'a', lambda r: r['scenario'] == 'b', ('task',))
        self.assertEqual(pairs, [(0, 1)])

    def test_cochran_uses_complete_blocks_only(self):
        rows = []
        for b in range(6):
            for i, s in enumerate(['a', 'b', 'c']):
                rows.append({'scenario': s, 'task': 'T%d' % b, 'model': 'm', 'trial': 1, 'correct': int(i <= b % 3)})
        rows.append({'scenario': 'a', 'task': 'T9', 'model': 'm', 'trial': 1, 'correct': None})
        result = stats.cochran(rows, ['a', 'b', 'c'])
        self.assertEqual((result['blocks'], result['df']), (6, 2))
        self.assertAlmostEqual(result['q'], 6.0, places=6)

    def test_the_bootstrap_is_deterministic(self):
        rows = self.balanced({'a': {'m1': 0.5, 'm2': 0.75}, 'b': {'m1': 0.875, 'm2': 0.625}})
        contrasts = {'x': ('scenario', 'b', 'a'), 'y': ('model', 'm1', 'm2')}
        first = stats.bootstrap_contrasts(rows, ['a', 'b'], ['m1', 'm2'], contrasts, replicates=300)
        self.assertEqual(first, stats.bootstrap_contrasts(rows, ['a', 'b'], ['m1', 'm2'], contrasts, replicates=300))
        self.assertLessEqual(first['x']['low'], first['x']['high'])


class T15Tests(unittest.TestCase):
    def test_the_crew_only_counts_over_all_missions(self):
        table = t15.crew_only_table()
        counts = [dfn['policies'][2]['withSeniorOfficer'] for dfn in table['definitions']]
        self.assertEqual(counts, [3, 38, 116, 207])
        self.assertTrue(all(dfn['policies'][2]['outOf'] == 300 for dfn in table['definitions']))

    def test_only_a_wrong_answer_that_matches_the_crew_only_counts_flips(self):
        table = t15.crew_only_table()
        records = [{'run': 'r', 'runKey': 'k1', 'task': 'T15', 'outcome': 'wrong_answer', 'submission': dict(LAB_116)},
                   {'run': 'r', 'runKey': 'k2', 'task': 'T15', 'outcome': 'wrong_answer', 'submission': dict(LAB_116, withSeniorOfficer=115)},
                   {'run': 'r', 'runKey': 'k3', 'task': 'T15', 'outcome': 'definition_not_accepted', 'submission': dict(LAB_116)},
                   {'run': 'r', 'runKey': 'k4', 'task': 'T14', 'outcome': 'wrong_answer', 'submission': dict(LAB_116)}]
        self.assertEqual(sorted(t15.rescore(records, table)), [('r', 'k1')])


class EndToEndTests(Fixture):
    def run_main(self, argv):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            code = analyze.main(argv)
        return code, err.getvalue()

    def test_the_outputs_are_written_and_reproducible(self):
        out_a, out_b = self.tmp / 'out-a', self.tmp / 'out-b'
        self.assertEqual(self.run_main(self.argv(out_a))[0], 0)
        self.assertEqual(self.run_main(self.argv(out_b))[0], 0)
        names = ['results.json', 'tables.md', 'figures/accuracy.svg', 'figures/comparisons.svg', 'figures/cost.svg', 'figures/seconds.svg']
        for name in names:
            self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes(), name)
        res = json.loads((out_a / 'results.json').read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in res['primary']['comparisons']], ['i', 'ii', 'iii', 'iv', 'v', 'vi'])
        self.assertEqual([e['id'] for e in res['primary']['equivalence']], ['iii', 'vi', 'iv'])
        self.assertEqual(res['descriptive']['cells']['beta']['gpt-6.1-sol']['missing'], 1)
        self.assertEqual(res['exploratory']['t15CrewOnly']['flips']['delta'], 4)
        self.assertEqual(res['sensitivity']['errorsAsWrong']['observations'], res['primary']['fit']['observations'] + 1)
        for name in names[2:]:
            ET.fromstring((out_a / name).read_text(encoding='utf-8'))

    def test_a_tampered_copy_stops_before_any_output(self):
        copy = self.copy_of(self.s1)
        (copy / 'runs' / 'alpha__T01__claude-sonnet-5-5__t1' / 'result.json').write_text('{}', encoding='utf-8')
        out = self.tmp / 'out-tampered'
        code, err = self.run_main(self.argv(out, study_1=copy))
        self.assertEqual(code, 2)
        self.assertIn('STOP', err)
        self.assertFalse(out.exists())

    def test_the_output_folder_must_be_outside_the_repository(self):
        with self.assertRaises(SystemExit):
            self.run_main(self.argv(analyze.STUDY / 'analysis' / 'out'))


class EvidenceTests(unittest.TestCase):
    def test_the_committed_evidence_matches_its_checksums(self):
        checks = json.loads((analyze.EVIDENCE / 'checksums.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(checks['runs']), ['gamma-prime-1', 'study-1'])
        for run_id, facts in checks['runs'].items():
            for name, digest in facts['evidenceFiles'].items():
                self.assertEqual(analyze.lf_sha256(analyze.EVIDENCE / run_id / name), digest, '%s/%s' % (run_id, name))
            manifest = json.loads((analyze.EVIDENCE / run_id / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['studyRunId'], run_id)

    def test_the_committed_scores_tables_have_every_run(self):
        for run_id, runs in (('study-1', 320), ('gamma-prime-1', 64)):
            with open(analyze.EVIDENCE / run_id / 'scores.csv', encoding='utf-8', newline='') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), runs)


class SvgTests(unittest.TestCase):
    def test_a_figure_is_valid_and_deterministic(self):
        items = [('A', 50, 40, 60, 'confirmatory'), ('B', 70, None, None, 'descriptive')]
        first = svg.interval_plot('T', 'x', items, 0, 100, range(0, 101, 50), margins=((10, '0.1'),), note='n')
        self.assertEqual(first, svg.interval_plot('T', 'x', items, 0, 100, range(0, 101, 50), margins=((10, '0.1'),), note='n'))
        root = ET.fromstring(first)
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')

    def test_tick_labels_keep_the_decimals_they_need(self):
        text = svg.interval_plot('T', 'x', [('A', 0.05, 0.02, 0.08, 'confirmatory')], 0, 0.1, [0, 0.02, 0.04, 0.1])
        labels = [t.text for t in ET.fromstring(text).iter('{http://www.w3.org/2000/svg}text')]
        for label in ('0', '0.02', '0.04', '0.1'):
            self.assertIn(label, labels)


if __name__ == '__main__':
    unittest.main()
