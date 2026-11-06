"""Timer-only host events; no invented program opcode or CPU fallback policy.

G pp109/113/117: STOP does not freeze timers, a power outage does, a warm
restart preserves V/P, a cold restart clears V/Q and restores configured P.
The owner supplies monotonically increasing elapsed wall time. Event handling
is outside a scan. Other resource resets and physical outputs belong to the
controller lifecycle adapter, not to this timer-family component.
"""

from .model import fail

EVENT_CODES = {"stop": 1, "run": 2, "power_off": 3, "warm_restart": 4, "cold_restart": 5}
EVENTS = frozenset(EVENT_CODES)


def elapsed(value):
    if type(value) is not int or value < 0:
        fail("timer elapsed time must be a nonnegative integer in milliseconds")
    return value


class TimerLifecycle:
    def __init__(self, timers):
        self.timers = timers
        self.running = True
        self.powered = True

    def refresh(self, now):
        elapsed(now)
        for timer in self.timers.values():
            timer.refresh(now)

    def apply(self, event, now):
        if type(event) is not str or event not in EVENTS:
            fail("unsupported timer lifecycle event: " + str(event))
        elapsed(now)
        if event == "run" and not self.powered:
            fail("timer RUN requires warm_restart or cold_restart after power_off")
        self.refresh(now)
        if event == "stop":
            self.running = False
        elif event == "run":
            self.running = True
        elif event == "power_off":
            for timer in self.timers.values():
                timer.power_off(now)
            self.running = self.powered = False
        elif event == "warm_restart":
            for timer in self.timers.values():
                timer.warm_restart(now)
            self.running = self.powered = True
        else:
            for timer in self.timers.values():
                timer.cold_restart(now)
            self.running = self.powered = True
