"""tests/test_engineer_worker.py

EngineerWorker has no Tkinter dependency, so it's tested directly here
(fast, no display needed). gui.py's own tests (test_gui.py) only cover the
thin Tkinter glue on top of this.
"""

import queue
from unittest.mock import patch

import pytest

import engineer_worker
import race_engineer as engine
from engineer_worker import EngineerWorker


@pytest.fixture(autouse=True)
def fast_interval():
    """Keeps these tests fast without waiting out a real polling interval."""
    original = engine.INTERVAL_SEC
    engine.INTERVAL_SEC = 0.05
    yield
    engine.INTERVAL_SEC = original


class _FakeReader:
    """Stands in for RF2Reader so tests never touch real shared memory."""
    def read_snapshot(self):
        return {}


def _drain_one(q: queue.Queue, timeout=2):
    item = q.get(timeout=timeout)
    return item


def test_start_emits_started_then_stop_emits_stopped():
    q = queue.Queue()
    worker = EngineerWorker(q)

    with patch('engineer_worker.RF2Reader', _FakeReader):
        worker.start(enable_tts=False)
        assert _drain_one(q) == {'kind': 'started'}
        assert worker.is_running()

        worker.stop()
        # Drain any 'no_data' cycle items until we hit the final 'stopped'.
        for _ in range(50):
            item = _drain_one(q)
            if item.get('kind') == 'stopped':
                break
        else:
            pytest.fail('worker never emitted a stopped message')

    assert not worker.is_running()


def test_cycle_results_carry_kind_and_timestamp():
    q = queue.Queue()
    worker = EngineerWorker(q)
    canned = {'ok': True, 'data': {'SpeedKmh': 200.0}, 'message': 'ok radio call',
              'error': None, 'reason': None}

    with patch('engineer_worker.RF2Reader', _FakeReader), \
         patch('engineer_worker.engine.run_one_cycle', return_value=canned):
        worker.start(enable_tts=False)
        assert _drain_one(q) == {'kind': 'started'}

        item = _drain_one(q)
        worker.stop()

    assert item['kind'] == 'cycle'
    assert 'timestamp' in item and item['timestamp']
    assert item['ok'] is True
    assert item['message'] == 'ok radio call'


def test_speak_async_called_when_ok_and_tts_enabled():
    q = queue.Queue()
    worker = EngineerWorker(q)
    canned = {'ok': True, 'data': {}, 'message': 'speak this', 'error': None, 'reason': None}

    with patch('engineer_worker.RF2Reader', _FakeReader), \
         patch('engineer_worker.engine.run_one_cycle', return_value=canned), \
         patch('engineer_worker.engine.speak_async') as mock_speak:
        worker.start(enable_tts=True)
        _drain_one(q)  # started
        _drain_one(q)  # cycle
        worker.stop()
        for _ in range(50):
            if q.get(timeout=2).get('kind') == 'stopped':
                break

    mock_speak.assert_called_with('speak this', engine.LANGUAGE)


def test_speak_async_not_called_when_tts_disabled():
    q = queue.Queue()
    worker = EngineerWorker(q)
    canned = {'ok': True, 'data': {}, 'message': 'speak this', 'error': None, 'reason': None}

    with patch('engineer_worker.RF2Reader', _FakeReader), \
         patch('engineer_worker.engine.run_one_cycle', return_value=canned), \
         patch('engineer_worker.engine.speak_async') as mock_speak:
        worker.start(enable_tts=False)
        _drain_one(q)  # started
        _drain_one(q)  # cycle
        worker.stop()
        for _ in range(50):
            if q.get(timeout=2).get('kind') == 'stopped':
                break

    mock_speak.assert_not_called()


def test_run_one_cycle_exception_becomes_error_result_without_killing_worker():
    q = queue.Queue()
    worker = EngineerWorker(q)

    with patch('engineer_worker.RF2Reader', _FakeReader), \
         patch('engineer_worker.engine.run_one_cycle', side_effect=RuntimeError('boom')):
        worker.start(enable_tts=False)
        _drain_one(q)  # started

        first = _drain_one(q)
        second = _drain_one(q)  # a second cycle proves the thread kept going
        worker.stop()
        for _ in range(50):
            if q.get(timeout=2).get('kind') == 'stopped':
                break

    for item in (first, second):
        assert item['kind'] == 'cycle'
        assert item['ok'] is False
        assert item['reason'] == 'error'
        assert item['error'] == 'boom'
