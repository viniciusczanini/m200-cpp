"""Typed numeric IL subset, independently evaluated with explicit error domains.

Sources: EIO0000003289.04 pp49-60,67-72; EIO0000002019.06 pp322-323.
Integer context models sticky S18 and S17/last-bit with signed modular results.
Exact overflow bits beyond the G55 ADDword example remain a local policy.
Unspecified integer results propagate until overwritten; observing one is an error.
"""

import math
import re
import struct
from dataclasses import dataclass

from .model import fail, CompileError
from .arithmetic import INTEGER_STEMS
from .scalar_constants import PATTERN as CONSTANT_PATTERN, parse as constant_reference
from .scalar_numeric import (OPS as SCALAR_OPS, SYSTEM_WORD_PATTERN, system_word,
    Indeterminate, known, real32, Real32, evaluate_float)
from .conversions import NUMERIC_CONVERSIONS, evaluate_conversion, needs_word_snapshot
from .communication import status_reference, NUM_FIELDS, NUM_REFERENCE, cpp_name
from .communication_properties import property_reference, ENUMS, has_buffer_writes
from .indexed import WORD_PATTERN, is_indexed, parse as parse_indexed
from .bits import STRING_PATTERN, is_string, bit_string
from .timers import (
    NUMERIC_PATTERN as TIMER_PATTERN,
    reference as timer_reference,
    GETTERS,
)

from .counters import (
    NUMERIC_PATTERN as COUNTER_PATTERN,
    reference as counter_reference,
    GETTERS as COUNTER_GETTERS,
)

from .registers import (
    NUMERIC_PATTERN as REGISTER_PATTERN,
    reference as register_reference,
    GETTERS as REGISTER_GETTERS,
)

from .rtc import NUMERIC_PATTERN as RTC_PATTERN, numeric_reference as rtc_reference, cpp_read as rtc_cpp

from .sequences import NUMERIC_PATTERN as DRUM_PATTERN, reference as sequence_reference

VALUE_PATTERN = (
    "(?:"
    + WORD_PATTERN
    + "|" + SYSTEM_WORD_PATTERN
    + "|" + CONSTANT_PATTERN
    + "|"
    + TIMER_PATTERN
    + "|"
    + COUNTER_PATTERN
    + "|"
    + REGISTER_PATTERN
    + "|" + NUM_REFERENCE
    + "|"
    + RTC_PATTERN
    + "|"
    + DRUM_PATTERN
    + ")"
)

TYPES = {"i16": ("MW", 1), "i32": ("MD", 2), "f32": ("MF", 2)}
READS = {"read_word": "i16", "read_dword": "i32", "read_real": "f32"}
WRITES = {"write_word": "i16", "write_dword": "i32", "write_real": "f32"}
# API: output type, input types, IL token, syntax shape.
OPS = {}
for typ in TYPES:
    for name, token in [("add", "+"), ("sub", "-"), ("mul", "*"), ("div", "/")]:
        OPS[name + "_" + typ] = (typ, (typ, typ), token, "binary")
    OPS["sqrt_" + typ] = (typ, (typ,), "SQRT", "function")
for typ in ("i16", "i32"):
    OPS["rem_" + typ] = (typ, (typ, typ), "REM", "binary")
    for name in ("shl", "shr", "rol", "ror"):
        OPS[name + "_" + typ] = (typ, (typ, "shift"), name.upper(), "function")
for name in ("and", "or", "xor"):
    OPS[name + "_i16"] = ("i16", ("i16", "i16"), name.upper(), "binary")
OPS["not_i16"] = ("i16", ("i16",), "NOT", "function")
OPS["abs_i32"] = ("i32", ("i32",), "ABS", "function")
for name in (
    "abs",
    "trunc",
    "log",
    "ln",
    "exp",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
):
    OPS[name + "_f32"] = ("f32", ("f32",), name.upper(), "function")
for name, dest, src, token in [
    ("int_to_real", "f32", "i16", "INT_TO_REAL"),
    ("dint_to_real", "f32", "i32", "DINT_TO_REAL"),
    ("real_to_int", "i16", "f32", "REAL_TO_INT"),
    ("real_to_dint", "i32", "f32", "REAL_TO_DINT"),
    ("low_word", "i16", "i32", "LW"),
    ("high_word", "i16", "i32", "HW"),
]:
    OPS[name] = (dest, (src,), token, "function")
OPS.update(NUMERIC_CONVERSIONS)
OPS.update(SCALAR_OPS)


@dataclass(frozen=True)
class Number:
    kind: str
    code: str


def f32(value):
    try:
        result = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, ValueError):
        fail("numeric arithmetic error: REAL32 overflow")
    if not math.isfinite(result):
        fail("numeric arithmetic error: non-finite REAL32")
    return result


def checked(value, kind):
    if kind == "f32":
        return f32(value)
    low, high = (-32768, 32767) if kind == "i16" else (-2147483648, 2147483647)
    if not low <= value <= high:
        fail("numeric arithmetic error: " + kind + " overflow")
    return int(value)


def literal(value, kind):
    value = checked(value, kind)
    if kind != "f32":
        return Number(kind, str(value))
    return Number(
        kind,
        format(value, ".9g")
        + (
            ".0"
            if kind == "f32" and float(value).is_integer() and abs(value) < 1e8
            else ""
        ),
    )


def expect(value, kind):
    if not isinstance(value, Number):
        fail("numeric operand required: " + kind)
    if value.kind == "literal":
        # Only integer literals can be contextually converted. REAL32 literals
        # already carry f32 and cannot silently become an integer.
        return literal(int(value.code), kind)
    if value.kind != kind:
        fail(
            "numeric type mismatch: "
            + value.kind
            + " to "
            + kind
            + "; use an explicit plc conversion"
        )
    return value


def boolean(value):
    if isinstance(value, Number):
        fail("numeric value cannot be implicitly converted to bool; use a comparison")
    return value


def word_address(text):
    m = re.fullmatch(r"%(MW|MD|MF)(0|[1-9][0-9]*)", text)
    if not m:
        fail("unsupported numeric address: " + text)
    prefix, index = m.group(1), int(m.group(2))
    kind = {"MW": "i16", "MD": "i32", "MF": "f32"}[prefix]
    width = TYPES[kind][1]
    if index + width > 8000:
        fail("numeric address exceeds shared 8000-word memory: " + text)
    return kind, index


def reference_address(text, writable=False):
    constant = constant_reference(text, writable)
    if constant:
        return constant[:2]
    if system_word(text, writable):
        return "i16", 17
    status = status_reference(text)
    if status:
        if status[1] not in NUM_FIELDS or (writable and not property_reference(text, True)):
            fail("communication output is read-only or nonnumeric: " + text)
        return NUM_FIELDS[status[1]][0], 0
    rtc = rtc_reference(text, writable)
    if rtc:
        return "i16", rtc[1]
    sequence = sequence_reference(text, writable)
    if sequence:
        if sequence[0] != "DR" or sequence[2] != "S":
            fail("native sequence property is not numeric: " + text)
        return "i16", sequence[1]
    register = register_reference(text, writable)
    if register:
        if register[1] not in ("I", "O"):
            fail("register output is not numeric: " + text)
        return "i16", register[0]
    counter = counter_reference(text, writable)
    if counter:
        if counter[1] not in ("P", "V"):
            fail("counter output is not numeric: " + text)
        return "i16", counter[0]
    timer = timer_reference(text, writable)
    if timer:
        if timer[1] not in ("P", "V"):
            fail("timer output is not numeric: " + text)
        return "i16", timer[0]
    if is_indexed(text):
        kind, base, _ = parse_indexed(text)
        return kind, base
    return word_address(text)


def operand(text, kind):
    if text.startswith("%"):
        status = status_reference(text)
        actual = (
            NUM_FIELDS[status[1]][0]
            if status and status[1] in NUM_FIELDS
            else reference_address(text)[0]
        )
        if actual != kind:
            fail("mixed numeric IL types")
        return Number(kind, text)
    based = re.fullmatch(r"(2|8|16)#([0-9A-Fa-f]+)", text)
    if based and kind != "f32":
        base, digits = int(based[1]), based[2]
        try:
            raw = int(digits, base)
        except ValueError:
            fail("invalid based numeric literal: " + text)
        width = 16 if kind == "i16" else 32
        if raw >= 1 << width:
            fail("based numeric literal exceeds operand width")
        return literal(raw - (1 << width) if raw >= 1 << (width - 1) else raw, kind)
    pattern = (
        r"-?(?:0|[1-9][0-9]*)"
        if kind != "f32"
        else r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    )
    if not re.fullmatch(pattern, text):
        fail("invalid numeric IL literal: " + text)
    literal(float(text) if kind == "f32" else int(text), kind)
    return Number(kind, text)


def operation(line):
    """Parse one closed operation (never eval source text)."""
    unary = re.fullmatch(r"\[\s*(INC|DEC)\s+(%(?:MW|MD)[0-9]+)\s*\]", line)
    if unary:
        token, target = unary.groups()
        typ, _ = word_address(target)
        return (
            target,
            token.lower() + "_" + typ,
            [Number(typ, target)],
        )
    m = re.fullmatch(
        r"\[\s*(" + VALUE_PATTERN + "|" + STRING_PATTERN + r")\s*:=\s*(.*?)\s*\]", line
    )
    if not m:
        fail("unsupported numeric operation: " + line)
    target, expression = m.groups()
    sequence = sequence_reference(target, True)
    if sequence:
        if sequence[0] != "DR" or sequence[2] != "S" or re.fullmatch(r"[0-7]", expression.strip()) is None:
            fail("Drum .S write requires decimal immediate 0..7")
        return target, "copy", [Number("i16", expression.strip())]
    expression = expression.strip()
    if is_string(target) or is_string(expression):
        source_string = is_string(expression)
        target_string = is_string(target)
        if target_string:
            tb, ts, tl = bit_string(target, True)
            if source_string:
                sb, ss, sl = bit_string(expression)
                if tl != sl:
                    fail("unequal native bit string lengths are unverified")
                if tb == sb and ts != ss and max(ts, ss) < min(ts + tl, ss + sl):
                    fail(
                        "overlapping native bit string copy is unverified; use explicit packed snapshot"
                    )
                typ = "i16" if tl <= 16 else "i32"
            elif expression.startswith("%"):
                typ = reference_address(expression)[0]
            else:
                typ = "i16" if tl <= 16 else "i32"
            if typ not in ("i16", "i32"):
                fail("bit string carrier must be word/dword")
            bit_string(target, True, 16 if typ == "i16" else 32)
        else:
            typ = reference_address(target, True)[0]
            if typ not in ("i16", "i32"):
                fail("bit string carrier must be word/dword")
        if source_string:
            bit_string(expression, width=16 if typ == "i16" else 32)
            value = Number(typ, expression)
        else:
            value = operand(expression, typ)
        return target, "copy", [value]
    typ, _ = reference_address(target, True)
    # Match longer names via exact token, not prefix. Arithmetic is one operator.
    for name, (out, args, token, shape) in OPS.items():
        if out != typ or shape == "inplace":
            continue
        if shape == "binary":
            atom = (
                r"("
                + NUM_REFERENCE
                + r"|"
                + VALUE_PATTERN
                + r"|(?:2|8|16)#[0-9A-Fa-f]+|-?[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)"
            )
            pat = atom + r"\s*" + re.escape(token) + r"\s*" + atom
        else:
            pat = re.escape(token) + r"\s*\((.*)\)"
        found = re.fullmatch(pat, expression)
        if not found:
            continue
        values = (
            list(found.groups()) if shape == "binary" else found.group(1).split(",")
        )
        if len(values) != len(args):
            fail("invalid numeric function arity")
        parsed = []
        for value, argkind in zip(values, args):
            value = value.strip()
            if argkind == "shift":
                if not value.isdigit() or not 1 <= int(value) <= (
                    16 if typ == "i16" else 32
                ):
                    fail("shift count outside operand width")
                parsed.append(int(value))
            else:
                parsed.append(operand(value, argkind))
        if any(
            isinstance(v, Number) and needs_word_snapshot(token, v.code) for v in parsed
        ):
            fail(
                "native "
                + token
                + " requires word operands; copy the value to MW first"
            )
        if (
            shape == "function"
            and token != "CONCATW"
            and not parsed[0].code.startswith("%")
        ):
            fail("numeric function requires an object operand")
        if (
            is_indexed(target)
            or any(isinstance(v, Number) and (is_indexed(v.code) or (v.code.startswith("%K") and "[" in v.code)) for v in parsed)
        ) and (typ != "i16" or shape != "binary"):
            fail(
                "indexed operands in this numeric instruction require a direct snapshot"
            )
        return target, name, parsed
    return target, "copy", [operand(expression, typ)]


def is_operation(line):
    return line.startswith("[") or re.match(r"OPER(?:\s|$)", line) is not None


def instruction_operation(line):
    if line.startswith("OPER"):
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or parts[0] != "OPER":
            fail("invalid OPER instruction")
        line = parts[1]
    return operation(line)


def comparison(text):
    m = re.fullmatch(
        r"\[\s*("
        + NUM_REFERENCE
        + r"|"
        + VALUE_PATTERN
        + r")\s*(>=|<=|<>|=|>|<)\s*(.+)\s*\]",
        text,
    )
    if not m:
        fail("unsupported numeric comparison: " + text)
    first, op, second = m.groups()
    if is_indexed(first) or (first.startswith("%K") and "[" in first):
        fail("indexed comparison first operand requires a direct snapshot")
    status = status_reference(first)
    kind = (
        NUM_FIELDS[status[1]][0]
        if status and status[1] in NUM_FIELDS
        else reference_address(first)[0]
    )
    return operand(first, kind), op, operand(second.strip(), kind)


def evaluate(name, values, kind, flags=None):
    stem = name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1] in TYPES else name
    if any(isinstance(v, Indeterminate) for v in values):
        return next(v for v in values if isinstance(v, Indeterminate))
    if kind == "f32" and name not in NUMERIC_CONVERSIONS:
        return evaluate_float(stem, values, flags)
    integer_flags = (
        flags is not None and kind in ("i16", "i32") and stem in INTEGER_STEMS
    )
    # REAL_TO_* errors set S18 (G3289 p72), but their invalid results must
    # remain refusals: including them in integer_flags would modular-wrap them.
    conversion_flags = flags is not None and name in ("real_to_int", "real_to_dint")
    try:
        if name == "copy":
            result = values[0]
        elif name in NUMERIC_CONVERSIONS:
            result = evaluate_conversion(name, values)
        else:
            stem = name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1] in TYPES else name
            a = values[0]
            b = values[1] if len(values) > 1 else None
            width = 16 if kind == "i16" else 32
            mask = (1 << width) - 1
            if stem in ("inc", "dec"):
                result = a + (1 if stem == "inc" else -1)
            elif stem == "add":
                result = a + b
            elif stem == "sub":
                result = a - b
            elif stem == "mul":
                result = a * b
            elif stem in ("div", "rem"):
                if b == 0:
                    if integer_flags:
                        flags.overflow = True
                        return Indeterminate("integer division by zero")
                    fail("numeric arithmetic error: division by zero")
                if kind == "f32":
                    result = a / b
                else:
                    q = abs(a) // abs(b) * (-1 if (a < 0) != (b < 0) else 1)
                    if not integer_flags:
                        checked(q, kind)
                    elif stem == "rem":
                        flags.integer_result(q, kind)
                    result = q if stem == "div" else a - q * b
            elif stem in (
                "and",
                "or",
                "xor",
                "not",
                "shl",
                "shr",
                "rol",
                "ror",
                "low_word",
                "high_word",
            ):
                unsigned = a & mask
                if integer_flags and stem in ("shl", "shr", "rol", "ror"):
                    flags.shifted(a, width, b, stem in ("shl", "rol"))
                if stem == "and":
                    result = a & b
                elif stem == "or":
                    result = a | b
                elif stem == "xor":
                    result = a ^ b
                elif stem == "not":
                    result = ~a
                elif stem == "shl":
                    result = unsigned << b
                elif stem == "shr":
                    result = unsigned >> b
                elif stem == "rol":
                    result = (unsigned << b) | (unsigned >> (width - b))
                elif stem == "ror":
                    result = (unsigned >> b) | (unsigned << (width - b))
                elif stem == "low_word":
                    result = a & 65535
                else:
                    result = (a >> 16) & 65535
                result &= mask
                if result >= 1 << (width - 1):
                    result -= 1 << width
            elif stem == "sqrt":
                if a < 0 and integer_flags:
                    flags.overflow = True
                    return Indeterminate("negative integer square root")
                result = math.sqrt(a) if kind == "f32" else math.isqrt(a)
            elif stem == "abs":
                result = abs(a)
            elif stem == "trunc":
                result = math.copysign(float(math.trunc(a)), a)
            elif stem == "log":
                result = math.log10(a)
            elif stem == "ln":
                result = math.log(a)
            elif stem == "exp":
                result = math.exp(a)
            elif stem in ("sin", "cos", "tan", "asin", "acos", "atan"):
                if stem in ("sin", "cos", "tan") and abs(a) > 4096 * math.pi:
                    fail(
                        "numeric arithmetic error: trigonometric argument out of range"
                    )
                result = getattr(math, stem)(a)
            elif stem in ("int_to_real", "dint_to_real"):
                result = a
            elif stem in ("real_to_int", "real_to_dint"):
                result = round(a)
            else:
                fail("unmodeled numeric operation: " + name)
        return (
            flags.integer_result(result, kind)
            if integer_flags
            else checked(result, kind)
        )
    except CompileError:
        if integer_flags or conversion_flags:
            flags.overflow = True
        raise
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        if integer_flags or conversion_flags:
            flags.overflow = True
        fail("numeric arithmetic error: " + str(exc))


def read(words, value):
    if not value.code.startswith("%"):
        return f32(float(value.code)) if value.kind == "f32" else int(value.code)
    kind, index = word_address(value.code)
    raw = words[index]
    if kind == "i16":
        return raw - 65536 if raw >= 32768 else raw
    raw |= words[index + 1] << 16
    if kind == "i32":
        return raw - 4294967296 if raw >= 2147483648 else raw
    return Real32(raw)


def write(words, target, value):
    kind, index = word_address(target)
    value = real32(value) if kind == "f32" else checked(value, kind)
    raw = (
        value.raw
        if kind == "f32"
        else int(value) & 0xFFFFFFFF
    )
    words[index] = raw & 65535
    if kind != "i16":
        words[index + 1] = (raw >> 16) & 65535


def compare(words, parsed, reader=None):
    a, op, b = parsed
    reader = reader or (lambda v: read(words, v))
    left, right = known(reader(a)), known(reader(b))
    if op == "=":
        return left == right
    if op == "<>":
        return left != right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    return left <= right


def cpp(value):
    constant = constant_reference(value.code)
    if constant:
        kind, index, indexed = constant
        fn = {"i16": "word", "i32": "dword", "f32": "real"}[kind]
        return "plc::read_constant_" + fn + ("_indexed(%d,%d)" % (index, indexed) if indexed is not None else "(%d)" % index)
    if system_word(value.code):
        return "plc::read_system_word(17)"
    rtc = rtc_cpp(value.code)
    if rtc is not None:
        return rtc
    sequence = sequence_reference(value.code)
    if sequence:
        if sequence[0] != "DR" or sequence[2] != "S":
            fail("numeric Drum step required")
        return "drum_%d.step()" % sequence[1]
    register = register_reference(value.code)
    if register:
        return "register_%d.%s()" % (register[0], REGISTER_GETTERS[register[1]])
    counter = counter_reference(value.code)
    if counter:
        return "counter_%d.%s()" % (counter[0], COUNTER_GETTERS[counter[1]])
    if is_string(value.code):
        bank, start, count = bit_string(value.code)
        prefix = {"M": "m", "I0.": "input", "Q0.": "output"}[bank]
        return f"plc::read_{prefix}_bits_{value.kind}({start},{count})"
    timer = timer_reference(value.code)
    if timer:
        return "timer_%d.%s()" % (timer[0], GETTERS[timer[1]])
    prop = property_reference(value.code)
    if prop:
        return cpp_name(prop[0]) + ".property(plc::CommProperty::" + ENUMS[prop[1]] + ")"
    status = status_reference(value.code)
    if status:
        return cpp_name(status[0]) + "." + NUM_FIELDS[status[1]][1] + "()"
    if is_indexed(value.code):
        kind, base, index = parse_indexed(value.code)
        fn = {v: k for k, v in READS.items()}[kind]
        return "plc::%s_indexed(%d,%d)" % (fn, base, index)
    if value.code.startswith("%"):
        kind, index = word_address(value.code)
        fn = {v: k for k, v in READS.items()}[kind]
        return "plc::%s(%d)" % (fn, index)
    return value.code + ("f" if value.kind == "f32" else "")


def memory_words_used(program):
    """Union of aliased MW/MD/MF cells and complete communication buffers."""
    text = (
        " ".join(" ".join(r) for r in program.rungs) + " " + " ".join(program.symbols)
    )
    words = set()
    for prefix, index in re.findall(r"%M([WDF])([0-9]+)", text):
        start = int(index)
        words.update(range(start, start + (1 if prefix == "W" else 2)))
    for cfg in program.communications.values():
        words.update(range(cfg.index_data, cfg.index_data + cfg.data_words))
        if cfg.kind == "WRITE_READ_VAR":
            words.update(
                range(cfg.index_data_in, cfg.index_data_in + cfg.read_quantity)
            )
    if has_buffer_writes(program):
        # Dynamic native buffer addresses/counts can reach the full real bank.
        # Frontend requires explicit ownership so private scratch cannot alias.
        words.update(range(8000))
    return words
