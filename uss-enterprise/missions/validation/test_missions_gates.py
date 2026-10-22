"""Missions admission and harness regressions; no runtime acceptance claim."""
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import missions_runtime as gates

ROOT = Path(__file__).resolve().parents[3]


class HarnessTest(unittest.TestCase):
    def setUp(self):
        # Discovery inside the gate inserts each probe folder into sys.path; restore it, like sys.modules below.
        saved = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.component = Path(self.temp.name)
        self.fixture_number = 0

    def directory(self):
        path = self.component / 'validation/runtime/data'
        path.mkdir(parents=True)
        return path

    def test_absent_and_empty_suites_fail(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            gates.validate('data', self.component)
        self.directory()
        with self.assertRaisesRegex(ValueError, 'Empty'):
            gates.validate('data', self.component)

    def run_fixture(self, body):
        self.fixture_number += 1
        component = self.component / ('probe_' + str(self.fixture_number))
        directory = component / 'validation/runtime/data'
        directory.mkdir(parents=True)
        name = 'test_probe_' + self.component.name.replace('-', '_') + '_' + str(self.fixture_number)
        (directory / (name + '.py')).write_text('import unittest\n' + body, encoding='utf-8')
        self.addCleanup(sys.modules.pop, name, None)
        return gates.validate('data', component, io.StringIO())

    def test_executed_suite_passes(self):
        self.assertEqual(self.run_fixture('class Probe(unittest.TestCase):\n    def test_ok(self): self.assertEqual(2 + 2, 4)\n'), 1)

    def test_skips_and_expected_failures_are_not_pass(self):
        for decorator, statement in (("@unittest.skip('missing Oracle')", 'pass'),
                                     ('@unittest.expectedFailure', 'self.fail()')):
            with self.subTest(decorator=decorator), self.assertRaisesRegex(ValueError, 'gate failed'):
                self.run_fixture('class Probe(unittest.TestCase):\n    ' + decorator +
                                 '\n    def test_probe(self): ' + statement + '\n')

    def test_failure_and_import_error_fail(self):
        for body in ('class Probe(unittest.TestCase):\n    def test_bad(self): self.fail("database unavailable")\n',
                     'raise ImportError("missing runtime dependency")\n'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, 'gate failed'):
                self.run_fixture(body)

    def test_incomplete_execution_fails(self):
        directory = self.directory()
        suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        result = unittest.TestResult()
        with patch.object(unittest.TestLoader, 'discover', return_value=suite), patch.object(unittest.TextTestRunner, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'gate failed'):
                gates.validate('data', self.component)

    def test_unknown_stage_fails(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            gates.validate('soap', self.component)

    def test_cli_absent_runtime_fails_with_no_pass_claim(self):
        # This repository currently has no runtime suites. Invoke a copied harness
        # in an empty root so this regression stays valid after runtime lands.
        script = self.component / 'validation/missions_runtime.py'
        script.parent.mkdir()
        script.write_bytes((ROOT / 'uss-enterprise/missions/validation/missions_runtime.py').read_bytes())
        result = subprocess.run([sys.executable, '-B', str(script), 'data'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Missing Missions data suite', result.stderr)
        self.assertNotIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main()
