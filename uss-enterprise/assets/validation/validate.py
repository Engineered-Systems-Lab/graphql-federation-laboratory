"""Offline Assets contract checks, for contract 1.0 and for contract 1.1 (each with its own fixtures): OpenAPI structure, JSON Schema subset, examples and negative probes.

Standard library only. No service, database or Docker is involved or established.
"""
from copy import deepcopy
from pathlib import Path
import re
import sys

COMPONENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import jsonschema_subset as js

CONTRACT_10 = COMPONENT / 'contracts/assets-v1.0.openapi.json'
CONTRACT_11 = COMPONENT / 'contracts/assets-v1.1.openapi.json'
# Which contract and fixture folders the checks below read. They start on 1.0; select() switches them, and main() runs both.
CONTRACT = CONTRACT_10
VALID = COMPONENT / 'fixtures/valid'
INVALID = COMPONENT / 'fixtures/invalid'

ENUMS = {
    'AssetKind': 'STARSHIP SHUTTLE ROVER ARMORED_VEHICLE PHASER TRICORDER COMMUNICATOR SCIENTIFIC_INSTRUMENT MUSICAL_INSTRUMENT',
    'AssetCategory': 'VEHICLE EQUIPMENT',
    'AssetStatus': 'ACTIVE MAINTENANCE DECOMMISSIONED DESTROYED MISSING',
    'ErrorCode': 'INVALID_REQUEST INVALID_ASSET_ID ASSET_NOT_FOUND METHOD_NOT_ALLOWED INTERNAL_ERROR',
}
ASSET_FIELDS = ['assetId', 'kind', 'category', 'name', 'description', 'status', 'parentAssetId']
# The kind-to-category table of the design document, spelled once more here on purpose: a new kind is one enum value
# and one row, and the check below fails until both exist. Only a VEHICLE can be a parent.
KIND_CATEGORY = {'STARSHIP': 'VEHICLE', 'SHUTTLE': 'VEHICLE', 'ROVER': 'VEHICLE', 'ARMORED_VEHICLE': 'VEHICLE',
                 'PHASER': 'EQUIPMENT', 'TRICORDER': 'EQUIPMENT', 'COMMUNICATOR': 'EQUIPMENT',
                 'SCIENTIFIC_INSTRUMENT': 'EQUIPMENT', 'MUSICAL_INSTRUMENT': 'EQUIPMENT'}
# The asset id grammar of the selected contract, spelled once more here on purpose: a change must be noticed.
# 1.0 uses the Missions grammar; 1.1 uses the native Assets grammar (see PROFILES).
ASSET_ID_PATTERN = '^[A-Z]{2,5}-[1-9][0-9]*$'
UNSUPPORTED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
# Operation -> status -> the error code its example must carry (None: a success body, not an error).
OPERATIONS = {
    ('/assets', 'get'): ('listAssets', {'200': None, '400': 'INVALID_REQUEST', '500': 'INTERNAL_ERROR'}),
    ('/assets/{assetId}', 'get'): ('getAsset', {'200': None, '400': 'INVALID_ASSET_ID', '404': 'ASSET_NOT_FOUND',
                                                '500': 'INTERNAL_ERROR'}),
}
# Invalid fixtures: file -> the schema it must be rejected by.
REJECTED = {
    'asset-invalid-id-lowercase.json': 'Asset',
    'asset-invalid-id-leading-zero.json': 'Asset',
    'asset-unknown-status.json': 'Asset',
    'asset-missing-name.json': 'Asset',
    'asset-empty-name.json': 'Asset',
    'asset-parent-not-an-id.json': 'Asset',
    'asset-parent-omitted.json': 'Asset',
    'asset-category-missing.json': 'Asset',
    'asset-kind-ground-vehicle.json': 'Asset',
    'asset-kind-ship.json': 'Asset',
    'asset-kind-equipment.json': 'Asset',
    'asset-extra-property.json': 'Asset',
    'asset-list-negative-total.json': 'AssetList',
    'error-unknown-code.json': 'Error',
}
# Invalid fixtures that satisfy the schema and are rejected only by the kind-to-category table.
TABLE_REJECTED = ['asset-category-wrong-for-kind.json', 'asset-category-wrong-for-phaser.json']
ASTRAL = '\U0001F680'
VALID_COUNT = 19
VERSION = '1.0'
UNMATCHED = False  # 1.1 adds the answer for a path outside the two paths
ID_CASES = [('SH-17', True), ('EQ-64', True), ('AB-1', True), ('ABCDE-1', True), ('SHT-4', True), ('SH-1000000', True),
            ('A-1', False), ('ABCDEF-1', False), ('sh-17', False), ('SH-0', False), ('SH-017', False), ('SH-', False),
            ('SH17', False), ('SH--1', False), ('SH-+1', False), ('SH-1.5', False), ('SH-1e3', False), (' SH-17', False),
            ('SH-17 ', False), ('SH-17\n', False), ('SH-17\r\n', False), ('S1-17', False), ('SH-１７', False),
            ('', False), (17, False), (None, False), (True, False)]
SAMPLE_ID, SAMPLE_OTHER_ID, LOWER_ID = 'SH-17', 'SH-18', 'sh-17'

# What differs between the two contracts. 1.1 replaces the Missions grammar with the native Assets grammar and adds
# PATH_NOT_FOUND. Its prefix is one to three segments of capital letters joined by single underscores (the first segment 2 to 8 letters,
# the others 1 to 8), a hyphen, and a number zero-padded to four digits (not 0000) or, from 10000, written without leading zeros.
ASSET_ID_PATTERN_11 = ('^[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-'
                       '(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})$')
PROFILES = {}


def select(version):
    """Point the checks at one contract, its fixture folders and its vocabulary."""
    globals().update(PROFILES[version])


PROFILES['1.0'] = {'CONTRACT': CONTRACT_10, 'VALID': VALID, 'INVALID': INVALID, 'VALID_COUNT': VALID_COUNT, 'VERSION': '1.0',
                   'UNMATCHED': False, 'ENUMS': dict(ENUMS), 'ASSET_ID_PATTERN': ASSET_ID_PATTERN, 'REJECTED': dict(REJECTED),
                   'TABLE_REJECTED': list(TABLE_REJECTED), 'ID_CASES': ID_CASES, 'SAMPLE_ID': 'SH-17',
                   'SAMPLE_OTHER_ID': 'SH-18', 'LOWER_ID': 'sh-17'}
PROFILES['1.1'] = {
    'CONTRACT': CONTRACT_11, 'VALID': COMPONENT / 'fixtures/v1.1/valid', 'INVALID': COMPONENT / 'fixtures/v1.1/invalid',
    'VALID_COUNT': 20, 'VERSION': '1.1', 'UNMATCHED': True,
    'ENUMS': {**ENUMS, 'ErrorCode': 'INVALID_REQUEST INVALID_ASSET_ID ASSET_NOT_FOUND PATH_NOT_FOUND METHOD_NOT_ALLOWED INTERNAL_ERROR'},
    'ASSET_ID_PATTERN': ASSET_ID_PATTERN_11,
    'REJECTED': {
        'asset-invalid-id-lowercase.json': 'Asset',
        'asset-invalid-id-leading-zero.json': 'Asset',
        'asset-invalid-id-old-style.json': 'Asset',
        'asset-invalid-id-leading-underscore.json': 'Asset',
        'asset-invalid-id-trailing-underscore.json': 'Asset',
        'asset-invalid-id-double-underscore.json': 'Asset',
        'asset-invalid-id-number-too-short.json': 'Asset',
        'asset-invalid-id-all-zeros.json': 'Asset',
        'asset-unknown-status.json': 'Asset',
        'asset-missing-name.json': 'Asset',
        'asset-empty-name.json': 'Asset',
        'asset-parent-not-an-id.json': 'Asset',
        'asset-parent-omitted.json': 'Asset',
        'asset-category-missing.json': 'Asset',
        'asset-kind-ground-vehicle.json': 'Asset',
        'asset-kind-ship.json': 'Asset',
        'asset-kind-equipment.json': 'Asset',
        'asset-extra-property.json': 'Asset',
        'asset-list-negative-total.json': 'AssetList',
        'error-unknown-code.json': 'Error',
    },
    'TABLE_REJECTED': list(TABLE_REJECTED),
    'ID_CASES': [('AST-0017', True), ('AST-0001', True), ('AST-0100', True), ('AST-9999', True), ('AST-10000', True),
                 ('AST-1234567', True), ('AB-0001', True), ('ABCDEFGH-0001', True), ('AB_CD-0001', True), ('AB_CD_EF-0001', True),
                 ('ABCDEFGH_ABCDEFGH_ABCDEFGH-0001', True),
                 ('SH-17', False), ('EQ-64', False), ('SH-017', False), ('AST-17', False), ('AST-017', False),
                 ('AST-0000', False), ('AST-00000', False), ('AST-000', False), ('AST-00017', False), ('AST-012345', False),
                 ('ast-0017', False), ('Ast-0017', False), ('_AST-0017', False), ('AST_-0017', False), ('AS__T-0017', False),
                 ('AST__-0017', False), ('AB_-0001', False), ('A_BC-0001', False), ('A-0001', False), ('ABCDEFGHI-0001', False),
                 ('AB_CD_EF_GH-0001', False), ('ABCDEFGHI_AB-0001', False), ('AB_C1-0001', False), ('AST0017', False),
                 ('AST--0017', False), ('AST-+017', False), ('AST-1.5', False), ('AST-1e3', False), ('AST-', False),
                 ('-0017', False), (' AST-0017', False), ('AST-0017 ', False), ('AST-0017\n', False), ('AST-0017\r\n', False),
                 ('AST-００１７', False), ('', False), (17, False), (None, False), (True, False)],
    'SAMPLE_ID': 'AST-0017', 'SAMPLE_OTHER_ID': 'AST-0018', 'LOWER_ID': 'ast-0017'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def schema_ref(name):
    return {'$ref': f'#/components/schemas/{name}'}


def accepted(root, schema, instance):
    return js.is_valid(instance, schema, root)


def category_problems(value):
    """The one rule between members the schema cannot state: category equals the table value for the kind."""
    records = value['items'] if isinstance(value, dict) and 'items' in value else [value]
    problems = []
    for record in records:
        if not isinstance(record, dict) or 'kind' not in record or 'category' not in record:
            continue
        expected = KIND_CATEGORY.get(record['kind'])
        if expected is None or record['category'] != expected:
            problems.append(f"{record.get('assetId')}: category {record['category']!r} does not match kind "
                            f"{record['kind']!r} (the table says {expected!r})")
    return problems


def check_structure(contract):
    """The OpenAPI document: version, paths, references, vocabulary and the decided surface."""
    require(contract.get('openapi') == '3.1.0', 'OpenAPI version must be 3.1.0')
    require(contract['info'].get('version') == VERSION, 'Contract version must be ' + VERSION)
    require(set(contract) == {'openapi', 'info', 'servers', 'paths', 'components'} | ({'x-unmatchedPath'} if UNMATCHED else set()),
            'Top-level members')
    if UNMATCHED:
        require(contract['x-unmatchedPath']['response'] == {'$ref': '#/components/responses/PathNotFound'}, '404 response for a path outside the contract')
        require(set(contract['x-unmatchedPath']) == {'description', 'response'}, 'x-unmatchedPath members')
    require(contract['servers'] == [{'url': '/'}], 'Servers')
    require(set(contract['paths']) == {path for path, _ in OPERATIONS}, 'Paths drift: ' + ', '.join(contract['paths']))
    components = contract['components']
    require(set(components) == {'schemas', 'parameters', 'headers', 'responses'}, 'Component groups')

    for name, schema in components['schemas'].items():
        js.check_schema(schema, contract, '#/components/schemas/' + name)
    for name, tokens in ENUMS.items():
        require(components['schemas'][name].get('enum') == tokens.split(), 'Enum drift: ' + name)
    require(components['schemas']['AssetId']['pattern'] == ASSET_ID_PATTERN, 'Asset id grammar drift')
    require(list(KIND_CATEGORY) == ENUMS['AssetKind'].split(), 'Every kind needs one row of the category table')
    require(sorted(set(KIND_CATEGORY.values())) == sorted(ENUMS['AssetCategory'].split()), 'Category table values')
    require(not {'GROUND_VEHICLE', 'SHIP', 'EQUIPMENT'} & set(KIND_CATEGORY), 'GROUND_VEHICLE, SHIP and the generic EQUIPMENT are not kinds')
    asset = components['schemas']['Asset']
    require(list(asset['properties']) == ASSET_FIELDS, 'Asset field drift (there is no location in 1.0)')
    require(sorted(asset['required']) == sorted(ASSET_FIELDS) and asset['additionalProperties'] is False, 'Asset is strict')
    require(sorted(components['schemas']['Error']['required']) == ['code', 'message'], 'Error shape')
    require(sorted(components['schemas']['AssetList']['required']) == ['items', 'limit', 'offset', 'total'], 'List shape')

    for path, item in contract['paths'].items():
        require(set(item) == {'get', 'x-unsupportedMethods'}, 'Only GET is an operation on ' + path)
        unsupported = item['x-unsupportedMethods']
        require(unsupported['methods'] == UNSUPPORTED_METHODS, 'Unsupported methods on ' + path)
        require(unsupported['response'] == {'$ref': '#/components/responses/MethodNotAllowed'}, '405 response on ' + path)
        operation = item['get']
        operation_id, statuses = OPERATIONS[(path, 'get')]
        require(operation['operationId'] == operation_id, 'operationId on ' + path)
        require(list(operation['responses']) == list(statuses), 'Response statuses on ' + path)
        require('security' not in operation and 'requestBody' not in operation, 'No security or request body on ' + path)
        for parameter in operation['parameters']:
            resolved = js.resolve(contract, parameter['$ref'])
            require(resolved['in'] in ('path', 'query'), 'Parameter location')
            js.check_schema(resolved['schema'], contract)
            if resolved['in'] == 'path':
                require('{' + resolved['name'] + '}' in path and resolved['required'] is True, 'Path parameter ' + resolved['name'])
    list_params = [js.resolve(contract, p['$ref'])['name'] for p in contract['paths']['/assets']['get']['parameters']]
    require(list_params == ['kind', 'category', 'status', 'parentAssetId', 'offset', 'limit'], 'List filters and paging')

    # Every reference resolves, locally, and every response has a description and an application/json body.
    def walk(node):
        if isinstance(node, dict):
            if '$ref' in node:
                js.resolve(contract, node['$ref'])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(contract)
    for name, response in components['responses'].items():
        require(response.get('description'), 'Response without description: ' + name)
        require(set(response['content']) == {'application/json'}, 'Response media type: ' + name)


def response_for(contract, path, status):
    response = contract['paths'][path]['get']['responses'][status]
    return js.resolve(contract, response['$ref']) if '$ref' in response else response


def check_examples(contract):
    """Every example of the contract validates against its own response schema; every valid fixture is used once."""
    used = {}
    for (path, method), (_, statuses) in OPERATIONS.items():
        for status, code in statuses.items():
            raw = contract['paths'][path][method]['responses'][status]
            owner = raw.get('$ref', f'{method.upper()} {path} {status}')
            media = response_for(contract, path, status)['content']['application/json']
            examples = media.get('examples') or {}
            require(examples, f'{method.upper()} {path} {status} has no example')
            for label, example in examples.items():
                require(set(example) == {'summary', 'externalValue'}, f'Example shape: {label}')
                target = (CONTRACT.parent / example['externalValue']).resolve()
                require(target.parent == VALID.resolve() and target.is_file(), 'Example outside fixtures/valid: ' + label)
                value = js.load_json(target)
                problems = js.errors(value, media['schema'], contract) + category_problems(value)
                require(not problems, f'{target.name} violates its schema: {problems}')
                if code is not None:
                    require(value['code'] == code, f'{target.name} must carry {code}')
                require(used.setdefault(target.name, owner) == owner, f'{target.name} is used by two responses')
    # 405 is shared by both paths: its single example is checked once through the component.
    response = contract['components']['responses']['MethodNotAllowed']
    for label, example in response['content']['application/json']['examples'].items():
        target = (CONTRACT.parent / example['externalValue']).resolve()
        value = js.load_json(target)
        require(not js.errors(value, response['content']['application/json']['schema'], contract), target.name + ' schema')
        require(value['code'] == 'METHOD_NOT_ALLOWED', target.name + ' code')
        require(used.setdefault(target.name, '#/components/responses/MethodNotAllowed') ==
                '#/components/responses/MethodNotAllowed', target.name + ' is used by two responses')
    if UNMATCHED:
        # A path outside the two has no operation: its 404 is its own code, never ASSET_NOT_FOUND.
        response = contract['components']['responses']['PathNotFound']
        media = response['content']['application/json']
        require(media['schema'] == schema_ref('Error'), 'PathNotFound body is an Error')
        for label, example in media['examples'].items():
            target = (CONTRACT.parent / example['externalValue']).resolve()
            require(target.parent == VALID.resolve() and target.is_file(), 'Example outside the fixtures: ' + label)
            value = js.load_json(target)
            require(not js.errors(value, media['schema'], contract), target.name + ' schema')
            require(value['code'] == 'PATH_NOT_FOUND', target.name + ' code')
            require(used.setdefault(target.name, '#/components/responses/PathNotFound') ==
                    '#/components/responses/PathNotFound', target.name + ' is used by two responses')
    on_disk = sorted(p.name for p in VALID.glob('*.json'))
    require(sorted(used) == on_disk, f'Valid fixture inventory differs from the examples: {sorted(set(on_disk) ^ set(used))}')
    require(len(on_disk) == VALID_COUNT, 'Valid fixture count')
    singles = [js.load_json(VALID / name) for name in on_disk if name.startswith('asset-') and 'list' not in name]
    require({a['status'] for a in singles} == set(ENUMS['AssetStatus'].split()), 'Every status needs an example')
    require({a['kind'] for a in singles} == set(ENUMS['AssetKind'].split()), 'Every kind needs an example')
    require({a['category'] for a in singles} == set(ENUMS['AssetCategory'].split()), 'Every category needs an example')
    require(any(a['parentAssetId'] for a in singles), 'An example with a parent is required')
    # Within the examples, a named parent is a VEHICLE: the one place the rule between records can be seen offline.
    known = {a['assetId']: a['category'] for a in singles}
    for asset in singles:
        parent = asset['parentAssetId']
        if parent in known:
            require(known[parent] == 'VEHICLE', f"{asset['assetId']} names the non-vehicle {parent} as its parent")
    require(any(known.get(a['parentAssetId']) == 'VEHICLE' and a['category'] == 'EQUIPMENT' for a in singles),
            'An equipment with a vehicle parent is required')


def check_rejections(contract):
    require(sorted(p.name for p in INVALID.glob('*.json')) == sorted([*REJECTED, *TABLE_REJECTED]), 'Invalid fixture inventory')
    for name in TABLE_REJECTED:
        value = js.load_json(INVALID / name)
        require(not js.errors(value, schema_ref('Asset'), contract), f'{name} must satisfy the schema: only the table rejects it')
        require(category_problems(value), f'Invalid fixture {name} was accepted by the category table')
    for name, schema_name in REJECTED.items():
        problems = js.errors(js.load_json(INVALID / name), schema_ref(schema_name), contract)
        require(problems, f'Invalid fixture {name} was accepted by {schema_name}')


def probe(contract, schema_name, base, valid, mutate, label):
    sample = deepcopy(base)
    mutate(sample)
    found = accepted(contract, schema_ref(schema_name), sample)
    require(found == valid, f'Probe {label}: expected {"accepted" if valid else "rejected"}')


def check_probes(contract):
    asset = js.load_json(VALID / 'asset-equipment-with-parent.json')
    listing = js.load_json(VALID / 'asset-list.json')
    error = js.load_json(VALID / 'error-asset-not-found.json')

    def field(name, cases, schema='Asset', base=asset):
        for value, valid in cases:
            probe(contract, schema, base, valid, lambda r, v=value: r.__setitem__(name, v), f'{name}={value!r}')

    def removal(name, valid, base=asset, schema='Asset'):
        probe(contract, schema, base, valid, lambda r: r.pop(name), 'missing ' + name)

    # Required fields and strictness.
    for name in ASSET_FIELDS:
        removal(name, False)
    probe(contract, 'Asset', asset, False, lambda r: r.__setitem__('extra', 1), 'unknown member')
    probe(contract, 'Asset', asset, False, lambda r: r.__setitem__('location', 'Deck 4'), 'location is not in 1.0')
    for wrong in ([], 'text', 1, None):
        require(not accepted(contract, schema_ref('Asset'), wrong), f'A non-object is not an asset: {wrong!r}')

    # Enumerations are exact and case-sensitive, and a number or null is not a token.
    for name, key in (('AssetKind', 'kind'), ('AssetCategory', 'category'), ('AssetStatus', 'status')):
        tokens = ENUMS[name].split()
        field(key, [(t, True) for t in tokens]
              + [(tokens[0].lower(), False), (' ' + tokens[0], False), (tokens[0] + ' ', False), ('', False),
                 ('UNKNOWN', False), (None, False), (1, False), (True, False)])
    field('status', [('LOST', False), ('RETIRED', False)])
    field('kind', [('GROUND_VEHICLE', False), ('SHIP', False), ('EQUIPMENT', False), ('AFV', False), ('TANK', False), ('STATION', False), ('ARMORED VEHICLE', False)])
    field('category', [('VESSEL', False), ('vehicle', False)])

    # The kind-to-category table: each kind has one category, and any other is rejected.
    for kind, category in KIND_CATEGORY.items():
        for other in ENUMS['AssetCategory'].split():
            record = dict(asset, kind=kind, category=other)
            require(bool(category_problems(record)) == (other != category), f'Category table: {kind} with {other}')
    require(category_problems(dict(asset, kind='UNKNOWN', category='VEHICLE')), 'An unknown kind has no category')
    require(not category_problems(listing), 'The list example agrees with the table')
    require(category_problems(dict(listing, items=[dict(listing['items'][0], category='VEHICLE')])),
            'A list item that disagrees with the table fails the list')

    # Identifiers: the grammar of the selected contract, one spelling each.
    ids = ID_CASES
    field('assetId', ids)
    field('parentAssetId', [(v, ok) for v, ok in ids if v is not None] + [(None, True)])
    starship = js.load_json(VALID / 'asset-starship-active.json')
    probe(contract, 'Asset', starship, True, lambda r: None, 'null parent')
    probe(contract, 'Asset', starship, True, lambda r: r.__setitem__('parentAssetId', SAMPLE_OTHER_ID), 'a parent is any asset id')

    # Text: code-point bounds, empty is invalid, whitespace and astral characters count as characters.
    for name, limit in (('name', 120), ('description', 1000)):
        field(name, [('x' * limit, True), ('x' * (limit + 1), False), ('', False), (ASTRAL * limit, True),
                     (ASTRAL * (limit + 1), False), ('   ', True), (' lead and trail ', True), (None, False), (1, False)])

    # The list: strict members, bounded items, integer bounds, no booleans as numbers.
    field('offset', [(0, True), (40, True), (-1, False), (1.5, False), ('0', False), (True, False), (None, False)], 'AssetList', listing)
    field('limit', [(1, True), (50, True), (0, False), (51, False), (1.5, False), (True, False)], 'AssetList', listing)
    field('total', [(0, True), (31, True), (-1, False), (1.5, False), ('31', False), (False, False)], 'AssetList', listing)
    for name in ('items', 'offset', 'limit', 'total'):
        removal(name, False, listing, 'AssetList')
    probe(contract, 'AssetList', listing, False, lambda r: r.__setitem__('extra', 1), 'list unknown member')
    probe(contract, 'AssetList', listing, True, lambda r: r['items'].clear(), 'empty items')
    probe(contract, 'AssetList', listing, True, lambda r: r.__setitem__('items', [deepcopy(asset)] * 50), '50 items')
    probe(contract, 'AssetList', listing, False, lambda r: r.__setitem__('items', [deepcopy(asset)] * 51), '51 items')
    probe(contract, 'AssetList', listing, False, lambda r: r['items'][0].pop('name'), 'a bad member fails the list')
    probe(contract, 'AssetList', listing, False, lambda r: r.__setitem__('items', {'assetId': SAMPLE_ID}), 'items is an array')

    # Errors.
    field('code', [(c, True) for c in ENUMS['ErrorCode'].split()]
          + [('ASSET_GONE', False), ('SERVICE_UNAVAILABLE', False), ('invalid_request', False), ('', False), (None, False)],
          'Error', error)
    field('message', [('x', True), ('x' * 1000, True), ('x' * 1001, False), (ASTRAL * 1000, True), (ASTRAL * 1001, False),
                      ('', False), (None, False)], 'Error', error)
    removal('code', False, error, 'Error')
    removal('message', False, error, 'Error')
    probe(contract, 'Error', error, False, lambda r: r.__setitem__('detail', 'x'), 'error unknown member')

    # Query parameters keep one canonical spelling.
    parameters = contract['components']['parameters']
    for name, cases in (
            ('Offset', [('0', True), ('20', True), ('100', True), ('00', False), ('01', False), ('+5', False),
                        ('-1', False), ('1.5', False), ('1e2', False), (' 1', False), ('', False), ('1\n', False)]),
            ('Limit', [('1', True), ('9', True), ('10', True), ('20', True), ('49', True), ('50', True), ('0', False),
                       ('51', False), ('99', False), ('100', False), ('01', False), ('050', False), ('+5', False),
                       ('', False), ('5 ', False)])):
        for value, valid in cases:
            found = accepted(contract, parameters[name]['schema'], value)
            require(found == valid, f'Query {name}={value!r}: expected {"accepted" if valid else "rejected"}')
    for name, tokens in (('KindFilter', ENUMS['AssetKind']), ('CategoryFilter', ENUMS['AssetCategory']),
                         ('StatusFilter', ENUMS['AssetStatus'])):
        for token in tokens.split():
            require(accepted(contract, parameters[name]['schema'], token), f'{name}={token}')
        require(not accepted(contract, parameters[name]['schema'], tokens.split()[0].lower()), name + ' is case-sensitive')
    require(accepted(contract, parameters['ParentAssetIdFilter']['schema'], SAMPLE_ID), 'parentAssetId filter')
    require(not accepted(contract, parameters['ParentAssetIdFilter']['schema'], LOWER_ID), 'parentAssetId filter grammar')
    require(parameters['Offset']['schema']['default'] == '0' and parameters['Limit']['schema']['default'] == '20', 'Defaults')
    require(contract['components']['headers']['Allow']['schema']['const'] == 'GET', 'Allow lists GET only')


def check_hygiene():
    for folder in (VALID, INVALID):
        for path in folder.glob('*.json'):
            text = path.read_bytes().decode('utf-8')
            require(re.search(r'\$schema|\$ref|externalValue', text) is None, 'Schema hints in fixture: ' + path.name)


def comparable(contract):
    """What 1.0 and 1.1 share: the contracts without prose, example links and the four things 1.1 changes."""
    stripped = deepcopy(contract)
    stripped['info'].pop('version', None)
    stripped.pop('x-unmatchedPath', None)
    stripped['components']['schemas'].pop('AssetId', None)
    stripped['components']['schemas'].pop('ErrorCode', None)
    stripped['components']['responses'].pop('PathNotFound', None)

    def strip(node):
        if isinstance(node, dict):
            for prose in ('description', 'summary', 'externalValue'):
                node.pop(prose, None)
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)
    strip(stripped)
    return stripped


def check_contract_evolution():
    """1.0 is the first published contract. 1.1 is a new file beside it. They differ in the identifier grammar and one error
    code and in nothing else: not in a path, a parameter, a response status, a schema, an enum or a bound."""
    published = sorted(p.name for p in CONTRACT_10.parent.glob('*.json'))
    require(published == ['assets-v1.0.openapi.json', 'assets-v1.1.openapi.json'], 'Published contract files: ' + ', '.join(published))
    old, new = js.load_json(CONTRACT_10), js.load_json(CONTRACT_11)
    require(comparable(old) == comparable(new), '1.1 differs from 1.0 by more than the identifier grammar and PATH_NOT_FOUND')
    old_codes = old['components']['schemas']['ErrorCode']['enum']
    new_codes = new['components']['schemas']['ErrorCode']['enum']
    expected = list(old_codes)
    expected.insert(expected.index('ASSET_NOT_FOUND') + 1, 'PATH_NOT_FOUND')
    require(new_codes == expected, 'The error codes of 1.1 are those of 1.0 plus PATH_NOT_FOUND')
    require(old['components']['schemas']['AssetId']['pattern'] != new['components']['schemas']['AssetId']['pattern'],
            '1.1 changes the identifier grammar')


def run(version):
    select(version)
    contract = js.load_json(CONTRACT)
    check_structure(contract)
    check_examples(contract)
    check_rejections(contract)
    check_probes(contract)
    check_hygiene()
    print(f'PASS: Assets OpenAPI {version} structure, subset-checked JSON Schemas, {VALID_COUNT} valid examples bound to '
          f'their responses, {len(REJECTED) + len(TABLE_REJECTED)} rejected fixtures, the kind-to-category table and '
          'enum/identifier/text/number/list/error/query negative probes.')


def main():
    try:
        for version in ('1.0', '1.1'):
            run(version)
        check_contract_evolution()
    finally:
        select('1.0')
    print('PASS: Assets contract 1.1 is 1.0 with the native identifier grammar and PATH_NOT_FOUND, and nothing else.')
    print('LIMITS: offline contract only. The JSON Schema checker covers the keywords this contract uses and fails on any '
          'other. Service behavior, HTTP status mapping, the Allow header, ordering, filtering, the database and every '
          'cross-record rule (a parent exists, only a VEHICLE is a parent, no cycle) belong to later slices and are not '
          'established here beyond the examples.')


def cli(entry):
    try:
        return entry() or 0
    except (ValueError, OSError, KeyError, TypeError, js.SchemaError) as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(cli(main))
