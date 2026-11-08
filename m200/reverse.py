from .il import validate
from .rtc import cpp_read as rtc_cpp_read, cpp_write as rtc_cpp_write, reference as rtc_reference, parse_exec as rtc_exec
import json
import re

from .model import address, fail
from .subroutine_contexts import decoded_rung, static_operand_view, context_view
from .timers import reference as timer_reference
from .registers import (
    reference as register_reference,
    index as register_index,
    GETTERS as REGISTER_GETTERS,
)
from .flow import JUMPS, ENDS, split_label
from .sequences import reference as sequence_reference, identity as sequence_identity, PINS as SEQUENCE_INPUTS, INTERNAL_PINS as SEQUENCE_PINS
from .sequence_reverse import declarations as sequence_declarations, read_cpp as sequence_read_cpp
from .native_logic import STORES, OPEN
from .bits import word_bit, is_string, bit_string
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, cpp as edge_cpp
from .edge_functions import parse as expression_edge
from .boolean_banks import word_bit as bank_word_bit, config as boolean_config
from .counters import (
    reference as counter_reference,
    index as counter_index,
    GETTERS as COUNTER_GETTERS,
    METHODS as COUNTER_METHODS,
)
from .indexed import (
    is_indexed,
    parse as parse_indexed,
    direct_word_limit,
    has_indexed,
    is_bit_indexed,
    parse_bit,
    has_indexed_bits,
    direct_bit_limit,
)
from .numeric import (
    comparison,
    cpp,
    WRITES,
    word_address,
    instruction_operation,
)
from .communication_properties import property_reference, ENUMS, has_buffer_writes
from .communication import (
    status_reference,
    BOOL_FIELDS,
    cpp_name,
    parse_block,
    constructor_cpp,
)


def _boolean_source_address(text):
    """Render a validated native bank identity in the closed C++ grammar.

    Import may preserve legacy decimal aliases. Only emitted Boolean operand
    strings are canonicalized; the native parser and source gate stay intact.
    """
    pattern = (
        r"%(?:(?:M|S)[0-9]+|(?:I|Q)[0-9]+\.[0-9]+|"
        r"(?:MW|SW|KW)[0-9]+(?::X[0-9]+)?|"
        r"(?:IW|QW|IWS|QWS)[0-9]+\.[0-9]+(?::X[0-9]+)?)"
    )
    if re.fullmatch(pattern, text) is None:
        return text
    return re.sub(r"[0-9]+", lambda part: part[0].lstrip("0") or "0", text)


def _boolean_address_literal(text):
    return json.dumps(_boolean_source_address(text))


def read_cpp(arg):
    arg = _boolean_source_address(arg)
    if ":X" in arg:
        bank, word, _, bit = bank_word_bit(arg)
        return f"plc::read_word_bit({word},{bit})" if bank == "MW" else "plc::read_bit(" + _boolean_address_literal(arg) + ")"
    rtc = rtc_cpp_read(arg)
    if rtc is not None:
        return rtc
    sequence = sequence_reference(arg)
    if sequence:
        return sequence_read_cpp(sequence)
    register = register_reference(arg)
    if register:
        return "register_%d.%s()" % (register[0], REGISTER_GETTERS[register[1]])
    counter = counter_reference(arg)
    if counter:
        return "counter_%d.%s()" % (counter[0], COUNTER_GETTERS[counter[1]])
    timer = timer_reference(arg)
    if timer:
        return "timer_%d.done()" % timer[0]
    if is_bit_indexed(arg):
        base, index = parse_bit(arg)
        return "plc::read_m_indexed(%d,%d)" % (base, index)
    status = status_reference(arg)
    if status:
        return cpp_name(status[0]) + "." + BOOL_FIELDS[status[1]] + "()"
    if arg.startswith("["):
        a, op, b = comparison(arg)
        return (
            "("
            + cpp(a)
            + {"=": "==", "<>": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}[op]
            + cpp(b)
            + ")"
        )
    kind, n = address(arg)
    if kind == "constant":
        return "true" if n else "false"
    return {
        "M": "plc::read_m",
        "I0.": "plc::input",
        "Q0.": "plc::output_state",
        "S": "plc::system",
    }[kind] + "(%d)" % n


def write_cpp(arg, value):
    arg = _boolean_source_address(arg)
    if arg in ("%S50", "%S51", "%S59"):
        return f"plc::write_system({int(arg[2:])},{value});"
    if arg in ("%S19", "%S28", "%S39"):
        if value != "false":
            fail("system status flag is writable only by reset")
        return "plc::reset_bit(" + _boolean_address_literal(arg) + ",true);"
    sequence = sequence_reference(arg, True)
    if sequence:
        family, index, prop = sequence
        return f"{family.lower()}_{index}.set_bit({prop},{value});"
    if ":X" in arg:
        bank, word, _, bit = bank_word_bit(arg, True)
        return f"plc::write_word_bit({word},{bit},{value});" if bank == "MW" else "plc::write_bit(" + _boolean_address_literal(arg) + "," + value + ");"
    if is_bit_indexed(arg):
        base, index = parse_bit(arg)
        return "plc::write_m_indexed(%d,%d,%s);" % (base, index, value)
    if arg in ("%S17", "%S18", "%S20"):
        if value != "false":
            fail("system flag is writable only by reset")
        return (
            "plc::"
            + {
                "%S17": "clear_shift_carry",
                "%S18": "clear_arithmetic_error",
                "%S20": "clear_index_error",
            }[arg]
            + "();"
        )
    kind, n = address(arg, True)
    if kind == "S":
        return "plc::write_bit(" + _boolean_address_literal(arg) + "," + value + ");"
    return ("plc::write_m" if kind == "M" else "plc::output") + "(%d, %s);" % (n, value)


def to_cpp(program, *, _local_context=False):
    if _local_context:
        from .il import _validate_flat

        _validate_flat(program, require_resource_use=False)
    else:
        validate(program)
    lines = [
        "// Reconstructed from ACTUAL IL. Official validation pending.",
        "// Addresses are explicit to preserve memory identity. Original C++ syntax is not recoverable.",
        "#include <plc.hpp>",
        "",
    ]
    from .scalar_constants import cpp_declarations as constant_declarations, extent as constant_extent
    if constant_extent(program):
        lines.append("plc::ConstantMemory native_constant_image{%d};" % constant_extent(program))
    lines.extend(constant_declarations(program.constants))
    cfg = boolean_config(program)
    if cfg != type(cfg)():
        lines.append("plc::BooleanContext boolean_context{%s,%s};" % (str(cfg.input_image_stable).lower(), str(cfg.native_expression_edges).lower()))
    for index, value in enumerate(sorted(cfg.word_objects)):
        lines.append("plc::BooleanWord boolean_word_%d{%s};" % (index,_boolean_address_literal(value)))
    for i, t in sorted(program.timers.items()):
        lines.append(
            "plc::%s timer_%d{%d,%d,%d%s};"
            % (
                {"TON": "Ton", "TOF": "Tof", "TP": "Pulse"}[t.kind],
                i,
                i,
                t.base_ms,
                t.preset,
                ("," + str(t.retentive).lower() + "," + str(t.dynamic_preset).lower())
                if t.retentive or t.dynamic_preset
                else "",
            )
        )
    for i, c in sorted(program.counters.items()):
        lines.append(f"plc::Counter counter_{i}{{{i},{c.preset}}};")
    for i, cfg in sorted(program.registers.items()):
        lines.append(f"plc::{cfg.mode} register_{i}{{{i}}};")
    for i, cfg in sorted(program.rtcs.items()):
        values = ",".join(str(getattr(cfg, key)) for key in ("day","month","year","hours","minutes","seconds"))
        lines.append(f"plc::Rtc rtc_{i}{{{i},{values}}};")
    for i, cfg in sorted(program.schedules.items()):
        bank, index = address(cfg.output, True)
        values = ",".join(str(getattr(cfg, key)) for key in ("start_day","start_month","start_hour","start_min","end_day","end_month","end_hour","end_min","dow"))
        bank_id = 0 if bank == "M" else 1
        lines.append(f"plc::Schedule schedule_{i}{{{i},{bank_id},{index},{values}}};")
    lines += sequence_declarations(program)
    resources = static_operand_view(program)
    from .scalar_constants import has_indexed as has_indexed_constants
    dynamic_communication_buffers = has_buffer_writes(resources)
    if dynamic_communication_buffers:
        lines.append("plc::WordMemory native_communication_word_image{8000};")
    if (has_indexed(resources) or has_indexed_constants(resources)) and not dynamic_communication_buffers:
        lines.append(
            "plc::WordMemory native_word_image{%d};" % direct_word_limit(resources)
        )
    if has_indexed_bits(resources):
        lines.append(
            "plc::BitMemory native_bit_image{%d};" % direct_bit_limit(resources)
        )
    for key, cfg in sorted(program.communications.items()):
        lines.append(constructor_cpp(key, cfg))
    for number, definition in sorted(program.subroutines.items()):
        # Resource definitions belong to the whole program, not to a call.
        # Reuse ordinary IL emission without copying a scan harness, globals or
        # committing another input/output image inside the leaf.
        leaf = context_view(program, definition)
        source = to_cpp(leaf, _local_context=True)
        body = source.split("void scan() {", 1)[1].rsplit("}", 1)[0]
        lines.append("void native_subroutine_body_%d() {" % number + body + "}")
        name = json.dumps(definition.name, ensure_ascii=False)
        lines.append(
            "plc::Subroutine native_subroutine_%d{%d,native_subroutine_body_%d,%s,%d};"
            % (number, number, number, name, definition.section_number)
        )
    lines += ["", "void scan() {", "  bool accumulator = false;"]
    if program.shift_bit_registers or program.step_counters or program.drums:
        lines += [f"  bool sequence_pin_{i} = false;" for i in range(3)]
    for i in sorted(program.registers):
        lines += [
            f"  bool register_reset_{i} = false;",
            f"  bool register_store_{i} = false;",
        ]
    max_saved = max_group = 0
    for raw in program.rungs:
        _, body = split_label(raw)
        if (
            body[0].startswith("BLK ")
            and body[0].split(maxsplit=1)[1] in program.communications
        ):
            continue
        saved_depth = group_depth = 0
        for op, _ in decoded_rung(body):
            if op == "MPS":
                saved_depth += 1
                max_saved = max(max_saved, saved_depth)
            elif op == "MPP":
                saved_depth -= 1
            elif op in OPEN:
                group_depth += 1
                max_group = max(max_group, group_depth)
            elif op == ")":
                group_depth -= 1
    lines += [f"  bool native_stack_{i} = false;" for i in range(max_saved)]
    lines += [f"  bool native_group_{i} = false;" for i in range(max_group)]
    for index, raw_rung in enumerate(program.rungs):
        lines.append("  // Rung %d" % index)
        label, rung = split_label(raw_rung)
        if label is not None:
            lines.append("  native_" + label[1:] + ": ;")
        if rung[0].startswith("BLK "):
            if rung[0].split(maxsplit=1)[1] in program.communications:
                key, execute, abort = parse_block(rung)
                ex = ("!" if execute[0] == "LDN" else "") + read_cpp(execute[1])
                ab = ("!" if abort[0] == "LDN" else "") + read_cpp(abort[1])
                lines.append("  " + cpp_name(key) + ".update(" + ex + "," + ab + ");")
                continue
        saved = []
        groups = []
        sequence_pins = {}
        for op, arg in decoded_rung(rung):
            if op in SEQUENCE_PINS:
                family, i = sequence_identity(arg)
                if op == "SEQ_COMMIT":
                    pins = SEQUENCE_INPUTS[family]
                    mask = sum(1 << n for n, pin in enumerate(pins) if pin in sequence_pins)
                    values = ",".join(sequence_pins.get(pin, "false") for pin in pins)
                    prefix = "drum" if family == "DR" else family.lower()
                    lines.append(f"  {prefix}_{i}.update_pins({mask},{values});")
                    sequence_pins = {}
                else:
                    # C++ locals are declared before labels to preserve goto legality.
                    name = f"sequence_pin_{SEQUENCE_INPUTS[family].index(op[4:])}"
                    lines.append(f"  {name} = accumulator;")
                    sequence_pins[op[4:]] = name
                continue
            if op in ("REG_R", "REG_I", "REG_O"):
                i = register_index(arg)
                if op == "REG_O":
                    lines.append(
                        f"  register_{i}.update(register_reset_{i},register_store_{i},accumulator);"
                    )
                else:
                    pin = "reset" if op == "REG_R" else "store"
                    lines.append(f"  register_{pin}_{i} = accumulator;")
                continue
            if op == "CALL_SR":
                lines.append("  native_subroutine_%s.call(accumulator);" % arg)
                continue
            if op in ENDS:
                lines.append(
                    "  return;"
                    if op == "END"
                    else "  if ("
                    + ("!" if op == "ENDCN" else "")
                    + "accumulator) { return; }"
                )
                continue
            if op in ("R", "S", "CU", "CD") and arg.startswith("%C") and "." not in arg:
                method = {v: k for k, v in COUNTER_METHODS.items()}[op]
                lines.append(f"  counter_{counter_index(arg)}.{method}(accumulator);")
                continue
            function = expression_edge(op)
            if function is not None:
                kind, i = function
                lines.append(f"  accumulator = plc::{kind.lower()}({i},accumulator);")
                continue
            if op == "RTC_EXEC":
                i, rd, wr = rtc_exec(arg)
                lines.append(f"  rtc_{i}.update(accumulator,{read_cpp(rd)},{read_cpp(wr)});")
                continue
            if op == "NUM":
                line = arg
                target, name, values = instruction_operation(line)
                rtc = rtc_reference(target, True)
                if rtc:
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = args[0] if name == "copy" else "plc::" + name + "(" + ",".join(args) + ")"
                    lines.append("  if (accumulator) { " + rtc_cpp_write(target, expression) + " }")
                    continue
                sequence = sequence_reference(target, True)
                if sequence:
                    lines.append(f"  if (accumulator) {{ drum_{sequence[1]}.set_step({values[0].code}); }}")
                    continue
                register = register_reference(target, True)
                if register:
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = (
                        args[0]
                        if name == "copy"
                        else "plc::" + name + "(" + ",".join(args) + ")"
                    )
                    method = "set_input" if register[1] == "I" else "set_output"
                    lines.append(
                        f"  if (accumulator) {{ register_{register[0]}.{method}({expression}); }}"
                    )
                    continue
                counter = counter_reference(target, True)
                if counter:
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = (
                        args[0]
                        if name == "copy"
                        else "plc::" + name + "(" + ",".join(args) + ")"
                    )
                    lines.append(
                        f"  if (accumulator) {{ counter_{counter[0]}.set_preset({expression}); }}"
                    )
                    continue
                if is_string(target):
                    bank, start, count = bit_string(target, True)
                    prefix = "m" if bank == "M" else "output"
                    lines.append(
                        f"  if (accumulator) {{ plc::write_{prefix}_bits_{values[0].kind}({start},{count},{cpp(values[0])}); }}"
                    )
                    continue
                timer = timer_reference(target, True)
                if timer:
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = (
                        args[0]
                        if name == "copy"
                        else "plc::" + name + "(" + ",".join(args) + ")"
                    )
                    lines.append(
                        "  if (accumulator) { timer_%d.set_preset(%s); }"
                        % (timer[0], expression)
                    )
                    continue
                if target == "%SW17":
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = args[0] if name == "copy" else "plc::" + name + "(" + ",".join(args) + ")"
                    lines.append("  if (accumulator) { plc::write_system_word(17," + expression + "); }")
                    continue
                prop = property_reference(target, True)
                if prop:
                    args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                    expression = args[0] if name == "copy" else "plc::" + name + "(" + ",".join(args) + ")"
                    lines.append("  if (accumulator) { " + cpp_name(prop[0]) + ".set_property(plc::CommProperty::" + ENUMS[prop[1]] + "," + expression + "); }")
                    continue
                if is_indexed(target):
                    kind, index, index_word = parse_indexed(target)
                else:
                    kind, index = word_address(target)
                    index_word = None
                args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                expression = (
                    args[0]
                    if name == "copy"
                    else "plc::" + name + "(" + ",".join(args) + ")"
                )
                if index_word is None and name in ("inc_" + kind, "dec_" + kind):
                    fn = name.split("_", 1)[0] + ("_word" if kind == "i16" else "_dword")
                    lines.append(f"  if (accumulator) {{ plc::{fn}({index}); }}")
                    continue
                if index_word is None and name in tuple(stem + "_" + kind for stem in ("div", "rem", "sqrt")) and kind in ("i16", "i32"):
                    fn = name.split("_", 1)[0] + ("_word" if kind == "i16" else "_dword")
                    lines.append("  if (accumulator) { plc::%s(%d,%s); }" % (fn, index, ",".join(args)))
                    continue
                if index_word is None and name == "copy" and re.fullmatch(r"%M[WDF][0-9]+", values[0].code):
                    source_kind, source_index = word_address(values[0].code)
                    fn = {"i16": "copy_word", "i32": "copy_dword", "f32": "copy_real"}[kind]
                    lines.append("  if (accumulator) { plc::%s(%d,%d); }" % (fn, index, source_index))
                    continue
                fn = {v: k for k, v in WRITES.items()}[kind]
                arguments = str(index) + "," + expression
                if index_word is not None:
                    fn += "_indexed"
                    arguments = str(index) + "," + str(index_word) + "," + expression
                lines.append("  if (accumulator) { plc::%s(%s); }" % (fn, arguments))
                continue
            if op == "IN":
                index = int(arg[3:])
                # A direct native IN need not test Q or add a wired output.
                lines.append(f"  timer_{index}.execute(accumulator);")
                continue
            if op == "N":
                lines.append("  accumulator = !accumulator;")
                continue
            if op == "MPS":
                name = f"native_stack_{len(saved)}"
                saved.append(name)
                lines.append("  " + name + " = accumulator;")
                continue
            if op in ("MRD", "MPP"):
                lines.append("  accumulator = " + saved[-1] + ";")
                if op == "MPP":
                    saved.pop()
                continue
            if op in OPEN:
                name = f"native_group_{len(groups)}"
                groups.append((op, name))
                lines.append("  " + name + " = accumulator;")
                lines.append("  accumulator = " + read_cpp(arg) + ";")
                continue
            if op == ")":
                operator, name = groups.pop()
                lines.append(
                    "  accumulator = "
                    + name
                    + (" && " if operator == "AND(" else " || ")
                    + "accumulator;"
                )
                continue
            if op in JUMPS:
                jump = "goto native_" + arg[1:] + ";"
                lines.append(
                    "  "
                    + (
                        jump
                        if op == "JMP"
                        else "if ("
                        + ("!" if op == "JMPCN" else "")
                        + "accumulator) { "
                        + jump
                        + " }"
                    )
                )
            elif op in STORES:
                statement = write_cpp(
                    arg,
                    "!accumulator"
                    if op == "STN"
                    else "accumulator"
                    if op == "ST"
                    else "true"
                    if op == "S"
                    else "false",
                )
                lines.append(
                    "  "
                    + (
                        statement
                        if op in ("ST", "STN")
                        else "if (accumulator) { " + statement + " }"
                    )
                )
            else:
                if op in EDGE_OPS:
                    value = edge_cpp(op, arg)
                    op = EDGE_BASE[op]
                else:
                    value = read_cpp(arg)
                if op in ("LDN", "ANDN", "ORN", "XORN"):
                    value = "!" + value
                if op not in ("LD", "LDN"):
                    value = (
                        "accumulator "
                        + (
                            {
                                "AND": "&&",
                                "ANDN": "&&",
                                "OR": "||",
                                "ORN": "||",
                                "XOR": "!=",
                                "XORN": "!=",
                            }[op]
                        )
                        + " "
                        + value
                    )
                lines.append("  accumulator = " + value + ";")
    return "\n".join(lines + ["}", ""])
