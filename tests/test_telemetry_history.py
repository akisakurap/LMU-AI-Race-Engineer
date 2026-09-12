import pytest

from telemetry_history import TelemetryHistory


def sample(lap, fuel, **extra):
    return dict(TrackName='Le Mans', Session=10, TotalLaps=lap, Fuel=fuel,
                InPits=False, **extra)


def test_fuel_estimate_uses_complete_laps_only():
    history = TelemetryHistory()
    assert 'FuelPerLap' not in history.update(sample(1, 50), 0)
    assert 'FuelPerLap' not in history.update(sample(2, 48), 10)
    result = history.update(sample(3, 44), 20)
    assert result['FuelPerLap'] == 4
    assert result['FuelLapsEstimate'] == 11


def test_refuel_and_session_restart_clear_estimate():
    history = TelemetryHistory()
    for lap, fuel in [(1, 50), (2, 48), (3, 44)]:
        history.update(sample(lap, fuel), lap * 10)
    assert 'FuelPerLap' not in history.update(sample(3, 60), 35)
    assert 'FuelPerLap' not in history.update(sample(1, 55), 40)


def test_skipped_laps_do_not_create_fuel_estimate():
    history = TelemetryHistory()
    history.update(sample(1, 50), 0)
    history.update(sample(2, 48), 10)
    assert 'FuelPerLap' not in history.update(sample(4, 40), 30)


def test_gap_and_tyre_trends_include_time_window():
    history = TelemetryHistory()
    history.update(sample(1, 50, GapToFront=3.0, TyreTemp=[90]*4), 0)
    result = history.update(sample(1, 49, GapToFront=2.0, TyreTemp=[92]*4), 10)
    assert result['GapToFrontChange'] == -1
    assert result['TyreTempChange'] == [2]*4
    assert result['TrendWindowSec'] == 10


def test_missing_data_resets_history_and_does_not_mutate_input():
    history = TelemetryHistory()
    data = sample(1, 50)
    history.update(data, 0)
    assert 'CapturedAt' not in data
    assert history.update({}, 10) == {}
    result = history.update(sample(4, 40), 20)
    assert 'FuelPerLap' not in result


def test_gap_trend_is_not_compared_across_position_change():
    history = TelemetryHistory()
    history.update(sample(1, 50, Position=3, GapToFront=3.0), 0)
    result = history.update(sample(1, 49, Position=2, GapToFront=10.0), 10)
    assert 'GapToFrontChange' not in result
