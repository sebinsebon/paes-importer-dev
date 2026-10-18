"""Read-only physical inventories, provenance, and exact distribution validation."""
import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath
from dev_paths import DEV_ROOT, linked, unlinked_path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(root):
    root = Path(root)
    result = {}
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted(names + files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if relative == '.git':
                if name in names:
                    names.remove(name)
                continue
            if linked(path):
                result[relative] = {'kind': 'link', 'target': os.readlink(path)}
                if name in names:
                    names.remove(name)
            elif path.is_dir():
                result[relative + '/'] = {'kind': 'directory'}
            elif path.is_file():
                result[relative] = {'kind': 'file', 'sha256': sha256(path), 'size': path.stat().st_size}
    return result


def git_sha(root):
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(Path(root).resolve()).replace('\\','/'), '-C', str(root), 'rev-parse', 'HEAD'],
                            text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def allowed_files(config=None):
    config = Path(config or DEV_ROOT / 'distribution.json')
    names = json.loads(config.read_text(encoding='utf-8'))['files']
    if not isinstance(names, list) or len(names) != len(set(names)):
        raise ValueError('Distribution files must be a unique list')
    for name in names:
        if not isinstance(name, str):
            raise ValueError('Distribution path must be a string')
        path = PurePosixPath(name)
        if (path.is_absolute() or path.as_posix() != name or '..' in path.parts
                or '\\' in name or ':' in name or name == 'release.json'):
            raise ValueError('Unsafe distribution path: ' + str(name))
    return sorted(names)


def records(runtime, config=None):
    result = []
    for name in allowed_files(config):
        path = unlinked_path(runtime / name)
        if not path.is_relative_to(runtime) or not path.is_file():
            raise ValueError('Missing or unsafe distributed file: ' + name)
        result.append({'path': name, 'sha256': sha256(path)})
    return result


def verify_release(runtime, config=None):
    release = unlinked_path(runtime / 'release.json')
    manifest = json.loads(release.read_text(encoding='utf-8'))
    current = records(runtime, config)
    if manifest.get('files') != current:
        old = {record['path']: record['sha256'] for record in manifest.get('files', [])}
        new = {record['path']: record['sha256'] for record in current}
        changed = sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
        raise ValueError('Release manifest mismatch: ' + ', '.join(changed))
    return manifest
