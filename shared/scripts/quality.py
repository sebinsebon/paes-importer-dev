"""Honest delivery status: integrity, review and curriculum remain separate."""
from lab import question_blocks


def summarize(candidate, self_checks=None):
    issues = []
    counts = {'fidelity_reviewed': 0, 'answers_verified': 0, 'curriculum_classified': 0,
              'curriculum_pending': 0, 'curriculum_doubtful': 0, 'unresolved_questions': 0}
    for q in candidate['questions']:
        qid = q['id']
        counts['fidelity_reviewed'] += q['fidelity']['status'] == 'reviewed'
        counts['answers_verified'] += q['answer']['status'] == 'verified'
        unresolved = any(b['type'] == 'unresolved' for b in question_blocks(q))
        counts['unresolved_questions'] += unresolved
        if unresolved:
            issues.append({'question_id': qid, 'field': 'content', 'code': 'UNRESOLVED', 'severity': 'warning'})
        if q['fidelity']['status'] == 'rejected':
            issues.append({'question_id': qid, 'field': 'content', 'code': 'FIDELITY_REJECTED', 'severity': 'critical'})
        if q['fidelity']['status'] != 'reviewed' or q['answer']['status'] != 'verified':
            issues.append({'question_id': qid, 'field': 'review', 'code': 'UNVERIFIED', 'severity': 'warning'})
        c = q.get('curriculum')
        if c:
            pending = c['eje'] is None
            counts['curriculum_pending'] += pending
            counts['curriculum_classified'] += not pending
            counts['curriculum_doubtful'] += c['en_temario'] == 'dudoso' and not pending
            if pending or c['en_temario'] == 'dudoso':
                issues.append({'question_id': qid, 'field': 'curriculum', 'code': 'CURRICULUM_PENDING' if pending else 'CURRICULUM_DOUBTFUL', 'severity': 'warning'})
        for issue in q['issues']:
            if issue.startswith('CRITICAL:'):
                issues.append({'question_id': qid, 'field': 'content', 'code': issue[9:].strip() or 'CRITICAL', 'severity': 'critical'})
        for dimension, check in (self_checks or {}).get(qid, {}).get('row', {}).get('checks', {}).items():
            if check['status'] != 'pass':
                issues.append({'question_id': qid, 'field': dimension, 'code': 'COTEJO_' + check['status'].upper(),
                               'severity': 'critical' if check['status'] == 'fail' else 'warning'})
    critical = any(i['severity'] == 'critical' for i in issues)
    complete = not critical and not any(i['code'].startswith('COTEJO_') for i in issues) and not counts['unresolved_questions'] and not counts['curriculum_pending'] and all(
        q['answer']['status'] != 'missing' and q['explanation']['status'] != 'missing' for q in candidate['questions'])
    return {'integrity': 'passed', 'coverage': {'questions': len(candidate['questions']), **counts},
            'issues': issues, 'publication_eligibility': 'blocked' if critical else 'complete' if complete else 'partial',
            'semantic_correctness': 'not_proven_by_structural_validation',
            'review_scope': 'independent' if counts['fidelity_reviewed'] == len(candidate['questions']) else 'mixed' if counts['fidelity_reviewed'] else 'producer_only',
            'reviewed_question_ids': [q['id'] for q in candidate['questions'] if q['fidelity']['status'] == 'reviewed'],
            'verified_answer_ids': [q['id'] for q in candidate['questions'] if q['answer']['status'] == 'verified']}


def require_publishable(result):
    if result['publication_eligibility'] == 'blocked':
        raise ValueError('Critical quality issues block publication; preserve candidate and resolve source conflict')
    return result
