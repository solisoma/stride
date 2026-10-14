"""Cooperative shutdown, signalled before Uvicorn drains active requests."""
import signal
import threading
from contextlib import contextmanager

shutdown_event = threading.Event()


class OperationCancelled(RuntimeError):
    pass


def check_shutdown(event=None):
    if (event if event is not None else shutdown_event).is_set():
        raise OperationCancelled('Server shutdown requested')


@contextmanager
def shutdown_signals():
    # TestClient runs lifespan on a worker thread where signal registration is invalid.
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    saved = []
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous = signal.getsignal(signum)
            def make_handler(original):
                def handle(received, frame):
                    shutdown_event.set()
                    if callable(original):
                        original(received, frame)
                    elif original != signal.SIG_IGN:
                        raise SystemExit(0)
                return handle
            handler = make_handler(previous)
            signal.signal(signum, handler)
            saved.append((signum, previous, handler))
        yield
    finally:
        shutdown_event.set()
        for signum, previous, handler in saved:
            if signal.getsignal(signum) is handler:
                signal.signal(signum, previous)
