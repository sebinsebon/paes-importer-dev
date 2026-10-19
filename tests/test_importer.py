"""Deterministic, fictional fixtures. No model calls or private exam dependencies."""
import argparse
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(DEV_ROOT/'examples'))
import importer as app
import verify
import synthetic
from policy import select_mode
from lab import configure_workspace, digest, read, write
import package_io

class PolicyTests(unittest.TestCase):
    def test_complete_key_fast_on_both_hosts(self):
        for host in ('cli', 'web'):
            mode = select_mode(host, ['q1','q2'], ['q1','q2'], True)
            self.assertEqual(mode['processing_mode'], 'answer-key')
            self.assertEqual(mode['independent_question_ids'], [])
    def test_web_requires_consent_absent_or_partial_key(self):
        for covered in ([], ['q1']):
            self.assertEqual(select_mode('web', ['q1','q2'], covered)['status'], 'needs_consent')
    def test_web_consent_yes_solves_only_missing(self):
        self.assertEqual(select_mode('web', ['q1','q2'], ['q1'], True, 'yes')['solve_question_ids'], ['q2'])
        self.assertEqual(select_mode('web', ['q1'], [], True, 'yes')['review_mode'], 'self')
    def test_web_consent_no_leaves_pending(self):
        self.assertEqual(select_mode('web', ['q1','q2'], ['q1'], False, 'no')['pending_question_ids'], ['q2'])
    def test_cli_independent_subset_or_self_fallback(self):
        self.assertEqual(select_mode('cli', ['q1','q2'], ['q1'], True)['independent_question_ids'], ['q2'])
        self.assertEqual(select_mode('cli', ['q1'], [], False)['review_mode'], 'self')

class ImporterTests(unittest.TestCase):
    def setUp(self):
        (WORK_ROOT).mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.home = Path(self.temporary.name)
        self.exam, self.solution = synthetic.create(self.home / 'sources')
        configure_workspace(self.home)
        self.cap = self.home / 'cap.json'
        write(self.cap, {**{k: True for k in app.CAPABILITIES}, 'observation': 'Synthetic fixture machinery; no real AI capability claim', 'result_visual':{'mode':'html','tool':'synthetic fixture','observation':'Synthetic renderer binding, not real comprehension'}})
    def tearDown(self): self.temporary.cleanup()
    def fixture_file(self, name, record):
        path = self.home / name
        configure_workspace(self.home); write(path, record)
        return path
    def start(self, host='cli', solution=True, runid='run-01', inventory_types=('math','table')):
        args = argparse.Namespace(exam=str(self.exam), solution=str(self.solution) if solution else None,
            title='Synthetic M1', run_id=runid, destination='custom', output_root=str(self.home / 'output'),
            host=host, client='synthetic-test', model='synthetic', effort='synthetic',
            session_id='synthetic-producer', capabilities=str(self.cap), scale=1.0)
        folder = Path(app.prepare(args)['run']); self.folder = folder
        selection = {'title': 'Synthetic M1', 'observed_question_count': 2,
            'observation': 'Fictional two-question fixture',
            'expected_questions': [{'id': f'q{i}', 'number': str(i), 'source_id': 'exam', 'page': i, 'option_labels':['A','B'], 'regions':([{'page':1,'bbox':[0,300,400,400]}] if i == 2 else []) + [{'page':i,'bbox':[0,0,400,400]}]} for i in (1,2)]}
        for q in selection['expected_questions']:
            q['content_inventory'] = [{'field':'stem','type':kind,'count':1,
                'regions':[{'page':q['page'],'bbox':[0,0,400,400]}]} for kind in inventory_types]
        for q in selection['expected_questions']:
            q['source_fields'] = {'stem':copy.deepcopy(q['regions']), **{'options/'+label:[{'page':q['page'],'bbox':[0,0,400,400]}] for label in q['option_labels']}}
            for item in q['content_inventory']:
                if item['type']=='table': item['shape']={'rows':1,'columns':2}
        sf = self.fixture_file('selection.json', selection)
        configure_workspace(folder.parent.parent); app.map_questions(folder, sf)
        return folder
    def key(self, covered=('q1','q2'), status='matched', explanations=False, source=None):
        candidate = read(self.folder / 'candidate.json')
        source = source or ('solution' if any(s['id']=='solution' for s in candidate['sources']) else 'exam')
        return {'exam_sha256': candidate['sources'][0]['sha256'],
            'match': {'status': status, 'reason': 'Synthetic source identities match',
                'evidence': [{'source_id': source, 'page': 1, 'observation': 'Fictional matching title'}]},
            'entries': [{'question_id': qid, 'label': 'B', 'source_id': source, 'page': 1,
                         'observation': 'Fictional key gives B', 'has_explanation': explanations, **({'content_inventory':[{'field':'explanation','type':'math','count':1,'source_id':source,'regions':[{'page':1,'bbox':[0,0,400,400]}]}]} if explanations else {})} for qid in covered]}
    def route(self, covered=None, host='cli', subagents=False, consent=None):
        keyfile = self.fixture_file('key.json', self.key(covered)) if covered is not None else None
        configure_workspace(self.folder.parent.parent)
        return app.route(self.folder, keyfile, subagents, consent)
    def produce(self, pending=(), explanation_origin='model', image=False):
        folder = self.folder
        if image:
            from pdf_assets import apply_crops
            apply_crops(folder, [{'id':'figure','source_id':'exam','page':1,'bbox':[35,115,145,205],'role':'asset'}])
            app.engine.sync_assets(folder)
        data = read(folder / 'candidate.json'); questions = []; provenance = {}
        for i, initial in enumerate(data['questions'], 1):
            q = copy.deepcopy(initial)
            q['regions'] = [{'page':i,'bbox':[0,0,400,400]}]
            if i == 2: q['regions'].insert(0, {'page':1,'bbox':[0,300,400,400]})
            q['stem'] = [{'type':'text','text':'Synthetic arithmetic: '}, {'type':'math','latex':'2+2' if i==1 else '3+1','display':False},
                {'type':'table','rows':[[[{'type':'text','text':'Value'}],[{'type':'math','latex':'4','display':False}]]]}]
            if image and i==1: q['stem'].append({'type':'image','asset_id':'figure','alt':'Fictional rectangle'})
            q['options'] = [{'label':'A','blocks':[{'type':'text','text':'3'}]}, {'label':'B','blocks':[{'type':'text','text':'4'}]}]
            q['answer'] = {'label':None if q['id'] in pending else 'B','status':'missing' if q['id'] in pending else 'provisional',
                'origin':'none' if q['id'] in pending else 'model','source_ref':None}
            q['explanation'] = {'blocks':[] if q['id'] in pending else [{'type':'math','latex':'2+2=4' if i==1 else '3+1=4','display':True}],
                'status':'missing' if q['id'] in pending else 'provisional'}
            q['issues']=[]
            q['curriculum']={'eje':'Números','subeje':'Conjunto de los números enteros y racionales','en_temario':'si'}
            if q['explanation']['blocks']:
                provenance[q['id']]={'origin':explanation_origin}
                if explanation_origin=='solution': provenance[q['id']].update(source_id='solution',page=1)
            questions.append(q)
        response = self.fixture_file('response.json', {'run_id':data['run']['id'],'questions':questions,'explanation_provenance':provenance, 'curriculum_provenance':{q['id']:{'reason':'Synthetic arithmetic requires addition of integers','evidence':[{'source_id':q['source_id'],'page':q['regions'][0]['page'],'observation':'Synthetic sum of integers'}]} for q in questions}})
        configure_workspace(folder.parent.parent); result=app.ingest(folder,response)
        if result['rejected']:
            raise ValueError('; '.join(r['reason'] for r in result['rejected']))
        ledger = read(folder / 'direct-input.template.json')
        ledger.update(mode='page_images_fallback',reader='synthetic fixture renderer',visual_content_understood=True,
            capability_observation='Deterministic fictional fixture, not actual AI comprehension')
        for s in ledger['sources']:
            source = next(x for x in data['sources'] if x['id']==s['source_id'])
            s['pages_read']=list(range(1,source['page_count']+1))
        lf=self.fixture_file('ledger.json',ledger)
        configure_workspace(folder.parent.parent);app.record_input(folder,lf)
        self.cotejo()
    def cotejo(self):
        from evidence import citation_requirements
        app.visual_review.create_review(self.folder)
        record=app.check_template(self.folder); candidate=read(self.folder/'candidate.json')
        selection={q['id']:q for q in read(self.folder/'selection.json')['expected_questions']}
        keys={e['question_id']:e for e in read(self.folder/'answer-key-map.json')['entries']} if (self.folder/'answer-key-map.json').exists() else {}
        provenance=read(self.folder/'explanation-provenance.json')
        for row in record['questions']:
            question=next(q for q in candidate['questions'] if q['id']==row['id'])
            row['visual_observation']={'mode':'html','tool':'synthetic fixture','observation':'Synthetic assertion only; not a real visual inspection'}
            for dimension,check in row['checks'].items():
                citations={}
                for field in check['field_paths']:
                    sid,regions=citation_requirements(question,dimension,field,selection[row['id']],keys.get(row['id']),provenance.get(row['id']))
                    for region in regions:
                        resource=next(e for e in candidate['evidence'] if e['source_id']==sid and e['page']==region['page'])
                        cite=citations.setdefault(resource['id'],{'id':resource['id'],'sha256':resource['sha256'],'observation':'Fictional source evidence','fields':[]})
                        if field not in cite['fields']:cite['fields'].append(field)
                check.update(status='pass',reason='Synthetic assertion only',evidence=list(citations.values()))
        f=self.fixture_file('check.json',record)
        configure_workspace(self.folder.parent.parent);app.record_check(self.folder,f)
    def commit_blind(self, vf):
        vr = read(vf/'run.json')
        baseline = {q['id']: q for q in read(vf/'baseline.json')['questions']}
        for bid in vr['batches']:
            batch = vf/'batches'/bid
            packet = read(batch/'input.json')
            if packet.get('stage') != 'source-reading':
                continue
            report = read(batch/'reading-template.json')
            report['reviewer'].update(id='fixture-reviewer',session_id=bid+'-synthetic-session',model='synthetic',effort='synthetic',fresh_context=True)
            for row in report['questions']:
                source = baseline[row['id']]
                row.update({k:copy.deepcopy(source[k]) for k in ('stem','options','regions')})
                ev = next(e for e in packet['evidence'] if e['source_id'] == row['source_id'] and e['page'] == int(row['number']))
                row['evidence'] = [{'path':ev['path'],'sha256':ev['sha256'],'observation':'Synthetic source reading'}]
            write(batch/'reading-response.json', report)
            verify.commit_reading(vf,bid,batch/'reading-response.json')

    def independent_reports(self):
        folder=self.folder
        app.baseline(folder)
        original=(folder/'final.json').read_bytes(); original_run=(folder/'run.json').read_bytes()
        vf=Path(verify.prepare(folder,'synthetic-review',10,'synthetic','synthetic','synthetic-coordinator',folder.parent.parent))
        self.commit_blind(vf)
        vr=read(vf/'run.json')
        for bid in vr['batches']:
            batch=vf/'batches'/bid; packet=read(batch/'input.json'); report=read(batch/'report-template.json')
            report['reviewer'].update(id='fixture-reviewer',session_id=bid+'-synthetic-session',model='synthetic',effort='synthetic',fresh_context=True)
            for row in report['questions']:
                question=next(q for q in packet['questions'] if q['id']==row['id'])
                exam_pages={r['page'] for r in question['regions']}
                exam_refs=[{'path':e['path'],'sha256':e['sha256'],'observation':'Synthetic test assertion only'} for e in packet['evidence'] if e['source_id']==question['source_id'] and e['page'] in exam_pages]
                for dimension,check in row['checks'].items():
                    required=packet.get('source_requirements',{}).get(row['id'],{}).get(dimension,[])
                    refs=exam_refs
                    if required:
                        refs=[{'path':e['path'],'sha256':e['sha256'],'observation':'Synthetic own-source assertion'} for e in packet['evidence'] if any(e['source_id']==r['source_id'] and e['page']==r['page'] for r in required)]
                    if dimension=='options':refs=[r for r in exam_refs if next(e for e in packet['evidence'] if e['path']==r['path'])['page']==int(question['number'])]
                    if dimension=='assets_math':refs=list({r['path']:r for r in exam_refs+[{'path':e['path'],'sha256':e['sha256'],'observation':'Synthetic explanation structure'} for e in packet['evidence'] if any(e['source_id']==r['source_id'] and e['page']==r['page'] for r in packet.get('source_requirements',{}).get(row['id'],{}).get('explanation',[]))]}.values())
                    if dimension=='consistency':refs=list({r['path']:r for r in exam_refs+[{'path':e['path'],'sha256':e['sha256'],'observation':'Synthetic own-source assertion'} for e in packet['evidence'] if any(e['source_id']==r['source_id'] and e['page']==r['page'] for values in packet.get('source_requirements',{}).get(row['id'],{}).values() for r in values)]}.values())
                    check.update(status='pass',reason='Synthetic pass',evidence=refs)
                evidence=exam_refs
                row['post_checks']={k:'pass' for k in app.CHECKS}
                row['independent_solution']={'label':'B','reasoning':'Fictional arithmetic fixture','evidence':evidence}
            write(batch/'report.json',report)
        verify.decisions(vf)
        decisions=read(vf/'decisions-template.json');decisions['reviewer'].update(id='fixture-coordinator',session_id='synthetic-coordinator')
        write(vf/'decisions.json',decisions)
        return vf, original, original_run
    def test_fast_key_package_reader_math_crop_and_provenance(self):
        folder=self.start(); self.route(('q1','q2'),subagents=True);self.produce(image=True)
        result=app.publish_base(folder)
        self.assertTrue(Path(result['zip']).name.startswith('m1-'))
        self.assertEqual(package_io.inspect_package(result['zip'])['questions'],2)
        final=read(folder.parent.parent/'final.json')
        self.assertEqual([q['answer']['origin'] for q in final['questions']],['answer-key']*2)
        self.assertTrue(all(q['answer']['status']=='provisional' for q in final['questions']))
        self.assertEqual(len(final['assets']),1);self.assertEqual(final['evidence'],[])
        self.assertEqual(Path(result['zip']).read_bytes(),Path(result['paessed']).read_bytes())
        import zipfile
        with zipfile.ZipFile(result['zip']) as z:self.assertFalse(any(n.endswith('.pdf') or '.work' in n for n in z.namelist()))
        with self.assertRaises(ValueError): app.publish_base(folder)
        with self.assertRaises(ValueError): app.ingest(folder,self.home/'response.json')
    def test_cli_no_key_self_fallback(self):
        self.start(solution=False);self.route();self.produce(); result=app.publish_base(self.folder)
        final=read(self.folder.parent.parent/'final.json');self.assertEqual(final['run']['review_mode'],'self')
        self.assertTrue(all(q['answer']['status']=='provisional' for q in final['questions']))
    def test_web_complete_key_needs_no_consent(self):
        self.start(host='web');self.route(('q1','q2'),host='web');self.produce();app.publish_base(self.folder)
    def test_web_no_key_accepts_experimental(self):
        self.start(host='web',solution=False)
        self.assertEqual(self.route(host='web')['status'],'needs_consent')
        self.assertFalse((self.folder/'route.json').exists())
        self.route(host='web',consent='yes');self.produce();app.publish_base(self.folder)
    def test_web_partial_decline_pending_package(self):
        self.start(host='web');self.route(('q1',),host='web',consent='no')
        self.produce(pending=('q2',));app.publish_base(self.folder)
        final=read(self.folder.parent.parent/'final.json');self.assertEqual(final['questions'][1]['answer']['status'],'missing')
    def test_partial_key_only_missing_get_independent_audit(self):
        folder=self.start();self.route(('q1',),subagents=True);self.produce()
        with self.assertRaises(ValueError):app.publish_base(folder)
        vf,original,original_run=self.independent_reports()
        self.assertEqual(read(vf/'run.json')['target_question_ids'],['q2'])
        args=argparse.Namespace(action='consolidate',run=str(vf),decisions=str(vf/'decisions.json'))
        result=app.verify_command(args); final=read(folder.parent.parent/'final.json')
        self.assertEqual([q['answer']['status'] for q in final['questions']],['provisional','verified'])
        self.assertEqual(read(vf/'metrics.json')['questions_audited'],1)
        self.assertEqual(read(folder.parent.parent/'run.json')['id'],final['run']['id'])
        self.assertEqual(result['summary']['answers_from_key'],1)
        self.assertEqual(result['summary']['independent_questions'],1)
        self.assertEqual((folder/'final.json').read_bytes(),original)
        self.assertEqual((folder/'run.json').read_bytes(),original_run)
        self.assertTrue(Path(result['zip']).is_file())
        with self.assertRaises(ValueError):app.verify_command(args)
    def test_no_key_independent_audit_all_questions(self):
        self.start(solution=False);self.route(subagents=True);self.produce()
        vf,_,_=self.independent_reports();verify.consolidate(vf,vf/'decisions.json')
        self.assertEqual(read(vf/'metrics.json')['questions_audited'],2)
        self.assertTrue(all(q['answer']['status']=='verified' for q in read(self.folder.parent.parent/'final.json')['questions']))
    def test_reused_agent_session_rejected(self):
        self.start(solution=False);self.route(subagents=True);self.produce();vf,_,_=self.independent_reports()
        p=vf/'batches/batch-01/report.json';r=read(p);r['reviewer']['session_id']='synthetic-producer';write(p,r)
        with self.assertRaisesRegex(ValueError,'Independent'):verify.load_reports(vf)
    def test_solution_explanation_provenance(self):
        self.start();f=self.fixture_file('justified-key.json',self.key(explanations=True));configure_workspace(self.folder.parent.parent)
        app.route(self.folder,f,False,None);self.produce(explanation_origin='solution');app.publish_base(self.folder)
        self.assertEqual(read(self.folder/'explanation-provenance.json')['q1']['origin'],'solution')
    def test_integrated_key_uses_exam_source(self):
        self.start(solution=False);self.route(('q1','q2'));self.produce();app.publish_base(self.folder)
        self.assertEqual(len(read(self.folder.parent.parent/'final.json')['sources']),1)
    def test_key_match_rejected(self):
        self.start()
        for status in ('ambiguous','incompatible'):
            keyfile=self.fixture_file(status+'.json',self.key(status=status));configure_workspace(self.folder.parent.parent)
            with self.assertRaises(ValueError):app.route(self.folder,keyfile,False,None)
        key=self.key();key['exam_sha256']='0'*64
        with self.assertRaises(ValueError):app.validate_key(key,read(self.folder/'candidate.json'))
    def test_key_duplicates_invalid_page_or_unknown_question(self):
        self.start();candidate=read(self.folder/'candidate.json')
        for mutation in ('duplicate','page','question'):
            key=self.key()
            if mutation=='duplicate':key['entries'].append(copy.deepcopy(key['entries'][0]))
            if mutation=='page':key['entries'][0]['page']=999
            if mutation=='question':key['entries'][0]['question_id']='not-present'
            with self.assertRaises(ValueError):app.validate_key(key,candidate)
    def test_frozen_map_route_and_source_changes_rejected(self):
        self.start();self.route(('q1','q2'));self.produce()
        p=self.folder/'route.json';r=read(p);r['review_mode']='independent';write(p,r)
        with self.assertRaises(ValueError):app.validate_for_pack(self.folder)
    def test_changed_source_blocks_resume(self):
        self.start();self.route();self.exam.write_bytes(self.exam.read_bytes()+b'\nchanged')
        with self.assertRaisesRegex(ValueError,'Source changed'):app.engine.verify_resume(self.folder)
    def test_missing_reading_or_cotejo_blocks_pack(self):
        self.start();self.route()
        with self.assertRaises((ValueError,FileNotFoundError)):app.publish_base(self.folder)
        self.produce();(self.folder/'self-checks.json').unlink()
        with self.assertRaisesRegex(ValueError,'Every question'):app.publish_base(self.folder)
    def test_partial_reading_rejected(self):
        self.start();self.route();ledger=read(self.folder/'direct-input.template.json')
        ledger.update(mode='native_pdf',reader='fixture',visual_content_understood=True,capability_observation='fixture')
        lf=self.fixture_file('partial.json',ledger);configure_workspace(self.folder.parent.parent)
        with self.assertRaises(ValueError):app.record_input(self.folder,lf)
    def test_stale_cotejo_rejected_and_recheck_recovers(self):
        self.start();self.route();self.produce();c=read(self.folder/'candidate.json')
        c['questions'][0]['stem'][0]['text']='Changed fictional wording';write(self.folder/'candidate.json',c)
        with self.assertRaisesRegex(ValueError,'Stale'):app.validate_for_pack(self.folder)
        q=c['questions'][0]
        f=self.fixture_file('curriculum-refresh.json',{'run_id':c['run']['id'],'questions':[q],
            'explanation_provenance':{'q1':{'origin':'model'}},'curriculum_provenance':{'q1':read(self.folder/'curriculum-ledger.json')['q1']}})
        configure_workspace(self.folder.parent.parent);app.ingest(self.folder,f)
        self.cotejo();app.publish_base(self.folder)
    def test_unresolved_dimension_survives_publication(self):
        self.start();self.route();self.produce()
        record=read(self.home/'check.json')
        record['questions'][0]['checks']['consistency']['status']='unresolved'
        record['questions'][0]['checks']['consistency']['reason']='Synthetic source ambiguity'
        f=self.fixture_file('pending-check.json',record)
        configure_workspace(self.folder.parent.parent);app.record_check(self.folder,f)
        result=app.publish_base(self.folder)
        quality=result['summary']['quality']
        self.assertEqual(quality['publication_eligibility'],'partial')
        self.assertTrue(any(i['code']=='COTEJO_UNRESOLVED' and i['field']=='consistency' for i in quality['issues']))
        self.assertEqual(read(self.folder.parent.parent/'final.json')['run']['quality'],quality)

    def test_frozen_option_order_after_independent_proposal(self):
        self.start(solution=False);self.route(subagents=True);self.produce()
        vf,_,_=self.independent_reports()
        report=read(vf/'batches/batch-01/report.json');row=report['questions'][0]
        original=read(vf/'baseline.json')['questions'][0]['options']
        row['changes']=[{'field':'options','before':original,'after':list(reversed(original)),
                       'reason':'Synthetic reordered proposal','evidence':row['checks']['options']['evidence']}]
        write(vf/'batches/batch-01/report.json',report)
        with self.assertRaisesRegex(ValueError,'frozen observed labels'):verify.load_reports(vf)

    def test_untouched_source_warning_survives_subset_review(self):
        self.start();self.route(('q1',),subagents=True);self.produce()
        record=read(self.home/'check.json')
        record['questions'][0]['checks']['consistency']['status']='unresolved'
        record['questions'][0]['checks']['consistency']['reason']='Synthetic unresolved original question'
        f=self.fixture_file('subset-check.json',record)
        configure_workspace(self.folder.parent.parent);app.record_check(self.folder,f)
        vf,_,_=self.independent_reports()
        verify.consolidate(vf,vf/'decisions.json')
        final=read(self.folder.parent.parent/'final.json')
        self.assertTrue(any(i['question_id']=='q1' and i['code']=='COTEJO_UNRESOLVED' for i in final['run']['quality']['issues']))
        self.assertEqual(final['run']['quality']['publication_eligibility'],'partial')

    def test_engine_cannot_mutate_finalized_candidate(self):
        self.start();self.route();self.produce();app.publish_base(self.folder)
        before=(self.folder/'candidate.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'finalized'):
            app.engine.ingest(self.folder,self.home/'response.json')
        self.assertEqual((self.folder/'candidate.json').read_bytes(),before)

    def test_fake_evidence_hash_rejected(self):
        self.start();self.route();self.produce();r=read(self.home/'check.json')
        r['questions'][0]['checks']['stem']['evidence'][0]['sha256']='0'*64
        f=self.fixture_file('bad-evidence.json',r);configure_workspace(self.folder.parent.parent)
        with self.assertRaises(ValueError):app.record_check(self.folder,f)
    def test_unverified_base_cannot_promote_status(self):
        self.start();self.route();self.produce();c=read(self.folder/'candidate.json')
        c['questions'][0]['fidelity']={'status':'reviewed','review_ref':'fake'}
        write(self.folder/'candidate.json',c)
        with self.assertRaises(ValueError):app.validate_for_pack(self.folder)
    def test_latex_and_markdown_in_text_rejected(self):
        self.start();self.route();self.produce();original=read(self.folder/'candidate.json')
        for text in (r'\sqrt{4}', '| a | b |\n| --- | --- |'):
            c=copy.deepcopy(original);c['questions'][0]['stem']=[{'type':'text','text':text}]
            with self.assertRaises(ValueError):package_io.validate(c,self.folder)
    def test_output_roots_and_spaces(self):
        with patch.object(app,'known_folder',return_value=self.home/'Redirected Documents'):
            self.assertEqual(app.output_root('documents',None),self.home/'Redirected Documents'/'EnsayosPaessedOutput')
            self.assertEqual(app.output_root('downloads',None),self.home/'Redirected Documents'/'EnsayosPaessedOutput')
        self.assertEqual(app.output_root('custom',str(self.home/'with spaces')),self.home/'with spaces')
        with self.assertRaises(ValueError):app.output_root('custom','relative')
        with self.assertRaises(ValueError):app.output_root('documents',str(self.home))
    def test_workspace_escape_and_occupied_destination(self):
        self.start()
        with self.assertRaises(ValueError):app.prepare(argparse.Namespace(
            capabilities=str(self.cap),exam=str(self.exam),solution=str(self.solution),title='Synthetic M1',run_id='run-01',
            destination='custom',output_root=str(self.home/'output'),host='cli',client='synthetic',model='synthetic',effort='synthetic',session_id='s',scale=1))
        from lab import inside
        with self.assertRaises(ValueError):inside(self.home/'outside.json')
    def test_no_visual_capability_blocks_preparation(self):
        with self.assertRaises(ValueError):app.require_capabilities({'pdf_visual':False,'observation':'Text only'})
    def test_permission_failure_does_not_choose_other_root(self):
        with patch.object(app,'known_folder',side_effect=PermissionError('Denied')):
            with self.assertRaises(PermissionError):app.output_root('documents',None)
    def test_symlink_output_rejected(self):
        link=self.home/'linked'
        try:link.symlink_to(self.home/'sources',target_is_directory=True)
        except OSError:self.skipTest('Symlink privilege unavailable')
        with self.assertRaises(ValueError):app.output_root('custom',str(link/'new'))
    def test_altered_zip_hash_rejected(self):
        self.start();self.route();self.produce();result=app.publish_base(self.folder)
        import zipfile
        damaged=self.home/'damaged.zip'
        with zipfile.ZipFile(result['zip']) as src, zipfile.ZipFile(damaged,'w') as dst:
            for name in src.namelist():dst.writestr(name,src.read(name)+(b' ' if name=='final.json' else b''))
        with self.assertRaises(ValueError):package_io.inspect_package(damaged)

    def test_cli_process_and_resume_after_publication(self):
        self.start(); self.route(('q1','q2')); self.produce(); result=app.publish_base(self.folder)
        for arguments in (['inspect','--package',result['zip']], ['resume','--run',str(self.folder)]):
            process=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/importer.py'),*arguments],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            data=json.loads(process.stdout)
            if arguments[0]=='resume': self.assertEqual(data['status'],'packaged')
    def test_visual_alternative_and_raw_key_binding(self):
        self.start(); self.route(('q1','q2'));self.produce(image=True)
        c=read(self.folder/'candidate.json')
        q=copy.deepcopy(c['questions'][0]);q['options'][1]['blocks'].append({'type':'image','asset_id':'figure','alt':'Fictional option B'})
        q['answer']={'label':'A','origin':'model','status':'provisional','source_ref':None}
        response={'run_id':c['run']['id'],'questions':[q],'explanation_provenance':{'q1':{'origin':'model'}},
            'curriculum_provenance':{'q1':read(self.folder/'curriculum-ledger.json')['q1']}}
        f=self.fixture_file('alternative.json',response); configure_workspace(self.folder.parent.parent)
        app.ingest(self.folder,f)
        self.assertEqual(read(self.folder/'candidate.json')['questions'][0]['answer']['label'],'B')
        raw=[read(p) for p in (self.folder/'raw').glob('*.json')]
        self.assertIn(response,raw)
        self.cotejo();app.publish_base(self.folder)
    def test_declined_solving_cannot_ingest_answer(self):
        self.start(host='web');self.route(('q1',),consent='no')
        with self.assertRaisesRegex(ValueError,'declined'):self.produce()
    def test_key_letter_not_in_alternatives_is_rejected(self):
        self.start();key=self.key();key['entries'][0]['label']='Z'
        f=self.fixture_file('bad-letter.json',key);configure_workspace(self.folder.parent.parent);app.route(self.folder,f,False,None)
        with self.assertRaisesRegex(ValueError,'alternatives'):self.produce()
    def test_wrong_claim_of_solution_explanation_is_rejected(self):
        self.start();self.route(('q1','q2'))
        with self.assertRaisesRegex(ValueError,'justification'):self.produce(explanation_origin='solution')
    def test_false_reading_boolean_is_rejected(self):
        self.start();self.route();ledger=read(self.folder/'direct-input.template.json')
        ledger.update(mode='native_pdf',reader='fixture',visual_content_understood='false',capability_observation='fixture')
        for s in ledger['sources']:s['pages_read']=list(range(1,next(x['page_count'] for x in read(self.folder/'sources.json') if x['id']==s['source_id'])+1))
        f=self.fixture_file('false-reading.json',ledger);configure_workspace(self.folder.parent.parent)
        with self.assertRaises(ValueError):app.record_input(self.folder,f)
    def test_changed_source_before_map_rejected(self):
        self.start();self.exam.write_bytes(self.exam.read_bytes()+b'\nchanged')
        with self.assertRaisesRegex(ValueError,'Source changed'):app.verify_pre_mapping(self.folder)
    def test_audit_target_tamper_rejected(self):
        self.start(solution=False);self.route(subagents=True);self.produce();app.baseline(self.folder)
        run=read(self.folder/'run.json');run['independent_question_ids']=['q1'];write(self.folder/'run.json',run)
        with self.assertRaisesRegex(ValueError,'selection'):verify.prepare(self.folder,'review',10,'synthetic','synthetic','coord',self.folder.parent.parent)
    def test_audit_expanded_evidence_and_stale_proposal(self):
        self.start(solution=False);self.route(subagents=True);self.produce();app.baseline(self.folder)
        vf=Path(verify.prepare(self.folder,'review',1,'synthetic','synthetic','coord',self.folder.parent.parent))
        self.assertEqual(len(read(vf/'run.json')['batches']),2)
        self.commit_blind(vf)
        before=read(vf/'batches/batch-01/input.json')
        verify.add_evidence(vf,'batch-01',[{'id':'extra','question_id':'q1','page':2,'role':'evidence','reason':'Synthetic multi-page check'}])
        after=read(vf/'batches/batch-01/input.json')
        self.assertNotEqual(app.json_digest(before),app.json_digest(after))
        self.assertTrue(list((vf/'batches/batch-01/history').glob('*.json')))
    def test_windows_junction_output_rejected(self):
        if sys.platform!='win32': self.skipTest('Windows-specific junction')
        link=self.home/'junction'
        created=subprocess.run(['cmd','/c','mklink','/J',str(link),str(self.home/'sources')],capture_output=True,text=True)
        if created.returncode: self.skipTest('Junction unavailable: '+created.stderr)
        self.assertTrue(link.is_junction())
        with self.assertRaises(ValueError):app.output_root('custom',str(link/'new'))

    def test_audit_accepted_and_rejected_corrections(self):
        for accepted in (True,False):
            self.start(solution=False,runid='accepted' if accepted else 'rejected');self.route(subagents=True);self.produce()
            vf,original,_=self.independent_reports();p=vf/'batches/batch-01/report.json';report=read(p)
            row=report['questions'][0];before=copy.deepcopy(read(vf/'baseline.json')['questions'][0]['explanation'])
            after={'blocks':[{'type':'text','text':'Fictional corrected short explanation.'}],'status':'provisional'}
            evidence=row['checks']['explanation']['evidence'];row['checks']['explanation']['status']='error'
            row['changes']=[{'field':'explanation','before':before,'after':after,'reason':'Fictional correction','evidence':evidence}]
            write(p,report)
            decision=read(vf/'decisions.json');decision['decisions']=[{'batch_id':'batch-01','question_id':'q1','field':'explanation',
                'report_sha256':digest(p),'accept':accepted,'reason':'Synthetic coordinator decision','evidence':evidence if accepted else []}]
            write(vf/'decisions.json',decision)
            if not accepted:
                with self.assertRaisesRegex(ValueError,'Critical'):
                    verify.consolidate(vf,vf/'decisions.json')
                self.assertFalse((self.folder.parent.parent/'final.json').exists())
                self.assertEqual((self.folder/'final.json').read_bytes(),original)
                continue
            verify.consolidate(vf,vf/'decisions.json')
            q=read(self.folder.parent.parent/'final.json')['questions'][0]
            self.assertEqual(q['explanation']['blocks'],after['blocks'] if accepted else before['blocks'])
            self.assertEqual(q['answer']['status'],'verified' if accepted else 'provisional')
            self.assertEqual((self.folder/'final.json').read_bytes(),original)
    def test_audit_stale_before_and_altered_baseline_rejected(self):
        self.start(solution=False);self.route(subagents=True);self.produce();vf,_,_=self.independent_reports()
        p=vf/'batches/batch-01/report.json';report=read(p);row=report['questions'][0]
        row['changes']=[{'field':'issues','before':['invented-before'],'after':['synthetic-after'],
            'reason':'Synthetic bad proposal','evidence':row['checks']['stem']['evidence']}];write(p,report)
        with self.assertRaisesRegex(ValueError,'Stale'):verify.load_reports(vf)
        (vf/'baseline.json').write_bytes((vf/'baseline.json').read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'Baseline'):verify.load_reports(vf)

if __name__ == '__main__':unittest.main(verbosity=2)
