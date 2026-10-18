"""CLI route, pre-transcription context and publication receipts; synthetic only."""
import argparse
import copy
import json
import subprocess
import sys
import unittest
from support import RUNTIME_ROOT, DEV_ROOT
import test_importer as fixtures
import importer as app
import verify
from batch_plan import plan_batches
from lab import configure_workspace, read, write


class ExecutionRepairs(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ImporterTests();self.fixture.setUp()

    def tearDown(self): self.fixture.tearDown()

    def test_actual_cli_review_all_with_complete_key_is_frozen(self):
        folder=self.fixture.start()
        key=self.fixture.fixture_file('key.json',self.fixture.key())
        result=subprocess.run([sys.executable,'-B',str(RUNTIME_ROOT/'scripts/importer.py'),
            'route','--run',str(folder),'--answer-key',str(key),'--subagents','--review-all'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        decision=json.loads(result.stdout)
        self.assertEqual(decision['independent_question_ids'],['q1','q2'])
        self.assertEqual(decision['solve_question_ids'],[])
        self.assertEqual(read(folder/'route.json')['review_mode'],'independent')

    def test_cli_rejects_conflicting_review_flags(self):
        result=subprocess.run([sys.executable,'-B',str(RUNTIME_ROOT/'scripts/importer.py'),
            'route','--run','unused','--review-all','--review-question','q1'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('not allowed',result.stderr)

    def test_initial_plan_uses_observed_pages_and_solution_context(self):
        folder=self.fixture.start();self.fixture.route(('q1','q2'))
        candidate=read(folder/'candidate.json')
        self.assertFalse(candidate['questions'][0]['regions'])
        plan=plan_batches(candidate,selection=read(folder/'selection.json'),route=read(folder/'route.json'))
        first=plan['question_index'][0]
        self.assertEqual(first['source_context_scope'],'frozen_source_map')
        self.assertEqual(first['pages'],[{'source_id':'exam','page':1},{'source_id':'solution','page':1}])
        self.assertEqual(first['question_limit'],2)  # observed table plus two source pages
        self.assertIn({'source_id':'exam','page':2},plan['question_index'][1]['pages'])
        self.assertEqual(candidate,read(folder/'candidate.json'))

    def test_publication_retains_measured_receipts(self):
        folder=self.fixture.start();self.fixture.route(('q1','q2'));self.fixture.produce()
        receipt=self.fixture.fixture_file('usage.json',{'run_id':read(folder/'run.json')['id'],
            'events':[{'event_id':'synthetic-call','usage_source':'synthetic receipt',
                'input_tokens':10,'output_tokens':5,'cost':0.2,'currency':'USD','duration_seconds':2}]})
        configure_workspace(folder.parent.parent);app.record_usage(folder,receipt)
        app.publish_base(folder)
        usage=read(folder.parent.parent/'run.json')['usage']
        self.assertEqual(usage['input_tokens'],10)
        self.assertEqual(usage['total_tokens'],15)
        self.assertEqual(usage['source'],'provider_receipts')

    def make_review(self, explanations=False):
        folder=self.fixture.start()
        key=self.fixture.fixture_file('key.json',self.fixture.key(explanations=explanations))
        configure_workspace(folder.parent.parent)
        app.route(folder,key,True,None,['q1'])
        self.fixture.produce(explanation_origin='solution' if explanations else 'model')
        app.baseline(folder)
        vf=__import__('pathlib').Path(verify.prepare(folder,'review',10,'synthetic','high','coordinator',folder.parent.parent))
        before=read(vf/'batches/batch-01/input.json')
        self.assertTrue(all(e['source_id']=='exam' for e in before['evidence']))
        self.assertNotIn('source_requirements',before)
        self.fixture.commit_blind(vf)
        return vf

    def test_solution_context_revealed_only_after_committed_reading(self):
        vf=self.make_review(explanations=True)
        packet=read(vf/'batches/batch-01/input.json')
        self.assertIn('solution',{e['source_id'] for e in packet['evidence']})
        self.assertEqual(packet['source_requirements']['q1']['explanation'],
                         [{'source_id':'solution','page':1,'bbox':None}])

    def test_add_solution_evidence_preserves_reading_and_reviewer(self):
        vf=self.make_review(explanations=True)
        template=read(vf/'batches/batch-01/report-template.json')
        verify.add_evidence(vf,'batch-01',[{'id':'solution-extra','question_id':'q1','source_id':'solution',
            'page':1,'bbox':[10,10,200,200],'role':'evidence','reason':'Synthetic explanation detail'}])
        updated=read(vf/'batches/batch-01/report-template.json')
        self.assertEqual(updated['reading_sha256'],template['reading_sha256'])
        self.assertEqual(updated['reviewer'],template['reviewer'])
        self.assertNotEqual(updated['input_sha256'],template['input_sha256'])
        self.assertTrue(any(e['source_id']=='solution' and e.get('id')=='solution-extra'
                            for e in read(vf/'batches/batch-01/input.json')['evidence']))

    def test_wrong_exam_evidence_cannot_approve_key_answer(self):
        self.fixture.start();self.fixture.route(('q1',),subagents=True);self.fixture.produce()
        vf,_,_=self.fixture.independent_reports()
        # q2 is model-solved; use a complete-key selected review for this assertion.
        # The explicit source requirements are themselves frozen in its comparison packet.
        packet=read(vf/'batches/batch-01/input.json')
        report=read(vf/'batches/batch-01/report.json')
        packet['source_requirements']['q2']['answer']=[{'source_id':'solution','page':1,'bbox':None}]
        # Do not alter frozen files: test validation by a controlled read overlay.
        from unittest.mock import patch
        original=verify.read
        report['input_sha256']=app.json_digest(packet)
        def overlay(path):
            if path == vf/'batches/batch-01/input.json': return packet
            if path == vf/'batches/batch-01/report.json': return report
            return original(path)
        with patch.object(verify,'read',side_effect=overlay),patch.object(verify,'binding',return_value=(read(vf/'run.json'),read(vf/'baseline.json'))):
            with self.assertRaisesRegex(ValueError,'wrong field/source page'):
                verify.load_reports(vf)

    def test_independent_assets_math_must_cover_graphical_options(self):
        self.fixture.start();self.fixture.route(('q1',),subagents=True);self.fixture.produce()
        vf,_,_=self.fixture.independent_reports()
        packet=read(vf/'batches/batch-01/input.json')
        report=read(vf/'batches/batch-01/report.json')
        selection=read(self.fixture.folder/'selection.json')
        mapping=next(q for q in selection['expected_questions'] if q['id']=='q2')
        # An enunciado on page 1 and alternatives on page 2 are distinct fields.
        mapping['source_fields']['stem']=[mapping['regions'][0]]
        row=next(q for q in report['questions'] if q['id']=='q2')
        row['checks']['assets_math']['evidence']=[ref for ref in row['checks']['assets_math']['evidence']
            if next(e for e in packet['evidence'] if e['path']==ref['path'])['page']==1]
        row['checks']['stem']['evidence']=copy.deepcopy(row['checks']['assets_math']['evidence'])
        row['independent_solution']['evidence']=copy.deepcopy(row['checks']['assets_math']['evidence'])
        from unittest.mock import patch
        original=verify.read
        def overlay(path):
            if path==self.fixture.folder/'selection.json': return selection
            if path==vf/'batches/batch-01/report.json': return report
            return original(path)
        with patch.object(verify,'read',side_effect=overlay):
            with self.assertRaisesRegex(ValueError,'omits required source coverage'):
                verify.load_reports(vf)


if __name__=='__main__': unittest.main()
