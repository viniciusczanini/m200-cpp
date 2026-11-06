"""Native timer properties, mode state and documented timer lifecycle hooks.

Tick phase is activation/resume relative, a local policy pending native traces.
"""

import re

from .model import fail

NUMERIC_PATTERN = r"%TM(?:0|[1-9][0-9]*)\.(?:P|V)"
REFERENCE = re.compile(r"%TM(0|[1-9][0-9]*)\.(P|V|Q)")
GETTERS = {"P": "preset", "V": "value", "Q": "done"}


def reference(text, writable=False):
    if not text.startswith("%TM"):
        return None
    match = REFERENCE.fullmatch(text)
    if not match or int(match[1]) >= 255:
        fail("unsupported timer property: " + text)
    if writable and match[2] != "P":
        fail("timer value/output is read-only: " + text)
    return int(match[1]), match[2]


def preset_value(value):
    if type(value) is not int or not 0 <= value <= 9999:
        fail("timer preset outside 0..9999; native invalid-value effects unverified")
    return value


class TimerState:
    def __init__(self, config):
        self.kind = config.kind
        self.base = config.base_ms
        self.initial_preset = config.preset
        self.preset = config.preset
        self.retentive = config.retentive
        self.dynamic = config.dynamic_preset
        self.active_preset = self.preset
        self.start = None
        self.previous = False
        self.q = False
        self.current = 0
        self.processed_ticks = 0
        self.completed = False
        self.offline_since = None

    def cold_restart(self, now):
        self.preset = self.initial_preset
        self.active_preset = self.preset
        self.start = None
        self.previous = self.q = self.completed = False
        self.current = self.processed_ticks = 0
        self.offline_since = None

    def power_off(self, now):
        if self.offline_since is None:
            self.refresh(now)
            self.offline_since = now

    def warm_restart(self, now):
        if self.offline_since is not None:
            if now < self.offline_since:
                fail("timer lifecycle clock moved backwards")
            if self.start is not None:
                self.start += now - self.offline_since
            self.offline_since = None
        self.refresh(now)

    def complete(self):
        self.completed = True
        self.q = self.kind == "TON"
        if self.kind != "TON":
            self.start = None

    def refresh(self, now):
        if self.offline_since is not None:
            return
        if self.start is not None and now < self.start:
            fail("timer clock moved backwards")
        if self.start is not None and not self.completed:
            ticks = (now - self.start) // self.base
            delta = ticks - self.processed_ticks
            if delta > 0:
                if self.dynamic:
                    self.active_preset = self.preset
                # A decrease below V completes at the next tick, preserving V.
                if self.current < self.active_preset:
                    self.current += min(delta, self.active_preset - self.current)
                self.processed_ticks = ticks
                if self.current >= self.active_preset:
                    self.complete()
        if self.kind == "TP" and self.start is None and not self.previous:
            self.current = 0

    def read(self, field, now):
        self.refresh(now)
        return {"P": self.preset, "V": self.current, "Q": self.q}[field]

    def set_preset(self, value, now):
        if self.offline_since is not None:
            fail("timer preset write while power is off")
        preset_value(value)
        self.refresh(now)
        self.preset = value
        paused = not self.previous if self.kind == "TON" else self.previous
        if (
            self.retentive
            and self.dynamic
            and self.start is None
            and paused
            and value < self.current
        ):
            self.current = 0

    def begin(self, now):
        self.start = now
        self.active_preset = self.preset
        self.processed_ticks = 0
        self.completed = False
        if not self.retentive:
            self.current = 0
        if self.current >= self.active_preset:
            self.complete()

    def update(self, enabled, now):
        if self.offline_since is not None:
            fail("timer IN update while power is off")
        self.refresh(now)
        if self.kind == "TON":
            if not enabled:
                if not self.retentive or self.completed:
                    self.current = 0
                self.start, self.q = None, False
                self.completed = False
            elif self.start is None:
                self.begin(now)
        elif self.kind == "TOF":
            if enabled:
                if not self.retentive or self.completed:
                    self.current = 0
                self.start, self.q = None, True
                self.completed = False
            elif self.previous:
                self.begin(now)
        elif enabled and not self.previous and self.start is None:
            self.q = True
            self.begin(now)
        self.previous = enabled
        self.refresh(now)
        return self.q
