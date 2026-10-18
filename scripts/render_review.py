"""Private maintenance entrypoint; runtime implementation is bundled."""
import argparse
import json
import sys
from pathlib import Path
from dev_paths import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT/'shared/scripts'))
from source_review import build_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--output', required=True)
    parser.add_argument('--scale', type=float, default=1.5)
    args = parser.parse_args()
    sources = {}
    for value in args.source:
        sid, sep, file = value.partition('=')
        if not sep or not sid or not file or sid in sources:
            parser.error('Supply unique --source ID=PATH')
        sources[sid] = file
    print(json.dumps(build_review(args.candidate, sources, args.output, args.scale, workspace=WORK_ROOT), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
