"""A small, strict JSON Schema checker for the Assets contract. Standard library only.

It implements exactly the keywords the contract uses. A keyword outside that set is
an error, never silently ignored, so the contract cannot drift into rules this checker
does not evaluate. Patterns are restricted to a portable subset: Python and ECMAScript
regular expressions agree on it, `$` means the very end of the text, and no escape or
group has a Unicode-dependent meaning.
"""
import json
import re

ANNOTATIONS = frozenset({'description', 'title', 'default', 'examples', '$comment'})
KEYWORDS = frozenset({
    'type', 'enum', 'const', 'pattern', 'minLength', 'maxLength', 'minimum', 'maximum',
    'required', 'properties', 'additionalProperties', 'items', 'minItems', 'maxItems',
    'oneOf', '$ref'}) | ANNOTATIONS
TYPES = frozenset({'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'})


class SchemaError(ValueError):
    """The schema itself is outside the supported subset or malformed."""


def _reject_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f'Duplicate JSON key: {key!r}')
        seen[key] = value
    return seen


def _reject_constant(name):
    raise ValueError(f'Non-JSON number constant: {name}')


def load_json(path):
    """Read strict JSON: UTF-8 without a byte-order mark, no duplicate keys, no NaN or Infinity."""
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError(f'Byte-order mark: {path.name}')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)


def compile_pattern(pattern):
    """Translate a portable pattern to Python. `$` is the end of the text, never before a final newline."""
    if re.search(r'\\[dDwWsSbBpPuUxXkK]|\(\?(?!:)|(?<!\\)\.', pattern):
        raise SchemaError(f'Pattern outside the portable subset: {pattern}')
    translated = pattern[:-1] + r'\Z' if pattern.endswith('$') and not pattern.endswith('\\$') else pattern
    if '$' in translated.replace('\\$', ''):
        raise SchemaError(f'Pattern uses $ other than at the end: {pattern}')
    return re.compile(translated)


def resolve(root, reference):
    if not isinstance(reference, str) or not reference.startswith('#/'):
        raise SchemaError(f'Only local references are supported: {reference!r}')
    node = root
    for part in reference[2:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f'Unresolved reference: {reference}')
        node = node[part]
    return node


def check_schema(schema, root, path='#'):
    """Raise SchemaError unless the schema, and every schema below it, uses only the supported subset."""
    if not isinstance(schema, dict):
        raise SchemaError(f'{path}: a schema is an object')
    unknown = sorted(set(schema) - KEYWORDS)
    if unknown:
        raise SchemaError(f'{path}: unsupported keyword(s) {unknown}')
    if '$ref' in schema:
        if len(set(schema) - ANNOTATIONS) != 1:
            raise SchemaError(f'{path}: $ref stands alone')
        check_schema(resolve(root, schema['$ref']), root, schema['$ref'])
        return
    if 'type' in schema:
        names = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not names or not all(isinstance(n, str) and n in TYPES for n in names):
            raise SchemaError(f'{path}: unsupported type {schema["type"]!r}')
    if 'pattern' in schema:
        compile_pattern(schema['pattern'])
    if 'enum' in schema and (not isinstance(schema['enum'], list) or not schema['enum']):
        raise SchemaError(f'{path}: enum is a non-empty list')
    if 'required' in schema and not (isinstance(schema['required'], list) and all(isinstance(n, str) for n in schema['required'])):
        raise SchemaError(f'{path}: required is a list of names')
    if 'additionalProperties' in schema and schema['additionalProperties'] is not False:
        raise SchemaError(f'{path}: additionalProperties is false or absent')
    for name, sub in (schema.get('properties') or {}).items():
        check_schema(sub, root, f'{path}/properties/{name}')
    if 'items' in schema:
        check_schema(schema['items'], root, f'{path}/items')
    for number, sub in enumerate(schema.get('oneOf') or []):
        check_schema(sub, root, f'{path}/oneOf/{number}')


def _is_integer(value):
    return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _type_matches(name, value):
    return {
        'object': lambda v: isinstance(v, dict),
        'array': lambda v: isinstance(v, list),
        'string': lambda v: isinstance(v, str),
        'integer': _is_integer,
        'number': _is_number,
        'boolean': lambda v: isinstance(v, bool),
        'null': lambda v: v is None,
    }[name](value)


def _same(a, b):
    """JSON equality that never equates true with 1 or false with 0."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def errors(instance, schema, root, path='$'):
    """Return the list of violations of instance against schema; empty means valid."""
    if '$ref' in schema:
        return errors(instance, resolve(root, schema['$ref']), root, path)
    found = []
    if 'type' in schema:
        names = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_type_matches(n, instance) for n in names):
            return [f'{path}: expected {"|".join(names)}']
    if 'const' in schema and not _same(instance, schema['const']):
        found.append(f'{path}: not the constant {schema["const"]!r}')
    if 'enum' in schema and not any(_same(instance, option) for option in schema['enum']):
        found.append(f'{path}: not one of {schema["enum"]}')
    if isinstance(instance, str):
        if 'minLength' in schema and len(instance) < schema['minLength']:
            found.append(f'{path}: shorter than {schema["minLength"]} code points')
        if 'maxLength' in schema and len(instance) > schema['maxLength']:
            found.append(f'{path}: longer than {schema["maxLength"]} code points')
        if 'pattern' in schema and not compile_pattern(schema['pattern']).search(instance):
            found.append(f'{path}: does not match {schema["pattern"]}')
    if _is_number(instance):
        if 'minimum' in schema and instance < schema['minimum']:
            found.append(f'{path}: below {schema["minimum"]}')
        if 'maximum' in schema and instance > schema['maximum']:
            found.append(f'{path}: above {schema["maximum"]}')
    if isinstance(instance, dict):
        for name in schema.get('required', []):
            if name not in instance:
                found.append(f'{path}: missing {name}')
        properties = schema.get('properties', {})
        for name, value in instance.items():
            if name in properties:
                found.extend(errors(value, properties[name], root, f'{path}.{name}'))
            elif schema.get('additionalProperties') is False:
                found.append(f'{path}: unexpected property {name}')
    if isinstance(instance, list):
        if 'minItems' in schema and len(instance) < schema['minItems']:
            found.append(f'{path}: fewer than {schema["minItems"]} items')
        if 'maxItems' in schema and len(instance) > schema['maxItems']:
            found.append(f'{path}: more than {schema["maxItems"]} items')
        if 'items' in schema:
            for number, value in enumerate(instance):
                found.extend(errors(value, schema['items'], root, f'{path}[{number}]'))
    if 'oneOf' in schema:
        matching = sum(1 for option in schema['oneOf'] if not errors(instance, option, root, path))
        if matching != 1:
            found.append(f'{path}: matches {matching} of the oneOf alternatives, not exactly one')
    return found


def is_valid(instance, schema, root):
    return not errors(instance, schema, root)
