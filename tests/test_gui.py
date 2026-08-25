"""tests/test_gui.py

Covers the Tkinter glue in gui.py directly (validation, rendering of
worker results into widgets). The polling/threading logic itself lives in
engineer_worker.py and is tested without a display in
test_engineer_worker.py.

Needs a real Tk display. Skipped entirely (not failed) wherever tkinter
isn't installed or no display is available — e.g. a minimal CI container
with no Xvfb — since that's an environment limitation, not a code defect.
"""

import pytest

tk = pytest.importorskip('tkinter')

import race_engineer as engine  # noqa: E402


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f'no Tk display available: {e}')
    root.withdraw()
    return root


@pytest.fixture
def app():
    import gui  # imported lazily so the importorskip above runs first

    root = _make_root()
    application = gui.RaceEngineerApp(root)
    yield application
    application.on_close()


@pytest.fixture(autouse=True)
def restore_engine_config():
    """_on_start mutates race_engineer's module-level config; restore it
    so these tests can't leak settings into ones that run after them."""
    keys = ['LANGUAGE', 'PERSONA', 'MODEL_NAME', 'LM_STUDIO_URL', 'INTERVAL_SEC', 'LLM_TIMEOUT']
    original = {k: getattr(engine, k) for k in keys}
    yield
    for k, v in original.items():
        setattr(engine, k, v)


def test_invalid_interval_shows_error_and_does_not_start(app):
    app.interval_var.set('not-a-number')
    app._on_start()

    assert '正の数' in app.status_var.get()
    assert not app.worker.is_running()
    assert str(app.start_btn['state']) == 'normal'


def test_valid_start_applies_config_and_toggles_buttons(app):
    app.language_var.set('en')
    app.persona_var.set('girl')
    app.model_var.set('my-test-model')
    app.interval_var.set('5')
    app.timeout_var.set('20')

    app._on_start()

    assert engine.LANGUAGE == 'en'
    assert engine.PERSONA == 'girl'
    assert engine.MODEL_NAME == 'my-test-model'
    assert engine.INTERVAL_SEC == 5.0
    assert engine.LLM_TIMEOUT == 20.0
    assert str(app.start_btn['state']) == 'disabled'
    assert str(app.stop_btn['state']) == 'normal'

    app._on_stop()


def test_handle_cycle_no_data_updates_status_only(app):
    app._handle_cycle({'timestamp': '12:00:00', 'data': None})
    assert 'LMU未起動' in app.status_var.get()
    assert app.log_text.get('1.0', 'end').strip() == ''


def test_handle_cycle_ok_updates_telemetry_and_log(app):
    data = {'SpeedKmh': 250.0, 'Gear': 6, 'TrackName': 'Le Mans'}
    app._handle_cycle({'timestamp': '12:00:01', 'data': data,
                        'ok': True, 'message': 'ペース良好です。'})

    assert 'Le Mans' in app.telemetry_text.get('1.0', 'end')
    assert 'ペース良好です。' in app.log_text.get('1.0', 'end')


def test_handle_cycle_error_appends_warning_tagged_log(app):
    data = {'SpeedKmh': 250.0}
    app._handle_cycle({'timestamp': '12:00:02', 'data': data,
                        'ok': False, 'error': 'LM Studio not available'})

    log_content = app.log_text.get('1.0', 'end')
    assert 'LM Studio not available' in log_content
    assert '警告' in app.status_var.get()


def test_handle_result_stopped_resets_ui(app):
    app._on_start()
    assert str(app.start_btn['state']) == 'disabled'

    app._handle_result({'kind': 'stopped'})

    assert str(app.start_btn['state']) == 'normal'
    assert str(app.stop_btn['state']) == 'disabled'
    assert '停止' in app.status_var.get()
