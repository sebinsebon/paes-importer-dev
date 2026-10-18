"""Geometry/source regressions; synthetic acceptance never proves real fidelity."""
import copy
import hashlib
import sys
import tempfile
import unittest

from support import RUNTIME_ROOT, WORK_ROOT
sys.path.insert(0, str(RUNTIME_ROOT / 'shared/scripts'))
from pathlib import Path
from evidence import (cover_regions, validate_source_fields, validate_mapping,
                      validate_citations, field_paths, citation_requirements)
from content_inventory import validate_inventory_record, validate_inventory, with_solution_inventory


def region(page, box):
    return {'page': page, 'bbox': box}


class FidelityRepairsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.root = Path(self.temp.name)
        self.catalog = {'pages': [{'source_id': sid, 'page': page, 'width': 200, 'height': 300}
                                  for sid in ('exam', 'solution') for page in (1, 2)]}
        self.record = {'id': 'q', 'source_id': 'exam', 'page': 1, 'option_labels': ['A', 'B'],
                       'regions': [region(1, [0, 0, 200, 300])],
                       'source_fields': {'stem': [region(1, [10, 10, 180, 70])],
                                         'options/A': [region(1, [10, 90, 90, 190])],
                                         'options/B': [region(1, [110, 90, 190, 190])]},
                       'content_inventory': []}
        self.q = {'id': 'q', 'source_id': 'exam', 'regions': copy.deepcopy(self.record['regions']),
                  'stem': [{'type': 'text', 'text': 'Enunciado ficticio'}],
                  'options': [{'label': 'A', 'blocks': [{'type': 'image', 'asset_id': 'a'}]},
                              {'label': 'B', 'blocks': [{'type': 'image', 'asset_id': 'b'}]}],
                  'explanation': {'blocks': []}, 'issues': []}
        self.candidate = {'questions': [self.q], 'assets': [], 'evidence': []}

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, name, box, page=1, source='exam', evidence=False):
        data = ('Synthetic resource: ' + name).encode('utf-8')
        (self.root / (name + '.png')).write_bytes(data)
        asset = {'id': name, 'path': name + '.png', 'sha256': hashlib.sha256(data).hexdigest(),
                 'source_id': source, 'page': page, 'bbox': box}
        self.candidate['evidence' if evidence else 'assets'].append(asset)
        return asset

    def check(self, dimension, refs, status='pass'):
        return {'status': status, 'field_paths': field_paths(self.q)[dimension],
                'evidence': [{'id': asset['id'], 'sha256': asset['sha256'], 'fields': fields,
                              'observation': 'Synthetic localized observation'} for asset, fields in refs]}

    def test_source_fields_validate_exact_fields_and_bounds(self):
        validate_source_fields(self.record, self.catalog)
        for change in ({'options/C': [region(1, [1, 1, 2, 2])]}, {'stem': []}):
            record = copy.deepcopy(self.record)
            record['source_fields'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_source_fields(record, self.catalog)

    def test_source_fields_must_observe_continuation_page(self):
        self.record['regions'].append(region(2, [0, 0, 200, 100]))
        with self.assertRaisesRegex(ValueError, 'every frozen question page'):
            validate_source_fields(self.record, self.catalog)

    def test_resolved_mapping_cannot_omit_frozen_page_even_legacy(self):
        self.record['regions'].append(region(2, [0, 0, 200, 100]))
        for strict in (True, False):
            record = copy.deepcopy(self.record)
            if not strict:
                record.pop('source_fields')
            with self.subTest(strict=strict), self.assertRaisesRegex(ValueError, 'omits frozen source page'):
                validate_mapping(self.candidate, {'expected_questions': [record]})

    def test_mapping_can_remove_empty_margins_but_not_essential_content(self):
        self.q['regions'] = [region(1, [10, 10, 190, 190])]
        validate_mapping(self.candidate, {'expected_questions': [self.record]})
        self.q['regions'] = [region(1, [20, 20, 190, 190])]
        with self.assertRaisesRegex(ValueError, 'essential source field'):
            validate_mapping(self.candidate, {'expected_questions': [self.record]})

    def test_empty_regions_only_allowed_for_explicit_source_placeholder(self):
        self.q['regions'] = []
        with self.assertRaisesRegex(ValueError, 'resolved question omits'):
            validate_mapping(self.candidate, {'expected_questions': [self.record]})
        self.q['stem'] = [{'type': 'unresolved', 'reason': 'Fictitious unreadable source'}]
        validate_mapping(self.candidate, {'expected_questions': [self.record]})

    def test_union_covers_split_region_but_preserves_holes(self):
        required = [region(1, [10, 10, 100, 100])]
        halves = [region(1, [10, 10, 55, 100]), region(1, [55, 10, 100, 100])]
        self.assertTrue(cover_regions(required, halves))
        halves[1]['bbox'][0] = 56
        self.assertFalse(cover_regions(required, halves))

    def test_tiny_citation_cannot_approve_whole_field(self):
        tiny = self.asset('tiny', [10, 10, 11, 11], evidence=True)
        check = self.check('stem', [(tiny, ['stem'])])
        with self.assertRaisesRegex(ValueError, 'every essential'):
            validate_citations(self.q, 'stem', check, self.candidate, self.root, self.record)
        check['status'] = 'unresolved'
        validate_citations(self.q, 'stem', check, self.candidate, self.root, self.record)

    def test_split_citations_cover_union_for_same_field(self):
        left = self.asset('left', [10, 10, 95, 70], evidence=True)
        right = self.asset('right', [95, 10, 180, 70], evidence=True)
        validate_citations(self.q, 'stem', self.check('stem', [(left, ['stem']), (right, ['stem'])]),
                           self.candidate, self.root, self.record)

    def test_assets_math_uses_containing_option(self):
        a = self.asset('a', [10, 90, 90, 190])
        b = self.asset('b', [110, 90, 190, 190])
        paths = field_paths(self.q)['assets_math']
        check = self.check('assets_math', [(a, [paths[0]]), (b, [paths[1]])])
        validate_citations(self.q, 'assets_math', check, self.candidate, self.root, self.record)
        self.assertEqual(citation_requirements(self.q, 'assets_math', paths[1], self.record),
                         ('exam', self.record['source_fields']['options/B']))

    def test_solution_citations_need_every_frozen_page_and_own_source(self):
        one = self.asset('s1', [0, 0, 200, 300], source='solution', evidence=True)
        key = {'source_id': 'solution', 'page': 1, 'pages': [1, 2]}
        with self.assertRaisesRegex(ValueError, 'every essential'):
            validate_citations(self.q, 'answer', self.check('answer', [(one, ['answer'])]),
                               self.candidate, self.root, self.record, key)
        two = self.asset('s2', [0, 0, 200, 300], page=2, source='solution', evidence=True)
        validate_citations(self.q, 'answer', self.check('answer', [(one, ['answer']), (two, ['answer'])]),
                           self.candidate, self.root, self.record, key)

    def test_explanation_pages_are_not_replaced_by_answer_key_pages(self):
        key = {'source_id': 'solution', 'page': 1, 'pages': [1]}
        provenance = {'source_id': 'solution', 'page': 1, 'pages': [1, 2]}
        _, regions = citation_requirements(self.q, 'explanation', 'explanation', self.record, key, provenance)
        self.assertEqual([r['page'] for r in regions], [1, 2])

    def add_images_inventory(self):
        self.record['content_inventory'] = [{'field': 'options/' + label, 'type': 'image', 'count': 1,
                                             'regions': copy.deepcopy(self.record['source_fields']['options/' + label])}
                                            for label in ('A', 'B')]

    def test_same_page_full_image_cannot_satisfy_distinct_alternatives(self):
        self.add_images_inventory()
        self.asset('page', [0, 0, 200, 300])
        for option in self.q['options']:
            option['blocks'][0]['asset_id'] = 'page'
        with self.assertRaisesRegex(ValueError, 'CROP_OUTSIDE_FIELD_OR_NEIGHBOR'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_precise_alternative_crops_pass(self):
        self.add_images_inventory()
        self.asset('a', [10, 90, 90, 190])
        self.asset('b', [110, 90, 190, 190])
        validate_inventory_record(self.record, self.catalog)
        validate_inventory(self.q, self.record, self.candidate)

    def test_same_observed_shared_diagram_can_reuse_resource(self):
        self.record['source_fields']['options/B'] = copy.deepcopy(self.record['source_fields']['options/A'])
        self.add_images_inventory()
        self.asset('shared', [10, 90, 90, 190])
        for option in self.q['options']:
            option['blocks'][0]['asset_id'] = 'shared'
        validate_inventory(self.q, self.record, self.candidate)

    def test_shared_diagram_allowed_when_field_boxes_also_contain_text(self):
        self.record['source_fields']['options/A'] = [region(1, [0, 80, 200, 180])]
        self.record['source_fields']['options/B'] = [region(1, [0, 80, 200, 220])]
        self.record['content_inventory'] = [{'field': 'options/' + label, 'type': 'image', 'count': 1,
                                            'regions': [region(1, [50, 100, 100, 150])]}
                                           for label in ('A', 'B')]
        self.asset('shared', [50, 100, 100, 150])
        for option in self.q['options']:
            option['blocks'][0]['asset_id'] = 'shared'
        validate_inventory(self.q, self.record, self.candidate)
        self.candidate['assets'][0]['bbox'] = [0, 80, 200, 180]
        with self.assertRaisesRegex(ValueError, 'CROP_OUTSIDE_FIELD_OR_NEIGHBOR'):
            validate_inventory(self.q, self.record, self.candidate)

    def math_inventory(self):
        self.record['content_inventory'] = [{'field': 'stem', 'type': 'math', 'count': 1, 'symbols': ['m'],
                                             'regions': copy.deepcopy(self.record['source_fields']['stem'])}]
        self.q['stem'] = [{'type': 'text', 'text': 'Sea m una variable'}, {'type': 'math', 'latex': '2m'}]

    def test_bare_variable_rejected_even_if_formula_contains_it(self):
        self.math_inventory()
        with self.assertRaisesRegex(ValueError, 'BARE_MATH_VARIABLE m'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_regular_word_containing_symbol_is_not_a_bare_variable(self):
        self.math_inventory()
        self.q['stem'][0]['text'] = 'Consideremos ambos términos'
        validate_inventory(self.q, self.record, self.candidate)

    def test_text_exception_requires_localized_source_observation(self):
        self.math_inventory()
        item = self.record['content_inventory'][0]
        item['text_exceptions'] = [{'symbol': 'm', 'reason': 'Unidad literal observada en esta región',
                                    'regions': copy.deepcopy(item['regions'])}]
        validate_inventory_record(self.record, self.catalog)
        validate_inventory(self.q, self.record, self.candidate)
        item['text_exceptions'][0]['regions'] = [region(1, [10, 10, 11, 11])]
        with self.assertRaisesRegex(ValueError, 'text_exceptions regions'):
            validate_inventory_record(self.record, self.catalog)

    def table_inventory(self):
        self.record['content_inventory'] = [{'field': 'stem', 'type': 'table', 'count': 1,
                                             'shape': {'rows': 2, 'columns': 2},
                                             'regions': copy.deepcopy(self.record['source_fields']['stem'])}]
        self.q['stem'] = [{'type': 'table', 'rows': [[[{'type': 'text', 'text': 'Dato'}]]]}]

    def test_minimal_placeholder_does_not_satisfy_observed_table_shape(self):
        self.table_inventory()
        with self.assertRaisesRegex(ValueError, 'TABLE_SHAPE_MISMATCH'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_new_source_field_maps_require_editable_table_shape(self):
        self.table_inventory()
        self.record['content_inventory'][0].pop('shape')
        with self.assertRaisesRegex(ValueError, 'require shape/shapes'):
            validate_inventory_record(self.record, self.catalog)
        legacy = copy.deepcopy(self.record)
        legacy.pop('source_fields')
        validate_inventory_record(legacy, self.catalog)

    def test_editable_table_dimensions_and_headers_pass(self):
        self.table_inventory()
        self.q['stem'][0]['rows'] = [[[{'type': 'text', 'text': str(n)}] for n in row] for row in ((1, 2), (3, 4))]
        self.record['content_inventory'][0]['shape']['headers'] = ['1', '2']
        validate_inventory_record(self.record, self.catalog)
        validate_inventory(self.q, self.record, self.candidate)
        self.q['stem'][0]['rows'][0][0][0]['text'] = 'Otro'
        with self.assertRaisesRegex(ValueError, 'TABLE_HEADERS_MISMATCH'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_table_image_fallback_needs_issue_and_preserved_regions(self):
        self.table_inventory()
        item = self.record['content_inventory'][0]
        item.update(representation='image-with-issue', limitation={'reason': 'Celdas combinadas',
                                                                 'regions': copy.deepcopy(item['regions'])})
        self.q['stem'] = [{'type': 'image', 'asset_id': 'table'}]
        self.asset('table', [10, 10, 180, 70])
        validate_inventory_record(self.record, self.catalog)
        with self.assertRaisesRegex(ValueError, 'TABLE_STRUCTURE_IMAGE_FALLBACK'):
            validate_inventory(self.q, self.record, self.candidate)
        self.q['issues'] = ['TABLE_STRUCTURE_IMAGE_FALLBACK']
        validate_inventory(self.q, self.record, self.candidate)

    def test_math_cannot_use_table_image_fallback(self):
        self.math_inventory()
        self.record['content_inventory'][0]['representation'] = 'image-with-issue'
        with self.assertRaisesRegex(ValueError, 'math must remain editable'):
            validate_inventory_record(self.record, self.catalog)

    def test_explanation_inventory_uses_solution_source(self):
        self.record['content_inventory'] = [{'field': 'explanation', 'source_id': 'solution', 'type': 'image',
                                             'count': 1, 'regions': [region(2, [10, 10, 180, 70])]}]
        self.q['explanation']['blocks'] = [{'type': 'image', 'asset_id': 'solution-plot'}]
        asset = self.asset('solution-plot', [10, 10, 180, 70], page=2, source='solution')
        validate_inventory_record(self.record, self.catalog)
        validate_inventory(self.q, self.record, self.candidate)
        asset['source_id'] = 'exam'
        with self.assertRaisesRegex(ValueError, 'CROP_EXCLUDES_SOURCE_REGION'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_solution_inventory_merge_preserves_source_and_input_records(self):
        key = {'source_id': 'solution', 'content_inventory': [{'field': 'explanation', 'type': 'image',
               'count': 1, 'regions': [region(2, [10, 10, 180, 70])]}]}
        combined = with_solution_inventory(self.record, key)
        validate_inventory_record(combined, self.catalog)
        self.assertEqual(combined['content_inventory'][0]['source_id'], 'solution')
        combined['content_inventory'][0]['regions'][0]['bbox'][0] = 20
        self.assertEqual(key['content_inventory'][0]['regions'][0]['bbox'][0], 10)
        self.assertEqual(self.record['content_inventory'], [])
        key['content_inventory'][0]['source_id'] = 'exam'
        with self.assertRaisesRegex(ValueError, 'frozen source_id'):
            with_solution_inventory(self.record, key)

    def test_inventory_region_cannot_change_question_source(self):
        self.record['content_inventory'] = [{'field': 'stem', 'source_id': 'solution', 'type': 'image',
                                             'count': 1, 'regions': [region(1, [10, 10, 180, 70])]}]
        with self.assertRaisesRegex(ValueError, 'question source'):
            validate_inventory_record(self.record, self.catalog)


if __name__ == '__main__':
    unittest.main()
