"""Run with: uv run python -m scripts.ingestion_worker"""
import os
from contextlib import contextmanager
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from db.session import create_database
from api.services.ingestion_queue import connect, declare, publish_pending, after_processing, parse_message, QUEUE
from utils.observability import get_logger
from core.config import Settings
from api.services.ingestion_jobs import initialize_worker, process_next
from utils.observability import configure_logging, close_logging
from utils.shutdown import shutdown_event, shutdown_signals


@contextmanager
def worker_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('An ingestion worker is already running for this storage directory') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def dispatch(settings, sessions):
    while not shutdown_event.is_set():
        try:
            publish_pending(settings, sessions)
        except Exception:
            get_logger('queue').warning('rabbitmq_publish_unavailable')
        shutdown_event.wait(2)


def consume_jobs(settings, sessions):
    # The connection stays on this thread; lengthy ingestion runs on another thread.
    # This keeps broker heartbeats alive throughout recursive model processing.
    with ThreadPoolExecutor(max_workers=1) as executor:
        while not shutdown_event.is_set():
            connection = None
            try:
                connection = connect(settings)
                channel = connection.channel()
                declare(channel)
                channel.basic_qos(prefetch_count=1)

                def handle(ch, method, properties, body):
                    try:
                        document_id = parse_message(body)
                    except (ValueError, TypeError):
                        get_logger('queue').warning('invalid_ingestion_message')
                        ch.basic_nack(method.delivery_tag, requeue=False)
                        return

                    def work():
                        try:
                            process_next(settings, document_id=document_id, auto_retry=True)
                            return after_processing(settings, sessions, document_id)
                        except Exception:
                            get_logger('queue').error('ingestion_delivery_interrupted')
                            shutdown_event.wait(5)
                            return False

                    future = executor.submit(work)
                    # Capture this delivery's connection; never use a later reconnect.
                    def completed(result, broker=connection, consumer=ch, tag=method.delivery_tag):
                        def acknowledge():
                            if not consumer.is_open:
                                return
                            if result.result() and not shutdown_event.is_set():
                                consumer.basic_ack(tag)
                            else:
                                consumer.basic_nack(tag, requeue=True)
                        if broker is not None and broker.is_open:
                            broker.add_callback_threadsafe(acknowledge)
                    future.add_done_callback(completed)

                channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
                while connection.is_open and not shutdown_event.is_set():
                    connection.process_data_events(time_limit=1)
            except Exception:
                get_logger('queue').warning('rabbitmq_consumer_unavailable')
                shutdown_event.wait(5)
            finally:
                if connection is not None and connection.is_open:
                    connection.close()


def main():
    settings = Settings.load()
    shutdown_event.clear()
    configure_logging(settings.log_dir or settings.storage.parent / 'logs', settings.log_level)
    engine, sessions = create_database(settings.database_url)
    publisher = None
    try:
        with worker_lock(settings.storage.resolve().parent / '.ingestion-worker.lock'), shutdown_signals():
            initialize_worker(settings)
            publisher = threading.Thread(target=dispatch, args=(settings, sessions), daemon=True)
            publisher.start()
            consume_jobs(settings, sessions)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_event.set()
        if publisher is not None:
            publisher.join(timeout=15)
        engine.dispose()
        close_logging()


if __name__ == '__main__':
    main()
