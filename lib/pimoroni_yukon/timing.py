from supervisor import ticks_ms

TICKS_PERIOD = const(1 << 29)
TICKS_MAX = const(TICKS_PERIOD - 1)
TICKS_HALFPERIOD = const(TICKS_PERIOD // 2)


# ticks_ms usage functions from: https://docs.circuitpython.org/en/latest/shared-bindings/supervisor/index.html#supervisor.ticks_ms
def ticks_add(ticks, delta):
    "Add a delta to a base number of ticks, performing wraparound at 2**29ms."
    return (ticks + delta) % TICKS_PERIOD


def ticks_diff(ticks1, ticks2):
    "Compute the signed difference between two ticks values, assuming that they are within 2**28 ticks"
    diff = (ticks1 - ticks2) & TICKS_MAX
    diff = ((diff + TICKS_HALFPERIOD) & TICKS_MAX) - TICKS_HALFPERIOD
    return diff


# Handy class for performing consistent time intervals
class RollingTime:
    def __init__(self):
        self.reset()

    def reset(self):
        self.ticks = ticks_ms()

    def advance(self, seconds):
        # Convert and handle the advance as milliseconds
        self.advance_ms(1000.0 * seconds + 0.5)

    def advance_ms(self, ms):
        if ms < 0:
            raise ValueError("advance length must be non-negative")

        self.ticks = ticks_add(self.ticks, int(ms))

    def reached(self):
        return ticks_diff(ticks_ms(), self.ticks) >= 0

    def value(self):
        return self.ticks


# Inspired by the Arduino Metro library: https://github.com/thomasfredericks/Metro-Arduino-Wiring
class TimeChecker:
    def __init__(self, interval=1.0):
        if interval <= 0:
            raise ValueError("interval must be positive")

        self.interval = int(1000.0 * interval + 0.5)
        self.restart()

    def restart(self):
        self.ticks = ticks_ms()

    def new_interval(self, interval):
        if interval <= 0:
            raise ValueError("interval must be positive")

        self.new_interval_ms(1000.0 * interval + 0.5)

    def new_interval_ms(self, interval):
        if interval <= 0:
            raise ValueError("interval must be positive")

        self.interval = int(interval)

    def check(self):
        current = ticks_ms()
        if ticks_diff(current, self.ticks) >= self.interval:
            self.ticks = current
            # without catchup would be: self.ticks = ticks_add(self.ticks, self.interval)
            return True
        return False
