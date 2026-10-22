"""Missions release authoring. Never invoked by startup or reset.

Algorithm and formats are frozen by recipe.json plus this generator's canonical
Git-content SHA256 in every manifest. Publishing is explicit and refuses reuse.
Only stdlib is required; generate --output writes a fresh review directory.
"""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
COMPONENT = HERE.parent
NS = 'urn:starfleet:missions:v1'
ET.register_namespace('', NS)
ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CATEGORIES = ('mission_id_start','change_id_start','history_timing','estimated_cost','estimate_revision','actual_cost')

def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('utf-8')

def digest(content):
    return hashlib.sha256(content).hexdigest()

def source_bytes(path):
    return path.read_bytes().replace(b'\r\n', b'\n')

class Stream:
    def __init__(self, category, mission='', event='', master=1701):
        if category not in CATEGORIES:
            raise ValueError('Unknown category')
        key = json.dumps(['missions-generator-1', master, category, mission, event],
                         ensure_ascii=True, separators=(',', ':')).encode('utf-8')
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
            value = int.from_bytes(hashlib.sha256(self.seed + self.counter.to_bytes(8,'big')).digest(),'big')
            self.counter += 1
            if value < limit:
                return lo + value % span

def mission_id(ordinal):
    if not 1 <= ordinal < 36**9:
        raise ValueError('Mission ordinal overflow')
    suffix = ''
    while ordinal:
        ordinal, digit = divmod(ordinal,36)
        suffix = ALPHABET[digit] + suffix
    return 'ST-' + suffix.zfill(9)

def stamp(value):
    return value.isoformat(timespec='milliseconds') + 'Z'

def moment(value):
    return datetime.fromisoformat(value.removesuffix('Z'))

def money(cents):
    return None if cents is None else ('-' if cents < 0 else '') + str(abs(cents)//100) + '.' + str(abs(cents)%100).zfill(2)

def cents(value):
    if value is None:
        return None
    sign = -1 if value.startswith('-') else 1
    whole, fraction = value.removeprefix('-').split('.')
    return sign*(int(whole)*100+int(fraction))

def band(kind):
    if kind == 'TACTICAL': return 10000000,50000000
    if kind in ('DIPLOMATIC','FIRST_CONTACT'): return 1000000,12000000
    if kind in ('MEDICAL','RESCUE','HUMANITARIAN','SECURITY','MAINTENANCE'): return 2500000,20000000
    return 500000,5000000

def element(root, name, value):
    if value is not None:
        ET.SubElement(root,'{' + NS + '}' + name).text = str(value)

def mission_xml(root, mission):
    item = ET.SubElement(root,'{' + NS + '}mission')
    for name in ('missionId','title','type','classification','status','priority','stardate','durationHours','objective'):
        element(item,name,mission[name])
    location = ET.SubElement(item,'{' + NS + '}location')
    for name in ('type','name','coordinates','travelVector'):
        element(location,name,mission['location'].get(name))
    element(item,'issuingAuthority',mission['issuingAuthority'])
    element(item,'commandingOfficerId',mission.get('commandingOfficerId'))
    for plural,singular in (('assignedCrewIds','crewId'),('participantIds','participantId'),('assignedAssetIds','assetId')):
        parent = ET.SubElement(item,'{' + NS + '}' + plural)
        for ref in mission[plural]: element(parent,singular,ref)
    for name in ('estimatedCostCredits','actualCostCredits','outcome','lastUpdated'):
        element(item,name,mission.get(name))

def render_xml(data):
    missions = ET.Element('{' + NS + '}missionList')
    for name,value in (('page',1),('pageSize',50),('totalCount',len(data['missions'])),('totalPages',1)):
        element(missions,name,value)
    for mission in data['missions']: mission_xml(missions,mission)
    # This is a release serialization, not a pretend API page: one document per
    # real <=50-entry page below; page metadata remains contract-valid.
    pages = {}
    rows = data['changes']
    for page,start in enumerate(range(0,len(rows),50),1):
        root = ET.Element('{' + NS + '}changeList')
        for name,value in (('page',page),('pageSize',50),('totalCount',len(rows)),('totalPages',(len(rows)+49)//50)):
            element(root,name,value)
        for row in rows[start:start+50]:
            item=ET.SubElement(root,'{' + NS + '}change')
            for name in ('changeId','missionId','operation','changedAt','changedBy','orderedBy','previousStatus','newStatus',
                         'estimatedCostCredits','estimatedCostCreditsChange','actualCostCredits','actualCostCreditsChange','summary'):
                element(item,name,row.get(name))
        pages[f'changes-{page}.xml'] = ET.tostring(root,encoding='utf-8',xml_declaration=True) + b'\n'
    pages['missions.xml'] = ET.tostring(missions,encoding='utf-8',xml_declaration=True) + b'\n'
    return pages

def sql_string(value):
    if value is None: return 'NULL'
    if '\x00' in value or len(value.encode('utf-8')) > 3900:
        raise ValueError('Seed SQL literal must fit its reviewed statement format')
    return "'" + value.replace("'","''") + "'"

def sql_timestamp(value):
    return 'NULL' if value is None else "TO_TIMESTAMP(" + sql_string(value) + ",'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"')"

def render_sql(data, manifest):
    lines = ['-- Immutable release load. Current schema must be operator-owned.', 'SET DEFINE OFF',
             "ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,';", "ALTER SESSION SET TIME_ZONE = '+00:00';"]
    for m in data['missions']:
        names = ['mission_id','title','mission_type','classification','status','priority','stardate','duration_hours','objective',
                 'location_type','location_name','coordinates','travel_vector','issuing_authority','commanding_officer_id',
                 'estimated_cost','actual_cost','outcome','last_updated','current_change_id','cancelled_without_estimate_allowed']
        values = [sql_string(m['missionId']),sql_string(m['title']),sql_string(m['type']),sql_string(m['classification']),
                  sql_string(m['status']),str(m['priority']),m['stardate'],str(m['durationHours']),
                  'TO_CLOB(' + sql_string(m['objective']) + ')',sql_string(m['location']['type']),sql_string(m['location']['name']),
                  sql_string(m['location'].get('coordinates')),sql_string(m['location'].get('travelVector')),
                  sql_string(m['issuingAuthority']),sql_string(m.get('commandingOfficerId')),
                  m.get('estimatedCostCredits') or 'NULL',m.get('actualCostCredits') or 'NULL',
                  'TO_CLOB(' + sql_string(m.get('outcome')) + ')',sql_timestamp(m['lastUpdated']),m['currentChangeId'],
                  str(int(m['cancelledWithoutEstimateAllowed']))]
        lines.append('INSERT INTO missions (' + ','.join(names) + ') VALUES (' + ','.join(values) + ');')
        for key,table in (('assignedCrewIds','mission_assigned_crew'),('participantIds','mission_participants'),('assignedAssetIds','mission_assigned_assets')):
            for ref in m[key]: lines.append('INSERT INTO ' + table + ' VALUES (' + sql_string(m['missionId']) + ',' + sql_string(ref) + ');')
    for row in data['changes']:
        values = [row['changeId'],sql_string(row['missionId']),sql_string(row['operation']),sql_timestamp(row['changedAt']),
                  sql_string(row['changedBy']),sql_string(row['orderedBy']),sql_string(row.get('previousStatus')),sql_string(row['newStatus']),
                  row.get('estimatedCostCredits') or 'NULL',row.get('estimatedCostCreditsChange') or 'NULL',
                  row.get('actualCostCredits') or 'NULL',row.get('actualCostCreditsChange') or 'NULL',sql_string(row['summary'])]
        lines.append('INSERT INTO mission_changes VALUES (' + ','.join(values) + ');')
    clock=manifest['clock']
    lines.append('INSERT INTO mission_clock VALUES (1,' + sql_timestamp(clock['baseline']) + ',0,1000,' + sql_string(manifest['datasetVersion']) + ',' + sql_string(manifest['files']['release.json']) + ');')
    lines.extend(['COMMIT;','DROP SEQUENCE mission_id_seq;','DROP SEQUENCE change_id_seq;',
                  f"CREATE SEQUENCE mission_id_seq START WITH {manifest['nextMissionOrdinal']} MINVALUE 1 MAXVALUE {36**9-1} INCREMENT BY 1 NOCACHE NOCYCLE;",
                  f"CREATE SEQUENCE change_id_seq START WITH {manifest['nextChangeId']} MINVALUE 1 MAXVALUE {10**28-1} INCREMENT BY 1 NOCACHE NOCYCLE;"])
    return ('\n'.join(lines) + '\n').encode('utf-8')

def generate():
    recipe=json.loads(source_bytes(HERE/'recipe.json'))
    inputs=json.loads(source_bytes(HERE/'curation.json'))
    if recipe['masterSeed'] != 1701 or recipe['generatorVersion'] != 'missions-generator-1' or recipe['algorithm'] != 'sha256-counter-v1':
        raise ValueError('This generator implements only its reviewed recipe version')
    start=Stream('mission_id_start').integer(990000,1010000)
    change_start=Stream('change_id_start').integer(9900000,10100000)
    missions=[]; changes=[]; event_times={}; metadata=[]
    for index,item in enumerate(inputs):
        mid=mission_id(start+index)
        first=moment(item['firstAuditDate'])
        edge=next((edge for edge in recipe['causalEdges'] if edge['to']==item['key']),None)
        if edge:
            first=max(first,event_times[(edge['from'],edge['event'])] + timedelta(minutes=Stream('history_timing',mid,'causal-start').integer(5,45)))
        typ=item['type']; duration=item['durationHours']*60
        timing='planning' if item['finalStatus'] == 'PLANNED' else 'urgent' if item['priority']<=2 else 'routine'
        lo,hi=recipe['timeBandsMinutes'][timing]
        elapsed=0; estimate=None; actual=None; previous=None; local=[]; objective=item['objective']
        for event_index,event in enumerate(item['events']):
            key=event['key']; status=event['status']; closure=status in ('COMPLETED','FAILED','CANCELLED') and event_index==len(item['events'])-1
            if event_index:
                if closure:
                    elapsed=duration
                else:
                    remaining=len(item['events'])-1-event_index
                    ceiling=min(hi,duration-elapsed-max(1,remaining)*lo)
                    elapsed+=Stream('history_timing',mid,key).integer(lo,ceiling)
            at=first+timedelta(minutes=elapsed)
            event_times[(item['key'],key)]=at
            before_estimate, before_actual=estimate,actual
            if status != 'PLANNED' or (item['plannedEstimate'] and event_index==len(item['events'])-1):
                if estimate is None:
                    estimate=Stream('estimated_cost',mid,'initial').integer(*band(typ))
                elif re.search(r'(estimate|raises? E|E revised|raises?\b|E\d)',event['action'],re.I):
                    estimate=(estimate*Stream('estimate_revision',mid,key).integer(1100,1350)+500)//1000
            if closure:
                ratio=Stream('actual_cost',mid,key).integer(200,600) if status=='CANCELLED' else Stream('actual_cost',mid,key).integer(800,1350)
                actual=(estimate*ratio+500)//1000
            # These selected refinements preserve purpose; not every mission is
            # artificially revised, and API clients receive no semantic parser rule.
            revised=(item['key']=='candidate-15' and event_index==2) or (item['key']=='candidate-14' and event_index==2)
            changed_by=item['commandingOfficerId'] or recipe['references']['crew']['Data']
            if revised:
                if item['key']=='candidate-15':
                    objective='Identify the cause and spread of shipboard contamination and recommend containment.'
                    changed_by=recipe['references']['crew']['La Forge']
                    summary='Objective update: ' + objective
                else:
                    objective="Establish safe communication and assess the entity's intentions with attention to contact risks."
                    changed_by=recipe['references']['crew']['Troi']
                    summary='The objective of the mission has drifted to: ' + objective
            elif event_index==0:
                summary='Initial objective: ' + objective
                if edge: summary += ' Follow-on to mission ' + missions[inputs.index(next(i for i in inputs if i['key']==edge['from']))]['missionId'] + '.'
            else:
                action=event['action'].split(';')[0]
                action=re.sub(r'E?\d+\.\d{2}',money(estimate) or 'pending',action)
                prefix='Log: ' if changed_by==recipe['references']['crew']['La Forge'] else 'Report: ' if changed_by==recipe['references']['crew']['Riker'] else 'Recorded: '
                summary=prefix+action+'.'
            if len(summary)>256:
                raise ValueError('Author a shorter complete summary for ' + item['key'] + '/' + key)
            row={'missionId':mid,'operation':'CREATED' if event_index==0 else 'UPDATED','changedAt':stamp(at),
                 'changedBy':changed_by,'orderedBy':recipe['references']['crew']['Picard'], 'newStatus':status,'summary':summary}
            if previous is not None: row['previousStatus']=previous
            for field,value,before in (('estimatedCostCredits',estimate,before_estimate),('actualCostCredits',actual,before_actual)):
                if value is not None:
                    row[field]=money(value)
                    if before is not None: row[field+'Change']=money(value-before)
            row['_sort']=(stamp(at),mid,event_index)
            changes.append(row); local.append(row); previous=status
            metadata.append({'missionId':mid,'eventKey':key,'changedAt':stamp(at),'timing':'duration-closure' if closure else timing,
                             'objectiveRevision':revised,'provenance':'Synthetic lab event/recorder/style/cost/timestamp.'})
        m={key:item[key] for key in ('title','type','classification','priority','stardate','durationHours','location','issuingAuthority','assignedCrewIds','participantIds','assignedAssetIds')}
        m.update(missionId=mid,status=item['finalStatus'],objective=objective,lastUpdated=local[-1]['changedAt'],
                 cancelledWithoutEstimateAllowed=False)
        if item['commandingOfficerId']: m['commandingOfficerId']=item['commandingOfficerId']
        if estimate is not None: m['estimatedCostCredits']=money(estimate)
        if actual is not None:
            m['actualCostCredits']=money(actual)
            m['outcome']=('Objective achieved; operational report filed.' if m['status']=='COMPLETED' else
                          'Objective unmet; assessment and incurred costs recorded.' if m['status']=='FAILED' else
                          'Further escort terminated following identity/security concerns; incurred costs recorded.')
        missions.append(m)
    changes.sort(key=lambda row:row['_sort'])
    for index,row in enumerate(changes): row['changeId']=str(change_start+index); row.pop('_sort')
    for m in missions: m['currentChangeId']=[r['changeId'] for r in changes if r['missionId']==m['missionId']][-1]
    data={'datasetVersion':recipe['datasetVersion'],'contractRevision':'1.1','missions':missions,'changes':changes}
    files={'release.json':canonical(data),'provenance.json':canonical({'missionSources':[{key:item[key] for key in
        ('key','episode','sourceUrl','sourceObservation','stardateProvenance','provenance')} for item in inputs],
        'events':metadata,'limitations':['No canonical finance/mission-order claim.','Snapshot statuses are selected lab states.',
        'Only two explicit modest objective revisions; narrative extraction is incomplete for arbitrary clients.',
        'Physical external references limited to 50; wire grammar is not narrowed.','No Personnel mapping.']})}
    files.update(render_xml(data))
    files.update({name:source_bytes(HERE/name) for name in ('generate.py','recipe.json','curation.json')})
    files['schema.sql']=source_bytes(COMPONENT/'schema/schema.sql')
    manifest={'datasetVersion':recipe['datasetVersion'],'contractRevision':'1.1','generatorVersion':recipe['generatorVersion'],
              'recipe':recipe,'sources':{name:digest(source_bytes(HERE/name)) for name in ('recipe.json','curation.json','generate.py')},
              'contractSha256':digest(source_bytes(COMPONENT/'contracts/missions-v1.1.xsd')),
              'preservedContract10Sha256':digest(source_bytes(COMPONENT/'contracts/missions-v1.0.xsd')),
              'counts':{'missions':len(missions),'changes':len(changes)},'firstMissionOrdinal':start,'firstChangeId':change_start,
              'nextMissionOrdinal':start+len(missions),'nextChangeId':change_start+len(changes),
              'clock':{'baseline':max(r['changedAt'] for r in changes),'counter':0,'intervalMs':1000},
              'files':{name:digest(content) for name,content in files.items()}}
    files['load.sql']=render_sql(data,manifest)
    manifest['files']['load.sql']=digest(files['load.sql'])
    files['manifest.json']=canonical(manifest)
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Output already exists; immutable versions are never overwritten')
    files=generate()
    args.output.mkdir(parents=True)
    for name,content in files.items(): (args.output/name).write_bytes(content)
    print('Authored candidate release; review and real acceptance remain required:',args.output)

if __name__=='__main__': main()
