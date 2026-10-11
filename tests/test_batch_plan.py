"""Lossless batching on fictional questions; no inference or token estimates."""
import copy
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/scripts'))
from batch_plan import plan_batches

def fixture(count=7):
    return {'sources':[{'id':'exam','sha256':'0'*64,'page_count':10,'name':'fictional.pdf','role':'exam'}],
        'assets':[], 'questions':[{'id':f'q{i}','source_id':'exam','number':str(i),
          'regions':[{'page':i,'bbox':[0,0,100,100]}], 'stem':[{'type':'text','text':'Fictional small question'}],
          'options':[{'label':'A','blocks':[{'type':'text','text':'1'}]}, {'label':'B','blocks':[{'type':'text','text':'2'}]}],
          'explanation':{'blocks':[]}} for i in range(1,count+1)]}

class BatchPlanTests(unittest.TestCase):
    def test_deterministic_order_and_complete_coverage(self):
        data=fixture();before=copy.deepcopy(data)
        plan=plan_batches(data)
        self.assertEqual(plan,plan_batches(data))
        self.assertEqual([b['question_ids'] for b in plan['batches']],[['q1','q2','q3','q4','q5'],['q6','q7']])
        self.assertEqual([qid for b in plan['batches'] for qid in b['question_ids']],[q['id'] for q in data['questions']])
        self.assertEqual(data,before)
        self.assertIsNone(plan['token_estimate'])
    def test_oversized_question_retains_full_context(self):
        data=fixture(2);data['questions'][0]['stem'][0]['text']='x'*10000
        plan=plan_batches(data,max_characters=500)
        self.assertEqual(plan['batches'][0]['question_ids'],['q1'])
        self.assertTrue(plan['batches'][0]['oversized'])
        self.assertEqual(plan['question_index'][0]['pages'],[{'source_id':'exam','page':1}])
    def test_tables_use_smaller_batches(self):
        data=fixture(5)
        for q in data['questions']:q['stem'].append({'type':'table','rows':[[[{'type':'text','text':'Fictional table'}]]]})
        plan=plan_batches(data)
        self.assertTrue(all(len(b['question_ids'])<=2 for b in plan['batches']))
    def test_images_keep_source_page_and_context_binding(self):
        data=fixture(1)
        data['sources'].append({'id':'solution','sha256':'1'*64,'page_count':2,'name':'fictional-solution.pdf','role':'solution'})
        data['assets']=[{'id':'plot','source_id':'solution','page':2,'bbox':[0,0,20,20],'sha256':'2'*64,'path':'assets/plot.png'}]
        data['questions'][0]['explanation']['blocks']=[{'type':'image','asset_id':'plot','alt':'Fictional explanation plot'}]
        plan=plan_batches(data)
        self.assertEqual(plan['batches'][0]['source_ids'],['exam','solution'])
        self.assertIn({'source_id':'solution','page':2},plan['batches'][0]['pages'])
        before=plan['batches'][0]['context_hashes']['q1']
        data['assets'][0]['sha256']='3'*64
        self.assertNotEqual(before,plan_batches(data)['batches'][0]['context_hashes']['q1'])
    def test_invalid_limits_or_identity_are_rejected(self):
        for value in (0,11,True):
            with self.assertRaises(ValueError):plan_batches(fixture(),max_questions=value)
        with self.assertRaises(ValueError):plan_batches(fixture(),max_characters=0)
        data=fixture(2);data['questions'][1]['id']='q1'
        with self.assertRaises(ValueError):plan_batches(data)
    def test_missing_regions_preserve_full_source(self):
        data=fixture(1);data['questions'][0]['regions']=[]
        plan=plan_batches(data)
        self.assertEqual(len(plan['batches'][0]['pages']),10)
        self.assertEqual(plan['question_index'][0]['source_context_scope'],'full_source_fallback')
    def test_page_index_preserves_shared_pages(self):
        data=fixture(2);data['questions'][1]['regions'][0]['page']=1
        self.assertEqual(plan_batches(data)['page_index'],[{'source_id':'exam','page':1,'question_ids':['q1','q2']}])

if __name__=='__main__':unittest.main()
