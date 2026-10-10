"""Record the actual PDF reading mechanism without inventing tool receipts."""
from lab import read

def validate_direct_input(candidate, root):
    ledger=read(root/'direct-input.json')
    if ledger.get('mode') not in ('native_pdf', 'page_images_fallback') or ledger.get('input_kind')!='pdf' or not ledger.get('reader'):
        raise ValueError('Identify the actual original-PDF reader; report a blocker if unavailable')
    if ledger.get('visual_content_understood') is not True or not ledger.get('capability_observation'):
        raise ValueError('Record a concrete visual capability observation')
    if candidate['run'].get('input_mode') != ledger.get('mode') or candidate['run'].get('all_pages_read') is not True:
        raise ValueError('Incomplete PDF reading')
    records=ledger.get('sources',[])
    indexed={s['source_id']:s for s in records}
    if len(indexed)!=len(records) or set(indexed)!={s['id'] for s in candidate['sources']}:
        raise ValueError('Record each PDF source once')
    for source in candidate['sources']:
        item=indexed[source['id']]
        if item.get('sha256')!=source['sha256'] or item.get('pages_read')!=list(range(1,source['page_count']+1)) or any(type(p) is not int for p in item.get('pages_read', [])):
            raise ValueError('Source hash or physical page coverage mismatch')
    return {'valid':True,'attestation':'declared_actual_mechanism_not_proof_of_comprehension'}
