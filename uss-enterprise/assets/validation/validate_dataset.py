"""Offline Assets dataset checks: records against the contract schema, the cross-record rules, the Missions cross-check,
the release manifest hashes and an exact regeneration of the release from its own curation file.

Standard library only. No service, database or Docker is involved or established.
"""
from collections import Counter
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys

COMPONENT = Path(__file__).resolve().parents[1]
REPOSITORY = COMPONENT.parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import jsonschema_subset as js

CONTRACT_10 = COMPONENT / 'contracts/assets-v1.0.openapi.json'
CONTRACT_11 = COMPONENT / 'contracts/assets-v1.1.openapi.json'
CONTRACT = CONTRACT_10  # the contract release 1.0 was made against; release 1.1 is checked against CONTRACT_11
RELEASES = COMPONENT / 'datasets/releases'
MISSIONS_RELEASE = REPOSITORY / 'uss-enterprise/missions/datasets/releases/1.0'
RELEASE_FILES = ['assets.json', 'curation.json', 'generate.py', 'manifest.json', 'provenance.json']
# The kind-to-category table, spelled once more here on purpose, as in validate.py.
KIND_CATEGORY = {'STARSHIP': 'VEHICLE', 'SHUTTLE': 'VEHICLE', 'ROVER': 'VEHICLE', 'ARMORED_VEHICLE': 'VEHICLE',
                 'PHASER': 'EQUIPMENT', 'TRICORDER': 'EQUIPMENT', 'COMMUNICATOR': 'EQUIPMENT',
                 'SCIENTIFIC_INSTRUMENT': 'EQUIPMENT', 'MUSICAL_INSTRUMENT': 'EQUIPMENT'}
ASSET_ID = re.compile(r'[A-Z]{2,5}-[1-9][0-9]*')
# The native grammar of contract 1.1, spelled once more here on purpose, as in validate.py.
ASSET_ID_11 = re.compile(r'[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})')
NATIVE_PREFIX = 'AST'
SOURCE_RELEASE = COMPONENT / 'datasets/releases/1.0'
MINIMUM_ASSETS = 30
MISSIONS_DISTINCT = 9
MISSIONS_REFERENCES = 68
CASES = {'NORMAL', 'DANGLING', 'DESTROYED', 'MISSING'}
CASES_11 = {'NORMAL', 'DESTROYED', 'MISSING', 'MAPPED_NOT_FOUND', 'UNMAPPED'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_bytes(path):
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


def sha(content):
    return hashlib.sha256(content).hexdigest()


def load(path):
    return json.loads(read_bytes(path).decode('utf-8'))


def id_key(asset_id):
    prefix, number = asset_id.split('-')
    return prefix, int(number)


def missions_references(directory=MISSIONS_RELEASE):
    """{assetId: sorted mission ids} and the number of references, read from the released Missions dataset."""
    found = {}
    total = 0
    for mission in load(Path(directory) / 'release.json')['missions']:
        for asset_id in mission['assignedAssetIds']:
            found.setdefault(asset_id, []).append(mission['missionId'])
            total += 1
    return {k: sorted(v) for k, v in found.items()}, total


def check_files_and_hashes(release, contract_path, missions_dir, revision='1.0', source_dir=None):
    release = Path(release)
    present = sorted(p.name for p in release.iterdir())
    require(present == RELEASE_FILES, 'Release files: ' + ', '.join(present))
    manifest = load(release / 'manifest.json')
    require(manifest['datasetVersion'] == release.name, 'Manifest version differs from the folder name')
    require(manifest['contractRevision'] == revision, 'Contract revision')
    for name, expected in manifest['files'].items():
        require(name in RELEASE_FILES and name != 'manifest.json', 'Unknown file in the manifest: ' + name)
        require(sha(read_bytes(release / name)) == expected, 'Content hash differs: ' + name)
    require(sorted(manifest['files']) == [n for n in RELEASE_FILES if n != 'manifest.json'], 'Manifest covers every file')
    require(manifest['contractSha256'] == sha(read_bytes(contract_path)), 'Contract hash')
    pinned = manifest['missionsRelease']
    require(pinned['releaseSha256'] == sha(read_bytes(Path(missions_dir) / 'release.json')), 'Missions release hash')
    require(pinned['manifestSha256'] == sha(read_bytes(Path(missions_dir) / 'manifest.json')), 'Missions manifest hash')
    if source_dir is not None:
        source = manifest['sourceRelease']
        require(source['datasetVersion'] == Path(source_dir).name, 'Source release version')
        require(source['assetsSha256'] == sha(read_bytes(Path(source_dir) / 'assets.json')), 'Source release assets hash')
        require(source['manifestSha256'] == sha(read_bytes(Path(source_dir) / 'manifest.json')), 'Source release manifest hash')
    return manifest


def check_records(assets_document, manifest, contract, grammar=None):
    require(set(assets_document) == {'assets', 'contractRevision', 'datasetVersion'}, 'Assets document members')
    items = assets_document['assets']
    schema = contract['components']['schemas']['Asset']
    for record in items:
        problems = js.errors(record, schema, contract)
        require(not problems, f'{record.get("assetId")}: ' + '; '.join(problems))
        require(record['category'] == KIND_CATEGORY[record['kind']], f'{record["assetId"]}: category differs from the kind table')
    ids = [r['assetId'] for r in items]
    require(len(ids) == len(set(ids)), 'Asset ids are unique')
    require(all((grammar or ASSET_ID).fullmatch(i) for i in ids), 'Asset id grammar')
    require(ids == sorted(ids, key=id_key), 'Assets are in id order (prefix as text, then number as a number)')
    require(len(items) >= MINIMUM_ASSETS, f'At least {MINIMUM_ASSETS} assets, found {len(items)}')
    kinds = {r['kind'] for r in items}
    require(kinds == set(KIND_CATEGORY), 'At least one asset of each of the nine kinds; missing: ' + ', '.join(sorted(set(KIND_CATEGORY) - kinds)))
    require(manifest['counts'] == {'assets': len(items), 'kinds': len(kinds)}, 'Manifest counts')
    by_id = {r['assetId']: r for r in items}
    for record in items:
        parent = record['parentAssetId']
        if parent is None:
            continue
        require(parent in by_id, f'{record["assetId"]}: parent {parent} does not exist')
        require(parent != record['assetId'], f'{record["assetId"]}: an asset is not its own parent')
        require(by_id[parent]['category'] == 'VEHICLE', f'{record["assetId"]}: parent {parent} is not a VEHICLE')
    for record in items:
        seen = set()
        current = record['assetId']
        while current is not None:
            require(current not in seen, f'{record["assetId"]}: the parent chain has a cycle')
            seen.add(current)
            current = by_id[current]['parentAssetId']
    return by_id


def check_missions_cross(provenance, by_id, missions_dir):
    references, total = missions_references(missions_dir)
    require(len(references) == MISSIONS_DISTINCT and total == MISSIONS_REFERENCES,
            f'Missions release references {len(references)} distinct assets in {total} references')
    require(provenance['missionsRelease'] == {'datasetVersion': '1.0', 'distinctAssets': len(references), 'references': total},
            'Provenance restates the Missions counts')
    expected = provenance['expectedReferences']
    require([e['assetId'] for e in expected] == sorted(references, key=id_key),
            'The expected outcomes cover exactly the Missions-referenced ids')
    cases = Counter()
    for entry in expected:
        asset_id = entry['assetId']
        held = asset_id in by_id
        cases[entry['case']] += 1
        require(entry['case'] in CASES, f'{asset_id}: case')
        require(entry['heldByAssets'] is held, f'{asset_id}: heldByAssets disagrees with the dataset')
        require(entry['resolution'] == ('RESOLVED' if held else 'UNRESOLVED'), f'{asset_id}: the expected resolution differs from the dataset')
        require(entry['status'] == (by_id[asset_id]['status'] if held else None), f'{asset_id}: the expected status differs from the dataset')
        require(entry['referenceCount'] == len(references[asset_id]) and entry['missionIds'] == references[asset_id],
                f'{asset_id}: the Missions references differ from the released Missions dataset')
        require(entry['assetsAnswers'] == ('200 with the record' if held else '404 ASSET_NOT_FOUND'), f'{asset_id}: what Assets answers')
        require(entry['consumerShows'] == ('RESOLVED with the asset' if held else 'UNRESOLVED with asset null, as data'),
                f'{asset_id}: what the consumer shows')
        if entry['case'] == 'DANGLING':
            require(not held, f'{asset_id}: a DANGLING reference must not be held')
        else:
            require(held, f'{asset_id}: case {entry["case"]} must be held')
        if entry['case'] in ('DESTROYED', 'MISSING'):
            require(entry['status'] == entry['case'], f'{asset_id}: status for case {entry["case"]}')
        if entry['case'] == 'NORMAL':
            require(entry['status'] not in ('DESTROYED', 'MISSING'), f'{asset_id}: a NORMAL case has a live status')
    require(1 <= cases['DANGLING'] <= 2, 'One or two Missions-referenced ids are left out on purpose')
    require(cases['DESTROYED'] >= 1 and cases['MISSING'] >= 1 and cases['NORMAL'] >= 1, 'A NORMAL, a DESTROYED and a MISSING case')
    unreferenced = [i for i in by_id if i not in references]
    require(unreferenced, 'At least one asset that no mission uses')
    for chain in provenance['parentChains']:
        require(len(chain) >= 3, 'A parent chain has a child and two levels above it')
        for child, parent in zip(chain, chain[1:]):
            require(by_id[child]['parentAssetId'] == parent, f'Parent chain: {child} is not aboard {parent}')
        require(by_id[chain[-1]]['parentAssetId'] is None, 'A parent chain ends at an asset with no parent')
    rule = provenance['consumerRule']
    require('404' in rule and 'UNRESOLVED' in rule and 'lookup failure' in rule, 'The consumer rule states that only a 404 maps to UNRESOLVED')
    for c in provenance['cases']:
        require(c['assetsAnswers'] and c['consumerShows'], 'Every case says what Assets answers and what the consumer shows: ' + c['case'])
    require({c['case'] for c in provenance['cases']} == CASES | {'UNREFERENCED', 'PARENT_CHAIN'}, 'Every controlled case is described')
    return len(unreferenced)


def check_missions_cross_11(provenance, by_id, missions_dir):
    """Release 1.1: the expected mapping from the Missions references to native ids, in its three layers."""
    references, total = missions_references(missions_dir)
    require(len(references) == MISSIONS_DISTINCT and total == MISSIONS_REFERENCES,
            f'Missions release references {len(references)} distinct assets in {total} references')
    require(provenance['missionsRelease'] == {'datasetVersion': '1.0', 'distinctReferences': len(references), 'references': total},
            'Provenance restates the Missions counts')
    assignment = provenance['idAssignment']
    pairs = assignment['pairs']
    require([p['to'] for p in pairs] == [f'{NATIVE_PREFIX}-{n:04d}' for n in range(1, len(pairs) + 1)],
            'Native ids are assigned in order, one step each')
    require([p['from'] for p in pairs] == sorted((p['from'] for p in pairs), key=id_key), 'The assignment follows the release 1.0 id order')
    require(sorted(p['to'] for p in pairs) == sorted(by_id), 'The assignment covers exactly the assets of the release')
    assigned = {p['from']: p['to'] for p in pairs}
    require(assignment['sourceRelease'] == {'datasetVersion': '1.0'}, 'Source release version')
    text = {c['case']: c for c in provenance['cases']}
    expected = provenance['expectedMapping']
    require([e['missionsReference'] for e in expected] == sorted(references, key=id_key),
            'The expected mapping covers exactly the Missions references')
    cases = Counter()
    for entry in expected:
        reference = entry['missionsReference']
        case = entry['case']
        cases[case] += 1
        require(case in CASES_11, f'{reference}: case')
        target = entry['mapsTo']
        if case == 'UNMAPPED':
            require(target is None and entry['mappingSays'] == 'no entry: the reference is not mapped',
                    f'{reference}: an unmapped reference has no target')
            require(entry['heldByAssets'] is False and entry['resolution'] == 'NO_MAPPING',
                    f'{reference}: an unmapped reference is a mapping failure')
        else:
            require(target is not None and ASSET_ID_11.fullmatch(target) and target.startswith(NATIVE_PREFIX + '-'),
                    f'{reference}: the mapping target is a native id')
            require(entry['mappingSays'] == 'maps to ' + target, f'{reference}: what the mapping says')
            require(entry['heldByAssets'] is (target in by_id), f'{reference}: heldByAssets disagrees with the dataset')
            if case == 'MAPPED_NOT_FOUND':
                require(target not in by_id and target not in assigned.values(), f'{reference}: a mapped-but-not-found target must not be held')
                require(entry['resolution'] == 'UNRESOLVED' and entry['status'] is None,
                        f'{reference}: expected resolution of a missing target')
            else:
                require(target in by_id, f'{reference}: case {case} must map to a held asset')
                require(reference in assigned and assigned[reference] == target, f'{reference}: the mapping target differs from the id assignment')
                require(entry['resolution'] == 'RESOLVED', f'{reference}: the expected resolution differs from the dataset')
                require(entry['status'] == by_id[target]['status'], f'{reference}: the expected status differs from the dataset')
        if case in ('DESTROYED', 'MISSING'):
            require(entry['status'] == case, f'{reference}: status for case {case}')
        if case == 'NORMAL':
            require(entry['status'] not in ('DESTROYED', 'MISSING'), f'{reference}: a NORMAL case has a live status')
        require(entry['referenceCount'] == len(references[reference]) and entry['missionIds'] == references[reference],
                f'{reference}: the Missions references differ from the released Missions dataset')
        require(entry['assetsAnswers'] == text[case]['assetsAnswers'] and entry['consumerShows'] == text[case]['consumerShows'],
                f'{reference}: what Assets answers and what the consumer shows differ from the case')
    require(cases['MAPPED_NOT_FOUND'] == 1 and cases['UNMAPPED'] == 1,
            'One mapped-but-not-found and one unmapped reference are left out on purpose')
    require(cases['DESTROYED'] >= 1 and cases['MISSING'] >= 1 and cases['NORMAL'] >= 1, 'A NORMAL, a DESTROYED and a MISSING case')
    require(text['MAPPED_NOT_FOUND']['assetsAnswers'] == '404 ASSET_NOT_FOUND', 'A mapped-but-not-found target answers 404 ASSET_NOT_FOUND')
    reached = {e['mapsTo'] for e in expected if e['heldByAssets']}
    unreferenced = [i for i in by_id if i not in reached]
    require(unreferenced, 'At least one asset that no mission reaches through the mapping')
    for chain in provenance['parentChains']:
        require(len(chain) >= 3, 'A parent chain has a child and two levels above it')
        for child, parent in zip(chain, chain[1:]):
            require(by_id[child]['parentAssetId'] == parent, f'Parent chain: {child} is not aboard {parent}')
        require(by_id[chain[-1]]['parentAssetId'] is None, 'A parent chain ends at an asset with no parent')
    rule = provenance['consumerRule']
    require('ASSET_NOT_FOUND' in rule and 'UNRESOLVED' in rule and 'lookup failure' in rule and 'mapping failure' in rule,
            'The consumer rule states that only a 404 ASSET_NOT_FOUND maps to UNRESOLVED and names the mapping failure')
    for c in provenance['cases']:
        require(c['mappingSays'] and c['assetsAnswers'] and c['consumerShows'],
                'Every case says what the mapping says, what Assets answers and what the consumer shows: ' + c['case'])
    require({c['case'] for c in provenance['cases']} == CASES_11 | {'UNREFERENCED', 'PARENT_CHAIN'}, 'Every controlled case is described')
    require(all(i.startswith(NATIVE_PREFIX + '-') for i in by_id), 'Every asset has a native identifier')
    return len(unreferenced)



def check_reproduction(release, contract_path, missions_dir, source_dir=None):
    """Load the release's own generator and require that it rebuilds every release file byte for byte."""
    release = Path(release)
    spec = importlib.util.spec_from_file_location('assets_release_generate_' + release.name.replace('.', '_'), release / 'generate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONTRACT = Path(contract_path)
    module.MISSIONS_RELEASE = Path(missions_dir)
    if source_dir is not None:
        module.SOURCE_RELEASE = Path(source_dir)
    for name, content in module.release_bytes().items():
        require(read_bytes(release / name) == content, 'The release does not reproduce from its curation: ' + name)


def validate_release(release, contract_path=None, missions_dir=MISSIONS_RELEASE, source_dir=None):
    release = Path(release)
    if (release / 'manifest.json').is_file() and load(release / 'manifest.json').get('contractRevision') == '1.1':
        return validate_release_11(release, contract_path or CONTRACT_11, missions_dir, source_dir or SOURCE_RELEASE)
    contract_path = contract_path or CONTRACT_10
    contract = js.load_json(contract_path)
    manifest = check_files_and_hashes(release, contract_path, missions_dir)
    by_id = check_records(load(release / 'assets.json'), manifest, contract)
    unreferenced = check_missions_cross(load(release / 'provenance.json'), by_id, missions_dir)
    check_reproduction(release, contract_path, missions_dir)
    return {'assets': len(by_id), 'unreferenced': unreferenced}


def validate_release_11(release, contract_path, missions_dir, source_dir):
    """Release 1.1: native identifiers, checked against contract 1.1 and renamed from release 1.0 by a stated rule."""
    contract = js.load_json(contract_path)
    manifest = check_files_and_hashes(release, contract_path, missions_dir, '1.1', source_dir)
    by_id = check_records(load(release / 'assets.json'), manifest, contract, ASSET_ID_11)
    unreferenced = check_missions_cross_11(load(release / 'provenance.json'), by_id, missions_dir)
    check_reproduction(release, contract_path, missions_dir, source_dir)
    return {'assets': len(by_id), 'unreferenced': unreferenced}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    folders = [Path(a) for a in argv] if argv else sorted(p for p in RELEASES.glob('*') if p.is_dir())
    require(folders, 'No Assets dataset release exists under ' + str(RELEASES))
    for folder in folders:
        found = validate_release(folder)
        print(f'PASS: Assets dataset {folder.name}: {found["assets"]} assets, each record valid against the contract schema, '
              f'the kind table, parents, the Missions cross-check ({found["unreferenced"]} assets no mission uses), '
              'the manifest hashes and an exact regeneration.')
    print('LIMITS: offline dataset checks only. No service, database or Docker; the PostgreSQL schema belongs to a later slice.')
    return 0


def cli(entry):
    try:
        return entry() or 0
    except (ValueError, OSError, KeyError, TypeError, js.SchemaError) as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(cli(main))
