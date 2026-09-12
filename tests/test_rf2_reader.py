"""tests/test_rf2_reader.py"""

import ctypes
import pytest
from unittest.mock import patch

from rf2_reader import RF2Reader, _damage_summary, _wind_speed
from rf2_structs import RF2Vec3
from rf2_structs import RF2TelemetryBuffer, RF2ScoringBuffer
from rf2_reader import _read_buffer
import io


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


def test_short_buffer_is_rejected_without_crashing():
    assert _read_buffer(io.BytesIO(b'\0' * 8), RF2ScoringBuffer) is None


def test_update_in_progress_is_rejected():
    buf = RF2ScoringBuffer()
    buf.mVersionUpdateBegin = 2
    buf.mVersionUpdateEnd = 1
    assert _read_buffer(io.BytesIO(bytes(buf)), RF2ScoringBuffer) is None


def test_update_during_copy_is_retried():
    old, new = RF2ScoringBuffer(), RF2ScoringBuffer()
    old.mVersionUpdateBegin = old.mVersionUpdateEnd = 1
    new.mVersionUpdateBegin = new.mVersionUpdateEnd = 2
    old.mScoringInfo.mNumVehicles = 1
    new.mScoringInfo.mNumVehicles = 2

    class UpdatingMemory(io.BytesIO):
        def read(self, size):
            result = super().read(size)
            if size == ctypes.sizeof(RF2ScoringBuffer):
                self.seek(0)
                self.write(bytes(new))
            return result

    result = _read_buffer(UpdatingMemory(bytes(old)), RF2ScoringBuffer)
    assert result.mScoringInfo.mNumVehicles == 2


@pytest.mark.parametrize('count', [-1, 129])
def test_invalid_vehicle_count_reports_corrupt_buffer(count):
    tel, scoring = RF2TelemetryBuffer(), RF2ScoringBuffer()
    scoring.mScoringInfo.mNumVehicles = count
    with pytest.raises(ValueError, match='vehicle count'):
        RF2Reader()._extract(tel, scoring)


def test_extract_matches_player_id_and_sanitizes_nonfinite_values():
    tel, scoring = RF2TelemetryBuffer(), RF2ScoringBuffer()
    scoring.mScoringInfo.mNumVehicles = 2
    player = scoring.mVehicles[1]
    player.mIsPlayer = True
    player.mID = 7
    player.mPlace = 2
    tel.mVehicles[3].mID = 7
    tel.mVehicles[3].mFuel = 42.5
    tel.mVehicles[3].mEngineWaterTemp = float('nan')
    data = RF2Reader()._extract(tel, scoring)
    assert data['Fuel'] == 42.5
    assert data['Position'] == 2
    assert data['PlayerID'] == 7
    assert data['WaterTemp'] is None
