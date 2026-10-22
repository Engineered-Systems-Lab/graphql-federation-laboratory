"""Derive the expected answers of the federation acceptance questions from the RELEASED files, never from a run.

Inputs (all committed, all immutable releases):
  uss-enterprise/missions/datasets/releases/1.2/missions-N.xml  the Missions dataset release 1.2 (300 missions in six pages of 50, its
                                                                participants reclassified as P and O), read in the contract's order
                                                                (stardate, priority, missionId), the service's order
  federation/mapping-releases/1.3/assets.json                   the mapping release 1.3, section assets
  federation/mapping-releases/1.3/crew.json                     the mapping release 1.3, section crew (800 references)
  uss-enterprise/assets/datasets/releases/1.1/assets.json       the Assets dataset release 1.1 (32 assets)
  uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/  the Personnel v2 snapshot of 1,000 people (ten pages of 100)

The earlier data (Missions 1.0 with 31 missions, mapping release 1.1, the snapshot personnel-v2-small-003; then Missions 1.1 with mapping
release 1.2) was the input of the earlier derivations; Git keeps those files. The participants section of mapping release 1.3 is not an
input: the graph does not resolve a participant.

Output: federation/acceptance/expected-outcomes.json (written with --write, compared without it).
The expected file is written BEFORE any router code and a test re-derives it from the inputs, so a stale file fails.
Usage (from the repository root): python -B federation/acceptance/derive_expected.py [--write]
"""
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MISSIONS_DIR = ROOT / 'uss-enterprise/missions/datasets/releases/1.2'
MAPPING = ROOT / 'federation/mapping-releases/1.3/assets.json'
CREW_MAPPING = ROOT / 'federation/mapping-releases/1.3/crew.json'
ASSETS = ROOT / 'uss-enterprise/assets/datasets/releases/1.1/assets.json'
PERSONNEL_DIR = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004'
OUT = ROOT / 'federation/acceptance/expected-outcomes.json'
NS = {'m': 'urn:starfleet:missions:v1'}
PNS = {'p': 'urn:graphql-federation-lab:personnel:v2'}
RELEASE = '1.3'
CREW_RELEASE = '1.3'
BAD_STATUSES = ('DESTROYED', 'MISSING')
SENIOR_RANKS = ('CAPTAIN', 'COMMANDER', 'LIEUTENANT_COMMANDER')


def sha256_lf(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def mission_pages():
    """The six numbered pages of the Missions release, in their numeric order."""
    return sorted(MISSIONS_DIR.glob('missions-*.xml'), key=lambda page: int(re.fullmatch(r'missions-([1-9][0-9]*)\.xml', page.name).group(1)))


def personnel_pages():
    """The ten numbered pages of the Personnel v2 snapshot."""
    return sorted(PERSONNEL_DIR.glob('page-*.xml'))


def load():
    missions = []
    nodes = [node for page in mission_pages() for node in ET.parse(page).getroot().findall('m:mission', NS)]
    # The service lists the missions in the contract's order, whatever the order of the files: stardate, priority, missionId, ascending.
    nodes.sort(key=lambda node: (Decimal(node.findtext('m:stardate', namespaces=NS)), int(node.findtext('m:priority', namespaces=NS)),
                                 node.findtext('m:missionId', namespaces=NS)))
    for node in nodes:
        missions.append({
            'missionId': node.findtext('m:missionId', namespaces=NS),
            'status': node.findtext('m:status', namespaces=NS),
            'commanderRef': node.findtext('m:commandingOfficerId', namespaces=NS),
            'assetRefs': [n.text for n in node.findall('m:assignedAssetIds/m:assetId', NS)],
            'crewRefs': [n.text for n in node.findall('m:assignedCrewIds/m:crewId', NS)],
        })
    entries = json.loads(MAPPING.read_text(encoding='utf-8'))['entries']
    assets = {a['assetId']: a for a in json.loads(ASSETS.read_text(encoding='utf-8'))['assets']}
    return missions, entries, assets


def load_crew():
    """The crew section of mapping release 1.1 and the people of the Personnel v2 snapshot, as the released files hold them."""
    entries = json.loads(CREW_MAPPING.read_text(encoding='utf-8'))['entries']
    people = {}
    for page in personnel_pages():
        for node in ET.parse(page).getroot().findall('p:personnelMember', PNS):
            crew = node.find('p:crewDetails', PNS)
            people[node.findtext('p:personnelId', namespaces=PNS)] = {
                'displayName': node.findtext('p:displayName', namespaces=PNS),
                'rank': crew.findtext('p:rank', namespaces=PNS) if crew is not None else None,
                'department': crew.findtext('p:department', namespaces=PNS) if crew is not None else None,
                'securityClearance': crew.findtext('p:securityClearance', namespaces=PNS) if crew is not None else None,
            }
    return entries, people


def outcome(ref, entries, assets):
    """The decided outcome of one asset reference when every service answers."""
    asset_id = entries.get(ref)
    if asset_id is None:
        return {'mappingOutcome': 'NO_ENTRY', 'assetId': None, 'resolution': 'UNMAPPED', 'status': None}
    if asset_id not in assets:
        return {'mappingOutcome': 'MAPPED', 'assetId': asset_id, 'resolution': 'UNRESOLVED', 'status': None}
    return {'mappingOutcome': 'MAPPED', 'assetId': asset_id, 'resolution': 'RESOLVED', 'status': assets[asset_id]['status']}


def crew_outcome(ref, entries, people):
    """The decided outcome of one crew reference in the crew section of release 1.1 when every service answers."""
    personnel_id = entries.get(ref)
    if personnel_id is None:
        return {'mappingOutcome': 'NO_ENTRY', 'personnelId': None, 'resolution': 'UNMAPPED'}
    if personnel_id not in people:
        return {'mappingOutcome': 'MAPPED', 'personnelId': personnel_id, 'resolution': 'UNRESOLVED'}
    return {'mappingOutcome': 'MAPPED', 'personnelId': personnel_id, 'resolution': 'RESOLVED', **people[personnel_id]}


def percentage(with_senior, without_senior):
    """Question 6: the missions that had a senior officer, as a share of the CONFIRMED missions (with + without), one decimal, half up.

    The unconfirmed missions are in neither side, and neither are the cancelled ones (out of the population). When no mission is
    confirmed the percentage is not a number: None, never 0.
    """
    confirmed = with_senior + without_senior
    if confirmed == 0:
        return None
    return float((Decimal(with_senior) * 100 / Decimal(confirmed)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


# The population and the buckets of question 6 (the lead developer's final rules, 2026-10-18):
#   CANCELLED: left OUT of the population. A cancelled mission never ran, so its staffing describes a dropped plan; the answer reports how
#       many cancelled missions were not counted beside the three counts and the percentage, never folded into any bucket.
#   PLANNED: unconfirmed unless it already has a confirmed senior officer (it can be confirmed WITH, never confirmed WITHOUT, because its
#       staffing is not final). A planned mission with nobody at all is therefore unconfirmed too.
#   Every other status (AUTHORIZED, ACTIVE, POSTPONED, COMPLETED, FAILED) counts by its staffing, as bucket() says; a mission of one of them
#       with nobody at all has started or ended and is confirmed without a senior officer.
EXCLUDED_STATUS = 'CANCELLED'
UNFINISHED_STATUS = 'PLANNED'


def bucket(members, status):
    """The bucket of one counted mission (status is never CANCELLED) from its Starfleet personnel: the commanding officer (when it has one)
    and the assigned crew.

    `members` holds one (resolution, rank) pair for each person; the rank is None for a civilian. Participants are never members.
    with: at least one member is confirmed senior (RESOLVED with a rank of SENIOR_RANKS); the unconfirmed members do not matter then.
    A PLANNED mission is unconfirmed otherwise, whatever its staffing: it is not final yet.
    without: no member is confirmed senior and every member is confirmed (RESOLVED); a mission with no member at all is confirmed without.
    unconfirmed: no member is confirmed senior and at least one member is not confirmed (UNMAPPED, UNRESOLVED, RELEASE_REFUSED,
    UNAVAILABLE, or a null resolution when the Personnel adapter cannot be asked).
    """
    assert status != EXCLUDED_STATUS, 'a cancelled mission is out of the population: it has no bucket'
    if any(resolution == 'RESOLVED' and rank in SENIOR_RANKS for resolution, rank in members):
        return 'with'
    if status == UNFINISHED_STATUS:
        return 'unconfirmed'
    if all(resolution == 'RESOLVED' for resolution, _ in members):
        return 'without'
    return 'unconfirmed'


def personnel_of(mission):
    """The references of a mission's Starfleet personnel: the commanding officer first (when it has one), then the assigned crew."""
    return ([mission['commanderRef']] if mission['commanderRef'] else []) + mission['crewRefs']


def buckets(missions, member):
    """The mission ids of the three buckets and of the cancelled missions left out, in the order of the dataset; `member` gives the
    (resolution, rank) of a reference."""
    found = {'with': [], 'without': [], 'unconfirmed': [], 'cancelled': []}
    for m in missions:
        if m['status'] == EXCLUDED_STATUS:
            found['cancelled'].append(m['missionId'])
        else:
            found[bucket([member(r) for r in personnel_of(m)], m['status'])].append(m['missionId'])
    return found


def counted_references(missions):
    """The number of personnel references of the counted missions (the cancelled ones are out of the population)."""
    return sum(len(personnel_of(m)) for m in missions if m['status'] != EXCLUDED_STATUS)


def answer6(found, total, not_resolved):
    return {'confirmedWithSenior': len(found['with']), 'confirmedWithoutSenior': len(found['without']), 'unconfirmed': len(found['unconfirmed']),
            'percentage': percentage(len(found['with']), len(found['without'])), 'cancelledNotCounted': len(found['cancelled']),
            'totalMissions': total, 'notResolvedReferences': not_resolved}


# Small controlled inputs: one mission each. A person is (localRef, resolution, rank): rank None for a civilian, resolution None for the
# null the router gives when it cannot ask the Personnel adapter. The commander is one person or None. (name, commander, crew, status.)
# A bucket is with, without, unconfirmed, or cancelled (left out of the population: in no bucket, counted beside the answer).
CONTROLLED_MISSIONS = (
    ('one confirmed senior and one unconfirmed member (null)', None, (('C-1', 'RESOLVED', 'COMMANDER'), ('C-2', None, None)), 'ACTIVE'),
    ('one confirmed senior and one UNRESOLVED member', None, (('C-1', 'RESOLVED', 'CAPTAIN'), ('C-2', 'UNRESOLVED', None)), 'ACTIVE'),
    ('a confirmed LIEUTENANT_COMMANDER only', None, (('C-1', 'RESOLVED', 'LIEUTENANT_COMMANDER'),), 'ACTIVE'),
    ('confirmed non-senior members only, one of them a civilian', None, (('C-1', 'RESOLVED', 'ENSIGN'), ('C-2', 'RESOLVED', None)), 'ACTIVE'),
    ('confirmed non-senior members plus one UNMAPPED member', None,
     (('C-1', 'RESOLVED', 'LIEUTENANT'), ('C-2', 'RESOLVED', None), ('C-3', 'UNMAPPED', None)), 'ACTIVE'),
    ('confirmed non-senior members plus one UNRESOLVED member', None, (('C-1', 'RESOLVED', 'CREWMAN'), ('C-2', 'UNRESOLVED', None)), 'ACTIVE'),
    ('confirmed non-senior members plus one RELEASE_REFUSED member', None, (('C-1', 'RESOLVED', 'ENSIGN'), ('C-2', 'RELEASE_REFUSED', None)), 'ACTIVE'),
    ('confirmed non-senior members plus one UNAVAILABLE member', None, (('C-1', 'RESOLVED', 'ENSIGN'), ('C-2', 'UNAVAILABLE', None)), 'ACTIVE'),
    ('confirmed non-senior members plus one null resolution', None, (('C-1', 'RESOLVED', 'CHIEF_PETTY_OFFICER'), ('C-2', None, None)), 'ACTIVE'),
    ('the only senior-ranked member is not confirmed (UNMAPPED)', None, (('C-1', 'UNMAPPED', 'CAPTAIN'),), 'ACTIVE'),
    ('the only senior is the commanding officer', ('C-9', 'RESOLVED', 'COMMANDER'), (('C-1', 'RESOLVED', 'ENSIGN'),), 'ACTIVE'),
    ('the commanding officer cannot be confirmed (null) and the crew is confirmed non-senior', ('C-9', None, None), (('C-1', 'RESOLVED', 'ENSIGN'),), 'ACTIVE'),
    ('the commanding officer is the only member and is confirmed non-senior', ('C-9', 'RESOLVED', 'LIEUTENANT'), (), 'ACTIVE'),
    ('the commanding officer is confirmed senior and a crew member is unconfirmed', ('C-9', 'RESOLVED', 'CAPTAIN'), (('C-1', 'UNMAPPED', None),), 'ACTIVE'),
    ('nobody at all (no commanding officer, no crew), PLANNED: not final, so unconfirmed', None, (), 'PLANNED'),
    ('nobody at all (no commanding officer, no crew), ACTIVE: started, so confirmed without', None, (), 'ACTIVE'),
    ('PLANNED, a confirmed senior member and an unconfirmed one: confirmed with is possible', None,
     (('C-1', 'RESOLVED', 'COMMANDER'), ('C-2', 'UNMAPPED', None)), 'PLANNED'),
    ('PLANNED, the commanding officer is a confirmed senior and the crew is confirmed non-senior', ('C-9', 'RESOLVED', 'CAPTAIN'),
     (('C-1', 'RESOLVED', 'ENSIGN'),), 'PLANNED'),
    ('PLANNED, only confirmed non-senior members: unconfirmed, never confirmed without', None,
     (('C-1', 'RESOLVED', 'CHIEF_PETTY_OFFICER'), ('C-2', 'RESOLVED', None)), 'PLANNED'),
    ('PLANNED, only confirmed non-senior members and a confirmed non-senior commanding officer: still unconfirmed', ('C-9', 'RESOLVED', 'LIEUTENANT'),
     (('C-1', 'RESOLVED', 'ENSIGN'),), 'PLANNED'),
    ('PLANNED, the only senior-ranked member is not confirmed (UNMAPPED): unconfirmed', None, (('C-1', 'UNMAPPED', 'CAPTAIN'),), 'PLANNED'),
    ('CANCELLED with a confirmed senior member is left out', None, (('C-1', 'RESOLVED', 'CAPTAIN'),), 'CANCELLED'),
    ('CANCELLED with only confirmed non-senior members is left out', None, (('C-1', 'RESOLVED', 'ENSIGN'),), 'CANCELLED'),
    ('CANCELLED with an unconfirmed member is left out', None, (('C-1', 'UNMAPPED', None),), 'CANCELLED'),
    ('CANCELLED with nobody at all is left out', None, (), 'CANCELLED'),
    ('CANCELLED with a confirmed senior commanding officer and two crew members is left out', ('C-9', 'RESOLVED', 'COMMANDER'),
     (('C-1', 'RESOLVED', 'ENSIGN'), ('C-2', 'RESOLVED', None)), 'CANCELLED'),
) + tuple(
    # The other statuses count by their staffing, as before.
    ('%s, confirmed non-senior members only: confirmed without' % status, None, (('C-1', 'RESOLVED', 'ENSIGN'),), status)
    for status in ('AUTHORIZED', 'ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED')
) + tuple(
    ('%s, a confirmed senior member: confirmed with' % status, None, (('C-1', 'RESOLVED', 'COMMANDER'),), status)
    for status in ('AUTHORIZED', 'POSTPONED', 'COMPLETED', 'FAILED')
) + tuple(
    ('%s, no confirmed senior and an unconfirmed member: unconfirmed' % status, None, (('C-1', 'RESOLVED', 'ENSIGN'), ('C-2', 'UNAVAILABLE', None)), status)
    for status in ('AUTHORIZED', 'POSTPONED', 'COMPLETED', 'FAILED')
)

# The percentage over the confirmed missions only: (name, missions with, without, unconfirmed, cancelled). 1 of 16 is 6.25, a tie: half up gives 6.3.
CONTROLLED_PERCENTAGES = (
    ('a tie goes up', 1, 15, 0, 0),
    ('the unconfirmed are in neither side', 1, 15, 4, 0),
    ('every confirmed mission has a senior officer', 3, 0, 2, 0),
    ('confirmed missions and none with a senior officer', 0, 4, 1, 0),
    ('nothing is confirmed', 0, 0, 3, 0),
    ('the cancelled missions are left out and counted beside, in no bucket', 3, 1, 1, 2),
    ('only cancelled missions: nothing is confirmed', 0, 0, 0, 4),
)


def controlled_buckets():
    cases = []
    for name, commander, crew, status in CONTROLLED_MISSIONS:
        case = {'name': name, 'status': status,
                'commandingOfficer': None if commander is None else {'localRef': commander[0], 'resolution': commander[1], 'rank': commander[2]},
                'crew': [{'localRef': ref, 'resolution': resolution, 'rank': rank} for ref, resolution, rank in crew]}
        people = ([commander] if commander else []) + list(crew)
        case['bucket'] = 'cancelled' if status == EXCLUDED_STATUS else bucket([(resolution, rank) for _, resolution, rank in people], status)
        cases.append(case)
    return {
        'rule': 'the people checked are the commanding officer (when the mission has one) and the assigned crew; with = at least one is confirmed '
                'senior; without = every one is confirmed and none senior; unconfirmed = no confirmed senior and at least one not confirmed '
                '(UNMAPPED, UNRESOLVED, RELEASE_REFUSED, UNAVAILABLE or a null resolution); a PLANNED mission is unconfirmed unless a confirmed '
                'senior is already assigned; a mission with nobody at all is without unless it is PLANNED; a CANCELLED mission is in no bucket',
        'missions': cases,
        'percentages': [{'name': name, 'confirmedWithSenior': w, 'confirmedWithoutSenior': wo, 'unconfirmed': u, 'cancelledNotCounted': c,
                         'percentage': percentage(w, wo)} for name, w, wo, u, c in CONTROLLED_PERCENTAGES],
    }


def question6(missions, references):
    """Question 6: how many missions had a senior officer among their Starfleet personnel, as three counts and one percentage, with the
    cancelled missions left out and counted beside.

    The personnel of a mission are its commanding officer (commandingOfficerId, when it has one) and its assigned crew (assignedCrewIds);
    the participants are never counted. Confirmed with a senior officer, confirmed without, and unconfirmed (see `bucket`), then the
    percentage over the confirmed missions (with / (with + without)). Senior is a rank of SENIOR_RANKS read from the crewDetails of a RESOLVED
    reference; a civilian has no rank and is never senior. An unconfirmed mission is never folded into either side. A PLANNED mission is
    unconfirmed unless a confirmed senior officer is already assigned; a CANCELLED mission is not counted at all (`cancelledNotCounted`).
    """
    # A reference the mapping has no entry for (UNMAPPED) carries no rank: the rank is read from a RESOLVED reference only.
    def member(ref):
        return references[ref]['resolution'], references[ref].get('rank')

    def senior(ref):
        return references[ref]['resolution'] == 'RESOLVED' and references[ref]['rank'] in SENIOR_RANKS

    total = len(missions)
    found = buckets(missions, member)
    # The controlled case: a mission whose ONLY senior-ranked member is unresolved when the reference is not RESOLVED. Here the member is
    # unmapped (release 1.0 has no crew section) or unavailable (the Personnel adapter is down); the first mission of the dataset with
    # exactly one senior member among its commanding officer and assigned crew is used, so the answer never depends on a lucky second member.
    controlled = next(m for m in missions if m['status'] != EXCLUDED_STATUS and sum(1 for r in personnel_of(m) if senior(r)) == 1)
    only_senior = next(r for r in personnel_of(controlled) if senior(r))
    all_references = counted_references(missions)
    # Release 1.0: every reference is UNMAPPED. Personnel adapter down: resolution is null, the fields of the mapping stay.
    nothing = buckets(missions, lambda ref: ('UNMAPPED', None))
    down = buckets(missions, lambda ref: (None, None))
    return {
        'seniorRanks': list(SENIOR_RANKS),
        'personnel': 'the commanding officer (when the mission has one) and the assigned crew; the participants are never counted',
        'buckets': 'confirmed with a senior officer, confirmed without, unconfirmed (never folded into either side)',
        'plannedRule': 'a PLANNED mission is unconfirmed unless it already has a confirmed senior officer (confirmed with is possible, confirmed '
                       'without never: its staffing is not final)',
        'cancelledRule': 'CANCELLED missions are left out of the population and their number is reported beside the answer (cancelledNotCounted), '
                         'never folded into any bucket; their staffing, their references and their resolutions are not looked at',
        'percentageOf': 'the confirmed missions: with / (with + without); not a number (null, never 0) when no mission is confirmed',
        'rounding': 'one decimal, half up',
        'confirmedWithSeniorMissionIds': found['with'],
        'confirmedWithoutSeniorMissionIds': found['without'],
        'unconfirmedMissionIds': found['unconfirmed'],
        'cancelledMissionIds': found['cancelled'],
        **answer6(found, total, sum(1 for m in missions if m['status'] != EXCLUDED_STATUS for r in personnel_of(m) if member(r)[0] != 'RESOLVED')),
        'seniorReferences': sorted({r for m in missions for r in personnel_of(m) if senior(r)}),
        'controlledCase': {
            'missionId': controlled['missionId'], 'personnelRefs': personnel_of(controlled), 'onlySeniorReference': only_senior,
            'seniorRank': references[only_senior]['rank'],
            'release1.0': answer6(nothing, total, all_references),
            'personnelDown': {'resolution': None, **answer6(down, total, all_references)},
        },
        'controlledBuckets': controlled_buckets(),
    }


def derive():
    missions, entries, assets = load()
    refs = sorted({r for m in missions for r in m['assetRefs']})
    references = {r: outcome(r, entries, assets) for r in refs}
    crew_entries, people = load_crew()
    crew_refs = sorted({r for m in missions for r in m['crewRefs']})
    crew_references = {r: crew_outcome(r, crew_entries, people) for r in crew_refs}
    commander_refs = sorted({m['commanderRef'] for m in missions if m['commanderRef']})
    commander_references = {r: crew_outcome(r, crew_entries, people) for r in commander_refs}
    per_mission = {}
    for m in missions:
        mapped = [r for r in m['assetRefs'] if references[r]['assetId'] is not None]
        per_mission[m['missionId']] = {
            'assetRefs': m['assetRefs'],
            'crewRefs': m['crewRefs'],
            'commandingOfficerRef': m['commanderRef'],
            'status': m['status'],
            # Question 5: with the Assets service down, one call per mapped reference fails, one errors entry each.
            'failedCallsWhenAssetsDown': len(mapped),
        }
    q2_by_asset = {}
    for r in refs:
        if references[r]['status'] in BAD_STATUSES:
            q2_by_asset[r] = [m['missionId'] for m in missions if r in m['assetRefs']]
    q3_unresolved = sorted({m['missionId'] for m in missions if any(references[r]['resolution'] == 'UNRESOLVED' for r in m['assetRefs'])})
    q3_unmapped = sorted({m['missionId'] for m in missions if any(references[r]['resolution'] == 'UNMAPPED' for r in m['assetRefs'])})
    chains = []
    for root_ref in ('EQ-64',):
        chain = [references[root_ref]['assetId']]
        while assets[chain[-1]]['parentAssetId']:
            chain.append(assets[chain[-1]]['parentAssetId'])
        chains.append({'fromReference': root_ref, 'chain': chain,
                       'missionIds': [m['missionId'] for m in missions if root_ref in m['assetRefs']]})
    return {
        'about': 'Expected answers of the federation acceptance questions 2 to 6 and the controlled cases, derived from the released files by '
                 'federation/acceptance/derive_expected.py, never from a run. A test re-derives this file and fails when it differs.',
        'mappingRelease': RELEASE,
        'derivedFrom': {
            'missionsDataset1.2': {page.relative_to(ROOT).as_posix(): sha256_lf(page) for page in mission_pages()},
            'mappingRelease1.3Assets': {'path': MAPPING.relative_to(ROOT).as_posix(), 'sha256Lf': sha256_lf(MAPPING)},
            'mappingRelease1.3Crew': {'path': CREW_MAPPING.relative_to(ROOT).as_posix(), 'sha256Lf': sha256_lf(CREW_MAPPING)},
            'assetsDataset1.1': {'path': ASSETS.relative_to(ROOT).as_posix(), 'sha256Lf': sha256_lf(ASSETS)},
            'personnelSnapshot004': {page.relative_to(ROOT).as_posix(): sha256_lf(page) for page in personnel_pages()},
        },
        'missionOrder': [m['missionId'] for m in missions],
        'references': references,
        'missions': per_mission,
        'question2': {'badStatuses': list(BAD_STATUSES), 'referencesByAsset': q2_by_asset,
                      'missionIds': sorted({i for ids in q2_by_asset.values() for i in ids})},
        'question3': {'unresolvedMissionIds': q3_unresolved, 'notCountedUnmappedMissionIds': q3_unmapped},
        # The chain is asked in ONE query: Asset.parent, resolved by the Assets adapter, one call per level.
        'question4': {'chains': chains, 'oneQuery': True},
        'question5': {'unavailableCode': 'SERVICE_UNAVAILABLE', 'httpStatus': 200},
        # Counted by the client and the test over the query result: the graph has no aggregate field.
        'question6': question6(missions, {**crew_references, **commander_references}),
        # The commanding officers of the missions, asked in release 1.1 like the crew: each with its decided outcome.
        'commandingOfficers': {'release': CREW_RELEASE, 'references': commander_references},
        # Crew references asked in release 1.0, which has no crew section: NO_ENTRY, UNMAPPED, no errors entry.
        'crewInRelease1.0': {'mappingOutcome': 'NO_ENTRY', 'resolution': 'UNMAPPED', 'errorsEntries': 0},
        # Crew references asked in release 1.1: the references of the Missions dataset, each with its decided outcome.
        'crew': {'release': CREW_RELEASE, 'references': crew_references, 'errorsEntries': 0,
                 'occurrencesInMissions': sum(len(m['crewRefs']) for m in missions)},
        # A refused release is a request error and also a resolution of its own: the data says so, beside the errors entry.
        'releaseErrors': {'blankRelease': 'MAPPING_RELEASE_REQUIRED', 'unknownReleases': ['2.0', 'latest', '1'],
                          'unknownCode': 'MAPPING_RELEASE_NOT_FOUND', 'mappingOutcome': 'RELEASE_REFUSED', 'resolution': 'RELEASE_REFUSED'},
    }


def render(data):
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + '\n'


def main(argv):
    text = render(derive())
    if '--write' in argv:
        OUT.write_bytes(text.encode('utf-8'))
        print('wrote', OUT.relative_to(ROOT).as_posix())
        return 0
    if OUT.read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text:
        print('FAIL: federation/acceptance/expected-outcomes.json differs from the derivation', file=sys.stderr)
        return 1
    print('ok: the expected outcomes match the released files')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
