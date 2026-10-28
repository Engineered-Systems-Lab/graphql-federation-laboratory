"""The scripted reference solution of every task of corpus 2, written once against the access interface (common.Access).

SOLVERS maps a task id to a function of an Access that returns the submission the task's schema expects. An ambiguity task returns one
submission per accepted interpretation, so that every interpretation is shown answerable. The solutions read only what the access layer
returns, which comes through the arm's own tools; they never read the released files or a key.

A task of category D is solved while its service is stopped: the solution tries what it needs, catches Unavailable, and reports the
stopped service, leaving null what it could not establish. Run outside its outage, a D task's solution gives the full answer, which is
not its key; the runner runs a D task only under its outage.
"""
from collections import Counter
from decimal import Decimal

from common import ReleaseRefused, Unavailable, staff_refs

REL = '1.3'
RANKS = ('CAPTAIN', 'COMMANDER', 'LIEUTENANT_COMMANDER', 'LIEUTENANT', 'ENSIGN', 'CHIEF_PETTY_OFFICER', 'CREWMAN')
SOLVERS = {}


def solver(task_id):
    def register(function):
        SOLVERS[task_id] = function
        return function
    return register


def answered(**fields):
    return {'answerStatus': 'ANSWERED', **fields}


def with_outage(fields, down):
    """An answer of category D: `down` is the set of services that did not answer and that the answer needed."""
    return {'answerStatus': 'ANSWERED', **fields, 'unavailableServices': sorted(down), 'complete': not down}


def money(total):
    return float(total)


# ---------------------------------------------------------------- shared steps

def assets_by_id(acc):
    return {a['assetId']: a for a in acc.list_assets()}


def people_by_id(acc):
    return {p['personnelId']: p for p in acc.list_people()}


def resolved(acc, missions, release=REL, catalogue=None):
    """{missionId: [Assets identifiers that the release maps a reference to and the Assets system holds, each once]}."""
    catalogue = assets_by_id(acc) if catalogue is None else catalogue
    out = {}
    for mid, pairs in acc.asset_map(missions, release).items():
        ids = []
        for _, asset_id in pairs:
            if asset_id and asset_id in catalogue and asset_id not in ids:
                ids.append(asset_id)
        out[mid] = ids
    return out


def identified(acc, missions, release=REL, roster=None):
    """{missionId: [Personnel identifiers of the staff that the release maps and the roster holds, each once]}."""
    roster = people_by_id(acc) if roster is None else roster
    out = {}
    for mid, pairs in acc.staff_map(missions, release).items():
        ids = []
        for _, pid in pairs:
            if pid and pid in roster and pid not in ids:
                ids.append(pid)
        out[mid] = ids
    return out


def distinct(values):
    return list(dict.fromkeys(values))


def counted(counter, key_name, count_name='count'):
    return [{key_name: k, count_name: n} for k, n in sorted(counter.items())]


# ============================================================ A
@solver('A01')
def a01(acc):
    m = acc.get_mission('ST-00000LDBE')
    return answered(title=m['title'], type=m['type'], status=m['status'])


@solver('A02')
def a02(acc):
    m = acc.get_mission('ST-00000LD8J')
    return answered(issuingAuthority=m['issuingAuthority'], classification=m['classification'], priority=m['priority'])


@solver('A03')
def a03(acc):
    m = acc.get_mission('ST-00000LD9E')
    return answered(locationType=m['locationType'], locationName=m['locationName'], durationHours=m['durationHours'])


@solver('A04')
def a04(acc):
    a = acc.get_asset('AST-0016')
    return answered(kind=a['kind'], status=a['status'], parentAssetId=a['parentAssetId'])


@solver('A05')
def a05(acc):
    return answered(assetIds=sorted(a['assetId'] for a in acc.list_assets(parentAssetId='AST-0029')))


@solver('A06')
def a06(acc):
    return answered(phasers=[{'assetId': a['assetId'], 'status': a['status']} for a in acc.list_assets(kind='PHASER')])


@solver('A07')
def a07(acc):
    p = acc.get_person('PRS-2167')
    return answered(rank=p['rank'], department=p['department'], dutyStatus=p['dutyStatus'])


@solver('A08')
def a08(acc):
    s = acc.get_person(acc.get_person('PRS-2382')['supervisor'])
    return answered(supervisorId=s['personnelId'], supervisorName=s['displayName'], supervisorRank=s['rank'])


@solver('A09')
def a09(acc):
    return answered(people=[{'personnelId': p['personnelId'], 'name': p['displayName']} for p in acc.list_people(dutyStatus='DECEASED')])


# ============================================================ B
def staff_people(acc, mission_id, release=REL):
    m = acc.get_mission(mission_id)
    pairs = acc.staff_map([m], release)[mission_id]
    return m, [acc.get_person(pid) for _, pid in pairs if pid]


@solver('B01')
def b01(acc):
    m = acc.get_mission('ST-00000LDAJ')
    p = acc.get_person(acc.crew_ref_map([m['co']], REL)[m['co']])
    return answered(personnelId=p['personnelId'], name=p['displayName'], rank=p['rank'])


@solver('B02')
def b02(acc):
    m = acc.get_mission('ST-00000LD8X')
    ids = acc.crew_ref_map(m['crew'], REL)
    people = [acc.get_person(ids[ref]) for ref in m['crew']]
    return answered(crew=[{'personnelId': p['personnelId'], 'department': p['department']} for p in people])


@solver('B03')
def b03(acc):
    _, people = staff_people(acc, 'ST-00000LDBX')
    return answered(personnelIds=sorted(p['personnelId'] for p in people if p['rank'] in RANKS[:4]))


@solver('B04')
def b04(acc):
    _, people = staff_people(acc, 'ST-00000LDBO')
    return answered(people=[{'personnelId': p['personnelId'], 'dutyStatus': p['dutyStatus']} for p in people])


def mission_assets(acc, mission_id):
    m = acc.get_mission(mission_id)
    out = []
    for _, asset_id in acc.asset_map([m], REL)[mission_id]:
        a = acc.get_asset(asset_id) if asset_id else None
        if a and a['assetId'] not in [x['assetId'] for x in out]:
            out.append(a)
    return m, out


@solver('B05')
def b05(acc):
    _, assets = mission_assets(acc, 'ST-00000LD4Z')
    return answered(assets=[{'assetId': a['assetId'], 'name': a['name']} for a in assets])


@solver('B06')
def b06(acc):
    _, assets = mission_assets(acc, 'ST-00000LD5K')
    return answered(assets=[{'assetId': a['assetId'], 'status': a['status']} for a in assets if a['status'] != 'ACTIVE'])


@solver('B07')
def b07(acc):
    _, assets = mission_assets(acc, 'ST-00000LD51')
    return answered(assets=[{'assetId': a['assetId'], 'parentAssetId': a['parentAssetId']} for a in assets])


@solver('B08')
def b08(acc):
    m, assets = mission_assets(acc, 'ST-00000LD8J')
    co = acc.get_person(acc.crew_ref_map([m['co']], REL)[m['co']])
    return answered(commandingOfficerName=co['displayName'], assetNames=[a['name'] for a in assets])


@solver('B09')
def b09(acc):
    _, people = staff_people(acc, 'ST-00000LD4R')
    _, assets = mission_assets(acc, 'ST-00000LD4R')
    return answered(people=[{'personnelId': p['personnelId'], 'rank': p['rank']} for p in people],
                    assets=[{'assetId': a['assetId'], 'status': a['status']} for a in assets])


def commanding_ids(acc, missions, release=REL):
    """{missionId: the Personnel identifier the release maps the commanding officer to, or None}."""
    staffed = [m for m in missions if m['co']]
    pairs = acc.staff_map(staffed, release) if staffed else {}
    return {m['missionId']: dict(pairs[m['missionId']]).get(m['co']) if m['co'] else None for m in missions}


@solver('B10')
def b10(acc):
    missions = acc.list_missions()
    return answered(missionIds=sorted(mid for mid, pid in commanding_ids(acc, missions).items() if pid == 'PRS-0001'))


@solver('B11')
def b11(acc):
    rows = commanding_ids(acc, acc.list_missions(type='MEDICAL'))
    return answered(missions=[{'missionId': k, 'commandingOfficerPersonnelId': v} for k, v in rows.items()])


@solver('B12')
def b12(acc):
    missions = acc.list_missions()
    users = [mid for mid, pairs in acc.asset_map(missions, REL).items() if any(x == 'AST-0025' for _, x in pairs)]
    return answered(missionIds=sorted(users))


@solver('B13')
def b13(acc):
    catalogue = assets_by_id(acc)
    used = resolved(acc, acc.list_missions(type='MAINTENANCE'), catalogue=catalogue)
    return answered(missionIds=sorted(mid for mid, ids in used.items() if any(catalogue[x]['status'] == 'MISSING' for x in ids)))


@solver('B14')
def b14(acc):
    used = resolved(acc, acc.list_missions(issuingAuthority='STARFLEET_MEDICAL'))
    return answered(missions=[{'missionId': mid, 'assetCount': len(ids)} for mid, ids in used.items()])


@solver('B15')
def b15(acc):
    missions = acc.list_missions(status='FAILED')
    used = resolved(acc, missions)
    roster = people_by_id(acc)
    cos = commanding_ids(acc, missions)
    rows = []
    for m in missions:
        p = roster.get(cos[m['missionId']]) if cos[m['missionId']] else None
        rows.append({'missionId': m['missionId'], 'commandingOfficerRank': p['rank'] if p else None, 'assetCount': len(used[m['missionId']])})
    return answered(missions=rows)


# ============================================================ C
@solver('C01')
def c01(acc):
    m = acc.get_mission('ST-00000LD9G')
    pairs = acc.staff_map([m], '1.1')[m['missionId']]
    return answered(people=[{'crewReference': ref, 'personnelId': pid} for ref, pid in pairs])


@solver('C02')
def c02(acc):
    if 'crew' not in acc.release_sections().get('1.0', set()):
        return {'answerStatus': 'CANNOT_BE_DETERMINED', 'personnelId': None}
    m = acc.get_mission('ST-00000LD5N')
    return answered(personnelId=acc.crew_ref_map([m['co']], '1.0')[m['co']])


@solver('C03')
def c03(acc):
    m = acc.get_mission('ST-00000LD8Q')
    try:
        pairs = acc.asset_map([m], '1.4')[m['missionId']]
    except ReleaseRefused:
        return {'answerStatus': 'CANNOT_BE_DETERMINED', 'assetIds': []}
    return answered(assetIds=[x for _, x in pairs if x])


@solver('C04')
def c04(acc):
    m = acc.get_mission('ST-00000LD5M')
    catalogue = assets_by_id(acc)
    rows = []
    for ref, asset_id in acc.asset_map([m], REL)[m['missionId']]:
        outcome = 'UNMAPPED' if asset_id is None else ('RESOLVED' if asset_id in catalogue else 'UNRESOLVED')
        rows.append({'reference': ref, 'assetId': asset_id, 'outcome': outcome})
    return answered(references=rows)


@solver('C05')
def c05(acc):
    m = acc.get_mission('ST-00000LDCC')
    return answered(crewReferences=sorted(ref for ref, pid in acc.staff_map([m], REL)[m['missionId']] if pid is None))


@solver('C06')
def c06(acc):
    return answered(release11PersonnelId=acc.crew_ref_map(['C-1638'], '1.1')['C-1638'],
                    release13PersonnelId=acc.crew_ref_map(['C-1638'], '1.3')['C-1638'])


@solver('C07')
def c07(acc):
    return answered(releases=sorted(r for r, sections in acc.release_sections().items() if 'crew' in sections))


@solver('C08')
def c08(acc):
    missions = acc.list_missions(issuingAuthority='ENTERPRISE_COMMAND')
    return answered(missionIds=sorted(mid for mid, pairs in acc.asset_map(missions, REL).items() if any(x is None for _, x in pairs)))


@solver('C09')
def c09(acc):
    missions = acc.list_missions(classification='SECRET')
    return answered(missionIds=sorted(mid for mid, pairs in acc.staff_map(missions, REL).items() if any(p is None for _, p in pairs)))


@solver('C10')
def c10(acc):
    catalogue = assets_by_id(acc)
    missions = acc.list_missions(type='MAINTENANCE')
    return answered(missionIds=sorted(mid for mid, pairs in acc.asset_map(missions, REL).items()
                                      if any(x is not None and x not in catalogue for _, x in pairs)))


@solver('C11')
def c11(acc):
    missions = acc.list_missions(type='DIPLOMATIC')
    pairs = acc.staff_map(missions, '1.1')
    known = {}
    for pid in distinct(p for rows in pairs.values() for _, p in rows if p):
        known[pid] = acc.get_person(pid) is not None
    return answered(missionIds=sorted(mid for mid, rows in pairs.items() if rows and all(p and known[p] for _, p in rows)))


@solver('C12')
def c12(acc):
    m = acc.get_mission('ST-00000LDBG')
    catalogue = assets_by_id(acc)
    tally = Counter('UNMAPPED' if x is None else ('RESOLVED' if x in catalogue else 'UNRESOLVED') for _, x in acc.asset_map([m], REL)[m['missionId']])
    return answered(resolved=tally['RESOLVED'], unresolved=tally['UNRESOLVED'], unmapped=tally['UNMAPPED'])


# ============================================================ G
@solver('G01')
def g01(acc):
    return answered(missionIds=sorted(m['missionId'] for m in acc.list_missions(status='COMPLETED')))


@solver('G02')
def g02(acc):
    return answered(missionIds=sorted(m['missionId'] for p in (4, 5) for m in acc.list_missions(priority=p)))


@solver('G03')
def g03(acc):
    return answered(personnelIds=sorted(p['personnelId'] for p in acc.list_people(department='SECURITY')))


@solver('G04')
def g04(acc):
    return answered(personnelIds=sorted(p['personnelId'] for p in acc.list_people(department='ENGINEERING')))


@solver('G05')
def g05(acc):
    return answered(assets=[{'assetId': a['assetId'], 'status': a['status']} for a in acc.list_assets()])


@solver('G06')
def g06(acc):
    return answered(missionIds=sorted(m['missionId'] for m in acc.list_missions() if not m['co']))


@solver('G07')
def g07(acc):
    return answered(missionIds=sorted(m['missionId'] for m in acc.list_missions() if m['durationHours'] >= 200))


@solver('G08')
def g08(acc):
    return answered(personnelIds=sorted(p['personnelId'] for p in acc.list_people() if p['civilian']))


@solver('G09')
def g09(acc):
    return answered(personnelIds=sorted(p['personnelId'] for p in acc.list_people() if p['positionTitle'] == 'Section Supervisor'))


@solver('G10')
def g10(acc):
    return answered(missionIds=sorted(m['missionId'] for m in acc.list_missions()
                                      if m['est'] and m['act'] and Decimal(m['act']) > Decimal(m['est'])))


# ============================================================ E
@solver('E01')
def e01(acc):
    return answered(statuses=counted(Counter(a['status'] for a in acc.list_assets(parentAssetId='AST-0029')), 'status'))


@solver('E02')
def e02(acc):
    missions = acc.list_missions(commandingOfficerId='C-92')
    return answered(totalEstimatedCost=money(sum((Decimal(m['est']) for m in missions if m['est']), Decimal('0'))), missionCount=len(missions))


@solver('E03')
def e03(acc):
    _, people = staff_people(acc, 'ST-00000LD9F')
    return answered(departments=counted(Counter(p['department'] for p in people), 'department'))


@solver('E04')
def e04(acc):
    ids = distinct(x for xs in resolved(acc, acc.list_missions(type='TACTICAL')).values() for x in xs)
    return answered(assetCount=len(ids), assetIds=sorted(ids))


@solver('E05')
def e05(acc):
    people = distinct(p for ps in identified(acc, acc.list_missions(commandingOfficerId='C-99')).values() for p in ps)
    return answered(distinctPeople=len(people))


@solver('E06')
def e06(acc):
    return answered(statuses=counted(Counter(m['status'] for m in acc.list_missions(issuingAuthority='STARFLEET_SCIENCE')), 'status'))


@solver('E07')
def e07(acc):
    return answered(ranks=counted(Counter(p['rank'] for p in acc.list_people(department='SCIENCE')), 'rank'))


@solver('E08')
def e08(acc):
    roster = people_by_id(acc)
    people = distinct(p for ps in identified(acc, acc.list_missions(classification='SECRET'), roster=roster).values() for p in ps)
    top = Counter(roster[p]['department'] or 'CIVILIAN' for p in people).most_common(1)[0][0]
    return answered(distinctPeople=len(people), topDepartment=top)


@solver('E09')
def e09(acc):
    catalogue = assets_by_id(acc)
    used = resolved(acc, acc.list_missions(issuingAuthority='STARFLEET_COMMAND'), catalogue=catalogue)
    return answered(missionCount=sum(1 for ids in used.values() if any(catalogue[x]['status'] != 'ACTIVE' for x in ids)))


@solver('E10')
def e10(acc):
    roster = people_by_id(acc)
    ids = commanding_ids(acc, acc.list_missions(issuingAuthority='STARFLEET_COMMAND'))
    officers = {pid: roster[pid]['rank'] for pid in ids.values() if pid and pid in roster}
    rank, n = Counter(officers.values()).most_common(1)[0]
    return answered(rank=rank, officerCount=n)


@solver('E11')
def e11(acc):
    missions = acc.list_missions(issuingAuthority='ENTERPRISE_COMMAND', status='COMPLETED')
    return answered(totalActualCost=money(sum((Decimal(m['act']) for m in missions if m['act']), Decimal('0'))), missionCount=len(missions))


@solver('E12')
def e12(acc):
    groups = {}
    for m in acc.list_missions():
        row = groups.setdefault(m['issuingAuthority'], [0, Decimal('0')])
        row[0] += 1
        row[1] += Decimal(m['est']) if m['est'] else Decimal('0')
    return answered(authorities=[{'issuingAuthority': k, 'missionCount': v[0], 'totalEstimatedCost': money(v[1])} for k, v in sorted(groups.items())])


@solver('E13')
def e13(acc):
    return answered(departments=counted(Counter(p['department'] or 'CIVILIAN' for p in acc.list_people()), 'department'))


@solver('E14')
def e14(acc):
    roster = people_by_id(acc)
    ids = commanding_ids(acc, acc.list_missions())
    commanders = {pid: roster[pid]['rank'] for pid in ids.values() if pid and pid in roster}
    return answered(distinctCommanders=len(commanders), mostCommonRank=Counter(commanders.values()).most_common(1)[0][0])


@solver('E15')
def e15(acc):
    per = Counter(x for ids in resolved(acc, acc.list_missions()).values() for x in ids)
    return answered(assets=counted(per, 'assetId', 'missionCount'))


@solver('E16')
def e16(acc):
    roster = people_by_id(acc)
    hits = sorted(mid for mid, ps in identified(acc, acc.list_missions(), roster=roster).items()
                  if any(roster[p]['dutyStatus'] != 'ACTIVE' for p in ps))
    return answered(missionCount=len(hits), missionIds=hits)


# ============================================================ D (each run with its service stopped)
@solver('D01')
def d01(acc):
    try:
        m = acc.get_mission('ST-00000LD9W')
    except Unavailable as down:
        return with_outage({'status': None, 'commandingOfficerName': None, 'commandingOfficerRank': None}, {down.service})
    p = acc.get_person(acc.crew_ref_map([m['co']], REL)[m['co']])
    return with_outage({'status': m['status'], 'commandingOfficerName': p['displayName'], 'commandingOfficerRank': p['rank']}, set())


@solver('D02')
def d02(acc):
    try:
        missions = acc.list_missions(type='SCIENTIFIC')
    except Unavailable as down:
        return with_outage({'missionCount': None, 'totalEstimatedCost': None}, {down.service})
    return with_outage({'missionCount': len(missions),
                        'totalEstimatedCost': money(sum((Decimal(m['est']) for m in missions if m['est']), Decimal('0')))}, set())


@solver('D03')
def d03(acc):
    p = acc.get_person('PRS-1058')
    return with_outage({'rank': p['rank'], 'department': p['department'], 'supervisorId': p['supervisor']}, set())


@solver('D14')
def d14(acc):
    return with_outage({'members': [{'personnelId': p['personnelId'], 'rank': p['rank']} for p in acc.list_people(department='MEDICAL')]}, set())


@solver('D04')
def d04(acc):
    m = acc.get_mission('ST-00000LD5M')
    rows, down = [], set()
    for _, asset_id in acc.asset_map([m], REL)[m['missionId']]:
        if not asset_id:
            continue
        try:
            a = acc.get_asset(asset_id)
            status = a['status'] if a else None
        except Unavailable as error:
            down.add(error.service)
            status = None
        rows.append({'assetId': asset_id, 'status': status})
    return with_outage({'title': m['title'], 'status': m['status'], 'assets': rows}, down)


@solver('D05')
def d05(acc):
    try:
        a = acc.get_asset('AST-0026')
    except Unavailable as down:
        return with_outage({'kind': None, 'status': None}, {down.service})
    return with_outage({'kind': a['kind'], 'status': a['status']}, set())


@solver('D06')
def d06(acc):
    missions = acc.list_missions(type='SECURITY')
    try:
        catalogue = assets_by_id(acc)
    except Unavailable as down:
        return with_outage({'missionIds': []}, {down.service})
    used = resolved(acc, missions, catalogue=catalogue)
    return with_outage({'missionIds': sorted(mid for mid, ids in used.items() if any(catalogue[x]['status'] == 'ACTIVE' for x in ids))}, set())


@solver('D07')
def d07(acc):
    missions = acc.list_missions(type='DIPLOMATIC')
    try:
        catalogue = assets_by_id(acc)
    except Unavailable as down:
        return with_outage({'missions': [{'missionId': m['missionId'], 'status': m['status'], 'assetNames': None} for m in missions]},
                           {down.service})
    used = resolved(acc, missions, catalogue=catalogue)
    return with_outage({'missions': [{'missionId': m['missionId'], 'status': m['status'],
                                      'assetNames': [catalogue[x]['name'] for x in used[m['missionId']]]} for m in missions]}, set())


@solver('D08')
def d08(acc):
    m = acc.get_mission('ST-00000LD5N')
    p = acc.get_person(acc.crew_ref_map([m['co']], REL)[m['co']])
    return with_outage({'name': p['displayName'], 'rank': p['rank']}, set())


@solver('D09')
def d09(acc):
    m = acc.get_mission('ST-00000LD4X')
    rows, down = [], set()
    for _, pid in acc.staff_map([m], REL)[m['missionId']]:
        try:
            p = acc.get_person(pid) if pid else None
        except Unavailable as error:
            down.add(error.service)
            p = None
        rows.append({'personnelId': pid, 'name': p['displayName'] if p else None, 'rank': p['rank'] if p else None})
    return with_outage({'people': rows}, down)


@solver('D10')
def d10(acc):
    try:
        p = acc.get_person('PRS-1100')
    except Unavailable as down:
        return with_outage({'rank': None, 'department': None}, {down.service})
    return with_outage({'rank': p['rank'], 'department': p['department']}, set())


@solver('D11')
def d11(acc):
    missions = acc.list_missions(type='MEDICAL')
    try:
        roster = people_by_id(acc)
    except Unavailable as down:
        return with_outage({'distinctPeople': None}, {down.service})
    people = distinct(p for ps in identified(acc, missions, roster=roster).values() for p in ps if roster[p]['department'] == 'MEDICAL')
    return with_outage({'distinctPeople': len(people)}, set())


@solver('D12')
def d12(acc):
    missions = acc.list_missions(status='ACTIVE')
    ids = commanding_ids(acc, missions)
    rows, down = [], set()
    for m in missions:
        pid = ids[m['missionId']]
        try:
            p = acc.get_person(pid) if pid else None
        except Unavailable as error:
            down.add(error.service)
            p = None
        rows.append({'missionId': m['missionId'], 'commandingOfficerPersonnelId': pid, 'rank': p['rank'] if p else None})
    return with_outage({'missions': rows}, down)


@solver('D13')
def d13(acc):
    _, assets = mission_assets(acc, 'ST-00000LD5J')
    return with_outage({'assets': [{'assetId': a['assetId'], 'status': a['status']} for a in assets]}, set())


# ============================================================ F: one submission per accepted interpretation
@solver('F01')
def f01(acc):
    m = acc.get_mission('ST-00000LD8Q')
    staff = staff_refs(m)
    return [answered(peopleCount=len(staff), interpretation={'countedGroups': ['COMMANDING_OFFICER', 'ASSIGNED_CREW']}),
            answered(peopleCount=len(staff) + len(m['participants']),
                     interpretation={'countedGroups': ['COMMANDING_OFFICER', 'ASSIGNED_CREW', 'PARTICIPANTS']}),
            answered(peopleCount=len(m['crew']), interpretation={'countedGroups': ['ASSIGNED_CREW']})]


@solver('F02')
def f02(acc):
    m = acc.get_mission('ST-00000LD6Q')
    return [answered(cost=money(Decimal(m['est'])), interpretation={'costBasis': 'ESTIMATED'}),
            answered(cost=money(Decimal(m['act'])), interpretation={'costBasis': 'ACTUAL'})]


@solver('F03')
def f03(acc):
    catalogue = assets_by_id(acc)

    def below(asset_id, root):
        parent = catalogue[asset_id]['parentAssetId']
        while parent:
            if parent == root:
                return True
            parent = catalogue[parent]['parentAssetId']
        return False
    direct = sorted(x for x, a in catalogue.items() if a['parentAssetId'] == 'AST-0029')
    nested = sorted(x for x in catalogue if below(x, 'AST-0029'))
    return [answered(assetIds=direct, interpretation={'scope': 'DIRECTLY_ABOARD'}),
            answered(assetIds=nested, interpretation={'scope': 'AT_ANY_LEVEL'})]


@solver('F04')
def f04(acc):
    shuttles = acc.list_assets(kind='SHUTTLE')
    active = sorted(a['assetId'] for a in shuttles if a['status'] == 'ACTIVE')
    serviceable = sorted(a['assetId'] for a in shuttles if a['status'] in ('ACTIVE', 'MAINTENANCE'))
    aboard = sorted(a['assetId'] for a in shuttles if a['status'] == 'ACTIVE' and a['parentAssetId'] == 'AST-0029')
    return [answered(assetIds=active, interpretation={'statusesCounted': ['ACTIVE'], 'onlyAboardTheEnterprise': False}),
            answered(assetIds=serviceable, interpretation={'statusesCounted': ['ACTIVE', 'MAINTENANCE'], 'onlyAboardTheEnterprise': False}),
            answered(assetIds=aboard, interpretation={'statusesCounted': ['ACTIVE'], 'onlyAboardTheEnterprise': True})]


@solver('F05')
def f05(acc):
    m = acc.get_mission('ST-00000LDCS')
    ids = acc.staff_map([m], REL)[m['missionId']]
    people = {ref: acc.get_person(pid) for ref, pid in ids}
    out = []
    for ranks in (RANKS[:5], RANKS[:4]):
        for with_co in (True, False):
            refs = staff_refs(m) if with_co else m['crew']
            out.append(answered(personnelIds=sorted(people[r]['personnelId'] for r in refs if people[r]['rank'] in ranks),
                                interpretation={'officerRanks': list(ranks), 'includesCommandingOfficer': with_co}))
    return out


@solver('F06')
def f06(acc):
    ref = 'C-554'
    commanded = acc.list_missions(commandingOfficerId=ref)
    crewed = acc.list_missions(assignedCrewId=ref)
    served = list({m['missionId']: m for m in commanded + crewed}.values())

    def latest(ms):
        return max(ms, key=lambda m: (Decimal(m['stardate']), m['missionId']))['missionId']
    out = []
    for roles, ms in ((['COMMANDING_OFFICER', 'ASSIGNED_CREW'], served), (['COMMANDING_OFFICER'], commanded)):
        for completed in (False, True):
            pick = [m for m in ms if m['status'] == 'COMPLETED' or not completed]
            out.append(answered(missionId=latest(pick), interpretation={'roles': roles, 'completedOnly': completed}))
    return out


# ============================================================ the development set
@solver('V01')
def v01(acc):
    m = acc.get_mission('ST-00000LDBK')
    return answered(status=m['status'], type=m['type'])


@solver('V02')
def v02(acc):
    m = acc.get_mission('ST-00000LD8L')
    p = acc.get_person(acc.crew_ref_map([m['co']], REL)[m['co']])
    return answered(personnelId=p['personnelId'], name=p['displayName'])


@solver('V03')
def v03(acc):
    return answered(personnelIds=sorted(p['personnelId'] for p in acc.list_people(department='FLIGHT_OPERATIONS')))


@solver('V04')
def v04(acc):
    m = acc.get_mission('ST-00000LDAH')
    rows, down = [], set()
    for _, asset_id in acc.asset_map([m], REL)[m['missionId']]:
        if not asset_id:
            continue
        try:
            a = acc.get_asset(asset_id)
            status = a['status'] if a else None
        except Unavailable as error:
            down.add(error.service)
            status = None
        rows.append({'assetId': asset_id, 'status': status})
    return with_outage({'status': m['status'], 'assets': rows}, down)


@solver('V05')
def v05(acc):
    roster = people_by_id(acc)
    people = distinct(p for ps in identified(acc, acc.list_missions(), roster=roster).values() for p in ps)
    return answered(distinctPeople=len(people), ranks=counted(Counter(roster[p]['rank'] or 'CIVILIAN' for p in people), 'rank'))


@solver('V06')
def v06(acc):
    catalogue = assets_by_id(acc)
    missions = acc.list_missions()
    used = resolved(acc, missions, catalogue=catalogue)
    per = Counter(m['type'] for m in missions if any(catalogue[x]['status'] != 'ACTIVE' for x in used[m['missionId']]))
    return answered(types=counted(per, 'type', 'missionCount'))


@solver('V07')
def v07(acc):
    missions = acc.list_missions(type='TRANSPORT')
    return answered(missionCount=len(missions), totalEstimatedCost=money(sum((Decimal(m['est']) for m in missions if m['est']), Decimal('0'))))


@solver('V08')
def v08(acc):
    missions = acc.list_missions(issuingAuthority='STARFLEET_SECURITY')
    people = distinct(p for ps in identified(acc, missions).values() for p in ps)
    return answered(staffPlaces=sum(len(staff_refs(m)) for m in missions), distinctPeople=len(people))
