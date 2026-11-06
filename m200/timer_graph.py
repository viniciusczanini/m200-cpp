"""Reconcile timer IN/Q ports and Boolean branches against actual ordered IL.

Uses the same bounded BDD/port technique as Counter graphs, with an independent
single-row Timer port map. This is consistency checking, not vendor acceptance.
"""

import re
from collections import defaultdict, deque
from .boolean_bdd import BDD
from .model import address, fail, SYSTEM_RESETS
from .counters import reference as counter_reference
from .timer_il import index as timer_index
from .numeric import comparison
from .indexed import ANY_INDEXED
from .timers import reference as timer_reference
from .native_logic import decode, OPEN, STORES
from .edges import BASE as EDGE_BASE, operand as edge_operand
from .flow import split_label
from .communication import status_reference, BOOL_FIELDS

CONTACTS = {"NormalContact", "NegatedContact", "RisingEdge", "FallingEdge", "Comparison"}
COILS = {"Coil": "ST", "SetCoil": "S", "ResetCoil": "R"}
OPPOSITE = {"Left": "Right", "Right": "Left", "Up": "Down", "Down": "Up"}
DELTAS = {"Left": (0, -1), "Right": (0, 1), "Up": (-1, 0), "Down": (1, 0)}


class State:
    def __init__(self, bdd, current, resources=None):
        self.bdd = bdd
        self.generations = {}
        self.bits = {}
        self.resources = resources
        self.references = set() if current is None else {("TM", current)}
        self.written = False

    def key(self, arg, writable=False, op=None):
        if "[" in arg:
            fail("raw Timer graph comparison/index effects require normalization")
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
                fail("undefined Timer graphical property/configuration")
            if counter[1] not in ("E", "D", "F") or writable:
                fail("unsupported Timer graph property/action")
            return ("C", *counter)
        timer = timer_reference(arg)
        if timer:
            self.references.add(("TM", timer[0]))
            if self.resources is not None and ("TM", timer[0]) not in self.resources:
                fail("undefined timer graphical property/configuration")
            if timer[1] != "Q" or writable:
                fail("unsupported Timer graph timer property/action")
            return ("TM", *timer)
        return address(arg, writable and not (op == "R" and arg in SYSTEM_RESETS))

    def read(self, arg):
        if arg.startswith("["):
            if self.written or ANY_INDEXED.search(arg):
                fail("Timer graph comparison after a write/index requires normalization")
            first, op, second = comparison(arg)
            # IN can change this timer's V/Q, but not arbitrary word memory.
            versions = tuple(
                (i, self.generations.get(i, 0))
                for i in sorted({
                    int(m[1]) for v in (first, second)
                    for m in re.finditer(r"%TM([0-9]+)\.", v.code)
                })
            )
            return self.bdd.atom(("comparison", first.kind, first.code, op, second.code, versions))
        key = self.key(arg)
        if key[0] == "constant":
            return key[1]
        if key[0] == "TM":
            generation = self.generations.get(key[1], 0)
            return self.bdd.atom((key, generation))
        if key not in self.bits:
            self.bits[key] = self.bdd.atom(key)
        return self.bits[key]

    def edge(self, arg, kind):
        return self.bdd.atom(("edge", kind, *edge_operand(arg)))

    def write(self, arg, op, value):
        self.written = True
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


def il_trace(rung, bdd):
    instructions = decode(rung)
    state = State(bdd, None)
    acc, saved, groups, actions = 0, [], [], []
    block = rung[0].startswith("BLK %TM")
    boundary = (rung.index("OUT_BLK") - 1 if "OUT_BLK" in rung else len(instructions)) if block else None
    current = timer_index(rung[0].split(maxsplit=1)[1]) if block else None
    for position, (op, arg) in enumerate(instructions):
        if op == "IN":
            i = timer_index(arg)
            if block and (position >= boundary or i != current):
                fail("Timer input outside its block/input section")
            actions.append(("IN", i, None, acc))
            state.references.add(("TM", i))
            state.generations[i] = state.generations.get(i, 0) + 1
            continue
        if op in STORES:
            if block and position < boundary:
                fail("Timer input side effects require normalization")
            value = bdd.negate(acc) if op == "STN" else acc
            action = "ST" if op == "STN" else op
            key = state.write(arg, action, value)
            actions.append((action, arg, key, value))
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
            value, base = state.edge(arg, op[-1]), EDGE_BASE[op]
        elif op in ("LD", "LDN", "AND", "ANDN", "OR", "ORN", "XOR", "XORN"):
            value = state.read(arg)
            base = op[:-1] if op.endswith("N") else op
            if op.endswith("N"):
                value = bdd.negate(value)
        else:
            fail("raw Timer graph instruction/effects require normalization: " + op)
        acc = value if base == "LD" else bdd.combine({"AND": "&", "OR": "|", "XOR": "^"}[base], acc, value)
    return actions, state.references


class Circuit:
    def __init__(self, elements, targets):
        if len(elements) > 8192:
            fail("Timer graph cell budget exceeded; prototype tool limitation")
        blocks = [e for e in elements if e[0] == "Timer"]
        if not 1 <= len(blocks) <= 5:
            fail("native Timer graph requires one to five blocks")
        block_specs = {}
        for _, descriptor, base, column, connection in blocks:
            i = timer_index(descriptor)
            if i not in targets or i in block_specs or connection not in ("Left", "Left, Right"):
                fail("Timer graphical identity/connections disagree")
            if not 0 <= base < 1024 or not 1 <= column <= 8:
                fail("Timer position/direct-rail wiring outside the known grid model")
            block_specs[i] = (base, column, connection)
        if set(block_specs) != targets:
            fail("Timer IL and graphical block identities disagree")
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
                fail("invalid Timer graph coordinates")
            if (row, col) in occupied:
                fail("overlapping Timer graph cells")
            occupied.add((row, col))
            if (
                any(
                    (typ != "Timer" or (row, col) != (base, column))
                    and row == base and column <= col < column + 2
                    for base, column, _ in block_specs.values()
                )
            ):
                fail("cell overlaps Timer body")
            if typ == "Timer":
                continue
            sides = connection.split(", ")
            if len(set(sides)) != len(sides) or any(s not in OPPOSITE for s in sides):
                fail("unsupported Timer graph connections")
            sides = set(sides)
            if typ in CONTACTS:
                if sides != {"Left", "Right"}:
                    fail("unsupported Timer contact connections")
                left = self.port(row, col, "Left")
                if typ == "Comparison":
                    if col >= 9 or (row, col + 1) in occupied:
                        fail("Timer comparison overlaps/end position")
                    occupied.add((row, col + 1))
                    right = self.port(row, col + 1, "Right")
                    arg = "[" + arg.strip().strip("[]") + "]"
                else:
                    right = self.port(row, col, "Right")
                self.contacts.append((typ, arg, left, right))
                self.cells.append([left, right])
            elif typ in COILS:
                if sides != {"Left"} or col != 10:
                    fail("unsupported Timer coil position/connections")
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
                    fail("unsupported Timer wire cell")
                nodes = [self.port(row, col, side) for side in sorted(sides)]
                for node in nodes[1:]:
                    self.union(nodes[0], node)
                self.cells.append(nodes)
            else:
                fail("unsupported Timer graphical element: " + typ)
        self.inputs = {
            i: self.port(base, column, "Left", optional=True)
            for i, (base, column, _) in block_specs.items()
        }
        self.outputs = {
            i: self.port(base, column + 1, "Right", optional=True)
            for i, (base, column, _) in block_specs.items()
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
                fail("unpaired Timer graph wire/contact port")
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
        for i, (_, _, connection) in block_specs.items():
            if (i in self.outputs) != (connection == "Left, Right"):
                fail("Timer Q port connection disagrees with actual output wiring")
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
            fail("overlapping Timer graph port")
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
    bdd = BDD()
    actions, referenced = il_trace(rung, bdd)
    inputs = [arg for op, arg, _, _ in actions if op == "IN"]
    if not inputs or len(set(inputs)) != len(inputs):
        fail("raw Timer graph needs distinct IN identities; repeated sites require normalization")
    targets = set(inputs)
    if resources is not None and any(("TM", i) not in resources for i in targets):
        fail("undefined Timer graphical configuration")
    circuit = Circuit(elements, targets)
    if set(circuit.inputs) != targets:
        fail("Timer IL and graphical input pins disagree")
    outputs = [record for record in actions if record[0] != "IN"]
    if len(circuit.coils) != len(outputs):
        fail("Timer IL and graphical output counts disagree")
    state = State(bdd, None, referenced if resources is None else resources)
    for (op, arg, _), (expected, _, key, _) in zip(circuit.coils, outputs):
        if op != expected or state.key(arg, True, op) != key:
            fail("Timer IL and graphical output order/targets disagree")
    stages = []
    coils = iter(circuit.coils)
    for op, arg, _, condition in actions:
        root = circuit.inputs[arg] if op == "IN" else next(coils)[2]
        stages.append((root, condition, op, arg))
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
        fail("Timer graph contains unused/unpowered components")
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
            fail("Timer graph propagation budget exceeded; prototype tool limitation")
        _, _, left, right = circuit.contacts[i]
        if i in conditions:
            add(right, bdd.combine("&", power[left], conditions[i]))

    for root in circuit.rails:
        add(root, 1)

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
            fail("Timer IL and Ladder graphical conditions disagree")
        if op == "IN":
            state.generations[arg] = state.generations.get(arg, 0) + 1
            if arg in circuit.outputs:
                add(circuit.outputs[arg], bdd.atom((("TM", arg, "Q"), state.generations[arg])))
                propagate()
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
