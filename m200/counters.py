"""Native %C grammar and explicitly provisional per-instruction local model."""

import re
from dataclasses import dataclass
from .model import fail

NUMERIC_PATTERN = r"%C(?:0|[1-9][0-9]*)\.(?:P|V)"
REFERENCE = re.compile(r"%C(0|[1-9][0-9]*)\.(P|V|E|D|F)")
ACTIONS = ("R", "S", "CU", "CD")
METHODS = {"reset": "R", "set": "S", "count_up": "CU", "count_down": "CD"}
GETTERS = {"P": "preset", "V": "value", "E": "empty", "D": "done", "F": "full"}


def preset_value(value):
    if type(value) is not int or not 0 <= value <= 9999:
        fail("counter preset outside 0..9999; native invalid-value effects unverified")
    return value


@dataclass
class Counter:
    preset: int = 9999

    def __post_init__(self):
        preset_value(self.preset)


def index(text):
    m = re.fullmatch(r"%C(0|[1-9][0-9]*)", text)
    if not m or int(m[1]) >= 255:
        fail("invalid native counter address: " + text)
    return int(m[1])


def reference(text, writable=False):
    if not text.startswith("%C"):
        return None
    m = REFERENCE.fullmatch(text)
    if not m or int(m[1]) >= 255:
        fail("unsupported counter property: " + text)
    if writable and m[2] != "P":
        fail("counter value/output is read-only: " + text)
    return int(m[1]), m[2]


def body(rung):
    rung = [" ".join(line.split()) for line in rung]
    if not rung or not rung[0].startswith("BLK %C"):
        return None
    target = rung[0].split(maxsplit=1)[1]
    index(target)
    if rung[-1] != "END_BLK" or any(line.startswith("BLK ") for line in rung[1:]):
        fail("invalid counter block structure")
    result = []
    output = False
    actions = 0
    for line in rung[1:-1]:
        if line == "OUT_BLK":
            if output or not actions:
                fail("invalid counter output section")
            output = True
            continue
        parts = line.split(maxsplit=1)
        op = parts[0] if parts else ""
        arg = parts[1] if len(parts) == 2 else ""
        if not output and op in ACTIONS and not arg:
            result.append(op + " " + target)
            actions += 1
        elif output and arg in ("E", "D", "F"):
            result.append(op + " " + target + "." + arg)
        else:
            result.append(line)
    if not actions:
        fail("counter block has no input action")
    return result


class CounterState:
    """Policy in docs/capabilities/COUNTERS.md; not a hardware-certified model."""

    def __init__(self, config):
        self.preset = config.preset
        self.current = 0
        self.empty = self.done = self.full = False
        self.reset = self.set = False
        self.previous_up = self.previous_down = False

    def read(self, field):
        return {
            "P": self.preset,
            "V": self.current,
            "E": self.empty,
            "D": self.done,
            "F": self.full,
        }[field]

    def set_preset(self, value):
        self.preset = preset_value(value)

    def action(self, pin, enabled):
        if pin not in ACTIONS:
            fail("unsupported counter action: " + pin)
        enabled = bool(enabled)
        rising = False
        if pin == "R":
            self.reset = enabled
        elif pin == "S":
            self.set = enabled
        elif pin == "CU":
            rising = enabled and not self.previous_up
            self.previous_up = enabled
        else:
            rising = enabled and not self.previous_down
            self.previous_down = enabled
        if self.reset:
            self.current = 0
            self.empty = self.done = self.full = False
        elif self.set:
            self.current = self.preset
            self.done = True
        elif pin in ("CU", "CD") and enabled:
            if rising and pin == "CU":
                self.current = (self.current + 1) % 10000
                self.full = self.current == 0
            elif rising:
                self.current = (self.current - 1) % 10000
                self.empty = self.current == 9999
            self.done = self.current == self.preset
