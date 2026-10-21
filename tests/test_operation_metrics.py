import json
import tempfile
import unittest
from pathlib import Path
from support import WORK_ROOT
from metrics import aggregate_usage, summarize_timeline
from benchmark import evaluate, host_events


class OperationMetricsTests(unittest.TestCase):
    def test_missing_receipts_do_not_mean_zero_calls(self):
        summary = aggregate_usage([])
        self.assertEqual(summary['provider_receipts_count'], 0)
        self.assertIsNone(summary['total_provider_calls'])
        cached=aggregate_usage([{'event_id':'measured','input_tokens':10,'cached_input_tokens':4}])
        self.assertEqual(cached['cached_input_tokens'],4)
        self.assertEqual(cached['input_tokens'],10)

    def test_intervals_overlap_and_announced_backoff_is_not_elapsed(self):
        result = summarize_timeline([
            {'operation_id':'a','category':'importer','started_at':'2026-01-01T00:00:02Z','finished_at':'2026-01-01T00:00:06Z','duration_seconds':4},
            {'operation_id':'b','category':'provider','started_at':'2026-01-01T00:00:04Z','finished_at':'2026-01-01T00:00:08Z','duration_seconds':4},
            {'event':'provider_retry','announced_backoff_seconds':99}],
            requested_at='2026-01-01T00:00:00Z', finished_at='2026-01-01T00:00:10Z')
        self.assertEqual(result['wall_seconds'],10)
        self.assertEqual(result['attributed_seconds']['importer'],2)
        self.assertEqual(result['attributed_seconds']['provider'],2)
        self.assertEqual(result['unattributed_seconds'],6)
        self.assertEqual(result['announced_backoff_seconds'],99)
        self.assertEqual(result['attributed_seconds']['backoff'],0)

    def test_unknown_wall_time_and_legacy_command_duration(self):
        result = summarize_timeline([{'stage':'command_review','duration_seconds':2}])
        self.assertIsNone(result['wall_seconds'])
        self.assertIsNone(result['attributed_seconds']['importer'])
        self.assertEqual(result['command_duration_sums']['command_review'],2)

    def test_invalid_intervals_and_duplicate_operations_rejected(self):
        for events in ([{'operation_id':'a'},{'operation_id':'a'}],
                       [{'started_at':'2026-01-01T00:00:00','finished_at':'2026-01-01T00:00:02'}],
                       [{'retry_count':True}], [{'duration_seconds':float('nan')}]):
            with self.assertRaises(ValueError): summarize_timeline(events)

    def test_host_jsonl_import_keeps_failed_run_and_hash(self):
        WORK_ROOT.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            path=Path(directory)/'host.jsonl'
            path.write_text(json.dumps({'event':'provider_retry','error_code':'503'})+'\n',encoding='utf-8')
            result=evaluate({'runs':[{'id':'failed','status':'failed','host_events':'host.jsonl'}]},directory)
            row=result['runs'][0]
            self.assertEqual(row['timing']['retry_count'],1)
            self.assertIsNone(row['timing']['wall_seconds'])
            self.assertEqual(len(row['log_hashes']['host_events']),64)

    def test_agy_retry_log_preserves_unknown_time_and_announced_backoff(self):
        WORK_ROOT.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            path=Path(directory)/'host.log'
            path.write_text('I1020 11:48:03.242177 1 run.go:395] Run: attempt 1 failed (UNAVAILABLE (code 503): No capacity), retrying in 4s\n'
                'I1020 11:49:03.242177 1 run.go:395] Run: attempt 2 failed (stream idle timeout (5m0s)), retrying in 7.25s\n',encoding='utf-8')
            events=host_events(path)
            self.assertEqual(len(events),2)
            self.assertIsNone(events[0]['timestamp'])
            self.assertEqual(events[1]['error_code'],'PROVIDER_STREAM_IDLE_TIMEOUT')
            self.assertEqual(summarize_timeline(events)['announced_backoff_seconds'],11.25)
            self.assertIsNone(summarize_timeline(events)['wall_seconds'])
            self.assertTrue(host_events(path,{'year':2026,'utc_offset':'-03:00'})[0]['timestamp'].endswith('-03:00'))


if __name__ == '__main__': unittest.main()
