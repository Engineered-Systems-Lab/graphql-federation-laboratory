"""Windows launcher of the study: reads the two API keys from Credential Manager and starts the harness with them.

    python launcher.py --check                         present or missing, never a value
    python launcher.py --set-credentials [vendor ...]  replace a key (for example after rotation); interactive terminal only
    python launcher.py run -- <runner arguments>       one command runs a whole pilot or study run

The keys reach only the harness child process. The launcher changes no global or user environment variable, no shell profile and no
coding-assistant authentication, takes no key as an argument and writes none to a file or a log. Real runs are started by the lead developer from
his own terminal; a worker never starts a run that spends money.
"""
import argparse
import os
import subprocess
import sys

import credentials
from credentials import CREDENTIALS, CredentialError

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runner.py')


def main(argv=None, store=None, interactive=None, ask=None, out=print, spawn=subprocess.call):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='report present or missing for each credential and exit')
    parser.add_argument('--set-credentials', nargs='*', metavar='VENDOR', help='store or replace the key of each named vendor (all when none is named)')
    parser.add_argument('--vendors', nargs='+', choices=sorted(CREDENTIALS), default=sorted(CREDENTIALS), help='vendors whose keys the run needs')
    parser.add_argument('command', nargs='?', choices=['run'])
    parser.add_argument('runner_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    interactive = credentials.is_interactive() if interactive is None else interactive
    ask = ask or credentials.getpass.getpass
    try:
        store = store or credentials.WindowsCredentialStore()
        if args.check:
            state = credentials.check(store)
            for vendor, present in sorted(state.items()):
                out('%s (%s): %s' % (CREDENTIALS[vendor]['target'], vendor, 'present' if present else 'missing'))
            return 0 if all(state.values()) else 1
        if args.set_credentials is not None:
            vendors = args.set_credentials or sorted(CREDENTIALS)
            unknown = [v for v in vendors if v not in CREDENTIALS]
            if unknown:
                raise CredentialError('Unknown vendor: ' + ', '.join(unknown))
            for vendor in vendors:
                credentials.prompt_and_store(store, vendor, interactive, ask=ask, out=out)
            return 0
        if args.command != 'run':
            parser.error('Say what to do: --check, --set-credentials or run -- <runner arguments>')
        runner_args = args.runner_args[1:] if args.runner_args[:1] == ['--'] else args.runner_args
        entries = credentials.load_for_child(store, args.vendors, interactive, ask=ask, out=out)
    except CredentialError as error:
        out('STOP: ' + str(error))
        return 2
    env = dict(os.environ)
    env.update(entries)
    return spawn([sys.executable, '-B', RUNNER, '--vendors', *args.vendors, *runner_args], env=env)


if __name__ == '__main__':
    sys.exit(main())
