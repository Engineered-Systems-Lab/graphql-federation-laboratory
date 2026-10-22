"""Checks of a mapping release against the files it stands on, with no Docker.

A mapping release is immutable and carries a checked-against list: the system versions and dataset releases it was built for. This
module compares a release with the repository as it is now, so that a system version or dataset release the mapping was not checked
against makes a check fail and surfaces the probable need for a new mapping, instead of leaving it to memory. Hashes are taken over
the LF-normalized bytes, the repository's canonical Git-content form, so a Windows checkout gives the same value.

The functions take the repository root as an argument so that the tests can build a small repository of their own.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys

RELEASES = 'federation/mapping-releases'
ASSETS_CONTRACTS = 'uss-enterprise/assets/contracts'
ASSETS_DATASETS = 'uss-enterprise/assets/datasets/releases'
MISSIONS_DATASETS = 'uss-enterprise/missions/datasets/releases'
PROVENANCE = ASSETS_DATASETS + '/1.1/provenance.json'
PERSONNEL_DATASETS = 'uss-enterprise/personnel-v2/datasets'
CREW_MAPPING = 'federation/personnel-mapping/crew_mapping.py'
NEW_MAPPING = 'This is the probable need for a new mapping release (a mapping release is immutable): check what changed, then publish one.'


def lf_sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


# System releases the repository holds before a mapping release exists for them. The lead developer chose this explicit list on 2026-10-19 so that
# Missions dataset release 1.1 (300 missions, appended to 1.0) could land before its mapping release; mapping release 1.2 listed 1.1 in its
# checkedAgainst and the entry went. The same list lets Missions dataset release 1.2 (the participants reclassified as P and O) land before
# its mapping release; mapping release 1.3 lists 1.2 in its checkedAgainst and the entry went. The list is empty now and stays the one place
# where a system release may be excused until its mapping release exists. Nothing else is excused.
PENDING_MAPPING = set()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def version_key(text):
    """MAJOR.MINOR for a release, a contract or a dataset release; the trailing number for a dataset snapshot such as personnel-v2-small-003."""
    if re.fullmatch(r'[0-9]+\.[0-9]+', text):
        major, minor = text.split('.')
        return int(major), int(minor)
    return int(re.fullmatch(r'.*-([0-9]+)', text).group(1)), 0


def release_folders(root):
    base = Path(root) / RELEASES
    return sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: version_key(p.name))


def check_files(release_dir):
    """The manifest names the release, lists every file with its hash, and the folder holds nothing else."""
    release_dir = Path(release_dir)
    problems = []
    manifest = load(release_dir / 'manifest.json')
    if manifest.get('release') != release_dir.name:
        problems.append(f'the manifest names release {manifest.get("release")!r}, the folder is {release_dir.name!r}')
    if not re.fullmatch(r'[0-9]+\.[0-9]+', release_dir.name):
        problems.append(f'{release_dir.name!r} is not MAJOR.MINOR')
    listed = manifest.get('files', {})
    on_disk = {p.name for p in release_dir.iterdir()} - {'manifest.json'}
    if on_disk != set(listed):
        problems.append(f'files on disk {sorted(on_disk)} differ from the files listed {sorted(listed)}')
    for name, digest in listed.items():
        if not (release_dir / name).is_file():
            problems.append(f'{name} is listed and missing')
        elif lf_sha256(release_dir / name) != digest:
            problems.append(f'{name} does not match its hash in the manifest: a published release never changes')
    return problems


def system_files(root):
    """What a checked-against entry stands on: (system, artifact, version) to the file whose LF hash it records."""
    root = Path(root)
    found = {}
    for path in sorted((root / MISSIONS_DATASETS).glob('*/manifest.json')):
        found[('missions', 'dataset release manifest', path.parent.name)] = path
    for path in sorted((root / ASSETS_DATASETS).glob('*/manifest.json')):
        found[('assets', 'dataset release manifest', path.parent.name)] = path
    for path in sorted((root / ASSETS_CONTRACTS).glob('assets-v*.openapi.json')):
        version = re.fullmatch(r'assets-v([0-9]+\.[0-9]+)\.openapi\.json', path.name)
        if version:
            found[('assets', 'contract file', version.group(1))] = path
    for path in sorted((root / PERSONNEL_DATASETS).glob('personnel-v2-small-*.xml')):
        found[('personnel', 'dataset snapshot', path.stem)] = path
    for path in sorted((root / PERSONNEL_DATASETS).glob('personnel-v2-large-*/manifest.json')):  # a paged package: its manifest binds every page
        found[('personnel', 'dataset snapshot', path.parent.name)] = path
    return found


def latest_versions(root):
    """The newest version of each system artifact the repository holds."""
    newest = {}
    for (system, artifact, version) in system_files(root):
        key = (system, artifact)
        if key not in newest or version_key(version) > version_key(newest[key]):
            newest[key] = version
    return newest


def check_against(release_dir, root, newest=True):
    """The checked-against list names real files with the hashes they have now, and, for the newest release (newest=True), names the
    newest version of each artifact. An older release only has to stay true to what it lists: it is immutable, and a newer release
    carries the newer versions."""
    manifest = load(Path(release_dir) / 'manifest.json')
    files = system_files(root)
    problems = []
    listed = set()
    for entry in manifest.get('checkedAgainst', []):
        key = (entry.get('system'), entry.get('artifact'), entry.get('version'))
        listed.add(key)
        if key not in files:
            problems.append(f'checked against {key}, which the repository does not hold. ' + NEW_MAPPING)
        elif lf_sha256(files[key]) != entry.get('sha256'):
            problems.append(f'{key} has changed since the mapping was checked against it. ' + NEW_MAPPING)
    if not listed:
        problems.append('the manifest has no checkedAgainst list')
    for (system, artifact), version in sorted(latest_versions(root).items() if newest else []):
        if (system, artifact, version) in PENDING_MAPPING:
            if (system, artifact, version) in listed:
                problems.append(f'{(system, artifact, version)} is listed as checked against and is still in PENDING_MAPPING: remove the entry')
        elif (system, artifact, version) not in listed:
            problems.append(f'the repository holds {system} {artifact} {version}, which the mapping was not checked against. ' + NEW_MAPPING)
    return problems


def expected_assets(root):
    """The entries and the controlled cases of the Assets dataset release 1.1: its expected mapping, with no entry invented."""
    provenance = load(Path(root) / PROVENANCE)
    entries = {}
    cases = {}
    for item in provenance['expectedMapping']:
        cases.setdefault(item['case'], []).append(item['missionsReference'])
        if item['mapsTo']:
            entries[item['missionsReference']] = item['mapsTo']
    return entries, cases


def check_assets_section(release_dir, root):
    """assets.json equals the expected mapping of the Assets dataset, and the dangling and the unmapped cases are as that dataset says."""
    root = Path(root)
    section = load(Path(release_dir) / 'assets.json')
    entries, cases = expected_assets(root)
    problems = []
    if section.get('entries') != entries:
        problems.append('assets.json entries differ from the expected mapping of the Assets dataset release 1.1: ' + str(
            sorted(set(section.get('entries', {}).items()) ^ set(entries.items()))))
    if section.get('controlledCases') != cases:
        problems.append('assets.json controlledCases differ from the cases of the Assets dataset release 1.1')
    held = {asset['assetId'] for asset in load(root / ASSETS_DATASETS / '1.1' / 'assets.json')['assets']}
    for reference in cases.get('MAPPED_NOT_FOUND', []):
        if section['entries'].get(reference) in held:
            problems.append(f'{reference} must map to an id Assets does not hold')
    for reference in cases.get('UNMAPPED', []):
        if reference in section['entries']:
            problems.append(f'{reference} must have no entry')
    for reference, ast_id in section['entries'].items():
        if reference not in cases.get('MAPPED_NOT_FOUND', []) and ast_id not in held:
            problems.append(f'{reference} maps to {ast_id}, which the Assets dataset does not hold')
    return problems


def crew_mapping_module(root):
    """The process module of the federation layer, loaded from the repository being checked."""
    path = Path(root) / CREW_MAPPING
    spec = importlib.util.spec_from_file_location('crew_mapping_under_check', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['crew_mapping_under_check'] = module
    spec.loader.exec_module(module)
    return module


def check_crew_section(release_dir, root):
    """crew.json is exactly what the crew mapping process builds from its pinned inputs, every pin holds, and the manifest of the
    release names the Personnel v2 snapshot the table was built against (the pinned target) in its checked-against list."""
    root = Path(root)
    release_dir = Path(release_dir)
    module = crew_mapping_module(root)
    problems = list(module.check_pins(root))
    if problems:
        return problems
    try:
        inputs = module.load_inputs(root)
        built = module.render(module.build_crew_section(inputs))
    except module.MappingFailure as failure:
        return ['the crew mapping process fails: ' + str(failure)]
    actual = (release_dir / 'crew.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    if actual != built:
        problems.append('crew.json differs from what the crew mapping process builds from its pinned inputs')
    target = root / inputs.pins['v2Target']['path']
    expected = ('personnel', 'dataset snapshot', target.stem, lf_sha256(target))
    listed = [(e.get('system'), e.get('artifact'), e.get('version'), e.get('sha256'))
              for e in load(release_dir / 'manifest.json').get('checkedAgainst', [])]
    if expected not in listed:
        problems.append(f'the checked-against list does not name the Personnel v2 snapshot {target.stem} with its current hash')
    return problems


def check_large_release(release_dir, root):
    """Mapping release 1.2: the pins of the process hold, and every file of the release (crew.json, participants.json, assets.json and the
    manifest, whose checked-against list names Missions dataset release 1.1 and the large Personnel v2 snapshot with their current hashes)
    is exactly what the process builds from its pinned inputs."""
    return _check_built_release(release_dir, root, 'RELEASE_PINS', 'load_release_inputs', 'build_release_large')


def check_release_13(release_dir, root):
    """Mapping release 1.3: the same check for the release built from Missions dataset release 1.2 (assets.json and crew.json as in
    release 1.2, participants.json with every P-reference resolved, the manifest naming Missions dataset release 1.2)."""
    return _check_built_release(release_dir, root, 'RELEASE_13_PINS', 'load_release_13_inputs', 'build_release_13')


def _check_built_release(release_dir, root, pins, load_inputs, build):
    root = Path(root)
    release_dir = Path(release_dir)
    module = crew_mapping_module(root)
    problems = list(module.check_pins(root, getattr(module, pins)))
    if problems:
        return problems
    try:
        expected = getattr(module, build)(getattr(module, load_inputs)(root))
    except module.MappingFailure as failure:
        return ['the crew mapping process fails: ' + str(failure)]
    on_disk = {path.name for path in release_dir.iterdir()}
    problems = [f'{name} is ' + ('extra' if name in on_disk else 'missing') for name in sorted(on_disk ^ set(expected))]
    for name, text in expected.items():
        path = release_dir / name
        if path.is_file() and path.read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text:
            problems.append(f'{name} differs from what the crew mapping process builds from its pinned inputs')
    return problems
