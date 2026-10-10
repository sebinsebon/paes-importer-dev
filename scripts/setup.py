"""Create a private environment for this checkout. Requires Python 3.12+ and Node."""
import argparse
import shutil
import subprocess
import sys
import venv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--dev', action='store_true'); args = p.parse_args()
    if sys.version_info < (3, 12): raise SystemExit('Python 3.12+ required')
    node = shutil.which('node')
    if not node: raise SystemExit('Node.js 18+ required on PATH')
    version = subprocess.run([node, '--version'], capture_output=True, text=True, check=True).stdout.strip()
    if not version.startswith('v') or not version[1:].split('.')[0].isdigit() or int(version[1:].split('.')[0]) < 18:
        raise SystemExit('Node.js 18+ required; found ' + version)
    environment = ROOT / '.venv'
    if environment.exists(): raise SystemExit('Environment exists; use its Python to install requirements')
    tmp = ROOT / 'tmp'; tmp.mkdir(exist_ok=True)
    import os
    os.environ.update(TEMP=str(tmp), TMP=str(tmp), PIP_CACHE_DIR=str(tmp / 'pip-cache'))
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    requirements = ROOT / ('requirements-dev.txt' if args.dev else 'requirements.txt')
    tmp = ROOT / 'tmp'; tmp.mkdir(exist_ok=True)
    import os
    env = {**os.environ, 'TEMP': str(tmp), 'TMP': str(tmp), 'PIP_CACHE_DIR': str(tmp / 'pip-cache')}
    subprocess.run([str(python), '-B', '-m', 'pip', 'install', '-r', str(requirements)], check=True, env=env)
    print('Ready: ' + str(python))
