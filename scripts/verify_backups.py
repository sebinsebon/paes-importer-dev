"""Read-only verification of migration backups and the protected RC3 reference."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
from dev_paths import DEV_ROOT, output_path, unlinked_path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, records, name, exact=False):
    root=unlinked_path(root).resolve(strict=True)
    for row in records:
        path=unlinked_path(root/row['path'])
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(name+': missing/unsafe '+row['path'])
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise ValueError(name+': changed '+row['path'])
    if exact:
        actual=set()
        for directory,names,files in os.walk(root,followlinks=False):
            base=Path(directory)
            for child in names:
                p=base/child
                if p.is_symlink() or p.is_junction():
                    raise ValueError(name+': unexpected linked directory')
            for child in files:
                p=unlinked_path(base/child)
                actual.add(p.relative_to(root).as_posix())
        if actual!={row['path'] for row in records}:
            raise ValueError(name+': file inventory changed')
    return {'name':name,'files':len(records),'status':'verified'}


def test_names(path):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    return {(c.name,n.name) for c in tree.body if isinstance(c,ast.ClassDef)
            for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rc3',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();destination=output_path(args.report, within_dev=True)
    if destination.exists(): raise ValueError('Preserve existing report')
    base=DEV_ROOT/'backups/pre-separation';checks=[]
    for directory,manifest in [('tracked','tracked-manifest.json'),('tmp','tmp-manifest.json'),('.venv','venv-manifest.json')]:
        checks.append(verify(base/directory,json.loads((base/manifest).read_text(encoding='utf-8')),directory))
    checks.append(verify(args.rc3,json.loads((base/'rc3-manifest.json').read_text(encoding='utf-8')),'TESLA RC3',exact=True))
    for directory in ('canonical-before',):
        root=DEV_ROOT/'backups'/directory
        checks.append(verify(root,json.loads((root/'manifest.json').read_text(encoding='utf-8')),directory))
    stray=base/'stray-caches';records=json.loads((stray/'manifest.json').read_text(encoding='utf-8'))
    checks.append(verify(stray,[{**r,'path':'__pycache__/'+Path(r['path']).name} for r in records],'stray-caches'))
    original=base/'tracked/tests';retained=0
    for source in original.glob('test*.py'):
        before=test_names(source);after=test_names(DEV_ROOT/'tests'/source.name)
        missing=before-after
        if missing: raise ValueError('Lost original tests: '+repr(missing))
        retained+=len(before)
    checks.append({'name':'original_test_methods','retained':retained,'status':'verified'})
    # A preserved junction is checked as a link, never traversed for hashing.
    for row in json.loads((base/'links.json').read_text(encoding='utf-8')):
        link=base/row['path']
        actual=str(link.readlink()).removeprefix('\\\\?\\')
        if not link.is_junction() or os.path.normcase(actual)!=os.path.normcase(row['target']):
            raise ValueError('Archived junction identity changed')
    checks.append({'name':'archived_junctions','links':1,'traversed':False,'status':'verified'})
    report={'checks':checks,'bundle_sha256':sha(DEV_ROOT/'backups/pre-separation.bundle')}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as handle: json.dump(report,handle,indent=2);handle.write('\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
