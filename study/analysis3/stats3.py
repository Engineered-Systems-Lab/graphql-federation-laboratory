"""The confirmatory statistics of study 3 (PLAN.md): the effort families, the CSL family, the accuracy floor and the rule that selects
between a GEE and its prespecified bootstrap fallback.

`confirmatory` is the whole selection procedure in one function. The analysis and validate3.py both call it, so what is validated is what
runs. Study 2's GEE (stats2.fit_gee, Fit.problems, planned_conditions) and study 1's Holm are used unchanged.
"""
import math

import numpy as np
from scipy import stats as sps
from statsmodels.genmod import families
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.generalized_estimating_equations import GEE

import data3  # noqa: F401  (puts study/analysis2 and study/analysis on the path)
import stats2

ARMS = data3.SQUARE_ARMS
FEDERATION = {'delta': 0.5, 'epsilon': 0.5}
COMPARISONS = (('P1', 'gamma', 'Federation (mean of Apollo and Cosmo) over GraphQL Adapters'),
               ('P2', 'beta', 'Federation (mean of Apollo and Cosmo) over Guided Direct Access'))
EFFORT_FAMILIES = ('toolCalls', 'cost')
SEED = 20261118
REPLICATES = 10000
UNUSABLE_LIMIT = 0.01
FLOOR_MARGIN = 0.10
FAMILY_ALPHA = 0.05
CSL_COVARIANCE = 'bias_reduced'  # A21
# The two CSL tests: the rows' group field, the reference group, the other group, the predicted sign of other minus reference.
CSL_TESTS = (('forwardReverse', 'cslGroup', 'forward', 'reverse', 1, 'Advantage smaller on reverse questions than on forward questions'),
             ('joinWidth', 'joinGroup', 'one', 'several', -1, 'Advantage larger on questions that read several systems than on one'))
FIT_ERRORS = (stats2.FitError, ValueError, ZeroDivisionError, OverflowError, ArithmeticError, np.linalg.LinAlgError)


def weights_of(comparator):
    return dict(FEDERATION, **{comparator: -1.0})


# ------------------------------------------------------------------------------------------------------------------ bootstrap pieces
def stratified_weights(rng, strata, replicates):
    """Replicate weights (replicates x tasks): whole tasks resampled with replacement within each stratum. `strata` is a list of index
    arrays that together cover the tasks."""
    size = sum(len(s) for s in strata)
    weights = np.zeros((replicates, size))
    for members in strata:
        weights[:, members] = rng.multinomial(len(members), np.full(len(members), 1.0 / len(members)), replicates)
    return weights


def two_sided_summary(delta, stars):
    """A10's matched test and interval on the log scale: p = (1 + #{|d* - d| >= |d|}) / (B_valid + 1), and d +/- q, q the order statistic
    of |d* - d| chosen so that the interval excludes 0 exactly when p < 0.05."""
    deviations = np.sort(np.abs(stars - delta))
    valid = deviations.size
    p = (1 + int(np.sum(deviations >= abs(delta)))) / (valid + 1)
    index = (95 * (valid + 1)) // 100 + 1  # the 1-based order statistic
    q = float(deviations[index - 1]) if index <= valid else math.inf
    return {'estimate': delta, 'low': delta - q, 'high': delta + q, 'p': p}


def one_sided_summary(delta, stars, sign):
    """A10's one-sided test: p = (1 + #{s(d* - d) >= s d}) / (B_valid + 1), with the matching one-sided 95 percent bound."""
    deviations = np.sort(sign * (stars - delta))
    valid = deviations.size
    p = (1 + int(np.sum(deviations >= sign * delta))) / (valid + 1)
    index = (95 * (valid + 1)) // 100 + 1
    q = float(deviations[index - 1]) if index <= valid else math.inf
    return {'estimate': delta, 'bound': delta - sign * q, 'p': p}


class CellTable:
    """The sums and counts of a value per task and arm x model x round cell, for A10's estimator: the mean of each cell, each arm the
    equal-weight mean of its cells, so over rounds and then over the two models."""

    def __init__(self, rows, value, models, rounds, tasks):
        self.tasks, self.cells = list(tasks), [(a, m, k) for a in ARMS for m in models for k in rounds]
        position = {cell: i for i, cell in enumerate(self.cells)}
        index = {task: i for i, task in enumerate(self.tasks)}
        self.sums, self.counts = np.zeros((len(self.tasks), len(self.cells))), np.zeros((len(self.tasks), len(self.cells)))
        for r in rows:
            i, j = index[r['task']], position[(r['arm'], r['model'], r['row'])]
            self.sums[i, j] += value(r)
            self.counts[i, j] += 1.0
        self.per_arm = len(models) * len(rounds)

    def arm_means(self, weights):
        """(arm: array of the arm's value per replicate); a replicate with an empty cell is not finite."""
        with np.errstate(invalid='ignore', divide='ignore'):
            means = (weights @ self.sums) / (weights @ self.counts)
        means = np.atleast_2d(means)
        return {a: means[:, i * self.per_arm:(i + 1) * self.per_arm].mean(axis=1) for i, a in enumerate(ARMS)}


def contrast_of(arms, comparator):
    return sum(w * arms[a] for a, w in weights_of(comparator).items())


def strata_indices(tasks, stratum_of):
    groups = {}
    for i, task in enumerate(tasks):
        groups.setdefault(stratum_of[task], []).append(i)
    return [np.array(groups[k]) for k in sorted(groups)]


def rounds_of(rows):
    return sorted({r['row'] for r in rows})


def small_sample_factor(tasks, strata):
    """A25: the widening of the effort fallback's bootstrap deviations, sqrt(n / (n - s)) x t(0.975, n - s) / z(0.975)."""
    df = tasks - strata
    return math.sqrt(tasks / df) * float(sps.t.ppf(0.975, df) / sps.norm.ppf(0.975))


def effort_fallback(rows, outcome, models, stratum_of, replicates=REPLICATES, seed=SEED, rounds=None):
    """A10's fallback for an effort family: the same contrasts on the transformed outcome, without a session adjustment, its bootstrap
    deviations widened (A25). `rounds` are the planned rounds, so a round with no runs is an empty required cell."""
    use = stats2.usable(rows, outcome)
    tasks = sorted({r['task'] for r in use})
    table = CellTable(use, lambda r: stats2.transform(outcome, r[outcome]), models, rounds or rounds_of(use), tasks)
    full = table.arm_means(np.ones((1, len(tasks))))
    rng = np.random.default_rng([seed, EFFORT_FAMILIES.index(outcome)])
    strata = strata_indices(tasks, stratum_of)
    arms = table.arm_means(stratified_weights(rng, strata, replicates))
    out = {'attempted': replicates, 'comparisons': {}}
    usable_mask = np.ones(replicates, bool)
    for arm in ARMS:
        usable_mask &= np.isfinite(arms[arm])
    out['usable'] = int(usable_mask.sum())
    if not all(np.isfinite(full[a][0]) for a in ARMS):
        return dict(out, estimable=False, reason='a cell of the full sample is empty')
    if 1.0 - usable_mask.mean() > UNUSABLE_LIMIT:
        return dict(out, estimable=False, reason='more than 1 percent of the replicates have an empty cell')
    if len(tasks) <= len(strata):
        return dict(out, estimable=False, reason='there are no more tasks than strata')
    factor = small_sample_factor(len(tasks), len(strata))
    out['widening'] = factor
    for cid, comparator, _ in COMPARISONS:
        delta = float(contrast_of(full, comparator)[0])
        out['comparisons'][cid] = two_sided_summary(delta, delta + factor * (contrast_of(arms, comparator)[usable_mask] - delta))
    return dict(out, estimable=True)


def per_task_contrasts(rows, models, comparator='gamma'):
    """A15: each task's own contrast on log(1 + calls). Within a task's model and round the contrast is 0.5 Apollo + 0.5 Cosmo minus the
    comparator; a pair that lacks any of the three runs is left out, so a missing run never changes federation's weights; the task's
    contrast is the mean of its pairs, and a task with no complete pair has none."""
    values = {}
    for r in rows:
        values.setdefault((r['task'], r['model'], r['row']), {}).setdefault(r['arm'], stats2.transform('toolCalls', r['toolCalls']))
    per_task = {}
    for (task, _, _), arms in values.items():
        if comparator in arms and all(a in arms for a in FEDERATION):
            per_task.setdefault(task, []).append(sum(w * arms[a] for a, w in FEDERATION.items()) - arms[comparator])
    return {task: sum(v) / len(v) for task, v in per_task.items()}


def rescaled(stars, mean, size, factor=1.0):
    """A21 and A24: a group's bootstrap means with their deviations from the group's mean widened by sqrt(n / (n - 1)) and by `factor`."""
    return mean + factor * math.sqrt(size / (size - 1)) * (stars - mean)


def stratified_acceleration(table, comparator, strata):
    """The BCa acceleration for resampling within fixed strata (the multisample jackknife). Leaving a task out gives the other tasks of its
    stratum the weight n / (n - 1), so every stratum keeps its size, as it does in the bootstrap."""
    numerator, denominator = 0.0, 0.0
    for members in strata:
        size = len(members)
        if size < 2:
            continue
        weights = np.ones((size, table.sums.shape[0]))
        weights[:, members] = size / (size - 1)
        weights[np.arange(size), members] = 0.0
        values = contrast_of(table.arm_means(weights), comparator)
        values = values[np.isfinite(values)]
        influence = (size - 1) * (values.mean() - values)
        numerator += float(np.sum(influence ** 3)) / size ** 3
        denominator += float(np.sum(influence ** 2)) / size ** 2
    return numerator / (6.0 * denominator ** 1.5) if denominator > 0 else 0.0


def bca_lower(stars, estimate, acceleration, alpha=0.025):
    """A22: the bias-corrected and accelerated lower bound. The bias correction comes from the replicates' share below the estimate."""
    share = float(np.mean(stars < estimate) + 0.5 * np.mean(stars == estimate))
    share = min(max(share, 1.0 / (stars.size + 1)), stars.size / (stars.size + 1))
    z0, z_alpha = float(sps.norm.ppf(share)), float(sps.norm.ppf(alpha))
    denominator = 1.0 - acceleration * (z0 + z_alpha)
    level = float(sps.norm.cdf(z0 + (z0 + z_alpha) / denominator)) if denominator > 0 else 0.0
    return float(np.quantile(stars, level))


def csl_fallback(rows, models, name, field, reference, other, sign, replicates=REPLICATES, seed=SEED):
    """A15's CSL fallback: per-task P1 contrasts, whole tasks resampled within each group, the difference of the two groups' means, each
    group's deviations rescaled (A21)."""
    use = [r for r in rows if r.get(field) in (reference, other)]
    contrasts = per_task_contrasts(use, models)
    group_of = {r['task']: r[field] for r in use}
    first = np.array([v for t, v in sorted(contrasts.items()) if group_of[t] == reference])
    second = np.array([v for t, v in sorted(contrasts.items()) if group_of[t] == other])
    if len(first) < 2 or len(second) < 2:
        return {'estimable': False, 'reason': 'a group has fewer than two tasks with a contrast'}
    rng = np.random.default_rng([seed, 11, [t[0] for t in CSL_TESTS].index(name)])
    star_first = (rng.multinomial(len(first), np.full(len(first), 1.0 / len(first)), replicates) @ first) / len(first)
    star_second = (rng.multinomial(len(second), np.full(len(second), 1.0 / len(second)), replicates) @ second) / len(second)
    delta = float(second.mean() - first.mean())
    factor = float(sps.t.ppf(0.975, len(first) + len(second) - 2) / sps.norm.ppf(0.975))  # A24
    summary = one_sided_summary(delta, rescaled(star_second, second.mean(), len(second), factor) - rescaled(star_first, first.mean(), len(first), factor), sign)
    return dict(summary, estimable=True, attempted=replicates, usable=replicates, tasks={reference: len(first), other: len(second)},
                groupLogRatios={reference: float(first.mean()), other: float(second.mean())})


def accuracy_floor(rows, comparator, models, stratum_of, replicates=REPLICATES, seed=SEED, vendor_errors_wrong=False, rounds=None):
    """A16 and A22: federation minus the comparator in accuracy by A10's recipe; the bound is the BCa lower bound at 2.5 percent, and the
    floor is cleared only when it is above -10 points and at most 1 percent of the replicates are unusable. `rounds` are the planned
    rounds, so a round with no runs is an empty required cell."""
    use = [dict(r, correct=0) if r['correct'] is None else r for r in rows] if vendor_errors_wrong else [r for r in rows if r['correct'] is not None]
    tasks = sorted({r['task'] for r in use})
    table = CellTable(use, lambda r: float(r['correct']), models, rounds or rounds_of(use), tasks)
    full = table.arm_means(np.ones((1, len(tasks))))
    rng = np.random.default_rng([seed, 21, ARMS.index(comparator), int(vendor_errors_wrong)])
    strata = strata_indices(tasks, stratum_of)
    stars = contrast_of(table.arm_means(stratified_weights(rng, strata, replicates)), comparator)
    valid = stars[np.isfinite(stars)]
    out = {'comparator': comparator, 'attempted': replicates, 'usable': int(valid.size), 'margin': -FLOOR_MARGIN}
    if not all(np.isfinite(full[a][0]) for a in ARMS) or 1.0 - valid.size / replicates > UNUSABLE_LIMIT:
        return dict(out, estimable=False, cleared=False, reason='an empty cell in the full sample or in more than 1 percent of the replicates')
    estimate = float(contrast_of(full, comparator)[0])
    lower = bca_lower(valid, estimate, stratified_acceleration(table, comparator, strata))
    return dict(out, estimable=True, estimate=estimate, lower=lower, cleared=bool(lower > -FLOOR_MARGIN))


# ------------------------------------------------------------------------------------------------------------------ the GEE families
def planned_rounds(conditions):
    return sorted({key[0] for key, _ in conditions})


def require_planned_rounds(rows, conditions):
    """A GEE cannot standardize over a planned round that has no runs: the round's term would be missing from the model."""
    absent = sorted(set(planned_rounds(conditions)) - {r['row'] for r in rows})
    if absent:
        raise stats2.FitError('the planned rounds %s have no runs' % absent)


def effort_gee(rows, outcome, models, conditions, cov_type='robust'):
    """P1 and P2 of one effort family from the primary GEE; raises FitError when the fit cannot be used."""
    require_planned_rounds(rows, conditions)
    fit = stats2.fit_gee(rows, outcome, ARMS, models, conditions=conditions, cov_type=cov_type)
    problems = fit.problems(interaction=True)
    if problems:
        raise stats2.FitError('; '.join(problems))
    out = {}
    for cid, comparator, _ in COMPARISONS:
        value, grad = 0.0, 0.0
        for arm, weight in weights_of(comparator).items():
            v, g = fit.marginal(arm)
            value, grad = value + weight * v, grad + weight * g
        out[cid] = fit.contrast((value, grad), (0.0, grad * 0.0))
    return fit, out


def effort_family(rows, outcome, models, conditions, stratum_of, replicates=REPLICATES, seed=SEED, force_fallback=False):
    """One effort family under the selection rule: the GEE when its fit is usable, otherwise A10's fallback for both comparisons."""
    problems = ['the fallback was forced'] if force_fallback else []
    summaries, facts = None, None
    if not force_fallback:
        try:
            fit, summaries = effort_gee(rows, outcome, models, conditions)
            facts = fit.facts()
        except FIT_ERRORS as error:
            problems, summaries = ['%s: %s' % (type(error).__name__, error)], None
    method = 'gee'
    bootstrap = None
    if summaries is None:
        method = 'bootstrap'
        bootstrap = effort_fallback(rows, outcome, models, stratum_of, replicates, seed, planned_rounds(conditions))
        if not bootstrap['estimable']:
            return {'outcome': outcome, 'method': 'notEstimable', 'problems': problems + [bootstrap['reason']], 'comparisons': [],
                    'attempted': bootstrap['attempted'], 'usable': bootstrap['usable']}
        summaries = bootstrap['comparisons']
    adjusted = stats2.holm([summaries[cid]['p'] for cid, _, _ in COMPARISONS])
    comparisons = []
    for (cid, comparator, label), p_holm in zip(COMPARISONS, adjusted):
        s = summaries[cid]
        comparisons.append({'id': cid, 'comparator': comparator, 'label': label, 'logRatio': s['estimate'], 'ratio': math.exp(s['estimate']),
                            'low': math.exp(s['low']), 'high': math.exp(s['high']), 'logLow': s['low'], 'logHigh': s['high'], 'p': s['p'],
                            'pHolm': p_holm, 'rejected': bool(p_holm < FAMILY_ALPHA)})
    out = {'outcome': outcome, 'method': method, 'problems': problems, 'comparisons': comparisons}
    if facts is not None:
        out['fit'] = facts
    if bootstrap is not None:
        out.update(attempted=bootstrap['attempted'], usable=bootstrap['usable'])
    return out


class GroupDesign(stats2.Design):
    """The primary design plus a group main effect and a group x arm interaction (A12)."""

    def __init__(self, arms, models, rounds=(), sessions=()):
        super().__init__(arms, models, rounds, sessions, True)
        self.names = self.names + ['group'] + ['group:arm[%s]' % a for a in self.arms[1:]]

    def row(self, arm, model, round_=None, session=None, group=0):
        base = super().row(arm, model, round_, session)
        a = self.arms.index(arm)
        return np.concatenate([base, [float(group)], [float(group and a == i) for i in range(1, len(self.arms))]])


def group_gee(rows, field, reference, other, models, conditions):
    """A12's GEE of log(1 + calls): the primary terms, a group main effect and group x arm, clustered by task, with the bias-reduced
    covariance (A21); a stats2.Fit."""
    use = [r for r in rows if r.get(field) in (reference, other)]
    require_planned_rounds(use, conditions)
    round_levels = sorted({r['row'] for r in use})
    session_list = stats2.session_levels(use)

    def matrix(sessions):
        design = GroupDesign(ARMS, models, round_levels, sessions)
        X = np.array([design.row(r['arm'], r['model'], r['row'], r['session'] if sessions else None, int(r[field] == other)) for r in use])
        return design, X

    design, X = matrix(session_list)
    dropped = False
    if session_list and np.linalg.matrix_rank(X) < X.shape[1]:
        session_list, dropped = [], True
        design, X = matrix(session_list)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise stats2.FitError('the design of the group model has dependent columns')
    y = np.array([stats2.transform('toolCalls', r['toolCalls']) for r in use])
    tasks = sorted({r['task'] for r in use})
    index = {t: i for i, t in enumerate(tasks)}
    groups = np.array([index[r['task']] for r in use])
    result = GEE(y, X, groups=groups, family=families.Gaussian(), cov_struct=Exchangeable()).fit(maxiter=200, cov_type=CSL_COVARIANCE)
    params, cov = np.asarray(result.params), np.asarray(result.cov_params())
    converged = bool(getattr(result, 'converged', True)) and bool(np.all(np.isfinite(params))) and bool(np.all(np.isfinite(cov)))
    return stats2.Fit(design, params, cov, 'identity', len(use), len(tasks), converged, CSL_COVARIANCE, stats2.collapse(conditions, session_list),
                      (), dropped)


def p1_vector(design, group):
    """The coefficients of a group's P1 log ratio (averaged over the two models; the round and session terms cancel)."""
    out = np.zeros(len(design.names))
    for model in design.models:
        for arm, weight in weights_of('gamma').items():
            out = out + weight * design.row(arm, model, design.rounds[0] if design.rounds else None, None, group) / len(design.models)
    return out


def csl_wald(fit, sign):
    """The Wald test of the interaction contrast: the P1 log ratio of the other group minus the reference group's, one-sided, with a t
    reference on the number of tasks minus 1 (A24)."""
    first, second = p1_vector(fit.design, 0), p1_vector(fit.design, 1)
    vector = second - first
    delta = float(vector @ fit.params)
    variance = float(vector @ fit.cov @ vector)
    if not (variance > 0 and math.isfinite(variance)):
        raise stats2.FitError('the covariance gives the variance %r for the interaction contrast' % variance)
    se = math.sqrt(variance)
    df = fit.clusters - 1
    return {'estimate': delta, 'se': se, 'df': df, 'p': float(sps.t.sf(sign * delta / se, df)), 'bound': delta - sign * float(sps.t.ppf(0.95, df)) * se,
            'groupLogRatios': (float(first @ fit.params), float(second @ fit.params))}


def csl_family(rows, planned, models, replicates=REPLICATES, seed=SEED, force_fallback=False):
    """The third family (A6, A12, A15): both tests from their GEEs when both fits are usable, otherwise both from the fallback."""
    results, problems = {}, ['the fallback was forced'] if force_fallback else []
    if not force_fallback:
        for name, field, reference, other, sign, _ in CSL_TESTS:
            try:
                conditions = stats2.planned_conditions([r for r in planned if r.get(field) in (reference, other)])
                fit = group_gee(rows, field, reference, other, models, conditions)
                found = fit.problems(interaction=True)
                if found:
                    raise stats2.FitError('; '.join(found))
                wald = csl_wald(fit, sign)
                results[name] = dict(wald, groupLogRatios={reference: wald['groupLogRatios'][0], other: wald['groupLogRatios'][1]},
                                     tasks={level: len({r['task'] for r in rows if r.get(field) == level}) for level in (reference, other)})
            except FIT_ERRORS as error:
                problems.append('%s: %s: %s' % (name, type(error).__name__, error))
    method = 'gee'
    if problems:
        method, results = 'bootstrap', {}
        for name, field, reference, other, sign, _ in CSL_TESTS:
            results[name] = csl_fallback(rows, models, name, field, reference, other, sign, replicates, seed)
        missing = [name for name, r in results.items() if not r['estimable']]
        if missing:
            return {'method': 'notEstimable', 'problems': problems + ['the fallback of %s has too few tasks' % ', '.join(missing)], 'tests': []}
    adjusted = stats2.holm([results[t[0]]['p'] for t in CSL_TESTS])
    tests = []
    for (name, field, reference, other, sign, label), p_holm in zip(CSL_TESTS, adjusted):
        entry = dict(results[name], id=name, label=label, groups=[reference, other], predictedSign=sign, pHolm=p_holm, rejected=bool(p_holm < FAMILY_ALPHA))
        tests.append(entry)
    return {'method': method, 'problems': problems, 'tests': tests}


def confirmatory(planned, models, stratum_of, replicates=REPLICATES, seed=SEED, force_fallback=False):
    """The whole selection procedure on the square's core runs: `planned` are all the planned runs, vendor errors included."""
    rows = [r for r in planned if r['correct'] is not None]
    conditions = stats2.planned_conditions(planned)
    floors = {comparator: accuracy_floor(rows, comparator, models, stratum_of, replicates, seed, rounds=planned_rounds(conditions))
              for _, comparator, _ in COMPARISONS}
    effort = {outcome: effort_family(rows, outcome, models, conditions, stratum_of, replicates, seed, force_fallback) for outcome in EFFORT_FAMILIES}
    csl = csl_family(rows, planned, models, replicates, seed, force_fallback)
    for family in effort.values():
        for entry in family['comparisons']:
            entry['floorCleared'] = floors[entry['comparator']]['cleared']
            entry['claimed'] = bool(entry['rejected'] and entry['floorCleared'])
    for test in csl['tests']:
        test['floorCleared'] = floors['gamma']['cleared']
        test['claimed'] = bool(test['rejected'] and test['floorCleared'])
    return {'floors': floors, 'effort': effort, 'csl': csl}
