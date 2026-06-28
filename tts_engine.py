"""
tts_engine.py
=============
Local TTS engine for LMU Race Engineer.

- Japanese : Voicevox (localhost:50021 HTTP API)
- English  : Kokoro-TTS (Python library, offline)

Usage:
    from tts_engine import speak
    speak("タイヤ温度が高いです。ペースを落としてください。", "ja")
    speak("Tyre temps are high. Back off the pace.", "en")
"""

import io
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
VOICEVOX_URL        = 'http://localhost:50021'
VOICEVOX_SPEAKER_ID = 3      # 3 = ずんだもん
KOKORO_VOICE        = 'af_heart'
KOKORO_SPEED        = 1.1    # 少し速めに読む

# ============================================================
# Lazy-initialized engine instances
# ============================================================
_kokoro_pipeline = None
_kokoro_failed   = False


def _play_wav_bytes(wav_bytes: bytes) -> None:
    """Play raw wav bytes via sounddevice."""
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    buf = io.BytesIO(wav_bytes)
    data, samplerate = sf.read(buf, dtype='float32')
    sd.play(data, samplerate)
    sd.wait()


def _speak_voicevox(text: str) -> None:
    import requests

    params = {'text': text, 'speaker': VOICEVOX_SPEAKER_ID}

    try:
        query_res = requests.post(
            f'{VOICEVOX_URL}/audio_query',
            params=params,
            timeout=5,
        )
        query_res.raise_for_status()
    except requests.exceptions.ConnectionError:
        logger.warning('[TTS] Voicevox not running — skipping speech')
        return
    except Exception as e:
        logger.warning('[TTS] Voicevox audio_query error: %s', e)
        return

    query_data = query_res.json()
    query_data['speedScale'] = KOKORO_SPEED  # reuse speed constant

    try:
        synth_res = requests.post(
            f'{VOICEVOX_URL}/synthesis',
            params={'speaker': VOICEVOX_SPEAKER_ID},
            json=query_data,
            timeout=15,
        )
        synth_res.raise_for_status()
    except Exception as e:
        logger.warning('[TTS] Voicevox synthesis error: %s', e)
        return

    _play_wav_bytes(synth_res.content)


def _get_kokoro_pipeline():
    global _kokoro_pipeline, _kokoro_failed
    if _kokoro_failed:
        return None
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
        _kokoro_pipeline = KPipeline(lang_code='a')  # 'a' = American English
        logger.info('[TTS] Kokoro-TTS initialized')
    except Exception as e:
        logger.warning('[TTS] Kokoro-TTS init failed: %s — English TTS disabled', e)
        _kokoro_failed = True
        return None
    return _kokoro_pipeline


def _speak_kokoro(text: str) -> None:
    import numpy as np
    import sounddevice as sd

    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        return

    try:
        audio_chunks = []
        for _, _, audio in pipeline(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED):
            if audio is not None:
                audio_chunks.append(audio)
        if not audio_chunks:
            return
        combined = np.concatenate(audio_chunks)
        sd.play(combined, samplerate=24000)
        sd.wait()
    except Exception as e:
        logger.warning('[TTS] Kokoro speak error: %s', e)


def speak(text: str, language: str) -> None:
    """Read aloud *text* using the engine matching *language*.

    Falls back silently on any error so the main loop is never interrupted.
    """
    if not text or not text.strip():
        return
    try:
        if language == 'ja':
            _speak_voicevox(text)
        else:
            _speak_kokoro(text)
    except Exception as e:
        logger.warning('[TTS] Unexpected error: %s', e)
