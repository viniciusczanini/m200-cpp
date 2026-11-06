"""Native DR/SBR/SC domains. Documentary runtime paths only; no guessed collisions.

Sources: EIO0000003289.04 pp147-158; EIO0000002019.06 pp21,25.
The local VM intentionally stops on undocumented endpoint/collision behavior.
Native emission can still represent those programs; this is a simulator gap.
"""

import re
from dataclasses import dataclass, field
from .model import fail

FAMILIES = {"SBR": "shift_bit_registers", "SC": "step_counters", "DR": "drums"}
CLASSES = {"SBR": "ShiftBitRegister", "SC": "StepCounter", "DR": "Drum"}
PINS = {"SBR": ("R", "CU", "CD"), "SC": ("R", "CU", "CD"), "DR": ("R", "U")}
NUMERIC_PATTERN = r"%DR(?:0|[1-9][0-9]*)\.S"
REFERENCE = re.compile(r"%(SBR|SC|DR)(0|[1-9][0-9]*)\.(0|[1-9][0-9]*|S|F)(?![0-9A-Za-z_.])")
INDEX = re.compile(r"%(SBR|SC|DR)(0|[1-9][0-9]*)")
INTERNAL_PINS = ("SEQ_R", "SEQ_CU", "SEQ_CD", "SEQ_U", "SEQ_COMMIT")


def identity(text):
    match = INDEX.fullmatch(text)
    if not match or int(match[2]) >= 8:
        fail("native sequence identity must be SBR/SC/DR0..7: " + text)
    return match[1], int(match[2])


def reference(text, writable=False):
    if not text.startswith(("%SBR", "%SC", "%DR")) or text.startswith("%SCH"):
        return None
    match = REFERENCE.fullmatch(text)
    if not match or int(match[2]) >= 8:
        fail("unsupported native sequence property: " + text)
    family, index, prop = match[1], int(match[2]), match[3]
    if family == "DR":
        if prop not in ("S", "F") or (writable and prop != "S"):
            fail("Drum requires RW .S or readonly .F: " + text)
    elif not prop.isascii() or not prop.isdecimal() or int(prop) >= (16 if family == "SBR" else 256):
        fail("native sequence bit outside its documented domain: " + text)
    return family, index, prop


def _symbols(values, count):
    if not isinstance(values, (tuple, list)) or len(values) != count or any(
        value is not None and type(value) is not str for value in values
    ):
        fail("invalid native sequence symbols")
    return list(values)


@dataclass
class ShiftBitRegisterConfig:
    bit_symbols: list = field(default_factory=lambda: [None] * 16)
    last_writen_bit: int = 0  # Native spelling; UI persistence, never runtime state.

    def __post_init__(self):
        self.bit_symbols = _symbols(self.bit_symbols, 16)
        if type(self.last_writen_bit) is not int or self.last_writen_bit != 0:
            fail("invalid persisted SBR LastWritenBit")


@dataclass
class StepCounterConfig:
    step_symbols: list = field(default_factory=lambda: [None] * 256)

    def __post_init__(self):
        self.step_symbols = _symbols(self.step_symbols, 256)


@dataclass
class DrumCam:
    slot: int
    output: str
    mask: int

    def __post_init__(self):
        from .model import address
        if type(self.slot) is not int or not 0 <= self.slot < 16:
            fail("Drum cam slot must be 0..15")
        if type(self.mask) is not int or not 0 <= self.mask < 256:
            fail("Drum cam mask must be an eight-bit literal")
        if type(self.output) is not str or address(self.output, True)[0] not in ("M", "Q0."):
            fail("Drum output must be a target M or Q0 bit")


@dataclass
class DrumConfig:
    steps: int = 8
    cams: list = field(default_factory=list)

    def __post_init__(self):
        if type(self.steps) is not int or not 1 <= self.steps <= 8:
            fail("Drum step count must be 1..8")
        if not isinstance(self.cams, list):
            fail("Drum cams must be a list")
        self.cams = [DrumCam(**c) if isinstance(c, dict) else c for c in self.cams]
        if any(not isinstance(c, DrumCam) for c in self.cams):
            fail("invalid Drum cam configuration")
        if len({c.slot for c in self.cams}) != len(self.cams):
            fail("duplicate Drum cam slot")
        # Output aliasing is retained for native emission. Local execution refuses
        # conflicting values rather than silently selecting a column priority.
        self.cams.sort(key=lambda cam: cam.slot)


CONFIGS = {"SBR": ShiftBitRegisterConfig, "SC": StepCounterConfig, "DR": DrumConfig}


def configurations_from_json(raw, family):
    if not isinstance(raw, dict) or any(k not in tuple(str(i) for i in range(8)) for k in raw):
        fail("invalid " + family + " configuration identity map")
    result = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            fail("invalid " + family + " configuration JSON")
        try:
            result[int(key)] = CONFIGS[family](**value)
        except (TypeError, ValueError):
            fail("invalid " + family + " configuration JSON")
    return result


def validate_configs(program):
    for family, name in FAMILIES.items():
        configs = getattr(program, name)
        if not isinstance(configs, dict):
            fail("invalid " + family + " configuration mapping")
        for i, cfg in configs.items():
            if type(i) is not int or not 0 <= i < 8 or type(cfg) is not CONFIGS[family]:
                fail("invalid " + family + " configuration")
            from dataclasses import asdict
            CONFIGS[family](**asdict(cfg))
    for raw in program.rungs:
        for line in raw:
            for match in REFERENCE.finditer(line):
                family, i, _ = reference(match[0])
                if i not in getattr(program, FAMILIES[family]):
                    fail("undefined native sequence property: " + match[0])
            if line.startswith("BLK %") and INDEX.fullmatch(line[4:]):
                family, i = identity(line[4:])
                if i not in getattr(program, FAMILIES[family]):
                    fail("undefined native sequence block: " + line[4:])


def parse_body(rung):
    """Decode ordered *present* pins, preserving omission rather than filling it.

    Generic pp155/157 explicitly shows partial pins. Every present expression is
    evaluated before a single block commit. Outputs observe the committed state.
    The raw native rungs remain the canonical source for reverse and export.
    """
    if not rung or not rung[0].startswith(("BLK %SBR", "BLK %SC", "BLK %DR")):
        return None
    key = rung[0].split(maxsplit=1)[1]
    family, _ = identity(key)
    if rung[-1] != "END_BLK" or any(line.startswith("BLK ") or line.split(maxsplit=1)[0].startswith(("SEQ_", "REG_")) for line in rung[1:]):
        fail("invalid native sequence block structure")
    from .native_logic import decode, LOGIC, OPEN, STACK, STORES
    result, group, used = [], [], []
    output = False
    output_lines = []
    for line in rung[1:-1]:
        if line == "OUT_BLK":
            if output or family != "DR" or group or not used:
                fail("invalid sequence OUT_BLK")
            output = True
            result.append("SEQ_COMMIT " + key)
        elif not output and line in PINS[family]:
            if not group or (used and PINS[family].index(line) <= PINS[family].index(used[-1])):
                fail("native sequence requires ordered unique present pins")
            checked = decode(group + ["ST %M0"])
            if any(op not in (*LOGIC, *OPEN, "N", ")") for op, _ in checked[:-1]):
                fail("sequence input requires pure balanced boolean logic")
            result += group + ["SEQ_" + line + " " + key]
            used.append(line)
            group = []
        elif output:
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[1] == "F":
                line = parts[0] + " " + key + ".F"
            output_lines.append(line)
            result.append(line)
        else:
            group.append(line)
    if group or not used:
        fail("sequence block requires at least one complete input group")
    if output:
        if not output_lines or any(op not in (*LOGIC, *OPEN, *STACK, *STORES, "N", ")", "NUM") for op, _ in decode(output_lines)):
            fail("unsupported native sequence output action")
    if not output:
        result.append("SEQ_COMMIT " + key)
    return result


def referenced_ids(rungs, family):
    ids = set()
    for rung in rungs:
        for line in rung:
            ids.update(int(m[2]) for m in REFERENCE.finditer(line) if m[1] == family)
            if line.startswith("BLK %") and INDEX.fullmatch(line[4:]):
                f, i = identity(line[4:])
                if f == family:
                    ids.add(i)
    return ids


class DirectionState:
    def __init__(self):
        self.pins = {"R": False, "CU": False, "CD": False}

    def edges(self, values):
        if any(value and pin not in values for pin, value in self.pins.items()):
            fail("omitted active sequence pin/history requires native qualification")
        up, down = values.get("CU"), values.get("CD")
        r = values.get("R", self.pins["R"])
        cu = up is not None and up and not self.pins["CU"]
        cd = down is not None and down and not self.pins["CD"]
        if (r and (values.get("CU", False) or values.get("CD", False))) or (cu and cd):
            fail("unresolved native sequence reset/direction collision; native qualification required")
        if r and any(self.pins[p] for p in ("CU", "CD")):
            fail("unresolved native sequence reset request-history interaction")
        self.pins.update(values)
        return r, cu, cd


class ShiftBitRegisterState(DirectionState):
    def __init__(self, config):
        super().__init__()
        self.value = 0

    def read(self, prop):
        return bool(self.value & (1 << int(prop)))

    def write(self, prop, value):
        mask = 1 << int(prop)
        self.value = (self.value | mask) if value else (self.value & ~mask)

    def update(self, values, write_bit=None):
        reset, up, down = self.edges(values)
        if reset:
            self.value = 0
        elif up:
            if self.value & 1:
                fail("SBR vacated bit0 fill is unresolved for a set endpoint")
            self.value = (self.value << 1) & 0xffff
        elif down:
            if self.value & 0x8000:
                fail("SBR vacated bit15 fill is unresolved for a set endpoint")
            self.value >>= 1


class StepCounterState(DirectionState):
    def __init__(self, config):
        super().__init__()
        self.current = 0

    def read(self, prop):
        return self.current == int(prop)

    def write(self, prop, value):
        bit = int(prop)
        if (value and self.current != bit) or (not value and self.current == bit):
            fail("SC active-step-changing assignment requires native qualification")

    def update(self, values, write_bit=None):
        reset, up, down = self.edges(values)
        if reset:
            self.current = 0
        elif up or down:
            if self.current == -1 or (up and self.current == 255) or (down and self.current == 0):
                fail("SC endpoint/no-active-step transition requires native qualification")
            self.current += 1 if up else -1


class DrumState:
    def __init__(self, config):
        self.config = config
        self.current = 0
        self.pending = None
        self.pins = {"R": False, "U": False}
        self.initialized = False

    def read(self, prop):
        return self.current if prop == "S" else self.current == self.config.steps - 1

    def write(self, prop, value):
        if prop != "S" or type(value) is not int or not 0 <= value <= 7:
            fail("Drum step assignment requires decimal immediate 0..7")
        self.pending = value

    def initialize_outputs(self, write_bit):
        writes = {}
        for cam in self.config.cams:
            value = bool(cam.mask & 1)
            if cam.output in writes and writes[cam.output] != value:
                fail("conflicting aliased Drum cams require native qualification")
            writes[cam.output] = value
        for output, value in writes.items():
            write_bit(output, value)
        self.initialized = True

    def update(self, values, write_bit):
        if any(value and pin not in values for pin, value in self.pins.items()):
            fail("omitted active Drum pin/history requires native qualification")
        reset = values.get("R", self.pins["R"])
        advance = values.get("U", self.pins["U"])
        edge = "U" in values and advance and not self.pins["U"]
        if (reset and advance) or (self.pending is not None and (reset or edge)):
            fail("Drum reset/advance/pending-step collision requires native qualification")
        target = 0 if reset else self.pending if self.pending is not None else (self.current + 1) % self.config.steps if edge else self.current
        if target >= self.config.steps:
            fail("Drum pending step beyond configured steps requires native qualification")
        if self.config.steps == 1 and reset:
            fail("single-step Drum F during reset requires native qualification")
        # Initial output application models a cold start, never a plain RUN entry.
        apply = not self.initialized or target != self.current
        writes = {}
        if apply:
            for cam in self.config.cams:
                value = bool(cam.mask & (1 << target))
                if cam.output in writes and writes[cam.output] != value:
                    fail("conflicting aliased Drum cams require native qualification")
                writes[cam.output] = value
        self.pins.update(values)
        self.pending = None
        self.current = target
        self.initialized = True
        for output, value in writes.items():
            write_bit(output, value)


STATES = {"SBR": ShiftBitRegisterState, "SC": StepCounterState, "DR": DrumState}
