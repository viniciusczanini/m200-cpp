from .il import validate
from .model import address
from .numeric import (
    comparison,
    cpp,
    WRITES,
    word_address,
    is_operation,
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
            "plc::%s timer_%d{%d};"
            % ({"TON": "Ton", "TOF": "Tof", "TP": "Pulse"}[t.kind], i, t.milliseconds)
        )
    for key, cfg in sorted(program.communications.items()):
        lines.append(constructor_cpp(key, cfg))
    lines += ["", "void scan() {", "  bool accumulator = false;"]
    for i in sorted(program.timers):
        lines.append("  bool timer_%d_result = false;" % i)
    for index, rung in enumerate(program.rungs):
        lines.append("  // Rung %d" % index)
        if rung[0].startswith("BLK "):
            if rung[0].split(maxsplit=1)[1] in program.communications:
                key, execute, abort = parse_block(rung)
                ex = ("!" if execute[0] == "LDN" else "") + read_cpp(execute[1])
                ab = ("!" if abort[0] == "LDN" else "") + read_cpp(abort[1])
                lines.append("  " + cpp_name(key) + ".update(" + ex + "," + ab + ");")
                continue
            n = int(rung[0].split("%TM")[1])
            op, arg = rung[1].split(maxsplit=1)
            enable = ("!" if op == "LDN" else "") + read_cpp(arg)
            lines += [
                "  timer_%d_result = timer_%d.update(%s);" % (n, n, enable),
                "  " + write_cpp(rung[5][3:], "timer_%d_result" % n),
            ]
            continue
        for line in rung:
            if is_operation(line):
                target, name, values = instruction_operation(line)
                kind, index = word_address(target)
                args = [str(v) if isinstance(v, int) else cpp(v) for v in values]
                expression = (
                    args[0]
                    if name == "copy"
                    else "plc::" + name + "(" + ",".join(args) + ")"
                )
                fn = {v: k for k, v in WRITES.items()}[kind]
                lines.append(
                    "  if (accumulator) { plc::%s(%d,%s); }" % (fn, index, expression)
                )
                continue
            op, arg = line.split(maxsplit=1)
            if op in ("ST", "S", "R"):
                statement = write_cpp(
                    arg,
                    "accumulator" if op == "ST" else "true" if op == "S" else "false",
                )
                lines.append(
                    "  "
                    + (
                        statement
                        if op == "ST"
                        else "if (accumulator) { " + statement + " }"
                    )
                )
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
