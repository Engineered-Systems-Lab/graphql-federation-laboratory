"""The Abstraction ladder study analysis: every table and figure of the report, from verified copies of study-1 and gamma-prime-1.

    python -B study/analysis/analyze.py --study-1 <copy> --gamma-prime-1 <copy> --sums-study-1 <SHA256SUMS file>
        --sums-gamma-prime-1 <SHA256SUMS file> --out <folder outside the repository>

The copies are verified first (data.verify_copy) against the archive sums and the bundle checksums of study/evidence/checksums.json, and
their score tables against the committed evidence; any difference stops the run before a number is computed. It writes results.json,
tables.md and figures/*.svg into --out, and nothing else. The same inputs give the same bytes. The plan it implements is the analysis plan
agreed on 2026-10-21 (local record agent_scenarios_design); the tiers are kept apart in every output: confirmatory, sensitivity,
secondary, exploratory and descriptive.
"""
import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

import data
import stats
import svg
import t15

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
EVIDENCE = STUDY / 'evidence'
CONFIRMATORY = ['alpha', 'beta', 'delta', 'epsilon']
ALL_SCENARIOS = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'gamma_prime']
NAMES = {'alpha': 'Alpha', 'beta': 'Beta', 'gamma': 'Gamma (as built)', 'delta': 'Delta', 'epsilon': 'Epsilon',
         'gamma_prime': 'Gamma-prime'}
MODELS = ['claude-sonnet-5-5', 'gpt-6.1-sol']
MODEL_NAMES = {'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'gpt-6.1-sol': 'GPT-6.1 Sol'}
# The named confirmatory comparisons of the plan, point 3. Each estimate is the second minus the first, so a positive value favours the
# later rung of the ladder (or Claude in comparison v).
COMPARISONS = [
    ('i', 'scenario', 'alpha', 'beta', 'Alpha vs Beta (the guide)'),
    ('ii', 'scenario', 'alpha', 'delta', 'Alpha vs Delta (the graph)'),
    ('iii', 'scenario', 'beta', 'delta', 'Beta vs Delta (guide against graph)'),
    ('iv', 'scenario', 'delta', 'epsilon', 'Delta vs Epsilon (Apollo against Cosmo)'),
    ('v', 'model', 'gpt-6.1-sol', 'claude-sonnet-5-5', 'Claude vs GPT (model effect over the four scenarios)'),
    ('vi', 'scenario', 'beta', 'epsilon', 'Beta vs Epsilon'),
]
EQUIVALENCE_PAIRS = ['iii', 'vi', 'iv']
MARGINS = [(10, 'primary'), (15, 'secondary')]
SECONDARY = ['seconds', 'toolCalls', 'cost', 'tokens']
SECONDARY_NAMES = {'seconds': 'run time (s)', 'toolCalls': 'tool calls', 'cost': 'cost (USD)', 'tokens': 'tokens'}


def r6(value):
    """Round every float to six decimals so the output bytes do not depend on the last bits of the arithmetic."""
    if isinstance(value, float):
        return 0.0 if value == 0 else round(value, 6)
    if isinstance(value, dict):
        return {k: r6(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [r6(v) for v in value]
    return value


def pp(value):
    return '%+.1f' % (100 * value)


def pct(value):
    return '%.1f' % (100 * value)


def lf_sha256(path):
    """SHA-256 of a text file with LF line ends, the form the run wrote; a Windows checkout may hold it with CRLF."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


# ------------------------------------------------------------------------------------------------------------------ inputs
def verify_inputs(args):
    evidence = Path(args.evidence)
    checks = json.loads((evidence / 'checksums.json').read_text(encoding='utf-8'))
    facts = {}
    for run_id, folder, sums in (('study-1', args.study_1, args.sums_study_1), ('gamma-prime-1', args.gamma_prime_1, args.sums_gamma_prime_1)):
        expected = checks['runs'][run_id]
        fact = data.verify_copy(folder, sums, run_id, expected['bundleChecksum'])
        if fact['sumsFileSha256'] != expected['sumsFile']['sha256']:
            raise data.VerificationError('%s: the sums file is not the archived one' % run_id)
        for name, digest in expected['evidenceFiles'].items():
            if lf_sha256(evidence / run_id / name) != digest or data.sha256_file(Path(folder) / name) != digest:
                raise data.VerificationError('%s: committed evidence %s differs from the copy' % (run_id, name))
        facts[run_id] = fact
    return facts


# ------------------------------------------------------------------------------------------------------------------ pieces
def cell_counts(rows, scenarios):
    out = {}
    for s in scenarios:
        out[s] = {}
        for m in MODELS:
            cell = [r for r in rows if r['scenario'] == s and r['model'] == m]
            out[s][m] = {'correct': sum(r['correct'] or 0 for r in cell), 'runs': len(cell),
                         'missing': sum(1 for r in cell if r['correct'] is None)}
    return out


def outcomes(rows, scenarios):
    return {s: dict(sorted(Counter(r['outcome'] for r in rows if r['scenario'] == s).items())) for s in scenarios}


def per_task(rows, scenarios):
    tasks = sorted({r['task'] for r in rows})
    return {t: {s: [sum(r['correct'] or 0 for r in rows if r['task'] == t and r['scenario'] == s),
                    sum(1 for r in rows if r['task'] == t and r['scenario'] == s and r['correct'] is not None)]
                for s in scenarios} for t in tasks}


def informative_tasks(rows, scenarios):
    """Tasks whose runs in these scenarios are not all right and not all wrong: only these can separate the scenarios."""
    out = []
    for t in sorted({r['task'] for r in rows}):
        values = {r['correct'] for r in rows if r['task'] == t and r['scenario'] in scenarios and r['correct'] is not None}
        if len(values) > 1:
            out.append(t)
    return out


def comparison_summaries(fit, rows, bootstrap=None):
    """The six named comparisons on one fit: estimate, interval, Wald p, Holm p and the cross-checks."""
    results = []
    for cid, kind, a, b, label in COMPARISONS:
        if kind == 'scenario':
            summary = fit.contrast(fit.marginal(b), fit.marginal(a))
            pairs = stats.matched(rows, lambda r, s=b: r['scenario'] == s, lambda r, s=a: r['scenario'] == s, ('task', 'model', 'trial'))
        else:
            summary = fit.contrast(fit.model_marginal(b), fit.model_marginal(a))
            pairs = stats.matched([r for r in rows if r['scenario'] in CONFIRMATORY], lambda r, m=b: r['model'] == m,
                                  lambda r, m=a: r['model'] == m, ('scenario', 'task', 'trial'))
        entry = {'id': cid, 'label': label, 'first': a, 'second': b, **summary, 'mcnemar': stats.mcnemar_exact(pairs)}
        if bootstrap is not None:
            entry['bootstrap'] = bootstrap[cid]
        results.append(entry)
    for entry, adjusted in zip(results, stats.holm([e['p'] for e in results])):
        entry['pHolm'] = adjusted
    for entry, adjusted in zip(results, stats.holm([e['mcnemar']['p'] for e in results])):
        entry['mcnemar']['pHolm'] = adjusted
    return results


def bootstrap_for(rows, replicates):
    contrasts = {cid: (kind, b, a) for cid, kind, a, b, _ in COMPARISONS}
    return stats.bootstrap_contrasts(rows, CONFIRMATORY, MODELS, contrasts, replicates=replicates)


def marginals(fit, scenarios):
    """Each scenario's marginal probability with a 95 percent interval taken on the logit scale, so it stays inside 0 to 1."""
    out = {}
    for s in scenarios:
        value, grad = fit.marginal(s)
        se = math.sqrt(float(grad @ fit.cov @ grad)) / (value * (1 - value))
        logit = math.log(value / (1 - value))
        out[s] = {'estimate': value, 'low': 1 / (1 + math.exp(-(logit - stats.Z95 * se))),
                  'high': 1 / (1 + math.exp(-(logit + stats.Z95 * se)))}
    return out


def fit_facts(fit):
    return {'observations': fit.n, 'clusters': fit.clusters, 'converged': fit.converged, 'covariance': fit.cov_kind,
            'workingCorrelation': 'exchangeable', 'parameters': dict(zip(fit.design.names, fit.params.tolist()))}


def primary(rows, replicates):
    fit = stats.fit_gee(rows, 'correct', CONFIRMATORY, MODELS)
    if not fit.converged:
        raise SystemExit('STOP: the primary GEE did not converge; the plan says to ask the lead developer before any fallback')
    comps = comparison_summaries(fit, rows, bootstrap_for(rows, replicates))
    by_id = {c['id']: c for c in comps}
    # The GEE interval decides (the lead developer's answer c of 2026-10-21); the bootstrap decision is reported beside it, so a disagreement shows.
    equiv = [{'id': cid, 'label': by_id[cid]['label'], 'estimate': by_id[cid]['estimate'], 'low': by_id[cid]['low'],
              'high': by_id[cid]['high'],
              'margins': [dict(stats.equivalence(by_id[cid], m), tier=tier,
                               bootstrapEquivalent=bool(100 * by_id[cid]['bootstrap']['low'] > -m and 100 * by_id[cid]['bootstrap']['high'] < m))
                          for m, tier in MARGINS]}
             for cid in EQUIVALENCE_PAIRS]
    return fit, {'fit': fit_facts(fit), 'marginals': marginals(fit, CONFIRMATORY), 'comparisons': comps,
                 'interaction': fit.interaction_test(), 'equivalence': equiv,
                 'cochranQ': stats.cochran(rows, CONFIRMATORY)}


def sensitivity(rows, t15_flips):
    out = {}
    as_wrong = [dict(r, correct=0) if r['correct'] is None else r for r in rows]
    fit = stats.fit_gee(as_wrong, 'correct', CONFIRMATORY, MODELS)
    out['errorsAsWrong'] = {'converged': fit.converged, 'observations': fit.n,
                            'comparisons': comparison_summaries(fit, as_wrong), 'interaction': fit.interaction_test()}
    fit = stats.fit_gee(rows, 'correct', CONFIRMATORY, MODELS, cov_type='bias_reduced')
    out['biasReducedCovariance'] = {'converged': fit.converged, 'comparisons': comparison_summaries(fit, rows),
                                    'interaction': fit.interaction_test()}
    flipped = [dict(r, correct=1) if (r['run'], r['runKey']) in t15_flips else r for r in rows]
    fit = stats.fit_gee(flipped, 'correct', CONFIRMATORY, MODELS)
    out['t15CrewOnly'] = {'tier': 'exploratory (post hoc)', 'converged': fit.converged, 'comparisons': comparison_summaries(fit, flipped),
                          'marginals': marginals(fit, CONFIRMATORY)}
    return out


def secondary(rows):
    out = {}
    for outcome in SECONDARY:
        out[outcome] = {}
        for subset, use in (('allRuns', [r for r in rows if r['correct'] is not None]), ('correctOnly', [r for r in rows if r['correct'] == 1])):
            fit = stats.fit_gee(use, outcome, CONFIRMATORY, MODELS, logistic=False)
            geo = {}
            for s in CONFIRMATORY:
                value, grad = fit.marginal(s)
                se = math.sqrt(float(grad @ fit.cov @ grad))
                geo[s] = {'geometricMean': math.exp(value), 'low': math.exp(value - stats.Z95 * se), 'high': math.exp(value + stats.Z95 * se)}
            ratios = []
            for cid, kind, a, b, label in COMPARISONS:
                c = (fit.contrast(fit.marginal(b), fit.marginal(a)) if kind == 'scenario'
                     else fit.contrast(fit.model_marginal(b), fit.model_marginal(a)))
                ratios.append({'id': cid, 'label': label, 'ratio': math.exp(c['estimate']), 'low': math.exp(c['low']),
                               'high': math.exp(c['high']), 'p': c['p']})
            out[outcome][subset] = {'converged': fit.converged, 'observations': fit.n, 'geometricMeans': geo, 'ratios': ratios}
    return out


def latency(folder, records):
    """Request latency per scenario and vendor, beside the cache-hit share (descriptive)."""
    scenario_of = {r['runKey']: r['scenario'] for r in records}
    groups = {}
    for req in data.request_log(folder):
        vendor = req['vendorFile'][len('budget-'):-len('.jsonl')]
        groups.setdefault((scenario_of[req['run']], vendor), []).append(req)
    out = []
    for (scenario, vendor), reqs in sorted(groups.items(), key=lambda kv: (ALL_SCENARIOS.index(kv[0][0]), kv[0][1])):
        seconds = sorted(q['seconds'] for q in reqs)
        prompt = sum(q['input'] + q['cached_read'] + q['cache_write'] for q in reqs)
        out.append({'scenario': scenario, 'vendor': vendor, 'requests': len(reqs), 'retries': sum(q['retry'] for q in reqs),
                    'medianSeconds': statistics.median(seconds), 'p90Seconds': seconds[min(len(seconds) - 1, int(0.9 * len(seconds)))],
                    'meanSeconds': statistics.fmean(seconds), 'cacheHitShare': sum(q['cached_read'] for q in reqs) / prompt if prompt else 0.0,
                    'cacheWriteShare': sum(q['cache_write'] for q in reqs) / prompt if prompt else 0.0})
    return out


def spend(folder, records, manifest):
    """Dollars per model from the run records and from the request ledger (they differ only by what a retried request cost)."""
    prices = {m: e['priceEntry'] for m, e in manifest['models'].items()}
    vendor_model = {e['vendor']: m for m, e in manifest['models'].items()}
    ledger = Counter()
    for req in data.request_log(folder):
        model = vendor_model[req['vendorFile'][len('budget-'):-len('.jsonl')]]
        ledger[model] += data.dollars(req, prices[model])
    return {m: {'runs': sum(r['cost'] for r in records if r['model'] == m), 'ledger': ledger[m],
                'tokens': sum(r['tokens'] for r in records if r['model'] == m)} for m in MODELS}


def exploratory(s1, gp, t15_table, t15_flips, corpus, primary_fit):
    out = {'tier': 'exploratory: chosen after the descriptive look, labelled, no confirmatory claim'}
    # Gamma-prime against Alpha and Beta: the lead developer's hunch. A separate, non-interleaved run.
    rows = [r for r in s1 if r['scenario'] in ('alpha', 'beta')] + gp
    fit = stats.fit_gee(rows, 'correct', ['alpha', 'beta', 'gamma_prime'], MODELS)
    vs = {}
    for other in ('alpha', 'beta'):
        c = fit.contrast(fit.marginal('gamma_prime'), fit.marginal(other))
        pairs = stats.matched(rows, lambda r: r['scenario'] == 'gamma_prime', lambda r, o=other: r['scenario'] == o, ('task', 'model', 'trial'))
        vs[other] = dict(c, mcnemar=stats.mcnemar_exact(pairs), margins=[dict(stats.equivalence(c, m), tier=tier) for m, tier in MARGINS])
    out['gammaPrime'] = {'fit': fit_facts(fit), 'marginals': marginals(fit, ['alpha', 'beta', 'gamma_prime']),
                         'gammaPrimeMinus': vs}
    # Gamma as built beside Gamma-prime: descriptive only (no tests, by the plan).
    gamma = {(r['task'], r['model'], r['trial']): r['correct'] for r in s1 if r['scenario'] == 'gamma'}
    prime = {(r['task'], r['model'], r['trial']): r['correct'] for r in gp}
    keys = sorted(set(gamma) & set(prime))
    split = {}
    for flag in (True, False):
        tasks = sorted(t for t, info in corpus.items() if info['tags'].get('mappingNeeded') is flag)
        split['mappingNeeded' if flag else 'noMapping'] = {
            'tasks': tasks,
            'gamma': [sum(gamma[k] or 0 for k in keys if k[0] in tasks), sum(1 for k in keys if k[0] in tasks)],
            'gammaPrime': [sum(prime[k] or 0 for k in keys if k[0] in tasks), sum(1 for k in keys if k[0] in tasks)]}
    out['gammaAsBuilt'] = {'tier': 'descriptive (our design error; no test)',
                           'rightOnlyInGammaPrime': sum(1 for k in keys if prime[k] == 1 and gamma[k] == 0),
                           'rightOnlyInGamma': sum(1 for k in keys if gamma[k] == 1 and prime[k] == 0), 'byMappingTag': split}
    # Structure over kind, read as: adding structure (a guide or a graph) to raw access matters more than which kind of structure.
    structured = [primary_fit.marginal(s) for s in ('beta', 'delta', 'epsilon')]
    mean_structured = (sum(v for v, _ in structured) / 3, sum(g for _, g in structured) / 3)
    graph = [primary_fit.marginal(s) for s in ('delta', 'epsilon')]
    mean_graph = (sum(v for v, _ in graph) / 2, sum(g for _, g in graph) / 2)
    out['structureOverKind'] = {
        'reading': 'structure (the guide or a graph) against raw access, and graph against guide as the kind of structure',
        'structuredMinusAlpha': primary_fit.contrast(mean_structured, primary_fit.marginal('alpha')),
        'graphMinusGuide': primary_fit.contrast(mean_graph, primary_fit.marginal('beta'))}
    # The outage tasks and T07, by scenario.
    everything = s1 + gp
    for key, tasks in (('outageTasks', ('T10', 'T11')), ('t07', ('T07',))):
        out[key] = {t: {s: {'correct': sum(r['correct'] or 0 for r in everything if r['task'] == t and r['scenario'] == s),
                            'runs': sum(1 for r in everything if r['task'] == t and r['scenario'] == s),
                            'outcomes': dict(sorted(Counter(r['outcome'] for r in everything if r['task'] == t and r['scenario'] == s).items())),
                            'honestyFailures': sum(1 for r in everything if r['task'] == t and r['scenario'] == s and r['honestyFailures']),
                            'tags': dict(sorted(Counter(r['tags'] for r in everything if r['task'] == t and r['scenario'] == s and r['tags']).items()))}
                        for s in ALL_SCENARIOS} for t in tasks}
    # T15 under the assigned-crew-only reading.
    flips = Counter(r['scenario'] for r in everything if (r['run'], r['runKey']) in t15_flips)
    out['t15CrewOnly'] = {'tier': 'exploratory (post hoc): the question says "among their crew" and does not say commanding officers included',
                          'table': t15_table, 'flips': {s: flips.get(s, 0) for s in ALL_SCENARIOS},
                          'flippedRuns': sorted('%s/%s' % key for key in t15_flips)}
    return out


def run_conditions(manifests, samples):
    out = {}
    for run_id, m in manifests.items():
        out[run_id] = {k: m[k] for k in ('createdAt', 'commit', 'treeDirty', 'machine', 'stackFacts', 'limits', 'sdkVersions', 'declaredSettings',
                                         'telemetry', 'pricesTableDate', 'stackRunsPerScenario', 'planHash')}
        out[run_id]['modelRequests'] = {name: e['request'] for name, e in m['models'].items()}
        out[run_id]['coldStartSeconds'] = {s['scenario']: s['seconds'] for s in samples[run_id] if s['kind'] == 'cold_start'}
    return out


# ------------------------------------------------------------------------------------------------------------------ outputs
def table(header, rows):
    lines = ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join('---' for _ in header) + ' |']
    lines += ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows]
    return '\n'.join(lines)


def interval(entry, scale=100, fmt='%+.1f'):
    return '%s [%s, %s]' % (fmt % (scale * entry['estimate']), fmt % (scale * entry['low']), fmt % (scale * entry['high']))


def tables_md(res):
    d, p, sec, x = res['descriptive'], res['primary'], res['secondary'], res['exploratory']
    parts = ['# Agent study analysis: tables', '',
             'Generated by study/analysis/analyze.py from verified copies of study-1 and gamma-prime-1. Do not edit by hand.', '']
    parts += ['## Correct answers by scenario and model (descriptive)', '',
              table(['Scenario'] + [MODEL_NAMES[m] for m in MODELS] + ['All', 'Missing'],
                    [[NAMES[s]] + ['%d/%d' % (d['cells'][s][m]['correct'], d['cells'][s][m]['runs']) for m in MODELS]
                     + ['%d/%d' % (sum(d['cells'][s][m]['correct'] for m in MODELS), sum(d['cells'][s][m]['runs'] for m in MODELS)),
                        sum(d['cells'][s][m]['missing'] for m in MODELS)] for s in ALL_SCENARIOS]), '']
    parts += ['## Outcomes by scenario (descriptive)', '',
              table(['Scenario', 'Outcomes'], [[NAMES[s], ', '.join('%s %d' % kv for kv in d['outcomes'][s].items())] for s in ALL_SCENARIOS]), '']
    parts += ['## Correct runs per task, of 4 (descriptive)', '',
              table(['Task'] + [NAMES[s] for s in ALL_SCENARIOS],
                    [[t] + ['%d/%d' % tuple(v[s]) for s in ALL_SCENARIOS] for t, v in d['perTask'].items()]), '',
              'Informative tasks in the confirmatory set (not all right and not all wrong): %d of 16 (%s).'
              % (len(d['informativeTasks']), ', '.join(d['informativeTasks'])), '']
    parts += ['## Confirmatory: marginal probability of a correct answer (GEE, percent, 95 percent interval)', '',
              table(['Scenario', 'Correct'], [[NAMES[s], interval(v, fmt='%.1f')] for s, v in p['marginals'].items()]), '']
    parts += ['## Confirmatory: the six named comparisons (percentage points, second minus first)', '',
              table(['', 'Comparison', 'Difference [95% CI]', 'p', 'p (Holm)', 'Bootstrap 95% CI', 'McNemar (2nd only / 1st only, exact p)'],
                    [[c['id'], c['label'], interval(c), '%.4f' % c['p'], '%.4f' % c['pHolm'],
                      '[%s, %s]' % (pp(c['bootstrap']['low']), pp(c['bootstrap']['high'])),
                      '%d / %d, p = %.4f' % (c['mcnemar']['aOnly'], c['mcnemar']['bOnly'], c['mcnemar']['p'])] for c in p['comparisons']]), '',
              'Scenario x model interaction (Wald, %d df): chi-square %.2f, p = %.4f (reported with comparison v, not in the Holm family).'
              % (p['interaction']['df'], p['interaction']['chi2'], p['interaction']['p']),
              "Cochran's Q over the four scenarios (%d complete blocks): Q = %.2f, df %d, p = %.2g."
              % (p['cochranQ']['blocks'], p['cochranQ']['q'], p['cochranQ']['df'], p['cochranQ']['p']), '']
    parts += ['## Confirmatory: equivalence (whole 95 percent interval inside the margin)', '',
              table(['', 'Pair', 'Difference [95% CI]', '+/-10 (primary)', '+/-15 (secondary)', 'Bootstrap agrees'],
                    [[e['id'], e['label'], interval(e)] + ['equivalent' if m['equivalent'] else 'not demonstrated' for m in e['margins']]
                     + ['yes' if all(m['equivalent'] == m['bootstrapEquivalent'] for m in e['margins']) else 'NO'] for e in p['equivalence']]), '']
    rows = []
    for name, block in (('errors as wrong', res['sensitivity']['errorsAsWrong']), ('bias-reduced covariance', res['sensitivity']['biasReducedCovariance']),
                        ('T15 crew-only (exploratory)', res['sensitivity']['t15CrewOnly'])):
        for c in block['comparisons']:
            rows.append([name, c['id'], interval(c), '%.4f' % c['pHolm']])
    parts += ['## Sensitivity of the comparisons', '', table(['Analysis', '', 'Difference [95% CI]', 'p (Holm)'], rows), '']
    for outcome in SECONDARY:
        for subset in ('allRuns', 'correctOnly'):
            block = sec[outcome][subset]
            parts += ['## Secondary: %s, %s (geometric means and ratios, 95 percent intervals)' % (SECONDARY_NAMES[outcome],
                                                                                                 'all runs' if subset == 'allRuns' else 'correct runs only'), '',
                      table(['Scenario', 'Geometric mean [95% CI]'],
                            [[NAMES[s], '%.3g [%.3g, %.3g]' % (g['geometricMean'], g['low'], g['high'])] for s, g in block['geometricMeans'].items()]), '',
                      table(['', 'Comparison', 'Ratio [95% CI]', 'p'],
                            [[r['id'], r['label'], '%.2f [%.2f, %.2f]' % (r['ratio'], r['low'], r['high']), '%.4f' % r['p']] for r in block['ratios']]), '']
    parts += ['## Request latency and cache share (descriptive)', '',
              table(['Run', 'Scenario', 'Vendor', 'Requests', 'Median s', 'p90 s', 'Cache-hit share', 'Cache-write share'],
                    [[run, NAMES[q['scenario']], q['vendor'], q['requests'], '%.2f' % q['medianSeconds'], '%.2f' % q['p90Seconds'],
                      pct(q['cacheHitShare']), pct(q['cacheWriteShare'])] for run, block in res['latency'].items() for q in block]), '']
    parts += ['## Spend (descriptive, prices of the run manifests)', '',
              table(['Run', 'Model', 'USD from run records', 'USD from request ledger', 'Tokens'],
                    [[run, MODEL_NAMES[m], '%.2f' % v['runs'], '%.2f' % v['ledger'], v['tokens']] for run, block in res['spend'].items()
                     for m, v in block.items()]), '']
    g = x['gammaPrime']
    parts += ['## Exploratory: Gamma-prime against Alpha and Beta (separate run, not interleaved)', '',
              table(['Scenario', 'Correct (GEE, percent)'], [[NAMES[s], interval(v, fmt='%.1f')] for s, v in g['marginals'].items()]), '',
              table(['Gamma-prime minus', 'Difference [95% CI]', 'p', 'McNemar', '+/-10', '+/-15'],
                    [[NAMES[o], interval(v), '%.4f' % v['p'], '%d / %d, p = %.4f' % (v['mcnemar']['aOnly'], v['mcnemar']['bOnly'], v['mcnemar']['p'])]
                     + ['inside' if m['equivalent'] else 'not inside' for m in v['margins']] for o, v in g['gammaPrimeMinus'].items()]), '']
    b = x['gammaAsBuilt']
    parts += ['## Gamma as built beside Gamma-prime (descriptive; our design error)', '',
              table(['Tasks', 'Gamma as built', 'Gamma-prime'],
                    [[k + ' (' + ', '.join(v['tasks']) + ')', '%d/%d' % tuple(v['gamma']), '%d/%d' % tuple(v['gammaPrime'])] for k, v in b['byMappingTag'].items()]), '',
              'Matched runs right only in Gamma-prime: %d; right only in Gamma as built: %d.' % (b['rightOnlyInGammaPrime'], b['rightOnlyInGamma']), '']
    s = x['structureOverKind']
    parts += ['## Exploratory: structure over kind', '', 'Reading: %s.' % s['reading'], '',
              table(['Contrast', 'Difference [95% CI]', 'p'],
                    [['mean of Beta, Delta, Epsilon minus Alpha', interval(s['structuredMinusAlpha']), '%.4f' % s['structuredMinusAlpha']['p']],
                     ['mean of Delta, Epsilon minus Beta', interval(s['graphMinusGuide']), '%.4f' % s['graphMinusGuide']['p']]]), '']
    for key, title in (('outageTasks', 'the outage tasks'), ('t07', 'T07 (equipment references that cannot be matched)')):
        rows = [[t, NAMES[sc], '%d/%d' % (v['correct'], v['runs']), ', '.join('%s %d' % kv for kv in v['outcomes'].items()),
                 v['honestyFailures'], ', '.join('%s %d' % kv for kv in v['tags'].items()) or '-'] for t, block in x[key].items() for sc, v in block.items()]
        parts += ['## Exploratory: %s' % title, '', table(['Task', 'Scenario', 'Correct', 'Outcomes', 'Honesty failures', 'Tags'], rows), '']
    c = x['t15CrewOnly']
    parts += ['## Exploratory (post hoc): T15 with the assigned crew only', '',
              table(['Definition', 'Lab-confirmed', 'Non-cancelled', 'All missions'],
                    [[dfn['name']] + ['%d of %d' % (q['withSeniorOfficer'], q['outOf']) for q in dfn['policies']] for dfn in c['table']['definitions']]), '',
              'Runs scored wrong that the crew-only counts accept: ' + ', '.join('%s %d' % (NAMES[k], v) for k, v in c['flips'].items() if v) + '.', '']
    return '\n'.join(parts) + '\n'


def figures(res):
    p, x, sec = res['primary'], res['exploratory'], res['secondary']
    items = [(NAMES[s], 100 * v['estimate'], 100 * v['low'], 100 * v['high'], 'confirmatory') for s, v in p['marginals'].items()]
    gp = x['gammaPrime']['marginals']['gamma_prime']
    items.append(('Gamma-prime (exploratory)', 100 * gp['estimate'], 100 * gp['low'], 100 * gp['high'], 'exploratory'))
    cells = res['descriptive']['cells']['gamma']
    raw = sum(c['correct'] for c in cells.values()) / sum(c['runs'] - c['missing'] for c in cells.values())
    items.append(('Gamma as built (no test)', 100 * raw, None, None, 'descriptive'))
    out = {'accuracy.svg': svg.interval_plot('Correct answers by scenario', 'percent correct (GEE marginal, 95% interval)', items, 0, 100,
                                             range(0, 101, 20), note='Gamma as built: share of runs, no interval (design error, not tested).')}
    items = [('%s %s' % (c['id'], c['label'].split(' (')[0]), 100 * c['estimate'], 100 * c['low'], 100 * c['high'], 'confirmatory')
             for c in p['comparisons']]
    out['comparisons.svg'] = svg.interval_plot('Confirmatory comparisons', 'percentage points, second minus first (95% interval)', items,
                                               -50, 50, range(-50, 51, 10), margins=((15, '0.07'), (10, '0.10')),
                                               note='Shaded: equivalence margins +/-10 (primary) and +/-15 (secondary).')
    for outcome, title in (('cost', 'Cost per run'), ('seconds', 'Run time')):
        geo = sec[outcome]['allRuns']['geometricMeans']
        top = max(g['high'] for g in geo.values())
        step = 0.02 if outcome == 'cost' else 10
        hi = step * math.ceil(top / step)
        items = [(NAMES[s], g['geometricMean'], g['low'], g['high'], 'confirmatory') for s, g in geo.items()]
        ticks = [round(step * i, 2) for i in range(int(round(hi / step)) + 1)]
        out['%s.svg' % outcome] = svg.interval_plot('%s by scenario (geometric mean)' % title, SECONDARY_NAMES[outcome] + ', 95% interval',
                                                    items, 0, hi, ticks)
    return out


def analyse(args):
    facts = verify_inputs(args)
    corpus = data.load_corpus(STUDY / 'corpus')
    s1, m1 = data.load_run(args.study_1, 'study-1')
    gp, m2 = data.load_run(args.gamma_prime_1, 'gamma-prime-1')
    samples = {run: [json.loads(line) for line in (Path(folder) / 'samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
               for run, folder in (('study-1', args.study_1), ('gamma-prime-1', args.gamma_prime_1))}
    t15_table = t15.crew_only_table()
    t15_flips = t15.rescore(s1 + gp, t15_table)
    conf = [r for r in s1 if r['scenario'] in CONFIRMATORY]
    fit, prim = primary(conf, args.replicates)
    res = {
        'about': 'Agent study analysis of study-1 and gamma-prime-1 under the plan agreed on 2026-10-21. Generated; do not edit.',
        'inputs': facts,
        'plan': {'confirmatory': [c[0] for c in COMPARISONS], 'equivalencePairs': EQUIVALENCE_PAIRS, 'margins': [m for m, _ in MARGINS],
                 'bootstrap': {'replicates': args.replicates, 'seed': stats.BOOTSTRAP_SEED}},
        'descriptive': {'cells': cell_counts(s1 + gp, ALL_SCENARIOS), 'outcomes': outcomes(s1 + gp, ALL_SCENARIOS),
                        'perTask': per_task(s1 + gp, ALL_SCENARIOS), 'informativeTasks': informative_tasks(conf, CONFIRMATORY)},
        'primary': prim,
        'sensitivity': sensitivity(conf, t15_flips),
        'secondary': secondary(conf),
        'latency': {'study-1': latency(args.study_1, s1), 'gamma-prime-1': latency(args.gamma_prime_1, gp)},
        'spend': {'study-1': spend(args.study_1, s1, m1), 'gamma-prime-1': spend(args.gamma_prime_1, gp, m2)},
        'exploratory': exploratory(s1, gp, t15_table, t15_flips, corpus, fit),
        'runConditions': run_conditions({'study-1': m1, 'gamma-prime-1': m2}, samples),
    }
    return r6(res)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('--study-1', '--gamma-prime-1', '--sums-study-1', '--sums-gamma-prime-1', '--out'):
        parser.add_argument(name, required=True)
    parser.add_argument('--replicates', type=int, default=stats.BOOTSTRAP_REPLICATES)
    parser.add_argument('--evidence', default=str(EVIDENCE), help='the committed evidence folder (the tests point it at a fixture)')
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.resolve().is_relative_to(STUDY.parent.resolve()):
        parser.error('--out must be outside the repository: the outputs are generated')
    try:
        res = analyse(args)
    except data.VerificationError as error:
        print('STOP: %s' % error, file=sys.stderr)
        return 2
    (out / 'figures').mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(res, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    (out / 'tables.md').write_text(tables_md(res), encoding='utf-8', newline='\n')
    for name, text in figures(res).items():
        (out / 'figures' / name).write_text(text, encoding='utf-8', newline='\n')
    print('analysis written to %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
