"""Fail-closed execution of component-owned Missions acceptance suites.

This harness supplies no service, database, dataset or acceptance tests. Each
implementation slice must deliver its reviewed suite before its gate can pass.
"""
import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / 'uss-enterprise/missions'
STAGES = ('data', 'service', 'packaging')


def validate(stage, component=COMPONENT, stream=None):
    if stage not in STAGES:
        raise ValueError('Unknown Missions gate: ' + stage)
    directory = component / 'validation/runtime' / stage
    if not directory.is_dir():
        raise ValueError('Missing Missions ' + stage + ' suite: ' + str(directory))
    # A fresh loader confines discovery to this stage, including nested packages.
    suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py')
    count = suite.countTestCases()
    if count == 0:
        raise ValueError('Empty Missions ' + stage + ' suite: ' + str(directory))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped or result.expectedFailures
            or result.testsRun != count):
        raise ValueError('Missions ' + stage + ' gate failed: failures/errors, skips, '
                         'expected failures or incomplete execution are not PASS')
    print(f'PASS: Missions {stage}: {result.testsRun} tests; implemented slice only.')
    return result.testsRun


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=STAGES)
    args = parser.parse_args(argv)
    try:
        validate(args.stage)
    except (ValueError, OSError, ImportError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
