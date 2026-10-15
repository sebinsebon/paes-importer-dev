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

if __name__ == '__main__':unittest.main()
