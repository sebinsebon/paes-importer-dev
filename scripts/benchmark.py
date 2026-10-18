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
from metrics import aggregate_usage, measured_savings

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
    required = ('host', 'model', 'effort', 'capabilities_sha256', 'generation_config_sha256')
    def conditions(report):
        result = {}
        for run in report['runs']:
            metadata = run.get('metadata', {})
            pair = metadata.get('pair_id', run['id'])
            if pair in result or any(not isinstance(metadata.get(k),str) or not metadata[k].strip() for k in required) or any(not re.fullmatch(r'[a-f0-9]{64}',metadata.get(k,'')) for k in ('capabilities_sha256','generation_config_sha256')) or not run.get('input_hashes', {}).get('gold'):
                return None
            result[pair] = (run['status'], run['input_hashes']['gold'],
                            tuple(run['input_hashes'].get(k) for k in ('gold_taxonomy','id_map','certification')),
                            tuple(metadata[k] for k in required))
        return result
    left, right = conditions(baseline), conditions(candidate)
    comparable = left is not None and left == right
    return {'conditions_matched': comparable,
            'measured_savings': measured_savings(baseline['usage'], candidate['usage']) if comparable else {key: None for key in ('input_tokens','output_tokens','cost','duration_seconds')},
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
