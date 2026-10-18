import unittest
import test_importer as fixtures
import importer
from lab import configure_workspace, read, write

class RuntimeUsageTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ImporterTests();self.fixture.setUp();self.fixture.start();self.fixture.route()
    def tearDown(self):self.fixture.tearDown()
    def test_receipts_idempotent_and_missing_unknown(self):
        folder=self.fixture.folder
        configure_workspace(folder.parent.parent)
        receipt={'event_id':'provider-call-1','usage_source':'provider synthetic fixture',
                 'input_tokens':10,'output_tokens':5,'cost':.01,'currency':'USD','duration_seconds':1.0}
        request=folder/'receipt.json';write(request,{'run_id':read(folder/'run.json')['id'],'events':[receipt]})
        importer.record_usage(folder,request);importer.record_usage(folder,request)
        self.assertEqual(importer.final_usage(folder)['total_tokens'],15)
        self.assertEqual(len(read(folder/'usage-events.json')),1)
        receipt['output_tokens']=None;receipt['event_id']='provider-call-2'
        write(request,{'run_id':read(folder/'run.json')['id'],'events':[receipt]})
        importer.record_usage(folder,request)
        self.assertIsNone(importer.final_usage(folder)['output_tokens'])
    def test_review_with_complete_key_and_observed_labels_required(self):
        from policy import select_mode
        decision=select_mode('cli',['q1','q2'],['q1','q2'],True,None,['q1'])
        self.assertEqual(decision['independent_question_ids'],['q1'])
        self.assertEqual(decision['solve_question_ids'],[])

    def test_independent_publication_keeps_unknown_scopes_separate(self):
        folder=self.fixture.folder
        configure_workspace(folder.parent.parent)
        write(folder/'usage-events.json',[{'event_id':'production','input_tokens':10,'output_tokens':5,
             'cost':0.1,'currency':'USD','duration_seconds':2}])
        write(folder.parent/'verification/metrics.json',{'verification_usage':{
            'input_tokens':4,'output_tokens':None,'total_tokens':None,'cost_usd':0.2,'duration_seconds':3}})
        scopes=importer.publication_usage(folder,True)
        self.assertEqual(scopes['production']['total_tokens'],15)
        self.assertEqual(scopes['production']['scope'],'production_only')
        self.assertEqual(scopes['combined']['input_tokens'],14)
        self.assertAlmostEqual(scopes['combined']['cost_usd'],0.3)
        self.assertIsNone(scopes['combined']['total_tokens'])
        self.assertIsNone(scopes['combined']['output_tokens'])

if __name__ == '__main__':unittest.main()
