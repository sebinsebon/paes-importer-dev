"""Source-observed requirements, kept outside model-editable final.json."""
import re
from lab import bbox, blocks_in


def validate_inventory_record(record, catalog):
    inventory = record.get('content_inventory')
    if not isinstance(inventory, list):
        raise ValueError('Observe content_inventory explicitly (empty only for plain text)')
    labels = record.get('option_labels') or []
    pages = {(p['source_id'], p['page']): p for p in catalog['pages']}
    seen = set()
    for item in inventory:
        if not isinstance(item, dict):
            raise ValueError('Invalid content inventory entry')
        field, kind = item.get('field'), item.get('type')
        if field not in ['stem', *['options/' + label for label in labels]] or kind not in ('image', 'table', 'math'):
            raise ValueError('Inventory needs a stem/options/LABEL field and image/table/math type')
        if (field, kind) in seen:
            raise ValueError('Duplicate inventory field/type; combine counts and regions')
        seen.add((field, kind))
        if type(item.get('count')) is not int or item['count'] < 1:
            raise ValueError('Inventory count must be a positive integer')
        if not isinstance(item.get('regions'), list) or not item['regions']:
            raise ValueError('Inventory requires source regions including labels and units')
        for region in item['regions']:
            if not isinstance(region, dict):
                raise ValueError('Inventory region must be an object')
            page = pages.get((record['source_id'], region.get('page')))
            if not page or type(region.get('page')) is not int:
                raise ValueError('Inventory region outside source catalog')
            bbox(region['bbox'], page['width'], page['height'])
        symbols = item.get('symbols', [])
        if not isinstance(symbols, list) or any(not isinstance(s, str) or not re.fullmatch('[A-Za-z]', s) for s in symbols):
            raise ValueError('Inventory symbols must be single mathematical variable letters')
        if symbols and kind != 'math':
            raise ValueError('Only math inventory entries declare variable symbols')


def validate_inventory(question, record, candidate):
    """Counts are minima: equivalent math may use multiple inline blocks."""
    fields = {'stem': question['stem'], **{'options/' + o['label']: o['blocks'] for o in question['options']}}
    assets = {a['id']: a for a in candidate['assets']}
    for item in record.get('content_inventory', []):
        field_blocks = list(blocks_in(fields.get(item['field'], [])))
        if any(b['type'] == 'unresolved' for b in field_blocks):
            continue  # Explicit uncertainty remains partial, never complete.
        blocks = [b for b in field_blocks if b['type'] == item['type']]
        prefix = question['id'] + ': SOURCE_CONTENT_OMITTED ' + item['field']
        if len(blocks) < item['count']:
            raise ValueError(prefix + ' needs ' + item['type'])
        if item['type'] == 'math':
            latex = ' '.join(b['latex'] for b in blocks)
            # Commands and prose/unit runs are not variable names. Adjacent
            # letters such as mn remain two valid mathematical symbols.
            latex = re.sub(r'\\(?:text|textrm|textnormal|mathrm|operatorname)\s*\{[^{}]*\}', '', latex)
            variables = re.sub(r'\\[A-Za-z]+', '', latex)
            for symbol in item.get('symbols', []):
                if symbol not in variables:
                    raise ValueError(prefix + ': variable ' + symbol + ' needs math.latex')
        if item['type'] == 'image':
            resources = [assets[b['asset_id']] for b in blocks]
            for region in item['regions']:
                if not any(a['source_id'] == question['source_id'] and a['page'] == region['page'] and
                           contains(a['bbox'], region['bbox']) for a in resources):
                    raise ValueError(question['id'] + ': CROP_EXCLUDES_SOURCE_REGION ' + item['field'])


def contains(outer, inner):
    return all(outer[i] <= inner[i] + .01 for i in (0, 1)) and all(outer[i] >= inner[i] - .01 for i in (2, 3))
