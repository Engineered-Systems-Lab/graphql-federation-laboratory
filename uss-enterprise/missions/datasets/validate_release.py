"""Validate an explicitly selected immutable Missions release without executing it."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
from datetime import datetime, timedelta

HERE=Path(__file__).resolve().parent
COMPONENT=HERE.parent
WHITESPACE={0x9,0xA,0xB,0xC,0xD,0x1C,0x1D,0x1E,0x1F,0x20,0x1680,*range(0x2000,0x2007),*range(0x2008,0x200B),0x2028,0x2029,0x205F,0x3000}
STATES={'PLANNED','AUTHORIZED','ACTIVE','POSTPONED','COMPLETED','FAILED','CANCELLED'}

def require(condition,message):
    if not condition: raise ValueError(message)

def content(path): return path.read_bytes().replace(b'\r\n',b'\n')
def sha(value): return hashlib.sha256(value).hexdigest()
def cents(value):
    if value is None: return None
    require(re.fullmatch(r'-?(0|[1-9][0-9]{0,12})\.[0-9]{2}',value) is not None and value!='-0.00','Cost lexical form')
    negative=value.startswith('-'); whole,fraction=value.removeprefix('-').split('.')
    return (-1 if negative else 1)*(int(whole)*100+int(fraction))
def moment(value):
    require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z',value) is not None,'Timestamp spelling')
    return datetime.fromisoformat(value[:-1])
def text_bound(value,limit):
    require(isinstance(value,str) and 1<=len(value)<=limit and any(ord(ch) not in WHITESPACE for ch in value),'Text code-point/non-whitespace bound')

def domain(m):
    require(m['status'] in STATES,'Status')
    text_bound(m['title'],120); text_bound(m['objective'],2000); text_bound(m['location']['name'],120)
    for key in ('coordinates','travelVector'):
        if key in m['location']: text_bound(m['location'][key],120)
    commander=m.get('commandingOfficerId')
    if m['status'] not in ('PLANNED','CANCELLED'): require(commander is not None,'Commander required')
    if commander is not None: require(re.fullmatch(r'C-[1-9][0-9]*',commander) is not None and len(commander)<=50,'Stored commander grammar/capacity')
    estimate=cents(m.get('estimatedCostCredits')); actual=cents(m.get('actualCostCredits'))
    require(estimate is None or estimate>=0,'Nonnegative estimate'); require(actual is None or actual>=0,'Nonnegative actual')
    terminal=m['status'] in ('COMPLETED','FAILED','CANCELLED')
    if terminal:
        require(actual is not None,'Terminal actual required')
        if m['status']!='CANCELLED' or not m['cancelledWithoutEstimateAllowed']: require(estimate is not None,'Estimate required')
    else:
        require(actual is None,'Nonterminal actual forbidden')
        if m['status']!='PLANNED': require(estimate is not None,'Authorized estimate required')
        require('outcome' not in m,'Nonterminal outcome forbidden')
    if 'outcome' in m: text_bound(m['outcome'],2000)
    require(m['status']=='CANCELLED' or not m['cancelledWithoutEstimateAllowed'],'Cancellation flag outside CANCELLED')
    for key,pattern,maximum in (('assignedCrewIds',r'C-[1-9][0-9]*',100),('participantIds',r'[PO]-[1-9][0-9]*',None),('assignedAssetIds',r'[A-Z]{2,5}-[1-9][0-9]*',50)):
        refs=m[key]; require(refs==sorted(set(refs)),'Canonical duplicate-free reference set')
        require(maximum is None or len(refs)<=maximum,'Collection bound')
        require(all(re.fullmatch(pattern,ref) is not None and len(ref)<=50 for ref in refs),'Stored reference grammar/capacity')
    require(re.fullmatch(r'ST-[A-Z0-9]{9}',m['missionId']) is not None,'Mission ID')
    require(re.fullmatch(r'4[3-8][0-9]{3}\.[0-9][05]',m['stardate']) is not None,'Stardate lattice')
    require(1<=m['priority']<=5 and 1<=m['durationHours']<=8760,'Priority/duration')
    moment(m['lastUpdated'])

def validate_data(data,manifest,provenance):
    missions=data['missions']; changes=data['changes']
    # Release 1.0 keeps its reviewed 20..100 range and snapshot mix. A larger release (D0NN) needs at least 20 missions.
    legacy=manifest['datasetVersion']=='1.0'
    require(((20<=len(missions)<=100) if legacy else len(missions)>=20) and len(changes)>=60,'Release count bounds')
    require(manifest['counts']=={'missions':len(missions),'changes':len(changes)},'Counts')
    if legacy: require(Counter(m['status'] for m in missions)==Counter({'COMPLETED':16,'PLANNED':4,'AUTHORIZED':3,'ACTIVE':3,'POSTPONED':2,'FAILED':2,'CANCELLED':1}),'Reviewed 1.0 snapshot mix')
    else:
        composition=manifest['composition']; origins=Counter(source['origin'] for source in provenance['missionSources'])
        require(origins=={'canon-carried':composition['canonCarried'],'canon':composition['canonNew'],'maintenance':composition['maintenanceGenerated'],'routine':composition['routineGenerated']},'Composition by origin')
        require(sum(composition[k] for k in ('canonCarried','canonNew','maintenanceGenerated','routineGenerated'))==len(missions),'Composition total')
        require(sum(1 for m in missions if m['type']=='MAINTENANCE')==composition['typeMaintenanceTotal'],'Maintenance total')
        require(all(source['synthetic'] for source in provenance['missionSources'] if source['origin'] in ('maintenance','routine')),'Generated missions labelled synthetic')
    ids=[m['missionId'] for m in missions]; require(ids==sorted(set(ids)),'Mission order/uniqueness')
    change_ids=[int(r['changeId']) for r in changes]
    require(change_ids==sorted(set(change_ids)),'Numeric change order/uniqueness')
    require(all(re.fullmatch(r'[1-9][0-9]*',r['changeId']) for r in changes),'Change lexical form')
    require(all(r['missionId'] in ids for r in changes),'No dangling audit')
    require(manifest['nextMissionOrdinal']==max(int(mid[3:],36) for mid in ids)+1,'Next mission ordinal')
    require(manifest['nextChangeId']==max(change_ids)+1,'Next change ID')
    require(manifest['clock']=={'baseline':max(r['changedAt'] for r in changes),'counter':0,'intervalMs':1000},'Clock baseline/state')
    corrections=manifest.get('corrections')
    correction_ids=set(r['changeId'] for r in changes[manifest['appendsTo']['changes']:]) if corrections else set()
    if corrections: require(len(correction_ids)==corrections['count'] and corrections['firstChangeId']==int(changes[manifest['appendsTo']['changes']]['changeId']),'Correction entries')
    for m in missions:
        domain(m)
        history=[r for r in changes if r['missionId']==m['missionId']]
        require(history and history[0]['operation']=='CREATED' and 'previousStatus' not in history[0],'Initial audit')
        previous=None; cancellation=False
        for i,row in enumerate(history):
            require(row['operation']==('CREATED' if i==0 else 'UPDATED'),'Operation population')
            require(row['newStatus'] in STATES,'Audit status')
            if row['changeId'] in correction_ids:
                # a records clean-up appended by an appended release: the state is unchanged, only the participants were corrected
                require(previous is not None and row['previousStatus']==row['newStatus']==previous['newStatus'],'Correction keeps the status')
                require(all(row.get(f)==previous.get(f) and (row.get(f+'Change')=='0.00')==(row.get(f) is not None) for f in ('estimatedCostCredits','actualCostCredits')),'Correction keeps the costs')
            if previous:
                require(row.get('previousStatus')==previous['newStatus'],'Audit status chain')
                require(moment(row['changedAt'])>moment(previous['changedAt']),'Strict curated local chronology')
            require(all(re.fullmatch(r'C-[1-9][0-9]*',row[actor]) and len(row[actor])<=50 for actor in ('changedBy','orderedBy')),'Audit actors')
            text_bound(row['summary'],256)
            if row['newStatus']=='CANCELLED': cancellation=(previous is not None and (previous['newStatus']=='PLANNED' or previous['newStatus']=='CANCELLED' and cancellation))
            else: cancellation=False
            resulting={'status':row['newStatus'],'estimatedCostCredits':row.get('estimatedCostCredits'),'actualCostCredits':row.get('actualCostCredits')}
            if row['newStatus'] not in ('PLANNED','CANCELLED'): require(resulting['estimatedCostCredits'] is not None,'Audit estimate lifecycle')
            terminal=row['newStatus'] in ('COMPLETED','FAILED','CANCELLED')
            require((resulting['actualCostCredits'] is not None)==terminal,'Audit actual lifecycle')
            if row['newStatus']=='CANCELLED' and not cancellation: require(resulting['estimatedCostCredits'] is not None,'Cancellation estimate')
            for field in ('estimatedCostCredits','actualCostCredits'):
                value=cents(row.get(field)); prior=cents(previous.get(field)) if previous else None
                delta=cents(row.get(field+'Change'))
                zero_ok=not legacy and field=='actualCostCredits' and value==0 and row['newStatus']=='CANCELLED' and cancellation and row.get('estimatedCostCredits') is None
                require(value is None or value>0 or zero_ok,'Positive curated cost-bearing value')
                require(delta==(None if value is None or prior is None else value-prior),'Exact absence-aware audit cost delta')
            previous=row
        curated=[r for r in history if r['changeId'] not in correction_ids]
        duration=moment(curated[-1]['changedAt'])-moment(history[0]['changedAt'])
        budget=timedelta(hours=m['durationHours'])
        require(duration<=budget,'Curated duration exceeded')
        if m['status'] in ('COMPLETED','FAILED','CANCELLED'): require(duration==budget,'Terminal duration closure')
        require(m['cancelledWithoutEstimateAllowed']==cancellation,'Final cancellation provenance')
        require(m['currentChangeId']==history[-1]['changeId'] and m['lastUpdated']==history[-1]['changedAt'] and m['status']==history[-1]['newStatus'],'Final current state')
        for field in ('estimatedCostCredits','actualCostCredits'): require(m.get(field)==history[-1].get(field),'Final cost state')
    if legacy: require([r['changedAt'] for r in changes]==sorted(r['changedAt'] for r in changes),'Global curated chronology')
    else:
        # Appended release: the carried entries and the appended entries are each in time order; the appended ones carry the higher change ids.
        cut=manifest['appendsTo']['changes']
        bounds=[0]+manifest['appendsTo'].get('earlierCuts',[])+[cut,len(changes)]
        for lo,hi in zip(bounds,bounds[1:]):
            segment=changes[lo:hi]; require([r['changedAt'] for r in segment]==sorted(r['changedAt'] for r in segment),'Segment chronology')
        require(all(r['missionId'] in {m['missionId'] for m in missions[:manifest['appendsTo']['missions']]} for r in changes[:cut]),'Carried entries belong to carried missions')
    sources=provenance['missionSources']; event_notes=provenance['events']
    require(len(sources)==len(missions) and len(event_notes)==len(changes),'Provenance coverage')
    keys={source['key']:m['missionId'] for source,m in zip(sources,missions)}
    event_times={(e['missionId'],e['eventKey']):e['changedAt'] for e in event_notes}
    for edge in manifest['recipe']['causalEdges']:
        require(event_times[(keys[edge['from']],edge['event'])]<event_times[(keys[edge['to']],'event-1')],'Cross-mission causality')
    return data

def check_participants(path,manifest,data,provenance):
    """The lead developer's definitions of the reference classes, as a check of the release itself: no C reference among the participants, every
    P reference names exactly one civilian of the pinned Personnel roster by exact display name and is no crew member of the same
    mission, no O reference names a person of the roster or a crew member, and the participant table holds what the missions use."""
    table=json.loads(content(path/'participants.json')); roster=json.loads(content(path/'civilians.json'))
    require(manifest['participantClasses']['personnelManifestSha256']==roster['manifestSha256'] and manifest['participantClasses']['civilians']==len(roster['civilians']),'Pinned Personnel roster')
    civilians=[c['name'] for c in roster['civilians']]
    earlier=json.loads(content(HERE/'releases'/manifest['appendsTo']['datasetVersion']/'recipe.json'))['references']
    crew=dict(earlier['crew'],**earlier['unmappedCrew'])
    used=set()
    for m in data['missions']:
        assigned=set(m['assignedCrewIds'])|({m['commandingOfficerId']} if m.get('commandingOfficerId') else set())
        for ref in m['participantIds']:
            used.add(ref)
            require(not ref.startswith('C-') and ref in table,'Participant class and table: '+ref)
            require(crew.get(table[ref]['name']) not in assigned,'A participant is also assigned crew: '+ref)
    require(used==set(table),'The participant table holds exactly the references the missions use')
    for ref,entry in table.items():
        require(entry['class']==ref[0],'Entry class equals the reference class: '+ref)
        if ref[0]=='P': require(civilians.count(entry['name'])==1,'A P reference names exactly one civilian: '+ref)
        else: require(entry['name'] not in civilians and entry['name'] not in crew,'An O reference names no one of the roster: '+ref)
    counts=Counter(ref[0] for ref in table)
    require(manifest['participantClasses']['referencesP']==counts['P'] and manifest['participantClasses']['referencesO']==counts['O'],'Participant reference counts')
    require(len(provenance['participantCorrections'])==manifest['corrections']['count'],'Provenance names each correction')

def release_path(version):
    require(re.fullmatch(r'[1-9][0-9]*\.(0|[1-9][0-9]*)',version) is not None,'Explicit MAJOR.MINOR required')
    path=HERE/'releases'/version
    require(path.is_dir() and not path.is_symlink(),'Unknown/indirect immutable release')
    return path

def validate_release(version,directory=None):
    path=release_path(version) if directory is None else Path(directory)
    require(path.is_dir() and not path.is_symlink(),'Release directory')
    require(not any(p.is_symlink() for p in path.iterdir()),'Indirect release files')
    manifest=json.loads(content(path/'manifest.json'))
    require(manifest['datasetVersion']==version and manifest['contractRevision']=='1.1','Selected version/contract')
    require(set(p.name for p in path.iterdir())==set(manifest['files'])|{'manifest.json'},'Exact release inventory')
    for name,expected in manifest['files'].items():
        require(re.fullmatch(r'[A-Za-z0-9_.-]+',name) is not None,'Unsafe manifest path')
        require(sha(content(path/name))==expected,'Integrity: '+name)
    for name,expected in manifest['sources'].items(): require(sha(content(path/name))==expected,'Archived source integrity')
    require(json.loads(content(path/'recipe.json'))==manifest['recipe'],'Recipe binding')
    require(sha(content(COMPONENT/'contracts/missions-v1.1.xsd'))==manifest['contractSha256'],'Immutable selected contract')
    require(sha(content(COMPONENT/'contracts/missions-v1.0.xsd'))==manifest['preservedContract10Sha256'],'Preserved 1.0 contract')
    data=json.loads(content(path/'release.json')); provenance=json.loads(content(path/'provenance.json'))
    require(data['datasetVersion']==version and data['contractRevision']=='1.1','Data version')
    validate_data(data,manifest,provenance)
    if version!='1.0':
        # An appended release keeps release 1.0's missions and change entries byte for byte, and continues its sequences.
        carried=manifest['appendsTo']; earlier=json.loads(content(HERE/'releases'/carried['datasetVersion']/'release.json')); earlier_manifest=json.loads(content(HERE/'releases'/carried['datasetVersion']/'manifest.json'))
        require(data['changes'][:carried['changes']]==earlier['changes'],'Appended prefix equals the earlier release')
        if 'corrections' in manifest:
            # only the participants of a corrected mission, with its lastUpdated and currentChangeId, differ from the earlier release
            corrected={r['missionId'] for r in data['changes'][carried['changes']:]}
            require(len(data['missions'])==carried['missions'] and len(corrected)==manifest['corrections']['count'],'Corrections name each mission once')
            for new,old in zip(data['missions'],earlier['missions']):
                if new['missionId'] in corrected:
                    changed={k for k in set(new)|set(old) if new.get(k)!=old.get(k)}
                    require(changed<={'participantIds','lastUpdated','currentChangeId'} and 'participantIds' in changed,'A correction changes only the participants and the current state')
                else: require(new==old,'An uncorrected mission equals the earlier release')
            check_participants(path,manifest,data,provenance)
        else: require(data['missions'][:carried['missions']]==earlier['missions'],'Appended prefix equals the earlier release')
        require(carried['nextMissionOrdinal']==earlier_manifest['nextMissionOrdinal'] and carried['nextChangeId']==earlier_manifest['nextChangeId'] and manifest['firstMissionOrdinal']==earlier_manifest['firstMissionOrdinal'] and manifest['firstChangeId']==earlier_manifest['firstChangeId'],'Sequences continue the earlier release')
    from lxml import etree
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False)
    xsd=etree.XMLSchema(etree.parse(str(COMPONENT/'contracts/missions-v1.1.xsd'),parser))
    for name in manifest['files']:
        if name.endswith('.xml'):
            raw=content(path/name); require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw,'DTD/entity forbidden')
            require(xsd.validate(etree.fromstring(raw,parser)), 'Released XML schema: '+name)
    # Compare every serialized XML scalar/collection to the authoritative JSON,
    # not just XSD shape/counts; divergent-but-valid XML must fail.
    ns={'m':'urn:starfleet:missions:v1'}
    if version=='1.0': mission_pages=['missions.xml']
    else: mission_pages=['missions-%d.xml'%page for page in range(1,(len(data['missions'])+49)//50+1)]
    xml_missions=[]
    for number,name in enumerate(mission_pages,1):
        root=etree.fromstring(content(path/name),parser)
        if version!='1.0': require([root.findtext('m:'+k,namespaces=ns) for k in ('page','pageSize','totalCount','totalPages')]==[str(number),'50',str(len(data['missions'])),str(len(mission_pages))],'Mission XML paging')
        xml_missions += root.findall('m:mission',ns)
    require(len(xml_missions)==len(data['missions']),'Mission XML inventory')
    for node,m in zip(xml_missions,data['missions']):
        for key in ('missionId','title','type','classification','status','priority','stardate','durationHours','objective','issuingAuthority','commandingOfficerId','estimatedCostCredits','actualCostCredits','outcome','lastUpdated'):
            expected=m.get(key); require(node.findtext('m:'+key,namespaces=ns)==(None if expected is None else str(expected)),'XML scalar '+key)
        for key,singular in (('assignedCrewIds','crewId'),('participantIds','participantId'),('assignedAssetIds','assetId')):
            require([n.text for n in node.findall('m:'+key+'/m:'+singular,ns)]==m[key],'XML collection '+key)
        for key in ('type','name','coordinates','travelVector'): require(node.findtext('m:location/m:'+key,namespaces=ns)==m['location'].get(key),'XML location')
    xml_changes=[]
    for page in range(1,(len(data['changes'])+49)//50+1):
        root=etree.fromstring(content(path/f'changes-{page}.xml'),parser)
        require(root.findtext('m:page',namespaces=ns)==str(page),'Audit XML paging')
        if version!='1.0': require([root.findtext('m:'+k,namespaces=ns) for k in ('pageSize','totalCount','totalPages')]==['50',str(len(data['changes'])),str((len(data['changes'])+49)//50)],'Audit XML page metadata')
        xml_changes += root.findall('m:change',ns)
    require(len(xml_changes)==len(data['changes']),'Audit XML count')
    for node,row in zip(xml_changes,data['changes']):
        for key in ('changeId','missionId','operation','changedAt','changedBy','orderedBy','previousStatus','newStatus','estimatedCostCredits','estimatedCostCreditsChange','actualCostCredits','actualCostCreditsChange','summary'):
            require(node.findtext('m:'+key,namespaces=ns)==row.get(key),'Audit XML scalar '+key)
    return path,manifest,data
