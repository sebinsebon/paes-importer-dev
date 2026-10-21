"""Synthetic recovery archives, portable source paths and continuation repairs."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from support import RUNTIME_ROOT, WORK_ROOT
sys.path.insert(0, str(RUNTIME_ROOT/'shared/scripts'))
from lab import configure_workspace, digest, json_digest, read, write
from checkpoint_export import export_checkpoint, resolve_sources
from adopt_checkpoint import adopt
from provenance_repair import repair


class CheckpointOptimizationTests(unittest.TestCase):
    def setUp(self):
        WORK_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.home = Path(self.temp.name)
        configure_workspace(self.home)
        self.root = self.home/'fictional-run'
        self.folder = self.root/'.work/base'
        self.folder.mkdir(parents=True)
        self.pdf = self.home/'fictional.pdf'
        self.pdf.write_bytes(b'%PDF-1.7 synthetic source, not private content')
        self.sources = [{'id':'exam', 'sha256':digest(self.pdf), 'page_count':8}]
        self.legacy = self.make_runtime('legacy', '1.4.1-portable')
        self.current = self.make_runtime('current', '1.5.0-portable')
        config = {'batch_size':5}
        self.run = {'id':self.root.name, 'protocol_version':'0.4.0', 'config':config,
                    'config_hash':json_digest(config), 'status':'awaiting_ai',
                    'release_sha256':digest(self.legacy/'release.json'), 'output_dir':str(self.root),
                    'route_hash':'prior'}
        self.candidate = {'run':{'answer_key_sha256':'prior'}, 'sources':self.sources,
                          'questions':[{'id':'q1','stem':[{'type':'text','text':'Fictional original'}]},
                                       {'id':'q2','stem':[]}]}
        write(self.folder/'run.json', self.run)
        write(self.folder/'candidate.json', self.candidate)
        write(self.folder/'sources.json', self.sources)
        write(self.folder/'sources.local.json', {'exam':str(self.pdf)})

    def tearDown(self):
        self.temp.cleanup()

    def make_runtime(self, name, version):
        root = self.home/name
        (root/'scripts').mkdir(parents=True)
        (root/'shared/scripts').mkdir(parents=True)
        # A minimal deterministic legacy host exercises real subprocess transport
        # and relocation. Real contract/transaction tests live in existing suites.
        (root/'scripts/importer.py').write_text(
            "import json,sys,pathlib\np=pathlib.Path(sys.argv[sys.argv.index('--run')+1])/'.work/base'\n"
            "s=json.loads((p/'sources.local.json').read_text())\nassert all((pathlib.Path(v) if pathlib.Path(v).is_absolute() else p.parent.parent/v).is_file() for v in s.values())\n"
            "print(json.dumps({'accepted_question_ids':['q1'],'pending_question_ids':['q2']}))\n")
        (root/'shared/scripts/pipeline.py').write_text('# synthetic pinned implementation\n')
        files = [{'path':name, 'sha256':digest(root/name)} for name in
                 ('scripts/importer.py','shared/scripts/pipeline.py')]
        write(root/'release.json', {'version':version,'protocol_version':'0.4.0','files':files})
        return root

    def archive(self, name='checkpoint.zip'):
        target = self.home/name
        export_checkpoint(self.folder, target)
        return target

    def test_partial_roundtrip_preserves_content_and_portable_sources(self):
        before = (self.folder/'candidate.json').read_bytes()
        archive = self.archive()
        self.pdf.unlink()  # Restoring never depends on the original host's paths.
        target = self.home/'restored'
        result = adopt(archive, self.legacy, target, self.current/'release.json')
        self.assertEqual(result['adoption']['accepted_question_ids'], ['q1'])
        base = target/'.work/base'
        self.assertEqual(before, (base/'candidate.json').read_bytes())
        self.assertFalse(Path(read(base/'sources.local.json')['exam']).is_absolute())
        self.assertTrue(Path(resolve_sources(base)['exam']).is_file())
        self.assertEqual(read(base/'run.json')['output_dir'], str(target))
        with self.assertRaisesRegex(ValueError, 'NEW'):
            adopt(archive, self.legacy, target, self.current/'release.json')

    def test_export_follows_current_capture_and_drops_unreferenced_review(self):
        write(self.folder/'reviews/live/render-review.json', {'files':[{'path':'reviews/live/index.html'}]})
        (self.folder/'reviews/live/index.html').write_text('<html>fictional preview</html>')
        write(self.folder/'reviews/old/render-review.json', {'obsolete':True})
        write(self.folder/'render-reviews.json', {'q1':{'path':'reviews/live/render-review.json'}})
        with zipfile.ZipFile(self.archive()) as archive:
            names = archive.namelist()
        self.assertTrue(any(n.endswith('reviews/live/index.html') for n in names))
        self.assertFalse(any('reviews/old/' in n for n in names))
        self.assertTrue((self.folder/'reviews/old/render-review.json').is_file())

    def test_default_run_workspace_can_export_to_explicit_external_filename(self):
        configure_workspace(self.root)
        write(self.folder/'cache/rendered.json', {'duplicate':True})
        write(self.folder/'startup-probe/nested/.runtime/host.json', {'temporary':True})
        archive = self.archive('external.zip')
        with zipfile.ZipFile(archive) as handle:
            self.assertFalse(any('/cache/' in name for name in handle.namelist()))
            self.assertFalse(any('/.runtime/' in name for name in handle.namelist()))
        with self.assertRaisesRegex(ValueError, 'new filename'):
            self.archive('external.zip')

    def test_cli_exports_outside_its_automatically_selected_workspace(self):
        output = self.home/'cli-export.zip'
        result = subprocess.run([sys.executable, '-B', str(RUNTIME_ROOT/'scripts/importer.py'),
                                 'export-checkpoint','--run',str(self.root),'--output',str(output)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['self_contained'])
        self.assertTrue(output.is_file())

    def test_startup_probe_subrun_exports_with_its_relative_receipts(self):
        from capture_review import startup_probe
        configure_workspace(self.root)
        with patch('capture_review._load_playwright', side_effect=ImportError('synthetic browser absent')):
            result = startup_probe(self.folder)
        self.assertEqual(result['status'], 'unavailable')
        write(self.folder/'capabilities-probe.json', result)
        output = self.home/'cli-probe-export.zip'
        checked = subprocess.run([sys.executable, '-B', str(RUNTIME_ROOT/'scripts/importer.py'),
                                  'export-checkpoint','--run',str(self.root),'--output',str(output)],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertTrue(any('/startup-probe-' in p and p.endswith('/reviews/probe/index.html') for p in names))
            self.assertTrue(any('/startup-probe-' in p and p.endswith('/capture-manifest.json') for p in names))
            self.assertFalse(any('/.runtime/' in p for p in names))

    def test_original_non_json_transport_is_retained_as_audit_bytes(self):
        path = self.folder/'raw/original.json'
        path.parent.mkdir()
        path.write_bytes(b'```json\n{"questions":[]}\n```')
        with zipfile.ZipFile(self.archive()) as archive:
            self.assertEqual(archive.read(self.root.name+'/.work/base/raw/original.json'), path.read_bytes())

    def test_current_resume_rejection_retains_staging_without_final_directory(self):
        path = self.current/'scripts/importer.py'
        path.write_text("raise SystemExit('synthetic incompatible resume')\n")
        release = read(self.current/'release.json')
        release['files'][0]['sha256'] = digest(path)
        write(self.current/'release.json', release)
        with self.assertRaisesRegex(ValueError, 'Current resume rejected'):
            adopt(self.archive(), self.legacy, self.home/'incompatible', self.current/'release.json')
        self.assertFalse((self.home/'incompatible').exists())
        self.assertTrue(list(self.home.glob('incompatible.adoption-*')))

    def test_source_and_runtime_tampering_fail_before_adoption(self):
        self.pdf.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'altered source'):
            self.archive()
        self.pdf.write_bytes(b'%PDF-1.7 synthetic source, not private content')
        archive = self.archive()
        (self.current/'shared/scripts/pipeline.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'manifest failed'):
            adopt(archive, self.legacy, self.home/'rejected', self.current/'release.json')

    def test_zip_traversal_and_case_collisions_rejected(self):
        for index, entries in enumerate((['fictional-run/../escape'], ['fictional-run/a','fictional-run/A'])):
            path = self.home/('unsafe'+str(index)+'.zip')
            with zipfile.ZipFile(path, 'w') as archive:
                for name in entries:
                    archive.writestr(name, 'bad')
            with self.assertRaises(ValueError):
                adopt(path, self.legacy, self.home/('bad'+str(index)), self.current/'release.json')
        self.assertFalse((self.home/'escape').exists())

    def test_portable_registry_traversal_rejected(self):
        write(self.folder/'sources.local.json', {'exam':'../fictional.pdf'})
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'):
            resolve_sources(self.folder)

    def test_checkpoint_inventory_detects_candidate_tampering(self):
        original = self.archive()
        altered = self.home/'altered.zip'
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(altered, 'w') as target:
            for item in source.infolist():
                payload = source.read(item)
                if item.filename.endswith('candidate.json'):
                    payload = payload.replace(b'Fictional original', b'Rewritten material')
                target.writestr(item, payload)
        with self.assertRaisesRegex(ValueError, 'file hash mismatch'):
            adopt(altered, self.legacy, self.home/'badcontent', self.current/'release.json')

    def prepare_continuations(self):
        entry = {'question_id':'q1','source_id':'exam','page':2,'pages':[2],
                 'label':'B','has_explanation':True,'content_inventory':[]}
        key = {'entries':[entry]}
        write(self.folder/'route.json', {'processing_mode':'answer-key','answer_key':key})
        write(self.folder/'answer-key-map.json', key)
        write(self.folder/'selection.json', {'expected_questions':[{'id':'q1'},{'id':'q2'}]})
        write(self.folder/'explanation-provenance.json', {'q1':{'origin':'solution','source_id':'exam','page':2,'pages':[2]}})
        write(self.folder/'self-checks.json', {'q1':{'prior':True},'q2':{'keep':True}})
        write(self.folder/'render-reviews.json', {'q1':{'prior':True},'q2':{'keep':True}})
        resources = []
        proof = []
        for page in (3,4,6,7):
            image = self.folder/('evidence/page-'+str(page)+'.png')
            image.parent.mkdir(exist_ok=True)
            image.write_bytes(b'fictional rendered page '+str(page).encode())
            item = {'id':'page-'+str(page), 'source_id':'exam','page':page,
                    'path':image.relative_to(self.folder).as_posix(),'sha256':digest(image)}
            resources.append(item)
            proof.append({'source_id':'exam','page':page,'evidence_id':item['id'],
                          'sha256':item['sha256'],'observation':'The original development continues on this physical page.'})
        write(self.folder/'catalog.json', {'evidence':resources})
        return {'reason':'Observed continuation pages in the original integrated exam source.',
                'changes':[{'question_id':'q1','old_pages':[2],'add_pages':[3,4,6,7],
                            'reason':'The source continues this development beyond the primary page.', 'evidence':proof}]}

    def apply_repair(self, request):
        return repair(self.folder, request, ensure_editable=lambda f:None,
                      frozen_route=lambda f:read(f/'route.json'), validate_key=lambda k,c:None,
                      observed_inventory=lambda q,k:q, validate_inventory_record=lambda q,c:None)

    def test_integrated_source_unbounded_documented_continuation_and_selective_invalidation(self):
        request = self.prepare_continuations()
        original_questions = copy.deepcopy(self.candidate['questions'])
        self.apply_repair(request)
        entry = read(self.folder/'answer-key-map.json')['entries'][0]
        self.assertEqual(entry['pages'], [2,3,4,6,7])
        self.assertEqual((entry['source_id'],entry['page'],entry['label']), ('exam',2,'B'))
        self.assertEqual(read(self.folder/'candidate.json')['questions'], original_questions)
        self.assertEqual(read(self.folder/'self-checks.json'), {'q2':{'keep':True}})
        self.assertEqual(read(self.folder/'render-reviews.json'), {'q2':{'keep':True}})
        self.assertTrue(list((self.folder/'versions').glob('provenance-*')))

    def test_partial_key_modes_allow_continuation_repairs(self):
        for mode in ('mixed', 'partial-pending'):
            request = self.prepare_continuations()
            decision = read(self.folder/'route.json')
            decision['processing_mode'] = mode
            write(self.folder/'route.json', decision)
            self.apply_repair(request)
            self.assertEqual(read(self.folder/'explanation-provenance.json')['q1']['pages'], [2,3,4,6,7])

    def test_stale_or_wrong_source_proof_is_atomic_failure(self):
        for defect in ('stale', 'source'):
            request = self.prepare_continuations()
            if defect == 'stale':
                request['changes'][0]['old_pages'] = [1]
            else:
                request['changes'][0]['evidence'][0]['source_id'] = 'solution'
            before = (self.folder/'candidate.json').read_bytes()
            with self.assertRaises(ValueError):
                self.apply_repair(request)
            self.assertEqual(before, (self.folder/'candidate.json').read_bytes())
            self.assertIn('q1', read(self.folder/'self-checks.json'))


if __name__ == '__main__':
    unittest.main()
