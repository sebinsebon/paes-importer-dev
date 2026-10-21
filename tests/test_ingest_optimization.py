"""Per-operation validation reuse never replaces global or final validation."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_recovery as recovery_fixtures
import package_io
import pipeline
from lab import digest, read, write


class IngestOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = recovery_fixtures.RecoveryTests()
        self.fixture.setUp()
        self.folder = self.fixture.folder

    def tearDown(self):
        self.fixture.tearDown()

    def map_inputs(self):
        write(self.folder/'catalog.json', {'pages':[{'source_id':'source','page':i,'width':100,'height':100} for i in (1,2)]})
        write(self.folder/'selection.json', {'expected_questions':[
            {'id':'q'+str(i),'source_id':'source','number':str(i),'page':i,
             'option_labels':['A','B'],'regions':[{'page':i,'bbox':[0,0,50,50]}]} for i in (1,2)]})

    def test_projects_only_question_but_validates_full_before_and_after(self):
        self.map_inputs()
        original_read = pipeline.read
        reads = []
        def observe_read(path):
            reads.append(Path(path).name)
            return original_read(path)
        original_validate = pipeline.validate
        sizes = []
        def observe_validate(data, *args, **kwargs):
            sizes.append(len(data['questions']))
            return original_validate(data, *args, **kwargs)
        with patch.object(pipeline, 'read', side_effect=observe_read), patch.object(pipeline, 'validate', side_effect=observe_validate):
            result = self.fixture.ingest([self.fixture.question(0), self.fixture.question(1)])
        self.assertEqual(result['accepted'], ['q1','q2'])
        self.assertEqual(sizes, [2,1,1,2])
        self.assertEqual(reads.count('catalog.json'), 1)
        self.assertEqual(reads.count('selection.json'), 1)

    def test_cross_question_identity_conflict_rejects_only_proposed_question(self):
        first = self.fixture.question(0)
        conflicting = self.fixture.question(1)
        conflicting['number'] = first['number']
        result = self.fixture.ingest([first, conflicting])
        self.assertEqual(result['accepted'], ['q1'])
        self.assertEqual(result['rejected'][0]['question_id'], 'q2')
        saved = read(self.folder/'candidate.json')
        self.assertEqual(saved['questions'][1], self.fixture.data['questions'][1])
        self.assertEqual(saved['questions'][0]['number'], '1')

    def resource(self):
        from PIL import Image
        path = self.folder/'assets/fictional.png'
        path.parent.mkdir()
        Image.new('RGB', (5,5), 'white').save(path)
        item = {'id':'fictional','source_id':'source','page':1,'bbox':[0,0,5,5],
                'path':'assets/fictional.png','sha256':digest(path),'mime':'image/png'}
        data = read(self.folder/'candidate.json')
        data['assets'] = [item]
        write(self.folder/'candidate.json', data)
        return path

    def test_fresh_final_validation_detects_bytes_changed_during_operation(self):
        resource = self.resource()
        before = (self.folder/'candidate.json').read_bytes()
        original_validate = pipeline.validate
        calls = 0
        def changing(data, *args, **kwargs):
            nonlocal calls
            calls += 1
            result = original_validate(data, *args, **kwargs)
            if calls == 2:
                resource.write_bytes(b'altered after per-question validation')
            return result
        with patch.object(pipeline, 'validate', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                self.fixture.ingest([self.fixture.question(0)])
        self.assertEqual(before, (self.folder/'candidate.json').read_bytes())
        self.assertFalse((self.folder/'ingest-checkpoints.json').exists())

    def test_global_invalid_resource_manifest_cannot_hide_outside_projection(self):
        self.resource()
        data = read(self.folder/'candidate.json')
        duplicate = copy.deepcopy(data['assets'][0])
        duplicate['id'] = 'other'
        data['assets'].append(duplicate)
        write(self.folder/'candidate.json', data)
        before = (self.folder/'candidate.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Duplicate resource path'):
            self.fixture.ingest([self.fixture.question(0)])
        self.assertEqual(before, (self.folder/'candidate.json').read_bytes())

    def test_schema_reads_are_reused_then_refreshed_at_final_validation(self):
        original_read = package_io.read
        schemas = []
        def observe_read(path):
            if Path(path).name == 'final.schema.json':
                schemas.append(path)
            return original_read(path)
        with patch.object(package_io, 'read', side_effect=observe_read):
            self.fixture.ingest([self.fixture.question(0), self.fixture.question(1)])
        self.assertEqual(len(schemas), 2)

    def test_asset_hash_cache_is_scoped_to_one_operation(self):
        resource = self.resource()
        question = self.fixture.question(0)
        question['stem'].append({'type':'image','asset_id':'fictional','alt':'Fictional rectangle'})
        original_digest = pipeline.digest
        images = []
        def observe_digest(path):
            if Path(path) == resource: images.append(path)
            return original_digest(path)
        with patch.object(pipeline, 'digest', side_effect=observe_digest):
            self.fixture.ingest([question])
        self.assertEqual(len(images), 1)
        resource.write_bytes(b'changed between operations')
        with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
            self.fixture.ingest([question])


if __name__ == '__main__':
    unittest.main()
