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
