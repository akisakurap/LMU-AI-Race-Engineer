"""
engineer_worker.py
===================
Background polling loop for the race engineer, decoupled from any UI.

`EngineerWorker` runs `race_engineer.run_one_cycle()` on its own thread and
publishes each result to a `queue.Queue`, so a UI (gui.py's Tkinter
dashboard today, potentially something else later) only ever has to drain
a queue on its own thread instead of touching widgets from a background
thread. It has no Tkinter dependency, so it can be tested and reused
without a display.
"""

import queue
import threading
import time
from datetime import datetime

import race_engineer as engine
from rf2_reader import RF2Reader
from tts_engine import cancel_speech
from telemetry_history import TelemetryHistory

SLEEP_STEP_SEC = 0.25  # granularity for reacting to stop() during the wait
SAMPLE_INTERVAL_SEC = 0.5


class _LatestSnapshot:
    """A sampling thread owns the real reader; inference consumes a copy."""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
        self.error = None

    def read_snapshot(self):
        with self.lock:
            if self.error is not None:
                raise RuntimeError(self.error)
            return dict(self.data)


class EngineerWorker:
    """Runs the polling loop on a background thread and publishes results
    to a queue. Consumers must never touch UI state directly from within
    a queued item's handling except on their own (e.g. UI) thread."""

    def __init__(self, result_queue: queue.Queue, engine_api=engine):
        self._queue = result_queue
        self.engine = engine_api
        self._stop_event = threading.Event()
        self._thread = None
        self._publish_lock = threading.Lock()

    def start(self, enable_tts: bool) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(enable_tts,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._publish_lock:
            self._stop_event.set()
            cancel_speech()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, enable_tts: bool) -> None:
        reader = RF2Reader()
        latest = _LatestSnapshot()
        self._queue.put({'kind': 'started'})
        sampler = threading.Thread(target=self._sample, args=(reader, latest), daemon=True)
        sampler.start()
        try:
            while not self._stop_event.is_set():
                if self._wait_for_next_cycle():
                    break
                try:
                    result = self.engine.run_one_cycle(latest)
                except Exception as e:
                    # Defensive: an unexpected bug here must not silently
                    # kill the background thread and leave the UI stuck
                    # showing "running" forever with no further updates.
                    result = {'ok': False, 'data': None, 'message': None,
                              'error': str(e), 'reason': 'error'}

                with self._publish_lock:
                    if self._stop_event.is_set():
                        break
                    result['kind'] = 'cycle'
                    result['timestamp'] = datetime.now().strftime('%H:%M:%S')
                    if result.get('ok') and enable_tts:
                        kwargs = ({'expires_at': result['expires_at']}
                                  if 'expires_at' in result else {})
                        self.engine.speak_async(result['message'], self.engine.LANGUAGE, **kwargs)
                    self._queue.put(result)
        finally:
            self._stop_event.set()
            sampler.join()
            self._queue.put({'kind': 'stopped'})

    def _sample(self, reader, latest):
        history = TelemetryHistory()
        while not self._stop_event.is_set():
            error = None
            try:
                data = reader.read_snapshot()
                data = history.update(data, time.monotonic())
                if data:
                    data = dict(data, CapturedAt=time.monotonic())
            except Exception as e:
                data, error = {}, str(e)
            with latest.lock:
                latest.data, latest.error = data, error
            with self._publish_lock:
                if not self._stop_event.is_set() and data:
                    self._queue.put({'kind': 'telemetry', 'data': data,
                                     'timestamp': datetime.now().strftime('%H:%M:%S')})
            if self._stop_event.wait(SAMPLE_INTERVAL_SEC):
                break

    def _wait_for_next_cycle(self) -> bool:
        """Sleeps in small steps so stop() takes effect within
        SLEEP_STEP_SEC instead of waiting out the full interval. Returns
        True if a stop was requested during the wait."""
        return self._stop_event.wait(self.engine.INTERVAL_SEC)
