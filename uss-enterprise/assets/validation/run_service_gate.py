"""Fail-closed execution of the Assets gates: the real read service against a disposable PostgreSQL 17 container (stage
service, the default) and the committed Dockerfile and compose file through Docker Compose (stage packaging).

Discovers the tests under validation/runtime/<stage> and runs them. A missing or empty suite, a failure, an error, an import
error (a missing driver included), a skip, an expected failure or an incomplete run is FAIL, never PASS. Docker is required.
"""
from pathlib import Path
import argparse
import sys
import time
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
STAGES = {'service': COMPONENT / 'validation/runtime/service', 'packaging': COMPONENT / 'validation/runtime/packaging'}


def validate(stage='service', directory=None, stream=None):
    directory = Path(directory) if directory else STAGES[stage]
    if not directory.is_dir():
        raise ValueError('Missing Assets ' + stage + ' suite: ' + str(directory))
    # A fresh loader confines discovery to this folder.
    suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py')
    count = suite.countTestCases()
    if count == 0:
        raise ValueError('Empty Assets ' + stage + ' suite: ' + str(directory))
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped or result.expectedFailures or result.testsRun != count):
        raise ValueError('Assets ' + stage + ' gate failed: failures/errors, skips, expected failures or incomplete execution are not PASS')
    print(f'PASS: Assets {stage}: {result.testsRun} tests in {time.monotonic() - started:.1f}s; implemented slice only.')
    return result.testsRun


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', nargs='?', default='service', choices=sorted(STAGES))
    args = parser.parse_args(argv)
    try:
        validate(args.stage)
    except (ValueError, OSError, ImportError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
