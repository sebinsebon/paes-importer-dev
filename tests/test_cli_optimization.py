import contextlib
import io
import json
import unittest
from unittest.mock import patch
import test_importer as fixtures
import importer as app
from lab import configure_workspace, read


class CLIOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ImporterTests(); self.fixture.setUp()
        self.folder=self.fixture.start(); self.fixture.route(('q1','q2')); self.fixture.produce()

    def tearDown(self): self.fixture.tearDown()

    def command(self,*args):
        output=io.StringIO()
        with patch('sys.argv',['importer',*args,'--run',str(self.folder)]), contextlib.redirect_stdout(output):
            code=app.main()
        return code,json.loads(output.getvalue())

    def test_pending_templates_and_native_diagnostics_cannot_auto_pass(self):
        configure_workspace(self.folder.parent.parent)
        template=app.check_template(self.folder)
        self.assertTrue(all(c['status']=='unresolved' for q in template['questions'] for c in q['checks'].values()))
        self.assertTrue(all(q['source_diagnostics'] for q in template['questions']))
        checks=read(self.folder/'self-checks.json')
        saved=read(self.folder/'reports/self-checks'/checks['q1']['report'])
        saved['questions'][0]['diagnostic_review']=[]
        with self.assertRaisesRegex(ValueError,'SOURCE_DIAGNOSTIC_PENDING'):
            app.check_record(self.folder,saved,read(self.folder/'candidate.json'))

    def test_capture_unavailable_is_functional_result_with_operation_scope(self):
        with patch('capture_review._load_playwright',side_effect=ImportError('Synthetic missing browser dependency')):
            code,result=self.command('capture-review','--question','q1')
        self.assertEqual(code,0)
        self.assertEqual(result['status'],'unavailable')
        rows=[json.loads(line) for line in (self.folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        end=rows[-1]
        self.assertEqual(end['outcome'],'unavailable')
        self.assertEqual(end['error_code'],'CAPTURE_UNAVAILABLE')
        self.assertEqual(end['question_ids'],['q1'])
        self.assertEqual(end['operation_id'],rows[-2]['operation_id'])
        self.assertIn('finished_at',end)

    def test_textual_html_without_artifact_is_rejected(self):
        configure_workspace(self.folder.parent.parent)
        checks=read(self.folder/'self-checks.json')
        record=read(self.folder/'reports/self-checks'/checks['q1']['report'])
        record['questions'][0]['visual_observation']={'mode':'html','tool':'read_file','observation':'Read HTML text'}
        with self.assertRaisesRegex(ValueError,'capture_receipt'):
            app.check_record(self.folder,record,read(self.folder/'candidate.json'))

    def test_diagnostic_adjudication_requires_all_continuation_pages(self):
        configure_workspace(self.folder.parent.parent)
        checks=read(self.folder/'self-checks.json')
        record=read(self.folder/'reports/self-checks'/checks['q1']['report'])
        record['questions']=[row for row in record['questions'] if row['id']=='q1']
        candidate=read(self.folder/'candidate.json')
        issue={'code':'EXPLANATION_SOURCE_COVERAGE','source_id':'exam','page':1,'pages':[1,2],'bbox':[10,10,30,30],'regions':[
            {'page':1,'bbox':[10,10,30,30]},{'page':2,'bbox':[10,10,30,30]}], 'diagnostic_sha256':'synthetic-binding'}
        def citation(page):
            resource=next(e for e in candidate['evidence'] if e['source_id']=='exam' and e['page']==page)
            return {'id':resource['id'],'sha256':resource['sha256'],'observation':'Synthetic localized continuation proof'}
        resolution={'diagnostic_sha256':'synthetic-binding','status':'dismissed','reason':'Synthetic fixture review',
                    'evidence':[citation(1)]}
        record['questions'][0]['diagnostic_review']=[resolution]
        with patch.object(app,'review_diagnostics',return_value={'q1':[issue],'q2':[]}):
            with self.assertRaisesRegex(ValueError,'every affected source page'):
                app.check_record(self.folder,record,candidate)
            resolution['evidence'].append(citation(2))
            self.assertEqual(len(app.check_record(self.folder,record,candidate)),1)


if __name__ == '__main__': unittest.main()
