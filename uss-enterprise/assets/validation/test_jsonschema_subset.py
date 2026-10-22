"""Unit tests of the strict JSON Schema subset checker used by the Assets contract validator."""
from pathlib import Path
import tempfile
import unittest

import jsonschema_subset as js


def ok(instance, schema, root=None):
    return js.is_valid(instance, schema, root if root is not None else schema)


class TypesAndValues(unittest.TestCase):
    def test_a_boolean_is_never_an_integer_or_a_number(self):
        for kind in ('integer', 'number'):
            self.assertFalse(ok(True, {'type': kind}))
            self.assertFalse(ok(False, {'type': kind}))
        self.assertTrue(ok(True, {'type': 'boolean'}))

    def test_integer_accepts_a_whole_float_and_refuses_a_fraction(self):
        self.assertTrue(ok(2.0, {'type': 'integer'}))
        self.assertFalse(ok(2.5, {'type': 'integer'}))

    def test_enum_and_const_do_not_equate_true_with_one(self):
        self.assertFalse(ok(True, {'enum': [1]}))
        self.assertFalse(ok(1, {'const': True}))
        self.assertTrue(ok('A', {'enum': ['A', 'B']}))
        self.assertFalse(ok('a', {'enum': ['A', 'B']}))

    def test_type_list_allows_null(self):
        schema = {'type': ['string', 'null']}
        self.assertTrue(ok(None, schema))
        self.assertTrue(ok('x', schema))
        self.assertFalse(ok(1, schema))

    def test_length_counts_code_points(self):
        schema = {'type': 'string', 'minLength': 1, 'maxLength': 2}
        self.assertTrue(ok('\U0001F680\U0001F680', schema))
        self.assertFalse(ok('\U0001F680' * 3, schema))
        self.assertFalse(ok('', schema))

    def test_numeric_bounds(self):
        schema = {'type': 'integer', 'minimum': 1, 'maximum': 50}
        self.assertEqual([ok(n, schema) for n in (0, 1, 50, 51)], [False, True, True, False])


class Patterns(unittest.TestCase):
    ID = {'type': 'string', 'pattern': '^[A-Z]{2,5}-[1-9][0-9]*$'}

    def test_dollar_is_the_end_of_the_text_not_before_a_final_newline(self):
        self.assertTrue(ok('SH-17', self.ID))
        self.assertFalse(ok('SH-17\n', self.ID))
        self.assertFalse(ok('SH-17\r\n', self.ID))

    def test_only_ascii_digits_match(self):
        self.assertFalse(ok('SH-１７', self.ID))

    def test_the_pattern_is_anchored_by_the_pattern_itself(self):
        self.assertTrue(ok('xSH-17', {'type': 'string', 'pattern': 'SH-17'}))
        self.assertFalse(ok('xSH-17', self.ID))

    def test_non_portable_patterns_are_refused(self):
        for bad in (r'^\d+$', r'^\w+$', r'^\s$', '^(?=a)a$', '^(?P<n>a)$', 'a.b', r'\p{L}', 'a$b'):
            with self.assertRaises(js.SchemaError, msg=bad):
                js.compile_pattern(bad)

    def test_an_escaped_dollar_is_a_literal(self):
        self.assertTrue(ok('a$', {'type': 'string', 'pattern': r'^a\$$'}))


class Objects(unittest.TestCase):
    SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['a'],
              'properties': {'a': {'type': 'string'}, 'b': {'type': 'integer'}}}

    def test_required_and_unknown_members(self):
        self.assertTrue(ok({'a': 'x'}, self.SCHEMA))
        self.assertFalse(ok({}, self.SCHEMA))
        self.assertFalse(ok({'a': 'x', 'c': 1}, self.SCHEMA))
        self.assertFalse(ok({'a': 'x', 'b': 'no'}, self.SCHEMA))

    def test_arrays_check_every_item_and_the_bounds(self):
        schema = {'type': 'array', 'maxItems': 2, 'items': {'type': 'integer'}}
        self.assertTrue(ok([1, 2], schema))
        self.assertFalse(ok([1, 'x'], schema))
        self.assertFalse(ok([1, 2, 3], schema))

    def test_one_of_needs_exactly_one_match(self):
        schema = {'oneOf': [{'type': 'string'}, {'type': 'null'}]}
        self.assertTrue(ok(None, schema))
        self.assertFalse(ok(1, schema))
        overlapping = {'oneOf': [{'type': 'integer'}, {'type': 'number'}]}
        self.assertFalse(ok(1, overlapping))

    def test_references_resolve_locally(self):
        root = {'components': {'schemas': {'N': {'type': 'integer'}}}}
        self.assertTrue(ok(1, {'$ref': '#/components/schemas/N'}, root))
        self.assertFalse(ok('x', {'$ref': '#/components/schemas/N'}, root))
        with self.assertRaises(js.SchemaError):
            ok(1, {'$ref': '#/components/schemas/Missing'}, root)
        with self.assertRaises(js.SchemaError):
            ok(1, {'$ref': 'other.json#/x'}, root)


class Vocabulary(unittest.TestCase):
    def test_an_unsupported_keyword_is_an_error_not_an_ignored_rule(self):
        for keyword in ({'format': 'date'}, {'allOf': []}, {'uniqueItems': True}, {'multipleOf': 2},
                        {'patternProperties': {}}, {'additionalProperties': True}, {'not': {}}):
            with self.assertRaises(js.SchemaError, msg=str(keyword)):
                js.check_schema(keyword, {})

    def test_a_reference_stands_alone_apart_from_annotations(self):
        root = {'a': {'type': 'string'}}
        js.check_schema({'$ref': '#/a', 'description': 'fine'}, root)
        with self.assertRaises(js.SchemaError):
            js.check_schema({'$ref': '#/a', 'type': 'string'}, root)

    def test_annotations_are_allowed(self):
        js.check_schema({'type': 'string', 'description': 'd', 'default': 'x', 'title': 't', 'examples': ['x']}, {})

    def test_unknown_type_names_are_refused(self):
        for bad in ('str', ['string', 'text'], [], 3):
            with self.assertRaises(js.SchemaError):
                js.check_schema({'type': bad}, {})


class Loading(unittest.TestCase):
    def load(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x.json'
            path.write_bytes(raw)
            return js.load_json(path)

    def test_strict_json(self):
        self.assertEqual(self.load(b'{"a": 1}'), {'a': 1})
        for raw in (b'{"a": 1, "a": 2}', b'{"a": NaN}', b'{"a": Infinity}', b'\xef\xbb\xbf{"a": 1}'):
            with self.assertRaises(ValueError, msg=raw):
                self.load(raw)


if __name__ == '__main__':
    unittest.main()
