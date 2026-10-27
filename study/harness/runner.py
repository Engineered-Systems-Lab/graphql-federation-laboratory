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
inside the schedule, block by block, and skips every block whose runs are all finished.

Records go to LAB_RESULTS_DIR/<study run id>/ : manifest.json (immutable), samples.jsonl, one budget ledger per vendor, runs/<key>/
(transcript.jsonl, result.json and, with the harness tools, results.jsonl), provenance/ (one observation per scenario, one per block, and the
checks), blocks.jsonl (with a schedule), scores.jsonl and scores.csv, bundle.json with the checksum. Nothing written holds an absolute path
or a key.
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
from budget import Budget
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
                 hasher=provenance.hash_path, fingerprint_runner=run_fingerprint_command):
        self.config, self.models_config, self.prices = config, models_config, prices
        self.schedule = config.get('schedule')
        if self.schedule is not None:
            schedule.validate(self.schedule, config['scenarios'], config['models'])
            validate_fingerprint_command(config.get('dataset_fingerprint'))
            self.scenarios = schedule.scenarios_of(self.schedule)
        else:
            self.scenarios = list(config['scenario_order'])
        for scenario in self.scenarios:
            provenance.validate(scenario, config['scenarios'][scenario].get('provenance'))
        self.tool_names = config.get('harness_tools', [])
        harness_tools.validate(self.tool_names)
        self.fingerprint_runner = fingerprint_runner
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
        if self.tool_names:
            identity['harnessTools'] = harness_tools.describe(self.tool_names)
        if self.contract.version != 1:
            identity['scoringContract'] = self.contract.version
        return identity

    def fingerprint_declaration(self):
        return provenance.redact_command(self.config['dataset_fingerprint'])

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
                                                            "and its session's first fingerprint"}})
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
        append_jsonl(self.dir / 'blocks.jsonl', {'at': utc_now(), 'event': event, 'block': block['id'], 'arm': block['arm'],
                                                 'sequence': block['sequence'], 'row': block['row'], **fields})

    # ---------------------------------------------------------------- budgets and clients
    def budget_for(self, model):
        vendor = self.models_config['models'][model]['vendor']
        if vendor not in self.budgets:
            setting = self.config['budgets'][vendor]
            self.budgets[vendor] = Budget(vendor, model, setting['tokens'], self.prices['models'][model], self.prices['dated'],
                                          self.dir / ('budget-%s.jsonl' % vendor), dollar_ceiling=setting.get('dollar_ceiling'))
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
        """One block: skipped when every run is finished; otherwise start the arm's stack, check provenance and the dataset fingerprint,
        warm up, run the missing runs in order, then once more every run that ended on a vendor error, and tear down."""
        keys = self.block_keys(block)
        if all(self.completed(key) for _, key in keys):
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
            observation = self.check_provenance(arm, block['id'])
            reading = self.check_fingerprint(block)
            self._block_event('start', block, session=reading['session'], fingerprint=reading['fingerprint'],
                              provenanceFingerprint=observation['fingerprint'], start=starts + 1,
                              runsFinishedBefore=sum(1 for _, key in keys if self.completed(key)))
            self.check_tool_names(arm, block['id'])
            self.warm_up(arm, block['id'], mark)
            fields = {'block': block['id'], 'blockSequence': block['sequence'], 'row': block['row'], 'roundSequence': block['roundSequence'],
                      'position': block['position'], 'half': block['half'], 'session': reading['session']}
            for requeue in (False, True):
                for run, key in keys:
                    if self.completed(key) or (self.vendor_errors(key) > 0) != requeue:
                        continue
                    task = self.by_id[run['task']]
                    service = task.get('stoppedService')
                    if service:
                        stack.stop_service(service)
                    try:
                        record = self.execute(arm, task, run['model'], key, {**fields, 'orderInBlock': keys.index((run, key)) + 1})
                    finally:
                        if service:
                            stack.start_service(service)
                            stack.wait_ready('%s__restore' % block['id'], timeout)
                    if record['outcome'] == 'budget_stop':
                        self._block_event('stopped', block, session=reading['session'], reason='budget_stop', runKey=key)
                        return record
            self._block_event('end', block, session=reading['session'],
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
            skipped = sum(1 for p in (self.dir / 'runs').glob('*/result.json') if self.completed(p.parent.name))
            append_jsonl(self.dir / 'resumes.jsonl', {'at': utc_now(), 'completedRunsKept': skipped})
        else:
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
                        'vendorErrors')

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
        body['checksum'] = sha256_bytes(json.dumps(files, sort_keys=True).encode('utf-8'))
        write_json_atomic(self.dir / 'bundle.json', body)
        return body['checksum']


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
    parser.add_argument('--corpus-dir', default=str(DEFAULT_CORPUS))
    parser.add_argument('--dry-run', action='store_true',
                        help='run the whole protocol with a fake vendor client that only submits an empty answer: no key, no API call, no cost')
    args = parser.parse_args(argv)
    if not args.config:
        parser.error('--config or STUDY_CONFIG is required')
    config = load_config(args.config)
    models_config = json.loads((HERE / 'models.json').read_text(encoding='utf-8'))
    prices = json.loads((HERE / 'prices.json').read_text(encoding='utf-8'))
    factory = None
    if args.dry_run:
        from fakes import FakeVendorClient, submit
        factory = lambda model: FakeVendorClient([lambda s, t, tools: submit({})] * 100000, max_output_tokens=1000, model=model)
    try:
        study = Study(config, models_config, prices, args.run_id, corpus_dir=args.corpus_dir, session_factory=make_session_factory(config),
                      client_factory=factory)
        for model in config['models']:  # fail early, before any stack starts, when a key is missing
            study.client_for(model)
    except MissingCredentialError as error:
        print('STOP: ' + str(error))
        return 2
    try:
        status = study.run(resume=args.resume)
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
    print('Study run %s: %s' % (args.run_id, status))
    return 0 if status == 'complete' else 3


if __name__ == '__main__':
    sys.exit(main())
