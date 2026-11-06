"""Scalar ALU flags; invalid integer data is modeled by scalar_numeric."""

from .model import fail

INTEGER_STEMS = frozenset(
    (
        "copy",
        "add",
        "inc",
        "dec",
        "sub",
        "mul",
        "div",
        "rem",
        "sqrt",
        "abs",
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
        "bcd_to_int",
        "bcd_to_dint",
        "int_to_bcd",
        "dint_to_bcd",
        "concat_words",
        "int_to_dint",
    )
)


class ArithmeticState:
    def __init__(self):
        self.carry = False
        self.overflow = False
        self.float_status = 0

    def floating_error(self, mask):
        self.float_status |= mask
        self.overflow = True

    def clear(self, index):
        if index == 17:
            self.carry = False
        elif index == 18:
            self.overflow = False
        else:
            fail("unsupported arithmetic flag reset")

    def integer_result(self, value, kind):
        if type(value) is not int or kind not in ("i16", "i32"):
            fail("invalid local integer ALU result")
        width = 16 if kind == "i16" else 32
        bound = 1 << (width - 1)
        if not -bound <= value < bound:
            self.overflow = True
        raw = value % (1 << width)
        return raw - (1 << width) if raw >= bound else raw

    def shifted(self, value, width, distance, left):
        self.carry = bool(
            (value % (1 << width)) & (1 << (width - distance if left else distance - 1))
        )
