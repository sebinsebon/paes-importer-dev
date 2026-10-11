"""Localized evidence coverage checks. Coverage is not proof of comprehension."""
from lab import artifact_path, bbox, digest


def field_paths(question):
    from package_io import located_blocks
    paths = [p for p, b in located_blocks(question) if not p.startswith('explanation.')]
    return {'stem': ['stem'], 'options': ['options/' + o['label'] for o in question['options']] or ['options'],
            'assets_math': [p for p, b in located_blocks(question) if b['type'] in ('math', 'table', 'image') and not p.startswith('explanation.')] or ['stem'],
            'answer': ['answer'], 'explanation': ['explanation'], 'consistency': ['stem', 'options', 'answer', 'explanation']}


def overlaps(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def validate_geometry(candidate, catalog):
    pages = {(p['source_id'], p['page']): p for p in catalog['pages']}
    for q in candidate['questions']:
        for r in q['regions']:
            page = pages.get((q['source_id'], r['page']))
            if not page:
                raise ValueError(q['id'] + ': unknown catalog page')
            bbox(r['bbox'], page['width'], page['height'])
    for resource in candidate['assets'] + candidate['evidence']:
        page = pages.get((resource['source_id'], resource['page']))
        if not page:
            raise ValueError('Resource page absent from catalog')
        bbox(resource['bbox'], page['width'], page['height'])


def validate_citations(question, dimension, check, candidate, root, selection=None, key=None, provenance=None):
    resources = {r['id']: r for r in candidate['assets'] + candidate['evidence']}
    expected = set(field_paths(question)[dimension])
    if set(check.get('field_paths', [])) != expected:
        raise ValueError(question['id'] + ': evidence field coverage mismatch for ' + dimension)
    refs = check.get('evidence', [])
    if not refs:
        raise ValueError('Localized evidence required')
    covered = set()
    regions = question['regions']
    if selection and selection.get('field_regions', {}).get(dimension):
        regions = selection['field_regions'][dimension]
    source = question['source_id']
    # Answer/solution evidence follows its own frozen source, not the exam page.
    source_entry = key if dimension == 'answer' else provenance if dimension == 'explanation' else None
    if source_entry and source_entry.get('source_id'):
        source = source_entry['source_id']
        regions = [{'page': source_entry['page'], 'bbox': None}]
    for citation in refs:
        resource = resources.get(citation.get('id'))
        if (not resource or resource['sha256'] != citation.get('sha256') or
                not isinstance(citation.get('observation'), str) or not citation['observation'].strip() or
                digest(artifact_path(root, resource['path'])) != citation['sha256']):
            raise ValueError('Unknown, altered or unjustified source evidence')
        if resource['source_id'] != source or not any(
                resource['page'] == region['page'] and (region.get('bbox') is None or overlaps(resource['bbox'], region['bbox']))
                for region in regions):
            raise ValueError(question['id'] + ': evidence does not cover the question field/source region')
        if selection and not selection.get('field_regions') and source == question['source_id'] and dimension in ('stem', 'options'):
            if resource['page'] != selection['page']:
                raise ValueError(question['id'] + ': evidence misses frozen primary page')
        fields = citation.get('fields', [])
        if not isinstance(fields, list) or not fields or not set(fields).issubset(expected):
            raise ValueError('Evidence citation must name covered field paths')
        covered.update(fields)
    if covered != expected:
        raise ValueError(question['id'] + ': fields without source evidence')
    return True


def validate_mapping(candidate, selection):
    """Bind observed option coverage and pages outside model-editable content."""
    mapped = {q['id']:q for q in selection['expected_questions']}
    for q in candidate['questions']:
        record = mapped[q['id']]
        if not q['regions']:
            continue  # Explicit unresolved placeholders remain representable.
        if record.get('mapping_pending'):
            continue
        labels = record.get('option_labels')
        if labels is not None and [o['label'] for o in q['options']] != labels:
            raise ValueError(q['id'] + ': options differ from frozen observed labels')
        observed = record.get('regions') or [{'page':record['page'], 'bbox':None}]
        for r in q['regions']:
            if not any(r['page'] == old['page'] and (old.get('bbox') is None or
                       all((r['bbox'][i] >= old['bbox'][i] - .01) if i < 2 else
                           (r['bbox'][i] <= old['bbox'][i] + .01) for i in range(4))) for old in observed):
                raise ValueError(q['id'] + ': question region outside frozen source map')
