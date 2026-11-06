from .il import validate
import json

from .model import address, fail, Program
from .subroutine_contexts import decoded_rung, static_operand_view
from .timers import reference as timer_reference
from .registers import (
    reference as register_reference,
    index as register_index,
    GETTERS as REGISTER_GETTERS,
)
from .flow import JUMPS, ENDS, split_label
from .native_logic import STORES, OPEN
from .bits import word_bit, is_string, bit_string
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, cpp as edge_cpp
from .edge_functions import parse as expression_edge
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
from .communication import (
    status_reference,
    BOOL_FIELDS,
    cpp_name,
    parse_block,
    constructor_cpp,
)


def read_cpp(arg):
    register = register_reference(arg)
    if register:
        return "register_%d.%s()" % (register[0], REGISTER_GETTERS[register[1]])
    counter = counter_reference(arg)
    if counter:
        return "counter_%d.%s()" % (counter[0], COUNTER_GETTERS[counter[1]])
    if ":X" in arg:
        word, bit = word_bit(arg)
        return f"plc::read_word_bit({word},{bit})"
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
    if ":X" in arg:
        word, bit = word_bit(arg)
        return f"plc::write_word_bit({word},{bit},{value});"
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
    return ("plc::write_m" if kind == "M" else "plc::output") + "(%d, %s);" % (n, value)


def to_cpp(program):
    validate(program)
    lines = [
        "// Reconstructed from ACTUAL IL. Experimental; official validation pending.",
        "// Addresses are explicit to preserve memory identity. Original C++ syntax is not recoverable.",
        "#include <plc.hpp>",
        "",
    ]
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
    resources = static_operand_view(program)
    if has_indexed(resources):
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
        # Leaf contexts are stateless and use the same explicit PLC addresses.
        # Reuse ordinary IL emission without copying a scan harness, globals or
        # committing another input/output image inside the leaf.
        leaf = Program(rungs=definition.rungs)
        source = to_cpp(leaf)
        body = source.split("void scan() {", 1)[1].rsplit("}", 1)[0]
        lines.append("void native_subroutine_body_%d() {" % number + body + "}")
        name = json.dumps(definition.name, ensure_ascii=False)
        lines.append(
            "plc::Subroutine native_subroutine_%d{%d,native_subroutine_body_%d,%s,%d};"
            % (number, number, number, name, definition.section_number)
        )
    lines += ["", "void scan() {", "  bool accumulator = false;"]
    for i in sorted(program.registers):
        lines += [
            f"  bool register_reset_{i} = false;",
            f"  bool register_store_{i} = false;",
        ]
    for i in sorted(program.timers):
        lines.append("  bool timer_%d_result = false;" % i)
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
        for op, arg in decoded_rung(rung):
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
            if op == "NUM":
                line = arg
                target, name, values = instruction_operation(line)
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
                fn = {v: k for k, v in WRITES.items()}[kind]
                arguments = str(index) + "," + expression
                if index_word is not None:
                    fn += "_indexed"
                    arguments = str(index) + "," + str(index_word) + "," + expression
                lines.append("  if (accumulator) { plc::%s(%s); }" % (fn, arguments))
                continue
            if op == "IN":
                index = int(arg[3:])
                lines.append(
                    f"  timer_{index}_result = timer_{index}.update(accumulator);"
                )
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
