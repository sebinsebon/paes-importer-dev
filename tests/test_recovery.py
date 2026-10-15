"""Granular retries and crash recovery with fictional questions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/scripts'))
import pipeline
import checkpoints
from lab import configure_workspace,read,write

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.folder=Path(self.temp.name)
        configure_workspace(self.folder)
        expected=[{'id':'q'+str(i),'source_id':'source','number':str(i)} for i in (1,2)]
        self.data={'format':'paessed-benchmark','schema_version':'0.2.0','pipeline':'demo',
          'run':{'id':'synthetic','cli':'synthetic','model':'synthetic','created_at':'2026-01-01'},
          'exam':{'id':'exam','title':'Synthetic','scope':'demo','expected_questions':expected},
          'sources':[{'id':'source','name':'fictional.pdf','sha256':'a'*64,'role':'exam','page_count':2}],
          'questions':[pipeline.empty_question(q) for q in expected],'assets':[],'evidence':[]}
        write(self.folder/'candidate.json',self.data)
    def tearDown(self):self.temp.cleanup()
    def question(self,index):
        q=copy.deepcopy(self.data['questions'][index]);q['regions']=[{'page':index+1,'bbox':[0,0,50,50]}]
        q['stem']=[{'type':'text','text':'Synthetic arithmetic'}]
        q['options']=[{'label':'A','blocks':[{'type':'text','text':'1'}]},{'label':'B','blocks':[{'type':'text','text':'2'}]}]
        q['curriculum']={'eje':'Números','subeje':'Conjunto de los números enteros y racionales','en_temario':'si'};q['issues']=[]
        return q
    def ingest(self,questions):
        response={'run_id':'synthetic','questions':questions,'curriculum_provenance':{q['id']:{'reason':'Fictional integer arithmetic','evidence':[{'source_id':'source','page':int(q['number']),'observation':'Synthetic addition'}]} for q in questions}}
        write(self.folder/'response.json',response)
        with patch.object(pipeline,'_verify_resume',return_value={}):
            return pipeline.ingest(self.folder,self.folder/'response.json')
    def test_partial_rejection_and_identical_retry(self):
        good=self.question(0);bad=self.question(1);bad['options'][1]['label']='A'
        result=self.ingest([good,bad]);self.assertEqual(result['accepted'],['q1']);self.assertEqual(result['rejected'][0]['question_id'],'q2')
        before=(self.folder/'candidate.json').read_bytes();archives=list((self.folder/'reports/ai').iterdir())
        retry=self.ingest([good]);self.assertEqual(retry['unchanged'],['q1']);self.assertEqual(retry['questions_updated'],0)
        self.assertEqual(before,(self.folder/'candidate.json').read_bytes());self.assertEqual(archives,list((self.folder/'reports/ai').iterdir()))
        result=self.ingest([self.question(1)]);self.assertEqual(result['accepted'],['q2'])
    def test_content_change_invalidates_confirmed_states(self):
        q=self.question(0)
        q['answer']={'label':'B','status':'provisional','origin':'model','source_ref':None}
        q['explanation']={'blocks':[{'type':'math','latex':'1+1=2','display':False}],'status':'provisional'}
        self.ingest([q])
        candidate=read(self.folder/'candidate.json');prior=candidate['questions'][0]
        prior['fidelity']={'status':'reviewed','review_ref':'synthetic-review'}
        prior['answer'].update(status='verified',source_ref='synthetic-answer-review')
        prior['explanation']['status']='verified';write(self.folder/'candidate.json',candidate)
        q['stem']=[{'type':'text','text':'Changed fictional arithmetic'}]
        result=self.ingest([q]);self.assertEqual(result['accepted'],['q1'])
        changed=read(self.folder/'candidate.json')['questions'][0]
        self.assertEqual(changed['fidelity']['status'],'pending')
        self.assertEqual(changed['answer']['status'],'provisional')
        self.assertEqual(changed['explanation']['status'],'provisional')
    def test_state_lock_reentrant_and_other_thread_excluded(self):
        import concurrent.futures
        with checkpoints.state_lock(self.folder):
            with checkpoints.state_lock(self.folder): pass
            def acquire():
                configure_workspace(self.folder)
                with checkpoints.state_lock(self.folder): return True
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaisesRegex(ValueError,'being updated'): pool.submit(acquire).result()

    def test_zero_accepted_and_duplicate_batch_do_not_change(self):
        bad=self.question(0);bad['stem']=[]
        before=(self.folder/'candidate.json').read_bytes()
        with self.assertRaises(ValueError):self.ingest([bad])
        with self.assertRaises(ValueError):self.ingest([self.question(0),self.question(0)])
        self.assertEqual(before,(self.folder/'candidate.json').read_bytes())
    def test_commit_exception_rolls_back_all_files(self):
        before=(self.folder/'candidate.json').read_bytes();original=checkpoints._atomic_bytes
        def failing(path,payload):
            if Path(path).name=='candidate.json':raise OSError('Synthetic replace failure')
            return original(path,payload)
        # Recover also writes candidate, so inject once at the commit point.
        failed=[False]
        def once(path,payload):
            if Path(path).name=='candidate.json' and not failed[0]:failed[0]=True;raise OSError('Synthetic replace failure')
            return original(path,payload)
        with patch.object(checkpoints,'_atomic_bytes',side_effect=once):
            with self.assertRaises(OSError):self.ingest([self.question(0)])
        self.assertEqual(before,(self.folder/'candidate.json').read_bytes())
        self.assertFalse((self.folder/'curriculum-ledger.json').exists());self.assertFalse((self.folder/'ingest-checkpoints.json').exists())
    def test_crash_before_and_after_commit_recovers_consistently(self):
        for after in (False,True):
            before=(self.folder/'candidate.json').read_bytes();new=copy.deepcopy(read(self.folder/'candidate.json'));new['run']['test_marker']=str(after)
            new_bytes=checkpoints.json_bytes(new)
            original=checkpoints._atomic_bytes
            def crash(path,payload):
                if Path(path).name=='candidate.json':
                    if after:original(path,payload)
                    raise SystemExit('Synthetic process interruption')
                return original(path,payload)
            with patch.object(checkpoints,'_atomic_bytes',side_effect=crash):
                with self.assertRaises(SystemExit):checkpoints.commit(self.folder,{'candidate.json':new_bytes,'ingest-checkpoints.json':b'{"done":true}'},before)
            result=checkpoints.recover(self.folder)
            self.assertEqual(result['action'],'committed' if after else 'rolled_back')
            self.assertEqual((self.folder/'candidate.json').read_bytes(),new_bytes if after else before)
            self.assertEqual((self.folder/'ingest-checkpoints.json').exists(),after)

if __name__=='__main__':unittest.main()
