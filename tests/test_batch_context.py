import copy
import unittest
from test_batch_plan import fixture
from batch_plan import plan_batches


class BatchContextTests(unittest.TestCase):
    def data(self):
        candidate=fixture(2)
        candidate['run']={'id':'synthetic'}
        candidate['sources'].append({'id':'guide','sha256':'1'*64,'page_count':1,'name':'guide.pdf','role':'solution'})
        mapping={'expected_questions':[{**{k:q[k] for k in ('id','source_id','number')},'regions':q['regions'],
            'option_labels':['A','B'],'content_inventory':[]} for q in candidate['questions']]}
        route={'answer_key':{'entries':[{'question_id':'q1','source_id':'guide','page':1,'label':'B',
            'has_explanation':True,'content_inventory':[{'field':'explanation','type':'table','count':1}]}]}}
        index={'source_hashes':{'exam':'0'*64,'guide':'1'*64},'version':'1.0.0','pages':[
            {'source_id':sid,'page':page,'width':400,'height':400,'rotation':0,
             'glyphs':[{'position':i,'text':c,'bbox':[10+i,10,11+i,20]} for i,c in enumerate(text)],
             'lines':[],'objects':[]} for sid,page,text in [('exam',1,'Source question'),('exam',2,'Second'),('guide',1,'Complete original development')]]}
        return candidate,mapping,route,index

    def test_context_contains_original_solution_template_and_hashes(self):
        candidate,mapping,route,index=self.data(); before=copy.deepcopy(candidate)
        plan=plan_batches(candidate,selection=mapping,route=route,source_index=index,include_context=True)
        context=plan['batches'][0]['contexts'][0]
        self.assertIn('Complete original development',context['native_source'][1]['text'])
        template=context['response_template']
        self.assertEqual(template['explanation_provenance']['q1']['source_id'],'guide')
        self.assertEqual(template['questions'][0]['answer']['label'],'B')
        self.assertEqual(template['run_id'],'synthetic')
        self.assertEqual(candidate,before)
        self.assertFalse(any(p['truncated'] for p in context['native_source']))
        self.assertTrue(all('context' not in item for item in plan['question_index']))

    def test_budget_counts_source_development_before_transcription(self):
        candidate,mapping,route,index=self.data()
        first=plan_batches(candidate,selection=mapping,route=route,source_index=index)
        index['pages'][-1]['glyphs']*=200
        second=plan_batches(candidate,selection=mapping,route=route,source_index=index)
        self.assertGreater(second['question_index'][0]['serialized_characters'],first['question_index'][0]['serialized_characters'])
        self.assertNotEqual(second['question_index'][0]['context_sha256'],first['question_index'][0]['context_sha256'])
        self.assertIsNone(second['token_estimate'])

    def test_solution_regions_inherit_actual_key_source(self):
        candidate,mapping,route,index=self.data()
        route['answer_key']['entries'][0]['content_inventory'][0]['regions']=[{'page':1,'bbox':[10,10,18,20]}]
        result=plan_batches(candidate,selection=mapping,route=route,source_index=index,include_context=True)
        native=result['batches'][0]['contexts'][0]['native_source']
        self.assertEqual(native[0]['text'],'Source question')
        self.assertEqual(native[1]['text'],'Complete')
        self.assertEqual(result['batches'][0]['contexts'][0]['response_template']['explanation_provenance']['q1']['regions'],[])

    def test_authorized_model_provenance_and_declined_pending(self):
        candidate,mapping,route,index=self.data()
        route['pending_question_ids']=['q2']
        result=plan_batches(candidate,selection=mapping,route=route,source_index=index,include_context=True)
        contexts=[c for b in result['batches'] for c in b['contexts']]
        self.assertEqual(contexts[1]['response_template']['explanation_provenance'],{})
        route['pending_question_ids']=[]
        result=plan_batches(candidate,selection=mapping,route=route,source_index=index,include_context=True)
        contexts=[c for b in result['batches'] for c in b['contexts']]
        self.assertEqual(contexts[1]['response_template']['explanation_provenance'],{'q2':{'origin':'model'}})

    def test_repeated_rejections_reduce_only_affected_question_cap(self):
        candidate=fixture(5)
        plan=plan_batches(candidate,failure_counts={'q1':2,'q3':1})
        self.assertEqual(plan['batches'][0]['question_ids'],['q1'])
        self.assertEqual(plan['question_index'][0]['question_limit'],1)
        self.assertEqual(plan['question_index'][2]['question_limit'],2)
        self.assertEqual(plan['question_index'][4]['question_limit'],5)


if __name__ == '__main__': unittest.main()
