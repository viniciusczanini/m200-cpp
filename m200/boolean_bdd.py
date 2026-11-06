"""Exact, bounded Boolean algebra with iterative reduced ordered BDDs."""

from .model import fail


class BDD:
    def __init__(self, *, node_limit=65536, operation_limit=262144):
        if (
            type(node_limit) is not int
            or node_limit < 1
            or type(operation_limit) is not int
            or operation_limit < 1
        ):
            fail("invalid Boolean proof tool budget")
        self.nodes = [None, None]
        self.unique = {}
        self.atoms = {}
        self.names = {}
        self.cache = {}
        self.node_limit = node_limit
        self.operation_limit = operation_limit

    def node(self, variable, low, high):
        if low == high:
            return low
        key = (variable, low, high)
        if key in self.unique:
            return self.unique[key]
        if len(self.nodes) - 2 >= self.node_limit:
            fail(
                "Boolean proof node budget exceeded; prototype tool limitation, not a PLC limit"
            )
        result = len(self.nodes)
        self.nodes.append(key)
        self.unique[key] = result
        return result

    def atom(self, key):
        if key not in self.atoms:
            # New variables precede existing ones; long incremental chains stay
            # compact without changing any previously established ordering.
            variable = -len(self.atoms)
            self.names[variable] = key
            self.atoms[key] = self.node(variable, 0, 1)
        return self.atoms[key]

    @staticmethod
    def key(op, a, b):
        return (op, a, b) if a <= b else (op, b, a)

    @staticmethod
    def simple(op, a, b):
        if a == b:
            return 0 if op == "^" else a
        if op == "&":
            if a == 0:
                return 0
            if a == 1:
                return b
        elif op == "|":
            if a == 0:
                return b
            if a == 1:
                return 1
        elif op == "^" and a == 0:
            return b
        return None

    def combine(self, op, a, b):
        if op not in ("&", "|", "^"):
            fail("unknown Boolean proof operator")
        start = self.key(op, a, b)
        pending = [start]
        while pending:
            key = pending[-1]
            if key in self.cache:
                pending.pop()
                continue
            operation, left, right = key
            if len(self.cache) >= self.operation_limit:
                fail(
                    "Boolean proof operation budget exceeded; prototype tool limitation, not a PLC limit"
                )
            result = self.simple(operation, left, right)
            if result is not None:
                self.cache[key] = result
                pending.pop()
                continue
            if len(self.cache) >= self.operation_limit:
                fail(
                    "Boolean proof operation budget exceeded; prototype tool limitation, not a PLC limit"
                )
            lv = self.nodes[left][0] if left > 1 else float("inf")
            rv = self.nodes[right][0] if right > 1 else float("inf")
            variable = min(lv, rv)
            ll, lh = self.nodes[left][1:] if lv == variable else (left, left)
            rl, rh = self.nodes[right][1:] if rv == variable else (right, right)
            low = self.key(operation, ll, rl)
            high = self.key(operation, lh, rh)
            if low not in self.cache:
                pending.append(low)
                continue
            if high not in self.cache:
                pending.append(high)
                continue
            self.cache[key] = self.node(variable, self.cache[low], self.cache[high])
            pending.pop()
        return self.cache[start]

    def negate(self, node):
        return self.combine("^", node, 1)

    def value(self, node, environment):
        while node > 1:
            variable, low, high = self.nodes[node]
            node = high if environment[self.names[variable]] else low
        return bool(node)
