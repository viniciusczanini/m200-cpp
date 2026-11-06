from .model import Program, fail
from .allocation import Storage
from .indexed import is_indexed, is_bit_indexed
from .numeric import Number, TYPES, boolean, expect, OPS, evaluate, read as read_number
from .arithmetic import ArithmeticState
from .conversions import needs_word_snapshot


class Lowerer:
    def __init__(self, reserved=(), reserved_words=()):
        self.program = Program()
        self.used = set(reserved)
        self.storage = Storage(reserved, reserved_words)
        self.constants = {}
        self.constant_rungs = []
        self.next_label = 0
        self.label_scratch = None
        self.origin = {"generated": "lowering"}
        self.origins = []
        self.used_words = set(reserved_words)
        self.guard = None
        self.instruction_count = 0

    def append(self, lines):
        self.program.rungs.append(list(lines))
        self.origins.append(dict(self.origin))
        self.instruction_count += len(lines)

    def bit(self, symbol="temporary", persistent=False):
        result = self.storage.bit(symbol, persistent)
        self.program.symbols[result] = symbol
        return result

    def array(self, kind, count, symbol, persistent=False):
        values = self.storage.array(kind, count, symbol, persistent)
        for i, value in enumerate(values):
            self.program.symbols[value.code if isinstance(value, Number) else value] = (
                f"{symbol}_{i}"
            )
        return values

    def rung(self, *lines):
        normalized = []
        for line in lines:
            parts = line.split()
            if len(parts) == 2 and parts[1] in ("0", "1"):
                key = parts[1]
                if key not in self.constants:
                    if "0" not in self.constants:
                        zero = self.bit("constant_false")
                        self.constants["0"] = zero
                        self.constant_rungs.append(
                            ["LD %I0.0", "ANDN %I0.0", "ST " + zero]
                        )
                    if key == "1":
                        one = self.bit("constant_true")
                        self.constants["1"] = one
                        self.constant_rungs.append(
                            ["LDN " + self.constants["0"], "ST " + one]
                        )
                line = parts[0] + " " + self.constants[key]
            normalized.append(line)
        self.append(normalized)
        if self.instruction_count > 100000:
            fail(
                "compiler construction instruction budget exceeded; emitted size is not established"
            )

    def new_label(self):
        if self.next_label >= 64:
            fail("native label capacity exceeded (%L0..%L63)")
        label = "%L" + str(self.next_label)
        self.next_label += 1
        return label

    def label(self, label):
        # Native labels must precede a load or a block. An explicit anchor also
        # works for an empty C++ statement or a loop exit at the end of scan().
        if self.label_scratch is None:
            self.label_scratch = self.bit("label_anchor")
        self.rung("LD 0", "ST " + self.label_scratch)
        self.program.rungs[-1].insert(0, label + ":")

    def jump(self, label, condition="1", negate=False):
        # Jump/JMPC is observed in an original Ladder project. Negate the
        # contact instead of guessing a graphical enum for JMPCN or JMP.
        self.rung(("LDN " if negate else "LD ") + condition, "JMPC " + label)

    def copy(self, value, name="temporary"):
        if isinstance(value, Number):
            out = self.word(value.kind, name)
            if is_indexed(value.code) and self.guard is not None:
                self.numeric_assign(out, Number("literal", "0"))
                end = self.new_label()
                self.jump(end, self.guard, negate=True)
                self.numeric_assign(out, value)
                self.label(end)
            else:
                self.numeric_assign(out, value)
            return out
        out = self.bit(name)
        if is_bit_indexed(value) and self.guard is not None:
            self.rung("LD 0", "ST " + out)
            end = self.new_label()
            self.jump(end, self.guard, negate=True)
            self.rung("LD " + value, "ST " + out)
            self.label(end)
        else:
            self.rung("LD " + value, "ST " + out)
        return out

    def neg(self, value):
        boolean(value)
        out = self.bit()
        self.rung("LDN " + value, "ST " + out)
        return out

    def expression_edge(self, op, signal, guard=None):
        boolean(signal)
        out = self.bit("expression_edge_result")
        end = None
        if guard is not None:
            self.assign(out, "0")
            end = self.new_label()
            self.jump(end, guard, negate=True)
        snapshot = self.copy(signal, "expression_edge_input")
        self.rung("LD " + snapshot, op, "ST " + out)
        if end is not None:
            self.label(end)
        return out

    def counter_action(self, index, pin, signal, guard=None):
        end = None
        if guard is not None:
            end = self.new_label()
            self.jump(end, guard, negate=True)
        snapshot = self.copy(boolean(signal), "counter_input")
        self.rung("LD " + snapshot, pin + " %C" + str(index))
        if end is not None:
            self.label(end)

    def binary(self, operator, a, b):
        boolean(a)
        boolean(b)
        if operator == "&&":
            out = self.bit()
            self.rung("LD " + a, "AND " + b, "ST " + out)
            return out
        if operator == "||":
            out = self.bit()
            self.rung("LDN " + a, "ANDN " + b, "ST " + out)
            return self.neg(out)
        if operator in ("^", "!="):
            return self.binary(
                "||",
                self.binary("&&", a, self.neg(b)),
                self.binary("&&", self.neg(a), b),
            )
        if operator == "==":
            return self.neg(self.binary("!=", a, b))
        fail("unsupported boolean operator " + operator)

    def assign(self, target, value, guard=None):
        if isinstance(target, Number):
            self.numeric_assign(target, expect(value, target.kind), guard)
            return
        boolean(value)
        if guard is not None:
            boolean(guard)
        if is_bit_indexed(target) and guard is not None:
            end = self.new_label()
            self.jump(end, guard, negate=True)
            self.assign(target, value)
            self.label(end)
            return
        if guard is None:
            # LD captures the RHS before ST resolves/writes the destination.
            self.rung("LD " + value, "ST " + target)
        elif value in ("0", "1"):
            self.rung("LD " + guard, ("S " if value == "1" else "R ") + target)
        else:
            # Capture before a SET can alter a value used by the RESET branch.
            value = self.copy(value)
            self.rung("LD " + guard, "AND " + value, "S " + target)
            self.rung("LD " + guard, "ANDN " + value, "R " + target)

    def timer(self, index, config, enable):
        out = self.bit("timer_%d_done" % index)
        self.program.timers[index] = config
        self.rung(
            f"BLK %TM{index}",
            "LD " + enable,
            "IN",
            "OUT_BLK",
            "LD Q",
            "ST " + out,
            "END_BLK",
        )
        return out

    def word(self, kind, symbol="numeric_temporary", persistent=False):
        if kind not in TYPES:
            fail("numeric literal requires a type context")
        out = self.storage.word(kind, symbol, persistent)
        self.program.symbols[out.code] = symbol
        return out

    def numeric_assign(self, target, value, guard=None):
        value = expect(value, target.kind)
        if guard is not None:
            boolean(guard)
        if guard is not None and (is_indexed(target.code) or is_indexed(value.code)):
            end = self.new_label()
            self.jump(end, guard, negate=True)
            self.numeric_assign(target, value)
            self.label(end)
            return
        self.rung(
            "LD " + (guard if guard is not None else "1"),
            "[" + target.code + ":=" + value.code + "]",
        )

    def numeric(self, name, values):
        kind, args, token, shape = OPS[name]
        if all(isinstance(v, int) or not v.code.startswith("%") for v in values):
            evaluate(
                name,
                [v if isinstance(v, int) else read_number([], v) for v in values],
                kind,
                flags=ArithmeticState(),
            )
        prepared = []
        for value, argkind in zip(values, args):
            if argkind == "shift":
                prepared.append(str(value))
            else:
                value = expect(value, argkind)
                if is_indexed(value.code):
                    value = self.copy(value, "indexed_operand_snapshot")
                if needs_word_snapshot(token, value.code):
                    value = self.copy(value, "conversion_operand_snapshot")
                # Object operands are required by several native functions.
                if shape != "binary" and not value.code.startswith("%"):
                    value = self.copy(value)
                prepared.append(value.code)
        out = self.word(kind)
        expression = (
            (prepared[0] + " " + token + " " + prepared[1])
            if shape == "binary"
            else token + "(" + ",".join(prepared) + ")"
        )
        self.rung(
            "LD " + (self.guard if self.guard is not None else "1"),
            "[" + out.code + ":=" + expression + "]",
        )
        return out

    def comparison(self, op, a, b):
        if not isinstance(a, Number) or not isinstance(b, Number):
            fail("cannot compare bool and numeric values")
        kind = (
            a.kind if a.kind != "literal" else b.kind if b.kind != "literal" else "i32"
        )
        a, b = expect(a, kind), expect(b, kind)
        if is_indexed(a.code):
            a = self.copy(a, "indexed_comparison_snapshot")
        if is_indexed(b.code):
            b = self.copy(b, "indexed_comparison_snapshot")
        if not a.code.startswith("%"):
            a = self.copy(a)
        out = self.bit("numeric_comparison")
        expression = (
            "["
            + a.code
            + {"==": "=", "!=": "<>", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[op]
            + b.code
            + "]"
        )
        self.rung(
            *(
                ["LD " + self.guard, "AND " + expression]
                if self.guard is not None
                else ["LD " + expression]
            ),
            "ST " + out,
        )
        return out
