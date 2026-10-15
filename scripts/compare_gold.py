"""Compare imports against references without claiming semantic certification."""
import argparse
import copy
import json
import re
from pathlib import Path
from gold import load_reference, sha

DIMENSIONS = ('stem', 'text', 'math', 'options', 'tables', 'answer', 'explanation', 'visual', 'curriculum', 'curriculum_eje', 'curriculum_subeje', 'curriculum_en_temario')
CRITICAL = ('stem', 'math', 'options', 'tables', 'answer')

def indexed(data):
    result = {}
    identities = set()
    for question in data['questions']:
        if question['id'] in result:
            raise ValueError('Duplicate question ID')
        key = (question['source_id'], str(question['number']))
        if key in identities:
            raise ValueError('Duplicate source/number')
        identities.add(key)
        result[question['id']] = question
    return result

def walk(blocks, prefix):
    for i, block in enumerate(blocks):
        location = f'{prefix}[{i}]'
        yield location, block
        if block['type'] == 'table':
            for r, row in enumerate(block['rows']):
                for c, cell in enumerate(row):
                    yield from walk(cell, f'{location}.rows[{r}][{c}]')

def located(question, explanations=False):
    yield from walk(question['stem'], 'stem')
    for i, option in enumerate(question['options']):
        yield from walk(option['blocks'], f'options[{i}].blocks')
    if explanations:
        yield from walk(question['explanation']['blocks'], 'explanation.blocks')

def blocks_signature(blocks, assets):
    result = copy.deepcopy(blocks)
    for block in result:
        if block['type'] == 'image':
            resource = assets.get(block.pop('asset_id'), {})
            block['image_sha256'] = resource.get('sha256')
        elif block['type'] == 'table':
            block['rows'] = [[blocks_signature(cell, assets) for cell in row] for row in block['rows']]
    return result

def fields(question, data):
    assets = {a['id']: a for a in data.get('assets', [])}
    blocks = list(located(question))
    all_blocks = list(located(question, True))
    return {
        'stem': blocks_signature(question['stem'], assets),
        'text': [(at, b['text']) for at, b in blocks if b['type'] == 'text'],
        'math': [(at, b['latex'], b.get('display', False)) for at, b in blocks if b['type'] == 'math'],
        'options': [{'label': o['label'], 'blocks': blocks_signature(o['blocks'], assets)} for o in question['options']],
        'tables': [(at, blocks_signature([b], assets)[0]) for at, b in blocks if b['type'] == 'table'],
        'answer': question['answer'].get('label'),
        'explanation': blocks_signature(question['explanation']['blocks'], assets),
        'visual': [(at, b.get('alt'), {k: assets.get(b['asset_id'], {}).get(k) for k in ('sha256','source_id','page','bbox')})
                   for at, b in all_blocks if b['type'] == 'image'],
        'curriculum': question.get('curriculum'),
        **{'curriculum_'+key: (question.get('curriculum') or {}).get(key) for key in ('eje','subeje','en_temario')}}

def normalized(value):
    # Only text whitespace. Never remove numbers, operators, units or math spacing.
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, tuple):
        return tuple(normalized(v) for v in value)
    if isinstance(value, dict):
        return {k: re.sub(r'\s+', ' ', v).strip() if k == 'text' and isinstance(v, str) else normalized(v) for k, v in value.items()}
    return value

def compare(gold, candidate, id_map=None, gold_taxonomy=None):
    from package_io import validate
    validate(gold)
    validate(candidate)
    if gold_taxonomy is not None:
        if not isinstance(gold_taxonomy,dict) or set(gold_taxonomy)!={q['id'] for q in gold['questions']}:
            raise ValueError('Gold annotation coverage mismatch')
        from curriculum import validate_question_curriculum
        gold=copy.deepcopy(gold)
        for q in gold['questions']:
            annotation=copy.deepcopy(gold_taxonomy[q['id']])
            validate_question_curriculum({'curriculum':annotation,'issues':['CURRICULUM_PENDING'] if annotation.get('eje') is None else []})
            q['curriculum']=annotation
    left, right = indexed(gold), indexed(candidate)
    if id_map is None:
        # Deterministic source/number identity, never positional or fuzzy matching.
        by_identity = {(q['source_id'], str(q['number'])): q['id'] for q in right.values()}
        mapping = {qid: by_identity.get((q['source_id'], str(q['number']))) for qid, q in left.items()}
    else:
        if not isinstance(id_map, dict) or not set(id_map).issubset(left):
            raise ValueError('id-map must map Gold IDs to candidate IDs')
        mapping = {qid: id_map.get(qid) for qid in left}
        if any(value is not None and value not in right for value in mapping.values()):
            raise ValueError('id-map names an unknown candidate ID')
    mapped = [qid for qid in mapping.values() if qid is not None]
    if len(mapped) != len(set(mapped)):
        raise ValueError('id-map is not one-to-one')
    missing = [qid for qid, target in mapping.items() if target is None]
    extra = sorted(set(right) - set(mapped))
    rows = []
    counts = {d: {'equal': 0, 'different': 0, 'unavailable': 0} for d in DIMENSIONS}
    for gold_id, candidate_id in mapping.items():
        if candidate_id is None:
            continue
        lf, rf = fields(left[gold_id], gold), fields(right[candidate_id], candidate)
        dimensions = {}
        for name in DIMENSIONS:
            status = 'unavailable' if name.startswith('curriculum') and (lf[name] is None or rf[name] is None) else ('equal' if lf[name] == rf[name] else 'different')
            counts[name][status] += 1
            dimensions[name] = {'status': status}
            if status == 'different':
                dimensions[name].update(gold=lf[name], candidate=rf[name])
                if name in ('stem', 'options', 'explanation'):
                    dimensions[name]['normalized_equal'] = normalized(lf[name]) == normalized(rf[name])
            if name in ('explanation', 'visual'):
                dimensions[name]['semantic_review'] = 'not_performed'
        rows.append({'gold_id': gold_id, 'candidate_id': candidate_id, 'dimensions': dimensions})
    source_gold = {s['id']: s.get('sha256') for s in gold.get('sources', [])}
    source_candidate = {s['id']: s.get('sha256') for s in candidate.get('sources', [])}
    return {'format': 'paessed-gold-comparison', 'schema_version': '0.1.0',
        'coverage': {'gold': len(left), 'candidate': len(right), 'compared': len(rows), 'missing': missing, 'extra': extra},
        'mapping_method': 'explicit_ids' if id_map is not None else 'exact_source_number',
        'source_hashes_equal': source_gold == source_candidate,
        'dimensions': counts, 'questions': rows,
        'critical_difference_questions': sum(any(r['dimensions'][d]['status'] == 'different' for d in CRITICAL) for r in rows),
        'semantic_correctness': 'not_proven',
        'explanation_rubric': ['correctness', 'domain_and_assumptions', 'sufficiency', 'key_consistency'],
        'visual_rubric': ['association', 'essential_labels', 'scale_and_units', 'legibility'],
        'certification': 'not_performed'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--id-map')
    parser.add_argument('--gold-taxonomy', help='Optional reference annotations; never applied to candidate')
    parser.add_argument('--output')
    args = parser.parse_args()
    gold, _ = load_reference(args.gold)
    candidate, _ = load_reference(args.candidate)
    annotations=json.loads(Path(args.gold_taxonomy).read_text(encoding='utf-8-sig'))['questions'] if args.gold_taxonomy else None
    mapping = json.loads(Path(args.id_map).read_text(encoding='utf-8-sig')) if args.id_map else None
    result = compare(gold, candidate, mapping, annotations)
    result['inputs'] = {key: sha(Path(value).read_bytes()) for key, value in (('gold', args.gold), ('candidate', args.candidate))}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        from maintenance_io import write_report
        write_report(args.output, raw)
    else:
        print(raw, end='')

if __name__ == '__main__':
    main()
