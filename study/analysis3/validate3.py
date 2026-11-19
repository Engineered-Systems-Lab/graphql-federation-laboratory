"""The error control, coverage and power of the implemented analysis (decision A11), on simulated studies at corpus 3's real shape.

    python -B study/analysis3/validate3.py --out <file outside the repository> [--sims 2000] [--workers 14] [--replicates 10000]
        [--master-seed 20261120]

Every simulated study runs the whole selection procedure of stats3.confirmatory: the usability check of each GEE, the fallback where a fit
cannot be used, Holm in each family and the accuracy gate. Each study is analysed as selected and, except in the accuracy-boundary scenarios,
again with the fallback forced, so the fallback is measured even though the GEE is almost always usable. Each study draws its own schedule
seed, its tasks' effects, about 2 percent missing runs, log-normal tool calls and cost at study 2's spread, and tool calls capped at 80. Every
second study has a session boundary inside a round.

Scenarios: `null` (no effect); `effort-100/75/50` (study 2's effects); `reverse-100/75/50` (the advantage gone on reverse questions);
`join-100/75/50` (several systems exceed one system by A18's difference); `both-100/75/50` (the two together); and the accuracy scenarios
`boundary-100`, `boundary-shift` and `boundary-tasks` (a true difference of exactly -10 points; simulate3.accuracy_draw defines them). Reverse
questions are more common among those that read several systems, so when both effects are present the join-width groups differ by less than
A18's difference. Each scenario reports the group differences it actually generates (`generatedEffects`) beside its power (decision A23).

Rates count every simulated study: a family that cannot be estimated counts as no rejection and no claim. Coverage is conditional on an
estimate, and the share of studies with one is reported beside it (`<family>.<comparison>.estimable`).

Thresholds (A11): a false-positive rate above 0.06 for a 0.05 test or family, above 0.035 for the 0.025 floor, or a coverage below 0.93 is
listed in `exceeded` and goes to the lead developer before the preview. The false-positive limits of the CSL family apply in every scenario
whose CSL effects are null. The output records the hashes of the code it validated, its master seed and the simulation error of a rate.
"""
import argparse
import collections
import hashlib
import json
import math
import multiprocessing
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import simulate3  # noqa: E402
import stats3  # noqa: E402

REPO = HERE.parent.parent
SIMS = 2000
MASTER_SEED = 20261120
SESSION_BOUNDARY = 6  # the second block of the second round
LIMIT_FAMILY = 0.06
LIMIT_FLOOR = 0.035
LIMIT_COVERAGE = 0.93
BOUNDARY = ('boundary-100', 'boundary-shift', 'boundary-tasks')
CSL_NULL = ('null', 'effort-100', 'effort-75', 'effort-50')
CODE = ('data3.py', 'simulate3.py', 'stats3.py', 'validate3.py')


def scenarios():
    out = {'null': {'effects': simulate3.NULL, 'accuracy': 'near', 'kind': 'null'}}
    for percent in (100, 75, 50):
        out['effort-%d' % percent] = {'effects': simulate3.effects_at(percent), 'accuracy': 'near', 'kind': 'effort'}
        out['reverse-%d' % percent] = {'effects': simulate3.effects_at(percent, reverse_gone=True), 'accuracy': 'near', 'kind': 'csl'}
        out['join-%d' % percent] = {'effects': simulate3.effects_at(percent, join=True), 'accuracy': 'near', 'kind': 'csl'}
        out['both-%d' % percent] = {'effects': simulate3.effects_at(percent, reverse_gone=True, join=True), 'accuracy': 'near', 'kind': 'csl'}
    for name in BOUNDARY:
        out[name] = {'effects': simulate3.NULL, 'accuracy': name, 'kind': 'floor'}
    return out


def core_entries():
    """Each core task's direction and join-width group, on corpus 3's shape."""
    tasks, directions = simulate3.tasks_of_shape()
    return [{'direction': directions[t['id']]['direction'], 'joinGroup': simulate3.data3.join_group(t['category'], directions[t['id']]['requiredSystems'])}
            for t in tasks if t['set'] == 'core']


def generated_effects(effects):
    """The difference of the mean P1 tool-call log ratios between the CSL groups that a scenario generates on corpus 3's shape."""
    groups = {'forward': [], 'reverse': [], 'one': [], 'several': []}
    for entry in core_entries():
        value = simulate3.task_p1(effects, entry, 'toolCalls')
        for level in (entry['direction'], entry['joinGroup']):
            if level in groups:
                groups[level].append(value)
    return {'reverseMinusForward': float(np.mean(groups['reverse']) - np.mean(groups['forward'])),
            'severalMinusOne': float(np.mean(groups['several']) - np.mean(groups['one']))}


def true_log_ratio(effects, outcome, label, draws=1000000, seed=20261118):
    """The true contrast on the analysis's scale, over the tasks' own effects. For tool calls the rounding and the cap move it slightly, so
    it is computed by simulation."""
    entries = core_entries()
    if outcome == 'cost':
        return float(np.mean([simulate3.task_p1(effects, e, 'cost') for e in entries])) if label == 'P1' else effects['P2']['cost']
    rng = np.random.default_rng([seed, 0 if label == 'P1' else 1])
    sd = simulate3.SD['toolCalls']

    def mean_of(arm, shift):
        spread = math.sqrt(sd['task'] ** 2 + sd['arm'][arm] ** 2 + sd['run'] ** 2)
        model = rng.choice([0.05, -0.05], draws)
        round_shift = rng.choice(list(simulate3.ROUND_SHIFT.values()), draws)
        y = 2.2 + shift + model + round_shift + spread * rng.standard_normal(draws)
        return float(np.log1p(np.minimum(80, np.maximum(0, np.round(np.expm1(y))))).mean())

    federation = 0.5 * (mean_of('delta', 0.0) + mean_of('epsilon', 0.0))
    if label == 'P2':
        return federation - mean_of('beta', -effects['P2']['toolCalls'])
    counts = collections.Counter(round(simulate3.task_p1(effects, e, 'toolCalls'), 12) for e in entries)
    return federation - sum(n * mean_of('gamma', -value) for value, n in sorted(counts.items())) / len(entries)


def summarize_one(result, truth):
    """The flags of one analysed study. A family that cannot be estimated counts as no rejection and no claim."""
    out = {}
    for outcome, family in result['effort'].items():
        out[outcome + '.method'] = family['method']
        out[outcome + '.any'] = bool(any(e['rejected'] for e in family['comparisons']))
        out[outcome + '.anyClaimed'] = bool(any(e['claimed'] for e in family['comparisons']))
        found = {e['id']: e for e in family['comparisons']}
        for cid, _, _ in stats3.COMPARISONS:
            e = found.get(cid)
            out['%s.%s.estimable' % (outcome, cid)] = e is not None
            out['%s.%s.rejected' % (outcome, cid)] = bool(e and e['rejected'])
            out['%s.%s.claimed' % (outcome, cid)] = bool(e and e['claimed'])
            if e is not None:
                out['%s.%s.covered' % (outcome, cid)] = bool(e['logLow'] <= truth[(outcome, cid)] <= e['logHigh'])
    out['csl.method'] = result['csl']['method']
    tests = {t['id']: t for t in result['csl']['tests']}
    out['csl.any'] = bool(any(t['rejected'] for t in tests.values()))
    out['csl.anyClaimed'] = bool(any(t['claimed'] for t in tests.values()))
    for name, *_ in stats3.CSL_TESTS:
        t = tests.get(name)
        out['csl.%s.estimable' % name] = t is not None
        out['csl.%s.alone' % name] = bool(t and t['p'] < stats3.FAMILY_ALPHA)
        out['csl.%s.rejected' % name] = bool(t and t['rejected'])
        out['csl.%s.claimed' % name] = bool(t and t['claimed'])
    for comparator, floor in result['floors'].items():
        out['floor.%s.cleared' % comparator] = floor['cleared']
        out['floor.%s.estimable' % comparator] = floor['estimable']
    return out


def one_study(job):
    name, spec, index, replicates, truth, master_seed = job
    seed = master_seed + 1000003 * (list(scenarios()).index(name) + 1) + index
    records, strata = simulate3.study_records(seed, spec['effects'], spec['accuracy'], plan_seed=master_seed + index + 1,
                                              session_boundary=SESSION_BOUNDARY if index % 2 else None)
    out = {'selected': summarize_one(stats3.confirmatory(records, simulate3.MODELS, strata, replicates), truth)}
    if spec['kind'] != 'floor':
        out['forced'] = summarize_one(stats3.confirmatory(records, simulate3.MODELS, strata, replicates, force_fallback=True), truth)
    return out


def rate(results, key):
    values = [r[key] for r in results if key in r]
    return float(np.mean(values)) if values else None


def tally(results):
    keys = sorted({k for r in results for k in r})
    out = {}
    for key in keys:
        if key.endswith('.method'):
            methods = [r[key] for r in results]
            out[key] = {m: methods.count(m) / len(methods) for m in sorted(set(methods))}
        else:
            out[key] = rate(results, key)
    return out


def checks(report):
    exceeded = []

    def limit(where, key, value, bound, above=True):
        if value is not None and (value > bound if above else value < bound):
            exceeded.append({'scenario': where, 'measure': key, 'value': value, 'limit': bound})

    for name, entry in report.items():
        if name in BOUNDARY:
            for comparator in ('gamma', 'beta'):
                key = 'floor.%s.cleared' % comparator
                limit(name, key, entry['selected'].get(key), LIMIT_FLOOR)
            continue
        for mode in ('selected', 'forced'):
            rates = entry.get(mode, {})
            where = '%s/%s' % (name, mode)
            if name == 'null':
                for key in ('toolCalls.any', 'cost.any'):
                    limit(where, key, rates.get(key), LIMIT_FAMILY)
            if name in CSL_NULL:
                for key in ('csl.any', 'csl.forwardReverse.alone', 'csl.joinWidth.alone'):
                    limit(where, key, rates.get(key), LIMIT_FAMILY)
            for key, value in rates.items():
                if key.endswith('.covered'):
                    limit(where, key, value, LIMIT_COVERAGE, above=False)
    return exceeded


def run(sims=SIMS, workers=1, replicates=stats3.REPLICATES, only=None, master_seed=MASTER_SEED):
    plan = {k: v for k, v in scenarios().items() if only is None or k in only}
    report = {}
    pool = multiprocessing.Pool(workers) if workers > 1 else None
    try:
        for name, spec in plan.items():
            truth = {(o, c): true_log_ratio(spec['effects'], o, c) for o in stats3.EFFORT_FAMILIES for c in ('P1', 'P2')}
            jobs = [(name, spec, i, replicates, truth, master_seed) for i in range(sims)]
            results = pool.map(one_study, jobs, chunksize=8) if pool else [one_study(j) for j in jobs]
            report[name] = {mode: tally([r[mode] for r in results]) for mode in results[0]}
            report[name]['trueLogRatios'] = {'%s %s' % k: v for k, v in truth.items()}
            report[name]['generatedEffects'] = generated_effects(spec['effects'])
    finally:
        if pool:
            pool.close()
            pool.join()
    return report


def code_hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for name in CODE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', required=True)
    parser.add_argument('--sims', type=int, default=SIMS)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--replicates', type=int, default=stats3.REPLICATES)
    parser.add_argument('--master-seed', type=int, default=MASTER_SEED)
    args = parser.parse_args(argv)
    if Path(args.out).resolve().is_relative_to(REPO.resolve()):
        parser.error('--out must be outside the repository: the output is generated')
    hashes = code_hashes()
    report = run(args.sims, args.workers, args.replicates, master_seed=args.master_seed)
    if code_hashes() != hashes:
        parser.error('the code changed while the validation ran, so its results describe no single version')
    body = {'about': "validate3.py: the implemented analysis on simulated studies at corpus 3's shape", 'simulations': args.sims, 'replicates': args.replicates,
            'masterSeed': args.master_seed, 'codeSha256': hashes, 'monteCarloSeOfARateOf005': math.sqrt(0.05 * 0.95 / args.sims),
            'limits': {'family': LIMIT_FAMILY, 'floor': LIMIT_FLOOR, 'coverage': LIMIT_COVERAGE}, 'exceeded': checks(report), 'scenarios': report}
    Path(args.out).write_text(json.dumps(body, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('exceeded: %d' % len(body['exceeded']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
