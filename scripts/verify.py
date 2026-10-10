"""Review a completed base run; AI review is performed by the host, not Python."""
from __future__ import annotations
import argparse
import copy
import math
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/scripts'))
from lab import configure_workspace, artifact_path, digest, inside, json_digest, now, question_blocks, read, write, reserve_output, publication_path, output_path
from package_io import pack, validate
from pdf_assets import render_crop
import pypdfium2 as pdfium

CHECKS = ('stem', 'options', 'assets_math', 'answer', 'explanation', 'consistency')
FIELDS = {'stem', 'options', 'regions', 'answer', 'explanation', 'issues'}
USAGE = ('duration_seconds', 'input_tokens', 'output_tokens', 'total_tokens', 'model_calls', 'cost_usd')

def new(path, value):
    path = inside(path)
    if path.exists():
        raise ValueError(f'Preserve existing artifact: {path}')
    write(path, value)

def usage_record(record):
    usage = record.get('usage', {})
    for key in USAGE:
        value = usage.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('Invalid usage measurement')
        if key in ('input_tokens', 'output_tokens', 'total_tokens', 'model_calls') and value is not None and type(value) is not int:
            raise ValueError('Token/call counts must be integers')
    if any(usage.get(k) is not None for k in USAGE) and record.get('usage_source') in (None, '', 'unavailable'):
        raise ValueError('Measured usage needs actual source')
    result = {k: usage.get(k) for k in USAGE}
    if result['total_tokens'] is None and result['input_tokens'] is not None and result['output_tokens'] is not None:
        result['total_tokens'] = result['input_tokens'] + result['output_tokens']
    return result

def copy_resource(source, target):
    target = inside(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Resource already exists')
    shutil.copyfile(source, target)

def binding(folder):
    folder = inside(folder)
    run = read(folder / 'run.json')
    parent = Path(run['parent']['path'])
    if digest(parent / 'final.json') != run['parent']['final_sha256']:
        raise ValueError('Parent final changed')
    if digest(parent / 'run.json') != run['parent']['run_sha256']:
        raise ValueError('Parent run metadata changed')
    paths = read(parent / 'sources.local.json')
    for source in read(folder / 'baseline.json')['sources']:
        if digest(paths[source['id']]) != source['sha256']:
            raise ValueError('PDF source changed since verification preparation')
    if digest(folder / 'baseline.json') != run['parent']['final_sha256']:
        raise ValueError('Baseline snapshot changed')
    for name, hashed in run['implementation'].items():
        if digest(ROOT / name) != hashed:
            raise ValueError('Verification implementation changed; use a new experiment')
    for name, hashed in run.get('dependencies', {}).items():
        if digest(ROOT / name) != hashed:
            raise ValueError('Frozen v1 dependency changed: ' + name)
    for name, hashed in run['inputs'].items():
        if digest(artifact_path(folder, name)) != hashed:
            raise ValueError('Frozen batch input changed: ' + name)
    for asset in read(folder / 'baseline.json')['assets']:
        if digest(artifact_path(folder, asset['path'])) != asset['sha256']:
            raise ValueError('Baseline asset changed')
    return run, read(folder / 'baseline.json')

def prepare(parent, run_id, batch_size=10, model='unknown', effort='unknown', session='unknown', output_dir=None):
    start = time.perf_counter()
    started_at = now()
    if type(batch_size) is not int or not 1 <= batch_size <= 10:
        raise ValueError('Batch size must be 1..10')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('Unsafe run ID')
    parent = Path(parent).resolve()
    baseline = read(parent / 'final.json')
    parent_run = read(parent / 'run.json')
    if baseline['pipeline'] != 'pdf-direct' or parent_run.get('variant') != 'direct' or parent_run.get('status') != 'packaged':
        raise ValueError('Requires completed PDF-directo v1 (direct), no chaining')
    validate(baseline, parent)
    dependencies = {}
    if parent_run.get('release_sha256'):
        release = ROOT / 'release.json'
        if digest(release) != parent_run['release_sha256']:
            raise ValueError('Parent frozen release changed')
        for record in read(release)['files']:
            if digest(artifact_path(ROOT, record['path'])) != record['sha256']:
                raise ValueError('Frozen v1 file changed: ' + record['path'])
            dependencies[record['path']] = record['sha256']
    paths = read(parent / 'sources.local.json')
    for source in baseline['sources']:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', source['id']):
            raise ValueError('Source ID must be safe for evidence filenames')
        if digest(paths[source['id']]) != source['sha256']:
            raise ValueError('Source PDF changed')
    destination = output_path(output_dir if output_dir is not None else parent.parent.parent)
    if parent != destination / '.work/base':
        raise ValueError('Parent must be the base of this Final run')
    folder = reserve_output(destination, 'verification')
    copy_resource(parent / 'final.json', folder / 'baseline.json')
    for asset in baseline['assets'] + baseline['evidence']:
        copy_resource(artifact_path(parent, asset['path']), folder / asset['path'])
    run = {'id': run_id, 'pipeline': 'pdf-direct', 'variant': 'direct-verified',
           'protocol_version': 'direct-verification-1.0', 'purpose': 'paired-experiment',
           'started_at': started_at, 'status': 'preparing', 'model': model, 'effort': effort,
           'session_id': session, 'batch_size': batch_size, 'output_dir': str(destination),
           'parent': {'path': str(parent), 'id': parent_run['id'], 'final_sha256': digest(parent / 'final.json'),
                      'run_sha256': digest(parent / 'run.json')},
           'implementation': {p.relative_to(ROOT).as_posix(): digest(p) for p in
                              [Path(__file__).resolve(), ROOT / 'SKILL.md', ROOT / 'references/workflow.md']},
           'dependencies': dependencies, 'inputs': {}, 'batches': []}
    write(folder / 'run.json', run)  # Failed preparation remains visible, never a measured success.
    route = read(parent / 'route.json')
    target_ids = route['independent_question_ids']
    if json_digest(route) != parent_run.get('route_hash') or target_ids != parent_run.get('independent_question_ids'):
        raise ValueError('Frozen audit selection changed')
    if not target_ids or not set(target_ids) <= {q['id'] for q in baseline['questions']}:
        raise ValueError('Requires frozen independent question coverage')
    questions = [q for q in baseline['questions'] if q['id'] in target_ids]
    run['target_question_ids'] = [q['id'] for q in questions]
    for offset in range(0, len(questions), batch_size):
        batch_id = f'batch-{offset // batch_size + 1:02d}'
        batch = folder / 'batches' / batch_id
        selected = questions[offset:offset + batch_size]
        used = {b['asset_id'] for q in selected for b in question_blocks(q) if b['type'] == 'image'}
        assets = [a for a in baseline['assets'] if a['id'] in used]
        evidence = []
        # Only physical pages needed by this batch; render source PDF, not extracted assets.
        pages = {(q['source_id'], r['page']) for q in selected for r in q['regions']}
        pages |= {(a['source_id'], a['page']) for a in assets}
        for source_id, page_no in sorted(pages):
            with pdfium.PdfDocument(str(paths[source_id])) as pdf:
                page = pdf[page_no - 1]
                try:
                    name = f'evidence/{source_id}-p{page_no:04d}.png'
                    box = render_crop(page, batch / name, scale=1.5)
                finally:
                    page.close()
            evidence.append({'path': name, 'source_id': source_id, 'page': page_no, 'bbox': box,
                             'sha256': digest(batch / name)})
        for asset in assets:
            copy_resource(artifact_path(parent, asset['path']), batch / asset['path'])
        packet = {'format': 'direct-verification-batch-1.0', 'batch_id': batch_id,
                  'baseline_sha256': run['parent']['final_sha256'], 'questions': selected,
                  'assets': assets, 'evidence': evidence, 'checks': list(CHECKS)}
        new(batch / 'input.json', packet)
        new(batch / 'report-template.json', report_template(packet))
        run['batches'].append(batch_id)
        for path in [batch / 'input.json', *(batch / e['path'] for e in evidence),
                     *(batch / a['path'] for a in assets)]:
            run['inputs'][path.relative_to(folder).as_posix()] = digest(path)
    run.update(status='awaiting_reviews', preparation_seconds=time.perf_counter() - start)
    write(folder / 'run.json', run)
    new(folder / 'coordinator-usage-template.json', {
        'scope': 'coordinator_only', 'usage_source': 'unavailable',
        'usage': {k: None for k in USAGE}, 'parallel_agents_peak': None, 'retries': None})
    return str(folder)

def add_evidence(folder, batch_id, requests):
    run, baseline = binding(folder)
    if run['status'] != 'awaiting_reviews' or batch_id not in run['batches']:
        raise ValueError('Unknown or completed batch')
    batch = folder / 'batches' / batch_id
    if (batch / 'report.json').exists():
        raise ValueError('Preserve completed reports; extra evidence needs a new experiment')
    packet = read(batch / 'input.json')
    paths = read(Path(run['parent']['path']) / 'sources.local.json')
    sources = {s['id']: s for s in baseline['sources']}
    qids = {q['id']: q for q in packet['questions']}
    known_ids = {a['id'] for a in baseline['assets'] + packet['assets']}
    additions = []
    for req in requests:
        q = qids.get(req['question_id'])
        if not q or not req.get('reason') or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', req['id']) or req['id'] in known_ids:
            raise ValueError('Evidence request needs batch question, reason and new safe ID')
        known_ids.add(req['id'])
        sid = q['source_id']
        page_no = req['page']
        if type(page_no) is not int or not 1 <= page_no <= sources[sid]['page_count']:
            raise ValueError('Invalid evidence page')
        if digest(paths[sid]) != sources[sid]['sha256']:
            raise ValueError('PDF source changed')
        role = req.get('role', 'evidence')
        if role not in ('evidence', 'asset'):
            raise ValueError('Invalid evidence role')
        name = f'{"assets" if role == "asset" else "evidence"}/{req["id"]}.png'
        if (batch / name).exists():
            raise ValueError('Evidence output exists')
        with pdfium.PdfDocument(str(paths[sid])) as pdf:
            page = pdf[page_no - 1]
            try: box = render_crop(page, batch / name, req.get('bbox'), scale=2)
            finally: page.close()
        record = {'id': req['id'], 'path': name, 'sha256': digest(batch / name),
                  'mime': 'image/png', 'source_id': sid, 'page': page_no, 'bbox': box}
        packet['assets' if role == 'asset' else 'evidence'].append(record)
        additions.append({'request': req, 'resource': record})
        run['inputs'][(batch / name).relative_to(folder).as_posix()] = record['sha256']
        if role == 'asset':
            copy_resource(batch / name, folder / 'additional-assets' / batch_id / name)
    revision = json_digest(packet)[:16]
    new(batch / 'history' / f'input-before-{revision}.json', read(batch / 'input.json'))
    new(batch / 'history' / f'evidence-{revision}.json', additions)
    write(batch / 'input.json', packet)
    write(batch / 'report-template.json', report_template(packet))
    run['inputs'][(batch / 'input.json').relative_to(folder).as_posix()] = digest(batch / 'input.json')
    write(folder / 'run.json', run)

def report_template(packet):
    return {'format': 'direct-verification-report-1.0', 'batch_id': packet['batch_id'],
            'input_sha256': json_digest(packet),
            'reviewer': {'id': '', 'session_id': '', 'model': '', 'effort': '', 'fresh_context': False},
            'usage': {k: None for k in USAGE}, 'usage_source': 'unavailable',
            'questions': [{'id': q['id'], 'checks': {k: {'status': 'unresolved', 'reason': '', 'evidence': []} for k in CHECKS},
                           'independent_solution': {'label': None, 'reasoning': '', 'evidence': []},
                           'changes': [], 'post_checks': {k: 'unresolved' for k in CHECKS}}
                          for q in packet['questions']]}

def load_reports(folder):
    run, baseline = binding(folder)
    reports = []
    sessions = set()
    for batch_id in run['batches']:
        batch = folder / 'batches' / batch_id
        packet = read(batch / 'input.json')
        report = read(batch / 'report.json')
        if report.get('format') != 'direct-verification-report-1.0' or report.get('batch_id') != batch_id or report.get('input_sha256') != json_digest(packet):
            raise ValueError('Report/input binding mismatch')
        reviewer = report['reviewer']
        sid = reviewer.get('session_id')
        parent_session = read(Path(run['parent']['path']) / 'run.json').get('session_id')
        if not all(reviewer.get(k) for k in ('id', 'session_id', 'model', 'effort')) or reviewer.get('fresh_context') is not True or sid in sessions or sid in (parent_session, run['session_id'], 'unknown'):
            raise ValueError('Independent fresh identified subagent required per batch')
        sessions.add(sid)
        report['usage'] = usage_record(report)
        original = {q['id']: q for q in packet['questions']}
        rows = report['questions']
        if len(rows) != len(original) or {q['id'] for q in rows} != set(original):
            raise ValueError('Batch coverage mismatch')
        known = {e['path']: e for e in packet['evidence'] + packet['assets']}
        def evidence(refs):
            if not refs:
                raise ValueError('Judgement/correction needs source evidence')
            for ref in refs:
                record = known.get(ref.get('path'))
                if not record or ref.get('sha256') != record['sha256'] or not ref.get('observation'):
                    raise ValueError('Evidence must bind an observed batch resource hash')
        for row in rows:
            if set(row['checks']) != set(CHECKS) or set(row['post_checks']) != set(CHECKS):
                raise ValueError('Six checks required')
            for check in row['checks'].values():
                if check['status'] not in ('pass', 'error', 'unresolved') or not check['reason']:
                    raise ValueError('Invalid check judgement')
                if check['status'] != 'unresolved':
                    evidence(check['evidence'])
            if any(s not in ('pass', 'unresolved') for s in row['post_checks'].values()):
                raise ValueError('Invalid post check')
            solution = row['independent_solution']
            if solution['label'] is not None:
                if not solution.get('reasoning'):
                    raise ValueError('Independent reasoning required')
                evidence(solution['evidence'])
            fields = set()
            for change in row['changes']:
                field = change['field']
                if field not in FIELDS or field in fields:
                    raise ValueError('Unsafe/duplicate correction field')
                fields.add(field)
                if change['before'] != original[row['id']][field] or change['before'] == change['after'] or not change['reason']:
                    raise ValueError('Stale or unjustified correction')
                evidence(change['evidence'])
            if not row['changes'] and any(v['status'] != 'pass' and row['post_checks'][k] == 'pass' for k, v in row['checks'].items()):
                raise ValueError('Cannot clear errors without a justified correction')
        # Validate the proposed batch before accepting its report. This does not
        # apply corrections or decide whether the coordinator accepts them.
        proposal = copy.deepcopy(baseline)
        proposal['questions'] = []
        proposal['exam']['expected_questions'] = [
            q for q in baseline['exam']['expected_questions'] if q['id'] in original]
        proposal['assets'] = packet['assets']
        # Packet evidence is a review-reference contract, not a final resource
        # record (it intentionally has no id/mime). Its binding is checked above.
        for row in rows:
            question = copy.deepcopy(original[row['id']])
            for change in row['changes']:
                question[change['field']] = copy.deepcopy(change['after'])
            proposal['questions'].append(question)
        validate(proposal)
        reports.append((batch_id, report))
    audited = [q['id'] for _, report in reports for q in report['questions']]
    if len(audited) != len(set(audited)) or set(audited) != set(run['target_question_ids']):
        raise ValueError('Independent coverage differs from frozen target questions')
    return run, baseline, reports

def decisions(folder):
    run, baseline, reports = load_reports(folder)
    new(folder / 'decisions-template.json', {'baseline_sha256': run['parent']['final_sha256'],
        'reviewer': {'id': '', 'session_id': ''}, 'decisions': [
        {'batch_id': bid, 'question_id': row['id'], 'field': c['field'],
         'report_sha256': digest(folder / 'batches' / bid / 'report.json'),
         'accept': False, 'reason': '', 'evidence': []}
        for bid, report in reports for row in report['questions'] for c in row['changes']]})

def consolidate(folder, decision_file):
    start = time.perf_counter()
    run, baseline, reports = load_reports(folder)
    if run['status'] != 'awaiting_reviews':
        raise ValueError('Already consolidated; use new experiment for a new pass')
    decision = read(decision_file)
    if decision['baseline_sha256'] != run['parent']['final_sha256']:
        raise ValueError('Decision baseline mismatch')
    rev = decision['reviewer']
    if not rev.get('id') or not rev.get('session_id') or rev['session_id'] in {r['reviewer']['session_id'] for _, r in reports}:
        raise ValueError('Coordinator must identify itself separately from batch agents')
    coordinator = read(folder / 'coordinator-usage.json') if (folder / 'coordinator-usage.json').exists() else {
        'scope': 'coordinator_only', 'usage_source': 'unavailable', 'usage': {k: None for k in USAGE}}
    if coordinator.get('scope') not in ('coordinator_only', 'verification_including_agents'):
        raise ValueError('Usage scope must avoid double counting')
    coordinator_usage = usage_record(coordinator)
    proposed = {(bid, row['id'], c['field']): c for bid, report in reports for row in report['questions'] for c in row['changes']}
    indexed = {(d['batch_id'], d['question_id'], d['field']): d for d in decision['decisions']}
    if len(indexed) != len(decision['decisions']) or set(indexed) != set(proposed):
        raise ValueError('Every proposed correction needs exactly one decision')
    accepted = set()
    for key, d in indexed.items():
        if type(d['accept']) is not bool or not d['reason'] or d['report_sha256'] != digest(folder / 'batches' / key[0] / 'report.json'):
            raise ValueError('Decision/report binding or justification invalid')
        if d['accept']:
            refs = proposed[key]['evidence']
            if not d['evidence'] or any(e not in refs for e in d['evidence']):
                raise ValueError('Accepted correction needs cited report evidence')
            accepted.add(key)
    final = copy.deepcopy(baseline)
    existing = {a['id'] for a in baseline['assets']}
    for bid, report in reports:
        packet = read(folder / 'batches' / bid / 'input.json')
        for a in packet['assets']:
            if a['id'] not in existing:
                if a['id'] in {r['id'] for r in final['assets']}:
                    raise ValueError('Cross-batch duplicate added asset ID')
                final['assets'].append(a)
                copy_resource(folder / 'additional-assets' / bid / a['path'], folder / a['path'])
    lookup = {q['id']: q for q in final['questions']}
    verified = errors = unresolved = 0
    for bid, report in reports:
        for row in report['questions']:
            q = lookup[row['id']]
            errors += sum(c['status'] == 'error' for c in row['checks'].values())
            for c in row['changes']:
                if (bid, q['id'], c['field']) in accepted:
                    q[c['field']] = copy.deepcopy(c['after'])
            ref = f'.work/verification/batches/{bid}/report.json#{q["id"]}'
            all_accepted = all((bid, q['id'], c['field']) in accepted for c in row['changes'])
            solution = row['independent_solution']
            clear = all_accepted and all(s == 'pass' for s in row['post_checks'].values()) and solution['label'] is not None and solution['label'] == q['answer']['label']
            if clear:
                q['fidelity'] = {'status': 'reviewed', 'review_ref': ref}
                q['answer'].update(status='verified', source_ref=ref)
                q['explanation']['status'] = 'verified'
                verified += 1
            else:
                q['fidelity'] = {'status': 'pending', 'review_ref': ref}
                if q['answer']['label'] is not None:
                    q['answer']['status'] = 'provisional'
                if q['explanation']['blocks']:
                    q['explanation']['status'] = 'provisional'
                q['issues'].append('Verificación experimental: discrepancia o evidencia insuficiente; revisar informe ' + ref)
                unresolved += 1
    # Compatible v1 container; experimental metadata is in extensible run, never schema changes.
    final['run'].update(id=run['id'], created_at=now(), verification_variant='direct-verified',
                        verification_model=run['model'], verification_effort=run['effort'],
                        parent_run_id=run['parent']['id'], parent_final_sha256=run['parent']['final_sha256'],
                        protocol_version=run['protocol_version'])
    output = publication_path(folder)
    for resource in final['assets'] + final['evidence']:
        copy_resource(artifact_path(folder, resource['path']), output / resource['path'])
    new(output / 'candidate.json', final)
    new(folder / 'decisions-applied.json', decision)
    result = pack(output / 'candidate.json')
    totals = {k: sum(r['usage'][k] for _, r in reports) if all(r['usage'].get(k) is not None for _, r in reports) else None for k in USAGE}
    combined = {k: coordinator_usage[k] if coordinator['scope'] == 'verification_including_agents' else
                totals[k] + coordinator_usage[k] if totals[k] is not None and coordinator_usage[k] is not None else None
                for k in USAGE}
    summary = {'format': 'direct-verification-metrics-1.0', 'baseline_sha256': run['parent']['final_sha256'],
               'final_sha256': digest(output / 'final.json'), 'questions_audited': sum(len(r['questions']) for _, r in reports),
               'questions_verified_by_ai': verified, 'questions_pending': sum(q['answer']['status'] != 'verified' for q in final['questions']),
               'check_errors_found': errors, 'questions_with_errors': sum(any(c['status']=='error' for c in row['checks'].values()) for _,r in reports for row in r['questions']),
               'corrections_proposed': len(proposed), 'corrections_applied': len(accepted),
               'corrections_rejected': len(proposed)-len(accepted), 'subagents': len(reports),
               'subagent_usage': totals, 'verification_usage': combined,
               'known_subagent_subtotals': {k: sum(r['usage'][k] for _, r in reports if r['usage'].get(k) is not None) for k in USAGE},
               'known_subagent_counts': {k: sum(r['usage'].get(k) is not None for _, r in reports) for k in USAGE},
               'coordinator': coordinator, 'preparation_seconds': run['preparation_seconds'],
               'consolidation_seconds': time.perf_counter()-start,
               'accuracy_gain': None, 'accuracy_note': 'Requires separate independent paired evaluation; AI verification is not ground truth.'}
    run.update(status='packaged', finished_at=now(), final_sha256=summary['final_sha256'])
    run['wall_seconds'] = (datetime.fromisoformat(run['finished_at']) - datetime.fromisoformat(run['started_at'])).total_seconds()
    summary['wall_seconds'] = run['wall_seconds']
    new(folder / 'metrics.json', summary)
    write(folder / 'run.json', run)
    # Evaluator receives run metadata next to final, with legacy variant matching its container.
    output_run = {**run, 'variant': final['run'].get('variant', 'direct'), 'model': final['run']['model'],
                  'verification_variant': 'direct-verified',
                  'suite_sha256': final['run'].get('suite_sha256'), 'config': {'effort': run['effort']}}
    new(output / 'run.json', output_run)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare')
    a.add_argument('--parent', required=True); a.add_argument('--run-id', required=True)
    a.add_argument('--output-dir', required=True)
    a.add_argument('--batch-size', type=int, default=10)
    for key in ('model', 'effort', 'session'):
        a.add_argument('--' + key, required=True)
    for name in ('check', 'decisions', 'consolidate'):
        c = sub.add_parser(name); c.add_argument('--run', required=True)
        if name == 'consolidate': c.add_argument('--decisions', required=True)
    e = sub.add_parser('add-evidence')
    e.add_argument('--run', required=True); e.add_argument('--batch', required=True)
    e.add_argument('--requests', required=True)
    args = p.parse_args()
    configure_workspace(Path(args.output_dir) if args.command == 'prepare' else Path(args.run).absolute().parent.parent)
    try:
        if args.command == 'prepare':
            print(prepare(args.parent, args.run_id, args.batch_size, args.model, args.effort, args.session, args.output_dir))
        elif args.command == 'check':
            _, _, reports = load_reports(inside(args.run)); print(f'{len(reports)} bound reports; semantic claims remain AI judgements')
        elif args.command == 'decisions': decisions(inside(args.run))
        elif args.command == 'add-evidence': add_evidence(inside(args.run), args.batch, read(args.requests))
        else: print(consolidate(inside(args.run), args.decisions))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr); return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
