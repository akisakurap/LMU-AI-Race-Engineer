"""
race_engineer.py
================
Live race engineer assistant for Le Mans Ultimate via SimHub + LM Studio.

Configuration variables are at the top of this file.
"""

import threading
import time
from datetime import datetime

import requests
from openai import OpenAI

# ============================================================
# Configuration — edit these to match your setup
# ============================================================
LANGUAGE = 'ja'                              # 'ja' (Japanese) or 'en' (English)
PERSONA  = 'default'                         # 'default' or 'girl'
MODEL_NAME = 'google/gemma-4-e2b'            # LM Studio model name (must match exactly)
INTERVAL_SEC = 10                            # Seconds between LLM calls
POLL_SEC = 2                                 # Seconds between SimHub polls
LLM_TIMEOUT = 30                             # Seconds before LLM call is abandoned
SIMHUB_URL = 'http://localhost:8888/api/getgamedata'
LM_STUDIO_URL = 'http://localhost:1234/v1'

# ============================================================
# System prompts (selected by PERSONA + LANGUAGE)
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

# SimHub REST API field names to extract (from NewData object)
SIMHUB_FIELDS = [
    'SpeedKmh', 'Rpms', 'Gear', 'CurrentLap',
    'CurrentLapTime', 'BestLapTime', 'LastLapTime',
    'Fuel', 'Position', 'OpponentsCount', 'BestSplitDelta',
    'TyreWearFrontLeft', 'TyreWearFrontRight', 'TyreWearRearLeft', 'TyreWearRearRight',
    'TyresWearAvg',
    'TyreTemperatureFrontLeft', 'TyreTemperatureFrontRight',
    'TyreTemperatureRearLeft', 'TyreTemperatureRearRight',
    'TyrePressureFrontLeft', 'TyrePressureFrontRight',
    'TyrePressureRearLeft', 'TyrePressureRearRight',
    'OilTemperature', 'WaterTemperature', 'ERSPercent',
    'Flag_Yellow', 'IsInPit', 'ABSActive', 'TCActive', 'CarClass',
]

# ============================================================
# Shared state — Thread 1 writes, Thread 2 reads
# ============================================================
latest_data: dict = {}
data_lock = threading.Lock()
data_received = threading.Event()  # set when first SimHub poll succeeds


def get_field(data: dict, key: str, default: str = 'N/A') -> str:
    """Safely extract a field from SimHub data as a string.

    Returns `default` if the key is missing or the value is None.
    """
    val = data.get(key)
    if val is None:
        return default
    return str(val)


def build_prompt(data: dict, language: str) -> str:
    """Format telemetry data into an LLM user prompt string.

    Produces a compact, multi-line summary of key telemetry values.
    Missing fields appear as 'N/A'.
    """
    g = lambda key: get_field(data, key)

    if language == 'ja':
        lines = [
            f"速度: {g('SpeedKmh')} km/h | ラップ: {g('CurrentLap')} | 燃料: {g('Fuel')}L",
            f"順位: P{g('Position')}/{g('OpponentsCount')} | ベストとの差: {g('BestSplitDelta')}s",
            f"タイヤ摩耗(平均): {g('TyresWearAvg')}% | FL {g('TyreWearFrontLeft')}% / FR {g('TyreWearFrontRight')}%"
            f" / RL {g('TyreWearRearLeft')}% / RR {g('TyreWearRearRight')}%",
            f"タイヤ温度: FL {g('TyreTemperatureFrontLeft')}°C / FR {g('TyreTemperatureFrontRight')}°C"
            f" / RL {g('TyreTemperatureRearLeft')}°C / RR {g('TyreTemperatureRearRight')}°C",
            f"タイヤ空気圧: FL {g('TyrePressureFrontLeft')} / FR {g('TyrePressureFrontRight')}"
            f" / RL {g('TyrePressureRearLeft')} / RR {g('TyrePressureRearRight')}",
            f"エンジン油温: {g('OilTemperature')}°C | 冷却水温: {g('WaterTemperature')}°C"
            f" | ERS: {g('ERSPercent')}%",
            f"前ラップ: {g('LastLapTime')} | ベスト: {g('BestLapTime')} | 現在: {g('CurrentLapTime')}",
            f"イエローフラグ: {g('Flag_Yellow')} | ピット中: {g('IsInPit')}"
            f" | ABS: {g('ABSActive')} | TC: {g('TCActive')}",
            f"クラス: {g('CarClass')}",
        ]
    else:
        lines = [
            f"Speed: {g('SpeedKmh')} km/h | Lap: {g('CurrentLap')} | Fuel: {g('Fuel')}L",
            f"Position: P{g('Position')}/{g('OpponentsCount')} | Delta to best: {g('BestSplitDelta')}s",
            f"Tyre wear (avg): {g('TyresWearAvg')}% | FL {g('TyreWearFrontLeft')}% / FR {g('TyreWearFrontRight')}%"
            f" / RL {g('TyreWearRearLeft')}% / RR {g('TyreWearRearRight')}%",
            f"Tyre temp: FL {g('TyreTemperatureFrontLeft')}°C / FR {g('TyreTemperatureFrontRight')}°C"
            f" / RL {g('TyreTemperatureRearLeft')}°C / RR {g('TyreTemperatureRearRight')}°C",
            f"Tyre pressure: FL {g('TyrePressureFrontLeft')} / FR {g('TyrePressureFrontRight')}"
            f" / RL {g('TyrePressureRearLeft')} / RR {g('TyrePressureRearRight')}",
            f"Engine oil: {g('OilTemperature')}°C | Coolant: {g('WaterTemperature')}°C"
            f" | ERS: {g('ERSPercent')}%",
            f"Last lap: {g('LastLapTime')} | Best: {g('BestLapTime')} | Current: {g('CurrentLapTime')}",
            f"Yellow: {g('Flag_Yellow')} | In pit: {g('IsInPit')}"
            f" | ABS: {g('ABSActive')} | TC: {g('TCActive')}",
            f"Class: {g('CarClass')}",
        ]

    return '\n'.join(lines)


class SimHubPoller(threading.Thread):
    """Thread 1: polls SimHub REST API every POLL_SEC seconds.

    Stores extracted telemetry in the global `latest_data` dict.
    Sets the `data_received` event on first successful poll.
    Errors are printed as warnings — the thread never crashes.
    """

    def __init__(self):
        super().__init__(daemon=True, name='SimHubPoller')
        self._stop_event = threading.Event()

    def stop(self):
        """Signal the thread to stop after its current sleep."""
        self._stop_event.set()

    def run(self):
        global latest_data
        while not self._stop_event.is_set():
            try:
                resp = requests.get(SIMHUB_URL, timeout=5)
                resp.raise_for_status()
                raw = resp.json()

                new_data = raw.get('NewData') or {}
                extracted = {field: new_data.get(field) for field in SIMHUB_FIELDS}

                with data_lock:
                    latest_data = extracted

                data_received.set()

            except requests.exceptions.ConnectionError:
                print(f'[WARNING] SimHub not available — retrying in {POLL_SEC}s')
            except requests.exceptions.Timeout:
                print(f'[WARNING] SimHub request timed out — retrying in {POLL_SEC}s')
            except requests.exceptions.RequestException as e:
                print(f'[WARNING] SimHub error: {e}')
            except Exception as e:
                print(f'[WARNING] Unexpected poller error: {e}')

            self._stop_event.wait(POLL_SEC)


def call_engineer(user_prompt: str) -> str:
    """Send telemetry prompt to LM Studio and return the response text.

    Uses the OpenAI-compatible API provided by LM Studio.
    Raises exceptions on connection failure or timeout — caller handles them.
    """
    client = OpenAI(base_url=LM_STUDIO_URL, api_key='lm-studio')

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPTS[PERSONA][LANGUAGE]},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
        timeout=LLM_TIMEOUT,
    )

    return response.choices[0].message.content.strip()


def engineer_loop():
    """Thread 2 (main thread): every INTERVAL_SEC, read telemetry and call the LLM.

    Waits for the first SimHub poll to succeed before making any LLM calls.
    Errors from LM Studio are printed as warnings — the loop never crashes.
    Stop with Ctrl+C.
    """
    print('=' * 60)
    print('  Race Engineer — LMU + SimHub + LM Studio')
    print(f'  Persona: {PERSONA} | Language: {LANGUAGE} | Model: {MODEL_NAME}')
    print(f'  SimHub poll: every {POLL_SEC}s | LLM call: every {INTERVAL_SEC}s')
    print('  Press Ctrl+C to stop.')
    print('=' * 60)
    print('[INFO] Waiting for first SimHub data...')

    while True:
        time.sleep(INTERVAL_SEC)

        if not data_received.is_set():
            print('[INFO] No SimHub data yet — still waiting...')
            continue

        with data_lock:
            current_data = dict(latest_data)

        prompt = build_prompt(current_data, LANGUAGE)

        speed    = get_field(current_data, 'SpeedKmh')
        lap      = get_field(current_data, 'CurrentLap')
        fuel     = get_field(current_data, 'Fuel')
        pos      = get_field(current_data, 'Position')
        total    = get_field(current_data, 'OpponentsCount')
        wear_avg = get_field(current_data, 'TyresWearAvg')
        delta    = get_field(current_data, 'BestSplitDelta')
        ts       = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('=' * 60)
        print(f'[{ts}] Lap {lap} | {speed} km/h | Fuel: {fuel}L | P{pos}/{total}')
        print(f'  Tyre wear: {wear_avg}% avg | Delta to best: {delta}s')
        print('-' * 60)

        try:
            answer = call_engineer(prompt)
            if answer:
                print(f'[ENGINEER] {answer}')
            else:
                print('[WARNING] LLM returned empty response — skipping')
        except Exception as e:
            err = str(e).lower()
            if 'connection' in err or 'refused' in err or 'connect' in err:
                print('[WARNING] LM Studio not available — skipping this cycle')
            elif 'timeout' in err or 'timed out' in err:
                print('[WARNING] LLM timed out — skipping this cycle')
            else:
                print(f'[WARNING] LLM error: {e}')

        print('=' * 60)


if __name__ == '__main__':
    poller = SimHubPoller()
    poller.start()

    try:
        engineer_loop()
    except KeyboardInterrupt:
        print('\n[INFO] Shutting down...')
        poller.stop()
        poller.join(timeout=POLL_SEC + 1)
        print('[INFO] Race Engineer stopped. Good race!')
