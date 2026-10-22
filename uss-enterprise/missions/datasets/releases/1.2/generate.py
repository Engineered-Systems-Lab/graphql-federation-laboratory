"""Missions release 1.2 authoring. Never invoked by startup or reset.

Release 1.2 APPENDS to release 1.1 and reclassifies the participants by the Captain's definitions of the Missions reference
classes (C crew, P on-board non-crew Personnel, O Outsiders). Every missionId and changeId of 1.1 is kept. The 300 missions
and the 865 change entries of 1.1 are read from the archived release 1.1; a mission whose participants change gets the corrected
participantIds, the new lastUpdated and currentChangeId, and one appended UPDATED correction entry with a change id after
1.1's last. The 1.1 change entries are in 1.2 byte for byte.

A P reference names a civilian of the Personnel v2 roster by exact display name; the names are archived in civilians.json (an
authoring step reads them once from personnel-v2-large-004 and pins its manifest by hash, so the generator itself reads only
archived inputs and the dataset has no runtime coupling to Personnel). An O reference names an outsider and never maps.

Algorithm and formats are frozen by recipe.json plus this generator's canonical Git-content SHA256 in the manifest.
Publishing is explicit and refuses reuse. Only the standard library is required.
  generate   --output DIR        write a fresh candidate release directory
  references --personnel-dir DIR --output DIR
                                 derive civilians.json from the released Personnel v2 pages (authoring step)
"""
from pathlib import Path
import argparse
import glob
import hashlib
import importlib.util
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
COMPONENT = HERE.parents[2]
PREVIOUS = HERE.parent / '1.1'
GEN3 = 'missions-generator-3'
CATEGORIES = ('participant_outsider', 'participant_pool', 'participant_roster')
PERSONNEL = 'personnel-v2-large-004'
PNS = '{urn:graphql-federation-lab:personnel:v2}'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The writers and the byte rules of release 1.1 are reused unchanged: the archived 1.1 generator is the one source of the formats.
G11 = load_module(PREVIOUS / 'generate.py', 'missions_generator_11')
canonical, digest, source_bytes = G11.canonical, G11.digest, G11.source_bytes


class Stream:
    def __init__(self, category, key='', item='', master=1701):
        if category not in CATEGORIES:
            raise ValueError('Unknown category')
        material = json.dumps([GEN3, master, category, key, item], ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        self.seed = hashlib.sha256(material).digest()
        self.counter = 0

    def integer(self, lo, hi):
        if lo > hi:
            raise ValueError('Draw bounds cannot fit declared constraints')
        span = hi - lo + 1
        if span > 1 << 256:
            raise ValueError('Draw span exceeds 256-bit algorithm')
        limit = (1 << 256) - (1 << 256) % span
        while True:
            value = int.from_bytes(hashlib.sha256(self.seed + self.counter.to_bytes(8, 'big')).digest(), 'big')
            self.counter += 1
            if value < limit:
                return lo + value % span

    def pick(self, seq):
        return seq[self.integer(0, len(seq) - 1)]

    def distinct(self, seq, count):
        """count different members of seq, drawn one by one without replacement."""
        if count > len(seq):
            raise ValueError('The pool is smaller than the number of participants')
        rest = list(seq)
        return [rest.pop(self.integer(0, len(rest) - 1)) for _ in range(count)]


# ---------------------------------------------------------------------------------------------------------------------
# The Personnel civilians (authoring step) ----------------------------------------------------------------------------

def read_civilians(directory):
    """The civilians of the released Personnel v2 pages in file order: display name and position title, nothing else."""
    rows, crew = [], []
    for page in sorted(glob.glob(str(Path(directory) / 'page-*.xml'))):
        for member in ET.fromstring(Path(page).read_bytes()):
            if member.tag != PNS + 'personnelMember':
                continue
            name, title = member.find(PNS + 'displayName').text, member.find(PNS + 'positionTitle').text
            (rows if member.find(PNS + 'civilianDetails') is not None else crew).append({'name': name, 'positionTitle': title})
    names = [row['name'] for row in rows]
    if len(set(names)) != len(names):
        raise ValueError('A civilian display name is not unique')
    if set(names) & {row['name'] for row in crew}:
        raise ValueError('A display name is both a civilian and a crew member')
    return rows


def derive_civilians(directory):
    directory = Path(directory)
    manifest = source_bytes(directory / 'manifest.json')
    return {'dataset': PERSONNEL, 'manifestSha256': digest(manifest), 'civilians': read_civilians(directory),
            'note': 'Display names and position titles of the civilians of the pinned snapshot, read once by the authoring step. '
                    'No Personnel identifier is kept: a P reference names a civilian by exact display name only.'}


# ---------------------------------------------------------------------------------------------------------------------
# The reclassification ------------------------------------------------------------------------------------------------

def outsider_names(recipe, taken):
    """The named synthetic outsiders of each pool. Drawn from syllable tables by an independent stream per pool member, with
    further draws from the same stream on a collision, and never equal to a civilian or crew display name."""
    pools = {}
    used = set(taken)
    for kind, spec in recipe['outsiderPools'].items():
        names = []
        for index in range(spec['count']):
            s = Stream('participant_outsider', kind, str(index))
            while True:
                name = s.pick(recipe['syllables']['given']) + s.pick(recipe['syllables']['givenEnd']) + ' ' + \
                       s.pick(recipe['syllables']['family']) + s.pick(recipe['syllables']['familyEnd'])
                if name not in used:
                    break
            used.add(name)
            names.append(name)
        pools[kind] = names
    return pools


def classify_routine(mission, source, recipe):
    """The class and the pool or position list the recipe gives a generated mission, by title first and then by template."""
    for rule in recipe['titleRules']:
        if mission['title'].startswith(rule['prefix']):
            return rule
    for rule in recipe['templateRules']:
        if source.get('template') in rule['templates']:
            return rule
    raise ValueError('No participant rule for ' + mission['missionId'] + ' ' + mission['title'])


def reclassify(previous, provenance, old_names, recipe, civilians, crew_names):
    """Return (missions, corrections, table): the missions with their new participantIds, the list of (missionId, before, after)
    for the missions that changed, and the participant table of the release (reference -> entry)."""
    pools = outsider_names(recipe, [c['name'] for c in civilians] + sorted(crew_names))
    civ_names = [c['name'] for c in civilians]
    canon = recipe['canon']
    keys_by_mission = []
    drawn_pool, drawn_roster = set(), set()
    for mission, source in zip(previous['missions'], provenance['missionSources']):
        old = mission['participantIds']
        if not old:
            keys_by_mission.append(None)
        elif source['origin'] in ('canon-carried', 'canon'):
            missing = [ref for ref in old if ref not in canon]
            if missing:
                raise ValueError('A curated mission uses a participant the recipe does not classify: ' + mission['missionId'] + ' ' + str(missing))
            keys_by_mission.append([('keep' if canon[ref]['class'] == 'keep' else 'canon', ref) for ref in old])
        else:
            if not all('placeholder' in old_names.get(ref, '') for ref in old):
                raise ValueError('A generated mission names a participant the recipe does not replace: ' + mission['missionId'])
            rule = classify_routine(mission, source, recipe)
            if rule['class'] == 'O':
                s = Stream('participant_pool', mission['missionId'])
                keys = [('pool', rule['pool'], i) for i in s.distinct(range(recipe['outsiderPools'][rule['pool']]['count']), len(old))]
                drawn_pool.update(keys)
            else:
                s = Stream('participant_roster', mission['missionId'])
                candidates = [c['name'] for c in civilians if c['name'] not in crew_names and (rule.get('positions') is None or c['positionTitle'] in rule['positions'])]
                keys = [('roster', name) for name in s.distinct(candidates, len(old))]
                drawn_roster.update(keys)
            keys_by_mission.append(keys)
    # numbering: the reclassified canon people in the order of their old reference, then the outsiders drawn from the pools in pool
    # order, then the civilians drawn in the order of the Personnel pages; a fixed step, each number used once
    refs, table = {}, {}
    number = recipe['numbering']['start']
    def allocate(key, entry):
        nonlocal number
        ref = '%s-%d' % (entry['class'], number)
        number += recipe['numbering']['step']
        refs[key] = ref
        table[ref] = entry
    for old in sorted(canon, key=lambda ref: int(ref[2:])):
        decision = canon[old]
        if decision['class'] == 'keep':
            refs[('keep', old)] = old
            table[old] = {'class': old[0], 'name': decision['name'], 'origin': 'kept'}
        else:
            entry = {'class': decision['class'], 'name': decision['name'], 'origin': 'reclassified', 'was': old}
            if decision.get('offRoster'):
                entry['offRosterOnBoardCivilian'] = True
            allocate(('canon', old), entry)
    for kind in recipe['outsiderPools']:
        for index in sorted(i for (tag, k, i) in drawn_pool if k == kind):
            allocate(('pool', kind, index), {'class': 'O', 'name': pools[kind][index], 'origin': 'synthetic-outsider', 'kind': kind, 'synthetic': True})
    for name in civ_names:
        if ('roster', name) in drawn_roster:
            allocate(('roster', name), {'class': 'P', 'name': name, 'origin': 'personnel-roster'})
    missions, corrections = [], []
    for mission, keys in zip(previous['missions'], keys_by_mission):
        if keys is None:
            missions.append(mission)
            continue
        ids = sorted({refs[key] for key in keys})
        if len(ids) != len(mission['participantIds']):
            raise ValueError('The participants of a mission changed in number: ' + mission['missionId'])
        missions.append(dict(mission, participantIds=ids))
        if ids != mission['participantIds']:
            corrections.append((mission['missionId'], mission['participantIds'], ids))
    used = {ref for m in missions for ref in m['participantIds']}
    return missions, corrections, {ref: entry for ref, entry in table.items() if ref in used}


def check_classes(missions, table, civilians, crew_map):
    """The build-time check of the Captain's definitions: no C reference among the participants, every P reference names exactly one
    civilian of the pinned roster, and no O reference names a person on the roster or a crew member (an off-roster canon civilian is
    an O by necessity and is flagged in the table)."""
    civ = [c['name'] for c in civilians]
    crew_names = set(crew_map)
    problems = []
    used = set()
    for mission in missions:
        assigned = set(mission['assignedCrewIds']) | ({mission['commandingOfficerId']} if mission.get('commandingOfficerId') else set())
        for ref in mission['participantIds']:
            used.add(ref)
            if ref in table and table[ref]['name'] in crew_map and crew_map[table[ref]['name']] in assigned:
                problems.append(f'{mission["missionId"]}: {ref} is also assigned to the mission as crew')
            if ref.startswith('C-'):
                problems.append(f'{mission["missionId"]}: a crew reference among the participants: {ref}')
            elif ref not in table:
                problems.append(f'{mission["missionId"]}: {ref} is not in the participant table')
    for ref in sorted(used & set(table)):
        entry = table[ref]
        if entry['class'] != ref[0]:
            problems.append(f'{ref}: the class {entry["class"]} does not match the reference')
        if ref[0] == 'P' and civ.count(entry['name']) != 1:
            problems.append(f'{ref}: {entry["name"]!r} is not exactly one civilian of {PERSONNEL}')
        if ref[0] == 'O' and (entry['name'] in civ or entry['name'] in crew_names):
            problems.append(f'{ref}: {entry["name"]!r} is a person on the roster and cannot be an outsider')
    if set(table) != used:
        problems.append('the participant table holds references no mission uses: ' + str(sorted(set(table) - used))[:200])
    return problems


def generate():
    recipe = json.loads(source_bytes(HERE / 'recipe.json'))
    civilian_file = json.loads(source_bytes(HERE / 'civilians.json'))
    civilians = civilian_file['civilians']
    previous = json.loads(source_bytes(PREVIOUS / 'release.json'))
    provenance = json.loads(source_bytes(PREVIOUS / 'provenance.json'))
    previous_manifest = json.loads(source_bytes(PREVIOUS / 'manifest.json'))
    previous_recipe = json.loads(source_bytes(PREVIOUS / 'recipe.json'))
    crew_map = dict(previous_recipe['references']['crew'], **previous_recipe['references']['unmappedCrew'])
    crew_names = set(crew_map)
    old_names = previous_recipe['references']['participants']
    missions, corrections, table = reclassify(previous, provenance, old_names, recipe, civilians, crew_names)
    problems = check_classes(missions, table, civilians, crew_map)
    if problems:
        raise ValueError('Participant classes: ' + '; '.join(problems[:5]))
    # the appended correction entries
    clock = recipe['correction']
    start = G11.moment(clock['start'])
    refs = recipe['references']
    by_id = {m['missionId']: m for m in missions}
    last = {}
    for row in previous['changes']:
        last[row['missionId']] = row
    next_change = previous_manifest['nextChangeId']
    changes = list(previous['changes'])
    events = list(provenance['events'])
    log = []
    for index, (mission_id, old, new) in enumerate(corrections):
        m = by_id[mission_id]
        at = G11.stamp(start + G11.timedelta(minutes=index * clock['intervalMinutes']))
        prior = last[mission_id]
        p_count = sum(1 for ref in new if ref[0] == 'P')
        row = {'changeId': str(next_change + index), 'missionId': mission_id, 'operation': 'UPDATED', 'changedAt': at,
               'changedBy': refs['changedBy'], 'orderedBy': refs['orderedBy'], 'previousStatus': m['status'], 'newStatus': m['status'],
               'summary': clock['summary'].format(p=p_count, o=len(new) - p_count)}
        for field in ('estimatedCostCredits', 'actualCostCredits'):
            if prior.get(field) is not None:
                row[field] = prior[field]
                row[field + 'Change'] = '0.00'
        changes.append(row)
        m['lastUpdated'] = at
        m['currentChangeId'] = row['changeId']
        events.append({'changedAt': at, 'eventKey': 'correction-1', 'missionId': mission_id, 'objectiveRevision': False,
                       'provenance': 'Synthetic lab records clean-up: the participant references of the mission were corrected by release 1.2.',
                       'timing': 'correction'})
        log.append({'missionId': mission_id, 'changeId': row['changeId'], 'before': old, 'after': new})
    data = {'datasetVersion': recipe['datasetVersion'], 'contractRevision': '1.1', 'missions': missions, 'changes': changes}
    flagged = [{'ref': ref, 'name': e['name']} for ref, e in sorted(table.items()) if e.get('offRosterOnBoardCivilian')]
    limitations = list(provenance['limitations']) + [
        'Release 1.2 reclassifies the participants by the Captain\'s definitions (C crew, P on-board non-crew Personnel, O outsiders); '
        'releases 1.0 and 1.1 are unchanged and keep their classification as history.',
        'Every P reference names a civilian of ' + PERSONNEL + ' by exact display name; the names of the outsiders drawn from the pools '
        'are synthetic.',
        'On-board civilians of the canon missions who are not on the roster stay O by necessity: ' + ', '.join(f['name'] for f in flagged) + '.',
        'The correction entries are synthetic audit entries of a records clean-up; they carry no canon claim.']
    provenance_out = {'missionSources': provenance['missionSources'], 'events': events, 'edgeLedger': provenance['edgeLedger'],
                      'limitations': limitations, 'participantCorrections': log, 'offRosterCivilians': flagged,
                      'participantClasses': recipe['classes']}
    participants = {ref: table[ref] for ref in sorted(table, key=lambda r: (r[0], int(r[2:])))}
    counts = {'P': sum(1 for r in participants if r[0] == 'P'), 'O': sum(1 for r in participants if r[0] == 'O')}
    files = {'release.json': canonical(data), 'provenance.json': canonical(provenance_out), 'participants.json': canonical(participants)}
    files.update(G11.render_xml(data))
    files.update({name: source_bytes(HERE / name) for name in ('generate.py', 'recipe.json', 'civilians.json')})
    files['schema.sql'] = source_bytes(COMPONENT / 'schema/schema.sql')
    manifest = {'datasetVersion': recipe['datasetVersion'], 'contractRevision': '1.1', 'generatorVersion': recipe['generatorVersion'],
                'recipe': recipe,
                'sources': {name: digest(source_bytes(HERE / name)) for name in ('recipe.json', 'civilians.json', 'generate.py')},
                'contractSha256': digest(source_bytes(COMPONENT / 'contracts/missions-v1.1.xsd')),
                'preservedContract10Sha256': digest(source_bytes(COMPONENT / 'contracts/missions-v1.0.xsd')),
                'counts': {'missions': len(missions), 'changes': len(changes)},
                'firstMissionOrdinal': previous_manifest['firstMissionOrdinal'], 'firstChangeId': previous_manifest['firstChangeId'],
                'nextMissionOrdinal': previous_manifest['nextMissionOrdinal'], 'nextChangeId': next_change + len(corrections),
                'appendsTo': {'datasetVersion': '1.1', 'manifestSha256': digest(source_bytes(PREVIOUS / 'manifest.json')),
                              'missions': len(previous['missions']), 'changes': len(previous['changes']),
                              'earlierCuts': [previous_manifest['appendsTo']['changes']],
                              'nextMissionOrdinal': previous_manifest['nextMissionOrdinal'], 'nextChangeId': previous_manifest['nextChangeId']},
                'composition': previous_manifest['composition'],
                'corrections': {'count': len(corrections), 'firstChangeId': next_change, 'changedBy': refs['changedBy'],
                                'orderedBy': refs['orderedBy'], 'firstChangedAt': changes[len(previous['changes'])]['changedAt'],
                                'lastChangedAt': changes[-1]['changedAt']},
                'participantClasses': {'definitions': recipe['classes'], 'personnelDataset': PERSONNEL,
                                       'personnelManifestSha256': civilian_file['manifestSha256'], 'civilians': len(civilians),
                                       'referencesP': counts['P'], 'referencesO': counts['O']},
                'clock': {'baseline': max(r['changedAt'] for r in changes), 'counter': 0, 'intervalMs': 1000},
                'files': {name: digest(content) for name, content in files.items()}}
    files['load.sql'] = G11.render_sql(data, manifest)
    manifest['files']['load.sql'] = digest(files['load.sql'])
    files['manifest.json'] = canonical(manifest)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    g = sub.add_parser('generate')
    g.add_argument('--output', required=True, type=Path)
    r = sub.add_parser('references')
    r.add_argument('--personnel-dir', required=True, type=Path)
    r.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'generate':
        if args.output.exists():
            raise ValueError('Output already exists; immutable versions are never overwritten')
        files = generate()
        args.output.mkdir(parents=True)
        for name, content in files.items():
            (args.output / name).write_bytes(content)
        print('Authored candidate release; review and real acceptance remain required:', args.output)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'civilians.json').write_bytes(canonical(derive_civilians(args.personnel_dir)))
        print('Civilians derived:', len(read_civilians(args.personnel_dir)))


if __name__ == '__main__':
    main()
