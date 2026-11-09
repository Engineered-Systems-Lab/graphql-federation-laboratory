"""Tests of the study gate: its choice of interpreter, its list of suites, and how it runs them, on fake suites that need no package and
run in a moment. It never starts a real suite."""
import io
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import study_gate

FAKE_TEST = '''import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Fake(unittest.TestCase):
    def test_fake(self):
        delay, outcome = (HERE / 'spec.txt').read_text(encoding='utf-8').split()
        (HERE / 'start.txt').write_text(repr(time.time()), encoding='utf-8')
        sys.stderr.write('\\n')  # end the line unittest -v has begun, so each line below stands alone
        sys.stderr.flush()
        for i in range(3):
            print('%s says %d' % (HERE.name, i), flush=True)
            sys.stderr.write('%s warns %d\\n' % (HERE.name, i))
            sys.stderr.flush()
            time.sleep(float(delay) / 3)
        print('%s sees \\u00e9 and \\u2713' % HERE.name, flush=True)
        sys.stderr.write('%s also sees \\u00e9 and \\u2713\\n' % HERE.name)
        sys.stderr.flush()
        (HERE / 'end.txt').write_text(repr(time.time()), encoding='utf-8')
        self.assertEqual(outcome, 'pass')
'''


def fake_interpreter(mode):
    """The fakes need nothing; a 'require' suite stands for one whose package is missing."""
    return None if mode == 'require' else sys.executable


class GateTests(unittest.TestCase):
    def test_a_suite_that_needs_nothing_uses_the_running_interpreter(self):
        self.assertEqual(study_gate.interpreter_for('no'), sys.executable)

    def test_the_mcp_suite_has_no_interpreter_when_none_has_the_package(self):
        with mock.patch.object(study_gate, 'can_import_mcp', return_value=False), mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(study_gate.interpreter_for('require'))
            self.assertEqual(study_gate.interpreter_for('prefer'), sys.executable)

    def test_the_named_interpreter_is_used_only_when_it_has_the_package(self):
        here = sys.executable
        with mock.patch.object(study_gate, 'can_import_mcp', side_effect=lambda python: python == here), \
                mock.patch.dict(os.environ, {'STUDY_MCP_PYTHON': here}):
            self.assertEqual(study_gate.interpreter_for('require'), here)

    def test_the_analysis_suite_needs_the_statistics_packages(self):
        here = sys.executable
        with mock.patch.object(study_gate, 'can_import_stats', return_value=False), mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(study_gate.interpreter_for('stats'))
        with mock.patch.object(study_gate, 'can_import_stats', side_effect=lambda python: python == here),                 mock.patch.object(study_gate, 'can_import_mcp', return_value=False), mock.patch.dict(os.environ, {'STUDY_MCP_PYTHON': here}):
            self.assertEqual(study_gate.interpreter_for('stats'), here)

    def test_the_suites_cover_the_four_areas(self):
        self.assertEqual([s[0] for s in study_gate.SUITES], ['harness', 'corpus', 'corpus2', 'mcp', 'analysis', 'analysis2', 'launch', 'preflight',
                                                                     'blind'])
        for _, folder, pattern, mode in study_gate.SUITES:
            self.assertTrue((study_gate.STUDY / folder).is_dir())
            self.assertIn(mode, ('no', 'prefer', 'require', 'stats'))

    def test_the_suites_that_start_a_server_are_in_the_server_lane(self):
        self.assertEqual(study_gate.SERVER_LANE, ('harness', 'mcp', 'blind'))
        self.assertLessEqual(set(study_gate.SERVER_LANE), {s[0] for s in study_gate.SUITES})
        self.assertEqual(study_gate.DEFAULT_JOBS, 4)


class FakeSuiteTests(unittest.TestCase):
    """The gate run on fake suites: s1 and s2 stand for the server lane, the f suites for the suites that start no server."""
    DELAY = 0.6

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def suites(self, *names, fail=(), modes=None, delay=None):
        modes = modes or {}
        for name in names:
            folder = self.root / name
            folder.mkdir()
            (folder / 'test_fake.py').write_text(FAKE_TEST, encoding='utf-8')
            (folder / 'spec.txt').write_text('%s %s' % (delay or self.DELAY, 'fail' if name in fail else 'pass'), encoding='utf-8')
        return [(name, name, 'test_*.py', modes.get(name, 'no')) for name in names]

    def run_gate(self, suites, *argv, interpreter=fake_interpreter, lane=('s1', 's2'), encoding='utf-8', newline='', raw=False):
        """Run the gate's main on the fakes; return its exit code and the lines it printed (or its raw bytes)."""
        out = io.TextIOWrapper(io.BytesIO(), encoding=encoding, newline=newline)
        with mock.patch.object(study_gate, 'STUDY', self.root), mock.patch.object(study_gate, 'SUITES', suites), \
                mock.patch.object(study_gate, 'SERVER_LANE', lane), mock.patch.object(study_gate, 'interpreter_for', interpreter), \
                mock.patch.object(sys, 'stdout', out):
            code = study_gate.main(list(argv))
            out.flush()
        data = out.buffer.getvalue()
        return code, data if raw else data.decode(encoding).replace('\r\n', '\n').splitlines()

    def interval(self, name):
        return tuple(float((self.root / name / part).read_text(encoding='utf-8')) for part in ('start.txt', 'end.txt'))

    def test_a_pass_exits_0_with_the_summary_line_of_today(self):
        code, lines = self.run_gate(self.suites('s1', 'f1', 'f2', 's2'))
        self.assertEqual((code, lines[-1]), (0, 'study gate: failed=none not_run=none'))

    def test_a_failure_in_the_free_suites_is_reported_and_exits_1(self):
        code, lines = self.run_gate(self.suites('s1', 'f1', 'f2', 's2', fail=('f2',)))
        self.assertEqual((code, lines[-1]), (1, "study gate: failed=['f2'] not_run=none"))
        self.assertTrue(any(re.fullmatch(r'f2: FAILED \(exit 1\) in \d+ s', line) for line in lines), lines)

    def test_a_failure_in_the_server_lane_is_reported_exits_1_and_the_lane_goes_on(self):
        code, lines = self.run_gate(self.suites('s1', 'f1', 's2', fail=('s1',)))
        self.assertEqual((code, lines[-1]), (1, "study gate: failed=['s1'] not_run=none"))
        self.assertTrue(any(re.fullmatch(r's2: OK in \d+ s', line) for line in lines), lines)

    def test_failures_are_listed_in_the_order_of_suites(self):
        code, lines = self.run_gate(self.suites('f1', 's1', 'f2', fail=('f2', 's1')), '--jobs', '2')
        self.assertEqual((code, lines[-1]), (1, "study gate: failed=['s1', 'f2'] not_run=none"))

    def test_not_run_passes_and_require_mcp_makes_it_fail_as_today(self):
        suites = self.suites('s1', 'f1', 'm1', modes={'m1': 'require'})
        code, lines = self.run_gate(suites)
        self.assertEqual((code, lines[-1]), (0, "study gate: failed=none not_run=['m1']"))
        self.assertIn('NOT RUN: m1 (the mcp package is not installed in this interpreter or in STUDY_MCP_PYTHON)', lines)
        self.assertFalse(any(line.startswith('== m1') for line in lines))
        code, lines = self.run_gate(suites, '--require-mcp')
        self.assertEqual((code, lines[-1]), (1, "study gate: failed=none not_run=['m1']"))

    def test_jobs_1_runs_the_suites_one_at_a_time_in_the_order_of_suites(self):
        names = ['f1', 's1', 'f2', 'f3', 's2']
        code, lines = self.run_gate(self.suites(*names), '--jobs', '1')
        self.assertEqual(code, 0)
        intervals = [self.interval(name) for name in names]
        for (_, end), (start, _) in zip(intervals, intervals[1:]):
            self.assertLessEqual(end, start)
        self.assertEqual([line[3:].split(':')[0] for line in lines if line.startswith('== ')], names)

    def test_the_server_lane_never_runs_two_suites_at_once_and_the_free_suites_run_side_by_side(self):
        code, _ = self.run_gate(self.suites('s1', 'f1', 'f2', 'f3', 'f4', 's2'), '--jobs', '4')
        self.assertEqual(code, 0)
        (_, s1_end), (s2_start, _) = self.interval('s1'), self.interval('s2')
        self.assertLessEqual(s1_end, s2_start, 's2 starts only after s1 ended')
        free = sorted(self.interval(name) for name in ('f1', 'f2', 'f3', 'f4'))
        self.assertTrue(any(later[0] < earlier[1] for earlier, later in zip(free, free[1:])), 'some free suites ran at the same time')
        self.assertLess(free[0][0], s1_end, 'the free suites run beside the server lane')

    def test_each_suite_has_a_start_line_an_end_line_and_one_whole_block(self):
        names = ['s1', 'f1', 'f2', 'f3', 's2']
        code, lines = self.run_gate(self.suites(*names, fail=('f3',)), '--jobs', '3')
        self.assertEqual(code, 1)
        for name in names:
            starts = [i for i, line in enumerate(lines) if line == '== %s: test_*.py in study/%s' % (name, name)]
            ends = [i for i, line in enumerate(lines) if re.fullmatch(r'%s: (OK|FAILED \(exit 1\)) in \d+ s' % name, line)]
            self.assertEqual((len(starts), len(ends)), (1, 1), (name, lines))
            first = min(lines.index('%s says 0' % name), lines.index('%s warns 0' % name))
            block = lines[first:ends[0]]
            self.assertLess(starts[0], first, 'the start line comes before the block')
            for i in range(3):
                self.assertIn('%s says %d' % (name, i), block)
                self.assertIn('%s warns %d' % (name, i), block, 'stderr is in the block')
            self.assertTrue(any(line.startswith('Ran 1 test') for line in block), block)
            others = tuple(['== '] + ['%s %s' % (n, verb) for n in names if n != name for verb in ('says', 'warns')]
                           + ['%s:' % n for n in names if n != name])
            self.assertEqual([line for line in block if line.startswith(others)], [], 'nothing of another suite inside the block of %s' % name)

    def test_jobs_must_be_a_positive_whole_number(self):
        for value in ('0', '-1', 'two'):
            with self.subTest(value=value), mock.patch.object(sys, 'stderr', io.StringIO()), self.assertRaises(SystemExit):
                study_gate.main(['--jobs', value])

    def test_an_interrupt_ends_the_running_suites_and_starts_no_other(self):
        """s1 and f1, f2 are running when the interrupt comes; s2 (the lane's next) and f3 (queued) must never start."""
        names = ['s1', 'f1', 'f2', 'f3', 's2']
        suites = self.suites(*names, delay=4)

        def interrupted(threads):
            deadline = time.monotonic() + 20
            while not all((self.root / n / 'start.txt').exists() for n in ('s1', 'f1', 'f2')):
                self.assertLess(time.monotonic(), deadline, 'the first suites never started')
                time.sleep(0.05)
            raise KeyboardInterrupt

        out = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', newline='')
        started = time.monotonic()
        with mock.patch.object(study_gate, 'STUDY', self.root), mock.patch.object(study_gate, 'SUITES', suites), \
                mock.patch.object(study_gate, 'SERVER_LANE', ('s1', 's2')), mock.patch.object(study_gate, 'interpreter_for', fake_interpreter), \
                mock.patch.object(study_gate, 'wait_for', interrupted), mock.patch.object(sys, 'stdout', out), \
                self.assertRaises(KeyboardInterrupt):
            study_gate.main(['--jobs', '2'])
        self.assertLess(time.monotonic() - started, 4, 'the gate did not wait for the running suites to finish')
        time.sleep(4.5)  # longer than a fake suite runs: one that was not ended would write its end file by now
        for name in ('s1', 'f1', 'f2'):
            self.assertFalse((self.root / name / 'end.txt').exists(), '%s was not ended' % name)
        for name in ('s2', 'f3'):
            self.assertFalse((self.root / name / 'start.txt').exists(), '%s was started after the interrupt' % name)
        out.flush()
        lines = out.buffer.getvalue().decode('utf-8').splitlines()
        self.assertEqual(lines[-1], 'study gate: interrupted; no suite was started after it and every running suite was ended')
        self.assertFalse(any(re.match(r'(s1|f1|f2): ', line) for line in lines), 'an ended suite prints no end line')

    def test_an_interrupt_while_the_lanes_start_stops_the_lane_already_running(self):
        """The interrupt comes as the second lane starts, while the first (the server lane) runs s1: s1 is ended and nothing else starts."""
        suites = self.suites('s1', 'f1', 's2', delay=4)
        original, starts = threading.Thread.start, []

        def start(thread):
            if thread.name.startswith('study-gate-lane-'):
                starts.append(thread.name)
                if len(starts) == 2:
                    deadline = time.monotonic() + 20
                    while not (self.root / 's1' / 'start.txt').exists():
                        self.assertLess(time.monotonic(), deadline, 's1 never started')
                        time.sleep(0.05)
                    raise KeyboardInterrupt
            return original(thread)

        out = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', newline='')
        with mock.patch.object(study_gate, 'STUDY', self.root), mock.patch.object(study_gate, 'SUITES', suites), \
                mock.patch.object(study_gate, 'SERVER_LANE', ('s1', 's2')), mock.patch.object(study_gate, 'interpreter_for', fake_interpreter), \
                mock.patch.object(threading.Thread, 'start', start), mock.patch.object(sys, 'stdout', out), self.assertRaises(KeyboardInterrupt):
            study_gate.main(['--jobs', '2'])
        time.sleep(4.5)
        self.assertFalse((self.root / 's1' / 'end.txt').exists(), 's1 was not ended')
        for name in ('s2', 'f1'):
            self.assertFalse((self.root / name / 'start.txt').exists(), '%s was started after the interrupt' % name)
        out.flush()
        self.assertTrue(out.buffer.getvalue().decode('utf-8').endswith('every running suite was ended\n'))

    def test_a_cancelled_gate_starts_no_suite(self):
        gate = study_gate.Gate({}, {'no': sys.executable})
        gate.cancel()
        with mock.patch.object(study_gate.subprocess, 'Popen', side_effect=AssertionError('a suite was started after the cancel')):
            gate.run_suite(('f1', 'f1', 'test_*.py', 'no'))
        self.assertEqual(gate.passed, {})

    def test_the_cleanup_goes_on_when_taskkill_or_a_kill_fails(self):
        for error in (OSError('no taskkill'), subprocess.TimeoutExpired('taskkill', 30)):
            with self.subTest(error=type(error).__name__):
                first, second = mock.Mock(pid=1), mock.Mock(pid=2)
                first.kill.side_effect = OSError('already gone')
                gate = study_gate.Gate({}, {})
                gate.live.update([first, second])
                with mock.patch.object(study_gate, 'WINDOWS', True), mock.patch.object(study_gate.subprocess, 'run', side_effect=error):
                    gate.cancel()
                first.kill.assert_called_once_with()
                second.kill.assert_called_once_with()

    def test_a_suite_writes_utf_8_and_the_gate_prints_it_in_its_own_encoding(self):
        code, lines = self.run_gate(self.suites('s1', 'f1'))
        self.assertEqual(code, 0)
        for name in ('s1', 'f1'):
            self.assertIn('%s sees é and ✓' % name, lines)
            self.assertIn('%s also sees é and ✓' % name, lines)
        code, lines = self.run_gate(self.suites('s2', 'f2'), encoding='cp1252')
        self.assertEqual((code, lines[-1]), (0, 'study gate: failed=none not_run=none'))
        self.assertIn('f2 sees é and \\u2713', lines, 'a character the stream cannot show is escaped, not an error')

    def test_a_suite_line_ends_once_in_a_stream_that_writes_crlf(self):
        code, data = self.run_gate(self.suites('s1', 'f1'), newline='\r\n', raw=True)
        self.assertEqual(code, 0)
        self.assertNotIn(b'\r\r\n', data)
        self.assertIn(b'f1 says 1\r\nf1 warns 1\r\n', data)

    def test_a_suite_whose_interpreter_cannot_start_fails(self):
        missing = str(self.root / 'no-such-python.exe')
        code, lines = self.run_gate(self.suites('s1', 'f1'), interpreter=lambda mode: missing, lane=('s1',))
        self.assertEqual((code, lines[-1]), (1, "study gate: failed=['s1', 'f1'] not_run=none"))
        self.assertTrue(any(re.fullmatch(r'f1: FAILED \(not started\) in \d+ s', line) for line in lines), lines)


if __name__ == '__main__':
    unittest.main()
