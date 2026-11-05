from .model import Program, fail


class Lowerer:
    def __init__(self, reserved=()):
        self.program = Program()
        self.used = set(reserved)
        self.next_bit = 500
        self.constants = {}
        self.origin = {"generated": "lowering"}
        self.origins = []

    def append(self, lines):
        self.program.rungs.append(list(lines))
        self.origins.append(dict(self.origin))

    def bit(self, symbol="temporary"):
        while self.next_bit in self.used:
            self.next_bit += 1
        if self.next_bit >= 1024:
            fail("memory exhausted (compiler temporaries also consume %M)")
        n = self.next_bit
        self.used.add(n)
        self.next_bit += 1
        result = "%M" + str(n)
        self.program.symbols[result] = symbol
        return result

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
                        self.append(["LD %I0.0", "ANDN %I0.0", "ST " + zero])
                    if key == "1":
                        one = self.bit("constant_true")
                        self.constants["1"] = one
                        self.append(["LDN " + self.constants["0"], "ST " + one])
                line = parts[0] + " " + self.constants[key]
            normalized.append(line)
        self.append(normalized)
        if sum(map(len, self.program.rungs)) > 10000:
            fail("experimental instruction budget exceeded")

    def copy(self, value, name="temporary"):
        out = self.bit(name)
        self.rung("LD " + value, "ST " + out)
        return out

    def neg(self, value):
        out = self.bit()
        self.rung("LDN " + value, "ST " + out)
        return out

    def binary(self, operator, a, b):
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
        # Capture before a SET can alter a value used by the RESET branch.
        value = self.copy(value)
        if guard is None:
            self.rung("LD " + value, "ST " + target)
        else:
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
