"""Fail-closed execution of the Missions adapter gates.

Stage offline (the default): the committed Dockerfile builds the adapter (its build stage runs the offline unit and
integration tests against a stub of the Missions service that serves the real contract fixtures and the released dataset, so no
JDK or Maven is needed on the machine), and the image, the compose file and the start script are checked and run on an ephemeral
loopback port.
Stage service: the adapter container against the REAL Missions service on Oracle 18c. It starts the reviewed Oracle container
when it is stopped and stops it again afterwards, so it is never part of an automatic checkpoint; run it deliberately.

Discovers the tests under validation/runtime/<stage> and runs them. A missing or empty suite, a failure, an error, an import
error, a skip, an expected failure or an incomplete run is FAIL, never PASS. Docker is required.
"""
from pathlib import Path
import argparse
import sys
import time
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
STAGES = {'offline': COMPONENT / 'validation/runtime/offline', 'service': COMPONENT / 'validation/runtime/service'}


def validate(stage='offline', directory=None, stream=None):
    directory = Path(directory) if directory else STAGES[stage]
    if not directory.is_dir():
        raise ValueError('Missing Missions adapter ' + stage + ' suite: ' + str(directory))
    # A fresh loader confines discovery to this folder.
    suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py')
    count = suite.countTestCases()
    if count == 0:
        raise ValueError('Empty Missions adapter ' + stage + ' suite: ' + str(directory))
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped or result.expectedFailures or result.testsRun != count):
        raise ValueError('Missions adapter ' + stage + ' gate failed: failures/errors, skips, expected failures or incomplete execution are not PASS')
    print(f'PASS: Missions adapter {stage}: {result.testsRun} tests in {time.monotonic() - started:.1f}s; implemented slice only.')
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
