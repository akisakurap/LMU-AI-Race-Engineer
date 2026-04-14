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
MODEL_NAME = 'gemma-4'                       # LM Studio model name (must match exactly)
INTERVAL_SEC = 10                            # Seconds between LLM calls
POLL_SEC = 2                                 # Seconds between SimHub polls
LLM_TIMEOUT = 30                             # Seconds before LLM call is abandoned
SIMHUB_URL = 'http://localhost:8888/api/v5/data'
LM_STUDIO_URL = 'http://localhost:1234/v1'

# ============================================================
# System prompts (selected by LANGUAGE)
# ============================================================
SYSTEM_PROMPTS = {
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
}

# SimHub REST API field names to extract
SIMHUB_FIELDS = [
    'SpeedKmh', 'Rpms', 'Gear', 'CurrentLap',
    'CurrentLapTime', 'BestLapTime', 'LastLapTime',
    'Fuel', 'GapFront', 'GapBehind',
    'TyrewearFrontLeft', 'TyrewearFrontRight', 'TyrewearRearLeft', 'TyrewearRearRight',
    'TyreTemperatureFrontLeft', 'TyreTemperatureFrontRight',
    'TyreTemperatureRearLeft', 'TyreTemperatureRearRight',
    'TyrePressureFrontLeft', 'TyrePressureFrontRight',
    'TyrePressureRearLeft', 'TyrePressureRearRight',
    'EngineOilTemp', 'EngineWaterTemp', 'BatteryCharge',
    'Flag_Yellow', 'IsInPit', 'ABSActive', 'TCActive', 'TyresCompound',
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
            f"タイヤ摩耗: FL {g('TyrewearFrontLeft')}% / FR {g('TyrewearFrontRight')}%"
            f" / RL {g('TyrewearRearLeft')}% / RR {g('TyrewearRearRight')}%",
            f"タイヤ温度: FL {g('TyreTemperatureFrontLeft')}°C / FR {g('TyreTemperatureFrontRight')}°C"
            f" / RL {g('TyreTemperatureRearLeft')}°C / RR {g('TyreTemperatureRearRight')}°C",
            f"タイヤ空気圧: FL {g('TyrePressureFrontLeft')} / FR {g('TyrePressureFrontRight')}"
            f" / RL {g('TyrePressureRearLeft')} / RR {g('TyrePressureRearRight')}",
            f"エンジン油温: {g('EngineOilTemp')}°C | 冷却水温: {g('EngineWaterTemp')}°C"
            f" | SOC: {g('BatteryCharge')}%",
            f"前車との差: +{g('GapFront')}s | 後車との差: -{g('GapBehind')}s",
            f"前ラップ: {g('LastLapTime')} | ベスト: {g('BestLapTime')} | 現在: {g('CurrentLapTime')}",
            f"イエローフラグ: {g('Flag_Yellow')} | ピット中: {g('IsInPit')}"
            f" | ABS: {g('ABSActive')} | TC: {g('TCActive')}",
            f"タイヤコンパウンド: {g('TyresCompound')}",
        ]
    else:
        lines = [
            f"Speed: {g('SpeedKmh')} km/h | Lap: {g('CurrentLap')} | Fuel: {g('Fuel')}L",
            f"Tyre wear: FL {g('TyrewearFrontLeft')}% / FR {g('TyrewearFrontRight')}%"
            f" / RL {g('TyrewearRearLeft')}% / RR {g('TyrewearRearRight')}%",
            f"Tyre temp: FL {g('TyreTemperatureFrontLeft')}°C / FR {g('TyreTemperatureFrontRight')}°C"
            f" / RL {g('TyreTemperatureRearLeft')}°C / RR {g('TyreTemperatureRearRight')}°C",
            f"Tyre pressure: FL {g('TyrePressureFrontLeft')} / FR {g('TyrePressureFrontRight')}"
            f" / RL {g('TyrePressureRearLeft')} / RR {g('TyrePressureRearRight')}",
            f"Engine oil: {g('EngineOilTemp')}°C | Coolant: {g('EngineWaterTemp')}°C"
            f" | SoC: {g('BatteryCharge')}%",
            f"Gap ahead: +{g('GapFront')}s | Gap behind: -{g('GapBehind')}s",
            f"Last lap: {g('LastLapTime')} | Best: {g('BestLapTime')} | Current: {g('CurrentLapTime')}",
            f"Yellow: {g('Flag_Yellow')} | In pit: {g('IsInPit')}"
            f" | ABS: {g('ABSActive')} | TC: {g('TCActive')}",
            f"Compound: {g('TyresCompound')}",
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

                extracted = {field: raw.get(field) for field in SIMHUB_FIELDS}

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
