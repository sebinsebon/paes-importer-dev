"""Private maintenance reports are confined to checkout tmp; no overwrite."""
from pathlib import Path
from dev_paths import DEV_ROOT as ROOT, WORK_ROOT

def write_report(file, text):
    file = Path(file).absolute()
    boundary = WORK_ROOT.resolve()
    if boundary not in file.resolve().parents:
        raise ValueError('Reports must remain within checkout tmp/')
    for part in (file, *file.parents):
        if part == ROOT.parent:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Linked report path is forbidden')
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
