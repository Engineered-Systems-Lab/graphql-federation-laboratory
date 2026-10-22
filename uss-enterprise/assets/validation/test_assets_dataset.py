"""The dataset validator accepts the shipped releases and fails when a release, or what it is checked against, is broken.

Release 1.0 stays validated by the shipped-release test (its own generator regenerates it byte for byte). The fresh-release tests
below build release 1.1 with the current generator into a temporary folder and break it one way at a time.
"""
from pathlib import Path
import json
import shutil
import importlib.util
import tempfile
import unittest

import validate_dataset as vd

# Loaded under its own name: other folders of the repository also hold a generate.py.
_spec = importlib.util.spec_from_file_location('assets_dataset_generate', vd.COMPONENT / 'datasets/generate.py')
generate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate)

# The ids the tests name (release 1.1 gives them by its rule): the Enterprise, the Magellan shuttle, the sensor suite
# aboard it and a phaser.
ENTERPRISE, SHUTTLE, SUITE, PHASER = 'AST-0029', 'AST-0023', 'AST-0004', 'AST-0008'


def write_json(path, value):
    Path(path).write_bytes(generate.canonical(value))


class Release(unittest.TestCase):
    """Each test owns a temporary copy of a freshly built release, of release 1.0 and of the Missions release it is checked against."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='assets-dataset-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.release = self.tmp / '1.1'
        generate.write_new_folder(self.release, generate.release_bytes())
        self.missions = self.tmp / 'missions'
        shutil.copytree(vd.MISSIONS_RELEASE, self.missions)
        self.source = self.tmp / '1.0'
        shutil.copytree(vd.COMPONENT / 'datasets/releases/1.0', self.source)

    def change(self, name, edit, rehash=True):
        """Edit a release JSON file and keep the manifest honest, so the check under test is the one that fires."""
        path = self.release / name
        value = json.loads(path.read_bytes())
        edit(value)
        write_json(path, value)
        if rehash:
            manifest = json.loads((self.release / 'manifest.json').read_bytes())
            manifest['files'][name] = vd.sha(vd.read_bytes(path))
            if name == 'assets.json':
                manifest['counts'] = {'assets': len(value['assets']), 'kinds': len({a['kind'] for a in value['assets']})}
            write_json(self.release / 'manifest.json', manifest)

    def rejects(self, text):
        with self.assertRaises(ValueError) as caught:
            vd.validate_release(self.release, missions_dir=self.missions, source_dir=self.source)
        self.assertIn(text, str(caught.exception))

    def asset(self, document, asset_id):
        return next(a for a in document['assets'] if a['assetId'] == asset_id)

    def entry(self, document, reference):
        return next(e for e in document['expectedMapping'] if e['missionsReference'] == reference)


class ShippedDataset(unittest.TestCase):
    def test_the_whole_validator_passes_for_every_release(self):
        self.assertEqual(vd.cli(lambda: vd.main([])), 0)

    def test_the_shipped_release_1_0_is_still_the_decided_dataset(self):
        release = vd.RELEASES / '1.0'
        document = vd.load(release / 'assets.json')
        self.assertGreaterEqual(len(document['assets']), 30)
        provenance = vd.load(release / 'provenance.json')
        self.assertEqual(provenance['missionsRelease'], {'datasetVersion': '1.0', 'distinctAssets': 9, 'references': 68})
        self.assertEqual({e['case'] for e in provenance['expectedReferences']} - {'NORMAL'}, {'DANGLING', 'DESTROYED', 'MISSING'})

    def test_the_shipped_release_1_1_is_the_native_dataset(self):
        release = vd.RELEASES / '1.1'
        document = vd.load(release / 'assets.json')
        self.assertEqual(len(document['assets']), 32)
        self.assertTrue(all(vd.ASSET_ID_11.fullmatch(a['assetId']) and a['assetId'].startswith('AST-') for a in document['assets']))
        self.assertFalse(any(vd.ASSET_ID.fullmatch(a['assetId']) for a in document['assets']))
        provenance = vd.load(release / 'provenance.json')
        self.assertEqual(provenance['missionsRelease'], {'datasetVersion': '1.0', 'distinctReferences': 9, 'references': 68})
        self.assertEqual({e['case'] for e in provenance['expectedMapping']},
                         {'NORMAL', 'MISSING', 'DESTROYED', 'MAPPED_NOT_FOUND', 'UNMAPPED'})
        by_reference = {e['missionsReference']: e for e in provenance['expectedMapping']}
        self.assertEqual(by_reference['EQ-108']['case'], 'UNMAPPED')
        self.assertIsNone(by_reference['EQ-108']['mapsTo'])
        self.assertEqual(by_reference['EQ-97']['case'], 'MAPPED_NOT_FOUND')
        self.assertEqual(by_reference['EQ-97']['assetsAnswers'], '404 ASSET_NOT_FOUND')
        self.assertEqual(by_reference['VS-31']['mapsTo'], ENTERPRISE)

    def test_release_1_1_renames_release_1_0_and_changes_nothing_else(self):
        old = vd.load(vd.RELEASES / '1.0/assets.json')['assets']
        new = vd.load(vd.RELEASES / '1.1/assets.json')['assets']
        assigned = {p['from']: p['to'] for p in vd.load(vd.RELEASES / '1.1/provenance.json')['idAssignment']['pairs']}
        self.assertEqual(len(old), len(new))
        for before, after in zip(old, new):
            self.assertEqual(assigned[before['assetId']], after['assetId'])
            renamed = dict(before, assetId=assigned[before['assetId']],
                           parentAssetId=assigned[before['parentAssetId']] if before['parentAssetId'] else None)
            self.assertEqual(renamed, after)


class FreshRelease(Release):
    def test_a_fresh_release_passes(self):
        found = vd.validate_release(self.release, missions_dir=self.missions, source_dir=self.source)
        self.assertGreaterEqual(found['assets'], 30)
        self.assertGreaterEqual(found['unreferenced'], 1)

    def test_the_rule_is_deterministic(self):
        self.assertEqual(generate.release_bytes(), generate.release_bytes())

    def test_a_missing_or_extra_file_fails(self):
        (self.release / 'review.html').write_text('x')
        self.rejects('Release files')

    def test_an_edited_file_fails_its_hash(self):
        self.change('assets.json', lambda d: d['assets'][0].update(name='Edited'), rehash=False)
        self.rejects('Content hash differs: assets.json')

    def test_the_pinned_missions_release_must_match(self):
        path = self.missions / 'release.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.rejects('Missions release hash')

    def test_the_pinned_source_release_must_match(self):
        path = self.source / 'assets.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.rejects('Source release assets hash')

    def test_a_dataset_that_does_not_reproduce_fails(self):
        def edit(document):
            document['assets'][0]['description'] = document['assets'][0]['description'] + ' '
        self.change('assets.json', edit)
        self.rejects('does not reproduce')


class Records(Release):
    def test_fewer_than_thirty_assets_fail(self):
        self.change('assets.json', lambda d: d.update(assets=d['assets'][:29]))
        self.rejects('At least 30 assets')

    def test_a_missing_kind_fails(self):
        def edit(document):
            for a in document['assets']:
                if a['kind'] == 'MUSICAL_INSTRUMENT':
                    a['kind'] = 'PHASER'
        self.change('assets.json', edit)
        self.rejects('MUSICAL_INSTRUMENT')

    def test_a_duplicate_id_fails(self):
        self.change('assets.json', lambda d: d['assets'].append(dict(d['assets'][0])))
        self.rejects('unique')

    def test_a_wrong_category_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(category='VEHICLE'))
        self.rejects('category differs from the kind table')

    def test_a_record_outside_the_schema_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(location='bridge'))
        self.rejects('unexpected property location')

    def test_a_bad_status_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(status='LOST'))
        self.rejects('not one of')

    def test_an_id_in_the_old_grammar_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(assetId='EQ-64'))
        self.rejects('does not match')

    def test_a_dangling_parent_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(parentAssetId='AST-0999'))
        self.rejects('does not exist')

    def test_an_equipment_parent_fails(self):
        self.change('assets.json', lambda d: self.asset(d, SUITE).update(parentAssetId=PHASER))
        self.rejects('not a VEHICLE')

    def test_a_cycle_fails(self):
        self.change('assets.json', lambda d: self.asset(d, ENTERPRISE).update(parentAssetId=SHUTTLE))
        self.rejects('cycle')

    def test_an_unsorted_dataset_fails(self):
        self.change('assets.json', lambda d: d['assets'].reverse())
        self.rejects('id order')


class MappingCrossCheck(Release):
    def test_a_wrong_expected_resolution_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-97').update(resolution='RESOLVED'))
        self.rejects('expected resolution')

    def test_a_wrong_expected_status_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-86').update(status='ACTIVE'))
        self.rejects('expected status differs')

    def test_a_mapping_that_differs_from_the_assignment_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-64').update(mapsTo=PHASER, mappingSays='maps to ' + PHASER))
        self.rejects('differs from the id assignment')

    def test_a_mapped_but_not_found_target_that_is_held_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-97').update(mapsTo=ENTERPRISE, mappingSays='maps to ' + ENTERPRISE))
        self.rejects('heldByAssets disagrees')

    def test_an_unmapped_reference_with_a_target_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-108').update(mapsTo=PHASER))
        self.rejects('has no target')

    def test_a_not_found_target_must_answer_404(self):
        def edit(document):
            for c in document['cases']:
                if c['case'] == 'MAPPED_NOT_FOUND':
                    c['assetsAnswers'] = '500 INTERNAL_ERROR'
            self.entry(document, 'EQ-97').update(assetsAnswers='500 INTERNAL_ERROR')
        self.change('provenance.json', edit)
        self.rejects('404 ASSET_NOT_FOUND')

    def test_a_reference_without_a_target_cannot_be_normal(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-108').update(case='NORMAL'))
        self.rejects('the mapping target is a native id')

    def test_the_consumer_rule_must_state_the_asset_not_found_only_mapping(self):
        self.change('provenance.json', lambda d: d.update(consumerRule='Everything unresolved is missing.'))
        self.rejects('only a 404 ASSET_NOT_FOUND maps to UNRESOLVED')

    def test_every_case_needs_all_three_columns(self):
        self.change('provenance.json', lambda d: next(c for c in d['cases'] if c['case'] == 'UNREFERENCED').update(mappingSays=''))
        self.rejects('what the mapping says, what Assets answers and what the consumer shows')

    def test_a_changed_missions_reference_count_fails(self):
        self.change('provenance.json', lambda d: self.entry(d, 'EQ-64').update(referenceCount=1))
        self.rejects('differ from the released Missions dataset')

    def test_a_changed_assignment_fails(self):
        def edit(document):
            pairs = document['idAssignment']['pairs']
            pairs[0]['to'], pairs[1]['to'] = pairs[1]['to'], pairs[0]['to']
        self.change('provenance.json', edit)
        self.rejects('assigned in order')

    def test_a_broken_parent_chain_fails(self):
        self.change('provenance.json', lambda d: d.update(parentChains=[[SUITE, ENTERPRISE, SHUTTLE]]))
        self.rejects('is not aboard')

    def test_the_missions_release_must_still_hold_nine_references(self):
        path = self.missions / 'release.json'
        document = json.loads(path.read_bytes())
        document['missions'][0]['assignedAssetIds'] = sorted(set(document['missions'][0]['assignedAssetIds']) | {'EQ-999'})
        write_json(path, document)
        manifest = json.loads((self.release / 'manifest.json').read_bytes())
        manifest['missionsRelease']['releaseSha256'] = vd.sha(vd.read_bytes(path))
        write_json(self.release / 'manifest.json', manifest)
        self.rejects('distinct assets')


class Generator(unittest.TestCase):
    def test_a_release_folder_is_never_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                generate.write_new_folder(folder, {})

    def test_the_rule_gives_one_step_each_in_the_old_order(self):
        source = generate.source_assets()
        assigned = generate.assign_ids(source)
        self.assertEqual(sorted(assigned.values()), [f'AST-{n:04d}' for n in range(1, len(source) + 1)])
        self.assertEqual(assigned['AV-2'], 'AST-0001')
        self.assertEqual(assigned['VS-31'], ENTERPRISE)
        ordered = sorted(assigned, key=generate.id_key)
        self.assertEqual([assigned[i] for i in ordered], sorted(assigned.values()))

    def test_the_review_page_is_self_contained_and_names_every_asset_and_case(self):
        files = generate.release_bytes()
        references, _ = generate.missions_references()
        page = generate.render_review(json.loads(files['assets.json']), json.loads(files['provenance.json']), references)
        for asset in json.loads(files['assets.json'])['assets']:
            self.assertIn(asset['assetId'], page)
        for column in ('Mapping says', 'Assets answers', 'Consumer shows', 'Only a 404'):
            self.assertIn(column, page)
        for case in ('NORMAL', 'MAPPED_NOT_FOUND', 'UNMAPPED', 'DESTROYED', 'MISSING', 'UNREFERENCED', 'PARENT_CHAIN'):
            self.assertIn(case, page)
        for forbidden in ('<script', 'http://', 'https://', '<link', '@import'):
            self.assertNotIn(forbidden, page)

    def test_an_unknown_kind_fails(self):
        original = generate.source_assets
        generate.source_assets = lambda: [{'assetId': 'EQ-1', 'kind': 'WIDGET', 'name': 'x', 'description': 'x',
                                           'status': 'ACTIVE', 'parentAssetId': None}]
        try:
            with self.assertRaises(ValueError):
                generate.build_assets({})
        finally:
            generate.source_assets = original


if __name__ == '__main__':
    unittest.main()
