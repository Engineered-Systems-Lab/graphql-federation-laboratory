#!/usr/bin/env python3
"""Independent B derivation, using only the sealed package and Python stdlib.

No generated key is used as a derivation input. Every packaged byte is verified
before parsing data. Money is summed as Decimal, then represented as a JSON
number only at the output boundary. Lists representing sets are sorted.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'study/corpus3/keys-b3.json'
MISSIONS = 'uss-enterprise/missions/datasets/releases/1.2/'
ASSETS = 'uss-enterprise/assets/datasets/releases/1.1/'
PERSONNEL = 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_package(root=ROOT):
    raw = (root / 'MANIFEST.json').read_bytes()
    manifest = json.loads(raw)
    unsigned = {k: v for k, v in manifest.items() if k != 'packageSha256'}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if sha(canonical) != manifest['packageSha256']:
        raise ValueError('Package SHA-256 mismatch')
    inputs = {'MANIFEST.json': sha(raw)}
    contents = {}
    for entry in manifest['files']:
        path = entry['path']
        data = (root / path).read_bytes()
        if sha(data) != entry['sha256'] or len(data) != entry['size']:
            raise ValueError('Packaged input mismatch: ' + path)
        inputs[path] = sha(data)
        contents[path] = data
    return manifest, inputs, contents


def select(record, *fields):
    return {field: record.get(field) for field in fields}


def groups(values, field, count_field='count'):
    return [{field: value, count_field: count} for value, count in sorted(Counter(values).items())]


def total(records, field):
    return float(sum((Decimal(r[field]) for r in records if r.get(field) is not None), Decimal('0.00')))


def staff(mission, commander=True):
    refs = set(mission['assignedCrewIds'])
    if commander and mission.get('commandingOfficerId'):
        refs.add(mission['commandingOfficerId'])
    return refs


class Data:
    def __init__(self, contents):
        self.contents = contents
        self.tasks = {t['id']: t for t in self.read('study/corpus3/tasks.json')['tasks']}
        self.schemas = self.read('study/corpus3/schemas.json')['schemas']
        self.missions = {m['missionId']: m for m in self.read(MISSIONS + 'release.json')['missions']}
        self.assets = {a['assetId']: a for a in self.read(ASSETS + 'assets.json')['assets']}
        self.mappings = {}
        for version in ('1.0', '1.1', '1.2', '1.3'):
            prefix = 'federation/mapping-releases/' + version + '/'
            manifest = self.read(prefix + 'manifest.json')
            self.mappings[version] = {
                filename[:-5]: self.read(prefix + filename)['entries']
                for filename in manifest['files']
            }
        self.people = {}
        self.page_counts = []
        pm = self.read(PERSONNEL + 'manifest.json')
        offset = 0
        for page in sorted(pm['pages'], key=lambda p: p['offset']):
            if page['offset'] != offset:
                raise ValueError('Personnel paging gap')
            raw = contents[PERSONNEL + page['filename']]
            if sha(raw) != page['sha256']:
                raise ValueError('Personnel page hash mismatch')
            tree = ET.fromstring(raw)
            ns = {'p': 'urn:graphql-federation-lab:personnel:v2'}
            members = tree.findall('p:personnelMember', ns)
            if len(members) != page['count']:
                raise ValueError('Personnel page count mismatch')
            self.page_counts.append(len(members))
            for member in members:
                record = {e.tag.split('}')[-1]: e.text for e in member.iter() if len(e) == 0}
                record['name'] = record['displayName']
                record['civilian'] = member.find('p:civilianDetails', ns) is not None
                record.setdefault('rank', None)
                record.setdefault('department', None)
                record.setdefault('supervisorPersonnelId', None)
                pid = record['personnelId']
                if pid in self.people:
                    raise ValueError('Duplicate personnel ID: ' + pid)
                self.people[pid] = record
            offset += page['count']
        if offset != pm['count'] or len(self.people) != pm['count']:
            raise ValueError('Personnel total mismatch')

    def read(self, path):
        return json.loads(self.contents[path])

    def crew_map(self, version='1.3'):
        return self.mappings[version].get('crew', {})

    def officer_id(self, mission, version='1.3'):
        return self.crew_map(version).get(mission.get('commandingOfficerId'))

    def officer(self, mission):
        return self.people.get(self.officer_id(mission), {})

    def people_ids(self, missions, commander=True, version='1.3'):
        mapping = self.crew_map(version)
        return sorted({mapping[r] for m in missions for r in staff(m, commander)
                       if mapping.get(r) in self.people})

    def asset_ids(self, mission, held=True):
        mapping = self.mappings['1.3']['assets']
        return sorted({mapping[r] for r in mission['assignedAssetIds']
                       if r in mapping and (not held or mapping[r] in self.assets)})

    def asset_outcome(self, reference):
        mapping = self.mappings['1.3']['assets']
        if reference not in mapping:
            return 'UNMAPPED'
        return 'RESOLVED' if mapping[reference] in self.assets else 'UNRESOLVED'

    def descendants(self, parent, recursive=False):
        found = {a['assetId'] for a in self.assets.values() if a['parentAssetId'] == parent}
        if recursive:
            frontier = set(found)
            while frontier:
                children = {a['assetId'] for a in self.assets.values() if a['parentAssetId'] in frontier}
                frontier = children - found
                found.update(frontier)
        return sorted(found)


def derive():
    manifest, inputs, contents = verify_package()
    d = Data(contents)
    missions = sorted(d.missions.values(), key=lambda m: m['missionId'])
    people = sorted(d.people.values(), key=lambda p: p['personnelId'])
    assets = sorted(d.assets.values(), key=lambda a: a['assetId'])
    keys = {}

    def add(tid, answer, basis):
        if tid in keys:
            raise ValueError('Duplicate key: ' + tid)
        keys[tid] = {'taskId': tid, 'set': d.tasks[tid]['set'],
                     'answer': {'answerStatus': 'ANSWERED', **answer},
                     'variants': [], 'basis': basis}

    def pids(title):
        result = {p['personnelId'] for p in people if p.get('positionTitle') == title}
        if not result:
            raise ValueError('Missing title: ' + title)
        return result

    def unique_title(title):
        result = pids(title)
        if len(result) != 1:
            raise ValueError('Nonunique title: ' + title)
        return next(iter(result))

    def unique_asset(name):
        result = [a['assetId'] for a in assets if a['name'] == name]
        if len(result) != 1:
            raise ValueError('Missing or nonunique asset: ' + name)
        return result[0]

    def mission_people(m, version='1.3', commander=True):
        return set(d.people_ids([m], commander=commander, version=version))

    def mission_assets(m, version='1.3'):
        mapping = d.mappings[version]['assets']
        return {mapping[r] for r in m['assignedAssetIds']
                if mapping.get(r) in d.assets}

    def matching_people(ids, version='1.3', commander=True):
        return [m for m in missions if mission_people(m, version, commander) & ids]

    def matching_assets(ids, version='1.3'):
        return [m for m in missions if mission_assets(m, version) & ids]

    def list_missions(tid, rows, basis):
        add(tid, {'missionIds': [m['missionId'] for m in rows]}, basis)

    def department(p):
        return 'CIVILIAN' if p['civilian'] else p['department']

    flight = unique_title('Flight Operations Lead')
    add('B16', {'missions': [
        {'missionId': m['missionId'], 'role': 'COMMANDING_OFFICER'
         if d.officer_id(m) == flight else 'ASSIGNED_CREW'}
        for m in matching_people({flight})]},
        flight + '; Personnel positionTitle, mapping 1.3 crew entries, and Missions commander/assigned crew union; commander role takes precedence.')
    transporter = unique_title('Transporter Chief')
    add('B17', {'missions': [select(m, 'missionId', 'type')
                           for m in matching_people({transporter}, commander=False)]},
        transporter + '; reverse mapping 1.3 into assignedCrewIds only, then mission type.')
    medical = unique_title('Chief Medical Officer')
    list_missions('B18', [m for m in missions if d.officer_id(m) == medical],
                  medical + '; reverse mapping 1.3 into commandingOfficerId only.')
    security = unique_title('Chief of Security')
    add('B19', {'missions': [select(m, 'missionId', 'status') for m in matching_people({security})]},
        security + '; reverse mapping 1.3 into commander or assigned crew, then mission status.')
    leave = []
    for p in people:
        if p['dutyStatus'] == 'ON_LEAVE':
            mids = [m['missionId'] for m in matching_people({p['personnelId']})]
            if mids:
                leave.append({'personnelId': p['personnelId'], 'missionIds': mids})
    add('B20', {'members': leave}, 'All 1000 Personnel records filtered by ON_LEAVE; reverse mapping 1.3 into commander/assigned crew, retaining nonempty mission sets.')
    for tid, title in [('C13', 'Acting Ensign'), ('C14', 'Engineering Officer')]:
        pid = unique_title(title)
        list_missions(tid, matching_people({pid}, version='1.1'),
                      pid + '; title resolved in Personnel; only mapping 1.1 crew entries qualify commander/assigned references. An empty match is an answered empty set.')
    supervisors = pids('Section Supervisor')
    list_missions('B21', matching_people(supervisors),
                  'Personnel Section Supervisor IDs ' + ', '.join(sorted(supervisors)) + '; mapping 1.3 commander/assigned crew intersection.')
    command = {p['personnelId'] for p in people if p['department'] == 'COMMAND'}
    list_missions('B22', [m for m in missions if d.officer_id(m) in command],
                  'Personnel COMMAND department; mapping 1.3 commandingOfficerId targets only.')
    reports = {p['personnelId'] for p in people
               if p['supervisorPersonnelId'] == medical and p['personnelId'] != medical}
    list_missions('B23', matching_people(reports),
                  'Direct supervisorPersonnelId=' + medical + ' in Personnel, excluding the supervisor; mapping 1.3 commander/assigned crew intersection.')
    kit = unique_asset('Away-team communications kit')
    magellan = unique_asset('Shuttlecraft Magellan')
    asset_filters = {
        'B24': ({kit}, 'Assets name resolves to ' + kit),
        'B25': ({a['assetId'] for a in assets if a['kind'] == 'SHUTTLE'}, 'Assets kind SHUTTLE'),
        'B26': (set(d.descendants('AST-0029')), 'Assets direct parentAssetId AST-0029'),
        'B27': ({a['assetId'] for a in assets if a['status'] == 'MISSING'}, 'Assets current status MISSING'),
        'B29': (set(d.descendants(magellan)), 'Assets direct parentAssetId ' + magellan),
        'C15': ({a['assetId'] for a in assets if a['kind'] == 'ROVER'}, 'Assets kind ROVER'),
        'C16': ({'AST-0024'}, 'Assets identifier AST-0024'),
    }
    for tid, (ids, rule) in asset_filters.items():
        version = d.tasks[tid]['tags']['mapping']
        list_missions(tid, matching_assets(ids, version),
                      rule + '; reverse mapping ' + version + ' into assignedAssetIds. Only held Assets targets count; no matching reference gives an answered empty set.')
    list_missions('B28', [m for m in missions if {'AST-0005', 'AST-0007'} <= mission_assets(m)],
                  'Both AST-0005 and AST-0007 in the mapping 1.3 targets of mission assignedAssetIds.')
    add('E17', {'shuttles': [{'assetId': a['assetId'],
                            'missionCount': len(matching_assets({a['assetId']}))}
                           for a in assets if a['kind'] == 'SHUTTLE']},
        'Every Assets SHUTTLE, including unused ones; distinct mission count after mapping 1.3 assigned assets.')
    for tid, field, output in [('E18', 'kind', 'kinds'), ('E19', 'status', 'statuses')]:
        add(tid, {output: groups((value for m in missions
                                for value in {d.assets[aid][field] for aid in mission_assets(m)}),
                               field, 'missionCount')},
            'Mapping 1.3 assigned assets joined to held Assets records; one contribution per mission per distinct ' + field + ', omitting zero groups.')
    cost_missions = matching_assets({'AST-0004'})
    add('E20', {'missionCount': len(cost_missions),
                'totalEstimatedCost': total(cost_missions, 'estimatedCostCredits')},
        'Mapping 1.3 assigned assets targeting AST-0004; each mission once; exact Decimal sum of non-null estimatedCostCredits.')
    add('E21', {'members': groups((d.officer_id(m) for m in missions if d.officer_id(m) in command),
                                 'personnelId', 'missionCount')},
        'Personnel COMMAND members joined through mapping 1.3 to commandingOfficerId; omit zero mission counts.')
    add('E22', {'statuses': groups((m['status'] for m in matching_people({'PRS-2018'})), 'status')},
        'PRS-2018 via mapping 1.3 in commander/assigned crew union, one count per mission, grouped by mission status.')
    used_people = set(d.people_ids(missions))
    unused = [p for p in people if p['personnelId'] not in used_people]
    add('E23', {'memberCount': len(unused), 'departments': groups((department(p) for p in unused), 'department')},
        'All ten Personnel pages (1000 unique IDs) minus mapping 1.3 commander/assigned crew targets across all 300 missions; civilian records grouped as CIVILIAN.')
    add('E24', {'members': [{'personnelId': pid, 'missionCount': len(matching_people({pid}))}
                           for pid in sorted(supervisors)]},
        'Every Personnel Section Supervisor; count distinct missions whose mapping 1.3 commander/assigned union includes that ID, including zeros.')
    add('E25', {'departments': groups((dep for m in missions
                                      for dep in {department(d.people[pid]) for pid in mission_people(m)}),
                                     'department', 'missionCount')},
        'Mapping 1.3 commander/assigned crew joined to Personnel; one mission contribution per department, civilian records grouped as CIVILIAN.')
    m = d.missions['ST-00000LD4T']
    add('B30', {'commandingOfficerDepartment': d.officer(m).get('department'),
                'assets': [select(d.assets[aid], 'assetId', 'kind') for aid in sorted(mission_assets(m))]},
        'ST-00000LD4T; mapping 1.3 commander to Personnel department and assigned assets to Assets kind.')
    add('B31', {'missions': [{'missionId': m['missionId'],
                             'commandingOfficerDepartment': d.officer(m).get('department'),
                             'assetIds': sorted(mission_assets(m))}
                            for m in missions if m['type'] == 'RESCUE']},
        'All RESCUE missions; mapping 1.3 commander joined to Personnel (absent department is null), assigned assets joined to held Assets records.')
    for tid, kind in [('E26', 'EXPLORATION'), ('E27', 'FIRST_CONTACT')]:
        selected = [m for m in missions if m['type'] == kind]
        ids = d.people_ids(selected)
        answer = {'assetIds': sorted({aid for m in selected for aid in mission_assets(m)})}
        if tid == 'E26':
            answer['distinctPeople'] = len(ids)
        else:
            answer['ranks'] = groups(('CIVILIAN' if d.people[pid]['civilian'] else d.people[pid]['rank']
                                      for pid in ids), 'rank')
        add(tid, answer, kind + ' missions; union of mapping 1.3 commander/assigned crew targets held in Personnel and separate union of assigned asset targets held in Assets. People deduplicated across all selected missions before counting.')
    if len(keys) != 31 or set(keys) != set(d.tasks):
        raise ValueError('Task coverage mismatch')
    return {'about': "The second independent derivation of the keys for corpus 3's 31 new tasks.",
            'derivation': 'B', 'packageSha256': manifest['packageSha256'],
            'labCommit': manifest['labCommit'], 'inputs': inputs, 'keys': keys,
            'assumptions': [
                {'taskIds': sorted(keys), 'text': 'Lists representing sets are sorted by identifier or group value. List permutations and optional unscored explanation text are representation choices, not semantic variants.'},
                {'taskIds': ['B17'], 'text': 'Assigned-crew membership is tested solely in assignedCrewIds; the commander and participants do not supply membership. No qualifying mission also has this person as commander, so excluding such missions would not alter the result.'},
                {'taskIds': ['C13', 'C14', 'C15', 'C16'], 'text': 'An existing release with no qualifying mapped references yields ANSWERED and an empty mission list, since the question defines membership by that release. Missing mappings are not inferred from other releases.'}
            ], 'gaps': []}


def encode(document):
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    result = encode(derive())
    if args.write:
        OUTPUT.write_bytes(result)
        print('Wrote 31 independently derived keys to ' + str(OUTPUT))
    elif not OUTPUT.exists() or OUTPUT.read_bytes() != result:
        print('Derived keys differ from ' + str(OUTPUT), file=sys.stderr)
        return 1
    else:
        print('No difference: all 31 derived keys match byte for byte.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
