"""Durable per-step cache with independent SQL sessions for concurrent pipeline calls."""
import hashlib
import json
import threading
from functools import wraps
from db.models import IngestionCheckpoint
from utils.shutdown import check_shutdown
from utils.observability import get_logger


class CheckpointCache:
    def __init__(self, sessions, document_id, configuration, progress=None):
        self.sessions, self.configuration, self.progress = sessions, configuration, progress
        self.prefix = f'memo:{document_id}:'
        self._locks, self._guard = {}, threading.Lock()

    def run(self, stage, inputs, call, decode=None, store_if=None):
        check_shutdown()
        digest = hashlib.sha256(json.dumps([self.configuration, stage, inputs], sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        key = self.prefix + digest
        with self._guard:
            lock = self._locks.setdefault(key, threading.RLock())
        with lock:
            with self.sessions() as db:
                row = db.get(IngestionCheckpoint, key)
                cached = row.state_data if row is not None else None
            if cached is not None:
                get_logger('ingestion').debug('checkpoint_reused', extra={'fields': {'stage': stage}})
                return decode(cached['result']) if decode else cached['result']
            if self.progress:
                self.progress(stage)
            result = call()
            check_shutdown()
            if store_if is None or store_if(result):
                dump = getattr(result, 'model_dump', None)
                value = dump(mode='json') if callable(dump) else result
                with self.sessions() as db:
                    db.add(IngestionCheckpoint(key=key, state_data={'stage': stage, 'result': value}))
                    db.commit()
            return result

    def bind(self, target, name, key_for, decode=None, store_if=None):
        original = getattr(target, name)
        @wraps(original)
        def cached(*args, **kwargs):
            return self.run(name, key_for(*args, **kwargs), lambda: original(*args, **kwargs), decode, store_if)
        setattr(target, name, cached)

    def clear(self):
        with self.sessions() as db:
            db.query(IngestionCheckpoint).filter(IngestionCheckpoint.key.like(self.prefix + '%')).delete(synchronize_session=False)
            db.commit()
