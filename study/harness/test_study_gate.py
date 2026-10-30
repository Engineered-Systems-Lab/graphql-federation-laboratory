"""Tests of the study gate's choice of interpreter and its list of suites. It starts no suite itself."""
import os
import sys
import unittest
from unittest import mock

import study_gate


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


if __name__ == '__main__':
    unittest.main()
