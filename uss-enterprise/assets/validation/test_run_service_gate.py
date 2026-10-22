"""The Assets service gate runner fails closed: a missing, empty, failing, skipping or erroring suite is never PASS."""
from pathlib import Path
import io
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_service_gate as gate  # noqa: E402


class RunnerTest(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.number = 0

    def run_suite(self, body):
        self.number += 1
        directory = Path(self.temp.name) / f'suite{self.number}'
        directory.mkdir()
        name = f'test_probe_{id(self)}_{self.number}'
        (directory / (name + '.py')).write_text('import unittest\n' + body, encoding='utf-8')
        self.addCleanup(sys.modules.pop, name, None)
        return gate.validate('service', directory, io.StringIO())

    def test_missing_and_empty_suites_fail(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            gate.validate('service', Path(self.temp.name) / 'absent')
        empty = Path(self.temp.name) / 'empty'
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, 'Empty'):
            gate.validate('service', empty)

    def test_a_passing_suite_passes(self):
        self.assertEqual(self.run_suite('class P(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n'), 1)

    def test_skips_expected_failures_failures_and_import_errors_are_not_pass(self):
        for body in ("class P(unittest.TestCase):\n    @unittest.skip('no docker')\n    def test_x(self): pass\n",
                     'class P(unittest.TestCase):\n    @unittest.expectedFailure\n    def test_x(self): self.fail()\n',
                     'class P(unittest.TestCase):\n    def test_x(self): self.fail("database down")\n',
                     'raise ImportError("psycopg is not installed")\n'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, 'gate failed'):
                self.run_suite(body)

    def test_the_real_gate_folder_exists_and_is_not_empty(self):
        for stage in ('service', 'packaging'):
            self.assertTrue(gate.STAGES[stage].is_dir(), stage)
            self.assertTrue(list(gate.STAGES[stage].glob('test_*.py')), stage)


if __name__ == '__main__':
    unittest.main()
