"""Fail-closed execution of the mapping adapter gate.

Stage offline (the only stage; the adapter has no service behind it): the release checks that need the system files (the hashes of
the release files, the checked-against list, the expected mapping of the Assets dataset); the start script's port rule; and the
committed Dockerfile, which builds the adapter (its build stage runs the offline unit and integration tests, so no JDK or Maven is
needed on the machine), then the image, the compose file and the start script, run on an ephemeral loopback port.

Discovers the tests under validation/runtime/<stage> and runs them. A missing or empty suite, a failure, an error, an import
error, a skip, an expected failure or an incomplete run is FAIL, never PASS. Docker is required.
"""
from pathlib import Path
import argparse
import sys
import time
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
STAGES = {'offline': COMPONENT / 'validation/runtime/offline'}


def validate(stage='offline', directory=None, stream=None):
    directory = Path(directory) if directory else STAGES[stage]
    if not directory.is_dir():
        raise ValueError('Missing mapping adapter ' + stage + ' suite: ' + str(directory))
    # A fresh loader confines discovery to this folder.
    suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py')
    count = suite.countTestCases()
    if count == 0:
        raise ValueError('Empty mapping adapter ' + stage + ' suite: ' + str(directory))
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped or result.expectedFailures or result.testsRun != count):
        raise ValueError('Mapping adapter ' + stage + ' gate failed: failures/errors, skips, expected failures or incomplete execution are not PASS')
    print(f'PASS: mapping adapter {stage}: {result.testsRun} tests in {time.monotonic() - started:.1f}s; implemented slice only.')
    return result.testsRun


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', nargs='?', default='offline', choices=sorted(STAGES))
    args = parser.parse_args(argv)
    try:
        validate(args.stage)
    except (ValueError, OSError, ImportError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
