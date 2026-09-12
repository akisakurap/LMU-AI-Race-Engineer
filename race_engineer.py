"""
race_engineer.py
================
Live race engineer assistant for Le Mans Ultimate via rF2 SharedMemory + LM Studio.

Configuration variables are at the top of this file. This module also
provides run_one_cycle(), which gui.py (via engineer_worker.py) reuses to
drive the same logic from a desktop window instead of the terminal.
"""

import argparse
import math
import queue
import sys
import time
from datetime import datetime

from openai import APIConnectionError, APITimeoutError, OpenAI

from rf2_reader import RF2Reader
from tts_engine import speak_async

# ============================================================
# Configuration
#
# Defaults below can be overridden per-run with CLI flags, e.g.:
#   python race_engineer.py --language en --persona girl --no-tts
# Run `python race_engineer.py --help` for the full list.
# ============================================================
LANGUAGE     = 'ja'
PERSONA      = 'default'
MODEL_NAME   = 'google/gemma-4-e2b'
INTERVAL_SEC = 10
LLM_TIMEOUT  = 30
LM_STUDIO_URL = 'http://localhost:1234/v1'
ENABLE_TTS   = True
MAX_DATA_AGE_SEC = 20.0


def positive_seconds(value) -> float:
    """Shared CLI/GUI validation; NaN and infinity are not durations."""
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError('must be a finite positive number')
    return number

# ============================================================
# System prompts
# ============================================================
SYSTEM_PROMPTS = {
    'default': {
        'ja': (
            'あなたはプロのモータースポーツ・レースエンジニアです。'
            'カテゴリーを問わず、ドライバーの冷静な相棒として的確なサポートを行います。'
            '以下の走行データから、短く簡潔に、状況報告や次に取るべきアクションの無線指示を'
            '【日本語で】出してください。実際のレース無線のようにお願いします。'
        ),
        'en': (
            'You are a professional motorsport race engineer. '
            'Based on the following telemetry data, give short, concise, and realistic '
            'radio instructions to the driver in English.'
        ),
    },
    'girl': {
        'ja': (
            'あなたは明るくてかわいい女の子のレースエンジニアです。名前は「アイ」です。'
            'ドライバーのことが大好きで、いつも全力で応援しています。'
            '走行データを見て、タメ口でフレンドリーに、でもちゃんと的確に無線指示を出してください。'
            '「〜だよ！」「〜だね！」「頑張って！」など、かわいい話し方で。'
            '長くなりすぎず、2〜3文でまとめてね！'
        ),
        'en': (
            'You are a cheerful and cute girl race engineer named "Ai". '
            'You love the driver and always cheer them on with energy. '
            'Based on the telemetry data, give friendly but accurate radio instructions. '
            'Use an upbeat, casual tone — "You got this!", "Awesome job!", etc. '
            'Keep it short, 2-3 sentences max!'
        ),
    },
}


def _g(data: dict, key: str, default: str = 'N/A') -> str:
    val = data.get(key)
    if val is None:
        return default
    return str(val)


def _tyre_str(data: dict, key: str, labels=('FL', 'FR', 'RL', 'RR')) -> str:
    vals = data.get(key)
    if not vals or len(vals) < 4:
        return 'N/A'
    return ' / '.join(f'{l} {v}' for l, v in zip(labels, vals))


def _session_name(session_id: int, language: str = 'ja') -> str:
    if 10 <= session_id <= 13:
        return 'レース' if language == 'ja' else 'Race'
    if 5 <= session_id <= 8:
        return '予選' if language == 'ja' else 'Qualifying'
    if 1 <= session_id <= 4:
        return '練習' if language == 'ja' else 'Practice'
    return 'テスト' if language == 'ja' else 'Test'


def build_prompt(data: dict, language: str) -> str:
    g = lambda key, default='N/A': _g(data, key, default)

    session_label = _session_name(int(float(g('Session', '0'))), language)

    time_rem = data.get('TimeRemaining')
    laps_rem = data.get('LapsRemaining')
    remaining_str = ''
    if time_rem is not None:
        m, s = divmod(int(time_rem), 60)
        remaining_str += f'{m}:{s:02d}'
    if laps_rem is not None:
        remaining_str += (f' / 残り{laps_rem}周' if language == 'ja'
                          else f' / {laps_rem} laps')
    if not remaining_str:
        remaining_str = 'N/A'

    damage_parts = []
    dmg = data.get('DamageSummary')
    if dmg and dmg not in ('なし', 'none', '', 'None'):
        damage_parts.append(f'車体:{dmg}' if language == 'ja' else f'Body:{dmg}')
    if data.get('PartDetached'):
        damage_parts.append('パーツ脱落' if language == 'ja' else 'Part detached')
    if data.get('Overheating'):
        damage_parts.append('過熱警告' if language == 'ja' else 'Overheat warning')
    damage_str = ' / '.join(damage_parts) if damage_parts else ('なし' if language == 'ja' else 'none')

    if language == 'ja':
        lines = [
            f"コース: {g('TrackName')} | セッション: {session_label} | クラス: {g('VehicleClass')}",
            f"速度: {g('SpeedKmh')} km/h | ギア: {g('Gear')} | RPM: {g('EngineRPM')}",
            f"順位: P{g('Position')}/{g('NumVehicles')} | ラップ: {g('TotalLaps')} | 残り: {remaining_str}",
            f"ギャップ: 前 {g('GapToFront')}s / 後 {g('GapToBehind')}s / リーダー {g('GapToLeader')}s",
            f"燃料: {g('Fuel')}L / {g('FuelCapacity')}L",
            f"タイヤ摩耗: {_tyre_str(data, 'TyreWear')}%",
            f"タイヤ温度: {_tyre_str(data, 'TyreTemp')}°C",
            f"タイヤ空気圧: {_tyre_str(data, 'TyrePressure')}kPa",
            f"タイヤ種別: F {g('FrontCompound')} / R {g('RearCompound')}",
            f"水温: {g('WaterTemp')}°C | 油温: {g('OilTemp')}°C | ERS: {g('ERSBattery')}% | ERS温度: {g('ERSMotorTemp')}°C",
            f"前ラップ: {g('LastLapTime')}s | ベスト: {g('BestLapTime')}s | 推定: {g('EstLapTime')}s",
            f"セクター(現在): S1 {g('CurSector1')}s / S2 {g('CurSector2')}s",
            f"天候: 雨 {g('Raining')} | 気温 {g('AmbientTemp')}°C | 路面 {g('TrackTemp')}°C | 風 {g('WindSpeed')}m/s",
            f"ダメージ: {damage_str}",
            f"ピット: {g('NumPitstops')}回 | ペナルティ: {g('NumPenalties')} | 青旗: {g('BlueFlag')}",
        ]
    else:
        lines = [
            f"Track: {g('TrackName')} | Session: {session_label} | Class: {g('VehicleClass')}",
            f"Speed: {g('SpeedKmh')} km/h | Gear: {g('Gear')} | RPM: {g('EngineRPM')}",
            f"Position: P{g('Position')}/{g('NumVehicles')} | Lap: {g('TotalLaps')} | Remaining: {remaining_str}",
            f"Gap: Front {g('GapToFront')}s / Behind {g('GapToBehind')}s / Leader {g('GapToLeader')}s",
            f"Fuel: {g('Fuel')}L / {g('FuelCapacity')}L",
            f"Tyre wear: {_tyre_str(data, 'TyreWear')}%",
            f"Tyre temp: {_tyre_str(data, 'TyreTemp')}°C",
            f"Tyre pressure: {_tyre_str(data, 'TyrePressure')}kPa",
            f"Tyre compound: F {g('FrontCompound')} / R {g('RearCompound')}",
            f"Water: {g('WaterTemp')}°C | Oil: {g('OilTemp')}°C | ERS: {g('ERSBattery')}% | ERS temp: {g('ERSMotorTemp')}°C",
            f"Last lap: {g('LastLapTime')}s | Best: {g('BestLapTime')}s | Est: {g('EstLapTime')}s",
            f"Sectors (current): S1 {g('CurSector1')}s / S2 {g('CurSector2')}s",
            f"Weather: Rain {g('Raining')} | Air {g('AmbientTemp')}°C | Track {g('TrackTemp')}°C | Wind {g('WindSpeed')}m/s",
            f"Damage: {damage_str}",
            f"Pit stops: {g('NumPitstops')} | Penalties: {g('NumPenalties')} | Blue flag: {g('BlueFlag')}",
        ]

    lines.append(
        f"Race control: YellowFlag: {g('YellowFlag')} | "
        f"SectorFlags: {g('SectorFlags')} | GamePhase: {g('GamePhase')} | "
        f"InPits: {g('InPits')} | PitState: {g('PitState')}"
    )
    if 'FuelPerLap' in data:
        lines.append(
            f"Fuel estimate (recent complete laps, approximate): {g('FuelPerLap')} L/lap | "
            f"{g('FuelLapsEstimate')} laps of fuel remaining"
        )
    if 'TrendWindowSec' in data:
        lines.append(
            f"Change over {g('TrendWindowSec')}s: gap to front {g('GapToFrontChange')}s "
            f"(negative = closing) | tyre temperature change {_tyre_str(data, 'TyreTempChange')} C"
        )
    return '\n'.join(lines)


def format_gap_line(data: dict) -> str:
    """Console status line for gaps. Uses `_g` so a genuine 0.0s gap prints
    as "0.0s" instead of falling back to "N/A" (a plain `or 'N/A'` treats
    0.0 as falsy)."""
    return (f"  Gap: +{_g(data, 'GapToFront')}s / -{_g(data, 'GapToBehind')}s | "
            f"Leader: {_g(data, 'GapToLeader')}s")


def call_engineer(user_prompt: str) -> str:
    with OpenAI(base_url=LM_STUDIO_URL, api_key='lm-studio', max_retries=0) as client:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPTS[PERSONA][LANGUAGE] +
                 ' Prioritize flags, race phase and pit state. Do not invent missing values '
                 'or decode unknown state codes by guessing. Fuel estimates are approximate, '
                 'not guarantees. Give at most two short sentences; avoid repeating routine advice.'},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
            timeout=LLM_TIMEOUT,
        )
    if not response.choices:
        return ''
    content = response.choices[0].message.content
    return content.strip() if content else ''


def run_one_cycle(reader: RF2Reader) -> dict:
    """Read one telemetry snapshot and call the LLM. Pure logic, no I/O
    side effects (no print/speak) — shared by the CLI loop and the GUI so
    both present the same result differently instead of duplicating it.

    Returns a dict:
        {'ok': bool, 'data': dict | None, 'message': str | None,
         'error': str | None, 'reason': str | None}

    `reason` is one of: 'no_data', 'connection', 'timeout', 'empty', 'error',
    or None when `ok` is True.
    """
    captured_at = time.monotonic()
    try:
        data = reader.read_snapshot()
        if data:
            captured_at = data.get('CapturedAt', captured_at)
            prompt = build_prompt(data, LANGUAGE)
    except Exception as e:
        return {'ok': False, 'data': None, 'message': None,
                'error': str(e), 'reason': 'error'}
    if not data:
        return {'ok': False, 'data': None, 'message': None,
                'error': None, 'reason': 'no_data'}

    try:
        answer = call_engineer(prompt)
    except APITimeoutError:
        # Must be checked before APIConnectionError: APITimeoutError is a
        # subclass of it in the openai SDK, so the broader except would
        # otherwise swallow timeouts and misreport them as "not available".
        return {'ok': False, 'data': data, 'message': None,
                'error': 'LLM timed out', 'reason': 'timeout'}
    except APIConnectionError:
        return {'ok': False, 'data': data, 'message': None,
                'error': 'LM Studio not available', 'reason': 'connection'}
    except Exception as e:
        return {'ok': False, 'data': data, 'message': None,
                'error': str(e), 'reason': 'error'}

    expires_at = captured_at + MAX_DATA_AGE_SEC
    if time.monotonic() >= expires_at:
        return {'ok': False, 'data': data, 'message': None,
                'error': 'Telemetry expired — discarded late reply', 'reason': 'stale'}

    if not answer:
        return {'ok': False, 'data': data, 'message': None,
                'error': 'LLM returned empty response', 'reason': 'empty'}

    return {'ok': True, 'data': data, 'message': answer,
            'error': None, 'reason': None, 'expires_at': expires_at}


def engineer_loop():
    from engineer_worker import EngineerWorker
    results = queue.Queue()
    worker = EngineerWorker(results, engine_api=sys.modules[__name__])

    print('=' * 60)
    print('  Race Engineer — LMU + rF2 SharedMemory + LM Studio')
    print(f'  Persona: {PERSONA} | Language: {LANGUAGE} | Model: {MODEL_NAME}')
    print(f'  LLM call: every {INTERVAL_SEC}s')
    print('  Press Ctrl+C to stop.')
    print('=' * 60)

    worker.start(enable_tts=ENABLE_TTS)
    try:
        while True:
            try:
                result = results.get(timeout=0.25)
            except queue.Empty:
                continue
            if result['kind'] == 'stopped':
                break
            if result['kind'] != 'cycle':
                continue
            if result['reason'] == 'no_data':
                print('[INFO] LMU not running or not in session — waiting...')
                continue
            data = result['data']
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print('=' * 60)
            if data is not None:
                print(f"[{ts}] Lap {data.get('TotalLaps')} | {data.get('SpeedKmh')} km/h | "
                      f"Fuel: {data.get('Fuel')}L | P{data.get('Position')}/{data.get('NumVehicles')}")
                print(format_gap_line(data))
                print('-' * 60)
            if result['ok']:
                print(f"[ENGINEER] {result['message']}")
            else:
                print(f"[WARNING] {result['error']}")
            print('=' * 60)
    finally:
        worker.stop()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='LMU AI Race Engineer — live radio-style engineer for Le Mans Ultimate.',
    )
    parser.add_argument('--language', choices=['ja', 'en'], default=LANGUAGE,
                         help=f"Radio message language (default: {LANGUAGE})")
    parser.add_argument('--persona', choices=sorted(SYSTEM_PROMPTS.keys()), default=PERSONA,
                         help=f"AI persona (default: {PERSONA})")
    parser.add_argument('--model', default=MODEL_NAME,
                         help=f"Model name exactly as loaded in LM Studio (default: {MODEL_NAME})")
    parser.add_argument('--interval', type=positive_seconds, default=INTERVAL_SEC,
                         help=f"Seconds between LLM calls (default: {INTERVAL_SEC})")
    parser.add_argument('--timeout', type=positive_seconds, default=LLM_TIMEOUT,
                         help=f"LLM call timeout in seconds (default: {LLM_TIMEOUT})")
    parser.add_argument('--lm-studio-url', default=LM_STUDIO_URL,
                         help=f"LM Studio base URL (default: {LM_STUDIO_URL})")
    parser.add_argument('--no-tts', action='store_true',
                         help='Disable local TTS voice playback (text output only)')
    parser.add_argument('--max-data-age', type=positive_seconds, default=MAX_DATA_AGE_SEC,
                         help='Discard radio replies older than this many seconds (default: 20)')
    return parser.parse_args(argv)


if __name__ == '__main__':
    args = parse_args()
    LANGUAGE      = args.language
    PERSONA       = args.persona
    MODEL_NAME    = args.model
    INTERVAL_SEC  = args.interval
    LLM_TIMEOUT   = args.timeout
    LM_STUDIO_URL = args.lm_studio_url
    ENABLE_TTS    = not args.no_tts
    MAX_DATA_AGE_SEC = args.max_data_age

    try:
        engineer_loop()
    except KeyboardInterrupt:
        print('\n[INFO] Race Engineer stopped. Good race!')
