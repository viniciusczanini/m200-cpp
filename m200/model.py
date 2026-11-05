import re
from dataclasses import asdict, dataclass, field


class CompileError(ValueError):
    pass


def fail(message):
    raise CompileError("M200-E: " + message)


@dataclass
class Timer:
    kind: str
    milliseconds: int
    base_ms: int = 10

    @property
    def preset(self):
        return self.milliseconds // self.base_ms


@dataclass
class Program:
    rungs: list = field(default_factory=list)
    timers: dict = field(default_factory=dict)
    symbols: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    communications: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "format": "m200-cpp-il-v1",
            "target": "TM200CE40T",
            "rungs": self.rungs,
            "timers": {str(k): asdict(v) for k, v in self.timers.items()},
            "symbols": self.symbols,
            "metadata": self.metadata,
            "communications": {k: v.to_dict() for k, v in self.communications.items()},
        }

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
        }:
            fail("unknown program JSON fields")
        if data.get("format") != "m200-cpp-il-v1" or data.get("target") != "TM200CE40T":
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
        return cls(
            data["rungs"],
            timers,
            data.get("symbols", {}),
            data.get("metadata", {}),
            {k: ModbusConfig.from_dict(v) for k, v in comms.items()},
        )


def address(text, writable=False):
    if text in ("0", "1") and not writable:
        return ("constant", int(text))
    m = re.fullmatch(r"%(I0\.|Q0\.|M|S)([0-9]+)", text)
    if not m:
        fail("unsupported bit address: " + text)
    kind, number = m.group(1), int(m.group(2))
    limits = {"I0.": 24, "Q0.": 16, "M": 1024, "S": 160}
    if number >= limits[kind]:
        fail("address outside target range: " + text)
    if kind == "S" and number not in (4, 5, 6, 7, 13):
        fail("unsupported system bit: " + text)
    if writable and kind not in ("M", "Q0."):
        fail("address is read-only: " + text)
    return kind, number


def timer_config(kind, milliseconds, index):
    if kind not in ("TON", "TOF", "TP") or index not in range(255):
        fail("invalid timer kind or index")
    for base in [1, 10, 100, 1000, 60000] if index < 6 else [10, 100, 1000, 60000]:
        if 0 <= milliseconds <= base * 9999 and milliseconds % base == 0:
            return Timer(kind, milliseconds, base)
    fail("timer duration is not representable at this timer index")
