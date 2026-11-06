"""Watch a study-2 run folder while the harness writes it, and print where the run stands: read only, never an outcome.

    python -B study/launch/watch_run.py <run folder> [--once] [--verbose] [--interval <seconds>] [--balance <vendor>=<dollars> ...]

The run folder is LAB_RESULTS_DIR/<study run id>/, the folder the harness (study/harness/runner.py) writes. The watcher prints one report
at its start and then, while it follows the folder, one after every block `end`, `void` or `stopped` event of blocks.jsonl and every new
line of resumes.jsonl. It ends by itself when the harness writes bundle.json again (a stop or the end of the run), after a last report.
Started on a run that has ended, it prints one report and ends. `--once` prints one report and ends.

Every time a report prints is in the machine's local time, with the time zone named once in its header; the files the harness writes
keep UTC. By default a report is compact: a header, the progress with the time so far, the time left, a money table per vendor and a
health line that says "all clear" when nothing happened. `--verbose` prints the full report, which shows:

- progress: the blocks ended out of the schedule's, the runs finished out of its runs, the current block (arm, half, attempt) and the
  time since the first block start, in blocks and per ended block on average, and the time left with the expected end (`time_left`);
- the health of the run: the void attempts (block, attempt, trigger, point and the first problem), the budget stops, the retried requests
  and the notes the ledgers hold, the vendor errors and requeued runs, the resumes and the health checks recorded;
- the spend per vendor: this run's dollars, priced from its ledgers with the manifest's price entries (budget.py `dollars`), plus the
  dollars carried from earlier study-2 runs (the manifest's budgetCarry), against the vendor's dollar_ceiling (the last one a resume
  recorded, else the manifest's), with the room left, and the tokens against the token budget. A reservation that has no settlement is
  counted at the output price, as budget.py `ledger_dollars` counts it for the carry;
- an estimate of the rest per vendor: every scheduled run not finished yet costs the mean cost of this run's finished runs of the same arm
  and model, or of the same model while that arm has none; with no finished run of the model it is "too early". The cost of a run is
  what its run key cost in the ledger since its block's current attempt began, retries included and a void attempt's spend left
  out. A block that has not ended may hold finished runs whose records are not read yet, so its estimate is a range: the whole mean for
  each of its runs, or nothing for those that already have spend in the current attempt. Only this run's finished runs are used
  (decision W2);
- with --balance, the room under each account balance given: the balance as read when the watcher starts, less what this run settled
  since and what its open reservations may still cost. The balances are kept in memory and printed, never written anywhere (decision
  W3).

The time left is one figure for the whole run, pooled over arms (decision E1 (a) of the Job study2_watch_eta, 2026-11-06): the mean
time per run of the ended blocks times the runs left, plus the mean time between blocks times the block starts left. A block's runs
and time are those since its current attempt's last start (the start event's runsFinishedBefore gives the runs done before it), and a
gap between blocks is an end followed by the next start, left out when a resume lies in it. The block running now is credited with the
time it has run. Before a block has ended it is "too early". Nothing is shown per arm, per model or per task, the mean per run included.

A report never shows an outcome, a score, a correctness count or any result of an arm: the `outcomes` field of a block's end event is
dropped when the event is read, a run record is reduced on reading to whether it is finished and its vendor-error count, and no cost is
shown per task or per arm, only per vendor. Interim results must not steer a scored run.

It only reads: it writes, moves, locks and starts nothing, and it never creates the folder it watches. It also keeps out of the
harness's way. On Windows a file that another process has open, even for a moment and even for os.stat, cannot be replaced or have its
folder moved: the harness's atomic replace of result.json and bundle.json, and its moves of run folders, would then fail and stop the run.
So the watcher reads at any time only the files the harness appends to (blocks.jsonl, resumes.jsonl, health.jsonl and the ledgers) and
the manifest, which is written once. It never opens bundle.json: a listing of the folder, which opens no file, gives the time the
harness wrote it, and the events say why it stopped. It reads the result.json files of a block only once the
block's current attempt has ended in blocks.jsonl: from then on the harness never replaces or moves them, whatever it does meanwhile.
The runs of a block that has not ended (running, starting, or stopped and waiting for a resume) are counted once it ends.

It is an operator tool beside launch.py and is not among the files a run hashes, so a fix of it never blocks a resume.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'harness'))
from agent import TERMINAL  # noqa: E402  (the outcomes that finish a run; only membership is ever tested)
from budget import Usage, dollars  # noqa: E402  (the harness's own pricing)

DEFAULT_INTERVAL = 15.0
REPORT_EVENTS = ('end', 'void', 'stopped')


# ---------------------------------------------------------------------------------------------------------------- reading
def read_text(path):
    """The UTF-8 text of a file, or None when it does not exist."""
    try:
        with open(path, 'rb') as handle:
            return handle.read().decode('utf-8')
    except FileNotFoundError:
        return None


def listed(folder, name):
    """(modification time, size) of a file as a listing of its folder shows it, or None. On Windows the listing gives both without
    opening the file, so it never stands in the way of a replace."""
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name == name and entry.is_file():
                    info = entry.stat()
                    return info.st_mtime_ns, info.st_size
    except FileNotFoundError:
        return None
    return None


def read_json(path):
    text = read_text(path)
    return None if text is None else json.loads(text)


def read_jsonl(path):
    """(entries, unreadable line count) of a JSON-lines file. A last line without its line end is a line the harness is still writing and
    is left for the next read; any other line that does not parse is counted."""
    text = read_text(path)
    if text is None:
        return [], 0
    lines = text.split('\n')
    tail = lines.pop()  # empty when the file ends with a line end
    entries, bad = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            bad += 1
    if tail.strip():
        try:
            entries.append(json.loads(tail))
        except ValueError:
            pass
    return entries, bad


def block_events(folder):
    """The events of blocks.jsonl, each without its `outcomes` field, which is dropped here and never read."""
    events, bad = read_jsonl(folder / 'blocks.jsonl')
    for event in events:
        event.pop('outcomes', None)
    return events, bad


def run_record(path):
    """What the watcher keeps of one run record: whether the run is finished and its vendor-error count. Nothing else of the record
    (its outcome, score, submission or reason) leaves this function."""
    record = read_json(path)
    if record is None:
        return None
    return {'finished': record.get('outcome') in TERMINAL, 'vendorErrors': int(record.get('vendorErrors') or 0),
            'requeued': bool(record.get('requeued'))}


# ---------------------------------------------------------------------------------------------------------------- the state of a run
def parse_time(text):
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def run_key(arm, task, model, suffix):
    """The run key of a scheduled run, as study/harness/schedule.py `run_key` builds it."""
    return '%s__%s__%s__%s' % (arm, task, model, suffix)


class Ledger:
    """One vendor ledger, read whole: the settled usage, the open reservations, the retries and notes, and the cost per run key."""

    def __init__(self, path, price_of_run):
        entries, self.unreadable = read_jsonl(path)
        self.spent, self.retries, self.notes, self.per_run, self.settled = Usage(), 0, {}, {}, 0
        reserved, self.dollars = {}, 0.0
        for entry in entries:
            event, seq = entry.get('event'), entry.get('seq')
            if event == 'reserve':
                reserved[seq] = entry
            elif event == 'settle':
                opened = reserved.pop(seq, None) or {}
                usage = Usage.from_dict(entry.get('usage') or {})
                price = price_of_run(opened.get('run'))
                cost = dollars(usage, price)
                self.spent.add(usage)
                self.dollars += cost
                self.settled += 1
                if opened.get('run'):
                    self.per_run.setdefault(opened['run'], []).append((parse_time(entry.get('ts')), cost))
                if entry.get('retry'):
                    self.retries += 1
                if entry.get('note'):
                    self.notes[entry['note']] = self.notes.get(entry['note'], 0) + 1
            elif event == 'release':
                reserved.pop(seq, None)
        self.open = list(reserved.values())
        self.open_tokens = sum(int(entry.get('tokens') or 0) for entry in self.open)
        self.open_dollars = sum(int(entry.get('tokens') or 0) * price_of_run(entry.get('run'))['output'] / 1_000_000 for entry in self.open)

    @property
    def counted_dollars(self):
        """The settled usage at its prices and every open reservation at the output price (budget.py `ledger_dollars`)."""
        return self.dollars + self.open_dollars

    @property
    def tokens(self):
        return self.spent.total + self.open_tokens


class RunState:
    """Everything a report needs, read from the folder in one pass. `None` from `read` means there is no manifest yet. bundle.json is
    never opened: its listing gives the time it was written."""

    @classmethod
    def read(cls, folder):
        if listed(folder, 'manifest.json') is None:
            return None
        return cls(folder, read_json(folder / 'manifest.json'))

    def __init__(self, folder, manifest):
        self.folder = folder
        self.run_id = manifest.get('studyRunId') or folder.name
        schedule = manifest.get('schedule')
        if not isinstance(schedule, dict) or not schedule.get('blocks'):
            raise ValueError('%s holds no block schedule: the watcher follows study-2 runs only' % (folder / 'manifest.json'))
        self.blocks = sorted(schedule['blocks'], key=lambda b: b['sequence'])
        self.models = {name: entry for name, entry in (manifest.get('models') or {}).items()}
        self.vendor_of = {name: entry.get('vendor') or (entry.get('priceEntry') or {}).get('vendor') for name, entry in self.models.items()}
        self.vendors = sorted({v for v in self.vendor_of.values() if v} | set((manifest.get('tokenBudgets') or {})))
        self.key_of = {}  # run key -> (block, arm, model)
        for block in self.blocks:
            for run in block['runs']:
                self.key_of[run_key(block['arm'], run['task'], run['model'], block['runSuffix'])] = (block, block['arm'], run['model'])
        self.budgets = {v: dict(b) for v, b in (manifest.get('tokenBudgets') or {}).items()}
        self.carried = {v: float(d) for v, d in ((manifest.get('budgetCarry') or {}).get('totals') or {}).items()}
        # bundle.json is listed before any log is read. The harness appends its last events before it writes the bundle, so a bundle
        # seen here comes with every event it follows; one written after this listing is seen at the next poll.
        self.bundle_listing = listing = listed(folder, 'bundle.json')
        self.bundle_written = datetime.fromtimestamp(listing[0] / 1e9, timezone.utc) if listing else None
        self.resumes, bad_resumes = read_jsonl(folder / 'resumes.jsonl')
        for entry in self.resumes:  # a resume may record other ceilings; the last one recorded holds
            for vendor, ceiling in (entry.get('ceilings') or {}).items():
                self.budgets.setdefault(vendor, {}).update({k: ceiling[k] for k in ('dollar_ceiling', 'ceiling_basis') if k in ceiling})
        self.events, bad_events = block_events(folder)
        health, bad_health = read_jsonl(folder / 'health.jsonl')
        self.health_checks, self.health_down = len(health), sum(1 for h in health if h.get('result') != 'up')
        self.requeues = manifest.get('vendorErrorRequeues')
        self.ledgers = {}
        for vendor in self.vendors:
            if any(self.vendor_of.get(m) == vendor and self.models[m].get('priceEntry') for m in self.models):
                self.ledgers[vendor] = Ledger(folder / ('budget-%s.jsonl' % vendor), self.price_of_run(vendor))
        self.stopped = self.is_stopped()
        # Only the records of a block whose current attempt has ended are read: from its end event on, the harness never replaces or
        # moves them again (run_block skips the block, and its settle_voids only reads them), whatever the harness does meanwhile. A
        # block that has not ended may be running, starting or resumed at any moment, so none of its files is opened.
        self.ended = self.ended_blocks()
        self.attempt_began = self.attempt_starts()
        self.records = {}
        for key, (block, _, _) in self.key_of.items():
            if block['id'] not in self.ended:
                continue
            record = run_record(folder / 'runs' / key / 'result.json')
            if record is not None:
                self.records[key] = record
        self.unreadable = (bad_resumes + bad_events + bad_health + sum(ledger.unreadable for ledger in self.ledgers.values()))

    def price_of_run(self, vendor):
        """The price entry of a ledger request: that of the model its run key names, else the vendor's model's."""
        default = next((self.models[m]['priceEntry'] for m in self.models if self.vendor_of.get(m) == vendor and self.models[m].get('priceEntry')),
                       None)

        def price(run):
            model = (self.key_of.get(run) or (None, None, None))[2]
            entry = self.models.get(model, {}).get('priceEntry') if model else None
            return entry or default
        return price

    # ------------------------------------------------------------ progress
    def attempts(self):
        """{block id: current attempt}: 1, and one more after every void event of the block."""
        current = {block['id']: 1 for block in self.blocks}
        for event in self.events:
            if event.get('event') == 'void' and event.get('block') in current:
                current[event['block']] += 1
        return current

    def ended_blocks(self):
        """{block id: (start time, end time)} of the blocks whose current attempt ended; the start is the attempt's last start before it."""
        attempts, starts, ended = self.attempts(), {}, {}
        for event in self.events:
            block, kind = event.get('block'), event.get('event')
            if kind == 'start':
                starts[(block, event.get('attempt'))] = parse_time(event.get('at'))
            elif kind == 'end' and attempts.get(block) == event.get('attempt'):
                ended[block] = (starts.get((block, event.get('attempt'))), parse_time(event.get('at')))
        return ended

    def current_block(self):
        """(block, attempt, started at) of the block started last with no end, void or stop after its start, or None."""
        current = None
        for event in self.events:
            kind = event.get('event')
            if kind == 'start':
                current = (event.get('block'), event.get('attempt'), parse_time(event.get('at')))
            elif kind in REPORT_EVENTS and current and event.get('block') == current[0]:
                current = None
        return current

    def is_stopped(self):
        """True when bundle.json was written after the last block event and the last resume: the harness has stopped writing."""
        written = self.bundle_written
        if written is None:
            return False
        times = [parse_time(e.get('at')) for e in self.events] + [parse_time(r.get('at')) for r in self.resumes]
        return all(moment is None or moment <= written for moment in times)

    def stop_status(self):
        """Why the harness stopped, from the events (bundle.json itself is never opened): complete, block_void, budget_stop or stopped."""
        if len(self.ended) == len(self.blocks):
            return 'complete'
        last = self.events[-1].get('event') if self.events else None
        return {'void': 'block_void', 'stopped': 'budget_stop'}.get(last, 'stopped')

    def attempt_starts(self):
        """{block id: time of the first start of its current attempt}, for the blocks whose current attempt has started."""
        attempts, out = self.attempts(), {}
        for event in self.events:
            if event.get('event') == 'start' and attempts.get(event.get('block')) == event.get('attempt'):
                out.setdefault(event['block'], parse_time(event.get('at')))
        return out

    def spent_on(self, key):
        """What the ledger has settled for a run key since its block's current attempt began, in dollars. A void attempt's spend, and
        spend before the attempt's first start, is not this run's."""
        block = self.key_of[key][0]['id']
        began = self.attempt_began.get(block)
        vendor = self.vendor_of.get(self.key_of[key][2])
        if began is None or vendor not in self.ledgers:
            return 0.0
        return sum(cost for moment, cost in self.ledgers[vendor].per_run.get(key, []) if moment is not None and moment >= began)

    def unread_blocks(self):
        """[(block, runs with spend)] of the blocks not ended that have begun (a start event or spend in the ledger): their runs are not
        counted, because their records are not read until they end."""
        started = {e.get('block') for e in self.events if e.get('event') == 'start'}
        out = []
        for block in self.blocks:
            if block['id'] in self.ended:
                continue
            spent = sum(1 for key, (b, _, _) in self.key_of.items() if b['id'] == block['id'] and self.spent_on(key) > 0)
            if spent or block['id'] in started:
                out.append((block, spent))
        return out

    def finished(self, key):
        record = self.records.get(key)
        return bool(record and record['finished'])

    def first_start(self):
        return next((parse_time(e.get('at')) for e in self.events if e.get('event') == 'start'), None)

    def last_resume(self):
        return parse_time(self.resumes[-1].get('at')) if self.resumes else None

    def running_block(self):
        """(block, attempt, started at) of the block running now, as the report's `now` line reads it, or None: the harness has not
        stopped, and no resume came after the block's start."""
        current, last_resume = self.current_block(), self.last_resume()
        if self.stopped or not current or current[0] not in {b['id'] for b in self.blocks}:
            return None
        if last_resume and current[2] and last_resume > current[2]:
            return None
        return current

    def last_starts(self):
        """{(block id, attempt): (time, runsFinishedBefore)} of the last start event of every attempt."""
        out = {}
        for event in self.events:
            if event.get('event') == 'start':
                out[(event.get('block'), event.get('attempt'))] = (parse_time(event.get('at')), int(event.get('runsFinishedBefore') or 0))
        return out


# ---------------------------------------------------------------------------------------------------------------- the report
def money(value):
    return '%.2f' % value


def span(seconds):
    if seconds is None:
        return '-'
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return '%dh%02dm' % (hours, minutes) if hours else '%dm%02ds' % (minutes, secs)


def local(moment, zone=None):
    """The moment in `zone`, or in the machine's local time zone when `zone` is None. Only the display is local: the records stay UTC."""
    return moment.astimezone(zone) if zone is not None else moment.astimezone()


def clock(moment, zone=None):
    """A moment as the report prints it: local date and time, with no zone (the header names it once)."""
    return local(moment, zone).strftime('%Y-%m-%d %H:%M:%S') if moment else '-'


def zone_name(moment, zone=None):
    """A short name of the local time zone at that moment, in ASCII: the zone's own abbreviation (EST), or the initials of a long name
    such as Windows gives (Eastern Standard Time), or the offset from UTC when the zone has no name."""
    moment = local(moment, zone)
    name = (moment.tzname() or '').strip()
    if ' ' in name:
        name = ''.join(word[0] for word in name.split() if word[:1].isalpha()).upper()
    return name if name and name.isascii() else utc_offset(moment, zone)


def utc_offset(moment, zone=None):
    offset = int(local(moment, zone).utcoffset().total_seconds() // 60)
    return 'UTC%s%02d:%02d' % ('-' if offset < 0 else '+', abs(offset) // 60, abs(offset) % 60)


def time_left(state, now):
    """The estimate of the time left, one figure for the whole run, pooled over arms (decision E1 (a) of the Job study2_watch_eta,
    2026-11-06). Returns {'state': 'done'} when every block has ended, {'state': 'too early'} before a block has ended with runs in its
    last part, else the seconds left and the counts it rests on. The mean per run and per gap stay inside this function: they are not
    in its result and never printed."""
    if len(state.ended) == len(state.blocks):
        return {'state': 'done'}
    by_id, attempts, last = {b['id']: b for b in state.blocks}, state.attempts(), state.last_starts()
    # The run time: per ended block, from the last start of its current attempt to its end, and the runs done in that part. An earlier
    # part that a stop cut off has no end event and is left out with its runs, and a void attempt counts neither time nor runs.
    run_seconds, runs, blocks_used = 0.0, 0, 0
    for block_id, (_, end) in state.ended.items():
        start = last.get((block_id, attempts[block_id]))
        done = len(by_id[block_id]['runs']) - (start[1] if start else 0)
        if not start or start[0] is None or end is None or done <= 0:
            continue
        run_seconds, runs, blocks_used = run_seconds + (end - start[0]).total_seconds(), runs + done, blocks_used + 1
    if not runs:
        return {'state': 'too early'}
    per_run = run_seconds / runs
    # The setup between blocks: an end followed by the next start (the teardown, then the next stack's start), left out when a resume
    # lies in it, because then it holds a stop and a wait for the operator.
    resumes = [moment for moment in (parse_time(r.get('at')) for r in state.resumes) if moment]
    gaps, previous = [], None
    for event in state.events:
        if event.get('event') == 'start' and previous is not None and previous.get('event') == 'end':
            ended_at, started_at = parse_time(previous.get('at')), parse_time(event.get('at'))
            if ended_at and started_at and started_at >= ended_at and not any(ended_at < r <= started_at for r in resumes):
                gaps.append((started_at - ended_at).total_seconds())
        previous = event
    per_gap = sum(gaps) / len(gaps) if gaps else 0.0
    running = state.running_block()
    seconds, runs_left, starts_left = 0.0, 0, 0
    for block in state.blocks:
        if block['id'] in state.ended:
            continue
        start = last.get((block['id'], attempts[block['id']]))
        left = max(0, len(block['runs']) - (start[1] if start else 0))  # a void's repeat has a new attempt: its runs count again
        runs_left += left
        if running and running[0] == block['id'] and running[1] == attempts[block['id']]:
            ran = (now - running[2]).total_seconds() if running[2] else 0.0
            seconds += max(0.0, per_run * left - ran)
        else:
            seconds += per_run * left
            starts_left += 1
    seconds += per_gap * starts_left
    return {'state': 'estimate', 'seconds': seconds, 'runs': runs, 'blocks': blocks_used, 'gaps': len(gaps), 'runs_left': runs_left,
            'starts_left': starts_left, 'stopped': state.stopped}


def finish_at(now, seconds, zone=None):
    """The expected end in local time: the time of day, with the date when it falls on another day."""
    end, today = local(now + timedelta(seconds=seconds), zone), local(now, zone)
    return end.strftime('%H:%M') if end.date() == today.date() else end.strftime('%Y-%m-%d %H:%M')


def time_left_text(estimate, now, zone=None):
    """The time left as one line of text, for both reports."""
    if estimate['state'] == 'done':
        return 'done'
    if estimate['state'] == 'too early':
        return 'too early (no block has ended yet)'
    left, end = span(estimate['seconds']), finish_at(now, estimate['seconds'], zone)
    if not estimate['gaps'] and estimate['starts_left']:
        # After the first block no gap between blocks is measured yet, and the setup before each block can take as long as a block.
        return 'about %s plus the setup before %d block(s), not measured yet; finish after %s%s' % (
            left, estimate['starts_left'], end, ' (the harness has stopped)' if estimate['stopped'] else '')
    if estimate['stopped']:
        return 'about %s once resumed (the harness has stopped; finish about %s if resumed now)' % (left, end)
    return 'about %s, finish about %s' % (left, end)


def projection(state):
    """{vendor: facts} of the estimate of the runs not finished yet, from this run's finished runs only."""
    by_arm_model, by_model = {}, {}
    for key, (_, arm, model) in state.key_of.items():
        if not state.finished(key):
            continue
        cost = state.spent_on(key)
        by_arm_model.setdefault((arm, model), []).append(cost)
        by_model.setdefault(model, []).append(cost)
    out = {v: {'left': 0, 'dollars': 0.0, 'low': 0.0, 'arm_model': 0, 'model_only': 0, 'too_early': 0, 'basis': {}, 'partly': 0}
           for v in state.vendors}
    for model, costs in by_model.items():
        vendor = state.vendor_of.get(model)
        if vendor in out:
            out[vendor]['basis'][model] = len(costs)
    for key, (_, arm, model) in state.key_of.items():
        if state.finished(key):
            continue
        facts = out.get(state.vendor_of.get(model))
        if facts is None:
            continue
        facts['left'] += 1
        if by_arm_model.get((arm, model)):
            costs, facts['arm_model'] = by_arm_model[(arm, model)], facts['arm_model'] + 1
        elif by_model.get(model):
            costs, facts['model_only'] = by_model[model], facts['model_only'] + 1
        else:
            facts['too_early'] += 1
            continue
        # A run of a block that has not ended and that has spend in the block's current attempt may be finished (a resume keeps a
        # stopped block's finished runs) or half done; its record is not read yet, so spend alone cannot tell. The estimate counts its
        # whole mean, and the low end of the range counts nothing for it.
        mean = sum(costs) / len(costs)
        facts['dollars'] += mean
        if state.spent_on(key) > 0:
            facts['partly'] += 1
        else:
            facts['low'] += mean
    return out


def report(state, now, reason, balances=None, spent_at_start=None, zone=None):
    """The full report (--verbose) as text. `balances` is {vendor: dollars} from the command line; `spent_at_start` is {vendor: dollars}
    at watcher start; `zone` is the time zone of the display, None for the machine's."""
    lines = ['== %s at %s %s, %s (%s) ==' % (state.run_id, clock(now, zone), zone_name(now, zone), utc_offset(now, zone), reason)]
    total_runs = len(state.key_of)
    finished = sum(1 for key in state.key_of if state.finished(key))
    ended = state.ended
    lines.append('Progress')
    unread = ''.join(' (block %s not counted until it ends, %d of its runs with spend in the ledger)' % (block['id'], spent)
                     for block, spent in state.unread_blocks())
    lines.append('  blocks ended %d of %d; runs finished %d of %d%s' % (len(ended), len(state.blocks), finished, total_runs, unread))
    by_id = {block['id']: block for block in state.blocks}
    current = state.current_block()
    last_resume = parse_time(state.resumes[-1].get('at')) if state.resumes else None
    last_event = parse_time(state.events[-1].get('at')) if state.events else None
    if state.stopped:
        lines.append('  now: no block running; the harness wrote bundle.json at %s (%s, from the events)'
                     % (clock(state.bundle_written, zone), state.stop_status()))
    elif current and current[0] in by_id and not (last_resume and current[2] and last_resume > current[2]):
        block = by_id[current[0]]
        lines.append('  now: block %s (sequence %s, arm %s, half %s, attempt %s) since %s'
                     % (block['id'], block.get('sequence', '?'), block['arm'], block.get('half') or '-', current[1],
                        clock(current[2], zone)))
    elif last_resume and (last_event is None or last_resume > last_event):
        lines.append('  now: a resume started at %s; no block has started since' % clock(last_resume, zone))
    elif state.events:
        lines.append('  now: no block running (last event: %s of block %s at %s)'
                     % (state.events[-1].get('event'), state.events[-1].get('block'), clock(last_event, zone)))
    else:
        lines.append('  now: no block has started yet')
    first = state.first_start()
    durations = [(end - start).total_seconds() for start, end in ended.values() if start and end]
    if first:
        until = state.bundle_written if state.stopped else now
        lines.append('  time: %s since the first block start; %s in ended blocks, %s per ended block on average'
                     % (span((until - first).total_seconds()), span(sum(durations)) if durations else '-',
                        span(sum(durations) / len(durations)) if durations else '-'))
    estimate = time_left(state, now)
    lines.append('  time left (an estimate, all arms pooled): %s' % time_left_text(estimate, now, zone))
    if estimate['state'] == 'estimate':
        lines.append('    based on %d run(s) in %d ended block(s) and %s; %d run(s) and %d block start(s) left'
                     % (estimate['runs'], estimate['blocks'],
                        '%d gap(s) between blocks, leaving out a gap that holds a resume' % estimate['gaps'] if estimate['gaps']
                        else 'no gap between blocks yet, so the setup before a block is not counted',
                        estimate['runs_left'], estimate['starts_left']))

    lines.append('Health')
    voids = [e for e in state.events if e.get('event') == 'void']
    if voids:
        for event in voids:
            problems = event.get('problems') or []
            first_problem = (': ' + str(problems[0])[:100]) if problems else ''
            lines.append('  void: block %s attempt %s, trigger %s at %s, %d problem(s)%s'
                         % (event.get('block'), event.get('attempt'), event.get('trigger'), event.get('point'), len(problems), first_problem))
    else:
        lines.append('  voids: none')
    stops = [e for e in state.events if e.get('event') == 'stopped']
    lines.append('  stops: ' + ('; '.join('%s in block %s at %s' % (e.get('reason'), e.get('block'), clock(parse_time(e.get('at')), zone))
                                         for e in stops) if stops else 'none'))
    for vendor in state.vendors:
        ledger = state.ledgers.get(vendor)
        if ledger is None:
            continue
        notes = ', '.join('"%s" x%d' % (note, count) for note, count in sorted(ledger.notes.items()))
        lines.append('  %s: %d requests settled, %d retried%s' % (vendor, ledger.settled, ledger.retries, ('; notes: ' + notes) if notes else ''))
    errors = sum(r['vendorErrors'] for r in state.records.values())
    requeued = sum(1 for r in state.records.values() if r['requeued'])
    lines.append('  vendor errors: %d attempt(s) ended on one; %d run(s) queued again (the manifest allows %s requeue per run)'
                 % (errors, requeued, state.requeues if state.requeues is not None else '?'))
    if state.resumes:
        last = state.resumes[-1]
        lines.append('  resumes: %d (last at %s, %s finished runs kept)' % (len(state.resumes), clock(parse_time(last.get('at')), zone),
                                                                           last.get('completedRunsKept', '?')))
    else:
        lines.append('  resumes: none')
    starts = {}
    for event in state.events:
        if event.get('event') == 'start':
            starts[(event.get('block'), event.get('attempt'))] = starts.get((event.get('block'), event.get('attempt')), 0) + 1
    again = ['%s attempt %s (%d starts)' % (block, attempt, count) for (block, attempt), count in starts.items() if count > 1]
    if again:
        lines.append('  blocks started again within one attempt (a stop with no event, then a resume): ' + '; '.join(again))
    lines.append('  health checks: %d recorded, %d not up' % (state.health_checks, state.health_down))
    if state.unreadable:
        lines.append('  unreadable lines: %d (left out of this report)' % state.unreadable)

    lines.append("Spend (dollars at the manifest's prices)")
    for vendor in state.vendors:
        ledger = state.ledgers.get(vendor)
        budget = state.budgets.get(vendor, {})
        this_run = ledger.counted_dollars if ledger else 0.0
        carried = state.carried.get(vendor, 0.0)
        ceiling = budget.get('dollar_ceiling')
        line = '  %s: this run %s + carried %s = %s' % (vendor, money(this_run), money(carried), money(this_run + carried))
        if ceiling is not None:
            line += ' of ceiling %s, room %s' % (money(float(ceiling)), money(float(ceiling) - this_run - carried))
        if ledger and budget.get('tokens'):
            line += '; tokens %s of %s' % (format(ledger.tokens, ','), format(int(budget['tokens']), ','))
        lines.append(line)
        if ledger and ledger.open:
            lines.append('    open reservations: %d (%s tokens), counted at the output price: %s'
                         % (len(ledger.open), format(ledger.open_tokens, ','), money(ledger.open_dollars)))

    lines.append('Estimate of the rest (an estimate, from this run\'s finished runs only)')
    estimate = projection(state)
    for vendor in state.vendors:
        facts = estimate[vendor]
        ledger = state.ledgers.get(vendor)
        so_far = (ledger.counted_dollars if ledger else 0.0) + state.carried.get(vendor, 0.0)
        ceiling = state.budgets.get(vendor, {}).get('dollar_ceiling')
        if not facts['left']:
            lines.append('  %s: no run left' % vendor)
            continue
        line = '  %s: %d run(s) left, about %s' % (vendor, facts['left'], money(facts['dollars']))
        if facts['partly']:
            line += (' (%s if the %d run(s) with spend in a block not ended yet are finished already)'
                     % (money(facts['low']), facts['partly']))
        if facts['too_early']:
            line += ' for %d of them; too early for %d (no finished run of their model yet)' % (facts['left'] - facts['too_early'],
                                                                                              facts['too_early'])
        if ceiling is not None:
            line += '; total about %s of ceiling %s, room after about %s' % (money(so_far + facts['dollars']), money(float(ceiling)),
                                                                             money(float(ceiling) - so_far - facts['dollars']))
        lines.append(line)
        basis = ', '.join('%d finished run(s) of %s' % (count, model) for model, count in sorted(facts['basis'].items()))
        lines.append('    based on %s; %d run(s) priced by their arm and model, %d by their model alone'
                     % (basis or 'no finished run', facts['arm_model'], facts['model_only']))

    if balances:
        lines.append('Balances (given on the command line when the watcher started; never stored)')
        for vendor, balance in sorted(balances.items()):
            # Settled spend since the start, apart from what open reservations may still cost: a reservation open at the start is in
            # neither the balance nor the baseline, so its settlement counts as spent since, and the allowance never lowers the baseline.
            ledger = state.ledgers.get(vendor)
            settled = ledger.dollars if ledger else 0.0
            since = settled - (spent_at_start or {}).get(vendor, settled)
            held = ledger.open_dollars if ledger else 0.0
            room = balance - since - held
            line = '  %s: %s - %s spent since%s = %s room' % (vendor, money(balance), money(since),
                                                              (' - %s held by open reservations at the output price' % money(held))
                                                              if held else '', money(room))
            facts = estimate.get(vendor)
            if facts and facts['left']:
                line += '; after the estimated rest about %s' % money(room - facts['dollars'])
                if facts['too_early']:
                    line += ' (%d run(s) too early to count)' % facts['too_early']
            lines.append(line)
    return '\n'.join(lines) + '\n'


VENDOR_NAMES = {'anthropic': 'Anthropic', 'openai': 'OpenAI'}
BAR = 16  # characters of the progress bar


def dollars_text(value):
    return '%s$%.2f' % ('-' if value < -0.005 else '', abs(value))


def health_lines(state, zone=None):
    """The compact report's health: one line per kind of event that happened, marked `!`, worded as the full report words them; none
    when the run is clear. Resumes are not an event here: the caller counts them."""
    out = []
    voids = [e for e in state.events if e.get('event') == 'void']
    if voids:
        out.append('voids: ' + '; '.join('block %s attempt %s, trigger %s at %s, %d problem(s)%s'
                                         % (e.get('block'), e.get('attempt'), e.get('trigger'), e.get('point'),
                                            len(e.get('problems') or []), (': ' + str(e['problems'][0])[:100]) if e.get('problems') else '')
                                         for e in voids))
    stops = ['%s in block %s at %s' % (e.get('reason'), e.get('block'), clock(parse_time(e.get('at')), zone))
             for e in state.events if e.get('event') == 'stopped']
    if stops:
        out.append('stops: ' + '; '.join(stops))
    starts = {}
    for event in state.events:
        if event.get('event') == 'start':
            starts[(event.get('block'), event.get('attempt'))] = starts.get((event.get('block'), event.get('attempt')), 0) + 1
    again = ['%s attempt %s (%d starts)' % (block, attempt, count) for (block, attempt), count in starts.items() if count > 1]
    if again:  # a line of its own, as in the full report, which says "stops: none" beside it
        out.append('blocks started again within one attempt (a stop with no event, then a resume): ' + '; '.join(again))
    retried = []
    for vendor in state.vendors:
        ledger = state.ledgers.get(vendor)
        if ledger and (ledger.retries or ledger.notes):
            notes = ', '.join('"%s" x%d' % (note, count) for note, count in sorted(ledger.notes.items()))
            retried.append('%s: %d requests settled, %d retried%s'
                           % (vendor, ledger.settled, ledger.retries, ('; notes: ' + notes) if notes else ''))
    if retried:
        out.append('retries: ' + '; '.join(retried))
    errors = sum(r['vendorErrors'] for r in state.records.values())
    requeued = sum(1 for r in state.records.values() if r['requeued'])
    if errors or requeued:
        out.append('vendor errors: %d attempt(s) ended on one; %d run(s) queued again' % (errors, requeued))
    if state.unreadable:
        out.append('unreadable lines: %d (left out of this report)' % state.unreadable)
    return out


def situation(state):
    """Where the run stands, for the compact header."""
    total, ended = len(state.blocks), len(state.ended)
    if state.stopped and state.stop_status() == 'complete':
        return 'ended, all %d blocks' % total
    last_end = next((e.get('block') for e in reversed(state.events) if e.get('event') == 'end' and e.get('block') in state.ended), None)
    text = 'after block %d of %d (%s)' % (ended, total, last_end) if ended else 'no block ended yet'
    running, last_resume = state.running_block(), state.last_resume()
    last_event = parse_time(state.events[-1].get('at')) if state.events else None
    if state.stopped:
        text += ', stopped (%s)' % state.stop_status()
    elif running:
        text += ', block %s running' % running[0]
    elif last_resume and (last_event is None or last_resume > last_event):
        text += ', resumed'
    return text


def compact(state, now, balances=None, spent_at_start=None, zone=None):
    """The compact report (the default) as text: the header, progress, time left, money and health, and nothing else (decision E3 of
    the Job study2_watch_eta, 2026-11-06). The header gives the zone's short name with its offset from UTC, because a short name taken
    from the initials of a long Windows name can mislead (W. Europe Standard Time gives WEST, a summer abbreviation, in winter)."""
    label = 11  # the width of the first column
    lines = ['%s   %s %s (%s)   %s' % (state.run_id, local(now, zone).strftime('%H:%M'), zone_name(now, zone), utc_offset(now, zone),
                                       situation(state)), '']
    total = len(state.key_of)
    finished = sum(1 for key in state.key_of if state.finished(key))
    filled = int(round(BAR * finished / total)) if total else 0
    first = state.first_start()
    so_far = span(((state.bundle_written if state.stopped else now) - first).total_seconds()) + ' so far' if first else 'not started'
    lines.append('  %s[%s]  %d of %d runs    %s' % ('Progress'.ljust(label), '#' * filled + '.' * (BAR - filled), finished, total, so_far))
    lines.append('  %s%s' % ('Time left'.ljust(label), time_left_text(time_left(state, now), now, zone)))
    lines.append('')

    estimate = projection(state)
    headers = ['spent', 'room (ceiling)'] + (['room (balance)'] if balances else []) + ['rest, est.', 'left after']
    rows = []
    for vendor in state.vendors:
        ledger = state.ledgers.get(vendor)
        spent = ledger.counted_dollars if ledger else 0.0
        ceiling = state.budgets.get(vendor, {}).get('dollar_ceiling')
        rooms = []
        row = [dollars_text(spent)]
        if ceiling is not None:
            rooms.append(float(ceiling) - state.carried.get(vendor, 0.0) - spent)
            row.append(dollars_text(rooms[-1]))
        else:
            row.append('-')
        if balances:
            if vendor in balances:
                settled = ledger.dollars if ledger else 0.0  # as the full report's balances count it
                since = settled - (spent_at_start or {}).get(vendor, settled)
                rooms.append(balances[vendor] - since - (ledger.open_dollars if ledger else 0.0))
                row.append(dollars_text(rooms[-1]))
            else:
                row.append('-')
        facts = estimate[vendor]
        if facts['too_early']:
            row += ['too early', '-']
        else:
            row += [dollars_text(facts['dollars']), dollars_text(min(rooms) - facts['dollars']) if rooms else '-']
        rows.append([VENDOR_NAMES.get(vendor, vendor.capitalize())] + row)
    first_width = max([label] + [len(row[0]) + 2 for row in rows])
    widths = [max([len(h)] + [len(row[i + 1]) for row in rows]) for i, h in enumerate(headers)]
    lines.append('  ' + 'Money'.ljust(first_width) + '   '.join(h.rjust(w) for h, w in zip(headers, widths)))
    for row in rows:
        lines.append('  ' + row[0].ljust(first_width) + '   '.join(v.rjust(w) for v, w in zip(row[1:], widths)))
    lines.append('')

    events = health_lines(state, zone)
    resumes = len(state.resumes)
    counted = '%d resume%s' % (resumes, '' if resumes == 1 else 's')
    if not events:
        lines.append('  %sall clear%s' % ('Health'.ljust(label), (' (%s)' % counted) if resumes else ''))
    else:
        for n, event in enumerate(events):
            lines.append('  %s! %s' % (('Health' if n == 0 else '').ljust(label), event))
        if resumes:
            lines.append('  %s(%s)' % (''.ljust(label), counted))
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------------------------------------------- following
def signature_of(events, resumes, bundle_listing):
    return {'events': [(e.get('event'), e.get('block'), e.get('attempt'), e.get('at')) for e in events if e.get('event') in REPORT_EVENTS],
            'resumes': len(resumes), 'bundle': bundle_listing}


def signature(folder):
    """What the follow loop compares between polls: the report events of blocks.jsonl, the number of resumes and the listing of
    bundle.json. Only appended files are read; bundle.json is not opened. It is listed first, as in RunState."""
    bundle = listed(folder, 'bundle.json')
    events, _ = block_events(folder)
    resumes, _ = read_jsonl(folder / 'resumes.jsonl')
    return signature_of(events, resumes, bundle)


def state_signature(state):
    """The signature of what a report was made from: the baseline of the next poll is always the state that was reported, so a write
    between two reads is seen at the next poll and never taken as seen."""
    return signature_of(state.events, state.resumes, state.bundle_listing)


def reason_of(before, after):
    if after['resumes'] > before['resumes']:
        return 'a resume started'
    new = after['events'][len(before['events']):]
    if new:
        kind, block, _, _ = new[-1]
        return {'end': 'the end of block %s', 'void': 'a void of block %s', 'stopped': 'a stop in block %s'}[kind] % block
    return 'a change'


def follow(folder, out, interval=DEFAULT_INTERVAL, once=False, balances=None, polls=None, sleep=time.sleep,
           now=lambda: datetime.now(timezone.utc), verbose=False, zone=None):
    """Print the reports, compact or full (`verbose`); returns the exit code. `polls` bounds the number of polls (for tests); None
    follows until the run stops. `sleep` is called with `interval` between polls. `zone` is the time zone of the display, None for the
    machine's local one."""
    def render(state, reason):
        if verbose:
            return report(state, now(), reason, balances, spent_at_start, zone)
        return compact(state, now(), balances, spent_at_start, zone)

    def write(text):
        out.write(text)
        out.flush()

    state = RunState.read(folder)
    while state is None:
        write('No manifest.json in %s yet: the run has not started.\n' % folder)
        if once or polls == 0:
            return 0
        sleep(interval)
        polls = None if polls is None else polls - 1
        state = RunState.read(folder)
    unknown = sorted(set(balances or {}) - set(state.vendors))
    if unknown:
        write('No such vendor in the manifest: %s (it has %s)\n' % (', '.join(unknown), ', '.join(state.vendors)))
        return 2
    seen = state_signature(state)
    spent_at_start = {v: ledger.dollars for v, ledger in state.ledgers.items()}  # settled only: see the balances
    write(render(state, 'watcher start'))
    if once or (state.stopped and state.stop_status() == 'complete'):
        return 0
    while polls is None or polls > 0:
        sleep(interval)
        polls = None if polls is None else polls - 1
        if signature(folder) == seen:
            continue
        state = RunState.read(folder)
        current = state_signature(state)
        bundle_written = current['bundle'] is not None and current['bundle'] != seen['bundle']
        reason = ('the harness wrote bundle.json (%s)' % state.stop_status() if bundle_written and state.stopped
                  else reason_of(seen, current))
        seen = current
        write('\n' + render(state, reason))
        if bundle_written and state.stopped:
            return 0
    return 0


def parse_balance(text):
    vendor, sep, amount = text.partition('=')
    try:
        value = float(amount)
    except ValueError:
        value = None
    if not sep or not vendor.strip() or value is None or value < 0:
        raise argparse.ArgumentTypeError('a balance is <vendor>=<dollars>, for example anthropic=60.00; got %r' % text)
    return vendor.strip(), value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Watch a study-2 run folder, read only: progress, health, spend, room and an estimate of '
                                                 'the rest, never an outcome.')
    parser.add_argument('folder', type=Path, help='the run folder, LAB_RESULTS_DIR/<study run id>')
    parser.add_argument('--once', action='store_true', help='print one report and end')
    parser.add_argument('--verbose', action='store_true', help='print the full report instead of the compact one')
    parser.add_argument('--interval', type=float, default=DEFAULT_INTERVAL, help='seconds between two reads of the folder (default 15)')
    parser.add_argument('--balance', action='append', type=parse_balance, default=[], metavar='VENDOR=DOLLARS',
                        help='an account balance as read now, for the room under it; repeat per vendor; never stored')
    parser.add_argument('--polls', type=int, default=None, help=argparse.SUPPRESS)  # for tests: stop after this many polls
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error('--interval must be a positive number of seconds')
    balances = dict(args.balance)
    try:
        return follow(args.folder, sys.stdout, interval=args.interval, once=args.once, balances=balances, polls=args.polls,
                      verbose=args.verbose)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
