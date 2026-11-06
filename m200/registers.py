"""Bounded native %R configuration and explicit local Register execution policy.

Generic Functions EIO0000003289.04 pp141-146 documents sixteen i16 words,
FIFO/LIFO order, rising requests, simultaneous-new-request no-op and retained O
on empty retrieval. See docs/validation/REGISTER-*-OBSERVATIONS.md for bounded
native simulator observations; those do not certify every runtime path.
"""

import re
from dataclasses import dataclass

from .model import fail


NUMERIC_PATTERN = r"%R(?:0|[1-9][0-9]*)\.(?:I|O)"
REFERENCE = re.compile(r"%R(0|[1-9][0-9]*)\.(I|O|E|F)")
GETTERS = {"I": "input", "O": "output", "E": "empty", "F": "full"}
_FAMILY = re.compile(r"%R(?:[0-9.+-]|$)")


@dataclass
class RegisterConfig:
    mode: str = "Fifo"

    def __post_init__(self):
        if type(self.mode) is not str or self.mode not in ("Fifo", "Lifo"):
            fail("invalid register mode; expected Fifo or Lifo")


def index(text):
    match = re.fullmatch(r"%R(0|[1-9][0-9]*)", text)
    if not match or int(match[1]) >= 4:
        fail("invalid native register address: " + text)
    return int(match[1])


def reference(text, writable=False):
    # A broad %R prefix would incorrectly claim READ_VAR and RTC resources.
    if not _FAMILY.match(text):
        return None
    match = REFERENCE.fullmatch(text)
    if not match or int(match[1]) >= 4:
        fail("unsupported register property: " + text)
    if writable and match[2] not in ("I", "O"):
        fail("register status is read-only: " + text)
    return int(match[1]), match[2]


class RegisterState:
    """Ordinary per-call local policy, not a hardware-certified lifecycle model.

    Reset dominates requests, clears I/O/storage and clears both request histories.
    Thus a held Store can rise on the first non-reset call. Outside reset, both
    histories advance on every call, including refused and simultaneous edges.
    History starts false, so an initial true request is a local rising edge.
    Skipped/repeated calls follow this same per-call policy; their native and
    cold/warm/STOP lifecycle equivalence remains unqualified. Callers evaluate
    all request expressions before update, preserving pre-call status reads.
    """

    def __init__(self, config):
        self._mode = config.mode
        RegisterConfig(self._mode)
        self._input = self._output = 0
        self._queue = [0] * 16
        self._head = self._count = 0
        self._previous_store = self._previous_retrieve = False

    def read(self, field):
        if field not in GETTERS:
            fail("unsupported register property: " + field)
        return {
            "I": self._input,
            "O": self._output,
            "E": self._count == 0,
            "F": self._count == 16,
        }[field]

    def write(self, field, value):
        if field not in ("I", "O"):
            fail("register data-word write required: " + field)
        if type(value) is not int or not -32768 <= value <= 32767:
            fail("register data word must be a signed i16")
        if field == "I":
            self._input = value
        else:
            self._output = value

    def update(self, reset, store, retrieve):
        if reset:
            self._input = self._output = 0
            self._queue[:] = [0] * 16
            self._head = self._count = 0
            self._previous_store = self._previous_retrieve = False
            return
        store, retrieve = bool(store), bool(retrieve)
        store_edge = store and not self._previous_store
        retrieve_edge = retrieve and not self._previous_retrieve
        self._previous_store, self._previous_retrieve = store, retrieve
        if store_edge == retrieve_edge:
            return
        if store_edge and self._count < 16:
            self._queue[(self._head + self._count) % 16] = self._input
            self._count += 1
        elif retrieve_edge and self._count:
            if self._mode == "Fifo":
                self._output = self._queue[self._head]
                self._head = (self._head + 1) % 16
                self._count -= 1
            else:
                self._count -= 1
                self._output = self._queue[(self._head + self._count) % 16]
