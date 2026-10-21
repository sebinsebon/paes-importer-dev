"""Opt-in migration through two real pinned runtimes; fictional source only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT, DEV_ROOT, WORK_ROOT


@unittest.skipUnless(os.environ.get('PAES_TEST_LEGACY_RUNTIME'),'Set PAES_TEST_LEGACY_RUNTIME for pinned-runtime migration')
class LegacyAdoptionTests(unittest.TestCase):
    def test_real_legacy_partial_checkpoint_preserves_accepted_candidate(self):
        legacy=Path(os.environ['PAES_TEST_LEGACY_RUNTIME']).resolve(strict=True)
        script=r'''
import hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'tests'))
import test_importer as fixtures
f=fixtures.ImporterTests();f.setUp()
try:
    f.start();f.route(('q1','q2'));f.cotejo=lambda:None;f.produce()
    original=(f.folder/'candidate.json').read_bytes()
    destination=Path(sys.argv[4]);checkpoint=destination/'legacy.zip';adopted=destination/'adopted'
    command=[sys.executable,'-B',str(Path(sys.argv[2])/'scripts/importer.py')]
    exported=subprocess.run(command+['export-checkpoint','--run',str(f.folder),'--output',str(checkpoint)],capture_output=True,text=True,encoding='utf-8')
    if exported.returncode:raise RuntimeError(exported.stderr)
    result=subprocess.run(command+['adopt-checkpoint','--checkpoint',str(checkpoint),'--legacy-bundle',sys.argv[3],'--output-run',str(adopted)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stderr)
    after=(adopted/'.work/base/candidate.json').read_bytes()
    if original!=after:raise RuntimeError('Candidate bytes changed during actual runtime adoption')
    resumed=subprocess.run(command+['resume','--run',str(adopted)],capture_output=True,text=True,encoding='utf-8')
    if resumed.returncode:raise RuntimeError(resumed.stderr)
    progress=json.loads(resumed.stdout)
    if progress['accepted_question_ids']!=['q1','q2']:raise RuntimeError('Lost accepted content')
    print(json.dumps({'accepted':progress['accepted_question_ids'],'candidate_sha256':hashlib.sha256(after).hexdigest(),'pending_review':progress['pending_review_ids']}))
finally:f.tearDown()
'''
        WORK_ROOT.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as directory:
            result=subprocess.run([sys.executable,'-B','-c',script,str(DEV_ROOT),str(RUNTIME_ROOT),str(legacy),directory],
                env={**os.environ,'PAES_IMPORTER_RUNTIME':str(legacy)},capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(result.returncode,0,result.stderr)
            row=json.loads(result.stdout)
            self.assertEqual(row['accepted'],['q1','q2'])
            self.assertEqual(row['pending_review'],['q1','q2'])
            self.assertEqual(len(row['candidate_sha256']),64)


if __name__=='__main__': unittest.main()
