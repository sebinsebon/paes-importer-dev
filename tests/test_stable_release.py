"""General source-fidelity regressions; fictional content, no real AI imports."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import RUNTIME_ROOT, WORK_ROOT
import importer as app
import verify
import synthetic
import pypdfium2 as pdfium
from lab import configure_workspace, read, write
from content_inventory import bare_variable, validate_inventory
from pdf_assets import crop_text_warnings, visible_bounds, apply_crops
from batch_plan import plan_batches
import test_importer as fixtures
import test_capture_review as captures


class InlineVariableTests(unittest.TestCase):
    def test_spanish_words_are_not_global_math_variables(self):
        for text, symbol in [('Se suma a la cantidad restante.', 'a'), ('Sean dos valores y su suma.', 'y'),
                             ('Dos números e intervalos.', 'e')]:
            self.assertFalse(bare_variable(text, symbol))
        for text, symbol in [('a', 'a'), ('y = 2', 'y'), ('El valor x aumenta.', 'x'), ('a + 1', 'a')]:
            self.assertTrue(bare_variable(text, symbol))

    def test_inline_symbols_and_grammatical_words_coexist(self):
        question = {'id':'fiction','source_id':'exam','stem':[
            {'type':'text','text':'Se suma a '},{'type':'math','latex':'a','display':False},
            {'type':'text','text':' y a '},{'type':'math','latex':'y','display':False}],
            'options':[], 'explanation':{'blocks':[]}}
        record = {'content_inventory':[{'field':'stem','type':'math','count':1,'symbols':['a','y']}]}
        validate_inventory(question,record,{'assets':[]})
        question['stem'][1]={'type':'text','text':'a'}
        with self.assertRaisesRegex(ValueError,'variable a'): validate_inventory(question,record,{'assets':[]})

    def test_text_options_and_text_solution_need_no_artificial_formula(self):
        q={'id':'fiction','stem':[{'type':'math','latex':'x=2','display':False}],
           'options':[{'label':'A','blocks':[{'type':'text','text':'Ninguno.'}]}],
           'explanation':{'blocks':[{'type':'text','text':'El desarrollo mostrado es correcto.'}]}}
        validate_inventory(q,{'content_inventory':[{'field':'stem','type':'math','count':1,'symbols':['x']}]},{})


class CropTextTests(unittest.TestCase):
    def test_clipped_dimension_and_complete_nearby_label_all_rotations(self):
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temp:
            source=Path(temp)/'geometry.pdf'
            synthetic.pdf(source,['BT /F1 14 Tf 100 230 Td (3x) Tj ET 100 235 60 40 re S'])
            with pdfium.PdfDocument(str(source)) as pdf:
                page=pdf[0]
                for rotation in (0,90,180,270):
                    page.set_rotation(rotation)
                    text=page.get_textpage()
                    native=text.get_charbox(0);text.close()
                    w,h=page.get_size();left,top,right,bottom=visible_bounds(native,rotation,w,h)
                    cut=[left-2,top-2,(left+right)/2,bottom+2]
                    with self.subTest(rotation=rotation):
                        self.assertTrue(crop_text_warnings(page,cut)['clipped_text'])
                        self.assertFalse(crop_text_warnings(page,[0,0,w,h])['clipped_text'])
                        nearby=crop_text_warnings(page,[left-10,top-15,right+20,top-1])
                        self.assertTrue(nearby['nearby_text'])
                page.close()


class StableImporterTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ImporterTests();self.f.setUp()

    def tearDown(self): self.f.tearDown()

    def test_native_source_text_preserves_registered_source_and_rejects_invalid_page(self):
        folder=self.f.start()
        result=app.source_text(folder,'exam',[1])
        self.assertEqual(result['source_id'],'exam')
        self.assertTrue(result['pages'][0]['text'])
        self.assertEqual(result['pages'][0]['page'],1)
        with self.assertRaises(ValueError): app.source_text(folder,'exam',[999])
        with self.assertRaises(ValueError): app.source_text(folder,'unknown',[1])

    def test_progress_and_empty_pending_plan_preserve_accepted_content(self):
        folder=self.f.start();self.f.route(('q1','q2'))
        self.assertEqual(app.progress(folder)['pending_question_ids'],['q1','q2'])
        self.f.produce()
        before=(folder/'candidate.json').read_bytes()
        state=app.progress(folder)
        self.assertEqual(state['accepted_question_ids'],['q1','q2'])
        self.assertEqual(state['pending_question_ids'],[])
        self.assertEqual(state['pending_review_ids'],[])
        plan=plan_batches(read(folder/'candidate.json'),selection=read(folder/'selection.json'),
                          route=read(folder/'route.json'),question_ids=[])
        self.assertEqual(plan['batches'],[])
        self.assertEqual(before,(folder/'candidate.json').read_bytes())

    def test_progress_does_not_repeat_declined_solution_work(self):
        folder=self.f.start(host='web');self.f.route(('q1',),host='web',consent='no')
        self.f.produce(pending=('q2',))
        state=app.progress(folder)
        self.assertEqual(state['pending_question_ids'],[])
        self.assertEqual(state['pending_solution_ids'],[])
        self.assertEqual(state['deferred_question_ids'],['q2'])

    def test_mapping_repair_rolls_back_on_interrupted_commit(self):
        import checkpoints
        folder=self.f.start();self.f.route(('q1','q2'));self.f.produce()
        before={name:(folder/name).read_bytes() for name in ('candidate.json','selection.json','run.json','route.json','self-checks.json')}
        record=copy.deepcopy(read(folder/'selection.json')['expected_questions'][0])
        record['content_inventory'][0]['symbols']=['x']
        request=self.f.fixture_file('repair.json',{'reason':'Synthetic interrupted repair','questions':[record]})
        configure_workspace(folder.parent.parent)
        original=checkpoints._atomic_bytes;interrupted=[]
        def fail_once(path,payload):
            if Path(path)==folder/'candidate.json' and not interrupted:
                interrupted.append(True);raise OSError('synthetic interruption')
            return original(path,payload)
        with patch('checkpoints._atomic_bytes',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'interruption'): app.repair_mapping(folder,request)
        for name,payload in before.items(): self.assertEqual((folder/name).read_bytes(),payload)
        app.frozen_route(folder)
        self.assertEqual(app.progress(folder)['pending_question_ids'],[])

    def test_repair_frozen_false_math_requirement_without_losing_other_review(self):
        folder=self.f.start();self.f.route(('q1','q2'));self.f.produce()
        before=read(folder/'candidate.json');old_selection=(folder/'selection.json').read_bytes()
        other=read(folder/'self-checks.json')['q2']
        record=copy.deepcopy(read(folder/'selection.json')['expected_questions'][0])
        record['content_inventory'][0]['symbols']=['x']
        request=self.f.fixture_file('repair.json',{'reason':'Fictional observed variable','questions':[record]})
        configure_workspace(folder.parent.parent);app.repair_mapping(folder,request)
        self.assertEqual(app.progress(folder)['pending_question_ids'],['q1'])
        self.assertEqual(read(folder/'self-checks.json'),{'q2':other})
        self.assertEqual(before['questions'],read(folder/'candidate.json')['questions'])
        self.assertIn(old_selection,[p.read_bytes() for p in (folder/'versions').glob('mapping-*/selection.json')])
        record['content_inventory'][0].pop('symbols')
        self.f.fixture_file('repair.json',{'reason':'Source contains no x; correct only the observation','questions':[record]})
        configure_workspace(folder.parent.parent)
        app.repair_mapping(folder,request)
        self.assertEqual(app.progress(folder)['pending_question_ids'],[])
        self.assertEqual(app.progress(folder)['pending_review_ids'],['q1'])
        app.frozen_route(folder)

    def test_repair_identity_rejected_without_candidate_change(self):
        folder=self.f.start();self.f.route(('q1','q2'))
        record=copy.deepcopy(read(folder/'selection.json')['expected_questions'][0]);record['number']='99'
        request=self.f.fixture_file('repair.json',{'reason':'Invalid identity change','questions':[record]})
        configure_workspace(folder.parent.parent);before=(folder/'candidate.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'identity'): app.repair_mapping(folder,request)
        self.assertEqual(before,(folder/'candidate.json').read_bytes())

    def test_total_and_partial_rejections_are_archived_with_reasons(self):
        folder=self.f.start();self.f.route(('q1','q2'));self.f.produce()
        response=read(self.f.home/'response.json')
        response['questions'][0]['stem']=[{'type':'text','text':'Omitted table and expression'}]
        path=self.f.fixture_file('partial.json',response);configure_workspace(folder.parent.parent)
        result=app.ingest(folder,path)
        self.assertEqual(result['rejected'][0]['question_id'],'q1')
        self.assertIn('needs math',read(folder/result['attempt_report'])['rejected'][0]['reason'])
        response['questions']=response['questions'][:1]
        response['curriculum_provenance']={'q1':response['curriculum_provenance']['q1']}
        self.f.fixture_file('partial.json',response);configure_workspace(folder.parent.parent)
        with self.assertRaisesRegex(ValueError,'No questions accepted'): app.ingest(folder,path)
        report=read(sorted((folder/'reports/ingest').glob('*.json'))[-1])
        self.assertEqual(report['rejected'][0]['question_id'],'q1')
        self.assertIn('SOURCE_CONTENT_OMITTED',report['error'])

    def test_gold_requires_current_visual_source_cotejos_not_verified_answers(self):
        folder=self.f.start();self.f.route(('q1','q2'));self.f.produce()
        candidate,decision=app.validate_for_pack(folder)
        self.assertTrue(decision['quality']['gold_eligible'])
        self.assertTrue(all(q['answer']['status']=='provisional' for q in candidate['questions']))
        checks=read(folder/'self-checks.json');checks.pop('q1');write(folder/'self-checks.json',checks)
        with self.assertRaisesRegex(ValueError,'Every question'):app.validate_for_pack(folder)

    def test_existing_solution_cannot_be_replaced_by_model_explanation(self):
        folder=self.f.start()
        key=self.f.fixture_file('key.json',self.f.key(explanations=True));configure_workspace(folder.parent.parent)
        app.route(folder,key,False,None)
        with self.assertRaisesRegex(ValueError,'existing solution'):self.f.produce(explanation_origin='model')

    def test_source_review_needs_no_independent_resolution(self):
        folder=self.f.start()
        key=self.f.fixture_file('key.json',self.f.key(explanations=True));configure_workspace(folder.parent.parent)
        app.route(folder,key,True,None,['q1'])
        self.f.produce(explanation_origin='solution')
        vf,_,_=self.f.independent_reports()
        packet=read(vf/'batches/batch-01/input.json')
        self.assertEqual(packet['source_backed_question_ids'],['q1'])
        template=read(vf/'batches/batch-01/report-template.json')
        self.assertNotIn('independent_solution',template['questions'][0])
        report=read(vf/'batches/batch-01/report.json')
        report['questions'][0].pop('independent_solution')
        write(vf/'batches/batch-01/report.json',report)
        # This report proposes no changes: the existing empty decisions remain valid.
        app.verify_command(__import__('argparse').Namespace(action='consolidate',run=str(vf),decisions=str(vf/'decisions.json')))
        self.assertEqual(read(folder.parent.parent/'final.json')['questions'][0]['answer']['status'],'verified')

    def test_crop_crossing_glyph_rejected_before_any_asset_is_written(self):
        folder=self.f.start();self.f.route(('q1','q2'))
        with pdfium.PdfDocument(str(self.f.exam)) as pdf:
            page=pdf[0];text=page.get_textpage();r=visible_bounds(text.get_charbox(0),0,400,400);text.close()
            box=[r[0]-1,r[1]-1,(r[0]+r[2])/2,r[3]+1];page.close()
        with self.assertRaisesRegex(ValueError,'CROP_CLIPS_TEXT'):
            apply_crops(folder,[{'id':'cut','source_id':'exam','page':1,'bbox':box}])
        self.assertFalse((folder/'assets/crops/cut.png').exists())


class MemoryCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fixture=captures.CaptureReviewTests();self.fixture.setUp()
        self.folder=self.fixture.folder;self.snapshot=self.fixture.snapshot;self.reference=self.fixture.reference

    def tearDown(self): self.fixture.tearDown()

    def test_memory_requests_serve_only_snapshot_bytes(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from capture_review import memory_request
        for url in ('https://example.invalid/x','https://paes-review.invalid/%2e%2e/candidate.json',
                    'https://paes-review.invalid/missing','file:///outside.html'):
            route=Mock(request=SimpleNamespace(url=url))
            memory_request(route,self.snapshot)
            route.abort.assert_called_once();route.fulfill.assert_not_called()
        route=Mock(request=SimpleNamespace(url='https://paes-review.invalid/index.html'))
        memory_request(route,self.snapshot)
        self.assertEqual(route.fulfill.call_args.kwargs['body'],(self.snapshot/'index.html').read_bytes())
        route.abort.assert_not_called()

    def factory(self):
        factory=self.fixture.factory();owner=self
        class Manager(factory):
            def __enter__(self):
                manager=super().__enter__()
                original=manager.chromium.launch
                def launch(**kwargs):
                    browser=original(**kwargs);create=browser.new_page
                    browser.unroute=lambda *args:owner.events.append('unroute')
                    def new_page():
                        page=create()
                        page.goto=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('net::ERR_BLOCKED_BY_ADMINISTRATOR'))
                        def set_content(html,**kwargs):
                            owner.assertIn('https://paes-review.invalid/',html)
                            owner.events.append('memory-loaded')
                        page.set_content=set_content
                        return page
                    browser.new_page=new_page
                    return browser
                manager.chromium.launch=launch
                return manager
        return Manager

    def test_memory_fallback(self):
        self.events=[]
        self.fixture.events=self.events
        # The real snapshot renderer always has a head element.
        from lab import digest
        html=self.snapshot/'index.html';html.write_text('<html><head></head><body>Fictional</body></html>',encoding='utf8')
        record=read(self.snapshot/'render-review.json');record['files'][0]['sha256']=digest(html)
        write(self.snapshot/'render-review.json',record);self.reference['sha256']=digest(self.snapshot/'render-review.json')
        from capture_review import capture_review
        with patch('capture_review._load_playwright',return_value=self.factory()):
            result=capture_review(self.folder,self.reference)
        self.assertEqual(result['status'],'captured',result.get('limitation'))
        self.assertEqual(result['transport'],'memory')
        self.assertIn('BLOCKED',result['file_limitation'])

if __name__=='__main__':unittest.main()
