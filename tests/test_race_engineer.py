# Tests for race_engineer.py pure functions
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from race_engineer import get_field


class TestGetField:
    def test_returns_string_value_when_present(self):
        assert get_field({'SpeedKmh': 245}, 'SpeedKmh') == '245'

    def test_returns_default_when_key_missing(self):
        assert get_field({}, 'SpeedKmh') == 'N/A'

    def test_returns_default_when_value_is_none(self):
        assert get_field({'SpeedKmh': None}, 'SpeedKmh') == 'N/A'

    def test_custom_default(self):
        assert get_field({}, 'SpeedKmh', default='0') == '0'

    def test_converts_float_to_string(self):
        assert get_field({'Fuel': 42.3}, 'Fuel') == '42.3'

    def test_converts_bool_to_string(self):
        assert get_field({'IsInPit': False}, 'IsInPit') == 'False'


from race_engineer import build_prompt

SAMPLE_DATA = {
    'SpeedKmh': 245, 'Rpms': 7800, 'Gear': 6, 'CurrentLap': 12,
    'CurrentLapTime': '3:49.123', 'BestLapTime': '3:47.903', 'LastLapTime': '3:48.521',
    'Fuel': 42.3, 'GapFront': 1.842, 'GapBehind': 0.531,
    'TyrewearFrontLeft': 23, 'TyrewearFrontRight': 25,
    'TyrewearRearLeft': 18, 'TyrewearRearRight': 20,
    'TyreTemperatureFrontLeft': 92, 'TyreTemperatureFrontRight': 94,
    'TyreTemperatureRearLeft': 88, 'TyreTemperatureRearRight': 87,
    'TyrePressureFrontLeft': 27.2, 'TyrePressureFrontRight': 27.5,
    'TyrePressureRearLeft': 26.8, 'TyrePressureRearRight': 26.9,
    'EngineOilTemp': 105, 'EngineWaterTemp': 88, 'BatteryCharge': 72,
    'Flag_Yellow': False, 'IsInPit': False, 'ABSActive': False,
    'TCActive': False, 'TyresCompound': 'Medium',
}


class TestBuildPrompt:
    def test_ja_contains_speed(self):
        assert '245 km/h' in build_prompt(SAMPLE_DATA, 'ja')

    def test_ja_contains_lap(self):
        assert 'ラップ: 12' in build_prompt(SAMPLE_DATA, 'ja')

    def test_ja_contains_fuel(self):
        assert '42.3L' in build_prompt(SAMPLE_DATA, 'ja')

    def test_ja_contains_tyre_wear(self):
        assert 'FL 23%' in build_prompt(SAMPLE_DATA, 'ja')

    def test_en_contains_speed(self):
        assert '245 km/h' in build_prompt(SAMPLE_DATA, 'en')

    def test_en_contains_lap(self):
        assert 'Lap: 12' in build_prompt(SAMPLE_DATA, 'en')

    def test_en_contains_fuel(self):
        assert '42.3L' in build_prompt(SAMPLE_DATA, 'en')

    def test_missing_fields_show_na(self):
        prompt = build_prompt({}, 'ja')
        assert 'N/A' in prompt

    def test_ja_and_en_differ(self):
        assert build_prompt(SAMPLE_DATA, 'ja') != build_prompt(SAMPLE_DATA, 'en')
