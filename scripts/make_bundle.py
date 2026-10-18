"""Build a byte-reproducible bundle from the exact verified runtime allowlist."""
import argparse
import zipfile
from pathlib import Path
from dev_paths import output_path, runtime_root
from integrity import sha256, verify_release


def build(runtime, output, config=None):
    output = output_path(output, runtime)
    if output.exists():
        raise ValueError('Preserve existing bundle; choose another filename')
    manifest = verify_release(runtime, config)
    paths = sorted([record['path'] for record in manifest['files']] + ['release.json'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle, zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for name in paths:
            item = zipfile.ZipInfo('paes-importer/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_STORED
            bundle.writestr(item, (runtime / name).read_bytes())
    return {'path': str(output), 'sha256': sha256(output), 'files': len(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--distribution')
    args = parser.parse_args()
    result = build(runtime_root(args.runtime), args.output, args.distribution)
    print(result['path'])


if __name__ == '__main__':
    main()
