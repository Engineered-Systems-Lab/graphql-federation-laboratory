"""Offline dataset-003 proposal generator; never registers or publishes a dataset."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import xml.etree.ElementTree as ET

VERSION = 'crew-v1-large-003'
GENERATOR = 'crew-personnel-003-v1'
ALGORITHM = 'sha256-name-order-v1'
SEED = 'enterprise-d-2366-003-v1'
TOOLCHAIN = {'implementation': 'CPython', 'version': '3.12.14', 'dependencies': 'stdlib-only'}
NS = 'urn:graphql-federation-lab:crew-personnel:v1'
FIELDS = ('crewId', 'displayName', 'rank', 'department', 'positionTitle', 'dutyStatus', 'supervisorCrewId')
RANKS = 'CAPTAIN COMMANDER LIEUTENANT_COMMANDER LIEUTENANT ENSIGN CHIEF_PETTY_OFFICER CREWMAN CIVILIAN'.split()
DEPARTMENTS = 'COMMAND OPERATIONS ENGINEERING SCIENCE MEDICAL SECURITY FLIGHT_OPERATIONS'.split()
MATRIX = [[1, 1, 2, 6, 4, 2, 4, 0], [0, 0, 1, 18, 30, 20, 75, 6],
          [0, 0, 3, 35, 45, 25, 112, 0], [0, 0, 3, 30, 35, 8, 58, 6],
          [0, 1, 3, 16, 15, 8, 43, 4], [0, 0, 0, 12, 20, 12, 76, 0],
          [0, 0, 1, 12, 11, 5, 27, 4]]
GIVEN = 'Aven Bela Cora Daro Evin Fara Galen Hara Iven Jora Kalen Lira Miro Nara Orin Pera Quin Rena Soren Tavi Ulan Vela Wren Xara Yori Zena Arlo Brin Ceri Deni Esra Fenn'.split()
FAMILY = 'Arden Bex Corin Dalen Eren Falin Goran Halen Irix Jalen Korr Laren Merin Noran Orel Perrin Quell Ralin Sarek Toren Urell Varen Wex Xorin Yaren Zorin Aster Bren Cadan Doran Elrin Faren'.split()
TITLES = dict(zip(RANKS[2:], ['Senior Specialist', 'Department Officer', 'Junior Officer',
                            'Technical Chief', 'Department Technician', 'Civilian Specialist']))
SEED_ROWS = [
    (1047, 'Jean-Luc Picard', 'CAPTAIN', 'COMMAND', 'Commanding Officer', 'ACTIVE', None),
    (1048, 'William Riker', 'COMMANDER', 'COMMAND', 'First Officer', 'ACTIVE', 1047),
    (1049, 'Geordi La Forge', 'LIEUTENANT_COMMANDER', 'ENGINEERING', 'Chief Engineer', 'ACTIVE', 1048),
    (1050, 'Data', 'LIEUTENANT_COMMANDER', 'SCIENCE', 'Science Department Lead', 'ACTIVE', 1048),
    (1051, 'Mara Venn', 'LIEUTENANT', 'FLIGHT_OPERATIONS', 'Shuttle Pilot', 'ON_LEAVE', 1048),
    (1052, 'Elias Renn', 'ENSIGN', 'ENGINEERING', 'Engineering Technician', 'INACTIVE', 1049),
    (1053, 'Beverly Crusher', 'COMMANDER', 'MEDICAL', 'Chief Medical Officer', 'ACTIVE', 1047),
    (1054, 'Deanna Troi', 'LIEUTENANT_COMMANDER', 'MEDICAL', "Ship's Counselor", 'ACTIVE', 1047),
    (1055, 'Wesley Crusher', 'ENSIGN', 'OPERATIONS', 'Acting Ensign', 'ACTIVE', 1050),
    (1056, 'Guinan', 'CIVILIAN', 'OPERATIONS', 'Bartender', 'ACTIVE', None),
    (1057, 'Reginald Barclay', 'LIEUTENANT', 'ENGINEERING', 'Systems Diagnostic Engineer', 'ACTIVE', 1049),
    (1058, 'Worf', 'LIEUTENANT', 'SECURITY', 'Chief of Security', 'ACTIVE', 1048),
    (1100, "Miles O'Brien", 'CHIEF_PETTY_OFFICER', 'OPERATIONS', 'Transporter Chief', 'ACTIVE', 1048),
    (1101, 'Sonya Gomez', 'ENSIGN', 'ENGINEERING', 'Engineering Officer', 'ACTIVE', 1049),
]
LEADS = dict(zip(DEPARTMENTS[:-1], ['CRW-1048', 'CRW-1100', 'CRW-1049', 'CRW-1050', 'CRW-1053', 'CRW-1058']))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_source(data):
    data = data.replace(b'\r\n', b'\n')
    require(not data.startswith(b'\xef\xbb\xbf') and b'\r' not in data, 'source BOM or bare CR')
    data.decode('utf-8')
    return data


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                       separators=(',', ': '), allow_nan=False) + '\n').encode('ascii')


def seed_records():
    result = []
    for row in SEED_ROWS:
        values = list(row)
        values[0] = f'CRW-{row[0]:04d}'
        if row[-1] is not None:
            values[-1] = f'CRW-{row[-1]:04d}'
        result.append({key: value for key, value in zip(FIELDS, values) if value is not None})
    return result


def name_candidates():
    ordered = sorted(range(1024), key=lambda k: (hashlib.sha256(
        f'{SEED}|name|{k}'.encode('utf-8')).digest(), k))
    used = {r['displayName'] for r in seed_records()}
    result = []
    for k in ordered:
        name = GIVEN[k // 32] + ' ' + FAMILY[k % 32]
        if name not in used:
            result.append((k, name))
            used.add(name)
    require(len(result) >= 786, 'insufficient distinct names')
    return result[:786]


def records_and_ledger():
    records = seed_records()
    counts = Counter((r['department'], r['rank']) for r in records)
    names = name_candidates()
    generated = []
    ledger = [dict(crewId=r['crewId'], displayName=r['displayName'], slot=None, nameCandidate=None)
              for r in records]
    for department, row in zip(DEPARTMENTS, MATRIX):
        for rank, count in zip(RANKS, row):
            residual = count - counts[department, rank]
            require(residual >= 0, 'negative residual')
            for _ in range(residual):
                j = len(generated)
                k, name = names[j]
                record = dict(crewId=f'CRW-{2000 + j:04d}', displayName=name, rank=rank,
                              department=department, positionTitle=TITLES[rank],
                              dutyStatus='INACTIVE' if j % 20 == 0 else 'ON_LEAVE' if j % 10 == 0 else 'ACTIVE')
                generated.append(record)
                ledger.append(dict(crewId=record['crewId'], displayName=name, slot=j, nameCandidate=k))
    require(len(generated) == 786, 'background count')
    for department in DEPARTMENTS:
        local = [r for r in generated if r['department'] == department]
        excluded = set()
        if department == 'FLIGHT_OPERATIONS':
            lead = next(r for r in local if r['rank'] == 'LIEUTENANT_COMMANDER')
            lead.update(positionTitle='Flight Operations Lead', dutyStatus='ACTIVE', supervisorCrewId='CRW-1048')
            lead_id = lead['crewId']
            excluded.add(lead_id)
        else:
            lead_id = LEADS[department]
        section = next(r for r in local if r['rank'] == 'LIEUTENANT')
        section.update(positionTitle='Section Supervisor', dutyStatus='ACTIVE', supervisorCrewId=lead_id)
        excluded.add(section['crewId'])
        others = sorted((r for r in local if r['crewId'] not in excluded), key=lambda r: r['crewId'])
        for t, record in enumerate(others):
            record['supervisorCrewId'] = lead_id if t % 10 == 0 else section['crewId']
    records += generated
    records.sort(key=lambda r: r['crewId'])
    validate_records(records)
    return records, ledger


def validate_records(records):
    require(len(records) == 800, 'personnel count')
    ids = [r.get('crewId') for r in records]
    require(len(set(ids)) == 800 and ids == sorted(ids), 'duplicate or unordered IDs')
    require(len({r.get('displayName') for r in records}) == 800, 'duplicate names')
    by_id = {r['crewId']: r for r in records}
    counts = Counter((r.get('department'), r.get('rank')) for r in records)
    require(counts == Counter({(d, rank): n for d, row in zip(DEPARTMENTS, MATRIX)
                              for rank, n in zip(RANKS, row) if n}), 'distribution')
    for r in records:
        require(set(FIELDS[:-1]) <= set(r) <= set(FIELDS), 'record fields')
        require(re.fullmatch(r'CRW-[0-9]{4}', r['crewId']) is not None and r['crewId'] != 'CRW-0000', 'ID syntax')
        require(r['dutyStatus'] in ('ACTIVE', 'ON_LEAVE', 'INACTIVE'), 'status')
        for field in ('displayName', 'positionTitle'):
            require(isinstance(r[field], str) and 1 <= len(r[field]) <= 100 and r[field].strip(' \t\r\n'), 'bounded text')
        seen = set()
        current = r['crewId']
        while current is not None:
            require(current in by_id, 'dangling supervisor')
            require(current not in seen, 'supervisor cycle')
            seen.add(current)
            current = by_id[current].get('supervisorCrewId')
    require([r['crewId'] for r in records if 'supervisorCrewId' not in r] == ['CRW-1047', 'CRW-1056'], 'roots')
    for seed in seed_records():
        require(by_id.get(seed['crewId']) == seed, 'named seed changed')


def xml_bytes(records, page):
    def element(field, value, indent=2):
        text = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return ' ' * indent + f'<cp:{field}>{text}</cp:{field}>'
    lines = ["<?xml version='1.0' encoding='utf-8'?>",
             f'<cp:ListCrewMembersResponse xmlns:cp="{NS}">', element('datasetVersion', VERSION)]
    for record in records[page * 100:(page + 1) * 100]:
        lines.append('  <cp:crewMember>')
        lines.extend(element(field, record[field], 4) for field in FIELDS if field in record)
        lines.append('  </cp:crewMember>')
    lines += [element('totalCount', 800), element('offset', page * 100), element('limit', 100),
              element('hasMore', 'true' if page < 7 else 'false'), '</cp:ListCrewMembersResponse>']
    return ('\n'.join(lines) + '\n').encode('utf-8')


def recipe(ledger):
    return dict(seed=SEED, referenceClock='2366-01-01T00:00:00Z', departments=DEPARTMENTS,
                ranks=RANKS, distribution=MATRIX, givenNames=GIVEN, familyNames=FAMILY,
                roster=seed_records(), identityLedger=ledger, positionTitles=TITLES,
                departmentLeads=LEADS,
                allocation=dict(backgroundStart=2000, backgroundCount=786, namedReservation=[1100, 1199],
                                order='department-rank-within-cell'),
                names=dict(candidateCount=1024, familyRadix=32, hashInput='seed|name|decimal(k)',
                           order='unsigned-sha256-bytes-then-k', deduplicate='exact-case-sensitive'),
                reporting=dict(flightLeadRank='LIEUTENANT_COMMANDER', flightLeadChoice='lowest-generated-ID',
                               flightLeadSupervisor='CRW-1048', flightLeadTitle='Flight Operations Lead',
                               sectionRank='LIEUTENANT', sectionChoice='lowest-generated-ID',
                               sectionTitle='Section Supervisor', directLeadModulo=10,
                               localOrder='crewId-excluding-generated-lead-and-section'),
                status=dict(inactiveModulo=20, onLeaveModulo=10, precedence=['lead-section-ACTIVE', 'INACTIVE', 'ON_LEAVE', 'ACTIVE']),
                serialization=dict(xml='dataset-003-xml-v1', json='dataset-003-json-v1', pageSize=100,
                                   recordOrder='ASCII-crewId', fieldOrder=list(FIELDS)))


def package_bytes():
    require(platform.python_implementation() == TOOLCHAIN['implementation'] and
            platform.python_version() == TOOLCHAIN['version'], 'requires CPython 3.12.14')
    records, ledger = records_and_ledger()
    pages = {f'page-{p:03d}.xml': xml_bytes(records, p) for p in range(8)}
    manifest = dict(formatVersion=1, datasetVersion=VERSION, count=800,
                    generator=dict(identity=GENERATOR, algorithm=ALGORITHM, toolchain=TOOLCHAIN,
                                   source=dict(path='generate_003.py', hashing='sha256-crlf-to-lf-v1',
                                               sha256=sha(canonical_source(Path(__file__).read_bytes())))),
                    recipe=recipe(ledger),
                    pages=[dict(filename=name, offset=p * 100, count=100, byteLength=len(data), sha256=sha(data))
                           for p, (name, data) in enumerate(pages.items())])
    return {**pages, 'manifest.json': json_bytes(manifest)}


def validate_package(directory):
    directory = Path(directory)
    expected = package_bytes()
    require({p.name for p in directory.iterdir()} == set(expected), 'missing or extra package files')
    records = []
    for p in range(8):
        path = directory / f'page-{p:03d}.xml'
        require(path.is_file() and not path.is_symlink(), 'nonregular page')
        raw = path.read_bytes()
        require(b'<!' not in raw, 'DTD/comments forbidden')
        root = ET.fromstring(raw)
        for member in root.findall(f'{{{NS}}}crewMember'):
            records.append({child.tag.removeprefix(f'{{{NS}}}'): child.text for child in member})
    validate_records(records)
    for name, data in expected.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'nonregular package file')
        require(path.read_bytes() == data, f'noncanonical or tampered {name}')
    return sha(expected['manifest.json'])


def generate(directory):
    directory = Path(directory)
    contents = package_bytes()
    # Never overwrite an earlier proposal or an immutable release.
    directory.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        (directory / name).write_bytes(data)
    return validate_package(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate', 'validate'])
    parser.add_argument('directory', type=Path, help='new output directory, or package to validate')
    args = parser.parse_args()
    try:
        digest = generate(args.directory) if args.command == 'generate' else validate_package(args.directory)
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    print(f'PASS {VERSION}: 800 personnel, 8 pages; package SHA-256 {digest}')


if __name__ == '__main__':
    main()
