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

SLEEP_STEP_SEC = 0.25  # granularity for reacting to stop() during the wait


class EngineerWorker:
    """Runs the polling loop on a background thread and publishes results
    to a queue. Consumers must never touch UI state directly from within
    a queued item's handling except on their own (e.g. UI) thread."""

    def __init__(self, result_queue: queue.Queue):
        self._queue = result_queue
        self._stop_event = threading.Event()
        self._thread = None

    def start(self, enable_tts: bool) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(enable_tts,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, enable_tts: bool) -> None:
        reader = RF2Reader()
        self._queue.put({'kind': 'started'})
        try:
            while not self._stop_event.is_set():
                if self._wait_for_next_cycle():
                    break
                try:
                    result = engine.run_one_cycle(reader)
                except Exception as e:
                    # Defensive: an unexpected bug here must not silently
                    # kill the background thread and leave the UI stuck
                    # showing "running" forever with no further updates.
                    result = {'ok': False, 'data': None, 'message': None,
                              'error': str(e), 'reason': 'error'}

                result['kind'] = 'cycle'
                result['timestamp'] = datetime.now().strftime('%H:%M:%S')
                self._queue.put(result)

                if result.get('ok') and enable_tts:
                    engine.speak_async(result['message'], engine.LANGUAGE)
        finally:
            self._queue.put({'kind': 'stopped'})

    def _wait_for_next_cycle(self) -> bool:
        """Sleeps in small steps so stop() takes effect within
        SLEEP_STEP_SEC instead of waiting out the full interval. Returns
        True if a stop was requested during the wait."""
        slept = 0.0
        while slept < engine.INTERVAL_SEC:
            if self._stop_event.is_set():
                return True
            time.sleep(min(SLEEP_STEP_SEC, engine.INTERVAL_SEC - slept))
            slept += SLEEP_STEP_SEC
        return self._stop_event.is_set()
