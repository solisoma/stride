import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
import httpx
from openai import RateLimitError
from utils.model_limits import ModelGate


def limited(code='rate_limit_exceeded', retry_after='3'):
    response = httpx.Response(429, headers={'retry-after': retry_after}, request=httpx.Request('POST', 'https://example.test'))
    return RateLimitError('simulated', response=response, body={'code': code})


class ModelLimitTests(unittest.TestCase):
    def test_retry_respects_provider_delay(self):
        gate = ModelGate(interval=0)
        call = Mock(side_effect=[limited(), 'done'])
        with patch.object(gate.cancel_event, 'wait', return_value=False) as sleep, patch('utils.model_limits.random.uniform', return_value=0):
            self.assertEqual(gate.run(call), 'done')
        self.assertEqual(call.call_count, 2)
        self.assertTrue(any(args.args[0] >= 2.9 for args in sleep.call_args_list))

    def test_quota_and_long_delays_do_not_retry(self):
        for error in (limited('insufficient_quota'), limited(retry_after='120')):
            call = Mock(side_effect=error)
            with self.assertRaises(RateLimitError):
                ModelGate(interval=0).run(call)
            self.assertEqual(call.call_count, 1)

    def test_retry_count_is_bounded(self):
        call = Mock(side_effect=limited(retry_after='0'))
        gate = ModelGate(interval=0, retries=1)
        with patch.object(gate.cancel_event, 'wait', return_value=False), self.assertRaises(RateLimitError):
            gate.run(call)
        self.assertEqual(call.call_count, 2)

    def test_shared_gate_serializes_threads(self):
        gate = ModelGate(concurrency=1, interval=0)
        entered = threading.Event()
        release = threading.Event()
        calls = []
        def first():
            calls.append('first')
            entered.set()
            self.assertTrue(release.wait(5))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_call = pool.submit(gate.run, first)
            self.assertTrue(entered.wait(5))
            second_call = pool.submit(gate.run, lambda: calls.append('second'))
            self.assertEqual(calls, ['first'])
            release.set()
            first_call.result(timeout=5)
            second_call.result(timeout=5)
        self.assertEqual(calls, ['first', 'second'])
