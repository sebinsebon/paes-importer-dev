"""Maintain portable, hash-pinned contract copies; no runtime absolute paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / '0.2.0'
MANIFEST = ROOT / 'sincronizacion.json'
FILES = [
    'shared/references/content-contract.md', 'shared/references/package-contract.md',
    'shared/references/curriculum-contract.md', 'shared/references/curriculum-m1.json',
    'shared/schemas/final.schema.json', 'shared/schemas/final-0.1.schema.json',
    'shared/scripts/package_io.py', 'shared/scripts/lab.py', 'shared/scripts/curriculum.py',
    'shared/scripts/quality.py',
    'shared/scripts/check_final.cjs', 'shared/scripts/check_package.cjs',
    'shared/scripts/check_math.cjs', 'viewer/validator.js', 'viewer/package-reader.js',
    'viewer/vendor/jszip/dist/jszip.min.js', 'viewer/vendor/jszip/LICENSE.markdown',
    'viewer/vendor/katex/dist/katex.min.js', 'viewer/vendor/katex/LICENSE',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file(base, relative):
    path = base / relative
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f'Path escapes selected root: {path}')
    return path


def main():
    global ROOT, VERSION, MANIFEST
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['adopt', 'check', 'sync', 'validate'])
    parser.add_argument('--importer', type=Path)
    parser.add_argument('--web', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--contract-root', type=Path,
                        help='Canonical contract directory (required when running a versioned source copy)')
    args = parser.parse_args()
    if args.contract_root:
        ROOT = args.contract_root.resolve(strict=True)
        VERSION = ROOT / '0.2.0'
        MANIFEST = ROOT / 'sincronizacion.json'
    if args.command == 'adopt':
        if args.importer is None:
            parser.error('adopt requires --importer (reviewed implementation source)')
        records = []
        for relative in FILES:
            source = safe_file(args.importer, relative)
            target = safe_file(VERSION, relative)
            if not source.is_file():
                raise ValueError(f'Missing reviewed source: {source}')
            records.append((relative, source, target, sha(source)))
        for relative, source, target, digest in records:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        manifest = {'format': 'paessed-contract-sync', 'version': '0.2.0',
                    'container_version': '0.1.0',
                    'files': [{'path': relative, 'sha256': digest}
                              for relative, _, _, digest in records]}
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Adopted {len(records)} reviewed contract resources')
        return
    if args.command in ('check', 'sync'):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        errors, copies, count = [], [], 0
        for record in manifest['files']:
            relative, expected = record['path'], record['sha256']
            source = safe_file(VERSION, relative)
            if not source.is_file() or sha(source) != expected:
                errors.append(f'Canonical hash mismatch: {relative}')
                continue
            if args.importer:
                target = safe_file(args.importer, relative)
                if args.command == 'sync':
                    copies.append((source, target))
                elif not target.is_file() or sha(target) != expected:
                    errors.append(f'Importer divergence: {relative}')
            if args.web and relative in ('viewer/validator.js', 'viewer/package-reader.js'):
                target = safe_file(args.web, 'lib/paessed-runtime/' + Path(relative).name)
                if args.command == 'sync':
                    copies.append((source, target))
                elif not target.is_file() or sha(target) != expected:
                    errors.append(f'Web divergence: {target.name}')
            count += 1
        relocations = ROOT / 'traslados.json'
        relocation_count = 0
        if relocations.exists():
            for record in json.loads(relocations.read_text(encoding='utf-8'))['files']:
                destination = safe_file(ROOT.parent, record['current'])
                if not destination.is_file() or sha(destination) != record['sha256'] or destination.stat().st_size != record['bytes']:
                    errors.append(f'Relocation integrity failure: {record["current"]}')
                relocation_count += 1
        if errors:
            raise ValueError('\n'.join(errors))
        for source, target in copies:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        print(f'{args.command}: {count} canonical resources, {relocation_count} archived/reference hashes OK; {len(copies)} copies written')
        return
    if args.package is None:
        parser.error('validate requires --package')
    sys.path.insert(0, str(VERSION / 'shared/scripts'))
    from package_io import inspect_package
    result = inspect_package(args.package.resolve())
    print(json.dumps({key: result[key] for key in (
        'valid', 'questions', 'assets', 'files', 'warnings', 'semantic_correctness')},
        ensure_ascii=False, indent=2))
    print('Structural validation only; Gold and semantic accuracy are separate.')


if __name__ == '__main__':
    main()
