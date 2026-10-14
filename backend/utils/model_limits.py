from utils.shutdown import OperationCancelled, shutdown_event, check_shutdown
"""Process-wide pacing and bounded retries for model calls across worker threads."""
import os
import random
import threading
import time
from functools import wraps
from openai import RateLimitError
from utils.observability import get_logger


class ModelGate:
    def __init__(self, concurrency=1, interval=1.0, retries=2, cancel_event=None):
        if concurrency < 1 or interval < 0 or retries < 0:
            raise ValueError('Model limits must be nonnegative with concurrency at least one')
        self.cancel_event = cancel_event if cancel_event is not None else threading.Event()
        self.slots = threading.BoundedSemaphore(concurrency)
        self.lock = threading.Lock()
        self.next_start = 0.0
        self.interval, self.retries = interval, retries

    def run(self, call, *args, **kwargs):
        for attempt in range(self.retries + 1):
            delay = None
            check_shutdown(self.cancel_event)
            while not self.slots.acquire(timeout=0.1):
                check_shutdown(self.cancel_event)
            try:
                check_shutdown(self.cancel_event)
                with self.lock:
                    delay_to_start = max(0.0, self.next_start - time.monotonic())
                    if delay_to_start:
                        if self.cancel_event.wait(delay_to_start):
                            raise OperationCancelled('Server shutdown requested')
                    self.next_start = time.monotonic() + self.interval
                try:
                    check_shutdown(self.cancel_event)
                    result = call(*args, **kwargs)
                    check_shutdown(self.cancel_event)
                    return result
                except RateLimitError as exc:
                    body = exc.body if isinstance(exc.body, dict) else {}
                    error = body.get('error', body)
                    code = error.get('code') if isinstance(error, dict) else None
                    if code in {'insufficient_quota', 'billing_hard_limit_reached'} or attempt == self.retries:
                        raise
                    try:
                        requested = float(exc.response.headers.get('retry-after', '0'))
                    except (TypeError, ValueError):
                        requested = 0
                    # Never retry sooner than the provider asks; long waits are surfaced.
                    if requested > 60:
                        raise
                    delay = max(requested, min(30, 2 ** (attempt + 1)) + random.uniform(0, 1))
                    with self.lock:
                        self.next_start = max(self.next_start, time.monotonic() + delay)
                    get_logger('model_limits').warning('model_rate_limited_retry', extra={'fields': {'attempt': attempt + 1, 'wait_seconds': round(delay, 2)}})
            finally:
                self.slots.release()
            # Cooldown is shared with other calls through next_start.


_gate = None
_gate_lock = threading.Lock()


def model_gate():
    global _gate
    with _gate_lock:
        if _gate is None:
            _gate = ModelGate(int(os.getenv('LLM_MAX_CONCURRENCY', '1')),
                              float(os.getenv('LLM_MIN_INTERVAL_SECONDS', '1')),
                              int(os.getenv('LLM_RATE_LIMIT_RETRIES', '2')), cancel_event=shutdown_event)
        return _gate


def limit_client(client):
    completions = getattr(getattr(client, 'chat', None), 'completions', None)
    if completions is None:
        return client
    gate = model_gate()
    for method in ('create', 'parse'):
        original = getattr(completions, method, None)
        if original is not None:
            def wrap(call):
                @wraps(call)
                def limited(*args, **kwargs):
                    return gate.run(call, *args, **kwargs)
                return limited
            setattr(completions, method, wrap(original))
    return client
