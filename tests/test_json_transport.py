"""Exercise actual PowerShell byte transport with synthetic currency and LaTeX."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT

class TransportTests(unittest.TestCase):
    def setUp(self):
        candidates=[shutil.which('pwsh'), shutil.which('powershell')]
        if sys.platform == 'win32':
            candidates.append(str(Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'))
        self.shell=None
        for candidate in candidates:
            if not candidate:continue
            try:
                probe=subprocess.run([candidate,'-NoProfile','-NonInteractive','-Command','exit 0'],capture_output=True)
                if probe.returncode==0:
                    self.shell=candidate
                    break
            except OSError:continue
        if not self.shell:self.skipTest('PowerShell unavailable or non-executable alias')
        (WORK_ROOT).mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.home=Path(self.temp.name)
    def tearDown(self):
        if hasattr(self,'temp'):self.temp.cleanup()
    def invoke(self,source,target,launcher=False,workspace=None,script_override=None):
        script=script_override or (ROOT/'run.ps1' if launcher else ROOT/'scripts/write_json.ps1')
        args=['-JsonInputPath',str(source),'-JsonOutputPath',str(target)] if launcher else ['-InputPath',str(source),'-OutputPath',str(target)]
        args.extend(['-WorkspaceRoot',str(workspace if workspace is not None else self.home)])
        return subprocess.run([self.shell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),*args],
                              capture_output=True,encoding='utf-8',errors='replace')
    def test_content_is_never_shell_source(self):
        source=self.home/'source with spaces.json';target=self.home/'transported.json'
        original=json.dumps({'text':'$11 000; $80 000; á "quote"\nnext', 'latex':r'\frac{a}{b}',
                             'literal':'$(throw "must not execute")'},ensure_ascii=False).encode('utf-8')
        source.write_bytes(original)
        result=self.invoke(source,target,launcher=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(target.read_bytes(),original)
        self.assertEqual(source.read_bytes(),original)
        self.assertNotEqual(self.invoke(source,target).returncode,0)
    def test_invalid_json_or_encoding_does_not_write(self):
        source=self.home/'bad.json';target=self.home/'target.json'
        for blob in (b'{invalid}',b'{"text":"\xff"}'):
            source.write_bytes(blob)
            self.assertNotEqual(self.invoke(source,target).returncode,0)
            self.assertFalse(target.exists())
    def test_explicit_external_workspace_and_escape(self):
        # Copy tool under its own synthetic checkout; keep test artifacts in tmp.
        checkout=self.home/'tool';(checkout/'scripts').mkdir(parents=True)
        tool=checkout/'scripts/write_json.ps1';shutil.copyfile(ROOT/'scripts/write_json.ps1',tool)
        selected=self.home/'selected-output';selected.mkdir()
        source=self.home/'source.json';source.write_bytes(b'{"amount":"$11 000"}')
        target=selected/'transport.json'
        result=self.invoke(source,target,workspace=selected,script_override=tool)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(target.read_bytes(),source.read_bytes())
        escaped=self.home/'outside-selected.json'
        self.assertNotEqual(self.invoke(source,escaped,workspace=selected,script_override=tool).returncode,0)
        self.assertFalse(escaped.exists())
    def test_outside_checkout_rejected(self):
        source=self.home/'source.json';source.write_bytes(b'{}')
        self.assertNotEqual(self.invoke(source,ROOT.parent/'outside-transport-test.json').returncode,0)

if __name__=='__main__':unittest.main()
