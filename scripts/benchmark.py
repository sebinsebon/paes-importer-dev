"""Evaluate existing imports and measured usage; does not generate AI imports."""
import argparse
import json
import re
import sys
from pathlib import Path
from compare_gold import compare
from gold import load_reference, sha
from maintenance_io import write_report
from dev_paths import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT / 'shared/scripts'))
from metrics import FIELDS as USAGE_FIELDS, aggregate_usage, measured_savings, summarize_timeline

def host_events(path, context=None):
    """Import normalized host JSON/JSONL; retain unknown times as unknown.

    Hosts export individual intervals with category auxiliary/provider/backoff/pause,
    explicit timezone timestamps and optional retry/backoff observations. Raw log
    messages without timing are retained as observations, never invented intervals.
    """
    path = Path(path)
    raw = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.log':
        # AGY's retry records expose an announced delay, not an observed sleep or
        # inference interval. The local log timestamp omits year/timezone.
        from datetime import datetime
        events=[]
        for number,line in enumerate(raw.splitlines(),1):
            match=re.search(r'Run: attempt (\d+) failed \((.*)\), retrying in ([\d.]+)s',line)
            if not match: continue
            reason=match[2]
            code=re.search(r'code (\d+)',reason)
            stamp=re.match(r'[IWEF](\d{2})(\d{2}) (\d{2}:\d{2}:\d{2}\.\d+)',line)
            timestamp=None
            if stamp and context and context.get('year') and context.get('utc_offset'):
                timestamp=datetime.fromisoformat(f"{context['year']}-{stamp[1]}-{stamp[2]}T{stamp[3]}{context['utc_offset']}").isoformat()
            events.append({'event':'provider_retry','category':'provider','source_line':number,
                'timestamp':timestamp,'retry_count':1,'attempt':int(match[1]),
                'error_code':'PROVIDER_'+code[1] if code else 'PROVIDER_STREAM_IDLE_TIMEOUT' if 'stream idle timeout' in reason else 'PROVIDER_ERROR',
                'announced_backoff_seconds':float(match[3]),'started_at':None,'finished_at':None})
        if not events and raw.strip():
            raise ValueError('No recognized AGY retry records; export normalized JSON/JSONL for other hosts')
        return events
    rows = json.loads(raw) if path.suffix.lower() == '.json' else [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(rows, dict):
        rows = rows.get('events')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Host logs must contain individual event objects')
    return rows

def evaluate(manifest, directory):
    directory = Path(directory)
    runs = manifest.get('runs', [])
    if not runs:
        raise ValueError('Benchmark needs existing runs')
    identifiers = set()
    all_events = []
    rows = []
    for run in runs:
        run_id = run.get('id')
        if not isinstance(run_id, str) or not run_id or run_id in identifiers:
            raise ValueError('Run IDs must be unique')
        identifiers.add(run_id)
        if run.get('status') not in ('completed', 'failed', 'interrupted'):
            raise ValueError('Declare completed, failed or interrupted status')
        events = run.get('usage', [])
        usage = aggregate_usage(events)
        all_events.extend(events)
        record = {'id': run_id, 'status': run['status'], 'usage': usage,
                  'metadata': run.get('metadata', {}), 'comparison': None}
        timeline = list(run.get('events', []))
        log_hashes = {}
        for name in ('importer_events', 'host_events'):
            if run.get(name):
                path = Path(run[name])
                path = path if path.is_absolute() else directory / path
                timeline.extend(host_events(path,run.get('host_log_context') if name=='host_events' else None))
                log_hashes[name] = sha(path.read_bytes())
        record['timing'] = summarize_timeline(timeline, requested_at=run.get('requested_at'), finished_at=run.get('finished_at'))
        record['log_hashes'] = log_hashes
        if run['status'] == 'completed':
            def resolve(name):
                supplied = Path(run[name])
                return supplied if supplied.is_absolute() else directory / supplied
            gold_path, candidate_path = resolve('gold'), resolve('candidate')
            reference, _ = load_reference(gold_path)
            candidate, _ = load_reference(candidate_path)
            annotations=None
            if run.get('gold_taxonomy'):
                annotations = json.loads(resolve('gold_taxonomy').read_text(encoding='utf-8-sig'))['questions']
                if set(annotations) != {q['id'] for q in reference['questions']}:
                    raise ValueError('Gold annotation coverage mismatch')
            mapping = json.loads(resolve('id_map').read_text(encoding='utf-8-sig')) if run.get('id_map') else None
            record['comparison'] = compare(reference, candidate, mapping, annotations)
            record['input_hashes'] = {'gold': sha(gold_path.read_bytes()), 'candidate': sha(candidate_path.read_bytes()),
                **{name:sha(resolve(name).read_bytes()) for name in ('gold_taxonomy','id_map','certification') if run.get(name)}}
            # Certification cannot be inferred from compared content or model statuses.
            record['gold_certification'] = 'not_checked'
            if run.get('certification'):
                certificate = json.loads(resolve('certification').read_text(encoding='utf-8-sig'))
                digest = record['input_hashes']['gold']
                if certificate.get('reference_sha256') != digest:
                    raise ValueError('Certificate is not bound to this reference')
                record['gold_certification'] = certificate.get('status', 'pending')
        else:
            record['failure_reason'] = run.get('failure_reason', 'not_supplied')
        rows.append(record)
    return {'format': 'paessed-benchmark-evaluation', 'schema_version': '0.1.0',
            'runs': rows, 'usage': aggregate_usage(all_events),
            'counts': {status: sum(r['status'] == status for r in rows) for status in ('completed','failed','interrupted')},
            'semantic_review': 'not_performed', 'automatic_promotion': False,
            'quality_gate': 'Requires source fidelity and adjudicated semantic/visual review; literal equality alone is insufficient.'}

def compare_reports(baseline, candidate):
    required = ('host', 'model', 'effort', 'capabilities_sha256', 'generation_config_sha256',
                'sources_sha256','environment_sha256','batch_policy_sha256')
    def conditions(report):
        result = {}
        for run in report['runs']:
            metadata = run.get('metadata', {})
            pair = metadata.get('pair_id', run['id'])
            if pair in result or any(not isinstance(metadata.get(k),str) or not metadata[k].strip() for k in required) or any(not re.fullmatch(r'[a-f0-9]{64}',metadata.get(k,'')) for k in required if k.endswith('_sha256')) or not run.get('input_hashes', {}).get('gold'):
                return None
            result[pair] = (run['status'], run['input_hashes']['gold'],
                            tuple(run['input_hashes'].get(k) for k in ('gold_taxonomy','id_map','certification')),
                            tuple(metadata[k] for k in required))
        return result
    left, right = conditions(baseline), conditions(candidate)
    comparable = left is not None and left == right
    from statistics import median
    pairs = []
    if comparable:
        right_rows = {r.get('metadata', {}).get('pair_id', r['id']):r for r in candidate['runs']}
        for row in baseline['runs']:
            other = right_rows[row.get('metadata', {}).get('pair_id', row['id'])]
            a, b = row.get('timing', {}).get('wall_seconds'), other.get('timing', {}).get('wall_seconds')
            if row['status'] == other['status'] == 'completed' and a is not None and b is not None:
                pairs.append((a,b))
    return {'conditions_matched': comparable,
            'measured_savings': measured_savings(baseline['usage'], candidate['usage']) if comparable else {key: None for key in USAGE_FIELDS},
            'wall_time': {'paired_repetitions': len(pairs),
                'baseline_median_seconds': median(a for a,b in pairs) if pairs else None,
                'candidate_median_seconds': median(b for a,b in pairs) if pairs else None,
                'median_paired_reduction_seconds': median(a-b for a,b in pairs) if pairs else None,
                'conclusion': 'descriptive_only_requires_fidelity_adjudication' if len(pairs)>=3 else 'inconclusive'},
            'warning': 'Savings are descriptive. Same reference, paired repetitions, host, model, effort, capabilities and generation settings are required; semantic quality must be adjudicated separately.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, help='Existing runs, references and individual measured provider calls')
    parser.add_argument('--output')
    parser.add_argument('--baseline-report', help='Optional earlier report; savings are descriptive, not quality promotion')
    args = parser.parse_args()
    manifest_file = Path(args.manifest)
    manifest = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    result = evaluate(manifest, manifest_file.parent)
    if args.baseline_report:
        previous = json.loads(Path(args.baseline_report).read_text(encoding='utf-8-sig'))
        result['baseline_comparison'] = compare_reports(previous, result)
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        write_report(args.output, raw)
    else:
        print(raw, end='')

if __name__ == '__main__':
    main()
