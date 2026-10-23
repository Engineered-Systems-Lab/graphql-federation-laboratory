"""The statistics of the Abstraction ladder study analysis, as the agreed plan (2026-10-21) fixes them.

- Primary model: correct (1/0) ~ scenario x model, logistic, fitted with GEE clustered by task (exchangeable working correlation, robust
  sandwich covariance). Effects are differences of marginal probabilities in percentage points (each scenario's probability averaged over
  the two models with equal weight), with 95 percent Wald intervals from the delta method. The p-value of a comparison is the Wald test
  of that same difference, so the interval and the test agree.
- Holm correction over the named confirmatory comparisons.
- Equivalence: holds at a margin only if the WHOLE 95 percent interval lies inside (-margin, +margin), as the plan says; that is the
  two one-sided tests at 2.5 percent each, stricter than the usual 90 percent interval.
- Cross-checks: Cochran's Q and exact McNemar tests on runs matched by task, model and trial; 95 percent percentile intervals from a
  bootstrap over tasks.
- Secondary outcomes: the same GEE structure, Gaussian on the log of the outcome; effects are ratios of geometric means.
"""
import math

import numpy as np
from scipy import stats as sps
from statsmodels.genmod import families
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.generalized_estimating_equations import GEE
from statsmodels.stats.contingency_tables import cochrans_q
from statsmodels.stats.multitest import multipletests

Z95 = sps.norm.ppf(0.975)
BOOTSTRAP_SEED = 20261021
BOOTSTRAP_REPLICATES = 10000


class Design:
    """Treatment coding of scenario x model with the full interaction; the first level of each factor is the reference."""

    def __init__(self, scenarios, models):
        self.scenarios, self.models = list(scenarios), list(models)
        self.names = (['intercept'] + ['scenario[%s]' % s for s in self.scenarios[1:]] + ['model[%s]' % m for m in self.models[1:]]
                      + ['scenario[%s]:model[%s]' % (s, m) for s in self.scenarios[1:] for m in self.models[1:]])

    def row(self, scenario, model):
        s, m = self.scenarios.index(scenario), self.models.index(model)
        x = [1.0] + [float(s == i) for i in range(1, len(self.scenarios))] + [float(m == j) for j in range(1, len(self.models))]
        x += [float(s == i and m == j) for i in range(1, len(self.scenarios)) for j in range(1, len(self.models))]
        return np.array(x)

    def interaction_columns(self):
        return [i for i, name in enumerate(self.names) if ':' in name]


class Fit:
    """A fitted GEE of one outcome: parameters, robust covariance and the design that maps cells to linear predictors."""

    def __init__(self, design, params, cov, logistic, n, clusters, converged, cov_kind):
        self.design, self.params, self.cov, self.logistic = design, params, cov, logistic
        self.n, self.clusters, self.converged, self.cov_kind = n, clusters, converged, cov_kind

    def cell(self, scenario, model):
        """(value, gradient) of a cell on the outcome scale used for contrasts: probability for the logistic model, log-mean otherwise."""
        x = self.design.row(scenario, model)
        eta = float(x @ self.params)
        if not self.logistic:
            return eta, x
        p = 1.0 / (1.0 + math.exp(-eta))
        return p, p * (1.0 - p) * x

    def marginal(self, scenario, models=None):
        models = models or self.design.models
        cells = [self.cell(scenario, m) for m in models]
        return sum(v for v, _ in cells) / len(cells), sum(g for _, g in cells) / len(cells)

    def model_marginal(self, model, scenarios=None):
        scenarios = scenarios or self.design.scenarios
        cells = [self.cell(s, model) for s in scenarios]
        return sum(v for v, _ in cells) / len(cells), sum(g for _, g in cells) / len(cells)

    def contrast(self, a, b):
        """Wald summary of value(a) - value(b), where a and b are (value, gradient) pairs."""
        diff, grad = a[0] - b[0], a[1] - b[1]
        se = math.sqrt(float(grad @ self.cov @ grad))
        z = diff / se if se > 0 else float('inf')
        return {'estimate': diff, 'se': se, 'low': diff - Z95 * se, 'high': diff + Z95 * se, 'p': float(2 * sps.norm.sf(abs(z)))}

    def interaction_test(self):
        idx = self.design.interaction_columns()
        b = self.params[idx]
        v = self.cov[np.ix_(idx, idx)]
        chi2 = float(b @ np.linalg.solve(v, b))
        return {'chi2': chi2, 'df': len(idx), 'p': float(sps.chi2.sf(chi2, len(idx)))}


def fit_gee(rows, outcome, scenarios, models, logistic=True, cov_type='robust'):
    """Fit the plan's GEE to rows with a non-missing value of `outcome` (a key of the row dicts)."""
    use = [r for r in rows if r.get(outcome) is not None and r['scenario'] in scenarios]
    design = Design(scenarios, models)
    X = np.array([design.row(r['scenario'], r['model']) for r in use])
    y = np.array([float(r[outcome]) if logistic else math.log(float(r[outcome])) for r in use])
    tasks = sorted({r['task'] for r in use})
    groups = np.array([tasks.index(r['task']) for r in use])
    family = families.Binomial() if logistic else families.Gaussian()
    model = GEE(y, X, groups=groups, family=family, cov_struct=Exchangeable())
    result = model.fit(maxiter=200, cov_type=cov_type)
    converged = bool(getattr(result, 'converged', True)) and bool(np.all(np.isfinite(result.params)))
    return Fit(design, np.asarray(result.params), np.asarray(result.cov_params()), logistic, len(use), len(tasks), converged, cov_type)


def holm(pvalues):
    """Holm-adjusted p-values, in the input order."""
    return [float(p) for p in multipletests(pvalues, method='holm')[1]]


def equivalence(summary, margin):
    """The plan's rule on the percentage-point scale: the whole 95 percent interval inside (-margin, +margin)."""
    low, high = 100 * summary['low'], 100 * summary['high']
    est, se = 100 * summary['estimate'], 100 * summary['se']
    p_tost = max(float(sps.norm.sf((est + margin) / se)), float(sps.norm.cdf((est - margin) / se))) if se > 0 else 0.0
    return {'margin': margin, 'equivalent': bool(low > -margin and high < margin), 'pTost': p_tost}


def matched(rows, key_a, key_b, by):
    """Pairs of `correct` values matched on the fields in `by`, between rows selected by key_a and key_b (predicates); missing dropped."""
    index_a = {tuple(r[f] for f in by): r['correct'] for r in rows if key_a(r)}
    index_b = {tuple(r[f] for f in by): r['correct'] for r in rows if key_b(r)}
    pairs = [(index_a[k], index_b[k]) for k in sorted(set(index_a) & set(index_b))]
    return [(a, b) for a, b in pairs if a is not None and b is not None]


def mcnemar_exact(pairs):
    """Exact two-sided McNemar: a binomial test on the discordant pairs. Returns a-only, b-only and p."""
    a_only = sum(1 for a, b in pairs if a == 1 and b == 0)
    b_only = sum(1 for a, b in pairs if a == 0 and b == 1)
    n = a_only + b_only
    p = 1.0 if n == 0 else float(sps.binomtest(a_only, n, 0.5).pvalue)
    return {'pairs': len(pairs), 'aOnly': a_only, 'bOnly': b_only, 'p': p}


def cochran(rows, scenarios, by=('task', 'model', 'trial')):
    """Cochran's Q over the scenarios on complete blocks (a block with a missing run is dropped)."""
    blocks = {}
    for r in rows:
        if r['scenario'] in scenarios:
            blocks.setdefault(tuple(r[f] for f in by), {})[r['scenario']] = r['correct']
    table = [[block[s] for s in scenarios] for _, block in sorted(blocks.items())
             if all(block.get(s) is not None for s in scenarios)]
    result = cochrans_q(np.array(table))
    return {'blocks': len(table), 'q': float(result.statistic), 'df': int(result.df), 'p': float(result.pvalue)}


def bootstrap_contrasts(rows, scenarios, models, contrasts, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    """Percentile 95 percent intervals of marginal differences, resampling tasks with replacement.

    `contrasts` maps a name to (kind, a, b): kind 'scenario' compares two scenarios averaged over the models, 'model' two models averaged
    over the scenarios. Cell proportions are pooled over the resampled tasks, then averaged with equal weight, like the GEE marginals."""
    tasks = sorted({r['task'] for r in rows if r['scenario'] in scenarios})
    hits = np.zeros((len(tasks), len(scenarios), len(models)))
    count = np.zeros_like(hits)
    for r in rows:
        if r['scenario'] in scenarios and r['correct'] is not None:
            t, s, m = tasks.index(r['task']), scenarios.index(r['scenario']), models.index(r['model'])
            hits[t, s, m] += r['correct']
            count[t, s, m] += 1
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(tasks), size=(replicates, len(tasks)))
    h = hits[draws].sum(axis=1)
    c = count[draws].sum(axis=1)
    with np.errstate(invalid='ignore', divide='ignore'):
        p = h / c
    out = {}
    for name, (kind, a, b) in contrasts.items():
        if kind == 'scenario':
            d = p[:, scenarios.index(a), :].mean(axis=1) - p[:, scenarios.index(b), :].mean(axis=1)
        else:
            d = p[:, :, models.index(a)].mean(axis=1) - p[:, :, models.index(b)].mean(axis=1)
        d = d[np.isfinite(d)]
        out[name] = {'low': float(np.percentile(d, 2.5)), 'high': float(np.percentile(d, 97.5)), 'replicates': int(d.size)}
    return out
