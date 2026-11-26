"""Tests of the legacy-load reader (legacy3.py), offline, on simulated transcripts and session folders: what counts, the run windows, the
block initialization load and the check before scoring, the clock limit, a missing or partial log, the figures and their intervals, the
reader's blindness and a session folder written by study/launch/launch.py itself. No stack, no vendor, no corpus."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import legacy3  # noqa: E402

sys.path.insert(0, str(HERE.parent / 'launch'))
import launch  # noqa: E402  (the writer of the session folders)

MODELS = ('model-a', 'model-b')
TASKS = {'T1': 'forward', 'T2': 'forward', 'T3': 'reverse', 'T4': 'reverse', 'T5': 'none', 'T6': 'none'}
ROWS = {'alpha': (None,), 'beta': (1, 2), 'gamma': (1, 2), 'delta': (1, 2), 'epsilon': (1, 2)}
# Requests per GraphQL run, per system, inside its window.
PER_RUN = {'gamma': {'missions': 1, 'personnel': 1, 'assets': 1}, 'delta': {'missions': 0, 'personnel': 2, 'assets': 0},
           'epsilon': {'missions': 2, 'personnel': 2, 'assets': 0}}
SECRET = 'QUESTION-TEXT-THAT-MUST-NEVER-LEAVE'
BASE = 1795000000.0


def iso(t):
    return launch.utc_iso(t)


def harness_iso(t):
    """The harness's own form (study_common.utc_now): milliseconds and +00:00."""
    return iso(t)[:23] + '+00:00'


def tool(name, url, is_error, text):
    return {'ts': 'x', 'kind': 'tool', 'id': 'c', 'name': name, 'arguments': {'url': url, 'envelope': SECRET}, 'isError': is_error,
            'resultChars': len(text), 'seconds': 0.1, 'text': text}


OK = '{"status": 200, "contentType": "text/xml", "truncated": false, "body": "%s"}' % SECRET
RAW_EVENTS = [
    tool('soap_request', 'http://127.0.0.1:8082/soap/personnel-v2', False, OK),                            # personnel, counted
    tool('http_request', 'http://127.0.0.1:8083/missions?x=1', False, OK.replace('200', '404')),             # missions, counted (a status)
    tool('http_request', 'http://127.0.0.1:8084/assets', True, 'The service did not answer: TimeoutError: timed out'),  # assets, counted
    tool('http_request', 'http://127.0.0.1:8084/assets', True, 'The service did not answer: ConnectionRefusedError: [Errno 111]'),
    tool('http_request', 'http://10.0.0.1:9999/x', True, 'Address refused: only these base addresses are reachable: ...'),
    tool('http_request', 'http://127.0.0.1:8083/missions', True, 'Error executing tool: The service did not answer: RemoteDisconnected: '
                                                                  'Remote end closed connection without response'),  # counted apart
    tool('http_request', 'http://127.0.0.1:8083/missions', True, 'something nobody expected'),             # unclassified
    tool('read_mapping_release', None, False, '{"truncated": false}'),
]
RAW_COUNTED = {'missions': 2, 'personnel': 1, 'assets': 1}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


def write_session(folder, scenario, start, end, rows, offsets=(0.2, 0.3), saved=('missions', 'personnel', 'assets'), with_end=True):
    """A session folder in launch.py's format: start.json, requests.jsonl, end.json and sha256.json."""
    folder = Path(folder)
    folder.mkdir(parents=True)
    write_json(folder / 'start.json', {'schema': 1, 'scenario': scenario, 'missions': 'real', 'at': iso(start),
                                       'clock': {'samples': [], 'offsetBound': offsets[0], 'error': None}})
    (folder / 'requests.jsonl').write_text(''.join(json.dumps({'t': iso(t), 'system': s, 'kind': k, 'status': st}) + '\n'
                                                   for t, s, k, st in sorted(rows, key=lambda r: r[0])), encoding='utf-8', newline='\n')
    names = ['start.json', 'requests.jsonl']
    if with_end:
        write_json(folder / 'end.json', {'schema': 1, 'scenario': scenario, 'missions': 'real', 'at': iso(end), 'opened': True,
                                         'clock': {'samples': [], 'offsetBound': offsets[1], 'error': None},
                                         'adapters': {s: ({'saved': True, 'error': None} if s in saved else {'saved': False, 'error': 'x'})
                                                      for s in ('missions', 'personnel', 'assets')}})
        names.append('end.json')
    write_json(folder / 'sha256.json', {n: hashlib.sha256((folder / n).read_bytes()).hexdigest() for n in names})


def snapshot_rows(t0, answers=(200,) * 11):
    """The Personnel exchanges of a snapshot read from t0, each a request and, unless None, its answer."""
    rows = []
    for i, status in enumerate(answers):
        rows.append((t0 + i * 0.05, 'personnel', 'request', None))
        if status is not None:
            rows.append((t0 + i * 0.05 + 0.01, 'personnel', 'response', status))
    return rows


class Study:
    """A simulated study: records, a bundle folder with each run's transcript and result, and the legacy-load sessions."""

    def __init__(self, root, snapshot=None, offsets=None, missing=(), partial=(), tamper=(), no_end=()):
        self.root = Path(root)
        self.bundle, self.legacy = self.root / 'bundle', self.root / 'legacy-load'
        self.legacy.mkdir(parents=True)
        self.records, clock = [], BASE
        for arm, rows in ROWS.items():
            for row in rows:
                block = '%s-r%s' % (arm, row)
                session_start, windows = clock, []
                clock += 30.0  # the stack start and the warm-up
                for task in TASKS:
                    for model in MODELS:
                        key = '%s__%s__%s__%s' % (arm, task, model, block)
                        start, end = clock, clock + 10.0
                        windows.append((start, end))
                        clock += 12.0
                        run = self.bundle / 'runs' / key
                        run.mkdir(parents=True)
                        events = [{'ts': harness_iso(start), 'kind': 'start', 'task': task},
                                  {'ts': harness_iso(start), 'kind': 'message', 'role': 'user', 'text': SECRET}]
                        if arm in legacy3.RAW_ARMS:
                            events += RAW_EVENTS
                        (run / 'transcript.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
                        write_json(run / 'result.json', {'runKey': key, 'finishedAt': harness_iso(end), 'question': SECRET})
                        self.records.append({'runKey': key, 'arm': arm, 'task': task, 'model': model, 'row': row, 'block': block,
                                             'set': 'core', 'outcome': 'correct'})
                clock += 30.0
                if arm in legacy3.GRAPHQL_ARMS and block not in missing:
                    rows_ = [(session_start + 5.0, 'missions', 'request', None), (session_start + 5.01, 'missions', 'response', 200)]
                    if arm in legacy3.ROUTER_ARMS:
                        rows_ += snapshot_rows(session_start + 6.0, (snapshot or {}).get(block, (200,) * 11))
                    for start, end in windows:
                        for system, n in PER_RUN[arm].items():
                            rows_ += [(start + 1.0 + i, system, 'request', None) for i in range(n)]
                    rows_.append((windows[0][1] + 1.0, 'assets', 'request', None))  # between two runs: unattributed
                    rows_.append((windows[-1][1] + 0.1, 'personnel', 'request', None))  # just after the last run, within the bound
                    write_session(self.legacy / ('%s-%s' % (block, arm)), arm, session_start, clock, rows_,
                                  offsets=(offsets or {}).get(block, (0.2, 0.3)),
                                  saved=('missions', 'personnel') if block in partial else ('missions', 'personnel', 'assets'),
                                  with_end=block not in no_end)
                    if block in tamper:
                        with open(self.legacy / ('%s-%s' % (block, arm)) / 'requests.jsonl', 'a', encoding='utf-8') as handle:
                            handle.write('{"t": "%s", "system": "assets", "kind": "request", "status": null}\n' % iso(windows[0][0] + 2))
        self.strata = {task: {'direction': direction} for task, direction in TASKS.items()}

    def compute(self, replicates=400):
        return legacy3.compute(self.records, self.strata, self.bundle, self.legacy, replicates)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class WhatCountsTests(unittest.TestCase):
    def test_raw_requests_count_when_they_reached_the_service(self):
        kinds = [legacy3.raw_request(e) for e in RAW_EVENTS]
        self.assertEqual(kinds, [('personnel', 'status'), ('missions', 'status'), ('assets', 'timeout'), ('assets', 'noConnection'),
                                 (None, 'refused'), ('missions', 'connected'), ('missions', 'unclassified'), None])
        self.assertEqual(legacy3.raw_request({'kind': 'message', 'text': 'x'}), None)
        refused = tool('http_request', 'http://127.0.0.1:8083/m', True, 'The header \'Cookie\' is not allowed.')
        self.assertEqual(legacy3.raw_request(refused), ('missions', 'refused'))
        elsewhere = tool('http_request', 'http://127.0.0.1:9000/m', False, OK)
        self.assertEqual(legacy3.raw_request(elsewhere), (None, 'unclassified'))

    def test_a_result_the_harness_tools_wrapped_is_read_from_results_jsonl(self):
        """With calculate on, the agent reads `result_id: <id>` and, for a long result, only its shape; results.jsonl holds the full text."""
        shape = 'result_id: ab12-3\\nstored: 9000 characters, shape: {"status": ...}'.replace('\\n', '\n')
        stored_event = dict(tool('http_request', 'http://127.0.0.1:8084/assets', False, shape), harness={'tool': 'http_request', 'resultId': 'ab12-3'})
        self.assertEqual(legacy3.raw_request(stored_event), ('assets', 'unclassified'), 'the shape alone holds no status')
        self.assertEqual(legacy3.raw_request(stored_event, {'ab12-3': (False, OK)}), ('assets', 'status'))
        shown = dict(tool('soap_request', 'http://127.0.0.1:8082/soap', False, 'result_id: ab12-4\nwarning: repeats ab12-1\n' + OK),
                     harness={'tool': 'soap_request', 'resultId': 'ab12-4'})
        self.assertEqual(legacy3.raw_request(shown), ('personnel', 'status'), 'a result shown in full, its id and warning lines removed')
        error = dict(tool('http_request', 'http://127.0.0.1:8083/m', True, 'result_id: ab12-5\nThe service did not answer: TimeoutError: x'),
                     harness={'tool': 'http_request', 'resultId': 'ab12-5'})
        self.assertEqual(legacy3.raw_request(error, {}), ('missions', 'timeout'))
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / 'transcript.jsonl').write_text(json.dumps(dict(stored_event, ts=harness_iso(BASE))) + '\n', encoding='utf-8')
            (run / 'results.jsonl').write_text(json.dumps({'resultId': 'ab12-3', 'tool': 'http_request', 'isError': False,
                                                           'arguments': {'url': SECRET}, 'text': OK}) + '\n', encoding='utf-8')
            self.assertEqual(legacy3.read_transcript(run / 'transcript.jsonl'), (BASE, [('assets', 'status')]))
            self.assertLessEqual(max(len(text) for _, text in legacy3.read_stored(run / 'results.jsonl').values()), legacy3.STORED_CHARS)

    def test_exactly_one_percent_of_unusable_replicates_still_gives_an_interval(self):
        import numpy as np
        draws = np.concatenate([np.ones(9900), np.full(100, np.nan)])
        self.assertTrue(legacy3.interval(1.0, draws, 10000)['estimable'])
        self.assertFalse(legacy3.interval(1.0, np.concatenate([np.ones(9899), np.full(101, np.nan)]), 10000)['estimable'])
        self.assertFalse(legacy3.interval(float('nan'), np.ones(10), 10)['estimable'])

    def test_the_snapshot_read_needs_eleven_answered_exchanges_in_a_row(self):
        self.assertTrue(legacy3.snapshot_read_completed(snapshot_rows(0.0), 10.0))
        self.assertFalse(legacy3.snapshot_read_completed(snapshot_rows(0.0), 0.3), 'not before the first scored run')
        failed = snapshot_rows(0.0, (200, 200, 200, 503))
        self.assertFalse(legacy3.snapshot_read_completed(failed, 10.0))
        self.assertTrue(legacy3.snapshot_read_completed(failed + snapshot_rows(1.0), 10.0), 'a read that failed and then completed')
        self.assertFalse(legacy3.snapshot_read_completed(snapshot_rows(0.0, (200,) * 9 + (None, 200)), 10.0), 'a timed-out page')
        probes = [r for i in range(12) for r in snapshot_rows(i * 1.0, (200,))]
        self.assertTrue(legacy3.snapshot_read_completed(probes, 20.0))
        self.assertFalse(legacy3.snapshot_read_completed([(0.0, 'missions', 'request', None), (0.1, 'missions', 'response', 200)] * 11, 20.0))


class ReaderTests(Workspace):
    def test_counts_windows_initialization_and_the_figures(self):
        result = Study(self.root).compute()
        self.assertEqual(result['notCountable'], {})
        per = result['perQuestion']
        for arm, systems in PER_RUN.items():
            for system, n in systems.items():
                entry = per[system]['arms'][arm]
                self.assertEqual((entry['estimate'], entry['low'], entry['high']), (float(n), float(n), float(n)), (arm, system))
        for system, n in RAW_COUNTED.items():
            for arm in legacy3.RAW_ARMS:
                self.assertEqual(per[system]['arms'][arm]['estimate'], float(n))
        self.assertEqual(per['all']['arms']['gamma']['estimate'], 3.0)
        self.assertEqual(per['all']['ratios']['federation/gamma']['estimate'], round((2 + 4) / 2 / 3, 6))
        self.assertEqual(per['all']['ratios']['federation/beta']['estimate'], 0.75)
        self.assertEqual(per['all']['ratios']['gamma/alpha']['estimate'], 0.75)
        self.assertEqual(per['missions']['ratios']['delta/alpha']['estimate'], 0.0, 'a zero numerator is a ratio of zero')
        self.assertEqual(per['assets']['ratios']['federation/gamma']['estimate'], 0.0)
        self.assertEqual(per['assets']['ratios']['delta/alpha']['estimate'], 0.0)
        # Initialization: delta and epsilon read the snapshot (11 Personnel requests) and ask Missions once; gamma asks Missions once.
        init = result['blockInitialization']
        self.assertEqual(init['delta']['requests'], {'missions': 2, 'personnel': 22, 'assets': 0})
        self.assertEqual(init['delta']['perSession'], {'missions': 1.0, 'personnel': 11.0, 'assets': 0.0})
        self.assertEqual(init['gamma']['requests'], {'missions': 2, 'personnel': 0, 'assets': 0})
        self.assertEqual(result['unattributed']['epsilon'], {'missions': 0, 'personnel': 2, 'assets': 2})
        total = result['totalWithInitialization']['delta']
        self.assertEqual(total['coreRuns'], 24)
        self.assertEqual(total['requests'], {'missions': 2, 'personnel': 24 * 2 + 22 + 2, 'assets': 2})
        self.assertEqual(result['blockInitialization']['alpha']['requests'], {'missions': 0, 'personnel': 0, 'assets': 0})
        self.assertEqual(result['nearBoundary']['delta-r1'], 1, 'the request 0.1 s after the last run, within the 0.3 s bound')
        raw = result['rawArms']['alpha']
        self.assertEqual(raw['connected'], {'missions': 12, 'personnel': 0, 'assets': 0}, 'reported apart, and counted')
        self.assertEqual(raw['noConnection']['assets'], 12)
        self.assertEqual(raw['unclassified']['missions'], 12)
        self.assertEqual(raw['unplaced'], 12, 'the allow-list refusal has no system')

    def test_the_total_and_the_raw_kinds_count_the_core_set_and_the_rest_is_reported_apart(self):
        """F1 (D1 (a)): the total with initialization and the raw arms' kinds count the scored runs of the core set, vendor errors missing
        (PLAN 10.3); the ambiguity set and the vendor errors are their own counts, and the three together are every request."""
        whole = Study(self.root / 'whole').compute()
        study = Study(self.root / 'split')
        for record in study.records:
            if record['task'] == 'T6':
                record['set'] = 'ambiguity'
        vendor = next(r for r in study.records if r['arm'] == 'delta' and r['task'] == 'T1' and r['model'] == 'model-a' and r['row'] == 1)
        vendor['outcome'] = 'vendor_error'
        result = study.compute()
        total = result['totalWithInitialization']['delta']
        self.assertEqual(total['coreRuns'], 24 - 4 - 1, 'T6 (2 models, 2 rows) is the ambiguity set; one core run failed at the vendor')
        self.assertEqual(total['requests'], {'missions': 2, 'personnel': 19 * 2 + 22 + 2, 'assets': 2})
        self.assertEqual(total['perCoreRun'], {s: round(v / 19, 6) for s, v in total['requests'].items()})
        self.assertNotIn('runs', total)
        self.assertIn('core set', total['note'])
        amb, err = result['ambiguitySet']['arms'], result['vendorErrors']['arms']
        self.assertEqual((amb['delta']['runs'], amb['delta']['requests']), (4, {'missions': 0, 'personnel': 8, 'assets': 0}))
        self.assertEqual((err['delta']['runs'], err['delta']['requests']), (1, {'missions': 0, 'personnel': 2, 'assets': 0}))
        self.assertIn('ambiguity set', result['ambiguitySet']['note'])
        for arm in legacy3.ARMS:
            for s in legacy3.SYSTEMS:
                parts = (result['totalWithInitialization'][arm]['requests'][s] + amb[arm]['requests'][s] + err[arm]['requests'][s])
                self.assertEqual(parts, whole['totalWithInitialization'][arm]['requests'][s], (arm, s))
        raw = result['rawArms']['alpha']
        self.assertEqual(raw['connected'], {'missions': 10, 'personnel': 0, 'assets': 0}, 'the 10 core runs of alpha')
        self.assertEqual(raw['unplaced'], 10)
        self.assertEqual(amb['alpha']['raw']['connected'], {'missions': 2, 'personnel': 0, 'assets': 0}, 'the ambiguity set, apart')
        self.assertEqual(amb['alpha']['runs'], 2)
        self.assertIn('core set', result['rawArmsNote'])
        self.assertEqual(result['blockInitialization'], whole['blockInitialization'], 'the block initialization does not change')
        self.assertEqual(result['unattributed'], whole['unattributed'])
        self.assertEqual(result['nearBoundary'], whole['nearBoundary'])

    def test_the_markdown_prints_every_figure_of_plan_10_6(self):
        study = Study(self.root)
        for record in study.records:
            if record['task'] == 'T6':
                record['set'] = 'ambiguity'
        result = study.compute()
        text = legacy3.tables(result)
        self.assertEqual(text, legacy3.tables(study.compute()), 'the same bytes twice')
        headings = [line for line in text.splitlines() if line.startswith('## ')]
        self.assertEqual(headings, ['## Mean requests per scored run of the core set (95 percent interval)',
                                    '## Ratios of the means (95 percent interval)',
                                    '## Block initialization load (requests before the first scored run of each stack start, countable blocks)',
                                    '## Total with initialization, core set (per scored run of the core set in a countable block)',
                                    '## Unattributed requests (outside every run window, after the first)',
                                    '## Apart: the ambiguity set (runs in countable blocks and their requests, not in the figures or the total)',
                                    '## Apart: the core runs that failed at the vendor twice (runs in countable blocks and their requests, not in '
                                    'the figures or the total)',
                                    "## The raw arms' requests by kind, core set (vendor errors missing)",
                                    '## Requests near a boundary, per block',
                                    '## Blocks that are not countable'])
        total = result['totalWithInitialization']
        self.assertIn('| core runs in countable blocks | %s |' % ' | '.join(str(total[a]['coreRuns']) for a in legacy3.ARMS), text)
        self.assertIn('| personnel | %s |' % ' | '.join('%.2f (%d requests)' % (total[a]['perCoreRun']['personnel'], total[a]['requests']['personnel'])
                                                        for a in legacy3.ARMS), text)
        self.assertIn('| runs in countable blocks | %s |' % ' | '.join(str(result['ambiguitySet']['arms'][a]['runs']) for a in legacy3.ARMS), text)
        # The raw arms' requests by kind of each group apart, as legacy-load.json holds them (scope item 1, the F1 sub-rule).
        ambiguity = text.split('## Apart: the ambiguity set')[1].split('\n## ')[0]
        self.assertIn("Their raw arms' requests by kind:", ambiguity)
        self.assertIn('| connected | missions 2, personnel 0, assets 0 | missions 4, personnel 0, assets 0 |', ambiguity)
        self.assertIn('| unplaced | 2 | 4 |', ambiguity)
        vendor = text.split('## Apart: the core runs that failed at the vendor twice')[1].split('\n## ')[0]
        self.assertIn('| connected | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |', vendor)
        self.assertIn('| stack starts | 0 | 0 | 2 | 2 | 2 |', text)
        self.assertIn('| personnel | 0 | 0 | 0 (0.00 per stack start) | 22 (11.00 per stack start) | 22 (11.00 per stack start) |', text)
        self.assertIn('| connected | missions 10, personnel 0, assets 0 | missions 20, personnel 0, assets 0 |', text)
        self.assertIn('- delta-r1: %d' % result['nearBoundary']['delta-r1'], text)

    def test_an_arm_with_no_core_run_still_shows_its_requests_in_the_markdown(self):
        """The total keeps the start-up load visible (PLAN 10.6) even when no core run of an arm counts and the rate per run is undefined."""
        study = Study(self.root)
        for record in study.records:
            if record['arm'] == 'delta':
                record['outcome'] = 'vendor_error'
        result = study.compute()
        total = result['totalWithInitialization']['delta']
        self.assertEqual((total['coreRuns'], total['perCoreRun']), (0, None))
        self.assertEqual(total['requests'], {'missions': 2, 'personnel': 24, 'assets': 2})
        rows = {line.split(' | ')[0][2:]: line.strip('|').split(' | ')[4].strip() for line in
                legacy3.tables(result).split('## Total with initialization')[1].split('\n## ')[0].splitlines() if line.startswith('| ')}
        self.assertEqual((rows['missions'], rows['personnel'], rows['assets'], rows['core runs in countable blocks']),
                         ('no core run in a countable block (2 requests)', 'no core run in a countable block (24 requests)',
                          'no core run in a countable block (2 requests)', '0'))

    def test_the_markdown_says_the_core_runs_it_counts_are_those_of_the_countable_blocks(self):
        """An arm whose blocks are all not countable had core runs: the markdown names the countable blocks, never "no core run" alone."""
        result = Study(self.root, missing=('gamma-r1', 'gamma-r2')).compute()
        self.assertEqual(result['totalWithInitialization']['gamma']['coreRuns'], 0)
        text = legacy3.tables(result)
        total = text.split('## Total with initialization')[1].split('\n## ')[0]
        self.assertIn('A run of a block that is not countable is not in it', total)
        self.assertIn('| missions | 2.00 (24 requests) | 2.00 (48 requests) | no core run in a countable block (0 requests) |', total)
        self.assertIn('| core runs in countable blocks | 12 | 24 | 0 | 24 | 24 |', total)
        self.assertNotRegex(text, r'\| (core runs|runs) \|')

    def test_an_arm_is_the_equal_weight_mean_of_its_cells(self):
        study = Study(self.root)
        counts = {r['runKey']: {'requests': {'missions': 2 if r['model'] == 'model-a' else 4, 'personnel': 0, 'assets': 0}}
                  for r in study.records}
        rows = [r for r in study.records if not (r['arm'] == 'gamma' and r['model'] == 'model-a' and r['task'] != 'T1')]
        out = legacy3.estimates(rows, counts, sorted(TASKS), {t: d for t, d in TASKS.items()}, 'missions', 200)
        self.assertEqual(out['arms']['gamma']['estimate'], 3.0, 'one model-a run per round weighs as much as six model-b runs')

    def test_the_check_before_scoring_and_the_clock_limit_make_a_block_not_countable(self):
        study = Study(self.root, snapshot={'delta-r1': (200, 200, 503)}, offsets={'epsilon-r2': (0.2, 1.4), 'gamma-r1': (1.1, 0.1)})
        result = study.compute()
        self.assertEqual(sorted(result['notCountable']), ['delta-r1', 'epsilon-r2', 'gamma-r1'])
        self.assertIn('no completed Personnel snapshot read', result['notCountable']['delta-r1'][0])
        self.assertIn('clock offset bound 1.400 s at the end, above 1.0 s', result['notCountable']['epsilon-r2'][0])
        self.assertIn('at the start', result['notCountable']['gamma-r1'][0])
        delta = result['perQuestion']['personnel']['arms']['delta']
        self.assertEqual((delta['runs'], delta['runsLeftOut']), (12, 12))
        self.assertEqual(result['totalWithInitialization']['delta']['coreRuns'], 12)
        self.assertEqual(result['blockInitialization']['delta']['blocks'], 1)

    def test_a_missing_partial_unsaved_or_altered_log_makes_a_block_not_countable(self):
        study = Study(self.root, missing=('gamma-r2',), partial=('delta-r2',), tamper=('epsilon-r1',), no_end=('epsilon-r2',))
        problems = study.compute()['notCountable']
        self.assertEqual(sorted(problems), ['delta-r2', 'epsilon-r1', 'epsilon-r2', 'gamma-r2'])
        self.assertIn('no saved session covers run', problems['gamma-r2'][0])
        self.assertIn('the assets adapter log was not saved', ' '.join(problems['delta-r2']))
        self.assertIn('requests.jsonl does not match its SHA-256', ' '.join(problems['epsilon-r1']))
        self.assertIn('no end.json', ' '.join(problems['epsilon-r2']))

    def test_a_planned_cell_whose_every_run_is_a_vendor_error_empties_the_figure(self):
        study = Study(self.root)
        for record in study.records:
            if record['arm'] == 'gamma' and record['model'] == 'model-a' and record['row'] == 1:
                record['outcome'] = 'vendor_error'
        per = study.compute()['perQuestion']['all']
        self.assertFalse(per['arms']['gamma']['estimable'])
        self.assertFalse(per['ratios']['federation/gamma']['estimable'])
        self.assertTrue(per['arms']['delta']['estimable'])

    def test_a_row_that_cannot_be_read_is_a_problem_of_its_block_and_never_stops_the_reader(self):
        study = Study(self.root)
        folder = study.legacy / 'delta-r1-delta'
        rows = (folder / 'requests.jsonl').read_text(encoding='utf-8')
        (folder / 'requests.jsonl').write_text(rows + '{"t": "2026-11-19T15:0', encoding='utf-8', newline='\n')
        sums = json.loads((folder / 'sha256.json').read_text(encoding='utf-8'))
        sums['requests.jsonl'] = hashlib.sha256((folder / 'requests.jsonl').read_bytes()).hexdigest()
        write_json(folder / 'sha256.json', sums)
        (study.legacy / 'gamma-r1-gamma' / 'end.json').write_text('{"schema": 1, "at": ', encoding='utf-8')
        result = study.compute()
        self.assertEqual(sorted(result['notCountable']), ['delta-r1', 'gamma-r1'])
        self.assertIn('requests.jsonl line', ' '.join(result['notCountable']['delta-r1']))
        self.assertIn('end.json cannot be read', ' '.join(result['notCountable']['gamma-r1']))
        self.assertFalse(result['perQuestion']['all']['arms']['delta']['estimable'], "delta's round-1 cells are empty")
        self.assertTrue(result['perQuestion']['all']['arms']['epsilon']['estimable'], 'every other figure is still written')
        self.assertEqual(result['blockInitialization']['delta']['blocks'], 1, 'the other block of the arm still counts')

    def test_malformed_session_metadata_is_a_problem_of_its_block_and_never_stops_the_reader(self):
        """Values of the wrong type inside start.json or end.json, with sums that agree, and an end.json that fails its sum."""
        study = Study(self.root)

        def rewrite(folder, name, change, resum=True):
            document = json.loads((folder / name).read_text(encoding='utf-8'))
            change(document)
            write_json(folder / name, document)
            if resum:
                sums = json.loads((folder / 'sha256.json').read_text(encoding='utf-8'))
                sums[name] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
                write_json(folder / 'sha256.json', sums)
        rewrite(study.legacy / 'delta-r1-delta', 'start.json', lambda d: d.update(clock='not a clock'))
        rewrite(study.legacy / 'delta-r2-delta', 'end.json', lambda d: d['clock'].update(offsetBound='0.2'))
        rewrite(study.legacy / 'epsilon-r1-epsilon', 'end.json', lambda d: d.update(adapters=['missions'], at=12))
        rewrite(study.legacy / 'gamma-r1-gamma', 'end.json', lambda d: d['clock'].update(offsetBound='x'), resum=False)
        result = study.compute()
        problems = result['notCountable']
        self.assertEqual(sorted(problems), ['delta-r1', 'delta-r2', 'epsilon-r1', 'gamma-r1'])
        self.assertIn('no clock reading at the start', ' '.join(problems['delta-r1']))
        self.assertIn("the clock reading at the end is not a number of seconds ('0.2')", ' '.join(problems['delta-r2']))
        self.assertIn('the missions adapter log was not saved', ' '.join(problems['epsilon-r1']))
        self.assertIn('end.json does not match its SHA-256', ' '.join(problems['gamma-r1']))
        self.assertTrue(result['perQuestion']['all']['arms']['epsilon']['estimable'] is False)
        self.assertTrue(result['perQuestion']['all']['arms']['beta']['estimable'], 'every other figure is still written')

    def test_an_arm_with_no_countable_block_is_not_estimable_and_the_rest_is_still_reported(self):
        study = Study(self.root, missing=('gamma-r1', 'gamma-r2'))
        result = study.compute()
        self.assertFalse(result['perQuestion']['all']['arms']['gamma']['estimable'])
        self.assertFalse(result['perQuestion']['all']['ratios']['federation/gamma']['estimable'])
        self.assertTrue(result['perQuestion']['all']['ratios']['federation/beta']['estimable'])
        self.assertEqual(result['blockInitialization']['gamma']['perSession'], None)

    def test_the_reader_keeps_no_question_argument_or_answer_text_and_gives_the_same_bytes_twice(self):
        study = Study(self.root)
        first = json.dumps(study.compute(), sort_keys=True)
        self.assertNotIn(SECRET, first)
        self.assertNotIn('127.0.0.1', first)
        self.assertEqual(first, json.dumps(study.compute(), sort_keys=True))
        self.assertNotIn(SECRET, legacy3.tables(study.compute()))

    def test_a_session_written_by_launch_py_reads_back_whole(self):
        class Machine:
            def __init__(self):
                self.clock = BASE

            def now(self):
                self.clock += 0.1
                return self.clock

            def read(self, argv):
                if argv[:3] == ['docker', 'ps', '--all']:
                    return 0, 'id-' + argv[-1].rsplit('=', 1)[1]
                return 0, '%.6f' % (self.clock + 0.02)

            def logs(self, argv):
                if argv[3] != 'id-personnel-adapter':
                    return 0, ''
                return 0, ''.join('%s x : jdk.httpclient.HttpClient : %s\n' % (stamp, line) for stamp, line in (
                    ('2026-11-19T15:00:00.100000000Z', 'REQUEST: http://personnel-service:8082/soap/personnel-v2 POST'),
                    ('2026-11-19T15:00:00.110000000Z', 'RESPONSE: (POST http://personnel-service:8082/soap/personnel-v2) 200 HTTP_1_1')))
        machine, lines = Machine(), []
        launch.legacy_start(self.root / 'legacy-load', 'delta', 'real', machine, lines.append)
        launch.legacy_save(self.root / 'legacy-load', 'delta', 'real', machine, lines.append)
        sessions = legacy3.read_sessions(self.root / 'legacy-load')
        self.assertEqual(len(sessions), 1, lines)
        session = sessions[0]
        self.assertEqual(session['problems'], [])
        self.assertEqual(session['scenario'], 'delta')
        self.assertEqual([(s, k, st) for _, s, k, st in session['rows']], [('personnel', 'request', None), ('personnel', 'response', 200)])
        self.assertLess(session['offset'], 0.2)
        self.assertLess(session['start'], session['end'])
        self.assertEqual(legacy3.SCHEMA, launch.LEGACY_SCHEMA)
        self.assertEqual(legacy3.SNAPSHOT_EXCHANGES, 11)

    def test_the_command_line_refuses_an_output_folder_in_the_repository(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = legacy3.main(['--bundle', 'b', '--sums', 's', '--bundle-checksum', 'c', '--corpus-dir', 'd', '--legacy-dir', 'l',
                                 '--out', str(HERE / 'out')])
        self.assertEqual(code, 2)
        self.assertIn('outside the repository', err.getvalue())
        self.assertFalse((HERE / 'out').exists())


if __name__ == '__main__':
    unittest.main()
