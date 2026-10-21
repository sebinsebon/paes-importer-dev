import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from support import RUNTIME_ROOT, WORK_ROOT
import benchmark_operations


class OperationBenchmarkTests(unittest.TestCase):
    def test_timeout_and_malformed_workers_are_retained_with_completed_pairs(self):
        WORK_ROOT.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            output=Path(directory)/'campaign'
            good=SimpleNamespace(returncode=0,stdout=json.dumps({'prepare_seconds':1,
                'ten_source_queries_seconds':2,'asset_bytes':0,'source_query_bytes':3,'review_seconds':[1,.5]}),stderr='')
            malformed=SimpleNamespace(returncode=0,stdout='invalid JSON',stderr='')
            responses=[subprocess.TimeoutExpired('synthetic worker',120),good,malformed,good,good,good]
            with patch('sys.argv',['benchmark_operations','--runtime',str(RUNTIME_ROOT),'--baseline',str(RUNTIME_ROOT),
                       '--output',str(output)]),patch('benchmark_operations.subprocess.run',side_effect=responses),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped: benchmark_operations.main()
            self.assertEqual(stopped.exception.code,1)
            report=json.loads((output/'report.json').read_text())
            statuses=[r[label]['status'] for r in report['pairs'] for label in ('baseline','candidate')]
            self.assertEqual(statuses.count('interrupted'),1)
            self.assertEqual(statuses.count('failed'),1)
            self.assertEqual(statuses.count('completed'),4)
            self.assertEqual(len(json.loads((output/'progress.json').read_text())['pairs']),3)
            self.assertIsNone(report['time_to_acceptable_delivery'])


if __name__=='__main__': unittest.main()
