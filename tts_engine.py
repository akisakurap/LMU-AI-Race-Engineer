"""
tts_engine.py
=============
Local TTS engine for LMU Race Engineer.

- Japanese : Voicevox (localhost:50021 HTTP API)
- English  : Kokoro-TTS (Python library, offline)

Usage:
    from tts_engine import speak, speak_async
    speak("タイヤ温度が高いです。ペースを落としてください。", "ja")        # blocking
    speak_async("Tyre temps are high. Back off the pace.", "en")  # non-blocking

`speak_async` hands the text to a background worker thread and returns
immediately, so a caller like the telemetry polling loop never stalls for
the duration of speech synthesis + playback. Only the most recent message
is kept queued — if playback is still catching up when a newer message
arrives, the stale one is dropped in favor of the latest telemetry-driven
instruction, and messages are always spoken one at a time (never overlapped).
"""

import io
import logging
import queue
import threading
import sys
import time

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


def _play_audio(data, samplerate):
    import sounddevice as sd
    # Cancellation and playback start are atomic: synthesis finishing after
    # Stop must not restart the audio device.
    with _speech_lock:
        if not _speech_is_current():
            return
        sd.play(data, samplerate)
    sd.wait()


def _play_wav_bytes(wav_bytes: bytes) -> None:
    """Play raw wav bytes via sounddevice."""
    import soundfile as sf

    buf = io.BytesIO(wav_bytes)
    data, samplerate = sf.read(buf, dtype='float32')
    _play_audio(data, samplerate)


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
        _play_audio(combined, 24000)
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


# ============================================================
# Non-blocking playback (background worker thread)
# ============================================================
_speech_queue = queue.Queue(maxsize=1)
_worker_thread = None
_worker_lock = threading.Lock()
_speech_lock = threading.Lock()
_generation = 0
_context = threading.local()


def _speech_is_current():
    generation = getattr(_context, 'generation', None)
    expires_at = getattr(_context, 'expires_at', None)
    return ((generation is None or generation == _generation)
            and (expires_at is None or time.monotonic() < expires_at))


def cancel_speech() -> None:
    """Discard queued/synthesizing speech and stop current playback."""
    global _generation
    with _speech_lock:
        _generation += 1
        while True:
            try:
                _speech_queue.get_nowait()
            except queue.Empty:
                break
        sd = sys.modules.get('sounddevice')
        if sd is not None:
            try:
                sd.stop()
            except Exception as e:
                logger.warning('[TTS] Audio stop failed: %s', e)


def _worker_loop() -> None:
    while True:
        generation, expires_at, language, text = _speech_queue.get()
        _context.generation = generation
        _context.expires_at = expires_at
        try:
            if _speech_is_current():
                speak(text, language)
        finally:
            _context.generation = None
            _context.expires_at = None


def _ensure_worker_started() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
            _worker_thread.start()


def speak_async(text: str, language: str, *, expires_at=None) -> None:
    """Non-blocking version of `speak()`.

    Queues *text* for the background worker thread and returns immediately.
    If the worker is still speaking a previous message, the newest message
    replaces any not-yet-started one in the queue (capacity 1) rather than
    piling up a backlog of stale radio calls.
    """
    if not text or not text.strip():
        return
    _ensure_worker_started()
    with _speech_lock:
        item = (_generation, expires_at, language, text)
        try:
            _speech_queue.put_nowait(item)
        except queue.Full:
            try:
                _speech_queue.get_nowait()
            except queue.Empty:
                pass
            _speech_queue.put_nowait(item)
