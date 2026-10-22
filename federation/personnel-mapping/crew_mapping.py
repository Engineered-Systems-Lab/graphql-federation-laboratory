"""The crew mapping process of the federation layer: Missions crew references (C-n) to Personnel v2 identifiers (PRS-nnnn).

One process is used by the migration and by the mapping build, so the two can never disagree. For each Missions crew reference of
the Missions recipe (uss-enterprise/missions/datasets/recipe.json, references.crew, the source of truth for the Missions side):

  1. the mapping exceptions table (C-n to PRS-nnnn; every target must exist in the pinned Personnel v2 snapshot; it never names v1).
     A match stops the process.
  2. an exact name match in the pinned Personnel v2 snapshot. Found: stop.
  3. an exact name match in the pinned v1 release, or the migration exceptions table (C-n to CRW-nnnn, used only here): that
     person must be migrated to Personnel v2. A migration exception wins over a name.
  4. otherwise the process fails and reports; live, the reference is UNMAPPED.

More than one match is a failure that reports every match, never a pick. Live mode (no v1 release) never runs step 3 and ends in
UNMAPPED; the static build ends in a failure instead, and a reference that still needs a migration is a failure of the static build.
Every input is pinned by hash in pins.json (and the release repeats the pins): a run refuses to start when one differs.

Commands, from the repository root (nothing is written without --write):
  check            verify the pins, the migration and the mapping release 1.1 against the files
  migrate          run the migration from the pinned v2 source and compare with (or write) the target snapshot
  build-crew       build the crew section of mapping release 1.1
  release          build all files of mapping release 1.1 (assets.json is the 1.0 file, unchanged)
  pins             recompute the hashes of pins.json (a deliberate act: it re-pins the inputs)
  large            batch mode: migrate EVERY person of the v1 release into the large Personnel v2 snapshot (steps 2 and 3 for each
                   person, the people of the pinned snapshot kept byte for byte) and add the generated civilians (civilians.py);
                   compare with, or with --write write, the package personnel-v2-large-004 (pages and manifest)
  release-large    build mapping release 1.2 (assets.json as in 1.1, crew.json for the 800 crew references of Missions dataset release
                   1.1 against personnel-v2-large-004, participants.json for its P participants; O-references are refused by class);
                   --write writes the folder and refuses to overwrite one
  check-large      verify the pins of release 1.2 and compare the folder on disk with what the process builds
  release-13       build mapping release 1.3 (assets.json and crew.json as in 1.2, participants.json for the P participants of Missions
                   dataset release 1.2, which must ALL resolve; O-references are refused by class); --write writes the folder and
                   refuses to overwrite one
  check-13         verify the pins of release 1.3 and compare the folder on disk with what the process builds

Reference classes of Missions: C is crew (the crew section), P is a participant that may be a non-crew person on the roster (the
participants section), O is an outsider and is REFUSED BY CLASS: the process never accepts an O-reference, whatever its name.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
PINS = 'federation/personnel-mapping/pins.json'
LARGE_PINS = 'federation/personnel-mapping/large-pins.json'
LARGE_VERSION = 'personnel-v2-large-004'
LARGE_FOLDER = 'uss-enterprise/personnel-v2/datasets/' + LARGE_VERSION
LARGE_IDENTITY = 'personnel-v2-large-004-v1'
LARGE_ALGORITHM = 'crew-mapping-batch-v1'
RELEASE_PINS = 'federation/personnel-mapping/release-large-pins.json'
RELEASE_LARGE = '1.2'
RELEASE_13_PINS = 'federation/personnel-mapping/release-1-3-pins.json'
RELEASE_13 = '1.3'
PAGE_SIZE = 100  # the Personnel v2 contract returns at most 100 members per response
RELEASE = '1.1'
V1NS = '{urn:graphql-federation-lab:crew-personnel:v1}'
V2NS = '{urn:graphql-federation-lab:personnel:v2}'
PRS = re.compile(r'PRS-([0-9]{4})')
CRW = re.compile(r'CRW-([0-9]{4})')
REFERENCE = re.compile(r'C-([0-9]+)')
ANY_REFERENCE = re.compile(r'([A-Z])-([0-9]+)')
V2_RANKS = ('CAPTAIN', 'COMMANDER', 'LIEUTENANT_COMMANDER', 'LIEUTENANT', 'ENSIGN', 'CHIEF_PETTY_OFFICER', 'CREWMAN')
V2_DEPARTMENTS = ('COMMAND', 'OPERATIONS', 'ENGINEERING', 'SCIENCE', 'MEDICAL', 'SECURITY', 'FLIGHT_OPERATIONS')
V2_DUTY = ('ACTIVE', 'ON_LEAVE', 'INACTIVE', 'DECEASED')
CLEARANCE_ORDER = ('NONE', 'SECRET', 'TOP_SECRET')
RANK_CLEARANCE = {'CAPTAIN': 'TOP_SECRET', 'COMMANDER': 'SECRET', 'LIEUTENANT_COMMANDER': 'SECRET'}
SMALL_SNAPSHOT_MAX = 20  # the Personnel v2 service reads a small snapshot as one page of at most 20 members


class MappingFailure(Exception):
    """A refusal of the process. `matches` lists every candidate when the cause is more than one match."""

    def __init__(self, message, matches=()):
        super().__init__(message)
        self.matches = list(matches)


class Resolution:
    """The outcome for one reference: EXCEPTION, NAME, MIGRATE (a person to bring to v2), UNMAPPED (live crew mapping, and a participant
    nobody places) or REFUSED (an O-reference, refused by class: it is never matched)."""

    def __init__(self, ref, name, outcome, target=None, v1_id=None, migrated_id=None):
        self.ref, self.name, self.outcome = ref, name, outcome
        self.target, self.v1_id, self.migrated_id = target, v1_id, migrated_id

    def __repr__(self):
        return f'Resolution({self.ref} {self.name!r} {self.outcome} {self.target or self.migrated_id})'


# ---- hashes, files and parsing -------------------------------------------------------------------------------------------------

def digest(path, hashing):
    data = Path(path).read_bytes()
    if hashing == 'lf':
        data = data.replace(b'\r\n', b'\n')
    elif hashing != 'raw':
        raise MappingFailure(f'unknown hashing {hashing!r}')
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def ref_number(ref):
    return int(REFERENCE.fullmatch(ref).group(1))


def reference_class(ref):
    """The class letter of a Missions-local reference: C crew, P participant, O outsider."""
    match = ANY_REFERENCE.fullmatch(ref)
    if not match:
        raise MappingFailure(f'{ref!r} is not a Missions-local reference of the form X-n')
    return match.group(1)


def reference_key(ref):
    """Order of the references of one section: by class letter, then by number."""
    match = ANY_REFERENCE.fullmatch(ref)
    if not match:
        raise MappingFailure(f'{ref!r} is not a Missions-local reference of the form X-n')
    return match.group(1), int(match.group(2))


def parse_v1(directory):
    """crewId to person for every page of a v1 release, in the order of the manifest."""
    directory = Path(directory)
    people = {}
    for page in read_json(directory / 'manifest.json')['pages']:
        for node in ET.parse(directory / page['filename']).getroot().findall(V1NS + 'crewMember'):
            fields = {child.tag.replace(V1NS, ''): (child.text or '') for child in node}
            people[fields['crewId']] = {'displayName': fields['displayName'], 'positionTitle': fields['positionTitle'],
                                        'dutyStatus': fields['dutyStatus'], 'rank': fields['rank'], 'department': fields['department'],
                                        'supervisor': fields.get('supervisorCrewId')}
    return people


def parse_v2(text):
    """personnelId to person for a Personnel v2 snapshot. A civilian has rank, department and clearance None."""
    people = {}
    for node in ET.fromstring(text).findall(V2NS + 'personnelMember'):
        crew = node.find(V2NS + 'crewDetails')

        def inner(name):
            return None if crew is None else crew.findtext(V2NS + name)
        people[node.findtext(V2NS + 'personnelId')] = {
            'displayName': node.findtext(V2NS + 'displayName'), 'positionTitle': node.findtext(V2NS + 'positionTitle'),
            'dutyStatus': node.findtext(V2NS + 'dutyStatus'), 'rank': inner('rank'), 'department': inner('department'),
            'securityClearance': inner('securityClearance'), 'supervisor': inner('supervisorPersonnelId')}
    return people


def validate_people(people):
    """The readiness rules of the Personnel v2 service: known supervisors and no reporting cycle."""
    for ident in people:
        seen = set()
        current = ident
        while current is not None:
            if current in seen:
                raise MappingFailure(f'reporting cycle through {current}')
            seen.add(current)
            if current not in people:
                raise MappingFailure(f'{ident} reports to {current}, which the snapshot does not hold')
            current = people[current]['supervisor']


# ---- the pins and the inputs ---------------------------------------------------------------------------------------------------

def check_pins(root=DEFAULT_ROOT, pins_file=PINS):
    """Every pinned input against its file, and every page of the v1 release against its manifest. Empty when all agree."""
    root = Path(root)
    pins = read_json(root / pins_file)
    problems = []
    for key, entry in pins.items():
        if not (isinstance(entry, dict) and 'path' in entry):
            continue
        path = root / entry['path']
        if not path.is_file():
            problems.append(f'{key}: {entry["path"]} is missing')
        elif digest(path, entry['hashing']) != entry['sha256']:
            problems.append(f'{key}: {entry["path"]} differs from its pin')
    for key in ('v1Release', 'v2Target'):  # a pinned manifest of pages: every page against the hash the manifest holds
        manifest = root / pins[key]['path'] if key in pins else None
        if manifest is not None and manifest.name == 'manifest.json' and manifest.is_file():
            for page in read_json(manifest)['pages']:
                file = manifest.parent / page['filename']
                if not file.is_file() or digest(file, 'lf') != page['sha256']:
                    problems.append(f'{key}: {page["filename"]} differs from the hash in the manifest of the release')
    return problems


class Inputs:
    pass


def load_inputs(root=DEFAULT_ROOT, verify_target=True):
    """Read every pinned input. A pin that does not hold stops the run (nothing is read from a changed file)."""
    root = Path(root)
    problems = check_pins(root)
    if not verify_target:
        problems = [p for p in problems if not p.startswith('v2Target:')]
    if problems:
        raise MappingFailure('the run refuses to start, an input differs from its pin: ' + '; '.join(problems))
    pins = read_json(root / PINS)
    inputs = Inputs()
    inputs.root, inputs.pins = root, pins
    crew = read_json(root / pins['recipe']['path'])['references']['crew']
    inputs.references = {ref: name for name, ref in sorted(crew.items(), key=lambda item: ref_number(item[1]))}
    inputs.v1 = parse_v1((root / pins['v1Release']['path']).parent)
    inputs.v2_source_text = (root / pins['v2Source']['path']).read_text(encoding='utf-8')
    inputs.v2_source = parse_v2(inputs.v2_source_text)
    target = root / pins['v2Target']['path']
    inputs.v2_target_text = target.read_text(encoding='utf-8') if target.is_file() else None
    inputs.v2_target = parse_v2(inputs.v2_target_text) if inputs.v2_target_text else None
    inputs.mapping_exceptions = read_json(root / pins['mappingExceptions']['path'])['entries']
    inputs.migration_exceptions = read_json(root / pins['migrationExceptions']['path'])['entries']
    return inputs


# ---- the process ---------------------------------------------------------------------------------------------------------------

def clearance(rank, department):
    """By rank (CAPTAIN TOP_SECRET, COMMANDER and LIEUTENANT_COMMANDER SECRET, the rest NONE), raised to at least SECRET for SECURITY."""
    value = RANK_CLEARANCE.get(rank, 'NONE')
    if department == 'SECURITY' and CLEARANCE_ORDER.index(value) < CLEARANCE_ORDER.index('SECRET'):
        value = 'SECRET'
    return value


def migrated_id(v1_id):
    """A migrated person keeps the number of the v1 id: CRW-1048 becomes PRS-1048."""
    number = CRW.fullmatch(v1_id).group(1)
    if int(number) == 0:
        raise MappingFailure(f'{v1_id} has no Personnel v2 identifier of the same number')
    return 'PRS-' + number


def _exact(people, name):
    return sorted(ident for ident, person in people.items() if person['displayName'] == name)


def map_references(references, mapping_exceptions, v2, v1=None, migration_exceptions=None, live=False, allow_pending=False):
    """Run the process for every reference (a dict of reference to recipe name) and return one Resolution each, in reference order.

    v1 None means live mode or a mapping build without the old release: step 3 never runs. live=True ends an unplaced reference in
    UNMAPPED; otherwise it is a failure. allow_pending is for the migration only: a mapping exception whose target is not in the
    snapshot yet is accepted when this very run migrates that person to exactly that identifier.
    """
    migration_exceptions = migration_exceptions or {}
    for ref in references:  # the classes: this process maps C-references; an O-reference is refused by class, whatever its name
        kind = reference_class(ref)
        if kind == 'O':
            raise MappingFailure(f'{ref} {references[ref]!r}: O-references are refused by class, the process never accepts one')
        if kind != 'C':
            raise MappingFailure(f'{ref}: the crew mapping takes C-references only, {kind}-references belong to the participants section')
    if live:
        v1 = None  # live mode never runs step 3
    for ref in list(mapping_exceptions) + list(migration_exceptions):
        if ref not in references:
            raise MappingFailure(f'an exception names {ref}, which the Missions recipe does not hold')
    for ref, target in mapping_exceptions.items():
        if not PRS.fullmatch(target) or int(target[4:]) == 0:
            raise MappingFailure(f'mapping exception {ref} names {target!r}, which is not a Personnel v2 identifier (the table never names v1)')
    if v1 is not None:
        for ref, v1_id in migration_exceptions.items():
            if v1_id not in v1:
                raise MappingFailure(f'migration exception {ref} names {v1_id}, which the pinned v1 release does not hold')
    results = []
    for ref in sorted(references, key=ref_number):
        name = references[ref]
        results.append(_resolve(ref, name, mapping_exceptions, v2, v1, migration_exceptions, live, allow_pending))
    taken = set(v2)
    for result in results:
        if result.outcome == 'MIGRATE' and result.migrated_id in taken:
            raise MappingFailure(f'{result.ref} {result.name!r}: {result.v1_id} would become {result.migrated_id}, which Personnel v2 holds')
    return results


def _resolve(ref, name, mapping_exceptions, v2, v1, migration_exceptions, live, allow_pending):
    pending = None
    target = mapping_exceptions.get(ref)
    if target is not None:
        if target in v2:
            return Resolution(ref, name, 'EXCEPTION', target)  # step 1: a match stops the process
        if not (allow_pending and v1 is not None):
            raise MappingFailure(f'mapping exception {ref} names {target}, which the pinned Personnel v2 snapshot does not hold')
        pending = target
    hits = _exact(v2, name)  # step 2
    if len(hits) > 1:
        raise MappingFailure(f'{ref} {name!r}: more than one exact name match in Personnel v2: {hits}', hits)
    if hits:
        if pending:
            raise MappingFailure(f'{ref}: the exception names {pending}, which is not in the snapshot, but {hits[0]} matches by name')
        return Resolution(ref, name, 'NAME', hits[0])
    if v1 is not None:  # step 3
        v1_id = migration_exceptions.get(ref)
        if v1_id is None:
            matches = _exact(v1, name)
            if len(matches) > 1:
                raise MappingFailure(f'{ref} {name!r}: more than one exact name match in the v1 release: {matches}', matches)
            v1_id = matches[0] if matches else None
        if v1_id is not None:
            result = Resolution(ref, name, 'MIGRATE', v1_id=v1_id, migrated_id=migrated_id(v1_id))
            if pending and pending != result.migrated_id:
                raise MappingFailure(f'{ref}: the exception names {pending}, but the migration creates {result.migrated_id}')
            return result
    if pending:
        raise MappingFailure(f'{ref}: the exception names {pending}, which is not in the snapshot, and nothing migrates to it')
    if live:
        return Resolution(ref, name, 'UNMAPPED')  # step 4, live
    raise MappingFailure(f'{ref} {name!r}: no mapping exception, no exact name in Personnel v2'
                         + (', none in the v1 release and no migration exception' if v1 is not None else ''))


# ---- the migration -------------------------------------------------------------------------------------------------------------

MEMBER_LINE = re.compile(r'  <personnelMember><personnelId>(PRS-[0-9]{4})</personnelId>')
COUNT_LINE = re.compile(r'(  <totalCount>)[0-9]+(</totalCount>)')


def _split(source_text):
    """A Personnel v2 snapshot of one member per line as (header lines, member lines, trailer lines)."""
    if '\r' in source_text:
        raise MappingFailure('the source snapshot must use LF line ends')
    lines = source_text.rstrip('\n').split('\n')
    members = [line for line in lines if MEMBER_LINE.match(line)]
    first = next((i for i, line in enumerate(lines) if MEMBER_LINE.match(line)), None)
    if first is None:
        first = next(i for i, line in enumerate(lines) if line.startswith('  <totalCount>'))
    header = [line for line in lines[:first]]
    trailer = lines[first + len(members):]
    if any(MEMBER_LINE.match(line) for line in trailer) or any(not MEMBER_LINE.match(line) for line in lines[first:first + len(members)]):
        raise MappingFailure('the source snapshot does not keep one member per line')
    return header, members, trailer


def _supervisor(person, v1, migrating, v2_people, who):
    v1_id = person['supervisor']
    if v1_id is None:
        return None
    if v1_id in migrating:
        return migrating[v1_id]
    if v1_id not in v1:
        raise MappingFailure(f'{who}: the supervisor {v1_id} is not in the v1 release')
    hits = _exact(v2_people, v1[v1_id]['displayName'])
    if len(hits) != 1:
        raise MappingFailure(f'{who}: the supervisor {v1_id} {v1[v1_id]["displayName"]!r} is neither migrated nor found once by name in '
                             f'Personnel v2 (found {hits}); only the people the process marks are migrated')
    return hits[0]


def _record(ident, person, supervisor):
    if person['rank'] == 'CIVILIAN':
        details = '<civilianDetails/>'
    else:
        if person['rank'] not in V2_RANKS or person['department'] not in V2_DEPARTMENTS:
            raise MappingFailure(f'{ident}: rank {person["rank"]!r} or department {person["department"]!r} is not a Personnel v2 value')
        details = ('<crewDetails><rank>' + person['rank'] + '</rank><department>' + person['department'] + '</department>'
                   '<securityClearance>' + clearance(person['rank'], person['department']) + '</securityClearance>'
                   + (f'<supervisorPersonnelId>{supervisor}</supervisorPersonnelId>' if supervisor else '') + '</crewDetails>')
    if person['dutyStatus'] not in V2_DUTY:
        raise MappingFailure(f'{ident}: duty status {person["dutyStatus"]!r} is not a Personnel v2 value')
    return ('  <personnelMember><personnelId>' + ident + '</personnelId><displayName>' + escape(person['displayName'])
            + '</displayName><positionTitle>' + escape(person['positionTitle']) + '</positionTitle><dutyStatus>' + person['dutyStatus']
            + '</dutyStatus>' + details + '</personnelMember>')


def migrate(source_text, v1, results, version):
    """The new snapshot: the source with the migrated people added. Existing records are kept byte for byte; only the people the
    process marked MIGRATE are added, each with the number of its v1 id; supervisors are remapped to Personnel v2 identifiers."""
    header, members, trailer = _split(source_text)
    people = parse_v2(source_text)
    migrating = {}
    for result in results:
        if result.outcome == 'MIGRATE':
            migrating[result.v1_id] = result.migrated_id
    added = {}
    for v1_id, ident in sorted(migrating.items(), key=lambda item: item[1]):
        added[ident] = _record(ident, v1[v1_id], _supervisor(v1[v1_id], v1, migrating, people, f'{v1_id} {v1[v1_id]["displayName"]!r}'))
    clash = set(added) & set(people)
    if clash:
        raise MappingFailure(f'identifiers already in the snapshot: {sorted(clash)}')
    merged = {MEMBER_LINE.match(line).group(1): line for line in members}
    merged.update(added)
    if len(merged) > SMALL_SNAPSHOT_MAX:
        raise MappingFailure(f'a small snapshot holds at most {SMALL_SNAPSHOT_MAX} members, not {len(merged)}')
    header = [re.sub(r'<datasetVersion>[^<]*</datasetVersion>', f'<datasetVersion>{version}</datasetVersion>', line) for line in header]
    trailer = [COUNT_LINE.sub(lambda m: m.group(1) + str(len(merged)) + m.group(2), line) for line in trailer]
    text = '\n'.join(header + [merged[key] for key in sorted(merged)] + trailer) + '\n'
    validate_people(parse_v2(text))
    return text


# ---- the mapping release -------------------------------------------------------------------------------------------------------

def static_table(inputs):
    """The crew table of the mapping release: the process on the target snapshot, in static mode. A reference that still needs a
    migration, or that nothing places, fails the build."""
    results = map_references(inputs.references, inputs.mapping_exceptions, inputs.v2_target, v1=inputs.v1,
                             migration_exceptions=inputs.migration_exceptions)
    waiting = [r for r in results if r.outcome == 'MIGRATE']
    if waiting:
        raise MappingFailure('these people must be migrated to Personnel v2 first: '
                             + ', '.join(f'{r.ref} {r.name!r} ({r.v1_id})' for r in waiting))
    return results


def _came_from_v1(target, inputs):
    """True when the person is a migrated one: the v1 release holds the same number with the same name."""
    v1_id = 'CRW-' + target[4:]
    return v1_id in inputs.v1 and inputs.v1[v1_id]['displayName'] == inputs.v2_target[target]['displayName']


def build_crew_section(inputs):
    results = static_table(inputs)
    migrated = [r.ref for r in results if _came_from_v1(r.target, inputs)]
    return {
        'section': 'crew',
        'description': 'The Missions-local crew reference to the Personnel v2 identifier PRS-nnnn: the full resulting table.',
        'source': 'Built by federation/personnel-mapping/crew_mapping.py from the pinned inputs below: the Missions recipe, the mapping '
                  'exceptions table and the Personnel v2 snapshot personnel-v2-small-003 (the migration of the cast from the v1 release '
                  'is described in federation/personnel-mapping/README.md). A reference with no entry has no mapping (UNMAPPED).',
        'inputs': {key: {'hashing': entry['hashing'], 'sha256': entry['sha256']} for key, entry in inputs.pins.items()
                   if isinstance(entry, dict) and 'path' in entry},
        'controlledCases': {
            'NORMAL': [r.ref for r in results if r.outcome == 'NAME' and r.ref not in migrated],
            'EXCEPTION': [r.ref for r in results if r.outcome == 'EXCEPTION' and r.ref not in migrated],
            'MIGRATED': migrated,
        },
        'entries': {r.ref: r.target for r in results},
    }


def render(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


def build_release(inputs):
    """The three files of mapping release 1.1: assets.json is the release 1.0 file, unchanged."""
    root = inputs.root
    previous = root / 'federation/mapping-releases/1.0'
    assets = (previous / 'assets.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    crew = render(build_crew_section(inputs))
    old = read_json(previous / 'manifest.json')
    target = root / inputs.pins['v2Target']['path']
    checked = list(old['checkedAgainst']) + [{'system': 'personnel', 'artifact': 'dataset snapshot', 'version': target.stem,
                                              'sha256': digest(target, 'lf')}]
    files = {'assets.json': assets, 'crew.json': crew}
    manifest = {'release': RELEASE,
                'files': {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in sorted(files.items())},
                'checkedAgainst': checked}
    files['manifest.json'] = render(manifest)
    return files


# ---- the large snapshot (batch mode) -------------------------------------------------------------------------------------------

def civilians_module():
    spec = importlib.util.spec_from_file_location('civilians', HERE / 'civilians.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_large_inputs(root=DEFAULT_ROOT):
    """Read the inputs of the batch (the v1 release and the Personnel v2 source snapshot), both pinned in large-pins.json."""
    root = Path(root)
    problems = check_pins(root, LARGE_PINS)
    if problems:
        raise MappingFailure('the run refuses to start, an input differs from its pin: ' + '; '.join(problems))
    inputs = Inputs()
    inputs.root, inputs.pins = root, read_json(root / LARGE_PINS)
    inputs.v1 = parse_v1((root / inputs.pins['v1Release']['path']).parent)
    inputs.v2_source_text = (root / inputs.pins['v2Source']['path']).read_bytes().decode('utf-8')
    inputs.v2_source = parse_v2(inputs.v2_source_text)
    return inputs


def map_people(v1, v2):
    """The process for every person of the v1 release, one Resolution each in v1 order: step 2 (an exact name in Personnel v2: the person
    is there already and the v2 record stands) and step 3 (the person is migrated and keeps the number of the v1 id). The mapping
    exceptions and the migration exceptions are about the Missions references and take no part. More than one match is a failure."""
    results = [_resolve(v1_id, v1[v1_id]['displayName'], {}, v2, v1, {}, False, False) for v1_id in sorted(v1)]
    taken = set(v2)
    for result in results:
        if result.outcome == 'MIGRATE' and result.migrated_id in taken:
            raise MappingFailure(f'{result.ref} {result.name!r}: {result.v1_id} would become {result.migrated_id}, which Personnel v2 holds')
    named = [r.target for r in results if r.outcome == 'NAME']
    if len(set(named)) != len(named):
        raise MappingFailure('two people of the v1 release match the same Personnel v2 person')
    return results


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, separators=(',', ': '), allow_nan=False) + '\n').encode('ascii')


def build_large(inputs):
    """The package personnel-v2-large-004 as {file name: bytes}: the pages (each a valid ListPersonnelMembersResponse of at most 100
    members, in personnelId order) and manifest.json. The people of the source snapshot stay byte for byte, every other person of the
    v1 release is migrated by the batch of the process, and the civilians are added. The contract (XSD, WSDL) does not change."""
    v1, source_text = inputs.v1, inputs.v2_source_text
    header, members, trailer = _split(source_text)
    people = parse_v2(source_text)
    results = map_people(v1, people)
    migrating = {r.v1_id: r.migrated_id for r in results if r.outcome == 'MIGRATE'}
    kept = {r.ref: r.target for r in results if r.outcome == 'NAME'}
    merged = {MEMBER_LINE.match(line).group(1): line for line in members}
    for v1_id, ident in sorted(migrating.items(), key=lambda item: item[1]):
        person = v1[v1_id]
        merged[ident] = _record(ident, person, _supervisor(person, v1, migrating, people, f'{v1_id} {person["displayName"]!r}'))
    module = civilians_module()
    generated = module.generate()
    for civilian in generated:
        if civilian['personnelId'] in merged:
            raise MappingFailure(f'the civilian {civilian["personnelId"]} would take an identifier that is already used')
        merged[civilian['personnelId']] = _record(civilian['personnelId'], dict(
            displayName=civilian['displayName'], positionTitle=civilian['positionTitle'], dutyStatus=civilian['dutyStatus'],
            rank='CIVILIAN', department=None, supervisor=None), None)
    ids = sorted(merged)
    total = len(ids)
    if total != len(members) + len(migrating) + len(generated):
        raise MappingFailure('the count of the snapshot does not add up')
    full = parse_v2('\n'.join(header + [merged[i] for i in ids] + [trailer[-1]]) + '\n')
    names = [person['displayName'] for person in full.values()]
    if len(set(names)) != len(names):
        raise MappingFailure('two people of the large snapshot share a name')
    validate_people(full)
    version = LARGE_VERSION
    top = [re.sub(r'<datasetVersion>[^<]*</datasetVersion>', f'<datasetVersion>{version}</datasetVersion>', line) for line in header]
    files = {}
    descriptors = []
    for page in range(-(-total // PAGE_SIZE)):
        chunk = ids[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        more = 'true' if (page + 1) * PAGE_SIZE < total else 'false'
        stats = f'  <totalCount>{total}</totalCount><offset>{page * PAGE_SIZE}</offset><limit>{PAGE_SIZE}</limit><hasMore>{more}</hasMore>'
        data = ('\n'.join(top + [merged[i] for i in chunk] + [stats, trailer[-1]]) + '\n').encode('utf-8')
        name = f'page-{page:03d}.xml'
        files[name] = data
        descriptors.append(dict(filename=name, offset=page * PAGE_SIZE, count=len(chunk), byteLength=len(data),
                                sha256=hashlib.sha256(data).hexdigest()))
    manifest = dict(
        formatVersion=1, datasetVersion=version, count=total, pageSize=PAGE_SIZE, pages=descriptors,
        generator=dict(identity=LARGE_IDENTITY, algorithm=LARGE_ALGORITHM + ' + ' + module.ALGORITHM,
                       toolchain=dict(implementation='CPython', minimumVersion='3.13', dependencies='stdlib-only'),
                       source=dict(path='federation/personnel-mapping/civilians.py', hashing='sha256-crlf-to-lf-v1',
                                   sha256=digest(HERE / 'civilians.py', 'lf'))),
        inputs={key: dict(path=entry['path'], hashing=entry['hashing'], sha256=entry['sha256'])
                for key, entry in sorted(inputs.pins.items()) if isinstance(entry, dict) and 'path' in entry},
        composition=dict(
            sourceRecords=len(members), keptByName=dict(sorted(kept.items())), migrated=len(migrating),
            migratedRule='a person not in the source snapshot by exact name keeps the number of the v1 id (CRW-1048 becomes PRS-1048)',
            civilians=dict(count=len(generated), firstId=generated[0]['personnelId'], lastId=generated[-1]['personnelId'],
                           seed=module.SEED, identity=module.IDENTITY, algorithm=module.ALGORITHM,
                           canonInspired=[c['personnelId'] for c in generated if c['origin'] == 'canon-inspired'],
                           synthetic='every other civilian of the range is generated and synthetic; the canon-inspired ones '
                                     'carry a name and a title only, with no episode facts')))
    files['manifest.json'] = _json_bytes(manifest)
    return files


def large_files(root=DEFAULT_ROOT):
    return build_large(load_large_inputs(root))


def compare_large(root):
    """Problems between the package on disk and what the batch builds; empty when they agree byte for byte."""
    root = Path(root)
    folder = root / LARGE_FOLDER
    expected = large_files(root)
    if not folder.is_dir():
        return [f'{LARGE_FOLDER} is missing']
    problems = []
    on_disk = {path.name for path in folder.iterdir()}
    for name in sorted(on_disk ^ set(expected)):
        problems.append(f'{LARGE_FOLDER}/{name} is ' + ('extra' if name in on_disk else 'missing'))
    for name, data in expected.items():
        path = folder / name
        if path.is_file() and path.read_bytes() != data:
            problems.append(f'{LARGE_FOLDER}/{name} differs from what the batch builds')
    return problems


# ---- the participants and the mapping release 1.2 -----------------------------------------------------------------------------

def map_participants(participants, exceptions, v2, strict=False):
    """The process for the participant references of Missions (a dict of reference to the recipe label), one Resolution each, ordered by
    class letter and number. The classes decide first: an O-reference is REFUSED BY CLASS and never matched, whatever its name (it
    carries no Personnel membership claim); a P-reference is placed by the participant exceptions table (P-n to PRS-nnnn, a match
    stops the process) or by an exact name among the NON-CREW people of the snapshot, and ends in UNMAPPED when nothing places it. More
    than one exact match is a failure that reports every match, and so is a name that only a crew member holds: a participant reaches
    a non-crew person, and any other decision belongs to the exceptions table. No other class is accepted here. In strict mode (mapping
    release 1.3) a P-reference that nobody places is a FAILURE that names it, not an UNMAPPED to accept: under the definitions of the
    Missions data a participant is an on-board person and must resolve."""
    for ref in exceptions:
        kind = reference_class(ref)
        if kind == 'O':
            raise MappingFailure(f'participant exception {ref}: O-references are refused by class, no table can accept one')
        if kind != 'P' or ref not in participants:
            raise MappingFailure(f'participant exception {ref} names a reference that is not a participant of the Missions recipe')
    for ref, target in exceptions.items():
        if not PRS.fullmatch(target) or int(target[4:]) == 0:
            raise MappingFailure(f'participant exception {ref} names {target!r}, which is not a Personnel v2 identifier')
        if target not in v2:
            raise MappingFailure(f'participant exception {ref} names {target}, which the pinned Personnel v2 snapshot does not hold')
        if v2[target]['rank'] is not None:
            raise MappingFailure(f'participant exception {ref} names {target}, a crew member: a participant reaches a non-crew person only')
    results = []
    for ref in sorted(participants, key=reference_key):
        label = participants[ref]
        kind = reference_class(ref)
        if kind == 'O':
            results.append(Resolution(ref, label, 'REFUSED'))
            continue
        if kind != 'P':
            raise MappingFailure(f'{ref}: the participants section takes P-references; O is refused by class and C belongs to the crew section')
        if ref in exceptions:
            results.append(Resolution(ref, label, 'EXCEPTION', exceptions[ref]))
            continue
        hits = _exact(v2, label)
        if len(hits) > 1:
            raise MappingFailure(f'{ref} {label!r}: more than one exact name match in Personnel v2: {hits}', hits)
        if hits and v2[hits[0]]['rank'] is not None:
            raise MappingFailure(f'{ref} {label!r}: the only exact name match {hits[0]} is a crew member, and a participant reaches a '
                                 'non-crew person only (a participant exception decides)', hits)
        if strict and not hits:
            raise MappingFailure(f'{ref} {label!r}: no exact name match among the non-crew people of Personnel v2 and no participant '
                                 'exception: a P-reference must resolve')
        results.append(Resolution(ref, label, 'NAME', hits[0]) if hits else Resolution(ref, label, 'UNMAPPED'))
    return results


def _load_release_common(root, pins_file):
    """The inputs a release stands on whatever its Missions side: the recipe's crew references, the legacy crew release, the three
    exceptions tables and the pages of the large Personnel v2 snapshot. A pin that does not hold stops the run. Returns the inputs and
    the references of the recipe."""
    root = Path(root)
    problems = check_pins(root, pins_file)
    if problems:
        raise MappingFailure('the run refuses to start, an input differs from its pin: ' + '; '.join(problems))
    inputs = Inputs()
    inputs.root, inputs.pins = root, read_json(root / pins_file)
    pins = inputs.pins
    references = read_json(root / pins['recipe']['path'])['references']
    inputs.references = {ref: name for name, ref in sorted(references['crew'].items(), key=lambda item: ref_number(item[1]))}
    inputs.unmapped_crew = {ref: name for name, ref in sorted(references['unmappedCrew'].items(), key=lambda item: ref_number(item[1]))}
    inputs.v1 = parse_v1((root / pins['v1Release']['path']).parent)
    manifest_path = root / pins['v2Target']['path']
    manifest = read_json(manifest_path)
    people = {}
    for page in manifest['pages']:
        people.update(parse_v2((manifest_path.parent / page['filename']).read_bytes().decode('utf-8')))
    if len(people) != manifest['count']:
        raise MappingFailure(f'the pages of {manifest["datasetVersion"]} hold {len(people)} people, the manifest says {manifest["count"]}')
    inputs.v2_target = people
    inputs.mapping_exceptions = read_json(root / pins['mappingExceptions']['path'])['entries']
    inputs.migration_exceptions = read_json(root / pins['migrationExceptions']['path'])['entries']
    inputs.participant_exceptions = read_json(root / pins['participantExceptions']['path'])['entries']
    return inputs, references


def load_release_inputs(root=DEFAULT_ROOT):
    """Read every pinned input of mapping release 1.2: the Missions dataset release 1.1 recipe (crew and participant references), the
    legacy crew release, the three exceptions tables and the pages of the large Personnel v2 snapshot."""
    inputs, references = _load_release_common(root, RELEASE_PINS)
    inputs.participants = dict(sorted(references['participants'].items(), key=lambda item: reference_key(item[0])))
    return inputs


def load_release_13_inputs(root=DEFAULT_ROOT):
    """Read every pinned input of mapping release 1.3. The crew side is that of release 1.2 (the recipe of Missions dataset release
    1.1 holds the crew references, which no later release changed). The participants are those of Missions dataset release 1.2, which
    classifies them by definition: participants.json there holds each reference with its class (P or O) and name."""
    inputs, _ = _load_release_common(root, RELEASE_13_PINS)
    classes = read_json(Path(root) / inputs.pins['participants']['path'])
    for ref, entry in classes.items():
        if reference_class(ref) != entry['class']:
            raise MappingFailure(f'{ref}: the Missions dataset release says class {entry["class"]!r}')
    inputs.participants = {ref: classes[ref]['name'] for ref in sorted(classes, key=reference_key)}
    return inputs


def release_results(inputs, strict=False):
    """The two tables of a release as (crew results, participant results). The crew references are those of the recipe; the
    references.unmappedCrew are NOT offered to the process, and the build fails if one of them turned out to have a roster entry.
    Strict (release 1.3): a participant nobody places is a failure."""
    results = map_references(inputs.references, inputs.mapping_exceptions, inputs.v2_target, v1=inputs.v1,
                             migration_exceptions=inputs.migration_exceptions)
    waiting = [r for r in results if r.outcome == 'MIGRATE']
    if waiting:
        raise MappingFailure('these people must be migrated to Personnel v2 first: '
                             + ', '.join(f'{r.ref} {r.name!r} ({r.v1_id})' for r in waiting))
    for ref, name in inputs.unmapped_crew.items():
        if ref in inputs.references:
            raise MappingFailure(f'{ref} is both a mapped and an unmapped crew reference of the recipe')
        if _exact(inputs.v2_target, name) or _exact(inputs.v1, name):
            raise MappingFailure(f'{ref} {name!r} is listed as unmapped crew, but the roster or the legacy release holds that name')
    return results, map_participants(inputs.participants, inputs.participant_exceptions, inputs.v2_target, strict=strict)


def _release_inputs_of(inputs, keys=None):
    return {key: {'hashing': entry['hashing'], 'sha256': entry['sha256']} for key, entry in inputs.pins.items()
            if isinstance(entry, dict) and 'path' in entry and (keys is None or key in keys)}


def build_release_crew_section(inputs, results=None, keys=None):
    results = results if results is not None else release_results(inputs)[0]
    return {
        'section': 'crew',
        'description': 'The Missions-local crew reference to the Personnel v2 identifier PRS-nnnn: the full resulting table.',
        'source': 'Built by federation/personnel-mapping/crew_mapping.py (release-large) from the pinned inputs below: the recipe of '
                  'Missions dataset release 1.1 (references.crew; references.unmappedCrew is not offered to the process), the mapping '
                  'exceptions table and the Personnel v2 snapshot personnel-v2-large-004. A reference with no entry has no mapping '
                  '(UNMAPPED).',
        'inputs': _release_inputs_of(inputs, keys),
        'controlledCases': {
            'NORMAL': [r.ref for r in results if r.outcome == 'NAME'],
            'EXCEPTION': [r.ref for r in results if r.outcome == 'EXCEPTION'],
            'UNMAPPED': list(inputs.unmapped_crew),
        },
        'entries': {r.ref: r.target for r in results},
    }


def build_release_participants_section(inputs, results=None):
    results = results if results is not None else release_results(inputs)[1]
    return {
        'section': 'participants',
        'description': 'The Missions-local participant reference P-n to the Personnel v2 identifier PRS-nnnn of a non-crew person on '
                       'the roster. An O-reference is refused by class and never has an entry.',
        'source': 'Built by federation/personnel-mapping/crew_mapping.py (release-large) from the pinned inputs below: the recipe of '
                  'Missions dataset release 1.1 (references.participants), the participant exceptions table and the Personnel v2 '
                  'snapshot personnel-v2-large-004. A P-reference with no entry has no mapping (UNMAPPED); an O-reference is '
                  'REFUSED_BY_CLASS and has no entry whatever its name.',
        'inputs': _release_inputs_of(inputs),
        'controlledCases': {
            'NORMAL': [r.ref for r in results if r.outcome == 'NAME'],
            'EXCEPTION': [r.ref for r in results if r.outcome == 'EXCEPTION'],
            'UNMAPPED': [r.ref for r in results if r.outcome == 'UNMAPPED'],
            'REFUSED_BY_CLASS': [r.ref for r in results if r.outcome == 'REFUSED'],
        },
        'entries': {r.ref: r.target for r in results if r.target},
    }


def build_release_large(inputs):
    """The four files of mapping release 1.2: assets.json is the release 1.1 file, unchanged (the recipe of Missions dataset release
    1.1 holds the same nine asset references), crew.json and participants.json are built by the process, and the manifest repeats the
    checked-against list of release 1.1 and adds Missions dataset release 1.1 and the large Personnel v2 snapshot."""
    root = inputs.root
    previous = root / 'federation/mapping-releases/1.1'
    assets = (previous / 'assets.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    crew_results, participant_results = release_results(inputs)
    files = {'assets.json': assets, 'crew.json': render(build_release_crew_section(inputs, crew_results)),
             'participants.json': render(build_release_participants_section(inputs, participant_results))}
    missions = root / 'uss-enterprise/missions/datasets/releases/1.1/manifest.json'
    target = root / inputs.pins['v2Target']['path']
    checked = list(read_json(previous / 'manifest.json')['checkedAgainst'])
    checked.append({'system': 'missions', 'artifact': 'dataset release manifest', 'version': '1.1', 'sha256': digest(missions, 'lf')})
    checked.append({'system': 'personnel', 'artifact': 'dataset snapshot', 'version': target.parent.name, 'sha256': digest(target, 'lf')})
    manifest = {'release': RELEASE_LARGE,
                'files': {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in sorted(files.items())},
                'checkedAgainst': checked}
    files['manifest.json'] = render(manifest)
    return files


def check_large(root):
    """Problems between the pins and the folder of release 1.2 on disk and what the process builds; empty when they agree."""
    root = Path(root)
    problems = check_pins(root, RELEASE_PINS)
    if problems:
        return problems
    expected = build_release_large(load_release_inputs(root))
    folder = root / 'federation/mapping-releases' / RELEASE_LARGE
    if not folder.is_dir():
        return [f'federation/mapping-releases/{RELEASE_LARGE} is missing']
    on_disk = {path.name for path in folder.iterdir()}
    problems = [f'federation/mapping-releases/{RELEASE_LARGE}/{name} is ' + ('extra' if name in on_disk else 'missing')
                for name in sorted(on_disk ^ set(expected))]
    for name, text in expected.items():
        path = folder / name
        if path.is_file() and path.read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text:
            problems.append(f'federation/mapping-releases/{RELEASE_LARGE}/{name} differs from what the process builds')
    return problems


# ---- the mapping release 1.3: the participants of Missions dataset release 1.2 -----------------------------------------------

CREW_KEYS = ('recipe', 'v1Release', 'v2Target', 'mappingExceptions', 'migrationExceptions', 'participantExceptions')
PARTICIPANT_KEYS = ('participants', 'v2Target', 'participantExceptions')


def build_release_13_participants_section(inputs, results):
    return {
        'section': 'participants',
        'description': 'The Missions-local participant reference P-n to the Personnel v2 identifier PRS-nnnn of a non-crew person on '
                       'the roster: every P-reference of the Missions data resolves. An O-reference is refused by class and never has '
                       'an entry.',
        'source': 'Built by federation/personnel-mapping/crew_mapping.py (release-13) from the pinned inputs below: the participants of '
                  'Missions dataset release 1.2 (participants.json, each reference with its class), the participant exceptions table '
                  'and the Personnel v2 snapshot personnel-v2-large-004. A P-reference that nobody places fails the build; an '
                  'O-reference is REFUSED_BY_CLASS and has no entry whatever its name.',
        'inputs': _release_inputs_of(inputs, PARTICIPANT_KEYS),
        'controlledCases': {
            'NORMAL': [r.ref for r in results if r.outcome == 'NAME'],
            'EXCEPTION': [r.ref for r in results if r.outcome == 'EXCEPTION'],
            'REFUSED_BY_CLASS': [r.ref for r in results if r.outcome == 'REFUSED'],
        },
        'entries': {r.ref: r.target for r in results if r.target},
    }


def build_release_13(inputs):
    """The four files of mapping release 1.3: assets.json and crew.json are those of release 1.2 byte for byte (the crew side and the
    assets did not change), participants.json is built by the process in strict mode for the participants of Missions dataset release
    1.2, and the manifest repeats the checked-against list of release 1.2 and adds Missions dataset release 1.2."""
    root = inputs.root
    previous = root / 'federation/mapping-releases' / RELEASE_LARGE
    assets = (previous / 'assets.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    crew_results, participant_results = release_results(inputs, strict=True)
    crew = render(build_release_crew_section(inputs, crew_results, CREW_KEYS))
    if crew != (previous / 'crew.json').read_bytes().replace(b'\r\n', b'\n').decode('utf-8'):
        raise MappingFailure(f'the crew section no longer equals that of release {RELEASE_LARGE}: the crew side of release {RELEASE_13} is '
                             'unchanged by definition')
    files = {'assets.json': assets, 'crew.json': crew,
             'participants.json': render(build_release_13_participants_section(inputs, participant_results))}
    missions = root / 'uss-enterprise/missions/datasets/releases/1.2/manifest.json'
    checked = list(read_json(previous / 'manifest.json')['checkedAgainst'])
    checked.append({'system': 'missions', 'artifact': 'dataset release manifest', 'version': '1.2', 'sha256': digest(missions, 'lf')})
    manifest = {'release': RELEASE_13,
                'files': {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in sorted(files.items())},
                'checkedAgainst': checked}
    files['manifest.json'] = render(manifest)
    return files


def check_13(root):
    """Problems between the pins and the folder of release 1.3 on disk and what the process builds; empty when they agree."""
    root = Path(root)
    problems = check_pins(root, RELEASE_13_PINS)
    if problems:
        return problems
    expected = build_release_13(load_release_13_inputs(root))
    folder = root / 'federation/mapping-releases' / RELEASE_13
    if not folder.is_dir():
        return [f'federation/mapping-releases/{RELEASE_13} is missing']
    on_disk = {path.name for path in folder.iterdir()}
    problems = [f'federation/mapping-releases/{RELEASE_13}/{name} is ' + ('extra' if name in on_disk else 'missing')
                for name in sorted(on_disk ^ set(expected))]
    for name, text in expected.items():
        path = folder / name
        if path.is_file() and path.read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text:
            problems.append(f'federation/mapping-releases/{RELEASE_13}/{name} differs from what the process builds')
    return problems


# ---- commands ------------------------------------------------------------------------------------------------------------------

def migration_text(inputs):
    results = map_references(inputs.references, inputs.mapping_exceptions, inputs.v2_source, v1=inputs.v1,
                             migration_exceptions=inputs.migration_exceptions, allow_pending=True)
    return migrate(inputs.v2_source_text, inputs.v1, results, Path(inputs.pins['v2Target']['path']).stem)


def check_all(root):
    problems = check_pins(root)
    if problems:
        return problems
    inputs = load_inputs(root)
    problems = []
    if migration_text(inputs).encode('utf-8') != (root / inputs.pins['v2Target']['path']).read_bytes():
        problems.append('the migration does not reproduce the target snapshot')
    folder = root / 'federation/mapping-releases' / RELEASE
    for name, text in build_release(inputs).items():
        path = folder / name
        if not path.is_file() or path.read_bytes().replace(b'\r\n', b'\n').decode('utf-8') != text:
            problems.append(f'federation/mapping-releases/{RELEASE}/{name} differs from what the process builds')
    return problems


def write_pins(root, pins_file=PINS):
    path = root / pins_file
    pins = read_json(path)
    for entry in pins.values():
        if isinstance(entry, dict) and 'path' in entry and (root / entry['path']).is_file():
            entry['sha256'] = digest(root / entry['path'], entry['hashing'])
    path.write_bytes(render(pins).encode('utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('check', 'migrate', 'build-crew', 'release', 'pins', 'large', 'release-large', 'check-large',
                                            'release-13', 'check-13'))
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--pins-file', default=PINS, help='the pins file the pins command reads (default: the pins of the mapping release 1.1)')
    parser.add_argument('--root', default=str(DEFAULT_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == 'pins':
            if not args.write:
                print('\n'.join(check_pins(root, args.pins_file)) or 'ok: every pin holds')
                return 0
            write_pins(root, args.pins_file)
            print(args.pins_file + ' recomputed')
            return 0
        if args.command == 'check-large':
            problems = check_large(root)
            print('\n'.join('FAIL: ' + p for p in problems) if problems else 'ok: pins and mapping release ' + RELEASE_LARGE + ' agree')
            return 1 if problems else 0
        if args.command == 'check-13':
            problems = check_13(root)
            print('\n'.join('FAIL: ' + p for p in problems) if problems else 'ok: pins and mapping release ' + RELEASE_13 + ' agree')
            return 1 if problems else 0
        if args.command == 'release-13':
            files = build_release_13(load_release_13_inputs(root))
            folder = root / 'federation/mapping-releases' / RELEASE_13
            if args.write:
                if folder.exists():
                    raise MappingFailure(f'federation/mapping-releases/{RELEASE_13} exists: a published release is never overwritten')
                folder.mkdir(parents=True)
                for name, text in files.items():
                    (folder / name).write_bytes(text.encode('utf-8'))
                print('wrote', folder.relative_to(root).as_posix())
            else:
                for name, text in files.items():
                    print('--', name, len(text), 'bytes')
            return 0
        if args.command == 'release-large':
            files = build_release_large(load_release_inputs(root))
            folder = root / 'federation/mapping-releases' / RELEASE_LARGE
            if args.write:
                if folder.exists():
                    raise MappingFailure(f'federation/mapping-releases/{RELEASE_LARGE} exists: a published release is never overwritten')
                folder.mkdir(parents=True)
                for name, text in files.items():
                    (folder / name).write_bytes(text.encode('utf-8'))
                print('wrote', folder.relative_to(root).as_posix())
            else:
                for name, text in files.items():
                    print('--', name, len(text), 'bytes')
            return 0
        if args.command == 'check':
            problems = check_all(root)
            print('\n'.join('FAIL: ' + p for p in problems) if problems else 'ok: pins, migration and mapping release ' + RELEASE + ' agree')
            return 1 if problems else 0
        if args.command == 'migrate':
            inputs = load_inputs(root, verify_target=False)
            text = migration_text(inputs)
            target = root / inputs.pins['v2Target']['path']
            if args.write:
                target.write_bytes(text.encode('utf-8'))
                print('wrote', inputs.pins['v2Target']['path'], '(run pins --write next)')
            else:
                same = target.is_file() and target.read_bytes() == text.encode('utf-8')
                print('ok: the migration reproduces the target snapshot' if same else 'FAIL: the migration differs from the target snapshot')
                return 0 if same else 1
            return 0
        if args.command == 'large':
            if args.write:
                folder = root / LARGE_FOLDER
                if folder.exists():
                    raise MappingFailure(f'{LARGE_FOLDER} exists: a published dataset is never overwritten')
                files = large_files(root)
                folder.mkdir(parents=True)
                for name, data in files.items():
                    (folder / name).write_bytes(data)
                print('wrote', LARGE_FOLDER, f'({len(files)} files)')
                return 0
            problems = compare_large(root)
            print('\n'.join('FAIL: ' + p for p in problems) if problems else 'ok: the batch reproduces ' + LARGE_VERSION + ' byte for byte')
            return 1 if problems else 0
        inputs = load_inputs(root)
        if args.command == 'build-crew':
            print(render(build_crew_section(inputs)), end='')
            return 0
        files = build_release(inputs)
        folder = root / 'federation/mapping-releases' / RELEASE
        if args.write:
            folder.mkdir(parents=True, exist_ok=True)
            for name, text in files.items():
                (folder / name).write_bytes(text.encode('utf-8'))
            print('wrote', folder.relative_to(root).as_posix())
        else:
            for name, text in files.items():
                print('--', name, len(text), 'bytes')
        return 0
    except MappingFailure as failure:
        print('FAIL: ' + str(failure), file=sys.stderr)
        for match in failure.matches:
            print('  match: ' + match, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
