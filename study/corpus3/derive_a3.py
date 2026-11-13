"""Corpus 3, the first derivation: carry corpus 2's checked pool and ambiguity set byte for byte, author the new questions of study 3
and derive their keys from the RELEASED files, never from a run.

What it writes (this folder, with --write; compared without it):
  tasks.json      the whole scored set, with no draw: corpus 2's 76 pool tasks, the 31 new tasks, then corpus 2's 6 ambiguity tasks, each
                  record as corpus 2 holds it (without its schema); `directions` gives every scored task its `direction` and `csl`,
                  its `anchor` and its `requiredSystems`
  schemas.json    the submit_answer schema of every scored task
  expected.json   the key of every scored task
  keys-a.json     the keys of the scored set and of the development set
  dev.json        corpus 2's development set, byte for byte
  corpus-manifest.json  the hashes of those files, the corpus 2 hashes every carried task is bound to, and the released inputs

The carried tasks. The records, schemas and keys of the 76 pool tasks, the 6 ambiguity tasks and the 8 development tasks are read from
corpus 2's files, never retyped: no corpus 2 question is written in this file. Corpus 2's frozen manifest must have the SHA-256 FREEZE2 and
every corpus 2 file it reads must have the hash that manifest lists, or the derivation refuses. Each carried task is bound in the manifest
to the SHA-256 of its corpus 2 record, schema and key (`carried`), so a test proves it unchanged.

The new tasks are written with corpus 2's own helpers (its World, its schema and check helpers and its Corpus.add), in the enterprise's
words, each pick asserted by the property that made it fit. Every new question states its inclusion and membership rules.

The direction fields (decision C5 of the Job study3_corpus3) come from one rule, `classify`, over each task's category, set, required
systems and its anchor. The anchor is the system whose records the question starts from (ANCHORS for the new tasks; for the carried tasks
`missions`, except the three corpus 2 tasks that start from a person or an asset, CARRIED_ANCHORS). The required systems are the services
an answer must read; the mapping release is not a service. They are kept apart from the anchor: a question may start from a Personnel or
Assets identifier and still need only Missions and the mapping. For a new task they are its `systems`. For a carried task they are its
`systems`, except B10, B11 and B12 (CARRIED_REQUIRED): corpus 2 listed a system there that the answer does not read (for B10 and B12
their anchor system; for B11 Personnel, though the officers' identifiers come from the mapping alone). The directions
map records both, so the join width is read from `requiredSystems`, never from the anchor.

Usage (from anywhere inside a checkout): python -B study/corpus3/derive_a3.py [--write]
"""
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS2 = ROOT / 'study' / 'corpus2'
FREEZE2 = 'c57081e3fbcaaf298fc3591b486930fa4fb5dd88a0772f3c29798e26a1a354bb'  # corpus 2's frozen manifest (the Job study2_freeze)
STAMP = 'draft, not frozen'
WRITTEN = ('tasks.json', 'schemas.json', 'expected.json', 'keys-a.json', 'dev.json')


def _load_corpus2_derivation():
    """Corpus 2's derive_a.py, loaded under its own name so that it never shadows this module (it puts corpus 2 on sys.path itself)."""
    spec = importlib.util.spec_from_file_location('corpus2_derive_a', CORPUS2 / 'derive_a.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D2 = _load_corpus2_derivation()
import scoring  # noqa: E402  (corpus 2's scorer; this folder's scoring.py is a byte-identical copy, which the tests check)

STR, INT, TOKEN, NAME, ID_LIST, MONEY = D2.STR, D2.INT, D2.TOKEN, D2.NAME, D2.ID_LIST, D2.MONEY
items, nullable, eq, scalar, as_set, keyed, tok = D2.items, D2.nullable, D2.eq, D2.scalar, D2.as_set, D2.keyed, D2.tok
REL, money_text = D2.REL, D2.money_text
# Corpus 3's own words for the shared definitions, so that no ten-word window of a corpus 2 question appears in a new one
# (corpus 2's leak check looks for those windows in every file outside study/corpus2/).
STAFF = ('the commanding officer or a member of the assigned crew of the mission; its participants are not counted, and a '
         'person listed twice counts once')

ROLE = {'type': 'string', 'enum': ['COMMANDING_OFFICER', 'ASSIGNED_CREW']}
DIRECTIONS = ('forward', 'reverse', 'none')
CSL = ('reverse-lookup', 'link-integrity', 'far-side-aggregate', None)
CARRIED_ANCHORS = {'B10': 'personnel', 'B12': 'assets', 'E15': 'assets'}
# Carried tasks whose corpus 2 `systems` name a service their answer does not read: B10 and B12 their anchor, B11 Personnel (it gives the
# commanding officers' Personnel identifiers, which the mapping alone holds). Their records stay byte for byte; only `directions` differs.
CARRIED_REQUIRED = {'B10': ['missions'], 'B11': ['missions'], 'B12': ['missions']}
ANCHORS = {}  # the new tasks' anchors, filled by build_new


def sha256_lf(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def digest(data):
    """SHA-256 of canonical JSON (sorted keys, compact), the form the carried bindings use."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- the direction rule (decision C5)

def classify(task, anchor, required=None):
    """(direction, csl) of a scored task; `required` is its required systems (default: its `systems`).

    - The ambiguity set and category D (run under an outage) are outside the direction test: none.
    - A task whose anchor is a person or an asset (it starts from Personnel or Assets) and that must read Missions is reverse: a far-side
      aggregate when it aggregates (category E), a reverse lookup otherwise.
    - A mapping task (category C) that starts from missions and must read another system to check the references is link integrity,
      outside the forward-against-reverse test.
    - Any other task that starts from missions and must read another system is forward; everything else (one system, or the mapping
      alone) is none.
    """
    systems = set(task['systems'] if required is None else required)
    if task.get('set') == 'ambiguity' or task['category'] == 'D':
        return 'none', None
    if anchor in ('personnel', 'assets'):
        if 'missions' not in systems:
            raise ValueError('%s: a reverse task must read missions' % task['id'])
        return 'reverse', 'far-side-aggregate' if task['category'] == 'E' else 'reverse-lookup'
    if anchor != 'missions':
        raise ValueError('%s: unknown anchor %r' % (task['id'], anchor))
    if task['category'] == 'C' and len(systems) >= 2:
        return 'none', 'link-integrity'
    if 'missions' in systems and len(systems) >= 2:
        return 'forward', None
    return 'none', None


# ---------------------------------------------------------------- the new tasks

def build_new(w):
    """The 31 new core tasks: 27 in the reverse group (18 reverse lookups, 9 far-side aggregates) and 4 forward tasks over all three
    systems. Returns corpus 2's Corpus object holding them in its 'core' group."""
    c = D2.Corpus(w)
    staffed = defaultdict(list)   # Personnel identifier -> [(mission, role)] under release 1.3
    for m in w.missions:
        for ref in w.staff(m):
            pid = w.person_id(ref)
            if pid and pid in w.people:
                staffed[pid].append((m, 'COMMANDING_OFFICER' if ref == m['co'] else 'ASSIGNED_CREW'))
    used = defaultdict(list)      # Assets identifier -> [missions] under release 1.3 (resolved references only)
    for m in w.missions:
        for x in w.resolved_assets(m):
            used[x].append(m)

    def titled(title):
        found = [p for p in w.people.values() if p['positionTitle'] == title]
        assert len(found) == 1, title
        return found[0]

    def ids(missions):
        return sorted({m['missionId'] for m in missions})

    def add(tid, anchor, *args, **kwargs):
        ANCHORS[tid] = anchor
        c.add('core', tid, *args, **kwargs)

    # ============================================================ reverse lookups from a person
    p = titled('Flight Operations Lead')
    rows = {m['missionId']: role for m, role in staffed[p['personnelId']]}
    assert len(rows) == 15 and set(rows.values()) == {'COMMANDING_OFFICER', 'ASSIGNED_CREW'}
    add('B16', 'personnel', 'B', 'small', ['missions', 'personnel'],
        'Using %s, on which missions was the member of the Personnel roster whose position title is Flight Operations Lead one of the '
        'people on the mission (%s)? For each mission give its identifier and that member\'s role on it: COMMANDING_OFFICER when the '
        'member commanded the mission, even if also listed among its assigned crew, and ASSIGNED_CREW otherwise.' % (REL, STAFF),
        {'missions': items({'missionId': STR, 'role': ROLE})},
        [keyed('missions', 'missionId', {k: {'role': {'equals': v}} for k, v in rows.items()})],
        {'missions': [{'missionId': k, 'role': v} for k, v in sorted(rows.items())]}, mapping='1.3',
        note='Reverse lookup: the person is found in the Personnel system by a unique position title, then the crew reference release '
             '1.3 maps to that person, then the missions that reference staffs.')

    p = titled('Transporter Chief')
    crewed = [m for m in w.missions if any(w.person_id(r) == p['personnelId'] for r in m['crew'])]
    assert len(crewed) == 11
    add('B17', 'personnel', 'B', 'small', ['missions', 'personnel'],
        'Using %s, which missions had the member of the Personnel roster whose position title is Transporter Chief among their assigned '
        'crew (not as commanding officer, not as a participant)? Give each mission\'s identifier and type.' % REL,
        {'missions': items({'missionId': STR, 'type': TOKEN})},
        [keyed('missions', 'missionId', {m['missionId']: {'type': {'equals': m['type']}} for m in crewed})],
        {'missions': [{'missionId': m['missionId'], 'type': m['type']} for m in sorted(crewed, key=lambda m: m['missionId'])]}, mapping='1.3')

    p = titled('Chief Medical Officer')
    commanded = ids(m for m, role in staffed[p['personnelId']] if role == 'COMMANDING_OFFICER')
    assert len(commanded) == 20
    add('B18', 'personnel', 'B', 'small', ['missions', 'personnel'],
        'Using %s, which missions were commanded by the member of the Personnel roster whose position title is Chief Medical Officer? '
        'List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', commanded)], {'missionIds': commanded}, mapping='1.3')

    p = titled('Chief of Security')
    on = sorted({m['missionId']: m for m, _ in staffed[p['personnelId']]}.values(), key=lambda m: m['missionId'])
    assert len(on) == 39
    add('B19', 'personnel', 'B', 'medium', ['missions', 'personnel'],
        'Using %s, on which missions was the member of the Personnel roster whose position title is Chief of Security one of the people '
        'on the mission (%s)? Give each mission\'s identifier and status.' % (REL, STAFF),
        {'missions': items({'missionId': STR, 'status': TOKEN})},
        [keyed('missions', 'missionId', {m['missionId']: {'status': {'equals': m['status']}} for m in on})],
        {'missions': [{'missionId': m['missionId'], 'status': m['status']} for m in on]}, mapping='1.3')

    leave = sorted(x for x, q in w.people.items() if q['dutyStatus'] == 'ON_LEAVE')
    rows = {x: ids(m for m, _ in staffed[x]) for x in leave if staffed[x]}
    assert len(leave) == 45 and 0 < len(rows) < len(leave)
    add('B20', 'personnel', 'B', 'medium', ['missions', 'personnel'],
        'Using %s, which members of the Personnel roster whose duty status is on leave were among the people of at least one mission '
        '(%s)? For each such member give the Personnel identifier and the identifiers of those missions, leaving out the members on '
        'leave who were on no mission.' % (REL, STAFF),
        {'members': items({'personnelId': STR, 'missionIds': ID_LIST})},
        [keyed('members', 'personnelId', {x: {'missionIds': {'set': v}} for x, v in rows.items()})],
        {'members': [{'personnelId': x, 'missionIds': v} for x, v in sorted(rows.items())]}, mapping='1.3',
        note='The population is the 45 members on leave; only some of them were on a mission.')

    p = titled('Acting Ensign')
    refs11 = [r for r, x in w.crew_map['1.1'].items() if x == p['personnelId']]
    on = ids(m for m in w.missions if any(r in refs11 for r in w.staff(m)))
    assert len(refs11) == 1 and len(on) == 2
    add('C13', 'personnel', 'C', 'small', ['missions', 'personnel'],
        'Using mapping release 1.1, on which missions was the member of the Personnel roster whose position title is Acting Ensign one '
        'of the people on the mission (%s)? A mission counts when release 1.1 maps one of those crew references to that member. List '
        'the mission identifiers.' % STAFF,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.1',
        note='Release 1.1 holds only ten crew entries; this member is one of them.')

    p = titled('Engineering Officer')
    assert p['personnelId'] not in w.crew_map['1.1'].values() and staffed[p['personnelId']]
    add('C14', 'personnel', 'C', 'small', ['missions', 'personnel'],
        'Using mapping release 1.1, and no other release, on which missions was the member of the Personnel roster whose position '
        'title is Engineering Officer one of the people on the mission (%s)? A mission counts only when release 1.1 maps one of those '
        'crew references to that member. List the mission identifiers.' % STAFF,
        {'missionIds': ID_LIST},
        [{'op': 'empty', 'path': 'missionIds', 'name': 'names_missions_anyway', 'honesty': True}],
        {'answerStatus': 'ANSWERED', 'missionIds': []}, mapping='1.1', status_spec={'in': ['ANSWERED', 'CANNOT_BE_DETERMINED']},
        note='Release 1.1 has no entry that maps a crew reference to this member (release 1.3 has one), so no mission counts. An answer '
             'that names no mission is accepted with either status; naming a mission fails.')

    sups = sorted(x for x, q in w.people.items() if q['positionTitle'] == 'Section Supervisor')
    on = ids(m for x in sups for m, _ in staffed[x])
    assert len(sups) == 7 and 21 <= len(on) <= 299
    add('B21', 'personnel', 'B', 'medium', ['missions', 'personnel'],
        'Using %s, which missions had among their people (%s) at least one member of the Personnel roster whose position title is '
        'Section Supervisor? List the mission identifiers.' % (REL, STAFF),
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    command = sorted(x for x, q in w.people.items() if q['department'] == 'COMMAND')
    commanded = ids(m for x in command for m, role in staffed[x] if role == 'COMMANDING_OFFICER')
    assert len(command) == 20 and 21 <= len(commanded) <= 299
    add('B22', 'personnel', 'B', 'medium', ['missions', 'personnel'],
        'Using %s, which missions were commanded by a member of the Command department of the Personnel roster? List the mission '
        'identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', commanded)], {'missionIds': commanded}, mapping='1.3')

    cmo = titled('Chief Medical Officer')['personnelId']
    team = sorted(x for x, q in w.people.items() if q['supervisor'] == cmo)
    on = ids(m for x in team for m, _ in staffed[x])
    assert cmo not in team and len(team) == 10 and len(on) == 17
    add('B23', 'personnel', 'B', 'small', ['missions', 'personnel'],
        'Using %s, which missions had among their people (%s) at least one member of the Personnel roster whom the Personnel system '
        'records as supervised by the member whose position title is Chief Medical Officer? A member counts when the supervisor their '
        'own record names is that member; the Chief Medical Officer does not count. List the mission identifiers.' % (REL, STAFF),
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    # ============================================================ reverse lookups from an asset
    kit = [x for x, a in w.assets.items() if a['name'] == 'Away-team communications kit']
    on = ids(used[kit[0]])
    assert len(kit) == 1 and len(on) == 33
    add('B24', 'assets', 'B', 'medium', ['assets', 'missions'],
        'Using %s, which missions used the asset that the Assets system names Away-team communications kit? A reference counts when the '
        'release maps it to that asset. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    shuttles = sorted(x for x, a in w.assets.items() if a['kind'] == 'SHUTTLE')
    on = ids(m for x in shuttles for m in used[x])
    assert len(shuttles) == 5 and len(on) == 82
    add('B25', 'assets', 'B', 'medium', ['assets', 'missions'],
        'Using %s, which missions used at least one asset of the kind shuttle? An asset reference is counted only if the release maps it to an asset that the Assets system holds. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    aboard = sorted(x for x, a in w.assets.items() if a['parentAssetId'] == 'AST-0029')
    on = ids(m for x in aboard for m in used[x])
    assert len(on) == 113 and not set(ids(used['AST-0029'])) <= set(on)
    add('B26', 'assets', 'B', 'medium', ['assets', 'missions'],
        'Using %s, which missions used at least one asset that the Assets system records as directly aboard or part of AST-0029 (an asset '
        'whose own record names AST-0029; not AST-0029 itself, and not the assets aboard those)? List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    missing = sorted(x for x, a in w.assets.items() if a['status'] == 'MISSING')
    on = ids(m for x in missing for m in used[x])
    assert len(missing) == 2 and len(on) == 47
    add('B27', 'assets', 'B', 'medium', ['assets', 'missions'],
        'Using %s, which missions used at least one asset whose current status in the Assets system is missing? An asset reference is counted only if the release maps it to an asset that the Assets system holds. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    both = ids(m for m in used['AST-0005'] if m in used['AST-0007'])
    assert len(both) == 1
    add('B28', 'assets', 'B', 'medium', ['missions'],
        'Using %s, which missions used both the asset AST-0005 and the asset AST-0007? A mission counts when the release maps one of its '
        'references to AST-0005 and another to AST-0007. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', both)], {'missionIds': both}, mapping='1.3',
        note='Medium: the answer rests on the 36 and 33 missions that used each asset, though it names one.')

    magellan = [x for x, a in w.assets.items() if a['name'] == 'Shuttlecraft Magellan']
    inside = sorted(x for x, a in w.assets.items() if magellan and a['parentAssetId'] == magellan[0])
    on = ids(m for x in inside for m in used[x])
    assert len(magellan) == 1 and len(on) == 88 and not used[magellan[0]]
    add('B29', 'assets', 'B', 'medium', ['assets', 'missions'],
        'Using %s, which missions used an asset that the Assets system records as directly aboard or part of the asset named Shuttlecraft '
        'Magellan (an asset whose own record names that shuttle; not the shuttle itself)? An asset reference is counted only if the release maps it to an asset that the Assets system holds. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST}, [as_set('missionIds', on)], {'missionIds': on}, mapping='1.3')

    rovers = sorted(x for x, a in w.assets.items() if a['kind'] == 'ROVER')
    assert len(rovers) == 3 and not any(used[x] for x in rovers)
    assert not any(w.asset_map['1.3'].get(r) in rovers for m in w.missions for r in m['assetRefs'])
    add('C15', 'assets', 'C', 'small', ['assets', 'missions'],
        'Using %s, which missions used at least one asset of the kind rover? An asset reference is counted only if the release maps it to an asset that the Assets system holds. List the mission identifiers.' % REL,
        {'missionIds': ID_LIST},
        [{'op': 'empty', 'path': 'missionIds', 'name': 'names_missions_anyway', 'honesty': True}],
        {'answerStatus': 'ANSWERED', 'missionIds': []}, mapping='1.3', status_spec={'in': ['ANSWERED', 'CANNOT_BE_DETERMINED']},
        note='The release maps no mission reference to a rover, so no mission counts. An answer that names no mission is accepted with '
             'either status; naming a mission fails.')

    on10 = ids(m for m in w.missions if any(w.asset_map['1.0'].get(r) == 'AST-0024' for r in m['assetRefs']))
    assert len(on10) == 56 and on10 == ids(used['AST-0024'])
    add('C16', 'assets', 'C', 'medium', ['missions'],
        'Using mapping release 1.0, which missions used the asset AST-0024? A reference counts when release 1.0 maps it to AST-0024. '
        'List the mission identifiers.',
        {'missionIds': ID_LIST}, [as_set('missionIds', on10)], {'missionIds': on10}, mapping='1.0',
        note='Release 1.0 has an assets section (and no crew section).')

    # ============================================================ far-side aggregates
    per = {x: len(used[x]) for x in shuttles}
    assert 0 in per.values() and len(set(per.values())) > 2
    add('E17', 'assets', 'E', 'medium', ['assets', 'missions'],
        'Using %s, for each asset of the kind shuttle that the Assets system holds, how many missions used it? Include every shuttle, '
        'with 0 when no mission used it; a reference counts when the release maps it to that shuttle, and each mission counts once per '
        'shuttle.' % REL,
        {'shuttles': items({'assetId': STR, 'missionCount': INT})},
        [keyed('shuttles', 'assetId', {x: {'missionCount': {'int': n}} for x, n in per.items()})],
        {'shuttles': [{'assetId': x, 'missionCount': n} for x, n in sorted(per.items())]}, mapping='1.3')

    kinds = defaultdict(set)
    statuses = defaultdict(set)
    for x, ms in used.items():
        kinds[w.assets[x]['kind']].update(m['missionId'] for m in ms)
        statuses[w.assets[x]['status']].update(m['missionId'] for m in ms)
    kinds = {k: len(v) for k, v in kinds.items() if v}
    statuses = {k: len(v) for k, v in statuses.items() if v}
    assert len(kinds) == 5 and len(statuses) == 3
    add('E18', 'assets', 'E', 'large', ['assets', 'missions'],
        'Using %s, for each asset kind, how many distinct missions used at least one asset of that kind? An asset reference is counted only if the release maps it to an asset that the Assets system holds, and a mission counts once per kind. Give the count per kind, leaving '
        'out kinds that no mission used.' % REL,
        {'kinds': items({'kind': TOKEN, 'missionCount': INT})},
        [keyed('kinds', 'kind', {k: {'missionCount': {'int': n}} for k, n in kinds.items()})],
        {'kinds': [{'kind': k, 'missionCount': n} for k, n in sorted(kinds.items())]}, mapping='1.3',
        note='Every mission is read; the assets are the starting side.')

    add('E19', 'assets', 'E', 'large', ['assets', 'missions'],
        'Using %s, for each status that the Assets system currently records for an asset, how many distinct missions used at least one '
        'asset with that status? An asset reference is counted only if the release maps it to an asset that the Assets system holds, and a mission '
        'counts once per status (it may count under several). Give the count per status, leaving out statuses that no mission used.' % REL,
        {'statuses': items({'status': TOKEN, 'missionCount': INT})},
        [keyed('statuses', 'status', {k: {'missionCount': {'int': n}} for k, n in statuses.items()})],
        {'statuses': [{'status': k, 'missionCount': n} for k, n in sorted(statuses.items())]}, mapping='1.3')

    ms = used['AST-0004']
    total = sum((Decimal(m['est']) for m in ms if m['est']), Decimal('0'))
    assert len(ms) == 88
    add('E20', 'assets', 'E', 'medium', ['missions'],
        'Using %s, how many missions used the asset AST-0004, and what do the estimated costs of those missions add up to? A reference counts '
        'when the release maps it to AST-0004; a mission without an estimated cost adds nothing to the total.' % REL,
        {'missionCount': INT, 'totalEstimatedCost': MONEY},
        [scalar('missionCount', {'int': len(ms)}), scalar('totalEstimatedCost', {'money': money_text(total)})],
        {'missionCount': len(ms), 'totalEstimatedCost': float(total)}, mapping='1.3')

    per = {x: sum(1 for _, role in staffed[x] if role == 'COMMANDING_OFFICER') for x in command}
    per = {x: n for x, n in per.items() if n}
    assert 2 < len(per) < len(command)
    add('E21', 'personnel', 'E', 'medium', ['missions', 'personnel'],
        'Using %s, for each member of the Command department of the Personnel roster who commanded at least one mission, how many '
        'missions did that member command? Leave out the members who commanded none.' % REL,
        {'members': items({'personnelId': STR, 'missionCount': INT})},
        [keyed('members', 'personnelId', {x: {'missionCount': {'int': n}} for x, n in per.items()})],
        {'members': [{'personnelId': x, 'missionCount': n} for x, n in sorted(per.items())]}, mapping='1.3')

    st = Counter(m['status'] for m, _ in staffed['PRS-2018'])
    assert sum(st.values()) == 11 and len(st) > 2
    add('E22', 'personnel', 'E', 'small', ['missions'],
        'Using %s, on how many missions of each status was Personnel member PRS-2018 one of the people on the mission (%s)? Give one count per status; statuses without such missions are left out.' % (REL, STAFF),
        {'statuses': items({'status': TOKEN, 'count': INT})},
        [keyed('statuses', 'status', {s: {'count': {'int': n}} for s, n in st.items()})],
        {'statuses': [{'status': s, 'count': n} for s, n in sorted(st.items())]}, mapping='1.3')

    idle = [x for x in w.people if not staffed[x]]
    dept = Counter(w.people[x]['department'] or 'CIVILIAN' for x in idle)
    assert len(idle) == 380 and 'CIVILIAN' in dept
    add('E23', 'personnel', 'E', 'large', ['missions', 'personnel'],
        'Using %s, how many members of the Personnel roster were on no mission at all, and how many of them are in each department? A '
        'member was on a mission when the release maps the mission\'s commanding officer or one of its assigned crew to that member '
        '(participants do not count). Count the civilians, who have no department, as one group named CIVILIAN, and leave out '
        'departments with no such members.' % REL,
        {'memberCount': INT, 'departments': items({'department': TOKEN, 'count': INT})},
        [scalar('memberCount', {'int': len(idle)}), keyed('departments', 'department', {d: {'count': {'int': n}} for d, n in dept.items()})],
        {'memberCount': len(idle), 'departments': [{'department': d, 'count': n} for d, n in sorted(dept.items())]}, mapping='1.3',
        note='Every member of the roster and every mission are read; a member that the release does not map was on no mission.')

    per = {x: len({m['missionId'] for m, _ in staffed[x]}) for x in sups}
    assert len(per) == 7 and 0 not in per.values()
    add('E24', 'personnel', 'E', 'medium', ['missions', 'personnel'],
        'Using %s, for each member of the Personnel roster whose position title is Section Supervisor, on how many missions was that '
        'member one of the people on the mission (%s)? Include every Section Supervisor, with 0 when on no mission.' % (REL, STAFF),
        {'members': items({'personnelId': STR, 'missionCount': INT})},
        [keyed('members', 'personnelId', {x: {'missionCount': {'int': n}} for x, n in per.items()})],
        {'members': [{'personnelId': x, 'missionCount': n} for x, n in sorted(per.items())]}, mapping='1.3')

    dep = defaultdict(set)
    for x, rows_ in staffed.items():
        for m, _ in rows_:
            dep[w.people[x]['department'] or 'CIVILIAN'].add(m['missionId'])
    dep = {d: len(v) for d, v in dep.items()}
    assert 'CIVILIAN' in dep and len(dep) == 8
    add('E25', 'personnel', 'E', 'large', ['missions', 'personnel'],
        'Using %s, for each department of the Personnel roster, how many distinct missions had at least one member of that department '
        'among their people (%s)? A mission counts once per department. Count the civilians, who have no department, as one group named '
        'CIVILIAN, and leave out departments with no such missions.' % (REL, STAFF),
        {'departments': items({'department': TOKEN, 'missionCount': INT})},
        [keyed('departments', 'department', {d: {'missionCount': {'int': n}} for d, n in dep.items()})],
        {'departments': [{'department': d, 'missionCount': n} for d, n in sorted(dep.items())]}, mapping='1.3')

    # ============================================================ forward tasks over all three systems
    m = w.by_id['ST-00000LD4T']
    co = w.person(m['co'])
    assets = w.resolved_assets(m)
    assert co and not co['civilian'] and len(assets) == len(m['assetRefs']) == 3
    add('B30', 'missions', 'B', 'small', ['assets', 'missions', 'personnel'],
        'Using %s, what is the department of the commanding officer of mission ST-00000LD4T, and what kind of asset is each asset the '
        'mission used? Give the department, and each asset\'s Assets identifier and kind.' % REL,
        {'commandingOfficerDepartment': TOKEN, 'assets': items({'assetId': STR, 'kind': TOKEN})},
        [eq('commandingOfficerDepartment', co['department']),
         keyed('assets', 'assetId', {x: {'kind': {'equals': w.assets[x]['kind']}} for x in assets})],
        {'commandingOfficerDepartment': co['department'], 'assets': [{'assetId': x, 'kind': w.assets[x]['kind']} for x in assets]},
        mapping='1.3')

    rescue = w.where(type='RESCUE')
    rows = {}
    for m in rescue:
        co = w.person(m['co']) if m['co'] else None
        rows[m['missionId']] = {'department': co['department'] if co else None, 'assets': sorted(w.resolved_assets(m))}
    assert len(rescue) == 19 and any(r['department'] is None for r in rows.values()) and len({len(r['assets']) for r in rows.values()}) > 1
    add('B31', 'missions', 'B', 'medium', ['assets', 'missions', 'personnel'],
        'Using %s, for every mission of the type rescue, give the department of its commanding officer (null when the mission has no '
        'commanding officer, when the release cannot identify the officer, or when the officer is a civilian with no department) and '
        'the Assets identifiers of the assets it used (an asset reference is counted only if the release maps it to an asset that the Assets system holds; an empty list when none does).' % REL,
        {'missions': items({'missionId': STR, 'commandingOfficerDepartment': nullable(TOKEN), 'assetIds': ID_LIST})},
        [keyed('missions', 'missionId', {k: {'commandingOfficerDepartment': tok(v['department']), 'assetIds': {'set': v['assets']}}
                                         for k, v in rows.items()})],
        {'missions': [{'missionId': k, 'commandingOfficerDepartment': v['department'], 'assetIds': v['assets']} for k, v in rows.items()]},
        mapping='1.3')

    expl = w.where(type='EXPLORATION')
    people_ = w.people_of(expl)
    assets = sorted({x for m in expl for x in w.resolved_assets(m)})
    assert len(expl) == 27 and len(people_) == 107 and len(assets) == 3
    add('E26', 'missions', 'E', 'medium', ['assets', 'missions', 'personnel'],
        'Using %s, across the missions of the type exploration, how many different members of the Personnel roster were among their people (the commanding officer or a member of the assigned crew of each mission, never a participant; each member counted once over all of those missions), and which distinct '
        'assets of the Assets system did they use (an asset reference is counted only if the release maps it to an asset that the Assets system holds)? Give the number of people and the Assets identifiers.' % REL,
        {'distinctPeople': INT, 'assetIds': ID_LIST},
        [scalar('distinctPeople', {'int': len(people_)}), as_set('assetIds', assets)],
        {'distinctPeople': len(people_), 'assetIds': assets}, mapping='1.3')

    fc = w.where(type='FIRST_CONTACT')
    ranks = Counter(w.people[x]['rank'] or 'CIVILIAN' for x in w.people_of(fc))
    assets = sorted({x for m in fc for x in w.resolved_assets(m)})
    assert len(fc) == 4 and len(ranks) > 1 and len(assets) == 4
    add('E27', 'missions', 'E', 'small', ['assets', 'missions', 'personnel'],
        'Using %s, across the missions of the type first contact, how many different members of the Personnel roster of each rank were among their people (the commanding officer or a member of the assigned crew of each mission, never a participant; each member counted once over all of those missions), and which '
        'distinct assets of the Assets system did they use (an asset reference is counted only if the release maps it to an asset that the Assets system holds)? Give one count per rank, without the ranks that have none and with any civilians counted as one group named CIVILIAN, and give the Assets identifiers.' % REL,
        {'ranks': items({'rank': TOKEN, 'count': INT}), 'assetIds': ID_LIST},
        [keyed('ranks', 'rank', {r: {'count': {'int': n}} for r, n in ranks.items()}), as_set('assetIds', assets)],
        {'ranks': [{'rank': r, 'count': n} for r, n in sorted(ranks.items())], 'assetIds': assets}, mapping='1.3')
    return c


# ---------------------------------------------------------------- corpus 2, carried

def corpus2_files():
    """Corpus 2's pool, ambiguity set, development set and keys, after checking its manifest is the frozen one and every file it
    reads has the hash the manifest lists. Returns ({name: parsed}, the manifest's SHA-256)."""
    manifest_path = CORPUS2 / 'corpus-manifest.json'
    held = sha256_lf(manifest_path)
    if held != FREEZE2:
        raise SystemExit('corpus 2\'s manifest is %s, not the frozen %s' % (held, FREEZE2))
    listed = json.loads(manifest_path.read_text(encoding='utf-8'))['files']
    out = {}
    for name in ('pool.json', 'ambiguity.json', 'dev.json', 'keys-a.json'):
        if sha256_lf(CORPUS2 / name) != listed[name]:
            raise SystemExit('corpus 2\'s %s differs from its frozen manifest' % name)
        out[name] = json.loads((CORPUS2 / name).read_text(encoding='utf-8'))
    return out, held


def bare(task):
    """A task record as tasks.json holds it: the pool record without its schema."""
    return {k: v for k, v in task.items() if k != 'schema'}


# ---------------------------------------------------------------- output

def self_check(entries):
    for entry, schema, key in entries:
        answer = dict(key['answer'])
        answer.setdefault('answerStatus', 'ANSWERED')
        errors = scoring.validate(answer, schema)
        assert not errors, (entry['id'], errors)
        outcome, _, failed, _ = scoring.evaluate_core(answer, key)
        assert outcome == 'correct', (entry['id'], failed)


def derive():
    """{file name: text} of every file this folder derives, the manifest included."""
    two, manifest2 = corpus2_files()
    ANCHORS.clear()
    new = build_new(D2.World()).groups['core']
    self_check(new)
    keys2 = two['keys-a.json']['keys']
    pool, ambiguity, dev = two['pool.json']['tasks'], two['ambiguity.json']['tasks'], two['dev.json']['tasks']
    taken = {t['id'] for t in pool + ambiguity + dev}
    clash = sorted(taken & {t['id'] for t, _, _ in new})
    assert not clash, clash
    records = [bare(t) for t in pool] + [t for t, _, _ in new] + [bare(t) for t in ambiguity]
    schemas = {t['id']: t['schema'] for t in pool + ambiguity}
    schemas.update({t['id']: s for t, s, _ in new})
    keys = {t['id']: keys2[t['id']] for t in pool + ambiguity}
    keys.update({t['id']: {'taskId': t['id'], **k} for t, _, k in new})
    anchors = {t['id']: CARRIED_ANCHORS.get(t['id'], 'missions') for t in pool + ambiguity}
    anchors.update(ANCHORS)
    directions = {}
    for t in records:
        required = sorted(CARRIED_REQUIRED.get(t['id'], t['systems']))
        direction, csl = classify(t, anchors[t['id']], required)
        directions[t['id']] = {'direction': direction, 'csl': csl, 'anchor': anchors[t['id']], 'requiredSystems': required}
    all_keys = dict(keys)
    all_keys.update({t['id']: keys2[t['id']] for t in dev})
    render = D2.render
    texts = {
        'tasks.json': render({
            'about': 'The scored tasks of corpus 3, the whole set with no draw: the 76 pool tasks of corpus 2, then the 31 new tasks of '
                     'study 3, then the 6 tasks of corpus 2\'s ambiguity set. A carried record is byte for byte its corpus 2 record; '
                     '`directions` gives every task its direction and CSL kind (derive_a3.py, classify), its anchor and the systems its '
                     'answer must read. The question is asked word for '
                     'word in every arm.',
            'directions': directions, 'tasks': records}),
        'schemas.json': render({'about': 'The submit_answer JSON Schema of each scored task.', 'schemas': schemas}),
        'expected.json': render({'about': 'The key of each scored task, from keys-a.json (the first derivation).', 'expected': keys}),
        'keys-a.json': render({'about': 'The keys of corpus 3 by the first derivation: the carried keys of corpus 2 byte for byte and the '
                                        'keys of the new tasks, derived from the released files by derive_a3.py, never from a run; for '
                                        'every scored task and every task of the development set.',
                               'status': STAMP, 'derivedFrom': D2.sources(), 'keys': all_keys}),
    }
    texts['dev.json'] = (CORPUS2 / 'dev.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    hashes = {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in texts.items()}
    carried = {t['id']: {'record': digest(t), 'schema': digest(t['schema']), 'key': digest(keys2[t['id']])} for t in pool + ambiguity + dev}
    counts = Counter(t.get('set', 'core') for t in records)
    manifest = {'about': 'Checksums of corpus 3 as derived. NOT frozen. `carried` binds every task carried from corpus 2 to the SHA-256 '
                         '(canonical JSON) of its corpus 2 record, schema and key; `corpus2Manifest` is corpus 2\'s frozen manifest.',
                'status': STAMP, 'coreTasks': counts['core'], 'newTasks': len(new), 'ambiguityTasks': counts['ambiguity'], 'devTasks': len(dev),
                'files': hashes, 'corpus2Manifest': manifest2, 'carried': carried, 'newTaskIds': [t['id'] for t, _, _ in new],
                'derivedFrom': D2.sources()}
    texts['corpus-manifest.json'] = render(manifest)
    return texts


def committed_status(folder=HERE):
    try:
        return json.loads((Path(folder) / 'corpus-manifest.json').read_text(encoding='utf-8')).get('status')
    except (OSError, ValueError, AttributeError):
        return None


def stale_files(texts, folder=HERE):
    return [name for name, text in texts.items()
            if not (Path(folder) / name).exists() or (Path(folder) / name).read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text]


def main(argv, folder=HERE):
    folder = Path(folder)
    if list(argv) not in ([], ['--write']):
        print('usage: derive_a3.py [--write]', file=sys.stderr)
        return 2
    texts = derive()
    if argv == ['--write']:
        held = committed_status(folder)
        if held not in (None, STAMP):
            print('FAIL: the committed manifest is %r; --write replaces only a draft manifest' % held, file=sys.stderr)
            return 1
        for name, text in texts.items():
            (folder / name).write_bytes(text.encode('utf-8'))
        print('wrote', ', '.join(texts), 'with the manifest status', STAMP)
        return 0
    stale = stale_files(texts, folder)
    if stale:
        print('FAIL: differs from the derivation:', ', '.join(stale), file=sys.stderr)
        return 1
    print('ok: corpus 3 matches corpus 2 and the released files (manifest status: %s)' % committed_status(folder))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
