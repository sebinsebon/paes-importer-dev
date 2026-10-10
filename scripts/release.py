"""Create or check the public bundle manifest; excludes private/generated artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', 'tmp', '__pycache__', 'EnsayosPaessedOutput', '.pytest_cache', 'Output', '.work'}
DIRECTORIES = {'scripts', 'shared', 'viewer', 'references', 'tests', 'examples', 'docs', '.github'}
ROOT_FILES = {'SKILL.md', 'README.md', 'AGENTS.md', 'LICENSE', 'NOTICE.md', 'requirements.txt', 'requirements-dev.txt', 'run.ps1', '.gitignore', '.gitattributes'}

def records():
    return [{'path': p.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(ROOT.rglob('*')) if p.is_file()
            and not any(part in EXCLUDED for part in p.relative_to(ROOT).parts)
            and p.name != 'release.json' and p.suffix.lower() not in ('.pdf', '.zip', '.paessed', '.png')
            and (p.relative_to(ROOT).parts[0] in DIRECTORIES or p.relative_to(ROOT).as_posix() in ROOT_FILES)]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    manifest = {'version': '1.0.0-portable', 'protocol_version': '0.3.0', 'files': records()}
    if args.write:
        (ROOT / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    else:
        if json.loads((ROOT / 'release.json').read_text(encoding='utf-8')) != manifest:
            raise SystemExit('Release differs; regenerate intentionally with --write')
        print(str(len(manifest['files'])) + ' release files verified')
