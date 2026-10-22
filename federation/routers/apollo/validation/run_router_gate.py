"""Fail-closed execution of the Apollo router gates.

Stage offline (the default): no container runs the stack. The expected outcomes are re-derived from the released files and compared;
the router configuration, the whole-stack compose file, the Rover image definition, the composition script and the start script are
checked; the stub of the Missions service is run against the released dataset. Docker is used only to validate the compose file.
Stage stack: the whole stack in stub-backend mode (four adapters, the real Assets service with PostgreSQL, the real Personnel v2
service, a stub of the Missions service, the Apollo router) in a uniquely named compose project; the supergraph is composed by the
committed script (Rover needs APOLLO_ELV2_LICENSE=accept, which you set on purpose); the acceptance questions 2 to 6 and the controlled
cases (the router-neutral suite in federation/acceptance), the determinism of the composition and the outages run through the router. Disposable, and removed by the gate.

Discovers the tests under validation/runtime/<stage> and runs them. A missing or empty suite, a failure, an error, an import
error, a skip, an expected failure or an incomplete run is FAIL, never PASS. Docker is required.
"""
from pathlib import Path
import argparse
import sys
import time
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
STAGES = {'offline': COMPONENT / 'validation/runtime/offline', 'stack': COMPONENT / 'validation/runtime/stack'}


def validate(stage='offline', directory=None, stream=None):
    directory = Path(directory) if directory else STAGES[stage]
    if not directory.is_dir():
        raise ValueError('Missing Apollo router ' + stage + ' suite: ' + str(directory))
    # A fresh loader confines discovery to this folder.
    suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py')
    count = suite.countTestCases()
    if count == 0:
        raise ValueError('Empty Apollo router ' + stage + ' suite: ' + str(directory))
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped or result.expectedFailures or result.testsRun != count):
        raise ValueError('Apollo router ' + stage + ' gate failed: failures/errors, skips, expected failures or incomplete execution are not PASS')
    print(f'PASS: Apollo router {stage}: {result.testsRun} tests in {time.monotonic() - started:.1f}s; implemented slice only.')
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
