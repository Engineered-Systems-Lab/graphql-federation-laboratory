"""The study-3 analysis: every table and figure of the plan (PLAN.md), from a verified copy of a study-3 bundle.

    python -B study/analysis3/analyze3.py --bundle <copy of the run folder> --sums <SHA256SUMS file> --bundle-checksum <sha256>
        --corpus-dir <the corpus the bundle ran> --out <new folder outside the repository> [--run-id study-3] [--replicates 10000]
        [--study2-scores study/evidence/study-2/scores.csv]

The copy is verified first; any difference stops the run with STOP and exit code 2 before a number is computed, and nothing is written. An
unusable fit does not stop the run: each family switches to its prespecified fallback (stats3.confirmatory), and a family that cannot be
estimated either way is reported as not estimable. The run writes results.json, tables.md and figures/effort.svg into --out, which must be
outside the repository and must not exist yet. The same inputs give the same bytes. The tiers stay apart in every output: confirmatory,
sensitivity, descriptive and exploratory.
"""
import argparse
import csv
import json
import math
import re
import shlex
import statistics
import sys
from pathlib import Path

import data3
import stats3
import analyze2  # study 2's descriptive and exploratory tables, read-only (on the path through data3)
import stats2
import svg  # study 1's figures, read-only

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ARMS = data3.SQUARE_ARMS
NAMES = data3.ARM_NAMES
OUTCOME_NAMES = {'toolCalls': '1 + tool calls per run', 'cost': 'cost per run (USD)'}
GROUP_NAMES = {'forward': 'forward', 'reverse': 'reverse', 'one': 'one system', 'several': 'several systems'}
# The labels of the verified facts in `inputs` (PLAN.md, section 1), in the order tables.md prints them.
BUNDLE_LABELS = {'run': 'run', 'files': 'files in the copy, each checked against the sums', 'bundleChecksum': 'bundle checksum (recomputed, equal to the one given)',
                 'writtenAt': 'bundle written at', 'sumsFile': 'sums file', 'sumsFileSha256': 'SHA-256 of the sums file',
                 'scoringContract': 'scorer contract version', 'scorerSha256': "scorer's SHA-256", 'corpusFreeze': "manifest's corpus hash",
                 'harnessCommit': 'harness commit', 'treeDirty': 'harness tree dirty', 'planHash': "manifest's run plan hash (planHash)"}
CORPUS_LABELS = {'corpusFreeze': 'corpus hash (SHA-256 of the corpus manifest)', 'tasksJsonSha256': 'SHA-256 of tasks.json', 'tasks': 'tasks'}
# The labels of `counting` (PLAN.md, section 3): study 2's, with study 3's words for the runs that enter the families and for Direct Access.
COUNTING_LABELS = dict(analyze2.COUNTING_LABELS, primary='core runs of the four full arms in the confirmatory analyses (vendor errors left out)',
                       primaryVendorErrorsMissing='vendor errors there, missing',
                       directAccess='runs of Direct Access (descriptive and exploratory, outside the confirmatory families)')
ZERO_COST_LABELS = {'runsWithZeroCost': 'scored runs with a zero cost', 'replacedBy': 'the cost they were given instead (USD, the smallest positive cost)'}
r6 = analyze2.r6
# Study 3's own tiers for study 2's secondary measures (PLAN.md, section 10; D069): time per run on P1 and P2 is descriptive, with
# intervals and no p-value; everything else of the block is exploratory, with its unadjusted p-values.
EXPLORATORY = 'exploratory: unadjusted p-values, outside the Holm families, no confirmatory claim (PLAN.md, section 10)'
TIME_TIER = ('descriptive: time per run of federation, Apollo and Cosmo weighted equally, over GraphQL Adapters (P1) and over Guided Direct Access (P2), '
             'ratios of geometric means with 95 percent intervals, no p-value and no claim (D069; PLAN.md, section 10)')
NO_P_EXPLORATORY = 'exploratory: no p-value, no confirmatory claim (PLAN.md, section 10)'
TIME_COMPARISONS = ('P1', 'P2')
FIGURE_TITLE = 'Confirmatory: federation over each comparison arm'
# Study 3's words for federation in the comparison labels it prints: stats3.COMPARISONS and study 2's analyze2.PLANNED say "mean of Apollo
# and Cosmo", which can read as an average of raw times or tool calls; the outputs say how the two arms are weighted instead.
LABEL_PHRASE = ('mean of Apollo and Cosmo', 'Apollo and Cosmo weighted equally')


def relabel(value):
    """The results with every comparison label (a `label` value) saying LABEL_PHRASE's second text in place of its first; nothing else
    changes, and the labels of stats3.py and analyze2.py stay as they are."""
    if isinstance(value, dict):
        return {k: v.replace(*LABEL_PHRASE) if k == 'label' and isinstance(v, str) else relabel(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relabel(v) for v in value]
    return value


def measures(rows, models, conditions):
    """Study 2's secondary measures (cost, time and tool calls, on all runs and on correct runs only) under study 3's tiers: the time ratios
    on P1 and P2 move, without their p-values, to `timeOnP1AndP2`, descriptive; cost, tool calls and the rest of time stay exploratory.
    No figure, interval or p-value changes."""
    out = analyze2.measures(rows, models, conditions)
    del out['tier']
    for outcome in analyze2.MEASURES:
        out[outcome]['tier'] = EXPLORATORY
    time = {'tier': TIME_TIER}
    for subset in ('allRuns', 'correctOnly'):
        entry = out['seconds'][subset]
        if not entry.get('estimable'):
            time[subset] = {'estimable': False, 'reason': entry.get('reason')}
            continue
        time[subset] = {'estimable': True, 'observations': entry['observations'], 'scale': entry['scale'],
                        'ratios': [{k: v for k, v in r.items() if k != 'p'} for r in entry['ratios'] if r['id'] in TIME_COMPARISONS]}
        entry['ratios'] = [r for r in entry['ratios'] if r['id'] not in TIME_COMPARISONS]
    out['timeOnP1AndP2'] = time
    return out


def legacy_load(run_id):
    """Where the legacy load is reported: legacy3.py's command line for the run this analysis read (README), with its own placeholders.
    Every argument is quoted whole; a run id that starts with a hyphen is joined to its option with '=', so it is not read as an option; and
    the code span's delimiter is longer than any run of backticks in the command."""
    run = ('--run-id=%s' if run_id.startswith('-') else '--run-id %s') % shlex.quote(run_id)
    command = ("\"$STUDY_MCP_PYTHON\" -B study/analysis3/legacy3.py %s --bundle %s --sums %s "
               "--bundle-checksum '<sha256 of the bundle>' --corpus-dir study/corpus3 --legacy-dir '<copy of the state folder>/legacy-load' "
               "--out '<folder outside the repository>'"
               % (run, shlex.quote('<copy>/%s' % run_id), shlex.quote('<archive>/SHA256SUMS-%s.txt' % run_id)))
    fence = '`' * (1 + max((len(m) for m in re.findall('`+', command)), default=0))
    return 'Reported by legacy3.py, a separate command with its own inputs, not by this analysis (README): %s%s%s' % (fence, command, fence)


def fact(value):
    """A recorded fact as results.json holds it: true, false and null in its own words, everything else as written."""
    return json.dumps(value) if value is None or isinstance(value, bool) else str(value)
table = analyze2.table


def group_accuracy(rows):
    """A14: accuracy per arm in each CSL group, descriptive."""
    out = {}
    for field, levels in (('cslGroup', ('forward', 'reverse')), ('joinGroup', ('one', 'several'))):
        for level in levels:
            use = [r for r in rows if r.get(field) == level and r['correct'] is not None]
            out[level] = {'tasks': len({r['task'] for r in use}),
                          'byArm': {a: [sum(r['correct'] for r in use if r['arm'] == a), sum(1 for r in use if r['arm'] == a)] for a in ARMS}}
    return out


def sensitivity(planned, models, stratum_of, replicates):
    rows = [r for r in planned if r['correct'] is not None]
    conditions = stats2.planned_conditions(planned)
    rounds = stats3.planned_rounds(conditions)
    out = {'floorVendorErrorsAsWrong': {c: stats3.accuracy_floor(planned, c, models, stratum_of, replicates, vendor_errors_wrong=True, rounds=rounds)
                                        for _, c, _ in stats3.COMPARISONS},
           'biasReducedCovariance': {}, 'bootstrapOfTheRatios': {}, 'correctRunsOnly': {}}
    correct = [r for r in rows if r['correct'] == 1]
    for outcome in stats3.EFFORT_FAMILIES:
        for key, use, cov in (('biasReducedCovariance', rows, 'bias_reduced'), ('correctRunsOnly', correct, 'robust')):
            try:
                _, summaries = stats3.effort_gee(use, outcome, models, conditions, cov_type=cov)
                out[key][outcome] = {'estimable': True, 'comparisons': {cid: dict(s, ratio=math.exp(s['estimate']), ratioLow=math.exp(s['low']), ratioHigh=math.exp(s['high']))
                                                                        for cid, s in summaries.items()}}
            except stats3.FIT_ERRORS as error:
                out[key][outcome] = {'estimable': False, 'reason': '%s: %s' % (type(error).__name__, error)}
        boot = stats3.effort_fallback(rows, outcome, models, stratum_of, replicates, rounds=rounds)
        if boot['estimable']:
            boot['comparisons'] = {cid: dict(s, ratio=math.exp(s['estimate']), ratioLow=math.exp(s['low']), ratioHigh=math.exp(s['high']))
                                   for cid, s in boot['comparisons'].items()}
        out['bootstrapOfTheRatios'][outcome] = boot
    return out


def per_stratum(rows, models):
    """P1's tool-call ratio per task group, descriptive: the mean of the per-task contrasts of each anchor, csl kind, category and size,
    and of the forward aggregates, a group of their own (PLAN.md, section 10; D068, decision 1a): the core tasks of category E with direction
    forward. A group with no task that has a contrast is reported as not estimable."""
    contrasts = stats3.per_task_contrasts(rows, models)
    facts = {r['task']: r for r in rows}
    out = {}
    for field in ('anchor', 'csl', 'category', 'size'):
        groups = {}
        for task, value in contrasts.items():
            groups.setdefault(str(facts[task].get(field)), []).append(value)
        out[field] = {k: {'tasks': len(v), 'p1Ratio': math.exp(statistics.fmean(v))} for k, v in sorted(groups.items())}
    forward = [value for task, value in sorted(contrasts.items()) if facts[task]['forwardAggregate']]
    out['forwardAggregates'] = ({'tasks': len(forward), 'p1Ratio': math.exp(statistics.fmean(forward))} if forward else
                                {'tasks': 0, 'estimable': False, 'reason': 'no forward aggregate has a complete set of runs'})
    return out


def study2_comparison(path, rows, models):
    """The tasks of study 2 that study 3 ran again: P1's tool-call ratio on those tasks in each study, exploratory."""
    if not path:
        return {'compared': False, 'reason': 'no --study2-scores given'}
    with open(path, encoding='utf-8', newline='') as handle:
        old = [{'task': r['taskId'], 'arm': r['scenario'], 'model': r['model'], 'row': r['row'], 'toolCalls': int(r['toolCalls'])}
               for r in csv.DictReader(handle) if r['scenario'] in ARMS and r['category'] != 'F']
    before = stats3.per_task_contrasts(old, sorted({r['model'] for r in old}))
    after = stats3.per_task_contrasts(rows, models)
    shared = sorted(set(before) & set(after))
    if not shared:
        return {'compared': False, 'reason': 'no task is in both studies'}
    return {'compared': True, 'tier': NO_P_EXPLORATORY, 'tasks': len(shared), 'study2P1Ratio': math.exp(statistics.fmean(before[t] for t in shared)),
            'study3P1Ratio': math.exp(statistics.fmean(after[t] for t in shared))}


def attempt(analysis, *args):
    """A descriptive or exploratory analysis that cannot be computed, for example with no usable run, is reported as not estimable, and
    every other output is still written. The confirmatory results do not pass through here: they have their own rules."""
    try:
        return analysis(*args)
    except stats3.FIT_ERRORS + (IndexError, KeyError, statistics.StatisticsError) as error:
        return {'estimable': False, 'reason': '%s: %s' % (type(error).__name__, error)}


def analyse(args):
    facts, corpus_facts, manifest, strata, records, blocks, zero = data3.load(args.bundle, args.sums, args.run_id, args.bundle_checksum, args.corpus_dir)
    models = sorted(manifest['models'])
    core = [r for r in records if r['set'] == 'core']
    square = [r for r in core if r['arm'] in ARMS]
    stratum_of = {t: e['direction'] for t, e in strata.items() if e['set'] == 'core'}
    rows = [r for r in square if r['correct'] is not None]
    conditions = stats2.planned_conditions(square)
    recorded = [dict(r, cost=r['costAsRecorded']) for r in records]
    return r6({
        'about': 'Abstraction ladder study 3 analysis under the plan study/analysis3/PLAN.md. Generated; do not edit.',
        'inputs': {'bundle': facts, 'corpus': corpus_facts},
        'plan': {'models': models, 'arms': {a: NAMES[a] for a in data3.ALL_ARMS}, 'seed': stats3.SEED, 'replicates': args.replicates,
                 'floorMarginPoints': 100 * stats3.FLOOR_MARGIN},
        'counting': dict(data3.data2.counting(records, blocks), zeroCost=zero),
        'confirmatory': stats3.confirmatory(square, models, stratum_of, args.replicates),
        'cslGroupAccuracy': {'tier': 'descriptive', 'groups': group_accuracy(square)},
        'sensitivity': sensitivity(square, models, stratum_of, args.replicates),
        'descriptive': {'cells': analyze2.cell_counts(core, data3.ALL_ARMS, models), 'outcomes': analyze2.outcome_table(core, data3.ALL_ARMS),
                        'measures': attempt(measures, square, models, conditions), 'perStratum': per_stratum(rows, models),
                        'spend': analyze2.spend(recorded, blocks), 'schedule': analyze2.schedule_facts(manifest, blocks),
                        'legacyLoad': {'status': legacy_load(args.run_id), 'measure': 'requests to Missions, Personnel and Assets per run and arm, descriptive, ratios with intervals'}},
        'exploratory': {'tables': attempt(analyze2.exploratory, records, models), 'honestGap': attempt(analyze2.honest_gap, square, models),
                        'study2Tasks': study2_comparison(args.study2_scores, rows, models)},
    })


# ------------------------------------------------------------------------------------------------------------------ outputs
def verdict(entry):
    if entry['claimed']:
        return 'claimed'
    if entry['rejected']:
        return 'significant, not claimed: the accuracy floor is not cleared'
    return 'not significant'


def time_heading():
    """The heading of tables.md's time section: the tier of `timeOnP1AndP2`, as results.json writes it, with a capital first letter."""
    return TIME_TIER[0].upper() + TIME_TIER[1:]


def tables_md(res):
    c = res['confirmatory']
    parts = ['# Abstraction ladder study 3: analysis tables', '', 'Generated by study/analysis3/analyze3.py from a verified copy of %s. Do not edit by hand.' % res['inputs']['bundle']['run'], '']
    bundle, corpus = res['inputs']['bundle'], res['inputs']['corpus']
    parts += ['## Inputs: the verification (PLAN.md, section 1)', '',
              'Every check of the plan passed before a number was computed; a failure stops the analysis and writes nothing. The facts as recorded:', '',
              table(['', 'Recorded'], [['bundle: %s' % label, fact(bundle[k])] for k, label in BUNDLE_LABELS.items()]
                    + [['corpus: %s' % label, fact(corpus[k])] for k, label in CORPUS_LABELS.items()]), '']
    counting = res['counting']
    parts += ['## Inputs: which runs count (PLAN.md, section 3)', '',
              table(['', 'Runs or blocks'], [[label, (', '.join(counting[k]) or 'none') if isinstance(counting[k], list) else fact(counting[k])]
                                             for k, label in COUNTING_LABELS.items()]
                    + [[label, 'none' if counting['zeroCost'][k] is None else fact(counting['zeroCost'][k])] for k, label in ZERO_COST_LABELS.items()]), '']
    rows = []
    for comparator, f in c['floors'].items():
        rows.append([NAMES[comparator], '%+.1f' % (100 * f['estimate']) if f['estimable'] else 'not estimable',
                     '%+.1f' % (100 * f['lower']) if f['estimable'] else '-', 'cleared' if f['cleared'] else 'not cleared'])
    parts += ['## Confirmatory: the accuracy floor (federation minus the arm, points; one-sided 0.025; margin -10)', '',
              table(['Against', 'Difference', 'Lower bound', 'Floor'], rows), '']
    for outcome, family in c['effort'].items():
        parts += ['## Confirmatory: %s (federation, Apollo and Cosmo weighted equally, over GraphQL Adapters (P1) and over Guided Direct Access (P2); '
                  'Holm over P1 and P2; method: %s)' % (OUTCOME_NAMES[outcome], family['method']), '']
        if family['method'] == 'notEstimable':
            parts += ['Not estimable: %s.' % '; '.join(family['problems']), '']
            continue
        if family['problems']:
            parts += ['The GEE could not be used: %s.' % '; '.join(family['problems']), '']
        parts += [table(['', 'Comparison', 'Ratio [95% CI]', 'p', 'p (Holm)', 'Result'],
                        [[e['id'], e['label'], '%.3f [%.3f, %.3f]' % (e['ratio'], e['low'], e['high']), '%.4f' % e['p'], '%.4f' % e['pHolm'], verdict(e)]
                         for e in family['comparisons']]), '']
    csl = c['csl']
    parts += ['## Confirmatory: the CSL family (tool calls of federation, Apollo and Cosmo weighted equally, over GraphQL Adapters (P1); one-sided 0.05; '
              'Holm over the two; method: %s)' % csl['method'], '']
    if csl['method'] == 'notEstimable':
        parts += ['Not estimable: %s.' % '; '.join(csl['problems']), '']
    else:
        parts += [table(['Test', 'Tasks', 'Difference of log ratios', 'One-sided 95% bound', 'p', 'p (Holm)', 'Result'],
                        [[t['label'], ', '.join('%s %d' % (GROUP_NAMES[k], v) for k, v in t['tasks'].items()), '%+.3f' % t['estimate'], '%+.3f' % t['bound'],
                          '%.4f' % t['p'], '%.4f' % t['pHolm'], verdict(t)] for t in csl['tests']]), '']
    groups = res['cslGroupAccuracy']['groups']
    parts += ['## Descriptive: accuracy in each CSL group', '',
              table(['Group', 'Tasks'] + [NAMES[a] for a in ARMS], [[GROUP_NAMES[k], v['tasks']] + ['%d/%d' % tuple(v['byArm'][a]) for a in ARMS] for k, v in groups.items()]), '']
    s = res['sensitivity']
    rows = [['Floor, vendor errors as wrong, against %s' % NAMES[k], 'lower bound %+.1f points' % (100 * v['lower']) if v['estimable'] else 'not estimable'] for k, v in s['floorVendorErrorsAsWrong'].items()]
    for key, name in (('biasReducedCovariance', 'bias-reduced covariance'), ('correctRunsOnly', 'correct runs only'), ('bootstrapOfTheRatios', 'bootstrap of the ratios')):
        for outcome, entry in s[key].items():
            text = ('; '.join('%s %.3f [%.3f, %.3f]' % (cid, v['ratio'], v['ratioLow'], v['ratioHigh']) for cid, v in entry['comparisons'].items())
                    if entry.get('estimable') else 'not estimable: %s' % entry.get('reason'))
            rows.append(['%s, %s' % (name, OUTCOME_NAMES[outcome]), text])
    parts += ['## Sensitivity', '', table(['Analysis', 'Result'], rows), '']
    measures_ = res['descriptive']['measures']
    block = measures_['timeOnP1AndP2']['allRuns'] if 'timeOnP1AndP2' in measures_ else measures_
    parts += ['## %s' % time_heading(), '', 'On all runs; results.json also holds them on correct runs only.', '']
    parts += [table(['', 'Comparison', 'Ratio [95% CI]'], [[r['id'], r['label'], '%.2f [%.2f, %.2f]' % (r['ratio'], r['low'], r['high'])] for r in block['ratios']]), '']\
        if block.get('estimable') else ['Not estimable: %s' % block.get('reason'), '']
    parts += ['## Descriptive: spend by arm (USD, prices of the manifest)', '',
              'Each run at its recorded cost: the zero-cost rule does not change the spend (PLAN.md, section 3).', '',
              table(['Arm', 'Counted runs', 'Archived attempts (operational only)', 'Void attempts (operational only)'],
                    [[NAMES[a], '%.6f' % v['countedRuns'], '%.6f' % v['archivedAttempts'], '%.6f' % v['voidAttempts']]
                     for a, v in ((a, res['descriptive']['spend'][a]) for a in data3.ALL_ARMS)]), '']
    parts += ['## Descriptive: legacy load', '', res['descriptive']['legacyLoad']['status'], '']
    return '\n'.join(parts) + '\n'


def figure(res):
    items = []
    for outcome, family in res['confirmatory']['effort'].items():
        items += [('%s %s' % (e['id'], OUTCOME_NAMES[outcome]), e['ratio'], e['low'], e['high'], 'confirmatory') for e in family['comparisons']]
    if not items:
        return None
    top = max(2.0, math.ceil(2 * max(i[3] for i in items)) / 2)
    ticks = [round(0.5 * k, 1) for k in range(int(2 * top) + 1)]
    return svg.interval_plot(FIGURE_TITLE, 'ratio of geometric means (95% interval); below 1 is less effort', items, 0, top, ticks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('--bundle', '--sums', '--bundle-checksum', '--corpus-dir', '--out'):
        parser.add_argument(name, required=True)
    parser.add_argument('--run-id', default='study-3')
    parser.add_argument('--replicates', type=int, default=stats3.REPLICATES)
    parser.add_argument('--study2-scores', default=None)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.resolve().is_relative_to(REPO.resolve()):
        parser.error('--out must be outside the repository: the outputs are generated')
    if out.exists():
        parser.error('--out must not exist yet: a file of an earlier run would stand beside the new outputs')
    try:
        res = relabel(analyse(args))
    except data3.VerificationError as error:
        print('STOP: %s' % error, file=sys.stderr)
        return 2
    picture = figure(res)
    (out / 'figures').mkdir(parents=True)
    (out / 'results.json').write_text(json.dumps(res, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    (out / 'tables.md').write_text(tables_md(res), encoding='utf-8', newline='\n')
    if picture:
        (out / 'figures' / 'effort.svg').write_text(picture, encoding='utf-8', newline='\n')
    print('analysis written to %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
