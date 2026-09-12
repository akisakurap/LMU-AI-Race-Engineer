"""
rf2_reader.py
=============
rF2 共有メモリからテレメトリ・スコアリングデータをオンデマンドで読み取る。
LMU 未起動時は空 dict を返す（クラッシュしない）。
"""

import ctypes
import mmap
import math

from rf2_structs import (
    RF2TelemetryBuffer,
    RF2ScoringBuffer,
    vec3_speed_kmh,
    tire_temp_mid_celsius,
)

TELEMETRY_MAP = '$rFactor2SMMP_Telemetry$'
SCORING_MAP   = '$rFactor2SMMP_Scoring$'


def _open_shm(name: str, size: int):
    """Windows 名前付き共有メモリを開いて mmap を返す。失敗時は None。"""
    try:
        return mmap.mmap(-1, size, tagname=name, access=mmap.ACCESS_READ)
    except Exception:
        return None


def _read_buffer(shm, buf_type):
    """Accept only a full copy bracketed by the same stable version pair."""
    size = ctypes.sizeof(buf_type)
    for _ in range(3):
        shm.seek(0)
        before = shm.read(8)
        if len(before) != 8:
            return None
        if before[:4] != before[4:]:
            continue
        shm.seek(0)
        raw = shm.read(size)
        shm.seek(0)
        after = shm.read(8)
        if len(raw) != size:
            return None
        if before == raw[:8] == after:
            return buf_type.from_buffer_copy(raw)
    return None


def _finite_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, list):
        return [_finite_values(item) for item in value]
    return value


def _damage_summary(dent: ctypes.Array) -> str:
    """mDentSeverity[8] から人間が読みやすいサマリーを生成する。"""
    max_sev = max(dent)
    if max_sev == 0:
        return 'なし'
    return f'あり（最大 {max_sev}）'


def _wind_speed(wind) -> float:
    """風速ベクトルのスカラー値 (m/s) を返す。"""
    return math.sqrt(wind.x ** 2 + wind.y ** 2 + wind.z ** 2)


class RF2Reader:
    """rF2 共有メモリからテレメトリスナップショットを取得する。"""

    def read_snapshot(self) -> dict:
        """
        LLM 呼び出し直前にオンデマンドで呼ぶ。
        LMU 未起動・共有メモリ不在・自車未検出のいずれでも空 dict を返す。
        """
        t_size = ctypes.sizeof(RF2TelemetryBuffer)
        s_size = ctypes.sizeof(RF2ScoringBuffer)

        shm_t = _open_shm(TELEMETRY_MAP, t_size)
        shm_s = _open_shm(SCORING_MAP,   s_size)

        if shm_t is None or shm_s is None:
            if shm_t: shm_t.close()
            if shm_s: shm_s.close()
            return {}

        try:
            tel_buf  = _read_buffer(shm_t, RF2TelemetryBuffer)
            scor_buf = _read_buffer(shm_s, RF2ScoringBuffer)
            if tel_buf is None or scor_buf is None:
                return {}

            return self._extract(tel_buf, scor_buf)
        finally:
            shm_t.close()
            shm_s.close()

    # ------------------------------------------------------------------

    def _extract(self, tel_buf: RF2TelemetryBuffer,
                 scor_buf: RF2ScoringBuffer) -> dict:
        info = scor_buf.mScoringInfo
        n    = info.mNumVehicles
        if not 0 <= n <= len(scor_buf.mVehicles):
            raise ValueError(f'Invalid scoring vehicle count: {n}')

        # プレイヤー車両をスコアリングから特定
        player_s = next(
            (scor_buf.mVehicles[i] for i in range(n)
             if scor_buf.mVehicles[i].mIsPlayer),
            None,
        )
        if player_s is None:
            return {}

        # テレメトリ側でも mID で突き合わせ
        player_t = next(
            (tel_buf.mVehicles[i] for i in range(len(tel_buf.mVehicles))
             if tel_buf.mVehicles[i].mID == player_s.mID),
            None,
        )
        if player_t is None:
            return {}

        # 後続車（mPlace + 1）を探してギャップを取得
        behind_gap = None
        for i in range(n):
            v = scor_buf.mVehicles[i]
            if v.mPlace == player_s.mPlace + 1:
                behind_gap = round(v.mTimeBehindNext, 3)
                break

        # タイヤ情報（4輪 FL=0 FR=1 RL=2 RR=3）
        wheels = player_t.mWheels
        w = {
            'wear':  [round(wheels[i].mWear * 100, 1) for i in range(4)],
            'temp':  [round(tire_temp_mid_celsius(wheels[i]), 1) for i in range(4)],
            'press': [round(wheels[i].mPressure, 1) for i in range(4)],
        }

        # 残り時間・残りラップ
        time_remaining = None
        if info.mEndET > 0 and info.mCurrentET > 0:
            time_remaining = max(0.0, round(info.mEndET - info.mCurrentET, 1))

        max_laps = int(info.mMaxLaps) if info.mMaxLaps > 0 else None
        laps_remaining = (
            max_laps - player_s.mTotalLaps
            if max_laps is not None else None
        )

        data = {
            'PlayerID':      int(player_s.mID),
            'SessionElapsed': float(info.mCurrentET),
            # --- 速度・駆動系 ---
            'SpeedKmh':      round(vec3_speed_kmh(player_t.mLocalVel), 1),
            'Gear':          int(player_t.mGear),
            'EngineRPM':     round(player_t.mEngineRPM, 0),
            # --- 燃料 ---
            'Fuel':          round(player_t.mFuel, 2),
            'FuelCapacity':  round(player_t.mFuelCapacity, 1),
            # --- 温度 ---
            'WaterTemp':     round(player_t.mEngineWaterTemp, 1),
            'OilTemp':       round(player_t.mEngineOilTemp, 1),
            # --- タイヤ ---
            'TyreWear':      w['wear'],
            'TyreTemp':      w['temp'],
            'TyrePressure':  w['press'],
            'FrontCompound': player_t.mFrontTireCompoundName.decode('utf-8', errors='replace').strip('\x00'),
            'RearCompound':  player_t.mRearTireCompoundName.decode('utf-8', errors='replace').strip('\x00'),
            # --- ERS ---
            'ERSBattery':    round(player_t.mBatteryChargeFraction * 100, 1),
            'ERSMotorTemp':  round(player_t.mElectricBoostMotorTemperature, 1),
            # --- ダメージ ---
            'DamageSummary': _damage_summary(player_t.mDentSeverity),
            'PartDetached':  bool(player_t.mDetached),
            'Overheating':   bool(player_t.mOverheating),
            # --- 順位・ラップ ---
            'Position':      int(player_s.mPlace),
            'NumVehicles':   int(info.mNumVehicles),
            'TotalLaps':     int(player_s.mTotalLaps),
            'TimeIntoLap':   round(player_s.mTimeIntoLap, 3),
            'LastLapTime':   round(player_s.mLastLapTime, 3),
            'BestLapTime':   round(player_s.mBestLapTime, 3),
            'EstLapTime':    round(player_s.mEstimatedLapTime, 3),
            'CurSector1':    round(player_s.mCurSector1, 3),
            'CurSector2':    round(player_s.mCurSector2, 3),
            'LastSector1':   round(player_s.mLastSector1, 3),
            'LastSector2':   round(player_s.mLastSector2, 3),
            'BestSector1':   round(player_s.mBestSector1, 3),
            'BestSector2':   round(player_s.mBestSector2, 3),
            # --- ギャップ ---
            'GapToFront':    round(player_s.mTimeBehindNext, 3),
            'GapToBehind':   behind_gap,
            'GapToLeader':   round(player_s.mTimeBehindLeader, 3),
            # --- セッション ---
            'TrackName':     info.mTrackName.decode('utf-8', errors='replace').strip('\x00'),
            'Session':       int(info.mSession),
            'TimeRemaining': time_remaining,
            'LapsRemaining': laps_remaining,
            # --- フラッグ・状態 ---
            'YellowFlag':    int(info.mYellowFlagState),
            'SectorFlags':   [int(info.mSectorFlag[i]) for i in range(3)],
            'GamePhase':     int(info.mGamePhase),
            'InPits':        bool(player_s.mInPits),
            'PitState':      int(player_s.mPitState),
            'NumPitstops':   int(player_s.mNumPitstops),
            'NumPenalties':  int(player_s.mNumPenalties),
            'BlueFlag':      int(player_s.mFlag) == 6,
            'VehicleClass':  player_s.mVehicleClass.decode('utf-8', errors='replace').strip('\x00'),
            # --- 天候 ---
            'Raining':       round(float(info.mRaining), 2),
            'AmbientTemp':   round(float(info.mAmbientTemp), 1),
            'TrackTemp':     round(float(info.mTrackTemp), 1),
            'WindSpeed':     round(_wind_speed(info.mWind), 1),
        }
        return {key: _finite_values(value) for key, value in data.items()}
