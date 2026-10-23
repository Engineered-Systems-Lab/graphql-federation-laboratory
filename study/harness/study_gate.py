"""The study test gate: the offline tests of the study, in one command that needs no stack and no API key.

    python -B study/harness/study_gate.py [--require-mcp]

It runs, each as its own unittest discovery in its own process:
  harness   study/harness  test_*.py    (fake vendor clients; the one live MCP-client test is skipped when no interpreter has `mcp`)
  corpus    study/corpus   test_corpus.py (the freeze reproduces from the released files; no question leaks)
  mcp       study/mcp      test_mcp_offline.py (the offline tests of the MCP servers; they need the pinned `mcp` package)
  analysis  study/analysis test_*.py    (the analysis scripts on a synthetic fixture and the committed evidence; they need statsmodels and scipy)

CONVENTION: a study area contributes tests by putting `test_*.py` files directly in its folder and listing the folder in SUITES below. A
new test file in a listed folder is picked up with no other change. The MCP offline suite needs the `mcp` package, which the interpreter of
the governance runtime does not have: it runs under the interpreter named by the machine-local variable STUDY_MCP_PYTHON (the virtual
environment of study/mcp/requirements.txt). The analysis suite needs statsmodels and scipy (study/analysis/requirements.txt), installed
into that same environment, and runs under it the same way. When neither the running interpreter nor that variable offers what a suite
needs, the suite is reported as NOT RUN, loudly, and the gate still passes unless `--require-mcp` is given, which then fails on any suite
that was not run. The gate never starts a stack and never calls an API.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
SUITES = [
    ('harness', 'harness', 'test_*.py', 'prefer'),
    ('corpus', 'corpus', 'test_corpus.py', 'no'),
    ('mcp', 'mcp', 'test_mcp_offline.py', 'require'),
    ('analysis', 'analysis', 'test_*.py', 'stats'),
]
PROBES = {'mcp': 'from mcp import Client', 'stats': 'import statsmodels, scipy'}
NEEDS = {'require': 'the mcp package', 'stats': 'statsmodels and scipy'}


def can_import(python, probe):
    """True when `python` runs the import `probe`. Checked in a neutral folder: a folder called mcp (study/mcp) is not the package."""
    done = subprocess.run([python, '-B', '-c', probe], capture_output=True, cwd=str(Path.home()))
    return done.returncode == 0


def can_import_mcp(python):
    return can_import(python, PROBES['mcp'])


def can_import_stats(python):
    return can_import(python, PROBES['stats'])


def interpreter_for(mode):
    """The interpreter of a suite: 'no' needs nothing, 'prefer' uses one with `mcp` when there is one, 'require' has none otherwise;
    'stats' is like 'require' for statsmodels and scipy."""
    if mode == 'no':
        return sys.executable
    has = can_import_stats if mode == 'stats' else can_import_mcp
    if has(sys.executable):
        return sys.executable
    candidate = os.environ.get('STUDY_MCP_PYTHON')
    if candidate and Path(candidate).exists() and has(candidate):
        return candidate
    return sys.executable if mode == 'prefer' else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--require-mcp', action='store_true', help='fail instead of reporting NOT RUN when a suite has no interpreter')
    args = parser.parse_args(argv)
    env = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'STUDY_MCP_STACK')}
    failed, not_run = [], []
    for name, folder, pattern, mode in SUITES:
        python = interpreter_for(mode)
        if python is None:
            not_run.append(name)
            print('NOT RUN: %s (%s is not installed in this interpreter or in STUDY_MCP_PYTHON)' % (name, NEEDS[mode]), flush=True)
            continue
        print('== %s: %s in study/%s' % (name, pattern, folder), flush=True)
        done = subprocess.run([python, '-B', '-m', 'unittest', 'discover', '-s', str(STUDY / folder), '-p', pattern, '-v'], env=env,
                              cwd=str(STUDY / folder))
        if done.returncode != 0:
            failed.append(name)
    print('study gate: failed=%s not_run=%s' % (failed or 'none', not_run or 'none'))
    if failed or (not_run and args.require_mcp):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
