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
