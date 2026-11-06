"""Strict executor for the explicitly supported boolean/native-timer IL subset."""

import re

from .model import address, fail, timer_config
from .timers import (
    TimerState,
    REFERENCE as TIMER_REFERENCE,
    reference as timer_reference,
    preset_value,
)
from .flow import JUMPS, destinations, label_name, split_label
from .native_logic import decode, STORES, OPEN, timer_index
from .bits import is_string, references as bit_references, signed_pattern
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, LOADS, operand as edge_operand
from .edge_functions import parse as expression_edge
from .indexed import (
    ANY_INDEXED,
    is_indexed,
    is_bit_indexed,
    resolve as resolve_indexed,
    resolve_bit,
    direct_word_limit,
    direct_bit_limit,
)
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
    reference_address,
    Number,
    TYPES,
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
        if type(t.retentive) is not bool or type(t.dynamic_preset) is not bool:
            fail("timer mode fields must be bool")
        if t.kind == "TP" and t.retentive:
            fail("retentive TP is unsupported in the Basic timer profile")
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
    labels = destinations(program)
    jumps = []
    expression_uses = set()
    for raw_rung in program.rungs:
        label, rung = split_label(raw_rung)
        if not rung:
            fail("empty IL rung")
        if label is not None and rung[0].split(maxsplit=1)[0] not in (
            *LOADS,
            "BLK",
        ):
            fail("label must precede a supported load or block")
        if len(rung) == 1 and rung[0].startswith("JMP "):
            jumps.append(label_name(rung[0].split(maxsplit=1)[1]))
            continue
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
        for op, arg in decode(rung):
            if expression_edge(op) is not None:
                if op in expression_uses:
                    fail("duplicate expression edge instruction identity: " + op)
                expression_uses.add(op)
                continue
            if op == "NUM":
                target, name, values = instruction_operation(arg)
                if (
                    timer_reference(target, True)
                    and name == "copy"
                    and not values[0].code.startswith("%")
                ):
                    preset_value(int(values[0].code))
                continue
            if op in ("N", "MPS", "MRD", "MPP", ")"):
                continue
            if op in EDGE_OPS:
                edge_operand(arg)
                continue
            if op == "IN":
                index = timer_index(arg)
                if index not in program.timers or index in timer_uses:
                    fail("undefined or multiply updated timer")
                timer_uses.add(index)
            elif op in JUMPS:
                jumps.append(label_name(arg))
            else:
                if op in ("AND", "ANDN", "OR", "ORN", *OPEN) and ANY_INDEXED.search(
                    arg
                ):
                    fail(
                        "indexed contact short-circuit/error effects are unverified; use an explicit load and CFG"
                    )
                if arg == "%S20" and op in ("S", "ST", "STN"):
                    fail("system index-error bit is writable only by R")
                bit_operand(arg, op in STORES and arg != "%S20")
    if set(jumps) - labels.keys():
        fail("jump references an undefined label")
    property_uses = {
        int(m[1])
        for rung in program.rungs
        for line in rung
        for m in TIMER_REFERENCE.finditer(line)
    }
    if property_uses - program.timers.keys():
        fail("undefined timer property")
    if set(program.timers) != timer_uses | property_uses:
        fail("unused timer configuration is unsupported")
    if set(program.communications) != communication_uses:
        fail("unused communication configuration is unsupported")
    for rung in program.rungs:
        for line in rung:
            for ref in re.findall(REFERENCE, line):
                if status_reference(ref)[0] not in program.communications:
                    fail("undefined communication status: " + ref)


class Machine:
    def __init__(
        self, program, communication_transport=None, *, instruction_limit=100000
    ):
        validate(program)
        if type(instruction_limit) is not int or not 1 <= instruction_limit <= 10000000:
            fail("invalid local execution limit")
        self.program = program
        self.decoded = []
        for raw in program.rungs:
            _, body = split_label(raw)
            communication = (
                body[0].startswith("BLK ")
                and body[0].split(maxsplit=1)[1] in program.communications
            )
            self.decoded.append(None if communication else decode(body))
        self.labels = destinations(program)
        self.instruction_limit = instruction_limit
        self.memory = [False] * 1024
        self.words = [0] * 8000
        self.index_error = False
        self.index_word_limit = direct_word_limit(program)
        self.index_bit_limit = direct_bit_limit(program)
        self.communication = CommunicationEngine(communication_transport)
        self.operations = {
            line: instruction_operation(line)
            for rung in program.rungs
            for line in rung
            if is_operation(line)
        }
        self.comparisons = {
            parts[1]: comparison(parts[1])
            for rung in program.rungs
            for line in rung
            for parts in [line.split(maxsplit=1)]
            if not is_operation(line) and len(parts) == 2 and parts[1].startswith("[")
        }
        self.outputs = [False] * 16
        self.now = 0
        self.first = True
        self.current_inputs = {}
        self.edge_previous = {
            arg: False
            for arg in sorted(
                {
                    arg
                    for rung in self.decoded
                    if rung is not None
                    for op, arg in rung
                    if op in EDGE_OPS
                }
            )
        }
        self.edge_events = {}
        self.expression_history = {
            op: False
            for rung in self.decoded
            if rung is not None
            for op, _ in rung
            if expression_edge(op) is not None
        }
        self.timers = {i: TimerState(t) for i, t in program.timers.items()}

    def read(self, operand, inputs):
        timer = timer_reference(operand)
        if timer:
            return self.timers[timer[0]].read(timer[1], self.now)
        if is_bit_indexed(operand):
            index, error = resolve_bit(operand, self.words, self.index_bit_limit)
            self.index_error |= error
            return self.memory[index]
        status = status_reference(operand)
        if status:
            return getattr(self.communication.status(status[0]), BOOL_FIELDS[status[1]])
        if operand.startswith("["):
            return compare(self.words, self.comparisons[operand], self.read_number)
        kind, index = address(operand)
        if kind == "MWbit":
            return bool(self.words[index // 16] & (1 << (index % 16)))
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
        if index == 20:
            return self.index_error
        period = {4: 10, 5: 100, 6: 1000, 7: 60000}[index]
        return bool((self.now // (period // 2)) % 2)

    def write(self, operand, value):
        if operand == "%S20":
            if value:
                fail("system index-error bit can only be cleared")
            self.index_error = False
            return
        if is_bit_indexed(operand):
            index, error = resolve_bit(operand, self.words, self.index_bit_limit)
            self.index_error |= error
            self.memory[index] = bool(value)
            return
        kind, index = address(operand, True)
        if kind == "MWbit":
            mask = 1 << (index % 16)
            old = self.words[index // 16]
            self.words[index // 16] = (old | mask) if value else (old & (65535 ^ mask))
            return
        (self.memory if kind == "M" else self.outputs)[index] = bool(value)

    def read_number(self, value):
        if is_string(value.code):
            raw = sum(
                int(self.read(ref, self.current_inputs)) << i
                for i, ref in enumerate(bit_references(value.code))
            )
            return signed_pattern(raw, value.kind)
        timer = timer_reference(value.code)
        if timer:
            return self.timers[timer[0]].read(timer[1], self.now)
        if is_indexed(value.code):
            kind, index, error = resolve_indexed(
                value.code, self.words, self.index_word_limit
            )
            self.index_error |= error
            value = Number(kind, "%" + TYPES[kind][0] + str(index))
        status = status_reference(value.code)
        return (
            getattr(self.communication.status(status[0]), NUM_FIELDS[status[1]][1])
            if status
            else read_number(self.words, value)
        )

    def write_number(self, target, value):
        if is_string(target):
            for i, ref in enumerate(bit_references(target)):
                self.write(ref, bool(value & (1 << i)))
            return
        timer = timer_reference(target, True)
        if timer:
            self.timers[timer[0]].set_preset(value, self.now)
            return
        if is_indexed(target):
            kind, index, error = resolve_indexed(
                target, self.words, self.index_word_limit
            )
            self.index_error |= error
            target = "%" + TYPES[kind][0] + str(index)
        write_number(self.words, target, value)

    def timer(self, index, enabled):
        return self.timers[index].update(enabled, self.now)

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
        pc = 0
        self.current_inputs = inputs
        for ref, previous in self.edge_previous.items():
            current = self.read(ref, inputs)
            self.edge_events[ref] = (current and not previous, previous and not current)
            self.edge_previous[ref] = current
        executed = 0
        while pc < len(self.program.rungs):
            _, rung = split_label(self.program.rungs[pc])
            pc += 1
            executed += len(rung)
            if executed > self.instruction_limit:
                fail(
                    "local execution limit exceeded; physical watchdog is not simulated"
                )
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
            acc = False
            saved = []
            groups = []
            for op, arg in self.decoded[pc - 1]:
                if op in self.expression_history:
                    current = acc
                    previous = self.expression_history[op]
                    acc = (
                        (current and not previous)
                        if op.startswith("RISING")
                        else (previous and not current)
                    )
                    self.expression_history[op] = current
                    continue
                if op == "NUM":
                    if acc:
                        target, name, values = self.operations[arg]
                        kind = (
                            values[0].kind
                            if is_string(target)
                            else reference_address(target)[0]
                        )
                        args = [
                            self.read_number(v) if not isinstance(v, int) else v
                            for v in values
                        ]
                        self.write_number(target, evaluate(name, args, kind))
                    continue
                if op == "IN":
                    self.timer(timer_index(arg), acc)
                    continue
                if op == "N":
                    acc = not acc
                    continue
                if op == "MPS":
                    saved.append(acc)
                    continue
                if op == "MRD":
                    acc = saved[-1]
                    continue
                if op == "MPP":
                    acc = saved.pop()
                    continue
                if op in OPEN:
                    groups.append((op, acc))
                    acc = self.read(arg, inputs)
                    continue
                if op == ")":
                    operator, outer = groups.pop()
                    acc = (outer and acc) if operator == "AND(" else (outer or acc)
                    continue
                if op in JUMPS:
                    if op == "JMP" or (acc if op == "JMPC" else not acc):
                        pc = self.labels[arg]
                    continue
                if op in STORES:
                    if op in ("ST", "STN"):
                        self.write(arg, not acc if op == "STN" else acc)
                    elif acc:
                        self.write(arg, op == "S")
                    continue
                if op in ("AND", "ANDN") and not acc:
                    continue
                if op in ("OR", "ORN") and acc:
                    continue
                if op in EDGE_OPS:
                    value = self.edge_events[arg][op[-1] == "F"]
                    op = EDGE_BASE[op]
                else:
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
