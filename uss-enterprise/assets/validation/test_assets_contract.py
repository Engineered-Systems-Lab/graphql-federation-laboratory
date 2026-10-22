"""The offline contract validator accepts the shipped contract and fails when it, or its examples, are broken."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

import jsonschema_subset as js
import validate

CONTRACT = js.load_json(validate.CONTRACT)


def broken(edit):
    contract = deepcopy(CONTRACT)
    edit(contract)
    return contract


class ShippedContract(unittest.TestCase):
    def test_the_whole_validator_passes(self):
        self.assertEqual(validate.cli(validate.main), 0)

    def test_the_contract_is_the_decided_surface(self):
        schemas = CONTRACT['components']['schemas']
        self.assertEqual(schemas['AssetStatus']['enum'], ['ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING'])
        self.assertEqual(schemas['AssetKind']['enum'], ['STARSHIP', 'SHUTTLE', 'ROVER', 'ARMORED_VEHICLE', 'PHASER', 'TRICORDER', 'COMMUNICATOR', 'SCIENTIFIC_INSTRUMENT', 'MUSICAL_INSTRUMENT'])
        self.assertEqual(schemas['AssetCategory']['enum'], ['VEHICLE', 'EQUIPMENT'])
        self.assertEqual(list(schemas['Asset']['properties']),
                         ['assetId', 'kind', 'category', 'name', 'description', 'status', 'parentAssetId'])
        self.assertNotIn('location', schemas['Asset']['properties'])
        self.assertEqual(sorted(CONTRACT['paths']), ['/assets', '/assets/{assetId}'])
        statuses = {p: list(item['get']['responses']) for p, item in CONTRACT['paths'].items()}
        self.assertEqual(statuses['/assets/{assetId}'], ['200', '400', '404', '500'])


class StructuralFailures(unittest.TestCase):
    def fails(self, edit, text=None):
        with self.assertRaises((ValueError, KeyError, js.SchemaError)) as caught:
            validate.check_structure(broken(edit))
        if text:
            self.assertIn(text, str(caught.exception))

    def test_a_dropped_status_value(self):
        self.fails(lambda c: c['components']['schemas']['AssetStatus']['enum'].remove('MISSING'), 'Enum drift')

    def test_an_added_asset_field(self):
        self.fails(lambda c: c['components']['schemas']['Asset']['properties'].update(location={'type': 'string'}),
                   'Asset field drift')

    def test_a_changed_identifier_grammar(self):
        self.fails(lambda c: c['components']['schemas']['AssetId'].update(pattern='^[A-Z]{2,5}-[0-9]+$'), 'grammar drift')

    def test_a_write_operation(self):
        self.fails(lambda c: c['paths']['/assets'].update(post={'operationId': 'x', 'responses': {}}), 'Only GET')

    def test_a_missing_404(self):
        self.fails(lambda c: c['paths']['/assets/{assetId}']['get']['responses'].pop('404'), 'Response statuses')

    def test_an_unsupported_schema_keyword(self):
        self.fails(lambda c: c['components']['schemas']['Error']['properties']['message'].update(format='email'))

    def test_a_reference_that_resolves_nowhere(self):
        self.fails(lambda c: c['components']['schemas']['Asset']['properties'].__setitem__(
            'kind', {'$ref': '#/components/schemas/Nope'}))

    def test_a_wrong_openapi_or_contract_version(self):
        self.fails(lambda c: c.__setitem__('openapi', '3.0.3'), 'OpenAPI version')
        self.fails(lambda c: c['info'].__setitem__('version', '1.1'), 'Contract version')

    def test_a_dropped_or_returned_kind(self):
        self.fails(lambda c: c['components']['schemas']['AssetKind']['enum'].remove('ROVER'), 'Enum drift')
        self.fails(lambda c: c['components']['schemas']['AssetKind']['enum'].append('GROUND_VEHICLE'), 'Enum drift')

    def test_a_kind_without_a_row_of_the_category_table(self):
        with mock.patch.dict(validate.ENUMS, {'AssetKind': 'STARSHIP SHUTTLE ROVER ARMORED_VEHICLE PHASER TRICORDER COMMUNICATOR SCIENTIFIC_INSTRUMENT MUSICAL_INSTRUMENT STATION'}):
            contract = broken(lambda c: c['components']['schemas']['AssetKind']['enum'].append('STATION'))
            with self.assertRaises(ValueError) as caught:
                validate.check_structure(contract)
            self.assertIn('category table', str(caught.exception))

    def test_a_missing_category_filter(self):
        def edit(c):
            params = c['paths']['/assets']['get']['parameters']
            params.remove({'$ref': '#/components/parameters/CategoryFilter'})
        self.fails(edit, 'List filters and paging')

    def test_a_changed_default_page_size_is_not_silent(self):
        contract = broken(lambda c: c['components']['parameters']['Limit']['schema'].update(default='25'))
        with self.assertRaises(ValueError):
            validate.check_probes(contract)


class ExampleAndFixtureFailures(unittest.TestCase):
    def test_every_invalid_fixture_is_rejected_for_its_own_schema(self):
        for name, schema in validate.REJECTED.items():
            problems = js.errors(js.load_json(validate.INVALID / name), validate.schema_ref(schema), CONTRACT)
            self.assertTrue(problems, name)

    def test_the_category_table_maps_each_kind_to_one_category(self):
        self.assertEqual(validate.KIND_CATEGORY, {'STARSHIP': 'VEHICLE', 'SHUTTLE': 'VEHICLE', 'ROVER': 'VEHICLE',
                                                  'ARMORED_VEHICLE': 'VEHICLE', 'PHASER': 'EQUIPMENT', 'TRICORDER': 'EQUIPMENT',
                                                  'COMMUNICATOR': 'EQUIPMENT', 'SCIENTIFIC_INSTRUMENT': 'EQUIPMENT',
                                                  'MUSICAL_INSTRUMENT': 'EQUIPMENT'})

    def test_a_wrong_category_is_rejected_by_the_table_and_not_by_the_schema(self):
        record = js.load_json(validate.INVALID / 'asset-category-wrong-for-kind.json')
        self.assertEqual(js.errors(record, validate.schema_ref('Asset'), CONTRACT), [])
        self.assertTrue(validate.category_problems(record))

    def test_a_missing_category_is_rejected_by_the_schema(self):
        record = js.load_json(validate.INVALID / 'asset-category-missing.json')
        self.assertTrue(js.errors(record, validate.schema_ref('Asset'), CONTRACT))

    def test_the_removed_ground_vehicle_kind_is_rejected(self):
        record = js.load_json(validate.INVALID / 'asset-kind-ground-vehicle.json')
        self.assertEqual(record['kind'], 'GROUND_VEHICLE')
        self.assertTrue(js.errors(record, validate.schema_ref('Asset'), CONTRACT))

    def test_the_removed_generic_equipment_kind_is_rejected(self):
        record = js.load_json(validate.INVALID / 'asset-kind-equipment.json')
        self.assertEqual((record['kind'], record['category']), ('EQUIPMENT', 'EQUIPMENT'))
        self.assertTrue(js.errors(record, validate.schema_ref('Asset'), CONTRACT))
        self.assertNotIn('EQUIPMENT', validate.KIND_CATEGORY)

    def test_a_phaser_with_the_vehicle_category_is_rejected_by_the_table(self):
        record = js.load_json(validate.INVALID / 'asset-category-wrong-for-phaser.json')
        self.assertEqual((record['kind'], record['category']), ('PHASER', 'VEHICLE'))
        self.assertEqual(js.errors(record, validate.schema_ref('Asset'), CONTRACT), [])
        self.assertTrue(validate.category_problems(record))

    def test_every_kind_has_a_valid_example(self):
        kinds = {js.load_json(validate.VALID / p.name)['kind']
                 for p in validate.VALID.glob('asset-*.json') if 'list' not in p.name}
        self.assertEqual(kinds, set(validate.KIND_CATEGORY))

    def test_the_renamed_ship_kind_is_rejected(self):
        record = js.load_json(validate.INVALID / 'asset-kind-ship.json')
        self.assertEqual(record['kind'], 'SHIP')
        self.assertTrue(js.errors(record, validate.schema_ref('Asset'), CONTRACT))
        valid = js.load_json(validate.VALID / 'asset-starship-active.json')
        self.assertEqual(valid['kind'], 'STARSHIP')
        self.assertEqual(js.errors(valid, validate.schema_ref('Asset'), CONTRACT), [])

    def test_a_list_item_with_the_wrong_category_fails_the_table(self):
        listing = js.load_json(validate.VALID / 'asset-list.json')
        self.assertEqual(validate.category_problems(listing), [])
        listing['items'][0]['category'] = 'VEHICLE'
        self.assertTrue(validate.category_problems(listing))

    def test_an_equipment_used_as_a_parent_in_the_examples_fails(self):
        real = js.load_json

        def lying(path, *args, **kwargs):
            value = real(path, *args, **kwargs)
            if getattr(path, 'name', '') == 'asset-equipment-aboard-rover.json':
                value = dict(value, parentAssetId='EQ-64')
            return value

        with mock.patch.object(js, 'load_json', lying):
            with self.assertRaises(ValueError) as caught:
                validate.check_examples(CONTRACT)
        self.assertIn('non-vehicle', str(caught.exception))

    def test_the_invalid_inventory_is_exact(self):
        with mock.patch.dict(validate.REJECTED, {'asset-ghost.json': 'Asset'}):
            with self.assertRaises(ValueError):
                validate.check_rejections(CONTRACT)

    def test_an_accepted_invalid_fixture_fails_the_gate(self):
        loose = broken(lambda c: c['components']['schemas']['AssetStatus'].__setitem__(
            'enum', ['ACTIVE', 'LOST', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING']))
        with self.assertRaises(ValueError):
            validate.check_rejections(loose)

    def test_an_example_pointing_outside_the_fixtures_fails(self):
        def edit(c):
            examples = c['paths']['/assets']['get']['responses']['200']['content']['application/json']['examples']
            examples['page']['externalValue'] = '../contracts/assets-v1.0.openapi.json'
        with self.assertRaises(ValueError):
            validate.check_examples(broken(edit))

    def test_a_response_without_an_example_fails(self):
        def edit(c):
            c['components']['responses']['AssetNotFound']['content']['application/json'].pop('examples')
        with self.assertRaises((ValueError, KeyError)):
            validate.check_examples(broken(edit))

    def test_an_error_example_with_the_wrong_code_fails(self):
        def edit(c):
            media = c['components']['responses']['AssetNotFound']['content']['application/json']
            media['examples']['assetNotFound']['externalValue'] = '../fixtures/valid/error-invalid-asset-id.json'
        with self.assertRaises(ValueError):
            validate.check_examples(broken(edit))

    def test_each_valid_fixture_validates_against_the_schema_its_name_implies(self):
        for path in sorted(validate.VALID.glob('*.json')):
            name = 'Error' if path.name.startswith('error-') else 'AssetList' if 'list' in path.name else 'Asset'
            self.assertEqual(js.errors(js.load_json(path), validate.schema_ref(name), CONTRACT), [], path.name)


class ContractOneDotOne(unittest.TestCase):
    """1.1 follows 1.0 with the native identifier grammar and PATH_NOT_FOUND, each checked with its own fixtures."""

    def setUp(self):
        validate.select('1.1')
        self.addCleanup(validate.select, '1.0')
        self.contract = js.load_json(validate.CONTRACT)

    def broken(self, edit):
        contract = deepcopy(self.contract)
        edit(contract)
        return contract

    def test_the_whole_1_1_checks_pass(self):
        validate.run('1.1')

    def test_the_selected_files_are_the_1_1_ones(self):
        self.assertEqual(validate.CONTRACT.name, 'assets-v1.1.openapi.json')
        self.assertEqual(validate.VALID.parts[-2:], ('v1.1', 'valid'))
        self.assertEqual(validate.INVALID.parts[-2:], ('v1.1', 'invalid'))
        self.assertEqual(self.contract['info']['version'], '1.1')

    def test_the_identifier_grammar_has_one_spelling_each(self):
        schema = validate.schema_ref('AssetId')
        for good in ('AST-0017', 'AST-0001', 'AST-9999', 'AST-10000', 'AB_CD-0100', 'ABCDEFGH_ABCDEFGH_ABCDEFGH-0001'):
            with self.subTest(good=good):
                self.assertTrue(js.is_valid(good, schema, self.contract))
        for bad in ('SH-17', 'AST-17', 'AST-017', 'AST-0000', 'AST-00017', 'ast-0017', '_AST-0017', 'AST_-0017', 'AS__T-0017', 'A-0001',
                    'AST-0017\n', 'AST-００１７'):
            with self.subTest(bad=bad):
                self.assertFalse(js.is_valid(bad, schema, self.contract))

    def test_path_not_found_is_a_code_of_1_1_and_not_of_1_0(self):
        self.assertIn('PATH_NOT_FOUND', self.contract['components']['schemas']['ErrorCode']['enum'])
        self.assertNotIn('PATH_NOT_FOUND', CONTRACT['components']['schemas']['ErrorCode']['enum'])
        self.assertEqual(self.contract['x-unmatchedPath']['response'], {'$ref': '#/components/responses/PathNotFound'})
        self.assertNotIn('x-unmatchedPath', CONTRACT)

    def test_the_evolution_check_passes_and_fails_on_any_other_change(self):
        validate.check_contract_evolution()
        original = validate.CONTRACT_11
        for label, edit in (
                ('a new status', lambda c: c['components']['schemas']['AssetStatus']['enum'].append('LOST')),
                ('a lost path', lambda c: c['paths'].pop('/assets')),
                ('a dropped code', lambda c: c['components']['schemas']['ErrorCode']['enum'].remove('ASSET_NOT_FOUND')),
                ('the old grammar kept', lambda c: c['components']['schemas']['AssetId'].update(pattern=CONTRACT['components']['schemas']['AssetId']['pattern'])),
                ('a changed bound', lambda c: c['components']['schemas']['Asset']['properties']['name'].update(maxLength=121))):
            with self.subTest(label), tempfile.TemporaryDirectory() as folder:
                changed = Path(folder) / 'assets-v1.1.openapi.json'
                changed.write_text(json.dumps(self.broken(edit)), encoding='utf-8')
                with mock.patch.object(validate, 'CONTRACT_11', changed), mock.patch.object(validate.Path, 'glob', return_value=[
                        validate.CONTRACT_10, changed]):
                    with self.assertRaises(ValueError):
                        validate.check_contract_evolution()
        self.assertEqual(validate.CONTRACT_11, original)

    def test_a_missing_path_not_found_answer_fails(self):
        with self.assertRaises((ValueError, KeyError)):
            validate.check_structure(self.broken(lambda c: c.pop('x-unmatchedPath')))
        with self.assertRaises((ValueError, KeyError)):
            validate.check_structure(self.broken(lambda c: c['x-unmatchedPath'].__setitem__('response', {'$ref': '#/components/responses/AssetNotFound'})))

    def test_a_path_not_found_example_must_carry_that_code(self):
        def edit(c):
            c['components']['responses']['PathNotFound']['content']['application/json']['examples']['pathNotFound'][
                'externalValue'] = '../fixtures/v1.1/valid/error-asset-not-found.json'
        with self.assertRaises(ValueError):
            validate.check_examples(self.broken(edit))

    def test_the_invalid_inventory_is_exact_and_the_old_style_id_is_rejected(self):
        with mock.patch.dict(validate.REJECTED, {'asset-ghost.json': 'Asset'}):
            with self.assertRaises(ValueError):
                validate.check_rejections(self.contract)
        old_style = js.load_json(validate.INVALID / 'asset-invalid-id-old-style.json')
        self.assertEqual(old_style['assetId'], 'SH-17')
        self.assertTrue(js.errors(old_style, validate.schema_ref('Asset'), self.contract))
        self.assertEqual(js.errors(old_style, validate.schema_ref('Asset'), CONTRACT), [])  # a valid 1.0 asset

    def test_every_1_0_fixture_name_has_a_1_1_counterpart(self):
        names_10 = {p.name for p in (validate.COMPONENT / 'fixtures/valid').glob('*.json')}
        names_11 = {p.name for p in validate.VALID.glob('*.json')}
        self.assertEqual(names_11 - names_10, {'error-path-not-found.json'})
        self.assertEqual(names_10 - names_11, set())


if __name__ == '__main__':
    unittest.main()
