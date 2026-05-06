"""tests/test_race_engineer.py"""

import pytest
from race_engineer import build_prompt, _session_name, _tyre_str


# -----------------------------------------------------------------------
# _session_name
# -----------------------------------------------------------------------

def test_session_name_race():
    assert _session_name(10) == 'レース'
    assert _session_name(13) == 'レース'


def test_session_name_qualifying():
    assert _session_name(5) == '予選'


def test_session_name_practice():
    assert _session_name(1) == '練習'


# -----------------------------------------------------------------------
# build_prompt — 日本語
# -----------------------------------------------------------------------

FULL_DATA = {
    'SpeedKmh': 230.5, 'Gear': 5, 'EngineRPM': 7200,
    'Fuel': 38.5, 'FuelCapacity': 60.0,
    'WaterTemp': 85.0, 'OilTemp': 110.0,
    'ERSBattery': 72.0, 'ERSMotorTemp': 65.0,
    'TyreWear': [85.0, 84.5, 82.0, 81.5],
    'TyreTemp': [95.0, 96.0, 92.0, 91.5],
    'TyrePressure': [180.0, 181.0, 178.0, 179.0],
    'FrontCompound': 'Soft', 'RearCompound': 'Soft',
    'Position': 3, 'NumVehicles': 20,
    'TotalLaps': 12, 'TimeIntoLap': 45.2,
    'LastLapTime': 105.321, 'BestLapTime': 104.876,
    'EstLapTime': 105.1,
    'CurSector1': 32.1, 'CurSector2': 68.4,
    'LastSector1': 31.9, 'LastSector2': 67.8,
    'BestSector1': 31.5, 'BestSector2': 67.2,
    'GapToFront': 1.234, 'GapToBehind': 0.876, 'GapToLeader': 8.5,
    'TrackName': 'Le Mans', 'Session': 10,
    'TimeRemaining': 3661, 'LapsRemaining': None,
    'YellowFlag': 0, 'SectorFlags': [0, 0, 0],
    'GamePhase': 5,
    'InPits': False, 'PitState': 0, 'NumPitstops': 1, 'NumPenalties': 0,
    'BlueFlag': False, 'VehicleClass': 'GTE',
    'Raining': 0.0, 'AmbientTemp': 22.0, 'TrackTemp': 35.0, 'WindSpeed': 2.5,
    'DamageSummary': 'なし', 'PartDetached': False, 'Overheating': False,
}


def test_build_prompt_ja_contains_gap():
    prompt = build_prompt(FULL_DATA, 'ja')
    assert 'ギャップ' in prompt
    assert '1.234' in prompt
    assert '0.876' in prompt


def test_build_prompt_ja_contains_weather():
    prompt = build_prompt(FULL_DATA, 'ja')
    assert '天候' in prompt
    assert '22.0' in prompt
    assert '35.0' in prompt


def test_build_prompt_ja_contains_damage_none():
    prompt = build_prompt(FULL_DATA, 'ja')
    assert 'ダメージ' in prompt
    assert 'なし' in prompt


def test_build_prompt_ja_damage_with_issue():
    data = dict(FULL_DATA, DamageSummary='あり（最大 3）')
    prompt = build_prompt(data, 'ja')
    assert 'あり（最大 3）' in prompt


def test_build_prompt_ja_remaining_time():
    prompt = build_prompt(FULL_DATA, 'ja')
    assert '61:01' in prompt    # 3661s = 61分01秒


def test_build_prompt_en_contains_gap():
    prompt = build_prompt(FULL_DATA, 'en')
    assert 'Gap' in prompt
    assert '1.234' in prompt


def test_build_prompt_no_data_does_not_crash():
    prompt = build_prompt({}, 'ja')
    assert 'N/A' in prompt


# -----------------------------------------------------------------------
# _tyre_str
# -----------------------------------------------------------------------

def test_tyre_str_normal():
    data = {'TyreWear': [85.0, 84.5, 82.0, 81.5]}
    result = _tyre_str(data, 'TyreWear')
    assert 'FL 85.0' in result
    assert 'RR 81.5' in result


def test_tyre_str_missing():
    result = _tyre_str({}, 'TyreWear')
    assert result == 'N/A'
