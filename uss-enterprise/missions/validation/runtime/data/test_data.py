"""Real Oracle 18c acceptance for the schema/release/reset slice only.

The reviewed database must already be provisioned. Missing Docker/Oracle is a
failure. A unique schema is created and only that owned schema is dropped.
No HTTP, JDBC, REST service or packaging conformance is claimed.
"""
from pathlib import Path
from copy import deepcopy
import concurrent.futures
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tempfile
import time
import unittest

COMPONENT=Path(__file__).resolve().parents[3]
DATASETS=COMPONENT/'datasets'
sys.path.insert(0,str(DATASETS))
import generate
# Avoid collision with Python's standard-library operator module.
spec=importlib.util.spec_from_file_location('missions_operator',DATASETS/'missions_operator.py')
operator=importlib.util.module_from_spec(spec); spec.loader.exec_module(operator)
import validate_release as validation

class ReleaseAcceptance(unittest.TestCase):
    def test_01_immutable_integrity_and_domain(self):
        path,manifest,data=validation.validate_release('1.0')
        self.assertEqual(manifest['counts'],{'missions':31,'changes':101})
        self.assertEqual(manifest['recipe']['masterSeed'],1701)

    def test_02_archived_reproduction_and_category_isolation(self):
        path,manifest,_=validation.validate_release('1.0')
        spec=importlib.util.spec_from_file_location('archived_generator',path/'generate.py')
        archived=importlib.util.module_from_spec(spec); spec.loader.exec_module(archived)
        archived.COMPONENT=COMPONENT
        files=archived.generate()
        self.assertEqual(set(files),set(p.name for p in path.iterdir()))
        for name,expected in files.items(): self.assertEqual(expected,validation.content(path/name),name)
        a=generate.Stream('estimated_cost','ST-00000AAAA','event-1')
        expected=a.integer(1,1000000)
        unrelated=generate.Stream('history_timing','ST-00000BBBB','event-99')
        for _ in range(100): unrelated.integer(5,45)
        self.assertEqual(generate.Stream('estimated_cost','ST-00000AAAA','event-1').integer(1,1000000),expected)
        # Independent proof of the first stream block, rather than a self-derived golden.
        key=b'["missions-generator-1",1701,"mission_id_start","",""]'
        seed=hashlib.sha256(key).digest()
        block=int.from_bytes(hashlib.sha256(seed+b'\0'*8).digest(),'big')
        self.assertEqual(generate.Stream('mission_id_start').integer(0,2**256-1),block)
        with self.assertRaisesRegex(ValueError,'overflow'): generate.mission_id(36**9)
        self.assertEqual(generate.mission_id(36**9-1),'ST-ZZZZZZZZZ')
        with self.assertRaisesRegex(ValueError,'256-bit'): generate.Stream('mission_id_start').integer(0,2**256)

    def test_03_reject_tamper_and_semantic_history_corruption(self):
        path,manifest,data=validation.validate_release('1.0')
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)
            for file in path.iterdir(): (copied/file.name).write_bytes(validation.content(file))
            (copied/'load.sql').write_bytes(validation.content(copied/'load.sql')+b'--tampered\n')
            with self.assertRaisesRegex(ValueError,'Integrity'): validation.validate_release('1.0',copied)
        provenance=json.loads(validation.content(path/'provenance.json'))
        damaged=deepcopy(data)
        damaged['changes'][1]['estimatedCostCreditsChange']='999999.99'
        with self.assertRaises(ValueError): validation.validate_data(damaged,manifest,provenance)
        damaged=deepcopy(data); damaged['missions'][0]['currentChangeId']='1'
        with self.assertRaisesRegex(ValueError,'Final current state'): validation.validate_data(damaged,manifest,provenance)
        with self.assertRaisesRegex(ValueError,'Unknown'): validation.validate_release('1.999')

    def test_04_objective_and_unicode_domain_bounds(self):
        _,_,data=validation.validate_release('1.0')
        m=deepcopy(data['missions'][0]); m['objective']='\U0001F680'*2000; m['title']='\U0001F680'*120
        validation.domain(m)
        m['objective']+='\U0001F680'
        with self.assertRaisesRegex(ValueError,'Text'): validation.domain(m)
        m=deepcopy(data['missions'][0]); m['title']='\u2000'*2
        with self.assertRaisesRegex(ValueError,'Text'): validation.domain(m)

class OracleAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        operator.db_guard()
        cls.schema='MS_TEST_'+secrets.token_hex(6).upper()
        cls.owned=False
        operator.create_schema(cls.schema); cls.owned=True
        try:
            operator.reset('1.0',cls.schema)
            cls.path,cls.manifest,cls.data=validation.validate_release('1.0')
        except Exception:
            operator.drop_test_schema(cls.schema); cls.owned=False
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.owned: operator.drop_test_schema(cls.schema)

    def sql(self,text): return operator.sql(text,self.schema)

    def test_01_real_ddl_load_every_field_and_indexes(self):
        operator.verify_loaded(self.schema,self.manifest,self.data)
        count=operator.sql("SELECT COUNT(*) FROM all_indexes WHERE owner='"+self.schema+"' AND index_name='MISSION_CHANGES_ORDER';")
        self.assertEqual(count,'1')
        rows=self.sql('SELECT mission_type FROM missions WHERE mission_type=\'MAINTENANCE\' ORDER BY mission_id;')
        self.assertEqual(rows.splitlines(),['MAINTENANCE','MAINTENANCE'])

    def test_02_database_clock_rollback_and_shared_timestamp(self):
        self.sql("""DECLARE v TIMESTAMP(3); c NUMBER; BEGIN
          v := missions_clock_tick(); SELECT counter INTO c FROM mission_clock;
          IF c != 1 THEN RAISE_APPLICATION_ERROR(-20901,'Advance before use'); END IF;
          SELECT COUNT(*) INTO c FROM mission_clock WHERE v=baseline+NUMTODSINTERVAL(1,'SECOND');
          IF c != 1 THEN RAISE_APPLICATION_ERROR(-20902,'Exact synthetic millisecond timestamp'); END IF;
          ROLLBACK;
          SELECT counter INTO c FROM mission_clock;
          IF c != 0 THEN RAISE_APPLICATION_ERROR(-20903,'Clock rollback'); END IF;
        END;
        /""")

    def test_03_resource_children_clock_atomic_failure(self):
        mid=self.data['missions'][0]['missionId']
        self.sql("""DECLARE v TIMESTAMP(3); c NUMBER; original_title VARCHAR2(144 CHAR); BEGIN
          SELECT title INTO original_title FROM missions WHERE mission_id='"""+mid+"""';
          BEGIN
            v:=missions_clock_tick();
            UPDATE missions SET title='atomic failure probe',last_updated=v WHERE mission_id='"""+mid+"""';
            INSERT INTO mission_assigned_crew VALUES ('"""+mid+"""','C-991');
            INSERT INTO mission_changes SELECT * FROM mission_changes WHERE change_id=(SELECT MIN(change_id) FROM mission_changes);
            RAISE_APPLICATION_ERROR(-20904,'Duplicate audit should fail');
          EXCEPTION WHEN DUP_VAL_ON_INDEX THEN ROLLBACK; END;
          SELECT COUNT(*) INTO c FROM missions WHERE mission_id='"""+mid+"""' AND title=original_title;
          IF c!=1 THEN RAISE_APPLICATION_ERROR(-20905,'Scalar rollback'); END IF;
          SELECT counter INTO c FROM mission_clock;
          IF c!=0 THEN RAISE_APPLICATION_ERROR(-20906,'Clock rollback'); END IF;
          SELECT COUNT(*) INTO c FROM mission_assigned_crew WHERE reference='C-991';
          IF c!=0 THEN RAISE_APPLICATION_ERROR(-20907,'Collection rollback'); END IF;
        END;
        /""")

    def test_04_constraints_and_immutable_audit(self):
        mid=self.data['missions'][0]['missionId']
        for statement,pattern in (
            ("INSERT INTO mission_participants VALUES ('"+mid+"','C-777');",'ORA-02290'),
            ("INSERT INTO mission_assigned_crew VALUES ('ST-000000001','C-777');",'ORA-02291'),
            ("UPDATE missions SET mission_id='ST-000000001' WHERE mission_id='"+mid+"';",'ORA-20001'),
            ('UPDATE mission_changes SET summary=\'rewritten\';','ORA-20002'),
            ('DELETE FROM mission_changes;','ORA-20002'),
            ("UPDATE missions SET status='PLANNED',actual_cost=0 WHERE mission_id='"+mid+"';",'ORA-02290')):
            with self.assertRaisesRegex((RuntimeError,ValueError),pattern): self.sql(statement)
        operator.verify_loaded(self.schema,self.manifest,self.data)

    def test_05_actual_unicode_clob_and_text_headroom(self):
        mid=self.data['missions'][1]['missionId']
        result=self.sql("""DECLARE v CLOB := TO_CLOB('x'); t VARCHAR2(144 CHAR); c NUMBER; BEGIN
          v:=NULL;
          FOR i IN 1..2000 LOOP v:=v||TO_CLOB(UNISTR('\\D83D\\DE80')); END LOOP;
          FOR i IN 1..120 LOOP t:=t||TO_CHAR(UNISTR('\\D83D\\DE80')); END LOOP;
          UPDATE missions SET objective=v,title=t WHERE mission_id='"""+mid+"""';
          SELECT LENGTH(title) INTO c FROM missions WHERE mission_id='"""+mid+"""';
          IF c!=120 THEN RAISE_APPLICATION_ERROR(-20908,'Supplementary title code points'); END IF;
          SELECT DBMS_LOB.GETLENGTH(objective) INTO c FROM missions WHERE mission_id='"""+mid+"""';
          -- Oracle CLOB length semantics can count supplementary characters as
          -- UCS2 units; preserve content and verify UTF-8 byte length separately.
          IF c NOT IN (2000,4000) THEN RAISE_APPLICATION_ERROR(-20909,'CLOB preserved length'); END IF;
        END;
        /
        SELECT objective FROM missions WHERE mission_id='"""+mid+"""';
        SELECT title FROM missions WHERE mission_id='"""+mid+"""';
        ROLLBACK;
        """)
        self.assertEqual(result.splitlines(),["\U0001F680"*2000,"\U0001F680"*120])
        self.assertEqual(self.sql("SELECT title FROM missions WHERE mission_id='"+mid+"';"),self.data['missions'][1]['title'])

    def test_06_zero_absence_decimal_capacity_and_ref_limit(self):
        mid=self.data['missions'][1]['missionId']
        self.sql("""DECLARE c NUMBER; BEGIN
          UPDATE missions SET estimated_cost=9999999999999.99,actual_cost=0 WHERE mission_id='"""+mid+"""';
          SELECT COUNT(*) INTO c FROM missions WHERE mission_id='"""+mid+"""' AND estimated_cost=9999999999999.99 AND actual_cost=0;
          IF c!=1 THEN RAISE_APPLICATION_ERROR(-20910,'Exact decimal maximum/zero'); END IF;
          ROLLBACK;
        END;
        /""")
        with self.assertRaisesRegex((RuntimeError,ValueError),'ORA-12899'):
            self.sql("INSERT INTO mission_assigned_crew VALUES ('"+mid+"','C-"+'1'*49+"');")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM missions WHERE status='PLANNED' AND estimated_cost IS NULL;"),'2')

    def test_07_clock_lock_serializes_transactions(self):
        first="""DECLARE v TIMESTAMP(3); BEGIN v:=missions_clock_tick(); DBMS_SESSION.SLEEP(5); COMMIT; END;
        /"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.sql,first)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                locked=operator.sql("SELECT COUNT(*) FROM v$locked_object l JOIN all_objects o ON o.object_id=l.object_id WHERE o.owner='"+self.schema+"' AND o.object_name='MISSION_CLOCK';")
                if locked!='0': break
                if future.done(): self.fail('First transaction completed before lock observation')
                time.sleep(0.1)
            else: self.fail('Clock row lock not observed')
            self.sql("""DECLARE v TIMESTAMP(3); c NUMBER; BEGIN
              v:=missions_clock_tick(); SELECT counter INTO c FROM mission_clock;
              IF c!=2 THEN RAISE_APPLICATION_ERROR(-20911,'Serialized clock ordering'); END IF;
              ROLLBACK;
            END;
            /""")
            future.result(timeout=20)
        self.assertEqual(self.sql('SELECT counter FROM mission_clock;'),'1')
        operator.reset('1.0',self.schema)

    def test_08_explicit_reset_sequence_positions_and_failure_guards(self):
        self.assertEqual(self.sql('SELECT mission_id_seq.NEXTVAL FROM dual;'),str(self.manifest['nextMissionOrdinal']))
        self.assertEqual(self.sql('SELECT change_id_seq.NEXTVAL FROM dual;'),str(self.manifest['nextChangeId']))
        for sequence,maximum in (('mission_id_seq',36**9-1),('change_id_seq',10**28-1)):
            self.sql('DROP SEQUENCE '+sequence+';\nCREATE SEQUENCE '+sequence+' START WITH '+str(maximum)+' MAXVALUE '+str(maximum)+' NOCACHE NOCYCLE;')
            self.assertEqual(self.sql("SELECT TO_CHAR("+sequence+".NEXTVAL,'FM9999999999999999999999999990') FROM dual;"),str(maximum))
            with self.assertRaisesRegex((RuntimeError,ValueError),'ORA-08004'):
                self.sql("SELECT TO_CHAR("+sequence+".NEXTVAL,'FM9999999999999999999999999990') FROM dual;")
        operator.reset('1.0',self.schema)
        operator.verify_loaded(self.schema,self.manifest,self.data)
        original_service=operator.ENV['serviceContainer']
        try:
            # Use the already running owned Oracle container to exercise the
            # actual Docker running-state guard without pulling a dummy image.
            operator.ENV['serviceContainer']=operator.ENV['container']
            with self.assertRaisesRegex(ValueError,'must be stopped'): operator.reset('1.0',self.schema)
        finally: operator.ENV['serviceContainer']=original_service
        with self.assertRaises((RuntimeError,ValueError)):
            self.sql('CREATE TABLE missions (bad NUMBER);')
        operator.service_stopped()
        operator.verify_loaded(self.schema,self.manifest,self.data)
        result=subprocess.run([sys.executable,'-B',str(DATASETS/'missions_operator.py'),'reset','--dataset','1.999'],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        operator.service_stopped()


def load_generator(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

REPO=COMPONENT.parents[1]
V1_CREW=REPO/'uss-enterprise/crew-personnel/datasets/released/crew-v1-large-003'

class Release11Acceptance(unittest.TestCase):
    """Release 1.1 appends to release 1.0: 300 missions, the 31 of 1.0 unchanged, the rest curated or generated."""
    @classmethod
    def setUpClass(cls):
        cls.path,cls.manifest,cls.data=validation.validate_release('1.1')
        cls.provenance=json.loads(validation.content(cls.path/'provenance.json'))
        cls.recipe=json.loads(validation.content(cls.path/'recipe.json'))
        cls.roster=json.loads(validation.content(cls.path/'roster.json'))
        cls.old=json.loads(validation.content(DATASETS/'releases/1.0/release.json'))

    def test_01_counts_composition_and_paging(self):
        from collections import Counter
        m=self.data['missions']
        self.assertEqual(self.manifest['counts'],{'missions':300,'changes':865})
        self.assertEqual(self.manifest['composition'],{'canonCarried':31,'canonNew':57,'maintenanceGenerated':45,'routineGenerated':167,'typeMaintenanceTotal':50})
        self.assertEqual(sum(1 for x in m if x['type']=='MAINTENANCE'),50)
        self.assertEqual(dict(Counter(x['status'] for x in m)),
                         {'COMPLETED':158,'PLANNED':30,'CANCELLED':27,'AUTHORIZED':25,'ACTIVE':23,'FAILED':22,'POSTPONED':15})
        self.assertEqual(sorted(p.name for p in self.path.glob('missions-*.xml')),['missions-%d.xml'%n for n in range(1,7)])
        self.assertEqual(sorted(p.name for p in self.path.glob('changes-*.xml')),sorted('changes-%d.xml'%n for n in range(1,19)))

    def test_02_appended_to_release_10_byte_for_byte(self):
        old=self.old
        self.assertEqual(self.data['missions'][:31],old['missions'])
        self.assertEqual(self.data['changes'][:101],old['changes'])
        last_mission=max(int(x['missionId'][3:],36) for x in old['missions']); last_change=max(int(x['changeId']) for x in old['changes'])
        self.assertTrue(all(int(x['missionId'][3:],36)>last_mission for x in self.data['missions'][31:]))
        self.assertTrue(all(int(x['changeId'])>last_change for x in self.data['changes'][101:]))
        # the appended entries are in time order among themselves; a new entry can be older than a carried one
        self.assertTrue(min(x['changedAt'] for x in self.data['changes'][101:])<max(x['changedAt'] for x in old['changes']))

    def test_03_archived_reproduction(self):
        archived=load_generator(self.path/'generate.py','archived_generator_11')
        files=archived.generate()
        self.assertEqual(set(files),set(p.name for p in self.path.iterdir()))
        for name,expected in files.items(): self.assertEqual(expected,validation.content(self.path/name),name)

    def test_04_generation_keys_and_category_isolation(self):
        g=load_generator(self.path/'generate.py','generator_11')
        old=load_generator(DATASETS/'releases/1.0/generate.py','generator_10')
        self.assertEqual(g.Stream('estimated_cost','ST-00000AAAA','event-1',generation=g.GEN1).integer(1,10**6),old.Stream('estimated_cost','ST-00000AAAA','event-1').integer(1,10**6))
        self.assertNotEqual(g.Stream('estimated_cost','ST-00000AAAA','event-1').integer(1,10**9),g.Stream('estimated_cost','ST-00000AAAA','event-1',generation=g.GEN1).integer(1,10**9))
        key=b'["missions-generator-2",1701,"crew_reference","CRW-1048",""]'
        block=int.from_bytes(hashlib.sha256(hashlib.sha256(key).digest()+b'\0'*8).digest(),'big')
        self.assertEqual(g.Stream('crew_reference','CRW-1048').integer(0,2**256-1),block)
        a=g.Stream('staffing_crew','routine-001').integer(1,10**6)
        unrelated=g.Stream('recipe_routine','routine-002')
        for _ in range(100): unrelated.integer(1,100)
        self.assertEqual(g.Stream('staffing_crew','routine-001').integer(1,10**6),a)
        with self.assertRaisesRegex(ValueError,'Unknown category'): g.Stream('nonsense')

    def test_05_reject_tamper_and_semantic_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)
            for file in self.path.iterdir(): (copied/file.name).write_bytes(validation.content(file))
            (copied/'load.sql').write_bytes(validation.content(copied/'load.sql')+b'--tampered\n')
            with self.assertRaisesRegex(ValueError,'Integrity'): validation.validate_release('1.1',copied)
        damaged=deepcopy(self.data)
        a,b=damaged['changes'][200],damaged['changes'][300]
        a['changedAt'],b['changedAt']=b['changedAt'],a['changedAt']
        with self.assertRaises(ValueError): validation.validate_data(damaged,self.manifest,self.provenance)
        damaged=deepcopy(self.data); damaged['missions'][40]['currentChangeId']='1'
        with self.assertRaisesRegex(ValueError,'Final current state'): validation.validate_data(damaged,self.manifest,self.provenance)
        damaged=deepcopy(self.data); damaged['missions'][100]['commandingOfficerId']='C-0'
        with self.assertRaises(ValueError): validation.validate_data(damaged,self.manifest,self.provenance)

    def test_06_references_are_missions_local_and_never_suffix_inferred(self):
        g=load_generator(self.path/'generate.py','references_generator_11')
        crew,unmapped,roster=g.derive_references(V1_CREW,self.recipe)
        self.assertEqual(crew,self.recipe['references']['crew']); self.assertEqual(unmapped,self.recipe['references']['unmappedCrew']); self.assertEqual(roster,self.roster)
        rows=g.read_v1_crew(V1_CREW)
        self.assertEqual(len(rows),800); self.assertEqual(len(crew),800)
        for row in rows:
            ref=crew[row['name']]
            self.assertNotEqual(int(ref[2:]),int(row['crewId'].split('-')[1]),'a reference must not equal the v1 suffix')
            self.assertEqual(self.roster[ref]['rank'],row['rank'])
        cast=('C-71','C-78','C-85','C-92','C-99','C-106','C-113','C-120','C-127','C-134')
        self.assertEqual({n:r for n,r in crew.items() if r in cast},self.recipe['references']['castKept'])
        self.assertTrue(set(unmapped.values()).isdisjoint(crew.values()))

    def test_07_edge_cases_are_present_and_measured(self):
        from collections import Counter
        m=self.data['missions']; recipe=self.recipe
        crew_refs=set(recipe['references']['crew'].values()); unmapped=set(recipe['references']['unmappedCrew'].values())
        officers=Counter(x.get('commandingOfficerId') for x in m)
        self.assertEqual((officers['C-71'],officers['C-78']),(52,50))
        self.assertEqual(sorted(len(x['assignedCrewIds']) for x in m)[-4:],[96,98,99,100])
        self.assertEqual(max(len(x['assignedAssetIds']) for x in m),50)
        self.assertEqual(sum(1 for x in m if x.get('commandingOfficerId') in x['assignedCrewIds']),5)
        used=set(r for x in m for r in x['assignedCrewIds'])
        self.assertEqual(sum(1 for r in used if r not in crew_refs and r not in unmapped),6)
        self.assertTrue(unmapped<=used)
        self.assertEqual(sum(1 for x in m if x['status']=='CANCELLED' and x['cancelledWithoutEstimateAllowed'] and 'estimatedCostCredits' not in x and x['actualCostCredits']=='0.00'),5)
        self.assertTrue(any('commandingOfficerId' not in x and not x['assignedCrewIds'] for x in m if x['status']=='PLANNED'))
        ledger=Counter(e['edge'] for e in self.provenance['edgeLedger'])
        for edge,count in {'crew-near-limit':4,'commander-is-only-senior':8,'assigned-crew-not-active':12,'civilian-listed-as-assigned-crew':5,
                           'asset-reference-without-mapping':14,'fifty-assigned-assets':1,'long-history':2,'non-ascii-text':3,'many-participants':10}.items():
            self.assertEqual(ledger[edge],count,edge)
        longest=Counter(c['missionId'] for c in self.data['changes']).most_common(2)
        self.assertEqual(sorted(n for _,n in longest),[8,12])
        self.assertEqual({x['stardate'] for x in m}&{'43000.00','48999.95'},{'43000.00','48999.95'})
        self.assertEqual({x['durationHours'] for x in m}&{1,8760},{1,8760})
        self.assertEqual((max(len(x['title']) for x in m),max(len(x['objective']) for x in m)),(120,2000))
        self.assertEqual(sum(1 for x in m if any(ord(c)>127 for c in x['title'])),3)
        # identity trap: Wesley Crusher, returning as a visitor, is an O participant and never C-120 or a P reference
        wesley=[ref for ref,name in recipe['references']['participants'].items() if name.startswith('Wesley Crusher')]
        self.assertEqual(len(wesley),1); self.assertTrue(wesley[0].startswith('O-'))
        visits=[x for x in m if wesley[0] in x['participantIds']]
        self.assertEqual(len(visits),2); self.assertEqual(ledger['returning-outsider-participant'],2)
        self.assertTrue(all('C-120' not in x['assignedCrewIds'] and x.get('commandingOfficerId')!='C-120' for x in visits))


class Oracle11Acceptance(unittest.TestCase):
    """Real Oracle 18c: release 1.1 loads through the same reset as 1.0 and every stored value matches the release."""
    @classmethod
    def setUpClass(cls):
        operator.db_guard()
        cls.schema='MS_TEST_'+secrets.token_hex(6).upper()
        cls.owned=False
        operator.create_schema(cls.schema); cls.owned=True
        try:
            operator.reset('1.1',cls.schema)
            cls.path,cls.manifest,cls.data=validation.validate_release('1.1')
        except Exception:
            operator.drop_test_schema(cls.schema); cls.owned=False
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.owned: operator.drop_test_schema(cls.schema)

    def sql(self,text): return operator.sql(text,self.schema)

    def test_01_real_load_of_all_300_missions(self):
        operator.verify_loaded(self.schema,self.manifest,self.data)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM missions;'),'300')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM mission_changes;'),'865')
        self.assertEqual(self.sql("SELECT COUNT(*) FROM missions WHERE mission_type='MAINTENANCE';"),'50')
        self.assertEqual(self.sql('SELECT MAX(change_id) FROM mission_changes;'),str(self.manifest['nextChangeId']-1))

    def test_02_appended_ids_and_an_older_timestamp_with_a_higher_change_id(self):
        carried=self.manifest['appendsTo']
        self.assertEqual(self.sql('SELECT COUNT(*) FROM mission_changes WHERE change_id<'+str(carried['nextChangeId'])+';'),str(carried['changes']))
        older=self.sql("SELECT COUNT(*) FROM mission_changes n WHERE n.change_id>="+str(carried['nextChangeId'])+" AND EXISTS (SELECT 1 FROM mission_changes o WHERE o.change_id<"+str(carried['nextChangeId'])+" AND o.changed_at>n.changed_at);")
        self.assertNotEqual(older,'0')

    def test_03_page_and_filter_shapes_the_data_must_support(self):
        self.assertEqual(self.sql("SELECT COUNT(*) FROM missions WHERE commanding_officer_id='C-71';"),'52')
        self.assertEqual(self.sql("SELECT COUNT(*) FROM missions WHERE commanding_officer_id='C-78';"),'50')
        self.assertEqual(self.sql('SELECT MAX(n) FROM (SELECT COUNT(*) n FROM mission_assigned_crew GROUP BY mission_id);'),'100')
        self.assertEqual(self.sql('SELECT MAX(n) FROM (SELECT COUNT(*) n FROM mission_assigned_assets GROUP BY mission_id);'),'50')
        self.assertEqual(self.sql("SELECT COUNT(*) FROM missions WHERE status='CANCELLED' AND cancelled_without_estimate_allowed=1 AND estimated_cost IS NULL AND actual_cost=0;"),'5')

    def test_04_reset_restores_release_after_runtime_changes(self):
        self.sql("DECLARE v TIMESTAMP(3); BEGIN v:=missions_clock_tick(); UPDATE missions SET title='changed at runtime' WHERE ROWNUM=1; COMMIT; END;\n/")
        operator.reset('1.1',self.schema)
        operator.verify_loaded(self.schema,self.manifest,self.data)
        self.assertEqual(self.sql('SELECT counter FROM mission_clock;'),'0')

PERSONNEL_DIR=REPO/'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004'

class Release12Acceptance(unittest.TestCase):
    """Release 1.2 appends to release 1.1 and reclassifies the participants by the definitions of C, P and O."""
    @classmethod
    def setUpClass(cls):
        cls.path,cls.manifest,cls.data=validation.validate_release('1.2')
        cls.provenance=json.loads(validation.content(cls.path/'provenance.json'))
        cls.table=json.loads(validation.content(cls.path/'participants.json'))
        cls.civilians=json.loads(validation.content(cls.path/'civilians.json'))
        cls.old=json.loads(validation.content(DATASETS/'releases/1.1/release.json'))
        cls.old_names=json.loads(validation.content(DATASETS/'releases/1.1/recipe.json'))['references']['participants']

    def test_01_counts_paging_and_unchanged_composition(self):
        from collections import Counter
        self.assertEqual(self.manifest['counts'],{'missions':300,'changes':973})
        self.assertEqual(self.manifest['composition'],{'canonCarried':31,'canonNew':57,'maintenanceGenerated':45,'routineGenerated':167,'typeMaintenanceTotal':50})
        self.assertEqual(self.manifest['corrections']['count'],108)
        self.assertEqual(dict(Counter(x['status'] for x in self.data['missions'])),dict(Counter(x['status'] for x in self.old['missions'])))
        self.assertEqual(sorted(p.name for p in self.path.glob('missions-*.xml')),['missions-%d.xml'%n for n in range(1,7)])
        self.assertEqual(sorted(p.name for p in self.path.glob('changes-*.xml')),sorted('changes-%d.xml'%n for n in range(1,21)))

    def test_02_every_identity_of_release_11_is_kept_and_the_entries_are_appended(self):
        self.assertEqual(self.data['changes'][:865],self.old['changes'])
        self.assertEqual([m['missionId'] for m in self.data['missions']],[m['missionId'] for m in self.old['missions']])
        last=max(int(x['changeId']) for x in self.old['changes'])
        appended=self.data['changes'][865:]
        self.assertEqual([int(x['changeId']) for x in appended],list(range(last+1,last+1+108)))
        self.assertEqual(self.manifest['nextChangeId'],last+109)
        corrected={x['missionId'] for x in appended}
        self.assertEqual(len(corrected),108)
        for new,old in zip(self.data['missions'],self.old['missions']):
            keys={k for k in set(new)|set(old) if new.get(k)!=old.get(k)}
            if new['missionId'] in corrected: self.assertEqual(keys,{'participantIds','lastUpdated','currentChangeId'},new['missionId'])
            else: self.assertEqual(keys,set(),new['missionId'])
        for row in appended:
            self.assertEqual((row['operation'],row['previousStatus']==row['newStatus'],row['changedBy'],row['orderedBy']),('UPDATED',True,'C-85','C-78'))
            self.assertTrue(row['changedAt']>max(x['changedAt'] for x in self.old['changes']))

    def test_03_archived_reproduction(self):
        archived=load_generator(self.path/'generate.py','archived_generator_12')
        files=archived.generate()
        self.assertEqual(set(files),set(p.name for p in self.path.iterdir()))
        for name,expected in files.items(): self.assertEqual(expected,validation.content(self.path/name),name)

    def test_04_generation_keys_and_category_isolation(self):
        g=load_generator(self.path/'generate.py','generator_12')
        key=b'["missions-generator-3",1701,"participant_pool","ST-00000LD8K",""]'
        block=int.from_bytes(hashlib.sha256(hashlib.sha256(key).digest()+b'\0'*8).digest(),'big')
        self.assertEqual(g.Stream('participant_pool','ST-00000LD8K').integer(0,2**256-1),block)
        a=g.Stream('participant_roster','ST-00000LD8K').integer(1,10**6)
        unrelated=g.Stream('participant_outsider','passenger','3')
        for _ in range(100): unrelated.integer(1,100)
        self.assertEqual(g.Stream('participant_roster','ST-00000LD8K').integer(1,10**6),a)
        with self.assertRaisesRegex(ValueError,'Unknown category'): g.Stream('staffing_crew')
        with self.assertRaisesRegex(ValueError,'smaller'): g.Stream('participant_pool','x').distinct([1,2],3)

    def test_05_reject_tamper_and_semantic_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)
            for file in self.path.iterdir(): (copied/file.name).write_bytes(validation.content(file))
            (copied/'load.sql').write_bytes(validation.content(copied/'load.sql')+b'--tampered\n')
            with self.assertRaisesRegex(ValueError,'Integrity'): validation.validate_release('1.2',copied)
        damaged=deepcopy(self.data); damaged['changes'][-1]['newStatus']='ACTIVE'
        with self.assertRaises(ValueError): validation.validate_data(damaged,self.manifest,self.provenance)
        damaged=deepcopy(self.data); damaged['changes'][-1]['previousStatus']='PLANNED'
        with self.assertRaises(ValueError): validation.validate_data(damaged,self.manifest,self.provenance)
        damaged=deepcopy(self.data); damaged['missions'][40]['currentChangeId']='1'
        with self.assertRaisesRegex(ValueError,'Final current state'): validation.validate_data(damaged,self.manifest,self.provenance)
        # the definitions: a crew reference, a made-up civilian and a roster person as an outsider are all refused
        first=next(m for m in self.data['missions'] if m['participantIds'])
        damaged=deepcopy(self.data); next(m for m in damaged['missions'] if m['missionId']==first['missionId'])['participantIds']=['C-71']
        with self.assertRaises(ValueError): validation.check_participants(self.path,self.manifest,damaged,self.provenance)
        table=deepcopy(self.table); p_ref=next(r for r,e in table.items() if r[0]=='P' and e['name']!='Guinan')
        table[p_ref]['name']='Nobody On The Roster'
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary)
            for file in self.path.iterdir(): (copied/file.name).write_bytes(validation.content(file))
            (copied/'participants.json').write_bytes(generate.canonical(table))
            with self.assertRaisesRegex(ValueError,'exactly one civilian'): validation.check_participants(copied,self.manifest,self.data,self.provenance)
            table=deepcopy(self.table); o_ref=next(r for r,e in table.items() if r[0]=='O')
            table[o_ref]['name']=self.civilians['civilians'][5]['name']
            (copied/'participants.json').write_bytes(generate.canonical(table))
            with self.assertRaisesRegex(ValueError,'names no one'): validation.check_participants(copied,self.manifest,self.data,self.provenance)

    def test_06_the_pinned_roster_is_what_personnel_released(self):
        g=load_generator(self.path/'generate.py','roster_generator_12')
        derived=g.derive_civilians(PERSONNEL_DIR)
        self.assertEqual(derived,self.civilians)
        self.assertEqual(self.civilians['dataset'],'personnel-v2-large-004')
        self.assertEqual(self.manifest['participantClasses']['personnelManifestSha256'],hashlib.sha256(validation.content(PERSONNEL_DIR/'manifest.json')).hexdigest())
        self.assertEqual(len(self.civilians['civilians']),219)

    def test_07_the_definitions_hold_on_the_released_data(self):
        used=sorted({r for m in self.data['missions'] for r in m['participantIds']})
        self.assertEqual(sorted(self.table),used)
        self.assertFalse(any(r.startswith('C-') for r in used))
        g=load_generator(self.path/'generate.py','roster_generator_12b')
        live=[c['name'] for c in g.read_civilians(PERSONNEL_DIR)]
        everyone=set(live)
        for page in PERSONNEL_DIR.glob('page-*.xml'):
            for name in __import__('re').findall(r'<displayName>(.*?)</displayName>',validation.content(page).decode('utf-8')): everyone.add(name)
        p=[r for r in used if r[0]=='P']; o=[r for r in used if r[0]=='O']
        self.assertEqual((len(p),len(o)),(self.manifest['participantClasses']['referencesP'],self.manifest['participantClasses']['referencesO']))
        for ref in p: self.assertEqual(live.count(self.table[ref]['name']),1,ref)
        for ref in o: self.assertNotIn(self.table[ref]['name'],everyone,ref)
        self.assertFalse(any('placeholder' in e['name'] for e in self.table.values()))
        self.assertEqual({r for r in used if self.table[r]['origin']=='kept'},{'P-1003','P-1068','O-224','O-380','O-639','O-860','O-938','O-951','O-977','O-1055'})
        self.assertEqual([x['name'] for x in self.provenance['offRosterCivilians']],['Clara Sutter'])
        self.assertEqual(self.table['O-860']['name'].split(' as ')[0],'Wesley Crusher')

    def test_08_outsiders_of_release_10_are_outsiders_now(self):
        by_title={m['title']:m for m in self.data['missions']}
        tau=by_title['Tau Cygna V evacuation']
        self.assertTrue(tau['participantIds'] and all(r.startswith('O-') for r in tau['participantIds']))
        self.assertEqual({self.table[r]['name'] for r in tau['participantIds']},{"Ard'rian McKenzie",'Gosheven'})
        old=next(m for m in self.old['missions'] if m['title']=='Tau Cygna V evacuation')
        self.assertTrue(all(r.startswith('P-') for r in old['participantIds']))
        self.assertIn('P-1003',by_title['Wedding ceremony hosting']['participantIds'])
        drill=by_title['Deck-by-deck emergency drill']
        self.assertTrue(len(drill['participantIds'])==15 and all(r.startswith('P-') for r in drill['participantIds']))


class Oracle12Acceptance(unittest.TestCase):
    """Real Oracle 18c: release 1.2 loads through the same reset and every stored value matches the release."""
    @classmethod
    def setUpClass(cls):
        operator.db_guard()
        cls.schema='MS_TEST_'+secrets.token_hex(6).upper()
        cls.owned=False
        operator.create_schema(cls.schema); cls.owned=True
        try:
            operator.reset('1.2',cls.schema)
            cls.path,cls.manifest,cls.data=validation.validate_release('1.2')
        except Exception:
            operator.drop_test_schema(cls.schema); cls.owned=False
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.owned: operator.drop_test_schema(cls.schema)

    def sql(self,text): return operator.sql(text,self.schema)

    def test_01_real_load_with_the_corrected_participants(self):
        operator.verify_loaded(self.schema,self.manifest,self.data)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM missions;'),'300')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM mission_changes;'),'973')
        self.assertEqual(self.sql('SELECT MAX(change_id) FROM mission_changes;'),str(self.manifest['nextChangeId']-1))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM mission_participants WHERE reference LIKE 'C-%';"),'0')
        self.assertEqual(self.sql("SELECT COUNT(DISTINCT reference) FROM mission_participants WHERE reference LIKE 'P-%';"),str(self.manifest['participantClasses']['referencesP']))
        self.assertEqual(self.sql("SELECT COUNT(DISTINCT reference) FROM mission_participants WHERE reference LIKE 'O-%';"),str(self.manifest['participantClasses']['referencesO']))

    def test_02_the_corrections_are_appended_audit_entries(self):
        carried=self.manifest['appendsTo']
        self.assertEqual(self.sql('SELECT COUNT(*) FROM mission_changes WHERE change_id<'+str(carried['nextChangeId'])+';'),str(carried['changes']))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM mission_changes WHERE change_id>='+str(carried['nextChangeId'])+" AND operation='UPDATED' AND previous_status=new_status;"),'108')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM missions m WHERE m.current_change_id>='+str(carried['nextChangeId'])+';'),'108')

    def test_03_reset_restores_release_after_runtime_changes(self):
        self.sql("DECLARE v TIMESTAMP(3); BEGIN v:=missions_clock_tick(); UPDATE missions SET title='changed at runtime' WHERE ROWNUM=1; COMMIT; END;\n/")
        operator.reset('1.2',self.schema)
        operator.verify_loaded(self.schema,self.manifest,self.data)
        self.assertEqual(self.sql('SELECT counter FROM mission_clock;'),'0')

if __name__=='__main__': unittest.main()
