"""Strict executor for the explicitly supported boolean/native-timer IL subset."""

import re

from .model import address, fail, timer_config, SYSTEM_RESETS
from .scalar_constants import parse as constant_reference, validate as validate_constants, extent as constant_extent
from .arithmetic import ArithmeticState
from .timer_lifecycle import TimerLifecycle, EVENTS as TIMER_EVENTS, elapsed as timer_elapsed
from .scalar_numeric import Indeterminate, IndeterminateMemory, known, system_word
from .rtc import RtcServices, reference as rtc_reference, validate_resources as validate_rtc, parse_exec as rtc_exec, READ_BITS as RTC_BITS
from .registers import (
    RegisterConfig,
    RegisterState,
    reference as register_reference,
    index as register_index,
)
from .register_il import referenced_ids as register_ids, PIN_OPS as REGISTER_PINS
from .sequences import reference as sequence_reference, identity as sequence_identity, FAMILIES as SEQUENCE_FAMILIES, STATES as SEQUENCE_STATES, INTERNAL_PINS as SEQUENCE_PINS, validate_configs as validate_sequences
from .timers import (
    TimerState,
    REFERENCE as TIMER_REFERENCE,
    reference as timer_reference,
    preset_value,
)
from .flow import JUMPS, ENDS, destinations, label_name, split_label
from .native_logic import decode, STORES, OPEN, timer_index
from .bits import is_string, references as bit_references, signed_pattern
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, LOADS, operand as edge_operand
from .edge_functions import parse as expression_edge
from .boolean_banks import (
    config as boolean_config, validate_operand as validate_boolean_operand,
    BooleanImages, SYSTEM_CLEAR, native_system_word, word_bit as bank_word_bit,
    system_bit_identity,
)
from .counters import (
    Counter,
    CounterState,
    reference as counter_reference,
    index as counter_index,
    ACTIONS as COUNTER_ACTIONS,
    REFERENCE as COUNTER_REFERENCE,
    preset_value as counter_preset,
)
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
from .communication_properties import property_reference
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
    from .subroutine_contexts import validate_contexts

    validate_contexts(program, _validate_flat)


def _validate_flat(program, *, require_resource_use=True):
    validate_constants(program.constants)
    boolean_config(program)
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
        if symbol_address.startswith("%K"):
            constant_reference(symbol_address)
        elif symbol_address.startswith(("%MW", "%MD", "%MF")):
            word_address(symbol_address)
        elif re.fullmatch(r"%M[0-9]+", symbol_address):
            address(symbol_address, True)
        else:
            fail("unsupported symbol metadata address")
    constant_extent(program)
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
    validate_rtc(program)
    timer_uses = set()
    validate_sequences(program)
    if not isinstance(program.registers, dict):
        fail("invalid register configuration map")
    for i, cfg in program.registers.items():
        if type(i) is not int or not 0 <= i < 4 or not isinstance(cfg, RegisterConfig):
            fail("invalid register configuration")
        RegisterConfig(cfg.mode)
    if register_ids(program.rungs) - program.registers.keys():
        fail("undefined Register block/property")
    if not isinstance(program.counters, dict):
        fail("invalid counter configuration map")
    for i, c in program.counters.items():
        if type(i) is not int or not 0 <= i < 255 or not isinstance(c, Counter):
            fail("invalid counter configuration")
        counter_preset(c.preset)
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
            if op == "RTC_EXEC":
                index, rd, wr = rtc_exec(arg)
                if index not in program.rtcs:
                    fail("undefined RTC execution")
                bit_operand(rd)
                bit_operand(wr)
                continue
            if op in SEQUENCE_PINS:
                family, i = sequence_identity(arg)
                if i not in getattr(program, SEQUENCE_FAMILIES[family]):
                    fail("undefined native sequence update")
                continue
            if op in REGISTER_PINS:
                if register_index(arg) not in program.registers:
                    fail("undefined Register update")
                continue
            if op in ENDS:
                continue
            if expression_edge(op) is not None:
                if op in expression_uses:
                    fail("duplicate expression edge instruction identity: " + op)
                expression_uses.add(op)
                continue
            if op == "NUM":
                target, name, values = instruction_operation(arg)
                if (
                    counter_reference(target, True)
                    and name == "copy"
                    and not values[0].code.startswith("%")
                ):
                    counter_preset(int(values[0].code))
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
            if op in ("CU", "CD") or (
                op in ("R", "S") and arg.startswith("%C") and "." not in arg
            ):
                if counter_index(arg) not in program.counters:
                    fail("undefined counter action: " + arg)
                continue
            if op == "IN":
                index = timer_index(arg)
                if index not in program.timers:
                    fail("undefined timer")
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
                validate_boolean_operand(program, arg, op if op in STORES else None)
                if arg in SYSTEM_RESETS and op in ("S", "ST", "STN"):
                    fail("system flag is writable only by R")
                clear_only = arg.startswith("%S") and arg[2:].isdigit() and int(arg[2:]) in SYSTEM_CLEAR
                bit_operand(arg, op in STORES and not clear_only)
    if set(jumps) - labels.keys():
        fail("jump references an undefined label")
    counter_uses = {
        int(m[1])
        for rung in program.rungs
        for line in rung
        for m in COUNTER_REFERENCE.finditer(line)
    }
    if counter_uses - program.counters.keys():
        fail("undefined counter property")
    property_uses = {
        int(m[1])
        for rung in program.rungs
        for line in rung
        for m in TIMER_REFERENCE.finditer(line)
    }
    if property_uses - program.timers.keys():
        fail("undefined timer property")
    if require_resource_use and set(program.timers) != timer_uses | property_uses:
        fail("unused timer configuration is unsupported")
    if require_resource_use and set(program.communications) != communication_uses:
        fail("unused communication configuration is unsupported")
    for rung in program.rungs:
        for line in rung:
            for ref in re.findall(REFERENCE, line):
                if status_reference(ref)[0] not in program.communications:
                    fail("undefined communication status: " + ref)


class Machine:
    def __init__(
        self, program, communication_transport=None, *, instruction_limit=100000,
        rtc=None, boolean_runtime=None
    ):
        validate(program)
        if type(instruction_limit) is not int or not 1 <= instruction_limit <= 10000000:
            fail("invalid local execution limit")
        self.program = program
        self.constants = dict(program.constants)
        self.boolean_images = BooleanImages(program, boolean_runtime)
        from .subroutine_contexts import decoded_rung, static_operand_view

        self.context_rungs = {
            None: program.rungs,
            **{i: sr.rungs for i, sr in program.subroutines.items()},
        }
        self.context_decoded = {}
        for context, rungs in self.context_rungs.items():
            values = []
            for raw in rungs:
                _, body = split_label(raw)
                communication = (
                    body[0].startswith("BLK ")
                    and body[0].split(maxsplit=1)[1] in program.communications
                )
                values.append(None if communication else decoded_rung(raw))
            self.context_decoded[context] = values
        self.decoded = self.context_decoded[None]
        all_rungs = [rung for rungs in self.context_rungs.values() for rung in rungs]
        all_decoded = [
            rung for rungs in self.context_decoded.values() for rung in rungs
        ]
        self.labels = destinations(program)
        from .subroutine_contexts import context_views

        self.context_labels = {
            number: destinations(view) for number, view in context_views(program)
        }
        self.instruction_limit = instruction_limit
        self.memory = [False] * 1024
        self.words = [0] * 8000
        self.index_error = False
        resources = static_operand_view(program)
        self.index_word_limit = direct_word_limit(resources)
        self.index_constant_limit = constant_extent(resources)
        self.index_bit_limit = direct_bit_limit(resources)
        self.communication = CommunicationEngine(communication_transport)
        for key, cfg in program.communications.items():
            self.communication.define(key, cfg)
        self.operations = {
            line: instruction_operation(line)
            for rung in all_rungs
            for line in rung
            if is_operation(line)
        }
        self.comparisons = {
            parts[1]: comparison(parts[1])
            for rung in all_rungs
            for line in rung
            for parts in [line.split(maxsplit=1)]
            if not is_operation(line) and len(parts) == 2 and parts[1].startswith("[")
        }
        self.outputs = [False] * 16
        self.now = 0
        self.first = True
        self.master_cycle_started = False
        self.current_inputs = {}
        self.edge_previous = {
            arg: False
            for arg in sorted(
                {
                    arg
                    for rung in all_decoded
                    if rung is not None
                    for op, arg in rung
                    if op in EDGE_OPS
                }
            )
        }
        self.edge_events = {}
        self.edge_sampled = False
        self.expression_history = {
            op: False
            for rung in all_decoded
            if rung is not None
            for op, _ in rung
            if expression_edge(op) is not None
        }
        self.timers = {i: TimerState(t) for i, t in program.timers.items()}
        self.timer_control = TimerLifecycle(self.timers)
        self.counters = {i: CounterState(c) for i, c in program.counters.items()}
        self.registers = {i: RegisterState(c) for i, c in program.registers.items()}
        self.arithmetic = ArithmeticState()
        self.indeterminate = IndeterminateMemory()
        self.indeterminate_bits = {}
        self.indeterminate_properties = {}
        self.rtc = RtcServices(program, rtc)
        self.sequences = {(family, i): SEQUENCE_STATES[family](cfg) for family, name in SEQUENCE_FAMILIES.items() for i, cfg in getattr(program, name).items()}
        cam_outputs = [cam.output for cfg in program.drums.values() for cam in cfg.cams]
        if len(cam_outputs) != len(set(cam_outputs)):
            fail("aliased Drum cam-output ownership requires native qualification")
        # VM construction models cold initialization, including unscanned cams.
        for (family, _), state in self.sequences.items():
            if family == "DR":
                state.initialize_outputs(self.write)

    def known_index(self, operand):
        match = re.search(r"\[%MW([0-9]+)\]", operand)
        if match:
            known(self.indeterminate.read(int(match[1]), 1))

    def copy_number(self, target, source):
        if not re.fullmatch(r"%M[WDF][0-9]+", target) or not re.fullmatch(r"%M[WDF][0-9]+", source):
            return False
        kind, dest = word_address(target)
        _, src = word_address(source)
        width = TYPES[kind][1]
        cells = self.words[src:src + width]
        unknown = [self.indeterminate.words.get(i) for i in range(src, src + width)]
        self.words[dest:dest + width] = cells
        for offset, entry in enumerate(unknown):
            if entry is None:
                self.indeterminate.words.pop(dest + offset, None)
            else:
                self.indeterminate.words[dest + offset] = entry
        return True

    def read(self, operand, inputs):
        operand = system_bit_identity(operand)
        if ":X" in operand and not operand.startswith("%MW"):
            bank, _, _, bit = bank_word_bit(operand)
            base = operand.split(":X", 1)[0]
            if bank == "SW" and native_system_word(base):
                raw = known(self.read_number(Number("i16", base)))
                return bool(raw & (1 << bit))
            return self.boolean_images.read(operand, self.words, self.constants)
        rtc = rtc_reference(operand)
        if rtc:
            return self.rtc.read(rtc)
        sequence = sequence_reference(operand)
        if sequence:
            return self.sequences[sequence[:2]].read(sequence[2])
        register = register_reference(operand)
        if register:
            return self.registers[register[0]].read(register[1])
        counter = counter_reference(operand)
        if counter:
            return self.counters[counter[0]].read(counter[1])
        timer = timer_reference(operand)
        if timer:
            return self.timers[timer[0]].read(timer[1], self.now)
        if is_bit_indexed(operand):
            self.known_index(operand)
            index, error = resolve_bit(operand, self.words, self.index_bit_limit)
            self.index_error |= error
            known(self.indeterminate_bits.get("%M" + str(index)))
            return self.memory[index]
        status = status_reference(operand)
        if status:
            return getattr(self.communication.status(status[0]), BOOL_FIELDS[status[1]])
        if operand.startswith("["):
            return compare(self.words, self.comparisons[operand], self.read_number)
        kind, index = address(operand)
        if kind == "MWbit":
            self.indeterminate.read_bit(index // 16, index % 16)
            return bool(self.words[index // 16] & (1 << (index % 16)))
        if operand in self.indeterminate_bits:
            known(self.indeterminate_bits[operand])
        if kind == "constant":
            return bool(index)
        if kind == "M":
            return self.memory[index]
        if kind == "I0.":
            return bool(inputs.get(index, inputs.get(str(index), False)))
        if kind == "Q0.":
            return self.outputs[index]
        if index in RTC_BITS:
            return self.rtc.bit(index)
        if index == 13:
            return self.first
        if index == 20:
            return self.index_error
        if index == 17:
            return self.arithmetic.carry
        if index == 18:
            return self.arithmetic.overflow
        if index in (4,5,6,7):
            period = {4: 10, 5: 100, 6: 1000, 7: 60000}[index]
            return bool((self.now // (period // 2)) % 2)
        return self.boolean_images.external("read_bit", operand)

    def write(self, operand, value):
        operand = system_bit_identity(operand)
        if ":X" in operand and not operand.startswith("%MW"):
            bank, _, _, bit = bank_word_bit(operand, True)
            base = operand.split(":X", 1)[0]
            if bank == "SW" and native_system_word(base, True):
                old = known(self.read_number(Number("i16", base))) & 65535
                mask = 1 << bit
                raw = (old | mask) if value else (old & (65535 ^ mask))
                self.write_number(base, raw - 65536 if raw >= 32768 else raw)
                return
            self.boolean_images.write(operand, value, self.words)
            return
        if operand in ("%S50", "%S51", "%S59"):
            self.rtc.set_bit(int(operand[2:]), value)
            return
        sequence = sequence_reference(operand, True)
        if sequence:
            self.sequences[sequence[:2]].write(sequence[2], bool(known(value)))
            return
        if operand in ("%S17", "%S18"):
            if value:
                fail("system arithmetic flags can only be cleared")
            self.arithmetic.clear(int(operand[2:]))
            return
        if operand == "%S20":
            if value:
                fail("system index-error bit can only be cleared")
            self.index_error = False
            return
        if operand in ("%S19", "%S28", "%S39"):
            if value:
                fail("system status flag can only be cleared")
            self.boolean_images.external("write_bit", operand, False)
            return
        if is_bit_indexed(operand):
            self.known_index(operand)
            index, error = resolve_bit(operand, self.words, self.index_bit_limit)
            self.index_error |= error
            self.indeterminate_bits.pop("%M" + str(index), None)
            self.memory[index] = bool(value)
            return
        kind, index = address(operand, True)
        if kind == "MWbit":
            mask = 1 << (index % 16)
            self.indeterminate.write_bit(index // 16, index % 16)
            old = self.words[index // 16]
            self.words[index // 16] = (old | mask) if value else (old & (65535 ^ mask))
            return
        self.indeterminate_bits.pop(operand, None)
        if kind == "S":
            self.boolean_images.external("write_bit", operand, bool(value))
            return
        (self.memory if kind == "M" else self.outputs)[index] = bool(value)

    def read_number(self, value):
        constant = constant_reference(value.code)
        if constant:
            kind, index, indexed = constant
            if indexed is not None:
                known(self.indeterminate.read(indexed, 1))
                raw = self.words[indexed]
                position = index + (raw - 65536 if raw >= 32768 else raw)
                if position < 0 or position + TYPES[kind][1] > self.index_constant_limit:
                    self.index_error = True
                else:
                    index = position
            raw = self.constants.get(index, 0)
            if kind != "i16":
                raw |= self.constants.get(index + 1, 0) << 16
            if kind == "f32":
                from .scalar_numeric import Real32
                return Real32(raw)
            width = 16 if kind == "i16" else 32
            return raw - (1 << width) if raw >= (1 << (width - 1)) else raw
        if system_word(value.code):
            raw = self.arithmetic.float_status
            return raw - 65536 if raw >= 32768 else raw
        if value.code in self.indeterminate_properties:
            return self.indeterminate_properties[value.code]
        prop = property_reference(value.code)
        if prop:
            return self.communication.read_property(*prop)
        rtc = rtc_reference(value.code)
        if rtc:
            return self.rtc.read(rtc)
        sequence = sequence_reference(value.code)
        if sequence:
            return self.sequences[sequence[:2]].read(sequence[2])
        register = register_reference(value.code)
        if register:
            return self.registers[register[0]].read(register[1])
        counter = counter_reference(value.code)
        if counter:
            return self.counters[counter[0]].read(counter[1])
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
            self.known_index(value.code)
            kind, index, error = resolve_indexed(
                value.code, self.words, self.index_word_limit
            )
            self.index_error |= error
            value = Number(kind, "%" + TYPES[kind][0] + str(index))
        if value.code.startswith(("%MW", "%MD", "%MF")):
            kind, index = word_address(value.code)
            unknown = self.indeterminate.read(index, TYPES[kind][1])
            if unknown is not None:
                return unknown
        status = status_reference(value.code)
        return (
            getattr(self.communication.status(status[0]), NUM_FIELDS[status[1]][1])
            if status
            else read_number(self.words, value)
        )

    def write_number(self, target, value):
        if system_word(target, True):
            self.arithmetic.float_status = known(value) & 65535
            return
        if re.fullmatch(r"%(?:R|C|TM)[0-9]+\.[A-Z]+", target):
            if isinstance(value, Indeterminate):
                self.indeterminate_properties[target] = value
                return
            self.indeterminate_properties.pop(target, None)
        prop = property_reference(target, True)
        if prop:
            self.communication.write_property(*prop, known(value))
            return
        rtc = rtc_reference(target, True)
        if rtc:
            self.rtc.write(rtc, known(value))
            return
        sequence = sequence_reference(target, True)
        if sequence:
            self.sequences[sequence[:2]].write(sequence[2], known(value))
            return
        register = register_reference(target, True)
        if register:
            self.registers[register[0]].write(register[1], value)
            return
        counter = counter_reference(target, True)
        if counter:
            self.counters[counter[0]].set_preset(value)
            return
        if is_string(target):
            if isinstance(value, Indeterminate):
                for ref in bit_references(target):
                    self.indeterminate_bits[ref] = value
                return
            for i, ref in enumerate(bit_references(target)):
                self.write(ref, bool(value & (1 << i)))
            return
        timer = timer_reference(target, True)
        if timer:
            self.timers[timer[0]].set_preset(value, self.now)
            return
        if is_indexed(target):
            self.known_index(target)
            kind, index, error = resolve_indexed(
                target, self.words, self.index_word_limit
            )
            self.index_error |= error
            target = "%" + TYPES[kind][0] + str(index)
        kind, index = word_address(target)
        self.indeterminate.write(index, TYPES[kind][1], value)
        if not isinstance(value, Indeterminate):
            write_number(self.words, target, value)

    def timer(self, index, enabled):
        if enabled:
            known(self.indeterminate_properties.get(f"%TM{index}.P"))
        return self.timers[index].update(enabled, self.now)

    def timer_event(self, event):
        """Timer-only host lifecycle event, outside the generated program.

        STOP/off suppress scans and leave the process image untouched here.
        CPU-wide memory/startup flags and physical fallback are not modeled by
        these timer hooks and must be applied by the owning lifecycle adapter.
        """
        self.timer_control.apply(event, self.now)

    def advance_time(self, dt_ms):
        """Advance timers without executing IL (including while STOPped)."""
        dt_ms = timer_elapsed(dt_ms)
        self.now += dt_ms
        self.timer_control.refresh(self.now)
        self.rtc.advance(dt_ms)

    def begin_master_cycle(self, inputs=None):
        """Sample native I/M edges once at the owning MAST boundary.

        A task adapter may invoke step(master_cycle=False) repeatedly after
        this call; event/task entry alone never advances MAST history.
        """
        inputs = {} if inputs is None else inputs
        if not isinstance(inputs, dict) or any(str(k) not in {str(i) for i in range(24)} or v not in (True,False,0,1) for k,v in inputs.items()):
            fail("invalid master-cycle input image")
        # S13 belongs to the first MAST interval, not to each task body.
        # A new boundary closes the preceding interval even when only
        # non-master step() calls executed within it.
        if self.master_cycle_started:
            self.first = False
        self.master_cycle_started = True
        self.rtc.begin_scan(self.write)
        for ref, previous in self.edge_previous.items():
            current = self.read(ref, inputs)
            self.edge_events[ref] = (current and not previous, previous and not current)
            self.edge_previous[ref] = current
        self.edge_sampled = True

    def step(self, inputs=None, dt_ms=10, timer_event=None, *, master_cycle=True):
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
        if type(master_cycle) is not bool:
            fail("master_cycle must be bool")
        if not master_cycle and dt_ms != 0:
            fail("non-master invocation requires dt_ms=0; owning scheduler advances time")
        if timer_event is not None:
            self.timer_event(timer_event)
        if not self.timer_control.running:
            self.advance_time(dt_ms)
            return list(self.outputs)
        pc = 0
        self.current_inputs = inputs
        if master_cycle:
            self.begin_master_cycle(inputs)
        elif self.edge_previous and not self.edge_sampled:
            fail("native contacts need an explicit initial master-cycle sample")
        executed = 0

        def consume(count):
            nonlocal executed
            executed += count
            if executed > self.instruction_limit:
                fail(
                    "local execution limit exceeded; physical watchdog is not simulated"
                )

        context = None
        return_pc = None
        while True:
            if pc >= len(self.context_rungs[context]):
                if context is None:
                    break
                context, pc, return_pc = None, return_pc, None
                continue
            _, rung = split_label(self.context_rungs[context][pc])
            current_decoded = self.context_decoded[context][pc]
            pc += 1
            if rung[0].startswith("BLK "):
                if rung[0].split(maxsplit=1)[1] in self.program.communications:
                    consume(len(rung))  # communication block is one atomic local update
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
            register_pins = []
            sequence_pins = {}
            for op, arg in current_decoded:
                consume(1)  # an early END must not consume its skipped suffix
                if op in SEQUENCE_PINS:
                    if op == "SEQ_COMMIT":
                        self.sequences[sequence_identity(arg)].update(sequence_pins, self.write)
                        sequence_pins = {}
                    else:
                        sequence_pins[op[4:]] = bool(known(acc))
                    continue
                if op in REGISTER_PINS:
                    register_pins.append(bool(acc))
                    if op == "REG_O":
                        if any(register_pins):
                            for field in ("I", "O"):
                                known(self.indeterminate_properties.get(f"%R{register_index(arg)}.{field}"))
                        self.registers[register_index(arg)].update(*register_pins)
                    continue
                if op in ENDS:
                    if op == "END" or (acc if op == "ENDC" else not acc):
                        # Finish this task's scan, including the bookkeeping below.
                        # No controller STOP state or task scheduler is simulated.
                        if context is None:
                            pc = len(self.program.rungs)
                        else:
                            context, pc, return_pc = None, return_pc, None
                        break
                    continue
                if op == "CALL_SR":
                    if acc:
                        if context is not None or return_pc is not None:
                            fail("native SR nesting is prohibited")
                        context, return_pc, pc = int(arg), pc, 0
                        break
                    continue
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
                if op == "RTC_EXEC":
                    index, rd, wr = rtc_exec(arg)
                    self.rtc.rtcs[index].update(self.rtc, acc, self.read(rd, inputs), self.read(wr, inputs))
                    continue
                if op == "NUM":
                    if acc:
                        target, name, values = self.operations[arg]
                        kind = (
                            values[0].kind
                            if is_string(target)
                            else reference_address(target)[0]
                        )
                        if name == "copy" and self.copy_number(target, values[0].code):
                            continue
                        args = [
                            self.read_number(v) if not isinstance(v, int) else v
                            for v in values
                        ]
                        self.write_number(
                            target, evaluate(name, args, kind, flags=self.arithmetic)
                        )
                    continue
                if op == "IN":
                    self.timer(timer_index(arg), acc)
                    continue
                if op in COUNTER_ACTIONS and arg.startswith("%C") and "." not in arg:
                    if acc:
                        known(self.indeterminate_properties.get(f"%C{counter_index(arg)}.P"))
                    self.counters[counter_index(arg)].action(op, acc)
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
                        pc = self.context_labels[context][arg]
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
        self.rtc.advance(dt_ms)
        self.now += dt_ms
        if master_cycle:
            self.first = False
        return list(self.outputs)


def validate_frames(frames):
    if not isinstance(frames, list) or not 1 <= len(frames) <= 100000:
        fail("trace must be an array of 1..100000 frames")
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) - {"inputs", "dt_ms", "timer_event"}:
            fail("invalid trace frame")
        if "timer_event" in frame and (
            type(frame["timer_event"]) is not str or frame["timer_event"] not in TIMER_EVENTS
        ):
            fail("invalid timer lifecycle trace event")
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
