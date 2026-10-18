"""Environment resolution and writes stay outside the selected installation."""
import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import RUNTIME_ROOT as ROOT, WORK_ROOT
from runtime_environment import default_environment, external_directory, process_environment


class RuntimeEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=WORK_ROOT)
        self.home = Path(self.temporary.name)
        self.runtime = self.home/'runtime'
        self.runtime.mkdir()
        (self.runtime/'requirements.txt').write_text('fictional==1\n', encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_environment_is_relocatable_and_read_only(self):
        storage = self.home/'data'
        env = {'PAES_IMPORTER_DATA_DIR': str(storage)}
        first = default_environment(environ=env, runtime_root=self.runtime)
        moved = self.home/'other-runtime'
        moved.mkdir()
        (moved/'requirements.txt').write_bytes((self.runtime/'requirements.txt').read_bytes())
        self.assertEqual(first, default_environment(environ=env, runtime_root=moved))
        self.assertFalse(storage.exists())
        (moved/'requirements.txt').write_text('fictional==2\n', encoding='utf-8')
        self.assertNotEqual(first, default_environment(environ=env, runtime_root=moved))

    def test_rejects_runtime_root_and_link_before_mkdir(self):
        destination = self.runtime/'forbidden'/'child'
        with self.assertRaisesRegex(ValueError, 'outside'):
            external_directory(destination, create=True, runtime_root=self.runtime)
        self.assertFalse((self.runtime/'forbidden').exists())
        with self.assertRaisesRegex(ValueError, 'filesystem root'):
            external_directory(Path(self.home.anchor), create=True, runtime_root=self.runtime)
        linked = self.home/'linked'
        with patch.object(Path, 'is_symlink', autospec=True, side_effect=lambda p: p == linked):
            with self.assertRaisesRegex(ValueError, 'Linked'):
                external_directory(linked/'child', create=True, runtime_root=self.runtime)
        self.assertFalse(linked.exists())

    def test_all_process_paths_are_preflighted_before_creation(self):
        workspace = self.home/'work'
        with self.assertRaisesRegex(ValueError, 'outside'):
            process_environment(workspace, create=True, runtime_root=self.runtime,
                                environ={'PLAYWRIGHT_BROWSERS_PATH': str(self.runtime/'browser-cache')})
        self.assertFalse(workspace.exists())
        settings = {'PAES_IMPORTER_DATA_DIR': str(self.home/'data')}
        env = process_environment(workspace, create=True, environ=settings, runtime_root=self.runtime)
        for key in ('TEMP','TMP','TMPDIR','PIP_CACHE_DIR','UV_CACHE_DIR','PYTHONPYCACHEPREFIX',
                    'XDG_CACHE_HOME'):
            self.assertTrue(Path(env[key]).is_dir(), key)
            self.assertTrue(Path(env[key]).is_relative_to(workspace), key)
        browsers = Path(env['PLAYWRIGHT_BROWSERS_PATH'])
        self.assertTrue(browsers.is_dir())
        self.assertTrue(browsers.is_relative_to(self.home/'data'))
        other = process_environment(self.home/'second-work', environ=settings, runtime_root=self.runtime)
        self.assertEqual(other['PLAYWRIGHT_BROWSERS_PATH'], str(browsers))
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')

    def test_setup_print_python_does_not_create_environment(self):
        storage = self.home/'external installation'
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/setup.py'), '--print-python'],
            env={**os.environ, 'PAES_IMPORTER_DATA_DIR': str(storage)}, cwd=self.home,
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).is_relative_to(storage))
        self.assertFalse(storage.exists())
        explicit = self.home/'explicit env'
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/setup.py'), '--print-python',
                                  '--env-dir', str(explicit)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).is_relative_to(explicit))
        self.assertFalse(explicit.exists())

    def test_setup_rejects_in_installation_environment_without_writing(self):
        forbidden = ROOT/'must-not-exist-environment'
        self.assertFalse(forbidden.exists())
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/setup.py'), '--env-dir', str(forbidden),
                                  '--print-python'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(forbidden.exists())

    def test_entrypoints_keep_detached_installation_clean_without_B_flag(self):
        installation=self.home/'detached-runtime'
        files=[r['path'] for r in json.loads((ROOT/'release.json').read_text(encoding='utf-8'))['files']]+['release.json']
        for name in files:
            target=installation/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONDONTWRITEBYTECODE','PYTHONPYCACHEPREFIX','PYTHONPATH')}
        env['PAES_IMPORTER_DATA_DIR']=str(self.home/'detached-data')
        for script,args in [('setup.py',['--print-python']),('verify.py',['--help'])]:
            result=subprocess.run([sys.executable,str(installation/'scripts'/script),*args],
                cwd=self.home,env=env,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(list(installation.rglob('__pycache__')),script)


if __name__ == '__main__':
    unittest.main()
