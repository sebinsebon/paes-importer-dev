"""Synthetic regressions for observable, current, incremental visual evidence."""
import copy
import unittest
from unittest.mock import patch

import test_capture_review as captures
import test_visual_review as reviews
from lab import configure_workspace, digest, read, write
from visual_review import create_review, validate_observation, validate_review
from capture_review import capture_review, startup_probe, record_browser_capture, validate_capture


class VisualEvidenceTests(unittest.TestCase):
    setUp = captures.CaptureReviewTests.setUp
    tearDown = captures.CaptureReviewTests.tearDown
    factory = captures.CaptureReviewTests.factory
    def test_textual_html_read_cannot_establish_visual_observation(self):
        observation = {'mode': 'html', 'tool': 'read_file', 'observation': 'Read HTML source'}
        with self.assertRaisesRegex(ValueError, 'visual artifact|capture_receipt'):
            validate_observation(self.folder, observation, self.reference, self.question, self.candidate)

    def test_capture_selection_rejects_unknown_question_before_output(self):
        with self.assertRaisesRegex(ValueError, 'Unknown question'):
            capture_review(self.folder, self.reference, question_ids=['missing'])
        self.assertFalse(list((self.folder/'reviews').glob('capture-*')))

    def test_capture_resume_preserves_valid_existing_images(self):
        self.events = []
        with patch('capture_review._load_playwright', return_value=self.factory()):
            first = capture_review(self.folder, self.reference)
        image = self.folder/first['screenshots'][0]['path']
        original = image.stat().st_mtime_ns
        with patch('capture_review._load_playwright', side_effect=AssertionError('No browser needed')):
            resumed = capture_review(self.folder, self.reference, resume_receipt=first['capture_receipt'])
        self.assertEqual(resumed['status'], 'captured')
        self.assertEqual(image.stat().st_mtime_ns, original)

    def test_pending_capture_reuses_valid_receipt_without_browser(self):
        self.events = []
        with patch('capture_review._load_playwright', return_value=self.factory()):
            first = capture_review(self.folder, self.reference)
        with patch('capture_review._load_playwright', side_effect=AssertionError('No browser needed')):
            result = capture_review(self.folder, self.reference, pending=True)
        self.assertEqual(first['capture_receipt'], result['capture_receipt'])

    def test_startup_probe_missing_browser_is_unavailable_and_archived(self):
        with patch('capture_review._load_playwright', side_effect=ImportError('Optional browser absent')):
            result = startup_probe(self.folder)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['review_status'], 'pending')
        path = self.folder/result['capture_receipt']['path']
        self.assertEqual(digest(path), result['capture_receipt']['sha256'])

    def test_external_browser_artifact_is_bound_and_altered_bytes_rejected(self):
        from PIL import Image
        image = self.folder/'browser.png'
        Image.new('RGB', (24, 32), 'white').save(image)
        receipt = record_browser_capture(self.folder, self.reference, self.question['id'], image,
            tool='fictional browser screenshot', observation='Synthetic attributed artifact')
        observation = {'mode':'html','tool':'fictional browser screenshot',
            'observation':'Inspected fictional artifact','capture_receipt':receipt}
        self.assertTrue(validate_observation(self.folder, observation, self.reference, self.question, self.candidate))
        record = validate_capture(self.folder, receipt, self.reference, self.question['id'])
        archived = self.folder/record['screenshots'][0]['path']
        archived.write_bytes(archived.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'Altered screenshot'):
            validate_observation(self.folder, observation, self.reference, self.question, self.candidate)

    def test_external_browser_artifact_rejects_truncated_png_header(self):
        import struct
        image = self.folder/'truncated.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 20, 20))
        with self.assertRaisesRegex(ValueError, 'cannot be decoded'):
            record_browser_capture(self.folder, self.reference, self.question['id'], image,
                tool='fictional screenshot tool', observation='A truncated image cannot be inspected')
        self.assertFalse(list((self.folder/'reviews').glob('browser-capture-*')))

    def test_resume_creates_immutable_new_receipt_and_preserves_existing_observation(self):
        from visual_review import question_binding
        second = copy.deepcopy(self.question); second['id'] = 'q2'; second['number'] = '2'
        self.candidate['questions'].append(second)
        write(self.folder/'candidate.json', self.candidate)
        record = read(self.snapshot/'render-review.json')
        record['questions']['q2'] = question_binding(self.folder, second, self.candidate)
        write(self.snapshot/'render-review.json', record)
        self.reference['sha256'] = digest(self.snapshot/'render-review.json')
        self.events = []
        with patch('capture_review._load_playwright', return_value=self.factory()):
            first = capture_review(self.folder, self.reference, question_ids=[self.question['id']])
            original_manifest = (self.folder/first['capture_receipt']['path']).read_bytes()
            resumed = capture_review(self.folder, self.reference, resume_receipt=first['capture_receipt'])
        self.assertNotEqual(first['capture_receipt']['path'], resumed['capture_receipt']['path'])
        self.assertEqual(original_manifest, (self.folder/first['capture_receipt']['path']).read_bytes())
        observation = {'mode':'images','tool':'synthetic reader','observation':'Fictional screenshot',
                       'capture_receipt':first['capture_receipt']}
        self.assertTrue(validate_observation(self.folder, observation, self.reference, self.question, self.candidate))
        self.assertEqual({item['question_id'] for item in resumed['screenshots']}, {self.question['id'], 'q2'})

    def test_auto_resume_of_memory_capture_retries_blocked_file_transport(self):
        from visual_review import question_binding
        second = copy.deepcopy(self.question); second['id'] = 'q2'; second['number'] = '2'
        self.candidate['questions'].append(second)
        write(self.folder/'candidate.json', self.candidate)
        record = read(self.snapshot/'render-review.json')
        record['questions']['q2'] = question_binding(self.folder, second, self.candidate)
        write(self.snapshot/'render-review.json', record)
        self.reference['sha256'] = digest(self.snapshot/'render-review.json')
        factory = self.factory()
        class Manager(factory):
            def __enter__(self):
                manager = super().__enter__(); original = manager.chromium.launch
                def launch(**kwargs):
                    browser = original(**kwargs); create_page = browser.new_page
                    browser.unroute = lambda *args:None
                    def new_page():
                        page = create_page()
                        def blocked(*args, **kwargs):raise RuntimeError('ERR_BLOCKED_BY_ADMINISTRATOR')
                        page.goto = blocked
                        page.set_content = lambda *args,**kwargs:None
                        return page
                    browser.new_page = new_page
                    return browser
                manager.chromium.launch = launch
                return manager
        self.events = []
        with patch('capture_review._load_playwright', return_value=Manager):
            first = capture_review(self.folder, self.reference, question_ids=[self.question['id']], transport='memory')
            resumed = capture_review(self.folder, self.reference, resume_receipt=first['capture_receipt'])
        self.assertEqual(resumed['status'], 'captured', resumed.get('limitation'))
        self.assertEqual(resumed['transport'], 'memory')
        self.assertEqual(len(resumed['screenshots']), 2)

    def test_auto_fallback_when_file_navigation_succeeds_but_image_is_blocked(self):
        factory = self.factory(); owner = self
        class Manager(factory):
            def __enter__(self):
                manager = super().__enter__(); launch = manager.chromium.launch
                def create_browser(**kwargs):
                    browser = launch(**kwargs); original = browser.new_page
                    browser.unroute = lambda *args:None
                    def create_page():
                        page = original(); evaluate = page.evaluate; page.memory_loaded = False
                        def set_content(html, **kwargs):page.memory_loaded = True
                        page.set_content = set_content
                        def checked(script):
                            if 'document.fonts.ready' in script and not page.memory_loaded:
                                raise RuntimeError('Image not rendered')
                            return evaluate(script)
                        page.evaluate = checked
                        return page
                    browser.new_page = create_page
                    return browser
                manager.chromium.launch = create_browser
                return manager
        self.events = []
        with patch('capture_review._load_playwright', return_value=Manager):
            result = capture_review(self.folder, self.reference)
        self.assertEqual(result['status'], 'captured', result.get('limitation'))
        self.assertEqual(result['transport'], 'memory')


class IncrementalReviewTests(unittest.TestCase):
    setUp = reviews.VisualReviewTests.setUp
    tearDown = reviews.VisualReviewTests.tearDown
    def test_selected_review_preserves_untouched_reference_and_reuses_page_cache(self):
        before = read(self.folder/'render-reviews.json')
        candidate = read(self.folder/'candidate.json')
        candidate['questions'][0]['stem'][0]['text'] = 'Changed fictional wording'
        write(self.folder/'candidate.json', candidate)
        configure_workspace(self.folder.parent.parent)
        with patch('source_review.render_crop', side_effect=AssertionError('Page should be cached')):
            result = create_review(self.folder, question_ids=['q1'])
        after = read(self.folder/'render-reviews.json')
        self.assertEqual(after['q2'], before['q2'])
        self.assertNotEqual(after['q1'], before['q1'])
        self.assertEqual(result['questions'], 1)
        validate_review(self.folder, after['q2'], candidate['questions'][1], candidate)

    def test_mapping_change_invalidates_only_affected_question(self):
        candidate = read(self.folder/'candidate.json')
        references = read(self.folder/'render-reviews.json')
        selection = read(self.folder/'selection.json')
        selection['expected_questions'][0]['content_inventory'][0]['symbols'] = ['z']
        write(self.folder/'selection.json', selection)
        with self.assertRaisesRegex(ValueError, 'Stale render review'):
            validate_review(self.folder, references['q1'], candidate['questions'][0], candidate)
        validate_review(self.folder, references['q2'], candidate['questions'][1], candidate)

    def test_source_renderer_or_katex_fonts_invalidate_review(self):
        from pathlib import Path
        from support import RUNTIME_ROOT
        import visual_review
        candidate = read(self.folder/'candidate.json')
        reference = read(self.folder/'render-reviews.json')['q1']
        original = visual_review.digest
        for target in ('pdf_assets.py', 'fonts'):
            def changed(path):
                path = Path(path)
                if path.is_relative_to(RUNTIME_ROOT) and (path.name==target or target in path.parts):
                    return 'f'*64
                return original(path)
            with self.subTest(target=target), patch('visual_review.digest', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'Stale render review'):
                    validate_review(self.folder, reference, candidate['questions'][0], candidate)

    def test_pdfium_version_invalidates_review_and_renderer_tree_is_cached_per_operation(self):
        import visual_review
        import pypdfium2 as pdfium
        candidate = read(self.folder/'candidate.json')
        reference = read(self.folder/'render-reviews.json')['q1']
        with patch.object(pdfium, 'PDFIUM_INFO', 'synthetic-new-renderer'):
            with self.assertRaisesRegex(ValueError, 'Stale render review'):
                validate_review(self.folder, reference, candidate['questions'][0], candidate)
        cache = {}
        with patch('visual_review.digest', wraps=visual_review.digest) as hashed:
            visual_review.dependency_hash(self.folder, candidate['questions'][0], cache)
            first = hashed.call_count
            visual_review.dependency_hash(self.folder, candidate['questions'][1], cache)
            self.assertEqual(hashed.call_count, first)


if __name__ == '__main__':
    unittest.main()
