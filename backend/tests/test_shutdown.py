import signal
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from utils.model_limits import ModelGate
from utils.shutdown import OperationCancelled, shutdown_event, shutdown_signals
from pipeline.tree_builder import TreeBuilder
from core.config import Settings
from pathlib import Path


class ShutdownTests(unittest.TestCase):
    def tearDown(self):
        shutdown_event.clear()

    def test_signal_sets_cancel_before_forwarding_and_restores_handlers(self):
        shutdown_event.clear()
        original = Mock(side_effect=lambda *args: self.assertTrue(shutdown_event.is_set()))
        handlers = {signal.SIGINT: original, signal.SIGTERM: original}
        def install(signum, handler):
            handlers[signum] = handler
        with patch('utils.shutdown.signal.getsignal', side_effect=lambda signum: handlers[signum]), patch('utils.shutdown.signal.signal', side_effect=install):
            with shutdown_signals():
                handlers[signal.SIGINT](signal.SIGINT, None)
                original.assert_called_once_with(signal.SIGINT, None)
            self.assertIs(handlers[signal.SIGINT], original)
            self.assertIs(handlers[signal.SIGTERM], original)

    def test_shutdown_interrupts_long_cooldown_without_calling_provider(self):
        event = threading.Event()
        entered = threading.Event()
        gate = ModelGate(cancel_event=event)
        gate.next_start = time.monotonic() + 60
        provider = Mock()
        original_wait = event.wait
        def observed_wait(timeout):
            entered.set()
            return original_wait(timeout)
        with patch.object(event, 'wait', side_effect=observed_wait), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(gate.run, provider)
            self.assertTrue(entered.wait(1))
            event.set()
            with self.assertRaises(OperationCancelled):
                future.result(timeout=1)
        provider.assert_not_called()
        self.assertTrue(gate.slots.acquire(blocking=False))
        gate.slots.release()

    def test_shutdown_interrupts_wait_for_a_busy_slot(self):
        event = threading.Event()
        gate = ModelGate(cancel_event=event)
        gate.slots.acquire()
        provider = Mock()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(gate.run, provider)
                event.set()
                with self.assertRaises(OperationCancelled):
                    future.result(timeout=1)
        finally:
            gate.slots.release()
        provider.assert_not_called()

    def test_cancelled_inflight_result_is_not_returned(self):
        event = threading.Event()
        def provider():
            event.set()
            return 'result'
        with self.assertRaises(OperationCancelled):
            ModelGate(cancel_event=event).run(provider)

    def test_recursive_split_does_not_schedule_more_calls(self):
        builder = TreeBuilder('test', client=object(), settings=Settings('sqlite://', Path('.'), '', None, ''))
        builder._ask_llm_to_split = Mock()
        shutdown_event.set()
        with self.assertRaises(OperationCancelled):
            builder.build_branch_recursive('Source text.', 1)
        builder._ask_llm_to_split.assert_not_called()
