"""Redacted publication screening of all reachable history and the public worktree.

Pattern screening finds candidates, not proof that publishing is safe. No network
operation or publication occurs. Ignored backups/results are deliberately not
public worktree inputs, but every reachable Git blob is scanned regardless of name.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from dev_paths import linked, output_path, unlinked_path

SCANNER_VERSION = '1.0.0'
PATTERN_VERSION = '2026-10-18.1'
PATTERNS = {
    'private-key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github-token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{50,})'),
    'openai-token': re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}'),
    'aws-access-id': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'credential-assignment-candidate': re.compile(
        rb'''(?i)\b(?:password|passwd|api[_-]?key|access[_-]?key|secret[_-]?key|client[_-]?secret|auth[_-]?token|token)\b["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']'''),
}
PRIVATE_NAME = re.compile(r'(?i)(?:^|/)(?:\.env(?:\..+)?|id_rsa|id_ed25519|credentials(?:\.[^/]*)?|secrets?(?:\.[^/]*)?)$|\.(?:pdf|paessed|zip|pfx|p12|pem|key)$')
PLACEHOLDER = re.compile(rb'(?i)(?:example|placeholder|dummy|synthetic|your[-_ ]|changeme|\$\{|<|^x+$|^0+$)')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repository, *arguments):
    return subprocess.run(['git', '-c', 'safe.directory=' + repository.as_posix(), '-C', str(repository), *arguments], capture_output=True, check=True).stdout


def signatures(data, location):
    findings = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(data):
            value = match.group(1) if match.lastindex else match.group()
            if kind == 'credential-assignment-candidate' and PLACEHOLDER.search(value):
                continue
            findings.append({**location, 'category': kind, 'line': data[:match.start()].count(b'\n') + 1,
                             'match_sha256': digest(value), 'disposition': 'human_review_required'})
    return findings


def audit(repository):
    repository = unlinked_path(repository).resolve(strict=True)
    refs = [line.split(' ', 1) for line in git(repository, 'for-each-ref', '--format=%(refname) %(objectname)').decode().splitlines()]
    head = git(repository, 'rev-parse', 'HEAD').decode().strip()
    commits = git(repository, 'rev-list', '--all', 'HEAD').decode().splitlines()
    objects = git(repository, 'rev-list', '--objects', '--all', 'HEAD').splitlines()
    object_ids = sorted({line.split(b' ', 1)[0].decode('ascii') for line in objects})
    batch = subprocess.run(['git', '-c', 'safe.directory=' + repository.as_posix(), '-C', str(repository), 'cat-file', '--batch-check=%(objectname) %(objecttype)'],
                           input=('\n'.join(object_ids) + '\n').encode(), capture_output=True, check=True).stdout
    blobs = [line.split()[0].decode() for line in batch.splitlines() if line.split()[1] == b'blob']
    findings = []
    historic_paths = set()
    metadata = []
    for commit in commits:
        content = git(repository, 'cat-file', 'commit', commit)
        metadata.append({'commit': commit, 'metadata_sha256': digest(content)})
        findings.extend(signatures(content, {'scope': 'commit_metadata', 'commit': commit}))
        for record in git(repository, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
            if not record:
                continue
            header, name = record.split(b'\t', 1)
            path = name.decode('utf-8', errors='replace')
            historic_paths.add(path)
    for path in sorted(historic_paths):
        if PRIVATE_NAME.search(path):
            findings.append({'scope': 'historical_path', 'path': path,
                             'category': 'private_or_archive_filename_candidate', 'disposition': 'human_review_required'})
    for blob in blobs:
        findings.extend(signatures(git(repository, 'cat-file', 'blob', blob), {'scope': 'blob', 'blob': blob}))
    public_files = []
    names = set(git(repository, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')) - {b''}
    for name in sorted(names):
        relative = name.decode('utf-8', errors='replace')
        path = repository / relative
        if not path.exists() and not linked(path):
            continue
        if linked(path):
            findings.append({'scope': 'public_worktree', 'path': relative, 'category': 'linked_path_candidate',
                             'disposition': 'human_review_required'})
            continue
        data = path.read_bytes()
        public_files.append({'path': relative, 'sha256': digest(data)})
        if PRIVATE_NAME.search(relative):
            findings.append({'scope': 'public_worktree', 'path': relative,
                             'category': 'private_or_archive_filename_candidate', 'disposition': 'human_review_required'})
        findings.extend(signatures(data, {'scope': 'public_worktree', 'path': relative}))
    return {'scanner_version': SCANNER_VERSION, 'pattern_version': PATTERN_VERSION,
            'scanner_sha256': digest(Path(__file__).read_bytes()), 'head': head,
            'refs': [{'name': name, 'object': object_id} for name, object_id in refs],
            'commit_count': len(commits), 'blob_count': len(blobs), 'historic_path_count': len(historic_paths),
            'commit_metadata': metadata, 'public_worktree': public_files, 'findings': findings,
            'publication_status': 'human_review_required' if findings else 'no_pattern_candidates_not_proof',
            'limitations': ['Heuristic screening cannot prove absence of private information.',
                            'Ignored local files are excluded from the public worktree, but reachable history is not excluded.',
                            'Commit identities and messages were scanned; only metadata hashes are reported.',
                            'No remote repository was created and no content was published.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    destination = output_path(args.report, within_dev=True)
    if destination.exists():
        raise ValueError('Preserve existing audit report; choose another filename')
    report = audit(args.repo)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'commits': report['commit_count'], 'blobs': report['blob_count'],
                      'findings': len(report['findings']), 'publication_status': report['publication_status']}))
    return int(bool(report['findings']))


if __name__ == '__main__':
    raise SystemExit(main())
