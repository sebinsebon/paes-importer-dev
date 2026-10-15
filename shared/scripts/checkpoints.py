"""Crash recovery for candidate, curriculum ledger and ingest checkpoints.

Candidate replacement is the commit point. A durable journal contains before/after
bytes; resume rolls back if candidate is old and finishes if candidate is new.
"""
import base64
import json
import os
import uuid
from contextlib import contextmanager
import threading
_lock_state = threading.local()
from pathlib import Path
from lab import artifact_path, inside, write, read

JOURNAL = 'ingest-transaction.json'

def _atomic_bytes(path, payload):
    path=inside(path)
    if payload is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    staged=inside(path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp'))
    try:
        with staged.open('wb') as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(staged,path)
    finally:
        staged.unlink(missing_ok=True)

def _encode(value):
    return None if value is None else base64.b64encode(value).decode('ascii')

def _decode(value):
    return None if value is None else base64.b64decode(value,validate=True)

def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')

def recover(folder, journal_name=JOURNAL):
    folder=inside(folder)
    journal=folder/journal_name
    if not journal.exists(): return {'recovered':False}
    record = read(journal)
    records=record['files']
    commit_point=record.get('commit_point','candidate.json')
    if commit_point not in records: raise ValueError('Invalid recovery journal')
    current=artifact_path(folder,commit_point).read_bytes()
    before=_decode(records[commit_point]['before']);after=_decode(records[commit_point]['after'])
    if current == after: direction='after'
    elif current == before: direction='before'
    else: raise ValueError('Candidate differs from both transaction versions; recovery requires adjudication')
    for relative,record in records.items():
        _atomic_bytes(artifact_path(folder,relative),_decode(record[direction]))
    journal.unlink()
    return {'recovered':True,'action':'committed' if direction=='after' else 'rolled_back'}

def commit(folder, updates, expected_candidate, commit_point="candidate.json", journal_name=JOURNAL):
    folder=inside(folder)
    recover(folder, journal_name)
    if artifact_path(folder,commit_point).read_bytes()!=expected_candidate:
        raise ValueError('Candidate changed concurrently; regenerate batch')
    records={}
    for relative,payload in updates.items():
        path=artifact_path(folder,relative)
        records[relative]={'before':_encode(path.read_bytes() if path.exists() else None),'after':_encode(payload)}
    if commit_point not in records: raise ValueError('Transaction must update commit point')
    _atomic_bytes(folder/journal_name,json_bytes({'files':records,'commit_point':commit_point}))
    try:
        for relative,payload in updates.items():
            if relative!=commit_point: _atomic_bytes(artifact_path(folder,relative),payload)
        _atomic_bytes(artifact_path(folder,commit_point),updates[commit_point])
        (folder/journal_name).unlink()
    except Exception:
        recover(folder, journal_name)
        raise


@contextmanager
def state_lock(folder, name='candidate-state.lock'):
    """OS locks release on process exit, including crashes; the marker may remain."""
    lock_path = inside(Path(folder)/name)
    key = str(lock_path)
    held = getattr(_lock_state,'held',{})
    _lock_state.held = held
    if key in held:
        held[key] += 1
        try: yield
        finally: held[key] -= 1
        return
    handle = lock_path.open('a+b')
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            if handle.seek(0,2) == 0:
                handle.write(b'0');handle.flush()
            handle.seek(0)
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc: raise ValueError('Run state is being updated; retry after the other operation') from exc
        else:
            import fcntl
            try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc: raise ValueError('Run state is being updated; retry after the other operation') from exc
        acquired = True
        held[key] = 1
        yield
    finally:
        if acquired:
            held.pop(key,None)
            if os.name == 'nt':
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        handle.close()
