"""tests/test_tts_engine.py

The audio backends (Voicevox HTTP API, Kokoro-TTS, sounddevice playback)
are not available in a plain test environment, so these tests focus on the
behaviour that matters most: TTS must never crash the race engineer loop,
and `speak()` must dispatch to the right engine for each language.
"""

from unittest.mock import MagicMock, patch

import requests

from tts_engine import _speak_voicevox, speak


def test_speak_empty_text_is_noop():
    with patch('tts_engine._speak_voicevox') as voicevox, \
         patch('tts_engine._speak_kokoro') as kokoro:
        speak('', 'ja')
        speak('   ', 'en')
    voicevox.assert_not_called()
    kokoro.assert_not_called()


def test_speak_ja_dispatches_to_voicevox():
    with patch('tts_engine._speak_voicevox') as voicevox, \
         patch('tts_engine._speak_kokoro') as kokoro:
        speak('タイヤ温度に注意', 'ja')
    voicevox.assert_called_once_with('タイヤ温度に注意')
    kokoro.assert_not_called()


def test_speak_en_dispatches_to_kokoro():
    with patch('tts_engine._speak_voicevox') as voicevox, \
         patch('tts_engine._speak_kokoro') as kokoro:
        speak('watch your tyre temps', 'en')
    kokoro.assert_called_once_with('watch your tyre temps')
    voicevox.assert_not_called()


def test_speak_never_raises_when_engine_errors():
    with patch('tts_engine._speak_voicevox', side_effect=RuntimeError('boom')):
        speak('hello', 'ja')  # must not raise — a TTS failure can't stop the loop


def test_speak_never_raises_when_optional_dependency_missing():
    # Simulates running with kokoro/sounddevice not installed, e.g. a
    # Japanese-only setup that skipped the English TTS extras.
    with patch('tts_engine._speak_kokoro',
               side_effect=ModuleNotFoundError("No module named 'kokoro'")):
        speak('hello', 'en')  # must not raise


def test_speak_voicevox_connection_error_is_swallowed():
    with patch('requests.post', side_effect=requests.exceptions.ConnectionError()):
        _speak_voicevox('hello')  # should log a warning and return, not raise


def test_speak_voicevox_bad_response_is_swallowed():
    bad_response = MagicMock()
    bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError('500')
    with patch('requests.post', return_value=bad_response):
        _speak_voicevox('hello')  # should log a warning and return, not raise
