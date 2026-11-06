import re
from dataclasses import asdict, dataclass, field

SYSTEM_RESETS = frozenset(("%S17", "%S18", "%S20"))


class CompileError(ValueError):
    pass


def fail(message):
    raise CompileError("M200-E: " + message)


@dataclass
class Timer:
    kind: str
    milliseconds: int
    base_ms: int = 10
    retentive: bool = False
    dynamic_preset: bool = False

    @property
    def preset(self):
        return self.milliseconds // self.base_ms


@dataclass
class SubroutineDefinition:
    number: int
    name: str
    section_number: int
    rungs: list
    origins: list = field(default_factory=list)


@dataclass
class Program:
    rungs: list = field(default_factory=list)
    timers: dict = field(default_factory=dict)
    symbols: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    communications: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)
    subroutines: dict = field(default_factory=dict)
    registers: dict = field(default_factory=dict)
    constants: dict = field(default_factory=dict)
    rtcs: dict = field(default_factory=dict)
    schedules: dict = field(default_factory=dict)
    boolean: object = None
    shift_bit_registers: dict = field(default_factory=dict)
    step_counters: dict = field(default_factory=dict)
    drums: dict = field(default_factory=dict)

    def as_dict(self):
        result = {
            "format": "m200-cpp-il-v2" if self.subroutines else "m200-cpp-il-v1",
            "target": "TM200CE40T",
            "rungs": self.rungs,
            "timers": {str(k): asdict(v) for k, v in self.timers.items()},
            "symbols": self.symbols,
            "metadata": self.metadata,
            "communications": {k: v.to_dict() for k, v in self.communications.items()},
            "counters": {str(k): asdict(v) for k, v in self.counters.items()},
        }
        if self.constants:
            result["constants"] = {str(k): v for k, v in self.constants.items()}
        if self.subroutines:
            result["subroutines"] = {
                str(k): asdict(v) for k, v in self.subroutines.items()
            }
        if self.registers:
            result["registers"] = {str(k): asdict(v) for k, v in self.registers.items()}
        if self.rtcs:
            result["rtcs"] = {str(k): asdict(v) for k, v in self.rtcs.items()}
        if self.schedules:
            result["schedules"] = {str(k): asdict(v) for k, v in self.schedules.items()}
        if self.boolean is not None:
            result["boolean"] = self.boolean.to_dict()
        for name in ("shift_bit_registers", "step_counters", "drums"):
            if getattr(self, name):
                result[name] = {str(k): asdict(v) for k, v in getattr(self, name).items()}
        return result

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            fail("program JSON must be an object")
        if set(data) - {
            "format",
            "target",
            "rungs",
            "timers",
            "symbols",
            "metadata",
            "communications",
            "counters",
            "registers",
            "constants",
            "rtcs",
            "schedules",
            "boolean",
            "shift_bit_registers",
            "step_counters",
            "drums",
            *(("subroutines",) if data.get("format") == "m200-cpp-il-v2" else ()),
        }:
            fail("unknown program JSON fields")
        if (
            data.get("format") not in ("m200-cpp-il-v1", "m200-cpp-il-v2")
            or data.get("target") != "TM200CE40T"
        ):
            fail("unsupported program format or target")
        if not isinstance(data.get("rungs"), list) or not isinstance(
            data.get("timers"), dict
        ):
            fail("invalid program JSON shape")
        if not isinstance(data.get("symbols", {}), dict) or not isinstance(
            data.get("metadata", {}), dict
        ):
            fail("invalid program metadata")
        if any(
            not isinstance(k, str) or not re.fullmatch(r"0|[1-9][0-9]*", k)
            for k in data["timers"]
        ):
            fail("timer indexes must use canonical decimal keys")
        try:
            timers = {int(k): Timer(**v) for k, v in data["timers"].items()}
        except (TypeError, ValueError):
            fail("invalid timer JSON")
        from .modbus import ModbusConfig

        comms = data.get("communications", {})
        if not isinstance(comms, dict):
            fail("invalid communication configuration map")
        from .counters import Counter

        raw_counters = data.get("counters", {})
        if not isinstance(raw_counters, dict) or any(
            not isinstance(k, str)
            or not re.fullmatch(r"0|[1-9][0-9]*", k)
            or int(k) >= 255
            for k in raw_counters
        ):
            fail("invalid counter configuration map")
        try:
            counters = {int(k): Counter(**v) for k, v in raw_counters.items()}
        except (TypeError, ValueError):
            fail("invalid counter JSON")
        subroutines = {}
        from .registers import RegisterConfig

        raw_registers = data.get("registers", {})
        if not isinstance(raw_registers, dict) or any(
            key not in ("0", "1", "2", "3")
            or not isinstance(value, dict)
            or set(value) != {"mode"}
            for key, value in raw_registers.items()
        ):
            fail("invalid register configuration map")
        try:
            registers = {int(k): RegisterConfig(**v) for k, v in raw_registers.items()}
        except (TypeError, ValueError):
            fail("invalid register JSON")
        if data.get("format") == "m200-cpp-il-v2":
            raw = data.get("subroutines")
            if not isinstance(raw, dict) or not raw:
                fail("v2 requires explicit subroutine contexts")
            for key, value in raw.items():
                if (
                    not isinstance(key, str)
                    or re.fullmatch(r"0|[1-9][0-9]*", key) is None
                    or len(key) > 2
                    or int(key) >= 64
                ):
                    fail("invalid subroutine JSON identity")
                if not isinstance(value, dict) or set(value) != {
                    "number",
                    "name",
                    "section_number",
                    "rungs",
                    "origins",
                }:
                    fail("invalid subroutine JSON definition")
                subroutines[int(key)] = SubroutineDefinition(**value)
        raw_constants = data.get("constants", {})
        if not isinstance(raw_constants, dict) or any(not isinstance(k, str) or re.fullmatch(r"0|[1-9][0-9]*", k) is None for k in raw_constants):
            fail("invalid constant image JSON")
        from .scalar_constants import validate as validate_constants
        constants = {int(k): v for k, v in raw_constants.items()}
        validate_constants(constants)
        from .rtc import configs_from_json, RtcConfig, ScheduleConfig
        rtcs = configs_from_json(data.get("rtcs", {}), RtcConfig, 2)
        schedules = configs_from_json(data.get("schedules", {}), ScheduleConfig, 16)
        from .boolean_banks import BooleanConfig

        from .sequences import configurations_from_json
        return cls(
            data["rungs"],
            timers,
            data.get("symbols", {}),
            data.get("metadata", {}),
            {k: ModbusConfig.from_dict(v) for k, v in comms.items()},
            counters,
            subroutines,
            registers,
            constants=constants,
            rtcs=rtcs,
            schedules=schedules,
            boolean=BooleanConfig.from_dict(data["boolean"]) if "boolean" in data else None,
            shift_bit_registers=configurations_from_json(data.get("shift_bit_registers", {}), "SBR"),
            step_counters=configurations_from_json(data.get("step_counters", {}), "SC"),
            drums=configurations_from_json(data.get("drums", {}), "DR"),
        )


def address(text, writable=False):
    if ":X" in text:
        from .boolean_banks import word_bit

        bank, word, channel, bit = word_bit(text, writable)
        return bank + "bit", (word * 16 + bit) if channel is None else (word, channel, bit)
    from .rtc import reference as rtc_reference
    rtc = rtc_reference(text, writable)
    if rtc:
        if rtc[0] != "rtc" or rtc[2] not in ("Done", "Error"):
            fail("numeric RTC/schedule property is not a bit: " + text)
        return "RTC." + rtc[2], rtc[1]
    from .sequences import reference as sequence_reference
    sequence = sequence_reference(text, writable)
    if sequence:
        family, index, prop = sequence
        if family == "DR":
            if prop != "F":
                fail("numeric Drum property is not a bit: " + text)
            return "DR.F", index
        return family + ".bit", index * (16 if family == "SBR" else 256) + int(prop)
    from .registers import reference as register_reference

    register = register_reference(text, writable)
    if register:
        if register[1] not in ("E", "F"):
            fail("numeric register property is not a bit: " + text)
        return "R." + register[1], register[0]
    if text.startswith("%C"):
        from .counters import reference

        index, field = reference(text, writable)
        if field not in ("E", "D", "F"):
            fail("numeric counter property is not a bit: " + text)
        return "C." + field, index
    if text.startswith("%TM"):
        from .timers import reference

        index, field = reference(text, writable)
        if field != "Q":
            fail("numeric timer property is not a bit: " + text)
        return "TM.Q", index
    if "[" in text:
        from .indexed import parse_bit

        base, _ = parse_bit(text)
        return "M", base
    if text in ("0", "1") and not writable:
        return ("constant", int(text))
    m = re.fullmatch(r"%(I0\.|Q0\.|M|S)([0-9]+)", text)
    if not m:
        fail("unsupported bit address: " + text)
    kind, number = m.group(1), int(m.group(2))
    limits = {"I0.": 24, "Q0.": 16, "M": 1024, "S": 160}
    if number >= limits[kind]:
        fail("address outside target range: " + text)
    if kind == "S":
        from .boolean_banks import system_bit

        system_bit(number, "ST" if writable else None)
    if writable and kind not in ("M", "Q0.", "S"):
        fail("address is read-only: " + text)
    return kind, number


def timer_config(kind, milliseconds, index):
    if kind not in ("TON", "TOF", "TP") or index not in range(255):
        fail("invalid timer kind or index")
    for base in [1, 10, 100, 1000, 60000] if index < 6 else [10, 100, 1000, 60000]:
        if 0 <= milliseconds <= base * 9999 and milliseconds % base == 0:
            return Timer(kind, milliseconds, base)
    fail("timer duration is not representable at this timer index")
