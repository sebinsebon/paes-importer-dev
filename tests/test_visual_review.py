"""Synthetic source/result review binding and publication policy."""
import copy
import json
import unittest
import test_importer as fixtures
import importer as app
from lab import configure_workspace, read, write
from visual_review import create_review, validate_review


class VisualReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ImporterTests()
        self.fixture.setUp()
        self.folder = self.fixture.start()
        self.fixture.route(('q1','q2'))
        self.fixture.produce(image=True)
        configure_workspace(self.folder.parent.parent)

    def tearDown(self): self.fixture.tearDown()

    def test_review_contains_solution_page_crop_and_inventory(self):
        reference = app.check_template(self.folder)['questions'][0]['render_review']
        manifest = read(self.folder/reference['path'])
        paths = [f['path'] for f in manifest['files']]
        self.assertTrue(any(p.endswith('index.html') for p in paths))
        directory = (self.folder/reference['path']).parent
        inventory = read(directory/'review-inventory.json')
        self.assertIn({'source_id':'solution','page':1}, inventory['question_pages']['q1'])
        self.assertEqual(len(inventory['requirements']['q1']), 2)
        html = (directory/'index.html').read_text(encoding='utf-8')
        self.assertIn("outline(a,'asset'", html)
        self.assertIn("img.src=a.path", html)
        self.assertTrue((directory/'assets/crops/figure.png').exists())

    def test_changed_question_requires_new_preview(self):
        candidate = read(self.folder/'candidate.json')
        reference = app.check_template(self.folder)['questions'][0]['render_review']
        candidate['questions'][0]['stem'][0]['text'] = 'Changed fictional wording'
        with self.assertRaisesRegex(ValueError,'Stale render review'):
            validate_review(self.folder, reference, candidate['questions'][0], candidate)
        # Unchanged questions retain their old preview.
        validate_review(self.folder, reference, candidate['questions'][1], candidate)

    def test_changed_crop_geometry_invalidates_preview(self):
        candidate = read(self.folder/'candidate.json')
        reference = app.check_template(self.folder)['questions'][0]['render_review']
        candidate['assets'][0]['bbox'][0] += 1
        with self.assertRaisesRegex(ValueError,'Stale render review'):
            validate_review(self.folder, reference, candidate['questions'][0], candidate)

    def test_changed_asset_bytes_rejected(self):
        candidate = read(self.folder/'candidate.json')
        reference = app.check_template(self.folder)['questions'][0]['render_review']
        asset = self.folder/candidate['assets'][0]['path']
        asset.write_bytes(asset.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError,'Asset bytes differ'):
            validate_review(self.folder, reference, candidate['questions'][0], candidate)

    def test_recheck_only_changed_question_keeps_other_cotejos(self):
        original = read(self.fixture.home/'check.json')
        response = read(self.fixture.home/'response.json')
        response['questions'] = [response['questions'][0]]
        response['questions'][0]['stem'][0]['text'] = 'Changed fictional wording'
        request = self.fixture.fixture_file('changed-question.json', response)
        configure_workspace(self.folder.parent.parent)
        self.assertEqual(app.ingest(self.folder, request)['accepted'], ['q1'])
        create_review(self.folder)
        refreshed = app.check_template(self.folder)
        row = refreshed['questions'][0]
        row['checks'] = copy.deepcopy(original['questions'][0]['checks'])
        refreshed['questions'] = [row]
        request = self.fixture.fixture_file('changed-cotejo.json', refreshed)
        configure_workspace(self.folder.parent.parent)
        app.record_check(self.folder, request)
        app.publish_base(self.folder)

    def test_changed_preview_files_rejected(self):
        record = read(self.fixture.home/'check.json')
        reference = record['questions'][0]['render_review']
        html = (self.folder/reference['path']).parent/'index.html'
        html.write_text('Altered preview', encoding='utf-8')
        request = self.fixture.fixture_file('altered.json', record)
        configure_workspace(self.folder.parent.parent)
        with self.assertRaisesRegex(ValueError,'Altered source/result preview'):
            app.record_check(self.folder, request)

    def test_missing_preview_reference_rejected(self):
        record = read(self.fixture.home/'check.json')
        record['questions'][0].pop('render_review')
        request = self.fixture.fixture_file('missing-preview.json', record)
        configure_workspace(self.folder.parent.parent)
        with self.assertRaisesRegex(ValueError,'Run review'):
            app.record_check(self.folder, request)

    def test_complete_key_unresolved_cannot_publish(self):
        record = read(self.fixture.home/'check.json')
        record['questions'][0]['checks']['assets_math'].update(status='unresolved', reason='Unreadable fictional label')
        request = self.fixture.fixture_file('unresolved.json', record)
        configure_workspace(self.folder.parent.parent)
        app.record_check(self.folder, request)
        with self.assertRaisesRegex(ValueError,'pending source cotejos'):
            app.publish_base(self.folder)
        self.assertFalse((self.folder.parent.parent/'final.json').exists())
        self.fixture.cotejo()
        result = app.publish_base(self.folder)
        self.assertEqual(result['summary']['quality']['publication_eligibility'], 'complete')
        self.assertEqual(result['summary']['answers_verified_by_ai'], 0)


class MultiPageSolutionTests(unittest.TestCase):
    def test_all_solution_pages_are_shown_and_citable(self):
        fixture = fixtures.ImporterTests()
        fixture.setUp()
        try:
            fixtures.synthetic.pdf(fixture.solution, ['BT /F1 12 Tf 20 370 Td (Key: 1 B, 2 B) Tj ET',
                                                    'BT /F1 12 Tf 20 370 Td (Continued explanation) Tj ET'])
            folder = fixture.start()
            key = fixture.key(explanations=True)
            key['entries'][0]['pages'] = [1,2]
            request = fixture.fixture_file('multipage-key.json', key)
            configure_workspace(folder.parent.parent)
            app.route(folder, request, False, None)
            fixture.produce(explanation_origin='solution')
            record = app.check_template(folder)
            reference = record['questions'][0]['render_review']
            inventory = read((folder/reference['path']).parent/'review-inventory.json')
            self.assertIn({'source_id':'solution','page':2}, inventory['question_pages']['q1'])
            cotejo = read(fixture.home/'check.json')
            candidate = read(folder/'candidate.json')
            resource = next(e for e in candidate['evidence'] if e['source_id']=='solution' and e['page']==2)
            for dimension in ('answer','explanation'):
                cite = cotejo['questions'][0]['checks'][dimension]['evidence'][0]
                cite.update(id=resource['id'], sha256=resource['sha256'])
            request = fixture.fixture_file('multipage-cotejo.json', cotejo)
            configure_workspace(folder.parent.parent)
            app.record_check(folder, request)
            app.publish_base(folder)
            invalid = copy.deepcopy(key)
            invalid['entries'][0]['pages'] = [2,2]
            with self.assertRaisesRegex(ValueError,'Key pages'):
                app.validate_key(invalid, candidate)
        finally:
            fixture.tearDown()


if __name__ == '__main__': unittest.main()
