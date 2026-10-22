"""The crew mapping against the released datasets, and the process that builds it, with no Docker.

The acceptance tests come first. EXPECTED_CREW is written by hand from the released files and not by running the process:
the Missions recipe (uss-enterprise/missions/datasets/recipe.json, references.crew), the Personnel v2 snapshot
personnel-v2-small-002 and the legacy crew release crew-v1-large-003. The process (federation/personnel-mapping/crew_mapping.py)
must reproduce it, the migration must reproduce the pinned snapshot personnel-v2-small-003 byte for byte, and the controlled
cases (a normal match, an exception match, a migrated person, an UNMAPPED reference) run on small inputs built here.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402

ROOT = support.ROOT
MODULE = ROOT / 'federation/personnel-mapping/crew_mapping.py'
SNAPSHOT_002 = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-small-002.xml'
SNAPSHOT_003 = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-small-003.xml'

spec = importlib.util.spec_from_file_location('crew_mapping', MODULE)
cm = importlib.util.module_from_spec(spec)
sys.modules['crew_mapping'] = cm
spec.loader.exec_module(cm)

# The Missions crew references of the recipe and where each lands, read by hand from the released files.
# Data (C-85) and Wesley Crusher (C-120) are found by exact name in Personnel v2; Picard (C-71) is a mapping exception because the
# systems write the full name; Beverly Crusher (C-106) and Worf (C-99) match by exact name in the v1 release and are migrated;
# Riker, La Forge, Troi, Barclay and O'Brien do not match exactly (the v1 release writes William Riker, Geordi La Forge, Deanna Troi,
# Reginald Barclay and Miles O'Brien), so each needs a migration exception and, after the migration, a mapping exception.
EXPECTED_CREW = {
    'C-71': 'PRS-0001',
    'C-78': 'PRS-1048',
    'C-85': 'PRS-0002',
    'C-92': 'PRS-1049',
    'C-99': 'PRS-1058',
    'C-106': 'PRS-1053',
    'C-113': 'PRS-1054',
    'C-120': 'PRS-0714',
    'C-127': 'PRS-1057',
    'C-134': 'PRS-1100',
}
EXPECTED_MIGRATED = {  # reference: (v1 id, v2 id)
    'C-78': ('CRW-1048', 'PRS-1048'), 'C-92': ('CRW-1049', 'PRS-1049'), 'C-99': ('CRW-1058', 'PRS-1058'),
    'C-106': ('CRW-1053', 'PRS-1053'), 'C-113': ('CRW-1054', 'PRS-1054'), 'C-127': ('CRW-1057', 'PRS-1057'),
    'C-134': ('CRW-1100', 'PRS-1100'),
}
# The seven migrated records as they must stand in personnel-v2-small-003:
# id, name, title, duty, rank, department, clearance, supervisor.
EXPECTED_RECORDS = [
    ('PRS-1048', 'William Riker', 'First Officer', 'ACTIVE', 'COMMANDER', 'COMMAND', 'SECRET', 'PRS-0001'),
    ('PRS-1049', 'Geordi La Forge', 'Chief Engineer', 'ACTIVE', 'LIEUTENANT_COMMANDER', 'ENGINEERING', 'SECRET', 'PRS-1048'),
    ('PRS-1053', 'Beverly Crusher', 'Chief Medical Officer', 'ACTIVE', 'COMMANDER', 'MEDICAL', 'SECRET', 'PRS-0001'),
    ('PRS-1054', 'Deanna Troi', "Ship's Counselor", 'ACTIVE', 'LIEUTENANT_COMMANDER', 'MEDICAL', 'SECRET', 'PRS-0001'),
    ('PRS-1057', 'Reginald Barclay', 'Systems Diagnostic Engineer', 'ACTIVE', 'LIEUTENANT', 'ENGINEERING', 'NONE', 'PRS-1049'),
    ('PRS-1058', 'Worf', 'Chief of Security', 'ACTIVE', 'LIEUTENANT', 'SECURITY', 'SECRET', 'PRS-1048'),
    ('PRS-1100', "Miles O'Brien", 'Transporter Chief', 'ACTIVE', 'CHIEF_PETTY_OFFICER', 'OPERATIONS', 'NONE', 'PRS-1048'),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReleasedDatasets(unittest.TestCase):
    """The acceptance cases, on the real released files."""

    @classmethod
    def setUpClass(cls):
        cls.inputs = cm.load_inputs(ROOT)

    def test_the_recipe_names_the_ten_crew_references_of_the_expected_mapping(self):
        self.assertEqual(sorted(self.inputs.references), sorted(EXPECTED_CREW))
        self.assertEqual(self.inputs.references['C-78'], 'Riker')
        self.assertEqual(self.inputs.references['C-106'], 'Beverly Crusher')

    def test_the_process_maps_the_ten_references_as_expected_before_the_migration(self):
        # Against personnel-v2-small-002 the process can only place Picard (exception), Data and Wesley (names) and plan seven migrations.
        results = cm.map_references(self.inputs.references, self.inputs.mapping_exceptions, self.inputs.v2_source,
                                    v1=self.inputs.v1, migration_exceptions=self.inputs.migration_exceptions,
                                    allow_pending=True)
        placed = {r.ref: r.target for r in results if r.target}
        self.assertEqual(placed, {'C-71': 'PRS-0001', 'C-85': 'PRS-0002', 'C-120': 'PRS-0714'})
        planned = {r.ref: (r.v1_id, r.migrated_id) for r in results if r.outcome == 'MIGRATE'}
        self.assertEqual(planned, EXPECTED_MIGRATED)

    def test_the_migration_reproduces_the_pinned_snapshot_byte_for_byte(self):
        results = cm.map_references(self.inputs.references, self.inputs.mapping_exceptions, self.inputs.v2_source,
                                    v1=self.inputs.v1, migration_exceptions=self.inputs.migration_exceptions,
                                    allow_pending=True)
        produced = cm.migrate(self.inputs.v2_source_text, self.inputs.v1, results, 'personnel-v2-small-003')
        self.assertEqual(hashlib.sha256(produced.encode('utf-8')).hexdigest(), self.inputs.pins['v2Target']['sha256'])
        self.assertEqual(produced.encode('utf-8'), SNAPSHOT_003.read_bytes())

    def test_the_new_snapshot_keeps_the_seven_existing_records_byte_for_byte_and_adds_the_seven_migrated(self):
        old = SNAPSHOT_002.read_text(encoding='utf-8').splitlines()
        new = SNAPSHOT_003.read_text(encoding='utf-8').splitlines()
        old_members = [line for line in old if line.startswith('  <personnelMember>')]
        new_members = [line for line in new if line.startswith('  <personnelMember>')]
        self.assertEqual(len(old_members), 7)
        self.assertEqual(len(new_members), 14)
        self.assertEqual([line for line in new_members if line in old_members], old_members)
        people = cm.parse_v2(SNAPSHOT_003.read_text(encoding='utf-8'))
        self.assertEqual(sorted(people), sorted(['PRS-0001', 'PRS-0002', 'PRS-0003', 'PRS-0004', 'PRS-0005', 'PRS-0006', 'PRS-0714']
                                                + [r[0] for r in EXPECTED_RECORDS]))
        for ident, name, title, duty, rank, department, clearance, supervisor in EXPECTED_RECORDS:
            self.assertEqual((people[ident]['displayName'], people[ident]['positionTitle'], people[ident]['dutyStatus'],
                              people[ident]['rank'], people[ident]['department'], people[ident]['securityClearance'],
                              people[ident]['supervisor']),
                             (name, title, duty, rank, department, clearance, supervisor), ident)
        self.assertEqual(new[1], '<ListPersonnelMembersResponse xmlns="urn:graphql-federation-lab:personnel:v2">')
        self.assertIn('  <datasetVersion>personnel-v2-small-003</datasetVersion>', new)
        self.assertIn('  <totalCount>14</totalCount><offset>0</offset><limit>20</limit><hasMore>false</hasMore>', new)

    def test_the_snapshot_files_are_lf_only_and_the_old_ones_are_untouched(self):
        self.assertNotIn(b'\r', SNAPSHOT_003.read_bytes())
        self.assertEqual(sha(SNAPSHOT_002), 'c7550f57350846f3a7833caf23461916ebef12ab26f34c631d92a115299168f8')
        self.assertEqual(sha(SNAPSHOT_002.with_name('personnel-v2-small-001.xml')),
                         'cecd2f407ccfd47356b07fc7d11b2cb84d4fb30a7701a241e067d51d36e174df')

    def test_after_the_migration_the_process_gives_the_expected_table_with_nothing_left_to_migrate(self):
        results = cm.map_references(self.inputs.references, self.inputs.mapping_exceptions, self.inputs.v2_target,
                                    v1=self.inputs.v1, migration_exceptions=self.inputs.migration_exceptions)
        self.assertEqual({r.ref: r.target for r in results}, EXPECTED_CREW)
        self.assertEqual([r for r in results if r.outcome == 'MIGRATE'], [])
        self.assertEqual({r.ref: r.outcome for r in results},
                         {'C-71': 'EXCEPTION', 'C-78': 'EXCEPTION', 'C-85': 'NAME', 'C-92': 'EXCEPTION', 'C-99': 'NAME',
                          'C-106': 'NAME', 'C-113': 'EXCEPTION', 'C-120': 'NAME', 'C-127': 'EXCEPTION', 'C-134': 'EXCEPTION'})

    def test_the_live_process_without_the_migration_step_gives_the_same_table_on_the_new_snapshot(self):
        live = cm.map_references(self.inputs.references, self.inputs.mapping_exceptions, self.inputs.v2_target, live=True)
        self.assertEqual({r.ref: r.target for r in live}, EXPECTED_CREW)

    def test_the_live_process_on_the_old_snapshot_leaves_the_unplaced_references_unmapped(self):
        live = cm.map_references(self.inputs.references, {'C-71': 'PRS-0001'}, self.inputs.v2_source, live=True)
        self.assertEqual({r.ref for r in live if r.outcome == 'UNMAPPED'},
                         {'C-78', 'C-92', 'C-99', 'C-106', 'C-113', 'C-127', 'C-134'})

    def test_the_mapping_exception_targets_exist_in_the_new_snapshot_and_never_name_v1(self):
        people = cm.parse_v2(SNAPSHOT_003.read_text(encoding='utf-8'))
        for ref, target in self.inputs.mapping_exceptions.items():
            self.assertRegex(target, r'^PRS-[0-9]{4}$', ref)
            self.assertIn(target, people, ref)
        self.assertEqual(self.inputs.mapping_exceptions,
                         {'C-71': 'PRS-0001', 'C-78': 'PRS-1048', 'C-92': 'PRS-1049', 'C-113': 'PRS-1054', 'C-127': 'PRS-1057',
                          'C-134': 'PRS-1100'})
        self.assertEqual(self.inputs.migration_exceptions,
                         {'C-78': 'CRW-1048', 'C-92': 'CRW-1049', 'C-113': 'CRW-1054', 'C-127': 'CRW-1057', 'C-134': 'CRW-1100'})

    def test_every_pinned_input_matches_its_file(self):
        self.assertEqual(cm.check_pins(ROOT), [])

    def test_the_crew_section_of_the_release_is_the_full_expected_table(self):
        section = cm.build_crew_section(self.inputs)
        self.assertEqual(section['section'], 'crew')
        self.assertEqual(section['entries'], EXPECTED_CREW)
        self.assertEqual(section['controlledCases'], {
            'NORMAL': ['C-85', 'C-120'],
            'EXCEPTION': ['C-71'],
            'MIGRATED': ['C-78', 'C-92', 'C-99', 'C-106', 'C-113', 'C-127', 'C-134'],
        })
        released = json.loads((ROOT / 'federation/mapping-releases/1.1/crew.json').read_text(encoding='utf-8'))
        self.assertEqual(released, section)


class Process(unittest.TestCase):
    """The controlled cases, on inputs small enough to read: a normal match, an exception match, a migrated person, an UNMAPPED one."""

    def v2(self, *members):
        return {i: {'displayName': n, 'positionTitle': 'T', 'dutyStatus': 'ACTIVE', 'rank': 'ENSIGN', 'department': 'OPERATIONS',
                    'securityClearance': 'NONE', 'supervisor': None} for i, n in members}

    def v1(self, *members):
        return {i: {'displayName': n, 'positionTitle': 'T', 'dutyStatus': 'ACTIVE', 'rank': 'ENSIGN', 'department': 'OPERATIONS',
                    'supervisor': s} for i, n, s in members}

    def run_one(self, name='Alice', mapping=None, v2=None, v1=None, migration=None, live=False):
        return cm.map_references({'C-1': name}, mapping or {}, v2 if v2 is not None else self.v2(), v1=v1, migration_exceptions=migration,
                                 live=live)[0]

    def test_a_normal_match_is_an_exact_name_in_the_snapshot(self):
        result = self.run_one(v2=self.v2(('PRS-0010', 'Alice')))
        self.assertEqual((result.outcome, result.target), ('NAME', 'PRS-0010'))

    def test_a_partial_or_differently_cased_name_does_not_match(self):
        for name in ('alice', 'Alice B', 'Ali', ' Alice'):
            with self.subTest(name=name):
                self.assertEqual(self.run_one(name=name, v2=self.v2(('PRS-0010', 'Alice')), live=True).outcome, 'UNMAPPED')

    def test_an_exception_match_stops_the_process_before_the_name_is_looked_at(self):
        result = self.run_one(mapping={'C-1': 'PRS-0011'}, v2=self.v2(('PRS-0010', 'Alice'), ('PRS-0011', 'Alice Smith')))
        self.assertEqual((result.outcome, result.target), ('EXCEPTION', 'PRS-0011'))

    def test_a_name_in_the_old_release_is_a_migration_and_a_migration_exception_wins_over_a_name(self):
        v1 = self.v1(('CRW-2001', 'Alice', None), ('CRW-2002', 'Alicia', None))
        result = self.run_one(v1=v1)
        self.assertEqual((result.outcome, result.v1_id, result.migrated_id, result.target), ('MIGRATE', 'CRW-2001', 'PRS-2001', None))
        result = self.run_one(v1=v1, migration={'C-1': 'CRW-2002'})
        self.assertEqual((result.outcome, result.v1_id, result.migrated_id), ('MIGRATE', 'CRW-2002', 'PRS-2002'))

    def test_a_reference_nobody_knows_is_unmapped_live_and_a_failure_otherwise(self):
        self.assertEqual(self.run_one(live=True).outcome, 'UNMAPPED')
        self.assertIsNone(self.run_one(live=True).target)
        with self.assertRaises(cm.MappingFailure) as caught:
            self.run_one()
        self.assertIn('C-1', str(caught.exception))
        with self.assertRaises(cm.MappingFailure):
            self.run_one(v1=self.v1(('CRW-2001', 'Someone', None)))

    def test_more_than_one_match_is_a_failure_that_reports_all_of_them(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            self.run_one(v2=self.v2(('PRS-0010', 'Alice'), ('PRS-0012', 'Alice')))
        self.assertEqual(caught.exception.matches, ['PRS-0010', 'PRS-0012'])
        with self.assertRaises(cm.MappingFailure) as caught:
            self.run_one(v1=self.v1(('CRW-2001', 'Alice', None), ('CRW-2005', 'Alice', None)))
        self.assertEqual(caught.exception.matches, ['CRW-2001', 'CRW-2005'])

    def test_live_mode_never_runs_the_migration_step(self):
        result = self.run_one(v1=self.v1(('CRW-2001', 'Alice', None)), live=True)
        self.assertEqual(result.outcome, 'UNMAPPED')

    def test_a_mapping_exception_target_that_is_not_in_the_snapshot_is_refused(self):
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Alice'}, {'C-1': 'PRS-0099'}, self.v2(('PRS-0010', 'Alice')))

    def test_an_exception_for_an_unknown_reference_or_in_the_wrong_grammar_is_refused(self):
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Alice'}, {'C-9': 'PRS-0010'}, self.v2(('PRS-0010', 'Alice')))
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Alice'}, {'C-1': 'CRW-1047'}, self.v2(('PRS-0010', 'Alice')))

    def test_a_pending_exception_is_allowed_only_for_the_migration_and_only_with_the_id_the_migration_creates(self):
        v1 = self.v1(('CRW-2001', 'Alicia', None))
        kwargs = dict(v1=v1, migration_exceptions={'C-1': 'CRW-2001'}, allow_pending=True)
        result = cm.map_references({'C-1': 'Alice'}, {'C-1': 'PRS-2001'}, self.v2(), **kwargs)[0]
        self.assertEqual((result.outcome, result.migrated_id), ('MIGRATE', 'PRS-2001'))
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Alice'}, {'C-1': 'PRS-2999'}, self.v2(), **kwargs)

    def test_a_migrated_id_that_is_taken_is_a_failure(self):
        with self.assertRaises(cm.MappingFailure):
            cm.map_references({'C-1': 'Alice'}, {}, self.v2(('PRS-2001', 'Someone Else')), v1=self.v1(('CRW-2001', 'Alice', None)))

    def test_the_clearance_rule(self):
        cases = [('CAPTAIN', 'COMMAND', 'TOP_SECRET'), ('CAPTAIN', 'SECURITY', 'TOP_SECRET'), ('COMMANDER', 'COMMAND', 'SECRET'),
                 ('LIEUTENANT_COMMANDER', 'SCIENCE', 'SECRET'), ('LIEUTENANT', 'ENGINEERING', 'NONE'), ('LIEUTENANT', 'SECURITY', 'SECRET'),
                 ('ENSIGN', 'SECURITY', 'SECRET'), ('CREWMAN', 'MEDICAL', 'NONE'), ('CHIEF_PETTY_OFFICER', 'OPERATIONS', 'NONE'),
                 ('COMMANDER', 'SECURITY', 'SECRET')]
        for rank, department, expected in cases:
            with self.subTest(rank=rank, department=department):
                self.assertEqual(cm.clearance(rank, department), expected)

    def test_a_migration_remaps_supervisors_and_refuses_a_supervisor_outside_the_set(self):
        base = ('<?xml version="1.0" encoding="UTF-8"?>\n<ListPersonnelMembersResponse xmlns="urn:graphql-federation-lab:personnel:v2">\n'
                '  <datasetVersion>x-1</datasetVersion>\n'
                '  <personnelMember><personnelId>PRS-0001</personnelId><displayName>Boss</displayName><positionTitle>T</positionTitle>'
                '<dutyStatus>ACTIVE</dutyStatus><crewDetails><rank>CAPTAIN</rank><department>COMMAND</department>'
                '<securityClearance>TOP_SECRET</securityClearance></crewDetails></personnelMember>\n'
                '  <totalCount>1</totalCount><offset>0</offset><limit>20</limit><hasMore>false</hasMore>\n'
                '</ListPersonnelMembersResponse>\n')
        v1 = self.v1(('CRW-3000', 'Boss', None), ('CRW-3001', 'Alice', 'CRW-3000'), ('CRW-3002', 'Bob', 'CRW-3001'),
                     ('CRW-3003', 'Outsider', None), ('CRW-3004', 'Dan', 'CRW-3003'))
        people = cm.parse_v2(base)
        results = cm.map_references({'C-1': 'Alice', 'C-2': 'Bob'}, {}, people, v1=v1)
        produced = cm.migrate(base, v1, results, 'x-2')
        migrated = cm.parse_v2(produced)
        self.assertEqual(migrated['PRS-3001']['supervisor'], 'PRS-0001')
        self.assertEqual(migrated['PRS-3002']['supervisor'], 'PRS-3001')
        self.assertIn('<datasetVersion>x-2</datasetVersion>', produced)
        self.assertIn('<totalCount>3</totalCount>', produced)
        with self.assertRaises(cm.MappingFailure):
            cm.migrate(base, v1, cm.map_references({'C-4': 'Dan'}, {}, people, v1=v1), 'x-2')

    def test_a_civilian_in_the_old_release_becomes_a_civilian_record(self):
        base = ('<?xml version="1.0" encoding="UTF-8"?>\n<ListPersonnelMembersResponse xmlns="urn:graphql-federation-lab:personnel:v2">\n'
                '  <datasetVersion>x-1</datasetVersion>\n'
                '  <totalCount>0</totalCount><offset>0</offset><limit>20</limit><hasMore>false</hasMore>\n'
                '</ListPersonnelMembersResponse>\n')
        v1 = {'CRW-3100': {'displayName': 'Guest', 'positionTitle': 'Visitor', 'dutyStatus': 'ACTIVE', 'rank': 'CIVILIAN',
                           'department': 'OPERATIONS', 'supervisor': None}}
        produced = cm.migrate(base, v1, cm.map_references({'C-1': 'Guest'}, {}, {}, v1=v1), 'x-2')
        self.assertIn('<personnelId>PRS-3100</personnelId><displayName>Guest</displayName><positionTitle>Visitor</positionTitle>'
                      '<dutyStatus>ACTIVE</dutyStatus><civilianDetails/></personnelMember>', produced)


class PinsRefuseChangedInputs(unittest.TestCase):
    """All inputs are pinned by hash; a run refuses to start when one differs."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='crew-mapping-pins-'))
        self.addCleanup(shutil.rmtree, self.temp, True)
        pins = json.loads((ROOT / 'federation/personnel-mapping/pins.json').read_text(encoding='utf-8'))
        names = [entry['path'] for entry in pins.values() if isinstance(entry, dict) and 'path' in entry]
        names.append('federation/personnel-mapping/pins.json')
        for name in names:
            target = self.temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        v1 = ROOT / pins['v1Release']['path']
        shutil.copytree(v1.parent, (self.temp / pins['v1Release']['path']).parent, dirs_exist_ok=True)

    def test_the_copy_passes(self):
        self.assertEqual(cm.check_pins(self.temp), [])
        cm.load_inputs(self.temp)

    def test_each_changed_input_makes_the_run_refuse_to_start(self):
        pins = json.loads((self.temp / 'federation/personnel-mapping/pins.json').read_text(encoding='utf-8'))
        for key, entry in pins.items():
            if not (isinstance(entry, dict) and 'path' in entry):
                continue
            with self.subTest(input=key):
                path = self.temp / entry['path']
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.assertTrue(cm.check_pins(self.temp), key)
                with self.assertRaises(cm.MappingFailure):
                    cm.load_inputs(self.temp)
                path.write_bytes(original)
        self.assertEqual(cm.check_pins(self.temp), [])

    def test_a_changed_page_of_the_old_release_is_refused(self):
        pins = json.loads((self.temp / 'federation/personnel-mapping/pins.json').read_text(encoding='utf-8'))
        page = (self.temp / pins['v1Release']['path']).parent / 'page-003.xml'
        page.write_bytes(page.read_bytes() + b' ')
        with self.assertRaises(cm.MappingFailure):
            cm.load_inputs(self.temp)


if __name__ == '__main__':
    unittest.main()
