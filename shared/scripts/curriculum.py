"""General M1 curriculum contract; classification is performed by the host agent."""
from pathlib import Path
import hashlib
import json

CATALOG_PATH = Path(__file__).resolve().parents[1] / 'references' / 'curriculum-m1.json'

def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))

def catalog_hash():
    return hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()

def pending_curriculum():
    return {'eje': None, 'subeje': None, 'en_temario': 'dudoso'}

def validate_question_curriculum(question):
    value = question.get('curriculum')
    if not isinstance(value, dict) or set(value) != {'eje','subeje','en_temario'}:
        raise ValueError('curriculum requires exactly eje, subeje and en_temario')
    if value['en_temario'] not in ('si','no','dudoso'):
        raise ValueError('Invalid en_temario')
    if value['eje'] is None or value['subeje'] is None:
        if value != pending_curriculum() or 'CURRICULUM_PENDING' not in question.get('issues',[]):
            raise ValueError('Pending curriculum requires null pair, dudoso and CURRICULUM_PENDING')
        return False
    pairs = {(axis['eje'],sub) for axis in catalog()['ejes'] for sub in axis['subejes']}
    if (value['eje'],value['subeje']) not in pairs:
        raise ValueError('Invalid curriculum eje/subeje pair')
    if 'CURRICULUM_PENDING' in question.get('issues',[]):
        raise ValueError('Classified curriculum cannot retain CURRICULUM_PENDING')
    return True

def curriculum_hash(question, content_sha256):
    payload={'content_sha256':content_sha256,'curriculum':question['curriculum'],'catalog_sha256':catalog_hash()}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

def prepare_ledger(candidate, response, content_hash, root, previous=None):
    """Require substantive host rationale; no claims of authenticated comprehension."""
    previous = previous or {}
    proposed = response.get('curriculum_provenance',{})
    batch_ids = {q['id'] for q in response['questions']}
    if not isinstance(proposed,dict) or not set(proposed).issubset(batch_ids):
        raise ValueError('Curriculum provenance must refer only to batch questions')
    result={}
    by_id={q['id']:q for q in response['questions']}
    for q in candidate['questions']:
        classified=validate_question_curriculum(q)
        binding=curriculum_hash(q,content_hash(q,candidate,root))
        if q['id'] in by_id:
            record=proposed.get(q['id'])
            if not classified:
                result[q['id']]={'curriculum_sha256':binding,'catalog_sha256':catalog_hash(),'status':'pending'}
                continue
            if not isinstance(record,dict) or not isinstance(record.get('reason'),str) or not record['reason'].strip():
                raise ValueError(q['id']+': classification requires curriculum_provenance.reason')
            evidence=record.get('evidence',[])
            if not isinstance(evidence,list) or not evidence:
                raise ValueError(q['id']+': classification requires localized evidence')
            for ref in evidence:
                if not isinstance(ref,dict) or ref.get('source_id')!=q['source_id'] or type(ref.get('page')) is not int or ref.get('page') not in {r['page'] for r in q['regions']} or not isinstance(ref.get('observation'),str) or not ref['observation'].strip():
                    raise ValueError(q['id']+': curriculum evidence must match question regions')
            result[q['id']]={**record,'curriculum_sha256':binding,'catalog_sha256':catalog_hash(),'status':'classified','attestation':'host declaration, not proof of comprehension'}
        elif previous.get(q['id'],{}).get('curriculum_sha256')==binding:
            result[q['id']]=previous[q['id']]
    return result
