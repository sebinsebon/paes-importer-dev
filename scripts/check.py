"""Run development checks against one explicit runtime without writing into it."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote
from dev_paths import DEV_ROOT as DEV, output_path, runtime_root
from integrity import git_sha, sha256, snapshot, verify_release
from contract import check as check_contract


def anchor(text):
    text = re.sub(r'<[^>]*>', '', text.strip().lower())
    text = re.sub(r'[^\w\- ]', '', text, flags=re.UNICODE)
    return text.replace(' ', '-')


def document_errors(runtime):
    errors = []
    markdown = [runtime / 'SKILL.md', runtime / 'README.md', runtime / 'NOTICE.md']
    for name in ('flows', 'references', 'shared/references'):
        markdown.extend(sorted((runtime / name).rglob('*.md')))
    for source in markdown:
        content = source.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if target.startswith(('http:', 'https:', 'mailto:')):
                continue
            target = unquote(target.strip('<>'))
            name, _, section = target.partition('#')
            path = (source.parent / name).resolve() if name else source
            label = source.relative_to(runtime).as_posix() + ': ' + target
            if not path.is_relative_to(runtime) or not path.is_file():
                errors.append('Broken local link: ' + label)
            elif section:
                anchors = []
                counts = {}
                for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*\s*$', path.read_text(encoding='utf-8'), re.M):
                    slug = anchor(heading)
                    count = counts.get(slug, 0)
                    counts[slug] = count + 1
                    anchors.append(slug + ('-' + str(count) if count else ''))
                if section not in anchors:
                    errors.append('Broken heading anchor: ' + label)
        for _, example in re.findall(r'^(```|~~~)json[^\S\n]*\n(.*?)^(?:```|~~~)', content, re.M | re.S):
            try:
                decoded = json.loads(example)
                if isinstance(decoded, dict) and isinstance(decoded.get('questions'), list):
                    from jsonschema import Draft202012Validator
                    final_schema = json.loads((runtime / 'shared/schemas/final.schema.json').read_text(encoding='utf-8'))
                    validator = Draft202012Validator({'$defs': final_schema['$defs'], '$ref': '#/$defs/question'})
                    for question in decoded['questions']:
                        for issue in validator.iter_errors(question):
                            errors.append('Invalid question example: ' + source.relative_to(runtime).as_posix() + ': ' + issue.message)
            except json.JSONDecodeError as error:
                errors.append('Invalid JSON example: ' + source.relative_to(runtime).as_posix() + ': ' + str(error))
    return errors


def runtime_tree_errors(runtime):
    manifest = json.loads((runtime / 'release.json').read_text(encoding='utf-8'))
    allowed = {record['path'] for record in manifest['files']} | {
        'release.json', '.gitignore', '.gitattributes', '.github/workflows/ci.yml'}
    directories = {parent.as_posix() + '/' for name in allowed for parent in Path(name).parents
                   if parent.as_posix() != '.'}
    errors = []
    for name, information in snapshot(runtime).items():
        if information['kind'] == 'link' or name not in allowed | directories:
            errors.append('Unexpected physical runtime entry: ' + name)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--work-dir', type=Path, default=DEV / 'tmp')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()
    runtime = runtime_root(args.runtime)
    # Validate every destination before creating even a parent directory.
    work = output_path(args.work_dir, runtime)
    cache = output_path(DEV / 'caches', runtime)
    destination = output_path(args.report, runtime) if args.report else None
    if destination and destination.exists():
        raise ValueError('Preserve existing verification report; choose another filename')
    work.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PAES_IMPORTER_RUNTIME': str(runtime), 'PAES_IMPORTER_WORK': str(work),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'TEMP': str(work), 'TMP': str(work),
           'TMPDIR': str(work), 'PIP_CACHE_DIR': str(cache / 'pip'), 'UV_CACHE_DIR': str(cache / 'uv'),
           'PLAYWRIGHT_BROWSERS_PATH': str(cache / 'browsers')}
    before = snapshot(runtime)
    start = time.perf_counter()
    stages = []
    if not args.tests_only:
        try:
            manifest = verify_release(runtime)
            stages.append({'name': 'release', 'returncode': 0, 'files': len(manifest['files'])})
        except (ValueError, OSError, KeyError) as error:
            stages.append({'name': 'release', 'returncode': 1, 'error': str(error)})
        errors = document_errors(runtime)
        stages.append({'name': 'documentation', 'returncode': int(bool(errors)), 'errors': errors})
        try:
            result = check_contract(runtime)
            stages.append({'name':'canonical_contract','returncode':0,**result})
        except (ValueError,OSError,KeyError) as error:
            stages.append({'name':'canonical_contract','returncode':1,'error':str(error)})
        errors = runtime_tree_errors(runtime)
        stages.append({'name': 'runtime_tree', 'returncode': int(bool(errors)), 'errors': errors})
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(DEV / 'tests'), '-p', args.pattern, '-v']
    result = subprocess.run(command, env=env, cwd=DEV, capture_output=True, text=True, encoding='utf-8')
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    summary = re.search(r'Ran (\d+) tests? in ([\d.]+)s', result.stderr)
    stages.append({'name': 'tests', 'returncode': result.returncode, 'command': command,
                   'tests_run': int(summary.group(1)) if summary else None,
                   'stdout': result.stdout, 'stderr': result.stderr})
    after = snapshot(runtime)
    changes = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    node = subprocess.run(['node', '--version'], text=True, capture_output=True, check=False)
    returncode = int(bool(changes) or any(item['returncode'] for item in stages))
    report = {'runtime': str(runtime), 'development': str(DEV), 'returncode': returncode,
              'runtime_changes': changes, 'stages': stages, 'runtime_commit': git_sha(runtime),
              'development_commit': git_sha(DEV), 'release_sha256': sha256(runtime / 'release.json'),
              'snapshot_before_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
              'snapshot_after_sha256': hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest(),
              'duration_seconds': time.perf_counter() - start, 'python': sys.version,
              'node': node.stdout.strip(), 'platform': platform.platform(),
              'dependency_versions': {package.metadata['Name']: package.version
                                      for package in importlib.metadata.distributions()}}
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
    for stage in stages:
        if stage['returncode']:
            print(stage['name'] + ': ' + str(stage.get('error', stage.get('errors', 'FAILED'))), file=sys.stderr)
    if changes:
        print('Runtime physical tree changed: ' + ', '.join(changes), file=sys.stderr)
    return returncode


if __name__ == '__main__':
    raise SystemExit(main())
