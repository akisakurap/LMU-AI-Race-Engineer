"""Exercise GUI handlers without requiring a display."""
from unittest.mock import Mock

import pytest

pytest.importorskip('tkinter')
from gui import RaceEngineerApp


def test_internal_error_without_data_is_logged():
    app = Mock()
    RaceEngineerApp._handle_cycle(app, {'data': None, 'reason': 'error',
                                      'error': 'buffer decode failed'})
    assert 'buffer decode failed' in app.status_var.set.call_args.args[0]
    assert 'buffer decode failed' in app._append_log.call_args.args[0]


@pytest.mark.parametrize('value', ['nan', 'inf', '-inf', '0', '-1'])
def test_gui_rejects_invalid_interval(value):
    app = Mock()
    app.interval_var.get.return_value = value
    app.timeout_var.get.return_value = '30'
    RaceEngineerApp._on_start(app)
    app.worker.start.assert_not_called()


def test_live_telemetry_updates_without_radio_result():
    app = Mock()
    app._stopping = False
    app._last_capture_at = 0
    RaceEngineerApp._handle_result(app, {'kind': 'telemetry',
        'data': {'CapturedAt': 10, 'Fuel': 35}, 'timestamp': '12:00'})
    assert '35' in app._set_telemetry_text.call_args.args[0]


def test_radio_result_does_not_replace_newer_telemetry():
    app = Mock()
    app._last_capture_at = 20
    RaceEngineerApp._handle_cycle(app, {'data': {'CapturedAt': 10, 'Fuel': 35},
        'ok': True, 'message': 'advice'})
    app._set_telemetry_text.assert_not_called()


def test_queued_results_are_ignored_while_stopping():
    app = Mock()
    app._stopping = True
    RaceEngineerApp._handle_result(app, {'kind': 'cycle', 'ok': True, 'message': 'old'})
    app._handle_cycle.assert_not_called()
