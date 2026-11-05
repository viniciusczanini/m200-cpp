from .il import validate
from .model import address


def read_cpp(arg):
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
    lines += ["", "void scan() {", "  bool accumulator = false;"]
    for i in sorted(program.timers):
        lines.append("  bool timer_%d_result = false;" % i)
    for index, rung in enumerate(program.rungs):
        lines.append("  // Rung %d" % index)
        if rung[0].startswith("BLK "):
            n = int(rung[0].split("%TM")[1])
            lines += [
                "  timer_%d_result = timer_%d.update(%s);"
                % (n, n, read_cpp(rung[1][3:])),
                "  " + write_cpp(rung[5][3:], "timer_%d_result" % n),
            ]
            continue
        for line in rung:
            op, arg = line.split()
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
