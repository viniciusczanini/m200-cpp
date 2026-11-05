"""Strict executor for the explicitly supported boolean/native-timer IL subset."""

import re

from .model import address, fail, timer_config


def validate(program):
    if not isinstance(program.rungs, list) or any(
        not isinstance(r, list) or any(not isinstance(s, str) for s in r)
        for r in program.rungs
    ):
        fail("IL rungs must be lists of instruction strings")
    if not isinstance(program.timers, dict):
        fail("invalid timer configuration map")
    if sum(map(len, program.rungs)) > 10000:
        fail("instruction budget exceeded")
    timer_uses = set()
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
            m = re.fullmatch(r"BLK %TM(\d+)", rung[0])
            if (
                not m
                or len(rung) != 7
                or rung[2:5] != ["IN", "OUT_BLK", "LD Q"]
                or rung[-1] != "END_BLK"
                or not rung[1].startswith("LD ")
                or not rung[5].startswith("ST ")
            ):
                fail("unsupported or non-reversible timer block")
            index = int(m.group(1))
            if index not in program.timers or index in timer_uses:
                fail("undefined or multiply updated timer")
            timer_uses.add(index)
            address(rung[1][3:])
            address(rung[5][3:], True)
            continue
        for i, line in enumerate(rung):
            parts = line.split()
            if len(parts) != 2:
                fail("unsupported IL instruction: " + line)
            op, arg = parts
            allowed = (
                ("LD", "LDN")
                if i == 0
                else ("ST", "S", "R")
                if i == len(rung) - 1
                else ("AND", "ANDN", "OR", "ORN", "XOR", "XORN")
            )
            if op not in allowed:
                fail("unsupported IL instruction/order: " + line)
            address(arg, op in ("ST", "S", "R"))
        if len(rung) < 2:
            fail("rung has no action")
    if set(program.timers) != timer_uses:
        fail("unused timer configuration is unsupported")


class Machine:
    def __init__(self, program):
        validate(program)
        self.program = program
        self.memory = [False] * 1024
        self.outputs = [False] * 16
        self.now = 0
        self.first = True
        self.timers = {
            i: {"start": None, "previous": False, "q": False} for i in program.timers
        }

    def read(self, operand, inputs):
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
                index = int(rung[0].split("%TM")[1])
                self.write(
                    rung[5][3:], self.timer(index, self.read(rung[1][3:], inputs))
                )
                continue
            acc = False
            for line in rung:
                op, arg = line.split()
                if op in ("ST", "S", "R"):
                    if op == "ST":
                        self.write(arg, acc)
                    elif acc:
                        self.write(arg, op == "S")
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
