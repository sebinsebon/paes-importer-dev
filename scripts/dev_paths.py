"""Explicit development/runtime roots; never discover a second runtime copy."""
import os
import stat
import sys
from pathlib import Path

DEV_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def linked(path):
    path = Path(path)
    try:
        information = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(information.st_mode) or bool(
        getattr(information, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def unlinked_path(path):
    """Check lexical ancestors before resolving, including Windows junctions."""
    path = Path(os.path.abspath(path))
    if any(linked(part) for part in (path, *path.parents)):
        raise ValueError('Linked path rejected: ' + str(path))
    return path


def runtime_root(value=None):
    value = value or os.environ.get('PAES_IMPORTER_RUNTIME')
    if not value:
        raise ValueError('Supply --runtime or PAES_IMPORTER_RUNTIME')
    root = unlinked_path(value).resolve(strict=True)
    if root == DEV_ROOT or not (root / 'SKILL.md').is_file():
        raise ValueError('Runtime root must be the independent skill containing SKILL.md')
    return root


def output_path(path, runtime=None, within_dev=False):
    path = unlinked_path(path)
    runtime = runtime or RUNTIME_ROOT
    if runtime is not None and (path == runtime or path.is_relative_to(runtime)):
        raise ValueError('Development output must be outside runtime')
    if within_dev and not path.is_relative_to(DEV_ROOT):
        raise ValueError('Output must remain inside development root')
    return path


RUNTIME_ROOT = runtime_root() if os.environ.get('PAES_IMPORTER_RUNTIME') else None
WORK_ROOT = output_path(os.environ.get('PAES_IMPORTER_WORK', DEV_ROOT / 'tmp'))
for directory in (DEV_ROOT / 'scripts', DEV_ROOT / 'examples',
                  *([RUNTIME_ROOT / 'scripts', RUNTIME_ROOT / 'shared/scripts'] if RUNTIME_ROOT else [])):
    sys.path.insert(0, str(directory))
