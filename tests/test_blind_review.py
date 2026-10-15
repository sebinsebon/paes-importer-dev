"""Synthetic two-phase reviewer boundaries; never a real comprehension claim."""
import copy
import unittest
import test_importer as fixtures
from lab import read, write
import verify

class BlindReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ImporterTests()
        self.fixture.setUp()
        self.fixture.start(solution=False)
        self.fixture.route(subagents=True)
        self.fixture.produce()
        import importer
        importer.baseline(self.fixture.folder)
        from pathlib import Path
        self.folder = Path(verify.prepare(self.fixture.folder,'blind-review',1,'synthetic','high','coordinator',self.fixture.folder.parent.parent))
    def tearDown(self): self.fixture.tearDown()
    def test_candidate_not_revealed_before_reading(self):
        packet = read(self.folder/'batches/batch-01/input.json')
        self.assertEqual(packet['stage'],'source-reading')
        for q in packet['questions']:
            for forbidden in ('stem','options','answer','explanation','curriculum'):
                self.assertNotIn(forbidden,q)
        self.assertFalse((self.folder/'batches/batch-01/report-template.json').exists())
        with self.assertRaisesRegex(ValueError,'not committed'): verify.load_reports(self.folder)
    def test_failed_reading_commit_rolls_back_and_retries(self):
        from unittest.mock import patch
        import checkpoints
        from lab import digest
        original_run = (self.folder/'run.json').read_bytes()
        original_input = (self.folder/'batches/batch-01/input.json').read_bytes()
        original_replace = checkpoints.os.replace
        def fail(source,target):
            if str(target).endswith('report-template.json'):
                raise OSError('synthetic interruption')
            return original_replace(source,target)
        with patch.object(checkpoints.os,'replace',side_effect=fail):
            with self.assertRaisesRegex(OSError,'synthetic'):
                self.fixture.commit_blind(self.folder)
        self.assertEqual(original_run,(self.folder/'run.json').read_bytes())
        self.assertEqual(original_input,(self.folder/'batches/batch-01/input.json').read_bytes())
        self.assertFalse((self.folder/'batches/batch-01/reading.json').exists())
        self.fixture.commit_blind(self.folder)
        self.assertEqual(read(self.folder/'batches/batch-01/input.json')['stage'],'comparison')

    def test_reading_committed_before_reveal_and_bound(self):
        self.fixture.commit_blind(self.folder)
        packet = read(self.folder/'batches/batch-01/input.json')
        self.assertEqual(packet['stage'],'comparison')
        self.assertIn('reading_sha256',packet)
        from lab import digest
        self.assertEqual(packet['reading_sha256'],digest(self.folder/'batches/batch-01/reading.json'))
        with self.assertRaisesRegex(ValueError,'already committed'):
            verify.commit_reading(self.folder,'batch-01',self.folder/'batches/batch-01/reading-response.json')

if __name__ == '__main__': unittest.main()
