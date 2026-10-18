"""Development infrastructure checks; synthetic fixtures, never copied runtime."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from support import DEV_ROOT, RUNTIME_ROOT, WORK_ROOT
from dev_paths import output_path
from history_audit import audit, signatures
from integrity import snapshot, verify_release
from make_bundle import build


class DevelopmentTests(unittest.TestCase):
    def workspace(self):
        return tempfile.TemporaryDirectory(dir=WORK_ROOT)

    def fixture(self, directory):
        runtime = directory / 'fixture-runtime'
        runtime.mkdir()
        (runtime / 'SKILL.md').write_bytes(b'# Synthetic fixture\n')
        config = directory / 'distribution.json'
        config.write_text(json.dumps({'files': ['SKILL.md']}), encoding='utf-8')
        import hashlib
        manifest = {'version': '1.4.0-test', 'protocol_version': '0.4.0',
                    'files': [{'path': 'SKILL.md', 'sha256': hashlib.sha256((runtime / 'SKILL.md').read_bytes()).hexdigest()}]}
        (runtime / 'release.json').write_text(json.dumps(manifest) + '\n', encoding='utf-8')
        return runtime, config

    def test_bundle_is_reproducible_and_matches_manifest_bytes(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            runtime, config = self.fixture(root)
            # Unlisted generated files are not silently packaged.
            (runtime / 'private.pdf').write_bytes(b'synthetic excluded fixture')
            a = build(runtime, root / 'one.zip', config)
            b = build(runtime, root / 'two.zip', config)
            self.assertEqual(a['sha256'], b['sha256'])
            with zipfile.ZipFile(a['path']) as archive:
                self.assertEqual(archive.namelist(), ['paes-importer/SKILL.md', 'paes-importer/release.json'])
                for item in archive.infolist():
                    self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(archive.read(item), (runtime / item.filename.split('/', 1)[1]).read_bytes())

    def test_release_check_rejects_changed_bytes_without_rewriting(self):
        with self.workspace() as temporary:
            runtime, config = self.fixture(Path(temporary))
            before = (runtime / 'release.json').read_bytes()
            (runtime / 'SKILL.md').write_text('# Changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                verify_release(runtime, config)
            self.assertEqual((runtime / 'release.json').read_bytes(), before)

    def test_release_write_keeps_existing_version_and_is_explicit(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            runtime, config = self.fixture(root)
            (runtime / 'SKILL.md').write_text('# Changed', encoding='utf-8')
            command = [sys.executable, '-B', str(DEV_ROOT / 'scripts/release.py'), '--runtime', str(runtime), '--distribution', str(config)]
            old = (runtime / 'release.json').read_bytes()
            result = subprocess.run(command, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((runtime / 'release.json').read_bytes(), old)
            subprocess.run(command + ['--write'], check=True, capture_output=True)
            self.assertEqual(json.loads((runtime / 'release.json').read_text())['version'], '1.4.0-test')
            verify_release(runtime, config)

    def test_destinations_inside_runtime_are_rejected_before_mkdir(self):
        with self.workspace() as temporary:
            runtime, config = self.fixture(Path(temporary))
            forbidden = runtime / 'new-directory/artifact.zip'
            with self.assertRaisesRegex(ValueError, 'outside runtime'):
                build(runtime, forbidden, config)
            self.assertFalse(forbidden.parent.exists())
            command = [sys.executable, '-B', str(DEV_ROOT / 'scripts/check.py'), '--runtime', str(runtime),
                       '--work-dir', str(runtime / 'new-directory'), '--tests-only']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((runtime / 'new-directory').exists())

    def test_bundle_rejects_existing_output_and_unsafe_allowlist(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            runtime, config = self.fixture(root)
            bundle = root / 'existing.zip'
            bundle.write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError, 'Preserve'):
                build(runtime, bundle, config)
            self.assertEqual(bundle.read_bytes(), b'preserve')
            config.write_text(json.dumps({'files': ['../SKILL.md']}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                verify_release(runtime, config)

    def test_snapshot_captures_ignored_files_and_empty_directories(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            (root / '.git').mkdir()
            (root / '.git/ignored').write_bytes(b'git metadata')
            (root / '__pycache__').mkdir()
            (root / '__pycache__/x.pyc').write_bytes(b'cache')
            actual = snapshot(root)
            self.assertIn('__pycache__/', actual)
            self.assertIn('__pycache__/x.pyc', actual)
            self.assertNotIn('.git/', actual)

    def test_linked_output_and_inventory_are_not_followed(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            target = root / 'target'
            target.mkdir()
            (target / 'secret.txt').write_bytes(b'synthetic')
            link = root / 'linked'
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest('Symlinks unavailable: ' + str(error))
            with self.assertRaisesRegex(ValueError, 'Linked'):
                output_path(link / 'output.txt', RUNTIME_ROOT)
            actual = snapshot(root)
            self.assertEqual(actual['linked']['kind'], 'link')
            self.assertNotIn('linked/secret.txt', actual)

    def test_history_audit_scans_deleted_history_metadata_and_public_tree(self):
        with self.workspace() as temporary:
            root = Path(temporary)
            def git(*arguments):
                return subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, check=True)
            git('init')
            git('config', 'user.name', 'Synthetic test author')
            git('config', 'user.email', 'synthetic@example.invalid')
            credential = 'ghp_' + 'a' * 36
            (root / 'deleted.txt').write_text(credential, encoding='utf-8')
            git('add', 'deleted.txt')
            git('commit', '-m', 'Synthetic history fixture')
            (root / 'deleted.txt').unlink()
            git('add', '-u')
            git('commit', '-m', 'Delete fixture, retain history')
            (root / 'public.pdf').write_bytes(b'synthetic filename screening')
            result = audit(root)
            self.assertEqual(result['commit_count'], 2)
            self.assertTrue(any(finding['category'] == 'github-token' for finding in result['findings']))
            self.assertTrue(any(finding.get('path') == 'public.pdf' for finding in result['findings']))
            self.assertNotIn(credential, json.dumps(result))
            self.assertEqual(result['publication_status'], 'human_review_required')
            self.assertEqual(len(result['commit_metadata']), 2)
            self.assertTrue(result['refs'])

    def test_assignment_candidates_are_redacted(self):
        value = b'fixture-value-for-assignment'
        found = signatures(b'password' + b' = "' + value + b'"', {'scope': 'fixture'})
        self.assertEqual(found[0]['category'], 'credential-assignment-candidate')
        self.assertNotIn(value.decode(), json.dumps(found))


if __name__ == '__main__':
    unittest.main()
