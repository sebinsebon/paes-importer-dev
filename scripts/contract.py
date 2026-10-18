"""Check distributed contract bytes against a reviewed canonical 0.2.0 lock.

The optional canonical directory is authoritative. This tool never changes it or
the selected runtime; --write-lock explicitly records its reviewed manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from dev_paths import DEV_ROOT, runtime_root, output_path, unlinked_path

LOCK = DEV_ROOT/'contract.lock.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract_records(document):
    if (document.get('format') != 'paessed-contract-sync' or
            document.get('version') != '0.2.0' or document.get('container_version') != '0.1.0'):
        raise ValueError('Expected canonical PAESSED 0.2.0 / container 0.1.0')
    records = document['files']
    seen = set()
    for row in records:
        name = row['path']; path = PurePosixPath(name)
        if (not name or path.is_absolute() or path.as_posix()!=name or '..' in path.parts or
                '\\' in name or ':' in name or name in seen):
            raise ValueError('Unsafe or duplicate canonical path')
        if len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256']):
            raise ValueError('Invalid canonical digest')
        seen.add(name)
    if not {'shared/schemas/final.schema.json','shared/schemas/final-0.1.schema.json'}.issubset(seen):
        raise ValueError('Canonical schemas missing from lock')
    return sorted(records, key=lambda row: row['path'])


def check(runtime, lock=LOCK, canonical=None):
    locked = json.loads(Path(lock).read_text(encoding='utf-8'))
    records = contract_records(locked)
    roots = [('runtime', runtime)]
    if canonical is not None:
        canonical = unlinked_path(canonical).resolve(strict=True)
        manifest = json.loads((canonical/'sincronizacion.json').read_text(encoding='utf-8'))
        if contract_records(manifest) != records:
            raise ValueError('Canonical manifest and reviewed lock diverge')
        roots.append(('canonical', canonical/'0.2.0'))
    for label, root in roots:
        for row in records:
            path = unlinked_path(root/row['path'])
            if not path.is_file() or sha(path) != row['sha256']:
                raise ValueError(label + ' contract divergence: ' + row['path'])
    return {'version':'0.2.0','container_version':'0.1.0','resources':len(records),
            'canonical_checked':canonical is not None,'lock_sha256':sha(Path(lock))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--contract-root',type=Path)
    parser.add_argument('--lock',type=Path,default=LOCK)
    parser.add_argument('--write-lock',action='store_true')
    args=parser.parse_args(); runtime=runtime_root(args.runtime)
    if args.write_lock:
        if not args.contract_root: parser.error('--write-lock requires the reviewed --contract-root')
        canonical=unlinked_path(args.contract_root).resolve(strict=True)
        manifest=json.loads((canonical/'sincronizacion.json').read_text(encoding='utf-8'))
        contract_records(manifest)
        # Validate all resources before replacing this development lock.
        for row in manifest['files']:
            for root in (canonical/'0.2.0',runtime):
                if sha(unlinked_path(root/row['path'])) != row['sha256']:
                    raise ValueError('Review divergence before writing a contract lock')
        destination=output_path(args.lock,runtime)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(check(runtime,args.lock,args.contract_root),indent=2))


if __name__=='__main__': main()
