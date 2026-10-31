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
from itertools import combinations
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'study/corpus2/keys-b.json'
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
        self.tasks = {}
        for filename in ('pool', 'ambiguity', 'dev'):
            for original in self.read('study/corpus2/' + filename + '.json')['tasks']:
                task = dict(original)
                task.setdefault('set', 'dev')
                if task['id'] in self.tasks:
                    raise ValueError('Duplicate task')
                self.tasks[task['id']] = task
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
    keys = {}
    assumptions = []
    all_m = sorted(d.missions.values(), key=lambda m: m['missionId'])
    all_p = sorted(d.people.values(), key=lambda p: p['personnelId'])
    all_a = sorted(d.assets.values(), key=lambda a: a['assetId'])
    cm = d.crew_map()
    am = d.mappings['1.3']['assets']

    def add(tid, answer, basis, variants=None, interpretations=None):
        answer = {'answerStatus': 'ANSWERED', **answer}
        key = {'taskId': tid, 'set': d.tasks[tid]['set'], 'answer': answer,
               'variants': variants or [], 'basis': basis}
        if interpretations is not None:
            key['interpretations'] = interpretations
        if tid in keys:
            raise ValueError('Duplicate derivation: ' + tid)
        keys[tid] = key

    def assume(ids, text):
        assumptions.append({'taskIds': sorted(ids), 'text': text})

    def ms(**filters):
        return [m for m in all_m if all(m.get(k) == v for k, v in filters.items())]

    def people_rows(ids, *fields):
        return [select(d.people[pid], 'personnelId', *fields) for pid in sorted(ids)]

    def asset_rows(ids, *fields):
        return [select(d.assets[aid], 'assetId', *fields) for aid in sorted(ids)]

    def nonactive_assets(m):
        return any(d.assets[aid]['status'] != 'ACTIVE' for aid in d.asset_ids(m))

    def top_answers(tid, counts, field, other, basis):
        highest = max(counts.values())
        winners = sorted(k for k, v in counts.items() if v == highest)
        answers = [{'answerStatus': 'ANSWERED', **other, field: w} for w in winners]
        add(tid, answers[0], basis, [
            {'answer': a, 'reason': 'This group ties for the largest distinct-person count.'}
            for a in answers[1:]])

    # Direct lookups and joins. The task text supplies the local record IDs.
    for tid in ('A01', 'A02', 'A03', 'A04', 'A07', 'A08', 'B01', 'B02',
                'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B09', 'C01',
                'C02', 'C03', 'C04', 'C05', 'C12', 'E03', 'V01', 'V02'):
        t = d.tasks[tid]
        match = re.search(r'ST-[A-Z0-9]+|AST-\d+|PRS-\d+', t['question'])
        rid = match.group()
        m = d.missions.get(rid)
        p = d.people.get(rid)
        a = d.assets.get(rid)
        basis = rid + '; '
        if tid in ('A01', 'A02', 'V01'):
            ans = select(m, *(f for f in t['schema']['required'] if f != 'answerStatus'))
            basis += 'direct fields in Missions release 1.2.'
        elif tid == 'A03':
            ans = {'locationType': m['location']['type'], 'locationName': m['location']['name'],
                   'durationHours': m['durationHours']}
            basis += 'location and duration in Missions release 1.2.'
        elif tid == 'A04':
            ans = select(a, 'kind', 'status', 'parentAssetId')
            basis += 'direct fields in Assets 1.1.'
        elif tid == 'A07':
            ans = select(p, 'rank', 'department', 'dutyStatus')
            basis += 'Personnel snapshot crew details and duty status.'
        elif tid == 'A08':
            supervisor = d.people[p['supervisorPersonnelId']]
            ans = dict(zip(('supervisorId', 'supervisorName', 'supervisorRank'),
                           (supervisor['personnelId'], supervisor['name'], supervisor['rank'])))
            basis += 'supervisorPersonnelId followed to ' + supervisor['personnelId'] + '.'
        elif tid in ('B01', 'V02'):
            ans = select(d.officer(m), 'personnelId', 'name', *(['rank'] if tid == 'B01' else []))
            basis += 'commandingOfficerId via crew mapping 1.3, then Personnel record.'
        elif tid in ('B02', 'B03', 'B04', 'B09', 'E03'):
            ids = d.people_ids([m], commander=tid != 'B02')
            if tid == 'B02':
                ans = {'crew': people_rows(ids, 'department')}
            elif tid == 'B03':
                ranks = {'LIEUTENANT', 'LIEUTENANT_COMMANDER', 'COMMANDER', 'CAPTAIN'}
                ans = {'personnelIds': [pid for pid in ids if d.people[pid]['rank'] in ranks]}
            elif tid == 'B04':
                ans = {'people': people_rows(ids, 'dutyStatus')}
            elif tid == 'B09':
                ans = {'people': people_rows(ids, 'rank'), 'assets': asset_rows(d.asset_ids(m), 'status')}
            else:
                ans = {'departments': groups((d.people[pid]['department'] for pid in ids), 'department')}
            basis += 'specified crew roles, mapping 1.3, distinct Personnel IDs, then requested fields; assets joined through asset mapping where requested.'
        elif tid in ('B05', 'B06', 'B07', 'B08'):
            ids = d.asset_ids(m)
            if tid == 'B06':
                ids = [aid for aid in ids if d.assets[aid]['status'] != 'ACTIVE']
            if tid == 'B08':
                ans = {'commandingOfficerName': d.officer(m)['name'],
                       'assetNames': sorted(d.assets[aid]['name'] for aid in ids)}
            else:
                field = {'B05': 'name', 'B06': 'status', 'B07': 'parentAssetId'}[tid]
                ans = {'assets': asset_rows(ids, field)}
            basis += 'assigned asset references through mapping 1.3 to Assets 1.1; commander through crew mapping where requested.'
        elif tid == 'C01':
            ans = {'people': [{'crewReference': r, 'personnelId': d.crew_map('1.1').get(r)} for r in sorted(staff(m))]}
            basis += 'distinct staff references looked up only in crew mapping 1.1.'
        elif tid == 'C02':
            ans = {'answerStatus': 'CANNOT_BE_DETERMINED', 'personnelId': None}
            basis += 'mapping 1.0 exists but contains no crew section, so it supplies no Personnel identifier.'
        elif tid == 'C03':
            ans = {'answerStatus': 'CANNOT_BE_DETERMINED', 'assetIds': []}
            basis += 'the sealed package contains mapping releases 1.0–1.3, with no release 1.4.'
        elif tid == 'C04':
            ans = {'references': [{'reference': r, 'assetId': am.get(r), 'outcome': d.asset_outcome(r)} for r in sorted(m['assignedAssetIds'])]}
            basis += 'test mapping membership first, then target existence in Assets 1.1.'
        elif tid == 'C05':
            ans = {'crewReferences': sorted(staff(m) - cm.keys())}
            basis += 'staff references absent from crew mapping 1.3.'
        elif tid == 'C12':
            counts = Counter(d.asset_outcome(r) for r in m['assignedAssetIds'])
            ans = {outcome.lower(): counts[outcome] for outcome in ('RESOLVED', 'UNRESOLVED', 'UNMAPPED')}
            basis += 'count each assigned reference by mapping membership and target existence.'
        add(tid, ans, basis)
    keys['C02']['variants'].append({'answer': {'answerStatus': 'ANSWERED', 'personnelId': None},
                                   'reason': 'The existing release can also be answered as an empty mapping result; the task explicitly allows either status when nobody is named.'})

    add('A05', {'assetIds': d.descendants('AST-0029')}, 'Assets 1.1 records whose parentAssetId is AST-0029; direct children only.')
    add('A06', {'phasers': [select(a, 'assetId', 'status') for a in all_a if a['kind'] == 'PHASER']}, 'All Assets 1.1 records with kind PHASER.')
    add('A09', {'people': [select(p, 'personnelId', 'name') for p in all_p if p['dutyStatus'] == 'DECEASED']}, 'All ten Personnel pages; dutyStatus DECEASED.')
    add('B10', {'missionIds': [m['missionId'] for m in all_m if d.officer_id(m) == 'PRS-0001']}, 'All missions; commandingOfficerId maps to PRS-0001 in release 1.3.')
    add('B11', {'missions': [{'missionId': m['missionId'], 'commandingOfficerPersonnelId': d.officer_id(m)} for m in ms(type='MEDICAL')]}, 'MEDICAL missions; crew mapping 1.3 lookup, null for absent officer or entry.')
    add('B12', {'missionIds': [m['missionId'] for m in all_m if 'AST-0025' in d.asset_ids(m)]}, 'All missions; an assigned asset reference maps to AST-0025 in release 1.3.')
    add('B13', {'missionIds': [m['missionId'] for m in ms(type='MAINTENANCE') if any(d.assets[a]['status'] == 'MISSING' for a in d.asset_ids(m))]}, 'MAINTENANCE missions with a mapped, held asset of status MISSING.')
    add('B14', {'missions': [{'missionId': m['missionId'], 'assetCount': len(d.asset_ids(m))} for m in ms(issuingAuthority='STARFLEET_MEDICAL')]}, 'STARFLEET_MEDICAL missions; count distinct held asset targets of mapping 1.3 per mission.')
    add('B15', {'missions': [{'missionId': m['missionId'], 'commandingOfficerRank': d.officer(m).get('rank'), 'assetCount': len(d.asset_ids(m))} for m in ms(status='FAILED')]}, 'FAILED missions; commander rank through mapping 1.3 and Personnel, distinct held asset targets per mission.')
    add('C06', {'release11PersonnelId': d.crew_map('1.1').get('C-1638'), 'release13PersonnelId': cm.get('C-1638')}, 'C-1638 looked up independently in crew mappings 1.1 and 1.3.')
    add('C07', {'releases': sorted(v for v, sections in d.mappings.items() if 'crew' in sections)}, 'Presence of crew.json in each packaged mapping release manifest.')
    add('C08', {'missionIds': [m['missionId'] for m in ms(issuingAuthority='ENTERPRISE_COMMAND') if any(r not in am for r in m['assignedAssetIds'])]}, 'ENTERPRISE_COMMAND missions with any asset reference absent from mapping 1.3.')
    add('C09', {'missionIds': [m['missionId'] for m in ms(classification='SECRET') if staff(m) - cm.keys()]}, 'Exactly SECRET missions; any staff reference absent from crew mapping 1.3.')
    add('C10', {'missionIds': [m['missionId'] for m in ms(type='MAINTENANCE') if any(d.asset_outcome(r) == 'UNRESOLVED' for r in m['assignedAssetIds'])]}, 'MAINTENANCE missions with a mapped asset target absent from Assets 1.1.')
    add('C11', {'missionIds': [m['missionId'] for m in ms(type='DIPLOMATIC') if staff(m) and all(d.crew_map('1.1').get(r) in d.people for r in staff(m))]}, 'Nonempty staff of DIPLOMATIC missions; every reference resolves via release 1.1 to Personnel.')

    mission_filters = {
        'G01': lambda m: m['status'] == 'COMPLETED',
        'G02': lambda m: m['priority'] in (4, 5),
        'G06': lambda m: not m.get('commandingOfficerId'),
        'G07': lambda m: m['durationHours'] >= 200,
        'G10': lambda m: m.get('actualCostCredits') is not None and m.get('estimatedCostCredits') is not None and Decimal(m['actualCostCredits']) > Decimal(m['estimatedCostCredits']),
    }
    for tid, predicate in mission_filters.items():
        add(tid, {'missionIds': [m['missionId'] for m in all_m if predicate(m)]}, 'All 300 Missions release 1.2 records, filtered by the task predicate; monetary comparison uses Decimal and excludes missing values.')
    for tid, department in [('G03', 'SECURITY'), ('G04', 'ENGINEERING'), ('V03', 'FLIGHT_OPERATIONS')]:
        add(tid, {'personnelIds': [p['personnelId'] for p in all_p if p['department'] == department]}, 'All ten Personnel pages; exact department ' + department + '.')
    add('G05', {'assets': asset_rows(d.assets, 'status')}, 'All Assets 1.1 records, retaining recorded statuses.')
    add('G08', {'personnelIds': [p['personnelId'] for p in all_p if p['civilian']]}, 'All ten Personnel pages; presence of civilianDetails, including an empty element.')
    add('G09', {'personnelIds': [p['personnelId'] for p in all_p if p['positionTitle'] == 'Section Supervisor']}, 'All ten Personnel pages; exact positionTitle Section Supervisor.')

    add('E01', {'statuses': groups((d.assets[a]['status'] for a in d.descendants('AST-0029')), 'status')}, 'Direct children of AST-0029 in Assets 1.1, grouped by status.')
    chosen = ms(commandingOfficerId='C-92')
    add('E02', {'totalEstimatedCost': total(chosen, 'estimatedCostCredits'), 'missionCount': len(chosen)}, 'All missions commanded by C-92; Decimal sum of present estimates; mission count includes missing estimates.')
    ids = sorted({a for m in ms(type='TACTICAL') for a in d.asset_ids(m)})
    add('E04', {'assetCount': len(ids), 'assetIds': ids}, 'TACTICAL missions; union of distinct held asset targets through mapping 1.3.')
    add('E05', {'distinctPeople': len(d.people_ids(ms(commandingOfficerId='C-99')))}, 'Missions commanded by C-99; union of staff Personnel IDs resolved through mapping 1.3.')
    add('E06', {'statuses': groups((m['status'] for m in ms(issuingAuthority='STARFLEET_SCIENCE')), 'status')}, 'STARFLEET_SCIENCE missions grouped by recorded status.')
    add('E07', {'ranks': groups((p['rank'] for p in all_p if p['department'] == 'SCIENCE'), 'rank')}, 'All Personnel pages; SCIENCE department grouped by recorded rank.')
    ids = d.people_ids(ms(classification='SECRET'))
    counts = Counter(d.people[p]['department'] for p in ids)
    top_answers('E08', counts, 'topDepartment', {'distinctPeople': len(ids)}, 'Exactly SECRET missions; distinct resolved staff Personnel IDs, counted by department.')
    command_m = ms(issuingAuthority='STARFLEET_COMMAND')
    add('E09', {'missionCount': sum(nonactive_assets(m) for m in command_m)}, 'STARFLEET_COMMAND missions; count once if any held mapped asset has non-ACTIVE status.')
    commanders = {d.officer_id(m) for m in command_m} & d.people.keys()
    counts = Counter(d.people[p]['rank'] for p in commanders)
    top_answers('E10', counts, 'rank', {'officerCount': max(counts.values())}, 'Distinct resolved commanders of STARFLEET_COMMAND missions; count officers per rank.')
    chosen = ms(status='COMPLETED', issuingAuthority='ENTERPRISE_COMMAND')
    add('E11', {'totalActualCost': total(chosen, 'actualCostCredits'), 'missionCount': len(chosen)}, 'COMPLETED ENTERPRISE_COMMAND missions; Decimal sum of present actual costs; count all selected missions.')
    add('E12', {'authorities': [{'issuingAuthority': authority, 'missionCount': len(ms(issuingAuthority=authority)), 'totalEstimatedCost': total(ms(issuingAuthority=authority), 'estimatedCostCredits')} for authority in sorted({m['issuingAuthority'] for m in all_m})]}, 'All missions grouped by issuingAuthority; Decimal sums with absent estimates contributing zero.')
    add('E13', {'departments': groups((p['department'] or 'CIVILIAN' for p in all_p), 'department')}, 'All 1,000 Personnel records; crew department, or CIVILIAN for civilian details.')
    commanders = {d.officer_id(m) for m in all_m} & d.people.keys()
    counts = Counter(d.people[p]['rank'] for p in commanders)
    top_answers('E14', counts, 'mostCommonRank', {'distinctCommanders': len(commanders)}, 'Distinct resolved commanding-officer Personnel IDs across all missions, grouped by rank.')
    add('E15', {'assets': groups((a for m in all_m for a in d.asset_ids(m)), 'assetId', 'missionCount')}, 'Mapping 1.3 to held assets; each mission contributes once per distinct asset target.')
    affected = [m['missionId'] for m in all_m if any(d.people[p]['dutyStatus'] != 'ACTIVE' for p in d.people_ids([m]))]
    add('E16', {'missionCount': len(affected), 'missionIds': affected}, 'All missions; any resolved staff member with non-ACTIVE Personnel duty status, one count per mission.')
    ids = d.people_ids(all_m)
    add('V05', {'distinctPeople': len(ids), 'ranks': groups((d.people[p]['rank'] or 'CIVILIAN' for p in ids), 'rank')}, 'Union of resolved staff Personnel IDs across all missions, grouped by rank; civilians grouped as CIVILIAN.')
    add('V06', {'types': groups((m['type'] for m in all_m if nonactive_assets(m)), 'type', 'missionCount')}, 'Count each mission with any mapped, held non-ACTIVE asset once, grouped by type; only qualifying types occur.')
    chosen = ms(type='TRANSPORT')
    add('V07', {'missionCount': len(chosen), 'totalEstimatedCost': total(chosen, 'estimatedCostCredits')}, 'TRANSPORT missions; count all and sum present estimated costs as Decimal.')
    chosen = ms(issuingAuthority='STARFLEET_SECURITY')
    add('V08', {'staffPlaces': sum(len(staff(m)) for m in chosen), 'distinctPeople': len(d.people_ids(chosen))}, 'STARFLEET_SECURITY missions; sum distinct local staff references per mission, and separately union resolved Personnel IDs.')

    # Simulate unavailable services: do not use their records to fill an answer.
    outage_ids = sorted(tid for tid, t in d.tasks.items() if 'stoppedService' in t)
    for tid in outage_ids:
        t = d.tasks[tid]
        stopped = t['stoppedService']
        needed = stopped in t['systems']
        ans = {'unavailableServices': [stopped] if needed else [], 'complete': not needed}
        basis = 'Stopped service: ' + stopped + '. '
        if tid in ('D01', 'D02', 'D05', 'D06', 'D10', 'D11'):
            for field in t['schema']['required']:
                if field not in ('answerStatus', 'unavailableServices', 'complete'):
                    types = t['schema']['properties'][field]['type']
                    ans[field] = [] if 'array' in types else None
            basis += 'No requested result can be established without that service; unavailable values are null or empty, with complete false.'
        elif tid in ('D03', 'D14'):
            if tid == 'D03':
                p = d.people['PRS-1058']
                ans.update(select(p, 'rank', 'department'))
                ans['supervisorId'] = p['supervisorPersonnelId']
                basis += 'PRS-1058 Personnel fields; Missions is not needed.'
            else:
                ans['members'] = [select(p, 'personnelId', 'rank') for p in all_p if p['department'] == 'MEDICAL']
                basis += 'All Personnel pages, MEDICAL department; Missions is not needed.'
        elif tid in ('D04', 'V04'):
            mid = 'ST-00000LD5M' if tid == 'D04' else 'ST-00000LDAH'
            m = d.missions[mid]
            ans['status'] = m['status']
            if tid == 'D04':
                ans['title'] = m['title']
            ans['assets'] = [{'assetId': aid, 'status': None} for aid in d.asset_ids(m, held=False)]
            basis += mid + '; mission fields and mapping 1.3 target IDs remain available, including targets whose existence cannot be checked; asset statuses are unknown.'
        elif tid == 'D07':
            ans['missions'] = [{'missionId': m['missionId'], 'status': m['status'], 'assetNames': []} for m in ms(type='DIPLOMATIC')]
            basis += 'All DIPLOMATIC mission IDs and statuses are available; no asset names can be established.'
        elif tid == 'D08':
            ans.update(select(d.officer(d.missions['ST-00000LD5N']), 'name', 'rank'))
            basis += 'ST-00000LD5N commander via mapping 1.3 to Personnel; Assets is not needed.'
        elif tid == 'D09':
            m = d.missions['ST-00000LD4X']
            ids = sorted({cm[r] for r in staff(m) if r in cm})
            ans['people'] = [{'personnelId': pid, 'name': None, 'rank': None} for pid in ids]
            basis += 'ST-00000LD4X staff references via mapping 1.3; mapped IDs remain available, names and ranks do not.'
        elif tid == 'D12':
            ans['missions'] = [{'missionId': m['missionId'], 'commandingOfficerPersonnelId': d.officer_id(m), 'rank': None} for m in ms(status='ACTIVE')]
            basis += 'ACTIVE mission records and mapping 1.3 provide officer IDs; Personnel ranks are unavailable.'
        elif tid == 'D13':
            ans['assets'] = asset_rows(d.asset_ids(d.missions['ST-00000LD5J']), 'status')
            basis += 'ST-00000LD5J assigned references via mapping 1.3 to Assets 1.1; Personnel is not needed.'
        else:
            raise ValueError('Unhandled outage: ' + tid)
        add(tid, ans, basis)

    # Canonical outage keys retain all available identifiers. The schema and
    # explicit notes allow partial identifier lists; enumerate those alternatives.
    for tid, field in (('D04', 'assets'), ('D09', 'people'), ('V04', 'assets')):
        answer = keys[tid]['answer']
        rows = answer[field]
        for size in range(len(rows)):
            for subset in combinations(rows, size):
                keys[tid]['variants'].append({
                    'answer': {**answer, field: list(subset)},
                    'reason': 'The outage schema permits a partial answer; this reports a subset of the identifiers available through the mapping, without inventing unavailable attributes.'})

    # Each ambiguity interpretation is derived separately from its closed definition.
    for tid in sorted(tid for tid, t in d.tasks.items() if t['set'] == 'ambiguity'):
        t = d.tasks[tid]
        interpretations = {}
        for reading in t['acceptedInterpretations']:
            definition = {field: next(iter(rule.values())) for field, rule in reading['definition'].items()}
            ans = {'answerStatus': 'ANSWERED', 'interpretation': definition}
            if tid == 'F01':
                m = d.missions['ST-00000LD8Q']
                refs = set()
                if 'ASSIGNED_CREW' in definition['countedGroups']:
                    refs.update(m['assignedCrewIds'])
                if 'COMMANDING_OFFICER' in definition['countedGroups'] and m.get('commandingOfficerId'):
                    refs.add(m['commandingOfficerId'])
                if 'PARTICIPANTS' in definition['countedGroups']:
                    refs.update(m['participantIds'])
                ans['peopleCount'] = len(refs)
            elif tid == 'F02':
                field = 'estimatedCostCredits' if definition['costBasis'] == 'ESTIMATED' else 'actualCostCredits'
                ans['cost'] = float(Decimal(d.missions['ST-00000LD6Q'][field]))
            elif tid == 'F03':
                ans['assetIds'] = d.descendants('AST-0029', definition['scope'] == 'AT_ANY_LEVEL')
            elif tid == 'F04':
                aboard = set(d.descendants('AST-0029', True))
                ans['assetIds'] = [a['assetId'] for a in all_a if a['kind'] == 'SHUTTLE' and a['status'] in definition['statusesCounted'] and (not definition['onlyAboardTheEnterprise'] or a['assetId'] in aboard)]
            elif tid == 'F05':
                ids = d.people_ids([d.missions['ST-00000LDCS']], commander=definition['includesCommandingOfficer'])
                ans['personnelIds'] = [pid for pid in ids if d.people[pid]['rank'] in definition['officerRanks']]
            elif tid == 'F06':
                candidates = [m for m in all_m
                              if (not definition['completedOnly'] or m['status'] == 'COMPLETED')
                              and (('COMMANDING_OFFICER' in definition['roles'] and m.get('commandingOfficerId') == 'C-554')
                                   or ('ASSIGNED_CREW' in definition['roles'] and 'C-554' in m['assignedCrewIds']))]
                latest = max(Decimal(m['stardate']) for m in candidates)
                winners = [m['missionId'] for m in candidates if Decimal(m['stardate']) == latest]
                if len(winners) != 1:
                    raise ValueError('Ambiguous latest mission requires explicit tie handling')
                ans['missionId'] = winners[0]
            interpretations[reading['name']] = {'answer': ans}
        first = t['acceptedInterpretations'][0]['name']
        other_readings = [{'answer': interpretations[r['name']]['answer'],
                           'reason': 'Equally accepted reading: ' + r['name'] + '; its exact definition is recorded in interpretation.'}
                          for r in t['acceptedInterpretations'][1:]]
        bases = {
            'F01': 'ST-00000LD8Q; union of local person references in exactly the groups in each interpretation.',
            'F02': 'ST-00000LD6Q; estimatedCostCredits or actualCostCredits according to costBasis.',
            'F03': 'Assets 1.1 parentAssetId links below AST-0029; direct children or transitive descendants.',
            'F04': 'Assets 1.1 SHUTTLE records; accepted status set and, when required, ancestry below AST-0029.',
            'F05': 'ST-00000LDCS; assigned crew, optionally commander, mapped through release 1.3 and filtered by accepted Personnel ranks.',
            'F06': 'All Missions release 1.2 records with C-554 in accepted roles and statuses; maximum Decimal stardate, uniquely attained in each reading.'}
        add(tid, interpretations[first]['answer'], bases[tid], other_readings, interpretations)

    assume(outage_ids, 'Treat stoppedService as unavailable at answer time despite its snapshot being packaged. ANSWERED reports the available portion, including an empty portion, rather than claiming the enterprise holds no answer. Set complete false and list only a needed stopped service; otherwise answer fully with no unavailable service. Mapping releases remain available independently, but cannot reveal a mission reference when Missions is stopped.')
    assume(['D04', 'D09', 'V04'], 'The primary outage answer retains every identifier established by the available mission and mapping; unavailable attributes are null. Partial identifier subsets are genuine variants under the outage allowance (explicitly reinforced by the D04 and D09 notes). Null versus empty collections, omitted optional null fields, list permutations and unscored prose are treated as representation choices rather than additional semantic variants.')
    assume(['C02'], 'Use CANNOT_BE_DETERMINED for the primary answer because release 1.0 has no crew mapping. Also include ANSWERED with a null identifier because the existing release yields an empty lookup and the task explicitly accepts either status.')
    assume(['C03'], 'The package is the complete release universe for this task: release 1.4 does not exist here. Return CANNOT_BE_DETERMINED with an empty identifier list; do not substitute a different release.')
    assume(['F01'], 'Count distinct Missions-local references in the groups specified by each accepted interpretation. No mapping release is requested. For this mission the commander, assigned crew and participant references are disjoint, so counting group entries gives the same result.')
    assume(['F03', 'F04'], 'Identify the USS Enterprise as AST-0029 from its Assets record. For the aboard-only shuttle interpretation, include descendants at any level; all qualifying shuttles are direct children, so a direct-only reading gives the same answer.')
    assume(['V08'], 'Staff places count distinct local crew references once per mission, including unmapped references. Distinct roster people instead count the union of Personnel IDs actually resolved by release 1.3. This follows the question applying the mapping qualification to roster people rather than staff places.')
    assume(['V06'], 'Read types that occur as types occurring among the qualifying missions, so the primary answer omits zero-count groups. The wording can also mean every type occurring anywhere in the mission dataset; include that reading as a variant with explicit zero counts.')
    positive_counts = {row['type']: row['missionCount'] for row in keys['V06']['answer']['types']}
    keys['V06']['variants'].append({
        'answer': {'answerStatus': 'ANSWERED', 'types': [
            {'type': kind, 'missionCount': positive_counts.get(kind, 0)}
            for kind in sorted({m['type'] for m in all_m})]},
        'reason': 'For each mission type and types that occur can refer to the types present in the full Missions dataset, including those with zero qualifying missions, rather than just the types present after filtering.'})

    if set(keys) != set(d.tasks) or len(keys) != 90:
        raise ValueError('Key coverage mismatch: ' + repr(set(d.tasks) ^ set(keys)))
    return {'about': 'The second independent derivation of the corpus 2 answer keys.',
            'derivation': 'B', 'packageSha256': manifest['packageSha256'],
            'labCommit': manifest['labCommit'], 'inputs': inputs, 'keys': keys,
            'assumptions': assumptions, 'gaps': []}


def encode(document):
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='write the derived keys')
    args = parser.parse_args(argv)
    result = encode(derive())
    if args.write:
        OUTPUT.write_bytes(result)
        print('Wrote 90 independently derived keys to ' + str(OUTPUT))
    elif not OUTPUT.exists() or OUTPUT.read_bytes() != result:
        print('Derived keys differ from ' + str(OUTPUT), file=sys.stderr)
        return 1
    else:
        print('No difference: all 90 derived keys match byte for byte.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
