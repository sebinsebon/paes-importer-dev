"""Publication policy, separate from backwards-compatible readers."""
OFFICIAL_FINAL_VERSION = '0.2.0'


def require_official_final(data):
    if data.get('schema_version') != OFFICIAL_FINAL_VERSION:
        raise ValueError('New publication requires final.json 0.2.0; historical 0.1.0 is read-only. Use its frozen release for an old run.')
