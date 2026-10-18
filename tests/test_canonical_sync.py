"""Runtime must match the reviewed normative contract without external checkout."""
import json
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT, DEV_ROOT, WORK_ROOT
from contract import check, contract_records


class CanonicalSyncTests(unittest.TestCase):
    def test_runtime_matches_normative_lock(self):
        result=check(RUNTIME_ROOT)
        self.assertEqual(result['version'],'0.2.0')
        self.assertEqual(result['container_version'],'0.1.0')
        self.assertEqual(result['resources'],20)

    def test_changed_normative_copy_is_rejected(self):
        lock=json.loads((DEV_ROOT/'contract.lock.json').read_text(encoding='utf-8'))
        lock['files'][0]['sha256']='0'*64
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as work:
            path=Path(work)/'lock.json';path.write_text(json.dumps(lock),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'contract divergence'):
                check(RUNTIME_ROOT,path)

    def test_unsafe_paths_and_version_change_are_rejected(self):
        for field,value in [('version','0.3.0'),('files',[{'path':'../secret','sha256':'0'*64}])]:
            doc=json.loads((DEV_ROOT/'contract.lock.json').read_text(encoding='utf-8'));doc[field]=value
            with self.assertRaises(ValueError): contract_records(doc)


if __name__=='__main__': unittest.main()
