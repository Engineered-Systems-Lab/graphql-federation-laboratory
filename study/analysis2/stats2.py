"""The statistics of the study-2 analysis (PLAN.md). Study 1's plain functions are used unchanged where they apply: Holm and the
equivalence rule (study/analysis/stats.py); everything that needs different behaviour is here.

- GEE (the primary model and its secondary uses): outcome ~ arm x model + round + session, logistic for accuracy and Gaussian on a log
  scale for cost, time and tool calls, clustered by task, exchangeable working correlation, robust (sandwich) covariance. Round is the
  square's row (treatment coded, row 1 the reference). Session enters only when a session boundary falls inside a round of the square
  (a boundary between rounds is absorbed by round), and only if the design with it has full rank: when it does not, the session columns
  are left out and that is recorded. No term is chosen from its p-value.
- Standardization: an arm's value is the model's prediction averaged with equal weight over the two models and over the PLANNED
  conditions: every round of the square with equal weight and, within a round, its sessions weighted by the planned runs of the
  square's blocks in each session (planned_conditions). The weights are fixed by the schedule, are the same for every arm and do not move
  when a vendor error removes a run. Probabilities are averaged first, then differenced. Differences have 95 percent Wald intervals by the
  delta method, and the p-value of a difference is the Wald test of that same difference.
- A fit is usable (Fit.problems) only when statsmodels reports it converged, its parameters and covariance are finite, the covariance
  has no negative eigenvalue beyond rounding (below -1e-10 times the largest), no arm x model cell is all right or all wrong
  (separation), no parameter is extreme (|b| > 10 on the logit scale) and, where an interaction is tested, its covariance block is
  positive definite. A covariance that is singular but not negative (its smallest eigenvalue within rounding of zero) is recorded as a
  diagnostic and does not stop the fit: the robust sandwich of a balanced design is often exactly singular in one direction. Every
  reported contrast must still have a positive variance, or it fails.
- Equivalence of the planned pair: the design's whole-interval rule is the two one-sided tests at 2.5 percent; over P1 and P2 the
  one-sided p-values (stats.equivalence's pTost) are Holm-adjusted and equivalence is established only when the adjusted value is under
  0.025 (holm_equivalence).
- Cluster bootstrap over tasks: whole tasks resampled with replacement (all their arms, models and rounds together), the cell
  proportions pooled over the resampled tasks and averaged with equal model weights, percentile 95 percent intervals. It is an unadjusted
  cross-check of pooled proportions, not a bootstrap of the fitted GEE: it does not refit and ignores round and session.
- Bayesian mixed model (the sensitivity analysis of decision S4): statsmodels' BinomialBayesMixedGLM, logistic, with a random intercept
  per task and per block, priors vcp_p=1 and fe_p=2, fitted by variational Bayes (fit_vb, BFGS with statsmodels' default options, its
  starting values from the seed MIXED_SEED; the Laplace fit, fit_map, does not converge on study-2 data). Its result is used only
  when the optimizer reports success and every estimate is finite; otherwise the sensitivity analysis is reported as not estimable.
  Mean-field variational
  inference is an approximation, not a frequentist mixed model. Its arm x model cells take one parameter each and round and session are
  coded to sum to zero. Its results come from POSTERIOR_DRAWS seeded draws of the variational posterior, the variance components
  included: each draw's cell probability is standardized over the same planned conditions as the GEE and integrated over the task and
  block random effects of that draw (normal, Gauss-Hermite quadrature). The estimate is the posterior mean, the interval the 2.5 and
  97.5 percent quantiles.
"""
import math

import numpy as np
from scipy import sparse
from scipy import stats as sps
from statsmodels.genmod import families
from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.generalized_estimating_equations import GEE

import data2  # noqa: F401  (puts study/analysis on the path)
import stats  # study 1's statistics, read-only: holm, equivalence, Z95

Z95 = stats.Z95
holm = stats.holm
equivalence = stats.equivalence
BOOTSTRAP_SEED = 20261028
BOOTSTRAP_REPLICATES = 10000
MIXED_SEED = 20261028
POSTERIOR_DRAWS = 4000
MARGIN = 10
EQUIVALENCE_ALPHA = 0.025  # one-sided level of each of the two one-sided tests: the whole 95 percent interval
EXTREME = 10.0
NEGATIVE_TOLERANCE = 1e-10  # relative to the largest eigenvalue
SINGULAR_TOLERANCE = 1e-12
LOGISTIC_OUTCOMES = ('correct', 'honest')


class FitError(Exception):
    """A fit that cannot be used; the message names every problem."""


def logistic(eta):
    return 1.0 / (1.0 + math.exp(-eta))


def session_levels(rows):
    """The sessions that may enter the model: none unless some round of the rows holds runs of more than one session."""
    by_round = {}
    for r in rows:
        by_round.setdefault(r['row'], set()).add(r['session'])
    if not any(len(s) > 1 for s in by_round.values()):
        return []
    order = []
    for r in sorted(rows, key=lambda r: (r.get('blockSequence') or 0, r.get('orderInBlock') or 0, r['runKey'])):
        if r['session'] not in order:
            order.append(r['session'])
    return order


def planned_conditions(records):
    """The fixed standardization weights: [((round, session), weight)], every round equal, its sessions by planned runs.

    `records` are ALL planned runs of the square's analysed set, vendor errors included, so a missing outcome cannot move the weights."""
    counts = {}
    for r in records:
        counts[(r['row'], r['session'])] = counts.get((r['row'], r['session']), 0) + 1
    rounds = sorted({row for row, _ in counts})
    per_round = {row: sum(n for (r, _), n in counts.items() if r == row) for row in rounds}
    return sorted((((row, s), n / per_round[row] / len(rounds)) for (row, s), n in counts.items()), key=lambda kv: (kv[0][0], str(kv[0][1])))


def collapse(conditions, sessions):
    """The conditions as the model sees them: sessions merged when the model has no session term."""
    if sessions:
        return conditions
    out = {}
    for (row, _), w in conditions:
        out[(row, None)] = out.get((row, None), 0.0) + w
    return sorted(out.items(), key=lambda kv: (str(kv[0][0]),))


class Design:
    """Treatment coding of arm x model (the interaction optional), plus round and session main effects (first level the reference)."""

    def __init__(self, arms, models, rounds=(), sessions=(), interaction=True):
        self.arms, self.models, self.rounds, self.sessions = list(arms), list(models), list(rounds), list(sessions)
        self.interaction = interaction
        self.names = (['intercept'] + ['arm[%s]' % a for a in self.arms[1:]] + ['model[%s]' % m for m in self.models[1:]]
                      + (['arm[%s]:model[%s]' % (a, m) for a in self.arms[1:] for m in self.models[1:]] if interaction else [])
                      + ['round[%s]' % k for k in self.rounds[1:]] + ['session[%s]' % s for s in self.sessions[1:]])

    def row(self, arm, model, round_=None, session=None):
        a, m = self.arms.index(arm), self.models.index(model)
        x = [1.0] + [float(a == i) for i in range(1, len(self.arms))] + [float(m == j) for j in range(1, len(self.models))]
        if self.interaction:
            x += [float(a == i and m == j) for i in range(1, len(self.arms)) for j in range(1, len(self.models))]
        x += [float(round_ == k) for k in self.rounds[1:]]
        x += [float(session == s) for s in self.sessions[1:]]
        return np.array(x)

    def interaction_columns(self):
        return [i for i, name in enumerate(self.names) if ':' in name]


class Fit:
    """A fitted GEE: parameters, covariance, the design, the standardization conditions and its diagnostics."""

    def __init__(self, design, params, cov, link, n, clusters, converged, cov_kind, conditions, separated=(), sessions_dropped=False):
        self.design, self.params, self.cov, self.link = design, np.asarray(params, float), np.asarray(cov, float), link
        self.n, self.clusters, self.converged, self.cov_kind, self.conditions = n, clusters, converged, cov_kind, conditions
        self.separated, self.sessions_dropped = list(separated), sessions_dropped

    def cell(self, arm, model):
        """(value, gradient) of a cell standardized over the conditions: a probability for the logistic model, a log-mean otherwise."""
        total = sum(w for _, w in self.conditions)
        value, grad = 0.0, np.zeros(len(self.params))
        for (round_, session), weight in self.conditions:
            x = self.design.row(arm, model, round_, session)
            eta = float(x @ self.params)
            if self.link == 'logit':
                p = logistic(eta)
                value, grad = value + weight * p, grad + weight * p * (1.0 - p) * x
            else:
                value, grad = value + weight * eta, grad + weight * x
        return value / total, grad / total

    def marginal(self, arm, models=None):
        return mean([self.cell(arm, m) for m in (models or self.design.models)])

    def model_marginal(self, model, arms=None):
        return mean([self.cell(a, model) for a in (arms or self.design.arms)])

    def contrast(self, a, b):
        """Wald summary of value(a) - value(b) for (value, gradient) pairs."""
        diff, grad = a[0] - b[0], a[1] - b[1]
        var = float(grad @ self.cov @ grad)
        if not (var > 0 and math.isfinite(var)):
            raise FitError('the covariance gives the variance %r for a contrast' % var)
        se = math.sqrt(var)
        return {'estimate': diff, 'se': se, 'low': diff - Z95 * se, 'high': diff + Z95 * se, 'p': float(2 * sps.norm.sf(abs(diff / se)))}

    def interaction_test(self):
        idx = self.design.interaction_columns()
        if not idx:
            raise FitError('the model has no interaction term')
        b = self.params[idx]
        v = self.cov[np.ix_(idx, idx)]
        chi2 = float(b @ np.linalg.solve(v, b))
        return {'chi2': chi2, 'df': len(idx), 'p': float(sps.chi2.sf(chi2, len(idx)))}

    def problems(self, interaction=False):
        """Why the fit cannot carry inference; empty when it can."""
        out = []
        if not self.converged:
            out.append('statsmodels did not report convergence, or an estimate is not finite')
        if not np.all(np.isfinite(self.cov)):
            out.append('the covariance is not finite')
        else:
            sym = (self.cov + self.cov.T) / 2
            ev = np.linalg.eigvalsh(sym)
            scale = max(float(np.abs(ev).max()), 1e-300)
            if float(ev.min()) < -NEGATIVE_TOLERANCE * scale:
                out.append('the covariance has a negative eigenvalue (%.3g)' % float(ev.min()))
            idx = self.design.interaction_columns()
            if interaction and idx and float(np.linalg.eigvalsh(sym[np.ix_(idx, idx)]).min()) <= SINGULAR_TOLERANCE * scale:
                out.append('the covariance of the interaction terms is not positive definite')
        if self.separated:
            out.append('separation: cells all right or all wrong: %s' % ', '.join('%s/%s' % c for c in self.separated))
        if self.link == 'logit' and np.all(np.isfinite(self.params)) and float(np.abs(self.params).max()) > EXTREME:
            out.append('an extreme estimate (|b| > %g on the logit scale)' % EXTREME)
        return out

    def singular(self):
        """True when the covariance is finite and not negative but singular within rounding (a diagnostic, not a stop)."""
        if not np.all(np.isfinite(self.cov)):
            return False
        ev = np.linalg.eigvalsh((self.cov + self.cov.T) / 2)
        scale = max(float(np.abs(ev).max()), 1e-300)
        return bool(-NEGATIVE_TOLERANCE * scale <= float(ev.min()) <= SINGULAR_TOLERANCE * scale)

    def facts(self):
        return {'covarianceSingular': self.singular(),'observations': self.n, 'clusters': self.clusters, 'converged': self.converged, 'covariance': self.cov_kind,
                'workingCorrelation': 'exchangeable', 'rounds': self.design.rounds, 'sessions': self.design.sessions,
                'sessionTermsLeftOutForRank': self.sessions_dropped, 'interaction': self.design.interaction,
                'standardization': [{'round': k[0], 'session': k[1], 'weight': w} for k, w in self.conditions],
                'diagnostics': self.problems(interaction=self.design.interaction),
                'parameters': dict(zip(self.design.names, self.params.tolist()))}


def mean(pairs):
    """The equal-weight mean of (value, gradient) pairs."""
    pairs = list(pairs)
    return sum(v for v, _ in pairs) / len(pairs), sum(g for _, g in pairs) / len(pairs)


def transform(outcome, value):
    """The scale of an outcome in the fits: correct and honest as they are, tool calls as log(1 + calls), cost and time as their log."""
    if outcome in LOGISTIC_OUTCOMES:
        return float(value)
    if outcome == 'toolCalls':
        return math.log1p(float(value))
    return math.log(float(value))


def usable(rows, outcome):
    """The rows a fit of `outcome` uses: a value present and, on a log scale, positive (tool calls may be zero)."""
    return [r for r in rows if r.get(outcome) is not None and (outcome in LOGISTIC_OUTCOMES or outcome == 'toolCalls' or float(r[outcome]) > 0)]


def fit_gee(rows, outcome, arms, models, rounds=True, sessions=True, cov_type='robust', interaction=True, conditions=None):
    """Fit the plan's GEE. `conditions` are the standardization weights (planned_conditions of all planned runs); without them the rows'
    own conditions are used. Round and session follow the module's rules unless switched off."""
    logistic_model = outcome in LOGISTIC_OUTCOMES
    use = usable([r for r in rows if r['arm'] in arms], outcome)
    round_levels = sorted({r['row'] for r in use}) if rounds else []
    if None in round_levels:
        raise ValueError('round is a factor only for runs of the square')
    session_list = session_levels(use) if (sessions and rounds) else []

    def matrix(session_list):
        design = Design(arms, models, round_levels, session_list, interaction)
        X = np.array([design.row(r['arm'], r['model'], r['row'] if rounds else None, r['session'] if session_list else None) for r in use])
        return design, X

    design, X = matrix(session_list)
    dropped = False
    if session_list and np.linalg.matrix_rank(X) < X.shape[1]:
        session_list, dropped = [], True
        design, X = matrix(session_list)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise FitError('the design of %s has dependent columns' % outcome)
    y = np.array([transform(outcome, r[outcome]) for r in use])
    tasks = sorted({r['task'] for r in use})
    groups = np.array([tasks.index(r['task']) for r in use])
    family = families.Binomial() if logistic_model else families.Gaussian()
    result = GEE(y, X, groups=groups, family=family, cov_struct=Exchangeable()).fit(maxiter=200, cov_type=cov_type)
    params, cov = np.asarray(result.params), np.asarray(result.cov_params())
    converged = bool(getattr(result, 'converged', True)) and bool(np.all(np.isfinite(params))) and bool(np.all(np.isfinite(cov)))
    if not rounds:
        conds = [((None, None), 1.0)]
    else:
        conds = collapse(conditions if conditions is not None else planned_conditions(use), session_list)
    separated = []
    if logistic_model:
        for a in arms:
            for m in models:
                values = {r[outcome] for r in use if r['arm'] == a and r['model'] == m}
                if len(values) == 1:
                    separated.append((a, m))
    return Fit(design, params, cov, 'logit' if logistic_model else 'identity', len(use), len(tasks), converged, cov_type, conds,
               separated, dropped)


def holm_equivalence(summaries, margin=MARGIN):
    """Equivalence over a family of differences: the one-sided p-values of the two one-sided tests, Holm-adjusted, against 2.5 percent."""
    single = [equivalence(s, margin) for s in summaries]
    adjusted = holm([e['pTost'] for e in single])
    return [dict(e, pTostHolm=a, equivalentHolm=bool(a < EQUIVALENCE_ALPHA)) for e, a in zip(single, adjusted)]


# ------------------------------------------------------------------------------------------------------------------ the bootstrap
def cluster_bootstrap(rows, arms, models, contrasts, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    """Percentile 95 percent intervals of pooled-proportion differences, resampling whole tasks with replacement.

    `contrasts` maps a name to ('arms', {arm: weight}) for a weighted difference of arm proportions (weights summing to zero), or
    ('models', a, b) for model a minus model b averaged over the arms."""
    use = [r for r in rows if r['arm'] in arms and r['correct'] is not None]
    tasks = sorted({r['task'] for r in use})
    hits = np.zeros((len(tasks), len(arms), len(models)))
    count = np.zeros_like(hits)
    for r in use:
        t, a, m = tasks.index(r['task']), arms.index(r['arm']), models.index(r['model'])
        hits[t, a, m] += r['correct']
        count[t, a, m] += 1
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(tasks), size=(replicates, len(tasks)))
    with np.errstate(invalid='ignore', divide='ignore'):
        p = hits[draws].sum(axis=1) / count[draws].sum(axis=1)
    arm_p = p.mean(axis=2)
    out = {}
    for name, spec in contrasts.items():
        if spec[0] == 'arms':
            d = sum(weight * arm_p[:, arms.index(arm)] for arm, weight in spec[1].items())
        else:
            d = p[:, :, models.index(spec[1])].mean(axis=1) - p[:, :, models.index(spec[2])].mean(axis=1)
        d = d[np.isfinite(d)]
        out[name] = {'low': float(np.percentile(d, 2.5)), 'high': float(np.percentile(d, 97.5)), 'replicates': int(d.size)}
    return out


# ------------------------------------------------------------------------------------------------------------------ the mixed model
def effect_columns(levels, value):
    """Sum-to-zero coding of one factor."""
    if len(levels) < 2:
        return []
    if value == levels[-1]:
        return [-1.0] * (len(levels) - 1)
    return [float(value == k) for k in levels[:-1]]


def fit_mixed(rows, arms, models, conditions, draws=POSTERIOR_DRAWS):
    """The Bayesian mixed model of the module notes. Returns its facts, the posterior mean of every arm and a function that summarizes
    the posterior of a weighted difference of arms {arm: weight}."""
    use = [r for r in rows if r['arm'] in arms and r['correct'] is not None]
    cells = [(a, m) for a in arms for m in models]
    rounds = sorted({r['row'] for r in use})
    session_list = session_levels(use)
    X = np.array([[float((r['arm'], r['model']) == c) for c in cells] + effect_columns(rounds, r['row'])
                  + effect_columns(session_list, r['session']) for r in use])
    if np.linalg.matrix_rank(X) < X.shape[1]:
        session_list = []
        X = np.array([[float((r['arm'], r['model']) == c) for c in cells] + effect_columns(rounds, r['row']) for r in use])
    y = np.array([float(r['correct']) for r in use])
    tasks = sorted({r['task'] for r in use})
    blocks = sorted({r['block'] for r in use})
    i = np.repeat(np.arange(len(use)), 2)
    j = np.array([[tasks.index(r['task']), len(tasks) + blocks.index(r['block'])] for r in use]).ravel()
    Z = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(len(use), len(tasks) + len(blocks)))
    ident = np.array([0] * len(tasks) + [1] * len(blocks))
    result = BinomialBayesMixedGLM(y, X, Z, ident, vcp_p=1, fe_p=2).fit_vb(rng=MIXED_SEED)
    fe_mean, fe_sd = np.asarray(result.fe_mean), np.asarray(result.fe_sd)
    vcp_mean, vcp_sd = np.asarray(result.vcp_mean), np.asarray(result.vcp_sd)
    retvals = getattr(result, 'optim_retvals', None) or {}
    optimizer_success = bool(retvals.get('success', False))
    converged = optimizer_success and bool(np.all(np.isfinite(fe_mean)) and np.all(np.isfinite(fe_sd)) and np.all(np.isfinite(vcp_mean))
                                           and np.all(np.isfinite(vcp_sd)))
    if not converged:
        raise FitError('the variational fit of the mixed model did not converge (optimizer success %s: %s)'
                       % (optimizer_success, retvals.get('message')))
    conds = collapse(conditions, session_list)
    total = sum(w for _, w in conds)
    E = np.array([effect_columns(rounds, row) + (effect_columns(session_list, s) if session_list else []) for (row, s), _ in conds])
    W = np.array([w / total for _, w in conds])
    rng = np.random.default_rng(MIXED_SEED + 1)
    fe = fe_mean + fe_sd * rng.standard_normal((draws, len(fe_mean)))
    sds = np.exp(vcp_mean + vcp_sd * rng.standard_normal((draws, len(vcp_mean))))
    spread = np.sqrt((sds ** 2).sum(axis=1))
    nodes, node_weights = np.polynomial.hermite_e.hermegauss(40)
    node_weights = node_weights / node_weights.sum()
    shift = fe[:, len(cells):] @ E.T if E.size else np.zeros((draws, 1))
    cell_p = np.zeros((draws, len(cells)))
    for k in range(len(cells)):
        eta = fe[:, k][:, None, None] + shift[:, :, None] + spread[:, None, None] * nodes[None, None, :]
        p = (1.0 / (1.0 + np.exp(-eta)) * node_weights).sum(axis=2)
        cell_p[:, k] = p @ W if E.size else p[:, 0]
    arm_p = {a: cell_p[:, [cells.index((a, m)) for m in models]].mean(axis=1) for a in arms}

    def contrast(weights):
        d = sum(w * arm_p[a] for a, w in weights.items())
        return {'estimate': float(d.mean()), 'low': float(np.percentile(d, 2.5)), 'high': float(np.percentile(d, 97.5)),
                'posteriorShareBelowZero': float((d < 0).mean())}

    facts = {'method': 'BinomialBayesMixedGLM, mean-field variational Bayes (fit_vb, BFGS, statsmodels defaults), priors vcp_p=1 and fe_p=2',
             'seed': MIXED_SEED, 'posteriorDraws': draws, 'observations': len(use), 'tasks': len(tasks), 'blocks': len(blocks),
             'rounds': rounds, 'sessions': session_list, 'converged': converged, 'optimizerIterations': retvals.get('nit'),
             'randomEffectSdPosteriorMean': {'task': float(sds[:, 0].mean()), 'block': float(sds[:, 1].mean())},
             'scale': 'population: each cell standardized over the planned conditions and integrated over the task and block effects',
             'intervals': 'posterior 2.5 and 97.5 percent quantiles of the variational posterior, variance components included'}
    return {'facts': facts, 'arm': {a: float(v.mean()) for a, v in arm_p.items()}, 'contrast': contrast}
