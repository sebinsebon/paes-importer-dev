"""Exercise the distributed bundle without a checkout or a matching working directory."""
import json
import re
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FLOW_FILES = (
    'flows/01-chat-con-solucionario/WORKFLOW.md',
    'flows/02-cli-con-solucionario/WORKFLOW.md',
    'flows/03-cli-sin-solucionario/WORKFLOW.md',
    'flows/04-chat-sin-solucionario/WORKFLOW.md',
)


class PortabilityTests(unittest.TestCase):
    def test_bundle_runs_from_unrelated_directory(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temporary:
            workspace = Path(temporary)
            caller = workspace / 'caller'
            caller.mkdir()
            environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
                           'TEMP': str(workspace), 'TMP': str(workspace), 'TMPDIR': str(workspace)}
            environment.pop('PYTHONPATH', None)

            def run(*arguments):
                result = subprocess.run([sys.executable, '-B', *map(str, arguments)],
                                        cwd=caller, env=environment, capture_output=True,
                                        text=True, encoding='utf-8', timeout=180)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            bundle = workspace / 'skill.zip'
            run(ROOT / 'scripts/make_bundle.py', '--output', bundle)
            extracted = workspace / 'instalación con espacios'
            manifest = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
            with zipfile.ZipFile(bundle) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {'paes-importer/' + entry['path'] for entry in manifest['files']}
                                 | {'paes-importer/release.json'})
                archive.extractall(extracted)
            skill = extracted / 'paes-importer'
            self.assertFalse((skill / '.git').exists())
            self.assertFalse((skill / '.venv').exists())
            run(skill / 'scripts/release.py')
            run(skill / 'scripts/importer.py', '--help')
            # The distributed skill includes no development inputs.
            forbidden = {'tests', 'examples', 'docs', 'development', '.github',
                         'AGENTS.md', 'requirements-dev.txt', '.gitignore', '.gitattributes'}
            self.assertTrue(all(not (skill / name).exists() for name in forbidden))
            self.assertTrue((skill / 'references/hosts.md').is_file())
            self.assertEqual({item['path'] for item in manifest['files'] if item['path'].startswith('flows/')},
                             set(FLOW_FILES))
            # Agent-facing links must resolve inside the extracted bundle.
            for markdown in [skill / 'README.md', skill / 'SKILL.md',
                             *(skill / 'flows').rglob('*.md'),
                             *(skill / 'references').rglob('*.md'),
                             *(skill / 'shared/references').rglob('*.md')]:
                content = markdown.read_text(encoding='utf-8')
                for target in re.findall(r'\]\(([^)]+)\)', content):
                    if target.startswith(('http://', 'https://', '#', 'mailto:')):
                        continue
                    path = target.split('#', 1)[0]
                    if path:
                        self.assertTrue((markdown.parent / path).is_file(),
                                        f'Broken bundled link: {markdown}: {target}')
            run(skill / 'scripts/verify.py', '--help')
            # Smoke test: create a synthetic PDF outside the bundle and prepare it.
            sources = workspace / 'sources'
            run(ROOT / 'examples/synthetic.py', '--output', sources)
            capabilities = workspace / 'capabilities.json'
            capabilities.write_text(json.dumps({
                'pdf_visual': True, 'crop': True, 'execute': True,
                'zip': True, 'validate': True,
                'observation': 'Synthetic fixtures only, not an AI reading claim'
            }), encoding='utf-8')
            result = run(skill / 'scripts/importer.py', 'prepare',
                         '--exam', sources / 'synthetic-m1.pdf',
                         '--solution', sources / 'synthetic-key.pdf',
                         '--host', 'cli', '--client', 'bundle-smoke-test',
                         '--session-id', 'synthetic-smoke-test',
                         '--destination', 'custom', '--output-root', workspace / 'output',
                         '--capabilities', capabilities, '--run-id', 'bundle-smoke-test')
            self.assertTrue((Path(json.loads(result.stdout)['run']) / 'catalog.json').is_file())

    def test_entrypoint_routes_to_one_self_contained_flow(self):
        entrypoint = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        selected = re.findall(r'\]\((flows/[^)]+/WORKFLOW\.md)\)', entrypoint)
        self.assertEqual(selected, list(FLOW_FILES))
        manifest = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
        self.assertEqual([item['path'] for item in manifest['files']
                          if item['path'].endswith('SKILL.md')], ['SKILL.md'])
        for flow in FLOW_FILES:
            instructions = (ROOT / flow).read_text(encoding='utf-8')
            links = re.findall(r'\]\(([^)]+)\)', instructions)
            self.assertTrue(links, flow)
            self.assertFalse(any('/flows/' in link or link.startswith('../WORKFLOW')
                                 for link in links), flow)
            self.assertTrue(any('references/workflow.md' in link for link in links), flow)
            self.assertTrue(any('content-contract.md' in link for link in links), flow)

    def test_environment_confirmation_precedes_resource_loading(self):
        entrypoint = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        body = entrypoint.split('---', 2)[2].strip()
        first_section = body.split('## ', 1)[1].split('\n\n', 2)
        self.assertEqual(first_section[0], 'Primero: confirmar el entorno')
        gate = first_section[1]
        self.assertIn('¿Dónde estás usando la skill: Chat Web o CLI / agente de terminal?', gate)
        self.assertIn('espera su respuesta antes de continuar', gate)
        self.assertIn('sin volver a preguntar', gate)
        self.assertNotRegex(gate, r'\]\([^)]+\)')

    def test_entrypoint_matches_runtime_coverage_policy(self):
        entrypoint = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        rows = re.findall(r'^\| (Chat web|CLI) \| ([^|]+) \| \[[^]]+\]\((flows/[^)]+)\) \|$',
                          entrypoint, re.MULTILINE)
        self.assertEqual(len(rows), 4)
        select_mode = runpy.run_path(str(ROOT / 'scripts/policy.py'))['select_mode']
        for host, covered, expected in (
            ('web', ('q1', 'q2'), FLOW_FILES[0]),
            ('cli', ('q1', 'q2'), FLOW_FILES[1]),
            ('cli', ('q1',), FLOW_FILES[2]),
            ('cli', (), FLOW_FILES[2]),
            ('web', ('q1',), FLOW_FILES[3]),
            ('web', (), FLOW_FILES[3]),
        ):
            decision = select_mode(host, ('q1', 'q2'), covered)
            complete = decision['status'] == 'ready' and decision['processing_mode'] == 'answer-key'
            environment = 'Chat web' if host == 'web' else 'CLI'
            matches = [path for name, coverage, path in rows if name == environment and
                       (coverage.strip() == 'Todas las preguntas') == complete]
            self.assertEqual(matches, [expected], (host, covered))

    def test_setup_rejects_missing_node_before_creating_environment(self):
        with patch.object(sys, 'argv', ['setup.py']), patch('shutil.which', return_value=None):
            with self.assertRaisesRegex(SystemExit, 'Node.js 18'):
                runpy.run_path(str(ROOT / 'scripts/setup.py'), run_name='__main__')

    def test_setup_rejects_old_node_before_creating_environment(self):
        with patch.object(sys, 'argv', ['setup.py']), patch('shutil.which', return_value='node'), \
             patch('subprocess.run', return_value=subprocess.CompletedProcess(['node'], 0, 'v16.20.2\n')):
            with self.assertRaisesRegex(SystemExit, 'Node.js 18'):
                runpy.run_path(str(ROOT / 'scripts/setup.py'), run_name='__main__')


if __name__ == '__main__':
    unittest.main(verbosity=2)
