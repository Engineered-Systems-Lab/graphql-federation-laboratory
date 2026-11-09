"""The study test gate: the offline tests of the study, in one command that needs no stack and no API key.

    python -B study/harness/study_gate.py [--require-mcp] [--jobs N]

It runs nine suites, each as its own unittest discovery in its own process, with its own folder as the working directory:
  harness    study/harness    test_*.py          (fake vendor clients; the live MCP-session test is skipped when no interpreter has `mcp`)
  corpus     study/corpus     test_corpus.py     (the freeze reproduces from the released files; no question leaks)
  corpus2    study/corpus2    test_corpus2.py    (corpus 2's derivation, keys and package checks)
  mcp        study/mcp        test_mcp_offline.py (the offline tests of the MCP servers; they need the pinned `mcp` package)
  analysis   study/analysis   test_*.py          (study 1's analysis on a synthetic fixture and the committed evidence; statsmodels, scipy)
  analysis2  study/analysis2  test_*.py          (study 2's analysis; statsmodels and scipy)
  launch     study/launch     test_*.py          (the launch kit and the run watcher, on fake machines)
  preflight  study/preflight  test_*.py          (the preflight checks and the totals check, on fakes)
  blind      study/blind      test_*.py          (the blind workers' packages and their leak checks; the request relay on the fakes)

HOW THE SUITES RUN. The suites that start a server or bind a port (SERVER_LANE: harness, mcp and blind) run one after another in a lane
of their own, in the order of SUITES. The six others share nothing and run side by side, at most N at a time (`--jobs N`, default 4),
in the order of SUITES, at the same time as the server lane. `--jobs 1` runs all nine one after another, in the order of SUITES, with no
lane. A line is printed when a suite starts (`== <name>: ...`) and when it ends (`<name>: OK in 48 s`, or FAILED with its exit code);
each suite's whole output (stdout and stderr) is kept apart and printed as one block just before its end line, never interleaved with
another suite's. Each suite writes its output in UTF-8 (PYTHONIOENCODING=utf-8 in its environment), and the gate prints it through its
own text stream, so the console shows it in its own encoding. An interrupt (Ctrl+C) stops the gate: no lane starts another suite, every
suite still running is ended (on Windows with the processes it started) and waited for, and the interrupt is raised again. The summary line, `--require-mcp` and the exit codes are
the same with any N.

CONVENTION: a study area contributes tests by putting `test_*.py` files directly in its folder and listing the folder in SUITES below. A
new test file in a listed folder is picked up with no other change. A suite that starts a server or binds a port, even one the system
assigns, is also listed in SERVER_LANE. The MCP offline suite needs the `mcp` package, which the interpreter of the governance runtime
does not have: it runs under the interpreter named by the machine-local variable STUDY_MCP_PYTHON (the virtual environment of
study/mcp/requirements.txt). The analysis suites need statsmodels and scipy (study/analysis/requirements.txt), installed into that same
environment, and run under it the same way. When neither the running interpreter nor that variable offers what a suite needs, the suite
is reported as NOT RUN, loudly, and the gate still passes unless `--require-mcp` is given, which then fails on any suite that was not
run. The gate never starts a stack and never calls an API.
"""
import argparse
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
SUITES = [
    ('harness', 'harness', 'test_*.py', 'prefer'),
    ('corpus', 'corpus', 'test_corpus.py', 'no'),
    ('corpus2', 'corpus2', 'test_corpus2.py', 'no'),
    ('mcp', 'mcp', 'test_mcp_offline.py', 'require'),
    ('analysis', 'analysis', 'test_*.py', 'stats'),
    ('analysis2', 'analysis2', 'test_*.py', 'stats'),
    ('launch', 'launch', 'test_*.py', 'no'),
    ('preflight', 'preflight', 'test_*.py', 'no'),
    ('blind', 'blind', 'test_*.py', 'prefer'),
]
SERVER_LANE = ('harness', 'mcp', 'blind')
DEFAULT_JOBS = 4
WINDOWS = os.name == 'nt'
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


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError('must be 1 or more')
    return value


def write_text(text):
    """Print through the gate's own text stream; a character its encoding cannot show is written as an escape, never an error."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'utf-8'
        sys.stdout.write(text.encode(encoding, 'backslashreplace').decode(encoding))


class Gate:
    """The suites in flight. One lock covers everything printed, so a start line, an end line and a suite's block never mix, and the
    set of live suite processes; `stop` is read by every lane before it starts a suite."""

    def __init__(self, env, interpreters):
        self.env, self.interpreters = env, interpreters
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.live = set()
        self.passed = {}

    def line(self, text):
        with self.lock:
            print(text, flush=True)

    def run_suite(self, suite):
        """Run one suite and record whether it passed. Its output is captured whole and printed as one block when it ends. A suite
        ended by `cancel` prints no block and records nothing."""
        name, folder, pattern, mode = suite
        # The stop check, the start and the registration of the process are one step under the lock that `cancel` takes, so no suite
        # starts after a cancel and every started process is in `live` before `cancel` reads it.
        with self.lock:
            if self.stop.is_set():
                return
            print('== %s: %s in study/%s' % (name, pattern, folder), flush=True)
            start = time.monotonic()
            try:
                process = subprocess.Popen([self.interpreters[mode], '-B', '-m', 'unittest', 'discover', '-s', str(STUDY / folder), '-p',
                                            pattern, '-v'], env=self.env, cwd=str(STUDY / folder), stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
            except OSError as error:  # the interpreter could not be started: a failure of the suite, never a silent gap
                process, output, code = None, 'the suite could not be started: %s\n' % error, None
            else:
                self.live.add(process)
        if process is not None:
            # the gate's text stream writes its own line ends, so a Windows suite's CRLF becomes LF first (else CR CR LF)
            output = process.communicate()[0].decode('utf-8', 'replace').replace('\r\n', '\n')
            code = process.returncode
            with self.lock:
                self.live.discard(process)
        if self.stop.is_set():
            return
        seconds = time.monotonic() - start
        result = 'OK' if code == 0 else 'FAILED (%s)' % ('not started' if code is None else 'exit %d' % code)
        with self.lock:
            if output:
                write_text(output if output.endswith('\n') else output + '\n')
            print('%s: %s in %d s' % (name, result, round(seconds)), flush=True)
            self.passed[name] = code == 0

    def lane(self, work):
        """Take suites from `work` one at a time until it is empty or the gate is stopped."""
        while not self.stop.is_set():
            try:
                suite = work.get_nowait()
            except queue.Empty:
                return
            self.run_suite(suite)

    def cancel(self):
        """Stop every lane and end every suite still running; the lanes then wait for their processes."""
        with self.lock:
            self.stop.set()
            processes = list(self.live)
        for process in processes:
            end_process(process)


def end_process(process):
    """End a suite's process and, on Windows, every process it started (harness starts an MCP server), then the process itself. Each
    step's error is ignored, so the direct kill still runs when taskkill cannot, and `cancel` goes on to the next suite."""
    if WINDOWS:
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def work_of(suites):
    work = queue.Queue()
    for suite in suites:
        work.put(suite)
    return work


def wait_for(threads):
    """Wait for the lanes in short steps, so that an interrupt reaches the main thread at once."""
    for thread in threads:
        while thread.is_alive():
            thread.join(0.2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--require-mcp', action='store_true', help='fail instead of reporting NOT RUN when a suite has no interpreter')
    parser.add_argument('--jobs', type=positive_int, default=DEFAULT_JOBS, metavar='N',
                        help='how many suites that start no server run at once (default %d); 1 runs every suite one after another'
                             % DEFAULT_JOBS)
    args = parser.parse_args(argv)
    env = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'STUDY_MCP_STACK')}
    env['PYTHONIOENCODING'] = 'utf-8'
    interpreters, runnable, not_run = {}, [], []
    for suite in SUITES:
        name, _, _, mode = suite
        if mode not in interpreters:
            interpreters[mode] = interpreter_for(mode)
        if interpreters[mode] is None:
            not_run.append(name)
            print('NOT RUN: %s (%s is not installed in this interpreter or in STUDY_MCP_PYTHON)' % (name, NEEDS[mode]), flush=True)
        else:
            runnable.append(suite)
    gate = Gate(env, interpreters)
    if args.jobs == 1:
        lanes = [work_of(runnable)]
    else:
        free = work_of([s for s in runnable if s[0] not in SERVER_LANE])
        lanes = [work_of([s for s in runnable if s[0] in SERVER_LANE])] + [free] * args.jobs
    threads = [threading.Thread(target=gate.lane, args=(work,), name='study-gate-lane-%d' % i) for i, work in enumerate(lanes)]
    try:  # the lanes start inside the handler, so an interrupt while they start also stops the ones already running
        for thread in threads:
            thread.start()
        wait_for(threads)
    except KeyboardInterrupt:
        gate.cancel()
        for thread in threads:
            if thread.ident is not None:  # a lane that never started has nothing to wait for
                thread.join()
        print('study gate: interrupted; no suite was started after it and every running suite was ended', flush=True)
        raise
    failed = [s[0] for s in runnable if gate.passed.get(s[0]) is not True]  # a suite with no result (a lane that died) counts as failed
    print('study gate: failed=%s not_run=%s' % (failed or 'none', not_run or 'none'))
    if failed or (not_run and args.require_mcp):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
