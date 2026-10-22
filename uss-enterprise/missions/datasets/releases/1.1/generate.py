"""Missions release 1.1 authoring. Never invoked by startup or reset.

Release 1.1 APPENDS to release 1.0: the 31 missions of 1.0 keep their mission ids and change ids byte for byte
(they are produced here by the unchanged 1.0 algorithm, with generator 1's seed key), and the new missions get
mission ids after 1.0's last and change ids after 1.0's last, in the order of their own timestamps among
themselves. A new change entry can therefore carry an older changedAt than a lower change id; within each mission
the history stays chronological (the design: changeId, not time, is the mutation order).

Algorithm and formats are frozen by recipe.json plus this generator's canonical Git-content SHA256 in the manifest.
Publishing is explicit and refuses reuse. Only the standard library is required.
  generate   --output DIR        write a fresh candidate release directory
  references --crew-dir DIR --output DIR
                                 derive roster.json and the references of recipe.json from the released Personnel v1
                                 pages (authoring step; the generator itself reads only the archived inputs)
"""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import glob
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
COMPONENT = HERE.parents[2]
NS = 'urn:starfleet:missions:v1'
ET.register_namespace('', NS)
ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
GEN1 = 'missions-generator-1'
GEN2 = 'missions-generator-2'
CATEGORIES = ('mission_id_start', 'change_id_start', 'history_timing', 'estimated_cost', 'estimate_revision', 'actual_cost',
              'recipe_maintenance', 'recipe_routine', 'staffing_commander', 'staffing_crew', 'staffing_participants',
              'staffing_assets', 'crew_reference', 'edge_cases', 'change_density')
PAGE = 50
NAMED = ('Jean-Luc Picard', 'William Riker', 'Geordi La Forge', 'Data', 'Beverly Crusher', 'Deanna Troi', 'Wesley Crusher',
         'Reginald Barclay', 'Worf', 'Miles O\'Brien', 'Sonya Gomez', 'Guinan')
LEGACY_NAMES = {'Data': 'Data', 'La Forge': 'Geordi La Forge', 'Riker': 'William Riker', 'Troi': 'Deanna Troi', 'Picard': 'Jean-Luc Picard'}
SENIOR = ('CAPTAIN', 'COMMANDER', 'LIEUTENANT_COMMANDER')
TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED')
NEEDS_CO = ('AUTHORIZED', 'ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED')


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('utf-8')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def source_bytes(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


class Stream:
    def __init__(self, category, mission='', event='', master=1701, generation=GEN2):
        if category not in CATEGORIES:
            raise ValueError('Unknown category')
        key = json.dumps([generation, master, category, mission, event], ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        self.seed = hashlib.sha256(key).digest()
        self.counter = 0

    def integer(self, lo, hi):
        if lo > hi:
            raise ValueError('Timing/category bounds cannot fit declared constraints')
        span = hi - lo + 1
        if span > 1 << 256:
            raise ValueError("Draw span exceeds 256-bit algorithm")
        limit = (1 << 256) - (1 << 256) % span
        while True:
            value = int.from_bytes(hashlib.sha256(self.seed + self.counter.to_bytes(8, 'big')).digest(), 'big')
            self.counter += 1
            if value < limit:
                return lo + value % span

    def pick(self, seq):
        return seq[self.integer(0, len(seq) - 1)]

    def weighted(self, table):
        total = sum(weight for _, weight in table)
        draw = self.integer(1, total)
        for value, weight in table:
            draw -= weight
            if draw <= 0:
                return value


def mission_id(ordinal):
    if not 1 <= ordinal < 36 ** 9:
        raise ValueError('Mission ordinal overflow')
    suffix = ''
    while ordinal:
        ordinal, digit = divmod(ordinal, 36)
        suffix = ALPHABET[digit] + suffix
    return 'ST-' + suffix.zfill(9)


def stamp(value):
    return value.isoformat(timespec='milliseconds') + 'Z'


def moment(value):
    return datetime.fromisoformat(value.removesuffix('Z'))


def money(cents_value):
    return None if cents_value is None else ('-' if cents_value < 0 else '') + str(abs(cents_value) // 100) + '.' + str(abs(cents_value) % 100).zfill(2)


def cents(value):
    if value is None:
        return None
    sign = -1 if value.startswith('-') else 1
    whole, fraction = value.removeprefix('-').split('.')
    return sign * (int(whole) * 100 + int(fraction))


def band(kind):
    if kind == 'TACTICAL': return 10000000, 50000000
    if kind in ('DIPLOMATIC', 'FIRST_CONTACT'): return 1000000, 12000000
    if kind in ('MEDICAL', 'RESCUE', 'HUMANITARIAN', 'SECURITY', 'MAINTENANCE'): return 2500000, 20000000
    return 500000, 5000000


def element(root, name, value):
    if value is not None:
        ET.SubElement(root, '{' + NS + '}' + name).text = str(value)


def mission_xml(root, mission):
    item = ET.SubElement(root, '{' + NS + '}mission')
    for name in ('missionId', 'title', 'type', 'classification', 'status', 'priority', 'stardate', 'durationHours', 'objective'):
        element(item, name, mission[name])
    location = ET.SubElement(item, '{' + NS + '}location')
    for name in ('type', 'name', 'coordinates', 'travelVector'):
        element(location, name, mission['location'].get(name))
    element(item, 'issuingAuthority', mission['issuingAuthority'])
    element(item, 'commandingOfficerId', mission.get('commandingOfficerId'))
    for plural, singular in (('assignedCrewIds', 'crewId'), ('participantIds', 'participantId'), ('assignedAssetIds', 'assetId')):
        parent = ET.SubElement(item, '{' + NS + '}' + plural)
        for ref in mission[plural]: element(parent, singular, ref)
    for name in ('estimatedCostCredits', 'actualCostCredits', 'outcome', 'lastUpdated'):
        element(item, name, mission.get(name))


def render_xml(data):
    pages = {}
    rows = data['missions']
    for page, start in enumerate(range(0, len(rows), PAGE), 1):
        root = ET.Element('{' + NS + '}missionList')
        for name, value in (('page', page), ('pageSize', PAGE), ('totalCount', len(rows)), ('totalPages', (len(rows) + PAGE - 1) // PAGE)):
            element(root, name, value)
        for mission in rows[start:start + PAGE]: mission_xml(root, mission)
        pages[f'missions-{page}.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    rows = data['changes']
    for page, start in enumerate(range(0, len(rows), PAGE), 1):
        root = ET.Element('{' + NS + '}changeList')
        for name, value in (('page', page), ('pageSize', PAGE), ('totalCount', len(rows)), ('totalPages', (len(rows) + PAGE - 1) // PAGE)):
            element(root, name, value)
        for row in rows[start:start + PAGE]:
            item = ET.SubElement(root, '{' + NS + '}change')
            for name in ('changeId', 'missionId', 'operation', 'changedAt', 'changedBy', 'orderedBy', 'previousStatus', 'newStatus',
                         'estimatedCostCredits', 'estimatedCostCreditsChange', 'actualCostCredits', 'actualCostCreditsChange', 'summary'):
                element(item, name, row.get(name))
        pages[f'changes-{page}.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    return pages


def sql_string(value):
    if value is None: return 'NULL'
    if '\x00' in value or len(value.encode('utf-8')) > 3900:
        raise ValueError('Seed SQL literal must fit its reviewed statement format')
    return "'" + value.replace("'", "''") + "'"


def sql_timestamp(value):
    return 'NULL' if value is None else "TO_TIMESTAMP(" + sql_string(value) + ",'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"')"


def render_sql(data, manifest):
    lines = ['-- Immutable release load. Current schema must be operator-owned.', 'SET DEFINE OFF',
             "ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,';", "ALTER SESSION SET TIME_ZONE = '+00:00';"]
    for m in data['missions']:
        names = ['mission_id', 'title', 'mission_type', 'classification', 'status', 'priority', 'stardate', 'duration_hours', 'objective',
                 'location_type', 'location_name', 'coordinates', 'travel_vector', 'issuing_authority', 'commanding_officer_id',
                 'estimated_cost', 'actual_cost', 'outcome', 'last_updated', 'current_change_id', 'cancelled_without_estimate_allowed']
        values = [sql_string(m['missionId']), sql_string(m['title']), sql_string(m['type']), sql_string(m['classification']),
                  sql_string(m['status']), str(m['priority']), m['stardate'], str(m['durationHours']),
                  'TO_CLOB(' + sql_string(m['objective']) + ')', sql_string(m['location']['type']), sql_string(m['location']['name']),
                  sql_string(m['location'].get('coordinates')), sql_string(m['location'].get('travelVector')),
                  sql_string(m['issuingAuthority']), sql_string(m.get('commandingOfficerId')),
                  m.get('estimatedCostCredits') or 'NULL', m.get('actualCostCredits') or 'NULL',
                  'TO_CLOB(' + sql_string(m.get('outcome')) + ')', sql_timestamp(m['lastUpdated']), m['currentChangeId'],
                  str(int(m['cancelledWithoutEstimateAllowed']))]
        lines.append('INSERT INTO missions (' + ','.join(names) + ') VALUES (' + ','.join(values) + ');')
        for key, table in (('assignedCrewIds', 'mission_assigned_crew'), ('participantIds', 'mission_participants'), ('assignedAssetIds', 'mission_assigned_assets')):
            for ref in m[key]: lines.append('INSERT INTO ' + table + ' VALUES (' + sql_string(m['missionId']) + ',' + sql_string(ref) + ');')
    for row in data['changes']:
        values = [row['changeId'], sql_string(row['missionId']), sql_string(row['operation']), sql_timestamp(row['changedAt']),
                  sql_string(row['changedBy']), sql_string(row['orderedBy']), sql_string(row.get('previousStatus')), sql_string(row['newStatus']),
                  row.get('estimatedCostCredits') or 'NULL', row.get('estimatedCostCreditsChange') or 'NULL',
                  row.get('actualCostCredits') or 'NULL', row.get('actualCostCreditsChange') or 'NULL', sql_string(row['summary'])]
        lines.append('INSERT INTO mission_changes VALUES (' + ','.join(values) + ');')
    clock = manifest['clock']
    lines.append('INSERT INTO mission_clock VALUES (1,' + sql_timestamp(clock['baseline']) + ',0,1000,' + sql_string(manifest['datasetVersion']) + ',' + sql_string(manifest['files']['release.json']) + ');')
    lines.extend(['COMMIT;', 'DROP SEQUENCE mission_id_seq;', 'DROP SEQUENCE change_id_seq;',
                  f"CREATE SEQUENCE mission_id_seq START WITH {manifest['nextMissionOrdinal']} MINVALUE 1 MAXVALUE {36 ** 9 - 1} INCREMENT BY 1 NOCACHE NOCYCLE;",
                  f"CREATE SEQUENCE change_id_seq START WITH {manifest['nextChangeId']} MINVALUE 1 MAXVALUE {10 ** 28 - 1} INCREMENT BY 1 NOCACHE NOCYCLE;"])
    return ('\n'.join(lines) + '\n').encode('utf-8')


# ---------------------------------------------------------------------------------------------------------------------
# References (authoring step) -----------------------------------------------------------------------------------------

def read_v1_crew(directory):
    rows = []
    for page in sorted(glob.glob(str(Path(directory) / 'page-*.xml'))):
        text = Path(page).read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
        for block in re.findall(r'<cp:crewMember>(.*?)</cp:crewMember>', text, re.S):
            def field(name):
                found = re.search(r'<cp:%s>(.*?)</cp:%s>' % (name, name), block)
                return found.group(1) if found else None
            rows.append({'crewId': field('crewId'), 'name': field('displayName'), 'rank': field('rank'), 'department': field('department'),
                         'dutyStatus': field('dutyStatus')})
    return rows


def derive_references(directory, recipe):
    """Number the Missions-local crew references of the 800 and of the canon people who are not among them.

    The ten references of release 1.0 are kept for the same people. Every other number is drawn by the crew_reference
    stream keyed by the v1 crew id (a fixed hash of the id, then deterministic probing upward on a collision, people
    taken in ascending v1 crew id), in 135..9999, and never equals the numeric suffix of that person's v1 id. Nothing
    is derived from a PRS number."""
    rows = sorted(read_v1_crew(directory), key=lambda row: row['crewId'])
    cast = {name: ref for name, ref in recipe['references']['castKept'].items()}
    used = {int(ref[2:]) for ref in cast.values()}
    crew, roster = {}, {}
    for row in rows:
        suffix = int(row['crewId'].split('-')[1])
        if row['name'] in cast:
            ref = cast[row['name']]
        else:
            n = 135 + Stream('crew_reference', row['crewId']).integer(0, 9999 - 135)
            while n in used or n == suffix:
                n = 135 if n >= 9999 else n + 1
            used.add(n)
            ref = 'C-%d' % n
        if row['name'] in crew:
            raise ValueError('Duplicate display name; the crew mapping matches exact names')
        crew[row['name']] = ref
        roster[ref] = {'rank': row['rank'], 'department': row['department'], 'dutyStatus': row['dutyStatus']}
    unmapped = {}
    for name in recipe['references']['unmappedNames']:
        n = 135 + Stream('crew_reference', 'unmapped:' + name).integer(0, 9999 - 135)
        while n in used:
            n = 135 if n >= 9999 else n + 1
        used.add(n)
        unmapped[name] = 'C-%d' % n
        roster['C-%d' % n] = {'rank': recipe['references']['unmappedRank'][name], 'department': 'OPERATIONS', 'dutyStatus': 'ACTIVE', 'mapped': False}
    return crew, unmapped, roster


# ---------------------------------------------------------------------------------------------------------------------
# History engine for the new missions ---------------------------------------------------------------------------------

def first_audit(stardate, offset_minutes=0):
    days = int((int(stardate.replace('.', '')) - 4300000) * 365 // 100000)
    at = datetime(2366, 1, 1, 8, 0) + timedelta(days=days)
    ceiling = datetime(2368, 12, 20, 8, 0)
    return min(at, ceiling) + timedelta(minutes=offset_minutes)


PREFIX = {'Geordi La Forge': 'Log: ', 'William Riker': 'Report: '}


def author_history(item, mid, recipe):
    """Author the change entries of one new mission. item has resolved references and explicit events."""
    typ = item['type']
    duration = item['durationHours'] * 60
    timing = 'planning' if item['finalStatus'] == 'PLANNED' else 'urgent' if item['priority'] <= 2 else 'routine'
    lo, hi = recipe['timeBandsMinutes'][timing]
    first = item['firstAudit']
    elapsed = 0
    estimate = None
    actual = None
    previous = None
    rows = []
    notes = []
    events = item['events']
    flagged_from_planned = False
    for index, event in enumerate(events):
        key, status = event['key'], event['status']
        closure = status in TERMINAL and index == len(events) - 1
        if index:
            if closure:
                elapsed = duration
            else:
                remaining = len(events) - 1 - index
                ceiling = min(hi, duration - elapsed - max(1, remaining) * lo)
                elapsed += Stream('history_timing', mid, key).integer(lo, ceiling)
        at = first + timedelta(minutes=elapsed)
        before_estimate, before_actual = estimate, actual
        withdrawn_unestimated = status == 'CANCELLED' and previous == 'PLANNED' and estimate is None
        if (status != 'PLANNED' and not withdrawn_unestimated) or item.get('plannedEstimate'):
            if estimate is None:
                low, high = item.get('estimateBand') or band(typ)
                estimate = Stream('estimated_cost', mid, 'initial').integer(low, high)
            elif event.get('revise'):
                estimate = (estimate * Stream('estimate_revision', mid, key).integer(1100, 1350) + 500) // 1000
        if closure:
            if status == 'CANCELLED':
                if estimate is None:
                    actual = 0
                else:
                    actual = (estimate * Stream('actual_cost', mid, key).integer(200, 600) + 500) // 1000
            else:
                actual = (estimate * Stream('actual_cost', mid, key).integer(800, 1350) + 500) // 1000
        changed_by = item['changedBy']
        if index == 0:
            summary = item.get('summaryOverride') or 'Initial objective: ' + item['objective']
        else:
            summary = PREFIX.get(item.get('changedByName'), 'Recorded: ') + event['action'].split(';')[0] + '.'
            if event.get('revise'):
                summary = PREFIX.get(item.get('changedByName'), 'Recorded: ') + event['action'].replace('; ', ', ') + '.'
        if len(summary) > 256:
            raise ValueError('Author a shorter complete summary for ' + item['key'] + '/' + key)
        row = {'missionId': mid, 'operation': 'CREATED' if index == 0 else 'UPDATED', 'changedAt': stamp(at), 'changedBy': changed_by,
               'orderedBy': item['orderedBy'], 'newStatus': status, 'summary': summary}
        if previous is not None: row['previousStatus'] = previous
        for field, value, before in (('estimatedCostCredits', estimate, before_estimate), ('actualCostCredits', actual, before_actual)):
            if value is not None:
                row[field] = money(value)
                if before is not None: row[field + 'Change'] = money(value - before)
        row['_sort'] = (stamp(at), mid, index)
        rows.append(row)
        notes.append({'missionId': mid, 'eventKey': key, 'changedAt': stamp(at), 'timing': 'duration-closure' if closure else timing,
                      'objectiveRevision': False, 'provenance': 'Synthetic lab event/recorder/style/cost/timestamp.'})
        previous = status
    if item['finalStatus'] == 'CANCELLED':
        flagged_from_planned = len(events) >= 2 and events[-2]['status'] == 'PLANNED'
    return rows, notes, estimate, actual, flagged_from_planned


# ---------------------------------------------------------------------------------------------------------------------
# Legacy: the 31 missions of release 1.0, by the unchanged 1.0 algorithm -----------------------------------------------

def author_legacy(inputs, recipe, start, change_start):
    crew = recipe['references']['crew']
    ref = lambda short: crew[LEGACY_NAMES[short]]
    missions, changes, event_times, metadata = [], [], {}, []
    for index, item in enumerate(inputs):
        mid = mission_id(start + index)
        first = moment(item['firstAuditDate'])
        edge = next((e for e in recipe['causalEdges'] if e['to'] == item['key']), None)
        if edge:
            first = max(first, event_times[(edge['from'], edge['event'])] + timedelta(minutes=Stream('history_timing', mid, 'causal-start', generation=GEN1).integer(5, 45)))
        typ = item['type']
        duration = item['durationHours'] * 60
        timing = 'planning' if item['finalStatus'] == 'PLANNED' else 'urgent' if item['priority'] <= 2 else 'routine'
        lo, hi = recipe['timeBandsMinutes'][timing]
        elapsed = 0
        estimate = None
        actual = None
        previous = None
        local = []
        objective = item['objective']
        for event_index, event in enumerate(item['events']):
            key = event['key']
            status = event['status']
            closure = status in TERMINAL and event_index == len(item['events']) - 1
            if event_index:
                if closure:
                    elapsed = duration
                else:
                    remaining = len(item['events']) - 1 - event_index
                    ceiling = min(hi, duration - elapsed - max(1, remaining) * lo)
                    elapsed += Stream('history_timing', mid, key, generation=GEN1).integer(lo, ceiling)
            at = first + timedelta(minutes=elapsed)
            event_times[(item['key'], key)] = at
            before_estimate, before_actual = estimate, actual
            if status != 'PLANNED' or (item['plannedEstimate'] and event_index == len(item['events']) - 1):
                if estimate is None:
                    estimate = Stream('estimated_cost', mid, 'initial', generation=GEN1).integer(*band(typ))
                elif re.search(r'(estimate|raises? E|E revised|raises?\b|E\d)', event['action'], re.I):
                    estimate = (estimate * Stream('estimate_revision', mid, key, generation=GEN1).integer(1100, 1350) + 500) // 1000
            if closure:
                ratio = Stream('actual_cost', mid, key, generation=GEN1).integer(200, 600) if status == 'CANCELLED' else Stream('actual_cost', mid, key, generation=GEN1).integer(800, 1350)
                actual = (estimate * ratio + 500) // 1000
            revised = (item['key'] == 'candidate-15' and event_index == 2) or (item['key'] == 'candidate-14' and event_index == 2)
            changed_by = item['commandingOfficerId'] or ref('Data')
            if revised:
                if item['key'] == 'candidate-15':
                    objective = 'Identify the cause and spread of shipboard contamination and recommend containment.'
                    changed_by = ref('La Forge')
                    summary = 'Objective update: ' + objective
                else:
                    objective = "Establish safe communication and assess the entity's intentions with attention to contact risks."
                    changed_by = ref('Troi')
                    summary = 'The objective of the mission has drifted to: ' + objective
            elif event_index == 0:
                summary = 'Initial objective: ' + objective
                if edge: summary += ' Follow-on to mission ' + missions[[i['key'] for i in inputs].index(edge['from'])]['missionId'] + '.'
            else:
                action = event['action'].split(';')[0]
                action = re.sub(r'E?\d+\.\d{2}', money(estimate) or 'pending', action)
                prefix = 'Log: ' if changed_by == ref('La Forge') else 'Report: ' if changed_by == ref('Riker') else 'Recorded: '
                summary = prefix + action + '.'
            if len(summary) > 256:
                raise ValueError('Author a shorter complete summary for ' + item['key'] + '/' + key)
            row = {'missionId': mid, 'operation': 'CREATED' if event_index == 0 else 'UPDATED', 'changedAt': stamp(at),
                   'changedBy': changed_by, 'orderedBy': ref('Picard'), 'newStatus': status, 'summary': summary}
            if previous is not None: row['previousStatus'] = previous
            for field, value, before in (('estimatedCostCredits', estimate, before_estimate), ('actualCostCredits', actual, before_actual)):
                if value is not None:
                    row[field] = money(value)
                    if before is not None: row[field + 'Change'] = money(value - before)
            row['_sort'] = (stamp(at), mid, event_index)
            changes.append(row)
            local.append(row)
            previous = status
            metadata.append({'missionId': mid, 'eventKey': key, 'changedAt': stamp(at), 'timing': 'duration-closure' if closure else timing,
                             'objectiveRevision': revised, 'provenance': 'Synthetic lab event/recorder/style/cost/timestamp.'})
        m = {key: item[key] for key in ('title', 'type', 'classification', 'priority', 'stardate', 'durationHours', 'location', 'issuingAuthority', 'assignedCrewIds', 'participantIds', 'assignedAssetIds')}
        m.update(missionId=mid, status=item['finalStatus'], objective=objective, lastUpdated=local[-1]['changedAt'], cancelledWithoutEstimateAllowed=False)
        if item['commandingOfficerId']: m['commandingOfficerId'] = item['commandingOfficerId']
        if estimate is not None: m['estimatedCostCredits'] = money(estimate)
        if actual is not None:
            m['actualCostCredits'] = money(actual)
            m['outcome'] = ('Objective achieved; operational report filed.' if m['status'] == 'COMPLETED' else
                            'Objective unmet; assessment and incurred costs recorded.' if m['status'] == 'FAILED' else
                            'Further escort terminated following identity/security concerns; incurred costs recorded.')
        missions.append(m)
    changes.sort(key=lambda row: row['_sort'])
    for index, row in enumerate(changes):
        row['changeId'] = str(change_start + index)
        row.pop('_sort')
    for m in missions:
        m['currentChangeId'] = [r['changeId'] for r in changes if r['missionId'] == m['missionId']][-1]
    return missions, changes, metadata


# ---------------------------------------------------------------------------------------------------------------------
# Staffing -----------------------------------------------------------------------------------------------------------

class Roster:
    def __init__(self, recipe, roster):
        self.crew = recipe['references']['crew']           # name -> ref
        self.by_ref = {ref: name for name, ref in self.crew.items()}
        self.unmapped = recipe['references']['unmappedCrew']
        self.info = roster
        named = {self.crew[n] for n in NAMED if n in self.crew}
        self.named_refs = named
        generic = [r for r in sorted(roster, key=lambda r: int(r[2:])) if r not in named and roster[r].get('mapped', True)]
        self.generic = generic
        self.active = [r for r in generic if roster[r]['dutyStatus'] == 'ACTIVE']
        self.cell = {}
        for r in self.active:
            self.cell.setdefault((roster[r]['rank'], roster[r]['department']), []).append(r)
        self.rank = {}
        for r in self.active:
            self.rank.setdefault(roster[r]['rank'], []).append(r)
        self.inactive = [r for r in generic if roster[r]['dutyStatus'] != 'ACTIVE' and roster[r]['rank'] != 'CIVILIAN']
        self.civilians = [r for r in generic if roster[r]['rank'] == 'CIVILIAN']

    def draw(self, stream, rank_table, departments, taken, other_percent=15, exclude_ranks=()):
        for _ in range(100000):
            rank = stream.weighted([row for row in rank_table if row[0] not in exclude_ranks])
            if departments and stream.integer(1, 100) > other_percent:
                cell = self.cell.get((rank, stream.pick(departments)))
                pool = cell or self.rank.get(rank, [])
            else:
                pool = self.rank.get(rank, [])
            if not pool:
                continue
            ref = pool[stream.integer(0, len(pool) - 1)]
            if ref not in taken:
                return ref
        raise ValueError('Roster cannot satisfy the staffing request')


def deal(counts, tag, category='recipe_routine'):
    items = []
    for value in sorted(counts):
        items += [value] * counts[value]
    keyed = sorted((Stream(category, tag + ':' + str(i)).integer(0, (1 << 64) - 1), i, v) for i, v in enumerate(items))
    return [v for _, _, v in keyed]


def order_by_hash(items, category, tag):
    return sorted(items, key=lambda it: (Stream(category, tag + ':' + it['key']).integer(0, (1 << 64) - 1), it['key']))


# ---------------------------------------------------------------------------------------------------------------------

STATUS_EVENTS = {
    'PLANNED': [('PLANNED', 'registered pending scope and staffing')],
    'AUTHORIZED': [('AUTHORIZED', 'approved and funded')],
    'ACTIVE': [('AUTHORIZED', 'approved and funded'), ('ACTIVE', 'work under way')],
    'POSTPONED': [('AUTHORIZED', 'approved and funded'), ('ACTIVE', 'work under way'), ('POSTPONED', 'deferred pending a revised window')],
    'COMPLETED': [('AUTHORIZED', 'approved and funded'), ('ACTIVE', 'work under way'), ('COMPLETED', 'objective achieved; report filed')],
    'FAILED': [('AUTHORIZED', 'approved and funded'), ('ACTIVE', 'work under way'), ('FAILED', 'objective unmet; assessment filed')],
    'CANCELLED': [('AUTHORIZED', 'approved and funded'), ('ACTIVE', 'work under way'), ('CANCELLED', 'withdrawn; incurred costs recorded')],
}


def build_events(status, path, revise, long_history=0, short=False, progress=False):
    base = [dict(key=None, status=s, action=a) for s, a in STATUS_EVENTS[status]]
    if status == 'CANCELLED':
        if path == 'from-planned':
            base = [dict(key=None, status='PLANNED', action='registered pending scope and staffing'), dict(key=None, status='CANCELLED', action='withdrawn before any work began; no cost incurred')]
        elif path == 'authorized':
            base = [dict(key=None, status='AUTHORIZED', action='approved and funded'), dict(key=None, status='CANCELLED', action='withdrawn before work began; preparation costs recorded')]
    if status == 'AUTHORIZED' and path == 'planned-first':
        base = [dict(key=None, status='PLANNED', action='registered pending scope and staffing'), dict(key=None, status='AUTHORIZED', action='approved and funded')]
    if short and status == 'COMPLETED':
        base = [dict(key=None, status='AUTHORIZED', action='approved and funded'), dict(key=None, status='COMPLETED', action='objective achieved; report filed')]
    if long_history:
        middle = [dict(key=None, status='ACTIVE', action='milestone %d reached; plan adjusted' % n, revise=(n % 3 == 0)) for n in range(1, long_history - 1)]
        base = [base[0]] + [dict(key=None, status='ACTIVE', action='work under way')] + middle[:-1] + [base[-1]]
    elif progress and status in ('ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED') and len(base) >= 3:
        at = [i for i, e in enumerate(base) if e['status'] == 'ACTIVE'][0]
        base.insert(at + 1, dict(key=None, status='ACTIVE', action='milestone reached; plan confirmed'))
    if revise and not long_history:
        for e in base:
            if e['status'] == 'ACTIVE':
                e['revise'] = True
                e['action'] = 'work under way; scope growth revises the estimate'
                break
    for number, e in enumerate(base, 1):
        e['key'] = 'event-%d' % number
    return base


# ---------------------------------------------------------------------------------------------------------------------
# New missions: specs ---------------------------------------------------------------------------------------------------

def sd_text(cents_value):
    return '%d.%02d' % (cents_value // 100, cents_value % 100)


def roman(n):
    return {2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'}.get(n, str(n))


def place_name(key, recipe, accent=False):
    s = Stream('recipe_routine', key, 'place')
    p = recipe['routine']['placeParts']
    first, second, third = s.pick(p['first']), s.pick(p['second']), s.pick(p['third'])
    if accent:
        first = s.pick(p['accentFirst'])
    return first + second + third


def mark(spec, label, detail=''):
    spec['edges'].append({'edge': label, 'detail': detail})


def has_edge(spec, *labels):
    return any(e['edge'] in labels for e in spec['edges'])


def new_spec(key, origin, **fields):
    spec = {'key': key, 'origin': origin, 'co': None, 'crew': [], 'participants': [], 'assets': [], 'events': [], 'edges': [],
            'plannedEstimate': False, 'meta': {}, 'summaryOverride': None, 'estimateBand': None}
    spec.update(fields)
    return spec


def canon_specs(items, recipe, R):
    """Resolve the new curated canon missions: names to references, generated crew drawn from the roster."""
    assets = recipe['references']['assets']
    pref = {name: ref for ref, name in recipe['references']['participants'].items()}
    out = []
    type_departments = recipe['routine']['departmentByType']
    for item in items:
        key = item['key']
        spec = new_spec(key, 'canon', type=item['type'], classification=item['classification'], priority=item['priority'],
                        stardate=item['stardate'], durationHours=item['durationHours'], title=item['title'], objective=item['objective'],
                        location=item['location'], issuingAuthority=item['issuingAuthority'], finalStatus=item['finalStatus'])
        spec['co'] = R.crew[item['commandingOfficer']] if item['commandingOfficer'] else None
        taken = set([spec['co']] if spec['co'] else [])
        for name in item['crew']:
            ref = R.crew[name]
            if ref not in taken:
                spec['crew'].append(ref)
                taken.add(ref)
        for name in item.get('unmappedCrew', []):
            spec['crew'].append(R.unmapped[name])
            mark(spec, 'unmapped-canon-crew', name)
        g = item['generatedCrew']
        stream = Stream('staffing_crew', key)
        rank_table = [(r, 1) for r in g['ranks']] or [('ENSIGN', 1)]
        for _ in range(g['count']):
            ref = R.draw(stream, rank_table, type_departments.get(item['type'], []), taken)
            spec['crew'].append(ref)
            taken.add(ref)
        for p in item['participants']:
            spec['participants'].append(pref[p['name']])
            if p['name'].startswith('Wesley Crusher'):
                mark(spec, 'returning-outsider-participant', pref[p['name']] + ' (never Crew, never mapped to a Personnel identity)')
                if R.crew['Wesley Crusher'] in spec['crew'] or spec['co'] == R.crew['Wesley Crusher']:
                    raise ValueError('A returning visitor must not be Crew')
        spec['assets'] = [assets[a] for a in item['assets']]
        spec['events'] = [dict(e) for e in item['events']]
        spec['meta'] = {k: item[k] for k in ('episode', 'sourceUrl', 'sourceObservation', 'stardateProvenance', 'provenance', 'sourceFacts')}
        if item.get('edge') == 'CANCELLED-WITH-FULL-STAFF':
            mark(spec, 'cancelled-with-full-staff')
        elif item.get('edge') == 'PARTLY-STAFFED-PLANNED':
            mark(spec, 'planned-partly-staffed', 'curated')
        spec['firstAuditDate'] = first_audit(item['stardate'])
        out.append(spec)
    return out


def maintenance_specs(recipe):
    cfg = recipe['maintenance']
    complexity = deal(cfg['complexityCounts'], 'maint-cx', 'recipe_maintenance')
    statuses = deal(cfg['statusCounts'], 'maint-st', 'recipe_maintenance')
    out = []
    for i in range(sum(cfg['complexityCounts'].values())):
        cx, status = complexity[i], statuses[i]
        task = cfg['tasks'][cx]
        key = 'maint-%03d' % i
        s = Stream('recipe_maintenance', key)
        title_base = s.pick(task['titles'])
        starbase = s.integer(1, 100) <= cfg['locations']['starbasePercent']
        if starbase:
            location = {'type': 'STARBASE', 'name': 'Starbase %d repair dock' % s.pick(cfg['locations']['starbaseNumbers'])}
        else:
            name = s.pick(cfg['locations']['names'])
            location = {'type': 'ENTERPRISE', 'name': name.replace('{n}', str(s.integer(1, 42))).replace('{s}', s.pick(list('ABCDEF')))}
        priority = s.weighted(task['priority'])
        lo, hi = task['durationHours']
        authority = s.weighted(cfg['issuingAuthority'])
        classification = s.weighted(cfg['classification'])
        sd = 4312500 + 5 * s.integer(0, (4599000 - 4312500) // 5)
        assets = ['VS-31'] if int(cx) >= 3 else []
        if int(cx) >= 3 or s.integer(1, 2) == 1:
            assets.append('EQ-86')
        spec = new_spec(key, 'maintenance', type='MAINTENANCE', classification=classification, priority=priority, stardate=sd_text(sd),
                        durationHours=s.integer(lo, hi), title=title_base + ' (' + location['name'] + ')',
                        objective=title_base + ' at ' + location['name'] + '; verify operation and log the result.',
                        location=location, issuingAuthority=authority, finalStatus=status, assets=sorted(set(assets)))
        spec['estimateBand'] = (task['estimateCredits'][0] * 100, task['estimateCredits'][1] * 100)
        spec['meta'] = {'complexity': int(cx), 'taskClass': task['taskClass'],
                        'provenance': 'Synthetic lab maintenance mission generated from the recipe; the complexity and task class are hidden recipe parameters, not contract fields.'}
        spec['complexity'] = cx
        spec['crewSize'] = tuple(task['crewSize'])
        out.append(spec)
    seen = {}
    for spec in out:
        base = spec['title']
        count = seen.get(base, 0) + 1
        seen[base] = count
        if count > 1:
            spec['title'] = base + ' ' + roman(count)
            spec['objective'] = spec['objective'].replace(';', ' (' + roman(count) + ');', 1)
    return out


def routine_specs(recipe):
    cfg = recipe['routine']
    types = deal(cfg['typeCounts'], 'routine-ty', 'recipe_routine')
    statuses = deal(cfg['statusCounts'], 'routine-st', 'recipe_routine')
    out = []
    for i in range(sum(cfg['typeCounts'].values())):
        typ, status = types[i], statuses[i]
        key = 'routine-%03d' % i
        s = Stream('recipe_routine', key)
        place = place_name(key, recipe)
        subject = s.pick(cfg['subjects'])
        template = s.pick(cfg['templates'][typ])
        title = template.replace('{place}', place).replace('{subject}', subject)
        title = title[0].upper() + title[1:]
        objective = s.pick(cfg['objectives'][typ]).replace('{place}', place).replace('{subject}', subject)
        location = {'type': s.pick(cfg['locationTypes'][typ]), 'name': place}
        if s.integer(1, 100) <= 35:
            location['coordinates'] = 'Grid %s-%d' % (s.pick(list('ABCDEFGHJKLM')), s.integer(1, 60))
        lo, hi = cfg['durationHours'][typ]
        sd = 4312500 + 5 * s.integer(0, (4599000 - 4312500) // 5)
        spec = new_spec(key, 'routine', type=typ, classification=s.weighted(cfg['classification']), priority=s.weighted(cfg['priority']),
                        stardate=sd_text(sd), durationHours=s.integer(lo, hi), title=title, objective=objective, location=location,
                        issuingAuthority=s.weighted(cfg['issuingAuthority'][typ]), finalStatus=status,
                        assets=sorted(set(cfg['assetsByType'][typ])))
        lo_b, hi_b = cfg['estimateBandsCredits'][typ]
        spec['estimateBand'] = (lo_b * 100, hi_b * 100)
        spec['meta'] = {'template': template, 'provenance': 'Synthetic lab routine mission generated from the recipe.'}
        size = s.weighted([(tuple(rng), w) for rng, w in cfg['crewSize']])
        spec['crewSize'] = size
        out.append(spec)
    seen = {}
    for spec in out:
        base = spec['title']
        count = seen.get(base, 0) + 1
        seen[base] = count
        if count > 1:
            spec['title'] = base + ' ' + roman(count)
    return out


def apply_quotas_and_edges(canon, maint, routine, recipe, R, legacy):
    """Assign commanding officers, staff the generated missions and place the deliberate edge cases."""
    cfg = recipe['routine']
    mcfg = recipe['maintenance']
    crew = R.crew
    needs = lambda spec: spec['finalStatus'] in NEEDS_CO

    def pick_n(pool, count, tag, label=None, detail=''):
        ordered = order_by_hash(pool, 'edge_cases', tag)
        if len(ordered) < count:
            raise ValueError('Edge case %s cannot be placed: %d eligible, %d needed' % (tag, len(ordered), count))
        chosen = ordered[:count]
        if label:
            for spec in chosen:
                mark(spec, label, detail)
        return chosen

    # ---- named commanding officers (totals include the curated canon core)
    for name, target in cfg['namedCommanderTotals'].items():
        have = sum(1 for s in canon if s['co'] == crew[name]) + sum(1 for m in legacy if m.get('commandingOfficerId') == crew[name])
        want = target - have
        if want < 0:
            raise ValueError('Canon core already exceeds the commander total of ' + name)
        types = cfg['namedCommanderTypes'][name]
        pool = [s for s in routine if s['co'] is None and needs(s) and s['type'] in types]
        for spec in pick_n(pool, want, 'named-' + name):
            spec['co'] = crew[name]
            spec['meta']['namedCommander'] = name
    for name, target in mcfg['namedCommanderTotals'].items():
        pool = [s for s in maint if s['co'] is None and needs(s) and s['complexity'] == '4']
        for spec in pick_n(pool, target, 'named-maint-' + name):
            spec['co'] = crew[name]

    # ---- the rest of the commanders from the rank tables
    for spec in routine + maint:
        if spec['co'] is not None:
            continue
        s = Stream('staffing_commander', spec['key'])
        if needs(spec) or s.integer(1, 100) <= cfg['optionalCommanderPercent']:
            if spec['origin'] == 'maintenance':
                table = mcfg['tasks'][spec['complexity']]['commanderRanks']
                departments = ['ENGINEERING', 'OPERATIONS']
            else:
                table = cfg['commanderRanks']
                departments = cfg['departmentByType'][spec['type']]
            spec['co'] = R.draw(s, table, departments, set(), 15)

    # ---- edge selections that shape the staffing
    planned = [s for s in routine + maint if s['finalStatus'] == 'PLANNED']
    variants = ['no-commander-no-crew'] * 7 + ['commander-only'] * 5 + ['commander-and-one-or-two-crew'] * 5
    for spec, variant in zip(order_by_hash(planned, 'edge_cases', 'planned-variants'), variants):
        mark(spec, 'planned-partly-staffed', variant)
        spec['plannedVariant'] = variant
        if variant == 'no-commander-no-crew':
            spec['co'] = None
    cancelled = [s for s in routine if s['finalStatus'] == 'CANCELLED']
    for k, spec in enumerate(order_by_hash(cancelled, 'edge_cases', 'cancelled-paths')):
        spec['cancelPath'] = 'from-planned' if k < 5 else 'full-staff' if k < 10 else 'authorized'
        if k < 5:
            mark(spec, 'cancelled-from-planned-no-estimate')
        elif k < 10:
            mark(spec, 'cancelled-with-full-staff')
    for spec in maint:
        if spec['finalStatus'] == 'CANCELLED':
            spec['cancelPath'] = 'authorized'
    for spec in pick_n([s for s in routine if s['co'] in (crew['William Riker'], crew['Beverly Crusher']) and needs(s)], 8, 'commander-only-senior', 'commander-is-only-senior'):
        spec['noSenior'] = True
    big = pick_n([s for s in routine if s['type'] in ('RESCUE', 'MEDICAL', 'HUMANITARIAN', 'TRANSPORT') and s['finalStatus'] == 'COMPLETED'
                  and s['co'] and not s.get('noSenior')], 4, 'near-limit-crews')
    for spec, size, title, objective in zip(big, (100, 99, 98, 96), cfg['bigCrew']['titles'], cfg['bigCrew']['objectives']):
        spec['crewSize'] = (size, size)
        spec['title'], spec['objective'] = title, objective
        mark(spec, 'crew-near-limit', str(size))

    # ---- staffing of every generated mission
    for spec in routine + maint:
        s = Stream('staffing_crew', spec['key'])
        taken = set([spec['co']] if spec['co'] else [])
        lo, hi = spec['crewSize']
        n = s.integer(lo, hi)
        if spec['origin'] == 'maintenance':
            table = mcfg['tasks'][spec['complexity']]['crewRanks']
            departments = ['ENGINEERING', 'OPERATIONS']
        else:
            table = cfg['crewRanks']
            departments = cfg['departmentByType'][spec['type']]
        if spec.get('plannedVariant'):
            v = spec['plannedVariant']
            n = 0 if v in ('no-commander-no-crew', 'commander-only') else s.integer(1, 2)
        if spec.get('cancelPath') == 'from-planned':
            n = s.integer(0, 2)
        elif spec.get('cancelPath') == 'full-staff':
            n = max(n, 4)
        elif spec.get('cancelPath') == 'authorized':
            n = max(1, min(n, 6))
        exclude = SENIOR if spec.get('noSenior') else ()
        for _ in range(n):
            ref = R.draw(s, table, departments, taken, 15, exclude)
            spec['crew'].append(ref)
            taken.add(ref)

    # ---- edge edits to the staffed crews
    def swap_in(spec, ref):
        if ref in spec['crew']:
            return
        if len(spec['crew']) >= 100:
            spec['crew'][-1] = ref
        else:
            spec['crew'].append(ref)

    def staffed(s):
        return [x for x in routine if x['crew'] and needs(x) and not has_edge(x, 'crew-near-limit', 'commander-is-only-senior')]

    for spec in pick_n([s for s in routine if s['co'] and s['crew'] and not has_edge(s, 'crew-near-limit')], 5, 'commander-also-assigned', 'commander-also-assigned-crew'):
        if spec['co'] not in spec['crew']:
            spec['crew'].append(spec['co'])
    for spec in pick_n(staffed(None), 12, 'inactive-or-leave', 'assigned-crew-not-active'):
        swap_in(spec, Stream('edge_cases', spec['key'], 'inactive').pick(R.inactive))
    for spec in pick_n(staffed(None), 5, 'civilian-as-crew', 'civilian-listed-as-assigned-crew'):
        swap_in(spec, Stream('edge_cases', spec['key'], 'civilian').pick(R.civilians))
    for name, types in (('Alyssa Ogawa', ('MEDICAL', 'HUMANITARIAN')), ('Hubbell', ('TRANSPORT',))):
        for spec in pick_n([s for s in staffed(None) if s['type'] in types and not has_edge(s, 'unmapped-canon-crew')], 2, 'unmapped-' + name, 'unmapped-canon-crew'):
            swap_in(spec, R.unmapped[name])
            spec['edges'][-1]['detail'] = name
    for spec in pick_n(staffed(None), 6, 'dangling-crew', 'crew-reference-in-no-recipe'):
        ref = 'C-%d' % (10000 + Stream('edge_cases', spec['key'], 'dangling').integer(0, 9999))
        spec['crew'].append(ref)
        spec['edges'][-1]['detail'] = ref

    # ---- classification: TOP_SECRET missions with crew whose rank carries no clearance
    for spec in routine + canon:
        if spec['classification'] == 'TOP_SECRET' and any(R.info.get(r, {}).get('rank') in ('CREWMAN', 'ENSIGN', 'LIEUTENANT', 'CHIEF_PETTY_OFFICER') for r in spec['crew']):
            mark(spec, 'classification-above-crew-clearance', 'TOP_SECRET with crew of rank below lieutenant commander')

    # ---- assets with no mapping entry, and the 50-asset mission
    for spec in pick_n([s for s in routine + maint if s['finalStatus'] != 'PLANNED'], 14, 'assets-without-mapping', 'asset-reference-without-mapping'):
        extra = Stream('staffing_assets', spec['key']).pick(cfg['inventedAssets'])
        spec['assets'] = sorted(set(spec['assets']) | {extra})
        spec['edges'][-1]['detail'] = extra
    biggest = pick_n([s for s in routine if s['type'] == 'TRANSPORT' and s['finalStatus'] == 'COMPLETED' and not s['edges']], 1, 'fifty-assets', 'fifty-assigned-assets')[0]
    pool_assets = sorted(set(recipe['references']['assets'].values()) | set(cfg['assetPool']), key=lambda r: (r.split('-')[0], int(r.split('-')[1])))
    biggest['assets'] = pool_assets[:50]
    if len(biggest['assets']) != 50:
        raise ValueError('Asset pool must supply 50 distinct references')

    # ---- participants
    ppool = sorted(recipe['references']['participantPool'])
    for spec in routine:
        s = Stream('staffing_participants', spec['key'])
        if s.integer(1, 100) <= cfg['participantPercent']:
            spec['participants'] = sorted(set(s.pick(ppool) for _ in range(s.integer(1, 3))))
    for spec in pick_n([s for s in routine if s['type'] in ('DIPLOMATIC', 'HUMANITARIAN', 'MEDICAL', 'TRANSPORT')], 10, 'many-participants', 'many-participants'):
        s = Stream('staffing_participants', spec['key'], 'many')
        spec['participants'] = sorted(set(s.pick(ppool) for _ in range(s.integer(10, 25))))
        spec['edges'][-1]['detail'] = str(len(spec['participants']))


def finish_specs(specs, recipe, R):
    crew = R.crew
    for spec in specs:
        if spec['origin'] != 'canon':
            status = spec['finalStatus']
            revise = status in ('ACTIVE', 'POSTPONED', 'COMPLETED', 'FAILED') and Stream('estimate_revision', spec['key'], 'plan').integer(1, 100) <= recipe['routine']['revisionPercent']
            planned_first = status == 'AUTHORIZED' and Stream('change_density', spec['key']).integer(1, 100) <= 40
            progress = Stream('change_density', spec['key'], 'progress').integer(1, 100) <= recipe['routine']['progressPercent']
            spec['events'] = build_events(status, 'planned-first' if planned_first else spec.get('cancelPath'), revise, progress=progress)
            if spec.get('shortHistory'):
                spec['events'] = build_events('COMPLETED', None, False, short=True)
            if spec.get('longHistory'):
                spec['events'] = build_events('COMPLETED', None, False, long_history=spec['longHistory'])
                spec['durationHours'] = max(spec['durationHours'], 720)
            spec['firstAuditDate'] = first_audit(spec['stardate'], Stream('history_timing', spec['key'], 'start').integer(0, 480))
    for spec in specs:
        spec['firstAudit'] = spec['firstAuditDate']
        fallback = spec['crew'][0] if spec['crew'] else crew['Data']
        spec['changedBy'] = spec['co'] or fallback
        spec['changedByName'] = R.by_ref.get(spec['changedBy'])
        spec['orderedBy'] = crew['William Riker'] if spec['issuingAuthority'] == 'ENTERPRISE_COMMAND' else crew['Jean-Luc Picard']
        if spec['origin'] != 'canon':
            timing = 'planning' if spec['finalStatus'] == 'PLANNED' else 'urgent' if spec['priority'] <= 2 else 'routine'
            lo = recipe['timeBandsMinutes'][timing][0]
            needed = ((len(spec['events']) - 1) * lo + 59) // 60 + 1 if len(spec['events']) > 2 else 1
            if not spec.get('keepDuration'):
                spec['durationHours'] = min(8760, max(spec['durationHours'], needed))


def generate():
    recipe = json.loads(source_bytes(HERE / 'recipe.json'))
    inputs = json.loads(source_bytes(HERE / 'curation.json'))
    roster = json.loads(source_bytes(HERE / 'roster.json'))
    if recipe['masterSeed'] != 1701 or recipe['generatorVersion'] != GEN2 or recipe['algorithm'] != 'sha256-counter-v1':
        raise ValueError('This generator implements only its reviewed recipe version')
    legacy_inputs = [i for i in inputs if i['origin'] == 'canon-carried']
    new_inputs = [i for i in inputs if i['origin'] == 'canon']
    start = Stream('mission_id_start', generation=GEN1).integer(990000, 1010000)
    change_start = Stream('change_id_start', generation=GEN1).integer(9900000, 10100000)
    legacy_missions, legacy_changes, legacy_meta = author_legacy(legacy_inputs, recipe, start, change_start)
    R = Roster(recipe, roster)
    canon = canon_specs(new_inputs, recipe, R)
    maint = maintenance_specs(recipe)
    routine = routine_specs(recipe)
    apply_quotas_and_edges(canon, maint, routine, recipe, R, legacy_missions)
    specs = canon + maint + routine
    # long histories, short history and boundary values (placed on missions that carry no other edge case)
    free = lambda status: [s for s in routine if not s['edges'] and s['finalStatus'] == status and s['crew']]
    taken_ids = set()

    def take(tag, status, count=1):
        chosen = [s for s in order_by_hash(free(status), 'edge_cases', tag) if id(s) not in taken_ids][:count]
        if len(chosen) < count:
            raise ValueError('Boundary case ' + tag)
        for s in chosen:
            taken_ids.add(id(s))
        return chosen

    for spec, count in zip(take('long-history', 'COMPLETED', 2), (8, 12)):
        spec['longHistory'] = count
        mark(spec, 'long-history', str(count))
    low = take('stardate-low', 'COMPLETED')[0]
    low['stardate'] = '43000.00'
    mark(low, 'boundary-stardate-low', '43000.00')
    high = take('stardate-high', 'PLANNED')[0] if free('PLANNED') else None
    if high is None:
        high = [s for s in order_by_hash([x for x in routine if not x['edges'] and x['finalStatus'] == 'PLANNED'], 'edge_cases', 'stardate-high')][0]
    high['stardate'] = '48999.95'
    mark(high, 'boundary-stardate-high', '48999.95')
    short = take('duration-1', 'COMPLETED')[0]
    short['durationHours'] = 1
    short['shortHistory'] = True
    short['keepDuration'] = True
    mark(short, 'boundary-duration-low', '1')
    longd = take('duration-8760', 'ACTIVE')[0]
    longd['durationHours'] = 8760
    longd['keepDuration'] = True
    mark(longd, 'boundary-duration-high', '8760')
    title = take('title-120', 'COMPLETED')[0]
    title['title'] = (title['title'] + ' - extended-duration operation with scheduled checkpoints, interim reports and a full final report to command')[:120].rstrip()
    mark(title, 'boundary-title-120', str(len(title['title'])))
    obj = take('objective-2000', 'COMPLETED')[0]
    text = ' '.join('Phase %d: %s' % (n, obj['objective']) for n in range(1, 40))[:2000]
    obj['objective'] = text[:-1] + '.' if text.endswith(' ') else text
    obj['summaryOverride'] = 'Initial objective registered in full on the mission (2000 characters).'
    mark(obj, 'boundary-objective-2000', str(len(obj['objective'])))
    for k, spec in enumerate(take('non-ascii', 'COMPLETED', 3)):
        accent = place_name(spec['key'], recipe, accent=True)
        spec['title'] = accent + ' ' + spec['title'].split(' ', 1)[0] + ' ' + str(k + 1) + ' (' + accent + ')'
        spec['objective'] = spec['objective'] + ' Rendezvous at ' + accent + '.'
        mark(spec, 'non-ascii-text', accent)
    finish_specs(specs, recipe, R)
    # ---- ids, history, assembly
    base_ordinal = start + len(legacy_missions)
    new_missions, new_changes, new_meta, sources, ledger = [], [], [], [], []
    for index, spec in enumerate(specs):
        mid = mission_id(base_ordinal + index)
        rows, notes, estimate, actual, from_planned = author_history(spec, mid, recipe)
        new_changes += rows
        new_meta += notes
        m = {'title': spec['title'], 'type': spec['type'], 'classification': spec['classification'], 'priority': spec['priority'],
             'stardate': spec['stardate'], 'durationHours': spec['durationHours'], 'location': spec['location'],
             'issuingAuthority': spec['issuingAuthority'], 'assignedCrewIds': sorted(set(spec['crew'])),
             'participantIds': sorted(set(spec['participants'])), 'assignedAssetIds': sorted(set(spec['assets'])),
             'missionId': mid, 'status': spec['finalStatus'], 'objective': spec['objective'], 'lastUpdated': rows[-1]['changedAt'],
             'cancelledWithoutEstimateAllowed': bool(from_planned and spec['finalStatus'] == 'CANCELLED')}
        if spec['co']: m['commandingOfficerId'] = spec['co']
        if estimate is not None: m['estimatedCostCredits'] = money(estimate)
        if actual is not None:
            m['actualCostCredits'] = money(actual)
            m['outcome'] = ('Objective achieved; operational report filed.' if m['status'] == 'COMPLETED' else
                            'Objective unmet; assessment and incurred costs recorded.' if m['status'] == 'FAILED' else
                            'Mission withdrawn; incurred costs recorded.')
        new_missions.append(m)
        src = {'key': spec['key'], 'origin': spec['origin'], 'provenance': spec['meta'].get('provenance'), 'synthetic': spec['origin'] != 'canon'}
        for k in ('episode', 'sourceUrl', 'sourceObservation', 'stardateProvenance', 'sourceFacts', 'complexity', 'taskClass', 'template', 'namedCommander'):
            if k in spec['meta']:
                src[k] = spec['meta'][k]
        src['edgeCases'] = [e['edge'] for e in spec['edges']]
        sources.append(src)
        for e in spec['edges']:
            ledger.append({'edge': e['edge'], 'missionId': mid, 'detail': e['detail']})
    new_changes.sort(key=lambda row: row['_sort'])
    next_change = change_start + len(legacy_changes)
    last = {}
    for index, row in enumerate(new_changes):
        row['changeId'] = str(next_change + index)
        row.pop('_sort')
        last[row['missionId']] = row['changeId']
    for m in new_missions:
        m['currentChangeId'] = last[m['missionId']]
    missions = legacy_missions + new_missions
    changes = legacy_changes + new_changes
    ledger.append({'edge': 'page-boundary', 'missionId': None, 'detail': 'missions %d in pages of %d' % (len(missions), PAGE)})
    data = {'datasetVersion': recipe['datasetVersion'], 'contractRevision': '1.1', 'missions': missions, 'changes': changes}
    mission_sources = [{key: item[key] for key in ('key', 'episode', 'sourceUrl', 'sourceObservation', 'stardateProvenance', 'provenance')} for item in legacy_inputs]
    for item in mission_sources:
        item['origin'] = 'canon-carried'
        item['carriedFrom'] = '1.0/' + item['key']
    mission_sources += sources
    limitations = ['No canonical finance/mission-order claim.', 'Snapshot statuses are selected or generated lab states.',
                   'Missions other than the curated canon core are synthetic: the recipe generated their titles, staffing, costs and histories.',
                   'Two explicit modest objective revisions in the carried missions; narrative extraction is incomplete for arbitrary clients.',
                   'Physical external references limited to 50; wire grammar is not narrowed.', 'No Personnel mapping.',
                   'Change ids of the new missions follow those of release 1.0 and are ordered by time among themselves only; a new entry can be older than a lower change id.']
    files = {'release.json': canonical(data),
             'provenance.json': canonical({'missionSources': mission_sources, 'events': legacy_meta + new_meta, 'edgeLedger': ledger, 'limitations': limitations})}
    files.update(render_xml(data))
    files.update({name: source_bytes(HERE / name) for name in ('generate.py', 'recipe.json', 'curation.json', 'roster.json')})
    files['schema.sql'] = source_bytes(COMPONENT / 'schema/schema.sql')
    manifest = {'datasetVersion': recipe['datasetVersion'], 'contractRevision': '1.1', 'generatorVersion': recipe['generatorVersion'],
                'recipe': recipe, 'sources': {name: digest(source_bytes(HERE / name)) for name in ('recipe.json', 'curation.json', 'generate.py', 'roster.json')},
                'contractSha256': digest(source_bytes(COMPONENT / 'contracts/missions-v1.1.xsd')),
                'preservedContract10Sha256': digest(source_bytes(COMPONENT / 'contracts/missions-v1.0.xsd')),
                'counts': {'missions': len(missions), 'changes': len(changes)}, 'firstMissionOrdinal': start, 'firstChangeId': change_start,
                'nextMissionOrdinal': start + len(missions), 'nextChangeId': change_start + len(changes),
                'appendsTo': {'datasetVersion': '1.0', 'missions': len(legacy_missions), 'changes': len(legacy_changes),
                              'nextMissionOrdinal': start + len(legacy_missions), 'nextChangeId': change_start + len(legacy_changes)},
                'composition': {'canonCarried': len(legacy_missions), 'canonNew': len(canon), 'maintenanceGenerated': len(maint), 'routineGenerated': len(routine),
                                'typeMaintenanceTotal': sum(1 for m in missions if m['type'] == 'MAINTENANCE')},
                'clock': {'baseline': max(r['changedAt'] for r in changes), 'counter': 0, 'intervalMs': 1000},
                'files': {name: digest(content) for name, content in files.items()}}
    files['load.sql'] = render_sql(data, manifest)
    manifest['files']['load.sql'] = digest(files['load.sql'])
    files['manifest.json'] = canonical(manifest)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    g = sub.add_parser('generate')
    g.add_argument('--output', required=True, type=Path)
    r = sub.add_parser('references')
    r.add_argument('--crew-dir', required=True, type=Path)
    r.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'generate':
        if args.output.exists(): raise ValueError('Output already exists; immutable versions are never overwritten')
        files = generate()
        args.output.mkdir(parents=True)
        for name, content in files.items(): (args.output / name).write_bytes(content)
        print('Authored candidate release; review and real acceptance remain required:', args.output)
    else:
        recipe = json.loads(source_bytes(HERE / 'recipe.json'))
        crew, unmapped, roster = derive_references(args.crew_dir, recipe)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'roster.json').write_bytes(canonical(roster))
        (args.output / 'references.json').write_bytes(canonical({'crew': crew, 'unmappedCrew': unmapped}))
        print('References derived:', len(crew), 'crew,', len(unmapped), 'unmapped canon')


if __name__ == '__main__': main()
