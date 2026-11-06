"""Reconcile known Counter Ladder ports with an ordered symbolic IL trace."""

from collections import defaultdict, deque
from .boolean_bdd import BDD
from .model import address, fail
from .counters import reference as counter_reference, index as counter_index
from .timers import reference as timer_reference
from .native_logic import decode, OPEN, STORES
from .edges import BASE as EDGE_BASE, operand as edge_operand
from .flow import split_label
from .communication import status_reference, BOOL_FIELDS

PIN_ROWS = {"R": 0, "S": 1, "CU": 2, "CD": 3}
CONTACTS = {"NormalContact", "NegatedContact", "RisingEdge", "FallingEdge"}
COILS = {"Coil": "ST", "SetCoil": "S", "ResetCoil": "R"}
OPPOSITE = {"Left": "Right", "Right": "Left", "Up": "Down", "Down": "Up"}
DELTAS = {"Left": (0, -1), "Right": (0, 1), "Up": (-1, 0), "Down": (1, 0)}


class State:
    def __init__(self, bdd, current, resources=None):
        self.bdd = bdd
        self.current = current
        self.generation = 0
        self.bits = {}
        self.resources = resources
        self.references = {("C", current)}

    def key(self, arg, writable=False, op=None):
        if "[" in arg:
            fail("raw Counter graph comparison/index effects require normalization")
        status = status_reference(arg)
        if status:
            resource = ("COMM", status[0])
            self.references.add(resource)
            if self.resources is not None and resource not in self.resources:
                fail("undefined communication graphical status/configuration")
            if writable or status[1] not in BOOL_FIELDS:
                fail("communication graphical status must be read-only BOOL")
            return ("COMM", *status)
        counter = counter_reference(arg)
        if counter:
            self.references.add(("C", counter[0]))
            if self.resources is not None and ("C", counter[0]) not in self.resources:
                fail("undefined Counter graphical property/configuration")
            if counter[1] not in ("E", "D", "F") or writable:
                fail("unsupported Counter graph property/action")
            return ("C", *counter)
        timer = timer_reference(arg)
        if timer:
            self.references.add(("TM", timer[0]))
            if self.resources is not None and ("TM", timer[0]) not in self.resources:
                fail("undefined timer graphical property/configuration")
            if timer[1] != "Q" or writable:
                fail("unsupported Counter graph timer property/action")
            return ("TM", *timer)
        return address(arg, writable and not (op == "R" and arg == "%S20"))

    def read(self, arg):
        key = self.key(arg)
        if key[0] == "constant":
            return key[1]
        if key[0] == "C":
            generation = self.generation if key[1] == self.current else 0
            return self.bdd.atom((key, generation))
        if key not in self.bits:
            self.bits[key] = self.bdd.atom(key)
        return self.bits[key]

    def edge(self, arg, kind):
        return self.bdd.atom(("edge", kind, *edge_operand(arg)))

    def write(self, arg, op, value):
        key = self.key(arg, True, op)
        if op == "ST":
            self.bits[key] = value
        elif op == "S":
            self.bits[key] = self.bdd.combine("|", self.read(arg), value)
        else:
            self.bits[key] = self.bdd.combine(
                "&", self.read(arg), self.bdd.negate(value)
            )
        return key


def il_trace(rung, bdd, current):
    body = decode(rung)
    state = State(bdd, current)
    acc = 0
    saved = []
    groups = []
    inputs = []
    outputs = []
    boundary = rung.index("OUT_BLK") - 1 if "OUT_BLK" in rung else len(body)
    for position, (op, arg) in enumerate(body):
        if op in PIN_ROWS and arg.startswith("%C") and "." not in arg:
            if position >= boundary or counter_index(arg) != current:
                fail("raw Counter graph requires its own ordered input actions")
            if inputs and PIN_ROWS[op] <= PIN_ROWS[inputs[-1][0]]:
                fail("raw Counter input order/repetition requires normalization")
            inputs.append((op, acc))
            state.generation += 1
            continue
        if op in STORES:
            if position < boundary:
                fail("raw Counter input side effects require normalization")
            value = bdd.negate(acc) if op == "STN" else acc
            action = "ST" if op == "STN" else op
            key = state.write(arg, action, value)
            outputs.append((action, arg, key, value))
            continue
        if op == "MPS":
            saved.append(acc)
            continue
        if op == "MRD":
            acc = saved[-1]
            continue
        if op == "MPP":
            acc = saved.pop()
            continue
        if op == "N":
            acc = bdd.negate(acc)
            continue
        if op in OPEN:
            groups.append((op, acc))
            acc = state.read(arg)
            continue
        if op == ")":
            operator, previous = groups.pop()
            acc = bdd.combine("&" if operator == "AND(" else "|", previous, acc)
            continue
        if op in EDGE_BASE:
            value = state.edge(arg, op[-1])
            base = EDGE_BASE[op]
        elif op in ("LD", "LDN", "AND", "ANDN", "OR", "ORN", "XOR", "XORN"):
            value = state.read(arg)
            base = op[:-1] if op.endswith("N") else op
            if op.endswith("N"):
                value = bdd.negate(value)
        else:
            fail("raw Counter graph instruction/effects require normalization: " + op)
        acc = (
            value
            if base == "LD"
            else bdd.combine({"AND": "&", "OR": "|", "XOR": "^"}[base], acc, value)
        )
    return inputs, outputs, state.references


class Circuit:
    def __init__(self, elements, target):
        if len(elements) > 8192:
            fail("Counter graph cell budget exceeded; prototype tool limitation")
        blocks = [e for e in elements if e[0] == "Counter"]
        if len(blocks) != 1:
            fail("Counter graph requires one block")
        _, descriptor, base, column, connection = blocks[0]
        if descriptor != target or connection not in ("Left", "Left, Right"):
            fail("Counter graphical identity/connections disagree")
        if not 0 <= base <= 1020 or not 1 <= column <= 8:
            fail("Counter position/direct-rail wiring outside verified grid model")
        self.parent = []
        self.rank = []
        self.ports = {}
        self.optional = set()
        self.matched = set()
        self.rails = set()
        self.cells = []
        self.contacts = []
        self.coils = []
        occupied = set()
        for typ, arg, row, col, connection in elements:
            if (
                type(row) is not int
                or type(col) is not int
                or not 0 <= row < 1024
                or not 0 <= col <= 10
            ):
                fail("invalid Counter graph coordinates")
            if (row, col) in occupied:
                fail("overlapping Counter graph cells")
            occupied.add((row, col))
            if (
                typ != "Counter"
                and base <= row < base + 4
                and column <= col < column + 2
            ):
                fail("cell overlaps Counter body")
            if typ == "Counter":
                continue
            sides = connection.split(", ")
            if len(set(sides)) != len(sides) or any(s not in OPPOSITE for s in sides):
                fail("unsupported Counter graph connections")
            sides = set(sides)
            if typ in CONTACTS:
                if sides != {"Left", "Right"}:
                    fail("unsupported Counter contact connections")
                left = self.port(row, col, "Left")
                right = self.port(row, col, "Right")
                self.contacts.append((typ, arg, left, right))
                self.cells.append([left, right])
            elif typ in COILS:
                if sides != {"Left"} or col != 10:
                    fail("unsupported Counter coil position/connections")
                left = self.port(row, col, "Left")
                self.coils.append((row, col, COILS[typ], arg, left))
                self.cells.append([left])
            elif typ in ("Line", "VerticalLine"):
                if (
                    arg
                    or len(sides) < 2
                    or (typ == "Line" and not sides & {"Left", "Right"})
                    or (typ == "VerticalLine" and not sides & {"Up", "Down"})
                ):
                    fail("unsupported Counter wire cell")
                nodes = [self.port(row, col, side) for side in sorted(sides)]
                for node in nodes[1:]:
                    self.union(nodes[0], node)
                self.cells.append(nodes)
            else:
                fail("unsupported Counter graphical element: " + typ)
        self.inputs = {
            pin: self.port(base + offset, column, "Left", optional=True)
            for pin, offset in PIN_ROWS.items()
        }
        self.outputs = {
            field: self.port(base + offset, column + 1, "Right", optional=True)
            for field, offset in {"E": 0, "D": 1, "F": 2}.items()
        }
        for (row, col, side), node in self.ports.items():
            dr, dc = DELTAS[side]
            other = self.ports.get((row + dr, col + dc, OPPOSITE[side]))
            if side == "Left" and col == 0:
                self.rails.add(node)
                self.matched.add(node)
            elif other is not None:
                self.union(node, other)
                self.matched.add(node)
            elif node not in self.optional:
                fail("unpaired Counter graph wire/contact port")
        self.inputs = {
            pin: self.find(node)
            for pin, node in self.inputs.items()
            if node in self.matched
        }
        self.outputs = {
            field: self.find(node)
            for field, node in self.outputs.items()
            if node in self.matched
        }
        self.rails = {self.find(n) for n in self.rails}
        self.contacts = [
            (typ, arg, self.find(left), self.find(right))
            for typ, arg, left, right in self.contacts
        ]
        self.coils = [
            (op, arg, self.find(n)) for _, _, op, arg, n in sorted(self.coils)
        ]
        self.cells = [[self.find(n) for n in cell] for cell in self.cells]

    def port(self, row, col, side, optional=False):
        key = (row, col, side)
        if key in self.ports:
            fail("overlapping Counter graph port")
        n = len(self.parent)
        self.parent.append(n)
        self.rank.append(0)
        self.ports[key] = n
        if optional:
            self.optional.add(n)
        return n

    def find(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left == right:
            return
        if self.rank[left] < self.rank[right]:
            left, right = right, left
        self.parent[right] = left
        if self.rank[left] == self.rank[right]:
            self.rank[left] += 1


def verify(elements, lines, resources=None):
    _, rung = split_label(lines)
    rung = [" ".join(line.split()) for line in rung]
    if not rung or not rung[0].startswith("BLK %C"):
        fail("Counter graph requires its native block")
    target = rung[0].split(maxsplit=1)[1]
    current = counter_index(target)
    bdd = BDD()
    inputs, outputs, referenced = il_trace(rung, bdd, current)
    if resources is not None and ("C", current) not in resources:
        fail("undefined Counter graphical configuration")
    circuit = Circuit(elements, target)
    if list(circuit.inputs) != [pin for pin, _ in inputs]:
        fail("Counter IL and graphical input pins disagree")
    if len(circuit.coils) != len(outputs):
        fail("Counter IL and graphical output counts disagree")
    state = State(bdd, current, referenced if resources is None else resources)
    for (op, arg, _), (expected, _, key, _) in zip(circuit.coils, outputs):
        if op != expected or state.key(arg, True, op) != key:
            fail("Counter IL and graphical output order/targets disagree")
    stages = [(circuit.inputs[pin], condition, pin, None) for pin, condition in inputs]
    stages += [
        (root, record[3], op, arg)
        for (op, arg, root), record in zip(circuit.coils, outputs)
    ]
    forward = defaultdict(list)
    backward = defaultdict(list)
    for i, (_, _, left, right) in enumerate(circuit.contacts):
        forward[left].append(i)
        backward[right].append(left)
    phases = {}
    pending = deque()
    for i, (root, _, _, _) in enumerate(stages):
        if root not in phases or i < phases[root]:
            phases[root] = i
            pending.append(root)
    while pending:
        root = pending.popleft()
        for left in backward[root]:
            if left not in phases or phases[root] < phases[left]:
                phases[left] = phases[root]
                pending.append(left)
    sources = set(circuit.rails) | set(circuit.outputs.values())
    reachable = set(sources)
    pending = deque(sources)
    while pending:
        root = pending.popleft()
        for i in forward[root]:
            right = circuit.contacts[i][3]
            if right not in reachable:
                reachable.add(right)
                pending.append(right)
    if any(
        root not in reachable or root not in phases
        for cell in circuit.cells
        for root in cell
    ):
        fail("Counter graph contains unused/unpowered components")
    by_phase = defaultdict(list)
    for i, (_, _, _, right) in enumerate(circuit.contacts):
        by_phase[phases[right]].append(i)
    power = defaultdict(int)
    conditions = {}
    pending = deque()
    work = 0

    def add(root, value):
        merged = bdd.combine("|", power[root], value)
        if merged != power[root]:
            power[root] = merged
            pending.append(root)

    def transfer(i):
        nonlocal work
        work += 1
        if work > 1000000:
            fail("Counter graph propagation budget exceeded; prototype tool limitation")
        _, _, left, right = circuit.contacts[i]
        if i in conditions:
            add(right, bdd.combine("&", power[left], conditions[i]))

    for root in circuit.rails:
        add(root, 1)
    for field, root in circuit.outputs.items():
        add(root, bdd.atom((("C", current, field), len(inputs))))

    def propagate():
        while pending:
            for i in forward[pending.popleft()]:
                transfer(i)

    propagate()
    for phase, (root, expected, op, arg) in enumerate(stages):
        for i in by_phase[phase]:
            typ, descriptor, _, _ = circuit.contacts[i]
            value = (
                state.edge(descriptor, "R" if typ == "RisingEdge" else "F")
                if typ in ("RisingEdge", "FallingEdge")
                else state.read(descriptor)
            )
            conditions[i] = bdd.negate(value) if typ == "NegatedContact" else value
            transfer(i)
        propagate()
        if power[root] != expected:
            fail("Counter IL and Ladder graphical conditions disagree")
        if phase < len(inputs):
            state.generation += 1
        else:
            state.write(arg, op, power[root])
    return {
        "method": "exact ordered Boolean/port reconciliation",
        "inputs": len(inputs),
        "outputs": len(outputs),
        "contacts": len(circuit.contacts),
        "bdd_nodes": len(bdd.nodes) - 2,
        "atoms": len(bdd.atoms),
    }
