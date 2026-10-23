"""Task 15 under the assigned-crew-only reading: an exploratory, post-hoc sensitivity line.

T15 asks how many missions had senior officers "among their crew". The frozen expected answers count the commanding officer together with
the assigned crew (the Question 6 rules); the question does not say that commanding officers are included, while T14 says so. This module
derives the same table as study/corpus/derive_corpus.py (senior_table) with the commanding officer left out, from the same released files
and the same rules, and rescores the T15 submissions that were scored wrong on their counts. The corpus and its scoring stay frozen: this is
a second reading beside the scored one, never a replacement.
"""
import sys
from decimal import Decimal
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY / 'corpus'))
import derive_corpus as DC  # noqa: E402  (its World, rank definitions and the Question 6 readers)
import scoring  # noqa: E402

DE = DC.DE


def crew_only_table(world=None):
    """The senior table of task 15 with the assigned crew only, in the shape of derive_corpus.senior_table()['data']."""
    w = world or DC.World()
    resolved = {}
    for ref in sorted({r for mm in w.missions for r in mm['crewRefs']}):
        o = DE.crew_outcome(ref, w.crew_map, w.people)
        resolved[ref] = (o['resolution'], o.get('rank'))

    def bucket(members, status, ranks):
        if any(res == 'RESOLVED' and rank in ranks for res, rank in members):
            return 'with'
        if status == DE.UNFINISHED_STATUS:
            return 'unconfirmed'
        return 'without' if all(res == 'RESOLVED' for res, _ in members) else 'unconfirmed'

    definitions = []
    for name, ranks in DC.SENIOR_DEFINITIONS.items():
        found = {'with': 0, 'without': 0, 'unconfirmed': 0}
        with_all = with_noncancelled = 0
        for mm in w.missions:
            members = [resolved[r] for r in mm['crewRefs']]
            has = any(res == 'RESOLVED' and rank in ranks for res, rank in members)
            with_all += has
            if mm['status'] == DE.EXCLUDED_STATUS:
                continue
            with_noncancelled += has
            found[bucket(members, mm['status'], ranks)] += 1
        total = len(w.missions)
        noncancelled = sum(1 for mm in w.missions if mm['status'] != DE.EXCLUDED_STATUS)
        definitions.append({'name': name, 'seniorRanks': list(ranks), 'policies': [
            {'name': 'lab-confirmed', 'withSeniorOfficer': found['with'], 'outOf': found['with'] + found['without'],
             'percentage': DE.percentage(found['with'], found['without'])},
            {'name': 'non-cancelled', 'withSeniorOfficer': with_noncancelled, 'outOf': noncancelled,
             'percentage': float(scoring.one_decimal(Decimal(with_noncancelled) * 100 / noncancelled))},
            {'name': 'all-missions', 'withSeniorOfficer': with_all, 'outOf': total,
             'percentage': float(scoring.one_decimal(Decimal(with_all) * 100 / total))},
        ]})
    return {'definitions': definitions}


def rescore(records, table):
    """{(run, runKey): outcome under the crew-only reading} for every T15 run scored wrong on its counts that the crew-only counts accept.

    Only `wrong_answer` runs can flip: a definition the rubric does not accept, a format error or a silent guess stays as scored."""
    flips = {}
    for r in records:
        if r['task'] != 'T15' or r['outcome'] != 'wrong_answer' or not r.get('submission'):
            continue
        outcome, tags, _ = scoring.score_senior_officers(r['submission'], table)
        if outcome == 'correct':
            flips[(r['run'], r['runKey'])] = {'outcome': outcome, 'tags': tags}
    return flips
