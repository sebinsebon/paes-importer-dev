"""Synthetic extractor-to-importer integration; no private PDFs or model calls."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile
from unittest.mock import patch

import test_importer as fixtures
from lab import read, write, configure_workspace
from output_policy import require_official_final
from draft_v1.draft_contract import validate_v1

app = fixtures.app


class DraftAdapterTests(unittest.TestCase):
    setUp = fixtures.ImporterTests.setUp
    tearDown = fixtures.ImporterTests.tearDown
    fixture_file = fixtures.ImporterTests.fixture_file
    start = fixtures.ImporterTests.start
    route = fixtures.ImporterTests.route
    key = fixtures.ImporterTests.key
    produce = fixtures.ImporterTests.produce
    cotejo = fixtures.ImporterTests.cotejo

    def draft(self):
        folder = self.start(solution=False, inventory_types=('math',))
        self.route()
        catalog = read(folder / 'catalog.json')
        candidate = read(folder / 'candidate.json')
        source = candidate['sources'][0]
        pages = [{'id': 'p' + str(p['page']), 'source_id': 'legacy', 'page_number': p['page'],
                  'width': p['width'], 'height': p['height'], 'rotation': 0,
                  'coordinate_system': 'top_left_pdf_points', 'transform': [1,0,0,1,0,0]}
                 for p in catalog['pages'] if p['source_id'] == 'exam']
        regions = [{'id': 'r' + str(i), 'page_id': 'p' + str(i), 'bbox': [0,0,400,400],
                    'kind': 'question', 'transform': [1,0,0,1,0,0]} for i in (1,2)]
        regions.append({'id':'r2-shared','page_id':'p1','bbox':[0,300,400,400],
                        'kind':'context','transform':[1,0,0,1,0,0]})
        questions = []
        for i in (1,2):
            questions.append({'id': 'legacy-' + str(i), 'original_number': str(i),
                              'region_ids': (['r2-shared'] if i == 2 else []) + ['r' + str(i)], 'context_ids': [],
                              'stem': [{'type':'text','text':'Synthetic sum ', 'source_ids': []},
                                       {'type':'math','latex':'2+2','display':False,'source_ids':[]}],
                              'options':[{'id':f'o{i}{label}', 'label':label, 'owner':f'option:o{i}{label}', 'source_ids':[],
                                          'blocks':[{'type':'text','text':value, 'source_ids':[]}]} for label,value in [('A','3'),('B','4')]],
                              'structural_fidelity': {'complete':False,'failures':[]},
                              'extraction_status':'partial', 'needs_manual_audit':True})
        data = {'schema_version':'1.0.0','sources':[{'id':'legacy','sha256':source['sha256'],'page_count':source['page_count']}],
                'extraction':{'status':'partial','tools':{},'ai_interventions':[], 'verification_status':'not_run','needs_manual_audit':True},
                'pages':pages,'regions':regions,'assets':[],'evidence':[], 'source_objects':[],
                'contexts':[],'questions':questions,'unassigned_fragments':[],'issues':[]}
        self.draft_home = self.home / 'extractor'
        self.draft_home.mkdir()
        self.draft_path = self.draft_home / 'draft.json'
        self.draft_path.write_text(json.dumps(data), encoding='utf-8')
        validate_v1(data, artifact_root=self.draft_home, check_files=True)
        return data

    def test_adapt_and_finish_existing_pipeline(self):
        data = self.draft()
        original = self.draft_path.read_bytes()
        report = app.adapt_draft(self.folder, self.draft_path)
        self.assertFalse(report['review_promoted'])
        candidate = read(self.folder / 'candidate.json')
        self.assertEqual(candidate['schema_version'], '0.2.0')
        self.assertEqual(candidate['questions'][0]['stem'][1]['latex'], '2+2')
        self.assertEqual(candidate['questions'][0]['answer']['status'], 'missing')
        self.assertEqual(candidate['questions'][0]['fidelity']['status'], 'pending')
        self.assertEqual((self.folder / report['archive']).read_bytes(), original)
        with self.assertRaises((ValueError, FileNotFoundError)): app.publish_base(self.folder)
        # Host must still read/classify/resolve and document field-level cotejo.
        self.produce()
        result = app.publish_base(self.folder)
        self.assertTrue(app.inspect_package(result['paessed'])['valid'])
        import zipfile
        with zipfile.ZipFile(result['paessed']) as archive:
            self.assertFalse(any('draft' in name or 'reports/' in name for name in archive.namelist()))
            self.assertEqual(json.loads(archive.read('final.json'))['schema_version'], '0.2.0')
        self.assertEqual(self.draft_path.read_bytes(), original)

    def test_shared_context_table_visual_option_and_multipage(self):
        data = self.draft()
        data['regions'].append({'id':'rctx','page_id':'p1','bbox':[0,300,400,400],
                                'kind':'context','transform':[1,0,0,1,0,0]})
        data['contexts'] = [{'id':'ctx','region_ids':['rctx'], 'blocks':[
            {'type':'table','source_ids':[], 'rows':[{'cells':[{'blocks':[{'type':'text','text':'Value','source_ids':[]}]}]}]}]}]
        data['questions'][1]['context_ids'] = ['ctx']
        # Use synthetic PNG already generated by the importer fixture renderer.
        resource = read(self.folder/'catalog.json')['evidence'][0]
        blob = (self.folder/resource['path']).read_bytes()
        target = self.draft_home/'assets/figure.png'
        target.parent.mkdir()
        target.write_bytes(blob)
        data['assets'] = [{'asset_id':'figure','path':'assets/figure.png','mime':'image/png',
                          'width':20,'height':20,'sha256':hashlib.sha256(blob).hexdigest(),'region_ids':['r1'],
                          'source_bbox':[10,20,30,40]}]
        data['questions'][0]['options'][0]['blocks'] = [{'type':'image','asset_id':'figure','source_ids':[]}]
        self.draft_path.write_text(json.dumps(data), encoding='utf-8')
        report = app.adapt_draft(self.folder,self.draft_path)
        candidate = read(self.folder/'candidate.json')
        q = candidate['questions'][1]
        self.assertEqual([r['page'] for r in q['regions']], [1,2])
        self.assertEqual(q['stem'][0]['rows'][0][0][0]['text'], 'Value')
        visual = candidate['questions'][0]['options'][0]['blocks'][0]
        asset = next(a for a in candidate['assets'] if a['id'] == visual['asset_id'])
        self.assertEqual((self.folder/asset['path']).read_bytes(), blob)
        self.assertEqual(asset['bbox'], [10,20,30,40])
        self.assertEqual((self.folder/report['archive']).read_bytes(), self.draft_path.read_bytes())
        from pdf_assets import apply_crops
        apply_crops(self.folder, [{'id':'new-crop','source_id':'exam','page':1,'bbox':[40,50,100,100],'role':'asset'}])
        app.engine.sync_assets(self.folder)
        self.assertIn(asset, read(self.folder/'candidate.json')['assets'])
        # Ingest the actual adapted visual content after the normal crop command.
        response = self.fixture_file('adapted-response.json', {'run_id':candidate['run']['id'], 'questions':candidate['questions']})
        configure_workspace(self.folder.parent.parent)
        self.assertEqual(app.ingest(self.folder,response)['rejected'], [])
        final_proposals = read(self.folder/'candidate.json')
        rationale = {}
        for q in final_proposals['questions']:
            q['answer'] = {'label':'B','status':'provisional','origin':'model','source_ref':None}
            q['explanation'] = {'blocks':[{'type':'math','latex':'2+2=4','display':True}], 'status':'provisional'}
            q['curriculum'] = {'eje':'Números','subeje':'Conjunto de los números enteros y racionales','en_temario':'si'}
            q['issues'] = []
            rationale[q['id']] = {'reason':'Synthetic addition','evidence':[{'source_id':'exam','page':q['regions'][0]['page'],'observation':'Synthetic arithmetic'}]}
        response = self.fixture_file('resolved-adapted.json', {'run_id':candidate['run']['id'],'questions':final_proposals['questions'],
            'curriculum_provenance':rationale,'explanation_provenance':{q['id']:{'origin':'model'} for q in final_proposals['questions']}})
        configure_workspace(self.folder.parent.parent)
        self.assertEqual(app.ingest(self.folder,response)['rejected'], [])
        ledger = read(self.folder/'direct-input.template.json')
        ledger.update(mode='page_images_fallback',reader='synthetic renderer',visual_content_understood=True,
                      capability_observation='Fictional fixture, not evidence of AI comprehension')
        for source in ledger['sources']:
            source['pages_read'] = list(range(1,next(s['page_count'] for s in candidate['sources'] if s['id']==source['source_id'])+1))
        response = self.fixture_file('adapted-ledger.json',ledger)
        configure_workspace(self.folder.parent.parent)
        app.record_input(self.folder,response)
        self.cotejo()
        result = app.publish_base(self.folder)
        import zipfile
        with zipfile.ZipFile(result['paessed']) as archive:
            self.assertEqual(archive.read(asset['path']), blob)
            self.assertFalse(any(n.startswith('reports/') for n in archive.namelist()))

    def test_invalid_precise_image_bbox_is_rejected_atomically(self):
        data = self.draft()
        resource = read(self.folder/'catalog.json')['evidence'][0]
        blob = (self.folder/resource['path']).read_bytes()
        asset = self.draft_home/'assets/x.png'; asset.parent.mkdir(); asset.write_bytes(blob)
        data['assets'] = [{'asset_id':'x','path':'assets/x.png','mime':'image/png','width':1,'height':1,
                          'sha256':hashlib.sha256(blob).hexdigest(),'region_ids':['r1']}]
        data['questions'][0]['options'][0]['blocks'] = [{'type':'image','asset_id':'x','source_ids':[]}]
        original = (self.folder/'candidate.json').read_bytes()
        catalog = (self.folder/'catalog.json').read_bytes()
        for box in ([-1,0,10,10],[0,0,10000,20],[10,20,5,30],[0,0,401,20]):
            data['assets'][0]['source_bbox'] = box
            self.draft_path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError): app.adapt_draft(self.folder,self.draft_path)
            self.assertEqual((self.folder/'candidate.json').read_bytes(),original)
            self.assertEqual((self.folder/'catalog.json').read_bytes(),catalog)

    def test_invalid_drafts_leave_candidate_and_archive_untouched(self):
        data = self.draft()
        original = (self.folder/'candidate.json').read_bytes()
        invalid = []
        wrong = copy.deepcopy(data); wrong['sources'][0]['sha256']='a'*64; invalid.append(wrong)
        wrong = copy.deepcopy(data); wrong['questions'][1]['original_number']='1'; invalid.append(wrong)
        wrong = copy.deepcopy(data); wrong['questions'].pop(); invalid.append(wrong)
        wrong = copy.deepcopy(data); wrong['questions'][0]['options'][0]['label']='Z'; invalid.append(wrong)
        wrong = copy.deepcopy(data); wrong['schema_version']='0.1.0'; invalid.append(wrong)
        wrong = copy.deepcopy(data); wrong['questions'][0]['stem'][0]['type']='custom'; invalid.append(wrong)
        for wrong in invalid:
            self.draft_path.write_text(json.dumps(wrong), encoding='utf-8')
            with self.assertRaises(ValueError): app.adapt_draft(self.folder, self.draft_path)
            self.assertEqual((self.folder/'candidate.json').read_bytes(), original)
            self.assertFalse((self.folder/'reports/drafts').exists())

    def test_reject_changed_files_and_escaping_paths(self):
        data = self.draft()
        data['assets'] = [{'asset_id':'x','path':'assets/x.png','mime':'image/png', 'width':1,'height':1,
                          'sha256':'b'*64,'region_ids':['r1']}]
        asset = self.draft_home/'assets/x.png'; asset.parent.mkdir(); asset.write_bytes(b'altered')
        for name in ('assets/x.png', 'assets/../../escape.png'):
            data['assets'][0]['path'] = name
            self.draft_path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError): app.adapt_draft(self.folder,self.draft_path)

    def test_no_overwrite_or_status_promotion(self):
        self.draft()
        app.adapt_draft(self.folder,self.draft_path)
        current = (self.folder/'candidate.json').read_bytes()
        with self.assertRaises(ValueError): app.adapt_draft(self.folder,self.draft_path)
        self.assertEqual((self.folder/'candidate.json').read_bytes(),current)

    def test_new_publications_reject_historical_version(self):
        self.draft()
        candidate = read(self.folder/'candidate.json')
        candidate['schema_version'] = '0.1.0'
        for q in candidate['questions']:
            q.pop('curriculum'); q['issues']=['NOT_PROCESSED']
        write(self.folder/'candidate.json',candidate)
        with self.assertRaisesRegex(ValueError,'0.2.0'): app.validate_for_pack(self.folder)
        with patch.object(fixtures.verify,'load_reports',return_value=({},candidate,[])):
            with self.assertRaisesRegex(ValueError,'0.2.0'): fixtures.verify.consolidate(self.folder, 'unused')
        require_official_final({'schema_version':'0.2.0'})

    def test_adapter_runs_from_extracted_bundle_and_unrelated_cwd(self):
        self.draft()
        bundle = self.home/'portable.zip'
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONUTF8':'1'}
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable,'-B',str(fixtures.DEV_ROOT/'scripts/make_bundle.py'),'--output',str(bundle)],
                                capture_output=True,text=True,encoding='utf-8',env=env,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        extracted = self.home/'instalación con espacios'
        with zipfile.ZipFile(bundle) as archive: archive.extractall(extracted)
        caller = self.home/'caller'; caller.mkdir()
        result = subprocess.run([sys.executable,'-B',str(extracted/'paes-importer/scripts/importer.py'),
                                 'adapt-draft','--run',str(self.folder),'--draft',str(self.draft_path)],
                                cwd=caller,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'pending_host_cotejo')
        self.assertEqual(read(self.folder/'candidate.json')['schema_version'],'0.2.0')
