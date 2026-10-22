"""The decisions of the Assets read service that need no database and no socket.

Routing, identifier and query validation, the error bodies, the order key and the JSON shape of an asset, as
docs/ASSETS-V1-DESIGN.md and contract 1.1 (a compatible minor of 1.0) state them. Standard library only. The values that the database owns
(the kinds, the categories and the statuses) arrive as a Reference read from the database: this module holds
no second copy of the kind-to-category table.
"""
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote
import re

# The native identifier grammar of contract 1.1: a prefix of capital letters (one to three segments joined by single
# underscores), a hyphen and a number written with four or more digits (zero-padded to four, never all zeros).
ASSET_ID = re.compile(r'[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})')
OFFSET = re.compile(r'0|[1-9][0-9]*')
LIMIT = re.compile(r'[1-9]|[1-4][0-9]|50')
DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 20
MAX_QUERY_FIELDS = 20
FILTERS = ('kind', 'category', 'status', 'parentAssetId')
PARAMETERS = frozenset(FILTERS + ('offset', 'limit'))
ALLOW = 'GET'
# The members of an asset, in the order the contract lists them. Member order carries no meaning.
ASSET_MEMBERS = ('assetId', 'kind', 'category', 'name', 'description', 'status', 'parentAssetId')


class ApiError(Exception):
    """A failure the contract names: an HTTP status, a stable code and a short human-readable message."""

    def __init__(self, status, code, message, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = dict(headers or {})

    def body(self):
        return {'code': self.code, 'message': self.message}


def internal_error():
    return ApiError(500, 'INTERNAL_ERROR', 'The service could not complete the request.')


@dataclass(frozen=True)
class Reference:
    """What the database says the filter tokens may be."""
    kinds: frozenset
    categories: frozenset
    statuses: frozenset


@dataclass(frozen=True)
class ListQuery:
    kind: object = None
    category: object = None
    status: object = None
    parent_asset_id: object = None
    offset: int = DEFAULT_OFFSET
    limit: int = DEFAULT_LIMIT


@dataclass(frozen=True)
class Response:
    status: int
    body: dict
    headers: dict


def id_sort_key(asset_id):
    """The order of the list: the prefix as text, then the number as a number (AST-0002, AST-0017, AST-10000)."""
    prefix, number = asset_id.split('-')
    return prefix, int(number)


def asset_json(row):
    """The seven members of an asset from a mapping with the database column names."""
    return {'assetId': row['asset_id'], 'kind': row['kind'], 'category': row['category'], 'name': row['name'],
            'description': row['description'], 'status': row['status'], 'parentAssetId': row['parent_asset_id']}


def parse_asset_id(text):
    """Validate an identifier exactly as sent: no case folding, trimming or other normalization."""
    if not ASSET_ID.fullmatch(text):
        raise ApiError(400, 'INVALID_ASSET_ID',
                       'The asset identifier must be a prefix of capital letters, a hyphen and a zero-padded number of at least four digits, for example AST-0017.')
    return text


def parse_list_query(raw_query, reference):
    """Turn the raw query string of GET /assets into a ListQuery, or raise INVALID_REQUEST for anything else."""
    try:
        pairs = parse_qsl(raw_query, keep_blank_values=True, strict_parsing=True, encoding='utf-8', errors='strict',
                          max_num_fields=MAX_QUERY_FIELDS) if raw_query else []
    except ValueError:
        raise ApiError(400, 'INVALID_REQUEST', 'The query string is malformed.') from None
    values = {}
    for name, value in pairs:
        if name not in PARAMETERS:
            raise ApiError(400, 'INVALID_REQUEST', 'The query contains a parameter that this service does not support.')
        if name in values:
            raise ApiError(400, 'INVALID_REQUEST', 'A query parameter is repeated; each may appear once.')
        values[name] = value
    allowed = {'kind': reference.kinds, 'category': reference.categories, 'status': reference.statuses}
    for name, tokens in allowed.items():
        if name in values and values[name] not in tokens:
            raise ApiError(400, 'INVALID_REQUEST', f'The {name} parameter must be exactly one of its documented values.')
    if 'parentAssetId' in values and not ASSET_ID.fullmatch(values['parentAssetId']):
        raise ApiError(400, 'INVALID_REQUEST', 'The parentAssetId parameter must be a well-formed asset identifier.')
    if 'offset' in values and not OFFSET.fullmatch(values['offset']):
        raise ApiError(400, 'INVALID_REQUEST', 'The offset parameter must be 0 or a positive whole number without leading zeros.')
    if 'limit' in values and not LIMIT.fullmatch(values['limit']):
        raise ApiError(400, 'INVALID_REQUEST', 'The limit parameter must be a whole number from 1 to 50.')
    return ListQuery(kind=values.get('kind'), category=values.get('category'), status=values.get('status'),
                     parent_asset_id=values.get('parentAssetId'),
                     offset=int(values['offset']) if 'offset' in values else DEFAULT_OFFSET,
                     limit=int(values['limit']) if 'limit' in values else DEFAULT_LIMIT)


def split_target(target):
    """The path and the raw query of a request target; no normalization of either."""
    path, _, query = target.partition('?')
    return path, query


def route(method, target):
    """Name the operation a request asks for: ('asset', raw id segment) or ('list', raw query).

    A path outside the two of the contract is 404 PATH_NOT_FOUND (never ASSET_NOT_FOUND) whatever the method; a method other than GET on either
    of them is 405 with Allow: GET; the identifier and the query are judged only for a GET.
    """
    path, query = split_target(target)
    if path == '/assets':
        operation = ('list', query)
    elif path.startswith('/assets/') and path.count('/') == 2 and len(path) > len('/assets/'):
        operation = ('asset', path[len('/assets/'):])
    else:
        raise ApiError(404, 'PATH_NOT_FOUND', 'No resource exists at this path.')
    if method != 'GET':
        raise ApiError(405, 'METHOD_NOT_ALLOWED', 'The Assets service is read-only; only GET is supported.', {'Allow': ALLOW})
    return operation


def handle(method, target, store, reference):
    """Answer one request against a store that offers get(asset_id) and page(query); return a Response."""
    kind, argument = route(method, target)
    if kind == 'asset':
        try:
            asset_id = parse_asset_id(unquote(argument, encoding='utf-8', errors='strict'))
        except UnicodeDecodeError:
            raise ApiError(400, 'INVALID_ASSET_ID', 'The asset identifier is not valid percent-encoded UTF-8.') from None
        row = store.get(asset_id)
        if row is None:
            raise ApiError(404, 'ASSET_NOT_FOUND', 'No asset has this identifier.')
        return Response(200, asset_json(row), {})
    query = parse_list_query(argument, reference)
    rows, total = store.page(query)
    return Response(200, {'items': [asset_json(row) for row in rows], 'offset': query.offset, 'limit': query.limit,
                          'total': total}, {})


def http_error(code):
    """Map a status that the HTTP server itself raises (a malformed request line, a header too large) to the contract."""
    if code >= 500 and code != 505:
        return internal_error()
    return ApiError(400, 'INVALID_REQUEST', 'The request is not a well-formed HTTP request.')
