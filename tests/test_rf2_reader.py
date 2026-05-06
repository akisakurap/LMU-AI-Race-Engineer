"""tests/test_rf2_reader.py"""

import ctypes
import pytest
from unittest.mock import patch

from rf2_reader import RF2Reader, _damage_summary, _wind_speed
from rf2_structs import RF2Vec3


# -----------------------------------------------------------------------
# ユニットテスト（LMU 不要）
# -----------------------------------------------------------------------

def test_damage_summary_no_damage():
    dent = (ctypes.c_uint8 * 8)(*([0] * 8))
    assert _damage_summary(dent) == 'なし'


def test_damage_summary_with_damage():
    dent = (ctypes.c_uint8 * 8)(*(0, 0, 3, 0, 0, 0, 0, 0))
    assert _damage_summary(dent) == 'あり（最大 3）'


def test_wind_speed_zero():
    wind = RF2Vec3(0.0, 0.0, 0.0)
    assert _wind_speed(wind) == pytest.approx(0.0)


def test_wind_speed_nonzero():
    wind = RF2Vec3(3.0, 4.0, 0.0)  # 3-4-5 三角形
    assert _wind_speed(wind) == pytest.approx(5.0)


# -----------------------------------------------------------------------
# LMU 未起動時のフォールバック
# -----------------------------------------------------------------------

def test_read_snapshot_returns_empty_when_lmu_not_running():
    """共有メモリが開けないとき空 dict を返す。"""
    reader = RF2Reader()
    with patch('rf2_reader._open_shm', return_value=None):
        result = reader.read_snapshot()
    assert result == {}
