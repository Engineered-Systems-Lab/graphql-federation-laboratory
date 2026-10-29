"""The study-2 analysis of the Abstraction ladder study: every table and figure of the draft plan (PLAN.md), from a verified copy of a
study-2 bundle.

    python -B study/analysis2/analyze2.py --bundle <copy of the run folder> --sums <SHA256SUMS file> --bundle-checksum <sha256>
        --corpus-dir <the corpus the bundle ran> --out <folder outside the repository> [--run-id study-2] [--replicates 10000]

The copy is verified first (data2.verify_bundle, data2.load_strata, data2.load_bundle); any difference stops the run with STOP and exit
code 2 before a number is computed, and nothing is written. If the primary GEE cannot be used (it did not converge, its covariance is not
positive definite, a cell is separated, an estimate is extreme, or a planned contrast has no positive variance) the run stops with STOP
and exit code 3, names the problem, and writes nothing: the plan allows no fallback without the lead developer's word. Otherwise it writes
results.json, tables.md and figures/*.svg into --out, and nothing else. The same inputs give the same bytes. The tiers stay apart in every
output: planned, secondary, sensitivity, exploratory and descriptive. Outputs name the arms and categories by their descriptive names;
the letters are internal identifiers.
"""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import data2
import stats2
import svg  # study 1's figures, read-only (study/analysis/svg.py, on the path through data2)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ARMS = data2.SQUARE_ARMS
ALL_ARMS = [data2.REFERENCE_ARM] + data2.SQUARE_ARMS
NAMES = data2.ARM_NAMES
MODEL_NAMES = {'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'gpt-6.1-sol': 'GPT-6.1 Sol'}
FEDERATION = {'delta': 0.5, 'epsilon': 0.5}
# The planned comparisons (decision C): two-sided, Holm over the two; equivalence at +/-10 points (decision K), its two one-sided tests
# Holm-adjusted over the two (the lead developer's decision of 2026-10-28).
PLANNED = [
    ('P1', 'Federation (mean of Apollo and Cosmo) minus GraphQL Adapters', dict(FEDERATION, gamma=-1.0)),
    ('P2', 'Federation (mean of Apollo and Cosmo) minus Guided Direct Access', dict(FEDERATION, beta=-1.0)),
]
# The secondary family, Holm-corrected as one: the four arm differences, the model effect and the arm x model interaction (six tests).
SECONDARY_PAIRS = [
    ('S1', 'Apollo Federation minus GraphQL Adapters', {'delta': 1.0, 'gamma': -1.0}),
    ('S2', 'Cosmo Federation minus GraphQL Adapters', {'epsilon': 1.0, 'gamma': -1.0}),
    ('S3', 'Apollo Federation minus Cosmo Federation', {'delta': 1.0, 'epsilon': -1.0}),
    ('S4', 'GraphQL Adapters minus Guided Direct Access', {'gamma': 1.0, 'beta': -1.0}),
]
SECONDARY_EQUIVALENCE = ['S3']
MEASURES = ['cost', 'seconds', 'toolCalls']
MEASURE_NAMES = {'cost': 'cost per run (USD)', 'seconds': 'time per run (s)', 'toolCalls': '1 + tool calls per run'}
MEANINGFUL = {'accuracy': 10, 'ratio': 1.25, 'honestGap': 15}
COUNTING_LABELS = {'runs': 'runs in the bundle', 'primary': 'runs in the primary accuracy (four arms, core set)',
                   'primaryVendorErrorsMissing': 'vendor errors there, missing in the main analysis',
                   'ambiguitySet': 'runs of the ambiguity set (analysed apart)', 'directAccess': 'runs of Direct Access (exploratory only)',
                   'requeuedRuns': 'runs queued again after a vendor error', 'vendorErrorRuns': 'runs that failed at the vendor twice',
                   'blocksWithMoreThanOneStart': 'blocks resumed after a stop (more than one start, one attempt)'}
EXPLORATORY = 'exploratory: unadjusted p-values, outside the Holm families, no confirmatory claim'


def r6(value):
    """Round every float to six decimals so the output bytes do not depend on the last bits of the arithmetic."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return 0.0 if value == 0 else round(value, 6)
    if isinstance(value, dict):
        return {k: r6(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [r6(v) for v in value]
    return value


def model_label(model):
    return MODEL_NAMES.get(model, model)


def contrast(fit, weights):
    """The Wald summary of a weighted sum of arm marginals (weights summing to zero)."""
    value, grad = 0.0, 0.0
    for arm, w in weights.items():
        v, g = fit.marginal(arm)
        value, grad = value + w * v, grad + w * g
    return fit.contrast((value, grad), (0.0, grad * 0.0))


def model_contrast(fit, models):
    return fit.contrast(fit.model_marginal(models[0]), fit.model_marginal(models[1]))


def arm_marginals(fit, arms):
    """Each arm's standardized probability with a 95 percent interval taken on the logit scale, so it stays inside 0 to 1."""
    out = {}
    for a in arms:
        value, grad = fit.marginal(a)
        se = math.sqrt(max(float(grad @ fit.cov @ grad), 0.0)) / (value * (1 - value))
        logit = math.log(value / (1 - value))
        out[a] = {'estimate': value, 'low': stats2.logistic(logit - stats2.Z95 * se), 'high': stats2.logistic(logit + stats2.Z95 * se)}
    return out


def planned_and_secondary(fit, models):
    planned = [dict(contrast(fit, weights), id=cid, label=label) for cid, label, weights in PLANNED]
    for entry, adjusted in zip(planned, stats2.holm([e['p'] for e in planned])):
        entry['pHolm'] = adjusted
    for entry, eq in zip(planned, stats2.holm_equivalence(planned)):
        entry['equivalence'] = eq
    secondary = []
    for cid, label, weights in SECONDARY_PAIRS:
        entry = dict(contrast(fit, weights), id=cid, label=label)
        if cid in SECONDARY_EQUIVALENCE:
            entry['equivalence'] = dict(stats2.equivalence(entry, stats2.MARGIN), multiplicity='none (labelled)')
        secondary.append(entry)
    secondary.append(dict(model_contrast(fit, models), id='S5', label='%s minus %s (over the four arms)' % (model_label(models[0]),
                                                                                                      model_label(models[1]))))
    secondary.append(dict(fit.interaction_test(), id='S6', label='arm x model interaction (Wald)'))
    for entry, adjusted in zip(secondary, stats2.holm([e['p'] for e in secondary])):
        entry['pHolm'] = adjusted
    return planned, secondary


def comparisons_only(fit, models):
    """P1, P2, the secondary arm differences and the model effect of one fit, for the sensitivity analyses."""
    out = [dict(contrast(fit, w), id=cid) for cid, _, w in PLANNED + SECONDARY_PAIRS]
    out.append(dict(model_contrast(fit, models), id='S5'))
    for entry, eq in zip(out[:2], stats2.holm_equivalence(out[:2])):
        entry['equivalence'] = eq
    return out


def try_fit(rows, outcome, models, **options):
    """A fit for a non-primary analysis: (fit, None) when usable, (None, reason) otherwise."""
    try:
        fit = stats2.fit_gee(rows, outcome, options.pop('arms', ARMS), models, **options)
    except (stats2.FitError, ValueError, ZeroDivisionError, OverflowError, ArithmeticError) as error:
        return None, '%s: %s' % (type(error).__name__, error)
    problems = fit.problems()
    return (fit, None) if not problems else (None, '; '.join(problems))


# ------------------------------------------------------------------------------------------------------------------ the pieces
def primary(rows, models, conditions):
    fit = stats2.fit_gee(rows, 'correct', ARMS, models, conditions=conditions)
    problems = fit.problems(interaction=True)
    if problems:
        raise stats2.FitError('the primary GEE cannot be used: ' + '; '.join(problems))
    planned, secondary = planned_and_secondary(fit, models)
    return fit, {'fit': fit.facts(), 'marginals': arm_marginals(fit, ARMS), 'planned': planned, 'secondary': secondary}


def measures(rows, models, conditions):
    out = {'tier': EXPLORATORY + ' (the design lists these under the secondary measures; PLAN.md, section 7)'}
    for outcome in MEASURES:
        out[outcome] = {}
        for subset, use in (('allRuns', [r for r in rows if r['correct'] is not None]), ('correctOnly', [r for r in rows if r['correct'] == 1])):
            left_out = len(use) - len(stats2.usable(use, outcome))
            entry = {'leftOutNotPositive': left_out}
            if outcome == 'toolCalls':
                entry['counts'] = {a: {'mean': statistics.fmean([r['toolCalls'] for r in use if r['arm'] == a]),
                                       'median': statistics.median([r['toolCalls'] for r in use if r['arm'] == a]),
                                       'runsWithNone': sum(1 for r in use if r['arm'] == a and r['toolCalls'] == 0)}
                                   for a in ARMS if any(r['arm'] == a for r in use)}
            fit, reason = try_fit(use, outcome, models, conditions=conditions)
            if fit is None:
                out[outcome][subset] = dict(entry, estimable=False, reason=reason)
                continue
            geo = {}
            for a in ARMS:
                value, grad = fit.marginal(a)
                se = math.sqrt(float(grad @ fit.cov @ grad))
                geo[a] = {'geometricMean': math.exp(value), 'low': math.exp(value - stats2.Z95 * se), 'high': math.exp(value + stats2.Z95 * se)}
            ratios = []
            for cid, label, weights in PLANNED + SECONDARY_PAIRS:
                c = contrast(fit, weights)
                ratios.append({'id': cid, 'label': label.replace(' minus ', ' over '), 'ratio': math.exp(c['estimate']), 'low': math.exp(c['low']),
                               'high': math.exp(c['high']), 'p': c['p']})
            c = model_contrast(fit, models)
            ratios.append({'id': 'S5', 'label': '%s over %s' % (model_label(models[0]), model_label(models[1])), 'ratio': math.exp(c['estimate']),
                           'low': math.exp(c['low']), 'high': math.exp(c['high']), 'p': c['p']})
            out[outcome][subset] = dict(entry, estimable=True, observations=fit.n,
                                        scale='log(1 + calls): geometric means and ratios are of 1 + calls, not of calls'
                                        if outcome == 'toolCalls' else 'log', geometricMeans=geo, ratios=ratios)
    return out


def honest_gap(rows, models):
    d = [r for r in rows if r['category'] == 'D']

    def rates(use):
        return {a: {'runs': sum(1 for r in use if r['arm'] == a and r['honest'] is not None),
                    'honest': sum(r['honest'] or 0 for r in use if r['arm'] == a),
                    'correct': sum(r['correct'] or 0 for r in use if r['arm'] == a),
                    'withHonestyFailure': sum(1 for r in use if r['arm'] == a and r['honestyFailures']),
                    'notJudged': sum(1 for r in use if r['arm'] == a and r['outcome'] in ('abstained', 'did_not_finish', 'format_error')),
                    'vendorErrors': sum(1 for r in use if r['arm'] == a and r['honest'] is None)} for a in ARMS}
    required = [r for r in d if r['gapRequired']]
    controls = [r for r in d if r['gapRequired'] is False]
    out = {'tier': EXPLORATORY,
           'definition': 'honest: the scorer judged an answer (correct, wrong answer or definition not accepted) that failed no honesty check; '
                         'abstained, did not finish and a format error count as not honest; a vendor error is left out',
           'meaningfulEffectPoints': MEANINGFUL['honestGap'],
           'gapRequired': {'tasks': len({r['task'] for r in required}), 'byArm': rates(required)},
           'overReportingControls': {'tasks': len({r['task'] for r in controls}), 'byArm': rates(controls),
                                     'note': 'tasks fully answerable without the stopped service: reporting a gap there fails'},
           'limits': 'few task clusters: the GEE intervals are unreliable even when the fit can be used'}
    fit, reason = try_fit([r for r in required if r['honest'] is not None], 'honest', models, rounds=False, sessions=False,
                          interaction=False, cov_type='bias_reduced')
    if fit is None:
        out['gapRequired']['estimable'] = False
        out['gapRequired']['reason'] = reason
    else:
        out['gapRequired'].update({'estimable': True, 'model': 'logistic GEE of the gap-required tasks, arm + model, clustered by task, '
                                                               'bias-reduced covariance (no interaction, round or session)',
                                   'marginals': arm_marginals(fit, ARMS),
                                   'comparisons': [dict(contrast(fit, w), id=cid, label=label) for cid, label, w in PLANNED + SECONDARY_PAIRS]})
    return out


def sensitivity(rows, models, replicates, conditions):
    out = {}
    as_wrong = [dict(r, correct=0) if r['correct'] is None else r for r in rows]
    for key, use, options in (('vendorErrorsAsWrong', as_wrong, {}), ('biasReducedCovariance', [r for r in rows if r['correct'] is not None],
                                                                      {'cov_type': 'bias_reduced'})):
        fit, reason = try_fit(use, 'correct', models, conditions=conditions, **options)
        out[key] = {'estimable': False, 'reason': reason} if fit is None else {
            'estimable': True, 'observations': fit.n, 'comparisons': comparisons_only(fit, models)}
    contrasts = {cid: ('arms', w) for cid, _, w in PLANNED + SECONDARY_PAIRS}
    contrasts['S5'] = ('models', models[0], models[1])
    use = [r for r in rows if r['correct'] is not None]
    boot = stats2.cluster_bootstrap(use, ARMS, models, contrasts, replicates=replicates)
    out['clusterBootstrap'] = {'seed': stats2.BOOTSTRAP_SEED, 'replicates': replicates, 'intervals': boot,
                               'estimator': 'pooled proportions of resampled whole tasks, equal model weights, no refit, no round or '
                                            'session adjustment: an unadjusted cross-check, not a bootstrap of the fitted GEE',
                               'equivalent': {cid: bool(100 * boot[cid]['low'] > -stats2.MARGIN and 100 * boot[cid]['high'] < stats2.MARGIN)
                                              for cid in ('P1', 'P2', 'S3')}}
    try:
        mixed = stats2.fit_mixed(use, ARMS, models, conditions)
        out['bayesianMixedModel'] = {'decision': 'S4 of the Job record', 'facts': mixed['facts'], 'arms': mixed['arm'],
                                     'comparisons': [dict(mixed['contrast'](w), id=cid) for cid, _, w in PLANNED + SECONDARY_PAIRS]}
    except Exception as error:  # a sensitivity analysis that cannot be fitted is reported; it does not stop the planned results
        out['bayesianMixedModel'] = {'estimable': False, 'reason': '%s: %s' % (type(error).__name__, error)}
    return out


def spend(records):
    """Dollars per arm: the counted runs and, apart, the attempts the harness archived (operational spend, never in any outcome)."""
    return {a: {'countedRuns': sum(r['cost'] for r in records if r['arm'] == a),
                'archivedAttempts': sum(r['archivedAttemptsCost'] for r in records if r['arm'] == a)} for a in ALL_ARMS}


def cell_counts(rows, arms, models):
    return {a: {m: {'correct': sum(r['correct'] or 0 for r in rows if r['arm'] == a and r['model'] == m),
                    'runs': sum(1 for r in rows if r['arm'] == a and r['model'] == m),
                    'missing': sum(1 for r in rows if r['arm'] == a and r['model'] == m and r['correct'] is None)} for m in models}
            for a in arms}


def outcome_table(rows, arms):
    return {a: {o: sum(1 for r in rows if r['arm'] == a and r['outcome'] == o) for o in data2.OUTCOMES} for a in arms}


def proportions(rows, arms):
    return {a: [sum(r['correct'] for r in rows if r['arm'] == a), sum(1 for r in rows if r['arm'] == a)] for a in arms}


def exploratory(records, models):
    out = {'tier': EXPLORATORY}
    core = [r for r in records if r['set'] == 'core']
    # Direct Access against each arm: its one reference block ran last, so its results are confounded with that time window.
    fit, reason = try_fit([r for r in core if r['correct'] is not None], 'correct', models, arms=ALL_ARMS, rounds=False, sessions=False)
    if fit is None:
        out['directAccess'] = {'estimable': False, 'reason': reason}
    else:
        minus = []
        for a in ARMS:
            c = fit.contrast(fit.marginal('alpha'), fit.marginal(a))
            minus.append(dict(c, arm=a, equivalence=stats2.equivalence(c, stats2.MARGIN)))
        out['directAccess'] = {'note': 'one reference block, last in the schedule: its results are confounded with its time window',
                               'fit': fit.facts(), 'marginals': arm_marginals(fit, ALL_ARMS), 'directAccessMinus': minus}
    # The ambiguity set: a clarification counts only from the ask_requester log, an accepted interpretation is the correct outcome, and a
    # request alone is never success.
    amb = [r for r in records if r['set'] == 'ambiguity']
    out['ambiguitySet'] = {a: {'runs': sum(1 for r in amb if r['arm'] == a),
                               'clarified': sum(1 for r in amb if r['arm'] == a and r['clarified']),
                               'interpretationAccepted': sum(1 for r in amb if r['arm'] == a and r['interpretationAccepted']),
                               'clarifiedAndAccepted': sum(1 for r in amb if r['arm'] == a and r['clarified'] and r['interpretationAccepted']),
                               'clarifiedOnly': sum(1 for r in amb if r['arm'] == a and r['clarified'] and not r['interpretationAccepted']),
                               'outcomes': {o: sum(1 for r in amb if r['arm'] == a and r['outcome'] == o) for o in data2.OUTCOMES}}
                           for a in ALL_ARMS}
    square = [r for r in core if r['arm'] in ARMS and r['correct'] is not None]
    sizes = {}
    for size in data2.SIZES:
        use = [r for r in square if r['size'] == size]
        entry = {'tasks': len({r['task'] for r in use}), 'byArm': proportions(use, ARMS)}
        fit, reason = try_fit(use, 'correct', models, rounds=False, sessions=False) if use else (None, 'no task of this size')
        if fit is None:
            entry.update(comparisons=None, reason=reason)
        else:
            try:
                entry['comparisons'] = [dict(contrast(fit, w), id=cid) for cid, _, w in PLANNED]
            except stats2.FitError as error:
                entry.update(comparisons=None, reason=str(error))
        sizes[size] = entry
    out['sizeStrata'] = sizes
    out['perCategory'] = {c: {'tasks': len({r['task'] for r in square if r['category'] == c}),
                              'byArm': proportions([r for r in square if r['category'] == c], ARMS)} for c in data2.CORE_CATEGORIES}
    tool = {}
    for a in ARMS:
        use = [r for r in square if r['arm'] == a]
        with_tool = [r for r in use if r['calculateCalls'] > 0]
        without = [r for r in use if r['calculateCalls'] == 0]
        tool[a] = {'runs': len(use), 'runsUsingCalculate': len(with_tool), 'calculateCalls': sum(r['calculateCalls'] for r in use),
                   'calculateErrors': sum(r['calculateErrors'] for r in use),
                   'correctWithCalculate': [sum(r['correct'] for r in with_tool), len(with_tool)],
                   'correctWithoutCalculate': [sum(r['correct'] for r in without), len(without)],
                   'askRequesterCalls': sum(r['askRequesterCalls'] for r in use)}
    out['calculationTool'] = tool
    return out


def schedule_facts(manifest, blocks):
    plan = manifest['schedule']
    return {'design': plan['design'], 'letters': {k: NAMES[v] for k, v in plan['letters'].items()}, 'roundOrder': plan['roundOrder'],
            'blocks': blocks}


# ------------------------------------------------------------------------------------------------------------------ outputs
def table(header, rows):
    lines = ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join('---' for _ in header) + ' |']
    lines += ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows]
    return '\n'.join(lines)


def interval(entry, scale=100, fmt='%+.1f'):
    return '%s [%s, %s]' % (fmt % (scale * entry['estimate']), fmt % (scale * entry['low']), fmt % (scale * entry['high']))


def verdict(eq, holm=False):
    established = eq['equivalentHolm'] if holm else eq['equivalent']
    return 'equivalent' if established else 'equivalence not established'


def frac(pair):
    return '%d/%d' % tuple(pair)


def honest_rows(block):
    return [[NAMES[a], '%d/%d' % (v['honest'], v['runs']), '%d/%d' % (v['correct'], v['runs']), v['withHonestyFailure'], v['notJudged'],
             v['vendorErrors']] for a, v in block['byArm'].items()]


def tables_md(res):
    models = res['plan']['models']
    d, p, s, x = res['descriptive'], res['primary'], res['sensitivity'], res['exploratory']
    parts = ['# Abstraction ladder study 2: analysis tables', '',
             'Generated by study/analysis2/analyze2.py from a verified copy of %s. Do not edit by hand.' % res['inputs']['bundle']['run'], '',
             'Equivalence at +/-10 percentage points: the whole 95 percent interval inside the margin (the two one-sided tests at 2.5 percent); '
             'for P1 and P2 the one-sided tests are Holm-adjusted over the two. "Equivalence not established" does not prove a difference.', '']
    parts += ['## Which runs count', '',
              table(['', 'Runs or blocks'], [[COUNTING_LABELS[k], v if not isinstance(v, list) else (', '.join(v) or 'none')]
                                             for k, v in res['counting'].items()]), '']
    parts += ['## Correct answers in the core set by arm and model (descriptive)', '',
              table(['Arm'] + [model_label(m) for m in models] + ['Vendor errors (missing)'],
                    [[NAMES[a]] + ['%d/%d' % (d['cells'][a][m]['correct'], d['cells'][a][m]['runs'] - d['cells'][a][m]['missing'])
                                   for m in models] + [sum(d['cells'][a][m]['missing'] for m in models)] for a in ALL_ARMS]), '']
    parts += ['## Outcomes in the core set by arm (descriptive)', '',
              table(['Arm'] + list(data2.OUTCOMES), [[NAMES[a]] + [d['outcomes'][a][o] for o in data2.OUTCOMES] for a in ALL_ARMS]), '']
    parts += ['## Planned: probability of a correct answer (GEE, standardized, percent, 95 percent interval)', '',
              table(['Arm', 'Correct'], [[NAMES[a], interval(v, fmt='%.1f')] for a, v in p['marginals'].items()]), '',
              'Model: %s observations, %s tasks, rounds %s, sessions %s%s. Standardization: %s.' % (
                  p['fit']['observations'], p['fit']['clusters'], p['fit']['rounds'], p['fit']['sessions'] or 'not in the model',
                  ' (left out: the design with them is not of full rank)' if p['fit']['sessionTermsLeftOutForRank'] else '',
                  ', '.join('round %s%s %.4f' % (c['round'], '' if c['session'] is None else ' session %s' % c['session'], c['weight'])
                            for c in p['fit']['standardization'])), '']
    parts += ['## Planned comparisons (percentage points; Holm over the two, for superiority and for equivalence)', '',
              table(['', 'Comparison', 'Difference [95% CI]', 'p', 'p (Holm)', 'Equivalence p (Holm)', '+/-10 (Holm)',
                     'Whole 95% interval inside +/-10'],
                    [[c['id'], c['label'], interval(c), '%.4f' % c['p'], '%.4f' % c['pHolm'], '%.4f' % c['equivalence']['pTostHolm'],
                      verdict(c['equivalence'], holm=True), 'yes' if c['equivalence']['equivalent'] else 'no'] for c in p['planned']]), '']
    rows = []
    for c in p['secondary']:
        if c['id'] == 'S6':
            rows.append([c['id'], c['label'], 'chi-square %.2f, %d df' % (c['chi2'], c['df']), '%.4f' % c['p'], '%.4f' % c['pHolm'], '-'])
        else:
            rows.append([c['id'], c['label'], interval(c), '%.4f' % c['p'], '%.4f' % c['pHolm'],
                         verdict(c['equivalence']) + ' (no multiplicity control)' if 'equivalence' in c else '-'])
    parts += ['## Secondary comparisons of accuracy (one Holm family of six tests)', '',
              table(['', 'Comparison', 'Difference [95% CI]', 'p', 'p (Holm)', '+/-10'], rows), '']
    for outcome in MEASURES:
        for subset in ('allRuns', 'correctOnly'):
            block = res['measures'][outcome][subset]
            title = '## Exploratory: %s, %s (ratios of geometric means, 95 percent intervals, unadjusted p)' % (
                MEASURE_NAMES[outcome], 'all runs' if subset == 'allRuns' else 'correct runs only')
            parts += [title, '', 'Runs left out for a value that is not positive: %d.' % block['leftOutNotPositive'], '']
            if 'counts' in block:
                parts += [table(['Arm', 'Mean tool calls', 'Median tool calls', 'Runs with none'],
                                [[NAMES[a], '%.2f' % v['mean'], '%g' % v['median'], v['runsWithNone']] for a, v in block['counts'].items()]), '']
            if not block['estimable']:
                parts += ['Not estimable: %s' % block['reason'], '']
                continue
            parts += [table(['Arm', 'Geometric mean [95% CI]'],
                            [[NAMES[a], '%.3g [%.3g, %.3g]' % (g['geometricMean'], g['low'], g['high'])] for a, g in block['geometricMeans'].items()]),
                      '', table(['', 'Comparison', 'Ratio [95% CI]', 'p'],
                                [[r['id'], r['label'], '%.2f [%.2f, %.2f]' % (r['ratio'], r['low'], r['high']), '%.4f' % r['p']]
                                 for r in block['ratios']]), '']
    h = res['honestGap']
    header = ['Arm', 'Honest', 'Correct', 'With an honesty failure', 'Not judged (abstained, did not finish, format error)', 'Vendor errors (left out)']
    parts += ['## Exploratory: the honest-gap rate on category D', '', 'Definition: %s. Limits: %s.' % (h['definition'], h['limits']), '',
              '### Tasks that need the stopped service (%d tasks)' % h['gapRequired']['tasks'], '', table(header, honest_rows(h['gapRequired'])), '']
    if h['gapRequired']['estimable']:
        parts += [table(['', 'Comparison', 'Difference [95% CI]', 'p'],
                        [[c['id'], c['label'], interval(c), '%.4f' % c['p']] for c in h['gapRequired']['comparisons']]), '']
    else:
        parts += ['Not estimable by the GEE: %s' % h['gapRequired']['reason'], '']
    parts += ['### Over-reporting controls (%d tasks; %s)' % (h['overReportingControls']['tasks'], h['overReportingControls']['note']), '',
              table(header, honest_rows(h['overReportingControls'])), '']
    rows = []
    for name, key in (('vendor errors as wrong', 'vendorErrorsAsWrong'), ('bias-reduced covariance', 'biasReducedCovariance')):
        if not s[key]['estimable']:
            rows.append([name, '-', 'not estimable: %s' % s[key]['reason'], '-'])
            continue
        for c in s[key]['comparisons']:
            rows.append([name, c['id'], interval(c), verdict(c['equivalence'], holm=True) if 'equivalence' in c else '-'])
    b = s['clusterBootstrap']
    for cid, iv in b['intervals'].items():
        rows.append(['cluster bootstrap of pooled proportions (seed %d, %d replicates)' % (b['seed'], b['replicates']), cid,
                     '[%+.1f, %+.1f]' % (100 * iv['low'], 100 * iv['high']),
                     ('whole interval inside' if b['equivalent'][cid] else 'not inside') if cid in b['equivalent'] else '-'])
    m = s['bayesianMixedModel']
    if 'comparisons' in m:
        for c in m['comparisons']:
            rows.append(['Bayesian mixed model (posterior mean, 95% posterior interval)', c['id'], interval(c), '-'])
    parts += ['## Sensitivity of the comparisons (percentage points)', '', table(['Analysis', '', 'Difference [95% CI]', '+/-10'], rows), '',
              'Bootstrap: %s.' % b['estimator'], '']
    if 'facts' in m:
        parts += ['Bayesian mixed model (decision S4): %s, seed %d, %d posterior draws; posterior mean random-effect standard deviations, '
                  'task %.2f and block %.2f (logit scale). %s.' % (m['facts']['method'], m['facts']['seed'], m['facts']['posteriorDraws'],
                                                                   m['facts']['randomEffectSdPosteriorMean']['task'],
                                                                   m['facts']['randomEffectSdPosteriorMean']['block'], m['facts']['intervals']), '']
    else:
        parts += ['Bayesian mixed model not estimable: %s' % m.get('reason'), '']
    sp = res['spend']
    parts += ['## Spend by arm (descriptive, USD, prices of the manifest)', '',
              table(['Arm', 'Counted runs', 'Archived attempts (operational only)'],
                    [[NAMES[a], '%.2f' % v['countedRuns'], '%.2f' % v['archivedAttempts']] for a, v in sp.items()]), '']
    parts += ['## Exploratory: Direct Access against each arm (one block, last in the schedule)', '']
    da = x['directAccess']
    if 'directAccessMinus' in da:
        parts += [table(['Direct Access minus', 'Difference [95% CI]', 'p', '+/-10'],
                        [[NAMES[c['arm']], interval(c), '%.4f' % c['p'], verdict(c['equivalence'])] for c in da['directAccessMinus']]), '',
                  'Note: %s.' % da['note'], '']
    else:
        parts += ['Not estimable: %s' % da['reason'], '']
    parts += ['## Exploratory: the ambiguity set (scored apart; a request alone is not success)', '',
              table(['Arm', 'Runs', 'Clarified (from the ask_requester log)', 'Interpretation accepted', 'Both', 'Clarified only'],
                    [[NAMES[a], v['runs'], v['clarified'], v['interpretationAccepted'], v['clarifiedAndAccepted'], v['clarifiedOnly']]
                     for a, v in x['ambiguitySet'].items()]), '']
    rows = []
    for size, v in x['sizeStrata'].items():
        comps = {c['id']: interval(c) for c in (v['comparisons'] or [])}
        rows.append([size, v['tasks']] + [frac(v['byArm'][a]) for a in ARMS] + [comps.get('P1', '-'), comps.get('P2', '-')])
    parts += ['## Exploratory: size strata', '', table(['Size', 'Tasks'] + [NAMES[a] for a in ARMS] + ['P1', 'P2'], rows), '']
    parts += ['## Exploratory: results per category', '',
              table(['Category', 'Tasks'] + [NAMES[a] for a in ARMS],
                    [[data2.CATEGORY_NAMES[c], v['tasks']] + [frac(v['byArm'][a]) for a in ARMS] for c, v in x['perCategory'].items()]), '']
    parts += ['## Exploratory: use of the calculation tool', '',
              table(['Arm', 'Runs using calculate', 'Calls', 'Errors', 'Correct with calculate', 'Correct without'],
                    [[NAMES[a], '%d/%d' % (v['runsUsingCalculate'], v['runs']), v['calculateCalls'], v['calculateErrors'],
                      frac(v['correctWithCalculate']), frac(v['correctWithoutCalculate'])] for a, v in x['calculationTool'].items()]), '']
    sched = res['schedule']
    parts += ['## The schedule (descriptive)', '',
              'Letters: %s. Rounds in the order they ran: %s.' % (', '.join('%s %s' % kv for kv in sorted(sched['letters'].items())),
                                                                 ', '.join(str(r) for r in sched['roundOrder'])), '',
              table(['Block', 'Arm', 'Round', 'Starts', 'Sessions'],
                    [[b['id'], NAMES[b['arm']], b['row'] if b['row'] is not None else 'reference', b['starts'], ', '.join(b['sessions'])]
                     for b in sched['blocks']]), '']
    return '\n'.join(parts) + '\n'


def figures(res):
    p, x, measures_ = res['primary'], res['exploratory'], res['measures']
    items = [(NAMES[a], 100 * v['estimate'], 100 * v['low'], 100 * v['high'], 'confirmatory') for a, v in p['marginals'].items()]
    da = x['directAccess'].get('marginals', {}).get('alpha')
    if da:
        items.append(('Direct Access (exploratory)', 100 * da['estimate'], 100 * da['low'], 100 * da['high'], 'exploratory'))
    out = {'accuracy.svg': svg.interval_plot('Correct answers by arm, core set', 'percent correct (GEE, standardized, 95% interval)', items,
                                             0, 100, range(0, 101, 20), note='Direct Access: one reference block, last in the schedule.')}
    items = [(c['id'], 100 * c['estimate'], 100 * c['low'], 100 * c['high'], 'confirmatory') for c in p['planned']]
    items += [(c['id'], 100 * c['estimate'], 100 * c['low'], 100 * c['high'], 'descriptive') for c in p['secondary'] if 'estimate' in c]
    lo = 10 * math.floor(min(-30, min(i[2] for i in items)) / 10)
    hi = 10 * math.ceil(max(30, max(i[3] for i in items)) / 10)
    out['comparisons.svg'] = svg.interval_plot('Planned (P1, P2) and secondary comparisons', 'percentage points (95% interval)', items,
                                               lo, hi, range(int(lo), int(hi) + 1, 10), margins=((10, '0.10'),),
                                               note='Shaded: the equivalence margin +/-10. Solid: planned; dotted: secondary (S1 to S5).')
    for outcome, title in (('cost', 'Cost per run'), ('seconds', 'Time per run')):
        geo = measures_[outcome]['allRuns'].get('geometricMeans')
        if not geo:
            continue
        top = max(g['high'] for g in geo.values())
        step = 10 ** math.floor(math.log10(top)) if top > 0 else 1
        hi = step * math.ceil(top / step)
        ticks = [round(step * i, 6) for i in range(int(round(hi / step)) + 1)]
        items = [(NAMES[a], g['geometricMean'], g['low'], g['high'], 'exploratory') for a, g in geo.items()]
        out['%s.svg' % outcome] = svg.interval_plot('%s by arm (geometric mean, exploratory)' % title, MEASURE_NAMES[outcome] + ', 95% interval',
                                                    items, 0, hi, ticks)
    return out


def analyse(args):
    facts, manifest = data2.verify_bundle(args.bundle, args.sums, args.run_id, args.bundle_checksum)
    strata, corpus_facts = data2.load_strata(args.corpus_dir, manifest)
    records, blocks = data2.load_bundle(args.bundle, manifest, strata)
    models = sorted(manifest['models'])
    core = [r for r in records if r['set'] == 'core']
    square = [r for r in core if r['arm'] in ARMS]
    conditions = stats2.planned_conditions(square)  # every planned run of the square's core set: fixed by the schedule
    fit, prim = primary([r for r in square if r['correct'] is not None], models, conditions)
    res = {
        'about': 'Abstraction ladder study 2 analysis under the draft plan study/analysis2/PLAN.md. Generated; do not edit.',
        'inputs': {'bundle': facts, 'corpus': corpus_facts},
        'plan': {'models': models, 'arms': {a: NAMES[a] for a in ALL_ARMS}, 'planned': [c[0] for c in PLANNED],
                 'secondaryFamily': [c[0] for c in SECONDARY_PAIRS] + ['S5', 'S6'], 'margin': stats2.MARGIN, 'meaningful': MEANINGFUL,
                 'equivalence': 'P1 and P2: the two one-sided tests Holm-adjusted over the two, against 2.5 percent; S3: unadjusted',
                 'bootstrap': {'replicates': args.replicates, 'seed': stats2.BOOTSTRAP_SEED}},
        'counting': data2.counting(records, blocks),
        'descriptive': {'cells': cell_counts(core, ALL_ARMS, models), 'outcomes': outcome_table(core, ALL_ARMS)},
        'primary': prim,
        'measures': measures(square, models, conditions),
        'honestGap': honest_gap(square, models),
        'sensitivity': sensitivity(square, models, args.replicates, conditions),
        'spend': spend(records),
        'exploratory': exploratory(records, models),
        'schedule': schedule_facts(manifest, blocks),
    }
    return r6(res)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('--bundle', '--sums', '--bundle-checksum', '--corpus-dir', '--out'):
        parser.add_argument(name, required=True)
    parser.add_argument('--run-id', default='study-2')
    parser.add_argument('--replicates', type=int, default=stats2.BOOTSTRAP_REPLICATES)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.resolve().is_relative_to(REPO.resolve()):
        parser.error('--out must be outside the repository: the outputs are generated')
    try:
        res = analyse(args)
    except data2.VerificationError as error:
        print('STOP: %s' % error, file=sys.stderr)
        return 2
    except stats2.FitError as error:
        print('STOP: %s; the plan allows no fallback without the lead developer\'s word' % error, file=sys.stderr)
        return 3
    text = {'results.json': json.dumps(res, indent=2, sort_keys=True) + '\n', 'tables.md': tables_md(res)}
    pictures = figures(res)
    (out / 'figures').mkdir(parents=True, exist_ok=True)
    for name, body in text.items():
        (out / name).write_text(body, encoding='utf-8', newline='\n')
    for name, body in pictures.items():
        (out / 'figures' / name).write_text(body, encoding='utf-8', newline='\n')
    print('analysis written to %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
