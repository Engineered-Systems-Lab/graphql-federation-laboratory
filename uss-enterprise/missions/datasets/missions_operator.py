"""Explicit reviewed Oracle data environment and stopped-service release reset.

No command starts Missions. SQLPlus is inside the selected Oracle container.
Only the fixed ownership-labeled database and Missions schema are managed.
Dependencies/images are never provisioned implicitly by acceptance or reset.
"""
from pathlib import Path
import argparse
import json
import os
import re
import secrets
import subprocess
import time
from validate_release import validate_release,require,content

HERE=Path(__file__).resolve().parent
ENV=json.loads(content(HERE/'oracle-environment.json'))
TABLES=('MISSIONS','MISSION_ASSIGNED_CREW','MISSION_PARTICIPANTS','MISSION_ASSIGNED_ASSETS','MISSION_CHANGES','MISSION_CLOCK')
EXTRA=('MISSION_ID_SEQ','CHANGE_ID_SEQ','MISSIONS_IDENTITY_IMMUTABLE','MISSION_CHANGES_APPEND_ONLY','MISSIONS_CLOCK_TICK','MISSIONS_OUTCOME_DOMAIN','MISSION_CHANGES_ORDER')

def command(argv,input=None,timeout=120,env=None):
    result=subprocess.run(argv,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=env)
    if result.returncode:
        # Do not expose Docker inspect environment or passwords.
        raise RuntimeError('Command failed ('+str(result.returncode)+'): '+argv[0]+' '+argv[1]+'\n'+result.stderr.decode('utf-8','replace')+result.stdout.decode('utf-8','replace'))
    return result.stdout.decode('utf-8','replace')

def container_exists(name):
    names=command(['docker','ps','-a','--format','{{.Names}}']).splitlines()
    return name in names

def db_guard():
    require(container_exists(ENV['container']),'Reviewed database container absent; provision explicitly')
    # Only a minimal projection is read: no credential-containing environment.
    info=json.loads(command(['docker','inspect','--format','{"image":{{json .Config.Image}},"running":{{json .State.Running}},"labels":{{json .Config.Labels}}}',ENV['container']]))
    key,value=ENV['ownershipLabel'].split('=',1)
    require(info['labels'].get(key)==value and info['image']==ENV['image']+'@'+ENV['digest'],'Database ownership/image mismatch')
    require(info['running'],'Database is not running')
    mode=command(['docker','inspect','--format','{{.HostConfig.NetworkMode}}',ENV['container']]).strip()
    require(mode==ENV['network'],'Database network mismatch')
    network_guard()

def network_guard():
    info=json.loads(command(['docker','network','inspect','--format','{"internal":{{json .Internal}},"driver":{{json .Driver}},"labels":{{json .Labels}}}',ENV['network']]))
    key,value=ENV['ownershipLabel'].split('=',1)
    require(info['internal'] is True and info['driver']=='bridge' and (info['labels'] or {}).get(key)==value,'Network isolation/ownership mismatch')

def provision_network():
    names=command(['docker','network','ls','--format','{{.Name}}']).splitlines()
    if ENV['network'] not in names:
        command(['docker','network','create','--internal','--driver',ENV['networkDriver'],'--label',ENV['ownershipLabel'],ENV['network']])
    network_guard()

def service_stopped():
    name=ENV['serviceContainer']
    if container_exists(name):
        running=command(['docker','inspect','--format','{{.State.Running}}',name]).strip()
        require(running=='false','Missions service must be stopped before reset')
    # Scope is the documented deployment name, not arbitrary unregistered hosts.

def schema_name(name):
    require(name==ENV['schema'] or re.fullmatch(r'MS_TEST_[A-F0-9]{12}',name) is not None,'Unowned schema name')
    return name

def sql(text,schema=None,timeout=120):
    if schema: schema_name(schema)
    prefix='WHENEVER OSERROR EXIT FAILURE ROLLBACK\nWHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK\n'
    prefix+='\n'.join('SET '+setting for setting in ('ECHO OFF','FEEDBACK OFF','HEADING OFF','PAGESIZE 0','VERIFY OFF','DEFINE OFF','LINESIZE 32767','LONG 1000000','LONGCHUNKSIZE 1000000','TRIMSPOOL ON'))+'\n'
    prefix+='ALTER SESSION SET CONTAINER = '+ENV['pdb']+';\nALTER SESSION SET TIME_ZONE = \'+00:00\';\n'
    if schema: prefix+='ALTER SESSION SET CURRENT_SCHEMA = '+schema+';\n'
    output=command(['docker','exec','--user','oracle','-i','-e','NLS_LANG=.AL32UTF8',ENV['container'],'sqlplus','-L','-s','/ as sysdba'],
                   input=(prefix+text+'\nEXIT SUCCESS\n').encode('utf-8'),timeout=timeout)
    require(re.search(r'(?m)^(ORA-|SP2-|PLS-)',output) is None,'SQLPlus reported failure: '+output)
    return output.strip()

def create_schema(name):
    schema_name(name)
    sql('CREATE USER '+name+' NO AUTHENTICATION DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;')

def drop_test_schema(name):
    require(re.fullmatch(r'MS_TEST_[A-F0-9]{12}',name) is not None,'Only disposable test schemas may be dropped')
    sql('DROP USER '+name+' CASCADE;')

def known_objects(name):
    rows=sql("SELECT object_name||'|'||object_type FROM all_objects WHERE owner='"+schema_name(name)+"' AND object_type IN ('TABLE','SEQUENCE','TRIGGER','FUNCTION','PACKAGE','VIEW','INDEX');").splitlines()
    for row in rows:
        obj,kind=row.split('|',1)
        require(obj in TABLES+EXTRA or kind=='INDEX' and obj.startswith('SYS_'),'Unexpected schema object; reset refused: '+row)

def reset(version,schema=None,check_service=True):
    path,manifest,data=validate_release(version)
    db_guard()
    if check_service: service_stopped()
    name=schema_name(schema or ENV['schema'])
    exists=sql("SELECT COUNT(*) FROM all_users WHERE username='"+name+"';").strip()=='1'
    if not exists: create_schema(name)
    known_objects(name)
    # Separate DDL stages intentionally have no whole-reset rollback claim.
    objects=sql("SELECT table_name FROM all_tables WHERE owner='"+name+"';").splitlines()
    for table in ('MISSION_ASSIGNED_CREW','MISSION_PARTICIPANTS','MISSION_ASSIGNED_ASSETS','MISSION_CHANGES','MISSION_CLOCK','MISSIONS'):
        if table in objects: sql('DROP TABLE '+table+' CASCADE CONSTRAINTS PURGE;',name)
    for typ,obj in (('SEQUENCE','MISSION_ID_SEQ'),('SEQUENCE','CHANGE_ID_SEQ'),('FUNCTION','MISSIONS_CLOCK_TICK')):
        count=sql("SELECT COUNT(*) FROM all_objects WHERE owner='"+name+"' AND object_name='"+obj+"' AND object_type='"+typ+"';")
        if count.strip()=='1': sql('DROP '+typ+' '+obj+';',name)
    sql(content(path/'schema.sql').decode('utf-8'),name)
    invalid=sql("SELECT COUNT(*) FROM all_objects WHERE owner='"+name+"' AND status!='VALID';")
    require(invalid.strip()=='0','Schema has invalid executable objects')
    sql(content(path/'load.sql').decode('utf-8'),name)
    verify_loaded(name,manifest,data)
    if check_service: service_stopped()
    print('Restored explicit dataset '+version+'; '+str(len(data['missions']))+' missions / '+str(len(data['changes']))+' changes; Missions remains stopped.')

def verify_loaded(name,manifest,data):
    table_count=sql("SELECT COUNT(*) FROM all_tables WHERE owner='"+schema_name(name)+"';")
    require(table_count.strip()=='6','Six-table inventory')
    expected={ 'MISSIONS':len(data['missions']),'MISSION_CHANGES':len(data['changes']),
              'MISSION_ASSIGNED_CREW':sum(len(m['assignedCrewIds']) for m in data['missions']),
              'MISSION_PARTICIPANTS':sum(len(m['participantIds']) for m in data['missions']),
              'MISSION_ASSIGNED_ASSETS':sum(len(m['assignedAssetIds']) for m in data['missions']),'MISSION_CLOCK':1}
    for table,count in expected.items(): require(sql('SELECT COUNT(*) FROM '+table+';',name).strip()==str(count),'Loaded count '+table)
    # Oracle-generated canonical JSON yields a comparison of every stored scalar,
    # CLOB, NULL, actor, decimal and child reference with the release oracle.
    rows=sql("""SELECT JSON_OBJECT('missionId' VALUE mission_id,'title' VALUE title,'type' VALUE mission_type,
      'classification' VALUE classification,'status' VALUE status,'priority' VALUE priority,
      'stardate' VALUE TO_CHAR(stardate,'FM00000.00'),'durationHours' VALUE duration_hours,
      'objective' VALUE objective,'locationType' VALUE location_type,'locationName' VALUE location_name,
      'coordinates' VALUE coordinates,'travelVector' VALUE travel_vector,'issuingAuthority' VALUE issuing_authority,
      'commandingOfficerId' VALUE commanding_officer_id,
      'estimatedCostCredits' VALUE TO_CHAR(estimated_cost,'FM9999999999990.00'),
      'actualCostCredits' VALUE TO_CHAR(actual_cost,'FM9999999999990.00'),'outcome' VALUE outcome,
      'lastUpdated' VALUE TO_CHAR(last_updated,'YYYY-MM-DD"T"HH24:MI:SS.FF3"Z"'),
      'currentChangeId' VALUE TO_CHAR(current_change_id,'FM9999999999999999999999999990'),
      'cancelFlag' VALUE cancelled_without_estimate_allowed NULL ON NULL RETURNING CLOB)
      FROM missions ORDER BY mission_id;""",name).splitlines()
    require(len(rows)==len(data['missions']),'Loaded scalar row count')
    for raw,m in zip(rows,data['missions']):
        row=json.loads(raw)
        for key in ('missionId','title','type','classification','status','priority','stardate','durationHours','objective','issuingAuthority','commandingOfficerId','estimatedCostCredits','actualCostCredits','outcome','lastUpdated','currentChangeId'):
            require(row[key]==m.get(key),'Loaded scalar '+key)
        require(row['cancelFlag']==int(m['cancelledWithoutEstimateAllowed']),'Loaded cancellation flag')
        for db,key in (('locationType','type'),('locationName','name'),('coordinates','coordinates'),('travelVector','travelVector')):
            require(row[db]==m['location'].get(key),'Loaded location')
    for field,table in (('assignedCrewIds','mission_assigned_crew'),('participantIds','mission_participants'),('assignedAssetIds','mission_assigned_assets')):
        expected_rows=sorted(m['missionId']+'|'+ref for m in data['missions'] for ref in m[field])
        require(sql("SELECT mission_id||'|'||reference FROM "+table+' ORDER BY mission_id,reference;',name).splitlines()==expected_rows,'Loaded child references')
    rows=sql("""SELECT JSON_OBJECT('changeId' VALUE TO_CHAR(change_id,'FM9999999999999999999999999990'),
      'missionId' VALUE mission_id,'operation' VALUE operation,'changedAt' VALUE TO_CHAR(changed_at,'YYYY-MM-DD"T"HH24:MI:SS.FF3"Z"'),
      'changedBy' VALUE changed_by,'orderedBy' VALUE ordered_by,'previousStatus' VALUE previous_status,'newStatus' VALUE new_status,
      'estimatedCostCredits' VALUE TO_CHAR(estimated_cost,'FM9999999999990.00'),
      'estimatedCostCreditsChange' VALUE TO_CHAR(estimated_cost_change,'FM9999999999990.00'),
      'actualCostCredits' VALUE TO_CHAR(actual_cost,'FM9999999999990.00'),
      'actualCostCreditsChange' VALUE TO_CHAR(actual_cost_change,'FM9999999999990.00'),
      'summary' VALUE summary NULL ON NULL RETURNING CLOB) FROM mission_changes ORDER BY change_id;""",name).splitlines()
    require(len(rows)==len(data['changes']),'Loaded audit row count')
    for raw,expected_row in zip(rows,data['changes']):
        row=json.loads(raw)
        for key,value in row.items(): require(value==expected_row.get(key),'Loaded audit '+key)
    clock=sql("SELECT TO_CHAR(baseline,'YYYY-MM-DD\"T\"HH24:MI:SS.FF3\"Z\"')||'|'||counter||'|'||interval_ms||'|'||dataset_version||'|'||release_sha256 FROM mission_clock;",name)
    require(clock==manifest['clock']['baseline']+'|0|1000|'+manifest['datasetVersion']+'|'+manifest['files']['release.json'],'Loaded clock/release identity')
    seq=sql("SELECT sequence_name||'|'||TO_CHAR(last_number,'FM9999999999999999999999999990') FROM all_sequences WHERE sequence_owner='"+name+"' ORDER BY sequence_name;")
    require(seq.splitlines()==['CHANGE_ID_SEQ|'+str(manifest['nextChangeId']),'MISSION_ID_SEQ|'+str(manifest['nextMissionOrdinal'])],'Restored next sequence values')
    require(sql("SELECT value FROM nls_database_parameters WHERE parameter='NLS_CHARACTERSET';")=='AL32UTF8','Database Unicode charset')
    version=sql("SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%';")
    require(version.startswith('18.'),'Oracle 18c required')
    print('Observed Oracle '+version+' / AL32UTF8; exact loaded release comparison passed.')

def provision():
    require(not container_exists(ENV['container']),'Container already exists; inspect rather than reuse/rebind')
    image=ENV['image']+'@'+ENV['digest']
    command(['docker','pull','--platform',ENV['platform'],image],timeout=1800)
    provision_network()
    env=os.environ.copy(); env['ORACLE_PWD']='Ms'+secrets.token_hex(12)+'9'
    command(['docker','run','-d','--name',ENV['container'],'--label',ENV['ownershipLabel'],
             '--hostname',ENV['hostname'],'--platform',ENV['platform'],'--memory',ENV['memory'],'--cpus',ENV['cpus'],'--shm-size',ENV['shmSize'],
             '--network',ENV['network'],'--env','ORACLE_PWD','--env','ORACLE_CHARACTERSET='+ENV['charset'],image],env=env)
    print('Owned Oracle container created. No host ports, host mounts or Missions startup.')
    deadline=time.monotonic()+ENV['readyTimeoutSeconds']
    while time.monotonic()<deadline:
        state=command(['docker','inspect','--format','{{.State.Status}}',ENV['container']]).strip()
        require(state=='running','Oracle exited during startup; owned container preserved for diagnosis')
        try:
            if sql('SELECT 1 FROM dual;',timeout=20)=='1':
                db_guard(); print('Oracle SQLPlus ready in '+ENV['pdb']); return
        except (RuntimeError,ValueError,subprocess.TimeoutExpired): pass
        time.sleep(5)
    raise RuntimeError('Oracle readiness timed out; owned container preserved for inspection, not automatically removed')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('provision')
    reset_parser=sub.add_parser('reset'); reset_parser.add_argument('--dataset',required=True)
    args=parser.parse_args()
    if args.action=='provision': provision()
    else: reset(args.dataset)

if __name__=='__main__': main()
