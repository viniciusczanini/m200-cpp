"""Test-only adapter protocol. Expectations never enter a production adapter."""

from dataclasses import dataclass, field
from typing import Any


class PendingAdapterError(AssertionError):
    """An unbound API is a visible failure, never a skip or a successful result."""


class PendingOracleError(AssertionError):
    """A missing independent expectation cannot be replaced by SDK/VM agreement."""


@dataclass(frozen=True)
class Case:
    name: str
    groups: tuple[str, ...]
    covers: tuple[str, ...]
    adapter: str
    basis: str
    request: dict[str, Any]
    expected: Any
    oracle_status: str = "prepared"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def adapter_input(self):
        # Do not pass self, expected, or any independent reference to adapters.
        import copy

        return copy.deepcopy(self.request)


def observation(words=(), bits=(), flags=None):
    result = {"words_u16": list(words), "bits": [bool(value) for value in bits]}
    if flags is not None:
        result["flags"] = {key: bool(value) for key, value in flags.items()}
    return result


def source_case(name, groups, covers, body, frames, observe, expected, basis, notes=()):
    return Case(
        name, tuple(groups), tuple(covers), "source_pipeline", basis,
        {"source": "#include <plc.hpp>\n" + body, "frames": frames, "observe": observe},
        expected, notes=tuple(notes),
    )


def frame(inputs=None, dt_ms=10):
    return {"inputs": {} if inputs is None else inputs, "dt_ms": dt_ms}
