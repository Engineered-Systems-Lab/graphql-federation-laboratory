"""The power to establish equivalence at +/-10 percentage points under the planned GEE (docs/STUDY-2-DESIGN.md, decision K), as a
seeded script.

    python -B study/analysis2/power.py [--evidence study/evidence | --profiles <table.json>] [--tasks 48] [--runs 2] [--sims 400]
        [--seed 20261027] [--contrasts P1 P2 apollo-cosmo] [--differences 0 5] [--out <file outside the repository>]
        [--write-profiles <file outside the repository>]

What power means here: the chance that a study of k core tasks ESTABLISHES equivalence (the whole 95 percent interval of the difference
inside +/-10 points) under the stated assumptions. It is not the probability that the arms are equivalent.

The method, as the design states it:
- A table of per-task accuracy profiles gives each task's probability of a correct answer in each of the four arms. From the committed
  evidence of study 1 (study/evidence): Guided Direct Access, Apollo Federation and Cosmo Federation are study-1's Beta, Delta and
  Epsilon, and GraphQL Adapters is the gamma-prime-1 run's Gamma; a task's probability is its share of correct runs over both models and
  both trials, a vendor error left out. The observed proportions are treated as true values. `study2_freeze` gives the table of the
  development runs instead (profiles_from_records).
- One simulated study draws k tasks with replacement from the table and runs each task `runs` times in each arm, the models alternating
  (2 runs: one per model, as W4-half). A run is correct with its task's probability in that arm.
- A true difference is set by shifting the reference arm of the contrast (the arm subtracted) by one constant on the probability scale,
  clipped to 0 and 1, chosen so that the difference averaged over the table equals the set difference.
- Each simulated study is analysed with the planned analysis itself (stats2.fit_gee: logistic GEE, arm x model, clustered by task,
  exchangeable working correlation, robust covariance, equal model weights; round and session are left out, as in the design, because the
  Williams schedule makes them close to orthogonal to arm), the contrast by the delta method and the equivalence rule of the whole 95
  percent interval. A fit that does not converge, or whose covariance gives no variance, counts as equivalence not established, and is
  counted.
- Power is the share of the simulated studies that establish equivalence; its Monte Carlo standard error is reported with it, with
  the requested difference, the difference the shifted table achieves and the mean true difference of the drawn tasks (clipping near 0
  and 1 is why they are reported).
- The design's figures are reproduced with the design's rule: each contrast alone, its whole 95 percent interval inside +/-10, and the
  fit usability rule of study 1 (statsmodels converged, finite). `simulate_planned_holm` uses the frozen rules of the draft plan instead:
  P1 and P2 from one fit of each simulated study, both set to the same true difference, their two one-sided tests Holm-adjusted over the
  two, and a fit usable only under stats2's full rule (Fit.problems); its failures are counted apart.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

import stats2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EVIDENCE = HERE.parent / 'evidence'
ARMS = ['beta', 'gamma', 'delta', 'epsilon']
MODELS = ['model-1', 'model-2']
# Each contrast: its weights over the arms and the reference arm whose shift sets the true difference.
CONTRASTS = {
    'P1': ({'delta': 0.5, 'epsilon': 0.5, 'gamma': -1.0}, 'gamma'),
    'P2': ({'delta': 0.5, 'epsilon': 0.5, 'beta': -1.0}, 'beta'),
    'apollo-cosmo': ({'delta': 1.0, 'epsilon': -1.0}, 'epsilon'),
    'apollo-guide': ({'delta': 1.0, 'beta': -1.0}, 'beta'),
    'cosmo-guide': ({'epsilon': 1.0, 'beta': -1.0}, 'beta'),
}
# The design's simulation figures at 48 tasks, 2 runs per task and arm, 400 simulated studies per line (docs/STUDY-2-DESIGN.md).
DESIGN_FIGURES = {('P1', 0): 0.68, ('P1', 5): 0.32, ('P2', 0): 0.53, ('P2', 5): 0.29, ('apollo-cosmo', 0): 0.91, ('apollo-cosmo', 5): 0.46,
                  ('apollo-guide', 0): 0.37, ('apollo-guide', 5): 0.22, ('cosmo-guide', 0): 0.58, ('cosmo-guide', 5): 0.30}
SEED = 20261027
EVIDENCE_ARMS = (('study-1', 'beta', 'beta'), ('study-1', 'delta', 'delta'), ('study-1', 'epsilon', 'epsilon'),
                 ('gamma-prime-1', 'gamma', 'gamma'))


def lf_sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def profiles_from_evidence(evidence=EVIDENCE):
    """The design's table: per task, the share of correct runs in each arm, from study 1's committed score tables."""
    hits, counts, sources = {}, {}, {}
    for run, scenario, arm in EVIDENCE_ARMS:
        path = Path(evidence) / run / 'scores.csv'
        sources[run] = lf_sha256(path)
        with open(path, encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                if row['scenario'] != scenario or row['outcome'] == 'error':
                    continue
                key = (row['taskId'], arm)
                hits[key] = hits.get(key, 0) + int(row['outcome'] == 'correct')
                counts[key] = counts.get(key, 0) + 1
    tasks = sorted({t for t, _ in counts})
    table = {t: {a: hits[(t, a)] / counts[(t, a)] for a in ARMS} for t in tasks}
    return {'about': "per-task accuracy profiles: study-1's Beta, Delta and Epsilon and gamma-prime-1's Gamma, both models and trials pooled",
            'sources': {'%s/scores.csv' % run: digest for run, digest in sorted(sources.items())}, 'arms': ARMS, 'tasks': table}


def profiles_from_records(records):
    """The same table from loaded study-2 records (data2.load_bundle): the development runs, for study2_freeze. Core set, four arms."""
    hits, counts = {}, {}
    for r in records:
        if r['arm'] in ARMS and r['set'] == 'core' and r['correct'] is not None:
            key = (r['task'], r['arm'])
            hits[key] = hits.get(key, 0) + r['correct']
            counts[key] = counts.get(key, 0) + 1
    tasks = sorted({t for t, _ in counts})
    missing = [(t, a) for t in tasks for a in ARMS if (t, a) not in counts]
    if missing:
        raise ValueError('a task lacks runs in an arm: %s' % (missing[:3],))
    return {'about': 'per-task accuracy profiles of study-2 runs', 'sources': {}, 'arms': ARMS,
            'tasks': {t: {a: hits[(t, a)] / counts[(t, a)] for a in ARMS} for t in tasks}}


def shifted(profiles, contrast, difference):
    """The probability matrix (tasks x arms) with the reference arm shifted so the mean difference over the table is `difference`."""
    weights, reference = CONTRASTS[contrast]
    tasks = sorted(profiles['tasks'])
    base = np.array([[profiles['tasks'][t][a] for a in ARMS] for t in tasks])
    ref = ARMS.index(reference)
    w = np.array([weights.get(a, 0.0) for a in ARMS])

    def mean_difference(c):
        p = base.copy()
        p[:, ref] = np.clip(p[:, ref] + c, 0.0, 1.0)
        return float((p @ w).mean()), p

    lo, hi = -1.0, 1.0  # the difference falls as the reference arm rises
    if not (mean_difference(hi)[0] <= difference <= mean_difference(lo)[0]):
        raise ValueError('the difference %s cannot be reached by shifting %s' % (difference, reference))
    for _ in range(200):
        mid = (lo + hi) / 2
        if mean_difference(mid)[0] > difference:
            lo = mid
        else:
            hi = mid
    c = (lo + hi) / 2
    return mean_difference(c)[1], c, mean_difference(0.0)[0]


def simulate_line(profiles, contrast, difference_points, tasks=48, runs=2, sims=400, seed=SEED, margin=stats2.MARGIN):
    """One line of the power table: the share of `sims` simulated studies that establish equivalence."""
    weights, _ = CONTRASTS[contrast]
    p, shift, observed = shifted(profiles, contrast, difference_points / 100.0)
    rng = np.random.default_rng([seed, sorted(CONTRASTS).index(contrast), int(round(1000 * difference_points)) + 100000])
    established = not_converged = degenerate = 0
    drawn = []
    for _ in range(sims):
        draw = rng.integers(0, p.shape[0], size=tasks)
        drawn.append(float((p[draw] @ np.array([weights.get(a, 0.0) for a in ARMS])).mean()))
        u = rng.random((tasks, len(ARMS), runs))
        rows = []
        for i, t in enumerate(draw):
            for a, arm in enumerate(ARMS):
                for j in range(runs):
                    rows.append({'arm': arm, 'model': MODELS[j % 2], 'task': i, 'row': None, 'session': None,
                                 'correct': int(u[i, a, j] < p[t, a])})
        try:
            fit = stats2.fit_gee(rows, 'correct', ARMS, MODELS, rounds=False, sessions=False)
        except stats2.FitError:
            degenerate += 1
            continue
        if not fit.converged:
            not_converged += 1
            continue
        value, grad = 0.0, 0.0
        for arm, w in weights.items():
            v, g = fit.marginal(arm)
            value, grad = value + w * v, grad + w * g
        try:
            summary = fit.contrast((value, grad), (0.0, grad * 0.0))
        except stats2.FitError:
            degenerate += 1
            continue
        established += int(stats2.equivalence(summary, margin)['equivalent'])
    power = established / sims
    return {'contrast': contrast, 'differencePoints': difference_points, 'tasks': tasks, 'runsPerTaskAndArm': runs, 'simulations': sims,
            'seed': seed, 'margin': margin, 'established': established, 'power': power, 'monteCarloSe': math.sqrt(power * (1 - power) / sims),
            'notConverged': not_converged, 'degenerate': degenerate, 'referenceShift': shift, 'unshiftedTableDifference': observed,
            'achievedTableDifference': float((p @ np.array([weights.get(a, 0.0) for a in ARMS])).mean()),
            'meanDrawnDifference': float(np.mean(drawn)),
            'designFigure': DESIGN_FIGURES.get((contrast, difference_points)) if (tasks, runs, sims) == (48, 2, 400) else None}


def simulate_planned_holm(profiles, difference_points, tasks=48, runs=2, sims=400, seed=SEED, margin=stats2.MARGIN):
    """P1 and P2 together under the draft plan's rules: one fit per simulated study, both true differences set to `difference_points`
    (GraphQL Adapters and Guided Direct Access shifted apart), equivalence by the Holm-adjusted two one-sided tests, a fit usable only
    under the full rule; returns the power of each and the counts of fits that could not be used."""
    target = difference_points / 100.0
    p1, shift1, _ = shifted(profiles, 'P1', target)
    p2, shift2, _ = shifted(profiles, 'P2', target)
    p = p1.copy()
    p[:, ARMS.index('beta')] = p2[:, ARMS.index('beta')]
    rng = np.random.default_rng([seed, 99, int(round(1000 * difference_points)) + 100000])
    established = {'P1': 0, 'P2': 0}
    unusable = 0
    for _ in range(sims):
        draw = rng.integers(0, p.shape[0], size=tasks)
        u = rng.random((tasks, len(ARMS), runs))
        rows = [{'arm': arm, 'model': MODELS[j % 2], 'task': i, 'row': None, 'session': None, 'correct': int(u[i, a, j] < p[t, a])}
                for i, t in enumerate(draw) for a, arm in enumerate(ARMS) for j in range(runs)]
        try:
            fit = stats2.fit_gee(rows, 'correct', ARMS, MODELS, rounds=False, sessions=False)
            if fit.problems():
                raise stats2.FitError('unusable')
            summaries = []
            for name in ('P1', 'P2'):
                value, grad = 0.0, 0.0
                for arm, w in CONTRASTS[name][0].items():
                    v, g = fit.marginal(arm)
                    value, grad = value + w * v, grad + w * g
                summaries.append(fit.contrast((value, grad), (0.0, grad * 0.0)))
        except stats2.FitError:
            unusable += 1
            continue
        for name, eq in zip(('P1', 'P2'), stats2.holm_equivalence(summaries, margin)):
            established[name] += int(eq['equivalentHolm'])
    out = {'rule': 'P1 and P2 Holm-adjusted two one-sided tests, full fit usability rule', 'differencePoints': difference_points,
           'tasks': tasks, 'runsPerTaskAndArm': runs, 'simulations': sims, 'seed': seed, 'unusableFits': unusable,
           'referenceShifts': {'gamma': shift1, 'beta': shift2}}
    for name in ('P1', 'P2'):
        power = established[name] / sims
        out[name] = {'established': established[name], 'power': power, 'monteCarloSe': math.sqrt(power * (1 - power) / sims)}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', default=str(EVIDENCE))
    parser.add_argument('--profiles', help='a profile table (JSON) instead of the committed evidence')
    parser.add_argument('--tasks', type=int, default=48)
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--sims', type=int, default=400)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--contrasts', nargs='+', default=['P1', 'P2', 'apollo-cosmo'], choices=sorted(CONTRASTS))
    parser.add_argument('--differences', nargs='+', type=float, default=[0.0, 5.0])
    parser.add_argument('--out')
    parser.add_argument('--write-profiles')
    parser.add_argument('--holm', action='store_true', help='also the P1 and P2 lines under the draft plan\'s Holm rule')
    args = parser.parse_args(argv)
    for name in ('out', 'write_profiles'):
        value = getattr(args, name)
        if value and Path(value).resolve().is_relative_to(REPO.resolve()):
            parser.error('--%s must be outside the repository: the output is generated' % name.replace('_', '-'))
    profiles = (json.loads(Path(args.profiles).read_text(encoding='utf-8')) if args.profiles else profiles_from_evidence(args.evidence))
    if args.write_profiles:
        Path(args.write_profiles).write_text(json.dumps(profiles, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    lines = [simulate_line(profiles, c, d if d != int(d) else int(d), args.tasks, args.runs, args.sims, args.seed)
             for c in args.contrasts for d in args.differences]
    holm_lines = ([simulate_planned_holm(profiles, d if d != int(d) else int(d), args.tasks, args.runs, args.sims, args.seed)
                   for d in args.differences] if args.holm else [])
    text = json.dumps({'about': 'power to establish equivalence at +/-%d points under the planned GEE' % stats2.MARGIN,
                       'profiles': {'about': profiles['about'], 'sources': profiles['sources'], 'tasks': len(profiles['tasks'])},
                       'lines': lines, 'planHolmLines': holm_lines}, indent=2, sort_keys=True) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8', newline='\n')
    for line in lines:
        print('%-13s difference %4s points: power %.3f (Monte Carlo SE %.3f)%s' % (
            line['contrast'], line['differencePoints'], line['power'], line['monteCarloSe'],
            '' if line['designFigure'] is None else '; design %.2f' % line['designFigure']))
    for line in holm_lines:
        print('P1 and P2 under Holm, difference %4s points: P1 %.3f, P2 %.3f (unusable fits %d)' % (
            line['differencePoints'], line['P1']['power'], line['P2']['power'], line['unusableFits']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
