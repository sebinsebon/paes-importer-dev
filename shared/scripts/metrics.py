"""Measured provider usage accounting. Missing measurements remain unknown."""
import math
FIELDS = ('input_tokens', 'output_tokens', 'cost', 'duration_seconds')

def aggregate_usage(events):
    identifiers = set()
    currencies = set()
    known = {key: 0 for key in FIELDS}
    measured = {key: 0 for key in FIELDS}
    for event in events:
        event_id = event.get('event_id')
        if not isinstance(event_id, str) or not event_id.strip() or event_id in identifiers:
            raise ValueError('Each measured call needs a unique event_id; do not repeat coordinator/worker totals')
        identifiers.add(event_id)
        if event.get('aggregate', False):
            raise ValueError('Supply individual provider calls, not overlapping aggregates')
        for key in FIELDS:
            value = event.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid measured usage: ' + key)
            if key.endswith('_tokens') and not isinstance(value, int):
                raise ValueError('Measured tokens must be integers')
            if key == 'cost':
                currency = event.get('currency')
                if not isinstance(currency, str) or not currency.strip():
                    raise ValueError('Measured cost requires its currency')
                currencies.add(currency.upper())
                if len(currencies) > 1:
                    raise ValueError('Cannot aggregate different cost currencies')
            known[key] += value
            measured[key] += 1
    return {'calls': len(events), 'currency': next(iter(currencies)) if currencies else None,
        **{key: known[key] if events and measured[key] == len(events) else None for key in FIELDS},
        'known_subtotals': known, 'measured_calls': measured,
        'accounting': 'individual_provider_calls_only', 'estimated_from_characters': False}

def measured_savings(baseline, candidate):
    result = {}
    for key in FIELDS:
        before, after = baseline.get(key), candidate.get(key)
        result[key] = None if (key == 'cost' and (not baseline.get('currency') or baseline.get('currency') != candidate.get('currency'))) or before is None or after is None or before <= 0 else (before - after) / before
    return result
