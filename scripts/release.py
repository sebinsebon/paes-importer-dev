"""Check a runtime manifest, or explicitly author its current-version hashes."""
import argparse
import json
from dev_paths import runtime_root
from integrity import records as file_records, verify_release


def records(runtime=None, config=None):
    return file_records(runtime_root(runtime), config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime')
    parser.add_argument('--distribution')
    parser.add_argument('--write', action='store_true', help='Intentionally replace only release.json file hashes')
    args = parser.parse_args()
    root = runtime_root(args.runtime)
    if args.write:
        manifest = json.loads((root / 'release.json').read_text(encoding='utf-8'))
        if not manifest.get('version') or not manifest.get('protocol_version'):
            raise ValueError('Existing release must declare version and protocol_version')
        manifest['files'] = file_records(root, args.distribution)
        (root / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    else:
        manifest = verify_release(root, args.distribution)
    print(str(len(manifest['files'])) + ' release files verified; version ' + manifest['version'])


if __name__ == '__main__':
    main()
