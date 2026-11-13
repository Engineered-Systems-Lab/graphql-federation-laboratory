"""The scripted reference solutions of corpus 3: corpus 2's solutions of the carried tasks, unchanged, and one solution per new task.

SOLVERS maps every scored task id (and every development task id) to a function of an Access (corpus 2's reference/common.py) that
returns the submission the task's schema expects. The carried tasks use corpus 2's solvers as they are (reference/solutions.py of
corpus 2, imported, never copied); the new tasks are written here against the same interface and corpus 2's shared steps, so a solution
in an arm reads only what that arm's own tools return. No new access method is needed.
"""
from collections import Counter, defaultdict
from decimal import Decimal

import solutions as corpus2  # corpus 2's reference/solutions.py (run_reference.py puts its folder on sys.path)
answered, counted, money = corpus2.answered, corpus2.counted, corpus2.money
resolved, people_by_id, assets_by_id, REL = corpus2.resolved, corpus2.people_by_id, corpus2.assets_by_id, corpus2.REL

NEW = {}
SOLVERS = dict(corpus2.SOLVERS)


def solver(task_id):
    def register(function):
        if task_id in corpus2.SOLVERS:
            raise ValueError('%s is a corpus 2 task; its solver is corpus 2\'s' % task_id)
        NEW[task_id] = SOLVERS[task_id] = function
        return function
    return register


# ---------------------------------------------------------------- shared steps

def staffing(acc, missions, release=REL):
    """{Personnel identifier: {missionId: role}} for the staff that the release maps, role COMMANDING_OFFICER or ASSIGNED_CREW."""
    pairs = acc.staff_map(missions, release) if missions else {}
    out = defaultdict(dict)
    for m in missions:
        for ref, pid in pairs.get(m['missionId'], []):
            if pid:
                role = 'COMMANDING_OFFICER' if ref == m['co'] else 'ASSIGNED_CREW'
                if out[pid].get(m['missionId']) != 'COMMANDING_OFFICER':
                    out[pid][m['missionId']] = role
    return out


def titled(roster, title):
    found = [p for p in roster.values() if p['positionTitle'] == title]
    if len(found) != 1:
        raise ValueError('%d members hold the position title %s' % (len(found), title))
    return found[0]['personnelId']


def users(acc, missions, release=REL, catalogue=None):
    """{Assets identifier: [missionIds]} of the resolved references."""
    out = defaultdict(list)
    for mid, ids in resolved(acc, missions, release, catalogue).items():
        for x in ids:
            out[x].append(mid)
    return out


def ids_of(missions):
    return sorted(set(missions))


# ============================================================ reverse lookups from a person
@solver('B16')
def b16(acc):
    pid = titled(people_by_id(acc), 'Flight Operations Lead')
    rows = staffing(acc, acc.list_missions())[pid]
    return answered(missions=[{'missionId': k, 'role': v} for k, v in sorted(rows.items())])


@solver('B17')
def b17(acc):
    pid = titled(people_by_id(acc), 'Transporter Chief')
    missions = acc.list_missions()
    pairs = acc.staff_map(missions, REL)
    hits = [m for m in missions if any(p == pid and ref in m['crew'] for ref, p in pairs[m['missionId']])]
    return answered(missions=[{'missionId': m['missionId'], 'type': m['type']} for m in hits])


@solver('B18')
def b18(acc):
    pid = titled(people_by_id(acc), 'Chief Medical Officer')
    rows = staffing(acc, acc.list_missions())[pid]
    return answered(missionIds=sorted(k for k, v in rows.items() if v == 'COMMANDING_OFFICER'))


@solver('B19')
def b19(acc):
    pid = titled(people_by_id(acc), 'Chief of Security')
    missions = {m['missionId']: m for m in acc.list_missions()}
    rows = staffing(acc, list(missions.values()))[pid]
    return answered(missions=[{'missionId': k, 'status': missions[k]['status']} for k in sorted(rows)])


@solver('B20')
def b20(acc):
    leave = [p['personnelId'] for p in acc.list_people(dutyStatus='ON_LEAVE')]
    rows = staffing(acc, acc.list_missions())
    return answered(members=[{'personnelId': x, 'missionIds': sorted(rows[x])} for x in sorted(leave) if rows.get(x)])


@solver('C13')
def c13(acc):
    pid = titled(people_by_id(acc), 'Acting Ensign')
    return answered(missionIds=sorted(staffing(acc, acc.list_missions(), '1.1').get(pid, {})))


@solver('C14')
def c14(acc):
    pid = titled(people_by_id(acc), 'Engineering Officer')
    return answered(missionIds=sorted(staffing(acc, acc.list_missions(), '1.1').get(pid, {})))


@solver('B21')
def b21(acc):
    sups = [p['personnelId'] for p in people_by_id(acc).values() if p['positionTitle'] == 'Section Supervisor']
    rows = staffing(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in sups for mid in rows.get(x, {})))


@solver('B22')
def b22(acc):
    command = {p['personnelId'] for p in acc.list_people(department='COMMAND')}
    rows = staffing(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in command for mid, role in rows.get(x, {}).items() if role == 'COMMANDING_OFFICER'))


@solver('B23')
def b23(acc):
    roster = people_by_id(acc)
    cmo = titled(roster, 'Chief Medical Officer')
    team = [p['personnelId'] for p in roster.values() if p['supervisor'] == cmo and p['personnelId'] != cmo]
    rows = staffing(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in team for mid in rows.get(x, {})))


# ============================================================ reverse lookups from an asset
@solver('B24')
def b24(acc):
    catalogue = assets_by_id(acc)
    kit = [x for x, a in catalogue.items() if a['name'] == 'Away-team communications kit']
    if len(kit) != 1:
        raise ValueError('%d assets carry that name' % len(kit))
    return answered(missionIds=sorted(users(acc, acc.list_missions(), catalogue=catalogue).get(kit[0], [])))


@solver('B25')
def b25(acc):
    shuttles = [a['assetId'] for a in acc.list_assets(kind='SHUTTLE')]
    per = users(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in shuttles for mid in per.get(x, [])))


@solver('B26')
def b26(acc):
    aboard = [a['assetId'] for a in acc.list_assets(parentAssetId='AST-0029')]
    per = users(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in aboard for mid in per.get(x, [])))


@solver('B27')
def b27(acc):
    missing = [a['assetId'] for a in acc.list_assets(status='MISSING')]
    per = users(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in missing for mid in per.get(x, [])))


@solver('B28')
def b28(acc):
    pairs = acc.asset_map(acc.list_missions(), REL)
    return answered(missionIds=sorted(mid for mid, rows in pairs.items()
                                      if {'AST-0005', 'AST-0007'} <= {x for _, x in rows if x}))


@solver('B29')
def b29(acc):
    catalogue = assets_by_id(acc)
    ship = [x for x, a in catalogue.items() if a['name'] == 'Shuttlecraft Magellan']
    if len(ship) != 1:
        raise ValueError('%d assets carry that name' % len(ship))
    inside = [x for x, a in catalogue.items() if a['parentAssetId'] == ship[0]]
    per = users(acc, acc.list_missions(), catalogue=catalogue)
    return answered(missionIds=ids_of(mid for x in inside for mid in per.get(x, [])))


@solver('C15')
def c15(acc):
    rovers = [a['assetId'] for a in acc.list_assets(kind='ROVER')]
    per = users(acc, acc.list_missions())
    return answered(missionIds=ids_of(mid for x in rovers for mid in per.get(x, [])))


@solver('C16')
def c16(acc):
    pairs = acc.asset_map(acc.list_missions(), '1.0')
    return answered(missionIds=sorted(mid for mid, rows in pairs.items() if any(x == 'AST-0024' for _, x in rows)))


# ============================================================ far-side aggregates
@solver('E17')
def e17(acc):
    shuttles = [a['assetId'] for a in acc.list_assets(kind='SHUTTLE')]
    per = users(acc, acc.list_missions())
    return answered(shuttles=[{'assetId': x, 'missionCount': len(set(per.get(x, [])))} for x in sorted(shuttles)])


def per_asset_field(acc, field):
    catalogue = assets_by_id(acc)
    groups = defaultdict(set)
    for x, mids in users(acc, acc.list_missions(), catalogue=catalogue).items():
        groups[catalogue[x][field]].update(mids)
    return Counter({k: len(v) for k, v in groups.items() if v})


@solver('E18')
def e18(acc):
    return answered(kinds=counted(per_asset_field(acc, 'kind'), 'kind', 'missionCount'))


@solver('E19')
def e19(acc):
    return answered(statuses=counted(per_asset_field(acc, 'status'), 'status', 'missionCount'))


@solver('E20')
def e20(acc):
    missions = {m['missionId']: m for m in acc.list_missions()}
    pairs = acc.asset_map(list(missions.values()), REL)  # the mapping alone: the question names the asset
    mids = {mid for mid, rows in pairs.items() if any(x == 'AST-0004' for _, x in rows)}
    total = sum((Decimal(missions[k]['est']) for k in mids if missions[k]['est']), Decimal('0'))
    return answered(missionCount=len(mids), totalEstimatedCost=money(total))


@solver('E21')
def e21(acc):
    command = [p['personnelId'] for p in acc.list_people(department='COMMAND')]
    rows = staffing(acc, acc.list_missions())
    per = {x: sum(1 for role in rows.get(x, {}).values() if role == 'COMMANDING_OFFICER') for x in command}
    return answered(members=[{'personnelId': x, 'missionCount': n} for x, n in sorted(per.items()) if n])


@solver('E22')
def e22(acc):
    missions = {m['missionId']: m for m in acc.list_missions()}
    rows = staffing(acc, list(missions.values())).get('PRS-2018', {})
    return answered(statuses=counted(Counter(missions[k]['status'] for k in rows), 'status'))


@solver('E23')
def e23(acc):
    roster = people_by_id(acc)
    rows = staffing(acc, acc.list_missions())
    idle = [x for x in roster if not rows.get(x)]
    return answered(memberCount=len(idle), departments=counted(Counter(roster[x]['department'] or 'CIVILIAN' for x in idle), 'department'))


@solver('E24')
def e24(acc):
    sups = [p['personnelId'] for p in people_by_id(acc).values() if p['positionTitle'] == 'Section Supervisor']
    rows = staffing(acc, acc.list_missions())
    return answered(members=[{'personnelId': x, 'missionCount': len(rows.get(x, {}))} for x in sorted(sups)])


@solver('E25')
def e25(acc):
    roster = people_by_id(acc)
    groups = defaultdict(set)
    for x, mids in staffing(acc, acc.list_missions()).items():
        if x in roster:
            groups[roster[x]['department'] or 'CIVILIAN'].update(mids)
    return answered(departments=counted(Counter({k: len(v) for k, v in groups.items()}), 'department', 'missionCount'))


# ============================================================ forward tasks over all three systems
@solver('B30')
def b30(acc):
    m = acc.get_mission('ST-00000LD4T')
    pid = acc.crew_ref_map([m['co']], REL)[m['co']]
    catalogue = assets_by_id(acc)
    ids = resolved(acc, [m], catalogue=catalogue)[m['missionId']]
    return answered(commandingOfficerDepartment=acc.get_person(pid)['department'],
                    assets=[{'assetId': x, 'kind': catalogue[x]['kind']} for x in ids])


@solver('B31')
def b31(acc):
    missions = acc.list_missions(type='RESCUE')
    roster = people_by_id(acc)
    cos = corpus2.commanding_ids(acc, missions)
    used = resolved(acc, missions)
    return answered(missions=[{'missionId': m['missionId'],
                               'commandingOfficerDepartment': roster[cos[m['missionId']]]['department'] if cos[m['missionId']] in roster else None,
                               'assetIds': sorted(used[m['missionId']])} for m in missions])


@solver('E26')
def e26(acc):
    missions = acc.list_missions(type='EXPLORATION')
    people = {p for ps in corpus2.identified(acc, missions).values() for p in ps}
    assets = {x for ids in resolved(acc, missions).values() for x in ids}
    return answered(distinctPeople=len(people), assetIds=sorted(assets))


@solver('E27')
def e27(acc):
    missions = acc.list_missions(type='FIRST_CONTACT')
    roster = people_by_id(acc)
    people = {p for ps in corpus2.identified(acc, missions, roster=roster).values() for p in ps}
    assets = {x for ids in resolved(acc, missions).values() for x in ids}
    return answered(ranks=counted(Counter(roster[p]['rank'] or 'CIVILIAN' for p in people), 'rank'), assetIds=sorted(assets))
