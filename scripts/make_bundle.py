"""Pack verified skill files for attachment, excluding generated/private data."""
import argparse
import json
import zipfile
from pathlib import Path
import release
ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); args = parser.parse_args()
    output = Path(args.output).absolute()
    if output.exists(): raise SystemExit('Preserve existing bundle; choose another filename')
    manifest = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    if manifest['files'] != release.records(): raise SystemExit('Release changed; validate and regenerate before bundling')
    if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (output,*output.parents)):
        raise SystemExit('Linked output path rejected')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as handle, zipfile.ZipFile(handle,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for record in manifest['files']:
            bundle.write(ROOT / record['path'], 'paes-importer/' + record['path'])
        bundle.write(ROOT / 'release.json','paes-importer/release.json')
    print(str(output))
