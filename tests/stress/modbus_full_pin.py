#!/usr/bin/env python3
"""Bounded full-pin Modbus composition audit, using only public local inputs.

Run: python3 tests/stress/modbus_full_pin.py --output /fresh/path
Without --output a fresh retained temporary directory is printed. Requires the
normal local Python/clang++ toolchain and the three public full-pin fixtures.
No sockets, GUI, Wine, physical PLC, CI or product writes. Repeated execution
paths compare 67 base positions plus seven focused control-entry positions.
"""

# ruff: noqa: E402
import argparse
import copy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.modbus import MemoryModbusPeer, MemoryTransport
from m200.native import run_native
from m200.project import load_project, write_project

HERE = None
ORACLES = None
TEMPLATE = ROOT / "tests/fixtures/official_tm200ce40t_modbus_full_pin_read.smbp"
NAMES = {"multi": ["r", "w", "x"], "cascade": ["a", "b"]}
KEYS = {
    "multi": ["%READ_VAR3", "%WRITE_VAR5", "%WRITE_READ_VAR7"],
    "cascade": ["%READ_VAR1", "%READ_VAR9"],
}
INDICES = {"multi": [3, 5, 7], "cascade": [1, 9]}
FIXTURE_DIGESTS = {
    "read": "8154e130ce73b6a1b6e90f5876264437ec36778207fc38c3a3661152059f9e50",
    "write": "ae6ffad294a36e79656f36845f2a0bebf19df6f3e60b8aa7b82597b867b79af3",
    "write_read": "9e7a3359a99c433bdebe7eaca21235960de806fdfb8151a678e39345e4b3588f",
}


def literal_oracles():
    """Hand-written timing/control/status and byte tables; no production calls."""
    Z = "0000"
    B = "0100"
    D = "1000"
    A = "0010"
    E = "0001"
    # Input indices set TRUE; I6 always enables the 20ms timer. One explicit 100ms scan advances to the timeout boundary.
    controls = [
        [],
        [],
        [0, 1, 2],
        [0, 1, 2],
        [0, 1, 2],
        [],
        [1],
        [1, 7],
        [1, 2],
        [2, 5],
        [],
        [2],
        [2, 7],
        [2],
        [],
        [0],
        [0],
        [0],
        [0],
        [],
        [0, 1],
        [0, 1],
        [0, 1],
        [],
        [1],
        [1],
        [1],
        [],
        [1],
        [1],
        [1],
        [],
        [2],
        [2],
        [2],
        [],
        [2, 7],
        [2, 7],
        [2, 7],
        [2, 7],
        [],
        [0, 2, 5],
        [0, 2, 3, 5],
        [],
    ]
    status = [
        (Z, Z, Z),
        (Z, Z, Z),
        (B, E, E),
        (B, E, E),
        (D, E, E),
        (Z, Z, Z),
        (Z, B, Z),
        (Z, B, Z),
        (Z, D, B),
        (Z, Z, A),
        (Z, Z, Z),
        (Z, Z, B),
        (Z, Z, B),
        (Z, Z, D),
        (Z, Z, Z),
        (B, Z, Z),
        (B, Z, Z),
        (E, Z, Z),
        (E, Z, Z),
        (Z, Z, Z),
        (B, E, Z),
        (B, E, Z),
        (D, E, Z),
        (Z, Z, Z),
        (Z, B, Z),
        (Z, E, Z),
        (Z, E, Z),
        (Z, Z, Z),
        (Z, B, Z),
        (Z, B, Z),
        (Z, D, Z),
        (Z, Z, Z),
        (Z, Z, B),
        (Z, Z, B),
        (Z, Z, E),
        (Z, Z, Z),
        (Z, Z, B),
        (Z, Z, B),
        (Z, Z, D),
        (Z, Z, D),
        (Z, Z, Z),
        (B, Z, Z),
        (A, Z, Z),
        (Z, Z, Z),
    ]
    assert len(controls) == len(status) == 44
    r_packet = "0200110011"
    r_reply = "0203018001"
    w_packet = "0f0049001103018001"
    w_reply = "0f00490011"
    x_packet = "170029000300110002041234abcd"
    x_reply = "17068001ffff1234"
    starts = [
        (2, "r", "normal", r_packet, r_reply),
        (6, "w", "normal", w_packet, w_reply),
        (8, "x", "cancel", x_packet, None),
        (11, "x", "normal", x_packet, x_reply),
        (15, "r", "exception", r_packet, "8202"),
        (20, "r", "read_changed", r_packet, "0203020000"),
        (24, "w", "timeout", w_packet, None),
        (28, "w", "normal", w_packet, w_reply),
        (32, "x", "malformed", x_packet, "17068001ffff12"),
        (36, "x", "normal", "1700290003001100020443211111", x_reply),
        (41, "r", "cancel", r_packet, None),
    ]
    rows = []
    now = 0
    for i, (keys, states) in enumerate(zip(controls, status)):
        inputs = {str(k): True for k in [6] + keys}
        if i == 32:
            inputs["8"] = True  # Seed distinct inbound words before the bad reply.
        gate = i >= 2
        errs = [[0, 0] for _ in states]
        if i in (2, 3, 4):
            errs[1:] = [[255, 11], [255, 11]]
        if i in (17, 18):
            errs[0] = [254, 2]
        if i in (20, 21, 22):
            errs[1] = [255, 11]
        if i in (25, 26):
            errs[1] = [1, 0]
        if i == 34:
            errs[2] = [0, 2]
        if i in (9,):
            errs[2] = [2, 0]
        if i == 42:
            errs[0] = [2, 0]
        words = {
            199: 0x7777,
            200: 0 if i < 4 else 0x8001 if i < 22 else 2,
            201: 0 if i < 4 or i >= 22 else 1,
            202: 0x8888,
            239: 0x7777,
            240: 2 if 7 in keys else 0x8001,
            241: 0 if 7 in keys else 1,
            242: 0x8888,
            299: 0x7777,
            300: 0x4321 if 7 in keys else 0x1234,
            301: 0x1111 if 7 in keys else 0xABCD,
            302: 0x8888,
            399: 0x7777,
            400: 0xAAAA if i < 13 else 0x2468 if 32 <= i < 38 else 0x8001,
            401: 0xBBBB if i < 13 else 0x1357 if 32 <= i < 38 else 0xFFFF,
            402: 0xCCCC if i < 13 else 0x369C if 32 <= i < 38 else 0x1234,
            403: 0x8888,
        }
        outputs = (
            "".join(states)
            + ("1" if states[2] == E else "0")
            + str(int(gate))
            + str(int(4 <= i < 22))
            + str(int(13 <= i < 32 or i >= 38))
        )
        absent_states = [
            E if gate and pin in keys and not (i == 41 and pin == 2) else Z
            for pin in (0, 1, 2)
        ]
        # Only false-to-true transitions produce absent-transport error; all request inputs are initialized false.
        if i == 42:
            absent_states[2] = (
                Z  # prior simultaneous Execute+Abort was suppressed, held Execute cannot retry.
            )
        absent = (
            "".join(absent_states)
            + str(int(absent_states[2] == E))
            + str(int(gate))
            + "00"
        )
        rows.append(
            dict(
                scan=i,
                now_ms=now,
                dt_ms=100 if i == 24 else 10,
                inputs=inputs,
                states=states,
                errors=errs,
                outputs=outputs,
                absent_outputs=absent,
                words={str(k): v for k, v in words.items()},
                timer_value=min(i, 2),
                shared_error=states[2] == E,
            )
        )
        now += rows[-1]["dt_ms"]
    # Cascade: a DONE is b Execute in the same scan; b's four writes to M90 end in ERROR.
    ccontrols = [
        [],
        [],
        [0],
        [0],
        [0],
        [0],
        [0],
        [0],
        [],
        [0],
        [0, 1],
        [],
        [0],
        [0],
        [0],
        [0, 2],
        [],
        [0],
        [0],
        [0],
        [0],
        [0],
        [],
    ]
    cstates = [
        (Z, Z),
        (Z, Z),
        (B, Z),
        (B, Z),
        (D, B),
        (D, B),
        (D, D),
        (D, D),
        (Z, Z),
        (B, Z),
        (A, Z),
        (Z, Z),
        (B, Z),
        (B, Z),
        (D, B),
        (D, A),
        (Z, Z),
        (B, Z),
        (B, Z),
        (D, B),
        (D, B),
        (D, D),
        (Z, Z),
    ]
    crows = []
    for i, (keys, states) in enumerate(zip(ccontrols, cstates)):
        words = {
            200: 0 if i < 4 else 0x8003,
            201: 0 if i < 4 else 1,
            250: 0 if i < 6 else 1,
        }
        outputs = (
            "".join(states)
            + "0"
            + str(int(states[0] == D))
            + str(int(i >= 2))
            + str(int(i >= 4))
            + str(int(i >= 6))
            + "000"
        )
        # With no transport a fails before DONE, so b never gets an Execute edge.
        absent = (
            (E if i >= 2 and 0 in keys else Z)
            + Z
            + "00"
            + str(int(i >= 2))
            + "00"
            + "000"
        )
        errs = [
            [2, 0] if states[0] == A else [0, 0],
            [2, 0] if states[1] == A else [0, 0],
        ]
        crows.append(
            dict(
                scan=i,
                now_ms=10 * i,
                dt_ms=10,
                inputs={str(k): True for k in [6] + keys},
                states=states,
                errors=errs,
                outputs=outputs,
                absent_outputs=absent,
                words={str(k): v for k, v in words.items()},
                timer_value=min(i, 2),
                shared_error=False,
            )
        )
    cstarts = [
        (2, "a", "normal", r_packet, "0203038001"),
        (4, "b", "normal", "0200120001", "020101"),
        (9, "a", "cancel", r_packet, None),
        (12, "a", "normal", r_packet, "0203038001"),
        (14, "b", "cancel", "0200120001", None),
        (17, "a", "normal", r_packet, "0203038001"),
        (19, "b", "normal", "0200120001", "020101"),
    ]
    for name, case_rows in [("multi", rows), ("cascade", crows)]:
        for row in case_rows:
            i = row["scan"]
            row["remote_written"] = (
                (
                    [0, 0]
                    if i < 13
                    else [0xBEEF, 0xCAFE]
                    if 32 <= i < 34
                    else [0x4321, 0x1111]
                    if i >= 38
                    else [0x1234, 0xABCD]
                )
                if name == "multi"
                else [0, 0]
            )
            row["remote_true_coils"] = (
                [73, 88, 89] if name == "multi" and i >= 8 else []
            )
    data = {
        "method": "Hand-written control/status tables and literal wire bytes; no production oracle calls. Native callbacks replay explicitly supplied statuses, not a native protocol stack.",
        "cases": {
            "multi": {
                "rows": rows,
                "starts": [
                    dict(zip(("scan", "name", "mode", "pdu", "response"), s))
                    for s in starts
                ],
            },
            "cascade": {
                "rows": crows,
                "starts": [
                    dict(zip(("scan", "name", "mode", "pdu", "response"), s))
                    for s in cstarts
                ],
            },
        },
    }
    return data["cases"]


SOURCES = {
    "multi": """#include <plc.hpp>
plc::ReadVar r{3,plc::Link::Serial1,1,1,plc::Object::DiscreteInputs,17,17,200};
plc::WriteVar w{5,plc::Link::Serial1,1,1,plc::Object::Coils,73,17,240};
plc::WriteReadVar x{7,plc::Link::Serial1,1,1,17,2,300,41,3,400};
plc::Ton gate{4,10,2};
void scan(){
  gate.update(plc::input(6));
  if(plc::system(13)){
    plc::write_word(199,30583);plc::write_word(202,-30584);
    plc::write_word(239,30583);plc::write_word(242,-30584);
    plc::write_word(299,30583);plc::write_word(302,-30584);
    plc::write_word(399,30583);plc::write_word(400,-21846);plc::write_word(401,-17477);plc::write_word(402,-13108);plc::write_word(403,-30584);
  }
  if(plc::input(7)){
    plc::write_word(240,2);plc::write_word(241,0);plc::write_word(300,17185);plc::write_word(301,4369);
  }else{
    plc::write_word(240,-32767);plc::write_word(241,1);plc::write_word(300,4660);plc::write_word(301,-21555);
  }
  if(plc::input(8)){
    plc::write_word(400,9320);plc::write_word(401,4951);plc::write_word(402,13980);
  }
  plc::write_m(10,plc::input(0)&&gate.done());plc::write_m(13,plc::input(3));
  plc::write_m(20,plc::input(1)&&gate.done());plc::write_m(23,plc::input(4));
  plc::write_m(30,plc::input(2)&&gate.done());plc::write_m(33,plc::input(5));
  r.update(plc::read_m(10),plc::read_m(13));
  plc::write_m(14,r.done());plc::write_m(15,r.busy());plc::write_m(16,r.aborted());plc::write_m(90,r.error());
  w.update(plc::read_m(20),plc::read_m(23));
  plc::write_m(24,w.done());plc::write_m(25,w.busy());plc::write_m(26,w.aborted());plc::write_m(90,w.error());
  x.update(plc::read_m(30),plc::read_m(33));
  plc::write_m(34,x.done());plc::write_m(35,x.busy());plc::write_m(36,x.aborted());plc::write_m(90,x.error());
  plc::output(0,r.done());plc::output(1,r.busy());plc::output(2,r.aborted());plc::output(3,r.error());
  plc::output(4,w.done());plc::output(5,w.busy());plc::output(6,w.aborted());plc::output(7,w.error());
  plc::output(8,x.done());plc::output(9,x.busy());plc::output(10,x.aborted());plc::output(11,x.error());
  plc::output(12,plc::read_m(90));plc::output(13,gate.done());
  plc::output(14,plc::read_word(200)==-32767&&plc::read_word(201)==1);
  plc::output(15,plc::read_word(400)==-32767&&plc::read_word(401)==-1&&plc::read_word(402)==4660);
}
""",
    "cascade": """#include <plc.hpp>
plc::ReadVar a{1,plc::Link::Serial1,1,1,plc::Object::DiscreteInputs,17,17,200};
plc::ReadVar b{9,plc::Link::Serial1,1,1,plc::Object::DiscreteInputs,18,1,250};
plc::Ton gate{4,10,2};
void scan(){
  gate.update(plc::input(6));
  plc::write_m(10,plc::input(0)&&gate.done());plc::write_m(13,plc::input(1));plc::write_m(23,plc::input(2));
  a.update(plc::read_m(10),plc::read_m(13));
  plc::write_m(20,a.done());plc::write_m(15,a.busy());plc::write_m(16,a.aborted());plc::write_m(17,a.error());
  b.update(plc::read_m(20),plc::read_m(23));
  plc::write_m(90,b.done());plc::write_m(90,b.busy());plc::write_m(90,b.aborted());plc::write_m(90,b.error());
  plc::output(0,a.done());plc::output(1,a.busy());plc::output(2,a.aborted());plc::output(3,a.error());
  plc::output(4,b.done());plc::output(5,b.busy());plc::output(6,b.aborted());plc::output(7,b.error());
  plc::output(8,plc::read_m(90));plc::output(9,plc::read_m(20));plc::output(10,gate.done());
  plc::output(11,plc::read_word(200)==-32765&&plc::read_word(201)==1);
  plc::output(12,plc::read_word(250)==1);
  plc::output(13,false);plc::output(14,false);plc::output(15,false);
}
""",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + "\n")


def command(args, log):
    completed = subprocess.run(
        args, cwd=ROOT, text=True, capture_output=True, timeout=120
    )
    (HERE / log).write_text(
        "$ "
        + " ".join(str(a) for a in args)
        + "\n"
        + completed.stdout
        + completed.stderr
        + "\nexit="
        + str(completed.returncode)
        + "\n"
    )
    assert completed.returncode == 0, (
        log,
        completed.returncode,
        completed.stderr[-2500:],
    )
    return completed


class TraceTransport(MemoryTransport):
    def __init__(self, case, prefix_commit_mutation=False):
        peer = MemoryModbusPeer(
            holding_registers=[0] * 128,
            input_registers=[0] * 128,
            coils=[False] * 128,
            discrete_inputs=[False] * 128,
        )
        for pos in (17, 32, 33) if case == "multi" else (17, 18, 32, 33):
            peer.discrete_inputs[pos] = True
        peer.holding_registers[41:44] = [0x8001, 0xFFFF, 0x1234]
        super().__init__(peer, latency_ms=20)
        self.spec = ORACLES[case]["starts"]
        self.events = []
        self.cancelled = []
        self.completed = []
        self.rows = ORACLES[case]["rows"]
        self.tokens = {}
        self.scan = -1
        self.prefix_commit_mutation = prefix_commit_mutation
        self.local_words = None

    def start(self, config, pdu, now_ms):
        spec = self.spec[len(self.events)]
        assert self.scan == spec["scan"] and now_ms == self.rows[self.scan]["now_ms"], (
            "start timing",
            spec,
            self.scan,
            now_ms,
        )
        assert pdu.hex() == spec["pdu"], ("wire request", spec, pdu.hex())
        if spec["mode"] == "read_changed":
            self.peer.discrete_inputs[:] = [False] * 128
            self.peer.discrete_inputs[18] = True
        if spec["mode"] == "malformed":
            self.peer.holding_registers[17:19] = [0xBEEF, 0xCAFE]
        original = self.latency_ms
        self.latency_ms = 500 if spec["mode"] == "timeout" else 20
        token = super().start(config, pdu, now_ms)
        self.latency_ms = original
        self.tokens[token] = spec
        self.events.append(
            {
                "scan": self.scan,
                "now_ms": now_ms,
                "name": spec["name"],
                "mode": spec["mode"],
                "config": asdict(config),
                "pdu": pdu.hex(),
            }
        )
        return token

    def poll(self, token, now_ms):
        config, pdu, ready = self._pending[token]
        if now_ms < ready:
            return None
        spec = self.tokens[token]
        assert spec["mode"] not in ("cancel", "timeout"), (
            "unexpected completion",
            spec,
        )
        if spec["mode"] == "exception":
            del self._pending[token]
            response = bytes.fromhex("8202")
        else:
            response = super().poll(token, now_ms)
            if spec["mode"] == "malformed":
                response = response[:-1]
                if self.prefix_commit_mutation:
                    # Deliberately faulty decoder surrogate: commit two complete
                    # prefix words before rejecting the dangling final byte.
                    self.local_words[400:402] = [0x8001, 0xFFFF]
        assert response.hex() == spec["response"], (
            "wire response",
            spec,
            response.hex(),
        )
        self.completed.append(
            {"scan": self.scan, "name": spec["name"], "response": response.hex()}
        )
        return response

    def cancel(self, token):
        # Malformed replies call cancel after poll has already consumed their token.
        pending = token in self._pending
        self.cancelled.append(
            {"scan": self.scan, "name": self.tokens[token]["name"], "pending": pending}
        )
        return super().cancel(token)


def vm_path(program, case, label, prefix_commit_mutation=False, done_alias=False):
    validate(program)
    transport = TraceTransport(case, prefix_commit_mutation)
    machine = Machine(program, communication_transport=transport)
    transport.local_words = machine.words
    observations = []
    for row in ORACLES[case]["rows"]:
        transport.scan = row["scan"]
        got = machine.step(row["inputs"], row["dt_ms"])
        bits = "".join(str(int(v)) for v in got)
        assert bits == row["outputs"], (
            case,
            label,
            "outputs",
            row["scan"],
            bits,
            row["outputs"],
        )
        if done_alias:
            assert machine.memory[14] == (row["states"][0] == "1000"), (
                "BUSY then DONE must retain the last DONE store",
                row["scan"],
                machine.memory[14],
            )
        words = {key: machine.words[int(key)] & 65535 for key in row["words"]}
        for address, expected in row["words"].items():
            assert words[address] == expected, (
                case,
                label,
                "word",
                row["scan"],
                address,
                words[address],
                expected,
            )
        statuses = [machine.communication.status(k) for k in KEYS[case]]
        errors = [[s.comm_error, s.oper_error] for s in statuses]
        assert errors == row["errors"], (
            case,
            label,
            "errors",
            row["scan"],
            errors,
            row["errors"],
        )
        assert machine.timers[4].read("V", row["now_ms"]) == row["timer_value"]
        assert machine.memory[90] == row["shared_error"]
        assert transport.peer.holding_registers[17:19] == row["remote_written"], (
            case,
            label,
            "remote FC23 timing",
            row["scan"],
            transport.peer.holding_registers[17:19],
            row["remote_written"],
        )
        assert [i for i, v in enumerate(transport.peer.coils) if v] == row[
            "remote_true_coils"
        ], (case, label, "remote FC15 timing", row["scan"])
        assert transport.peer.holding_registers[41:44] == [0x8001, 0xFFFF, 0x1234]
        assert transport.peer.input_registers == [0] * 128
        observations.append(
            dict(
                scan=row["scan"],
                outputs=bits,
                words=words,
                errors=errors,
                timer_value=row["timer_value"],
                remote_written=row["remote_written"],
                remote_true_coils=row["remote_true_coils"],
            )
        )
    assert len(transport.events) == len(transport.spec)
    expected_cancel = (
        [
            (9, "x", True),
            (17, "r", False),
            (25, "w", True),
            (34, "x", False),
            (42, "r", True),
        ]
        if case == "multi"
        else [(10, "a", True), (15, "b", True)]
    )
    assert [
        (r["scan"], r["name"], r["pending"]) for r in transport.cancelled
    ] == expected_cancel, transport.cancelled
    assert not transport._pending and not machine.communication._active_links
    if case == "multi":
        assert [i for i, v in enumerate(transport.peer.coils) if v] == [73, 88, 89]
        assert transport.peer.holding_registers[17:19] == [0x4321, 0x1111]
        assert (
            transport.peer.holding_registers[:17] == [0] * 17
            and transport.peer.holding_registers[19:41] == [0] * 22
        )
        assert transport.peer.holding_registers[41:44] == [0x8001, 0xFFFF, 0x1234]
    else:
        assert not any(transport.peer.coils) and transport.peer.holding_registers[
            17:19
        ] == [0, 0]
    return dict(
        label=label,
        frames=len(observations),
        events=transport.events,
        completed=transport.completed,
        cancelled=transport.cancelled,
        observations=observations,
        remote_guards_preserved=True,
        no_pending_after_trace=True,
    )


def absent_path(program, source, case, label):
    expected = [[b == "1" for b in r["absent_outputs"]] for r in ORACLES[case]["rows"]]
    frames = [
        {"inputs": r["inputs"], "dt_ms": r["dt_ms"]} for r in ORACLES[case]["rows"]
    ]
    machine = Machine(program)
    got = [machine.step(f["inputs"], f["dt_ms"]) for f in frames]
    assert got == expected, (
        case,
        label,
        "absent VM",
        next((i for i, (a, b) in enumerate(zip(got, expected)) if a != b), None),
    )
    actual = run_native(source, frames)
    assert actual == expected, (
        case,
        label,
        "absent native",
        next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), None),
    )
    return dict(
        label=label, frames=len(frames), status="pass", no_fabricated_transport=True
    )


def prefix_mutation_control(program):
    """The literal oracle must kill an intentional partial-reply commit."""
    try:
        vm_path(program, "multi", "deliberate_prefix_commit", True)
    except AssertionError as error:
        mismatch = error.args[0]
        assert mismatch == (
            "multi",
            "deliberate_prefix_commit",
            "word",
            34,
            "400",
            0x8001,
            0x2468,
        ), mismatch
        return {
            "status": "caught_as_required",
            "mutation": "Commit the two complete FC23 prefix words before rejecting the truncated response",
            "first_mismatch": {
                "scan": 34,
                "now_ms": 430,
                "address": "%MW400",
                "actual_unsigned": 0x8001,
                "expected_unsigned": 0x2468,
            },
            "new_distinct_timeline_positions": 0,
            "production_code_changed": False,
        }
    raise AssertionError("The deliberate partial-prefix commit escaped the oracle")


def native_injected(program, source, case, label):
    rows = ORACLES[case]["rows"]
    names = NAMES[case]
    keys = KEYS[case]
    n = len(names)
    words = list(map(int, rows[0]["words"]))
    table = []
    for row in rows:
        results = []
        for state, err in zip(row["states"], row["errors"]):
            results.append(
                "{"
                + ",".join(
                    ["true" if v == "1" else "false" for v in state]
                    + [str(v) for v in err]
                )
                + "}"
            )
        table.append("{" + ",".join(results) + "}")
    inputs = []
    for row in rows:
        if case == "multi":
            controls = [(0, 3), (1, 4), (2, 5)]
            pins = [
                (
                    i >= 0 and row["inputs"].get(str(i), False) and row["scan"] >= 2,
                    row["inputs"].get(str(a), False),
                )
                for i, a in controls
            ]
        else:
            pins = [
                (
                    row["inputs"].get("0", False) and row["scan"] >= 2,
                    row["inputs"].get("1", False),
                ),
                (row["states"][0] == "1000", row["inputs"].get("2", False)),
            ]
        inputs.append(
            "{"
            + ",".join("{" + str(int(e)) + "," + str(int(a)) + "}" for e, a in pins)
            + "}"
        )
    configs = []
    for key in keys:
        c = program.communications[key]
        configs.append(
            "{"
            + ",".join(
                map(
                    str,
                    [
                        {"READ_VAR": 0, "WRITE_VAR": 1, "WRITE_READ_VAR": 2}[c.kind],
                        1,
                        c.id,
                        c.timeout_100ms,
                        c.obj_type,
                        c.first_obj,
                        c.quantity,
                        c.index_data,
                        c.first_read_obj,
                        c.read_quantity,
                        c.index_data_in,
                    ],
                )
            )
            + "}"
        )
    commits = []
    for i, row in enumerate(rows):
        if case == "multi":
            changes = (
                [(200, int(row["words"]["200"])), (201, int(row["words"]["201"]))]
                if i in (4, 22)
                else []
            ) + ([(400, 0x8001), (401, 0xFFFF), (402, 0x1234)] if i in (13, 38) else [])
        else:
            changes = ([(200, 0x8003), (201, 1)] if i in (4, 14, 19) else []) + (
                [(250, 1)] if i in (6, 21) else []
            )
        if changes:
            commits.append(
                "if(frame=="
                + str(i)
                + " && call=="
                + str(0 if changes[0][0] == 200 else n - 1)
                + "){"
                + "".join("words[" + str(k) + "]=" + str(v) + ";" for k, v in changes)
                + "}"
            )
    harness = HERE / (case + "-" + label + "-native-hook.cpp")
    binary = HERE / (case + "-" + label + "-native-hook")
    text = (
        '#define PLC_NATIVE\n#include "'
        + str(source)
        + '"\n#include <cstdio>\n#include <cstdlib>\n'
    )
    text += (
        "static int frame=0,call=0;\nstatic const plc::detail::CommunicationResult results["
        + str(len(rows))
        + "]["
        + str(n)
        + "]={"
        + ",".join(table)
        + "};\n"
    )
    text += (
        "static const int pins["
        + str(len(rows))
        + "]["
        + str(n)
        + "][2]={"
        + ",".join(inputs)
        + "};\n"
    )
    text += (
        "static const int configs[" + str(n) + "][11]={" + ",".join(configs) + "};\n"
    )
    text += (
        "static const int native_ids["
        + str(n)
        + "]={"
        + ",".join(map(str, INDICES[case]))
        + "};\n"
    )
    text += (
        "plc::detail::CommunicationResult hook(const plc::detail::CommunicationConfig& c,int id,bool e,bool a,unsigned long long now,unsigned short* words){\nint actual[]={c.kind,c.link,c.id,c.timeout,c.obj,c.first,c.quantity,c.index,c.first_read,c.read_quantity,c.index_in};\nif(call>="
        + str(n)
        + "||id!=native_ids[call]||e!=pins[frame][call][0]||a!=pins[frame][call][1])std::abort();\nfor(int j=0;j<11;++j)if(actual[j]!=configs[call][j])std::abort();\n"
    )
    text += (
        "".join(commits)
        + "return results[frame][call++];}\nint main(){plc::detail::communication_hook=hook;\n"
    )
    for row in rows:
        text += (
            "frame="
            + str(row["scan"])
            + ";call=0;for(int j=0;j<24;++j)plc::detail::inputs[j]=false;"
        )
        text += "".join(
            "plc::detail::inputs[" + str(k) + "]=true;" for k in row["inputs"]
        )
        text += "plc::detail::begin_scan();scan();if(call!=" + str(n) + ")std::abort();"
        text += 'for(int j=0;j<16;++j)std::printf("%d",plc::detail::outputs[j]?1:0);std::printf(" ");'
        text += "".join(
            'std::printf("%u ",(unsigned)plc::detail::words[' + str(w) + "]);"
            for w in words
        )
        text += (
            'std::printf("%d %d",plc::detail::memory[90]?1:0,(int)'
            + ("gate" if label == "source" else "timer_4")
            + ".value());"
        )
        text += "".join(
            'std::printf(" %d %d",(int)'
            + name
            + ".comm_error(),(int)"
            + name
            + ".oper_error());"
            for name in names
        )
        text += (
            'std::printf("\\n");plc::detail::first_scan=false;plc::detail::now_ms+='
            + str(row["dt_ms"])
            + ";\n"
        )
    text += "}\n"
    harness.write_text(text)
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    assert compiler, "clang++ not found"
    command(
        [
            compiler,
            "-std=c++17",
            "-O0",
            "-I",
            str(ROOT / "sdk"),
            str(harness),
            "-o",
            str(binary),
        ],
        case + "-" + label + "-native-build.log",
    )
    completed = command([str(binary)], case + "-" + label + "-native-run.log")
    actual = completed.stdout.splitlines()
    assert len(actual) == len(rows)
    for row, line in zip(rows, actual):
        expected = (
            [row["outputs"]]
            + [str(row["words"][str(w)]) for w in words]
            + [str(int(row["shared_error"])), str(row["timer_value"])]
            + [str(v) for pair in row["errors"] for v in pair]
        )
        assert line.split() == expected, (
            case,
            label,
            "injected native",
            row["scan"],
            line.split(),
            expected,
        )
    return dict(
        label=label,
        frames=len(rows),
        status="pass",
        callback="literal status/commit replay; not native protocol implementation",
    )


def semantic_checks(program, project, case):
    tree = ET.parse(project)
    full = [
        r
        for r in tree.findall(".//RungEntity")
        if len(r.findall("InstructionLines/InstructionLineEntity")) == 15
    ]
    assert len(full) == len(KEYS[case])
    assert all(len(r.findall("LadderElements/LadderEntity")) == 27 for r in full)
    imported = load_project(project)
    assert (
        imported.communications == program.communications
        and imported.timers == program.timers
    )
    groups = imported.metadata.get("native_full_pin_groups", [])
    assert len(groups) == len(KEYS[case])
    return dict(
        canonical_rungs=len(program.rungs),
        canonical_instructions=sum(map(len, program.rungs)),
        native_rungs=len(tree.findall(".//RungEntity")),
        native_instructions=len(tree.findall(".//InstructionLine")),
        full_pin_groups=len(full),
        group_graph_entities=[27] * len(full),
        configs_timers_equal=True,
    )


def mutations(program, case):
    if case != "multi":
        return []
    results = []

    def reject(p, template, label):
        before = copy.deepcopy(p.as_dict())
        template_bytes = template.read_bytes()
        for exists in (False, True):
            dest = HERE / (
                "mutation-existing.smbp" if exists else "mutation-absent.smbp"
            )
            if dest.exists():
                dest.unlink()
            if exists:
                dest.write_bytes(b"PRESERVE_DESTINATION")
            try:
                write_project(p, template, dest)
            except CompileError as exc:
                error = str(exc)
            else:
                raise AssertionError("mutation accepted: " + label)
            assert p.as_dict() == before and template.read_bytes() == template_bytes
            assert (
                dest.read_bytes() == b"PRESERVE_DESTINATION"
                if exists
                else not dest.exists()
            )
            results.append(
                dict(
                    case=label,
                    destination="existing" if exists else "absent",
                    error=error,
                    atomic=True,
                )
            )
            if dest.exists():
                dest.unlink()

    for token in ("FunctLevelMan20_0", "FunctLevelMan7_0"):
        tree = ET.parse(TEMPLATE)
        tree.find("ManagementLevel").text = token
        path = HERE / ("bad-" + token + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        forged = copy.deepcopy(program)
        forged.metadata["functional_level"] = "FunctLevelMan21_0"
        reject(forged, path, "actual_template_" + token)
    tree = ET.parse(TEMPLATE)
    node = tree.find(".//SerialLineConfiguration/Addressing")
    assert node is not None
    node.text = "SlaveAddressing"
    path = HERE / "bad-slave.smbp"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    reject(program, path, "actual_SL1_slave")
    key = "%READ_VAR3"
    p = copy.deepcopy(program)
    p.communications[key] = replace(p.communications[key], obj_type=0)
    reject(p, TEMPLATE, "unverified_full_pin_READ_MW")
    # Complete two-word bit buffer at MW7999 must fail construction, not be clipped.
    try:
        replace(program.communications[key], index_data=7999)
    except CompileError as exc:
        results.append(
            dict(
                case="incomplete_two_word_buffer",
                error=str(exc),
                stage="typed config construction",
            )
        )
    else:
        raise AssertionError("incomplete bit span admitted")
    return results


def decomposition_checks(program):
    """Newly admitted canonical forms must decompose without moving stores."""
    key = "%READ_VAR3"
    base = next(i for i, rung in enumerate(program.rungs) if rung[0] == "BLK " + key)
    reorder = copy.deepcopy(program)
    reorder.metadata.pop("rung_origins", None)
    reorder.rungs[base + 1], reorder.rungs[base + 2] = (
        reorder.rungs[base + 2],
        reorder.rungs[base + 1],
    )
    alias = copy.deepcopy(reorder)
    alias.rungs[base + 1][-1] = "ST %M14"
    labeled = copy.deepcopy(program)
    labeled.metadata.pop("rung_origins", None)
    labeled.rungs[base + 2].insert(0, "%L61:")
    labeled.rungs.insert(0, ["LD %M70", "JMPC %L61"])
    results = []
    graph_control_source = None
    for name, candidate, done_alias in (
        ("reordered_status_stores", reorder, False),
        ("reordered_same_target_alias", alias, True),
        ("interior_label_control_entry", labeled, False),
    ):
        original = copy.deepcopy(candidate.as_dict())
        template = TEMPLATE.read_bytes()
        for existing in (False, True):
            destination = HERE / (
                name + ("-existing" if existing else "-absent") + ".smbp"
            )
            if existing:
                destination.write_bytes(b"PRESERVE_UNTIL_SUCCESSFUL_REPLACEMENT")
            write_project(candidate, TEMPLATE, destination)
            assert candidate.as_dict() == original and TEMPLATE.read_bytes() == template
            imported = load_project(destination)
            assert imported.rungs == candidate.rungs, name
            assert imported.communications == candidate.communications
            tree = ET.parse(destination)
            bare = [
                rung
                for rung in tree.findall(".//RungEntity")
                if [
                    " ".join((n.text or "").split())
                    for n in rung.findall(".//InstructionLine")
                ]
                == candidate.rungs[
                    base + (1 if name == "interior_label_control_entry" else 0)
                ]
            ]
            assert len(bare) == 1
            assert len(bare[0].findall("LadderElements/LadderEntity")) == 3
            assert len(imported.metadata.get("native_full_pin_groups", [])) == 2
            vm_path(imported, "multi", name, done_alias=done_alias)
            results.append(
                {
                    "case": name,
                    "destination": "existing" if existing else "absent",
                    "status": "pass",
                    "exact_rung_store_label_order": True,
                    "caller_and_template_preserved": True,
                    "successful_complete_output": True,
                    "bare_graph_entities": 3,
                    "other_full_pin_groups": 2,
                    "same_target_last_DONE_store_checked": done_alias,
                }
            )
            graph_control_source = graph_control_source or destination
    # These malformed native graphs must not gain admission merely because
    # canonical IR can now decompose into safe bare + ordinary rungs.
    graph_negatives = []
    for name in (
        "missing_abort",
        "unknown_field",
        "extra_output",
        "wrong_class",
        "wrong_connection",
        "wrong_abort",
    ):
        tree = ET.parse(graph_control_source)
        rung = next(
            r
            for r in tree.findall(".//RungEntity")
            if " ".join(
                (
                    r.findtext("InstructionLines/InstructionLineEntity/InstructionLine")
                    or ""
                ).split()
            )
            == "BLK " + key
        )
        graph = rung.find("LadderElements")
        block = next(n for n in graph if n.findtext("Descriptor") == key)
        abort = next(
            n
            for n in graph
            if n.findtext("ElementType") == "NormalContact"
            and n.findtext("Row") == "1"
            and n.findtext("Column") == "0"
        )
        if name == "missing_abort":
            graph.remove(abort)
        elif name == "unknown_field":
            ET.SubElement(block, "UnknownGraphField").text = "1"
        elif name == "extra_output":
            extra = copy.deepcopy(abort)
            extra.find("ElementType").text = "Coil"
            extra.find("Column").text = "10"
            graph.append(extra)
        elif name == "wrong_class":
            block.find("ElementType").text = "WriteVarBasic"
        elif name == "wrong_connection":
            block.find("ChosenConnection").text = "Left, Right"
        else:
            abort.find("Descriptor").text = "%M12"
        path = HERE / ("bad-native-" + name + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        before = path.read_bytes()
        try:
            load_project(path)
        except CompileError as error:
            assert path.read_bytes() == before, (
                "Rejected native graph source bytes changed",
                name,
            )
            graph_negatives.append(
                {
                    "case": name,
                    "error": str(error),
                    "input_bytes_preserved": path.read_bytes() == before,
                }
            )
        else:
            raise AssertionError("Unknown/partial native graph admitted: " + name)
    result = {
        "status": "pass",
        "positive_forms": 2,
        "same_target_alias_variant": 1,
        "successful_destination_checks": results,
        "native_graph_negative_checks": graph_negatives,
        "reused_base_timeline_positions_not_added_to_frame_count": 44,
    }
    put("decomposition-results.json", result)
    return result


CONTROL_SOURCE = """#include <plc.hpp>
plc::ReadVar remote{3,plc::Link::Serial1,1,100,plc::Object::DiscreteInputs,17,17,200};
void scan(){
  plc::write_m(70,plc::input(0));plc::write_m(10,plc::input(1));plc::write_m(13,plc::input(2));
  if(plc::input(3)){plc::write_m(14,true);}if(plc::input(4)){plc::write_m(14,false);}
  if(plc::read_m(70)){goto busy_status;}
  remote.update(plc::read_m(10),plc::read_m(13));
  plc::write_m(14,remote.done());
busy_status:
  plc::write_m(15,remote.busy());plc::write_m(16,remote.aborted());plc::write_m(17,remote.error());
  plc::output(0,plc::read_m(14));plc::output(1,plc::read_m(15));
  plc::output(2,remote.done());plc::output(3,remote.error());
}
"""


def control_entry_trace():
    """Seven new literal positions expose a skipped update and DONE store."""
    controls = [[], [1], [0], [0, 1, 2, 3], [1], [0, 4], []]
    positive = ["0000", "0100", "0100", "1100", "1010", "0010", "0000"]
    absent = ["0000", "0001", "0001", "1001", "0001", "0001", "0000"]
    states = ["0000", "0100", "0100", "0100", "1000", "1000", "0000"]
    frames = [
        {"inputs": {str(k): True for k in keys}, "dt_ms": 10} for keys in controls
    ]
    source = HERE / "control-entry.cpp"
    source.write_text(CONTROL_SOURCE)
    put(
        "control-entry-oracle.json",
        {
            "frames": frames,
            "callback_outputs_Q0_3": positive,
            "absent_outputs_Q0_3": absent,
            "callback_states_DONE_BUSY_ABORTED_ERROR": states,
            "literal_request": "0200110011",
            "literal_response": "0203018001",
        },
    )
    build = HERE / "control-entry-build"
    command(
        [
            sys.executable,
            "-m",
            "m200",
            "compile",
            str(source),
            "--template",
            str(TEMPLATE),
            "-o",
            str(build),
        ],
        "control-entry-compile.log",
    )
    reverse = HERE / "control-entry-reverse.cpp"
    command(
        [
            sys.executable,
            "-m",
            "m200",
            "decompile",
            str(build / "program.smbp"),
            "-o",
            str(reverse),
        ],
        "control-entry-decompile.log",
    )
    reverse_build = HERE / "control-entry-reverse-build"
    command(
        [
            sys.executable,
            "-m",
            "m200",
            "compile",
            str(reverse),
            "--template",
            str(TEMPLATE),
            "-o",
            str(reverse_build),
        ],
        "control-entry-recompile.log",
    )
    programs = [
        ("source_IR", compile_source(source)),
        (
            "serialized_IR",
            Program.from_dict(json.loads((build / "program.m200.json").read_text())),
        ),
        ("project", load_project(build / "program.smbp")),
        ("reverse_IR", compile_source(reverse)),
        ("reverse_project", load_project(reverse_build / "program.smbp")),
    ]
    for label, program in programs:

        class Peer(MemoryModbusPeer):
            def handle_request(self, pdu):
                assert pdu == bytes.fromhex("0200110011")
                response = super().handle_request(pdu)
                assert response == bytes.fromhex("0203018001")
                self.completions += 1
                return response

        peer = Peer(discrete_inputs=[False] * 64)
        for index in (17, 32, 33):
            peer.discrete_inputs[index] = True
        peer.completions = 0
        transport = MemoryTransport(peer, latency_ms=20)
        machine = Machine(program, communication_transport=transport)
        for i, frame in enumerate(frames):
            output = machine.step(frame["inputs"], 10)
            assert "".join(str(int(v)) for v in output) == positive[i] + "0" * 12, (
                label,
                i,
                output,
            )
            state = machine.communication.status("%READ_VAR3")
            assert (
                "".join(
                    str(int(getattr(state, k)))
                    for k in ("done", "busy", "aborted", "error")
                )
                == states[i]
            )
            assert transport._next_token == (0 if i == 0 else 1)
            assert peer.completions == (1 if i >= 4 else 0)
            assert machine.words[200:202] == ([0x8001, 1] if i >= 4 else [0, 0])
        assert not transport._pending
        no_transport = Machine(program)
        assert [
            "".join(str(int(v)) for v in no_transport.step(f["inputs"], 10))
            for f in frames
        ] == [r + "0" * 12 for r in absent]
    for path in (source, reverse):
        assert run_native(path, frames) == [
            [b == "1" for b in row + "0" * 12] for row in absent
        ]
    for folder in (build, reverse_build):
        report = json.loads((folder / "report.json").read_text())
        for name, expected in report["artifacts"].items():
            assert digest(folder / name) == expected
        root = ET.parse(folder / "program.smbp").getroot()
        assert plain_tree(root.find("HardwareConfiguration")) == plain_tree(
            ET.parse(TEMPLATE).getroot().find("HardwareConfiguration")
        )
        assert (
            sum(
                len(r.findall(".//InstructionLine")) == 6
                and len(r.findall("LadderElements/LadderEntity")) == 3
                for r in root.findall(".//RungEntity")
            )
            == 1
        )
    result = {
        "status": "pass",
        "distinct_timeline_positions": 7,
        "exchange_starts": 1,
        "completions": 1,
        "skipped_invocations": [2, 3, 5],
        "VM_paths": [p[0] for p in programs],
        "native_absent_paths": 2,
        "literal_positive_outputs_Q0_3": positive,
        "literal_absent_outputs_Q0_3": absent,
        "new_compiler_bundles": 2,
        "shape": {
            "canonical_rungs": len(programs[0][1].rungs),
            "canonical_instructions": sum(map(len, programs[0][1].rungs)),
        },
    }
    put("control-entry-results.json", result)
    return result


def plain_tree(node):
    """Ignore indentation only; preserve ordered hardware fields and attributes."""
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        (node.text or "").strip(),
        tuple(plain_tree(child) for child in node),
    )


def verify_outputs():
    template = ET.parse(TEMPLATE).getroot()
    bundles = []
    origins = []
    for case in ORACLES:
        for suffix in ("build", "reverse-build"):
            folder = HERE / (case + "-" + suffix)
            report = json.loads((folder / "report.json").read_text())
            for name, expected in report["artifacts"].items():
                assert digest(folder / name) == expected, (folder, name)
            root = ET.parse(folder / "program.smbp").getroot()
            assert plain_tree(root.find("HardwareConfiguration")) == plain_tree(
                template.find("HardwareConfiguration")
            )
            assert root.findtext("ManagementLevel") == "FunctLevelMan21_0"
            assert (
                root.findtext(".//SerialLineConfiguration/Addressing")
                == "MasterAddressing"
            )
            imported = load_project(folder / "program.smbp")
            ir = Program.from_dict(
                json.loads((folder / "program.m200.json").read_text())
            )
            groups = imported.metadata["native_full_pin_groups"]
            assert len(groups) == len(KEYS[case])
            for group in groups:
                start = group["canonical_start"]
                assert (
                    group["source_origins"]
                    == ir.metadata["rung_origins"][start : start + 5]
                )
                assert all(
                    origin.get("file") and origin.get("line")
                    for origin in group["source_origins"]
                )
                origins.append(
                    {
                        "case": case,
                        "path": suffix,
                        "key": group["key"],
                        "source_origins": group["source_origins"],
                    }
                )
            assert (
                imported.communications == ir.communications
                and imported.timers == ir.timers
            )
            bundles.append(
                {
                    "path": folder.name,
                    "owned_artifacts": len(report["artifacts"]),
                    "hardware_equal": True,
                    "actual_Man21_SL1_master": True,
                    "groups": len(groups),
                }
            )
    verification = {
        "status": "pass",
        "bundles": bundles,
        "group_origin_sets": origins,
        "groups_verified": len(origins),
    }
    put("verification.json", verification)
    return verification


def inventory():
    records = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS"}:
            records.append(
                {
                    "path": path.relative_to(HERE).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
    put("MANIFEST.json", {"schema": 1, "status": "pass", "files": records})
    (HERE / "SHA256SUMS").write_text(
        "".join(record["sha256"] + "  " + record["path"] + "\n" for record in records)
    )
    for record in records:
        assert digest(HERE / record["path"]) == record["sha256"]


def main(argv=None):
    global HERE, ORACLES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Fresh artifact directory; must not exist. Default: retained system temporary directory.",
    )
    args = parser.parse_args(argv)
    if not __debug__:
        parser.error("Assertions must remain enabled; do not use Python -O.")
    if args.output is None:
        HERE = Path(tempfile.mkdtemp(prefix="m200-modbus-full-pin-"))
    else:
        HERE = args.output.expanduser().resolve()
        if HERE.exists():
            parser.error(
                "Output already exists; choose a fresh directory. Existing data is never replaced."
            )
        HERE.mkdir(parents=True)
    print("Artifacts: " + str(HERE), flush=True)
    started = time.monotonic()
    ORACLES = literal_oracles()
    put(
        "literal-oracles.json",
        {
            "method": "Independent literal timelines; native callback replay is composition evidence, not native transport.",
            "cases": ORACLES,
        },
    )
    for case, source in SOURCES.items():
        (HERE / (case + ".cpp")).write_text(source)
    pins = {
        str(path.relative_to(ROOT)): digest(path)
        for path in sorted((ROOT / "m200").glob("*.py"))
    }
    for path in (ROOT / "sdk/plc.hpp", Path(__file__).resolve()):
        pins[str(path.relative_to(ROOT))] = digest(path)
    for case, expected in FIXTURE_DIGESTS.items():
        path = ROOT / (
            "tests/fixtures/official_tm200ce40t_modbus_full_pin_" + case + ".smbp"
        )
        assert digest(path) == expected, ("Authentic fixture differs", path)
        assert len(load_project(path).rungs) == 5
        pins[str(path.relative_to(ROOT))] = expected
        provenance = path.with_suffix(".provenance.json")
        pins[str(provenance.relative_to(ROOT))] = digest(provenance)
    put("input-pin.json", pins)
    generated_inputs = {
        name: digest(HERE / name)
        for name in ("multi.cpp", "cascade.cpp", "literal-oracles.json")
    }
    outcomes = {}
    for case in ORACLES:
        print("CASE " + case, flush=True)
        source = HERE / (case + ".cpp")
        build = HERE / (case + "-build")
        command(
            [
                sys.executable,
                "-m",
                "m200",
                "compile",
                str(source),
                "--template",
                str(TEMPLATE),
                "-o",
                str(build),
            ],
            case + "-compile.log",
        )
        program = compile_source(source)
        ir = Program.from_dict(json.loads((build / "program.m200.json").read_text()))
        imported = load_project(build / "program.smbp")
        shape = semantic_checks(program, build / "program.smbp", case)
        reverse = HERE / (case + "-reverse.cpp")
        command(
            [
                sys.executable,
                "-m",
                "m200",
                "decompile",
                str(build / "program.smbp"),
                "-o",
                str(reverse),
            ],
            case + "-decompile.log",
        )
        reverse_build = HERE / (case + "-reverse-build")
        command(
            [
                sys.executable,
                "-m",
                "m200",
                "compile",
                str(reverse),
                "--template",
                str(TEMPLATE),
                "-o",
                str(reverse_build),
            ],
            case + "-recompile.log",
        )
        rebuilt = compile_source(reverse)
        reverse_import = load_project(reverse_build / "program.smbp")
        assert (
            rebuilt.communications == program.communications
            and rebuilt.timers == program.timers
        )
        paths = [
            ("source_IR", program),
            ("serialized_IR", ir),
            ("generated_project", imported),
            ("reverse_IR", rebuilt),
            ("reverse_project", reverse_import),
        ]
        runs = [vm_path(candidate, case, label) for label, candidate in paths]
        absent = [
            absent_path(candidate, path, case, label)
            for label, candidate, path in [
                ("source", program, source),
                ("reverse", rebuilt, reverse),
            ]
        ]
        callbacks = [native_injected(program, source, case, "source")]
        from m200.communication import cpp_name

        original_names = NAMES[case]
        try:
            NAMES[case] = [cpp_name(key) for key in KEYS[case]]
            callbacks.append(native_injected(rebuilt, reverse, case, "reverse"))
        finally:
            NAMES[case] = original_names
        negative = mutations(program, case)
        decomposition = decomposition_checks(program) if case == "multi" else None
        prefix_control = prefix_mutation_control(program) if case == "multi" else None
        if prefix_control is not None:
            put("prefix-mutation-control.json", prefix_control)
        outcomes[case] = {
            "shape": shape,
            "distinct_frames": len(ORACLES[case]["rows"]),
            "vm_representation_paths": runs,
            "absent_transport_paths": absent,
            "native_callback_paths": callbacks,
            "negative_cases": negative,
            "positive_bare_decomposition": decomposition,
            "deliberate_prefix_commit_control": prefix_control,
            "status": "pass",
        }
        put(case + "-results.json", outcomes[case])
        print("PASS " + case, flush=True)
    control_trace = control_entry_trace()
    verification = verify_outputs()
    for path, expected in pins.items():
        assert digest(ROOT / path) == expected, ("Input changed during run", path)
    for path, expected in generated_inputs.items():
        assert digest(HERE / path) == expected, (
            "Generated source/oracle changed",
            path,
        )
    results = {
        "status": "pass",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "distinct_recipes": 3,
        "distinct_timeline_positions": sum(
            len(case["rows"]) for case in ORACLES.values()
        )
        + control_trace["distinct_timeline_positions"],
        "distinct_exchange_starts": sum(
            len(case["starts"]) for case in ORACLES.values()
        )
        + control_trace["exchange_starts"],
        "negative_scenarios": 5,
        "negative_destination_checks": 8,
        "native_graph_negative_scenarios": 6,
        "positive_decomposition_forms": 2,
        "positive_decomposition_destination_checks": 6,
        "control_entry_trace": control_trace,
        "deliberate_fault_mutation_controls": 1,
        "cases": outcomes,
        "input_pins": pins,
        "generated_input_pins": generated_inputs,
        "input_pins_unchanged": True,
        "verified_bundles": len(verification["bundles"]) + 2,
        "verified_group_origin_sets": verification["groups_verified"],
        "network_GUI_Wine_physical_CI": False,
        "full_suite_run": False,
        "limits": [
            "Native callbacks replay literal outcomes; they test C++ composition, not a native protocol implementation.",
            "SL1 arbitration, clock, edge and error behavior are local reference-model policies.",
            "Representation paths repeat 67 base positions plus seven control-entry positions, not extra distinct cases.",
            "No exact-complex-project official editor, simulator or physical PLC validation.",
        ],
    }
    put("results.json", results)
    inventory()
    print(
        json.dumps(
            {
                key: value
                for key, value in results.items()
                if key not in {"cases", "input_pins", "generated_input_pins"}
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if HERE is not None:
            put(
                "failure.json",
                {
                    "status": "fail",
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "expectations_weakened": False,
                },
            )
        raise
