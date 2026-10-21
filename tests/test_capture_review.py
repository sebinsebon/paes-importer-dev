"""Optional capture plumbing; synthetic receipts never establish semantic fidelity."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from support import RUNTIME_ROOT as ROOT, WORK_ROOT
from capture_review import capture_review, _local_request_allowed
from lab import configure_workspace, digest, read, write
from pipeline import content_hash, solution_hash
from test_contract_compatibility import fixture
from visual_review import PROTOCOL, validate_observation, dependency_hash


class CaptureReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.folder = Path(self.temporary.name)
        configure_workspace(self.folder)
        self.candidate = fixture()
        self.question = self.candidate['questions'][0]
        write(self.folder/'candidate.json', self.candidate)
        self.snapshot = self.folder/'reviews/snapshot'
        self.snapshot.mkdir(parents=True)
        html = self.snapshot/'index.html'
        html.write_text('<html>Fictional render</html>', encoding='utf-8')
        record = {'protocol': PROTOCOL, 'run_id': self.candidate['run']['id'],
            'questions': {self.question['id']: {
                'content_sha256': content_hash(self.question,self.candidate,self.folder),
                'solution_sha256': solution_hash(self.question,self.candidate,self.folder),
                'dependencies_sha256': dependency_hash(self.folder,self.question)}},
            'files': [{'path':html.relative_to(self.folder).as_posix(),'sha256':digest(html)}]}
        manifest = self.snapshot/'render-review.json'
        write(manifest, record)
        self.reference = {'path':manifest.relative_to(self.folder).as_posix(),'sha256':digest(manifest)}

    def tearDown(self):
        self.temporary.cleanup()

    def test_native_html_does_not_require_playwright_and_unavailable_is_pending(self):
        code = "import sys;sys.path.insert(0,sys.argv[1]);import capture_review,runtime_environment;assert not any(k.startswith('playwright') for k in sys.modules)"
        result = subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'shared/scripts')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        html = {'mode':'html','tool':'synthetic-native','observation':'Inspected fictional rendered result'}
        with self.assertRaisesRegex(ValueError, 'capture_receipt'):
            validate_observation(self.folder,html,self.reference,self.question,self.candidate)
        missing = {'mode':'unavailable','tool':'none','observation':'No HTML or image inspection tool'}
        self.assertFalse(validate_observation(self.folder,missing,self.reference,self.question,self.candidate))
        with self.assertRaisesRegex(ValueError,'tool'):
            validate_observation(self.folder,{'mode':'html'},self.reference,self.question,self.candidate)

    def test_absent_optional_dependency_preserves_limitation_without_approval(self):
        with patch('capture_review._load_playwright',side_effect=ImportError('Optional Playwright absent')):
            result = capture_review(self.folder,self.reference)
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['screenshots'],[])
        self.assertEqual(result['review_status'],'pending')
        self.assertIn('Optional Playwright absent',result['limitation'])
        observation = {'mode':'images','tool':'synthetic','observation':'Cannot inspect missing images',
                       'capture_receipt':result['capture_receipt']}
        with self.assertRaisesRegex(ValueError,'incomplete'):
            validate_observation(self.folder,observation,self.reference,self.question,self.candidate)

    def factory(self):
        owner = self
        class Locator:
            def __init__(self, selector): self.selector=selector
            def inner_text(self): return ''
            def evaluate_all(self, script): return [q['id'] for q in owner.candidate['questions']]
            def nth(self, index): return self
            def screenshot(self, **kwargs): Image.new('RGB',(12,8),'white').save(kwargs['path'])
        class Page:
            def goto(self,*args,**kwargs): owner.events.append('loaded')
            def wait_for_function(self,*args,**kwargs): owner.events.append('ready')
            def evaluate(self,script):
                if 'capture-self-test' in script:
                    return True
                owner.assertIn('document.fonts.ready',script)
                owner.assertIn('document.images',script)
                owner.events.append('fonts-and-images')
            def locator(self,selector): return Locator(selector)
        class Browser:
            version = 'synthetic'
            def new_context(self,**kwargs):
                owner.assertEqual(kwargs['service_workers'],'block')
                return self
            def route(self,*args): owner.events.append('network-filter')
            def new_page(self): return Page()
            def close(self): owner.events.append('closed')
        class Chromium:
            def launch(self,**kwargs):
                owner.assertTrue(Path(kwargs['env']['TEMP']).is_relative_to(owner.folder))
                return Browser()
        class Manager:
            chromium = Chromium()
            def __enter__(self): return self
            def __exit__(self,*args): return False
        return Manager

    def test_capture_is_bound_to_snapshot_and_changed_image_rejected(self):
        self.events=[]
        environment_before=dict(os.environ)
        with patch('capture_review._load_playwright',return_value=self.factory()):
            result=capture_review(self.folder,self.reference)
        self.assertEqual(result['status'],'captured',result.get('limitation'))
        self.assertEqual(dict(os.environ),environment_before)
        self.assertEqual(self.events,['network-filter','loaded','ready','fonts-and-images','closed'])
        observation={'mode':'images','tool':'synthetic-image-reader','observation':'Inspected fictional screenshot',
                     'capture_receipt':result['capture_receipt']}
        self.assertTrue(validate_observation(self.folder,observation,self.reference,self.question,self.candidate))
        image=self.folder/result['screenshots'][0]['path']
        image.write_bytes(image.read_bytes()+b'altered')
        with self.assertRaisesRegex(ValueError,'Altered screenshot'):
            validate_observation(self.folder,observation,self.reference,self.question,self.candidate)

    def test_snapshot_change_rejected_before_capture_output(self):
        (self.snapshot/'index.html').write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Altered source/result'):
            capture_review(self.folder,self.reference)
        self.assertFalse(list((self.folder/'reviews').glob('capture-*')))

    def test_external_requests_and_files_outside_snapshot_are_blocked(self):
        self.assertTrue(_local_request_allowed((self.snapshot/'index.html').as_uri(),self.snapshot))
        self.assertFalse(_local_request_allowed('https://example.invalid/script.js',self.snapshot))
        self.assertFalse(_local_request_allowed((self.folder/'candidate.json').as_uri(),self.snapshot))


@unittest.skipUnless(os.environ.get('PAES_TEST_BROWSER'), 'Set PAES_TEST_BROWSER to an existing browser for opt-in capture')
class ActualBrowserCaptureTests(unittest.TestCase):
    def test_generated_review_captures_real_render_and_validates_receipt(self):
        self.assert_capture('file')

    def test_memory_transport_captures_real_math_images_and_fonts(self):
        self.assert_capture('memory')

    def assert_capture(self, transport):
        import test_importer as fixtures
        import importer as app
        producer = fixtures.ImporterTests()
        producer.setUp()
        try:
            folder = producer.start()
            producer.route(('q1','q2'))
            producer.produce(image=True)
            configure_workspace(folder.parent.parent)
            reference = app.check_template(folder)['questions'][0]['render_review']
            result = capture_review(folder, reference, executable_path=os.environ['PAES_TEST_BROWSER'], transport=transport)
            self.assertEqual(result['status'], 'captured', result.get('limitation'))
            self.assertEqual(result['transport'], transport)
            self.assertEqual(len(result['screenshots']), 2)
            candidate = read(folder/'candidate.json')
            for screenshot, question in zip(result['screenshots'], candidate['questions']):
                image = folder/screenshot['path']
                self.assertEqual(digest(image), screenshot['sha256'])
                self.assertGreater(image.stat().st_size, 1000)
                self.assertGreater(min(screenshot['size']), 100)
                observation = {'mode':'images', 'tool':'existing-browser-and-synthetic-image-check',
                    'observation':'Generated fictional source/result capture inspected only by image-format checks; no fidelity claim',
                    'capture_receipt':result['capture_receipt']}
                self.assertTrue(validate_observation(folder, observation, reference, question, candidate))
            self.assertEqual(result['review_status'], 'pending')
            self.assertEqual(result['certification'], 'not_performed')
        finally:
            producer.tearDown()


if __name__ == '__main__':
    unittest.main()
