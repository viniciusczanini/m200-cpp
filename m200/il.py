"""Strict executor for the explicitly supported boolean/native-timer IL subset."""

import re

from .model import address, fail, timer_config
from .communication import (
    status_reference,
    BOOL_FIELDS,
    NUM_FIELDS,
    block_address,
    parse_block,
    REFERENCE,
)
from .modbus import CommunicationEngine, validate_config
from .numeric import (
    comparison,
    compare,
    evaluate,
    read as read_number,
    write as write_number,
    word_address,
    is_operation,
    instruction_operation,
)


def bit_operand(text, writable=False):
    status = status_reference(text)
    if status:
        if writable or status[1] not in BOOL_FIELDS:
            fail("communication status is read-only BOOL")
        return
    if text.startswith("[") and not writable:
        comparison(text)
    else:
        address(text, writable)


def validate(program):
    if not isinstance(program.rungs, list) or any(
        not isinstance(r, list) or any(not isinstance(s, str) for s in r)
        for r in program.rungs
    ):
        fail("IL rungs must be lists of instruction strings")
    if not isinstance(program.timers, dict):
        fail("invalid timer configuration map")
    if not isinstance(program.symbols, dict) or not isinstance(program.metadata, dict):
        fail("invalid program metadata")
    for symbol_address, name in program.symbols.items():
        if not isinstance(symbol_address, str) or not isinstance(name, str):
            fail("invalid symbol metadata")
        if symbol_address.startswith(("%MW", "%MD", "%MF")):
            word_address(symbol_address)
        elif re.fullmatch(r"%M[0-9]+", symbol_address):
            address(symbol_address, True)
        else:
            fail("unsupported symbol metadata address")
    origins = program.metadata.get("rung_origins")
    if origins is not None:
        if not isinstance(origins, list) or len(origins) != len(program.rungs):
            fail("invalid source map metadata")
        for origin in origins:
            if not isinstance(origin, dict) or set(origin) - {
                "file",
                "line",
                "column",
                "generated",
            }:
                fail("invalid source origin metadata")
            for key, value in origin.items():
                if key in ("line", "column"):
                    if type(value) is not int or value < 1:
                        fail("invalid source location metadata")
                elif not isinstance(value, str):
                    fail("invalid source text metadata")
    if sum(map(len, program.rungs)) > 10000:
        fail("instruction budget exceeded")
    timer_uses = set()
    if not isinstance(program.communications, dict):
        fail("invalid communication configuration map")
    communication_uses = set()
    for key, cfg in program.communications.items():
        kind, _ = block_address(key)
        validate_config(cfg)
        if cfg.kind != kind:
            fail("communication address/configuration kind mismatch")
    for index, t in program.timers.items():
        if type(index) is not int or any(
            type(x) is not int for x in (t.milliseconds, t.base_ms)
        ):
            fail("invalid timer numeric parameters")
        timer_config(t.kind, t.milliseconds, index)
        if (
            t.base_ms not in (1, 10, 100, 1000, 60000)
            or (t.base_ms == 1 and index >= 6)
            or t.milliseconds % t.base_ms
            or not 0 <= t.preset <= 9999
        ):
            fail("invalid timer base/preset")
    for rung in program.rungs:
        if not rung:
            fail("empty IL rung")
        if rung[0].startswith("BLK "):
            if (
                rung[0]
                .split(maxsplit=1)[1]
                .startswith(("%READ_VAR", "%WRITE_VAR", "%WRITE_READ_VAR"))
            ):
                key, execute, abort = parse_block(rung)
                if key not in program.communications or key in communication_uses:
                    fail("undefined or multiply updated communication block")
                communication_uses.add(key)
                bit_operand(execute[1])
                bit_operand(abort[1])
                continue
            m = re.fullmatch(r"BLK %TM([0-9]+)", rung[0])
            if (
                not m
                or len(rung) != 7
                or rung[2:5] != ["IN", "OUT_BLK", "LD Q"]
                or rung[-1] != "END_BLK"
                or rung[1].split(maxsplit=1)[:1] not in (["LD"], ["LDN"])
                or not rung[5].startswith("ST ")
            ):
                fail("unsupported or non-reversible timer block")
            index = int(m.group(1))
            if index not in program.timers or index in timer_uses:
                fail("undefined or multiply updated timer")
            timer_uses.add(index)
            args = rung[1].split(maxsplit=1)
            if len(args) != 2:
                fail("timer input has no operand")
            bit_operand(args[1])
            address(rung[5][3:], True)
            continue
        for i, line in enumerate(rung):
            if is_operation(line) and i > 0:
                instruction_operation(line)
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                fail("unsupported IL instruction: " + line)
            op, arg = parts
            allowed = (
                ("LD", "LDN")
                if i == 0
                else ("ST", "S", "R")
                if i == len(rung) - 1
                else ("AND", "ANDN", "OR", "ORN", "XOR", "XORN", "ST", "S", "R")
            )
            if op not in allowed:
                fail("unsupported IL instruction/order: " + line)
            bit_operand(arg, op in ("ST", "S", "R"))
        if len(rung) < 2:
            fail("rung has no action")
    if set(program.timers) != timer_uses:
        fail("unused timer configuration is unsupported")
    if set(program.communications) != communication_uses:
        fail("unused communication configuration is unsupported")
    for rung in program.rungs:
        for line in rung:
            for ref in re.findall(REFERENCE, line):
                if status_reference(ref)[0] not in program.communications:
                    fail("undefined communication status: " + ref)


class Machine:
    def __init__(self, program, communication_transport=None):
        validate(program)
        self.program = program
        self.memory = [False] * 1024
        self.words = [0] * 8000
        self.communication = CommunicationEngine(communication_transport)
        self.operations = {
            line: instruction_operation(line)
            for rung in program.rungs
            for line in rung
            if is_operation(line)
        }
        self.comparisons = {
            line.split(maxsplit=1)[1]: comparison(line.split(maxsplit=1)[1])
            for rung in program.rungs
            for line in rung
            if not is_operation(line) and " [" in line
        }
        self.outputs = [False] * 16
        self.now = 0
        self.first = True
        self.timers = {
            i: {"start": None, "previous": False, "q": False} for i in program.timers
        }

    def read(self, operand, inputs):
        status = status_reference(operand)
        if status:
            return getattr(self.communication.status(status[0]), BOOL_FIELDS[status[1]])
        if operand.startswith("["):
            return compare(self.words, self.comparisons[operand], self.read_number)
        kind, index = address(operand)
        if kind == "constant":
            return bool(index)
        if kind == "M":
            return self.memory[index]
        if kind == "I0.":
            return bool(inputs.get(index, inputs.get(str(index), False)))
        if kind == "Q0.":
            return self.outputs[index]
        if index == 13:
            return self.first
        period = {4: 10, 5: 100, 6: 1000, 7: 60000}[index]
        return bool((self.now // (period // 2)) % 2)

    def write(self, operand, value):
        kind, index = address(operand, True)
        (self.memory if kind == "M" else self.outputs)[index] = bool(value)

    def read_number(self, value):
        status = status_reference(value.code)
        return (
            getattr(self.communication.status(status[0]), NUM_FIELDS[status[1]][1])
            if status
            else read_number(self.words, value)
        )

    def timer(self, index, enabled):
        config = self.program.timers[index]
        state = self.timers[index]
        start = state["start"]
        q = state["q"]
        prev = state["previous"]
        if config.kind == "TON":
            if not enabled:
                start = None
                q = False
            else:
                if start is None:
                    start = self.now
                q = self.now - start >= config.milliseconds
        elif config.kind == "TOF":
            if enabled:
                q = True
                start = None
            else:
                if prev:
                    start = self.now
                if start is not None and self.now - start >= config.milliseconds:
                    q = False
                    start = None
        else:
            if enabled and not prev and start is None:
                start = self.now
            if start is not None and self.now - start >= config.milliseconds:
                start = None
            q = start is not None
        state.update(start=start, previous=enabled, q=q)
        return q

    def step(self, inputs=None, dt_ms=10):
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            fail("inputs must be an object")
        if type(dt_ms) is not int or not 0 <= dt_ms <= 3600000:
            fail("dt_ms must be an integer between 0 and 3600000")
        for k, v in inputs.items():
            if str(k) not in [str(i) for i in range(24)] or v not in (
                True,
                False,
                0,
                1,
            ):
                fail("invalid input trace")
        for rung in self.program.rungs:
            if rung[0].startswith("BLK "):
                if rung[0].split(maxsplit=1)[1] in self.program.communications:
                    key, execute, abort = parse_block(rung)
                    enabled = self.read(execute[1], inputs)
                    cancel = self.read(abort[1], inputs)
                    self.communication.update(
                        key,
                        self.program.communications[key],
                        not enabled if execute[0] == "LDN" else enabled,
                        not cancel if abort[0] == "LDN" else cancel,
                        self.now,
                        self.words,
                    )
                    continue
                index = int(rung[0].split("%TM")[1])
                op, arg = rung[1].split(maxsplit=1)
                enabled = self.read(arg, inputs)
                if op == "LDN":
                    enabled = not enabled
                self.write(rung[5][3:], self.timer(index, enabled))
                continue
            acc = False
            for line in rung:
                if is_operation(line):
                    if acc:
                        target, name, values = self.operations[line]
                        kind, _ = word_address(target)
                        args = [
                            self.read_number(v) if not isinstance(v, int) else v
                            for v in values
                        ]
                        write_number(self.words, target, evaluate(name, args, kind))
                    continue
                op, arg = line.split(maxsplit=1)
                if op in ("ST", "S", "R"):
                    if op == "ST":
                        self.write(arg, acc)
                    elif acc:
                        self.write(arg, op == "S")
                    continue
                if op in ("AND", "ANDN") and not acc:
                    continue
                if op in ("OR", "ORN") and acc:
                    continue
                value = self.read(arg, inputs)
                if op in ("LDN", "ANDN", "ORN", "XORN"):
                    value = not value
                if op in ("LD", "LDN"):
                    acc = value
                elif op in ("AND", "ANDN"):
                    acc = acc and value
                elif op in ("OR", "ORN"):
                    acc = acc or value
                else:
                    acc = acc != value
        self.now += dt_ms
        self.first = False
        return list(self.outputs)


def validate_frames(frames):
    if not isinstance(frames, list) or not 1 <= len(frames) <= 100000:
        fail("trace must be an array of 1..100000 frames")
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) - {"inputs", "dt_ms"}:
            fail("invalid trace frame")
        dt = frame.get("dt_ms", 10)
        inputs = frame.get("inputs", {})
        if (
            type(dt) is not int
            or not 0 <= dt <= 3600000
            or not isinstance(inputs, dict)
        ):
            fail("invalid trace dt_ms/inputs")
        for k, v in inputs.items():
            if str(k) not in [str(i) for i in range(24)] or v not in (
                True,
                False,
                0,
                1,
            ):
                fail("invalid input trace")
    return frames
