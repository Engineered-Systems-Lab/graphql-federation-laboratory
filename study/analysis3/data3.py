"""Reading a study-3 bundle: verify a copy, read each task's strata and corpus 3's directions map, and load one record per run.

The counting rules, the void-block rule, the vendor-error rule and the reading of a run are study 2's and are imported unchanged from
study/analysis2/data2.py (load_strata, load_bundle, counting). What is new here: the analysis plan whose hash the manifest must name is
study/analysis3/PLAN.md; the directions map of corpus 3 is read and checked; each record carries its forward-against-reverse group and
its join-width group; and a run with a zero cost takes the smallest positive cost of the bundle's scored runs (PLAN.md, section 3).

Blindness. From tasks.json the analysis reads a task's id, category, set, size, systems, stopped service and the category-D tag, and the
directions map's direction, csl, anchor and requiredSystems: never a question, a schema, a key, a design note or a reference solution. A
task id is a cluster label and nothing else.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'analysis2'))

import data2  # noqa: E402  (study 2's reader, read-only; it puts study/analysis on the path)

data = data2.data
VerificationError = data2.VerificationError
PLAN = HERE / 'PLAN.md'  # the plan this analysis runs under; its hash must be the bundle's identity.analysisPlan
SQUARE_ARMS = data2.SQUARE_ARMS
REFERENCE_ARM = data2.REFERENCE_ARM
ALL_ARMS = data2.ALL_ARMS
ARM_NAMES = data2.ARM_NAMES
DIRECTIONS = ('forward', 'reverse', 'none')
CSL_KINDS = (None, 'reverse-lookup', 'far-side-aggregate', 'link-integrity')
sha256_file = data2.sha256_file


def verify_bundle(folder, sums_file, run_id, bundle_checksum):
    """Verify a copy of a study-3 run folder and its manifest, as study 2's are, against this folder's plan."""
    if not bundle_checksum:
        raise VerificationError('the bundle checksum must be given')
    facts = data.verify_copy(folder, sums_file, run_id, bundle_checksum)
    manifest = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
    contract = manifest.get('scoringContract')
    if not isinstance(contract, dict) or contract.get('version') is None or not contract.get('scorerSha256'):
        raise VerificationError('%s: the manifest names no scorer contract with the scorer hash' % run_id)
    if contract.get('version') != 2:
        raise VerificationError('%s: scorer contract version %r; the study-3 analysis reads version 2' % (run_id, contract.get('version')))
    identity = manifest.get('identity') or {}
    if not identity.get('corpusFreeze'):
        raise VerificationError('%s: the manifest names no corpus hash (identity.corpusFreeze)' % run_id)
    if not identity.get('analysisPlan'):
        raise VerificationError('%s: the manifest names no analysis plan hash (identity.analysisPlan)' % run_id)
    if identity['analysisPlan'] != sha256_file(PLAN):
        raise VerificationError("%s: the manifest's analysis plan hash %s is not the hash of the plan this analysis runs under "
                                '(study/analysis3/PLAN.md, %s)' % (run_id, identity['analysisPlan'], sha256_file(PLAN)))
    if not manifest.get('commit'):
        raise VerificationError('%s: the manifest names no harness commit' % run_id)
    plan = manifest.get('schedule')
    if not isinstance(plan, dict) or plan.get('design') != 'williams-4-half':
        raise VerificationError('%s: the manifest holds no williams-4-half schedule' % run_id)
    arms = sorted({b['arm'] for b in plan['blocks'] if b.get('row') is not None})
    if arms != sorted(SQUARE_ARMS) or plan.get('reference') != REFERENCE_ARM:
        raise VerificationError('%s: the schedule runs %s with the reference %s; the analysis expects %s and %s'
                                % (run_id, arms, plan.get('reference'), sorted(SQUARE_ARMS), REFERENCE_ARM))
    if len(manifest.get('models') or {}) != 2:
        raise VerificationError('%s: the manifest does not name exactly two models' % run_id)
    facts.update({'scoringContract': contract['version'], 'scorerSha256': contract['scorerSha256'], 'corpusFreeze': identity['corpusFreeze'],
                  'harnessCommit': manifest['commit'], 'treeDirty': manifest.get('treeDirty'), 'planHash': manifest.get('planHash')})
    return facts, manifest


def join_group(category, required):
    """The join-width group of a task: None for category D and for a task that reads no system, else one system or several."""
    if category == 'D' or not required:
        return None
    return 'one' if len(required) == 1 else 'several'


def load_strata(corpus_dir, manifest):
    """Study 2's strata of every task, plus corpus 3's directions map, read field by field and checked against the tasks."""
    strata, facts = data2.load_strata(corpus_dir, manifest)
    document = json.loads((Path(corpus_dir) / 'tasks.json').read_text(encoding='utf-8'))
    directions = document.get('directions')
    if not isinstance(directions, dict) or set(directions) != set(strata):
        raise VerificationError('tasks.json holds no directions entry for exactly its tasks')
    for task, entry in strata.items():
        given = directions[task]
        direction, csl, anchor, required = (given.get('direction'), given.get('csl'), given.get('anchor'), given.get('requiredSystems'))
        if direction not in DIRECTIONS:
            raise VerificationError('task %s has the unknown direction %r' % (task, direction))
        if csl not in CSL_KINDS:
            raise VerificationError('task %s has the unknown csl kind %r' % (task, csl))
        if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
            raise VerificationError('task %s has no list of required systems' % task)
        entry.update(direction=direction, csl=csl, anchor=anchor, requiredSystems=sorted(required),
                     cslGroup=direction if direction in ('forward', 'reverse') else None,
                     joinGroup=join_group(entry['category'], required))
    return strata, facts


def annotate(records, strata):
    """Copy each task's direction, csl kind, anchor and groups onto its records."""
    for record in records:
        entry = strata[record['task']]
        record.update({name: entry[name] for name in ('direction', 'csl', 'anchor', 'cslGroup', 'joinGroup')})
    return records


def apply_zero_cost_rule(records):
    """A scored run with a zero cost takes the smallest positive cost among the bundle's scored runs (a vendor error is not scored).
    Returns the facts; the run's spend in the descriptive tables keeps its true value in `costAsRecorded`."""
    scored = [r for r in records if r['outcome'] != 'vendor_error']
    positive = [r['cost'] for r in scored if r['cost'] > 0]
    zero = [r for r in scored if r['cost'] <= 0]
    if zero and not positive:
        raise VerificationError('no scored run has a positive cost, so a zero cost cannot be replaced')
    smallest = min(positive) if positive else None
    for record in records:
        record['costAsRecorded'] = record['cost']
    for record in zero:
        record['cost'] = smallest
    return {'runsWithZeroCost': len(zero), 'replacedBy': smallest if zero else None}


def load(folder, sums_file, run_id, bundle_checksum, corpus_dir):
    """Everything the analysis reads, verified: (facts, corpus facts, manifest, strata, records, blocks, zero-cost facts)."""
    facts, manifest = verify_bundle(folder, sums_file, run_id, bundle_checksum)
    strata, corpus_facts = load_strata(corpus_dir, manifest)
    records, blocks = data2.load_bundle(folder, manifest, strata)
    annotate(records, strata)
    zero = apply_zero_cost_rule(records)
    return facts, corpus_facts, manifest, strata, records, blocks, zero
