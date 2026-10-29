"""The run protocol of the Abstraction ladder study: one stack run per scenario, the models nested inside it, results saved as they finish.

Per scenario (the whole plot): start the stack and the MCP server, measure the cold start and the cold first request, run the declared
warm-up, then run every task of the set with every model against that one warm stack (the sub-plots), sequentially. The order of the tasks
and trials is shuffled from a recorded seed; the model order is interleaved per task and counterbalanced across the units. Every sample
carries its phase (cold, warm-up, measurement). After each run its result is written at once; a budget stop ends the study cleanly with
everything completed kept, and a resume runs only the missing or incomplete runs.

Before the warm-up and the first paid request of each scenario (dry runs included), the running stack is observed read-only and compared
with the scenario's declared provenance (provenance.py); a mismatch, or on resume a drift from the stored observation, refuses the run.

With a `schedule` in the config (study 2) the unit is a block instead of a scenario: the Williams square of schedule.py, then the reference
block. Every block starts its arm's stack, observes its provenance and checks the dataset fingerprint before any paid request, runs its runs
in their order, queues a run that ended on a vendor error again once at the end of the block, and tears the stack down. A resume continues
inside the schedule, block by block, and skips every block whose runs are all finished and whose attempt ended.

The void-block rule of the schedule (docs/STUDY-2-DESIGN.md, Exclusions; decisions F2 and F3 of the Job study2_build_followups): every block
start carries the block's `attempt` (1, 2, ...), and every run record carries it as `blockAttempt`. The arm's declared `health` command
probes every backend at the block start, after every restore of a category D task's stopped service (waiting up to the scenario's
`ready_timeout_seconds` for every backend to answer again), every `health_every_runs` runs (default 10) and at the block end. A backend
down, found by the health check or by the provenance observation at the block start, outside the window in which a category D task's own
service is deliberately stopped, is a declared trigger: the attempt is void. The harness records a `void` event (the block, the attempt, the
trigger and its problems), moves the attempt's run folders to runs-void/<block>/<attempt>/, so no void result stays a run's current result,
and stops cleanly with the status `block_void`. The resume repeats the block whole as the next attempt. The void attempt's spend stays in
the vendor ledgers, because it was billed, and is reported apart in bundle.json.

The budget across study runs (decision F1): under a schedule every vendor budget has a `dollar_ceiling` and its `ceiling_basis` (decision D,
or the lead developer's dated raise), and `earlier_study_runs` lists the earlier study-2 runs whose ledgers count against the ceiling. Their
ids, ledger hashes and dollars are recorded in the manifest; a listed run that is missing refuses the start, and a resume with another
ceiling or basis records both in resumes.jsonl.

Records go to LAB_RESULTS_DIR/<study run id>/ : manifest.json (immutable), samples.jsonl, one budget ledger per vendor, runs/<key>/
(transcript.jsonl, result.json and, with the harness tools, results.jsonl), provenance/ (one observation per scenario, one per block, and the
checks), blocks.jsonl, health.jsonl and runs-void/ (with a schedule), scores.jsonl and scores.csv, bundle.json with the checksum. Nothing
written holds an absolute path or a key.
"""
import argparse
import csv
import importlib.util
import itertools
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import harness_tools
import provenance
import schedule
import scoring_contract
from agent import SYSTEM_PROMPT, TERMINAL, AgentRun, Limits
from budget import Budget, Usage, dollars, ledger_dollars
from study_common import (Redactor, append_jsonl, child_environment, read_jsonl, results_dir, sha256_bytes, sha256_file, sha256_json, utc_now,
                          write_json_atomic)
from vendors import MissingCredentialError, build_client

HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = HERE.parent / 'corpus'


# ---------------------------------------------------------------------------------------------------------------- corpus
def load_scoring(corpus_dir):
    spec = importlib.util.spec_from_file_location('study_corpus_scoring', Path(corpus_dir) / 'scoring.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STRATA_FIELDS = ('set', 'size', 'systems')


def _strata(task):
    """The optional fields of a corpus-2 task that the schedule stratifies on: set (core or ambiguity), size and systems."""
    return {name: task[name] for name in STRATA_FIELDS if name in task}


def load_tasks(corpus_dir, task_set):
    """The tasks of `dev` or `scored` as dicts: id, category, question, schema, expected, stoppedService, and set, size and systems when the
    corpus gives them. Task text is read here at run time and is never copied anywhere else."""
    corpus_dir = Path(corpus_dir)
    if task_set == 'dev':
        data = json.loads((corpus_dir / 'dev.json').read_text(encoding='utf-8'))
        return [{'id': t['id'], 'category': t['category'], 'question': t['question'], 'schema': t['schema'], 'expected': t['expected'],
                 'stoppedService': t.get('stoppedService'), **_strata(t)} for t in data['tasks']]
    if task_set == 'scored':
        tasks = json.loads((corpus_dir / 'tasks.json').read_text(encoding='utf-8'))['tasks']
        schemas = json.loads((corpus_dir / 'schemas.json').read_text(encoding='utf-8'))['schemas']
        expected = json.loads((corpus_dir / 'expected.json').read_text(encoding='utf-8'))['expected']
        return [{'id': t['id'], 'category': t['category'], 'question': t['question'], 'schema': schemas[t['id']], 'expected': expected[t['id']],
                 'stoppedService': t.get('stoppedService'), **_strata(t)} for t in tasks]
    raise ValueError('task_set must be dev or scored')


# ---------------------------------------------------------------------------------------------------------------- the dataset fingerprint
class FingerprintRefused(RuntimeError):
    """A block does not run: the dataset fingerprint could not be read, or differs from the study's or the session's first one."""

    def __init__(self, block, problems):
        self.block, self.problems = block, list(problems)
        super().__init__('Dataset fingerprint refused block %s before any paid request:\n- %s' % (block, '\n- '.join(self.problems)))


def validate_fingerprint_command(command):
    if not (isinstance(command, dict) and isinstance(command.get('argv'), list) and command['argv']
            and all(isinstance(a, str) and a for a in command['argv'])):
        raise ValueError('dataset_fingerprint must be a command {argv, cwd?, env?} with a non-empty argv: the schedule checks the dataset '
                         'fingerprint at every block start')
    unknown = sorted(set(command) - {'argv', 'cwd', 'env'})
    if unknown:
        raise ValueError('dataset_fingerprint has unknown keys: %s' % ', '.join(unknown))


def run_fingerprint_command(command, timeout=600):
    """Run the declared fingerprint command (without the API keys in its environment) and return what it prints."""
    done = subprocess.run(command['argv'], cwd=command.get('cwd'), env=child_environment(extra=command.get('env')), capture_output=True,
                          text=True, encoding='utf-8', timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError('the fingerprint command exited with %d: %s' % (done.returncode, provenance.redact_value(
            (done.stderr or done.stdout or '').strip()[-300:])))
    return done.stdout


def parse_fingerprint(text):
    """The command prints one JSON object with two non-empty texts: `fingerprint` (the dataset) and `session` (one continuous run of the
    database, for example its instance start time)."""
    try:
        value = json.loads((text or '').strip())
    except ValueError:
        raise ValueError('the fingerprint command did not print a JSON object')
    if not isinstance(value, dict):
        raise ValueError('the fingerprint command did not print a JSON object')
    for name in ('fingerprint', 'session'):
        if not (isinstance(value.get(name), str) and value[name].strip()):
            raise ValueError('the fingerprint command printed no %s text' % name)
    return {'fingerprint': value['fingerprint'], 'session': value['session']}


# ---------------------------------------------------------------------------------------------------------------- the void-block rule
HEALTH_EVERY_RUNS = 10
HEALTH_POINTS = ('start', 'periodic', 'restore', 'end')
VOID_TRIGGERS = {
    'provenance': 'the provenance observation at the block start finds a declared backend down (no container, or not running)',
    'health': 'the health check finds a backend down, or cannot be read, at the block start, every health_every_runs runs or at the block end',
    'restore': 'after a category D task, the restored service, the MCP server or any backend does not answer again within the scenario\'s '
               'ready_timeout_seconds',
}
VOID_FOLDER = 'runs-void'


class BlockVoid(RuntimeError):
    """A declared void trigger fired: the block's attempt is void, its runs are moved aside and the study stops with `block_void`."""

    def __init__(self, block, attempt, trigger, problems):
        self.block, self.attempt, self.trigger, self.problems = block, attempt, trigger, list(problems)
        super().__init__('Block %s, attempt %d, is void (trigger %s); the resume repeats it whole as attempt %d:\n- %s'
                         % (block, attempt, trigger, attempt + 1, '\n- '.join(self.problems)))


class BackendDown(RuntimeError):
    """The provenance observation at a block start finds declared backends down, and nothing else wrong."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('; '.join(self.problems))


def validate_command(command, what):
    """A declared command {argv, cwd?, env?} with a non-empty argv."""
    if not (isinstance(command, dict) and isinstance(command.get('argv'), list) and command['argv']
            and all(isinstance(a, str) and a for a in command['argv'])):
        raise ValueError('%s must be a command {argv, cwd?, env?} with a non-empty argv' % what)
    unknown = sorted(set(command) - {'argv', 'cwd', 'env'})
    if unknown:
        raise ValueError('%s has unknown keys: %s' % (what, ', '.join(unknown)))


def run_health_command(command, timeout=120):
    """Run a scenario's declared health command (without the API keys in its environment) and return what it prints."""
    done = subprocess.run(command['argv'], cwd=command.get('cwd'), env=child_environment(extra=command.get('env')), capture_output=True,
                          text=True, encoding='utf-8', timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError('the health command exited with %d: %s' % (done.returncode, provenance.redact_value(
            (done.stderr or done.stdout or '').strip()[-300:])))
    return done.stdout


def parse_health(text, backends):
    """The health command prints one JSON object {"backends": {<name>: {"up": true|false, ...}, ...}}, one entry per backend of the arm.
    Returns {name: {'up': bool, 'detail': text}} for the declared `backends`; a declared backend the output does not name is a ValueError."""
    try:
        value = json.loads((text or '').strip())
    except ValueError:
        raise ValueError('the health command did not print a JSON object')
    if not (isinstance(value, dict) and isinstance(value.get('backends'), dict)):
        raise ValueError('the health command printed no "backends" object')
    out = {}
    for name in backends:
        entry = value['backends'].get(name)
        if not (isinstance(entry, dict) and isinstance(entry.get('up'), bool)):
            raise ValueError('the health command printed no up true or false for the backend %s' % name)
        out[name] = {'up': entry['up'], 'detail': str(entry.get('detail') or '')[:300]}
    return out


def validate_budgets(config, vendors):
    """Under a schedule every vendor's budget names its dollar ceiling and the basis of that ceiling (decision D, or the lead developer's
    dated raise), and `earlier_study_runs` is a list of distinct run ids."""
    for vendor in vendors:
        setting = (config.get('budgets') or {}).get(vendor)
        if not isinstance(setting, dict):
            raise ValueError('budgets.%s is missing' % vendor)
        ceiling = setting.get('dollar_ceiling')
        if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)) or ceiling <= 0:
            raise ValueError('budgets.%s.dollar_ceiling must be a positive number: the ceiling of decision D is for all of study 2' % vendor)
        basis = setting.get('ceiling_basis')
        if not (isinstance(basis, str) and basis.strip()):
            raise ValueError('budgets.%s.ceiling_basis must say what the ceiling rests on (decision D, or the lead developer\'s dated raise)'
                             % vendor)
    earlier = config.get('earlier_study_runs', [])
    if not (isinstance(earlier, list) and all(isinstance(r, str) and r.strip() for r in earlier) and len(set(earlier)) == len(earlier)):
        raise ValueError('earlier_study_runs must be a list of distinct study run ids')


def validate_health_every(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('health_every_runs must be a whole number of runs, 1 or more')


class BudgetCarryRefused(RuntimeError):
    """The study does not start: an earlier study run listed in earlier_study_runs is missing, cannot be priced, or changed."""


# ---------------------------------------------------------------------------------------------------------------- the plan
def build_plan(config, tasks):
    """The whole study as data: scenarios in order; per scenario the units (task, trial) shuffled from the seed, each with its model order.

    Model order is counterbalanced: the permutations of the models are cycled from a seeded random start, so every model stands in every
    position equally often (within one permutation cycle), and it is interleaved per unit, never one model's tasks in a block."""
    seed = config['seed']
    models = list(config['models'])
    perms = list(itertools.permutations(models))
    plan = []
    for scenario in config['scenario_order']:
        rng = random.Random('%s/%s' % (seed, scenario))
        units = [(t['id'], trial) for t in tasks for trial in range(1, config['trials'] + 1)]
        rng.shuffle(units)
        offset = rng.randrange(len(perms))
        plan.append({'scenario': scenario, 'units': [{'task': task, 'trial': trial, 'models': list(perms[(offset + i) % len(perms)])}
                                                     for i, (task, trial) in enumerate(units)]})
    return plan


def run_key(scenario, task, model, trial):
    return '%s__%s__%s__t%d' % (scenario, task, model, trial)


# ---------------------------------------------------------------------------------------------------------------- the stack
class CommandStack:
    """Starts and stops a scenario's stack through the commands of the machine-local config. Subprocesses get an environment without the
    API keys. `stack` entries: {'start': [command...], 'teardown': [...], 'stop_service': {name: [command...]}, 'start_service': {...}};
    a command is {'argv': [...], 'cwd': optional, 'env': optional, 'background': optional}."""

    def __init__(self, scenario_config, session_factory, clock=time.monotonic, sleep=time.sleep):
        self.config, self.session_factory, self.clock, self.sleep = scenario_config, session_factory, clock, sleep
        self.background = []

    def _run(self, commands):
        for command in commands:
            env = child_environment(extra=command.get('env'))
            if command.get('background'):
                self.background.append(subprocess.Popen(command['argv'], cwd=command.get('cwd'), env=env,
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            else:
                done = subprocess.run(command['argv'], cwd=command.get('cwd'), env=env, capture_output=True, text=True)
                if done.returncode != 0:
                    raise RuntimeError('Stack command failed (%s): %s' % (command['argv'][0], (done.stderr or done.stdout)[-300:]))

    def start(self):
        self._run(self.config.get('start', []))

    def wait_ready(self, run_id, timeout):
        deadline = self.clock() + timeout
        while True:
            try:
                with self.session_factory(run_id) as session:
                    session.tools()
                return
            except Exception:
                if self.clock() > deadline:
                    raise RuntimeError('The stack did not become ready in %s seconds' % timeout)
                self.sleep(2)

    def stop_service(self, name):
        self._run(self.config.get('stop_service', {}).get(name, []))

    def start_service(self, name):
        self._run(self.config.get('start_service', {}).get(name, []))

    def teardown(self):
        for proc in self.background:
            proc.terminate()
        for proc in self.background:
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.background = []
        self._run(self.config.get('teardown', []))


# ---------------------------------------------------------------------------------------------------------------- facts
def machine_facts():
    facts = {'platform': platform.platform(), 'machine': platform.machine(), 'processor': platform.processor(), 'cpuCount': os.cpu_count(),
             'python': platform.python_version()}
    try:
        if sys.platform == 'win32':
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            facts['totalMemoryBytes'] = status.ullTotalPhys
        elif os.path.exists('/proc/meminfo'):
            facts['totalMemoryBytes'] = int(open('/proc/meminfo').readline().split()[1]) * 1024
    except Exception:
        facts['totalMemoryBytes'] = None
    return facts


def sdk_versions():
    from importlib import metadata
    out = {}
    for name in ('anthropic', 'openai', 'mcp'):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def run_fact_commands(commands):
    """{label: output} of the machine-local `facts_commands` (image digests, docker version, ...). Output only, never the command's paths."""
    out = {}
    for label, argv in (commands or {}).items():
        try:
            done = subprocess.run(argv, capture_output=True, text=True, env=child_environment(), timeout=60)
            out[label] = (done.stdout or done.stderr).strip()[:4000]
        except Exception as error:
            out[label] = 'unavailable: ' + type(error).__name__
    return out


def git_commit(repo_dir):
    """{'commit', 'treeDirty'} of the checkout the harness code lives in (or of the config's `repo_dir`); the folder itself is never recorded."""
    where = str(repo_dir or HERE)
    try:
        commit = subprocess.run(['git', '-C', where, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=30).stdout.strip() or None
        dirty = bool(subprocess.run(['git', '-C', where, 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True,
                                    timeout=30).stdout.strip())
        return {'commit': commit, 'treeDirty': dirty}
    except Exception:
        return {'commit': None, 'treeDirty': None}


# ---------------------------------------------------------------------------------------------------------------- the study
class Study:
    def __init__(self, config, models_config, prices, study_run_id, root=None, corpus_dir=DEFAULT_CORPUS, client_factory=None,
                 session_factory=None, stack_factory=None, clock=time.monotonic, sleep=time.sleep, redactor=None, repo_dir=None, docker=None,
                 hasher=provenance.hash_path, fingerprint_runner=run_fingerprint_command, health_runner=run_health_command):
        self.config, self.models_config, self.prices = config, models_config, prices
        self.schedule = config.get('schedule')
        if self.schedule is not None:
            schedule.validate(self.schedule, config['scenarios'], config['models'])
            validate_fingerprint_command(config.get('dataset_fingerprint'))
            self.scenarios = schedule.scenarios_of(self.schedule)
            for scenario in self.scenarios:
                validate_command(config['scenarios'][scenario].get('health'),
                                 'scenarios.%s.health (the schedule checks every backend of the arm by it)' % scenario)
            self.health_every = config.get('health_every_runs', HEALTH_EVERY_RUNS)
            validate_health_every(self.health_every)
            validate_budgets(config, sorted({models_config['models'][m]['vendor'] for m in config['models']}))
            if study_run_id in config.get('earlier_study_runs', []):
                raise ValueError('earlier_study_runs lists this study run itself (%s)' % study_run_id)
        else:
            self.scenarios = list(config['scenario_order'])
        for scenario in self.scenarios:
            provenance.validate(scenario, config['scenarios'][scenario].get('provenance'))
        self.tool_names = config.get('harness_tools', [])
        harness_tools.validate(self.tool_names)
        self.fingerprint_runner = fingerprint_runner
        self.health_runner = health_runner
        self.carry = None  # the earlier study runs' spend, read at the start (schedule only)
        self.void = None  # the BlockVoid that stopped this run, if one did
        self.docker = docker or provenance.DockerCli()
        self.hasher = hasher
        self.study_run_id = study_run_id
        self.dir = Path(root or results_dir()) / study_run_id
        self.corpus_dir = Path(corpus_dir)
        self.client_factory = client_factory or (lambda model: build_client(model, models_config))
        self.session_factory = session_factory
        self.stack_factory = stack_factory or (lambda scenario: CommandStack(config['scenarios'][scenario]['stack'],
                                                                              lambda run_id: self.session_factory(scenario, run_id)))
        self.clock, self.sleep = clock, sleep
        self.redactor = redactor or Redactor.from_env()
        self.repo_dir = repo_dir
        self.limits = Limits(**config.get('limits', {}))
        self.scoring = load_scoring(self.corpus_dir)
        self.contract = scoring_contract.Contract(self.scoring, self.corpus_dir / 'scoring.py')
        self.tasks = load_tasks(self.corpus_dir, config['task_set'])
        self.by_id = {t['id']: t for t in self.tasks}
        self.plan = schedule.build(config, self.tasks) if self.schedule is not None else build_plan(config, self.tasks)
        vendors = [models_config['models'][m]['vendor'] for m in config['models']]
        if len(set(vendors)) != len(vendors):
            raise ValueError('The budget is per vendor and the price entry per model: this round has one model per vendor')
        self.budgets = {}
        self.clients = {}

    # ---------------------------------------------------------------- identity of the plan
    def plan_identity(self):
        """What a resume must find unchanged. A config without a schedule, harness tools or a version-2 scorer gives exactly the identity of
        the study-1 harness, so its plan hash is unchanged."""
        guides = {s: (sha256_file(self._guide_path(s)) if self._guide_path(s) else None) for s in self.scenarios}
        identity = {'plan': self.plan, 'models': self.models_config['models'], 'limits': self.limits.as_dict(), 'systemPrompt': SYSTEM_PROMPT,
                    'taskSet': self.config['task_set'], 'seed': self.config['seed'], 'guides': guides,
                    'corpusFreeze': sha256_file(self.corpus_dir / 'corpus-manifest.json'), 'pricesDated': self.prices['dated']}
        if self.schedule is None:
            identity['trials'] = self.config['trials']
        else:
            identity['datasetFingerprint'] = self.fingerprint_declaration()
            identity['voidRule'] = self.void_rule_identity()
            identity['earlierStudyRuns'] = list(self.config.get('earlier_study_runs', []))
        if self.tool_names:
            identity['harnessTools'] = harness_tools.describe(self.tool_names)
        if self.contract.version != 1:
            identity['scoringContract'] = self.contract.version
        return identity

    def fingerprint_declaration(self):
        return provenance.redact_command(self.config['dataset_fingerprint'])

    def void_rule_identity(self):
        """The part of the void-block rule a resume must find unchanged: the health interval (fixed for the study run, decision F3) and
        every arm's health command."""
        return {'healthEveryRuns': self.health_every,
                'health': {s: provenance.redact_command(self.config['scenarios'][s]['health']) for s in self.scenarios}}

    def _guide_path(self, scenario):
        guide = self.config['scenarios'][scenario].get('guide_file')
        return Path(guide) if guide else None

    def manifest(self):
        identity = self.plan_identity()
        hashed = {label: sha256_file(path) for label, path in (self.config.get('hash_files') or {}).items()}
        harness_files = {p.name: sha256_file(p) for p in sorted(HERE.glob('*.py')) if not p.name.startswith('test_')}
        manifest = {
            'studyRunId': self.study_run_id, 'createdAt': utc_now(), 'planHash': sha256_json(identity), 'identity': identity,
            **git_commit(self.repo_dir or self.config.get('repo_dir')), 'sdkVersions': sdk_versions(), 'harnessFiles': harness_files,
            'models': {m: {**self.models_config['models'][m], 'priceEntry': self.prices['models'][m]} for m in self.config['models']},
            'pricesTableDate': self.prices['dated'], 'limits': self.limits.as_dict(),
            'tokenBudgets': {v: b for v, b in self.config['budgets'].items()}, 'telemetry': self.config.get('telemetry'),
            'declaredSettings': self.config.get('declared_settings'), 'datasetHashes': hashed,
            'machine': machine_facts(), 'stackFacts': run_fact_commands(self.config.get('facts_commands')),
            'stackRunsPerScenario': 1, 'resultsRootSetting': 'LAB_RESULTS_DIR',
            'provenance': {'schema': provenance.SCHEMA, 'intended': self.intended_provenance(),
                           'observationCommands': provenance.OBSERVATION_COMMANDS},
            'scoringContract': self.contract.describe(),
        }
        if self.schedule is not None:
            del manifest['stackRunsPerScenario']
            manifest.update({'schedule': self.plan, 'stackRunsPerBlock': 1, 'vendorErrorRequeues': 1,
                             'datasetFingerprint': {'command': self.fingerprint_declaration(),
                                                    'rule': "checked at every block start; it must equal the study's first fingerprint "
                                                            "and its session's first fingerprint"},
                             'voidRule': {**self.void_rule_identity(), 'healthPoints': list(HEALTH_POINTS), 'triggers': dict(VOID_TRIGGERS),
                                          'excludedWindow': "a category D task's own stopped service, from its stop until its restore",
                                          'voidRunsFolder': VOID_FOLDER + '/<block>/<attempt>/',
                                          'onVoid': 'stop with status block_void; the resume repeats the block whole as the next attempt',
                                          'spend': 'the void attempt stays in the vendor ledgers and is reported apart in bundle.json '
                                                   '(voidAttempts)'},
                             'budgetCarry': self.carry})
        if self.tool_names:
            manifest['harnessTools'] = harness_tools.describe(self.tool_names)
        return manifest

    def intended_provenance(self):
        return {s: provenance.intended(self.config['scenarios'][s]['provenance']) for s in self.scenarios}

    # ---------------------------------------------------------------- provenance
    def check_provenance(self, scenario, block=None):
        """Observe the running stack of `scenario` and refuse it unless it matches the declaration and, on resume, the stored observation.
        The first matching observation is kept as provenance/<scenario>.json; every later check is a line of provenance/checks.jsonl.
        With a `block` id (the schedule) every block start is checked and recorded, and its matching observation is kept as
        provenance/<block>.json; a block of an arm is compared with the arm's first stored observation too."""
        sconfig = self.config['scenarios'][scenario]
        folder = self.dir / 'provenance'
        checks = folder / 'checks.jsonl'
        where = {'scenario': scenario, **({'block': block} if block else {})}
        label = '%s, block %s' % (scenario, block) if block else scenario
        try:
            observation = self.redactor.deep(provenance.observe(scenario, sconfig, self.docker, self.hasher))
        except Exception as error:
            problems = self.redactor.deep(['the stack could not be observed: %s: %s' % (type(error).__name__, provenance.redact_value(error))])
            append_jsonl(checks, {'at': utc_now(), **where, 'result': 'unobserved', 'problems': problems})
            raise provenance.ProvenanceRefused(label, 'unobserved', problems)
        problems = self.redactor.deep(provenance.compare(sconfig['provenance'], observation))
        if block and problems:
            down = self.redactor.deep(provenance.down_backends(sconfig['provenance'], observation))
            if all(p in down for p in problems):  # only backends down: a void trigger of the schedule, not a wrong backend
                append_jsonl(checks, {'at': observation['observedAt'], **where, 'result': 'down', 'fingerprint': observation['fingerprint'],
                                      'problems': problems, 'changes': []})
                raise BackendDown(problems)
        stored_path = folder / ('%s.json' % scenario)
        stored = json.loads(stored_path.read_text(encoding='utf-8')) if stored_path.exists() else None
        changes = self.redactor.deep(provenance.drift(stored['stable'], observation['stable'])) if stored else []
        if problems or stored or block:
            result = 'mismatch' if problems else ('drift' if changes else 'match')
            append_jsonl(checks, {'at': observation['observedAt'], **where, 'result': result,
                                  'fingerprint': observation['fingerprint'], 'problems': problems, 'changes': changes})
        if problems:
            raise provenance.ProvenanceRefused(label, 'mismatch', problems)
        if changes:
            raise provenance.ProvenanceRefused(label, 'drift since the stored observation', changes)
        if not stored:
            write_json_atomic(stored_path, {**observation, 'comparison': {'result': 'match', 'problems': []}})
        if block:
            write_json_atomic(folder / ('%s.json' % block), {**observation, 'block': block, 'comparison': {'result': 'match', 'problems': []}})
        return observation

    def check_fingerprint(self, block):
        """Run the declared fingerprint command at a block start and refuse the block unless its fingerprint equals the study's first one and
        its session's first one. Returns the reading ({fingerprint, session}); the caller records the block start with it."""
        try:
            reading = self.redactor.deep(parse_fingerprint(self.fingerprint_runner(self.config['dataset_fingerprint'])))
        except Exception as error:
            problems = ['the dataset fingerprint could not be read: %s: %s' % (type(error).__name__, provenance.redact_value(error))]
            self._block_event('refused', block, reason='fingerprint', problems=self.redactor.deep(problems))
            raise FingerprintRefused(block['id'], self.redactor.deep(problems))
        starts = [e for e in read_jsonl(self.dir / 'blocks.jsonl') if e.get('event') == 'start']
        problems = []
        if starts and reading['fingerprint'] != starts[0]['fingerprint']:
            problems.append("the dataset fingerprint %s differs from the study's first, %s (block %s, session %s)"
                            % (reading['fingerprint'], starts[0]['fingerprint'], starts[0]['block'], starts[0]['session']))
        same = [e for e in starts if e.get('session') == reading['session']]
        if same and reading['fingerprint'] != same[0]['fingerprint']:
            problems.append("the dataset fingerprint %s differs from the first of session %s, %s (block %s)"
                            % (reading['fingerprint'], reading['session'], same[0]['fingerprint'], same[0]['block']))
        if problems:
            self._block_event('refused', block, reason='fingerprint', session=reading['session'], fingerprint=reading['fingerprint'],
                              problems=problems)
            raise FingerprintRefused(block['id'], problems)
        return reading

    def _block_event(self, event, block, **fields):
        fields.setdefault('attempt', self.attempt_of(block))
        append_jsonl(self.dir / 'blocks.jsonl', {'at': utc_now(), 'event': event, 'block': block['id'], 'arm': block['arm'],
                                                 'sequence': block['sequence'], 'row': block['row'], **fields})

    # ---------------------------------------------------------------- attempts, health and the void-block rule
    def attempt_of(self, block):
        """The block's current attempt: 1, and one more after every void event of the block."""
        return 1 + sum(1 for e in read_jsonl(self.dir / 'blocks.jsonl') if e.get('event') == 'void' and e.get('block') == block['id'])

    def attempt_ended(self, block, attempt):
        return any(e.get('event') == 'end' and e.get('block') == block['id'] and e.get('attempt') == attempt
                   for e in read_jsonl(self.dir / 'blocks.jsonl'))

    def probe_health(self, block, timeout=None):
        """Run the arm's health command once, within `timeout` seconds when given (the rest of a restore's deadline): (result, statuses,
        problems). The result is up, down or unreadable; a command that fails, times out or prints something unreadable is a problem too."""
        arm = block['arm']
        names = sorted(self.config['scenarios'][arm]['provenance']['backends'])
        command = self.config['scenarios'][arm]['health']
        try:
            text = self.health_runner(command) if timeout is None else self.health_runner(command, timeout=timeout)
            statuses = parse_health(text, names)
            problems = ['backend %s is down%s' % (n, (': ' + statuses[n]['detail']) if statuses[n]['detail'] else '')
                        for n in names if not statuses[n]['up']]
            result = 'down' if problems else 'up'
        except Exception as error:
            statuses, result = None, 'unreadable'
            problems = ['the health check could not be read: %s: %s' % (type(error).__name__, provenance.redact_value(error))]
        return result, self.redactor.deep(statuses), self.redactor.deep(problems)

    def record_health(self, block, attempt, point, probe, after=None, polls=None):
        result, statuses, problems = probe
        entry = {'at': utc_now(), 'block': block['id'], 'arm': block['arm'], 'attempt': attempt, 'point': point, 'result': result,
                 'backends': statuses, 'problems': problems}
        if after:
            entry['afterRun'] = after
        if polls is not None:
            entry['polls'] = polls
        append_jsonl(self.dir / 'health.jsonl', self.redactor.deep(entry))
        return problems

    def check_health(self, block, attempt, point, after=None):
        """One recorded health check; returns its problems (empty when every backend of the arm is up)."""
        return self.record_health(block, attempt, point, self.probe_health(block), after=after)

    def restore(self, stack, block, attempt, service, timeout, key):
        """Start the stopped service again and wait, within the scenario's ready_timeout_seconds, until the MCP server answers and the
        health check passes for every backend. Returns the problems of a restore that did not come back in time (a void trigger)."""
        deadline = self.clock() + timeout
        late = 'after %s was started again %%s did not answer within %s seconds' % (service, timeout)
        try:
            stack.start_service(service)
        except Exception as error:
            return self.redactor.deep(['the stopped service %s could not be started again: %s' % (service, provenance.redact_value(error))])
        remaining = deadline - self.clock()
        if remaining <= 0:
            return [late % 'the service']
        try:
            stack.wait_ready('%s__restore' % block['id'], remaining)
        except Exception as error:
            return self.redactor.deep([(late % 'the MCP server') + ': ' + provenance.redact_value(error)])
        if self.clock() > deadline:  # the MCP server answered, but after the deadline
            return [late % 'the MCP server']
        polls = 0
        while True:
            polls += 1
            remaining = deadline - self.clock()
            probe = self.probe_health(block, timeout=max(remaining, 0.001)) if remaining > 0 else (
                'down', None, ['no health check started before the deadline'])
            in_time = self.clock() <= deadline
            if (probe[0] == 'up' and in_time) or not in_time:  # the passing check, or the last one, is recorded with the number of polls
                if probe[0] == 'up' and not in_time:
                    probe = ('down', probe[1], ['every backend answered only after the deadline'])
                problems = self.record_health(block, attempt, 'restore', probe, after=key, polls=polls)
                if problems:
                    return ['after %s was started again the health check did not pass for every backend within %s seconds: %s'
                            % (service, timeout, '; '.join(problems))]
                return []
            self.sleep(2)

    def void_spend(self, folders):
        """{vendor: {'dollars', 'tokens', 'runs'}} of the run records in `folders` (their current results and archived attempts), at the
        prices of this run."""
        out = {}
        for folder in folders:
            for path in [folder / 'result.json'] + sorted((folder / 'attempts').glob('*/result.json')):
                if not path.exists():
                    continue
                record = json.loads(path.read_text(encoding='utf-8'))
                vendor = self.models_config['models'][record['model']]['vendor']
                usage = Usage.from_dict(record.get('usage') or {})
                entry = out.setdefault(vendor, {'dollars': 0.0, 'tokens': 0, 'runs': 0})
                entry['dollars'] = round(entry['dollars'] + dollars(usage, self.prices['models'][record['model']]), 6)
                entry['tokens'] += usage.total
                entry['runs'] += 1
        return out

    def declare_void(self, block, attempt, trigger, point, problems, session=None):
        """Record the void event, move the attempt's run folders to runs-void/<block>/<attempt>/ and stop with BlockVoid."""
        keys = [key for _, key in self.block_keys(block) if (self.dir / 'runs' / key).exists()]
        self._block_event('void', block, attempt=attempt, trigger=trigger, point=point, problems=self.redactor.deep(list(problems)),
                          session=session, runs=keys, spend=self.void_spend([self.dir / 'runs' / k for k in keys]))
        self.settle_voids(block)
        self.write_scores()
        raise BlockVoid(block['id'], attempt, trigger, problems)

    def folder_attempt(self, folder):
        """The block attempt a run folder belongs to: its result's blockAttempt, or None when it has no result yet."""
        path = folder / 'result.json'
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding='utf-8')).get('blockAttempt')

    def settle_voids(self, block):
        """Move every run folder that a void event of the block names, that is still among the runs and that belongs to that void attempt,
        to runs-void/<block>/<attempt>/. A folder belongs to the void attempt when its result names that attempt, or, with no result yet,
        when no later attempt of the block has started. A folder of a later attempt (the repeat) is never touched. Repeating it after an
        interruption finishes the move; a folder of the void attempt that is in both places stops for inspection."""
        events = read_jsonl(self.dir / 'blocks.jsonl')
        own = [e for e in events if e.get('block') == block['id']]
        for event in own:
            if event.get('event') != 'void':
                continue
            number = event['attempt']
            later_started = any(e.get('event') == 'start' and (e.get('attempt') or 0) > number for e in own)
            target_root = self.dir / VOID_FOLDER / block['id'] / str(number)
            for key in event.get('runs', []):
                source, target = self.dir / 'runs' / key, target_root / key
                if not source.exists():
                    continue
                owner = self.folder_attempt(source)
                if owner != number and not (owner is None and not later_started):
                    continue  # the folder of a later attempt: the repeat's own run
                if target.exists():
                    raise RuntimeError('The run %s of void attempt %d of block %s is both among the runs and in %s; inspect it before '
                                       'resuming' % (key, event['attempt'], block['id'], VOID_FOLDER))
                target_root.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))

    # ---------------------------------------------------------------- the budget across study runs
    def read_carry(self):
        """The earlier study runs' spend, from their vendor ledgers (read only): ids, ledger hashes, dollars and tokens, and the totals per
        vendor. A listed run without a manifest, or with a ledger of a vendor its manifest does not price, refuses the start."""
        runs, totals = [], {}
        for run_id in self.config.get('earlier_study_runs', []):
            folder = self.dir.parent / run_id
            manifest_path = folder / 'manifest.json'
            if not manifest_path.exists():
                raise BudgetCarryRefused('The earlier study run %s, listed in earlier_study_runs, has no manifest in the results folder: its '
                                         'spend cannot be counted against the ceiling' % run_id)
            earlier = json.loads(manifest_path.read_text(encoding='utf-8'))
            price_of = {entry.get('vendor'): entry.get('priceEntry') for entry in (earlier.get('models') or {}).values()}
            ledgers = {}
            for path in sorted(folder.glob('budget-*.jsonl')):
                vendor = path.name[len('budget-'):-len('.jsonl')]
                if not price_of.get(vendor):
                    raise BudgetCarryRefused('The earlier study run %s has a %s ledger but its manifest prices no %s model' % (run_id, vendor,
                                                                                                                     vendor))
                spent, tokens = ledger_dollars(path, price_of[vendor])
                ledgers[vendor] = {'sha256': sha256_file(path), 'dollars': round(spent, 6), 'tokens': tokens}
                totals[vendor] = round(totals.get(vendor, 0.0) + spent, 6)
            runs.append({'runId': run_id, 'ledgers': ledgers})
        return {'runs': runs, 'totals': totals,
                'rule': 'the dollars of these ledgers count against each vendor\'s dollar_ceiling from the first request of this run; '
                        'a reservation never settled is counted at the output price'}

    def check_carry(self, stored):
        """On resume: the earlier runs' ledgers must still hash as the manifest recorded them."""
        current = self.read_carry()
        before = {(r['runId'], v): l['sha256'] for r in (stored or {}).get('runs', []) for v, l in r['ledgers'].items()}
        after = {(r['runId'], v): l['sha256'] for r in current['runs'] for v, l in r['ledgers'].items()}
        if before != after:
            changed = sorted('%s (%s)' % key for key in set(before) | set(after) if before.get(key) != after.get(key))
            raise BudgetCarryRefused('The ledgers of earlier study runs changed since this run started: %s. Start a new study run instead.'
                                     % ', '.join(changed))
        return stored

    def ceilings(self):
        return {v: {'dollar_ceiling': b.get('dollar_ceiling'), 'ceiling_basis': b.get('ceiling_basis')}
                for v, b in sorted(self.config['budgets'].items())}

    def ceiling_changes(self, stored_manifest):
        """The ceiling or basis changes of a resume against the last values the run recorded (the manifest, or the last resume). A changed
        ceiling with an unchanged basis refuses: a raise or a cut needs its basis (decision D, or the lead developer's dated raise)."""
        last = {v: {'dollar_ceiling': b.get('dollar_ceiling'), 'ceiling_basis': b.get('ceiling_basis')}
                for v, b in (stored_manifest.get('tokenBudgets') or {}).items()}
        for entry in read_jsonl(self.dir / 'resumes.jsonl'):
            if 'ceilings' in entry:
                last = entry['ceilings']
        changes = []
        for vendor, now in self.ceilings().items():
            before = last.get(vendor, {})
            if before != now:
                if before.get('dollar_ceiling') != now['dollar_ceiling'] and before.get('ceiling_basis') == now['ceiling_basis']:
                    raise RuntimeError('The dollar ceiling of %s changed from %s to %s with the same ceiling_basis; a changed ceiling needs '
                                       'its basis (decision D, or the lead developer\'s dated raise)'
                                       % (vendor, before.get('dollar_ceiling'), now['dollar_ceiling']))
                changes.append({'vendor': vendor, 'old': before, 'new': now})
        return changes

    # ---------------------------------------------------------------- budgets and clients
    def budget_for(self, model):
        vendor = self.models_config['models'][model]['vendor']
        if vendor not in self.budgets:
            setting = self.config['budgets'][vendor]
            carried = (self.carry or {}).get('totals', {}).get(vendor, 0.0) if self.schedule is not None else None
            self.budgets[vendor] = Budget(vendor, model, setting['tokens'], self.prices['models'][model], self.prices['dated'],
                                          self.dir / ('budget-%s.jsonl' % vendor), dollar_ceiling=setting.get('dollar_ceiling'),
                                          carried_dollars=carried)
        return self.budgets[vendor]

    def client_for(self, model):
        if model not in self.clients:
            self.clients[model] = self.client_factory(model)
        return self.clients[model]

    # ---------------------------------------------------------------- one run
    def completed(self, key):
        path = self.dir / 'runs' / key / 'result.json'
        if not path.exists():
            return False
        return json.loads(path.read_text(encoding='utf-8')).get('outcome') in TERMINAL

    def _archive_attempt(self, key):
        run_dir = self.dir / 'runs' / key
        if not run_dir.exists() or not any(p for p in run_dir.iterdir() if p.name != 'attempts'):
            return 1
        attempts = run_dir / 'attempts'
        number = len(list(attempts.iterdir())) + 1 if attempts.exists() else 1
        target = attempts / ('%03d' % number)
        target.mkdir(parents=True)
        for item in list(run_dir.iterdir()):
            if item.name != 'attempts':
                shutil.move(str(item), str(target / item.name))
        return number + 1

    def vendor_errors(self, key):
        """How many attempts of a run ended on a vendor error: its current result and its archived attempts."""
        run_dir = self.dir / 'runs' / key
        paths = [run_dir / 'result.json'] + sorted((run_dir / 'attempts').glob('*/result.json'))
        return sum(1 for p in paths if p.exists() and json.loads(p.read_text(encoding='utf-8')).get('outcome') in ('error', 'vendor_error'))

    def run_one(self, scenario, task, model, trial):
        return self.execute(scenario, task, model, run_key(scenario, task['id'], model, trial), {'trial': trial})

    def execute(self, scenario, task, model, key, fields):
        """One run with its record. `fields` are added to the record (the trial, or the block facts of the schedule). In the schedule a
        vendor error is kept as `error`, to be queued again once, and a second one is recorded as `vendor_error`."""
        prior_errors = self.vendor_errors(key) if self.schedule is not None else 0
        attempt = self._archive_attempt(key)
        run_dir = self.dir / 'runs' / key
        transcript = run_dir / 'transcript.jsonl'
        budget = self.budget_for(model)
        system = SYSTEM_PROMPT
        guide = self._guide_path(scenario)
        if guide:
            system += '\n\nGuide to the enterprise systems:\n\n' + guide.read_text(encoding='utf-8')
        tools = {}

        def score(submission):
            context = {'taskId': task['id'], 'set': task.get('set') or 'core', 'category': task['category'],
                       'askRequester': [dict(q) for q in tools['session'].questions] if 'session' in tools else []}
            return self.contract.score(submission, task, context)

        with self.session_factory(scenario, key) as session:
            if self.tool_names:
                store = harness_tools.ResultStore(run_dir / 'results.jsonl', harness_tools.run_tag(key, attempt),
                                                   redact=self.redactor.deep)
                session = tools['session'] = harness_tools.HarnessToolSession(session, self.tool_names, store, key, clock=self.clock)
            agent = AgentRun(self.client_for(model), session, budget, self.limits, score, lambda event: append_jsonl(transcript, event),
                             self.redactor, clock=self.clock, sleep=self.sleep, run_id=key)
            before = budget.snapshot()
            result = agent.run({'id': task['id'], 'question': task['question'], 'schema': task['schema'], 'system': system})
        after = budget.snapshot()
        record = {'runKey': key, 'studyRunId': self.study_run_id, 'scenario': scenario, 'model': model, **fields, 'category': task['category'],
                  'attempt': attempt, 'phase': 'measurement', 'finishedAt': utc_now(), 'budgetBefore': before, 'budgetAfter': after, **result}
        if 'session' in tools:
            record['harnessToolCalls'] = dict(tools['session'].counts)
            record['askRequester'] = [dict(q) for q in tools['session'].questions]
        if self.schedule is not None:
            errors = prior_errors + (1 if result['outcome'] == 'error' else 0)
            record.update({'requeued': prior_errors > 0, 'vendorErrors': errors})
            if result['outcome'] == 'error' and prior_errors > 0:
                record['outcome'] = 'vendor_error'
        write_json_atomic(run_dir / 'result.json', self.redactor.deep(record))
        append_jsonl(self.dir / 'samples.jsonl', {'phase': 'measurement', 'scenario': scenario, 'kind': 'agent_run', 'runKey': key,
                                                  'seconds': result['elapsedSeconds'], 'outcome': record['outcome']})
        self.write_scores()
        return record

    def warm_up(self, scenario, label, extra=None):
        """The cold first request and the declared warm-up passes, each a sample. `extra` is added to every sample (the block id)."""
        sconfig = self.config['scenarios'][scenario]
        samples = self.dir / 'samples.jsonl'
        first = True
        for pass_number in range(1, self.config.get('warmup_passes', 3) + 1):
            for call in sconfig.get('warmup_calls', []):
                with self.session_factory(scenario, '%s__warmup' % label) as session:
                    t0 = self.clock()
                    session.call(call['tool'], call['arguments'])
                    append_jsonl(samples, {'phase': 'cold' if first else 'warm-up', 'scenario': scenario,
                                           'kind': 'cold_first_request' if first else 'warmup_call', 'pass': pass_number,
                                           'seconds': round(self.clock() - t0, 3), **(extra or {})})
                    first = False

    def check_tool_names(self, scenario, label):
        """Refuse a scenario whose MCP server offers a tool named like a harness tool, before any paid request."""
        if self.tool_names:
            with self.session_factory(scenario, '%s__tools' % label) as session:
                harness_tools.HarnessToolSession(session, self.tool_names, None, label).tools()

    # ---------------------------------------------------------------- one block of the schedule (one stack run)
    def block_keys(self, block):
        return [(run, schedule.run_key(block['arm'], run['task'], run['model'], block['runSuffix'])) for run in block['runs']]

    def run_block(self, block):
        """One block: skipped when every run is finished and its attempt ended; otherwise start the arm's stack, check provenance and the
        dataset fingerprint, record the start of the current attempt, check the health of every backend, warm up, run the missing runs in
        order (the health checked again every health_every_runs runs, and after every restore of an outage task's service), then once more
        every run that ended on a vendor error, check the health at the end, and tear down. A void trigger raises BlockVoid."""
        self.settle_voids(block)
        keys = self.block_keys(block)
        attempt = self.attempt_of(block)
        if all(self.completed(key) for _, key in keys) and self.attempt_ended(block, attempt):
            return None
        arm = block['arm']
        sconfig = self.config['scenarios'][arm]
        timeout = sconfig.get('ready_timeout_seconds', 300)
        stack = self.stack_factory(arm)
        mark = {'block': block['id']}
        starts = sum(1 for e in read_jsonl(self.dir / 'blocks.jsonl') if e.get('event') == 'start' and e.get('block') == block['id'])
        try:
            began = self.clock()
            stack.start()
            stack.wait_ready('%s__ready' % block['id'], timeout)
            append_jsonl(self.dir / 'samples.jsonl', {'phase': 'cold', 'scenario': arm, 'kind': 'cold_start',
                                                      'seconds': round(self.clock() - began, 3), **mark})
            try:
                observation = self.check_provenance(arm, block['id'])
            except BackendDown as down:
                self.declare_void(block, attempt, 'provenance', 'start', down.problems)
            reading = self.check_fingerprint(block)
            session = reading['session']
            self._block_event('start', block, attempt=attempt, session=session, fingerprint=reading['fingerprint'],
                              provenanceFingerprint=observation['fingerprint'], start=starts + 1,
                              runsFinishedBefore=sum(1 for _, key in keys if self.completed(key)))
            problems = self.check_health(block, attempt, 'start')
            if problems:
                self.declare_void(block, attempt, 'health', 'start', problems, session)
            self.check_tool_names(arm, block['id'])
            self.warm_up(arm, block['id'], mark)
            fields = {'block': block['id'], 'blockSequence': block['sequence'], 'row': block['row'], 'roundSequence': block['roundSequence'],
                      'position': block['position'], 'half': block['half'], 'session': session, 'blockAttempt': attempt}
            executed = 0
            for requeue in (False, True):
                for run, key in keys:
                    if self.completed(key) or (self.vendor_errors(key) > 0) != requeue:
                        continue
                    task = self.by_id[run['task']]
                    service = task.get('stoppedService')
                    if service:
                        stack.stop_service(service)
                    restore_problems = []
                    try:
                        record = self.execute(arm, task, run['model'], key, {**fields, 'orderInBlock': keys.index((run, key)) + 1})
                    finally:
                        if service:
                            restore_problems = self.restore(stack, block, attempt, service, timeout, key)
                    executed += 1
                    if restore_problems:
                        self.declare_void(block, attempt, 'restore', 'restore', restore_problems, session)
                    if record['outcome'] == 'budget_stop':
                        self._block_event('stopped', block, session=session, reason='budget_stop', runKey=key)
                        return record
                    if not service and executed % self.health_every == 0:  # after an outage run the restore check stands for it
                        problems = self.check_health(block, attempt, 'periodic', after=key)
                        if problems:
                            self.declare_void(block, attempt, 'health', 'periodic', problems, session)
            problems = self.check_health(block, attempt, 'end')
            if problems:
                self.declare_void(block, attempt, 'health', 'end', problems, session)
            self._block_event('end', block, session=session,
                              outcomes={o: sum(1 for _, k in keys if self._outcome(k) == o) for o in sorted({self._outcome(k) for _, k in keys})})
        finally:
            stack.teardown()
        return None

    def _outcome(self, key):
        path = self.dir / 'runs' / key / 'result.json'
        return (json.loads(path.read_text(encoding='utf-8')).get('outcome') if path.exists() else None) or 'missing'

    # ---------------------------------------------------------------- one scenario (one stack run)
    def run_scenario(self, scenario_plan):
        scenario = scenario_plan['scenario']
        sconfig = self.config['scenarios'][scenario]
        stack = self.stack_factory(scenario)
        samples = self.dir / 'samples.jsonl'
        stopped = None
        try:
            began = self.clock()
            stack.start()
            stack.wait_ready('%s__ready' % scenario, sconfig.get('ready_timeout_seconds', 300))
            append_jsonl(samples, {'phase': 'cold', 'scenario': scenario, 'kind': 'cold_start', 'seconds': round(self.clock() - began, 3)})
            self.check_provenance(scenario)
            self.check_tool_names(scenario, scenario)
            self.warm_up(scenario, scenario)
            for unit in scenario_plan['units']:
                task = self.by_id[unit['task']]
                pending = [m for m in unit['models'] if not self.completed(run_key(scenario, task['id'], m, unit['trial']))]
                if not pending:
                    continue
                service = task.get('stoppedService')
                if service:
                    stack.stop_service(service)
                try:
                    for model in unit['models']:
                        if model not in pending:
                            continue
                        record = self.run_one(scenario, task, model, unit['trial'])
                        if record['outcome'] == 'budget_stop':
                            stopped = record
                            return stopped
                finally:
                    if service:
                        stack.start_service(service)
                        stack.wait_ready('%s__restore' % scenario, sconfig.get('ready_timeout_seconds', 300))
        finally:
            stack.teardown()
        return stopped

    # ---------------------------------------------------------------- the whole study
    def run(self, resume=False):
        manifest_path = self.dir / 'manifest.json'
        if manifest_path.exists():
            if not resume:
                raise RuntimeError('Study run %s already exists: use --resume to continue it, or choose a new run id' % self.study_run_id)
            stored = json.loads(manifest_path.read_text(encoding='utf-8'))
            if stored['planHash'] != sha256_json(self.plan_identity()):
                raise RuntimeError('The plan, models, limits, prompt, guides or corpus differ from the stored manifest: a resume repeats the '
                                   'same study. Start a new study run instead.')
            stored_intended = (stored.get('provenance') or {}).get('intended')
            if stored_intended is None:
                raise RuntimeError('The stored manifest records no provenance, so a resume cannot verify the backends. Start a new study run '
                                   'instead.')
            changes = provenance.drift(stored_intended, self.redactor.deep(self.intended_provenance()))
            if changes:
                raise RuntimeError('The declared provenance differs from the stored manifest, so a resume would run against other backends. '
                                   'Start a new study run instead. Changes:\n- ' + '\n- '.join(changes))
            resume = {'at': utc_now()}
            if self.schedule is not None:
                self.carry = self.check_carry(stored.get('budgetCarry'))
                budget_changes = self.ceiling_changes(stored)
                resume['ceilings'] = self.ceilings()
                if budget_changes:
                    resume['ceilingChanges'] = budget_changes
            skipped = sum(1 for p in (self.dir / 'runs').glob('*/result.json') if self.completed(p.parent.name))
            append_jsonl(self.dir / 'resumes.jsonl', {**resume, 'completedRunsKept': skipped})
        else:
            if self.schedule is not None:
                self.carry = self.read_carry()
            self.dir.mkdir(parents=True, exist_ok=True)
            write_json_atomic(manifest_path, self.redactor.deep(self.manifest()))
        status = 'complete'
        stop = None
        units = self.plan['blocks'] if self.schedule is not None else self.plan
        try:
            for unit in units:
                stop = self.run_block(unit) if self.schedule is not None else self.run_scenario(unit)
                if stop:
                    status = 'budget_stop'
                    break
        except BlockVoid as void:
            self.void = void
            status = 'block_void'
        except (provenance.ProvenanceRefused, FingerprintRefused, scoring_contract.ScoringContractError) as error:
            self.write_scores()
            self.write_bundle({provenance.ProvenanceRefused: 'provenance_refused', FingerprintRefused: 'fingerprint_refused',
                               scoring_contract.ScoringContractError: 'scoring_error'}[type(error)])
            raise
        self.write_scores()
        self.write_bundle(status)
        return status

    # ---------------------------------------------------------------- records
    SCHEDULE_COLUMNS = ('block', 'blockSequence', 'row', 'roundSequence', 'position', 'half', 'orderInBlock', 'session', 'requeued',
                        'vendorErrors', 'blockAttempt')

    def write_scores(self):
        """One row per run. The columns of the schedule, the harness tools and the ambiguity flags are added only when a record has them,
        so a study-1 run writes the same columns as before. A vendor error is no score (it is missing in the main analysis)."""
        rows = []
        for path in sorted((self.dir / 'runs').glob('*/result.json')):
            r = json.loads(path.read_text(encoding='utf-8'))
            scored = r.get('score') or {}
            row = {'runKey': r['runKey'], 'scenario': r['scenario'], 'taskId': r['taskId'], 'category': r['category'], 'model': r['model'],
                   'trial': r.get('trial', ''), 'outcome': r['outcome'], 'reason': r.get('reason') or '',
                   'score': scored.get('score', 0) if r['outcome'] in TERMINAL and r['outcome'] != 'vendor_error' else '',
                   'tags': ';'.join(scored.get('tags', [])), 'seconds': r['elapsedSeconds'], 'turns': r['turns'],
                   'toolCalls': r['toolCalls'], **{'tokens_' + k: v for k, v in r['usage'].items()}, 'attempt': r['attempt']}
            row.update({name: r[name] for name in self.SCHEDULE_COLUMNS if name in r})
            if 'harnessToolCalls' in r:
                calls = r['harnessToolCalls']
                row.update({'calculateCalls': calls.get('calculate', 0), 'calculateErrors': calls.get('calculateErrors', 0),
                            'askRequesterCalls': calls.get('askRequester', 0)})
            row.update({name: scored[name] for name in scoring_contract.AMBIGUITY_FLAGS if name in scored})
            rows.append(row)
        with open(self.dir / 'scores.jsonl', 'w', encoding='utf-8', newline='\n') as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + '\n')
        if rows:
            fieldnames = []
            for row in rows:
                fieldnames.extend(name for name in row if name not in fieldnames)
            with open(self.dir / 'scores.csv', 'w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, restval='', lineterminator='\n')
                writer.writeheader()
                writer.writerows(rows)

    def write_bundle(self, status):
        files = {}
        for path in sorted(self.dir.rglob('*')):
            if path.is_file() and path.name not in ('bundle.json',):
                files[path.relative_to(self.dir).as_posix()] = sha256_file(path)
        body = {'studyRunId': self.study_run_id, 'status': status, 'writtenAt': utc_now(), 'files': files,
                'budgets': {v: b.snapshot() for v, b in self.budgets.items()}}
        if self.schedule is not None:
            body['voidAttempts'] = self.void_attempts()
            body['budgetCarry'] = {'totals': (self.carry or {}).get('totals', {})}
        body['checksum'] = sha256_bytes(json.dumps(files, sort_keys=True).encode('utf-8'))
        write_json_atomic(self.dir / 'bundle.json', body)
        return body['checksum']

    def void_attempts(self):
        """The void attempts of the run, from blocks.jsonl, and their spend per vendor apart from the counted runs (it stays in the ledgers,
        because it was billed)."""
        attempts, spend = [], {}
        for event in read_jsonl(self.dir / 'blocks.jsonl'):
            if event.get('event') != 'void':
                continue
            attempts.append({k: event.get(k) for k in ('block', 'arm', 'attempt', 'trigger', 'point', 'at', 'runs', 'spend')})
            for vendor, entry in (event.get('spend') or {}).items():
                total = spend.setdefault(vendor, {'dollars': 0.0, 'tokens': 0, 'runs': 0})
                total['dollars'] = round(total['dollars'] + entry['dollars'], 6)
                total['tokens'] += entry['tokens']
                total['runs'] += entry['runs']
        return {'attempts': attempts, 'spend': spend}


# ---------------------------------------------------------------------------------------------------------------- command line
def load_config(path):
    """The machine-local config. With a `schedule` (study 2) `scenario_order` and `trials` are not used, and `dataset_fingerprint` is needed."""
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    needed = ('scenarios', 'models', 'seed', 'budgets', 'task_set')
    needed += ('dataset_fingerprint',) if 'schedule' in config else ('scenario_order', 'trials')
    for name in needed:
        if name not in config:
            raise ValueError('The study config lacks %r' % name)
    return config


def corpus_of(config, given=None):
    """The corpus folder: --corpus-dir, else the config's `corpus_dir` (make_config.py writes it), else study 1's corpus. A --corpus-dir
    that names another folder than the config's is refused, so a run never reads a corpus its config does not name."""
    named = config.get('corpus_dir')
    if given and named and Path(given).resolve() != Path(named).resolve():
        raise ValueError('--corpus-dir %s differs from the config\'s corpus_dir %s; give one of them' % (given, named))
    return Path(given or named or DEFAULT_CORPUS)


def make_session_factory(config):
    def factory(scenario, run_id):
        from mcp_client import McpSession
        return McpSession(config['scenarios'][scenario]['mcp_url'], run_id)
    return factory


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the Abstraction ladder study (start it through launcher.py, which supplies the API keys).')
    parser.add_argument('--config', default=os.environ.get('STUDY_CONFIG'), help='the machine-local study config (or the variable STUDY_CONFIG)')
    parser.add_argument('--run-id', required=True, help='the study run id (a folder of LAB_RESULTS_DIR)')
    parser.add_argument('--resume', action='store_true', help='continue a stopped study run: only missing or incomplete runs are executed')
    parser.add_argument('--vendors', nargs='*', help='vendors whose key the run needs (set by the launcher)')
    parser.add_argument('--corpus-dir', help='the corpus folder (default: the config\'s corpus_dir, else study 1\'s study/corpus)')
    parser.add_argument('--dry-run', action='store_true',
                        help='run the whole protocol with a fake vendor client that only submits an empty answer: no key, no API call, no cost')
    args = parser.parse_args(argv)
    if not args.config:
        parser.error('--config or STUDY_CONFIG is required')
    config = load_config(args.config)
    try:
        corpus_dir = corpus_of(config, args.corpus_dir)
    except ValueError as error:
        parser.error(str(error))
    models_config = json.loads((HERE / 'models.json').read_text(encoding='utf-8'))
    prices = json.loads((HERE / 'prices.json').read_text(encoding='utf-8'))
    factory = None
    if args.dry_run:
        from fakes import FakeVendorClient, submit
        factory = lambda model: FakeVendorClient([lambda s, t, tools: submit({})] * 100000, max_output_tokens=1000, model=model)
    try:
        study = Study(config, models_config, prices, args.run_id, corpus_dir=corpus_dir, session_factory=make_session_factory(config),
                      client_factory=factory)
        for model in config['models']:  # fail early, before any stack starts, when a key is missing
            study.client_for(model)
    except MissingCredentialError as error:
        print('STOP: ' + str(error))
        return 2
    try:
        status = study.run(resume=args.resume)
    except BudgetCarryRefused as error:
        print('STOP: ' + str(error))
        print('Study run %s: budget_carry_refused' % args.run_id)
        return 3
    except provenance.ProvenanceRefused as error:
        print('STOP: ' + str(error))
        print('Study run %s: provenance_refused' % args.run_id)
        return 3
    except FingerprintRefused as error:
        print('STOP: ' + str(error))
        print('Study run %s: fingerprint_refused' % args.run_id)
        return 3
    except scoring_contract.ScoringContractError as error:
        print('STOP: the scorer broke its contract: ' + str(error))
        print('Study run %s: scoring_error' % args.run_id)
        return 3
    for vendor, budget in study.budgets.items():
        print(json.dumps(budget.snapshot()))
    if study.void is not None:
        print('STOP: ' + str(study.void))
    print('Study run %s: %s' % (args.run_id, status))
    return 0 if status == 'complete' else 3


if __name__ == '__main__':
    sys.exit(main())
