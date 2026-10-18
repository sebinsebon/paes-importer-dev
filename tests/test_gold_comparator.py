import copy
import sys
import unittest
from pathlib import Path
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0,str(ROOT/'scripts'))
from compare_gold import compare

def fixture():
    return {'format':'paessed-benchmark','schema_version':'0.2.0','pipeline':'demo',
        'run':{'id':'demo','cli':'synthetic','model':'synthetic','created_at':'2026-01-01'},
        'exam':{'id':'exam','title':'Synthetic','scope':'demo','expected_questions':[{'id':'q1','source_id':'exam','number':'1'}]},
        'evidence':[], 'sources':[{'id':'exam','name':'synthetic.pdf','sha256':'a'*64,'page_count':1,'role':'exam'}], 'assets':[], 'questions':[
        {'id':'q1','source_id':'exam','number':'1','regions':[{'page':1,'bbox':[0,0,100,100]}],'fidelity':{'status':'pending','review_ref':None},'issues':[],'stem':[{'type':'text','text':'Fictional sum '},{'type':'math','latex':'2+2','display':False},
            {'type':'table','rows':[[[{'type':'text','text':'4'}]]]}],
         'options':[{'label':'A','blocks':[{'type':'text','text':'3'}]},{'label':'B','blocks':[{'type':'text','text':'4'}]}],
         'answer':{'label':'B','status':'provisional','origin':'model','source_ref':None},'explanation':{'status':'provisional','blocks':[{'type':'text','text':'The fictional sum is four.'}]},
         'curriculum':{'eje':'Números','subeje':'Conjunto de los números enteros y racionales','en_temario':'si'}}]}

class ComparatorTests(unittest.TestCase):
    def test_identity(self):
        result=compare(fixture(),fixture())
        self.assertEqual(result['critical_difference_questions'],0)
        self.assertTrue(all(v['equal']==1 for v in result['dimensions'].values()))
        self.assertEqual(result['certification'],'not_performed')
    def test_math_option_answer_and_table_changes_localized(self):
        for dimension in ('math','options','answer','tables'):
            data=fixture();q=data['questions'][0]
            if dimension=='math':q['stem'][1]['latex']='2-2'
            elif dimension=='options':q['options'].reverse()
            elif dimension=='answer':q['answer']['label']='A'
            else:q['stem'][2]['rows'][0][0][0]['text']='5'
            result=compare(fixture(),data)
            self.assertEqual(result['dimensions'][dimension]['different'],1)
            self.assertEqual(result['critical_difference_questions'],1)
    def test_explanation_difference_requires_rubric_not_literal_failure(self):
        data=fixture();data['questions'][0]['explanation']['blocks'][0]['text']='Adding two and two yields four.'
        result=compare(fixture(),data)
        self.assertEqual(result['dimensions']['explanation']['different'],1)
        self.assertEqual(result['critical_difference_questions'],0)
        self.assertEqual(result['questions'][0]['dimensions']['explanation']['semantic_review'],'not_performed')
    def test_missing_and_extra_without_fuzzy_matching(self):
        data=fixture();data['questions'][0].update(id='other',number='2');data['exam']['expected_questions'][0].update(id='other',number='2')
        result=compare(fixture(),data)
        self.assertEqual(result['coverage']['missing'],['q1'])
        self.assertEqual(result['coverage']['extra'],['other'])
        result=compare(fixture(),data,{'q1':'other'})
        self.assertEqual(result['coverage']['compared'],1)
    def test_curriculum_fields_are_independently_counted(self):
        data=fixture();data['questions'][0]['curriculum']['en_temario']='dudoso'
        dimensions=compare(fixture(),data)['dimensions']
        self.assertEqual(dimensions['curriculum_en_temario']['different'],1)
        self.assertEqual(dimensions['curriculum_eje']['equal'],1)
        self.assertEqual(dimensions['curriculum_subeje']['equal'],1)
    def test_curriculum_absent_is_unavailable(self):
        data=fixture();data['questions'][0].pop('curriculum');data['schema_version']='0.1.0'
        self.assertEqual(compare(fixture(),data)['dimensions']['curriculum']['unavailable'],1)
    def test_malformed_equal_documents_are_rejected(self):
        for mutator in (lambda d:d['questions'][0].pop('answer'),lambda d:d['questions'][0]['stem'][0].update(text='   '),lambda d:d.pop('run')):
            data=fixture();mutator(data)
            with self.assertRaises((ValueError,KeyError)):compare(data,copy.deepcopy(data))
    def test_legacy_external_annotation_overlay_after_validation(self):
        gold=fixture();annotations={q['id']:q.pop('curriculum') for q in gold['questions']};gold['schema_version']='0.1.0'
        result=compare(gold,fixture(),gold_taxonomy=annotations)
        self.assertEqual(result['dimensions']['curriculum']['equal'],1)
        self.assertNotIn('curriculum',gold['questions'][0])
    def test_duplicate_identity_and_invalid_map_rejected(self):
        data=fixture();data['questions'].append(copy.deepcopy(data['questions'][0]))
        with self.assertRaises(ValueError):compare(fixture(),data)
        with self.assertRaises(ValueError):compare(fixture(),fixture(),{'q1':'absent'})

if __name__=='__main__':unittest.main()
