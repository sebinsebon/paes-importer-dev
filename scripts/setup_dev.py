"""Install explicit runtime and development requirements into an external dev venv."""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path
from dev_paths import DEV_ROOT, output_path, runtime_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--env-dir', type=Path, default=DEV_ROOT / '.venv')
    args = parser.parse_args()
    runtime = runtime_root(args.runtime)
    environment = output_path(args.env_dir, runtime, within_dev=True)
    cache = output_path(DEV_ROOT / 'caches/pip', runtime, within_dev=True)
    work = output_path(DEV_ROOT / 'tmp', runtime, within_dev=True)
    cache.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    if not environment.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    env = {**os.environ, 'PIP_CACHE_DIR': str(cache), 'PYTHONDONTWRITEBYTECODE': '1',
           'TEMP': str(work), 'TMP': str(work), 'TMPDIR': str(work)}
    subprocess.run([str(python), '-B', '-m', 'pip', 'install', '--disable-pip-version-check',
                    '-r', str(runtime / 'requirements.txt'), '-r', str(DEV_ROOT / 'requirements-dev.txt')],
                   env=env, check=True, cwd=DEV_ROOT)
    print(str(python))


if __name__ == '__main__':
    main()
