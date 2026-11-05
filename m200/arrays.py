"""Array layout and safe offset lowering, independent of source text rewriting."""

from dataclasses import dataclass

from .numeric import Number, TYPES, boolean, literal, expect


@dataclass
class Array:
    kind: str
    elements: list
    dynamic: bool


def reference(frontend, array, subscript, env=None):
    lower = frontend.lower
    value = frontend.expr(subscript, env)
    if not isinstance(value, Number):
        signal = lower.copy(boolean(value), "array_boolean_index")
        value = lower.word("i16", "array_boolean_index_word")
        lower.numeric_assign(value, literal(0, "i16"))
        lower.assign(value, literal(1, "i16"), signal)
    elif value.kind not in ("i16", "i32"):
        frontend.error(subscript, "array index requires bool, i16 or i32")
    else:
        value = lower.copy(value, "array_index_snapshot")
    low = lower.comparison(">=", value, Number("literal", "0"))
    high = lower.comparison("<", value, Number("literal", str(len(array.elements))))
    valid = lower.binary("&&", low, high)
    offset = lower.word("i16", "array_word_offset")
    lower.numeric_assign(offset, literal(-32768, "i16"))
    end = lower.new_label()
    lower.jump(end, valid, negate=True)
    old_guard = lower.guard
    lower.guard = None
    try:
        narrow = value if value.kind == "i16" else lower.numeric("low_word", [value])
        stride = 1 if array.kind == "bool" else TYPES[array.kind][1]
        scaled = (
            narrow
            if stride == 1
            else lower.numeric(
                "mul_i16", [narrow, expect(Number("literal", str(stride)), "i16")]
            )
        )
        lower.numeric_assign(offset, scaled)
        lower.label(end)
    finally:
        lower.guard = old_guard
    base = array.elements[0]
    return (
        base + "[" + offset.code + "]"
        if array.kind == "bool"
        else Number(array.kind, base.code + "[" + offset.code + "]")
    )
