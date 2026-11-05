"""Closed timer properties and the nonretentive, nondynamic local time model."""

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
        self.preset = config.preset
        self.active_preset = self.preset
        self.start = None
        self.previous = False
        self.q = False
        self.current = 0

    def refresh(self, now):
        if self.start is not None:
            ticks = (now - self.start) // self.base
            self.current = min(ticks, self.active_preset)
            if ticks >= self.active_preset:
                self.q = self.kind == "TON"
                if self.kind != "TON":
                    self.start = None
        if self.kind == "TP" and self.start is None and not self.previous:
            self.current = 0

    def read(self, field, now):
        self.refresh(now)
        return {"P": self.preset, "V": self.current, "Q": self.q}[field]

    def set_preset(self, value):
        self.preset = preset_value(value)

    def begin(self, now):
        self.start = now
        self.active_preset = self.preset
        self.current = 0

    def update(self, enabled, now):
        self.refresh(now)
        if self.kind == "TON":
            if not enabled:
                self.start, self.current, self.q = None, 0, False
            elif self.start is None:
                self.begin(now)
        elif self.kind == "TOF":
            if enabled:
                self.start, self.current, self.q = None, 0, True
            elif self.previous:
                self.begin(now)
        elif enabled and not self.previous and self.start is None:
            self.begin(now)
            self.q = True
        self.previous = enabled
        self.refresh(now)
        return self.q
