"""Offline tests of the run watcher on synthetic run folders written in the harness's shapes: no run yet, partway, a void, a retry and a
vendor error, a resume, ended. They check what a report says, that it never says an outcome or a score even when the folder holds them,
and that the watcher changes nothing in the folder it follows."""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import watch_run  # noqa: E402
from agent import TERMINAL  # noqa: E402  (study/harness, put on the path by watch_run)
from budget import ledger_dollars  # noqa: E402

CLAUDE, GPT = 'claude-fixture', 'gpt-fixture'
PRICES = {CLAUDE: {'vendor': 'anthropic', 'input': 2.0, 'cached_read': 0.1, 'cache_write': 2.5, 'output': 10.0},
          GPT: {'vendor': 'openai', 'input': 2.0, 'cached_read': 0.1, 'cache_write': 0.0, 'output': 10.0}}
TASKS = (('T1', GPT), ('T2', CLAUDE), ('T3', GPT), ('T4', CLAUDE))
BLOCKS = (('r1-beta', 'beta', 'H1', 'r1'), ('r1-gamma', 'gamma', 'H2', 'r1'), ('r2-beta', 'beta', 'H1', 'r2'),
          ('ref-alpha', 'alpha', None, 'ref'))
T0 = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
# Text a report must never hold: every outcome the harness writes, the word score, and markers put in the records' score and reason.
FORBIDDEN = tuple(TERMINAL) + ('score', 'SCORE-MARKER', 'REASON-MARKER', 'SUBMISSION-MARKER', 'outcome')


def key(block, task, model):
    _, arm, _, suffix = next(b for b in BLOCKS if b[0] == block)
    return '%s__%s__%s__%s' % (arm, task, model, suffix)


class RunFolder:
    """A run folder written the way runner.py writes it, with a clock that moves one minute per event."""

    def __init__(self, root, run_id='study2-fixture-1'):
        self.dir = Path(root) / run_id
        self.run_id = run_id
        self.minutes = 0
        self.seq = {'anthropic': 0, 'openai': 0}

    def at(self):
        self.minutes += 1
        return (T0 + timedelta(minutes=self.minutes)).isoformat(timespec='milliseconds')

    def append(self, name, entry):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / name, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(entry, sort_keys=True) + '\n')

    def write(self, name, value):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')

    def manifest(self, schedule=True, carried=None, ceilings=None):
        blocks = [{'id': bid, 'arm': arm, 'half': half, 'runSuffix': suffix, 'sequence': n + 1, 'row': 1 if half else None,
                   'runs': [{'model': model, 'task': task} for task, model in TASKS]} for n, (bid, arm, half, suffix) in enumerate(BLOCKS)]
        ceilings = ceilings or {'anthropic': 20.0, 'openai': 10.0}
        body = {'studyRunId': self.run_id, 'models': {m: {'vendor': p['vendor'], 'priceEntry': dict(p)} for m, p in PRICES.items()},
                'tokenBudgets': {v: {'dollar_ceiling': c, 'ceiling_basis': 'fixture', 'tokens': 5_000_000} for v, c in ceilings.items()}}
        if schedule:
            body.update({'schedule': {'blocks': blocks, 'reference': 'alpha'}, 'vendorErrorRequeues': 1,
                         'budgetCarry': {'runs': [], 'totals': carried if carried is not None else {'anthropic': 1.5, 'openai': 0.5},
                                         'rule': 'fixture'}})
        self.write('manifest.json', body)

    def block(self, event, block, attempt=1, **fields):
        _, arm, half, _ = next(b for b in BLOCKS if b[0] == block)
        sequence = [b[0] for b in BLOCKS].index(block) + 1
        self.append('blocks.jsonl', {'at': self.at(), 'event': event, 'block': block, 'arm': arm, 'sequence': sequence, 'row': 1,
                                     'attempt': attempt, **fields})

    def request(self, run, model, output, retry=False, note=None, settle=True):
        vendor = PRICES[model]['vendor']
        self.seq[vendor] += 1
        seq = self.seq[vendor]
        name = 'budget-%s.jsonl' % vendor
        self.append(name, {'event': 'reserve', 'seq': seq, 'run': run, 'label': 'request', 'tokens': 20000, 'inputTokens': 4000,
                           'maxOutputTokens': 16000, 'ts': self.at()})
        if settle:
            self.append(name, {'event': 'settle', 'seq': seq, 'usage': {'input': 0, 'cached_read': 0, 'cache_write': 0, 'output': output},
                               'retry': retry, 'note': note, 'requestSeconds': 1.0, 'ts': self.at()})

    def run(self, block, task, model, outcome='correct', output=10000, vendor_errors=0, requeued=False):
        """One run with its record and one settled request of `output` tokens (output 10000 costs 0.10 dollars)."""
        run = key(block, task, model)
        self.request(run, model, output)
        self.write('runs/%s/result.json' % run, {'runKey': run, 'model': model, 'outcome': outcome, 'taskId': task,
                                                 'score': {'score': 0.4242, 'tags': ['SCORE-MARKER']}, 'reason': 'REASON-MARKER',
                                                 'submission': 'SUBMISSION-MARKER', 'vendorErrors': vendor_errors, 'requeued': requeued,
                                                 'blockAttempt': 1})

    def whole_block(self, block, outcomes=('correct', 'wrong_answer', 'silent_guess', 'abstained'), outputs=(10000,) * 4):
        self.block('start', block, session='s1')
        for (task, model), outcome, output in zip(TASKS, outcomes, outputs):
            self.run(block, task, model, outcome, output=output)
        counts = {}
        for outcome in outcomes:
            counts[outcome] = counts.get(outcome, 0) + 1
        self.block('end', block, session='s1', outcomes=counts)

    def resume(self, kept, ceilings=None):
        entry = {'at': self.at(), 'completedRunsKept': kept}
        if ceilings:
            entry['ceilings'] = {v: {'dollar_ceiling': c, 'ceiling_basis': 'a raise'} for v, c in ceilings.items()}
        self.append('resumes.jsonl', entry)

    def bundle(self, status):
        written = self.at()
        self.write('bundle.json', {'studyRunId': self.run_id, 'status': status, 'writtenAt': written, 'files': {}, 'checksum': 'x'})
        moment = datetime.fromisoformat(written).timestamp()  # the watcher reads the write time from the listing, on the fixture's clock
        os.utime(self.dir / 'bundle.json', (moment, moment))


def snapshot(folder):
    """Every path under the folder with its size, modification time and content hash."""
    out = {}
    for path in sorted(Path(folder).rglob('*')):
        info = path.stat()
        out[path.relative_to(folder).as_posix()] = (path.is_dir(), info.st_size, info.st_mtime_ns,
                                                     None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest())
    return out


def once(folder, balances=None, now=None):
    out = io.StringIO()
    code = watch_run.follow(Path(folder), out, once=True, balances=balances, sleep=lambda _s: None,
                            now=lambda: now or T0 + timedelta(hours=2))
    return code, out.getvalue()


class WatchRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='watch-run-')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.run_folder = RunFolder(self.tmp)

    def assertNoOutcome(self, text):
        lowered = text.lower()
        for word in FORBIDDEN:
            self.assertNotIn(word.lower(), lowered, 'the report names %r' % word)
        self.assertNotIn('0.4242', text)

    # ------------------------------------------------------------ the shapes of a run
    def test_no_run_yet(self):
        code, text = once(self.run_folder.dir)
        self.assertEqual(code, 0)
        self.assertIn('has not started', text)
        self.assertFalse(self.run_folder.dir.exists(), 'the watcher never creates the folder')
        out, sleeps = io.StringIO(), []
        self.assertEqual(watch_run.follow(self.run_folder.dir, out, polls=2, sleep=sleeps.append), 0)
        self.assertEqual(len(sleeps), 2)
        self.assertFalse(self.run_folder.dir.exists())

    def test_started_with_no_block_yet(self):
        self.run_folder.manifest()
        code, text = once(self.run_folder.dir)
        self.assertEqual(code, 0)
        self.assertIn('blocks ended 0 of 4; runs finished 0 of 16\n', text)
        self.assertIn('now: no block has started yet', text)
        self.assertIn('anthropic: 8 run(s) left, about 0.00 for 0 of them; too early for 8', text)

    def test_partway(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.whole_block('r1-gamma', outputs=(30000, 50000, 10000, 10000))
        f.block('start', 'r2-beta', session='s1')
        f.run('r2-beta', 'T1', GPT, output=20000)
        f.request(key('r2-beta', 'T3', GPT), GPT, 0, settle=False)  # the request in flight
        code, text = once(f.dir)
        self.assertEqual(code, 0)
        self.assertIn('blocks ended 2 of 4; runs finished 8 of 16 (block r2-beta not counted until it ends, 1 of its runs with spend in '
                      'the ledger)', text)
        self.assertIn('now: block r2-beta (sequence 3, arm beta, half H1, attempt 1) since 2026-11-06 10:', text)
        # anthropic: 0.10 + 0.10, then 0.50 + 0.10 settled; carried 1.50; ceiling 20
        self.assertIn('anthropic: this run 0.80 + carried 1.50 = 2.30 of ceiling 20.00, room 17.70', text)
        # openai: 0.20, 0.40 and 0.20 settled, and one open reservation of 20000 tokens at the output price, 0.20
        self.assertIn('openai: this run 1.00 + carried 0.50 = 1.50 of ceiling 10.00, room 8.50', text)
        self.assertIn('open reservations: 1 (20,000 tokens), counted at the output price: 0.20', text)
        for vendor, price in (('anthropic', PRICES[CLAUDE]), ('openai', PRICES[GPT])):
            expected = ledger_dollars(f.dir / ('budget-%s.jsonl' % vendor), price)[0]
            self.assertAlmostEqual(watch_run.RunState.read(f.dir).ledgers[vendor].counted_dollars, expected, places=9)
        # left: r2-beta's four at beta's mean for their model (0.10 each), alpha's four at their model's mean (gpt 0.15, claude 0.20);
        # r2-beta's T1 has spend in the block's attempt and may be finished, so the low end leaves it out
        self.assertIn('openai: 4 run(s) left, about 0.50 (0.40 if the 1 run(s) with spend in a block not ended yet are finished already); '
                      'total about 2.00 of ceiling 10.00, room after about 8.00', text)
        self.assertIn('anthropic: 4 run(s) left, about 0.60; total about 2.90 of ceiling 20.00, room after about 17.10', text)
        self.assertIn('based on 4 finished run(s) of gpt-fixture; 2 run(s) priced by their arm and model, 2 by their model alone', text)
        self.assertNoOutcome(text)

    def test_a_void(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.block('start', 'r1-gamma', session='s1')
        f.run('r1-gamma', 'T1', GPT)
        f.block('void', 'r1-gamma', trigger='health', point='periodic', problems=['assets: assets-service is not running'],
                runs=[key('r1-gamma', 'T1', GPT)], spend={'openai': {'dollars': 0.1, 'tokens': 10000, 'runs': 1}})
        (f.dir / 'runs-void' / 'r1-gamma' / '1').mkdir(parents=True)
        shutil.move(str(f.dir / 'runs' / key('r1-gamma', 'T1', GPT)), str(f.dir / 'runs-void' / 'r1-gamma' / '1'))
        f.bundle('block_void')
        code, text = once(f.dir)
        self.assertIn('void: block r1-gamma attempt 1, trigger health at periodic, 1 problem(s): assets: assets-service is not running', text)
        self.assertIn('blocks ended 1 of 4; runs finished 4 of 16', text)
        self.assertIn('now: no block running; the harness wrote bundle.json at 2026-11-06 10:', text)
        self.assertIn('(block_void, from the events)', text)
        self.assertIn('openai: this run 0.30', text, 'the void attempt stays in the ledger and is counted')
        # the repeat: attempt 2 runs and ends; the block counts as ended for its current attempt only
        f.resume(4)
        f.block('start', 'r1-gamma', attempt=2, session='s1')
        code, text = once(f.dir)
        self.assertIn('now: block r1-gamma (sequence 2, arm gamma, half H2, attempt 2)', text)
        self.assertIn('blocks ended 1 of 4', text)
        self.assertNoOutcome(text)

    def test_a_retry_and_a_vendor_error(self):
        f = self.run_folder
        f.manifest()
        f.block('start', 'r1-beta', session='s1')
        run = key('r1-beta', 'T1', GPT)
        f.request(run, GPT, 0, retry=True, note='transient: Connection error.')
        f.request(run, GPT, 10000, note='after 1 retries')
        f.write('runs/%s/result.json' % run, {'runKey': run, 'model': GPT, 'outcome': 'error', 'vendorErrors': 1, 'requeued': False,
                                              'reason': 'REASON-MARKER'})
        f.run('r1-beta', 'T2', CLAUDE, outcome='vendor_error', vendor_errors=2, requeued=True)
        f.block('end', 'r1-beta', session='s1', outcomes={'error': 1, 'vendor_error': 1, 'missing': 2})
        code, text = once(f.dir)
        self.assertIn('openai: 2 requests settled, 1 retried; notes: "after 1 retries" x1, "transient: Connection error." x1', text)
        self.assertIn('vendor errors: 3 attempt(s) ended on one; 1 run(s) queued again (the manifest allows 1 requeue per run)', text)
        self.assertIn('runs finished 1 of 16', text, 'a run waiting for its requeue is not finished')
        self.assertNoOutcome(text)

    def test_a_resume_with_a_new_ceiling(self):
        f = self.run_folder
        f.manifest()
        f.block('start', 'r1-beta', session='s1')
        f.run('r1-beta', 'T1', GPT)
        f.bundle('budget_stop')
        f.resume(1, ceilings={'anthropic': 30.0, 'openai': 12.0})
        code, text = once(f.dir)
        self.assertIn('resumes: 1 (last at', text)
        self.assertIn('1 finished runs kept', text)
        self.assertIn('now: a resume started at', text)
        self.assertIn('of ceiling 30.00', text)
        self.assertIn('of ceiling 12.00', text)
        f.block('start', 'r1-beta', session='s1')
        code, text = once(f.dir)
        self.assertIn('blocks started again within one attempt (a stop with no event, then a resume): r1-beta attempt 1 (2 starts)', text)
        self.assertIn('now: block r1-beta', text)

    def test_ended(self):
        f = self.run_folder
        f.manifest()
        for block, _, _, _ in BLOCKS:
            f.whole_block(block, outcomes=('correct', 'format_error', 'definition_not_accepted', 'did_not_finish'))
        f.bundle('complete')
        out, sleeps = io.StringIO(), []
        self.assertEqual(watch_run.follow(f.dir, out, sleep=sleeps.append, now=lambda: T0 + timedelta(hours=3)), 0)
        text = out.getvalue()
        self.assertEqual(sleeps, [], 'a complete run is reported once')
        self.assertIn('blocks ended 4 of 4; runs finished 16 of 16', text)
        self.assertIn('(complete, from the events)', text)
        self.assertIn('anthropic: no run left', text)
        self.assertIn('per ended block on average', text)
        self.assertNoOutcome(text)

    def test_balances(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        code, text = once(f.dir, balances={'anthropic': 60.0})
        self.assertIn('Balances (given on the command line when the watcher started; never stored)', text)
        self.assertIn('anthropic: 60.00 - 0.00 spent since = 60.00 room; after the estimated rest about 59.40', text)
        # spend after the watcher started is taken from the balance
        out = io.StringIO()

        def harness(_seconds):
            f.whole_block('r1-gamma')
        watch_run.follow(f.dir, out, balances={'anthropic': 60.0}, polls=1, sleep=harness, now=lambda: T0)
        self.assertIn('anthropic: 60.00 - 0.20 spent since = 59.80 room', out.getvalue())
        self.assertEqual(watch_run.parse_balance('openai=12.5'), ('openai', 12.5))
        for bad in ('openai', 'openai=', '=3', 'openai=-1', 'openai=lots'):
            with self.assertRaises(Exception):
                watch_run.parse_balance(bad)
        with redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(watch_run.main([str(f.dir), '--once', '--balance', 'nobody=1']), 2)
        self.assertIn('No such vendor in the manifest: nobody', printed.getvalue())

    # ------------------------------------------------------------ following
    def test_follow_reports_after_each_event_and_ends_on_the_bundle(self):
        f = self.run_folder
        f.manifest()
        f.bundle('budget_stop')  # an earlier stop: its bundle does not end the watcher
        steps = [lambda: f.resume(0), lambda: f.whole_block('r1-beta'), lambda: None,
                 lambda: (f.block('start', 'r1-gamma', session='s1'),
                          f.block('void', 'r1-gamma', trigger='health', point='start', problems=['x'], runs=[], spend={})),
                 lambda: f.bundle('block_void'), lambda: self.fail('the watcher polled after the bundle')]
        out = io.StringIO()
        code = watch_run.follow(f.dir, out, sleep=lambda s: steps.pop(0)() if s == watch_run.DEFAULT_INTERVAL else None, now=lambda: T0)
        self.assertEqual(code, 0)
        heads = re.findall(r'^== study2-fixture-1 at \S+ \S+ UTC \((.*)\) ==$', out.getvalue(), re.M)
        self.assertEqual(heads, ['watcher start', 'a resume started', 'the end of block r1-beta', 'a void of block r1-gamma',
                                 'the harness wrote bundle.json (block_void)'])
        self.assertNoOutcome(out.getvalue())

    def test_the_watcher_only_reads(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.block('start', 'r1-gamma', session='s1')
        f.run('r1-gamma', 'T1', GPT)
        f.request(key('r1-gamma', 'T3', GPT), GPT, 0, settle=False)
        before = snapshot(f.dir)
        once(f.dir, balances={'openai': 5.0})
        watch_run.follow(f.dir, io.StringIO(), polls=3, sleep=lambda _s: None, balances={'openai': 5.0})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(watch_run.main([str(f.dir), '--polls', '2', '--interval', '0.01']), 0)
        self.assertEqual(snapshot(f.dir), before)

    def test_a_line_being_written_is_left_for_the_next_read(self):
        f = self.run_folder
        f.manifest()
        f.block('start', 'r1-beta', session='s1')
        with open(f.dir / 'blocks.jsonl', 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('{"event": "end", "blo')
        events, bad = watch_run.read_jsonl(f.dir / 'blocks.jsonl')
        self.assertEqual(([e['event'] for e in events], bad), (['start'], 0))
        with open(f.dir / 'blocks.jsonl', 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('\nnot json\n')
        self.assertEqual(watch_run.read_jsonl(f.dir / 'blocks.jsonl')[1], 2)
        self.assertIn('unreadable lines: 2', once(f.dir)[1])

    def test_while_the_run_is_live_it_opens_no_file_the_harness_replaces_or_moves(self):
        # On Windows a file held open, even for a moment, cannot be replaced and its folder cannot be moved. The watcher therefore opens
        # no result.json of the block that may be running, and bundle.json only once its listing has settled.
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.bundle('budget_stop')
        f.resume(4)
        f.block('start', 'r1-gamma', session='s1')
        f.run('r1-gamma', 'T1', GPT)
        log = []
        real = watch_run.read_text

        def recording(path):
            log.append(Path(path).relative_to(f.dir).as_posix())
            return real(path)

        def harness(seconds):
            log.append('sleep %s' % seconds)
            if seconds == watch_run.DEFAULT_INTERVAL and 'gamma ended' not in log:
                f.run('r1-gamma', 'T2', CLAUDE)
                f.block('end', 'r1-gamma', session='s1', outcomes={'correct': 2})
                log.append('gamma ended')
        with unittest.mock.patch.object(watch_run, 'read_text', recording):
            watch_run.follow(f.dir, io.StringIO(), polls=2, sleep=harness, now=lambda: T0)
        gamma = [i for i, name in enumerate(log) if name.startswith('runs/gamma__')]
        self.assertTrue(gamma, 'the block is read once it ended')
        self.assertGreater(min(gamma), log.index('gamma ended'), 'no record of the running block before its end')
        r2_beta = [i for i, name in enumerate(log) if name.startswith('runs/') and name.endswith('__r2/result.json')]
        self.assertTrue(all(i < log.index('gamma ended') for i in r2_beta),
                        'nor of the next block once it may be starting (before, it had no files to read)')
        self.assertNotIn('bundle.json', log, 'bundle.json is never opened: its listing gives its write time')

    def test_no_record_of_a_block_is_opened_before_its_end_whatever_the_harness_does_meanwhile(self):
        # The harness may move on between any two reads of the watcher. Here it takes one step at every file the watcher opens: the
        # running block ends, the next starts, runs and stops, a resume starts and repeats it. Each result.json the watcher opens must
        # belong to a block whose current attempt had ended in blocks.jsonl at that moment, so the harness never touches it again.
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.block('start', 'r1-gamma', session='s1')
        f.run('r1-gamma', 'T1', GPT)
        steps = [lambda: f.run('r1-gamma', 'T2', CLAUDE), lambda: f.block('end', 'r1-gamma', session='s1', outcomes={}),
                 lambda: f.block('start', 'r2-beta', session='s1'), lambda: f.run('r2-beta', 'T1', GPT),
                 lambda: f.block('stopped', 'r2-beta', session='s1', reason='budget_stop', runKey='x'), lambda: f.bundle('budget_stop'),
                 lambda: f.resume(9), lambda: f.block('start', 'r2-beta', session='s1'), lambda: f.run('r2-beta', 'T2', CLAUDE)]
        opened, real = [], watch_run.read_text

        def ended_now():
            events = [json.loads(line) for line in (f.dir / 'blocks.jsonl').read_text(encoding='utf-8').splitlines()]
            voids = {}
            for event in events:
                if event['event'] == 'void':
                    voids[event['block']] = voids.get(event['block'], 0) + 1
            return {e['block'] for e in events if e['event'] == 'end' and e['attempt'] == 1 + voids.get(e['block'], 0)}

        def stepping(path):
            name = Path(path).relative_to(f.dir).as_posix()
            if name.startswith('runs/'):
                block = next(b for b, arm, _, suffix in BLOCKS if name.startswith('runs/%s__' % arm) and name.endswith('__%s/result.json' % suffix))
                opened.append((name, block in ended_now()))
            if steps:
                steps.pop(0)()
            return real(path)
        with unittest.mock.patch.object(watch_run, 'read_text', stepping):
            for _ in range(4):
                watch_run.follow(f.dir, io.StringIO(), once=True, sleep=lambda _s: None, now=lambda: T0)
        self.assertEqual(steps, [], 'the harness took every step')
        self.assertTrue(opened)
        self.assertEqual([name for name, ended in opened if not ended], [])

    def test_a_resumed_block_does_not_price_its_finished_runs_again(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.whole_block('r1-gamma')
        f.block('start', 'r2-beta', session='s1')
        f.run('r2-beta', 'T1', GPT)  # finished, 0.10, as beta's gpt mean
        f.run('r2-beta', 'T2', CLAUDE, output=4000)  # finished, 0.04, below beta's claude mean of 0.10
        f.block('stopped', 'r2-beta', session='s1', reason='budget_stop', runKey=key('r2-beta', 'T3', GPT))
        f.bundle('budget_stop')
        f.resume(10)
        f.block('start', 'r2-beta', session='s1')
        code, text = once(f.dir)
        self.assertIn('runs finished 8 of 16 (block r2-beta not counted until it ends, 2 of its runs with spend in the ledger)', text)
        # T1 and T2 have spend in the block's attempt and may be finished (they are): 0.40 if not, 0.30 if they are
        self.assertIn('openai: 4 run(s) left, about 0.40 (0.30 if the 1 run(s) with spend in a block not ended yet are finished already)',
                      text)
        self.assertIn('anthropic: 4 run(s) left, about 0.40 (0.30 if the 1 run(s) with spend', text)
        f.run('r2-beta', 'T3', GPT)
        f.run('r2-beta', 'T4', CLAUDE)
        f.block('end', 'r2-beta', session='s1', outcomes={})
        code, text = once(f.dir)
        self.assertIn('blocks ended 3 of 4; runs finished 12 of 16\n', text)
        self.assertIn('openai: 2 run(s) left, about 0.20;', text)

    def test_a_void_attempt_spend_is_not_credited_to_its_repeat(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.whole_block('r1-gamma')
        f.block('start', 'r2-beta', session='s1')
        f.run('r2-beta', 'T1', GPT, output=200000)  # 2.00 in the void attempt
        f.block('void', 'r2-beta', trigger='health', point='end', problems=['x'], runs=[key('r2-beta', 'T1', GPT)], spend={})
        f.bundle('block_void')
        f.resume(8)
        f.block('start', 'r2-beta', attempt=2, session='s1')
        code, text = once(f.dir)
        # r2-beta's T1 and T3 at beta's gpt mean 0.10 each, alpha's two at gpt's mean 0.10: the 2.00 of the void attempt is no credit
        self.assertIn('openai: 4 run(s) left, about 0.40; total about', text)
        self.assertIn('runs finished 8 of 16 (block r2-beta not counted until it ends, 0 of its runs with spend in the ledger)', text)
        self.assertIn('openai: this run 2.40', text, 'the void attempt stays in the spend')
        f.run('r2-beta', 'T1', GPT)
        code, text = once(f.dir)
        self.assertIn('openai: 4 run(s) left, about 0.40 (0.30 if the 1 run(s) with spend', text)

    def test_a_reservation_open_at_the_start_is_never_negative_spend(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        f.block('start', 'r1-gamma', session='s1')
        run = key('r1-gamma', 'T1', GPT)
        f.request(run, GPT, 0, settle=False)  # open: 20000 tokens, 0.20 at the output price
        out = io.StringIO()

        def harness(_seconds):
            f.append('budget-openai.jsonl', {'event': 'settle', 'seq': f.seq['openai'], 'usage': {'input': 0, 'cached_read': 0,
                     'cache_write': 0, 'output': 5000}, 'retry': False, 'note': None, 'ts': f.at()})  # settles for 0.05
            f.block('end', 'r1-gamma', session='s1', outcomes={})
        watch_run.follow(f.dir, out, balances={'openai': 5.0}, polls=1, sleep=harness, now=lambda: T0)
        first, second = out.getvalue().split('\n\n')
        self.assertIn('openai: 5.00 - 0.00 spent since - 0.20 held by open reservations at the output price = 4.80 room', first)
        self.assertIn('openai: 5.00 - 0.05 spent since = 4.95 room', second)
        self.assertNotIn('- -', out.getvalue())

    def test_a_bundle_written_just_after_a_read_is_still_reported(self):
        # The harness may write its last event and bundle.json right after the watcher read the state it reports: at the start, and
        # after a poll that found a change. The next poll must see them as new, report the end and stop.
        for hook_at in (1, 2):
            with self.subTest(read=hook_at):
                f = RunFolder(self.tmp, 'study2-fixture-%d' % hook_at)
                f.manifest()
                for block, _, _, _ in BLOCKS[:3]:
                    f.whole_block(block)
                f.block('start', 'ref-alpha', session='s1')
                for task, model in TASKS:
                    f.run('ref-alpha', task, model)
                real, calls, changed = watch_run.RunState.read, [], []

                def reading(folder, real=real, calls=calls, f=f, hook_at=hook_at):
                    state = real(folder)
                    calls.append(1)
                    if len(calls) == hook_at:
                        f.block('end', 'ref-alpha', session='s1', outcomes={})
                        f.bundle('complete')
                    return state

                def harness(_seconds, f=f, changed=changed):
                    if not changed:  # one change, so that the second read follows a poll
                        changed.append(1)
                        f.resume(12)
                out = io.StringIO()
                with unittest.mock.patch.object(watch_run.RunState, 'read', staticmethod(reading)):
                    code = watch_run.follow(f.dir, out, polls=5, sleep=harness if hook_at == 2 else (lambda _s: None), now=lambda: T0)
                self.assertEqual(code, 0)
                heads = re.findall(r'^== \S+ at \S+ \S+ UTC \((.*)\) ==$', out.getvalue(), re.M)
                self.assertEqual(heads[-1], 'the harness wrote bundle.json (complete)', heads)
                self.assertIn('blocks ended 4 of 4; runs finished 16 of 16', out.getvalue().split('\n\n')[-1])
                self.assertLess(len(calls), 5, 'it stopped on the bundle instead of polling on')

    def test_a_bundle_written_within_one_snapshot_comes_with_its_last_event(self):
        # The harness appends the last block's end and then writes bundle.json. If both land while the watcher is between its reads of
        # one snapshot, the snapshot must not hold the new bundle with the old events: a report would then call the run stopped, leave
        # the last block out and end. Here both land just after the snapshot read blocks.jsonl: at the start, and in a poll.
        for hook_at in (1, 3):  # block_events calls: 1 is the start's snapshot; 2 a poll's check and 3 that poll's snapshot
            with self.subTest(read=hook_at):
                f = RunFolder(self.tmp, 'study2-within-%d' % hook_at)
                f.manifest()
                for block, _, _, _ in BLOCKS[:3]:
                    f.whole_block(block)
                f.block('start', 'ref-alpha', session='s1')
                for task, model in TASKS:
                    f.run('ref-alpha', task, model)
                real, calls, changed = watch_run.block_events, [], []

                def reading(folder, real=real, calls=calls, f=f, hook_at=hook_at):
                    events = real(folder)
                    calls.append(1)
                    if len(calls) == hook_at:  # just after the snapshot read blocks.jsonl
                        f.block('end', 'ref-alpha', session='s1', outcomes={})
                        f.bundle('complete')
                    return events

                def harness(_seconds, f=f, changed=changed):
                    if not changed:  # one change, so that the first poll takes a snapshot
                        changed.append(1)
                        f.resume(12)
                out = io.StringIO()
                with unittest.mock.patch.object(watch_run, 'block_events', reading):
                    code = watch_run.follow(f.dir, out, polls=5, sleep=harness if hook_at == 3 else (lambda _s: None), now=lambda: T0)
                self.assertEqual(code, 0)
                reports = out.getvalue().split('\n\n')
                heads = re.findall(r'^== \S+ at \S+ \S+ UTC \((.*)\) ==$', out.getvalue(), re.M)
                self.assertEqual(heads[-1], 'the harness wrote bundle.json (complete)', heads)
                self.assertIn('blocks ended 4 of 4; runs finished 16 of 16', reports[-1])
                for text in reports:
                    self.assertNotIn('(stopped, from the events)', text)

    def test_end_events_lose_their_outcomes_on_reading(self):
        f = self.run_folder
        f.manifest()
        f.whole_block('r1-beta')
        events, _ = watch_run.block_events(f.dir)
        self.assertTrue(all('outcomes' not in e for e in events))
        record = watch_run.run_record(f.dir / 'runs' / key('r1-beta', 'T1', GPT) / 'result.json')
        self.assertEqual(sorted(record), ['finished', 'requeued', 'vendorErrors'])

    def test_refuses_a_run_without_a_schedule(self):
        self.run_folder.manifest(schedule=False)
        with redirect_stderr(io.StringIO()) as printed:
            self.assertEqual(watch_run.main([str(self.run_folder.dir), '--once']), 2)
        self.assertIn('holds no block schedule', printed.getvalue())


if __name__ == '__main__':
    unittest.main()
