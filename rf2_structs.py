"""
rf2_structs.py
==============
rF2State.h の ctypes 構造体定義。
rFactor2SharedMemoryMapPlugin64.dll が書き出す共有メモリのレイアウトに対応。

MSVC 64-bit では long = 4 bytes。_pack_ は未指定（ctypes の自然アライメントを使用）。
"""

import ctypes
import math


# ---------------------------------------------------------------------------
# 基本型
# ---------------------------------------------------------------------------

class RF2Vec3(ctypes.Structure):
    _fields_ = [
        ('x', ctypes.c_double),
        ('y', ctypes.c_double),
        ('z', ctypes.c_double),
    ]


class RF2Wheel(ctypes.Structure):
    _fields_ = [
        ('mSuspensionDeflection',        ctypes.c_double),
        ('mRideHeight',                  ctypes.c_double),
        ('mSuspForce',                   ctypes.c_double),
        ('mBrakeTemp',                   ctypes.c_double),
        ('mBrakePressure',               ctypes.c_double),
        ('mRotation',                    ctypes.c_double),
        ('mLateralPatchVel',             ctypes.c_double),
        ('mLongitudinalPatchVel',        ctypes.c_double),
        ('mLateralGroundVel',            ctypes.c_double),
        ('mLongitudinalGroundVel',       ctypes.c_double),
        ('mCamber',                      ctypes.c_double),
        ('mLateralForce',                ctypes.c_double),
        ('mLongitudinalForce',           ctypes.c_double),
        ('mTireLoad',                    ctypes.c_double),
        ('mGripFract',                   ctypes.c_double),
        ('mPressure',                    ctypes.c_double),
        ('mTemperature',                 ctypes.c_double * 3),   # inner/mid/outer (K)
        ('mWear',                        ctypes.c_double),
        ('mTerrainName',                 ctypes.c_char * 16),
        ('mSurfaceType',                 ctypes.c_uint8),
        ('mFlat',                        ctypes.c_bool),
        ('mDetached',                    ctypes.c_bool),
        ('mStaticUndeflectedRadius',     ctypes.c_uint8),
        # 4 bytes → 次の double を 8 バイト境界に揃える
        ('_pad_wheel',                   ctypes.c_uint8 * 4),
        ('mVerticalTireDeflection',      ctypes.c_double),
        ('mWheelYLocation',              ctypes.c_double),
        ('mToe',                         ctypes.c_double),
        ('mTireCarcassTemperature',      ctypes.c_double),
        ('mTireInnerLayerTemperature',   ctypes.c_double * 3),
        ('mExpansion',                   ctypes.c_uint8 * 24),
    ]


# ---------------------------------------------------------------------------
# Telemetry バッファ
# ---------------------------------------------------------------------------

class RF2VehicleTelemetry(ctypes.Structure):
    _fields_ = [
        ('mID',                           ctypes.c_int32),
        ('_pad0',                         ctypes.c_uint8 * 4),
        ('mDeltaTime',                    ctypes.c_double),
        ('mElapsedTime',                  ctypes.c_double),
        ('mLapNumber',                    ctypes.c_int32),
        ('_pad1',                         ctypes.c_uint8 * 4),
        ('mLapStartET',                   ctypes.c_double),
        ('mVehicleName',                  ctypes.c_char * 64),
        ('mTrackName',                    ctypes.c_char * 64),
        ('mPos',                          RF2Vec3),
        ('mLocalVel',                     RF2Vec3),
        ('mLocalAccel',                   RF2Vec3),
        ('mOri',                          RF2Vec3 * 3),
        ('mLocalRot',                     RF2Vec3),
        ('mLocalRotAccel',                RF2Vec3),
        ('mGear',                         ctypes.c_int32),
        ('_pad2',                         ctypes.c_uint8 * 4),
        ('mEngineRPM',                    ctypes.c_double),
        ('mEngineWaterTemp',              ctypes.c_double),
        ('mEngineOilTemp',                ctypes.c_double),
        ('mClutchRPM',                    ctypes.c_double),
        ('mUnfilteredThrottle',           ctypes.c_double),
        ('mUnfilteredBrake',              ctypes.c_double),
        ('mUnfilteredSteering',           ctypes.c_double),
        ('mUnfilteredClutch',             ctypes.c_double),
        ('mFilteredThrottle',             ctypes.c_double),
        ('mFilteredBrake',                ctypes.c_double),
        ('mFilteredSteering',             ctypes.c_double),
        ('mFilteredClutch',               ctypes.c_double),
        ('mSteeringShaftTorque',          ctypes.c_double),
        ('mFront3rdDeflection',           ctypes.c_double),
        ('mRear3rdDeflection',            ctypes.c_double),
        ('mFrontWingHeight',              ctypes.c_double),
        ('mFrontRideHeight',              ctypes.c_double),
        ('mRearRideHeight',               ctypes.c_double),
        ('mDrag',                         ctypes.c_double),
        ('mFrontDownforce',               ctypes.c_double),
        ('mRearDownforce',                ctypes.c_double),
        ('mFuel',                         ctypes.c_double),
        ('mEngineMaxRPM',                 ctypes.c_double),
        ('mScheduledStops',               ctypes.c_uint8),
        ('mOverheating',                  ctypes.c_bool),
        ('mDetached',                     ctypes.c_bool),
        ('mHeadlights',                   ctypes.c_uint8),
        ('mDentSeverity',                 ctypes.c_uint8 * 8),
        ('_pad3',                         ctypes.c_uint8 * 4),
        ('mLastImpactET',                 ctypes.c_double),
        ('mLastImpactMagnitude',          ctypes.c_double),
        ('mLastImpactPos',                RF2Vec3),
        ('mEngineTorque',                 ctypes.c_double),
        ('mCurrentSector',                ctypes.c_int32),
        ('mSpeedLimiter',                 ctypes.c_uint8),
        ('mMaxGears',                     ctypes.c_uint8),
        ('mFrontTireCompoundIndex',       ctypes.c_uint8),
        ('mRearTireCompoundIndex',        ctypes.c_uint8),
        ('mFuelCapacity',                 ctypes.c_double),
        ('mFrontFlapActivated',           ctypes.c_uint8),
        ('mRearFlapActivated',            ctypes.c_uint8),
        ('mRearFlapLegalStatus',          ctypes.c_uint8),
        ('mIgnitionStarter',              ctypes.c_uint8),
        ('mFrontTireCompoundName',        ctypes.c_char * 18),
        ('mRearTireCompoundName',         ctypes.c_char * 18),
        ('mSpeedLimiterAvailable',        ctypes.c_uint8),
        ('mAntiStallActivated',           ctypes.c_uint8),
        ('mUnused',                       ctypes.c_uint8 * 2),
        ('mVisualSteeringWheelRange',     ctypes.c_float),
        ('_pad4',                         ctypes.c_uint8 * 4),
        ('mRearBrakeBias',                ctypes.c_double),
        ('mTurboBoostPressure',           ctypes.c_double),
        ('mPhysicsToGraphicsOffset',      ctypes.c_float * 3),
        ('mPhysicalSteeringWheelRange',   ctypes.c_float),
        ('mBatteryChargeFraction',        ctypes.c_double),
        ('mElectricBoostMotorTorque',     ctypes.c_double),
        ('mElectricBoostMotorRPM',        ctypes.c_double),
        ('mElectricBoostMotorTemperature',ctypes.c_double),
        ('mElectricBoostWaterTemperature',ctypes.c_double),
        ('mElectricBoostMotorState',      ctypes.c_uint8),
        ('mExpansion',                    ctypes.c_uint8 * 111),
        ('mWheels',                       RF2Wheel * 4),
    ]


class RF2TelemetryBuffer(ctypes.Structure):
    _fields_ = [
        ('mVersionUpdateBegin', ctypes.c_uint32),
        ('mVersionUpdateEnd',   ctypes.c_uint32),
        ('mBytesUpdatedHint',   ctypes.c_int32),
        ('_pad_hdr',            ctypes.c_uint8 * 4),
        ('mVehicles',           RF2VehicleTelemetry * 128),
    ]


# ---------------------------------------------------------------------------
# Scoring バッファ
# ---------------------------------------------------------------------------

class RF2VehicleScoring(ctypes.Structure):
    _fields_ = [
        ('mID',                 ctypes.c_int32),
        ('mDriverName',         ctypes.c_char * 32),
        ('mVehicleName',        ctypes.c_char * 64),
        ('mTotalLaps',          ctypes.c_int16),
        ('mSector',             ctypes.c_int8),
        ('mFinishStatus',       ctypes.c_int8),
        ('mLapDist',            ctypes.c_double),
        ('mPathLateral',        ctypes.c_double),
        ('mTrackEdge',          ctypes.c_double),
        ('mBestSector1',        ctypes.c_double),
        ('mBestSector2',        ctypes.c_double),
        ('mBestLapTime',        ctypes.c_double),
        ('mLastSector1',        ctypes.c_double),
        ('mLastSector2',        ctypes.c_double),
        ('mLastLapTime',        ctypes.c_double),
        ('mCurSector1',         ctypes.c_double),
        ('mCurSector2',         ctypes.c_double),
        ('mNumPitstops',        ctypes.c_int16),
        ('mNumPenalties',       ctypes.c_int16),
        ('mIsPlayer',           ctypes.c_bool),
        ('mControl',            ctypes.c_int8),
        ('mInPits',             ctypes.c_bool),
        ('mPlace',              ctypes.c_uint8),
        ('mVehicleClass',       ctypes.c_char * 32),
        ('mTimeBehindNext',     ctypes.c_double),
        ('mLapsBehindNext',     ctypes.c_int32),
        ('_pad_s1',             ctypes.c_uint8 * 4),
        ('mTimeBehindLeader',   ctypes.c_double),
        ('mLapsBehindLeader',   ctypes.c_int32),
        ('_pad_s2',             ctypes.c_uint8 * 4),
        ('mLapStartET',         ctypes.c_double),
        ('mPos',                RF2Vec3),
        ('mLocalVel',           RF2Vec3),
        ('mLocalAccel',         RF2Vec3),
        ('mOri',                RF2Vec3 * 3),
        ('mLocalRot',           RF2Vec3),
        ('mLocalRotAccel',      RF2Vec3),
        ('mHeadlights',         ctypes.c_uint8),
        ('mPitState',           ctypes.c_uint8),
        ('mServerScored',       ctypes.c_uint8),
        ('mIndividualPhase',    ctypes.c_uint8),
        ('mQualification',      ctypes.c_int32),
        ('mTimeIntoLap',        ctypes.c_double),
        ('mEstimatedLapTime',   ctypes.c_double),
        ('mPitGroup',           ctypes.c_char * 24),
        ('mFlag',               ctypes.c_uint8),
        ('mUnderYellow',        ctypes.c_bool),
        ('mCountLapFlag',       ctypes.c_uint8),
        ('mInGarageStall',      ctypes.c_bool),
        ('mUpgradePack',        ctypes.c_uint8 * 16),
        ('mPitLapDist',         ctypes.c_float),
        ('mBestLapSector1',     ctypes.c_float),
        ('mBestLapSector2',     ctypes.c_float),
        ('mExpansion',          ctypes.c_uint8 * 48),
    ]


class RF2ScoringInfo(ctypes.Structure):
    _fields_ = [
        ('mTrackName',          ctypes.c_char * 64),
        ('mSession',            ctypes.c_int32),
        ('_pad_si0',            ctypes.c_uint8 * 4),
        ('mCurrentET',          ctypes.c_double),
        ('mEndET',              ctypes.c_double),
        ('mMaxLaps',            ctypes.c_double),
        ('mLapDist',            ctypes.c_double),
        ('_ptr1',               ctypes.c_uint8 * 8),   # MM_NEW pointer (skip)
        ('mNumVehicles',        ctypes.c_int32),
        ('mGamePhase',          ctypes.c_uint8),
        ('mYellowFlagState',    ctypes.c_int8),
        ('mSectorFlag',         ctypes.c_int8 * 3),
        ('mStartLight',         ctypes.c_uint8),
        ('mNumRedLights',       ctypes.c_uint8),
        ('mInRealtime',         ctypes.c_bool),
        ('mPlayerName',         ctypes.c_char * 32),
        ('mPlrFileName',        ctypes.c_char * 64),
        ('mDarkCloud',          ctypes.c_double),
        ('mRaining',            ctypes.c_double),
        ('mAmbientTemp',        ctypes.c_double),
        ('mTrackTemp',          ctypes.c_double),
        ('mWind',               RF2Vec3),
        ('mMinPathWetness',     ctypes.c_double),
        ('mMaxPathWetness',     ctypes.c_double),
        ('mGameMode',           ctypes.c_uint8),
        ('mIsPasswordProtected',ctypes.c_bool),
        ('mServerPort',         ctypes.c_uint16),
        ('mServerPublicIP',     ctypes.c_uint32),
        ('mMaxPlayers',         ctypes.c_int32),
        ('mServerName',         ctypes.c_char * 32),
        ('mStartET',            ctypes.c_float),
        ('_pad_si1',            ctypes.c_uint8 * 4),
        ('mAvgPathWetness',     ctypes.c_double),
        ('mExpansion',          ctypes.c_uint8 * 200),
        ('_ptr2',               ctypes.c_uint8 * 8),   # MM_NEW pointer (skip)
    ]


class RF2ScoringBuffer(ctypes.Structure):
    _fields_ = [
        ('mVersionUpdateBegin', ctypes.c_uint32),
        ('mVersionUpdateEnd',   ctypes.c_uint32),
        ('mBytesUpdatedHint',   ctypes.c_int32),
        ('_pad_hdr',            ctypes.c_uint8 * 4),
        ('mScoringInfo',        RF2ScoringInfo),
        ('mVehicles',           RF2VehicleScoring * 128),
    ]


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def vec3_speed_kmh(v: RF2Vec3) -> float:
    """ローカル速度ベクトルから km/h を計算する。"""
    return math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2) * 3.6


def kelvin_to_celsius(k: float) -> float:
    return k - 273.15


def tire_temp_mid_celsius(wheel: RF2Wheel) -> float:
    """タイヤ温度の中央値（中間バンド）を摂氏で返す。"""
    return kelvin_to_celsius(wheel.mTemperature[1])
