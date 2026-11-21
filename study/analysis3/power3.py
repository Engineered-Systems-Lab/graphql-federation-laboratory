"""The t-test stand-in for study 3's power, from study 2's committed scores (PLAN.md, section 11), seeded.

    python -B study/analysis3/power3.py [--sims 4000] [--out <file outside the repository>]

Method. The 384 core runs of study 2's four full arms (category F left out); cost from the token columns at the price table of study 2's
manifest. Per question: the contrast of federation (the mean of Apollo and Cosmo) against each comparison arm, averaged over the two
models, on the log scale (log(1 + calls), log cost, log seconds). A new study resamples whole questions with replacement, so tool calls,
cost and time stay correlated, and each contrast is its centred value plus 100, 75 or 50 percent of study 2's effect. P1 and P2 are
one-sample t-tests over the questions, Holm over the two at 0.05. The CSL tests are Welch tests between two groups' P1 tool-call contrasts,
one-sided at 0.05, Holm over the two; the two tests are drawn independently, an approximation, because their groups overlap.

These figures are a stand-in. validate3.py gives the power of the implemented analysis, and the freeze uses that.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats as sps

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EVIDENCE = HERE.parent / 'evidence' / 'study-2'
CORPUS2_TASKS = HERE.parent / 'corpus2' / 'tasks.json'
SCORES_SHA256 = 'e43a8924eba9be624766cad082e2e48d12501c46c4cf40f82ebf9e4c9e50ff35'
SEED = 20261110
SIMS = 4000
OUTCOMES = ('toolCalls', 'cost', 'seconds')
PERCENTS = (100, 75, 50)
SIZES = {'tasks': 107, 'forward': 24, 'reverse': 30, 'one': 39, 'several': 52}
# The figures of the calculation of 2026-11-10, as the Job record gives them: the check of this script.
REFERENCE = (('P1 tool calls, 76 questions, 75 percent', 1.00), ('P2 tool calls, 76 questions, 75 percent', 0.84),
             ('forward against reverse, 30 and 30, advantage gone on reverse', 0.90), ('forward against reverse, 21 and 30, advantage gone on reverse', 0.82))


def load_contrasts(evidence=EVIDENCE):
    """{(outcome, 'P1' or 'P2'): contrast per question} and the question ids, from study 2's scores and manifest."""
    path = Path(evidence) / 'scores.csv'
    digest = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    if digest != SCORES_SHA256:
        raise ValueError('study 2\'s scores.csv hashes to %s, not the file the calculation used' % digest)
    prices = {m: e['priceEntry'] for m, e in json.loads((Path(evidence) / 'manifest.json').read_text(encoding='utf-8'))['models'].items()}
    # A score row holds a run's summed tokens, so it is priced per request only under an entry without long-context rates, where the two
    # are the same (decision N1 of the Job study3_openai_long_context); study 2's entries have none.
    tiered = sorted(m for m, e in prices.items() if e.get('long_context') is not None)
    if tiered:
        raise ValueError('the price entries of %s have long-context rates, and score rows cannot be priced per request' % ', '.join(tiered))
    with open(path, encoding='utf-8', newline='') as handle:
        rows = [r for r in csv.DictReader(handle) if r['scenario'] in ('beta', 'gamma', 'delta', 'epsilon') and r['category'] != 'F']
    if len(rows) != 384:
        raise ValueError('expected the 384 core runs of the four full arms, found %d' % len(rows))

    def dollars(r):
        p = prices[r['model']]
        return sum(int(r['tokens_' + k]) * p[k] for k in ('input', 'cached_read', 'cache_write', 'output')) / 1e6

    values = {(r['taskId'], r['scenario'], r['model']): {'toolCalls': math.log1p(int(r['toolCalls'])), 'cost': math.log(dollars(r)), 'seconds': math.log(float(r['seconds']))}
              for r in rows}
    tasks, models = sorted({r['taskId'] for r in rows}), sorted({r['model'] for r in rows})
    out = {}
    for outcome in OUTCOMES:
        for label, other in (('P1', 'gamma'), ('P2', 'beta')):
            out[(outcome, label)] = np.array([np.mean([0.5 * (values[(t, 'delta', m)][outcome] + values[(t, 'epsilon', m)][outcome]) - values[(t, other, m)][outcome]
                                                       for m in models]) for t in tasks])
    return out, tasks


def join_width_difference(contrasts, tasks, corpus_tasks=CORPUS2_TASKS):
    """A18: study 2's P1 tool-call log ratio on questions reading several systems minus one system, without category D. Reads only each
    task's category and systems from corpus 2."""
    facts = {t['id']: (t['category'], len(t.get('systems') or [])) for t in json.loads(Path(corpus_tasks).read_text(encoding='utf-8'))['tasks']}
    values = contrasts[('toolCalls', 'P1')]
    one = [v for t, v in zip(tasks, values) if facts[t][0] != 'D' and facts[t][1] == 1]
    several = [v for t, v in zip(tasks, values) if facts[t][0] != 'D' and facts[t][1] >= 2]
    return {'one': float(np.mean(one)), 'several': float(np.mean(several)), 'difference': float(np.mean(several) - np.mean(one)), 'questions': [len(one), len(several)]}


def t_p(values):
    n = values.shape[1]
    t = values.mean(axis=1) / (values.std(axis=1, ddof=1) / math.sqrt(n))
    return 2 * sps.t.sf(np.abs(t), n - 1)


def holm_two(first, second):
    """The Holm-adjusted p-values of two arrays of p-values."""
    low = np.minimum(1.0, 2 * np.minimum(first, second))
    high = np.maximum(low, np.maximum(first, second))
    return np.where(first <= second, low, high), np.where(second < first, low, high)


def family_power(contrasts, outcome, questions, percent, sims=SIMS, seed=SEED):
    """The power of P1 and P2 of one family, Holm over the two at 0.05."""
    rng = np.random.default_rng([seed, OUTCOMES.index(outcome), questions, percent])
    draws = rng.integers(0, len(contrasts[(outcome, 'P1')]), (sims, questions))
    p = {}
    for label in ('P1', 'P2'):
        c = contrasts[(outcome, label)]
        p[label] = t_p((c - c.mean())[draws] + percent / 100.0 * c.mean())
    first, second = holm_two(p['P1'], p['P2'])
    return {'P1': float((first < 0.05).mean()), 'P2': float((second < 0.05).mean())}


def welch_p(first, second):
    """One-sided p of second minus first being below zero is taken by the caller from the sign; this returns t and its degrees of freedom."""
    n1, n2 = first.shape[1], second.shape[1]
    v1, v2 = first.var(axis=1, ddof=1) / n1, second.var(axis=1, ddof=1) / n2
    return (second.mean(axis=1) - first.mean(axis=1)) / np.sqrt(v1 + v2), (v1 + v2) ** 2 / (v1 ** 2 / (n1 - 1) + v2 ** 2 / (n2 - 1))


def group_draw(contrast, sizes, shifts, rng, sims):
    centred = contrast - contrast.mean()
    return [centred[rng.integers(0, len(contrast), (sims, n))] + s for n, s in zip(sizes, shifts)]


def forward_reverse_p(contrast, forward, reverse, percent, rng, sims):
    """Forward keeps the share of study 2's P1 effect; the advantage is gone on reverse; one-sided, reverse minus forward above zero."""
    first, second = group_draw(contrast, (forward, reverse), (percent / 100.0 * contrast.mean(), 0.0), rng, sims)
    t, df = welch_p(first, second)
    return sps.t.sf(t, df)


def join_width_p(contrast, one, several, percent, difference, rng, sims):
    """Several systems' advantage exceeds one system's by the share of A18's difference; one-sided, several minus one below zero."""
    first, second = group_draw(contrast, (one, several), (contrast.mean(), contrast.mean() + percent / 100.0 * difference), rng, sims)
    t, df = welch_p(first, second)
    return sps.t.cdf(t, df)


def csl_power(contrast, difference, percent, sizes=SIZES, sims=SIMS, seed=SEED):
    """The CSL family at corpus 3's sizes: each test alone at one-sided 0.05, and under Holm over the two."""
    rng = np.random.default_rng([seed, 77, percent])
    fr = forward_reverse_p(contrast, sizes['forward'], sizes['reverse'], percent, rng, sims)
    jw = join_width_p(contrast, sizes['one'], sizes['several'], percent, difference, rng, sims)
    first, second = holm_two(fr, jw)
    return {'forwardReverse': {'alone': float((fr < 0.05).mean()), 'holm': float((first < 0.05).mean())},
            'joinWidth': {'alone': float((jw < 0.05).mean()), 'holm': float((second < 0.05).mean())}}


def reproduction(contrasts, sims=SIMS, seed=SEED):
    """This script's figures beside the calculation's, with the simulation error of each."""
    calls = contrasts[('toolCalls', 'P1')]
    family = family_power(contrasts, 'toolCalls', 76, 75, sims, seed)
    figures = [family['P1'], family['P2']]
    for forward in (30, 21):
        rng = np.random.default_rng([seed, 88, forward])
        figures.append(float((forward_reverse_p(calls, forward, 30, 100, rng, sims) < 0.05).mean()))
    return [{'figure': name, 'reference': ref, 'thisScript': got, 'monteCarloSe': math.sqrt(max(got * (1 - got), 1e-9) / sims)}
            for (name, ref), got in zip(REFERENCE, figures)]


def calculate(sims=SIMS, seed=SEED):
    contrasts, tasks = load_contrasts()
    join = join_width_difference(contrasts, tasks)
    return {'about': 'the t-test stand-in; validate3.py gives the power of the implemented analysis', 'seed': seed, 'simulationsPerCell': sims,
            'sizes': SIZES, 'study2Effects': {'%s %s' % k: float(v.mean()) for k, v in contrasts.items()}, 'joinWidth': join,
            'reproduction': reproduction(contrasts, sims, seed),
            'families': {outcome: {str(p): family_power(contrasts, outcome, SIZES['tasks'], p, sims, seed) for p in PERCENTS} for outcome in OUTCOMES},
            'csl': {str(p): csl_power(contrasts[('toolCalls', 'P1')], join['difference'], p, SIZES, sims, seed) for p in PERCENTS}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sims', type=int, default=SIMS)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    if args.out and Path(args.out).resolve().is_relative_to(REPO.resolve()):
        parser.error('--out must be outside the repository: the output is generated')
    text = json.dumps(calculate(args.sims), indent=2, sort_keys=True) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8', newline='\n')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
