"""Local benchmark CLI. The host agent, not this script, performs inference."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from lab import ROOT, UPSTREAM, artifact_path, digest, event, inside, json_digest, now, read, write, blocks_in, reserve_output
from package_io import inspect_package, pack, validate
from pdf_assets import apply_crops, prepare_catalog, source_record



def verify_resume(run_dir):
    folder = inside(run_dir)
    run = read(folder/'run.json')
    if run.get('release_sha256'):
        if digest(ROOT/'release.json') != run['release_sha256']:
            raise ValueError('Frozen laboratory release changed')
        verify_release()
    if run['config_hash'] != json_digest(run['config']):
        raise ValueError('Configuration changed since preparation')
    selection = read(folder/'selection.json')
    if run.get('selection_hash') and json_digest(selection) != run['selection_hash']:
        raise ValueError('Frozen selection changed')
    paths = read(folder/'sources.local.json')
    for source in read(folder/'sources.json'):
        if digest(paths[source['id']]) != source['sha256']:
            raise ValueError('Source changed since preparation')
    validate_run_contract(folder/'candidate.json')
    return {'run_dir':str(folder),'status':run['status'],'sources_unchanged':True}

def verify_release():
    path=ROOT/'release.json'
    if not path.exists():
        raise ValueError('Missing local release.json for this Skill')
    for record in read(path)['files']:
        if digest(artifact_path(ROOT,record['path'])) != record['sha256']:
            raise ValueError('Frozen laboratory file changed: '+record['path'])
    return digest(path)

def ingest(run_dir, response_path):
    folder=inside(run_dir)
    verify_resume(folder)
    response=read(response_path)
    candidate=read(folder/'candidate.json')
    if response.get('run_id') != candidate['run']['id']:
        raise ValueError('AI response belongs to a different run')
    questions=response.get('questions', [])
    if not questions or len({q['id'] for q in questions}) != len(questions):
        raise ValueError('AI batch must have unique questions')
    existing={q['id']:q for q in candidate['questions']}
    for q in questions:
        if q['id'] not in existing:
            raise ValueError('AI question outside frozen selection')
        if q['fidelity']['status']=='reviewed' or q['answer']['status']=='verified' or q['explanation']['status']=='verified':
            raise ValueError('Ingest provisional content; record independent reviews separately')
        prior=existing[q['id']]
        if content_hash(q,candidate,folder)==content_hash(prior,candidate,folder):
            q['fidelity']=copy.deepcopy(prior['fidelity'])
            if solution_hash(q,candidate,folder)==solution_hash(prior,candidate,folder):
                q['answer']=copy.deepcopy(prior['answer'])
                q['explanation']=copy.deepcopy(prior['explanation'])
        existing[q['id']]=q
    candidate['questions']=[existing[q['id']] for q in candidate['questions']]
    validate(candidate,folder)
    stamp=str(time.time_ns())
    write(folder/f'versions/candidate-before-{stamp}.json',read(folder/'candidate.json'))
    archive=inside(folder/f'reports/ai/{stamp}.json');archive.parent.mkdir(parents=True,exist_ok=True)
    archive.write_bytes(Path(response_path).read_bytes())
    write(folder/'candidate.json',candidate)
    event(folder,'ai_batch_ingested',notes=f'{len(questions)} questions; {archive.name}')
    return {'questions_updated':len(questions),'archive':str(archive)}


def empty_question(expected):
    return {**{k: expected[k] for k in ('id', 'source_id', 'number')}, 'regions': [],
            'stem': [{'type': 'unresolved', 'reason': 'Pendiente de lectura y reconstrucción por el CLI'}],
            'options': [], 'answer': {'label': None, 'status': 'missing', 'origin': 'none', 'source_ref': None},
            'explanation': {'blocks': [], 'status': 'missing'},
            'fidelity': {'status': 'pending', 'review_ref': None}, 'issues': ['NOT_PROCESSED']}


def initial_candidate(run, suite, sources):
    return {'format': 'paessed-benchmark', 'schema_version': '0.1.0', 'pipeline': run['pipeline'],
            'run': {'id': run['id'], 'cli': run['cli'], 'model': run['model'], 'created_at': now(),
                    'variant': run['variant'], 'protocol_version': run['protocol_version'], 'eligible': run['eligible'],
                    'suite_sha256': run['suite_sha256'], 'config_hash': run['config_hash'],
                    'input_mode': 'local_extraction' if run['pipeline'] == 'hybrid' else 'unavailable',
                    'all_pages_read': False},
            'exam': {'id': suite['id'], 'title': suite['title'], 'scope': suite['scope'],
                     'expected_questions': [{k: q[k] for k in ('id', 'source_id', 'number')} for q in suite['expected_questions']]},
            'sources': sources, 'questions': [empty_question(q) for q in suite['expected_questions']],
            'assets': [], 'evidence': []}


def bound_assets(blocks, candidate, root=None):
    ids=sorted({b['asset_id'] for b in blocks_in(blocks) if b['type']=='image'})
    if ids and candidate is None:
        raise ValueError('Hashing image content requires its candidate asset manifest')
    assets={a['id']:a for a in (candidate or {}).get('assets',[])}
    records=[]
    for aid in ids:
        record=copy.deepcopy(assets[aid])
        if root is not None and digest(artifact_path(root,record['path'],'assets')) != record['sha256']:
            raise ValueError('Asset bytes differ from declared hash')
        records.append(record)
    return records


def content_hash(q, candidate=None, root=None):
    payload={k:q[k] for k in ('id','source_id','number','regions','stem','options')}
    payload['assets']=bound_assets(q['stem']+[b for o in q['options'] for b in o['blocks']],candidate,root)
    payload['source']=next((s for s in (candidate or {}).get('sources',[]) if s['id']==q['source_id']),None)
    return json_digest(payload)


def solution_hash(q, candidate=None, root=None):
    return json_digest({'content':content_hash(q,candidate,root),'label':q['answer']['label'],'origin':q['answer']['origin'],
                        'explanation':q['explanation']['blocks'],'assets':bound_assets(q['explanation']['blocks'],candidate,root)})


def record_review(run_dir, path):
    run_dir = inside(run_dir)
    lock = inside(run_dir / '.review.lock')
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        return _record_review(run_dir,path)
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)


def _record_review(run_dir, path):
    response_bytes = Path(path).read_bytes()
    response = json.loads(response_bytes.decode('utf-8-sig'))
    candidate = read(run_dir / 'candidate.json')
    original_bytes=(run_dir/'candidate.json').read_bytes()
    by_id = {q['id']: q for q in candidate['questions']}
    kind = response['kind']
    if kind not in ('fidelity', 'answer') or response.get('independent') is not True:
        raise ValueError('Review must declare kind and independent context')
    if not all(response.get('agent', {}).get(k) for k in ('cli', 'model', 'session_id')):
        raise ValueError('Review needs CLI/model/session_id provenance')
    if (run_dir/'run.json').exists():
        run=read(run_dir/'run.json')
        if response.get('run_id')!=run['id']:
            raise ValueError('Review belongs to a different run')
        if response['agent']['session_id']==run.get('session_id'):
            raise ValueError('Review must use an independent session')
    if not response.get('checks') or len({c['question_id'] for c in response['checks']}) != len(response['checks']):
        raise ValueError('Review checks must be nonempty and unique')
    for check in response['checks']:
        q = by_id[check['question_id']]
        if check['content_sha256'] != content_hash(q,candidate,run_dir):
            raise ValueError('Review belongs to a different question version')
        if kind == 'answer' and check.get('solution_sha256') != solution_hash(q,candidate,run_dir):
            raise ValueError('Review belongs to a different answer/explanation version')
        if check['verdict'] not in ('pass', 'fail', 'abstain') or not check.get('notes') or not check.get('evidence_ids'):
            raise ValueError('Every check needs verdict, notes and localized evidence IDs')
        resource_ids = {r['id'] for r in candidate['assets'] + candidate['evidence']}
        if not set(check['evidence_ids']).issubset(resource_ids):
            raise ValueError('Review references unknown evidence')
    ref = hashlib.sha256(response_bytes).hexdigest()
    destination = inside(run_dir / 'reports/reviews' / f'{ref}.json')
    for check in response['checks']:
        q = by_id[check['question_id']]
        if kind == 'fidelity':
            q['fidelity'] = {'status': 'reviewed' if check['verdict'] == 'pass' else ('rejected' if check['verdict'] == 'fail' else 'pending'),
                             'review_ref': 'sha256:' + ref}
            if check['verdict'] != 'pass' and q['answer']['status'] == 'verified':
                q['answer']['status'] = 'provisional'
                q['explanation']['status'] = 'provisional' if q['explanation']['blocks'] else 'missing'
        elif check['verdict'] == 'pass':
            if q['fidelity']['status'] != 'reviewed' or q['answer']['label'] is None or not q['explanation']['blocks']:
                raise ValueError('Answer verification needs reviewed fidelity, a label and explanation')
            q['answer'].update(status='verified', source_ref='sha256:' + ref)
            q['explanation']['status'] = 'verified'
        else:
            q['answer']['status'] = 'provisional' if q['answer']['label'] else 'missing'
            q['explanation']['status'] = 'provisional' if q['explanation']['blocks'] else 'missing'
            q['issues'].append('ANSWER_REVIEW_' + check['verdict'].upper())
    validate(candidate, run_dir)
    version = run_dir / 'versions' / f'candidate-before-{time.time_ns()}.json'
    # Candidate replacement is the commit point. Preflight completes before
    # archival. A failed replace removes the newly created response archive.
    if (run_dir/'candidate.json').read_bytes()!=original_bytes:
        raise ValueError('Candidate changed concurrently; regenerate the review')
    staged=inside(run_dir/f'candidate-review-{time.time_ns()}.tmp')
    write(staged,candidate)
    new_archive=not destination.exists()
    events_path=run_dir/'events.jsonl'
    old_events=events_path.read_bytes() if events_path.exists() else None
    try:
        destination.parent.mkdir(parents=True,exist_ok=True)
        if new_archive:
            destination.write_bytes(response_bytes)
        elif digest(destination)!=ref:
            raise ValueError('Existing review archive differs')
        write(version,json.loads(original_bytes))
        event(run_dir, 'review_recorded', notes=f'{kind}: {ref}; independence is declared by CLI, not authenticated by script')
        os.replace(staged,run_dir/'candidate.json')
    except Exception:
        if new_archive:
            destination.unlink(missing_ok=True)
        version.unlink(missing_ok=True)
        if old_events is None:
            events_path.unlink(missing_ok=True)
        else:
            events_path.write_bytes(old_events)
        raise
    finally:
        staged.unlink(missing_ok=True)
    return {'review_ref': 'sha256:' + ref, 'questions': len(response['checks'])}


def check_review_bindings(candidate, root):
    for q in candidate['questions']:
        for kind, status, ref in [('fidelity', q['fidelity']['status'], q['fidelity']['review_ref']),
                                   ('answer', q['answer']['status'], q['answer']['source_ref'])]:
            if status not in ('reviewed', 'verified'):
                continue
            if not ref or not re.fullmatch(r'sha256:[a-f0-9]{64}', ref):
                raise ValueError(f'{q["id"]}: confirmed status needs an archived review')
            path = artifact_path(root, f'reports/reviews/{ref[7:]}.json')
            if digest(path) != ref[7:]:
                raise ValueError('Review hash mismatch')
            review = read(path)
            if (Path(root)/'run.json').exists():
                run=read(Path(root)/'run.json')
                if review.get('run_id')!=run['id'] or review.get('agent',{}).get('session_id')==run.get('session_id'):
                    raise ValueError('Review run/session provenance mismatch')
            check = next((c for c in review.get('checks', []) if c['question_id'] == q['id']), None)
            if review.get('kind') != kind or not review.get('independent') or not check or check['verdict'] != 'pass' or check['content_sha256'] != content_hash(q,candidate,root):
                raise ValueError(f'{q["id"]}: stale or failed review')
            if kind == 'answer' and check.get('solution_sha256') != solution_hash(q,candidate,root):
                raise ValueError(f'{q["id"]}: stale answer review')


def sync_assets(run_dir):
    run_dir = inside(run_dir)
    candidate = read(run_dir / 'candidate.json')
    catalog = read(run_dir / 'catalog.json')
    candidate['assets'] = catalog['assets']
    candidate['evidence'] = catalog['evidence']
    write(run_dir / 'candidate.json', candidate)
    return {'assets': len(candidate['assets']), 'evidence': len(candidate['evidence'])}


def validate_run_contract(file):
    """Freeze expected coverage and provenance outside the model-editable JSON."""
    path = Path(file)
    candidate = read(path)
    if not (path.parent / 'run.json').exists():
        if candidate['pipeline'] != 'demo':
            raise ValueError('A benchmark final must stay with its run.json/selection.json/sources.json')
        return
    run = read(path.parent / 'run.json')
    selection = read(path.parent / 'selection.json')
    expected = [{k: q[k] for k in ('id', 'source_id', 'number')} for q in selection['expected_questions']]
    if candidate['exam']['expected_questions'] != expected or candidate['exam']['scope'] != selection['scope']:
        raise ValueError('Candidate changed frozen question coverage/scope')
    if candidate['sources'] != read(path.parent / 'sources.json'):
        raise ValueError('Candidate changed frozen source provenance')
    frozen = ['id','model','cli','suite_sha256','config_hash']
    if run.get('protocol_version') == '0.3.0':
        frozen += ['variant','protocol_version','eligible']
    if candidate['pipeline'] != run['pipeline'] or any(candidate['run'].get(k) != run[k] for k in frozen):
        raise ValueError('Candidate changed frozen run identity/configuration')
