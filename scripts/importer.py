"""Portable deterministic PAESSED M1 tools. The host AI reads and interprets PDFs."""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/scripts'))
from lab import (artifact_path, configure_workspace, digest, event, inside, json_digest,
                 no_links, now, publication_path, read, relative_path, write)
from package_io import inspect_package, pack, validate
from pdf_assets import apply_crops, prepare_catalog, source_record
from direct_gate import validate_direct_input
import pipeline as engine
from policy import select_mode

CHECKS = ('stem', 'options', 'assets_math', 'answer', 'explanation', 'consistency')
CAPABILITIES = ('pdf_visual', 'crop', 'execute', 'zip', 'validate')
PROTOCOL = '0.3.0'


def slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    value = re.sub(r'[^a-zA-Z0-9]+', '-', value).strip('-').lower()[:100]
    return value or 'm1-ensayo'


def known_folder(kind):
    home = Path.home()
    if sys.platform == 'win32':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            name = 'Personal' if kind == 'documents' else '{374DE290-123F-4565-9164-39C4925E467B}'
            try:
                value, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                value = str(home / ('Documents' if kind == 'documents' else 'Downloads'))
            return Path(os.path.expandvars(value))
    name = 'XDG_DOCUMENTS_DIR' if kind == 'documents' else 'XDG_DOWNLOAD_DIR'
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'user-dirs.dirs'
    if config.is_file():
        for line in config.read_text(encoding='utf-8').splitlines():
            match = re.fullmatch(r'\s*' + name + r'="([^"\n]+)"\s*', line)
            if match:
                return Path(match[1].replace('$HOME', str(home)))
    return home / ('Documents' if kind == 'documents' else 'Downloads')


def output_root(destination, custom):
    if destination == 'custom':
        if not custom or not Path(custom).is_absolute():
            raise ValueError('Custom output-root must be an absolute path')
        return no_links(custom)
    if custom:
        raise ValueError('Use --destination custom with --output-root')
    return no_links(known_folder(destination) / 'EnsayosPaessedOutput')


def require_capabilities(record):
    if any(record.get(k) is not True for k in CAPABILITIES) or not record.get('observation'):
        raise ValueError('Need observed PDF visuals, crops, execution, validation and ZIP capabilities')


def base_folder(value):
    folder = Path(value).absolute()
    if (folder / '.work/base/run.json').is_file():
        folder = folder / '.work/base'
    if folder.name != 'base' or folder.parent.name != '.work':
        raise ValueError('Expected an output run or its .work/base directory')
    configure_workspace(folder.parent.parent)
    return inside(folder)


def prepare(args):
    capabilities = read(args.capabilities)
    require_capabilities(capabilities)
    exam = Path(args.exam).resolve(strict=True)
    solution = Path(args.solution).resolve(strict=True) if args.solution else None
    if solution == exam:
        raise ValueError('An embedded key uses the exam source; do not repeat --solution')
    title = args.title or exam.stem
    exam_id = slug(title)
    if not exam_id.startswith('m1-'):
        exam_id = 'm1-' + exam_id
    rid = args.run_id or time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', rid):
        raise ValueError('Unsafe run-id')
    destination = output_root(args.destination, args.output_root) / exam_id / rid
    configure_workspace(destination)
    engine.verify_release()
    if destination.exists():
        raise ValueError('Output already exists; use resume or a new run-id')
    folder = inside(destination / '.work/base')
    folder.mkdir(parents=True)
    temporary = inside(destination / '.work/tmp')
    temporary.mkdir()
    os.environ.update(TEMP=str(temporary), TMP=str(temporary), UV_CACHE_DIR=str(temporary / 'uv-cache'))
    config = {'host': args.host, 'model': args.model, 'effort': args.effort, 'batch_size': 5,
              'capabilities': capabilities, 'max_retries': 1,
              'suggested_save_location': getattr(args, 'suggested_save_location', None)}
    run = {'id': rid, 'pipeline': 'pdf-direct', 'variant': 'direct', 'protocol_version': PROTOCOL,
           'purpose': 'portable-import', 'eligible': False, 'status': 'preparing',
           'cli': args.client or args.host, 'host': args.host, 'model': args.model,
           'session_id': args.session_id, 'started_at': now(), 'output_dir': str(destination),
           'config': config, 'config_hash': json_digest(config), 'exam_id': exam_id, 'title': title,
           'release_sha256': digest(ROOT / 'release.json')}
    write(folder / 'run.json', run)
    try:
        paths = {'exam': str(exam)}
        if solution:
            paths['solution'] = str(solution)
        sources = [source_record(sid, p, 'exam' if sid == 'exam' else 'solution') for sid, p in paths.items()]
        write(folder / 'sources.local.json', paths)
        write(folder / 'sources.json', sources)
        prepare_catalog(sources, paths, folder, scale=args.scale)
        write(folder / 'direct-input.template.json', {
            'mode': 'unavailable', 'input_kind': 'pdf', 'reader': '',
            'visual_content_understood': False, 'capability_observation': '', 'limitations': [],
            'sources': [{'source_id': s['id'], 'sha256': s['sha256'], 'pages_read': []} for s in sources]})
        run['status'] = 'awaiting_mapping'
        write(folder / 'run.json', run)
    except Exception:
        run['status'] = 'failed_preparation'
        write(folder / 'run.json', run)
        raise
    return {'run': str(folder), 'output': str(destination), 'next': 'Read source pages, then map'}


def verify_pre_mapping(folder):
    run = read(folder / 'run.json')
    if digest(ROOT / 'release.json') != run['release_sha256'] or json_digest(run['config']) != run['config_hash']:
        raise ValueError('Frozen implementation/configuration changed')
    engine.verify_release()
    paths = read(folder / 'sources.local.json')
    for source in read(folder / 'sources.json'):
        if digest(paths[source['id']]) != source['sha256']:
            raise ValueError('Source changed before question mapping')


def map_questions(folder, selection_file):
    verify_pre_mapping(folder)
    run = read(folder / 'run.json')
    if run['status'] != 'awaiting_mapping' or (folder / 'selection.json').exists():
        raise ValueError('Question map is already frozen or preparation failed')
    selection = read(selection_file)
    expected = selection.get('expected_questions', [])
    if not expected or len({q['id'] for q in expected}) != len(expected):
        raise ValueError('Expected questions must be nonempty and unique')
    pages = next(s['page_count'] for s in read(folder / 'sources.json') if s['id'] == 'exam')
    numbers = set()
    for q in expected:
        if (q.get('source_id') != 'exam' or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', q['id'])
                or not isinstance(q.get('number'), str) or not q['number']
                or type(q.get('page')) is not int or not 1 <= q['page'] <= pages or q['number'] in numbers):
            raise ValueError('Invalid question identity, number, exam source or physical page')
        numbers.add(q['number'])
    if selection.get('observed_question_count') != len(expected) or not selection.get('observation'):
        raise ValueError('Record observed total question count and mapping observation')
    suite = {'id': run['exam_id'], 'title': selection.get('title', run['title']), 'scope': 'full',
             'expected_questions': expected, 'observation': selection['observation']}
    write(folder / 'selection.json', suite)
    run.update(selection_hash=json_digest(suite), suite_sha256=digest(folder / 'selection.json'),
               status='awaiting_route')
    write(folder / 'run.json', run)
    candidate = engine.initial_candidate(run, suite, read(folder / 'sources.json'))
    catalog = read(folder / 'catalog.json')
    candidate.update(assets=catalog['assets'], evidence=catalog['evidence'])
    write(folder / 'candidate.json', candidate)
    return {'questions': len(expected)}


def validate_key(record, candidate):
    sources = {s['id']: s for s in candidate['sources']}
    exam = sources['exam']
    if record.get('exam_sha256') != exam['sha256']:
        raise ValueError('Answer key is bound to another exam')
    match = record.get('match', {})
    if match.get('status') != 'matched' or not match.get('reason') or not match.get('evidence'):
        raise ValueError('Resolve ambiguous/incompatible key; do not apply it')
    def cite(item):
        source = sources.get(item.get('source_id'))
        if (not source or type(item.get('page')) is not int or not 1 <= item['page'] <= source['page_count']
                or not item.get('observation')):
            raise ValueError('Key correspondence needs source/page/observation')
    for item in match['evidence']:
        cite(item)
    allowed = {q['id'] for q in candidate['questions']}
    entries = record.get('entries', [])
    if len({e['question_id'] for e in entries}) != len(entries):
        raise ValueError('Duplicate answer-key entry')
    for entry in entries:
        if entry['question_id'] not in allowed or not re.fullmatch('[A-Z]', entry.get('label', '')):
            raise ValueError('Invalid answer-key question or label')
        cite(entry)
    return {e['question_id']: e for e in entries}


def route(folder, key_file, subagents, experimental):
    engine.verify_resume(folder)
    run, candidate = read(folder / 'run.json'), read(folder / 'candidate.json')
    if run['status'] != 'awaiting_route':
        raise ValueError('Processing route is already frozen')
    key = read(key_file) if key_file else None
    entries = validate_key(key, candidate) if key else {}
    decision = select_mode(run['host'], [q['id'] for q in candidate['questions']], entries,
                           subagents, experimental)
    if decision['status'] == 'needs_consent':
        return decision
    record = {**decision, 'experimental_consent': experimental, 'answer_key': key}
    write(folder / 'route.json', record)
    if key:
        write(folder / 'answer-key-map.json', key)
    run.update(route_hash=json_digest(record), status='awaiting_ai')
    candidate['run'].update(processing_mode=decision['processing_mode'], review_mode=decision['review_mode'],
                            host=run['host'], answer_key_sha256=json_digest(key) if key else None)
    write(folder / 'candidate.json', candidate)
    write(folder / 'run.json', run)
    return decision


def ensure_editable(folder):
    run = read(folder / 'run.json')
    if run['status'] != 'awaiting_ai' or (folder / 'final.json').exists() or (folder.parent.parent / 'final.json').exists():
        raise ValueError('Preserve completed/failed runs; use a new run')


def frozen_route(folder):
    engine.verify_resume(folder)
    run, decision = read(folder / 'run.json'), read(folder / 'route.json')
    if json_digest(decision) != run.get('route_hash'):
        raise ValueError('Processing route changed')
    if decision['answer_key'] and read(folder / 'answer-key-map.json') != decision['answer_key']:
        raise ValueError('Answer-key provenance changed')
    return decision


def ingest(folder, response_file):
    ensure_editable(folder)
    decision = frozen_route(folder)
    response = read(response_file)
    candidate = read(folder / 'candidate.json')
    key = validate_key(decision['answer_key'], candidate) if decision['answer_key'] else {}
    explanations = response.get('explanation_provenance', {})
    allowed = {q['id'] for q in candidate['questions']}
    if not set(explanations) <= allowed:
        raise ValueError('Unknown explanation question')
    for q in response.get('questions', []):
        if q['id'] in key:
            label = key[q['id']]['label']
            if label not in {o['label'] for o in q['options']}:
                raise ValueError('Key answer does not exist among question alternatives')
            q['answer'] = {'label': label, 'status': 'provisional', 'origin': 'answer-key',
                           'source_ref': '.work/base/answer-key-map.json#' + q['id']}
        elif q['id'] in decision['pending_question_ids']:
            if q['answer']['label'] is not None or q['explanation']['blocks']:
                raise ValueError('Experimental solving declined: keep uncovered answers/explanations missing')
        elif q['answer']['origin'] == 'answer-key':
            raise ValueError('Answer-key origin requires a frozen matching entry')
        if q['explanation']['blocks']:
            provenance = explanations.get(q['id'])
            if not provenance or provenance.get('origin') not in ('model', 'solution'):
                raise ValueError('Every explanation needs model/solution provenance')
            if provenance['origin'] == 'solution':
                if q['id'] not in key or not key[q['id']].get('has_explanation'):
                    raise ValueError('No source justification recorded for this question')
                if provenance.get('source_id') != key[q['id']]['source_id'] or provenance.get('page') != key[q['id']]['page']:
                    raise ValueError('Solution explanation source/page mismatch')
    # Archive exact host output before applying deterministic answer-key binding.
    stamp = str(time.time_ns())
    raw = inside(folder / 'raw' / (stamp + '.json')); raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(Path(response_file).read_bytes())
    staged = folder / 'requests' / (stamp + '.json')
    write(staged, response)
    result = engine.ingest(folder, staged)
    saved = read(folder / 'explanation-provenance.json') if (folder / 'explanation-provenance.json').exists() else {}
    for q in response.get('questions', []):
        saved[q['id']] = explanations.get(q['id'], {'origin': 'none'})
    write(folder / 'explanation-provenance.json', saved)
    return result


def record_input(folder, response_file):
    ensure_editable(folder)
    frozen_route(folder)
    candidate = read(folder / 'candidate.json')
    ledger = read(response_file)
    proposed = copy.deepcopy(candidate)
    proposed['run'].update(input_mode=ledger.get('mode'), all_pages_read=True)
    temporary = folder / 'requests' / ('reading-' + str(time.time_ns()))
    temporary.mkdir(parents=True)
    write(temporary / 'direct-input.json', ledger)
    validate_direct_input(proposed, temporary)
    archive(folder, 'reading', ledger)
    write(folder / 'direct-input.json', ledger)
    write(folder / 'candidate.json', proposed)
    return {'reading_recorded': True, 'attestation': 'host declaration, not proof of comprehension'}


def archive(folder, kind, record):
    name = kind + '-' + str(time.time_ns()) + '.json'
    write(folder / 'reports' / kind / name, record)
    return name


def check_template(folder):
    candidate = read(folder / 'candidate.json')
    return {'run_id': candidate['run']['id'], 'independent': False,
            'session_id': read(folder / 'run.json')['session_id'],
            'questions': [{'id': q['id'], 'content_sha256': engine.content_hash(q, candidate, folder),
                           'solution_sha256': engine.solution_hash(q, candidate, folder),
                           'checks': {k: {'status': 'unresolved', 'reason': '', 'evidence': []} for k in CHECKS}}
                          for q in candidate['questions']]}


def check_record(folder, record, candidate):
    run = read(folder / 'run.json')
    if (record.get('run_id') != run['id'] or record.get('independent') is not False
            or record.get('session_id') != run['session_id']):
        raise ValueError('Self-check must identify this producing session and declare independent=false')
    by_id = {q['id']: q for q in candidate['questions']}
    rows = record.get('questions', [])
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Self-check rows must be nonempty and unique')
    resources = {a['id']: a for a in candidate['assets'] + candidate['evidence']}
    for row in rows:
        q = by_id.get(row['id'])
        if (not q or row.get('content_sha256') != engine.content_hash(q, candidate, folder)
                or row.get('solution_sha256') != engine.solution_hash(q, candidate, folder)):
            raise ValueError('Stale self-check question/solution')
        if set(row.get('checks', {})) != set(CHECKS):
            raise ValueError('Self-check needs all six dimensions')
        for check in row['checks'].values():
            if check.get('status') not in ('pass', 'unresolved') or not check.get('reason') or not check.get('evidence'):
                raise ValueError('Self-check needs pass/unresolved, reason and visual evidence')
            for citation in check['evidence']:
                resource = resources.get(citation.get('id'))
                if (not resource or resource['sha256'] != citation.get('sha256')
                        or not citation.get('observation')
                        or digest(artifact_path(folder, resource['path'])) != citation['sha256']):
                    raise ValueError('Unknown, altered or unjustified self-check evidence')
    return rows


def record_check(folder, response_file):
    ensure_editable(folder)
    frozen_route(folder)
    candidate = read(folder / 'candidate.json')
    record = read(response_file)
    rows = check_record(folder, record, candidate)
    current = read(folder / 'self-checks.json') if (folder / 'self-checks.json').exists() else {}
    name = archive(folder, 'self-checks', record)
    for row in rows:
        current[row['id']] = {'report': name, 'row': row}
    write(folder / 'self-checks.json', current)
    return {'self_checked': len(rows), 'independent': False}


def validate_for_pack(folder):
    if read(folder / 'run.json')['status'] in ('failed', 'failed_preparation'):
        raise ValueError('Failed runs cannot publish')
    decision = frozen_route(folder)
    candidate = read(folder / 'candidate.json')
    engine.validate_run_contract(folder / 'candidate.json')
    for field in ('processing_mode', 'review_mode'):
        if candidate['run'].get(field) != decision[field]:
            raise ValueError('Candidate changed selected mode')
    expected_key_hash = json_digest(decision['answer_key']) if decision['answer_key'] else None
    if candidate['run'].get('answer_key_sha256') != expected_key_hash:
        raise ValueError('Candidate changed answer-key identity')
    validate_direct_input(candidate, folder)
    validate(candidate, folder)
    key = validate_key(decision['answer_key'], candidate) if decision['answer_key'] else {}
    provenance = read(folder / 'explanation-provenance.json') if (folder / 'explanation-provenance.json').exists() else {}
    checks = read(folder / 'self-checks.json') if (folder / 'self-checks.json').exists() else {}
    for q in candidate['questions']:
        if q['id'] in key:
            if (q['answer']['label'] != key[q['id']]['label'] or q['answer']['origin'] != 'answer-key'
                    or q['answer']['source_ref'] != '.work/base/answer-key-map.json#' + q['id']):
                raise ValueError('Candidate changed mapped answer-key response')
        elif q['answer']['origin'] == 'answer-key':
            raise ValueError('Unknown key answer')
        if q['id'] in decision['pending_question_ids'] and (q['answer']['label'] is not None or q['explanation']['blocks']):
            raise ValueError('Solving declined for this question')
        if q['fidelity']['status'] != 'pending' or q['answer']['status'] == 'verified' or q['explanation']['status'] == 'verified':
            raise ValueError('Base/self-check cannot claim independent verified status')
        if q['explanation']['blocks'] and provenance.get(q['id'], {}).get('origin') not in ('model', 'solution'):
            raise ValueError('Missing explanation provenance')
        entry = checks.get(q['id'])
        if not entry:
            raise ValueError('Every question needs its own documented source cotejo')
        archived = read(folder / 'reports/self-checks' / entry['report'])
        bound = check_record(folder, archived, candidate)
        if entry['row'] not in bound:
            raise ValueError('Self-check archive binding mismatch')
    return candidate, decision


def publish_base(folder):
    candidate, decision = validate_for_pack(folder)
    if decision['independent_question_ids']:
        raise ValueError('Independent route needs baseline and verification before publication')
    output = publication_path(folder)
    used = {b['asset_id'] for q in candidate['questions'] for b in __import__('lab').question_blocks(q) if b['type'] == 'image'}
    for resource in candidate['assets']:
        if resource['id'] in used:
            target = inside(output / resource['path']); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact_path(folder, resource['path']), target)
    candidate['assets'] = [a for a in candidate['assets'] if a['id'] in used]
    candidate['evidence'] = []
    write(output / 'candidate.json', candidate)
    result = pack(output / 'candidate.json')
    return finish_publication(folder, output, result, decision)


def finish_publication(folder, output, result, decision):
    run = read(folder / 'run.json')
    target = inside(output / (run['exam_id'] + '.zip'))
    Path(result['zip']).rename(target)
    companion = inside(output / (run['exam_id'] + '.paessed'))
    Path(result['paessed']).rename(companion)
    result.update(zip=str(target), paessed=str(companion))
    final = read(output / 'final.json')
    metadata = {**run, 'id': final['run']['id'], 'status': 'packaged', 'finished_at': now(),
                'processing_mode': decision['processing_mode'], 'review_mode': decision['review_mode'],
                'final_sha256': digest(output / 'final.json'), 'package_sha256': digest(target),
                'usage': {'input_tokens': None, 'output_tokens': None, 'total_tokens': None, 'cost_usd': None,
                          'source': 'unavailable'},
                'summary': {'questions': result['questions'],
                            'answers_from_key': sum(q['answer']['origin'] == 'answer-key' for q in final['questions']),
                            'answers_from_model': sum(q['answer']['origin'] == 'model' for q in final['questions']),
                            'answers_missing': sum(q['answer']['status'] == 'missing' for q in final['questions']),
                            'answers_verified_by_ai': sum(q['answer']['status'] == 'verified' for q in final['questions']),
                            'independent_questions': len(decision['independent_question_ids']),
                            'accuracy': None,
                            'note': 'Structural validation and AI review are not ground truth'}}
    if (output / 'run.json').exists():
        metadata['verification'] = read(output / 'run.json')
    if not decision['independent_question_ids']:
        run.update(status='packaged', finished_at=metadata['finished_at'], final_sha256=metadata['final_sha256'])
        write(folder / 'run.json', run)
    write(output / 'run.json', metadata)
    result['summary'] = metadata['summary']
    return result


def baseline(folder):
    _, decision = validate_for_pack(folder)
    if not decision['independent_question_ids']:
        raise ValueError('This route publishes directly; no independent baseline needed')
    result = pack(folder / 'candidate.json')
    run = read(folder / 'run.json')
    run.update(status='packaged', finished_at=now(), final_sha256=digest(folder / 'final.json'),
               independent_question_ids=decision['independent_question_ids'])
    write(folder / 'run.json', run)
    return result


def verify_command(args):
    import verify
    if args.action == 'prepare':
        parent = base_folder(args.run)
        decision = frozen_route(parent)
        if not decision['independent_question_ids']:
            raise ValueError('No independent work selected')
        validate_for_pack(parent)
        run = read(parent / 'run.json')
        if args.session_id in ('unknown', '', run['session_id']):
            raise ValueError('Independent coordinator session required')
        return {'verification': verify.prepare(parent, run['id'] + '-review', 10, run['model'],
                                              run['config']['effort'], args.session_id,
                                              parent.parent.parent)}
    folder = Path(args.run).absolute()
    if (folder / '.work/verification/run.json').is_file():
        folder = folder / '.work/verification'
    if folder.name != 'verification' or folder.parent.name != '.work':
        raise ValueError('Expected .work/verification')
    configure_workspace(folder.parent.parent)
    if args.action == 'check':
        return {'reports': len(verify.load_reports(folder)[2])}
    if args.action == 'decisions':
        verify.decisions(folder)
        return {'template': str(folder / 'decisions-template.json')}
    if args.action == 'add-evidence':
        return verify.add_evidence(folder, args.batch, read(args.requests))
    parent = base_folder(folder.parent / 'base')
    decision = frozen_route(parent)
    validate_for_pack(parent)
    result = verify.consolidate(folder, args.decisions)
    return finish_publication(parent, folder.parent.parent, result, decision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--exam', required=True); p.add_argument('--solution')
    p.add_argument('--destination', choices=['documents', 'downloads', 'custom'], default='documents')
    p.add_argument('--output-root'); p.add_argument('--title'); p.add_argument('--run-id')
    p.add_argument('--suggested-save-location')
    p.add_argument('--host', choices=['cli', 'web'], required=True); p.add_argument('--client')
    p.add_argument('--model', default='unknown'); p.add_argument('--effort', default='unknown')
    p.add_argument('--session-id', required=True); p.add_argument('--capabilities', required=True)
    p.add_argument('--scale', type=float, default=1.5)
    p = sub.add_parser('inspect'); p.add_argument('--package', required=True)
    p = sub.add_parser('verify')
    p.add_argument('action', choices=['prepare', 'check', 'decisions', 'consolidate', 'add-evidence'])
    p.add_argument('--run', required=True); p.add_argument('--session-id', default='unknown')
    p.add_argument('--decisions'); p.add_argument('--batch'); p.add_argument('--requests')
    for name in ('map', 'route', 'ingest', 'record-input', 'check-template', 'record-check', 'crops',
                 'validate', 'pack', 'baseline', 'resume', 'fail'):
        p = sub.add_parser(name); p.add_argument('--run', required=True)
        if name == 'map': p.add_argument('--selection', required=True)
        if name in ('ingest', 'record-input', 'record-check'): p.add_argument('--response', required=True)
        if name == 'route':
            p.add_argument('--answer-key'); p.add_argument('--subagents', action='store_true')
            p.add_argument('--experimental', choices=['yes', 'no'])
        if name == 'crops': p.add_argument('--requests', required=True)
        if name == 'fail': p.add_argument('--reason', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare': result = prepare(args)
        elif args.command == 'inspect': result = inspect_package(args.package)
        elif args.command == 'verify': result = verify_command(args)
        else:
            folder = base_folder(args.run)
            if args.command == 'map': result = map_questions(folder, args.selection)
            elif args.command == 'route': result = route(folder, args.answer_key, args.subagents, args.experimental)
            elif args.command == 'ingest': result = ingest(folder, args.response)
            elif args.command == 'record-input': result = record_input(folder, args.response)
            elif args.command == 'check-template': result = check_template(folder)
            elif args.command == 'record-check': result = record_check(folder, args.response)
            elif args.command == 'crops':
                ensure_editable(folder)
                frozen_route(folder)
                result = apply_crops(folder, read(args.requests)); engine.sync_assets(folder)
            elif args.command == 'validate': result = validate_for_pack(folder)[1]
            elif args.command == 'pack': result = publish_base(folder)
            elif args.command == 'baseline': result = baseline(folder)
            elif args.command == 'fail':
                run = read(folder / 'run.json'); run.update(status='failed', reason=args.reason)
                write(folder / 'run.json', run); result = {'status': 'failed', 'reason': args.reason}
            else:
                run = read(folder / 'run.json')
                if run['status'] == 'awaiting_mapping':
                    verify_pre_mapping(folder); result = {'status': run['status']}
                else:
                    result = engine.verify_resume(folder)
                    if (folder / 'route.json').exists(): frozen_route(folder)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
