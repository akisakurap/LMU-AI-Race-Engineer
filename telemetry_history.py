"""Bounded, session-local estimates derived from sampled telemetry."""
from collections import deque
import math


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


class TelemetryHistory:
    def __init__(self):
        self.previous = None
        self.lap_start = None
        self.consumption = deque(maxlen=5)
        self.samples = deque(maxlen=120)

    def update(self, data, now):
        if not data:
            self.__init__()
            return {}
        previous = self.previous
        identity = ('TrackName', 'Session', 'PlayerID', 'VehicleClass')
        if previous and (
            any(data.get(key) != previous.get(key) for key in identity)
            or data.get('TotalLaps', 0) < previous.get('TotalLaps', 0)
            or data.get('SessionElapsed', 0) < previous.get('SessionElapsed', 0)
        ):
            self.__init__()
            previous = None

        fuel, lap = data.get('Fuel'), data.get('TotalLaps')
        old_fuel = previous.get('Fuel') if previous else None
        if (not _number(fuel) or fuel < 0 or data.get('InPits')
                or (_number(old_fuel) and fuel > old_fuel + 0.05)):
            self.lap_start = None
            self.consumption.clear()
        elif previous and _number(lap) and lap != previous.get('TotalLaps'):
            if self.lap_start and lap == self.lap_start[0] + 1:
                used = self.lap_start[1] - fuel
                if used > 0:
                    self.consumption.append(used)
            else:
                self.consumption.clear()
            self.lap_start = (lap, fuel)

        result = dict(data)
        if self.consumption:
            per_lap = sum(self.consumption) / len(self.consumption)
            result['FuelPerLap'] = round(per_lap, 3)
            result['FuelLapsEstimate'] = round(fuel / per_lap, 1)

        while self.samples and now - self.samples[0][0] > 30:
            self.samples.popleft()
        if self.samples:
            then, baseline = self.samples[0]
            if now - then >= 5:
                result['TrendWindowSec'] = round(now - then, 1)
                gap, old_gap = data.get('GapToFront'), baseline.get('GapToFront')
                if (_number(gap) and _number(old_gap)
                        and data.get('Position') == baseline.get('Position')):
                    result['GapToFrontChange'] = round(gap - old_gap, 3)
                temps, old_temps = data.get('TyreTemp'), baseline.get('TyreTemp')
                if (temps and old_temps and len(temps) == len(old_temps) == 4
                        and all(_number(t) for t in [*temps, *old_temps])):
                    result['TyreTempChange'] = [round(a-b, 1) for a, b in zip(temps, old_temps)]
        self.samples.append((now, dict(data)))
        self.previous = dict(data)
        return result
