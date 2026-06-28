"""
race_engineer.py
================
Live race engineer assistant for Le Mans Ultimate via rF2 SharedMemory + LM Studio.

Configuration variables are at the top of this file.
"""

import time
from datetime import datetime

from openai import OpenAI

from rf2_reader import RF2Reader
from tts_engine import speak

# ============================================================
# Configuration
# ============================================================
LANGUAGE     = 'ja'
PERSONA      = 'default'
MODEL_NAME   = 'google/gemma-4-e2b'
INTERVAL_SEC = 10
LLM_TIMEOUT  = 30
LM_STUDIO_URL = 'http://localhost:1234/v1'

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


def _session_name(session_id: int) -> str:
    if 10 <= session_id <= 13:
        return 'レース'
    if 5 <= session_id <= 8:
        return '予選'
    if 1 <= session_id <= 4:
        return '練習'
    return 'テスト'


def build_prompt(data: dict, language: str) -> str:
    g = lambda key, default='N/A': _g(data, key, default)

    session_label = _session_name(int(float(g('Session', '0'))))

    time_rem = data.get('TimeRemaining')
    laps_rem = data.get('LapsRemaining')
    remaining_str = ''
    if time_rem is not None:
        m, s = divmod(int(time_rem), 60)
        remaining_str += f'{m}:{s:02d}'
    if laps_rem is not None:
        remaining_str += f' / 残り{laps_rem}周'
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

    return '\n'.join(lines)


def call_engineer(user_prompt: str) -> str:
    client = OpenAI(base_url=LM_STUDIO_URL, api_key='lm-studio')
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPTS[PERSONA][LANGUAGE]},
            {'role': 'user',   'content': user_prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
        timeout=LLM_TIMEOUT,
    )
    if not response.choices:
        return ''
    content = response.choices[0].message.content
    return content.strip() if content else ''


def engineer_loop():
    reader = RF2Reader()

    print('=' * 60)
    print('  Race Engineer — LMU + rF2 SharedMemory + LM Studio')
    print(f'  Persona: {PERSONA} | Language: {LANGUAGE} | Model: {MODEL_NAME}')
    print(f'  LLM call: every {INTERVAL_SEC}s')
    print('  Press Ctrl+C to stop.')
    print('=' * 60)

    while True:
        time.sleep(INTERVAL_SEC)

        data = reader.read_snapshot()

        if not data:
            print('[INFO] LMU not running or not in session — waiting...')
            continue

        prompt = build_prompt(data, LANGUAGE)
        ts     = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print('=' * 60)
        print(f"[{ts}] Lap {data.get('TotalLaps')} | {data.get('SpeedKmh')} km/h | "
              f"Fuel: {data.get('Fuel')}L | P{data.get('Position')}/{data.get('NumVehicles')}")
        print(f"  Gap: +{data.get('GapToFront') or 'N/A'}s / -{data.get('GapToBehind') or 'N/A'}s | "
              f"Leader: {data.get('GapToLeader') or 'N/A'}s")
        print('-' * 60)

        try:
            answer = call_engineer(prompt)
            if answer:
                print(f'[ENGINEER] {answer}')
                speak(answer, LANGUAGE)
            else:
                print('[WARNING] LLM returned empty response — skipping')
        except Exception as e:
            err = str(e).lower()
            if 'connection' in err or 'refused' in err:
                print('[WARNING] LM Studio not available — skipping this cycle')
            elif 'timeout' in err or 'timed out' in err:
                print('[WARNING] LLM timed out — skipping this cycle')
            else:
                print(f'[WARNING] LLM error: {e}')

        print('=' * 60)


if __name__ == '__main__':
    try:
        engineer_loop()
    except KeyboardInterrupt:
        print('\n[INFO] Race Engineer stopped. Good race!')
