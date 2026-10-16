"""Adapt a frozen Stage 1 draft to pending 0.2.0 proposals, never to Gold."""
import copy
import hashlib
import json

from draft_v1.draft_contract import validate_v1
from lab import artifact_path, bbox, inside, no_links, read, relative_path
from checkpoints import commit, json_bytes
from evidence import validate_geometry, validate_mapping
from output_policy import require_official_final
from package_io import validate
from pipeline import empty_question


def adapt(folder, draft_path):
    """Called under importer candidate lock, after prepare/map/route.

    The complete draft and its resources stay in reports/drafts/<SHA256>.
    Source identity and original number, not array position, map questions.
    """
    path = no_links(draft_path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    archive = 'reports/drafts/' + sha
    candidate_bytes = (folder / 'candidate.json').read_bytes()
    candidate = json.loads(candidate_bytes)
    require_official_final(candidate)
    if (folder / archive / 'report.json').exists():
        raise ValueError('Draft already adapted; use existing report and continue ingest/cotejo')
    if any(q != empty_question(q) for q in candidate['questions']):
        raise ValueError('Adapt only an untouched mapped candidate; preserve existing proposals in another run')
    draft = json.loads(raw.decode('utf-8-sig'))
    if draft.get('schema_version') != '1.0.0':
        raise ValueError('Only draft.json v1 (1.0.0) is supported; no implicit legacy conversion')
    validate_v1(draft, artifact_root=path.parent, check_files=True)

    # Freeze checked bytes; later validation reads the same captured resources.
    originals = {}
    for collection in ('assets', 'evidence'):
        for resource in draft[collection]:
            relative_path(resource['path'], collection)
            data = artifact_path(path.parent, resource['path'], collection).read_bytes()
            if hashlib.sha256(data).hexdigest() != resource['sha256'].lower():
                raise ValueError('Draft resource changed: ' + resource['path'])
            originals[resource['path']] = data

    sources = {}
    for old in draft['sources']:
        matches = [s for s in candidate['sources'] if s['sha256'].lower() == old['sha256'].lower()
                   and s['page_count'] == old['page_count']]
        if len(matches) != 1:
            raise ValueError('Draft source must match exactly one prepared PDF hash/page count: ' + old['id'])
        if matches[0]['id'] in sources.values():
            raise ValueError('Ambiguous duplicate draft source identity')
        sources[old['id']] = matches[0]['id']
    pages = {p['id']: p for p in draft['pages']}
    regions = {r['id']: r for r in draft['regions']}
    contexts = {c['id']: c for c in draft['contexts']}
    assets = {a['asset_id']: a for a in draft['assets']}
    catalog_pages = {(p['source_id'], p['page']): p for p in read(folder / 'catalog.json')['pages']}

    def convert_regions(ids, source):
        output = []
        for rid in ids:
            region = regions[rid]
            page = pages[region['page_id']]
            actual = sources[page['source_id']]
            if actual != source or page['coordinate_system'] != 'top_left_pdf_points':
                raise ValueError('Region/context is not from the question PDF')
            prepared = catalog_pages.get((source, page['page_number']))
            if not prepared or any(abs(page[k] - prepared[k]) > .01 for k in ('width', 'height')):
                raise ValueError('Draft page dimensions differ from prepared PDF')
            item = {'page': page['page_number'], 'bbox': region['bbox']}
            if item not in output:
                output.append(item)
        return output

    resources = {}
    payloads = {}

    def image(old_id, source):
        old = assets[old_id]
        if old.get('mime') != 'image/png':
            raise ValueError('Draft asset is not PNG: ' + old_id)
        locations = convert_regions(old['region_ids'], source)
        if len(locations) != 1:
            raise ValueError('Asset needs one unambiguous source region: ' + old_id)
        # Content-addressed IDs avoid relying on extractor-specific identifiers.
        resource_id = 'draft-' + hashlib.sha256((sha + ':' + old_id).encode()).hexdigest()[:32]
        dest = 'assets/draft-' + sha + '/' + resource_id + '.png'
        box = locations[0]['bbox']
        if old.get('source_bbox') is not None:
            page = catalog_pages[(source, locations[0]['page'])]
            # Extractor source_bbox is already in visible top-left PDF points.
            box = old['source_bbox']
            bbox(box, page['width'], page['height'])
            region_box = locations[0]['bbox']
            if any((box[i] < region_box[i] - .5) if i < 2 else
                   (box[i] > region_box[i] + .5) for i in range(4)):
                raise ValueError('Asset crop lies outside its source region: ' + old_id)
        resource = {'id': resource_id, 'path': dest, 'sha256': old['sha256'].lower(),
                    'mime': 'image/png', 'source_id': source, 'page': locations[0]['page'], 'bbox': box}
        if resource_id in resources and resources[resource_id] != resource:
            raise ValueError('Asset has conflicting provenance')
        resources[resource_id] = resource
        payloads[dest] = originals[old['path']]
        return {'type': 'image', 'asset_id': resource_id,
                'alt': 'Figura de la fuente; descripción pendiente de cotejo'}

    def blocks(items, source):
        result = []
        for block in items:
            kind = block['type']
            if kind == 'text':
                value = {'type': kind, 'text': block['text']}
            elif kind == 'math':
                value = {'type': kind, 'latex': block['latex'], 'display': block['display']}
            elif kind == 'table':
                value = {'type': kind, 'rows': [[blocks(cell['blocks'], source) for cell in row['cells']]
                                               for row in block['rows']]}
            elif kind == 'image':
                value = image(block['asset_id'], source)
            elif kind == 'unresolved':
                value = {'type': kind, 'reason': block['reason']}
            else:
                raise ValueError('Unsupported draft block: ' + str(kind))
            result.append(value)
        return result

    expected = {(q['source_id'], q['number']): q for q in candidate['questions']}
    seen = set()
    mapped = []
    proposals = []
    for old in draft['questions']:
        locations = [pages[regions[r]['page_id']]['source_id'] for r in old['region_ids']]
        source = sources[locations[0]]
        identity = (source, old['original_number'])
        if identity not in expected or identity in seen:
            raise ValueError('Draft question is absent, duplicate or ambiguous in frozen selection: ' + str(identity))
        seen.add(identity)
        q = copy.deepcopy(expected[identity])
        related = [contexts[c] for c in old['context_ids']]
        q['regions'] = convert_regions([rid for ctx in related for rid in ctx['region_ids']] + old['region_ids'], source)
        q['stem'] = [b for ctx in related for b in blocks(ctx['blocks'], source)] + blocks(old['stem'], source)
        if not q['stem']:
            q['stem'] = [{'type': 'unresolved', 'reason': 'Extracción sin enunciado utilizable'}]
        q['options'] = [{'label': o['label'], 'blocks': blocks(o['blocks'], source)} for o in old['options']]
        q['issues'] = ['DRAFT_REVIEW_PENDING', 'CURRICULUM_PENDING']
        for issue in draft['issues']:
            if issue['target_id'] == old['id']:
                q['issues'].append('DRAFT:' + issue['code'] + ': ' + issue['message'])
        proposals.append(q)
        mapped.append({'draft_question_id': old['id'], 'question_id': q['id'],
                       'context_ids': old['context_ids'], 'extraction_status': old['extraction_status']})
    if seen != set(expected):
        raise ValueError('Draft coverage differs from the complete frozen selection')
    tentative = copy.deepcopy(candidate)
    by_id = {q['id']: q for q in proposals}
    tentative['questions'] = [by_id[q['id']] for q in candidate['questions']]
    tentative['assets'] += list(resources.values())
    validate(tentative, blob_reader=lambda name: payloads[name] if name in payloads else artifact_path(folder, name).read_bytes())
    validate_geometry(tentative, read(folder / 'catalog.json'))
    validate_mapping(tentative, read(folder / 'selection.json'))
    report = {'draft_sha256': sha, 'draft_schema_version': '1.0.0', 'output_schema_version': '0.2.0',
              'source_id_map': sources, 'questions': mapped, 'status': 'pending_host_cotejo',
              'review_promoted': False, 'archive': archive + '/draft.json',
              'next': 'Read original PDF, resolve/classify via ingest, record-input, record-check, then validate/pack or baseline/verify.'}
    catalog = read(folder / 'catalog.json')
    catalog['assets'] += list(resources.values())
    updates = {**payloads, archive + '/draft.json': raw, archive + '/report.json': json_bytes(report),
               'catalog.json': json_bytes(catalog),
               'candidate.json': json_bytes(tentative)}
    for name, data in originals.items():
        updates[archive + '/' + name] = data
    # No output side effects occur until every draft/resource/mapping check passed.
    for name in updates:
        if name not in ('candidate.json', 'catalog.json') and inside(folder / name).exists():
            raise ValueError('Adaptation would overwrite an existing artifact: ' + name)
    commit(folder, updates, candidate_bytes)
    return report
