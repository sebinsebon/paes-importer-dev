"""Host-independent routing. No inference or claims of model accuracy."""
def select_mode(host, question_ids, covered_ids, subagents=False, experimental=None, review_ids=None):
    if host not in ('cli', 'web'):
        raise ValueError('host must be cli or web')
    expected, covered = set(question_ids), set(covered_ids)
    if not expected or not covered <= expected:
        raise ValueError('Invalid question coverage')
    missing = expected - covered
    if host == 'web' and missing and experimental not in ('yes', 'no'):
        return {'status': 'needs_consent', 'missing_questions': sorted(missing)}
    solve = missing if host == 'cli' or experimental == 'yes' else set()
    requested_reviews = set(review_ids or [])
    if not requested_reviews <= expected:
        raise ValueError('Review selection outside question coverage')
    if requested_reviews and (host != 'cli' or not subagents):
        raise ValueError('Requested independent review requires CLI and available subagents')
    independent = solve | requested_reviews if host == 'cli' and subagents else set()
    mode = 'answer-key' if not missing else ('mixed' if covered else 'solve')
    if missing and not solve:
        mode = 'partial-pending'
    return {'status': 'ready', 'processing_mode': mode,
            'review_mode': 'independent' if independent else 'self',
            'solve_question_ids': sorted(solve),
            'independent_question_ids': sorted(independent),
            'pending_question_ids': sorted(missing - solve)}
