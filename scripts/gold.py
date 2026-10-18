"""Read-only Gold inventory and compatible derivative; never certifies comprehension."""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from dev_paths import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT / 'shared/scripts'))

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def load_reference(file):
    file = Path(file)
    if file.suffix.lower() in ('.zip', '.paessed'):
        from package_io import inspect_package
        inspect_package(file)
        with zipfile.ZipFile(file) as archive:
            inventory = checked_archive(archive)
            data = json.loads(archive.read('final.json'))
        return data, inventory
    data=json.loads(file.read_text(encoding='utf-8-sig'))
    from package_io import validate
    validate(data)
    return data, []

def checked_archive(archive):
    entries = archive.infolist()
    names = [e.filename for e in entries]
    if len(entries) > 10000 or sum(e.file_size for e in entries) > 256 * 1024 * 1024:
        raise ValueError('Archive exceeds inventory limits')
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('Duplicate archive path')
    for entry in entries:
        name = entry.filename
        pure = PurePosixPath(name)
        if not name or pure.is_absolute() or '\\' in name or ':' in name or any(p in ('', '.', '..') for p in name.split('/')):
            raise ValueError('Unsafe archive path: ' + name)
        if entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError('Directories or symlinks are unsupported')
    if not {'final.json', 'manifest.json'}.issubset(names):
        raise ValueError('Missing final.json or manifest.json')
    manifest = json.loads(archive.read('manifest.json'))
    if manifest.get('format') != 'paessed-package' or manifest.get('schema_version') != '0.1.0':
        raise ValueError('Unsupported manifest')
    records = manifest.get('files', [])
    indexed = {r['path']: r for r in records}
    if len(indexed) != len(records) or set(indexed) != set(names) - {'manifest.json'}:
        raise ValueError('Manifest inventory mismatch')
    inventory = []
    for name in names:
        blob = archive.read(name)
        record = {'path': name, 'bytes': len(blob), 'sha256': sha(blob)}
        if name != 'manifest.json' and any(record[k] != indexed[name].get(k) for k in ('bytes', 'sha256')):
            raise ValueError('Manifest integrity failure: ' + name)
        inventory.append(record)
    return inventory

def inventory(package, taxonomy=None, sources=()):
    package = Path(package)
    with zipfile.ZipFile(package) as archive:
        files = checked_archive(archive)
        data = json.loads(archive.read('final.json'))
    questions = data['questions']
    ids = [q['id'] for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate question IDs')
    identities = [(q['source_id'], q['number']) for q in questions]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate source/number')
    expected = {q['id'] for q in data['exam']['expected_questions']}
    if set(ids) != expected:
        raise ValueError('Question coverage mismatch')
    source_records = []
    for file in sources:
        file = Path(file)
        digest = sha(file.read_bytes())
        source_records.append({'name': file.name, 'sha256': digest,
            'matches_declared_source': any(s.get('sha256') == digest for s in data['sources'])})
    tax = None
    if taxonomy:
        file = Path(taxonomy)
        value = json.loads(file.read_text(encoding='utf-8-sig'))
        annotations = value.get('questions') if isinstance(value, dict) else None
        if not isinstance(annotations, dict) or set(annotations) != set(ids):
            raise ValueError('Taxonomy question coverage mismatch')
        for qid, row in annotations.items():
            if set(row) != {'eje', 'subeje', 'en_temario'} or row['en_temario'] not in ('si', 'no', 'dudoso'):
                raise ValueError('Invalid taxonomy annotation: ' + qid)
        tax = {'questions': len(annotations), 'membership_counts': {label: sum(r['en_temario'] == label for r in annotations.values()) for label in ('si', 'no', 'dudoso')}, 'name': file.name, 'sha256': sha(file.read_bytes()), 'shape': type(value).__name__,
               'adjudication': 'pending', 'role': 'reference_annotation_not_runtime_classifier'}
    return {'format': 'paessed-gold-inventory', 'schema_version': '0.1.0',
        'package_sha256': sha(package.read_bytes()), 'package_name': package.name,
        'questions': len(ids), 'question_ids': ids, 'assets': len(data['assets']), 'files': files,
        'sources': source_records, 'taxonomy': tax,
        'inherited_status_counts': {key: sum(q[key]['status'] in ('verified', 'reviewed') for q in questions)
                                   for key in ('answer', 'explanation', 'fidelity')},
        'certification': {'status': 'pending', 'independent_review': 'not_performed',
                          'visual_review': 'not_performed', 'web_roundtrip': 'not_performed'},
        'warning': 'Inherited reviewed/verified states are declarations, not Gold certification.'}

def safe_output(output):
    output = Path(output).absolute()
    boundary = WORK_ROOT.resolve()
    resolved = output.resolve()
    if resolved == boundary or boundary not in resolved.parents:
        raise ValueError('Gold outputs must be a fresh directory within this checkout tmp/')
    # Detect junctions and symlinks even when they resolve back into tmp.
    for part in (output, *output.parents):
        if part == ROOT.parent:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Linked output path is forbidden')
    if output.exists():
        raise ValueError('Output exists; use a new dossier directory')
    return output

def prepare(package, output, taxonomy=None, sources=()):
    output = safe_output(output)
    report = inventory(package, taxonomy, sources)
    with zipfile.ZipFile(package) as archive:
        data = json.loads(archive.read('final.json'))
        keep = {'final.json'} | {r['path'] for r in data['assets'] + data['evidence']}
        if not keep.issubset(archive.namelist()):
            raise ValueError('Missing referenced resource')
        blobs = {name: archive.read(name) for name in sorted(keep)}
        removed = {name: archive.read(name) for name in archive.namelist() if name not in keep | {'manifest.json'}}
    manifest = {'format': 'paessed-package', 'schema_version': '0.1.0', 'files': [
        {'path': name, 'bytes': len(blob), 'sha256': sha(blob)} for name, blob in blobs.items()]}
    blobs['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, blob in blobs.items():
            archive.writestr(name, blob)
    # Structural validity is required before any dossier is written.
    from package_io import inspect_package
    report['derivative_validation'] = inspect_package(io.BytesIO(buffer.getvalue()))
    report['derivative_sha256'] = sha(buffer.getvalue())
    report['removed_files'] = sorted(removed)
    output.mkdir(parents=True)
    for name, blob in removed.items():
        destination = output / 'original-extras' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
    for name in ('package.zip', 'package.paessed'):
        (output / name).write_bytes(buffer.getvalue())
    (output / 'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'certification.json').write_text(json.dumps(report['certification'], indent=2) + '\n', encoding='utf-8')
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--taxonomy')
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--output', help='Fresh directory under checkout tmp/; omit for read-only inventory')
    args = parser.parse_args()
    result = prepare(args.package, args.output, args.taxonomy, args.source) if args.output else inventory(args.package, args.taxonomy, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
