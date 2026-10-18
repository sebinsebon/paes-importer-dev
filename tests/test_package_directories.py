"""Match the browser's handling of ordinary ZIP directory entries."""
import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT / 'shared/scripts'))
from package_io import inspect_package
from test_contract_compatibility import fixture


def archive(version, directories):
    raw = json.dumps(fixture(version)).encode('utf-8')
    manifest = {'format': 'paessed-package', 'schema_version': '0.1.0', 'files': [
        {'path': 'final.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr('final.json', raw)
        package.writestr('manifest.json', json.dumps(manifest))
        for name, content in directories:
            package.writestr(name, content)
    output.seek(0)
    return output


class PackageDirectoryTests(unittest.TestCase):
    def test_empty_resource_directories_match_browser_for_both_versions(self):
        for version in ('0.1.0', '0.2.0'):
            with self.subTest(version=version):
                result = inspect_package(archive(version, [
                    ('assets/', b''), ('assets/crops/', b''), ('evidence/', b'')]))
                self.assertEqual(result['questions'], 1)
                self.assertEqual(result['files'], 2)

    def test_unsafe_unexpected_nonempty_and_duplicate_directories_rejected(self):
        for directories in ([('../assets/', b'')], [('assets/../', b'')],
                            [('assets//', b'')], [('other/', b'')],
                            [('assets/', b'payload')],
                            [('assets/', b''), ('ASSETS/', b'')]):
            with self.subTest(directories=directories):
                with self.assertRaises(ValueError):
                    inspect_package(archive('0.2.0', directories))


if __name__ == '__main__':
    unittest.main()
