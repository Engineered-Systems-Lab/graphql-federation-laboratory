"""Mapping release 1.3: the participants of Missions dataset release 1.2 against the large Personnel v2 snapshot, with no Docker.

The acceptance tests come first and are written by hand from the released files, not by calling the process: the participants.json of
Missions dataset release 1.2 (every participant reference with its class P or O and its name), the crew references of the recipe of
Missions dataset release 1.1 and the pages of personnel-v2-large-004. Release 1.3 must hold exactly what that reading gives: all 58 P
references resolved (56 civilians of the roster by exact name, Guinan, and P-1003 Alexander Rozhenko), no entry at all for any of the 153
O references (refused by class, the returning Wesley Crusher O-860 and the off-roster civilian Clara Sutter O-2836 among them), and the
crew and assets sections unchanged from release 1.2. The controlled cases (a P that nobody places is a FAILURE here, a P that only a
crew member could match, an O with a roster name) run on small inputs built here.
"""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter_support as support  # noqa: E402
import release_check as check  # noqa: E402

ROOT = support.ROOT
RELEASES = ROOT / check.RELEASES
MISSIONS_12 = ROOT / 'uss-enterprise/missions/datasets/releases/1.2'
LARGE = ROOT / 'uss-enterprise/personnel-v2/datasets/personnel-v2-large-004'
V2NS = '{urn:graphql-federation-lab:personnel:v2}'

spec = importlib.util.spec_from_file_location('crew_mapping', ROOT / 'federation/personnel-mapping/crew_mapping.py')
cm = importlib.util.module_from_spec(spec)
sys.modules['crew_mapping'] = cm
spec.loader.exec_module(cm)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def roster():
    """personnelId to (name, is crew) read from the ten pages of the large snapshot, with nothing of the process."""
    people = {}
    for page in sorted(LARGE.glob('page-*.xml')):
        for node in ET.parse(page).getroot().findall(V2NS + 'personnelMember'):
            people[node.findtext(V2NS + 'personnelId')] = (node.findtext(V2NS + 'displayName'), node.find(V2NS + 'crewDetails') is not None)
    return people


class TheReleaseHoldsWhatTheReleasedFilesSay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = load(MISSIONS_12 / 'participants.json')
        cls.people = roster()
        cls.by_name = {}
        for ident, (name, crew) in cls.people.items():
            cls.by_name.setdefault(name, []).append(ident)
        cls.participants = load(RELEASES / '1.3/participants.json')
        cls.crew = load(RELEASES / '1.3/crew.json')

    def test_the_missions_release_holds_58_p_and_153_o_references(self):
        p_refs = sorted(r for r, e in self.classes.items() if e['class'] == 'P')
        o_refs = sorted(r for r, e in self.classes.items() if e['class'] == 'O')
        self.assertEqual((len(p_refs), len(o_refs), len(self.classes)), (58, 153, 211))
        self.assertTrue(all(r.startswith('P-') for r in p_refs) and all(r.startswith('O-') for r in o_refs))

    def test_every_p_reference_resolves_to_the_non_crew_person_of_that_exact_name(self):
        entries = self.participants['entries']
        p_refs = [r for r, e in self.classes.items() if e['class'] == 'P']
        self.assertEqual(sorted(entries), sorted(p_refs), 'every P has an entry and nothing else has one')
        for ref in p_refs:
            with self.subTest(ref=ref):
                name = self.classes[ref]['name']
                self.assertEqual(self.by_name[name], [entries[ref]], 'an exact name, found once on the roster')
                self.assertFalse(self.people[entries[ref]][1], 'a participant reaches a non-crew person')
        self.assertEqual(len(set(entries.values())), 58, 'no two references share a person')

    def test_the_two_known_participants_and_the_56_civilians(self):
        entries = self.participants['entries']
        self.assertEqual((entries['P-1003'], entries['P-1068']), ('PRS-3001', 'PRS-0003'))
        self.assertEqual((self.people['PRS-3001'][0], self.people['PRS-0003'][0]), ('Alexander Rozhenko', 'Guinan'))
        others = {r: t for r, t in entries.items() if r not in ('P-1003', 'P-1068')}
        self.assertEqual(len(others), 56)
        self.assertTrue(all(self.classes[r]['origin'] == 'personnel-roster' for r in others))
        self.assertTrue(all(t.startswith('PRS-3') for t in others.values()), 'the generated civilians PRS-3001 to PRS-3199')

    def test_the_controlled_cases_account_for_every_reference(self):
        cases = self.participants['controlledCases']
        self.assertEqual(sorted(cases), ['EXCEPTION', 'NORMAL', 'REFUSED_BY_CLASS'], 'there is no UNMAPPED case: a P that does not resolve fails the build')
        self.assertEqual(cases['EXCEPTION'], ['P-1003'])
        self.assertEqual(len(cases['NORMAL']), 57)
        self.assertEqual(sorted(cases['REFUSED_BY_CLASS']), sorted(r for r, e in self.classes.items() if e['class'] == 'O'))

    def test_no_o_reference_has_an_entry_and_the_returning_wesley_and_the_off_roster_civilian_are_refused(self):
        for ref, entry in self.classes.items():
            if entry['class'] == 'O':
                self.assertNotIn(ref, self.participants['entries'], ref)
                self.assertNotIn(ref, self.crew['entries'], ref)
        self.assertIn('Wesley Crusher', self.classes['O-860']['name'])
        self.assertEqual(self.classes['O-2836']['name'], 'Clara Sutter')
        self.assertTrue(self.classes['O-2836']['offRosterOnBoardCivilian'])
        self.assertIn('O-860', self.participants['controlledCases']['REFUSED_BY_CLASS'])
        self.assertIn('O-2836', self.participants['controlledCases']['REFUSED_BY_CLASS'])
        for section in (self.crew, self.participants):
            self.assertNotIn('PRS-0714', [t for r, t in section['entries'].items() if r != 'C-120'], 'only the crew reference C-120 reaches Wesley')

    def test_the_crew_and_assets_sections_are_release_1_2_unchanged_byte_for_byte(self):
        for name in ('crew.json', 'assets.json'):
            self.assertEqual((RELEASES / '1.3' / name).read_bytes(), (RELEASES / '1.2' / name).read_bytes(), name)
        self.assertEqual(len(self.crew['entries']), 800)

    def test_the_older_releases_stand_unchanged(self):
        manifest = load(RELEASES / '1.3/manifest.json')
        self.assertEqual(manifest['release'], '1.3')
        self.assertEqual(sorted(manifest['files']), ['assets.json', 'crew.json', 'participants.json'])
        self.assertEqual(check.check_files(RELEASES / '1.3'), [])
        for version in ('1.0', '1.1', '1.2'):
            self.assertEqual(check.check_files(RELEASES / version), [], version)
            self.assertEqual(check.check_against(RELEASES / version, ROOT, newest=False), [], version)
        self.assertNotEqual(load(RELEASES / '1.2/participants.json'), self.participants, 'release 1.2 keeps its own participants')

    def test_the_checked_against_list_repeats_release_1_2_and_adds_missions_1_2(self):
        manifest = load(RELEASES / '1.3/manifest.json')
        self.assertEqual(manifest['checkedAgainst'][:-1], load(RELEASES / '1.2/manifest.json')['checkedAgainst'])
        last = manifest['checkedAgainst'][-1]
        self.assertEqual((last['system'], last['artifact'], last['version']), ('missions', 'dataset release manifest', '1.2'))
        self.assertEqual(last['sha256'], check.lf_sha256(MISSIONS_12 / 'manifest.json'))
        self.assertEqual(check.check_against(RELEASES / '1.3', ROOT), [])
        self.assertEqual(check.PENDING_MAPPING, set())

    def test_the_release_is_what_the_process_builds(self):
        self.assertEqual(check.check_release_13(RELEASES / '1.3', ROOT), [])
        self.assertEqual(cm.check_13(ROOT), [])
        self.assertEqual(cm.check_large(ROOT), [])
        self.assertEqual(check.check_assets_section(RELEASES / '1.3', ROOT), [])

    def test_the_release_folder_is_lf_only(self):
        for path in (RELEASES / '1.3').iterdir():
            self.assertNotIn(b'\r', path.read_bytes(), path.name)


class TheProcessInStrictMode(unittest.TestCase):
    """Controlled cases on inputs small enough to read."""

    ROSTER = (('PRS-0001', 'Guinan', False), ('PRS-0002', 'Wesley Crusher', True), ('PRS-0003', 'Keiko Ito', False))

    def v2(self, *members):
        return {ident: {'displayName': name, 'positionTitle': 'T', 'dutyStatus': 'ACTIVE', 'rank': 'ENSIGN' if crew else None,
                        'department': 'OPERATIONS' if crew else None, 'securityClearance': 'NONE' if crew else None, 'supervisor': None}
                for ident, name, crew in members}

    def test_a_p_reference_that_nobody_places_is_a_failure_that_names_it(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_participants({'P-1': 'Guinan', 'P-2': 'Nobody Known'}, {}, self.v2(*self.ROSTER), strict=True)
        self.assertIn('P-2', str(caught.exception))
        self.assertIn('must resolve', str(caught.exception))

    def test_the_default_mode_still_accepts_an_unmapped_p_as_release_1_2_did(self):
        results = cm.map_participants({'P-1': 'Guinan', 'P-2': 'Nobody Known'}, {}, self.v2(*self.ROSTER))
        self.assertEqual([(r.ref, r.outcome) for r in results], [('P-1', 'NAME'), ('P-2', 'UNMAPPED')])

    def test_strict_mode_places_by_exception_and_by_exact_name_and_refuses_o_by_class(self):
        results = cm.map_participants({'O-9': 'Guinan', 'P-1': 'Guinan', 'P-2': 'the child'}, {'P-2': 'PRS-0003'}, self.v2(*self.ROSTER), strict=True)
        self.assertEqual([(r.ref, r.outcome, r.target) for r in results],
                         [('O-9', 'REFUSED', None), ('P-1', 'NAME', 'PRS-0001'), ('P-2', 'EXCEPTION', 'PRS-0003')])

    def test_a_p_that_only_a_crew_member_matches_is_still_a_failure_in_strict_mode(self):
        with self.assertRaises(cm.MappingFailure) as caught:
            cm.map_participants({'P-1': 'Wesley Crusher'}, {}, self.v2(*self.ROSTER), strict=True)
        self.assertEqual(caught.exception.matches, ['PRS-0002'])


class TheChecksCatchChanges(unittest.TestCase):
    """The release 1.3 checks on a copy of the files they stand on, in a temporary folder."""

    FILES = ('federation/personnel-mapping/crew_mapping.py', 'federation/personnel-mapping/release-1-3-pins.json',
             'federation/mapping-releases/1.2/manifest.json', 'federation/mapping-releases/1.2/assets.json',
             'federation/mapping-releases/1.2/crew.json', 'uss-enterprise/missions/datasets/releases/1.2/manifest.json')

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='mapping-release-1-3-'))
        self.addCleanup(shutil.rmtree, self.temp, True)
        pins = load(ROOT / cm.RELEASE_13_PINS)
        for name in list(self.FILES) + [entry['path'] for entry in pins.values() if isinstance(entry, dict) and 'path' in entry]:
            target = self.temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for folder in (ROOT / pins['v1Release']['path']).parent, LARGE, RELEASES / '1.3':
            shutil.copytree(folder, self.temp / folder.relative_to(ROOT), dirs_exist_ok=True)
        self.release = self.temp / 'federation/mapping-releases/1.3'

    def test_the_copy_passes(self):
        self.assertEqual(check.check_release_13(self.release, self.temp), [])
        self.assertEqual(cm.check_13(self.temp), [])

    def test_a_changed_or_invented_entry_fails(self):
        for ref, target in (('O-860', 'PRS-0714'), ('P-1068', 'PRS-0001'), ('P-4006', 'PRS-3199')):
            with self.subTest(ref=ref):
                path = self.release / 'participants.json'
                original = path.read_bytes()
                section = json.loads(original.decode('utf-8'))
                section['entries'][ref] = target
                path.write_bytes((json.dumps(section, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
                self.assertTrue(any('participants.json differs' in p for p in check.check_release_13(self.release, self.temp)))
                path.write_bytes(original)
        self.assertEqual(check.check_release_13(self.release, self.temp), [])

    def test_a_missing_or_extra_file_fails(self):
        (self.release / 'participants.json').rename(self.release / 'participants.bak')
        problems = check.check_release_13(self.release, self.temp)
        self.assertTrue(any('participants.json is missing' in p for p in problems), problems)
        self.assertTrue(any('participants.bak is extra' in p for p in problems), problems)

    def test_a_changed_pinned_input_stops_the_run(self):
        pins = load(self.temp / cm.RELEASE_13_PINS)
        for key, entry in pins.items():
            if not (isinstance(entry, dict) and 'path' in entry):
                continue
            with self.subTest(input=key):
                path = self.temp / entry['path']
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.assertTrue(any('differs from its pin' in p for p in check.check_release_13(self.release, self.temp)))
                with self.assertRaises(cm.MappingFailure):
                    cm.load_release_13_inputs(self.temp)
                path.write_bytes(original)
        self.assertEqual(check.check_release_13(self.release, self.temp), [])

    def test_a_participant_that_the_roster_does_not_place_fails_the_build_instead_of_being_unmapped(self):
        path = self.temp / 'uss-enterprise/missions/datasets/releases/1.2/participants.json'
        section = load(path)
        section['P-9999'] = {'class': 'P', 'name': 'A Person Nobody Placed', 'origin': 'personnel-roster'}
        path.write_text(json.dumps(section, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        pins = load(self.temp / cm.RELEASE_13_PINS)
        pins['participants']['sha256'] = cm.digest(path, 'lf')
        (self.temp / cm.RELEASE_13_PINS).write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
        problems = check.check_release_13(self.release, self.temp)
        self.assertTrue(any('P-9999' in p and 'must resolve' in p for p in problems), problems)

    def test_a_class_letter_that_disagrees_with_the_reference_stops_the_run(self):
        path = self.temp / 'uss-enterprise/missions/datasets/releases/1.2/participants.json'
        section = load(path)
        section['O-860']['class'] = 'P'
        path.write_text(json.dumps(section, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        pins = load(self.temp / cm.RELEASE_13_PINS)
        pins['participants']['sha256'] = cm.digest(path, 'lf')
        (self.temp / cm.RELEASE_13_PINS).write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
        with self.assertRaises(cm.MappingFailure):
            cm.load_release_13_inputs(self.temp)

    def test_a_manifest_that_does_not_name_missions_release_1_2_fails(self):
        path = self.release / 'manifest.json'
        manifest = load(path)
        manifest['checkedAgainst'] = [e for e in manifest['checkedAgainst'] if not (e['system'] == 'missions' and e['version'] == '1.2')]
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        self.assertTrue(any('manifest.json differs' in p for p in check.check_release_13(self.release, self.temp)))
        self.assertTrue(any('not checked against' in p for p in check.check_against(self.release, self.temp)))


if __name__ == '__main__':
    unittest.main()
