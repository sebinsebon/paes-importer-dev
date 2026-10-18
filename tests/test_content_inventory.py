"""Fictional source requirements catch omissions and truncated crops."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shared/scripts'))
from content_inventory import validate_inventory_record, validate_inventory


class ContentInventoryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {'pages':[{'source_id':'exam','page':2,'width':400,'height':600}]}
        self.record = {'source_id':'exam','option_labels':['A','B'], 'content_inventory':[
            {'field':'stem','type':'math','count':1,'symbols':['m','n'],
             'regions':[{'page':2,'bbox':[10,10,250,50]}]},
            {'field':'options/A','type':'image','count':1,
             'regions':[{'page':2,'bbox':[20,80,200,260]}]},
            {'field':'options/B','type':'table','count':1,
             'regions':[{'page':2,'bbox':[20,300,200,500]}]}]}
        self.q = {'id':'fictional','source_id':'exam',
                  'stem':[{'type':'text','text':'Si '},{'type':'math','latex':r'\frac{m}{n}','display':False}],
                  'options':[{'label':'A','blocks':[{'type':'image','asset_id':'plot'}]},
                             {'label':'B','blocks':[{'type':'table','rows':[[[{'type':'text','text':'Value'}]]]}]}]}
        self.candidate = {'assets':[{'id':'plot','source_id':'exam','page':2,'bbox':[15,75,205,265]}]}

    def test_structures_and_variables_preserved(self):
        validate_inventory_record(self.record, self.catalog)
        validate_inventory(self.q, self.record, self.candidate)

    def test_omitted_figure_table_or_math_rejected(self):
        for field in ('stem','A','B'):
            q = copy.deepcopy(self.q)
            if field == 'stem': q['stem'] = [{'type':'text','text':'Si m y n son enteros'}]
            else: next(o for o in q['options'] if o['label']==field)['blocks'] = [{'type':'text','text':'Flattened content'}]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'SOURCE_CONTENT_OMITTED'):
                validate_inventory(q, self.record, self.candidate)

    def test_variable_in_prose_does_not_replace_math(self):
        self.q['stem'] = [{'type':'text','text':'m y n'},{'type':'math','latex':'2+2','display':False}]
        with self.assertRaisesRegex(ValueError,'variable m'):
            validate_inventory(self.q, self.record, self.candidate)

    def test_correct_math_can_split_into_inline_blocks(self):
        self.q['stem'] = [{'type':'math','latex':s,'display':False} for s in ('m','n')]
        validate_inventory(self.q, self.record, self.candidate)

    def test_implicit_multiplication_preserves_variables(self):
        self.q['stem'] = [{'type':'math','latex':'2mn','display':False}]
        validate_inventory(self.q, self.record, self.candidate)

    def test_command_names_and_text_do_not_supply_variables(self):
        for latex in (r'\min(1,2)', r'\text{m y n}', r'\mathrm{mn}'):
            self.q['stem'] = [{'type':'math','latex':latex,'display':False}]
            with self.subTest(latex=latex), self.assertRaisesRegex(ValueError,'variable m'):
                validate_inventory(self.q, self.record, self.candidate)

    def test_cut_label_wrong_page_and_wrong_source_rejected(self):
        for change in ({'bbox':[25,85,200,260]}, {'page':1}, {'source_id':'solution'}):
            candidate = copy.deepcopy(self.candidate)
            candidate['assets'][0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError,'CROP_EXCLUDES_SOURCE_REGION'):
                validate_inventory(self.q, self.record, candidate)

    def test_empty_inventory_explicit_but_missing_rejected(self):
        validate_inventory_record({**self.record,'content_inventory':[]}, self.catalog)
        with self.assertRaisesRegex(ValueError,'explicitly'):
            validate_inventory_record({'source_id':'exam'}, self.catalog)

    def test_explicit_unresolved_preserves_partial_representation(self):
        self.q['options'][0]['blocks'] = [{'type':'unresolved','reason':'Fictional figure unreadable'}]
        validate_inventory(self.q, self.record, self.candidate)

    def test_invalid_source_inventory_rejected(self):
        for change in ({'field':'options/C'}, {'type':'text'}, {'count':True}, {'symbols':['word']},
                       {'regions':[{'page':2,'bbox':[0,0,500,600]}]}):
            record = copy.deepcopy(self.record)
            record['content_inventory'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_inventory_record(record, self.catalog)


if __name__ == '__main__': unittest.main()
