"""Make the study environment (the interpreter STUDY_MCP_PYTHON names) from the committed lock files, at a path outside the repository.

    python -B study/mcp/setup_env.py <new folder outside the repository> [--python <base Python 3.13 or later>] [--dry-run]

It creates a virtual environment with `<base python> -m venv`, installs into it, with `pip install --no-deps`, exactly the packages of
the lock files below, and then checks with `pip freeze` that the environment holds those packages and nothing else. These are the
packages the MCP offline tests and the analysis tests ran with:

- study/mcp/requirements-lock.txt (the pinned `mcp` package and everything it needs);
- study/analysis/requirements.txt and study/analysis/requirements-lock.txt (statsmodels, scipy and what they need), which the
  analysis and analysis2 suites of the study gate need.

The harness's vendor SDKs (study/harness/requirements.txt) are not part of it, as in the environment made by hand before this script.

At the end it prints the lines that set STUDY_MCP_PYTHON to the new interpreter, for PowerShell and for Git Bash. It never sets a
variable itself, user or session, and never touches an existing folder: a path that exists, or lies inside the repository, is refused.
--dry-run prints the commands and runs nothing. pip needs the package index (network) to install. Standard library only.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCK_FILES = (HERE / 'requirements-lock.txt', ROOT / 'study' / 'analysis' / 'requirements.txt',
              ROOT / 'study' / 'analysis' / 'requirements-lock.txt')


class Refused(Exception):
    pass


def pins(paths=LOCK_FILES):
    """The exact `name==version` pins of the lock files, as pip freeze writes them (names folded to lower case)."""
    out = {}
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if '==' not in line:
                raise Refused('%s holds a line that is not an exact pin: %s' % (path.name, line))
            name, version = line.split('==', 1)
            name = name.strip().lower().replace('_', '-')
            if out.get(name, version.strip()) != version.strip():
                raise Refused('the lock files pin %s twice with different versions' % name)
            out[name] = version.strip()
    return out


def frozen(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if '==' in line:
            name, version = line.split('==', 1)
            out[name.strip().lower().replace('_', '-')] = version.strip()
    return out


def interpreter(folder):
    return folder / ('Scripts' if os.name == 'nt' else 'bin') / ('python.exe' if os.name == 'nt' else 'python')


def plan(folder, base):
    python = interpreter(folder)
    install = [str(python), '-m', 'pip', 'install', '--no-deps', '--disable-pip-version-check']
    for path in LOCK_FILES:
        install += ['-r', str(path)]
    return [[base, '-m', 'venv', str(folder)], install], python


def target_folder(path):
    folder = Path(path).resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise Refused('the environment must be outside the repository, not %s' % folder)
    if folder.exists():
        raise Refused('%s exists; give a new folder (an existing environment is never changed)' % folder)
    return folder


def main(argv=None, run=subprocess.run, out=print):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('folder', help='the new folder of the environment, outside the repository')
    parser.add_argument('--python', default=sys.executable, help='the base Python 3.13 or later (default: this one)')
    parser.add_argument('--dry-run', action='store_true', help='print the commands, run nothing')
    args = parser.parse_args(argv)
    try:
        folder = target_folder(args.folder)
        wanted = pins()
        commands, python = plan(folder, args.python)
        for command in commands:
            out('%s: %s' % ('would run' if args.dry_run else 'run', ' '.join(command)))
            if not args.dry_run and run(command).returncode != 0:
                raise Refused('the command failed: %s' % ' '.join(command))
        if not args.dry_run:
            done = run([str(python), '-m', 'pip', 'freeze', '--disable-pip-version-check'], capture_output=True, text=True)
            have = frozen(done.stdout or '')
            if done.returncode != 0 or have != wanted:
                extra = sorted(set(have) - set(wanted))
                missing = sorted(n for n in wanted if have.get(n) != wanted[n])
                raise Refused('the environment differs from the lock files: missing or other version %s, not pinned %s'
                              % (', '.join(missing) or 'none', ', '.join(extra) or 'none'))
            out('the environment holds exactly the %d pinned packages' % len(wanted))
    except Refused as error:
        print('setup_env.py: refused: %s' % error, file=sys.stderr)
        return 1
    out('To use it, set STUDY_MCP_PYTHON yourself (this script sets nothing):')
    out("  PowerShell (for your user): [Environment]::SetEnvironmentVariable('STUDY_MCP_PYTHON', '%s', 'User')" % python)
    out("  Git Bash (this shell only): export STUDY_MCP_PYTHON='%s'" % python)
    return 0


if __name__ == '__main__':
    sys.exit(main())
